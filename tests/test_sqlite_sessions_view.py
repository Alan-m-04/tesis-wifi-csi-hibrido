"""Dashboard HTTP/SQLite checks; no device discovery, UART or acquisition."""
import contextlib
import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tools')]
import csi_sqlite_view as view
from csi_sqlite import database, summaries
import panel_dispositivos as cli
from test_device_panel import FakeSocket


class ViewTests(unittest.TestCase):
    def request(self, path='/sessions', *, collector=None, method='GET', host='127.0.0.1:8766'):
        sock = FakeSocket(f'{method} {path} HTTP/1.0\r\nHost: {host}\r\n\r\n'.encode())
        handler = cli.handler(lambda: self.fail('SQLite view must not query USB'), b'historical fixture',
                              collector or (lambda: dict(schema='synthetic_http_fixture')))
        with patch.object(handler, 'log_message'):
            handler(sock, ('127.0.0.1', 1234), SimpleNamespace(server_port=8766))
        return bytes(sock.output)

    def test_navigation_and_stylesheet_are_shared_with_existing_panel(self):
        for route, content_type in (('/sessions', b'text/html'), ('/sessions.mjs', b'text/javascript'), ('/panel.css', b'text/css')):
            response = self.request(route)
            self.assertIn(b'200 OK', response.split(b'\r\n')[0])
            self.assertIn(content_type, response)
            self.assertIn(b"connect-src 'self'", response)
        page = self.request().decode()
        self.assertIn('Datos guardados por sesión y receptor', page)
        self.assertIn('R5-N01 sigue pendiente', page)
        self.assertIn('preámbulo', page)
        for path in ('/', '/replay'):
            self.assertIn(f'href="{path}"', page)
        device_page = self.request('/').decode()
        for page_text in (device_page, page):
            self.assertIn('href="/panel.css"', page_text)
        self.assertIn('href="/sessions"', device_page)

    def test_session_API_never_queries_devices_and_is_not_cacheable(self):
        payload = dict(schema='synthetic_http_fixture', read_only=True)
        with patch('serial.Serial', side_effect=AssertionError('No UART')):
            response = self.request('/api/sessions', collector=lambda: payload)
        headers, body = response.split(b'\r\n\r\n', 1)
        self.assertIn(b'200 OK', headers)
        self.assertIn(b'Cache-Control: no-store', headers)
        self.assertNotIn(b'Access-Control-Allow-Origin', headers)
        self.assertEqual(json.loads(body), payload)

    def test_unavailable_database_or_mismatched_report_returns_503(self):
        for error in (sqlite3.OperationalError('missing DB'), ValueError('CSV differs'), FileNotFoundError('missing CSV')):
            def fail(): raise error
            with self.subTest(error=str(error)):
                self.assertIn(b'503', self.request('/api/sessions', collector=fail).split(b'\r\n')[0])

    def test_mutations_paths_and_external_hosts_are_not_available(self):
        for route in ('/api/sessions?sql=DELETE', '/piloto.sqlite3', '/api/import', '/sessions/../README.md'):
            self.assertIn(b'404', self.request(route).split(b'\r\n')[0])
        self.assertIn(b'405', self.request('/api/sessions', method='POST').split(b'\r\n')[0])
        self.assertIn(b'403', self.request('/api/sessions', host='other.example:8766').split(b'\r\n')[0])

    def test_sin_replay_startup_never_builds_or_consults_data(self):
        server = SimpleNamespace(server_port=8766, serve_forever=lambda: (_ for _ in ()).throw(KeyboardInterrupt()),
                                 server_close=lambda: None)
        with (patch.object(cli, 'build', side_effect=AssertionError('No C01/C03')),
              patch.object(cli, 'snapshot', side_effect=AssertionError('No USB')),
              patch.object(cli, 'read_sessions', side_effect=AssertionError('Not before GET')),
              patch.object(cli, 'make_server', return_value=server) as make,
              patch.object(cli.sys, 'addaudithook'), contextlib.redirect_stdout(io.StringIO()) as out):
            self.assertEqual(cli.main(['--sin-replay']), 0)
        make.assert_called_once_with(8766, replay_html=None, database_path=cli.DEFAULT_DATABASE)
        self.assertIn('/sessions', out.getvalue())

    def test_missing_database_never_creates_a_file_or_imports(self):
        with tempfile.TemporaryDirectory() as temporary:
            missing = Path(temporary) / 'missing.sqlite3'
            with patch.object(view, 'STORAGE', Path(temporary)), self.assertRaises(sqlite3.Error):
                view.read_sessions(missing)
            self.assertFalse(missing.exists())

    def test_empty_database_and_reserved_paths_remain_explicit(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'empty.sqlite3'
            with database(target, writable=True): pass
            before = target.read_bytes()
            with patch.object(view, 'STORAGE', Path(temporary)):
                result = view.read_sessions(target)
            self.assertEqual(result['sessions'], [])
            self.assertEqual(result['pilot_csv_comparison']['state'], 'not_present')
            self.assertEqual(before, target.read_bytes())
        with patch.object(view, 'database', side_effect=AssertionError('No reserved read')):
            with self.assertRaises(PermissionError): view.read_sessions(ROOT / 'results/local/RX02-C04/unknown.sqlite3')
            with self.assertRaises(ValueError): view.read_sessions(ROOT / 'results/local/piloto-rx02-r1-C01/x.sqlite3')


@unittest.skipUnless(view.DEFAULT_DATABASE.is_file(), 'The SQLite pilot is local and is not distributed with Git')
class PilotTests(unittest.TestCase):
    def test_readonly_snapshot_matches_CSV_and_keeps_full_rejection_reasons(self):
        before = hashlib.sha256(view.DEFAULT_DATABASE.read_bytes()).hexdigest()
        with (patch('serial.Serial', side_effect=AssertionError('No UART')),
              patch('subprocess.run', side_effect=AssertionError('No USB, replay or audio')),
              patch.object(view, 'database', wraps=database) as opened):
            result = view.read_sessions()
        opened.assert_called_once_with(view.DEFAULT_DATABASE)
        self.assertEqual(before, hashlib.sha256(view.DEFAULT_DATABASE.read_bytes()).hexdigest())
        row, = result['sessions']
        self.assertTrue(result['read_only'] and result['historical'])
        self.assertFalse(result['live_capture'])
        self.assertEqual(result['pilot_csv_comparison']['state'], 'matched')
        self.assertEqual((row['rows'], row['duration_ns'], row['max_host_gap_ns']), (1192, 240005564743, 614782902))
        self.assertEqual(row['quality_status'], 'rejected')
        self.assertTrue(row['preamble_rejected'])
        self.assertEqual({r['reason']: r['count'] for r in row['quality_reasons']},
                         {'format:RX-02': 20, 'preamble_anomaly:RX-02': 1})
        self.assertEqual([row[k] for k in ('integrity_ok', 'replay_ok', 'close_ok', 'diagnostic_ok')], [1, 1, 1, 1])

    def test_CSV_comparison_rejects_changed_metrics_and_quality(self):
        with database(view.DEFAULT_DATABASE) as conn: rows = summaries(conn)
        for key, value in (('rows', 1193), ('duration_ns', 240005564744),
                           ('capture_frequency_hz', 5.0), ('max_host_gap_ns', 1),
                           ('quality_status', 'accepted'), ('quality_details_json', '{}')):
            altered = copy.deepcopy(rows)
            altered[0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): view.compare_pilot_csv(altered)

    def test_CSV_duplicate_pilot_rows_cannot_be_reported_as_matched(self):
        with database(view.DEFAULT_DATABASE) as conn: rows = summaries(conn)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'duplicate.csv'
            with view.PILOT_CSV.open(newline='') as stream: expected = list(csv.DictReader(stream))
            with path.open('w', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=list(expected[0]))
                writer.writeheader(); writer.writerow(expected[0]); writer.writerow(expected[0])
            with self.assertRaises(ValueError): view.compare_pilot_csv(rows, path)

    def test_incomplete_or_non_numeric_CSV_is_not_reported_as_verified(self):
        with database(view.DEFAULT_DATABASE) as conn: rows = summaries(conn)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'invalid.csv'
            path.write_text('session_id,receiver_id\nRX02-DIAG-VISOR-240S-R1,RX-02\n')
            with self.assertRaises(ValueError): view.compare_pilot_csv(rows, path)
            with view.PILOT_CSV.open(newline='') as stream: expected = list(csv.DictReader(stream))
            expected[0]['rows'] = 'no verificable'
            with path.open('w', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=list(expected[0]))
                writer.writeheader(); writer.writerow(expected[0])
            with self.assertRaises(ValueError): view.compare_pilot_csv(rows, path)


if __name__ == '__main__': unittest.main()
