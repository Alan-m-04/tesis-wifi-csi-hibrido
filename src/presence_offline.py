"""LLTF52 feature extraction only from an audited, original v3 window.

Required incompleteness invalidates the receiver/session features, never just
silently drops a row/tone. No serial imports, calibration or inference calls.
Binary64 extraction; the separately verified head port accepts binary32 fields.
"""
import copy
import math
import statistics

from ruview_presence_port import CONTRACT, RUVIEW_COMMIT

RECEIVERS = {'RX-01': '5C93199744', 'RX-02': '5C93200689'}
INDICES = list(range(32)) + list(range(-32, 0))
ACTIVE = [k for k in INDICES if 1 <= abs(k) <= 26]
PILOTS = {-21, -7, 7, 21}


def _role(k):
    return 'pilot' if k in PILOTS else 'data' if k in ACTIVE else 'DC' if k == 0 else 'guard'


def row_mean(frame, receiver):
    """Return one actual scalar or a reason; no partial-set fallback."""
    try:
        if frame['receiver_id'] != receiver or frame['usb_serial'] != RECEIVERS[receiver]:
            return None, 'receiver_identity_mismatch'
        candidates = [b for b in frame['blocks'] if b['ltf'] == 'LLTF']
        if len(candidates) != 1:
            return None, 'missing_or_duplicate_LLTF'
        b = candidates[0]
        if b['byte_start'] != 0 or b['byte_stop'] != 128 or b['indices'] != INDICES:
            return None, 'LLTF_layout_mismatch'
        for field in ('roles', 'hardware_valid', 'cfr_usable', 'real', 'imag', 'amplitude'):
            if len(b[field]) != 64:
                return None, 'incomplete_' + field
        amplitudes = []
        for i, k in enumerate(INDICES):
            role = _role(k)
            hw, usable = b['hardware_valid'][i], b['cfr_usable'][i]
            if b['roles'][i] != role or type(hw) is not bool or type(usable) is not bool or usable != (hw and k in ACTIVE):
                return None, 'mask_or_role_mismatch'
            if k not in ACTIVE:
                continue
            if not hw or not usable:
                return None, 'required_tone_invalid'
            real, imag, amplitude = b['real'][i], b['imag'][i], b['amplitude'][i]
            if any(type(x) is not int or not -128 <= x <= 127 for x in (real, imag)):
                return None, 'required_IQ_incomplete'
            if type(amplitude) not in (int, float) or not math.isfinite(amplitude) or amplitude < 0:
                return None, 'required_amplitude_incomplete'
            actual = math.hypot(real, imag)
            if not math.isclose(amplitude, actual, rel_tol=1e-12, abs_tol=1e-12):
                return None, 'amplitude_IQ_mismatch'
            amplitudes.append(actual)
        return statistics.fmean(amplitudes), None
    except (KeyError, TypeError, ValueError):
        return None, 'required_row_fields_incomplete'


def extract_window(canonical, receiver):
    """Separate RX result. Historical rejection is data, never overwritten."""
    if receiver not in RECEIVERS:
        raise ValueError('Known RX identity required')
    result = {'schema': 'tesis-presence-offline-features-v1', 'contract': CONTRACT,
        'ruview_commit': RUVIEW_COMMIT, 'implementation': 'Python adapter; head is an explicit separately tested port',
        'receiver': receiver, 'usb_serial': RECEIVERS[receiver], 'ltf': 'LLTF',
        'active_tone_indices': ACTIVE[:], 'nominal_active_tones': 52,
        'primary_input': receiver == 'RX-01', 'RX_fusion_performed': False,
        'feature_status': 'no evaluable', 'presence_status': 'no evaluable',
        'presence': None, 'confidence_margin': None, 'calibration_used': False, 'inference_executed': False,
        'features': None, 'row_features': [], 'reasons': [],
        'unused_head_fields': ['motion', 'breathing_score', 'breathing_hz', 'heart_score', 'heart_hz'],
        'numeric_contract': 'binary64 hypot, equal-tone row mean, equal-row population mean/variance; no sampling rate assumed'}
    result.update(source_run_id=canonical.get('run_id'), evidence_type=canonical.get('evidence_type'),
                  connection_full=copy.deepcopy(canonical.get('connection_full')),
                  global_quality_ok=canonical.get('strict_quality_ok'))
    try:
        if (canonical['schema'] != 'tesis-canonical-csi-v1' or
                canonical['evidence_type'] not in ('physical_capture', 'synthetic_fixture') or
                type(canonical['strict_quality_ok']) is not bool or
                type(canonical['connection_full']['quality_ok']) is not bool):
            result['reasons'].append('required_history_or_schema_invalid')
        w = canonical['experimental_window']
        result['experimental_window'] = copy.deepcopy({k: v for k, v in w.items() if k != 'receivers'})
        result['coverage'] = copy.deepcopy(w['receivers'][receiver]['coverage'])
        t0, t1 = int(w['T0_ns']), int(w['T1_ns'])
        result['T0_ns'], result['T1_ns'] = str(t0), str(t1)
        if canonical['original_session']['protocol'] != 'controlled_dual_v3' or t1 - t0 != 30_000_000_000:
            result['reasons'].append('original_v3_window_required')
        if not all(w[k] is True for k in ('quality_ok', 'integrity_ok', 'shared_prerequisites_ok')):
            result['reasons'].append('experimental_window_not_conforming')
        if canonical['receivers'][receiver]['usb_serial'] != RECEIVERS[receiver]:
            result['reasons'].append('receiver_identity_mismatch')
        profile = canonical['profile']
        if (profile['target'] != 'esp32s3' or profile['channel'] != 11 or profile['bandwidth'] != 'HT20' or
                profile['receivers'][receiver] != RECEIVERS[receiver]):
            result['reasons'].append('profile_mismatch')
        frames = canonical['receivers'][receiver]['frames']
        included, excluded = [], []
        for frame in frames:
            if type(frame['received_in_experimental_window']) is not bool:
                raise ValueError('Membership must be explicit')
            selected = frame['timing_phase'] == 'included'
            if selected != frame['received_in_experimental_window']:
                result['reasons'].append('membership_mismatch')
            r = frame['window_reference']
            if r['inclusion'] != frame['timing_phase'] or r['kind'] != 'row':
                result['reasons'].append('row_trace_inclusion_mismatch')
            inside = int(r['first_read_started_ns']) >= t0 and int(r['returned_ns']) < t1
            if inside != selected or str(r['returned_ns']) != str(frame['host_monotonic_ns']):
                result['reasons'].append('prospective_boundary_or_timestamp_mismatch')
            (included if selected else excluded).append(frame)
        result['complete_rows'] = len(frames)
        result['included_rows'] = len(included)
        result['excluded_rows'] = len(excluded)
        result['excluded_row_references'] = [copy.deepcopy(f['window_reference']) for f in excluded]
        if not included or len(included) != result['coverage']['included_rows']:
            result['reasons'].append('required_included_rows_incomplete')
        if included:
            times = [int(f['window_reference']['returned_ns']) for f in included]
            gaps = [b-a for a, b in zip(times, times[1:])]
            start, end = times[0]-t0, t1-times[-1]
            observed = {'first_ns': str(times[0]), 'last_ns': str(times[-1]),
                        'start_gap_ns': str(start), 'end_gap_ns': str(end),
                        'interior_gaps_ns': [str(x) for x in gaps],
                        'max_observed_gap_ns': str(max([start, end] + gaps))}
            if any(x < 0 for x in gaps) or any(result['coverage'][k] != v for k, v in observed.items()):
                result['reasons'].append('coverage_trace_mismatch')
        for f in included:
            value, reason = row_mean(f, receiver)
            trace = {'source_run_id': canonical['run_id'], 'receiver': receiver,
                     'csv_record_index_0based': f['csv_record_index_0based'], 'callback_id': f['callback_id'],
                     'host_monotonic_ns': f['host_monotonic_ns'], 'local_timestamp_us_uint32': f['local_timestamp_us_uint32'],
                     'window_reference': copy.deepcopy(f['window_reference']),
                     'x_mean_amplitude_LLTF52': value, 'status': 'evaluable' if reason is None else 'no evaluable',
                     'reason': reason}
            result['row_features'].append(trace)
            if reason:
                result['reasons'].append(reason)
        if result['reasons']:
            result['reasons'] = sorted(set(result['reasons']))
            return result
        values = [r['x_mean_amplitude_LLTF52'] for r in result['row_features']]
        result.update(feature_status='evaluable', presence_status='sin calibración',
                      features={'n': len(values), 'mean': statistics.fmean(values), 'variance': statistics.pvariance(values)})
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        result['reasons'].append('required_window_fields_incomplete:' + type(exc).__name__)
    return result
