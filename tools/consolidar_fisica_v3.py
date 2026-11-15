#!/usr/bin/env python3
"""Reproduce one existing physical v3 report from regular local files only.

Never discovers devices, constructs serial ports, acquires data or selects a
window. Run via tools/offline_sandbox.sh for a private /dev and isolated network.
Exit 0 verifies the consolidation, NOT acceptance of the rejected acquisition.
"""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'results/local/preparacion-dual-v3-20261026T000758Z'
RUN = BASE / 'captura-dual-v3-20261026T000758Z-intento-unico'
CONTROL = BASE / 'control/ejecucion-autorizada-v3-intento01'
ANALYSIS = BASE / 'analisis-v3-intento-unico'
VIEW = ANALYSIS / 'visualization'
sys.path.insert(0, str(ROOT / 'src'))
from validate_capture import audit_capture


def require(condition, message):
    if not condition:
        raise ValueError(message)


def regular(path):
    require(path.is_file() and not path.is_symlink(), 'Regular file required: ' + str(path))
    require(path.resolve().is_relative_to(ROOT), 'Input outside the repository')
    return path


def digest(data):
    return hashlib.sha256(data).hexdigest()


def ref(path):
    regular(path)
    return {'path': str(path.relative_to(ROOT)), 'bytes': path.stat().st_size,
            'sha256': digest(path.read_bytes())}


def load(path):
    return json.loads(regular(path).read_text())


def verify_entries(directory, entries, key):
    for entry in entries:
        relative = Path(entry[key])
        require(not relative.is_absolute() and '..' not in relative.parts, 'Unsafe manifest entry')
        actual = ref(directory / relative)
        require(actual['bytes'] == entry['bytes'] and actual['sha256'] == entry['sha256'],
                'Hash/size mismatch: ' + actual['path'])
    return len(entries)


def consolidate():
    manifest = load(RUN / 'capture-manifest.json')
    bundle = load(RUN / 'bundle-manifest.json')
    capture_entries = manifest['files'] + manifest['read_ledgers'] + [manifest['coordination_trace']]
    capture_verified = verify_entries(RUN / 'capture', capture_entries, 'name')
    bundle_verified = verify_entries(RUN, bundle['files'], 'path')
    control_manifest = load(CONTROL / 'control-manifest.json')
    self_entries = [x for x in control_manifest['files'] if x['path'] == 'control-manifest.json']
    other_entries = [x for x in control_manifest['files'] if x['path'] != 'control-manifest.json']
    control_verified = verify_entries(CONTROL, other_entries, 'path')
    # Preserve and disclose the existing manifest construction defect. Never
    # silently waive other mismatches or rewrite a historical manifest.
    require(len(self_entries) == 1 and self_entries[0]['bytes'] == 0 and
            self_entries[0]['sha256'] == digest(b''), 'Unexpected auxiliary self-entry')
    actual_control = ref(CONTROL / 'control-manifest.json')
    require(actual_control['bytes'] != 0, 'Expected nonempty auxiliary manifest')

    provenance = load(RUN / 'provenance.json')
    require(provenance == manifest['source_provenance'], 'Provenance copies differ')
    commit = provenance['git_commit']
    source_checks = {}
    for name, expected in provenance['files'].items():
        blob = subprocess.check_output(['git', 'show', commit + ':' + name], cwd=ROOT)
        require(digest(blob) == expected == ref(ROOT / name)['sha256'], 'Source differs: ' + name)
        source_checks[name] = expected
    import serial
    import serial.serialposix
    require(serial.__version__ == provenance['pyserial_version'] == '3.5', 'pySerial version mismatch')
    require(digest(Path(serial.serialposix.__file__).read_bytes()) == provenance['serialposix_sha256'],
            'pySerial POSIX source mismatch')

    session = load(RUN / 'capture/session.json')
    plan = load(RUN / 'plan.json')
    authorization = load(CONTROL / 'autorizacion-nueva.json')
    consumed = load(CONTROL / 'estado-final-autorizacion.json')
    execution = load(CONTROL / 'resultado-ejecucion.json')
    require(ref(RUN / 'plan.json')['sha256'] == ref(CONTROL / 'plan-confirmado.json')['sha256'] ==
            authorization['plan_sha256'] == manifest['plan_sha256'], 'Authorized plan differs')
    require(authorization['authorized'] is True and consumed['state'] == 'CONSUMED' and
            consumed['capture_child_invocations'] == execution['capture_child_invocations'] == 1 and
            not execution['retry_performed'] and not execution['errors'], 'Single invocation not demonstrated')
    require(session['protocol'] == manifest['source_run_kind'] == 'controlled_dual_v3' and
            manifest['evidence_type'] == session['evidence_type'] == 'physical_capture', 'Wrong session kind')

    audit = audit_capture(RUN / 'capture', manifest)
    stored = load(RUN / 'quality.json')
    canonical = load(VIEW / 'canonical.json')
    audits = {'acquisition': stored['full_session'], 'independent_original': load(CONTROL / 'auditoria-independiente.json'),
              'analysis': load(ANALYSIS / 'quality.json'), 'canonical': canonical['strict_audit']}
    require(all(x == audit for x in audits.values()), 'Audits disagree')
    require(not audit['quality_ok'] and not audit['connection_full']['quality_ok'] and
            audit['experimental_window']['quality_ok'], 'Historical scope result changed')
    old_summary = load(CONTROL / 'VALIDACION_FISICA_V3.json')
    require(old_summary['connection_full'] == audit['connection_full'] and
            old_summary['global_quality_ok'] == audit['quality_ok'], 'Original local summary differs')
    archived_references = [old_summary[k] for k in
        ('acquisition_bundle', 'independent_audit', 'authorization_record', 'plan_record')]
    archived_references += list(old_summary['visualization']['artifacts'].values())
    archived_references += list(old_summary['visualization']['screenshots'].values())
    archived_links_verified = verify_entries(ROOT, archived_references, 'path')

    common = session['controlled']
    a, d, t0, t1 = (int(common[k]) for k in ('A_ns', 'D_ns', 'T0_ns', 'T1_ns'))
    require(t1 - t0 == common['availability_policy']['window_ns'] and d - a == common['availability_policy']['max_wait_ns'],
            'Nominal deadlines differ from policy')
    trace = [json.loads(line) for line in regular(RUN / 'capture/availability.events.jsonl').read_text().splitlines()]
    armed = [x for x in trace if x['kind'] == 'armed']
    require(len(armed) == 1 and int(armed[0]['T0_ns']) == t0 and int(armed[0]['T1_ns']) == t1,
            'Prospective decision not unique')
    receivers = {}
    for rx, item in audit['receivers'].items():
        stem = rx.lower()
        with regular(RUN / 'capture' / (stem + '.csv')).open(newline='') as stream:
            csv_rows = list(csv.DictReader(stream))
        raw = regular(RUN / 'capture' / (stem + '.serial.log')).read_bytes()
        ledger = [json.loads(line) for line in regular(RUN / 'capture' / (stem + '.reads.jsonl')).read_text().splitlines()]
        scope = audit['experimental_window']['receivers'][rx]
        index = scope['index']
        rows = [x for x in index if x.get('csv_record_index_0based') is not None]
        included, excluded = [], []
        for line in rows:
            i = line['csv_record_index_0based']; csv_row = csv_rows[i]
            first, last = ledger[line['first_read_index']], ledger[line['last_read_index']]
            require(first['offset'] <= line['byte_offset'] < first['offset'] + first['size'] and
                    last['offset'] < line['byte_end'] <= last['offset'] + last['size'], 'Read/line offsets disagree')
            require(digest(raw[line['byte_offset']:line['byte_end']]) == line['line_sha256'], 'Row byte hash differs')
            s, e = int(first['started_ns']), int(last['returned_ns'])
            require(str(s) == line['first_read_started_ns'] and str(e) == line['returned_ns'] == csv_row['host_monotonic_ns'],
                    'Host row timestamp differs from ledger')
            selected = line['kind'] == 'row' and not line.get('continuity_error') and s >= t0 and e < t1
            require(selected == (line['inclusion'] == 'included'), 'Inclusion rule differs')
            reference = {k: line[k] for k in ('line_1based', 'byte_offset', 'byte_end', 'line_sha256',
                'first_read_index', 'last_read_index', 'first_read_started_ns', 'returned_ns', 'inclusion')}
            reference.update(csv_record_index_0based=i, csv_line_1based=i + 2, callback_id=int(csv_row['id']),
                local_timestamp_us_uint32=int(csv_row['local_timestamp']), host_timestamp_utc=csv_row['host_timestamp_utc'])
            (included if selected else excluded).append(reference)
        require(len(rows) == len(csv_rows) == item['valid_rows'], 'Complete row count differs')
        times = [int(x['returned_ns']) for x in included]
        gaps = [b - a for a, b in zip(times, times[1:])]
        start_gap, end_gap = times[0] - t0, t1 - times[-1]
        coverage = {'minimum_rows_ok': bool(times), 'included_rows': len(times), 'first_ns': str(times[0]),
            'last_ns': str(times[-1]), 'start_gap_ns': str(start_gap), 'end_gap_ns': str(end_gap),
            'interior_gaps_ns': [str(x) for x in gaps], 'max_observed_gap_ns': str(max([start_gap, end_gap] + gaps)),
            'max_gap_limit_ns': None, 'continuous_observation_claimed': False}
        require(coverage == scope['coverage'] == old_summary['receivers'][rx]['coverage'], 'Recomputed coverage differs')
        ready = next(x for x in index if x['kind'] == 'ready')
        problem_lines = [x for x in index if x['problem']]
        require(all(int(x['returned_ns']) < t0 for x in problem_lines), 'Problem does not precede window')
        first_line = raw[:raw.index(b'\n') + 1]
        prefix_size = first_line.index(b'ESP-ROM:')
        summary = session['results'][rx]
        refs = armed[0]['evidence'][rx]
        gate_rows = [trace[n]['evidence'] for n in refs['row_seqs']]
        lifecycle = [x for x in session['lifecycle'] if x.get('receiver') == rx]
        receivers[rx] = {'usb_serial': plan['ports'][rx].split('Serial_')[1].split('-if')[0],
            'complete_rows': len(rows), 'included_rows': len(included), 'excluded_rows': len(excluded),
            'row_classification_counts': dict(sorted(Counter(x['inclusion'] for x in rows).items())),
            'excluded_rows_with_reasons_and_references': excluded, 'first_included_row': included[0], 'last_included_row': included[-1],
            'T0_ns': str(t0), 'T1_ns': str(t1), 'decision_delay_after_A_ns': str(t0 - a),
            'ready_after_A_ns': str(int(ready['returned_ns']) - a), 'ready_reference': ready,
            'availability_row_ids': [x['id'] for x in gate_rows],
            'last_availability_row_age_ns': str(t0 - int(gate_rows[-1]['returned_ns'])),
            'coverage': coverage, 'interior_gap_count': len(gaps), 'max_interior_gap_ns': str(max(gaps)),
            'first_callback_id': int(csv_rows[0]['id']), 'last_callback_id': int(csv_rows[-1]['id']),
            'raw_bytes': len(raw), 'nonempty_reads': len(ledger), 'counts': item['counts'],
            'first_queue_drops': summary['first_queue_drops'], 'last_queue_drops': summary['last_queue_drops'],
            'capture_error': summary['error'], 'integrity_ok': item['integrity_ok'],
            'complete_rows_quality_ok': item['complete_rows_quality_ok'], 'connection_quality_ok': item['quality_ok'],
            'experimental_window_quality_ok': scope['quality_ok'], 'trailing_bytes': item['trailing_bytes'],
            'stop_quality_ok': item['stop_quality_ok'], 'stop': item['stop'],
            'stop_after_T1_ns': str(int(item['stop']['stopped_ns']) - t1), 'lifecycle': lifecycle,
            'startup': {'prefix_before_ROM_bytes': prefix_size, 'prefix_sha256': digest(first_line[:prefix_size]),
                'first_line_bytes': len(first_line), 'first_line_sha256': digest(first_line),
                'problem_reason_counts': dict(sorted(Counter(x['reason'] for x in problem_lines).items())),
                'all_problem_evidence_before_T0': True, 'problem_references': problem_lines}}

    view_count = verify_entries(VIEW / 'originals', capture_entries, 'name')
    visual_validation = load(VIEW / 'validation.json')
    for name, entry in visual_validation['files'].items():
        actual = ref(VIEW / name)
        require(actual['bytes'] == entry['bytes'] and actual['sha256'] == entry['sha256'], 'Visualization changed')
    browser = load(VIEW / 'browser-qa/validation.json')
    require(len(browser['views']) == 4 and all(x['connection'] == 'Conexión completa: rechazada' and
            x['window'] == 'Ventana experimental: conforme' for x in browser['views'].values()), 'UI states differ')
    ruview = load(ROOT / 'vendor/ruview/PROVENANCE.json')
    require(ref(ROOT / 'vendor/ruview/esp32.js')['sha256'] == ruview['sha256'], 'Official module changed')
    require(ref(ROOT / '.tools/node-v22.20.0/bin/node')['sha256'] == ruview['node_binary_sha256'], 'Pinned Node changed')
    for name in ('vendor/ruview/PROVENANCE.json', 'vendor/ruview/LICENSE', 'vendor/ruview/esp32.js'):
        require(digest(subprocess.check_output(['git', 'show', commit + ':' + name], cwd=ROOT)) == ref(ROOT / name)['sha256'],
                'Vendor source/license differs from acquisition commit')
    source_paths = [RUN / 'bundle-manifest.json', RUN / 'capture-manifest.json', RUN / 'plan.json', RUN / 'provenance.json',
        RUN / 'preflight.json', RUN / 'postflight.json', RUN / 'quality.json', RUN / 'window-index.json',
        CONTROL / 'control-manifest.json', CONTROL / 'autorizacion-nueva.json', CONTROL / 'estado-final-autorizacion.json',
        CONTROL / 'resultado-ejecucion.json', CONTROL / 'preflight-inmediato.json', CONTROL / 'comprobacion-posterior.json',
        CONTROL / 'auditoria-independiente.json', CONTROL / 'VALIDACION_FISICA_V3.json', ANALYSIS / 'quality.json',
        VIEW / 'canonical.json', VIEW / 'ruview-consumer.json', VIEW / 'index.html', VIEW / 'validation.json',
        VIEW / 'browser-qa/validation.json', ROOT / 'vendor/ruview/PROVENANCE.json', ROOT / 'vendor/ruview/LICENSE']
    source_paths += [RUN / 'capture' / x['name'] for x in capture_entries]
    return {'schema': 'tesis-physical-v3-consolidated-v1', 'operation': 'offline_consolidation_only',
        'new_physical_capture': False, 'new_UART_opened': False, 'source_run_id': session['session_id'],
        'source_evidence_type': session['evidence_type'], 'acquisition_git_commit': commit,
        'reproducer': ref(Path(__file__).resolve()), 'provenance': {'files_match_acquisition_commit_and_current_tree': source_checks,
            'pyserial_version': provenance['pyserial_version'], 'serialposix_sha256': provenance['serialposix_sha256'],
            'installed_firmware_sha256': provenance['installed_firmware_sha256'],
            'environment_evidence': provenance['environment_evidence'], 'ruview': ruview},
        'hash_verification': {'acquisition_files_and_ledgers_verified': capture_verified, 'acquisition_bundle_files_verified': bundle_verified,
            'auxiliary_control_entries_verified': control_verified, 'auxiliary_control_manifest_literal_valid': False,
            'archived_bundle_audit_authorization_plan_visual_and_screenshot_links_verified': archived_links_verified,
            'auxiliary_control_self_entry_anomaly': {'stored': self_entries[0], 'actual': actual_control,
                'interpretation': 'Manifest says no self hash, yet pins its still-empty self. Original preserved; only this declared self-entry fails. Not a raw/CSV/ledger mismatch.'},
            'visual_original_copies_verified': view_count, 'all_four_stored_audits_equal_fresh_reaudit': True},
        'started_utc': session['started_utc'], 'finished_utc': session['finished_utc'],
        'connection_envelope_ns': str(session['capture_deadline_monotonic_ns'] - session['capture_start_monotonic_ns']),
        'A_ns': str(a), 'D_ns': str(d), 'T0_ns': str(t0), 'T1_ns': str(t1), 'availability_delay_ns': str(t0 - a),
        'nominal_window_ns': str(t1 - t0), 'armed_events': len(armed), 'availability_policy': common['availability_policy'],
        'stop_policy': common['stop_policy'], 'environment_declared': plan['environment'],
        'reconnection_history_declared': {k: plan['reconnection_history'][k] for k in
            ('boards_disconnected', 'exact_time_utc', 'boot_or_ready_epoch_attested')}, 'session_status': session['status'],
        'capture_returncode': execution['returncode'], 'physical_capture_child_invocations': execution['capture_child_invocations'],
        'authorization_state': consumed['state'], 'capture_authorization_currently_valid': False,
        'connection_full': audit['connection_full'], 'experimental_window': {k: v for k, v in audit['experimental_window'].items() if k != 'receivers'},
        'global_quality_ok': audit['quality_ok'], 'receivers': receivers,
        'all_lifecycle_events': session['lifecycle'], 'postflight': load(RUN / 'postflight.json'),
        'fuser_after_recorded': load(CONTROL / 'comprobacion-posterior.json')['fuser'],
        'stored_browser_verification': {'views': 4, 'reexecuted_for_this_documentation_change': False,
            'connection_rejection_and_window_conformity_both_visible': True},
        'sources': [ref(p) for p in source_paths],
        'limits': ['No RF synchronization, presence detection, continuous RF coverage or training approval demonstrated.',
            'Startup prefix origin undetermined; readable unrecognized boot logs are a grammar limitation, not proof of RF/firmware corruption.',
            'Auxiliary self-entry mismatch is disclosed; acquisition transport integrity and historical scope results are unchanged.',
            'Future pilot coverage proposals are not applied to this session or v1/v2.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--output-new', type=Path)
    mode.add_argument('--check', type=Path)
    args = parser.parse_args()
    try:
        report = consolidate()
        if args.check:
            require(load(args.check.resolve()) == report, 'Versioned summary differs from reconstructed evidence')
            print('CONSOLIDATION_VERIFIED; connection_full=rejected; experimental_window=conforming; global=rejected; auxiliary_self_entry_mismatch=disclosed')
        else:
            with args.output_new.open('x') as stream:
                json.dump(report, stream, ensure_ascii=False, indent=2); stream.write('\n')
            print(args.output_new)
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as exc:
        parser.exit(2, 'Offline consolidation failed: ' + str(exc) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
