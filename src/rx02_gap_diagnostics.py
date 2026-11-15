"""Read-only RX-02 continuity forensics; never changes policy or eligibility."""
from collections import Counter
import hashlib
import json
from pathlib import Path

from continuity_diagnostics import distribution, partial_header
from presence_rx02_journal import audit_rx02

ROOT = Path(__file__).resolve().parents[1]
RX = 'RX-02'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load(path):
    return json.loads(Path(path).read_text())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inventory(folder):
    folder = Path(folder)
    return {str(p.relative_to(folder)): dict(bytes=p.stat().st_size, sha256=digest(p))
            for p in sorted(folder.rglob('*')) if p.is_file()}


def adjacent_gaps(events):
    """Keep zero host gaps from same-chunk rows; never manufacture RF times."""
    return [dict(previous=a, following=b,
                 host_gap_ns=int(b['evidence']['returned_ns'])-int(a['evidence']['returned_ns']),
                 local_gap_us=(b['evidence']['local_timestamp']-a['evidence']['local_timestamp']) % 2**32,
                 callback_id_delta=b['evidence']['id']-a['evidence']['id'],
                 queue_drops_delta=b['evidence']['queue_drops']-a['evidence']['queue_drops'])
            for a, b in zip(events, events[1:])]


def timing(reads):
    return dict(read_duration_ns=distribution([r['data']['returned_ns']-r['data']['started_ns'] for r in reads]),
        return_to_decision_sample_ns=distribution([r['now_ns']-r['data']['returned_ns'] for r in reads]),
        bytes_per_read=distribution([r['data']['size'] for r in reads]),
        read_return_gap_ns=distribution([b['data']['returned_ns']-a['data']['returned_ns'] for a,b in zip(reads,reads[1:])]),
        previous_return_to_next_read_start_ns=distribution([b['data']['started_ns']-a['data']['returned_ns']
                                                           for a,b in zip(reads,reads[1:])]))


def phase(rows, reads, lo, hi):
    selected = [e for e in rows if lo <= int(e['evidence']['returned_ns']) < hi]
    chosen_reads = [r for r in reads if lo <= r['data']['returned_ns'] < hi]
    gaps = adjacent_gaps(selected)
    return dict(start_ns=lo, end_exclusive_ns=hi, complete_rows_by_return=len(selected),
        host_row_gap_ns=distribution([g['host_gap_ns'] for g in gaps]),
        local_row_gap_us=distribution([g['local_gap_us'] for g in gaps]),
        host_row_gaps_over_500ms=sum(g['host_gap_ns'] > 500_000_000 for g in gaps),
        host_row_gaps_over_1s=sum(g['host_gap_ns'] > 1_000_000_000 for g in gaps),
        reads_by_return=len(chosen_reads), timing=timing(chosen_reads))


def inspect_bundle(bundle):
    bundle = Path(bundle).resolve()
    before = inventory(bundle)
    audit = audit_rx02(bundle)
    state = audit['state']
    operations = [json.loads(line) for line in (bundle/'operations.jsonl').read_text().splitlines()]
    events = load(bundle/'events.json')
    rows = [e for e in events if e['kind'] == 'line' and e['evidence']['kind'] == 'row']
    reads = [o for o in operations if o['op'] == 'chunk']
    require(all(r['data']['receiver'] == RX for r in reads), 'Only RX-02 expected')
    raw = (bundle/'rx-02.serial.log').read_bytes()
    for event in rows:
        r = event['evidence']; line = raw[r['byte_offset']:r['byte_end']]
        require(len(line)==r['byte_length'] and hashlib.sha256(line).hexdigest()==r['line_sha256'], 'Row raw reference changed')
    gaps = adjacent_gaps(rows)
    close = state['closed'][RX]['at_ns']
    opened = next(o['now_ns'] for o in operations if o['op']=='opened')
    windows = []
    for w in state['windows']:
        refs = w['receivers'][RX]['included_line_references']
        t0,t1 = w['T0_ns'],w['T1_ns']
        require(t0 is not None and t1-t0==30_000_000_000, 'Original completed 30 s window required')
        returns = [int(r['returned_ns']) for r in refs]
        require(all(t0<=int(r['first_read_started_ns'])<=int(r['returned_ns'])<t1 for r in refs), 'Window boundaries differ')
        bins = [sum(t0+i*5_000_000_000<=t<t0+(i+1)*5_000_000_000 for t in returns) for i in range(6)]
        coverage = w['receivers'][RX]['coverage']
        edge_gaps=[returns[0]-t0]+[b-a for a,b in zip(returns,returns[1:])]+[t1-returns[-1]]
        require(len(refs)==coverage['included_rows'] and bins==coverage['bins_5s'] and edge_gaps==coverage['gaps_ns'],
                'Original coverage does not reproduce')
        windows.append(dict(**{k:v for k,v in w.items() if k!='receivers'}, coverage=coverage,
            start_gap_ns=edge_gaps[0],end_gap_ns=edge_gaps[-1],
            first_included_reference=refs[0],last_included_reference=refs[-1],
            timing_scope='Original references for coverage; read timing below grouped by return, without RF synchronization',
            read_and_row_timing=phase(rows,reads,t0,t1)))
    result=dict(bundle=str(bundle.relative_to(ROOT)),original_files=before,
        integrity_ok=audit['integrity_ok'],replay_ok=audit['replay_ok'],
        operations=len(operations),events=len(events),operation_counts=dict(Counter(o['op'] for o in operations)),
        fatal=state['fatal'],connection=state['connection'],exploratory_eligibility=audit['exploratory_eligibility'],
        open_to_close_ns=close-opened,complete_CSI_rows=len(rows),raw_bytes=len(raw),
        host_row_gap_ns=distribution([g['host_gap_ns'] for g in gaps]),
        local_row_gap_us=distribution([g['local_gap_us'] for g in gaps]),
        host_row_gaps_over_500ms=sum(g['host_gap_ns']>500_000_000 for g in gaps),
        host_row_gaps_over_1s=sum(g['host_gap_ns']>1_000_000_000 for g in gaps),
        host_zero_gaps=sum(g['host_gap_ns']==0 for g in gaps),
        callbacks_consecutive=all(g['callback_id_delta']==1 for g in gaps),
        callback_ids=[rows[0]['evidence']['id'],rows[-1]['evidence']['id']],
        queue_drops_values=sorted({e['evidence']['queue_drops'] for e in rows}),
        row_assembly_ns=distribution([int(e['evidence']['returned_ns'])-int(e['evidence']['first_read_started_ns']) for e in rows]),
        timing=timing(reads),windows=windows,signals=state['signals'],remaining_slots=state['remaining_slots'],
        close_receipt=load(bundle/'close-receipt.json'),runtime=load(bundle/'summary.json')['runtime'],
        authorization_consumed=load(bundle/'authorization-consumed.json'),provenance=load(bundle/'provenance.json'),
        plan=load(bundle/'plan.json'),tails=state['tails'])
    require(inventory(bundle)==before,'Original bundle changed')
    return result,dict(audit=audit,state=state,operations=operations,events=events,rows=rows,reads=reads,raw=raw,gaps=gaps)


def incident_details(context, summary):
    state,events,ops = context['state'],context['events'],context['operations']
    rows,reads,raw = context['rows'],context['reads'],context['raw']
    fatal = next(e for e in events if e['kind']=='suspended')
    require(fatal['reason']=='availability_gap:RX-02', 'Original RX-02 gap failure required')
    candidates=[g for g in context['gaps'] if g['following']['seq']<fatal['seq'] and
                g['following']['now_ns']==fatal['now_ns'] and
                g['host_gap_ns']>summary['plan']['policy']['freshness_ns']]
    require(len(candidates)==1, 'Exactly one causally triggering complete-row pair required')
    gap=candidates[0];previous,following=gap['previous'],gap['following']
    trigger=next(o for o in ops if o['now_ns']==fatal['now_ns'] and o['op']=='chunk')
    p=previous['evidence'];r=following['evidence']
    require(reads[p['last_read_index']]['data']['returned_ns']==int(p['returned_ns']), 'Previous read binding differs')
    require(reads[r['last_read_index']]==trigger, 'Trigger read binding differs')
    threshold=summary['plan']['policy']['freshness_ns']
    t0,t1=state['windows'][0]['T0_ns'],state['windows'][0]['T1_ns']
    end_cue_earliest=t1+summary['plan']['policy']['label_tail_ns']
    tail_size=state['tails'][RX]['bytes'];tail=raw[len(raw)-tail_size:] if tail_size else b''
    require(len(tail)==349 and b'\n' not in tail,'Original incomplete tail expected, never repaired')
    require(hashlib.sha256(tail).hexdigest()==state['tails'][RX]['sha256'],'Tail hash differs')
    tail_reference=next(a for a in state['exploration']['anomalies'] if a.get('kind')=='incomplete_tail')
    last_pre_fatal_tick=next(o for o in reversed(ops[:trigger['seq']]) if o['op']=='tick')
    between=[o for o in ops if previous['now_ns']<=o['now_ns']<=fatal['now_ns']]
    neighboring_ops=ops[reads[p['last_read_index']]['seq']:trigger['seq']+2]
    portions=[]
    times=[('previous_read_return',int(p['returned_ns'])),
           ('previous_decision_sample',previous['now_ns'])]
    times += [('operation_'+str(o['seq'])+'_'+o['op'],o['now_ns']) for o in ops
              if previous['now_ns']<o['now_ns']<trigger['data']['started_ns']]
    times += [('trigger_read_start',trigger['data']['started_ns']),
              ('trigger_read_return',trigger['data']['returned_ns']),('trigger_decision_sample',trigger['now_ns'])]
    for a,b in zip(times,times[1:]):portions.append(dict(start=a[0],end=b[0],start_ns=a[1],end_ns=b[1],elapsed_ns=b[1]-a[1]))
    phase_ranges=[('window',t0,t1),('post_T1_first_4s',t1,t1+4_000_000_000),
                  ('post_T1_after_4s',t1+4_000_000_000,fatal['now_ns']+1)]
    result=dict(suspension=fatal,triggering_operation=trigger,triggering_row_pair=gap,
        final_complete_row=rows[-1],last_tick_before_failure=last_pre_fatal_tick,
        last_tick_age_of_previous_valid_row_ns=last_pre_fatal_tick['now_ns']-int(p['returned_ns']),
        trigger_read_to_decision_ns=trigger['now_ns']-trigger['data']['returned_ns'],
        trigger_read_duration_ns=trigger['data']['returned_ns']-trigger['data']['started_ns'],
        threshold_ns=threshold,first_exceedance_ns=int(p['returned_ns'])+threshold+1,
        gap_excess_over_threshold_ns=gap['host_gap_ns']-threshold,
        previous_row_age_at_decision_ns=trigger['now_ns']-int(p['returned_ns']),
        T0_ns=t0,T1_ns=t1,suspension_after_T1_ns=fatal['now_ns']-t1,
        earliest_end_cue_ns=end_cue_earliest,time_remaining_until_earliest_end_cue_ns=end_cue_earliest-fatal['now_ns'],
        original_end_cue_requested=state['windows'][0]['end_signal'] is not None,
        window_end_event=next(e for e in events if e['kind']=='window_ended_connection_open'),
        row_pair_gap_is_post_window=int(p['returned_ns'])>=t1,
        tail=dict(byte_offset=len(raw)-tail_size,byte_end=len(raw),bytes=tail_size,
            sha256=hashlib.sha256(tail).hexdigest(),contains_LF=False,original_reference=tail_reference,
            literal_partial_header=partial_header(tail),validated_as_CSI=False,complete_row_counted=False),
        final_chunk_complete_rows=[e for e in rows if int(e['evidence']['returned_ns'])==trigger['data']['returned_ns']],
        parsed_rows_after_suspension_event_in_same_chunk=[e for e in rows if e['seq']>fatal['seq']],
        explicit_failures=state['exploration']['failures'],eligibility_reasons=summary['exploratory_eligibility']['windows'][0]['reasons'],
        operation_chain=neighboring_ops,recorded_time_portions=portions,
        max_operation_sample_gap_in_causal_chain_ns=max(b['now_ns']-a['now_ns'] for a,b in zip(between,between[1:])),
        final_reads=[dict(operation=o,relative_read_return_to_T1_ns=o['data']['returned_ns']-t1,
                         read_duration_ns=o['data']['returned_ns']-o['data']['started_ns'],
                         return_to_decision_ns=o['now_ns']-o['data']['returned_ns']) for o in reads[-10:]],
        phases={name:phase(rows,reads,lo,hi) for name,lo,hi in phase_ranges},
        post_T1_complete_rows=sum(int(e['evidence']['returned_ns'])>=t1 for e in rows),
        all_gaps_over_500ms=[g for g in context['gaps'] if g['host_gap_ns']>500_000_000])
    require(result['row_pair_gap_is_post_window'] and result['suspension_after_T1_ns']>0,'Failure scope must match evidence')
    return result


def compare_c01_c02(c01,c02):
    summaries,contexts={},{}
    for key,path in (('C01',c01),('C02',c02)):
        summaries[key],contexts[key]=inspect_bundle(path)
    a,b=summaries['C01'],summaries['C02']
    require(a['authorization_consumed']['reference']!=b['authorization_consumed']['reference'], 'Distinct permissions required')
    sources_a={x['path']:x['sha256'] for x in a['provenance']['sources']}
    sources_b={x['path']:x['sha256'] for x in b['provenance']['sources']}
    shared=['protocol','policy','receivers','ports','baud','storage_policy','transmitter','eligibility_revision','line_policy_revision']
    comparability=dict(acquisition_sources_identical=sources_a==sources_b,
        source_count=len(sources_a),fixed_plan_fields_equal={k:a['plan'][k]==b['plan'][k] for k in shared},
        serial_settings_equal=a['runtime']['receivers'][RX]['serial_settings']==b['runtime']['receivers'][RX]['serial_settings'],
        same_selected_identity=a['provenance']['transport']['identities'][RX]==b['provenance']['transport']['identities'][RX],
        installed_binaries_attested=False,mounting_and_no_changes_since_C01='current operator declaration; not an independent measurement',
        repeated_READY='Both recorded attempts reached initial availability; no general repeatability or electrical behavior claim')
    result=dict(schema='tesis-rx02-C02-gap-diagnostic-1',bundles=summaries,comparability=comparability,
        incident=incident_details(contexts['C02'],b),
        statistical_method='Equal actual observed intervals; nearest-rank p95/p99; zero host gaps retained as shared-read timestamps',
        diagnostic_activity=dict(physical_UART_opened=False,new_acquisition=False,parameters_changed=False,
                                 calibration=False,training=False,classification=False,replacement_prepared=False),
        conclusions=dict(C02_remains_ineligible=True,label_not_reconstructed=True,C01_result_unchanged=True,
            recorded_host_delivery_and_processing_pipeline_degraded=True,
            one_second_gap_in_firmware_timestamps_at_trigger=False,
            exclusive_RF_USB_firmware_disk_or_scheduler_cause_demonstrated=False,
            acquisition_recommended_or_prepared=False),
        timing_limits=['Decision now_ns follows durable raw write/flush/fsync but precedes reducer and operations-journal fsync',
          'Return-to-decision includes lock, scheduling, raw persistence and Python overhead; no isolated disk latency',
          'Decision-to-next-operation includes reducer, journal fsync, notifications, console/input and scheduling; no isolated parser duration',
          'No per-stage end clocks, BOOTTIME, scheduler trace, USB URBs or RF/transmitter log; no absolute one-way delivery latency',
          'Same-chunk rows may be parsed after suspension; this is not a resumed acquisition or new observation interval'])
    for key,path in (('C01',c01),('C02',c02)):
        require(inventory(path)==summaries[key]['original_files'],'Original bundle changed')
    return result,{k:ctx['audit'] for k,ctx in contexts.items()}
