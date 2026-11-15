#!/usr/bin/env python3
"""Práctica R5 con la interfaz vigente y declaración humana; sin UART ni captura."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tools')]
from devrep_keyboard_prompt import KeyboardInput, PromptConsole
from presence_v4_audio import LaptopNotifier
from presence_v4_journal import digest, write_new
from practica_guiada_devrep_v3 import PracticeLog, practice
import preflight_devrep_r5 as prep


def practice_sources():
    names = ('tools/practica_devrep_r5_n01.py', 'tools/practica_guiada_devrep_v3.py',
             'tools/practica_guiada_devrep_v2.py', 'src/devrep_practice_diagnostics_v3.py',
             'src/devrep_guided_prompt_v2.py', 'src/devrep_keyboard_prompt.py',
             'src/devrep_operation_view.py', 'src/devrep_operator_interface.py',
             'src/presence_v4_audio.py')
    return {name: digest(ROOT / name) for name in names}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rapida', action='store_true', help='Reloj de práctica x10')
    args = parser.parse_args(argv)
    target = ROOT / prep.KEYBOARD_PRACTICE
    if os.path.lexists(target):
        raise ValueError('Práctica confirmada existente; conservarla y revisar sin sobrescribir')
    if not shutil.which('aplay'):
        raise ValueError('No se encontró aplay; falta practicar los avisos audibles')
    # Solo práctica: nunca se consulta USB, se construye una sesión o se crea un grant.
    plan = prep.template()
    sources = practice_sources()
    (ROOT / prep.PREPARATION).mkdir(parents=True, exist_ok=True)
    log = PracticeLog(ROOT / 'results/local')
    keyboard = console = notifier = None
    try:
        keyboard = KeyboardInput(sys.stdin.fileno())
        console = PromptConsole(sys.stdout.fileno())
        notifier = LaptopNotifier(log.root / 'audio-practica')
        outcome = practice(keyboard, console, notifier, plan,
                           rate=10 if args.rapida else 1, log=log)
    finally:
        try:
            if notifier is not None: notifier.finish()
        finally:
            try:
                if console is not None: console.close()
            finally:
                if keyboard is not None: keyboard.close()
        if not log.closed:
            log.finish(dict(code='interface_error', exit_code=6))
    if outcome['code'] != 'completed':
        return outcome['exit_code']
    response = input('Solo si completaste E/S y distinguiste todos los avisos desde fuera '
                     'con salida y volumen actuales, escribe CONFIRMO: ')
    if response.strip() != 'CONFIRMO':
        print('Práctica conservada sin confirmar audibilidad; no autoriza captura.')
        return 1
    if practice_sources() != sources:
        raise ValueError('Las fuentes cambiaron durante la práctica; revisar')
    files = {str((log.root / name).relative_to(ROOT)): digest(log.root / name)
             for name in ('eventos-practica.jsonl', 'resultado-practica.json')}
    write_new(target, dict(connection_id=prep.CONNECTION_ID, practice_only=True,
        operator_reported_completed=True, operator_reported_audible_outside=True,
        interface_sha256=digest(ROOT / 'src/devrep_keyboard_prompt.py'), sources=sources,
        outcome=outcome, log_files=files, response=response,
        evidence_type='practice_and_human_audibility_declaration_not_physical_validation',
        physical_UART_opened=False, capture_executed=False, authorization_granted=False))
    print('Práctica declarada para R5-N01: ' + str(target.relative_to(ROOT)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
