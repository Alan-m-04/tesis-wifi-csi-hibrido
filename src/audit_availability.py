"""Offline v3 byte/ledger/decision audit; never searches for a replacement window."""
import csv
from datetime import datetime
import hashlib
import json

import capture_csi_multi as capture
from controlled_protocol import V3, STOP_POLICY_V2, AVAILABILITY_V3
from availability_window import LineFramer, transition_error
from audit_bounded_stop import audit_bounded_stop


def inclusion(line, t0, t1):
    if t0 is None:
        return 'window_not_started'
    s, e = int(line['first_read_started_ns']), int(line['returned_ns'])
    if e < t0:
        return 'preamble'
    if s < t0:
        return 'crosses_start' if e < t1 else 'crosses_both_boundaries'
    if e >= t1:
        return 'at_or_after_deadline'
    return 'included' if line['kind'] == 'row' and not line.get('continuity_error') else 'invalid_in_window'


def intersects(line, t0, t1):
    return t0 is not None and int(line['first_read_started_ns']) < t1 and int(line['returned_ns']) >= t0


def coverage(lines, t0, t1):
    times = [int(x['returned_ns']) for x in lines if x['inclusion'] == 'included']
    if t0 is None:
        return {'minimum_rows_ok': False, 'included_rows': 0, 'first_ns': None, 'last_ns': None,
                'start_gap_ns': None, 'end_gap_ns': None, 'interior_gaps_ns': [], 'max_observed_gap_ns': None,
                'max_gap_limit_ns': None, 'continuous_observation_claimed': False}
    gaps = [b - a for a, b in zip(times, times[1:])]
    start_gap, end_gap = ((times[0] - t0, t1 - times[-1]) if times else (t1 - t0, t1 - t0))
    return {'minimum_rows_ok': bool(times), 'included_rows': len(times),
            'first_ns': str(times[0]) if times else None, 'last_ns': str(times[-1]) if times else None,
            'start_gap_ns': str(start_gap), 'end_gap_ns': str(end_gap),
            'interior_gaps_ns': [str(x) for x in gaps],
            'max_observed_gap_ns': str(max([start_gap, end_gap] + gaps)),
            'max_gap_limit_ns': None, 'continuous_observation_claimed': False}


def audit_trace(root, manifest, session, ledgers, raws):
    from validate_capture import sha
    item = manifest['coordination_trace']
    if item['name'] != 'availability.events.jsonl':
        raise ValueError('Unexpected coordination trace')
    path = root / item['name']
    if path.is_symlink() or not path.is_file():
        raise ValueError('Regular coordination trace required')
    events = [json.loads(x) for x in path.read_text().splitlines()]
    ok = sha(path) == item['sha256'] and path.stat().st_size == item['bytes']
    framers = {rx: LineFramer(rx) for rx in capture.RECEIVERS}
    states = {rx: {'active': False, 'ready': None, 'streak': [], 'previous': None, 'read_index': 0}
              for rx in capture.RECEIVERS}
    lines = {rx: [] for rx in capture.RECEIVERS}
    expected_lines = []
    chunk_seq = None
    a = d = t0 = t1 = None
    timed_out = False
    fatal = None
    required_fatal = []
    disqualified = False
    conflicts = []
    last = int(session['capture_start_monotonic_ns'])
    end = int(session['capture_deadline_monotonic_ns'])
    common = session['controlled']
    wait_ns, window_ns = int(common['effective_wait_ns']), int(common['effective_window_ns'])
    armed_valid = False
    finished_seen = False
    for index, event in enumerate(events):
        when = int(event['processed_ns'])
        ok &= event['seq'] == index and last <= when <= end and not finished_seen
        last = when
        kind, rx = event['kind'], event.get('receiver')
        if kind == 'begin':
            ok &= a is None
            a, d = int(event['A_ns']), int(event['D_ns'])
            ok &= int(session['capture_start_monotonic_ns']) <= a <= when and d == a + wait_ns
        elif kind == 'reader_active':
            ok &= not states[rx]['active']
            states[rx]['active'] = True
        elif kind == 'chunk':
            ok &= chunk_seq is None and not expected_lines
            state = states[rx]
            j = state['read_index']
            if j >= len(ledgers[rx]):
                return False, lines, False
            read = ledgers[rx][j]
            chunk = raws[rx][read['offset']:read['offset'] + read['size']]
            ok &= (event['read_index'] == j and event['read'] == read
                   and int(read['returned_ns']) <= when and state['active']
                   and event['chunk_sha256'] == hashlib.sha256(chunk).hexdigest())
            expected_lines = framers[rx].feed(chunk, j, read)
            state['read_index'] += 1
            chunk_seq = index
        elif kind == 'line':
            if not expected_lines or chunk_seq is None:
                return False, lines, False
            line = expected_lines.pop(0)
            state = states[rx]
            error = transition_error(state['previous'], line) if line['kind'] == 'row' else None
            if error:
                line['continuity_error'] = error
            ok &= event['chunk_seq'] == chunk_seq and event['evidence'] == line
            post_ready = state['ready'] is not None
            bad = line['kind'] in ('invalid', 'error') or error is not None or (
                post_ready and line['kind'] in ('reset', 'ready'))
            # Pre-READY ROM markers are startup context. They still invalidate a
            # late activation if their publication contradicts a used READY epoch.
            activation_bad = bad or line['kind'] == 'reset' or (post_ready and line['kind'] == 'info')
            if t0 is not None and int(line['returned_ns']) < t0 and activation_bad:
                conflicts.append(index)
            derived = dict(line, event_seq=index, processed_ns=event['processed_ns'],
                           problem=bad, post_ready=post_ready)
            lines[rx].append(derived)
            k = line['kind']
            required_reason = (line.get('fatal_if_ready') if post_ready and line.get('fatal_if_ready') else
                               'duplicate_ready' if k == 'ready' and post_ready else
                               'post_ready_' + k if k in ('reset', 'error') and post_ready else
                               'callback_restart' if error == 'callback_restart' and post_ready else None)
            if required_reason is not None:
                required_fatal.append((rx, required_reason)); disqualified = True
            if k == 'ready' and not post_ready:
                state['ready'] = index; state['streak'] = []
            elif k == 'row':
                if error:
                    state['streak'] = []
                elif post_ready:
                    state['streak'] = (state['streak'] + [index])[-3:]
                state['previous'] = line
            elif k != 'neutral':
                state['streak'] = []
        elif kind == 'batch_complete':
            ok &= chunk_seq == event['chunk_seq'] and not expected_lines
            chunk_seq = None
        elif kind == 'freshness_expired':
            state = states[rx]
            ok &= event['streak'] == state['streak'] and bool(state['streak'])
            if state['streak']:
                previous = events[state['streak'][-1]]['evidence']
                ok &= when - int(previous['returned_ns']) > AVAILABILITY_V3['freshness_ns']
            state['streak'] = []
        elif kind == 'armed':
            decision = int(event['T0_ns'])
            eligible = (a is not None and t0 is None and not timed_out and fatal is None and not disqualified
                        and chunk_seq is None and not expected_lines and decision < d
                        and (int(events[index - 1]['processed_ns']) if index else a) <= decision <= when)
            for role, state in states.items():
                cited = event['evidence'][role]
                eligible &= (state['active'] and state['ready'] is not None and len(state['streak']) == 3
                             and cited == {'ready_seq': state['ready'], 'row_seqs': state['streak']})
                for ref in state['streak']:
                    eligible &= int(events[ref]['processed_ns']) <= decision
                if state['streak']:
                    eligible &= 0 <= decision - int(events[state['streak'][-1]]['evidence']['returned_ns']) <= AVAILABILITY_V3['freshness_ns']
            t0, t1 = decision, int(event['T1_ns'])
            eligible &= t1 == t0 + window_ns
            armed_valid = bool(eligible)
            ok &= armed_valid
        elif kind == 'availability_timeout':
            ok &= t0 is None and not timed_out and int(event['deadline_ns']) == d and when >= d
            timed_out = True
        elif kind == 'fatal':
            if required_fatal:
                expected_rx, expected_reason = required_fatal.pop(0)
                ok &= event.get('receiver') == expected_rx and event['reason'] == expected_reason
            else:
                ok &= event['reason'] in ('reader_error', 'reader_exception', 'lifecycle_error', 'operator_abort', 'close_error')
            if fatal is None:
                fatal = event['reason']
        elif kind == 'activation_inconsistent':
            ok &= event['evidence_seq'] in conflicts
        elif kind == 'reader_finished':
            ok &= states[rx]['active']
            states[rx]['active'] = False
            stopped = int(event['stopped_ns'])
            actual_stop = session['results'][rx]['stop']
            ok &= (stopped <= when and event['stopped_ns'] == actual_stop['stopped_ns']
                   and event['reason'] == actual_stop['stop_reason'])
            if t0 is not None and stopped < t0:
                conflicts.append(index)
            if t0 is not None and stopped < t1:
                required_fatal.append((rx, 'reader_termination_before_T1')); disqualified = True
            elif t0 is None and not timed_out and fatal is None:
                required_fatal.append((rx, 'reader_termination_before_availability')); disqualified = True
        elif kind == 'finished':
            ok &= event['status'] == session['status'] and chunk_seq is None
            finished_seen = True
        else:
            ok = False
    ok &= (finished_seen and chunk_seq is None and not expected_lines and not required_fatal
           and all(states[rx]['read_index'] == len(ledgers[rx]) for rx in states)
           and common['A_ns'] == (None if a is None else str(a))
           and common['D_ns'] == (None if d is None else str(d))
           and common['T0_ns'] == (None if t0 is None else str(t0))
           and common['T1_ns'] == (None if t1 is None else str(t1))
           and common['stop_deadline_ns'] == (str(t1) if t1 is not None else str(d) if timed_out else None)
           and common['timed_out'] is timed_out and common['fatal'] == fatal
           and common['activation_conflicts'] == conflicts)
    opening = [e for e in session['lifecycle'] if e['event'] == 'opening' and e.get('receiver') == 'RX-01']
    opened = [e for e in session['lifecycle'] if e['event'] == 'opened' and e.get('receiver') == 'RX-01']
    ok &= (len(opening) == len(opened) == 1 and a is not None and
           int(opening[0]['monotonic_ns']) <= a <= int(opened[0]['monotonic_ns']))
    return bool(ok), lines, armed_valid and not conflicts


def audit_availability_capture(root, manifest, session):
    from validate_capture import NAMES, ROLES, regular_file, sha, scan_raw, audit_read_ledger
    from controlled_capture import PORTS
    common = session['controlled']
    if (manifest is None or manifest.get('schema') != 'tesis-controlled-capture-v3'
            or manifest.get('source_run_kind') != V3 or common['availability_policy'] != AVAILABILITY_V3
            or common['stop_policy'] != STOP_POLICY_V2 or common.get('stable_window') is not None):
        raise ValueError('Fixed v3 manifest/policies required')
    if session['evidence_type'] != 'synthetic_fixture' and (
            int(common['effective_window_ns']) != AVAILABILITY_V3['window_ns'] or
            int(common['effective_wait_ns']) != AVAILABILITY_V3['max_wait_ns']):
        raise ValueError('Physical v3 requires fixed 10 s wait and 30 s window')
    if int(common['effective_window_ns']) <= 0 or int(common['effective_wait_ns']) <= 0:
        raise ValueError('Positive synthetic or physical durations required')
    if (int(float(session['requested_seconds']) * 1e9) != int(common['effective_window_ns'])
            or common['seconds'] != session['requested_seconds'] or manifest['source_run_id'] != session['session_id']):
        raise ValueError('Session identity or nominal duration mismatch')
    if set(session['results']) != set(ROLES) or session['receivers'] != PORTS:
        raise ValueError('Exactly two fixed receivers required')
    entries = manifest['files']
    if len(entries) != len(NAMES) or {x['name'] for x in entries} != NAMES:
        raise ValueError('Exactly seven original files required')
    manifest_ok = all(regular_file(root, x['name']).stat().st_size == x['bytes'] and
                      sha(regular_file(root, x['name'])) == x['sha256'] for x in entries)
    gate, end = int(session['capture_start_monotonic_ns']), int(session['capture_deadline_monotonic_ns'])
    if not 0 <= gate < end:
        raise ValueError('Invalid full connection envelope')
    raws, ledgers, parsed, summaries, exports = {}, {}, {}, {}, {}
    report = {'schema': 'tesis-offline-capture-audit-v3', 'operation': 'offline_validation',
              'new_physical_capture': False, 'source_evidence_type': session['evidence_type'],
              'manifest_ok': manifest_ok, 'session_status': session['status'], 'receivers': {}}
    for rx, serial in ROLES.items():
        raw = regular_file(root, rx.lower() + '.serial.log')
        exported = regular_file(root, rx.lower() + '.csv')
        raws[rx] = raw.read_bytes()
        ledger_path = root / (rx.lower() + '.reads.jsonl')
        if ledger_path.is_symlink() or not ledger_path.is_file():
            raise ValueError('Regular read ledger required')
        ledgers[rx] = [json.loads(x) for x in ledger_path.read_text().splitlines()]
        parsed[rx] = p = scan_raw(raw)
        summaries[rx] = s = json.loads(regular_file(root, rx.lower() + '.summary.json').read_text())
        with exported.open(newline='') as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != capture.EXTRA_FIELDS + capture.FIELDS:
                raise ValueError('Unexpected CSV schema')
            exports[rx] = rows = list(reader)
        if any(None in r or any(v is None for v in r.values()) for r in rows):
            raise ValueError('Truncated CSV')
        frames_match = p['rows'] == [[r[k] for k in capture.FIELDS] for r in rows]
        identity = all(r['receiver_id'] == rx and r['usb_serial'] == serial and r['session_id'] == session['session_id'] for r in rows)
        times = [int(r['host_monotonic_ns']) for r in rows]
        wall = [datetime.fromisoformat(r['host_timestamp_utc']) for r in rows]
        hosts = (all(gate <= t < end for t in times) and all(b >= a for a, b in zip(times, times[1:]))
                 and all(t.utcoffset() is not None for t in wall) and all(b >= a for a, b in zip(wall, wall[1:])))
        original = p['collector_quality_ok'] and not s.get('error')
        summary_ok = (s == session['results'][rx] and s.get('valid_rows') == len(rows)
            and s.get('receiver_id') == rx and s.get('usb_serial') == serial
            and all(s.get(k) == v for k, v in p['counts'].items())
            and s.get('trailing_bytes') == p['trailing_bytes'] and s.get('format_reception_ok') == original
            and s.get('serial_log_sha256') == sha(raw) and s.get('csv_sha256') == sha(exported))
        ledger_ok = audit_read_ledger(root, rx, manifest, p, rows, gate, end)
        stop_metadata, stop_quality = audit_bounded_stop(root, rx, s, p, session)
        matrix = all(n['len'] == 256 and n['first_word_invalid'] == 0 and n['sig_mode'] == 1
                     and n['mcs'] == 0 and n['stbc'] == 0 for n in p['numeric'])
        report['receivers'][rx] = {'valid_rows': len(rows), 'raw_sha256': sha(raw), 'csv_sha256': sha(exported),
            'raw_frames_equal_csv': frames_match, 'integrity_ok': all((manifest_ok, identity, hosts, summary_ok, frames_match, ledger_ok, stop_metadata)),
            'collector_quality_recorded': s['format_reception_ok'], 'collector_quality_recomputed': original,
            'representation_profile_ok': matrix, 'complete_rows_quality_ok': bool(rows) and matrix and not any(
                p['counts'][key] for key in ('malformed_rows', 'unexpected_source_rows', 'unexpected_metadata_rows',
                    'callback_id_gaps', 'nonincreasing_ids', 'device_time_discontinuities',
                    'queue_drop_increment', 'queue_counter_decreases')),
            'counts': p['counts'], 'trailing_bytes': p['trailing_bytes'], 'embedded_boot_lines': p['embedded_boot_lines'],
            'initial_boot_markers': p['initial_boot_markers'], 'midstream_boot_markers': p['midstream_boot_markers'],
            'orphan_fragment_lines': p['orphan_fragment_lines'], 'read_ledger_ok': ledger_ok,
            'stop_metadata_ok': stop_metadata, 'stop_quality_ok': stop_quality, 'stop': s['stop']}

    trace_ok, lines, activation_ok = audit_trace(root, manifest, session, ledgers, raws)
    report['coordination_trace_ok'] = trace_ok
    t0 = None if common['T0_ns'] is None else int(common['T0_ns'])
    t1 = None if common['T1_ns'] is None else int(common['T1_ns'])
    postflight = all(manifest.get('postflight', {}).get(rx, {}).get('identity_ok') is True for rx in ROLES)
    report['postflight_identity_ok'] = postflight
    recorded_integrity = manifest_ok and trace_ok and all(x['integrity_ok'] for x in report['receivers'].values())
    shared = recorded_integrity and postflight and all(x['stop_quality_ok'] for x in report['receivers'].values())
    window_receivers = {}
    for rx, item in report['receivers'].items():
        item['integrity_ok'] &= trace_ok
        index_by_end = {e: i for i, e in enumerate(parsed[rx]['row_byte_ends'])}
        for line in lines[rx]:
            line['inclusion'] = inclusion(line, t0, t1)
            line['csv_record_index_0based'] = index_by_end.get(line['byte_end'])
        # Preserve trailing fragments with their real first/last read references.
        tail = parsed[rx]['trailing_bytes']
        if tail:
            offset = len(raws[rx]) - tail
            candidates = [(j, e) for j, e in enumerate(ledgers[rx]) if e['offset'] + e['size'] > offset]
            if not candidates:
                raise ValueError('Tail without read evidence')
            first, last = candidates[0], candidates[-1]
            lines[rx].append({'kind': 'fragment', 'problem': True, 'byte_offset': offset, 'byte_end': len(raws[rx]),
                'byte_length': tail, 'line_sha256': hashlib.sha256(raws[rx][offset:]).hexdigest(),
                'first_read_index': first[0], 'last_read_index': last[0], 'first_read_started_ns': first[1]['started_ns'],
                'returned_ns': last[1]['returned_ns'], 'inclusion': 'incomplete_fragment', 'csv_record_index_0based': None})
        problems = [x for x in lines[rx] if x['problem']]
        intersects_window = [x for x in problems if intersects(x, t0, t1)]
        stats = coverage(lines[rx], t0, t1)
        item['quality_ok'] = bool(item['integrity_ok'] and item['complete_rows_quality_ok'] and
                                  item['stop_quality_ok'] and not problems and not tail and not item['midstream_boot_markers'])
        item['format_ok'] = not problems
        window_receivers[rx] = {'integrity_ok': item['integrity_ok'], 'format_continuity_ok': not intersects_window,
            'problem_event_seqs': [x.get('event_seq') for x in intersects_window], 'coverage': stats,
            'stop_quality_ok': item['stop_quality_ok'], 'index': lines[rx],
            'quality_ok': bool(shared and not intersects_window and stats['minimum_rows_ok'])}
    complete = session['status'] == 'completed' and t0 is not None and end >= t1 and not common['fatal']
    window_ok = complete and activation_ok and shared and all(x['quality_ok'] for x in window_receivers.values())
    full_ok = complete and all(x['quality_ok'] for x in report['receivers'].values()) and postflight
    report['connection_full'] = {'quality_ok': bool(full_ok), 'status': 'conforme' if full_ok else 'rechazada',
        'integrity_ok': manifest_ok and trace_ok and all(x['integrity_ok'] for x in report['receivers'].values()),
        'format_ok': all(x['format_ok'] for x in report['receivers'].values()),
        'complete_rows_quality_ok': all(x['complete_rows_quality_ok'] for x in report['receivers'].values()),
        'stop_quality_ok': all(x['stop_quality_ok'] for x in report['receivers'].values())}
    report['experimental_window'] = {'quality_ok': bool(window_ok),
        'status': 'no_iniciada' if t0 is None else 'conforme' if window_ok else 'rechazada',
        'T0_ns': common['T0_ns'], 'T1_ns': common['T1_ns'], 'integrity_ok': recorded_integrity,
        'shared_prerequisites_ok': shared,
        'availability': {'activation_ok': activation_ok and trace_ok, **{k: common[k] for k in
                        ('A_ns', 'D_ns', 'timed_out', 'fatal', 'activation_conflicts')}},
        'format_continuity_ok': all(x['format_continuity_ok'] for x in window_receivers.values()),
        'coverage_minimum_ok': all(x['coverage']['minimum_rows_ok'] for x in window_receivers.values()),
        'stop_quality_ok': all(x['stop_quality_ok'] for x in report['receivers'].values()),
        'complete_duration_observed': complete, 'flow_drop_policy': AVAILABILITY_V3['flow_drop'],
        'max_gap_limit_ns': None, 'campaign_model_suitability': 'not_evaluated',
        'receivers': window_receivers}
    report['quality_ok'] = bool(full_ok and window_ok)  # Neither scope can approve the other.
    return report
