#!/usr/bin/env python3
"""Prepare v4 without devices, run an explicit PTY fixture, or audit its evidence."""
import argparse
import csv
import io
import json
import select
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from availability_window import TAGS
from capture_csi_multi import FIELDS, RECEIVERS, SOURCE
from persistent_presence_v4 import POLICY, PROTOCOL, validate_plan
from presence_v4_journal import audit_v4
from presence_v4_audio import LaptopNotifier, create_wav, PATTERNS
from presence_v4_pty import PtySession, SyntheticClock, SteppedFixtureClock


def fixture_ready(rx):
    return f'I (10) {TAGS[rx]}: {rx} READY channel=11 HT20 UART0=115200 raw CSI; source={SOURCE}\n'.encode()


def fixture_row(ident, timestamp):
    fields = dict.fromkeys(FIELDS, '0')
    fields.update(type='CSI_DATA', id=str(ident), mac=SOURCE, channel='11', rssi='-50',
                  sig_mode='1', len='256', local_timestamp=str(timestamp % 2**32),
                  data=json.dumps([1,2]*128, separators=(',', ':')))
    out = io.StringIO()
    csv.writer(out, lineterminator='\n').writerow([fields[k] for k in FIELDS])
    return out.getvalue().encode()


class FixtureSource:
    """Explicit synthetic 10 Hz input, no reading or calibration of physical data."""
    def __init__(self):
        self.next_ns = 0
        self.index = 0
        self.ready_sent = False

    def advance(self, session):
        if session.read_loop_stopped or session.machine.close_requested:
            return
        now = session.clock()
        if not self.ready_sent:
            for rx, endpoint in session.endpoints.items():
                endpoint.fixture_write(fixture_ready(rx))
            self.ready_sent = True
        if now >= self.next_ns:
            for endpoint in session.endpoints.values():
                endpoint.fixture_write(fixture_row(self.index, 100000+self.index*100000))
            self.index += 1
            self.next_ns = now+100_000_000


def run_demo(plan, output, speed=20, *, stepped=False):
    source = FixtureSource()
    with PtySession(output, plan, clock=SteppedFixtureClock() if stepped else SyntheticClock(speed)) as session:
        # A stepped clock has no relationship to wall speed or fsync latency.
        # This is a fixture hang guard, never evidence of a port close.
        guard_seconds = max(120, len(plan['slots'])*120) if stepped else (len(plan['slots'])*115+15)/speed+10
        real_deadline = time.monotonic()+guard_seconds
        while not session.read_loop_stopped:
            if stepped:
                session.clock.advance(50_000_000)
            source.advance(session)
            session.step()
            m = session.machine
            if not m.fatal and m.initial_available is not None:
                if m.windows:
                    w = m.windows[-1]
                    if w['end_signal'] is not None and m.signals[w['end_signal']]['ack_ns'] is not None and w['label']['status'] == 'pending':
                        session.command('declare', slot_id=w['id'], established=True, maintained=True,
                                        heard=True, notes='')
                if (not m.close_requested and len(m.windows) < len(plan['slots']) and
                        (not m.windows or m.windows[-1]['label']['status'] == 'declared')):
                    slot = plan['slots'][len(m.windows)]
                    session.command('request', slot_id=slot['id'], last=len(m.windows)+1 == len(plan['slots']))
            if time.monotonic() > real_deadline:
                session.command('interrupt')
            time.sleep(.0003)
        session.finalize()
    return audit_v4(output)


def rehearse_operator(plan, output, audio=False):
    """Local terminal rehearsal, synthetic CSI only; no automatic slot requests."""
    source = FixtureSource()
    with PtySession(output, plan) as session:
        if audio:
            session.notifier = LaptopNotifier(Path(output)/'audio')
        print('ENSAYO PTY SINTÉTICO. Ninguna UART física. Laptop/RX simulados dentro.', flush=True)
        print('Órdenes: slot ID [last]; declare ID yes; declare ID uncertain MOTIVO; close; abort.', flush=True)
        print('Una declaración yes afirma haber establecido y mantenido la condición y oído los avisos; no mide la transición.', flush=True)
        if not audio:
            print('SIN AUDIO: solo eventos simulados; no acredita operación audible.', flush=True)
        cursor = 0
        while True:
            source.advance(session); session.step()
            for event in session.machine.events[cursor:]:
                if event['kind'] in ('initial_available','gate_opened','window_started',
                    'window_ended_connection_open','both_ports_closed_confirmed','suspended','signal_result'):
                    print(json.dumps(event, ensure_ascii=False), flush=True)
            cursor = len(session.machine.events)
            if session.read_loop_stopped and all(w['label']['status'] != 'pending' or w['end_signal'] is None
                                                for w in session.machine.windows):
                break
            if select.select([sys.stdin], [], [], .005)[0]:
                line = sys.stdin.readline()
                if not line:
                    session.command('interrupt')
                    # EOF cannot confirm pending labels.
                    for w in session.machine.windows:
                        if w['label']['status']=='pending' and w['end_signal'] is not None:
                            session.command('declare',slot_id=w['id'],established=False,
                                            maintained=False,heard=False,notes='EOF, declaración ausente')
                    continue
                words = line.strip().split()
                try:
                    if len(words) in (2,3) and words[0]=='slot' and (len(words)==2 or words[2]=='last'):
                        session.command('request',slot_id=words[1],last=len(words)==3)
                    elif len(words)>=3 and words[0]=='declare' and words[2] in ('yes','uncertain'):
                        ok=words[2]=='yes'
                        session.command('declare',slot_id=words[1],established=ok,maintained=ok,
                                        heard=ok,notes=' '.join(words[3:]) if not ok else '')
                    elif words==['close']:
                        session.command('close_request')
                    elif words==['abort']:
                        session.command('interrupt')
                    else:
                        print('Orden rechazada; no se abre otra conexión o ventana.',flush=True)
                except (ValueError,StopIteration,IndexError) as exc:
                    print('Orden rechazada: '+str(exc),flush=True)
        session.finalize()
    return audit_v4(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, default=ROOT/'config/campana_presencia_v4.template.json')
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--demo-pty', action='store_true')
    modes.add_argument('--operador-pty', action='store_true')
    modes.add_argument('--export-cues', action='store_true')
    modes.add_argument('--audit', type=Path)
    parser.add_argument('--output-new', type=Path)
    parser.add_argument('--synthetic-speed', type=int, default=20)
    parser.add_argument('--stepped-fixture-clock', action='store_true', help='Demo PTY only: deterministic virtual clock, no real-time claim')
    parser.add_argument('--audio', action='store_true', help='Only for manual PTY rehearsal; uses the laptop via aplay')
    args = parser.parse_args()
    if args.audio and not args.operador_pty:
        parser.error('--audio requires --operador-pty')
    if args.stepped_fixture_clock and not args.demo_pty:
        parser.error('--stepped-fixture-clock requires --demo-pty')
    if args.export_cues:
        if args.output_new is None or not args.output_new.resolve().is_relative_to(ROOT/'results/local'):
            parser.error('Export requires a new directory in results/local')
        args.output_new.mkdir(parents=True,exist_ok=False)
        for kind in PATTERNS:
            create_wav(args.output_new/('PRUEBA-'+kind+'.wav'),kind)
        print('PRUEBA DE SONIDOS EXPORTADA; no se reproducen ni se confirma cierre de ningún puerto.')
        return
    if args.audit:
        report = audit_v4(args.audit)
        print(json.dumps(dict(integrity_ok=report['integrity_ok'], replay_ok=report['replay_ok'],
                             windows=len(report['state']['windows'])), indent=2)); return
    plan = validate_plan(json.loads(args.plan.read_text()))
    if not args.demo_pty and not args.operador_pty:
        print(json.dumps(dict(state='PREPARED_OFFLINE_NOT_EXECUTED', protocol=PROTOCOL,
              physical_UART_opened=False, physical_execution_enabled=False, slots=plan['slots'],
              policy=POLICY, pending='Physical transport promotion, mounting, initial READY, audibility and new authorization'), indent=2))
        return
    if args.output_new is None or not args.output_new.resolve().is_relative_to(ROOT/'results/local'):
        parser.error('PTY fixture requires --output-new in results/local; existing outputs are never overwritten')
    report = rehearse_operator(plan,args.output_new,args.audio) if args.operador_pty else run_demo(
        plan,args.output_new,args.synthetic_speed,stepped=args.stepped_fixture_clock)
    print(json.dumps(dict(evidence_type='synthetic_fixture', integrity_ok=report['integrity_ok'],
        replay_ok=report['replay_ok'], fatal=report['state']['fatal'],
        windows=len(report['state']['windows']), physical_UART_opened=False), indent=2))
    return int(report['state']['fatal'] is not None)


if __name__ == '__main__':
    raise SystemExit(main())
