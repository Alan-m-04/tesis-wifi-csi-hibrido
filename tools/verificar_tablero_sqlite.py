#!/usr/bin/env python3
"""Verify the real SQLite pilot via in-memory HTTP, explicitly without browser/socket."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tools')]
from csi_sqlite import database, summaries
from csi_sqlite_view import DEFAULT_DATABASE, PILOT_CSV, compare_pilot_csv, read_sessions
from demo_offline import guard
from panel_dispositivos import handler, no_serial_open


def fingerprint(path):
    stat = path.stat()
    return dict(bytes=stat.st_size, mtime_ns=stat.st_mtime_ns,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())


class MemorySocket:
    def __init__(self, request):
        self.input = io.BytesIO(request)
        self.output = bytearray()

    def makefile(self, *args, **kwargs):
        return self.input

    def sendall(self, data):
        self.output.extend(data)


def verify():
    paths = (DEFAULT_DATABASE, PILOT_CSV)
    before = {str(p.relative_to(ROOT)): fingerprint(p) for p in paths}
    sidecars_before = sorted(p.name for p in DEFAULT_DATABASE.parent.iterdir() if p.is_file())
    def forbidden():
        raise AssertionError('No se permiten consultas de dispositivos')
    routes = {}
    api = None
    http = handler(forbidden, None, read_sessions)
    class QuietHandler(http):
        def log_message(self, *args):
            pass
    for route in ('/sessions', '/sessions.mjs', '/panel.css', '/api/sessions', '/api/sessions', '/api/sessions'):
        sock = MemorySocket(f'GET {route} HTTP/1.0\r\nHost: 127.0.0.1:8766\r\n\r\n'.encode())
        QuietHandler(sock, ('127.0.0.1', 12345), SimpleNamespace(server_port=8766))
        headers, body = bytes(sock.output).split(b'\r\n\r\n', 1)
        assert headers.startswith(b'HTTP/1.0 200 OK'), headers
        assert b'Cache-Control: no-store' in headers
        routes[route] = dict(status=200, bytes=len(body))
        if route == '/api/sessions':
            api = json.loads(body)
    with database(DEFAULT_DATABASE) as connection:
        sql = summaries(connection)
        count = connection.execute('SELECT count(*) FROM csi_samples').fetchone()[0]
        assert connection.execute('PRAGMA query_only').fetchone()[0] == 1
        assert connection.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert not connection.execute('PRAGMA foreign_key_check').fetchall()
    assert compare_pilot_csv(sql)['state'] == 'matched'
    row, = api['sessions']
    assert count == row['rows'] == 1192
    assert row['duration_ns'] == 240005564743
    assert row['max_host_gap_ns'] == 614782902
    assert row['capture_frequency_hz'] == 1191 / 239.191988869
    assert row['quality_status'] == 'rejected' and row['preamble_rejected']
    assert {r['reason']: r['count'] for r in row['quality_reasons']} == {
        'format:RX-02': 20, 'preamble_anomaly:RX-02': 1}
    after = {str(p.relative_to(ROOT)): fingerprint(p) for p in paths}
    sidecars_after = sorted(p.name for p in DEFAULT_DATABASE.parent.iterdir() if p.is_file())
    assert before == after and sidecars_before == sidecars_after
    return dict(schema='tesis-dashboard-offline-verification-1',
        transport='HTTP handler over memory streams; no listening socket',
        browser_verified=False, api_queries=3, routes=routes, pilot=row,
        pilot_csv_comparison=api['pilot_csv_comparison'], before=before, after=after,
        sqlite_unchanged=True, csv_unchanged=True, sidecar_set_unchanged=True,
        physical_UART_opened=False, reserve_opened=False), api


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-new', type=Path, required=True)
    args = parser.parse_args(argv)
    from edge_presence_evaluation import safe_path
    output = safe_path(args.output_new)
    if output.exists() or not output.is_relative_to(ROOT / 'results/local'):
        parser.error('Elija una carpeta nueva dentro de results/local/')
    sys.addaudithook(guard)
    sys.addaudithook(no_serial_open)
    report, api = verify()
    output.mkdir(parents=True)
    for name, value in (('verification.json', report), ('sessions-api.json', api)):
        with (output / name).open('x', encoding='utf-8') as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write('\n')
    print(json.dumps(report, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
