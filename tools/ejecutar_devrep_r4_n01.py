#!/usr/bin/env python3
"""Revisión offline o un único intento R4-N01, solo tras autorización nueva registrada."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tools')]
import preflight_devrep_r4 as prep
from presence_v4_journal import digest
from rx02_devrep_r4_n01.contract import runtime_plan
from rx02_devrep_r4_n01.session import DevrepSession, audit_devrep
from devrep_keyboard_prompt import operate

DIRECTORY = prep.PREPARATION
PLAN = prep.CONFIRMED_PLAN
RECEIPT = DIRECTORY / 'preflight-r4-N01-r1.json'
REQUEST = DIRECTORY / 'solicitud-autorizacion-R4-N01.json'
AUTHORIZATION = DIRECTORY / 'autorizacion-nueva-R4-N01.json'
ADDED_SOURCES = ['src/rx02_devrep_r4_n01/' + n + '.py' for n in
                 ('__init__', 'contract', 'journal', 'session', 'series')] + ['tools/ejecutar_devrep_r4_n01.py']


def serialized_hash(value):
    return hashlib.sha256((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()).hexdigest()


def base_sources():
    sources = prep.source_hashes()
    sources['tools/preflight_devrep_r4.py'] = digest(ROOT / 'tools/preflight_devrep_r4.py')
    return sources


def all_sources():
    return dict(base_sources(), **{name: digest(ROOT / name) for name in ADDED_SOURCES})


def review_receipt(plan, receipt, sidecar, *, current_boot=True):
    prep.validate(plan, confirmed=current_boot)
    if (receipt.get('schema') != 'devrep-r4-preparation-metadata-1' or
            receipt.get('state') != 'PREFLIGHT_METADATA_ONLY' or
            receipt.get('connection_id') != prep.CONNECTION_ID or receipt.get('series_id') != prep.SERIES_ID or
            receipt.get('plan_sha256') != digest(ROOT / PLAN) or receipt.get('sources') != base_sources() or
            any(receipt.get(k) is not False for k in ('physical_UART_opened', 'capture_executed',
                                                    'authorization_granted', 'acquisition_executor_enabled')) or
            receipt.get('conditions_confirmed_current') is not True or
            (current_boot and receipt.get('host_boot_id') != prep.boot_id()) or
            receipt.get('host_boot_id') != plan['conditions_confirmation']['host_boot_id']):
        raise ValueError('R4-N01 receipt, plan, sources, boot or state differs')
    snapshots = receipt.get('metadata_snapshots', {})
    first, second = snapshots.get('first'), snapshots.get('second')
    expected_comparison = dict(revision=prep.METADATA_COMPARISON_REVISION, raw_equal=first == second,
                               equal_under_revision=prep.metadata_snapshots_equal(first, second))
    if (first is None or second is None or receipt.get('metadata') != first or
            not expected_comparison['equal_under_revision'] or receipt.get('metadata_comparison') != expected_comparison or
            sidecar.get('state') != 'SNAPSHOTS_ONLY_NOT_APPROVAL' or
            any(sidecar.get(k) != receipt.get(k) for k in ('connection_id', 'plan_sha256', 'host_boot_id', 'sources')) or
            sidecar.get('first') != first or sidecar.get('second') != second or
            sidecar.get('metadata_comparison') != expected_comparison or
            receipt.get('free_bytes', 0) < plan['storage_policy']['initial_free_bytes']):
        raise ValueError('R4-N01 snapshot evidence differs')
    identity = first['identities'].get('RX-02', {})
    if (set(first['identities']) != {'RX-02'} or identity.get('by_id') != prep.PORTS['RX-02'] or
            identity.get('serial') != '5C93200689' or identity.get('vid') != '1a86' or
            identity.get('pid') != '55d3' or identity.get('bus') != 'usb'):
        raise ValueError('R4-N01 fixed receiver identity differs')
    return True


def make_request():
    prepared = json.loads((ROOT / PLAN).read_text())
    receipt = json.loads((ROOT / RECEIPT).read_text())
    sidecar = json.loads((ROOT / RECEIPT).with_suffix('.snapshots.json').read_text())
    review_receipt(prepared, receipt, sidecar)
    practice_path, practice_hash = prep.practice_reference()
    return dict(schema='r4-n01-single-attempt-authorization-request-1', state='AWAITING_NEW_HUMAN_AUTHORIZATION',
                connection_id=prep.CONNECTION_ID, order=['E', 'S'], max_attempts=1, retry_allowed=False,
                authorization_granted=False, plan_path=str(PLAN), plan_sha256=digest(ROOT / PLAN),
                receipt_path=str(RECEIPT), receipt_sha256=digest(ROOT / RECEIPT),
                sidecar_sha256=digest((ROOT / RECEIPT).with_suffix('.snapshots.json')),
                host_boot_id=prep.boot_id(), output_new=prep.OUTPUT,
                runtime_plan_sha256=serialized_hash(runtime_plan(prepared)), sources=all_sources(),
                operator_interface_revision=prep.OPERATOR_INTERFACE_REVISION,
                keyboard_practice_path=practice_path, keyboard_practice_sha256=practice_hash,
                ready_requirement='READY exacto y disponibilidad antes de begin+10 s, sin garantía de repetición; fallo detiene sin reintento',
                operator_terminal_only=True)


def validate_authorization(authorization, request_hash):
    if (authorization.get('schema') != 'r4-n01-new-human-authorization-1' or
            authorization.get('connection_id') != prep.CONNECTION_ID or
            authorization.get('request_sha256') != request_hash or
            authorization.get('authorization_granted') is not True or
            authorization.get('ready_risk_reviewed') is not True or
            authorization.get('max_attempts') != 1 or authorization.get('retry_allowed') is not False or
            authorization.get('operator_terminal_only') is not True or
            not isinstance(authorization.get('user_statement'), str) or not authorization['user_statement'].strip()):
        raise ValueError('New explicit R4-N01 single-attempt authorization and READY review required')


def review_request():
    recorded = json.loads((ROOT / REQUEST).read_text())
    if recorded != make_request():
        raise ValueError('Frozen R4-N01 authorization request differs from current inputs/sources')
    if (ROOT / prep.OUTPUT).exists():
        raise ValueError('R4-N01 output exists; no retry or alternate output')
    return recorded


def execute(authorization_path, output):
    # El grant se comprueba antes de consultar metadatos o construir una sesión.
    if Path(authorization_path).resolve() != (ROOT / AUTHORIZATION).resolve():
        raise ValueError('Use only the new R4-N01 authorization artifact')
    if Path(output).resolve() != (ROOT / prep.OUTPUT).resolve():
        raise ValueError('Only the exclusive R4-N01 output is permitted')
    authorization = json.loads(Path(authorization_path).read_text())
    request_hash = digest(ROOT / REQUEST)
    validate_authorization(authorization, request_hash)
    request = review_request()
    prepared = json.loads((ROOT / PLAN).read_text())
    receipt = json.loads((ROOT / RECEIPT).read_text())
    current = prep.metadata_snapshot()
    if not prep.metadata_snapshots_equal(receipt['metadata'], current):
        raise ValueError('Current USB metadata differs from the reviewed R4-N01 receipt; no opening')
    runtime = runtime_plan(prepared)
    if serialized_hash(runtime) != request['runtime_plan_sha256']:
        raise ValueError('Runtime plan differs; no opening')
    if request != make_request():
        raise ValueError('Inputs changed immediately before session; no opening')
    entry = dict(request=request, request_sha256=request_hash, authorization=authorization,
                 receipt=receipt, sidecar=json.loads((ROOT / RECEIPT).with_suffix('.snapshots.json').read_text()),
                 prepared_plan=prepared, identities=current['identities'])
    reference = prep.CONNECTION_ID + ':' + request['runtime_plan_sha256']
    with DevrepSession(ROOT / prep.OUTPUT, runtime, authorization_reference=reference, entry_evidence=entry) as session:
        operate(session)
    report = audit_devrep(ROOT / prep.OUTPUT)
    print(json.dumps(dict(integrity_ok=report['integrity_ok'], replay_ok=report['replay_ok'],
                         series_can_continue=report['series_can_continue'], closed=report['state']['closed']), indent=2))
    return int(not report['series_can_continue'])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--execute-after-approval', action='store_true')
    mode.add_argument('--audit', type=Path)
    parser.add_argument('--authorization-file', type=Path, default=ROOT / AUTHORIZATION)
    parser.add_argument('--output-new', type=Path, default=ROOT / prep.OUTPUT)
    args = parser.parse_args(argv)
    if args.audit:
        print(json.dumps(audit_devrep(args.audit), ensure_ascii=False, indent=2))
        return 0
    if args.execute_after_approval:
        return execute(args.authorization_file, args.output_new)
    # Sin solicitud/grant nuevos, revisar solo el borrador; no fabricar autorización.
    prepared_path = ROOT / DIRECTORY / 'plan.local.r1.json'
    prepared = json.loads(prepared_path.read_text())
    prep.validate(prepared)
    print(json.dumps(dict(state='ENTRY_VALIDATED_OFFLINE_PREFLIGHT_PENDING', connection_id=prep.CONNECTION_ID,
                         operator_interface_revision=prep.OPERATOR_INTERFACE_REVISION,
                         preflight_receipt=str(RECEIPT), authorization_file=str(AUTHORIZATION),
                         plan_sha256=digest(prepared_path), output_new=prep.OUTPUT,
                         physical_UART_opened=False, capture_executed=False, authorization_granted=False), indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
