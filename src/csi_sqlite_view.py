"""Read-only dashboard snapshot of the existing SQLite summary view."""
from collections import Counter
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re

from csi_sqlite import ROOT, database, summaries

STORAGE = ROOT / 'results/local/base-datos-csi'
DEFAULT_DATABASE = STORAGE / 'piloto.sqlite3'
PILOT_CSV = ROOT / 'results/BASE_DATOS_CSI_PILOTO/RX02-DIAG-VISOR-240S-R1__RX-02.csv'
PILOT = ('RX02-DIAG-VISOR-240S-R1', 'RX-02')
METRICS = ('duration_ns', 'duration_s', 'rows', 'capture_frequency_hz', 'max_host_gap_ns',
           'max_host_gap_ms', 'strict_quality_ok', 'integrity_ok', 'replay_ok', 'close_ok', 'diagnostic_ok')


def compare_pilot_csv(rows, path=PILOT_CSV):
    """Compare exact serialized numeric values, not rounded presentation strings."""
    pilot = [row for row in rows if (row['session_id'], row['receiver_id']) == PILOT]
    if not pilot:
        return dict(state='not_present', checked_fields=[])
    with Path(path).open(newline='', encoding='utf-8') as stream:
        reader = csv.DictReader(stream)
        required = {*METRICS, 'session_id', 'receiver_id', 'quality_status', 'quality_details_json'}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError('El CSV del piloto tiene columnas incompletas')
        references = list(reader)
    references = [row for row in references if (row['session_id'], row['receiver_id']) == PILOT]
    if len(pilot) != 1 or len(references) != 1:
        raise ValueError('El piloto SQLite/CSV no tiene una identidad única')
    actual, expected = pilot[0], references[0]
    for name in METRICS:
        value = actual[name]
        try:
            matches = expected[name] == '' if value is None else Decimal(str(value)) == Decimal(expected[name])
        except (InvalidOperation, TypeError) as exc:
            raise ValueError('El CSV del piloto tiene un indicador no numérico: ' + name) from exc
        if not matches:
            raise ValueError('El piloto SQLite no coincide con el CSV: ' + name)
    if (actual['quality_status'] != expected['quality_status'] or
            json.loads(actual['quality_details_json']) != json.loads(expected['quality_details_json'])):
        raise ValueError('La calidad original del piloto SQLite/CSV no coincide')
    return dict(state='matched', checked_fields=[*METRICS, 'quality_status', 'quality_details_json'])


def read_sessions(path=DEFAULT_DATABASE):
    path = Path(path).resolve()
    if re.search(r'C0[456]', str(path), re.I):
        raise PermissionError('C04-C06 permanecen reservadas')
    if not path.is_relative_to(STORAGE) or path == STORAGE:
        raise ValueError('Use una base derivada dentro de results/local/base-datos-csi/')
    with database(path) as connection:  # Existing mode=ro + query_only=ON, never writable=True.
        connection.execute('BEGIN')
        rows = summaries(connection)
    comparison = compare_pilot_csv(rows)
    for row in rows:
        details = json.loads(row.pop('quality_details_json') or '{}')
        if not isinstance(details, dict):
            raise ValueError('Detalle de calidad no verificable')
        reasons = details.get('reasons', [])
        if not isinstance(reasons, list) or any(not isinstance(reason, str) for reason in reasons):
            raise ValueError('Motivos de validación no verificables')
        row['quality_reasons'] = [dict(reason=reason, count=count) for reason, count in Counter(reasons).items()]
        row['preamble_rejected'] = (row['strict_quality_ok'] == 0 and
                                    any(reason.startswith('preamble_anomaly:') for reason in reasons))
    return dict(schema='csi-sqlite-dashboard-1', historical=True, read_only=True, live_capture=False,
                queried_at_utc=datetime.now(timezone.utc).isoformat(),
                pilot_csv_comparison=comparison, sessions=rows)
