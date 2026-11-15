"""Explicit condition guidance, layered over the frozen nonblocking keyboard UI.

No schedule, authorization, quality reducer or transport is modified here.
R4 keeps its original interface and rejection; this revision is opt-in only.
"""
import json
import sys
from devrep_keyboard_prompt import PromptConsole, PROMPT_TEXT, operate as keyboard_operate

LEAVE = 'SAL DEL CUARTO AHORA Y CIERRA LA PUERTA'
STAY_OUT = 'PERMANECE FUERA'
RETURN = 'REGRESA Y DECLARA'
SIT = 'SIÉNTATE Y PERMANECE QUIETO'


class Guidance:
    def __init__(self):
        self.condition = None
        self.phase = 'waiting'
        self.slot_id = None
        self.close_sound_finished = False

    def event(self, event, machine):
        kind = event['kind']
        if kind in ('suspended', 'devrep_schedule_failed'):
            self.phase = 'failed'
            return
        if self.phase == 'failed' or machine.fatal:
            return
        if kind == 'slot_requested':
            slot = next(slot for slot in machine.plan['slots'] if slot['id'] == event['slot_id'])
            self.slot_id, self.condition = slot['id'], slot['condition']
            self.phase = 'leave' if self.condition == 'E' else 'sit'
        elif kind == 'signal_requested' and event['signal_kind'] == 'establish_condition':
            if self.condition == 'E':
                self.phase = 'stay_out'
        elif kind == 'window_started' and self.condition == 'E':
            self.phase = 'stay_out'
        elif kind == 'signal_result' and event['success']:
            cue = machine.signals[event['signal_id']]
            if cue['kind'] == 'establish_condition' and self.condition == 'E':
                self.phase = 'stay_out'
            elif cue['kind'] == 'window_finished_connection_open' and self.condition == 'E':
                # T1/window_ended alone is too early: the final short sound is T1+10 s.
                self.phase = 'return'
            elif cue['kind'] == 'selected_port_closed_confirmed' and self.condition == 'S':
                self.close_sound_finished = True

    def current(self, machine):
        if machine.fatal or self.phase == 'failed':
            return 'INTENTO DETENIDO. Conserva la evidencia; no relances el comando.'
        if self.phase == 'leave':
            window = next(w for w in machine.windows if w['id'] == self.slot_id)
            if window['start_signal'] is not None:
                self.phase = 'stay_out'
                return STAY_OUT + '\nEspera el tono corto final; todavía no regreses.'
            return LEAVE + '\nDebes estar fuera antes de los dos tonos cortos.'
        if self.phase == 'stay_out':
            return STAY_OUT + '\nEspera el tono corto final; todavía no regreses.'
        if self.phase == 'return':
            window = next(w for w in machine.windows if w['id'] == self.slot_id)
            if window['label']['status'] in ('declared', 'practice_acknowledged'):
                return SIT + '\nEspera la solicitud S en la misma conexión.'
            return RETURN + '\nVuelve a la terminal, escribe la declaración E y pulsa Enter.'
        if self.phase == 'sit':
            if self.close_sound_finished:
                return 'CIERRE CONFIRMADO: declara S en la terminal y pulsa Enter.'
            return SIT + '\nMantén la condición hasta los tres tonos largos de cierre confirmado.'
        return 'Espera la solicitud de condición; las solicitudes son automáticas.'

    def render(self, status, machine):
        if self.condition == 'S' and not self.close_sound_finished and PROMPT_TEXT in status:
            # Do not invite an early S declaration while the three long tones are pending.
            status = 'Espera el aviso de cierre; el plazo original sigue corriendo.'
        return self.current(machine) + '\n' + status


class GuidedConsole:
    """Event-driven instructions stay visible during the whole applicable phase."""
    def __init__(self, console, machine):
        self.console, self.machine = console, machine
        self.guidance = Guidance()

    def message(self, text):
        try:
            event = json.loads(text)
        except (TypeError, ValueError):
            event = None
        if isinstance(event, dict) and 'kind' in event:
            self.guidance.event(event, self.machine)
        self.console.message(text)

    def update(self, status):
        self.console.update(self.guidance.render(status, self.machine))

    def flush(self):
        self.console.flush()


def operate(session, commands=None, console=None, **kwargs):
    """Future opt-in entry: original coordinator and deadlines remain authoritative."""
    owned = console is None
    if owned:
        console = PromptConsole(sys.stdout.fileno())
    try:
        return keyboard_operate(session, commands=commands,
            console=GuidedConsole(console, session.machine), **kwargs)
    finally:
        if owned:
            console.close()
