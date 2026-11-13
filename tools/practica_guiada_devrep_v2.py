#!/usr/bin/env python3
"""Complete E/S instruction and sound practice: no UART, CSI or experimental labels."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from devrep_keyboard_prompt import KeyboardInput, PromptConsole, declaration_status, SECOND
from devrep_guided_prompt_v2 import Guidance
from presence_v4_audio import LaptopNotifier


class PracticeTimeline:
    """Simulation of cues using the unchanged policy; never generates CSI/quality results."""
    def __init__(self, plan):
        self.plan = dict(plan, slots=[dict(id='PRACTICA-GUIADA-'+c, condition=c) for c in ('E', 'S')])
        self.windows, self.signals, self.events = [], [], []
        self.initial_available = self.now = 0
        self.fatal = None
        self.done = False
        self.close_cue = None

    def emit(self, kind, **data):
        self.events.append(dict(kind=kind, now_ns=self.now, practice_only=True, **data))

    def signal(self, kind):
        ident = len(self.signals)
        self.signals.append(dict(id=ident, kind=kind, ack_ns=None, software_playback_ok=None))
        self.emit('signal_requested', signal_id=ident, signal_kind=kind)
        return ident

    def fail(self, reason):
        if not self.fatal:
            self.fatal = reason
            self.emit('suspended', reason=reason)
            self.signal('failure')

    def tick(self, now):
        self.now = now
        if self.fatal or self.done:
            return
        schedule, policy = self.plan['schedule'], self.plan['policy']
        for index, window in enumerate(self.windows):
            if (window['label']['status'] == 'pending' and
                    now > schedule['label_due_offsets_ns'][index]):
                self.fail('practice_missing_declaration_by_deadline')
                return
        index = len(self.windows)
        if index < 2 and now >= schedule['request_offsets_ns'][index]:
            if index and self.windows[0]['label']['status'] != 'practice_acknowledged':
                self.fail('practice_previous_declaration_missing')
                return
            slot = self.plan['slots'][index]
            self.windows.append(dict(**slot, requested_ns=now, state='delay',
                start_signal=None, end_signal=None, T0_ns=None, T1_ns=None,
                label=dict(status='pending')))
            self.emit('slot_requested', slot_id=slot['id'])
        if not self.windows:
            return
        window = self.windows[-1]
        if window['state'] == 'delay':
            if (window['start_signal'] is None and
                    now >= window['requested_ns'] + policy['start_cue_delay_ns']):
                window['start_signal'] = self.signal('establish_condition')
            cue = self.signals[window['start_signal']] if window['start_signal'] is not None else None
            if (cue and cue['software_playback_ok'] and
                    now >= max(window['requested_ns'] + policy['exit_delay_ns'],
                               cue['ack_ns'] + policy['establishment_ns'])):
                window.update(state='running', T0_ns=now, T1_ns=now+policy['window_ns'])
                self.emit('window_started', slot_id=window['id'])
        elif window['state'] == 'running' and now >= window['T1_ns']:
            window['state'] = 'complete'
            self.emit('window_ended_connection_open', slot_id=window['id'])
        if (window['state'] == 'complete' and window['end_signal'] is None and
                now >= window['T1_ns'] + policy['label_tail_ns']):
            window['end_signal'] = self.signal('window_finished_connection_open')

    def ack(self, ident, success):
        cue = self.signals[ident]
        cue.update(ack_ns=self.now, software_playback_ok=success)
        self.emit('signal_result', signal_id=ident, success=success)
        if not success:
            self.fail('practice_audio_failed')
        elif (cue['kind'] == 'window_finished_connection_open' and
                self.windows[-1]['condition'] == 'S' and not self.fatal):
            self.emit('selected_port_closed_confirmed', simulated=True)
            self.close_cue = self.signal('selected_port_closed_confirmed')

    def pending(self):
        if self.fatal or not self.windows:
            return None
        w = self.windows[-1]
        if w['label']['status'] != 'pending' or w['end_signal'] is None:
            return None
        if not self.signals[w['end_signal']]['software_playback_ok']:
            return None
        if w['condition'] == 'S' and (self.close_cue is None or
                not self.signals[self.close_cue]['software_playback_ok']):
            return None
        return w

    def command(self, words):
        w = self.pending()
        if w and words == ['declare', w['id'], 'yes']:
            w['label']['status'] = 'practice_acknowledged'
            self.emit('practice_input_recognized', slot_id=w['id'])
            self.done = w['condition'] == 'S'
        else:
            self.fail('practice_abort_uncertainty_or_invalid_input')


def practice(keyboard, console, notifier, plan, *, rate=1, clock=time.monotonic_ns, pause=time.sleep):
    machine, guide = PracticeTimeline(plan), Guidance()
    console.message('PRÁCTICA GUIADA CON SONIDOS, SIN UART. No hay CSI, READY, cierre real ni etiquetas experimentales.')
    console.message('Escribe practicar y pulsa Enter. Después sigue los letreros y sonidos; '
                    'sal físicamente para E y regresa al tono corto final. Abort detiene.')
    if rate != 1:
        console.message(f'PRÁCTICA ACELERADA x{rate}: reloj simulado; no son tiempos físicos experimentales.')
    started = None
    cursor = 0
    sent = set()
    try:
        while not machine.done:
            now = clock()
            if started is not None:
                machine.tick(int((now-started)*rate))
            for ident, success in notifier.poll():
                machine.ack(ident, success)
            for event in machine.events[cursor:]:
                guide.event(event, machine)
                if event['kind'] == 'practice_input_recognized':
                    console.message('Entrada de práctica reconocida: ' + event['slot_id'] + '; no es etiqueta experimental.')
                elif event['kind'] == 'selected_port_closed_confirmed':
                    console.message('CIERRE SOLO SIMULADO: aquí no hay UART abierto.')
                elif event['kind'] == 'suspended':
                    console.message('PRÁCTICA DETENIDA: ' + event['reason'])
            cursor = len(machine.events)
            for cue in machine.signals:
                if cue['id'] not in sent:
                    kind = 'both_ports_closed_confirmed' if cue['kind'] == 'selected_port_closed_confirmed' else cue['kind']
                    notifier.start(dict(cue, kind=kind))
                    sent.add(cue['id'])
            if started is None:
                console.update('PRÁCTICA > escribe practicar y pulsa Enter')
            else:
                pending = machine.pending()
                status = (declaration_status(pending['id'], machine.plan['schedule']['label_due_offsets_ns'][len(machine.windows)-1],
                          machine.now, keyboard.text) if pending else
                          f'PRÁCTICA | A+{machine.now//SECOND} s simulados | > {keyboard.text}')
                console.update(guide.render(status, machine))
            console.flush()
            if machine.fatal:
                # Wait for the failure WAV result without blocking the UI thread.
                failures = [cue for cue in machine.signals if cue['kind'] == 'failure']
                if failures and failures[-1]['ack_ns'] is not None:
                    return 1
                pause(.005)
                continue
            for words in keyboard.poll():
                if started is None:
                    if words != ['practicar']:
                        return 1
                    started = clock()
                else:
                    machine.command(words)
            if keyboard.eof:
                machine.fail('practice_EOF')
            pause(.005)
        for event in machine.events[cursor:]:
            if event['kind'] == 'practice_input_recognized':
                console.message('Entrada de práctica reconocida: ' + event['slot_id'] + '; no es etiqueta experimental.')
        console.message('PRÁCTICA TERMINADA: E y S reconocidas, sin datos ni etiquetas experimentales.')
        console.update(''); console.flush()
        return 0
    finally:
        notifier.finish()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rapida', action='store_true', help='Reloj simulado x10, solo práctica')
    args = parser.parse_args(argv)
    if not shutil.which('aplay'):
        parser.error('Falta aplay; no se simulará audibilidad')
    plan = json.loads((ROOT/'config/devrep_r4_N01.review.json').read_text())
    keyboard = console = None
    try:
        with tempfile.TemporaryDirectory(prefix='practica-guiada-devrep-') as directory:
            # Real default audio only. Tests can inject a notifier; no silent/null CLI mode.
            notifier = LaptopNotifier(Path(directory)/'audio')
            entered_practice = False
            try:
                keyboard = KeyboardInput(sys.stdin.fileno())
                console = PromptConsole(sys.stdout.fileno())
                entered_practice = True
                return practice(keyboard, console, notifier, plan, rate=10 if args.rapida else 1)
            finally:
                if not entered_practice:
                    notifier.finish()
    except (KeyboardInterrupt, OSError, ValueError):
        return 1
    finally:
        try:
            if console is not None:
                console.close()
        finally:
            if keyboard is not None:
                keyboard.close()


if __name__ == '__main__':
    raise SystemExit(main())
