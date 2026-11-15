#!/usr/bin/env python3
"""Prepare a separate 240 s diagnostic; UART requires an explicit single grant."""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from rx02_diagnostic.contract import validate_plan
from rx02_diagnostic.uart import preflight_rx02
from rx02_diagnostic.checkpoint import CheckpointRx02Session,audit_checkpoint_rx02
from presence_rx02 import certify_rx02
from presence_v4_journal import digest,write_new

PREPARATION=ROOT/'results/local/preparacion-rx02-diagnostico-checkpoints-r1'
OUTPUT=ROOT/'results/local/diagnostico-checkpoints-rx02-r1'
PLAN=PREPARATION/'plan.local.json'
PREFLIGHT=PREPARATION/'preflight.json'


def diagnostic_report(directory):
    root=Path(directory)
    report=audit_checkpoint_rx02(root)
    p=json.loads((root/'plan.json').read_text())
    provenance=json.loads((root/'provenance.json').read_text())
    # Only identity/storage checks are reused; no slots or eligibility are issued.
    checks=certify_rx02(root,provenance,report['state'])
    events=json.loads((root/'events.json').read_text())
    opened=[e for e in events if e['kind']=='opened']
    operations=[json.loads(line) for line in (root/'operations.jsonl').read_text().splitlines()]
    closing=[e for e in operations if e['op']=='closing']
    elapsed=closing[0]['now_ns']-opened[0]['now_ns'] if len(opened)==len(closing)==1 else None
    receipt=json.loads((root/'close-receipt.json').read_text())
    runtime=json.loads((root/'summary.json').read_text())['runtime']
    endpoint=runtime['receivers'].get('RX-02',{})
    closed=(report['state']['closed'].get('RX-02',{}).get('confirmed') is True and
            receipt['selected_confirmed'] is True and runtime['startup_reader_stopped'] is True and
            endpoint.get('open_attempts')==1 and endpoint.get('close_attempts')==1 and endpoint.get('is_open') is False)
    sustained=(elapsed is not None and elapsed>=p['duration_ns'] and
               report['state']['initial_available_ns'] is not None and report['state']['fatal'] is None)
    report['diagnostic']=dict(target_duration_ns=p['duration_ns'],observed_open_to_closing_ns=elapsed,
        sustained_service_ok=sustained,identity_ok=checks['identity_ok'],storage_ok=checks['storage_ok'],
        close_ok=closed,checkpoint_ok=True,
        diagnostic_ok=bool(sustained and closed and checks['identity_ok'] and checks['storage_ok']),
        quality_is_separate=True,no_campaign_replacement=True,windows_requested=False,
        permitted_uses=dict(calibration=False,training=False,production=False))
    return report


def serve(session):
    opened=next(e['now_ns'] for e in session.machine.events if e['kind']=='opened')
    deadline=opened+session.machine.plan['duration_ns']
    start_cpu=time.process_time_ns();steps=0;max_step=0;cursor=0
    try:
        while not session.read_loop_stopped:
            if session.clock()>=deadline:
                session.command('close_request')
                session.close()
                break
            before=session.clock()
            session.step()
            max_step=max(max_step,session.clock()-before);steps+=1
            for event in session.machine.events[cursor:]:
                if event['kind'] in ('initial_available','suspended','selected_port_closed_confirmed','signal_result'):
                    print(json.dumps(event,ensure_ascii=False),flush=True)
            cursor=len(session.machine.events)
            if not session.read_loop_stopped:
                time.sleep(.005)
    except KeyboardInterrupt:
        session.command('interrupt',detail='operator interruption; no restart')
        session.close()
    # Stored before manifest finalization; metrics describe this process, not a resource guarantee.
    write_new(session.journal.root/'service-metrics.json',dict(steps=steps,max_step_ns=max_step,
        service_cpu_ns=time.process_time_ns()-start_cpu,
        process_peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        peak_rss_scope='whole process through service end; not periodic sampling',
        deadline_ns=deadline,wall_clock_io_deadline_guaranteed=False))


def condition_hash(plan):
    content={k:v for k,v in plan.items() if k not in ('authorization_granted','review_state')}
    return hashlib.sha256(json.dumps(content,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,default=PLAN)
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--preflight-only',action='store_true')
    mode.add_argument('--audit',type=Path)
    mode.add_argument('--execute-after-approval',action='store_true')
    parser.add_argument('--authorization-reference')
    parser.add_argument('--output-new',type=Path)
    args=parser.parse_args(argv)
    if args.audit:
        report=diagnostic_report(args.audit)
        print(json.dumps(report,ensure_ascii=False,indent=2))
        return int(not report['diagnostic']['diagnostic_ok'])
    p=validate_plan(json.loads(args.plan.read_text()),allow_physical=True)
    if not args.preflight_only and not args.execute_after_approval:
        print(json.dumps(dict(state='PREPARED_NOT_AUTHORIZED',physical_UART_opened=False,
            authorization_granted=False,plan_sha256=digest(args.plan),output_new=str(OUTPUT),plan=p),indent=2))
        return 0
    validate_plan(p,allow_physical=True,execution=True)
    if args.preflight_only:
        if PREFLIGHT.exists():
            raise ValueError('Preflight evidence already exists; preserve it for review')
        report=dict(state='PREFLIGHT_METADATA_ONLY',physical_UART_opened=False,
            plan_sha256=digest(args.plan),conditions_sha256=condition_hash(p),identities=preflight_rx02(p))
        write_new(PREFLIGHT,report)
        print(json.dumps(report,indent=2))
        return 0
    if (p.get('authorization_granted') is not True or p.get('review_state')!='authorized_single_attempt' or
        args.authorization_reference!='RX02-DIAG-CP-R1:'+digest(args.plan)):
        raise ValueError('New explicit grant bound to this exact diagnostic plan required')
    if args.output_new is None or args.output_new.resolve()!=OUTPUT or OUTPUT.exists():
        raise ValueError('Only the fixed, still nonexistent diagnostic output is permitted; no retry')
    preflight=json.loads(PREFLIGHT.read_text())
    # Grant fields may change after metadata preflight; identities are checked again now and by the session.
    if (preflight.get('state')!='PREFLIGHT_METADATA_ONLY' or preflight.get('physical_UART_opened') is not False or
        preflight.get('conditions_sha256')!=condition_hash(p) or preflight['identities']!=preflight_rx02(p)):
        raise ValueError('Preflight metadata changed; no UART opened')
    with CheckpointRx02Session(OUTPUT,p,authorization_reference=args.authorization_reference) as session:
        serve(session)
    report=diagnostic_report(OUTPUT)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return int(not report['diagnostic']['diagnostic_ok'])


if __name__=='__main__':
    raise SystemExit(main())
