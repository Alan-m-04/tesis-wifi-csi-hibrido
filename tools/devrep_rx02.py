#!/usr/bin/env python3
"""DEVREP per-connection review/audit or future explicitly authorized fixed-agenda run."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools')]
from rx02_devrep.contract import validate_plan,CONNECTIONS,INTEGRATION_REVISION,SCHEDULE_REVISION
from rx02_devrep.session import DevrepSession,audit_devrep,preflight_rx02
from rx02_devrep.coordinator import operate
from rx02_devrep.series import predecessor_context,validate_setup_snapshot,boot_id
from presence_v4_journal import digest,write_new
CONDITIONS_REVISION='devrep-operational-conditions-2'
ADMINISTRATIVE_FIELDS=frozenset(('authorization_granted','review_state','review_only'))


def condition_hash(plan):
    operational={k:v for k,v in plan.items() if k not in ADMINISTRATIVE_FIELDS}
    return hashlib.sha256(json.dumps(operational,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def validate_evidence(evidence,plan,sources,context,host_boot):
    if (evidence.get('conditions_revision')!=CONDITIONS_REVISION or
        evidence.get('state')!='PREFLIGHT_METADATA_ONLY' or evidence.get('physical_UART_opened') is not False or
        evidence.get('authorization_granted') is not False or
        evidence.get('conditions_sha256')!=condition_hash(plan) or evidence.get('sources')!=sources or
        evidence.get('series_context')!=context or evidence.get('host_boot_id')!=host_boot):
        raise ValueError('Metadata conditions, revision, sources, boot or predecessor changed; no opening')


def source_hashes():
    names=['src/'+n for n in ('persistent_presence_v4.py','presence_v4_journal.py','presence_v4_pty.py','presence_v4_audio.py',
        'availability_window.py','capture_csi_multi.py','capture_csi.py','preserving_serial.py','controlled_protocol.py',
        'presence_v4_exploratory.py','presence_rx02.py','presence_rx02_journal.py','presence_rx02_uart.py','presence_v4_uart.py','rx02_checkpoint_journal.py')]
    names+=['tools/campana_presencia_v4.py','tools/piloto_presencia_rx02.py','config/csi_esp32s3.json','config/pyserial_uart_v4.lock.json']
    names+=['src/rx02_c03/'+n+'.py' for n in ('__init__','contract','journal','uart','checkpoint')]+['tools/campana_rx02_checkpoint.py']
    names+=['src/rx02_devrep/'+n+'.py' for n in ('__init__','contract','journal','session','coordinator','series')]+['tools/devrep_rx02.py']
    return {n:digest(ROOT/n) for n in names}


def preparation(plan):
    ordinal=CONNECTIONS[plan['connection_id']]['ordinal']
    return ROOT/f'results/local/preparacion-devrep-r1-D{ordinal:02d}'


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,default=ROOT/'config/devrep_r1/D01.review.json')
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--audit',type=Path)
    mode.add_argument('--preflight-only',action='store_true')
    mode.add_argument('--execute-after-approval',action='store_true')
    parser.add_argument('--authorization-reference');parser.add_argument('--output-new',type=Path)
    parser.add_argument('--preflight-receipt',type=Path,help='New metadata receipt, directly within this connection preparation directory')
    args=parser.parse_args(argv)
    if args.audit:
        report=audit_devrep(args.audit);print(json.dumps(report,ensure_ascii=False,indent=2));return 0
    plan=validate_plan(json.loads(args.plan.read_text()),allow_physical=True)
    if not args.preflight_only and not args.execute_after_approval:
        print(json.dumps(dict(state='PREPARED_NOT_AUTHORIZED',physical_UART_opened=False,physical_preflight_performed=False,
            authorization_granted=False,connection_id=plan['connection_id'],slots=plan['slots'],schedule=plan['schedule'],
            persistence_revision=plan['persistence_revision'],integration_revision=INTEGRATION_REVISION,schedule_revision=SCHEDULE_REVISION,
            ready_risk_reviewed=plan['ready_risk_reviewed'],ready_repetition_guaranteed=False,
            output_new=plan['output_new'],plan_sha256=digest(args.plan)),indent=2));return 0
    validate_plan(plan,allow_physical=True,execution=True)
    root=preparation(plan);receipt=args.preflight_receipt or root/'preflight.json';output=ROOT/plan['output_new']
    if receipt.resolve().parent!=root.resolve() or receipt.suffix!='.json':
        raise ValueError('Metadata receipt must be a JSON file in the fixed preparation directory')
    if args.execute_after_approval:
        if (plan.get('authorization_granted') is not True or plan.get('review_only') is not False or
            plan.get('review_state')!='authorized_single_attempt' or args.authorization_reference!=plan['connection_id']+':'+digest(args.plan)):
            raise ValueError('New explicit single-connection DEVREP authorization required')
        if args.output_new is None or args.output_new.resolve()!=output or output.exists():
            raise ValueError('Fixed new output required; no retry or alternate output')
    validate_setup_snapshot(plan)
    context=predecessor_context(plan)
    if args.preflight_only:
        if receipt.exists():raise ValueError('Metadata receipt already exists; do not overwrite')
        evidence=dict(state='PREFLIGHT_METADATA_ONLY',physical_UART_opened=False,authorization_granted=False,
            plan_sha256=digest(args.plan),conditions_revision=CONDITIONS_REVISION,conditions_sha256=condition_hash(plan),sources=source_hashes(),
            series_context=context,host_boot_id=boot_id(),identities=preflight_rx02(plan))
        root.mkdir(parents=True,exist_ok=True);write_new(receipt,evidence)
        print(json.dumps(evidence,indent=2));return 0
    evidence=json.loads(receipt.read_text())
    validate_evidence(evidence,plan,source_hashes(),context,boot_id())
    if evidence['identities']!=preflight_rx02(plan):raise ValueError('USB identity changed; no opening')
    with DevrepSession(output,plan,authorization_reference=args.authorization_reference) as session:operate(session)
    report=audit_devrep(output)
    print(json.dumps(dict(integrity_ok=report['integrity_ok'],replay_ok=report['replay_ok'],
        series_can_continue=report['series_can_continue'],schedule=report['state']['devrep_schedule'],
        exploratory_eligibility=report['exploratory_eligibility'],closed=report['state']['closed']),indent=2))
    return int(not report['series_can_continue'])


if __name__=='__main__':raise SystemExit(main())
