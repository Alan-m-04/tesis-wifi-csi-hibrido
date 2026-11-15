#!/usr/bin/env python3
"""Audit existing C01 and describe its original E/S windows; no acquisition.

Raw streams, canonical rows and masks stay local. Only aggregate descriptions,
source references and figures are intended for version control.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tools'))
from canonical_csi import canonical_block
from capture_csi_multi import ANSI, SOURCE, validate_sample
from csi_correspondence import documented_ht20_layout
from comparar_fisicas_v3 import describe_block, stats
from presence_offline import row_mean
from presence_rx02_journal import audit_rx02

BASE = 'd8350483a3704f18b57f06f8c673b9fe28c7eebe'
RX = 'RX-02'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inventory(folder):
    return {str(p.relative_to(folder)): dict(bytes=p.stat().st_size, sha256=sha(p))
            for p in sorted(Path(folder).rglob('*')) if p.is_file()}


def write_new(path, value):
    with Path(path).open('x') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')


def verify_reference(raw, reference):
    start, end = reference['byte_offset'], reference['byte_end']
    require(0 <= start < end <= len(raw), 'Raw reference outside source')
    line = raw[start:end]
    require(len(line) == reference['byte_length'] and line.endswith(b'\n') and
            hashlib.sha256(line).hexdigest() == reference['line_sha256'], 'Raw line hash differs')
    return line


def frame_from_reference(raw, reference, config):
    line = verify_reference(raw, reference)
    _, record, metadata = validate_sample(ANSI.sub('', line.decode('utf-8', errors='strict')).strip())
    require(record['mac'].lower() == SOURCE and metadata['channel'] == 11 and metadata['rx_state'] == 0,
            'Unexpected source/channel/rx_state')
    require(metadata['id'] == reference['id'] and metadata['local_timestamp'] == reference['local_timestamp'] and
            metadata['queue_drops'] == reference['queue_drops'], 'Metadata and journal differ')
    layout = documented_ht20_layout(metadata, config)
    block = next(b for b in layout if b['name'] == 'LLTF')
    frame = dict(receiver_id=RX, usb_serial='5C93200689', original_fields=record,
                 window_reference=reference,
                 blocks=[canonical_block(json.loads(record['data']), block, bool(metadata['first_word_invalid']))])
    mean, reason = row_mean(frame, RX)
    return frame, mean, reason


def coverage_from_refs(refs, t0, t1):
    require(t1 - t0 == 30_000_000_000 and bool(refs), 'Original nonempty 30 s window required')
    times = [int(r['returned_ns']) for r in refs]
    require(all(t0 <= int(r['first_read_started_ns']) <= t < t1 for r, t in zip(refs, times)),
            'Prospective boundary violation')
    require(all(a <= b for a, b in zip(times, times[1:])), 'Nonmonotonic read times')
    gaps = [times[0]-t0] + [b-a for a, b in zip(times, times[1:])] + [t1-times[-1]]
    bins = [sum(t0+i*5_000_000_000 <= t < t0+(i+1)*5_000_000_000 for t in times) for i in range(6)]
    return dict(included_rows=len(refs), bins_5s=bins, gaps_ns=gaps, max_gap_ns=max(gaps),
                start_gap_ns=gaps[0], end_gap_ns=gaps[-1],
                rate_rows_per_30s=len(refs)/30, rate_is_not_RF_sampling_frequency=True)


def consolidate(bundle):
    bundle = Path(bundle).resolve()
    before = inventory(bundle)
    audit = audit_rx02(bundle)
    state = audit['state']
    plan, provenance = load(bundle/'plan.json'), load(bundle/'provenance.json')
    runtime = load(bundle/'summary.json')['runtime']
    require(state['connection_id'] == 'RX02-C01' and state['evidence_type'] == 'physical_capture', 'Physical C01 required')
    require([(w['id'], w['condition'], w['last']) for w in state['windows']] ==
            [('RX02-C01-E', 'E', False), ('RX02-C01-S', 'S', True)], 'Original E/S last order differs')
    profile = load(ROOT/'config/csi_esp32s3.json')
    for entry in provenance['sources']:
        original = subprocess.check_output(['git', 'show', BASE+':'+entry['path']], cwd=ROOT)
        require(hashlib.sha256(original).hexdigest() == entry['sha256'], 'Acquisition source differs from fixed commit')
    events = load(bundle/'events.json')
    lines = [e['evidence'] for e in events if e['kind'] == 'line']
    rows = [r for r in lines if r['kind'] == 'row']
    processed = {e['evidence']['line_1based']: e['now_ns'] for e in events if e['kind'] == 'line'}
    raw = (bundle/'rx-02.serial.log').read_bytes()
    for r in rows:
        verify_reference(raw, r)
    operations = [json.loads(line) for line in (bundle/'operations.jsonl').read_text().splitlines()]
    counts = Counter(op['op'] for op in operations)
    require(counts['opened'] == counts['closed'] == 1 and counts['request'] == counts['declare'] == 2,
            'Single connection/two manual windows not demonstrated')
    require(runtime['retry_count'] == 0, 'Unexpected retry')
    mounting_path, mounting_hash = plan['mounting_reference'].split('#sha256=')
    require(sha(ROOT/mounting_path) == mounting_hash, 'Current mounting declaration changed')
    authorization_records = [p for p in (ROOT/'results/local').glob('autorizacion-rx02-C01-*/autorizacion.json')
        if load(p)['reference'] == provenance['transport']['authorization_reference']]
    require(len(authorization_records) == 1, 'Unique original operator authorization required')
    auth_path = authorization_records[0]
    auth = load(auth_path)
    require(auth['authorization_granted'] is True and auth['scope']['max_connection_attempts'] == 1,
            'Single attempt permission not documented')
    require(sha(auth_path.parent/'plan-autorizado.json') == sha(bundle/'plan.json'), 'Authorized and captured plans differ')
    preflight = ROOT/auth['preflight_log']
    require(sha(preflight) == auth['preflight_log_sha256'], 'Preflight evidence changed')
    require(load(preflight)['identities'] == provenance['transport']['identities'] and
            load(preflight)['physical_UART_opened'] is False, 'Preflight and captured identities differ')
    sound = ROOT/'results/local/SONIDOS-FUERA-PRUEBA02/practice.json'
    require(sha(sound) == plan['environment']['sound_practice_reference'].split('#sha256=')[1].split(';')[0],
            'Sound practice reference changed')
    supporting = [ROOT/mounting_path, auth_path, auth_path.parent/'plan-autorizado.json', preflight, sound]
    supporting_files = {str(p.relative_to(ROOT)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in supporting}
    conditions, data, traces = {}, {}, {}
    membership = set()
    for w, conservative in zip(state['windows'], state['exploration']['windows']):
        condition = w['condition']
        refs = w['receivers'][RX]['included_line_references']
        coverage = coverage_from_refs(refs, w['T0_ns'], w['T1_ns'])
        original_coverage = w['receivers'][RX]['coverage']
        require(all(original_coverage[k] == coverage[k] for k in ('included_rows','bins_5s','gaps_ns','max_gap_ns')),
                'Recomputed coverage differs')
        require(conservative['receivers'][RX]['included_line_references'] == refs,
                'Conservative membership differs; do not silently choose a subset')
        require(all(processed[r['line_1based']] < w['T1_ns'] for r in refs), 'Row processed after deadline')
        require(not membership.intersection(r['line_1based'] for r in refs), 'Window memberships overlap')
        membership.update(r['line_1based'] for r in refs)
        frames, means, reasons = [], [], []
        for r in refs:
            frame, mean, reason = frame_from_reference(raw, r, profile['firmware_ltf_config'])
            frames.append(frame); means.append(mean); reasons.append(reason)
        description, described_means = describe_block(frames, 'LLTF')
        require(means == described_means, 'Independent full LLTF52 row means differ')
        if any(reasons):
            # The per-tone support remains visible, but never report the mean
            # of a silently reduced set of rows as a complete-window statistic.
            description['frame_mean_amplitude'] = dict(n=0, mean=None, std_population=None,
                median=None, min=None, max=None, reason='required_row_or_tone_incomplete')
        rssi = [int(f['original_fields']['rssi']) for f in frames]
        metadata = {key: dict(sorted(Counter(f['original_fields'][key] for f in frames).items())) for key in
                    ('mac','channel','bandwidth','sig_mode','mcs','stbc','secondary_channel','rx_state',
                     'first_word_invalid','len','queue_drops','noise_floor','ant')}
        conditions[condition] = dict(slot_id=w['id'], last=w['last'], T0_ns=str(w['T0_ns']), T1_ns=str(w['T1_ns']),
            requested_ns=str(w['requested_ns']), label=w['label'], coverage=coverage,
            window_quality_ok=w['window_quality_ok'], pilot_coverage_ok=w['pilot_coverage_ok'],
            label_quality_ok=w['label_quality_ok'], original_strict_eligible=w['eligible'],
            exploratory=next(x for x in audit['exploratory_eligibility']['windows'] if x['slot_id']==w['id']),
            rssi_dBm=stats(rssi), LLTF52=description, metadata=metadata,
            included_line_references=refs,
            mask_status='complete' if not any(reasons) else 'incomplete', mask_reasons=sorted(set(r for r in reasons if r)))
        data[condition] = dict(time_s=[(int(r['returned_ns'])-w['T0_ns'])/1e9 for r in refs],
                               rssi_dBm=rssi, mean_amplitude=means)
        traces[condition] = frames
    first_op, last_op = operations[0]['now_ns'], operations[-1]['now_ns']
    summary = dict(schema='tesis-rx02-c01-descriptive-1', acquisition_source_commit=BASE,
        source_commit_evidence='All 18 recorded acquisition sources match this Git commit; original provenance base is retained separately.',
        bundle_path=str(bundle.relative_to(ROOT)), original_files=before, supporting_files=supporting_files,
        supporting_evidence=dict(operator_authorization=auth, current_declaration=load(ROOT/mounting_path),
                                 preflight=load(preflight), sound_practice=load(sound)),
        audit=dict(integrity_ok=audit['integrity_ok'], replay_ok=audit['replay_ok'], operations=audit['operations'],
                   physical_UART_opened_by_audit=False, exploratory_eligibility=audit['exploratory_eligibility']),
        connection=dict(result=state['connection'], fatal=state['fatal'], line_kinds=dict(Counter(r['kind'] for r in lines)),
            total_CSI_rows=len(rows), in_windows=len(membership), outside_windows=len(rows)-len(membership),
            first_callback_id=rows[0]['id'], last_callback_id=rows[-1]['id'],
            callbacks_consecutive=all(b['id']==a['id']+1 for a,b in zip(rows,rows[1:])),
            queue_drops_values=sorted(set(r['queue_drops'] for r in rows)), operation_counts=dict(counts),
            first_operation_ns=str(first_op), last_operation_ns=str(last_op), journal_span_s=(last_op-first_op)/1e9,
            open_to_close_s=(state['closed'][RX]['at_ns']-next(o['now_ns'] for o in operations if o['op']=='opened'))/1e9,
            initial_available_ns=str(state['initial_available_ns']), tails=state['tails']),
        preamble=dict(status=state['exploration']['preamble_status'],
            anomalous_entries=len(state['exploration']['anomalies']), failures=state['exploration']['failures'],
            end_processed_ns=str(state['exploration']['preamble']['end_processed_ns']),
            byte_end=state['exploration']['preamble']['receivers'][RX]['byte_end'],
            sha256=state['exploration']['preamble']['receivers'][RX]['sha256'],
            source_reference='summary.json#/state/exploration; full preamble/anomalies preserved in original and local audit'),
        windows=conditions, runtime=runtime, close_receipt=load(bundle/'close-receipt.json'),
        signals=state['signals'], provenance=provenance, captured_plan=plan,
        authorization_consumed=load(bundle/'authorization-consumed.json'),
        method=dict(amplitude='hypot(Re,Im), original signed int8 Im/Re; 52 data+pilot LLTF tones, DC/guards excluded',
            row_mean='Equal weight of all 52 valid active tones; incomplete required row makes full-window aggregate unavailable',
            variability='Population temporal standard deviation per tone; separately population std of per-row spatial means',
            weights='Equal observed rows, not duration-weighted; no interpolation, resampling, demeaning or normalization',
            clocks='Original host monotonic read return and first-byte/read boundaries, not RF time; local uint32 retained in references',
            configuration='Conditional ESP-IDF v5.4 ESP32-S3 HT20 non-STBC model; merge/filter/auto-scale retained; installed binary not attested',
            uncertainty='Human yes labels, unknown timing uncertainty; mean ± sigma is dispersion, not confidence interval'),
        partition=dict(group=state['partition_group'], future_partition=state['future_partition'], split_rows_or_windows=False),
        limitations=['one connection, fixed E then S order, one person/mounting/day',
            'time/order and occupancy confounded; no concurrent RX-01 reader/control',
            'uncalibrated int8 amplitudes, gain/AGC and radio environment not independently controlled',
            'no presence decisions, accuracy, causal inference, calibration, training or production'],
        permitted_uses=dict(calibration=False, training=False, production=False))
    summary['S_minus_E'] = dict(
        rssi_mean_dB=conditions['S']['rssi_dBm']['mean']-conditions['E']['rssi_dBm']['mean'],
        LLTF52_mean_amplitude=(conditions['S']['LLTF52']['frame_mean_amplitude']['mean']-
                              conditions['E']['LLTF52']['frame_mean_amplitude']['mean'])
            if all(conditions[c]['mask_status']=='complete' for c in ('E','S')) else None)
    require(inventory(bundle) == before, 'Original bundle modified during audit/description')
    require(all(sha(ROOT/p)==e['sha256'] for p,e in supporting_files.items()), 'Supporting evidence changed')
    return summary, data, traces, audit


def render_plots(summary, data, folder):
    sys.path.insert(0, str(ROOT/'.tools/comparacion-v3-python-v2'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy
    require(matplotlib.__version__ == '3.10.8' and numpy.__version__ == '2.4.2', 'Pinned plotting runtime required')
    plt.rcParams.update({'font.family':'DejaVu Sans', 'font.size':10, 'svg.fonttype':'none', 'svg.hashsalt':'rx02-c01-1'})
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=False)
    colors = {'E':'#1764ab','S':'#c7520a'}
    labels = {'E':'Vacío (E), declarado','S':'Sentado (S), declarado'}
    windows = summary['windows']
    rssi_all = [x for c in ('E','S') for x in data[c]['rssi_dBm']]
    amp_all = [x for c in ('E','S') for x in data[c]['mean_amplitude'] if x is not None]
    tones = [t for c in ('E','S') for t in windows[c]['LLTF52']['per_tone'] if t['n']]
    low = min(t['mean']-t['std_population'] for t in tones)
    high = max(t['mean']+t['std_population'] for t in tones)
    scales = dict(time_s=[0,30], tone_index=[-32,31], rssi_dBm=[min(rssi_all)-1,max(rssi_all)+1],
        amplitude=[0,max(amp_all,default=1)*1.08], profile=[min(0,low*1.08),high*1.08],
        sigma=[0,max((t['std_population'] for t in tones),default=1)*1.08], gap_ms=[0,550])
    summary['common_axes'] = scales
    artifacts = []
    def save(fig, name, xlim, ylim):
        axes = []
        for ax in fig.axes:
            ax.set_xlim(xlim); ax.set_ylim(ylim); ax.grid(alpha=.25)
            require(list(ax.get_xlim())==xlim and list(ax.get_ylim())==ylim, 'Rendered scales differ')
            axes.append(dict(title=ax.get_title(), xlim=list(ax.get_xlim()), ylim=list(ax.get_ylim())))
        fig.text(.5,.015,'RX-02 · conexión rechazada por preámbulo · ventanas exploratorias · sin clasificación de presencia',
                 ha='center',fontsize=8)
        fig.tight_layout(rect=(0,.05,1,1))
        for ext in ('svg','png'):
            path=folder/(name+'.'+ext)
            fig.savefig(path,dpi=150,metadata={'Date':None} if ext=='svg' else {'Software':'Matplotlib 3.10.8'})
            if ext=='svg':
                path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
            artifacts.append(dict(path=str(path.relative_to(folder.parent)),bytes=path.stat().st_size,sha256=sha(path),axes=axes))
        plt.close(fig)
    for name, metric, limits, title, ylabel in (
        ('rssi','rssi_dBm',scales['rssi_dBm'],'RSSI por ventana','RSSI (dBm)'),
        ('amplitud_lltf52','mean_amplitude',scales['amplitude'],'Media por fila LLTF52','Amplitud int8 sin calibrar')):
        fig,axs=plt.subplots(1,2,figsize=(11,4),sharex=True,sharey=True)
        for ax,c in zip(axs,('E','S')):
            pairs=[(t,v) for t,v in zip(data[c]['time_s'],data[c][metric]) if v is not None]
            ax.scatter([p[0] for p in pairs],[p[1] for p in pairs],s=10,color=colors[c])
            ax.set_title(title+' · '+labels[c]); ax.set_xlabel('Tiempo desde T0 de cada ventana (s)');ax.set_ylabel(ylabel)
        save(fig,name,scales['time_s'],limits)
    for name,title,limits,errorbars in (
        ('perfil_lltf52','Media ± σ temporal por tono LLTF52',scales['profile'],True),
        ('variabilidad_lltf52','σ temporal por tono LLTF52',scales['sigma'],False)):
        fig,axs=plt.subplots(1,2,figsize=(11,4),sharex=True,sharey=True)
        for ax,c in zip(axs,('E','S')):
            values=[t for t in windows[c]['LLTF52']['per_tone'] if t['n']]
            if errorbars:
                ax.errorbar([t['index'] for t in values],[t['mean'] for t in values],
                    yerr=[t['std_population'] for t in values],fmt='o',ms=3,lw=.8,color=colors[c])
            else:
                ax.scatter([t['index'] for t in values],[t['std_population'] for t in values],s=12,color=colors[c])
            ax.set_title(title+' · '+labels[c]); ax.set_xlabel('Índice de subportadora');ax.set_ylabel('Amplitud int8 sin calibrar')
        save(fig,name,scales['tone_index'],limits)
    fig,axs=plt.subplots(1,2,figsize=(11,4),sharex=True,sharey=True)
    for ax,c in zip(axs,('E','S')):
        times=data[c]['time_s']; gaps=[g/1e6 for g in windows[c]['coverage']['gaps_ns']]
        ax.scatter([times[0],*times[1:],30],gaps,s=13,color=colors[c])
        ax.scatter([times[0],30],[gaps[0],gaps[-1]],marker='^',s=45,color=colors[c])
        ax.axhline(500,color='#555555',ls='--',lw=.8,label='Límite contractual 500 ms')
        ax.legend(fontsize=8);ax.set_title('Huecos host incluidos bordes · '+labels[c])
        ax.set_xlabel('Tiempo desde T0 (s)');ax.set_ylabel('Hueco host (ms)')
    save(fig,'cobertura',scales['time_s'],scales['gap_ms'])
    return dict(schema='tesis-rx02-c01-figures-1',runtime=dict(matplotlib=matplotlib.__version__,numpy=numpy.__version__),
                common_axes=scales,figures=artifacts)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,default=ROOT/'results/local/piloto-rx02-r1-C01')
    parser.add_argument('--output-new',type=Path,required=True)
    args=parser.parse_args(argv)
    bundle=args.bundle.resolve();out=args.output_new.resolve()
    require(not out.exists() and not out.is_relative_to(bundle), 'New output outside original bundle required')
    summary,data,traces,audit=consolidate(bundle)
    out.mkdir(parents=True,exist_ok=False)
    write_new(out/'audit.json',audit)
    write_new(out/'traces.local.json',traces)
    write_new(out/'observations.local.json',data)
    figures=render_plots(summary,data,out/'figures')
    summary['local_derivatives']={p.name:dict(bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(out.iterdir()) if p.is_file()}
    summary['analysis_sources']={name:sha(ROOT/name) for name in
        ('tools/consolidar_rx02_c01.py','tools/comparar_fisicas_v3.py','tools/consolidar_fisica_v3.py',
         'src/canonical_csi.py','src/csi_correspondence.py','src/presence_offline.py','requirements-comparacion.txt')}
    require(inventory(bundle)==summary['original_files'], 'Original bundle changed during rendering')
    summary['preservation_verified']=dict(files=len(summary['original_files']),all_bytes_and_hashes_unchanged=True)
    write_new(out/'summary.json',summary)
    figures['summary_sha256']=sha(out/'summary.json')
    write_new(out/'figures.json',figures)
    print(out)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
