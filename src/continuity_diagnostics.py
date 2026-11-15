"""Read-only continuity-dual-1 forensics. Never opens or changes acquisition."""
import collections
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics

from capture_csi_multi import FIELDS, RECEIVERS
from dual_continuity import audit
from presence_v4_journal import digest

SCHEMA = 'continuity-dual-forensics-1'
GAP_EDGES_NS = (0, 250_000_000, 500_000_000, 750_000_000,
                1_000_000_000, 1_250_000_000, 1_500_000_000)


def distribution(values):
    values = sorted(values)
    if not values:
        return dict(count=0, min=None, median=None, mean=None, p95=None, p99=None, max=None)
    return dict(count=len(values), min=values[0], median=statistics.median(values),
        mean=statistics.mean(values), p95=values[math.ceil(.95*len(values))-1],
        p99=values[math.ceil(.99*len(values))-1], max=values[-1])


def gap_distribution(values):
    result = distribution(values)
    result['unit'] = 'ns'
    result['over_1s'] = sum(x > 1_000_000_000 for x in values)
    result['histogram'] = [dict(lower_inclusive_ns=lo, upper_exclusive_ns=hi,
        count=sum(lo <= x < hi for x in values)) for lo, hi in zip(GAP_EDGES_NS, GAP_EDGES_NS[1:])]
    result['histogram'].append(dict(lower_inclusive_ns=GAP_EDGES_NS[-1], upper_exclusive_ns=None,
                                    count=sum(x >= GAP_EDGES_NS[-1] for x in values)))
    return result


def intervals(points):
    return [b-a for a,b in zip(points, points[1:])]


def service_gaps(events, rx, start, end):
    points = [start]+[e['clocks']['monotonic_ns'] for e in events
        if e['kind']=='service' and e['receiver']==rx and start < e['clocks']['monotonic_ns'] < end]+[end]
    return intervals(points)


def partial_header(raw):
    """Only literal metadata; never repair, validate, count, or return a CSI row."""
    result = dict(validated_as_CSI=False, complete_row_counted=False)
    if raw.startswith(b'CSI_DATA,') and b',"[' in raw:
        columns = raw.split(b',"[', 1)[0].split(b',')
        if len(columns) == len(FIELDS)-1:
            try:
                result['literal_fields'] = {key:int(columns[FIELDS.index(key)]) for key in
                                            ('id', 'local_timestamp', 'queue_drops', 'channel', 'len')}
            except ValueError:
                pass
    return result


def analyze_continuity(bundle):
    bundle = Path(bundle)
    original = audit(bundle)  # Reconstructs from raw bytes and read references.
    report = original['report']
    metadata = json.loads((bundle/'metadata.json').read_text())
    events = [json.loads(line) for line in (bundle/'ledger.jsonl').read_text().splitlines()]
    start = report['dual_observation']['start']['monotonic_ns']
    deadline = report['dual_observation']['deadline_ns']
    stop = next(e['acquisition_stopped']['monotonic_ns'] for e in events if e['kind']=='end')
    result = dict(schema=SCHEMA, original_integrity_ok=True, original_replay_ok=True,
        acquisition=report['acquisition'], analysis_activity=dict(physical_UART_opened=False),
        quality_approval=False, permitted_uses=report['permitted_uses'],
        authorization=json.loads((bundle/'authorization-consumed.json').read_text()),
        input_files={p.name:dict(bytes=p.stat().st_size, sha256=digest(p))
                     for p in sorted(bundle.iterdir()) if p.is_file()},
        acquisition_commit=metadata['git_commit'],
        acquisition_sources=metadata['sources'],
        acquisition_sources_match_current={p:digest(Path(__file__).resolve().parents[1]/p)==sha
                                           for p,sha in metadata['sources'].items()},
        interval=dict(common_start_ns=start, common_deadline_ns=deadline,
            common_duration_ns=deadline-start, actual_common_elapsed_ns=stop-start,
            actual_stop_ns=stop, clocks=report['elapsed']),
        quantile_method='p95/p99 nearest rank ceil(p*n); median conventional; no interpolation of measurements',
        scopes=dict(rows='Only strict complete valid CSI rows returned in [common_start, common_deadline)',
            reads='Whole connection and common interval reported separately; read return is not byte/RF arrival time',
            service='Common interval includes clipped boundaries; incident service spans include both exact boundaries',
            gaps='Between adjacent complete rows; leading/trailing ages reported separately; local clocks not synchronized across RX'),
        receivers={}, incidents=[])
    for rx in RECEIVERS:
        state = report['receivers'][rx]
        raw = (bundle/(rx.lower()+'.serial.log')).read_bytes()
        rows = [x for x in state['rows'] if start <= int(x['returned_ns']) < deadline]
        reads = [e for e in events if e['kind']=='read' and e['receiver']==rx]
        common_reads = [e for e in reads if start <= e['returned']['monotonic_ns'] < deadline]
        returns = [int(x['returned_ns']) for x in rows]
        local = [(b['local_timestamp']-a['local_timestamp']) % 2**32 for a,b in zip(rows, rows[1:])]
        profile = collections.defaultdict(set)
        for row in rows:
            literal = next(csv.reader([raw[row['byte_offset']:row['byte_end']].decode().strip()]))
            for key in ('mac','channel','bandwidth','rx_state','len','first_word_invalid','sig_mode','mcs','stbc'):
                profile[key].add(literal[FIELDS.index(key)])
        time_metrics = {}
        for name,a,b in [('read_duration','started','returned'), ('raw_persistence','persist_started','persisted'),
                         ('return_to_persistence_start','returned','persist_started'),
                         ('processing_after_raw_persistence','persisted','processed'),
                         ('processing_to_ledger_sample','processed','clocks')]:
            time_metrics[name+'_ns'] = distribution([e[b]['monotonic_ns']-e[a]['monotonic_ns'] for e in common_reads])
        tail = raw[state['tail']['byte_offset']:]
        source_clock_histogram = collections.Counter(round(x/200_000) for x in local)
        summary = dict(valid_complete_rows_common=len(rows), valid_complete_rows_connection=len(state['rows']),
            row_evidence=rows, complete_line_kinds=dict(collections.Counter(x['kind'] for x in state['lines'])),
            nonrow_evidence=[x for x in state['lines'] if x['kind']!='row'],
            valid_rows_per_10s=[sum(start+i*10_000_000_000 <= t < start+(i+1)*10_000_000_000
                                    for t in returns) for i in range(6)],
            host_row_gaps_ns=gap_distribution(intervals(returns)),
            local_row_gaps_ns=gap_distribution([x*1000 for x in local]),
            local_nearest_200ms_periods=dict(reference_only_not_packet_loss=True,
                counts={str(k):v for k,v in sorted(source_clock_histogram.items())},
                max_absolute_residual_us=max((abs(x-round(x/200_000)*200_000) for x in local), default=None)),
            first_row_age_from_common_start_ns=returns[0]-start if returns else None,
            last_row_age_at_common_deadline_ns=deadline-returns[-1] if returns else None,
            host_valid_row_span_ns=returns[-1]-returns[0] if len(returns)>1 else None,
            local_valid_row_span_us=sum(local),
            callback_ids=dict(first=rows[0]['id'] if rows else None, last=rows[-1]['id'] if rows else None,
                deltas=dict(collections.Counter(str(b['id']-a['id']) for a,b in zip(rows, rows[1:])))),
            queue_drops_values=sorted({x['queue_drops'] for x in rows}),
            callback_transitions=state['callback_transitions'], profile_values={k:sorted(v) for k,v in profile.items()},
            bytes_connection=len(raw), reads_connection=len(reads),
            bytes_common_return_time=sum(e['size'] for e in common_reads), reads_common_return_time=len(common_reads),
            pre_common_reads=sum(e['returned']['monotonic_ns'] < start for e in reads),
            post_deadline_reads=sum(e['returned']['monotonic_ns'] >= deadline for e in reads),
            read_sizes_bytes=distribution([e['size'] for e in common_reads]),
            read_return_gaps_ns=gap_distribution(intervals([e['returned']['monotonic_ns'] for e in common_reads])),
            service_gaps_ns=gap_distribution(service_gaps(events,rx,start,deadline)),
            service_count_common=sum(e['kind']=='service' and e['receiver']==rx and
                start <= e['clocks']['monotonic_ns'] < deadline for e in events),
            row_assembly_ns=distribution([int(x['returned_ns'])-int(x['first_read_started_ns']) for x in rows]),
            timing=time_metrics, closure=report['closure'][rx],
            tail=dict(**state['tail'], literal_header=partial_header(tail)),
            incidents_recorded=state['incidents'])
        result['receivers'][rx] = summary
    for rx in RECEIVERS:
        state = report['receivers'][rx]
        for number, incident in enumerate(state['incidents'], 1):
            anchor, recovered = incident['anchor_ns'], incident['recovered_ns']
            end = recovered if recovered is not None else stop
            recovery = next((x for x in state['rows'] if x['line_1based']==incident.get('recovery_line')), None)
            preceding = [x for x in state['rows'] if int(x['returned_ns']) <= anchor]
            evidence = dict(receiver=rx, number=number, original=incident,
                anchor_relative_ns=anchor-start, recovery_relative_ns=end-start if recovered is not None else None,
                previous_row=preceding[-1] if preceding else None, recovery_row=recovery, context={})
            if preceding and recovery:
                evidence['local_gap_us'] = (recovery['local_timestamp']-preceding[-1]['local_timestamp']) % 2**32
                evidence['callback_id_delta'] = recovery['id']-preceding[-1]['id']
                evidence['queue_drops_delta'] = recovery['queue_drops']-preceding[-1]['queue_drops']
                following = [x for x in state['rows'] if int(x['returned_ns']) >= end][:6]
                evidence['recovery_and_next_complete_rows'] = following
            for other in RECEIVERS:
                reads = [e for e in events if e['kind']=='read' and e['receiver']==other and
                         anchor < e['returned']['monotonic_ns'] <= end]
                evidence['context'][other] = dict(read_count=len(reads), bytes=sum(e['size'] for e in reads),
                    read_evidence=reads,
                    valid_rows=sum(x['kind']=='row' for e in reads for x in e['lines']),
                    service_count=sum(e['kind']=='service' and e['receiver']==other and
                        anchor < e['clocks']['monotonic_ns'] <= end for e in events),
                    max_service_gap_with_boundaries_ns=max(service_gaps(events, other, anchor, end)),
                    first_read_return_relative_to_anchor_ns=reads[0]['returned']['monotonic_ns']-anchor if reads else None)
            result['incidents'].append(evidence)
    samples = [e['clocks'] for e in events if e['clocks']['monotonic_ns'] <= stop]
    result['host_clocks'] = dict(
        boottime_minus_monotonic_offset_ns=distribution([s['boottime_ns']-s['monotonic_ns'] for s in samples]),
        realtime_minus_monotonic_offset_ns=distribution([s['realtime_ns']-s['monotonic_ns'] for s in samples]),
        ledger_sample_gaps_ns=distribution(intervals([s['monotonic_ns'] for s in samples])))
    storage = [e for e in events if e['kind']=='storage_check']
    result['storage'] = dict(checks=len(storage), min_free_bytes=min(e['free_bytes'] for e in storage),
        max_raw_bytes=max(e['raw_bytes'] for e in storage), max_bundle_bytes=max(e['size_bytes'] for e in storage))
    return result
