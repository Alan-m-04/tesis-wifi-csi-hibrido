#!/usr/bin/env python3
"""Persist synthetic v3 evidence. Private PTY, no network or host UART devices."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-new', type=Path, required=True)
    parser.add_argument('--inside-sandbox', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    output = args.output_new.resolve()
    if not output.is_relative_to(ROOT / 'results/local'):
        parser.error('Choose a NEW internal results/local directory')
    if not args.inside_sandbox:
        output.mkdir(parents=True, exist_ok=False)
        command = ['bwrap', '--unshare-all', '--die-with-parent', '--ro-bind', '/usr', '/usr',
            '--ro-bind', '/lib', '/lib', '--ro-bind', '/lib64', '/lib64',
            '--ro-bind', '/etc/ld.so.cache', '/etc/ld.so.cache', '--ro-bind', '/etc/localtime', '/etc/localtime',
            '--ro-bind', str(ROOT), str(ROOT), '--bind', str(output), str(output), '--proc', '/proc',
            '--dev', '/dev', '--tmpfs', '/tmp', '--chdir', str(ROOT), '--setenv', 'HOME', '/tmp',
            '--setenv', 'PYTHONDONTWRITEBYTECODE', '1', str(ROOT / '.venv/bin/python'), '-B',
            str(Path(__file__).resolve()), '--output-new', str(output), '--inside-sandbox']
        raise SystemExit(subprocess.run(command).returncode)
    if list(output.iterdir()):
        raise ValueError('Output must be empty')
    sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests')]
    from pty_dual_v3_fixture import run_pty_v3
    cases = [('accepted-30s', 'completion', 30, 10_000_000_000, True, True),
             ('connection-rejected-window-conforming', 'startup_residue', .16, 700_000_000, False, True),
             ('late-error', 'late_error', .16, 700_000_000, False, False),
             ('timeout-10s-no-data', 'silent', .16, 10_000_000_000, False, False)]
    results = {}
    for name, scenario, duration, wait_ns, full_ok, window_ok in cases:
        folder = output / name
        evidence = run_pty_v3(ROOT, name=str(folder.relative_to(ROOT / 'results/local')),
                              scenario=scenario, duration=duration, wait_ns=wait_ns)
        quality = json.loads((folder / 'quality.json').read_text())
        if ('audit_error' in quality or quality['connection_full']['quality_ok'] != full_ok
                or quality['experimental_window']['quality_ok'] != window_ok
                or not evidence['all_ports_closed'] or evidence['writer_errors']):
            raise RuntimeError('Unexpected synthetic result: ' + json.dumps(quality))
        results[name] = {k: v for k, v in evidence.items() if k != 'run'}
        results[name].update(quality=quality, source_directory=str(folder))
    sources = sorted({p for folder in ('src', 'tools', 'tests', 'config') for p in (ROOT / folder).rglob('*')
                      if p.is_file() and p.suffix in ('.py', '.mjs', '.sh', '.json') and '__pycache__' not in p.parts})
    report = {'evidence_type': 'synthetic_fixture', 'physical_UART_opened': False,
              'authorization_created_or_consumed': False, 'runs': results,
              'source_hashes': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}}
    with (output / 'synthetic-results.json').open('x') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2); stream.write('\n')
    print(output / 'synthetic-results.json')


if __name__ == '__main__': main()
