#!/usr/bin/env python3
"""Prepare RX-02 pilot, metadata preflight or offline audit; execution gated."""
import argparse
import json
import os
from pathlib import Path
import select
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from presence_rx02 import validate_plan
from presence_rx02_journal import audit_rx02
from presence_rx02_uart import Rx02Session, preflight_rx02
from presence_v4_uart import check_authorization


class CommandInput:
    """Read only available bytes; a partial command never blocks UART service."""
    def __init__(self, fd):
        self.fd, self.buffer, self.eof = fd, b'', False

    def poll(self):
        if self.eof or not select.select([self.fd], [], [], .005)[0]:
            return []
        chunk = os.read(self.fd, 4096)
        if not chunk:
            self.eof = True
            return []
        self.buffer += chunk
        if len(self.buffer) > 8192:
            raise ValueError('Operator input exceeded 8192 bytes')
        parts = self.buffer.split(b'\n')
        self.buffer = parts.pop()
        return [line.decode('utf-8', errors='strict').strip().split() for line in parts]


def operator_command(session, words):
    if len(words) in (2, 3) and words[0] == 'slot' and (len(words) == 2 or words[2] == 'last'):
        session.command('request', slot_id=words[1], last=len(words) == 3)
    elif len(words) >= 3 and words[0] == 'declare' and words[2] in ('yes', 'uncertain'):
        if words[2] == 'yes' and len(words) != 3:
            raise ValueError('yes cannot carry unresolved notes; declare uncertain instead')
        ok = words[2] == 'yes'
        session.command('declare', slot_id=words[1], established=ok, maintained=ok,
                        heard=ok, notes='' if ok else ' '.join(words[3:]))
    elif words == ['close']:
        session.command('close_request')
    elif words == ['abort']:
        session.command('interrupt')
    else:
        raise ValueError('slot ID [last]; declare ID yes|uncertain MOTIVO; close; abort')


def operate(session, command_input=None):
    print('Sólo RX-02. Slots manuales; yes declara condición y avisos oídos, no mide verdad física.', flush=True)
    commands = command_input or CommandInput(sys.stdin.fileno())
    cursor = 0
    while True:
        session.step()
        m = session.machine
        for event in m.events[cursor:]:
            if event['kind'] in ('initial_available', 'gate_opened', 'window_started',
                'window_ended_connection_open', 'selected_port_closed_confirmed', 'suspended', 'signal_result'):
                print(json.dumps(event, ensure_ascii=False), flush=True)
        cursor = len(m.events)
        if session.read_loop_stopped and (m.fatal or all(w['label']['status'] != 'pending' for w in m.windows)):
            break
        for words in commands.poll():
            try:
                operator_command(session, words)
            except (ValueError, IndexError, StopIteration) as exc:
                print('Orden rechazada: '+str(exc), flush=True)
        if commands.eof:
            session.command('interrupt', detail='operator EOF; labels remain unconfirmed')
    session.finalize()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, default=ROOT/'config/piloto_rx02_r1_C01.review.json')
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--preflight-only', action='store_true')
    modes.add_argument('--audit', type=Path)
    modes.add_argument('--execute-after-approval', action='store_true')
    parser.add_argument('--authorization-reference')
    parser.add_argument('--output-new', type=Path)
    args = parser.parse_args(argv)
    if args.audit:
        print(json.dumps(audit_rx02(args.audit), ensure_ascii=False, indent=2))
        return 0
    plan = validate_plan(json.loads(args.plan.read_text()), allow_physical=True)
    if args.preflight_only:
        print(json.dumps(dict(state='PREFLIGHT_METADATA_ONLY', physical_UART_opened=False,
                              identities=preflight_rx02(plan)), indent=2))
        return 0
    if not args.execute_after_approval:
        print(json.dumps(dict(state='PREPARED_NOT_AUTHORIZED', physical_UART_opened=False,
                              authorization_granted=False, plan=plan), ensure_ascii=False, indent=2))
        return 0
    check_authorization(args.authorization_reference)
    validate_plan(plan, allow_physical=True, execution=True)
    if args.output_new is None:
        parser.error('--output-new required for one explicitly authorized connection')
    with Rx02Session(args.output_new, plan, authorization_reference=args.authorization_reference) as session:
        operate(session)
    report = audit_rx02(args.output_new)
    print(json.dumps(dict(integrity_ok=True, replay_ok=True, physical_capture=True,
        acquisition=dict(physical_UART_opened=session.machine.states['RX-02']['opened']),
        audit_activity=dict(physical_UART_opened=False),
        connection=report['state']['connection'], fatal=report['state']['fatal'],
        exploratory_eligibility=report['exploratory_eligibility']), indent=2))
    windows = report['exploratory_eligibility']['windows']
    return int(report['state']['fatal'] is not None or len(windows) != 2 or
               not all(w['eligible'] for w in windows))


if __name__ == '__main__':
    raise SystemExit(main())
