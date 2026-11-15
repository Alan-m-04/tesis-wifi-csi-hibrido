#!/usr/bin/env python3
"""Review one prospective E/S plan and exercise its existing UI with simulated states."""
import argparse
import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tools')]

from csi_live_observer import guard, small_json
from devrep_operation_view import LEAVE, PROMPT_TEXT, RETURN, SIT, STAY_OUT, render, sound_pattern
from practica_guiada_devrep_v2 import PracticeTimeline
from preflight_devrep_r4 import validate as validate_reference
from presence_v4_audio import PATTERNS
from presence_v4_journal import digest

CONNECTION_ID = 'RX02-DEVREP-R5-N01'
PLAN = ROOT / 'config/devrep_r5_N01.propuesta.review.json'
REFERENCE = ROOT / 'config/devrep_r4_N01.review.json'
PRESENTATION = dict(adapter='src/devrep_operator_interface.py', renderer='src/devrep_operation_view.py',
                    practice='tools/practica_guiada_devrep_v3.py')
SECOND = 1_000_000_000


def review(path=PLAN):
    proposal = small_json(path, 131072)
    reference = small_json(REFERENCE, 131072)
    validate_reference(reference)
    if (proposal.get('schema') != 'rx02-guided-es-review-1' or
            proposal.get('state') != 'REVIEW_ONLY_NOT_AUTHORIZED' or
            proposal.get('reference_profile') != str(REFERENCE.relative_to(ROOT)) or
            proposal.get('reference_profile_sha256') != digest(REFERENCE) or
            proposal.get('presentation') != PRESENTATION or proposal.get('physical_entrypoint_enabled') is not False):
        raise ValueError('Revisión E/S, perfil o presentación incompatible')
    expected = copy.deepcopy(reference)
    expected.update(connection_id=CONNECTION_ID, partition_group=CONNECTION_ID, series_id='RX02-DEVREP-R5',
                    slots=[dict(id=CONNECTION_ID + '-' + condition, condition=condition) for condition in ('E', 'S')],
                    output_new='results/local/devrep-rx02-r5-N01',
                    review_state='R5_PREPARED_GUIDED_UI_NOT_AUTHORIZED',
                    operator_interface_revision='devrep-shared-operation-view-1')
    expected['environment'].update(
        occupancy='Declaración actual: el operador está haciendo tarea. PENDIENTE confirmar las condiciones del intento E/S.',
        movement='Declaración actual: el operador se moverá por el cuarto. PENDIENTE establecer E y S cuando se soliciten en un intento futuro autorizado.')
    if proposal.get('plan') != expected:
        raise ValueError('Identidad, orden, agenda, criterios o permisos de la propuesta cambiaron')
    paths = ('results/RX02_DIAG_VISOR_240S_R1.md',
             'results/local/consolidacion-rx02-visor-240s-r1/evidencia.json',
             'results/local/diagnostico-rx02-visor-240s-r1/manifest.json',
             'results/local/vista-rx02-visor-240s-r1/audit-result.json')
    if proposal.get('prior_acquisition_visualization_evidence') != {name: digest(ROOT / name) for name in paths}:
        raise ValueError('Cambió la evidencia antecedente del visor auditado')
    evidence = small_json(ROOT / paths[1])
    audit = small_json(ROOT / paths[3])
    if not (audit['integrity_ok'] and audit['replay_ok'] and audit['close_verified'] and
            audit['diagnostic_ok'] and audit['quality_ok'] is False):
        raise ValueError('El antecedente debe conservar su auditoría y calidad originales')
    if (ROOT / expected['output_new']).exists():
        raise ValueError('La salida propuesta ya existe')
    return dict(state='REVIEW_ONLY_NOT_AUTHORIZED', connection_id=CONNECTION_ID,
                partition_group=CONNECTION_ID, output_new=expected['output_new'],
                plan_sha256=digest(path), plan=expected, presentation=PRESENTATION,
                acquisition_visualization_evidence=dict(attempt_id=evidence['attempt_id'],
                    rows=evidence['cadence']['complete_rows'], observed_rows=evidence['observer']['rows_seen'],
                    quality_ok=False, diagnostic_ok=True),
                declarations=[f'declare {slot["id"]} yes' for slot in expected['slots']],
                sources={name: digest(ROOT / name) for name in (
                    'tools/revisar_devrep_r5_n01.py', 'src/devrep_operation_view.py',
                    'src/devrep_operator_interface.py', 'src/devrep_keyboard_prompt.py',
                    'src/rx02_devrep/coordinator.py', 'src/rx02_checkpoint_journal.py',
                    'src/persistent_presence_v4.py', 'src/presence_v4_exploratory.py')},
                physical_UART_opened=False, capture_started=False, authorization_granted=False,
                physical_entrypoint_enabled=False,
                next_stage='Revisar el plan y, cuando el operador esté disponible, las condiciones y la entrada física con el adaptador vigente.')


def check_guidance(plan):
    # Reuse the practice timeline for state projection only. Restore the proposed
    # slot IDs before any event. All inputs, clock advances and closes are simulated.
    machine = PracticeTimeline(plan)
    machine.plan = copy.deepcopy(plan)
    machine.closed = {}
    transcript = []

    def snapshot(name):
        text = render(machine, 'physical', machine.now)
        transcript.append(dict(stage=name, simulated_ns=machine.now, rendered_text=text))
        return text

    machine.tick(30 * SECOND)
    assert LEAVE in snapshot('solicitud_E')
    machine.tick(60 * SECOND)
    assert STAY_OUT in snapshot('aviso_establecer_E')
    machine.ack(0, True)
    machine.tick(90 * SECOND)
    machine.tick(120 * SECOND)
    machine.tick(130 * SECOND)
    assert RETURN not in snapshot('E_antes_de_confirmar_tono_final')
    machine.ack(1, True)
    text = snapshot('regresar_y_declarar_E')
    assert RETURN in text and PROMPT_TEXT in text and f'declare {CONNECTION_ID}-E yes' in text
    machine.command(['declare', CONNECTION_ID + '-E', 'yes'])
    assert SIT in snapshot('E_reconocida_esperar_S')
    machine.tick(240 * SECOND)
    assert SIT in snapshot('solicitud_S')
    machine.tick(270 * SECOND)
    machine.ack(2, True)
    machine.tick(300 * SECOND)
    machine.tick(330 * SECOND)
    machine.tick(340 * SECOND)
    machine.ack(3, True)
    assert PROMPT_TEXT not in snapshot('S_sin_prueba_de_cierre')
    machine.closed = {'RX-02': dict(confirmed=True, reader_stopped=True)}
    assert PROMPT_TEXT not in snapshot('S_sin_reproduccion_final')
    machine.ack(4, True)
    text = snapshot('declarar_S_tras_cierre_simulado')
    assert PROMPT_TEXT in text and f'declare {CONNECTION_ID}-S yes' in text
    machine.command(['declare', CONNECTION_ID + '-S', 'yes'])
    assert machine.done and machine.fatal is None
    patterns = [sound_pattern(signal['kind']) for signal in machine.signals]
    assert patterns == ['establish_condition', 'window_finished_connection_open',
                        'establish_condition', 'window_finished_connection_open', 'both_ports_closed_confirmed']
    assert machine.plan == plan
    return dict(simulation_only=True, physical_UART_opened=False, capture_started=False,
                experimental_labels_created=False, sequence_verified=True, transcript=transcript,
                waveform_patterns=[dict(name=name, specification=PATTERNS[name]) for name in patterns],
                policy_unchanged=True, schedule_unchanged=True,
                scope='Proyección de estados en el renderizador vigente. Audio y cierres simulados.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-guidance', action='store_true', help='Proyectar la secuencia en memoria, con entradas y sonidos simulados')
    args = parser.parse_args(argv)
    sys.addaudithook(guard)
    result = review()
    if args.check_guidance:
        result['guidance_check'] = check_guidance(result['plan'])
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
