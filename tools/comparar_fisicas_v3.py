#!/usr/bin/env python3
"""Consolidate/describe two existing v3 windows; never acquires or selects T0.

Inputs and plots are isolated by Bubblewrap. Raw matrices remain local. Exit 0
verifies this descriptive analysis, not the globally rejected acquisitions.
"""
import argparse
from collections import Counter
import importlib.metadata
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'src'))
import consolidar_fisica_v3 as original
from canonical_csi import canonicalize
from controlled_protocol import AVAILABILITY_V3, STOP_POLICY_V2
from validate_capture import audit_capture

require, load, ref, digest = original.require, original.load, original.ref, original.digest
PLOT_RUNTIME = ROOT / '.tools/comparacion-v3-python-v2'
SESSIONS = {
    'sentado': {
        'base': 'results/local/preparacion-dual-v3-20261026T000758Z',
        'run': 'captura-dual-v3-20261026T000758Z-intento-unico',
        'control': 'control/ejecucion-autorizada-v3-intento01',
        'analysis': 'analisis-v3-intento-unico',
        'bundle_sha256': '156f71ffe1e19a5a6c55596aab235979d154130e9bc73bee1a099dfb1ac8110b',
    },
    'libre': {
        'base': 'results/local/preparacion-dual-v3-movimiento-libre-20261026T035823Z',
        'run': 'captura-dual-v3-movimiento-libre-20261026T035823Z-intento-unico',
        'control': 'control/ejecucion-autorizada-intento01',
        'analysis': 'analisis-movimiento-libre-intento-unico',
        'bundle_sha256': '0957e3f98ea4cf5c72c780504eca296dec361b49d7dad92533c799e1664f2999',
    },
}
LABELS = {'sentado': 'Sentada (declarada)', 'libre': 'Libre (inicio incierto)'}
COLORS = {'sentado': '#1764ab', 'libre': '#c7520a'}
RX = ('RX-01', 'RX-02')
LTF = ('LLTF', 'HT-LTF')
METADATA_FIELDS = ('mac', 'rate', 'sig_mode', 'mcs', 'bandwidth', 'channel',
                   'secondary_channel', 'stbc', 'fec_coding', 'sgi', 'smoothing',
                   'not_sounding', 'aggregation', 'noise_floor', 'ant', 'sig_len',
                   'rx_state', 'len', 'first_word_invalid')


def stats(values):
    """Population descriptions of actual values, equal weight per observation."""
    require(all(math.isfinite(x) for x in values), 'Nonfinite measured statistic')
    if not values:
        return {'n': 0, 'mean': None, 'std_population': None, 'median': None, 'min': None, 'max': None}
    return {'n': len(values), 'mean': statistics.fmean(values),
            'std_population': statistics.pstdev(values), 'median': statistics.median(values),
            'min': min(values), 'max': max(values)}


def window_frames(canonical, rx):
    """Use the audited prospective window, never a new or improved interval."""
    w = canonical['experimental_window']
    t0, t1 = int(w['T0_ns']), int(w['T1_ns'])
    require(t1 - t0 == 30_000_000_000, 'Wrong prospective duration')
    selected = []
    for frame in canonical['receivers'][rx]['frames']:
        r = frame['window_reference']
        inside = int(r['first_read_started_ns']) >= t0 and int(r['returned_ns']) < t1
        included = frame['timing_phase'] == 'included'
        require(inside == included == frame['received_in_experimental_window'], 'Window boundary/inclusion mismatch')
        if included:
            selected.append(frame)
    require(len(selected) == w['receivers'][rx]['coverage']['included_rows'], 'Coverage count mismatch')
    return selected


def describe_block(frames, ltf):
    """Keep all rows and nominal masks; missing values never become zeros."""
    per_tone = {}
    row_means, row_spreads = [], []
    shape = None
    mask_counts = Counter({k: 0 for k in ('hardware_invalid_pairs', 'excluded_by_cfr_mask_pairs',
                                          'usable_active_pairs', 'zero_active_amplitudes')})
    expected = 52 if ltf == 'LLTF' else 56
    for frame in frames:
        blocks = [b for b in frame['blocks'] if b['ltf'] == ltf]
        require(len(blocks) == 1, 'Exactly one requested LTF required')
        b = blocks[0]
        layout = [[k, role] for k, role in zip(b['indices'], b['roles'])]
        require(shape is None or shape == layout, 'Tone/role layout changed')
        shape = layout
        require(all(len(b[k]) == len(layout) == 64 for k in
                    ('hardware_valid', 'cfr_usable', 'amplitude')), 'Malformed mask dimensions')
        active = []
        for k, role, hw, usable, amp in zip(b['indices'], b['roles'], b['hardware_valid'], b['cfr_usable'], b['amplitude']):
            nominal = role in ('data', 'pilot')
            require(usable == (hw and nominal), 'CFR mask contradicts hardware/role')
            mask_counts[role + '_pairs'] += 1
            if not hw:
                mask_counts['hardware_invalid_pairs'] += 1
            if not usable:
                mask_counts['excluded_by_cfr_mask_pairs'] += 1
            if nominal:
                per_tone.setdefault(k, [])
            if usable:
                require(isinstance(amp, (int, float)) and math.isfinite(amp) and amp >= 0,
                        'Invalid usable amplitude')
                per_tone[k].append(amp)
                active.append(amp)
                mask_counts['usable_active_pairs'] += 1
                mask_counts['zero_active_amplitudes'] += int(amp == 0)
        require(sum(role in ('data', 'pilot') for _, role in layout) == expected, 'Unexpected active tone set')
        # Full nominal set required for comparable per-row spatial means. The
        # acquisition row remains in the session even if this description is NA.
        row_means.append(statistics.fmean(active) if len(active) == expected else None)
        row_spreads.append(statistics.pstdev(active) if len(active) == expected else None)
    tones = [{'index': k, **stats(values)} for k, values in sorted(per_tone.items())]
    temporal = [x['std_population'] for x in tones if x['n'] > 1]
    result = {'rows_in_window': len(frames), 'nominal_active_tones': expected,
              'layout_indices_and_roles': shape, 'mask_counts': dict(sorted(mask_counts.items())),
              'rows_with_complete_active_mask': sum(x is not None for x in row_means),
              'rows_not_describable_as_full_tone_mean': sum(x is None for x in row_means),
              'frame_mean_amplitude': stats([x for x in row_means if x is not None]),
              'frame_spatial_std': stats([x for x in row_spreads if x is not None]),
              'per_tone': tones,
              'mean_per_tone_temporal_std': statistics.fmean(temporal) if temporal else None}
    return result, row_means


def source_session(key):
    cfg = SESSIONS[key]
    base = ROOT / cfg['base']; run = base / cfg['run']
    control = base / cfg['control']; analysis = base / cfg['analysis']; view = analysis / 'visualization'
    require(ref(run / 'bundle-manifest.json')['sha256'] == cfg['bundle_sha256'], 'Pinned acquisition bundle changed')
    bundle = load(run / 'bundle-manifest.json'); manifest = load(run / 'capture-manifest.json')
    bundle_count = original.verify_entries(run, bundle['files'], 'path')
    entries = manifest['files'] + manifest['read_ledgers'] + [manifest['coordination_trace']]
    capture_count = original.verify_entries(run / 'capture', entries, 'name')
    original.verify_entries(view / 'originals', entries, 'name')
    for name, e in load(view / 'validation.json')['files'].items():
        require(ref(view / name)['sha256'] == e['sha256'] and ref(view / name)['bytes'] == e['bytes'], 'Visualization changed')
    plan, session, prov = load(run / 'plan.json'), load(run / 'capture/session.json'), load(run / 'provenance.json')
    require(prov == manifest['source_provenance'], 'Provenance copies disagree')
    require(session['protocol'] == 'controlled_dual_v3' and session['evidence_type'] == 'physical_capture', 'Wrong evidence')
    require(plan['availability_policy'] == AVAILABILITY_V3 and plan['stop_policy'] == STOP_POLICY_V2, 'Protocol changed')
    for path, expected in prov['files'].items():
        require(ref(ROOT / path)['sha256'] == digest(subprocess.check_output(
            ['git', 'show', prov['git_commit'] + ':' + path], cwd=ROOT)) == expected, 'Provenance mismatch: ' + path)
    auth, consumed, execution = (load(control / name) for name in
        ('autorizacion-nueva.json', 'estado-final-autorizacion.json', 'resultado-ejecucion.json'))
    require(auth['authorized'] and consumed['state'] == 'CONSUMED' and
            consumed['capture_child_invocations'] == execution['capture_child_invocations'] == 1 and
            not execution['retry_performed'], 'Single attempt not demonstrated')
    require(ref(run / 'plan.json')['sha256'] == auth['plan_sha256'] == manifest['plan_sha256'] ==
            ref(control / 'plan-confirmado.json')['sha256'], 'Authorized plan mismatch')
    audit = audit_capture(run / 'capture', manifest)
    canonical = canonicalize(run / 'capture', manifest, load(ROOT / 'config/csi_esp32s3.json'))
    require(canonical == load(view / 'canonical.json'), 'Canonical reconstruction differs')
    require(audit == load(run / 'quality.json')['full_session'] == load(analysis / 'quality.json') ==
            canonical['strict_audit'], 'Fresh/stored audits differ')
    require(not audit['quality_ok'] and not audit['connection_full']['quality_ok'] and
            audit['experimental_window']['quality_ok'], 'Historical quality results changed')
    require(audit['connection_full']['integrity_ok'], 'Transport integrity failure')
    closed = {x['receiver'] for x in session['lifecycle'] if x['event'] == 'closed'}
    require(closed == set(RX) and not any(x['event'] == 'close_error' for x in session['lifecycle']), 'Closure not demonstrated')
    browser = load(view / 'browser-qa/validation.json')
    require(len(browser['views']) == 4 and all(x['connection'] == 'Conexión completa: rechazada' and
            x['window'] == 'Ventana experimental: conforme' for x in browser['views'].values()), 'UI quality states differ')
    auxiliary_count = None
    if key == 'sentado':
        require(original.consolidate() == load(ROOT / 'results/CAPTURA_FISICA_V3.resumen.json'), 'Sitting report changed')
    else:
        auxiliary = load(base / 'resultado-manifest.json')
        require(not auxiliary['self_hash_included'] and all(x['path'] != 'resultado-manifest.json' for x in auxiliary['files']),
                'Unexpected auxiliary self-entry')
        auxiliary_count = original.verify_entries(base, auxiliary['files'], 'path')
    paths = [run / name for name in ('bundle-manifest.json', 'capture-manifest.json', 'plan.json', 'provenance.json',
             'preflight.json', 'postflight.json', 'quality.json', 'window-index.json', 'capture/session.json')]
    paths += [run / 'capture' / x['name'] for x in entries]
    paths += [analysis / 'quality.json', view / 'canonical.json', view / 'validation.json', view / 'browser-qa/validation.json']
    paths += [control / name for name in ('autorizacion-nueva.json', 'estado-final-autorizacion.json',
                                         'resultado-ejecucion.json', 'preflight-inmediato.json', 'comprobacion-posterior.json')]
    if key == 'libre':
        paths += [base / 'resultado-manifest.json', base / 'RESULTADO_MOVIMIENTO_LIBRE_V3.resumen.json',
                  control / 'transicion-declarada.json']
    return {'key': key, 'base': base, 'run': run, 'control': control, 'view': view,
            'audit': audit, 'canonical': canonical, 'plan': plan, 'session': session, 'provenance': prov,
            'sources': [ref(x) for x in paths], 'bundle_files_verified': bundle_count,
            'capture_files_and_ledgers_verified': capture_count, 'auxiliary_manifest_entries_verified': auxiliary_count}


def consolidate_movement(s):
    audit, session, canonical = s['audit'], s['session'], s['canonical']
    historical = load(s['base'] / 'RESULTADO_MOVIMIENTO_LIBRE_V3.resumen.json')
    common = session['controlled']; t0, t1 = int(common['T0_ns']), int(common['T1_ns'])
    receiver = {}
    for rx in RX:
        item = audit['receivers'][rx]; w = audit['experimental_window']['receivers'][rx]
        rows = [x for x in w['index'] if x['kind'] == 'row']; included = [x for x in rows if x['inclusion'] == 'included']
        problems = [x for x in w['index'] if x['problem']]
        require(all(int(x['returned_ns']) < t0 for x in problems), 'Problem intersects window')
        ready = next(x for x in w['index'] if x['kind'] == 'ready')
        previous = historical['receivers'][rx]
        require(previous['coverage'] == w['coverage'] and previous['complete_rows'] == len(rows) and
                previous['included_rows'] == len(included) and previous['stop'] == item['stop'], 'Local physical result disagrees')
        receiver[rx] = {'usb_serial': canonical['receivers'][rx]['usb_serial'], 'complete_rows': len(rows),
            'included_rows': len(included), 'excluded_rows': len(rows) - len(included),
            'row_classification_counts': dict(sorted(Counter(x['inclusion'] for x in rows).items())),
            'excluded_row_references': [x for x in rows if x['inclusion'] != 'included'],
            'first_included_row': included[0], 'last_included_row': included[-1], 'coverage': w['coverage'],
            'ready_reference': ready, 'ready_after_A_ns': str(int(ready['returned_ns']) - int(common['A_ns'])),
            'integrity_ok': item['integrity_ok'], 'complete_rows_quality_ok': item['complete_rows_quality_ok'],
            'counts': item['counts'], 'raw_bytes': item['stop']['bytes_received'],
            'raw_sha256': item['raw_sha256'], 'csv_sha256': item['csv_sha256'],
            'stop_quality_ok': item['stop_quality_ok'], 'stop': item['stop'], 'trailing_bytes': item['trailing_bytes'],
            'lifecycle': [x for x in session['lifecycle'] if x.get('receiver') == rx],
            'startup_problem_reason_counts': dict(sorted(Counter(x['reason'] for x in problems).items())),
            'startup_problem_references': problems, 'all_problems_before_T0': True}
    require(historical['global_quality_ok'] == audit['quality_ok'] and
            historical['connection_full'] == audit['connection_full'], 'Local quality changed')
    return {'schema': 'tesis-physical-free-movement-v3-consolidated-v1', 'operation': 'offline_consolidation_only',
        'new_UART_opened': False, 'new_physical_capture': False, 'source_run_id': session['session_id'],
        'acquisition_git_commit': s['provenance']['git_commit'], 'source_evidence_type': session['evidence_type'],
        'started_utc': session['started_utc'], 'finished_utc': session['finished_utc'],
        'A_ns': common['A_ns'], 'D_ns': common['D_ns'], 'T0_ns': str(t0), 'T1_ns': str(t1),
        'nominal_window_ns': str(t1 - t0), 'availability_delay_ns': str(t0 - int(common['A_ns'])),
        'availability_policy': common['availability_policy'], 'stop_policy': common['stop_policy'],
        'session_status': session['status'], 'physical_capture_child_invocations': 1, 'automatic_retries': 0,
        'authorization_state': 'CONSUMED', 'capture_authorization_currently_valid': False,
        'environment_declared': s['plan']['environment'], 'usage_restrictions': s['plan']['usage_restrictions'],
        'operator_transition': load(s['control'] / 'transicion-declarada.json'),
        'connection_full': audit['connection_full'],
        'experimental_window': {k: v for k, v in audit['experimental_window'].items() if k != 'receivers'},
        'global_quality_ok': audit['quality_ok'], 'receivers': receiver, 'provenance': s['provenance'],
        'all_lifecycle_events': session['lifecycle'], 'postflight': load(s['run'] / 'postflight.json'),
        'hash_verification': {'pinned_bundle': True, 'bundle_entries': s['bundle_files_verified'],
            'capture_files_and_ledgers': s['capture_files_and_ledgers_verified'], 'fresh_and_stored_audits_equal': True,
            'canonical_rebuilt_equal': True, 'original_control_manifest_entries': s['auxiliary_manifest_entries_verified'],
            'original_control_self_entry_present': False, 'stored_browser_views': 4},
        'sources': s['sources'], 'reproducer': ref(Path(__file__).resolve()),
        'limits': ['Physical activity began after the authorization message according to declaration; exact onset/offset not measured.',
            'No continuous motion label, causal movement effect, presence detection, accuracy or training suitability demonstrated.',
            'Full connection and global remain rejected; initial byte/boot causes undetermined.']}


def comparison(sessions):
    output = {}; plot_data = {}
    for key, s in sessions.items():
        can, audit, sess = s['canonical'], s['audit'], s['session']
        output[key] = {'source_run_id': sess['session_id'], 'acquisition_git_commit': s['provenance']['git_commit'],
            'started_utc': sess['started_utc'], 'finished_utc': sess['finished_utc'],
            'A_ns': sess['controlled']['A_ns'], 'T0_ns': sess['controlled']['T0_ns'], 'T1_ns': sess['controlled']['T1_ns'],
            'availability_delay_ns': str(int(sess['controlled']['T0_ns']) - int(sess['controlled']['A_ns'])),
            'connection_full': audit['connection_full'], 'global_quality_ok': audit['quality_ok'],
            'experimental_window_status': audit['experimental_window']['status'], 'receivers': {}}
        plot_data[key] = {}
        for rx in RX:
            frames = window_frames(can, rx)
            times = [(int(f['host_monotonic_ns']) - int(can['experimental_window']['T0_ns'])) / 1e9 for f in frames]
            rssi = [int(f['original_fields']['rssi']) for f in frames]
            receiver = {'usb_serial': can['receivers'][rx]['usb_serial'],
                'complete_rows': audit['receivers'][rx]['valid_rows'], 'included_rows': len(frames),
                'excluded_row_reasons': dict(sorted(Counter(f['timing_phase'] for f in can['receivers'][rx]['frames']
                                                        if not f['received_in_experimental_window']).items())),
                'coverage': audit['experimental_window']['receivers'][rx]['coverage'], 'RSSI_dBm': stats(rssi),
                'metadata_distributions': {field: dict(sorted(Counter(f['original_fields'][field] for f in frames).items()))
                                           for field in METADATA_FIELDS}, 'blocks': {}}
            plot_data[key][rx] = {'times': times, 'rssi': rssi, 'blocks': {}}
            for ltf in LTF:
                description, means = describe_block(frames, ltf)
                receiver['blocks'][ltf] = description
                plot_data[key][rx]['blocks'][ltf] = means
            output[key]['receivers'][rx] = receiver
    left, right = sessions['sentado'], sessions['libre']
    keys = sorted(set(left['provenance']['files']) | set(right['provenance']['files']))
    common_hashes = {path: {'sentado': left['provenance']['files'].get(path), 'libre': right['provenance']['files'].get(path)} for path in keys}
    evidence = {'recorded_profile_equal': left['canonical']['profile'] == right['canonical']['profile'],
        'profile_sha256': ref(ROOT / 'config/csi_esp32s3.json')['sha256'], 'profile': left['canonical']['profile'],
        'pinned_acquisition_sources_equal': all(v['sentado'] == v['libre'] for v in common_hashes.values()),
        'acquisition_source_hashes': common_hashes,
        'serial_runtime_equal': all(left['provenance'][k] == right['provenance'][k] for k in ('pyserial_version', 'serialposix_sha256')),
        'physical_installed_binary_attested': False, 'measured_geometry_equality_attested': False,
        'geometry_evidence': 'Same positions declared in the free-movement plan; no measured coordinates, controlled geometry or camera proof.',
        'environment_declarations': {k: s['plan']['environment'] for k, s in sessions.items()},
        'acquisition_identities': {k: load(s['run'] / 'preflight.json') for k, s in sessions.items()},
        'reconnection_history_sitting': left['plan']['reconnection_history'],
        'activity_transition_free_movement': load(right['control'] / 'transicion-declarada.json'),
        'metadata_distribution_differences': {rx: [field for field in METADATA_FIELDS if
            output['sentado']['receivers'][rx]['metadata_distributions'][field] !=
            output['libre']['receivers'][rx]['metadata_distributions'][field]] for rx in RX}}
    # Distribution counts differ with N even if value sets coincide; report
    # value sets separately so 150 vs 149 is not called a PHY configuration change.
    evidence['metadata_value_set_differences'] = {rx: [field for field in METADATA_FIELDS if
        set(output['sentado']['receivers'][rx]['metadata_distributions'][field]) !=
        set(output['libre']['receivers'][rx]['metadata_distributions'][field])] for rx in RX}
    ranges = common_axes(output, plot_data)
    differences = {}
    for rx in RX:
        a, b = (output[k]['receivers'][rx] for k in ('sentado', 'libre'))
        differences[rx] = {'RSSI_mean_dBm_libre_minus_sentado': b['RSSI_dBm']['mean'] - a['RSSI_dBm']['mean'], 'blocks': {}}
        for ltf in LTF:
            x, y = a['blocks'][ltf], b['blocks'][ltf]
            differences[rx]['blocks'][ltf] = {
                'frame_mean_amplitude_difference': y['frame_mean_amplitude']['mean'] - x['frame_mean_amplitude']['mean'],
                'mean_per_tone_temporal_std_difference': y['mean_per_tone_temporal_std'] - x['mean_per_tone_temporal_std']}
    return {'schema': 'tesis-physical-v3-descriptive-comparison-v1', 'operation': 'offline_existing_prospective_windows_only',
        'new_UART_opened': False, 'new_physical_capture': False, 'sessions': output, 'comparability': evidence,
        'differences': differences, 'common_axes': ranges,
        'method': {'window': 'Original audited [T0,T1), first_read>=T0 and LF_return<T1; no new interval.',
            'amplitude': 'hypot(Re,Im), raw int8 scale, uncalibrated; no normalization or dB transform.',
            'mask': 'Fixed nominal data+pilot set (LLTF 52, HT-LTF 56) and original hardware/CFR mask. DC/guards excluded; valid zero amplitudes retained.',
            'row_mean': 'Equal weight per active tone; NA if any required tone invalid. Row stays in original window.',
            'variability': 'Population std per tone across its actual valid rows; separately std of per-row spatial means.',
            'sampling': 'Equal row weights; no interpolation, imputation, resampling, bin selection or duration weighting.',
            'plotting': 'Scatter at actual host LF times relative to each original T0; common axes per metric; no lines across missing time.',
            'uncertainty': 'No p-values, confidence intervals or accuracy; frames are not independent session replicates.',
            'scope': 'Separate session/RX/LTF; RSSI belongs to each row, not duplicated as independent LTF evidence.'},
        'sources': {k: s['sources'] for k, s in sessions.items()}, 'reproducer': ref(Path(__file__).resolve())}, plot_data


def common_axes(summary, data):
    rssi = [v for s in data.values() for r in s.values() for v in r['rssi']]
    means = [v for s in data.values() for r in s.values() for b in r['blocks'].values() for v in b if v is not None]
    blocks = [b for s in summary.values() for r in s['receivers'].values() for b in r['blocks'].values()]
    tones = [t for b in blocks for t in b['per_tone'] if t['n']]
    gaps = [int(v)/1e6 for s in summary.values() for r in s['receivers'].values() for v in
            ([r['coverage']['start_gap_ns'], r['coverage']['end_gap_ns']] + r['coverage']['interior_gaps_ns'])]
    return {'time_seconds': [0, 30], 'tone_index': [-32, 31], 'rssi_dBm': [math.floor(min(rssi)-2), math.ceil(max(rssi)+2)],
            'frame_mean_amplitude': [0, math.ceil(max(means)*1.05)],
            'tone_mean_and_std_amplitude': [0, math.ceil(max(t['mean']+t['std_population'] for t in tones)*1.05)],
            'tone_temporal_std_amplitude': [0, max(1, math.ceil(max(t['std_population'] for t in tones)*1.05))],
            'host_gap_ms': [0, math.ceil(max(gaps)*1.1)]}


def render_plots(report, data, out):
    sys.path.insert(0, str(PLOT_RUNTIME))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy
    require(matplotlib.__version__ == '3.10.8', 'Pinned Matplotlib required')
    require(numpy.__version__ == '2.4.2', 'Pinned NumPy required')
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'svg.fonttype': 'none', 'svg.hashsalt': 'tesis-v3-descriptivo'})
    folder = out / 'figures/comparacion_v3'; folder.mkdir(parents=True)
    axes = report['common_axes']; figures = []
    footer = 'Conexiones/global rechazados; ventanas conformes. Descripción sin inferencia de presencia.'
    def save(fig, name, title):
        rendered_axes = []
        metric = {'rssi': 'rssi_dBm', 'amplitud_fila': 'frame_mean_amplitude',
                  'amplitud_tono': 'tone_mean_and_std_amplitude', 'variabilidad_tono': 'tone_temporal_std_amplitude'}
        for i, ax in enumerate(fig.axes):
            x_expected = axes['tone_index' if name in ('amplitud_tono', 'variabilidad_tono') else 'time_seconds']
            y_expected = ([-.5, 1.5] if i < 2 else axes['host_gap_ms']) if name == 'cobertura' else axes[metric[name]]
            require(list(ax.get_xlim()) == list(x_expected) and list(ax.get_ylim()) == list(y_expected), 'Rendered axes differ from common scales')
            rendered_axes.append({'panel': ax.get_title(), 'xlim': list(ax.get_xlim()), 'ylim': list(ax.get_ylim())})
        fig.suptitle(title, fontsize=15)
        fig.text(.5, .015, footer, ha='center', fontsize=9)
        fig.tight_layout(rect=(0, .045, 1, .95))
        for ext in ('svg', 'png'):
            path = folder / (name + '.' + ext)
            metadata = {'Date': None} if ext == 'svg' else {'Software': 'Matplotlib 3.10.8'}
            fig.savefig(path, dpi=150, metadata=metadata)
            if ext == 'svg':
                # Matplotlib emits spaces before path-command newlines. Keep
                # the XML/coordinates unchanged while satisfying Git hygiene.
                path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines()) + '\n')
            figures.append({'path': str(path.relative_to(out)), 'bytes': path.stat().st_size,
                            'sha256': digest(path.read_bytes()), 'verified_rendered_axes': rendered_axes})
        plt.close(fig)
    fig, axs = plt.subplots(1, 2, figsize=(12, 4.5), sharex=True, sharey=True)
    for ax, rx in zip(axs, RX):
        for key in SESSIONS:
            d = data[key][rx]
            ax.scatter(d['times'], d['rssi'], s=13, alpha=.65, color=COLORS[key], label=LABELS[key])
        ax.set(title=rx, xlabel='s desde T0 propio (host)', xlim=axes['time_seconds'], ylim=axes['rssi_dBm'])
        ax.grid(alpha=.2); ax.legend(fontsize=8)
    axs[0].set_ylabel('RSSI registrado (dBm)')
    save(fig, 'rssi', 'RSSI por RX · mismas escalas; tiempos host, sin alineación RF')
    for name, metric, title, ylabel in [
        ('amplitud_fila', 'frame_mean_amplitude', 'Media de amplitud sobre tonos activos por fila', 'Amplitud media (u. int8 no calibradas)'),
        ('amplitud_tono', 'tone_mean_and_std_amplitude', 'Perfil de amplitud por tono: media ± σ poblacional temporal', 'Amplitud (u. int8 no calibradas)'),
        ('variabilidad_tono', 'tone_temporal_std_amplitude', 'Variabilidad temporal por tono (σ poblacional)', 'σ amplitud (u. int8 no calibradas)')]:
        fig, axs = plt.subplots(2, 2, figsize=(12, 7), sharex=True, sharey=True)
        for i, rx in enumerate(RX):
            for j, ltf in enumerate(LTF):
                ax = axs[i, j]
                for key in SESSIONS:
                    b = report['sessions'][key]['receivers'][rx]['blocks'][ltf]
                    if name == 'amplitud_fila':
                        vals = data[key][rx]['blocks'][ltf]
                        pairs = [(t, a) for t, a in zip(data[key][rx]['times'], vals) if a is not None]
                        ax.scatter([x for x, _ in pairs], [y for _, y in pairs], s=9, alpha=.65, color=COLORS[key], label=LABELS[key])
                    else:
                        tones = [t for t in b['per_tone'] if t['n'] > (1 if name == 'variabilidad_tono' else 0)]
                        x = [t['index'] for t in tones]
                        if name == 'amplitud_tono':
                            ax.errorbar(x, [t['mean'] for t in tones], yerr=[t['std_population'] for t in tones],
                                        fmt='.', markersize=4, alpha=.65, color=COLORS[key], elinewidth=.6, label=LABELS[key])
                        else:
                            ax.scatter(x, [t['std_population'] for t in tones], s=14, alpha=.75, color=COLORS[key], label=LABELS[key])
                if name != 'amplitud_fila':
                    for k, role in b['layout_indices_and_roles']:
                        if role not in ('data', 'pilot'):
                            ax.axvspan(k-.48, k+.48, color='#dddddd', alpha=.5, zorder=0)
                ax.set(title=rx+' · '+ltf, xlabel='s desde T0 propio (host)' if name == 'amplitud_fila' else 'Índice de tono (DC/guardas en gris)',
                       xlim=axes['time_seconds' if name == 'amplitud_fila' else 'tone_index'], ylim=axes[metric])
                ax.grid(alpha=.2); ax.legend(fontsize=8)
                if j == 0: ax.set_ylabel(ylabel)
        save(fig, name, title)
    fig, axs = plt.subplots(2, 2, figsize=(12, 6), sharex=True, sharey='row')
    for j, rx in enumerate(RX):
        for position, key in enumerate(SESSIONS):
            d = data[key][rx]; cov = report['sessions'][key]['receivers'][rx]['coverage']
            axs[0, j].scatter(d['times'], [position]*len(d['times']), marker='|', s=75, color=COLORS[key])
            gaps = [int(x)/1e6 for x in cov['interior_gaps_ns']]
            axs[1, j].scatter(d['times'][1:], gaps, s=10, color=COLORS[key], alpha=.65, label=LABELS[key])
            axs[1, j].scatter([d['times'][0], 30], [int(cov['start_gap_ns'])/1e6, int(cov['end_gap_ns'])/1e6],
                              marker='^', s=35, facecolors='none', edgecolors=COLORS[key])
        axs[0, j].set(title=rx, ylim=(-.5, 1.5), yticks=[0, 1], yticklabels=[LABELS[k] for k in SESSIONS])
        axs[1, j].set(xlim=axes['time_seconds'], ylim=axes['host_gap_ms'], xlabel='s desde T0 propio (host)', ylabel='Intervalo LF host (ms)')
        axs[1, j].legend(fontsize=8)
        for ax in axs[:, j]: ax.grid(alpha=.2)
    save(fig, 'cobertura', 'Cobertura real: marcas LF; huecos interiores y de borde (triángulos)')
    return figures


def write_json(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, allow_nan=False, indent=2); stream.write('\n')


def reports():
    sessions = {k: source_session(k) for k in SESSIONS}
    movement = consolidate_movement(sessions['libre'])
    compared, data = comparison(sessions)
    return movement, compared, data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--output-new', type=Path)
    mode.add_argument('--check', type=Path, help='Directory with the two published JSON summaries and figure manifest')
    parser.add_argument('--inside-sandbox', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    destination = (args.output_new or args.check).resolve()
    if not args.inside_sandbox:
        require(destination.is_relative_to(ROOT), 'Output/check must be internal')
        cmd = ['bwrap', '--unshare-all', '--die-with-parent', '--ro-bind', '/usr', '/usr', '--ro-bind', '/lib', '/lib',
               '--ro-bind', '/lib64', '/lib64', '--ro-bind', '/etc/ld.so.cache', '/etc/ld.so.cache',
               '--ro-bind', '/etc/localtime', '/etc/localtime', '--ro-bind', '/etc/fonts', '/etc/fonts',
               '--ro-bind', str(ROOT), str(ROOT),
               '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp', '--chdir', str(ROOT),
               '--setenv', 'HOME', '/tmp', '--setenv', 'MPLCONFIGDIR', '/tmp/mpl', '--setenv', 'PYTHONDONTWRITEBYTECODE', '1']
        if args.output_new:
            require(destination.is_relative_to(ROOT / 'results/local'), 'Generated output must be NEW results/local')
            destination.mkdir(parents=True, exist_ok=False)
            cmd += ['--bind', str(destination), str(destination)]
        cmd += [str(ROOT / '.venv/bin/python'), '-B', str(Path(__file__).resolve()), '--inside-sandbox',
                '--output-new' if args.output_new else '--check', str(destination)]
        return subprocess.run(cmd).returncode
    movement, compared, data = reports()
    names = ('CAPTURA_MOVIMIENTO_LIBRE_V3.resumen.json', 'COMPARACION_FISICA_V3.resumen.json')
    if args.check:
        for name, value in zip(names, (movement, compared)):
            require(load(destination / name) == value, 'Published reconstruction differs: ' + name)
        manifest = load(destination / 'COMPARACION_FISICA_V3.figuras.json')
        original.verify_entries(destination, manifest['files'], 'path')
        require(manifest['common_axes'] == compared['common_axes'], 'Published axes differ')
        print('OFFLINE_DESCRIPTIVE_REPORTS_VERIFIED; both connection/global rejections preserved')
    else:
        for name, value in zip(names, (movement, compared)): write_json(destination / name, value)
        figures = render_plots(compared, data, destination)
        runtime = {d.metadata['Name']: d.version for d in importlib.metadata.distributions(path=[str(PLOT_RUNTIME)])}
        write_json(destination / 'COMPARACION_FISICA_V3.figuras.json', {'schema': 'tesis-comparison-v3-figures-v1',
            'files': figures, 'common_axes': compared['common_axes'], 'runtime': runtime,
            'requirements': ref(ROOT / 'requirements-comparacion.txt'), 'raw_matrices_published': False,
            'sigma_interpretation': 'Population sample spread; not confidence intervals, RF stability or causal effects.'})
        print(destination)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
