"""Offline session-grouped baseline; no acquisition, discovery or parameter search.

Reuses LLTF52 extraction and the attributed RuView head without changing them.
Synthetic audit answers are fixtures, never native acquisition audit results.
"""
from collections import Counter
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import re

from eligible_presence_features import extract_eligible_window
from ruview_presence_port import Anchor, CONTRACT, PresenceSpecialistPort, RUVIEW_COMMIT

SCHEMA = 'tesis-edge-labeled-sessions-1'
ROOT = Path(__file__).resolve().parents[1]
MIN_GROUPS = {'train': 2, 'evaluation': 2}


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def safe_path(path):
    path = Path(path)
    require(not re.search(r'C0[456]', str(path), re.I), 'C04-C06 permanecen reservadas')
    resolved = path.resolve()
    require(not re.search(r'C0[456]', str(resolved), re.I), 'C04-C06 permanecen reservadas')
    require(not str(resolved).startswith('/dev/'), 'No se admiten dispositivos')
    return resolved


def sha(path):
    return hashlib.sha256(safe_path(path).read_bytes()).hexdigest()


def load_json(path):
    return json.loads(safe_path(path).read_text(encoding='utf-8'))


def checked_file(base, entry):
    path = safe_path(base / entry['path'])
    require(path.is_relative_to(base), 'La fuente debe estar dentro del bundle')
    require(sha(path) == entry['sha256'], 'SHA-256 de fuente distinto')
    return path


def validate_manifest(manifest, base):
    require(manifest.get('schema') == SCHEMA, 'Esquema de sesiones desconocido')
    kind = manifest.get('evidence_type')
    require(kind in ('synthetic_fixture', 'physical_capture'), 'Tipo de evidencia explícito requerido')
    require(manifest.get('receiver') == 'RX-02', 'Esta revisión admite solo RX-02, sin fusión')
    require(isinstance(manifest.get('scope'), str) and bool(manifest['scope'].strip()), 'Ámbito requerido')
    sessions = manifest.get('sessions')
    require(isinstance(sessions, list) and bool(sessions), 'Sesiones completas requeridas')
    ids, bundles, groups = set(), set(), {}
    for session in sessions:
        sid, group, split = (session.get(k) for k in ('id', 'partition_group', 'split'))
        require(all(isinstance(s, str) and s.strip() for s in (sid, group)), 'ID/grupo requeridos')
        require(split in MIN_GROUPS, 'Partición train/evaluation requerida')
        require(sid not in ids, 'ID de sesión duplicado')
        require(not re.search(r'C0[456]', sid + ' ' + group, re.I), 'Reserva prohibida')
        require(group not in groups or groups[group] == split, 'Fuga de grupo entre entrenamiento y evaluación')
        bundle = safe_path(base / session['bundle'])
        require(bundle.is_relative_to(base), 'Bundle fuera de la carpeta del manifiesto')
        require(bundle not in bundles, 'Bundle duplicado o alias de sesión')
        if kind == 'synthetic_fixture':
            require(sid.startswith('SYNTHETIC-'), 'ID sintético explícito requerido')
        ids.add(sid); bundles.add(bundle); groups[group] = split
    for split, minimum in MIN_GROUPS.items():
        require(sum(s == split for s in groups.values()) >= minimum,
                f'Se requieren al menos {minimum} grupos completos en {split}')
    return sessions


def read_synthetic(bundle):
    source = load_json(bundle / 'sources.json')
    raw = checked_file(bundle, source['raw']).read_bytes()
    audit = load_json(checked_file(bundle, source['audit']))
    require(audit.get('native_audit_executed') is False and
            audit['state'].get('evidence_type') == 'synthetic_fixture',
            'Fixture de auditoría sintético explícito requerido')
    from consolidar_rx02_c01 import frame_from_reference
    profile = source['firmware_ltf_config']
    traces = {}
    for window in audit['state']['windows']:
        refs = window['receivers']['RX-02']['included_line_references']
        traces[window['id']] = [frame_from_reference(raw, ref, profile)[0] for ref in refs]
    return audit, traces, {name: sha(bundle / name) for name in
                           ('sources.json', source['raw']['path'], source['audit']['path'])}


def read_physical(bundle, split, scope):
    """Future audited bundles only; existing exploratory plans cannot train.

    The acquisition contract must prospectively permit the intended use. This
    loader does not grant that permission or alter historical plans/rejections.
    """
    plan = load_json(bundle / 'plan.json')
    use = 'training' if split == 'train' else 'evaluation'
    require(plan.get('permitted_uses', {}).get(use) is True,
            'El plan original no permite ' + use + '; no promover datos exploratorios')
    if split == 'train':
        require(plan['permitted_uses'].get('calibration') is True,
                'El plan original no permite calibration')
    require(plan.get('edge_scope') == scope, 'Ámbito de receptor/geometría no coincide')
    require(plan.get('future_partition') == 'development_future',
            'Solo desarrollo autorizado; la reserva final no se consulta')
    from presence_rx02_journal import audit_rx02
    from rx02_c03.checkpoint import audit_c03_checkpoints
    from consolidar_c03_comparar_c01 import describe_windows
    audit = (audit_c03_checkpoints(bundle) if plan.get('persistence_revision') else audit_rx02(bundle))
    state = audit['state']
    require(state.get('evidence_type') == 'physical_capture', 'No mezclar evidencia real y sintética')
    require(state['connection']['quality_ok'] is True and not state.get('fatal'),
            'Se requiere calidad estricta aceptada de la conexión completa')
    require(all(c['confirmed'] and not c['error'] for c in state['closed'].values()) and
            set(state['closed']) == {'RX-02'}, 'Cierre RX-02 no confirmado')
    _, _, by_condition = describe_windows(bundle, audit)
    traces = {w['id']: by_condition[w['condition']] for w in state['windows']}
    return audit, traces, {'manifest.json': sha(bundle / 'manifest.json')}


def read_dataset(path):
    path = safe_path(path)
    manifest = load_json(path)
    sessions = validate_manifest(manifest, path.parent)
    records, inputs, seen_slots = [], {str(path): sha(path)}, set()
    for session in sorted(sessions, key=lambda s: s['id']):
        bundle = safe_path(path.parent / session['bundle'])
        if manifest['evidence_type'] == 'synthetic_fixture':
            audit, traces, sources = read_synthetic(bundle)
        else:
            audit, traces, sources = read_physical(bundle, session['split'], manifest['scope'])
        state = audit['state']
        require(state['connection_id'] == session['id'] and state['partition_group'] == session['partition_group'],
                'Identidad/grupo difiere de la fuente original')
        require(state.get('scope') == manifest['scope'] if manifest['evidence_type'] == 'synthetic_fixture'
                else True, 'Ámbito sintético distinto')
        windows = state['windows']
        require(len(windows) == 2 and {w['condition'] for w in windows} == {'E', 'S'},
                'Cada conexión debe conservar E y S completas')
        membership = set()
        for window in windows:
            require(window['id'] not in seen_slots, 'Ventana duplicada')
            seen_slots.add(window['id'])
            refs = window['receivers']['RX-02']['included_line_references']
            lines = [r['line_1based'] for r in refs]
            require(len(set(lines)) == len(lines) and not membership.intersection(lines),
                    'Muestras repetidas o compartidas entre ventanas')
            membership.update(lines)
            feature = extract_eligible_window(audit, window['id'], traces[window['id']])
            records.append(dict(session_id=session['id'], partition_group=session['partition_group'],
                split=session['split'], slot_id=window['id'], truth='vacio' if window['condition'] == 'E' else 'ocupado',
                features=feature['features'], feature_status=feature['feature_status'], reasons=feature['reasons'],
                connection_full=feature.get('connection_full'), input_rows=len(refs)))
        inputs.update({str(bundle / name): digest for name, digest in sources.items()})
    return manifest, records, inputs


def evaluate(manifest, records):
    """One decision per original E/S window; no row shuffling or model search."""
    train = [r for r in records if r['split'] == 'train']
    queries = [r for r in records if r['split'] == 'evaluation']
    require(all(r['features'] is not None for r in train), 'Entrenamiento incompleto: no se eliminan ventanas')
    anchors = [Anchor('Empty' if r['truth'] == 'vacio' else 'Sit',
                      r['features']['mean'], r['features']['variance']) for r in train]
    model = PresenceSpecialistPort.train(anchors)
    usable = model is not None and math.isfinite(model.occupied_var) and math.isfinite(model.empty_mean)
    usable = usable and (model.mean_dist_threshold is None or math.isfinite(model.mean_dist_threshold))
    usable = usable and (math.isfinite(model.threshold) or model.mean_dist_threshold is not None)
    matrix = {label: dict(vacio=0, ocupado=0, abstencion=0) for label in ('vacio', 'ocupado')}
    results = []
    for row in queries:
        result = dict(row, prediction='abstencion', confidence_margin=None)
        if row['features'] is None:
            result['abstention_reason'] = 'required_features_incomplete'
        elif not usable:
            result['abstention_reason'] = 'no_separable_model'
        else:
            reading = model.infer(row['features']['mean'], row['features']['variance'])
            result.update(prediction='ocupado' if reading['value'] else 'vacio',
                          confidence_margin=reading['confidence_margin'], abstention_reason=None)
        matrix[row['truth']][result['prediction']] += 1
        results.append(result)
    tn, fp = matrix['vacio']['vacio'], matrix['vacio']['ocupado']
    fn, tp = matrix['ocupado']['vacio'], matrix['ocupado']['ocupado']
    total = len(results); decided = tn + fp + fn + tp
    ratio = lambda a, b: a / b if b else None
    by_session = {}
    for result in results:
        counts = by_session.setdefault(result['session_id'], Counter())
        counts['windows'] += 1
        counts['abstentions'] += result['prediction'] == 'abstencion'
        counts['false_alarms'] += result['truth'] == 'vacio' and result['prediction'] == 'ocupado'
        counts['false_negatives'] += result['truth'] == 'ocupado' and result['prediction'] == 'vacio'
    serialized = {k: v if v is None or math.isfinite(v) else None
                  for k, v in asdict(model).items()} if model else None
    return dict(schema='tesis-edge-evaluation-1', evidence_type=manifest['evidence_type'],
        title='EVALUACIÓN SINTÉTICA · SIN VALIDEZ FÍSICA' if manifest['evidence_type'] == 'synthetic_fixture'
              else 'EVALUACIÓN OFFLINE DE DESARROLLO · SIN VALIDACIÓN MIPYME',
        receiver=manifest['receiver'], scope=manifest['scope'], contract=CONTRACT,
        ruview=dict(commit=RUVIEW_COMMIT, license='MIT', provenance='vendor/ruview/presence/PROVENANCE.json'),
        policy=dict(unit='original_30s_window', split_unit='whole_session_partition_group',
            empty_anchor='first Empty in session_id lexical order; remaining Empty anchors not used by upstream head',
            occupied_anchor='unweighted average of all Sit anchors',
            model_selection='none', resampling=False, confidence_is_probability=False,
            min_groups=MIN_GROUPS, final_reserve_opened=False),
        partitions={split: sorted({r['partition_group'] for r in records if r['split'] == split})
                    for split in MIN_GROUPS},
        model=dict(status='trained' if usable else 'no_separable_model', parameters=serialized,
                   empty_anchor_slot=next(r['slot_id'] for r in train if r['truth'] == 'vacio'),
                   training_windows=len(train)),
        confusion_matrix=dict(rows='truth', columns=['vacio', 'ocupado', 'abstencion'], counts=matrix),
        metrics=dict(evaluation_windows=total, decided_windows=decided, abstentions=total-decided,
            coverage=ratio(decided, total), accuracy_decided=ratio(tn+tp, decided),
            correct_over_all_windows=ratio(tn+tp, total), false_alarms=fp, false_negatives=fn,
            false_alarm_rate_decided_empty=ratio(fp, fp+tn),
            false_alarm_rate_all_empty=ratio(fp, sum(matrix['vacio'].values())),
            abstention_rate=ratio(total-decided, total)),
        by_session=by_session, training=train, predictions=results)


def markdown(report):
    m = report['metrics']; matrix = report['confusion_matrix']['counts']
    lines = ['# ' + report['title'], '',
        'Prueba de integración de software. No estima exactitud física ni desempeño en una MIPYME.', '',
        f"Contrato: `{report['contract']}`. RuView `{RUVIEW_COMMIT}` (MIT).", '',
        'Partición por conexiones completas; E y S de una conexión siempre juntas.', '']
    for split, groups in report['partitions'].items():
        lines.append(f"- {split}: {', '.join(groups)}")
    lines += ['', '| Verdad / predicción | Vacío | Ocupado | Abstención |',
              '| --- | ---: | ---: | ---: |']
    for label, name in (('vacio', 'Vacío'), ('ocupado', 'Ocupado')):
        r = matrix[label]; lines.append(f"| {name} | {r['vacio']} | {r['ocupado']} | {r['abstencion']} |")
    lines += ['', '| Métrica | Valor |', '| --- | ---: |']
    lines.extend(f'| {name} | {value} |' for name, value in m.items())
    lines += ['', 'La tasa de falsas alarmas decididas es FP/(FP+TN); el otro denominador incluye',
        'las abstenciones en vacío. Los cocientes sin denominador se guardan como null.',
        'La cobertura y los aciertos sobre todas las ventanas impiden ocultar abstenciones.', '',
        'El port original usa la primera ancla Empty y promedia las ocupadas. Se fija el orden',
        'lexicográfico por ID antes de leer evaluación. No se seleccionan umbrales con evaluación.',
        'El margen de confianza no es una probabilidad. Una máscara incompleta invalida toda',
        'la característica; un modelo no separable produce abstención.', '',
        'Ver JSON para características, rechazos conservados, decisiones y métricas por sesión.',
        'No se han leído C04–C06 ni abierto UART. No hay adquisición o detector en vivo.', '']
    return '\n'.join(lines)
