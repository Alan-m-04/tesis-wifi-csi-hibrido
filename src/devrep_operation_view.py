"""Shared presentation only: identical actions/prompts/sound mapping in both domains.

The native coordinator remains the sole owner of physical timing and acceptance.
Practice may simulate a finish; physical closure always requires recorded proof.
"""
from devrep_keyboard_prompt import SECOND

LEAVE='SAL DEL CUARTO AHORA Y CIERRA LA PUERTA'
STAY_OUT='PERMANECE FUERA'
RETURN='REGRESA Y ESCRIBE LA DECLARACIÓN'
SIT='SIÉNTATE Y PERMANECE QUIETO'
PROMPT_TEXT='ESCRIBE LA DECLARACIÓN Y PULSA ENTER'


def sound_pattern(kind):
    return 'both_ports_closed_confirmed' if kind=='selected_port_closed_confirmed' else kind


def played(machine,ident):
    return ident is not None and machine.signals[ident]['software_playback_ok'] is True


def phase(machine,domain):
    if domain not in ('practice','physical'):raise ValueError('Explicit presentation domain required')
    if machine.fatal:return 'stopped'
    if not machine.windows:return 'waiting'
    w=machine.windows[-1]
    close_played=any(s['kind'] in ('selected_port_closed_confirmed','both_ports_closed_confirmed') and
                     s['software_playback_ok'] is True for s in machine.signals)
    closed=getattr(machine,'closed',{})
    physical_proof=bool(closed) and all(c.get('confirmed') is True and c.get('reader_stopped') is True for c in closed.values())
    if w['label']['status'] in ('declared','practice_acknowledged'):
        if w['condition']=='E':return 'sit_ready'
        return 'finished' if close_played and (domain=='practice' or physical_proof) else 'sit'
    if w['condition']=='E':
        if played(machine,w['end_signal']):return 'declare_E'
        return 'leave' if w['start_signal'] is None else 'stay_out'
    if close_played and (domain=='practice' or physical_proof):return 'declare_S'
    return 'sit'


def declaration_prompt(slot_id,deadline_ns,now_ns,typed=''):
    remaining=max(0,deadline_ns-now_ns)//SECOND
    return (f'{PROMPT_TEXT}\nTiempo disponible para responder: {remaining} s\n'
            f'Orden completa si se cumplió: declare {slot_id} yes\n'
            f'Orden completa ante duda: declare {slot_id} uncertain MOTIVO\n> {typed[-512:]}')


def instruction(machine,domain):
    p=phase(machine,domain)
    text=dict(waiting='Espera la solicitud de condición; las solicitudes son automáticas.',
              leave=LEAVE,stay_out=STAY_OUT,declare_E=RETURN,sit_ready=SIT,sit=SIT)
    if p in text:return text[p]
    if p=='stopped':return 'EJERCICIO DETENIDO' if domain=='practice' else 'ADQUISICIÓN DETENIDA. Conserva la evidencia y no relances.'
    if domain=='practice':return 'FIN SIMULADO DEL EJERCICIO. No hay un puerto físico que cerrar.'
    return 'CIERRE FÍSICO COMPROBADO: lectura detenida y descriptor liberado.'


def render(machine,domain,now_ns,typed=''):
    prefix='[PRÁCTICA]' if domain=='practice' else '[ADQUISICIÓN FÍSICA]'
    p=phase(machine,domain)
    lines=[prefix+' '+instruction(machine,domain)]
    if p=='leave':lines.append('Debes estar fuera antes de los dos tonos cortos.')
    if p=='stay_out':lines.append('Espera el tono corto final; todavía no regreses.')
    if p=='sit':lines.append('Mantén la condición hasta los tres tonos largos del aviso final.')
    if p=='sit_ready':lines.append('Espera la solicitud S; mantén la postura indicada.')
    if p in ('declare_E','declare_S'):
        w=machine.windows[-1];index=len(machine.windows)-1
        deadline=machine.initial_available+machine.plan['schedule']['label_due_offsets_ns'][index]
        lines.append(declaration_prompt(w['id'],deadline,now_ns,typed))
    elif typed:lines.append('> '+typed[-512:])
    return '\n'.join(lines)
