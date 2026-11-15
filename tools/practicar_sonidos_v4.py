#!/usr/bin/env python3
"""Laptop-only sound examples. No serial, PTY, detector or capture imports."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from presence_v4_audio import PATTERNS, create_wav


def write_new(path, value):
    with Path(path).open('x') as f:
        json.dump(value,f,ensure_ascii=False,indent=2)
        f.write('\n');f.flush();os.fsync(f.fileno())


def practice(output, *, delay=None, gap=5, feedback=input, player=None, sleep=time.sleep):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    result=dict(kind='sound_examples_without_ESP',UART_opened=False,PTY_opened=False,
                no_real_close_confirmed=True,human_audibility_verified_automatically=False,
                human_confirmation='pending',playback=[],operator_answer=None)
    for kind in PATTERNS:
        create_wav(out/('PRUEBA-'+kind+'.wav'),kind)
    print('PRUEBA SIN ESP. Ningún sonido acredita cierre de puertos.',flush=True)
    print('Orden: 2 cortos=establecer; 1 corto=ventana/conexión abierta; 3 largos=ejemplo cierre; 8 rápidos=ejemplo fallo.',flush=True)
    if delay is None:
        write_new(out/'practice.json',result)
        print('Exportados; sin reproducción. Para salir del cuarto, use --play-after-delay 30.',flush=True)
        return result
    if type(delay) is not int or delay<10 or gap<3:
        raise ValueError('Practice requires >=10 seconds to exit and >=3 seconds between examples')
    executable=player or shutil.which('aplay')
    try:
        if not executable:
            raise RuntimeError('aplay unavailable; no playback or human confirmation inferred')
        print(f'Salga con los equipos sin mover. Comienza en {delay} s; vuelva después de los ocho tonos rápidos.',flush=True)
        sleep(delay)
        for kind in PATTERNS:
            played=subprocess.run([executable,'--quiet',str(out/('PRUEBA-'+kind+'.wav'))],
                                  timeout=10,capture_output=True,check=False)
            result['playback'].append(dict(example=kind,returncode=played.returncode,software_ok=played.returncode==0))
            if played.returncode:
                raise RuntimeError('Audio playback failed; human audibility stays pending')
            sleep(gap)
        answer=feedback('Desde FUERA: ¿distinguió los cuatro patrones? sí/no/incierto: ').strip().lower()
        result['operator_answer']=answer
        result['human_confirmation']='declared_distinguishable' if answer in ('sí','si') else 'declared_not_distinguishable' if answer=='no' else 'uncertain'
        result['observation_method']='human_declaration_after_practice; not an automated acoustic measurement'
        return result
    except BaseException as exc:
        result['error']=type(exc).__name__+': '+str(exc)
        raise
    finally:
        write_new(out/'practice.json',result)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-new',type=Path,required=True)
    parser.add_argument('--play-after-delay',type=int)
    args=parser.parse_args()
    if not args.output_new.resolve().is_relative_to(ROOT/'results/local'):
        parser.error('New output inside results/local required')
    practice(args.output_new,delay=args.play_after_delay)


if __name__=='__main__':main()
