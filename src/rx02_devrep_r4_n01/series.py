"""Solo la primera conexión R4-N01; no consulta ni continúa predecesores R1."""
import json
from presence_v4_journal import digest
from rx02_devrep.series import boot_id, validate_setup_snapshot
from rx02_devrep_r4_n01.contract import validate_plan, OPERATOR_INTERFACE_REVISION


def validate_entry(entry, runtime, *, current_boot=False):
    from ejecutar_devrep_r4_n01 import serialized_hash, validate_authorization, review_receipt, all_sources
    from rx02_devrep_r4_n01.contract import runtime_plan
    if not isinstance(entry, dict):
        raise ValueError('New independent R4-N01 entry evidence required')
    request = entry.get('request', {})
    request_hash = serialized_hash(request)
    validate_authorization(entry.get('authorization', {}), request_hash)
    prepared = entry.get('prepared_plan', {})
    receipt = entry.get('receipt', {})
    sidecar = entry.get('sidecar', {})
    from preflight_devrep_r4 import practice_reference
    practice_path, practice_hash = practice_reference()
    if (entry.get('request_sha256') != request_hash or
            request.get('plan_sha256') != serialized_hash(prepared) or
            request.get('receipt_sha256') != serialized_hash(receipt) or
            request.get('sidecar_sha256') != serialized_hash(sidecar) or
            request.get('runtime_plan_sha256') != serialized_hash(runtime) or
            runtime_plan(prepared) != runtime or request.get('sources') != all_sources() or
            request.get('connection_id') != 'RX02-DEVREP-R4-N01' or
            request.get('output_new') != runtime['output_new'] or
            request.get('order') != ['E', 'S'] or request.get('max_attempts') != 1 or
            request.get('retry_allowed') is not False or request.get('operator_terminal_only') is not True or
            request.get('host_boot_id') != receipt.get('host_boot_id') or
            request.get('operator_interface_revision') != OPERATOR_INTERFACE_REVISION or
            request.get('keyboard_practice_path') != practice_path or
            request.get('keyboard_practice_sha256') != practice_hash or
            entry.get('identities') != receipt.get('metadata', {}).get('identities')):
        raise ValueError('R4-N01 entry plan/receipt/authorization/source binding differs')
    review_receipt(prepared, receipt, sidecar, current_boot=current_boot)


def predecessor_context(plan):
    validate_plan(plan, allow_physical=True)
    if plan.get('predecessor') is not None:
        raise ValueError('R4-N01 has no predecessor; R1 cannot be reused')
    return None


def wait_for_open_target(context, clock=None):
    if context is not None:
        raise ValueError('R4-N01 cannot wait for or continue an older connection')


def verify_recorded_predecessor(root, report):
    plan = json.loads((root / 'plan.json').read_text())
    transport = json.loads((root / 'provenance.json').read_text())['transport']
    predecessor_context(plan)
    entry = transport.get('entry_evidence', {})
    validate_entry(entry, plan)
    if (transport.get('series_context') is not None or
            transport.get('authorization_reference') != plan['connection_id'] + ':' + digest(root / 'plan.json') or
            not plan.get('authorization_granted') or
            entry.get('authorization', {}).get('authorization_granted') is not True or
            entry.get('authorization', {}).get('connection_id') != plan['connection_id'] or
            entry.get('request', {}).get('runtime_plan_sha256') != digest(root / 'plan.json') or
            entry.get('receipt', {}).get('host_boot_id') != transport.get('host_boot_id')):
        raise ValueError('R4-N01 independent receipt/authorization provenance differs')
