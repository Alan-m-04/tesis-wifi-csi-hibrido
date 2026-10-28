#!/usr/bin/env python3
"""Prepare or metadata-only preflight by default; explicit physical execution gate."""
import argparse
import json
from pathlib import Path
import select
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from presence_v4_uart import UartSession, check_authorization, preflight_uart, validate_uart_plan
from presence_v4_journal import audit_v4


def operate(session):
    print('UART v4: un slot manual por vez. slot ID [last]; declare ID yes|uncertain MOTIVO; close; abort.', flush=True)
    print('yes declara condición establecida/mantenida y avisos oídos; no mide la etiqueta físicamente.', flush=True)
    cursor = 0
    while True:
        session.step()
        m = session.machine
        for event in m.events[cursor:]:
            if event['kind'] in ('initial_available','gate_opened','window_started',
                'window_ended_connection_open','both_ports_closed_confirmed','suspended','signal_result'):
                print(json.dumps(event,ensure_ascii=False),flush=True)
        cursor = len(m.events)
        if session.read_loop_stopped and (m.fatal or all(w['label']['status']!='pending' for w in m.windows)):
            break
        if select.select([sys.stdin],[],[],.005)[0]:
            line = sys.stdin.readline()
            if not line:
                session.command('interrupt', detail='operator EOF; labels remain unconfirmed')
                continue
            words = line.strip().split()
            try:
                if len(words) in (2,3) and words[0]=='slot' and (len(words)==2 or words[2]=='last'):
                    session.command('request', slot_id=words[1], last=len(words)==3)
                elif len(words)>=3 and words[0]=='declare' and words[2] in ('yes','uncertain'):
                    ok = words[2]=='yes'
                    session.command('declare',slot_id=words[1],established=ok,maintained=ok,heard=ok,
                                    notes='' if ok else ' '.join(words[3:]))
                elif words==['close']:
                    session.command('close_request')
                elif words==['abort']:
                    session.command('interrupt')
                else:
                    print('Orden rechazada, sin reintento automático.',flush=True)
            except (ValueError,IndexError,StopIteration) as exc:
                print('Orden rechazada: '+str(exc),flush=True)
    session.finalize()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,default=ROOT/'config/campana_presencia_uart_v4.template.json')
    modes=parser.add_mutually_exclusive_group()
    modes.add_argument('--preflight-only',action='store_true')
    modes.add_argument('--execute-after-approval',action='store_true')
    parser.add_argument('--authorization-reference')
    parser.add_argument('--output-new',type=Path)
    args=parser.parse_args()
    plan=validate_uart_plan(json.loads(args.plan.read_text()))
    if args.preflight_only:
        print(json.dumps(dict(state='PREFLIGHT_METADATA_ONLY',physical_UART_opened=False,
                              identities=preflight_uart(plan)),indent=2));return 0
    if not args.execute_after_approval:
        print(json.dumps(dict(state='PREPARED_NOT_EXECUTED',physical_UART_opened=False,
            authorization_granted=False,plan=plan),ensure_ascii=False,indent=2));return 0
    check_authorization(args.authorization_reference)
    validate_uart_plan(plan,execution=True)
    if args.output_new is None:
        parser.error('--output-new is required for an explicitly authorized physical connection')
    with UartSession(args.output_new,plan,authorization_reference=args.authorization_reference) as session:
        operate(session)
    report=audit_v4(args.output_new)
    print(json.dumps(dict(integrity_ok=report['integrity_ok'],replay_ok=report['replay_ok'],
        fatal=report['state']['fatal'],physical_capture=True),indent=2))
    return int(report['state']['fatal'] is not None or not report['state']['connection']['quality_ok'])


if __name__=='__main__':
    raise SystemExit(main())
