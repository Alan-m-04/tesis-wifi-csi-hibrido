"""Read the explicitly selected historical diagnostic; retain its strict rejection."""
import json
from pathlib import Path
import re

from capture_csi_multi import ANSI, validate_sample
from csi_sqlite import ROOT, encoded, sha256
from rx02_gap_diagnostics import require

PILOT_CONFIG = 'config/csi_sqlite_pilot.review.json'


def source_path(relative):
    path = ROOT / relative
    if re.search(r'C0[456]', str(path), re.I) or re.search(r'C0[456]', str(path.resolve()), re.I):
        raise PermissionError('C04-C06 remain reserved')
    if not path.resolve().is_relative_to(ROOT) or path.is_symlink():
        raise ValueError('Only original local regular sources are supported')
    return path


def sample_record(session_id, device_key, raw, reference):
    from consolidar_rx02_c01 import verify_reference
    line = verify_reference(raw, reference)
    _, fields, metadata = validate_sample(ANSI.sub('', line.decode('utf-8', errors='strict')).strip())
    require(all(metadata[name] == reference[name] for name in ('id', 'local_timestamp', 'queue_drops')),
            'CSI metadata differs from audited raw reference')
    return dict(session_id=session_id, device_key=device_key, line_1based=reference['line_1based'],
        callback_id=metadata['id'], local_timestamp_us=metadata['local_timestamp'],
        returned_ns=int(reference['returned_ns']), first_read_started_ns=int(reference['first_read_started_ns']),
        rssi_dbm=metadata['rssi'], source_mac=fields['mac'], queue_drops=metadata['queue_drops'],
        byte_offset=reference['byte_offset'], byte_length=reference['byte_length'],
        line_sha256=reference['line_sha256'], original_fields_json=encoded(fields),
        reference_json=encoded(reference), raw_line=line)


def pilot_snapshot():
    from diagnostico_checkpoints_rx02 import diagnostic_report
    from rx02_physical_report import summarize

    config = json.loads(source_path(PILOT_CONFIG).read_text())
    bundle = source_path(config['bundle'])
    # Check every candidate before invoking the existing native inventory/replay.
    paths = [p for p in bundle.rglob('*') if p.is_file()]
    paths += [source_path(name) for name in config['references']]
    before = {}
    for path in paths:
        path = source_path(str(path.relative_to(ROOT)))
        before[str(path.relative_to(ROOT))] = dict(bytes=path.stat().st_size, sha256=sha256(path.read_bytes()))
    for name, expected in config['references'].items():
        require(before[name]['sha256'] == expected, 'Original report hash differs: ' + name)
    require(sha256((bundle / 'manifest.json').read_bytes()) == config['manifest_sha256'],
            'Pilot manifest differs from reviewed selection')
    report = json.loads(source_path(config['report_json']).read_text())
    require(report['attempt_id'] == config['session_id'], 'Original report identity differs')
    require({str(p.relative_to(bundle)): before[str(p.relative_to(ROOT))] for p in paths
             if p.is_relative_to(bundle)} == report['inputs']['bundle'], 'Original bundle inventory differs')
    summary, audit = summarize(bundle, diagnostic_report)
    saved_audit = json.loads(source_path(config['audit_json']).read_text())
    require(audit == saved_audit, 'Native replay differs from original saved audit')
    require(summary['cadence_full'] == report['cadence'] and summary['timings'] == report['lifecycle'],
            'Native timing/cadence differs from original report')
    require(summary['connection'] == report['quality']['result'], 'Original strict quality changed')
    require(audit['integrity_ok'] and audit['replay_ok'], 'Audited integrity/replay required for import')
    state = audit['state']
    plan = summary['plan']
    session_id = config['session_id']
    require(state['connection_id'] == session_id and state['windows'] == [] and
            plan['future_partition'] == 'diagnostic_only', 'Only selected diagnostic pilot is supported')
    provenance = json.loads((bundle / 'provenance.json').read_text())
    events = json.loads((bundle / 'events.json').read_text())
    raw = (bundle / 'rx-02.serial.log').read_bytes()
    receiver = 'RX-02'
    serial = plan['receivers'][receiver]
    rx_key = 'usb:' + serial
    tx_mac = plan['transmitter']['source_mac']
    tx_key = 'mac:' + tx_mac
    stamps = summary['timings']['stamps_ns']
    samples = [sample_record(session_id, rx_key, raw, event['evidence']) for event in events
               if event['kind'] == 'line' and event['evidence']['kind'] == 'row']
    require(all(a['returned_ns'] <= b['returned_ns'] and a['line_1based'] < b['line_1based']
                for a, b in zip(samples, samples[1:])), 'Original sample order must be monotonic')
    require(all(s['source_mac'] == tx_mac for s in samples), 'Unexpected transmitter in pilot')
    expected = dict(duration_ns=report['lifecycle']['open_to_close_ns'],
        service_duration_ns=report['lifecycle']['open_to_closing_ns'], rows=report['cadence']['complete_rows'],
        sample_span_ns=report['cadence']['first_to_last_return_ns'],
        capture_frequency_hz=report['cadence']['host_interarrival_hz'],
        max_host_gap_ns=report['cadence']['host_gap_ns']['max'],
        max_local_gap_us=report['cadence']['local_gap_us']['max'],
        strict_quality_ok=int(report['quality']['result']['quality_ok']),
        quality_status='accepted' if report['quality']['result']['quality_ok'] else 'rejected',
        integrity_ok=1, replay_ok=1, close_ok=int(report['diagnostic']['close_ok']),
        diagnostic_ok=int(report['diagnostic']['diagnostic_ok']))
    validations = [dict(session_id=session_id, device_key=rx_key, check_name=name,
        passed=int(passed), details_json=encoded(details)) for name, passed, details in (
            ('integrity', audit['integrity_ok'], dict(manifest_sha256=config['manifest_sha256'])),
            ('replay', audit['replay_ok'], dict(operations=audit['operations'], audit_sha256=config['references'][config['audit_json']])),
            ('strict_quality', state['connection']['quality_ok'], state['connection']),
            ('closure', report['diagnostic']['close_ok'], state['closed'][receiver]),
            ('diagnostic', audit['diagnostic']['diagnostic_ok'], audit['diagnostic']),
            ('identity', audit['diagnostic']['identity_ok'], provenance['transport']['identities']),
            ('storage', audit['diagnostic']['storage_ok'], dict(permitted_uses=plan['permitted_uses'])),
            ('checkpoints', audit['diagnostic']['checkpoint_ok'], audit['persistence_status']),
        )]
    # Bind this derivative to the selected source inventory and its content hashes.
    fingerprint = sha256(encoded(dict(files=before, adapter='csi-sqlite-pilot-1')).encode())
    snapshot = dict(
        devices=[dict(device_key=rx_key, identity_kind='usb_serial', identity_value=serial),
                 dict(device_key=tx_key, identity_kind='source_mac', identity_value=tx_mac)],
        sessions=[dict(session_id=session_id, protocol=plan['protocol'], evidence_type=state['evidence_type'],
            partition_group=plan['partition_group'], future_partition=plan['future_partition'],
            bundle_path=config['bundle'], input_sha256=fingerprint,
            plan_json=encoded(plan), provenance_json=encoded(provenance))],
        session_devices=[dict(session_id=session_id, device_key=rx_key, role='receiver', label=receiver,
            identity_json=encoded(provenance['transport']['identities'][receiver]),
            opened_ns=stamps['opened'], closing_ns=stamps['closing'], closed_ns=stamps['closed']),
            dict(session_id=session_id, device_key=tx_key, role='transmitter', label='TX-01',
                 identity_json=encoded(plan['transmitter']), opened_ns=None, closing_ns=None, closed_ns=None)],
        source_files=[dict(session_id=session_id, path=name, **info) for name, info in sorted(before.items())],
        csi_samples=samples, validation_results=validations, expected_metrics=expected)
    require(all(path.is_file() and path.stat().st_size == before[str(path.relative_to(ROOT))]['bytes'] and
                sha256(path.read_bytes()) == before[str(path.relative_to(ROOT))]['sha256'] for path in paths),
            'Original sources changed during import preparation')
    return snapshot
