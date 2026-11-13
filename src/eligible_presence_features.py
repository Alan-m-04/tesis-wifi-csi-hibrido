"""Features only for prospectively eligible singleton RX-02 windows.

Keeps the historical dual-v3 extractor unchanged. No calibration or inference.
The audited eligibility, membership and complete LLTF52 mask are prerequisites.
"""
import copy
import statistics
from presence_offline import row_mean
from ruview_presence_port import CONTRACT


def extract_eligible_window(audit, slot_id, frames):
    result = dict(contract=CONTRACT, operation='features_only', feature_status='no evaluable',
        features=None, row_features=[], reasons=[], presence=None, inference_executed=False,
        calibration_executed=False, receiver='RX-02', slot_id=slot_id)
    try:
        state = audit['state']
        result['connection_full'] = copy.deepcopy(state['connection'])
        if audit.get('integrity_ok') is not True or audit.get('replay_ok') is not True:
            raise ValueError('audited_integrity_and_replay_required')
        if state['protocol'] != 'presence_rx02_persistent_1':
            raise ValueError('explicit_RX02_protocol_required')
        window = next(w for w in state['windows'] if w['id'] == slot_id)
        eligibility = next(w for w in audit['exploratory_eligibility']['windows'] if w['slot_id'] == slot_id)
        result['window_eligibility'] = copy.deepcopy(eligibility)
        if eligibility.get('eligible') is not True:
            raise ValueError('window_not_eligible_exploratory')
        if window['label']['status'] != 'declared' or not window['label_quality_ok']:
            raise ValueError('prospective_operator_label_required')
        refs = window['receivers']['RX-02']['included_line_references']
        if not refs or [f['window_reference'] for f in frames] != refs:
            raise ValueError('exact_original_membership_required')
        t0, t1 = window['T0_ns'], window['T1_ns']
        if t1-t0 != 30_000_000_000:
            raise ValueError('original_30s_window_required')
        previous = t0
        for frame, ref in zip(frames, refs):
            when = int(ref['returned_ns'])
            if not t0 <= int(ref['first_read_started_ns']) <= when < t1 or when < previous:
                raise ValueError('original_time_boundaries_required')
            previous = when
            value, reason = row_mean(frame, 'RX-02')
            result['row_features'].append(dict(value=value, reason=reason,
                host_monotonic_ns=str(when), reference=copy.deepcopy(ref)))
            if reason:result['reasons'].append(reason)
        if len(frames) != window['receivers']['RX-02']['coverage']['included_rows']:
            raise ValueError('original_row_count_required')
        if result['reasons']:
            return result
        values = [f['value'] for f in result['row_features']]
        result.update(feature_status='evaluable', features=dict(n=len(values),
            mean=statistics.fmean(values), variance=statistics.pvariance(values)))
    except (KeyError, TypeError, ValueError, StopIteration) as exc:
        result['reasons'].append(str(exc) or type(exc).__name__)
    return result
