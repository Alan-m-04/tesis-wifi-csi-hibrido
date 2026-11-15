"""Practice-only stop classification and wording; never used by physical acquisition."""
from practica_guiada_devrep_v2 import PracticeTimeline
from devrep_operation_view import render as render_operation

EXIT_CODES = dict(completed=0, cancelled=1, invalid_input=2, uncertain=3,
                  expired=4, audio_error=5, interface_error=6)


class DiagnosticPractice(PracticeTimeline):
    def __init__(self, plan):
        super().__init__(plan)
        self.termination = None

    def expected(self):
        if not self.windows:
            return 'practicar'
        slot = self.windows[-1]['id']
        return f'declare {slot} yes | declare {slot} uncertain MOTIVO | abort'

    def stop(self, code, detail='', origin=None):
        if self.termination is not None or self.done:
            return
        phase = self.windows[-1]['condition'] if self.windows else 'antes de comenzar'
        self.termination = dict(code=code, detail=detail, origin=origin,
            phase=phase, at_simulated_ns=self.now, expected=self.expected())
        self.fatal = 'practice_' + code
        self.emit('practice_stopped', **self.termination)
        # Input/practice stops do not emit the eight-tone physical failure alarm.

    def fail(self, reason):
        if reason in ('practice_missing_declaration_by_deadline', 'practice_previous_declaration_missing'):
            index = len(self.windows)-1
            deadline = self.plan['schedule']['label_due_offsets_ns'][index]
            self.stop('expired', f'Se agotó el plazo simulado A+{deadline//1_000_000_000} s; '
                      'no se recibió una declaración válida de práctica.', reason)
        elif reason == 'practice_audio_failed':
            self.stop('audio_error', 'No se completó la reproducción del aviso de práctica.', reason)
        else:
            self.stop('interface_error', str(reason), reason)

    def command(self, words):
        if self.termination or self.done:
            return
        if words == ['abort']:
            self.stop('cancelled', 'Cancelaste con abort.', 'abort')
            return
        slot = self.windows[-1]['id'] if self.windows else None
        if len(words)>=2 and words[0]=='declare' and words[1].startswith('RX02-'):
            self.stop('invalid_input','Ese ID pertenece a una adquisición física. '
                      'Usa el ID PRACTICA-GUIADA que muestra este ejercicio.','physical_ID_in_practice')
            return
        if len(words) >= 3 and words[0] == 'declare' and words[1] == slot:
            if words[2] == 'uncertain':
                if len(words) < 4:
                    self.stop('invalid_input', 'Falta el motivo después de uncertain.', 'missing_uncertainty_reason')
                else:
                    self.stop('uncertain', ' '.join(words[3:]), 'operator_uncertain')
                return
            if words[2] == 'yes' and len(words) == 3:
                if self.pending() is None:
                    self.stop('invalid_input', 'La declaración aún no está habilitada; espera su aviso y prompt.', 'premature_declaration')
                else:
                    super().command(words)
                return
        received = ' '.join(words) if words else '(línea vacía)'
        self.stop('invalid_input', 'Entrada recibida: ' + repr(received) + '. Revisa formato e ID.', 'format_or_slot')


def stop_message(result):
    code = result['code']
    labels = dict(cancelled='PRÁCTICA CANCELADA', invalid_input='ENTRADA INVÁLIDA EN PRÁCTICA',
        uncertain='PRÁCTICA DETENIDA POR INCERTIDUMBRE', expired='PLAZO DE PRÁCTICA VENCIDO',
        audio_error='FALLO DE AUDIO EN PRÁCTICA', interface_error='ERROR DE INTERFAZ DE PRÁCTICA')
    text = f"[PRÁCTICA] {labels[code]} — {result['phase']}: {result['detail']}"
    if code == 'invalid_input':
        text += '\n[PRÁCTICA] Se esperaba: ' + result['expected']
    if code == 'uncertain':
        text += '\n[PRÁCTICA] No se dará la condición por cumplida.'
    return text + '\n[PRÁCTICA] El ejercicio terminó; no se ha iniciado ni rechazado una adquisición física.'


def practice_instruction(machine):
    """No physical failure/connection/closure claims in practice notices."""
    if machine.termination:
        return stop_message(machine.termination)
    return render_operation(machine,'practice',machine.now)
