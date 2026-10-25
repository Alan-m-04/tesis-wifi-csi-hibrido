#!/usr/bin/env python3
"""Generate explicit synthetic PTY evidence in a private /dev, never host UART.

Creates one 30-second nominal PTY fixture and a short rejected startup fixture.
This is not a physical capture or an authorization workflow.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-new', required=True, type=Path)
    parser.add_argument('--inside-sandbox', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    output = args.output_new.resolve()
    if not output.is_relative_to(ROOT / 'results/local'):
        parser.error('Choose a new results/local directory')
    if not args.inside_sandbox:
        output.mkdir(parents=True, exist_ok=False)
        command = ['bwrap', '--unshare-all', '--die-with-parent', '--ro-bind', '/usr', '/usr',
                   '--ro-bind', '/lib', '/lib', '--ro-bind', '/lib64', '/lib64',
                   '--ro-bind', '/etc/ld.so.cache', '/etc/ld.so.cache',
                   '--ro-bind', '/etc/localtime', '/etc/localtime',
                   '--ro-bind', str(ROOT), str(ROOT), '--bind', str(output), str(output),
                   '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp', '--chdir', str(ROOT),
                   '--setenv', 'HOME', '/tmp', str(ROOT / '.venv/bin/python'), '-B',
                   str(Path(__file__).resolve()), '--output-new', str(output), '--inside-sandbox']
        raise SystemExit(subprocess.run(command).returncode)
    if list(output.iterdir()):
        raise ValueError('Synthetic output must be empty')
    sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests')]
    from pty_dual_v2_fixture import run_pty_dual
    results = {}
    for name, scenario, duration in [('accepted', 'complete', 30), ('rejected', 'startup_residue', .12)]:
        folder = output / name
        evidence = run_pty_dual(ROOT, str(folder.relative_to(ROOT / 'results/local')),
                               scenario=scenario, duration=duration)
        quality = json.loads((folder / 'quality.json').read_text())
        results[name] = {key: value for key, value in evidence.items() if key != 'run'}
        results[name]['quality'] = quality
        if evidence['returncode'] != (0 if name == 'accepted' else 1):
            raise RuntimeError('Unexpected synthetic result: ' + json.dumps(results[name]))
    with (output / 'synthetic-results.json').open('x') as stream:
        json.dump({'evidence_type': 'synthetic_fixture', 'physical_UART_opened': False,
                   'authorization_created_or_consumed': False, 'runs': results}, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(output / 'synthetic-results.json')


if __name__ == '__main__':
    main()
