#!/usr/bin/env python3
"""Keyboard-only practice. No UART, audio, CSI, experimental labels or permission."""
import argparse
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from devrep_keyboard_prompt import KeyboardInput, PromptConsole, declaration_status, SECOND


def practice(commands, console, *, clock=time.monotonic_ns, pause=time.sleep, seconds=60):
    console.message('PRÁCTICA DE TECLADO SIN UART. Sin captura, audio ni etiquetas experimentales.')
    console.message(f'{seconds} s por entrada de práctica; no son los plazos experimentales. '
                    'No hace falta salir del cuarto. Retroceso corrige; Ctrl-U borra; abort detiene.')
    for condition in ('E', 'S'):
        slot = 'PRACTICA-TECLADO-' + condition
        deadline = clock() + seconds * SECOND
        while True:
            now = clock()
            if now > deadline:
                console.message('PRÁCTICA DETENIDA: plazo agotado; entrada sin confirmar.')
                console.update(''); console.flush()
                return 1
            console.update(declaration_status(slot, deadline, now, commands.text))
            console.flush()
            words_list = commands.poll()
            if commands.eof:
                console.message('PRÁCTICA DETENIDA: EOF, sin declaración implícita.')
                console.update(''); console.flush()
                return 1
            accepted = False
            for words in words_list:
                # A second pasted command is never saved for a future prompt.
                if accepted or words != ['declare', slot, 'yes'] or clock() > deadline:
                    console.message('PRÁCTICA DETENIDA: abort, incertidumbre, entrada tardía o formato no válido.')
                    console.update(''); console.flush()
                    return 1
                console.message(f'Entrada {condition} reconocida en práctica; no es etiqueta experimental.')
                accepted = True
            if accepted:
                break
            pause(.005)
    console.message('PRÁCTICA TERMINADA: ambas entradas reconocidas. Sin UART ni datos adquiridos.')
    console.update(''); console.flush()
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds-per-prompt', type=int, default=60)
    args = parser.parse_args(argv)
    if not 2 <= args.seconds_per_prompt <= 120:
        parser.error('Use de 2 a 120 segundos por entrada de práctica')
    keyboard = console = None
    try:
        keyboard = KeyboardInput(sys.stdin.fileno())
        console = PromptConsole(sys.stdout.fileno())
        return practice(keyboard, console, seconds=args.seconds_per_prompt)
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
