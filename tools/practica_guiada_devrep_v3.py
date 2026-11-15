#!/usr/bin/env python3
"""Practice-only diagnostics, explicit stop messages and a fresh local log; no UART."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'tools')]
from devrep_keyboard_prompt import KeyboardInput, PromptConsole, SECOND
from devrep_operation_view import render as render_operation, sound_pattern
from devrep_practice_diagnostics_v3 import DiagnosticPractice, EXIT_CODES, practice_instruction, stop_message
from presence_v4_audio import LaptopNotifier


class PracticeLog:
    def __init__(self, parent):
        self.root = Path(tempfile.mkdtemp(prefix='practica-guiada-v3-', dir=parent))
        self.file = (self.root/'eventos-practica.jsonl').open('x')
        self.closed = False
        self.record('practice_log_started', recorded_at_utc=datetime.now(timezone.utc).isoformat())

    def record(self, kind, **data):
        payload=dict(data,kind=kind,practice_only=True)
        self.file.write(json.dumps(payload, ensure_ascii=False)+'\n')
        self.file.flush()

    def finish(self, outcome):
        if self.closed:
            return
        self.closed = True
        try:
            self.record('practice_finished',**outcome)
            with (self.root/'resultado-practica.json').open('x') as f:
                json.dump(dict(outcome, practice_only=True, physical_UART_opened=False,
                    physical_capture_executed=False, experimental_labels_created=False,
                    new_capture_prepared=False),f,ensure_ascii=False,indent=2)
                f.write('\n');f.flush();os.fsync(f.fileno())
        finally:
            self.file.flush();os.fsync(self.file.fileno());self.file.close()


def practice(keyboard, console, notifier, plan, *, rate=1, clock=time.monotonic_ns,
             pause=time.sleep, log=None):
    machine = DiagnosticPractice(plan)
    started = None
    cursor = 0
    sent = set()
    last_phase = None
    def record(kind, **data):
        if log is not None:log.record(kind, **data)
    def outcome():
        result = machine.termination
        if result is None:
            result = dict(code='completed' if machine.done else 'interface_error',
                detail='E y S reconocidas en el ejercicio.' if machine.done else 'La práctica salió sin completar E/S.',
                phase='S' if machine.done else 'interfaz',at_simulated_ns=machine.now)
        return dict(result, exit_code=EXIT_CODES[result['code']], rate=rate,
                    recognized_practice_slots=[w['id'] for w in machine.windows
                                              if w['label']['status']=='practice_acknowledged'],
                    unsubmitted_input=keyboard.text)
    console.message('[PRÁCTICA] EJERCICIO GUIADO CON SONIDOS. Reloj simulado, sin UART ni etiquetas experimentales.')
    console.message('[PRÁCTICA] Escribe practicar y pulsa Enter para empezar; abort o Ctrl-C cancelan el ejercicio.')
    if rate != 1:console.message(f'[PRÁCTICA] Reloj acelerado x{rate}; no cambia tiempos experimentales.')
    if log is not None:console.message('[PRÁCTICA] Registro de este ejercicio: '+str(log.root))
    try:
        while not machine.done and machine.termination is None:
            if started is not None:machine.tick(int((clock()-started)*rate))
            for ident, success in notifier.poll():
                record('practice_audio_result', signal_id=ident, software_playback_ok=success)
                machine.ack(ident, success)
            for event in machine.events[cursor:]:
                clean = dict(event)
                kind = clean.pop('kind')
                if kind == 'selected_port_closed_confirmed':kind = 'practice_simulated_finish_announced'
                record('practice_event', event_kind=kind, **clean)
                if kind == 'practice_input_recognized':
                    console.message('[PRÁCTICA] Entrada reconocida: '+event['slot_id']+'.')
                elif kind == 'practice_simulated_finish_announced':
                    console.message('[PRÁCTICA] Aviso final simulado; no se está cerrando ningún puerto.')
            cursor = len(machine.events)
            if machine.termination is not None:break
            for cue in machine.signals:
                if cue['id'] not in sent:
                    pattern = sound_pattern(cue['kind'])
                    notifier.start(dict(cue,kind=pattern))
                    record('practice_audio_requested',signal_id=cue['id'],waveform_pattern=pattern)
                    sent.add(cue['id'])
            pending = machine.pending()
            if started is None:
                status = '[PRÁCTICA] > escribe practicar y pulsa Enter'
            else:
                status = render_operation(machine,'practice',machine.now,keyboard.text)
            phase = (len(machine.windows), machine.windows[-1]['state'] if machine.windows else 'startup', bool(pending))
            if phase != last_phase:
                record('practice_phase',status=status,at_simulated_ns=machine.now)
                last_phase = phase
            console.update(status);console.flush()
            for words in keyboard.poll():
                record('practice_input',words=words,at_simulated_ns=machine.now)
                if started is None:
                    if words==['practicar']:started=clock()
                    elif words==['abort']:machine.stop('cancelled','Cancelaste antes de iniciar con abort.','abort')
                    else:machine.stop('invalid_input','Para iniciar escribe exactamente practicar y pulsa Enter.','startup_input')
                else:machine.command(words)
                if machine.termination is not None or machine.done:break
            if keyboard.eof and not machine.done:
                machine.stop('cancelled','Se cerró la entrada (EOF); la línea incompleta no se envió.','EOF')
            pause(.005)
    except KeyboardInterrupt:
        machine.stop('cancelled','Cancelaste con Ctrl-C.','KeyboardInterrupt')
    except (OSError, ValueError) as exc:
        machine.stop('interface_error',type(exc).__name__+': '+str(exc),'terminal_or_io')
    finally:
        try:
            if machine.termination:
                console.message(stop_message(machine.termination))
            elif machine.done:
                console.message('[PRÁCTICA] EJERCICIO COMPLETADO: E y S reconocidas. Sin adquisición física.')
            console.update('');console.flush()
        finally:
            try:notifier.finish()
            finally:
                if log is not None:log.finish(outcome())
    return outcome()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rapida',action='store_true',help='Reloj de práctica x10, sin cambiar criterios experimentales')
    args=parser.parse_args(argv)
    parent=ROOT/'results/local';parent.mkdir(parents=True,exist_ok=True)
    log=PracticeLog(parent)
    keyboard=console=notifier=None
    entered=False
    try:
        console=PromptConsole(sys.stdout.fileno())
        console.message('[PRÁCTICA] Registro: '+str(log.root));console.flush()
        if not shutil.which('aplay'):
            result=dict(code='audio_error',phase='antes de comenzar',detail='No se encontró aplay.',exit_code=5)
            console.message(stop_message(dict(result,expected='practicar')));console.update('');console.flush()
            log.finish(result);return 5
        keyboard=KeyboardInput(sys.stdin.fileno())
        notifier=LaptopNotifier(log.root/'audio-practica')
        plan=json.loads((ROOT/'config/devrep_r4_N01.review.json').read_text())
        entered=True
        return practice(keyboard,console,notifier,plan,rate=10 if args.rapida else 1,log=log)['exit_code']
    except (KeyboardInterrupt,OSError,ValueError) as exc:
        code='cancelled' if isinstance(exc,KeyboardInterrupt) else 'interface_error'
        result=dict(code=code,phase='antes de comenzar',detail='Ctrl-C' if code=='cancelled' else str(exc),exit_code=EXIT_CODES[code])
        if console is not None:
            console.message(stop_message(dict(result,expected='practicar')));console.update('');console.flush()
        log.finish(result);return result['exit_code']
    finally:
        try:
            if notifier is not None and not entered:notifier.finish()
        finally:
            try:
                if keyboard is not None:keyboard.close()
            finally:
                if console is not None:console.close()


if __name__=='__main__':raise SystemExit(main())
