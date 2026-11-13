#!/usr/bin/env python3
"""Offline CSI SQLite pilot: audited import, read-only queries and session CSVs."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tools')]
from csi_live_observer import guard
from csi_sqlite import database, export_csv, import_snapshot, summaries, check_metrics
from csi_sqlite_pilot import pilot_snapshot

STORAGE = ROOT / 'results/local/base-datos-csi'
DEFAULT_DATABASE = STORAGE / 'piloto.sqlite3'


def output_path(path):
    path = Path(path).resolve()
    if not path.is_relative_to(STORAGE) or path == STORAGE:
        raise ValueError('Use only derivative outputs under results/local/base-datos-csi/')
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=DEFAULT_DATABASE)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('import-pilot', help='Reaudit and import the one reviewed historical session; idempotent')
    export = commands.add_parser('export', help='One CSV per imported session/receiver')
    export.add_argument('--output-new', type=Path, required=True)
    commands.add_parser('verify', help='Reaudit originals and compare all stored records and SQL metrics, read-only')
    query = commands.add_parser('query', help='Read-only SQL; database mode=ro and query_only=ON')
    query.add_argument('--sql', default='SELECT * FROM session_receiver_summary')
    args = parser.parse_args(argv)
    try:
        target = output_path(args.database)
        if args.command == 'import-pilot':
            snapshot = pilot_snapshot()  # Audit before creating/opening any derivative database.
            target.parent.mkdir(parents=True, exist_ok=True)
            with database(target, writable=True) as connection:
                result = import_snapshot(connection, snapshot)
        else:
            with database(target) as connection:
                if args.command == 'export':
                    result = dict(files=export_csv(connection, output_path(args.output_new)))
                elif args.command == 'verify':
                    from csi_sqlite import _check_stored
                    snapshot = pilot_snapshot()
                    _check_stored(connection, snapshot)
                    summary, = summaries(connection, snapshot['sessions'][0]['session_id'])
                    result = dict(state='verified', metrics_verified=check_metrics(summary, snapshot['expected_metrics']),
                                  foreign_key_errors=[list(r) for r in connection.execute('PRAGMA foreign_key_check')],
                                  sqlite_integrity=connection.execute('PRAGMA integrity_check').fetchone()[0])
                    if result['foreign_key_errors'] or result['sqlite_integrity'] != 'ok':
                        raise ValueError('SQLite integrity check failed')
                else:
                    allowed = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ,
                               sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE}
                    connection.set_authorizer(lambda action, *unused:
                                              sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY)
                    result = [dict(row) for row in connection.execute(args.sql)]
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, sqlite3.Error) as exc:
        print('OFFLINE_DATABASE_ERROR: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.addaudithook(guard)
    raise SystemExit(main())
