"""Offline physical checkpoint comparison; preserves every original byte."""
from collections import Counter
import json
from pathlib import Path

from continuity_diagnostics import distribution
from presence_rx02_journal import audit_rx02
from rx02_diagnostic.contract import HISTORICAL_CONNECTION
from rx02_gap_diagnostics import inventory,adjacent_gaps,timing,phase,require

ROOT=Path(__file__).resolve().parents[1]


def load(path):
    return json.loads(Path(path).read_text())


def summarize(root,auditor):
    root=Path(root).resolve();before=inventory(root)
    audit=auditor(root);state=audit['state']
    operations=[json.loads(line) for line in (root/'operations.jsonl').read_text().splitlines()]
    events=load(root/'events.json')
    rows=[e for e in events if e['kind']=='line' and e['evidence']['kind']=='row']
    reads=[o for o in operations if o['op']=='chunk']
    require(rows and reads,'Complete physical rows and reads required')
    gaps=adjacent_gaps(rows)
    stamps={name:[o['now_ns'] for o in operations if o['op']==name]
            for name in ('begin','opened','close_request','closing','closed')}
    require(all(len(stamps[k])==1 for k in ('begin','opened','closing','closed')),'Exactly one lifecycle required')
    t={k:v[0] if v else None for k,v in stamps.items()}
    available=state['initial_available_ns']
    # Both full connection and fixed common interval are descriptive, never eligible windows.
    steady=[e for e in rows if int(e['evidence']['returned_ns'])>=available]
    steady_gaps=adjacent_gaps(steady)
    line_kinds=Counter(e['evidence']['kind'] for e in events if e['kind']=='line')
    plan=load(root/'plan.json');runtime=load(root/'summary.json')['runtime']
    raw_bytes=(root/'rx-02.serial.log').read_bytes()
    for row in rows:
        import hashlib
        evidence=row['evidence'];raw=raw_bytes[evidence['byte_offset']:evidence['byte_end']]
        require(len(raw)==evidence['byte_length'] and hashlib.sha256(raw).hexdigest()==evidence['line_sha256'],
                'Row reference mismatch')
    def cadence(selected,selected_gaps):
        elapsed=int(selected[-1]['evidence']['returned_ns'])-int(selected[0]['evidence']['returned_ns'])
        return dict(complete_rows=len(selected),first_id=selected[0]['evidence']['id'],last_id=selected[-1]['evidence']['id'],
            first_to_last_return_ns=elapsed,host_interarrival_hz=(len(selected)-1)*1e9/elapsed if elapsed else None,
            host_gap_ns=distribution([g['host_gap_ns'] for g in selected_gaps]),
            local_gap_us=distribution([g['local_gap_us'] for g in selected_gaps]),
            over_500ms=sum(g['host_gap_ns']>500_000_000 for g in selected_gaps),
            over_1s=sum(g['host_gap_ns']>1_000_000_000 for g in selected_gaps),
            zero_host_gaps=sum(g['host_gap_ns']==0 for g in selected_gaps),
            callback_ids_consecutive=all(g['callback_id_delta']==1 for g in selected_gaps),
            queue_drops_values=sorted({e['evidence']['queue_drops'] for e in selected}),
            continuity_errors=sum(bool(e['evidence']['continuity_error']) for e in selected),
            worst_host_gap=dict(previous_id=max(selected_gaps,key=lambda g:g['host_gap_ns'])['previous']['evidence']['id'],
                following_id=max(selected_gaps,key=lambda g:g['host_gap_ns'])['following']['evidence']['id'],
                host_gap_ns=max(g['host_gap_ns'] for g in selected_gaps),
                corresponding_local_gap_us=max(selected_gaps,key=lambda g:g['host_gap_ns'])['local_gap_us']) if selected_gaps else None)
    operation_intervals=[b['now_ns']-a['now_ns'] for a,b in zip(operations,operations[1:])]
    ticks=[o for o in operations if o['op']=='tick' and t['opened']<=o['now_ns']<=t['closing']]
    tick_intervals=[b['now_ns']-a['now_ns'] for a,b in zip(ticks,ticks[1:])]
    result=dict(bundle=str(root.relative_to(ROOT)),files=before,integrity_ok=audit['integrity_ok'],replay_ok=audit['replay_ok'],
        evidence_type=state['evidence_type'],connection_id=plan['connection_id'],partition_group=plan['partition_group'],
        future_partition=plan['future_partition'],fatal=state['fatal'],connection=state['connection'],
        timings=dict(stamps_ns=t,begin_to_open_ns=t['opened']-t['begin'],open_to_closing_ns=t['closing']-t['opened'],
            open_to_close_ns=t['closed']-t['opened'],open_to_close_request_ns=t['close_request']-t['opened'] if t['close_request'] is not None else None,
            close_driver_and_record_interval_ns=t['closed']-t['closing'],initial_available_after_open_ns=available-t['opened'],
            last_operation_after_open_ns=operations[-1]['now_ns']-t['opened'],
            all_operation_sample_intervals_ns=distribution(operation_intervals),tick_sample_intervals_ns=distribution(tick_intervals),
            read=timing(reads)),
        cadence_full=cadence(rows,gaps),cadence_after_initial_available=cadence(steady,steady_gaps),
        common_first_180s_after_available=phase(rows,reads,available,available+180_000_000_000),
        common_phase_is_descriptive_not_window=True,line_kinds=dict(line_kinds),raw_bytes=len(raw_bytes),
        operations=len(operations),events=len(events),reads=len(reads),operation_counts=dict(Counter(o['op'] for o in operations)),
        windows=[dict(id=w['id'],condition=w['condition'],label=w['label'],state=w['state'],T0_ns=w['T0_ns'],T1_ns=w['T1_ns']) for w in state['windows']],
        signals=state['signals'],tails=state['tails'],closed=state['closed'],runtime=runtime,
        authorization_consumed=load(root/'authorization-consumed.json'),plan=plan,
        source_snapshots=load(root/'provenance.json')['sources'],
        exploratory_eligibility=audit.get('exploratory_eligibility'),diagnostic=audit.get('diagnostic'))
    for name in ('checkpoint-status.json','persistence-policy.json','service-metrics.json'):
        result[name.removesuffix('.json').replace('-','_')]=load(root/name) if (root/name).exists() else None
    require(inventory(root)==before,'Original changed during audit')
    return result,audit


def compare(diagnostic,c02,diagnostic_auditor):
    plan=load(Path(diagnostic)/'plan.json')
    require(plan.get('connection_id')==plan.get('partition_group')==HISTORICAL_CONNECTION and
            'live_view' not in plan,'Historical RX02-DIAG-CP-R1 bundle required for this comparison')
    d,da=summarize(diagnostic,diagnostic_auditor);c,ca=summarize(c02,audit_rx02)
    require(d['evidence_type']==c['evidence_type']=='physical_capture','Existing physical evidence required')
    fields=('policy','receivers','ports','baud','storage_policy','transmitter','line_policy_revision')
    comparisons={name:d['plan'][name]==c['plan'][name] for name in fields}
    shared={e['path']:e['sha256'] for e in c['source_snapshots']}
    present={e['path']:e['sha256'] for e in d['source_snapshots']}
    require(all(present.get(name)==sha for name,sha in shared.items()),'Historical acquisition sources changed')
    result=dict(schema='tesis-rx02-physical-checkpoint-comparison-1',physical_UART_opened_by_analysis=False,
        diagnostic=d,C02=c,comparability=dict(fixed_fields_equal=comparisons,historical_sources_unchanged=len(shared),
            periods_are_different=True,not_paired_or_randomized=True,
            diagnostic_has_no_windows_or_operator_command_poll=True,
            rx01_diagnostic='disconnected by current operator declaration',rx01_C02=c['plan']['unused_receiver'],
            geometry_scope='Operator declares same positions/antennas; no new geometrical measurement',
            power_scope='TX wall charger both; new power-on interval after disconnection; TX power unmeasured',
            absent_measurements=['C02 CPU/RSS','periodic physical RSS/fd/thread samples','individual fsync end clocks','scheduler/USB/RF traces'],
            common_interval='First 180 s after each initial availability; descriptive prefix excludes the later C02 failure and is not an eligibility window'),
        limits=['A successful 240 s diagnostic does not approve strict connection quality, campaign windows, labels, calibration or training.',
            'Observed host gap and local receiver timestamp gap are different clocks; no RF loss or one-way latency claim.',
            'Maxima and counts depend on duration, sample count, startup, operator loop, audio, scheduling and hardware state.',
            'Return-to-decision includes raw persistence, locking, scheduling and Python work; it is not isolated fsync latency.',
            'Only process CPU and ru_maxrss through service end were recorded physically. No new fd/thread or per-stage profiler data are invented.',
            'Checkpoint count describes successful decorator syncs, not all kernel/device flushes or a power-loss recovery experiment.',
            'The diagnostic authorization is consumed. No additional physical action is authorized.'])
    return result,{'diagnostic':da,'C02':ca}
