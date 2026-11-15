"""Transactional SQLite derivative of audited CSI bundles; no acquisition backend."""
from contextlib import contextmanager
import csv
import hashlib
import json
import math
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / 'config/csi_sqlite_v1.sql'
APPLICATION_ID = 0x43534931
VERSION = 1
TABLES = ('devices', 'sessions', 'session_devices', 'source_files', 'csi_samples', 'validation_results')


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


@contextmanager
def database(path, *, writable=False):
    path = Path(path).resolve()
    mode = 'rwc' if writable else 'ro'
    connection = sqlite3.connect(path.as_uri() + '?mode=' + mode, uri=True, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute('PRAGMA foreign_keys=ON')
        app = connection.execute('PRAGMA application_id').fetchone()[0]
        version = connection.execute('PRAGMA user_version').fetchone()[0]
        tables = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        if writable and app == version == 0 and not tables:
            connection.executescript('BEGIN IMMEDIATE;\n' + SCHEMA.read_text() +
                f'\nPRAGMA application_id={APPLICATION_ID}; PRAGMA user_version={VERSION}; COMMIT;')
            app, version = APPLICATION_ID, VERSION
        if app != APPLICATION_ID or version != VERSION:
            raise ValueError('Unrecognized SQLite database or schema version; refusing to modify it')
        if not writable:
            connection.execute('PRAGMA query_only=ON')
        yield connection
    finally:
        connection.close()


def summaries(connection, session_id=None):
    sql = 'SELECT * FROM session_receiver_summary'
    parameters = ()
    if session_id is not None:
        sql += ' WHERE session_id=?'
        parameters = (session_id,)
    return [dict(row) for row in connection.execute(sql + ' ORDER BY session_id, receiver_id', parameters)]


def check_metrics(actual, expected):
    """SQL-derived metrics versus independent, previously published exact values."""
    checks = {}
    for name, value in expected.items():
        measured = actual.get(name)
        same = (math.isclose(measured, value, rel_tol=1e-12, abs_tol=1e-12)
                if isinstance(value, float) and isinstance(measured, (int, float)) else measured == value)
        checks[name] = dict(actual=measured, expected=value, matches=same)
    if not all(item['matches'] for item in checks.values()):
        raise ValueError('Metrics differ from original report: ' + encoded(checks))
    return checks


def _check_stored(connection, snapshot):
    """An existing import is a no-op only if every stored record still matches."""
    session_id = snapshot['sessions'][0]['session_id']
    for table in TABLES:
        rows = snapshot[table]
        if table == 'devices':
            actual = [dict(connection.execute('SELECT * FROM devices WHERE device_key=?',
                                             (row['device_key'],)).fetchone() or {}) for row in rows]
        else:
            actual = [dict(row) for row in connection.execute(
                f'SELECT * FROM {table} WHERE session_id=?', (session_id,))]
        def comparable(row):
            return encoded({k: v.hex() if isinstance(v, bytes) else v for k, v in row.items()})
        if sorted(map(comparable, actual)) != sorted(map(comparable, rows)):
            raise ValueError('Existing import conflicts with source or stored data: ' + table)


def import_snapshot(connection, snapshot):
    """All six related tables and reference checks succeed or roll back together."""
    session_id = snapshot['sessions'][0]['session_id']
    connection.execute('BEGIN IMMEDIATE')
    try:
        existing = connection.execute('SELECT 1 FROM sessions WHERE session_id=?', (session_id,)).fetchone()
        if existing:
            _check_stored(connection, snapshot)
        else:
            for table in TABLES:
                for row in snapshot[table]:
                    columns = ','.join(row)
                    placeholders = ','.join('?' for _ in row)
                    clause = ' ON CONFLICT(device_key) DO NOTHING' if table == 'devices' else ''
                    connection.execute(f'INSERT INTO {table} ({columns}) VALUES ({placeholders}){clause}',
                                       tuple(row.values()))
            _check_stored(connection, snapshot)
        summary, = summaries(connection, session_id)
        checks = check_metrics(summary, snapshot['expected_metrics'])
        if connection.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('SQLite foreign key violation')
        connection.commit()
        return dict(state='already_imported' if existing else 'imported', session_id=session_id,
                    rows=summary['rows'], metrics_verified=checks)
    except BaseException:
        connection.rollback()
        raise


def export_csv(connection, output_new):
    """One one-row CSV per session/receiver. Never replace an earlier export."""
    rows = summaries(connection)
    if not rows:
        raise ValueError('No imported sessions to export')
    output = Path(output_new)
    # IDs are SQL text, so reject filename traversal even in an edited database.
    import re
    for row in rows:
        if any(not re.fullmatch(r'[A-Za-z0-9_-]+', row[key]) for key in ('session_id', 'receiver_id')):
            raise ValueError('Unsafe session/receiver filename')
    output.mkdir(parents=True, exist_ok=False)
    files = []
    for row in rows:
        path = output / (row['session_id'] + '__' + row['receiver_id'] + '.csv')
        with path.open('x', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(row), lineterminator='\n')
            writer.writeheader()
            writer.writerow(row)
        files.append(dict(path=str(path), sha256=sha256(path.read_bytes())))
    return files
