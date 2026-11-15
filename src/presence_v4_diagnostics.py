"""Read-only v4 diagnostics. Host timestamps are evidence, not causal attribution."""
import collections
from datetime import datetime
import hashlib
import json
from pathlib import Path

from capture_csi_multi import RECEIVERS, FIELDS
from presence_v4_journal import audit_v4


def acquisition_activity(report):
    """Distinguish recorded physical acquisition from this offline auditor."""
    state = report['state']
    physical = state['evidence_type'] == 'physical_capture'
    bindings = state.get('exploration', {}).get('identity_bindings', {})
    opened = {rx: (True if rx in bindings or state.get('closed', {}).get(rx, {}).get('confirmed') is True
                    else None) if physical else False for rx in RECEIVERS}
    observed = True if any(v is True for v in opened.values()) else (
        None if any(v is None for v in opened.values()) else False)
    return dict(evidence_type=state['evidence_type'], physical_capture=physical,
                physical_UART_opened=observed, physical_UART_opened_by_receiver=opened,
                basis='replayed opened/identity binding or confirmed closure; unknown if proof absent')


def _stats(values):
    return dict(count=len(values), min_ns=min(values) if values else None,
                max_ns=max(values) if values else None,
                mean_ns=sum(values)/len(values) if values else None)


def compare_wall_monotonic(report, claim, launch):
    """UTC endpoints include launch/finalization; they do not isolate host sleep."""
    start = datetime.fromisoformat(claim['claimed_utc'])
    end = datetime.fromisoformat(launch['finished_utc'])
    if start.tzinfo is None or end.tzinfo is None or end < start:
        raise ValueError('Ordered timezone-aware launcher timestamps required')
    delta = end-start
    wall_ns = (delta.days*86400+delta.seconds)*1_000_000_000+delta.microseconds*1000
    mono_ns = report['last_operation_sample_ns']-report['begin_ns']
    return dict(launch_claim_utc=claim['claimed_utc'], child_finished_utc=launch['finished_utc'],
        wall_span_ns=wall_ns, recorded_monotonic_span_ns=mono_ns,
        wall_minus_monotonic_span_ns=wall_ns-mono_ns,
        limitation='Linux CLOCK_MONOTONIC excludes system suspend; UTC endpoints also include startup/finalization and may undergo clock adjustment; no BOOTTIME or suspend trace was recorded')


def analyze_availability(directory, control_directory=None):
    root = Path(directory)
    replay = audit_v4(root)
    operations = [json.loads(line) for line in (root/'operations.jsonl').read_text().splitlines()]
    events = json.loads((root/'events.json').read_text())
    plan = json.loads((root/'plan.json').read_text())
    provenance = json.loads((root/'provenance.json').read_text())
    fatal = next((e for e in events if e['kind'] == 'suspended'), None)
    if not fatal or not fatal['reason'].startswith('availability_lost:'):
        raise ValueError('Recorded availability_lost suspension required')
    target = fatal['reason'].split(':', 1)[1]
    if target not in RECEIVERS:
        raise ValueError('Unknown suspended receiver')
    end = fatal['now_ns']; threshold = plan['policy']['freshness_ns']
    available = next(e for e in events if e['kind'] == 'initial_available')
    active = [o for o in operations if o['now_ns'] <= end]
    receivers = {}
    for rx in RECEIVERS:
        ready = next(e['evidence']['line_1based'] for e in events
                     if e['kind'] == 'line' and e['receiver'] == rx and e['evidence']['kind'] == 'ready')
        rows = [e for e in events if e['kind'] == 'line' and e['receiver'] == rx and
                e['evidence']['kind'] == 'row' and not e['evidence']['continuity_error'] and
                e['evidence']['line_1based'] > ready and e['now_ns'] <= end]
        last = rows[-1]; line = last['evidence']; returned = int(line['returned_ns'])
        reads = [o for o in active if o['op'] == 'chunk' and o['data']['receiver'] == rx]
        completing = reads[line['last_read_index']]
        later = reads[line['last_read_index']+1:]
        raw = (root/(rx.lower()+'.serial.log')).read_bytes()
        tail = raw[line['byte_end']:]
        partial = None
        if tail.startswith(b'CSI_DATA,') and b',"[' in tail:
            # Literal header columns only. Never validate/count/reconstruct a
            # complete CSI row from an unterminated payload.
            columns = tail.split(b',"[', 1)[0].split(b',')
            if len(columns) == len(FIELDS)-1:
                try:
                    partial = dict(id=int(columns[FIELDS.index('id')]),
                        local_timestamp=int(columns[FIELDS.index('local_timestamp')]),
                        queue_drops=int(columns[FIELDS.index('queue_drops')]),
                        validated_as_CSI=False, complete_row_counted=False)
                except ValueError:
                    pass
        receivers[rx] = dict(valid_complete_rows=len(rows), last_valid_event=last,
            last_valid_completing_operation=completing,
            last_valid_returned_ns=returned, processing_clock_sample_ns=last['now_ns'],
            last_valid_age_at_suspension_ns=end-returned,
            last_valid_return_to_decision_sample_ns=last['now_ns']-returned,
            deadline_ns=returned+threshold, deadline_excess_ns=end-returned-threshold,
            last_recorded_read=reads[-1], reads_after_last_valid=later,
            no_recorded_bytes_gap_ns=later[0]['data']['started_ns']-returned if later else None,
            read_duration=_stats([o['data']['returned_ns']-o['data']['started_ns'] for o in reads]),
            return_to_decision_sample=_stats([o['now_ns']-o['data']['returned_ns'] for o in reads]),
            residual_after_last_valid=dict(byte_offset=line['byte_end'], byte_end=len(raw),
                bytes=len(tail), sha256=hashlib.sha256(tail).hexdigest(),
                contains_LF=b'\n' in tail, literal_partial_header=partial))
    causal_start = receivers[target]['processing_clock_sample_ns']
    causal = [o for o in active if causal_start <= o['now_ns'] <= end]
    gaps = [dict(previous_seq=a['seq'], previous_op=a['op'], next_seq=b['seq'], next_op=b['op'],
                 gap_ns=b['now_ns']-a['now_ns']) for a,b in zip(causal, causal[1:])]
    before = [o for o in active if o['op'] == 'tick' and o['now_ns'] < end]
    close_events = [e for e in events if e['kind'] in ('read_stop_requested', 'port_close_result',
        'both_ports_closed_confirmed', 'signal_result') and e['now_ns'] >= end]
    result = dict(schema='tesis-v4-availability-diagnostic-v1', integrity_ok=replay['integrity_ok'],
        replay_ok=replay['replay_ok'], acquisition=acquisition_activity(replay),
        diagnostic_activity=dict(UART_opened=False, mode='offline'),
        operations=len(operations), events=len(events), begin_ns=operations[0]['now_ns'],
        last_operation_sample_ns=operations[-1]['now_ns'],
        initial_available=available, suspension=fatal, threshold_ns=threshold,
        previous_tick=before[-1], receivers=receivers,
        causal_interval=dict(start_processing_sample_ns=causal_start, end_ns=end,
            ticks=sum(o['op'] == 'tick' for o in causal),
            nonempty_reads_after_last_valid=dict(collections.Counter(o['data']['receiver'] for o in causal
                if o['op'] == 'chunk' and o['now_ns'] > causal_start)),
            operation_gaps=_stats([g['gap_ns'] for g in gaps]), largest_gaps=sorted(gaps,key=lambda g:g['gap_ns'],reverse=True)[:8]),
        active_operation_gaps=_stats([b['now_ns']-a['now_ns'] for a,b in zip(active,active[1:])]),
        post_suspension_events=close_events,
        windows=replay['state']['windows'],
        raw_durable_before_decision_sample=provenance.get('transport',{}).get('decision_clock_sampled_after_raw_persistence'),
        timing_limits=['now_ns is sampled after raw write/flush/fsync and before reducer and operations fsync',
            'return-to-sample includes persistence, scheduling, lock and Python overhead; it is not isolated fsync time',
            'no separate parser, stdin, stdout, select-ready, scheduler, RF-loss or USB-electrical trace',
            'operation samples bound visible global stalls, not per-device delivery or unobserved cause',
            'partial header is literal evidence only; no missing CSI or LF is reconstructed'])
    if control_directory is not None:
        control = Path(control_directory)
        claim = json.loads((control/'intento-consumido.json').read_text())
        launch = json.loads((control/'resultado-lanzamiento.json').read_text())
        if (Path(launch['output']).resolve() != root.resolve() or
                claim['authorization_reference'] != launch['authorization_reference'] or
                claim['authorization_reference'] != provenance['transport']['authorization_reference']):
            raise ValueError('Launcher control does not match the recorded acquisition')
        result['wall_monotonic_comparison'] = compare_wall_monotonic(result, claim, launch)
    return result
