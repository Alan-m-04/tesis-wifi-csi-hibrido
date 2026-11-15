"""Read-only boundary diagnosis of an existing controlled capture; no UART."""
import hashlib
import json
from pathlib import Path

from validate_capture import audit_capture, scan_raw


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def diagnose(run):
    run = Path(run).resolve()
    bundle = json.loads((run / 'bundle-manifest.json').read_text())
    pinned = {}
    for item in bundle['files']:
        path = run / item['path']
        if path.is_symlink() or not path.resolve().is_relative_to(run) or not path.is_file():
            raise ValueError('Unsafe bundle path')
        data = path.read_bytes()
        if len(data) != item['bytes'] or sha_bytes(data) != item['sha256']:
            raise ValueError('Bundle integrity mismatch: ' + item['path'])
        pinned[item['path']] = sha_bytes(data)
    manifest = json.loads((run / 'capture-manifest.json').read_text())
    audit = audit_capture(run / 'capture', manifest)
    if not audit['manifest_ok'] or not all(r['integrity_ok'] for r in audit['receivers'].values()):
        raise ValueError('Cannot diagnose unverified transport records')
    session = json.loads((run / 'capture/session.json').read_text())
    start = int(session['controlled']['common_start_ns'])
    deadline = int(session['controlled']['common_deadline_ns'])
    lifecycle = session['lifecycle']
    opened = {e['receiver']: int(e['monotonic_ns']) for e in lifecycle if e['event'] == 'opened'}
    joined = next(int(e['monotonic_ns']) for e in lifecycle if e['event'] == 'readers_joined')
    closed = next(int(e['monotonic_ns']) for e in lifecycle if e['event'] == 'ports_closed')
    output = {'schema': 'tesis-offline-boundary-diagnosis-v1', 'operation': 'read_only_offline',
              'run_id': session['session_id'], 'new_physical_capture': False,
              'common_start_ns': str(start), 'common_deadline_ns': str(deadline),
              'readers_joined_ns': str(joined), 'ports_closed_ns': str(closed),
              'session_quality_ok': audit['quality_ok'], 'derived_window': None,
              'bundle_files_verified': len(pinned), 'audit': audit, 'receivers': {}}
    for rx in opened:
        raw_path = run / 'capture' / (rx.lower() + '.serial.log')
        raw = raw_path.read_bytes()
        events = [json.loads(line) for line in (run / 'capture' / (rx.lower() + '.reads.jsonl')).read_text().splitlines()]

        def region(begin, end):
            overlapping = [dict(event,
                                overlap_start=max(begin, event['offset']),
                                overlap_end=min(end, event['offset'] + event['size']),
                                started_relative_to_deadline_ns=int(event['started_ns']) - deadline,
                                returned_relative_to_deadline_ns=int(event['returned_ns']) - deadline,
                                returned_after_open_ns=int(event['returned_ns']) - opened[rx])
                           for event in events if event['offset'] < end and event['offset'] + event['size'] > begin]
            return {'offset': begin, 'end_exclusive': end, 'bytes': end - begin,
                    'sha256': sha_bytes(raw[begin:end]), 'hex': raw[begin:end].hex(), 'reads': overlapping}

        first_lf = raw.index(b'\n') + 1
        rom = raw[:first_lf].find(b'ESP-ROM:')
        tail_start = raw.rfind(b'\n') + 1
        parsed = scan_raw(raw_path)
        first_csi_line = next(i for i, line in enumerate(raw.split(b'\n')[:-1])
                              if line.startswith(b'CSI_DATA,'))
        after_first = raw.split(b'\n')[first_csi_line:-1]
        invalid_utf8_lines = []
        for i, line in enumerate(after_first, first_csi_line + 1):
            try:
                line.decode('utf-8', errors='strict')
            except UnicodeError:
                invalid_utf8_lines.append(i)
        last_complete_end = parsed['row_byte_ends'][-1]
        last_complete_start = raw.rfind(b'\n', 0, last_complete_end - 1) + 1
        tail = region(tail_start, len(raw))
        report = {'raw_bytes': len(raw), 'raw_sha256': sha_bytes(raw), 'read_count': len(events),
                  'opened_ns': str(opened[rx]), 'first_line': region(0, first_lf),
                  'prefix_before_rom': region(0, rom) if rom > 0 else None,
                  'rom_marker_offset': rom, 'tail': tail,
                  'last_complete_line': region(last_complete_start, last_complete_end),
                  'last_read': events[-1],
                  'last_read_to_join_ns': joined - int(events[-1]['returned_ns']),
                  'last_read_to_close_ns': closed - int(events[-1]['returned_ns']),
                  'first_complete_csi_line_1based': first_csi_line + 1,
                  'invalid_utf8_complete_lines_after_first_csi': invalid_utf8_lines,
                  'non_csi_complete_lines_after_first_csi': [i for i, line in
                      enumerate(after_first, first_csi_line + 1) if not line.startswith(b'CSI_DATA,')],
                  'classification': {
                      'prefix_already_present_in_first_read': rom > 0 and events[0]['offset'] == 0 and events[0]['size'] == rom,
                      'prefix_pending_before_os_open': 'undetermined: no trace before open/configuration',
                      'host_stopped_with_line_pending': bool(tail['bytes']) and int(events[-1]['returned_ns']) >= deadline,
                      'last_read_started_before_deadline': int(events[-1]['started_ns']) < deadline,
                      'remainder_ever_emitted_on_wire': 'undetermined: not observed after host stopped reading',
                      'corruption_of_complete_rows': 'not demonstrated by these records',
                      'origin_of_startup_prefix': 'undetermined; no automatic WiFi/firmware/electrical attribution'}}
        output['receivers'][rx] = report
    if any(sha_bytes((run / name).read_bytes()) != digest for name, digest in pinned.items()):
        raise ValueError('Acquisition changed during diagnosis')
    output['acquisition_unchanged'] = True
    return output
