"""Offline relational import, independent SQL metrics and immutable pilot regressions."""
import contextlib
import copy
import csv
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tools')]
from csi_sqlite import database, import_snapshot, summaries, export_csv, check_metrics, sha256, encoded, TABLES
from csi_sqlite_pilot import pilot_snapshot, source_path, sample_record
import base_datos_csi as cli


def synthetic_snapshot():
    session_id, device = 'SYNTHETIC-ONLY', 'usb:fixture'
    samples = []
    for line, timestamp, local in ((1, 10, 4294967290), (2, 10, 5), (3, 30, 20)):
        samples.append(dict(session_id=session_id, device_key=device, line_1based=line,
            callback_id=line-1, local_timestamp_us=local, returned_ns=timestamp,
            first_read_started_ns=timestamp, rssi_dbm=-50, source_mac='fixture', queue_drops=0,
            byte_offset=line-1, byte_length=1, line_sha256=sha256(b'x'),
            original_fields_json='{}', reference_json='{}', raw_line=b'x'))
    return dict(
        devices=[dict(device_key=device, identity_kind='usb_serial', identity_value='fixture')],
        sessions=[dict(session_id=session_id, protocol='synthetic_only', evidence_type='synthetic_fixture',
            partition_group=session_id, future_partition='test_only', bundle_path='synthetic-fixture',
            input_sha256='0'*64, plan_json='{}', provenance_json='{}')],
        session_devices=[dict(session_id=session_id, device_key=device, role='receiver', label='RX-TEST',
            identity_json='{}', opened_ns=0, closing_ns=90, closed_ns=100)],
        source_files=[], csi_samples=samples,
        validation_results=[dict(session_id=session_id, device_key=device, check_name='strict_quality',
                                 passed=0, details_json=encoded(dict(reasons=['synthetic_rejection'])))],
        expected_metrics=dict(rows=3, duration_ns=100, service_duration_ns=90, sample_span_ns=20,
                              max_host_gap_ns=20, max_local_gap_us=15, capture_frequency_hz=1e8,
                              quality_status='rejected'))


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.path = self.root / 'fixture.sqlite3'
        self.snapshot = synthetic_snapshot()

    def test_two_imports_are_identical_and_quality_rejection_is_preserved(self):
        with database(self.path, writable=True) as conn:
            self.assertEqual(import_snapshot(conn, self.snapshot)['state'], 'imported')
            counts = {t: conn.execute('SELECT COUNT(*) FROM ' + t).fetchone()[0] for t in TABLES}
            changes = conn.total_changes
            self.assertEqual(import_snapshot(conn, self.snapshot)['state'], 'already_imported')
            self.assertEqual(conn.total_changes, changes)
            self.assertEqual(counts, {t: conn.execute('SELECT COUNT(*) FROM ' + t).fetchone()[0] for t in TABLES})
            summary, = summaries(conn)
            self.assertEqual(summary['quality_status'], 'rejected')
            self.assertIsNone(summary['diagnostic_ok'])

    def test_zero_host_gaps_and_local_uint32_wrap_are_preserved(self):
        with database(self.path, writable=True) as conn:
            import_snapshot(conn, self.snapshot)
            summary, = summaries(conn)
            self.assertEqual(summary['rows'], 3)
            self.assertEqual(summary['sample_span_ns'], 20)
            self.assertEqual(summary['capture_frequency_hz'], 2*1e9/20)
            self.assertEqual(summary['max_local_gap_us'], 15)

    def test_empty_singleton_and_equal_timestamps_have_no_invented_frequency(self):
        with database(self.path, writable=True) as conn:
            for size in (0, 1, 2):
                snapshot = copy.deepcopy(self.snapshot)
                new_id = 'SYNTHETIC-' + str(size)
                for table in TABLES:
                    for row in snapshot[table]:
                        if 'session_id' in row: row['session_id'] = new_id
                snapshot['csi_samples'] = snapshot['csi_samples'][:size]
                snapshot['expected_metrics'] = dict(rows=size, capture_frequency_hz=None)
                import_snapshot(conn, snapshot)
                summary, = summaries(conn, new_id)
                self.assertIsNone(summary['capture_frequency_hz'])

    def test_report_mismatch_rolls_back_all_six_tables(self):
        self.snapshot['expected_metrics']['rows'] = 99
        with database(self.path, writable=True) as conn:
            with self.assertRaisesRegex(ValueError, 'Metrics differ'):
                import_snapshot(conn, self.snapshot)
            self.assertTrue(all(conn.execute('SELECT COUNT(*) FROM ' + t).fetchone()[0] == 0 for t in TABLES))

    def test_duplicate_sample_or_unknown_device_rolls_back_without_partial_session(self):
        for mode in ('duplicate', 'missing_device'):
            snapshot = copy.deepcopy(self.snapshot)
            if mode == 'duplicate': snapshot['csi_samples'].append(snapshot['csi_samples'][0])
            else: snapshot['csi_samples'][0]['device_key'] = 'unknown'
            with database(self.path, writable=True) as conn:
                with self.subTest(mode=mode), self.assertRaises(sqlite3.IntegrityError):
                    import_snapshot(conn, snapshot)
                self.assertEqual(conn.execute('SELECT COUNT(*) FROM sessions').fetchone()[0], 0)

    def test_conflicting_source_or_database_tampering_is_rejected_without_replacing_records(self):
        with database(self.path, writable=True) as conn:
            import_snapshot(conn, self.snapshot)
            changed = copy.deepcopy(self.snapshot)
            changed['sessions'][0]['input_sha256'] = '1'*64
            with self.assertRaisesRegex(ValueError, 'conflicts'):
                import_snapshot(conn, changed)
            self.assertEqual(conn.execute('SELECT input_sha256 FROM sessions').fetchone()[0], '0'*64)
            conn.execute('UPDATE csi_samples SET rssi_dbm=-1 WHERE line_1based=1')
            conn.commit()
            with self.assertRaisesRegex(ValueError, 'conflicts'):
                import_snapshot(conn, self.snapshot)

    def test_device_identity_conflict_rolls_back_new_session(self):
        with database(self.path, writable=True) as conn:
            import_snapshot(conn, self.snapshot)
            altered = copy.deepcopy(self.snapshot)
            for table in TABLES:
                for row in altered[table]:
                    if 'session_id' in row: row['session_id'] = 'SYNTHETIC-OTHER'
            altered['devices'][0]['identity_value'] = 'different'
            with self.assertRaisesRegex(ValueError, 'conflicts'):
                import_snapshot(conn, altered)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM sessions').fetchone()[0], 1)

    def test_export_uses_sql_metrics_and_cannot_overwrite_or_traverse(self):
        with database(self.path, writable=True) as conn:
            import_snapshot(conn, self.snapshot)
            export = self.root / 'csv'
            files = export_csv(conn, export)
            self.assertNotIn(b'\r', Path(files[0]['path']).read_bytes())
            with Path(files[0]['path']).open(newline='') as stream:
                row, = list(csv.DictReader(stream))
            self.assertEqual(row['rows'], '3')
            self.assertEqual(row['quality_status'], 'rejected')
            self.assertEqual(float(row['capture_frequency_hz']), 1e8)
            with self.assertRaises(FileExistsError): export_csv(conn, export)
            conn.execute("UPDATE session_devices SET label='../escape'")
            with self.assertRaisesRegex(ValueError, 'Unsafe'):
                export_csv(conn, self.root / 'unsafe')
            self.assertFalse((self.root / 'unsafe').exists())

    def test_read_only_query_rejects_writes_and_attach(self):
        with database(self.path, writable=True) as conn: import_snapshot(conn, self.snapshot)
        before = self.path.read_bytes()
        with patch.object(cli, 'STORAGE', self.root), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(['--database', str(self.path), 'query', '--sql', 'SELECT COUNT(*) AS n FROM csi_samples']), 0)
            for sql in ('DELETE FROM csi_samples', 'PRAGMA query_only=OFF', "ATTACH DATABASE ':memory:' AS other"):
                self.assertEqual(cli.main(['--database', str(self.path), 'query', '--sql', sql]), 1)
        self.assertEqual(before, self.path.read_bytes())

    def test_unknown_database_schema_is_never_modified(self):
        with contextlib.closing(sqlite3.connect(self.path)) as conn:
            conn.execute('CREATE TABLE unrelated(x)')
            conn.commit()
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'Unrecognized'):
            with database(self.path, writable=True): self.fail('Unsupported database accepted')
        self.assertEqual(before, self.path.read_bytes())

    def test_output_and_reserve_boundaries_before_read_or_write(self):
        with self.assertRaises(ValueError): cli.output_path(ROOT / 'results/local/diagnostico-rx02-visor-240s-r1/x.db')
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('No reserved read')):
            with self.assertRaises(PermissionError): source_path('results/local/RX02-C04/manifest.json')


@unittest.skipUnless((ROOT / 'results/local/diagnostico-rx02-visor-240s-r1/manifest.json').is_file(),
                     'Audited historical pilot is local and is not distributed with Git')
class HistoricalPilotTests(unittest.TestCase):
    def test_reaudit_exact_report_metrics_twice_no_UART_or_discovery_and_lossless_row(self):
        with (patch('serial.Serial', side_effect=AssertionError('No physical UART')),
              patch('subprocess.run', side_effect=AssertionError('No USB discovery/audio'))):
            snapshot = pilot_snapshot()
        self.assertEqual(len(snapshot['csi_samples']), 1192)
        self.assertEqual(len(snapshot['devices']), 2)
        self.assertEqual(sum(s['passed'] for s in snapshot['validation_results']), 7)
        first = snapshot['csi_samples'][0]
        fields = json.loads(first['original_fields_json'])
        self.assertEqual(len(json.loads(fields['data'])), int(fields['len']))
        ref = json.loads(first['reference_json'])
        changed = dict(ref, line_sha256='0'*64, byte_offset=0, byte_end=len(first['raw_line']))
        with self.assertRaisesRegex(ValueError, 'hash differs'):
            sample_record('SYNTHETIC-ONLY', first['device_key'], first['raw_line'], changed)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'historical.sqlite3'
            with database(target, writable=True) as conn:
                first_import = import_snapshot(conn, snapshot)
                counts = {t: conn.execute('SELECT COUNT(*) FROM ' + t).fetchone()[0] for t in TABLES}
                second_import = import_snapshot(conn, snapshot)
                self.assertEqual(first_import['state'], 'imported')
                self.assertEqual(second_import['state'], 'already_imported')
                self.assertEqual(counts, {t: conn.execute('SELECT COUNT(*) FROM ' + t).fetchone()[0] for t in TABLES})
                row, = summaries(conn)
                check_metrics(row, snapshot['expected_metrics'])
                self.assertEqual(row['duration_ns'], 240005564743)
                self.assertEqual(row['sample_span_ns'], 239191988869)
                self.assertEqual(row['max_host_gap_ns'], 614782902)
                self.assertEqual(row['quality_status'], 'rejected')
                stored = conn.execute('SELECT raw_line, original_fields_json FROM csi_samples ORDER BY line_1based LIMIT 1').fetchone()
                self.assertEqual(bytes(stored['raw_line']), first['raw_line'])
                self.assertEqual(json.loads(stored['original_fields_json']), fields)
                self.assertIn('preamble_anomaly:RX-02', row['quality_details_json'])


if __name__ == '__main__': unittest.main()
