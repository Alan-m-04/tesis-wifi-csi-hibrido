#!/usr/bin/env python3
"""Explicit C03 checkpoints; absent persistence revision delegates to historical CLI."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools')]
import piloto_presencia_rx02 as historical
from presence_rx02_uart import Rx02Session
from presence_rx02_journal import audit_rx02
from rx02_checkpoint_journal import PERSISTENCE_REVISION
from rx02_c03.contract import validate_plan,INTEGRATION_REVISION,OUTPUT_RELATIVE
from rx02_c03.checkpoint import C03CheckpointSession,audit_c03_checkpoints
from rx02_c03.uart import preflight_rx02
from presence_v4_journal import digest,write_new

PREPARATION=ROOT/'results/local/preparacion-C03-checkpoint-r1'
PLAN=PREPARATION/'plan.local.json'
PREFLIGHT=PREPARATION/'preflight.json'
OUTPUT=ROOT/OUTPUT_RELATIVE
SOURCES=['src/rx02_checkpoint_journal.py']+['src/rx02_c03/'+n+'.py' for n in
    ('__init__','contract','journal','uart','checkpoint')]+['tools/campana_rx02_checkpoint.py']


def select_path(plan):
    if 'persistence_revision' not in plan:
        if 'integration_revision' in plan:
            raise ValueError('Integration without explicit persistence revision is invalid')
        return Rx02Session,audit_rx02
    if plan.get('persistence_revision')!=PERSISTENCE_REVISION:
        raise ValueError('Unsupported persistence revision; no silent historical fallback')
    validate_plan(plan,allow_physical=True)
    return C03CheckpointSession,audit_c03_checkpoints


def condition_hash(plan):
    content={k:v for k,v in plan.items() if k not in ('authorization_granted','review_state')}
    return hashlib.sha256(json.dumps(content,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def source_hashes():
    return {name:digest(ROOT/name) for name in SOURCES}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,default=PLAN)
    modes=parser.add_mutually_exclusive_group()
    modes.add_argument('--preflight-only',action='store_true')
    modes.add_argument('--audit',type=Path)
    modes.add_argument('--execute-after-approval',action='store_true')
    parser.add_argument('--authorization-reference')
    parser.add_argument('--output-new',type=Path)
    args=parser.parse_args(argv)
    if args.audit:
        plan=json.loads((args.audit/'plan.json').read_text())
        _,auditor=select_path(plan)
        print(json.dumps(auditor(args.audit),ensure_ascii=False,indent=2))
        return 0
    plan=json.loads(args.plan.read_text())
    session_type,auditor=select_path(plan)
    if session_type is Rx02Session:
        return historical.main(argv)
    if not args.preflight_only and not args.execute_after_approval:
        print(json.dumps(dict(state='PREPARED_NOT_AUTHORIZED',physical_UART_opened=False,
            authorization_granted=False,persistence_revision=PERSISTENCE_REVISION,
            integration_revision=INTEGRATION_REVISION,session_class=session_type.__name__,
            auditor=auditor.__name__,plan_sha256=digest(args.plan),output_new=str(OUTPUT),plan=plan),indent=2))
        return 0
    validate_plan(plan,allow_physical=True,execution=True)
    if args.preflight_only:
        if PREFLIGHT.exists():
            raise ValueError('Preflight already recorded; preserve it, do not overwrite')
        evidence=dict(state='PREFLIGHT_METADATA_ONLY',physical_UART_opened=False,
            authorization_granted=False,plan_sha256=digest(args.plan),conditions_sha256=condition_hash(plan),
            persistence_revision=PERSISTENCE_REVISION,integration_revision=INTEGRATION_REVISION,
            sources=source_hashes(),identities=preflight_rx02(plan))
        write_new(PREFLIGHT,evidence)
        print(json.dumps(evidence,indent=2))
        return 0
    expected_reference='RX02-C03-CHECKPOINT-R1:'+digest(args.plan)
    if (plan.get('authorization_granted') is not True or plan.get('review_only') is not False or
        plan.get('review_state')!='authorized_single_attempt' or args.authorization_reference!=expected_reference):
        raise ValueError('New explicit C03 single-attempt authorization bound to exact plan required')
    if args.output_new is None or args.output_new.resolve()!=OUTPUT or OUTPUT.exists():
        raise ValueError('Fixed new C03 output required; no retry or alternate directory')
    evidence=json.loads(PREFLIGHT.read_text())
    if (evidence.get('state')!='PREFLIGHT_METADATA_ONLY' or evidence.get('physical_UART_opened') is not False or
        evidence.get('persistence_revision')!=PERSISTENCE_REVISION or
        evidence.get('integration_revision')!=INTEGRATION_REVISION or
        evidence.get('conditions_sha256')!=condition_hash(plan) or evidence.get('sources')!=source_hashes()):
        raise ValueError('Preflight conditions, revisions or sources changed; no opening')
    if evidence['identities']!=preflight_rx02(plan):
        raise ValueError('USB metadata changed; no opening or fallback')
    with session_type(OUTPUT,plan,authorization_reference=args.authorization_reference) as session:
        historical.operate(session)
    report=auditor(OUTPUT)
    print(json.dumps(dict(integrity_ok=report['integrity_ok'],replay_ok=report['replay_ok'],
        persistence_revision=report['persistence_revision'],integration_revision=report['integration_revision'],
        connection=report['state']['connection'],fatal=report['state']['fatal'],
        exploratory_eligibility=report['exploratory_eligibility'],
        selected_close_confirmed=report['state']['closed']['RX-02']['confirmed']),indent=2))
    windows=report['exploratory_eligibility']['windows']
    return int(report['state']['fatal'] is not None or len(windows)!=2 or not all(w['eligible'] for w in windows))


if __name__=='__main__':raise SystemExit(main())
