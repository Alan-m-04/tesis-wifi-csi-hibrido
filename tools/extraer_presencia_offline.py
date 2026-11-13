#!/usr/bin/env python3
"""Extract/trace only the two existing physical v3 windows; no model options.

This CLI has no calibration, inference or acquisition path. Original audits and
source hashes are reused; output is new local-only per-row feature artifacts.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'src'))
from comparar_fisicas_v3 import SESSIONS, source_session
from presence_offline import extract_window
from ruview_presence_port import CONTRACT, RUVIEW_COMMIT


def ref(path):
    return {'path': str(path.relative_to(ROOT)), 'bytes': path.stat().st_size,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def build_features():
    report = {'schema': 'tesis-physical-presence-features-only-v1', 'contract': CONTRACT,
        'implementation_base_commit': '796d534a9d04bb040f9868f77030980529ec02e7',
        'ruview_commit': RUVIEW_COMMIT, 'operation': 'physical_feature_extraction_and_traceability_only',
        'new_UART_opened': False, 'new_physical_capture': False, 'calibration_executed': False,
        'thresholds_fit': False, 'inference_executed': False, 'sessions': {},
        'row_features_distributed_in_git': False,
        'limits': ['Features are not presence decisions. Both historical full connections/global rejections remain.',
                   'Physical movement onset and continuity remain uncertain; no per-row activity truth inferred.',
                   'No empty calibration, physical fitting, classifier scores, RX fusion or HT-LTF input.'],
        'implementation': [ref(ROOT / p) for p in ('src/presence_offline.py', 'src/ruview_presence_port.py',
            'tools/extraer_presencia_offline.py', 'vendor/ruview/presence/PROVENANCE.json')]}
    row_files = {}
    for key in SESSIONS:
        original = source_session(key)
        session = {'source_run_id': original['session']['session_id'],
            'acquisition_git_commit': original['provenance']['git_commit'],
            'environment_declared': original['plan']['environment'],
            'connection_full': original['audit']['connection_full'],
            'global_quality_ok': original['audit']['quality_ok'],
            'experimental_window_status': original['audit']['experimental_window']['status'],
            'sources': original['sources'], 'receivers': {}}
        if key == 'libre':
            session['usage_restrictions'] = original['plan']['usage_restrictions']
            session['operator_transition'] = json.loads((original['control'] / 'transicion-declarada.json').read_text())
        for receiver in ('RX-01', 'RX-02'):
            extracted = extract_window(original['canonical'], receiver)
            rows = extracted.pop('row_features')
            name = key + '-' + receiver.lower() + '.LLTF52.features.jsonl'
            data = ''.join(json.dumps(row, ensure_ascii=False, allow_nan=False, separators=(',', ':')) + '\n' for row in rows).encode()
            row_files[name] = data
            extracted['row_features_artifact'] = {'name': name, 'bytes': len(data),
                'sha256': hashlib.sha256(data).hexdigest(), 'rows': len(rows), 'storage': 'new ignored local output only'}
            session['receivers'][receiver] = extracted
        report['sessions'][key] = session
    return report, row_files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--output-new', type=Path)
    mode.add_argument('--check', type=Path)
    parser.add_argument('--inside-sandbox', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args(); target = (args.output_new or args.check).resolve()
    if not target.is_relative_to(ROOT):
        raise ValueError('Internal output/check required')
    if not args.inside_sandbox:
        cmd = ['bwrap', '--unshare-all', '--die-with-parent', '--ro-bind', '/usr', '/usr', '--ro-bind', '/lib', '/lib',
            '--ro-bind', '/lib64', '/lib64', '--ro-bind', '/etc/ld.so.cache', '/etc/ld.so.cache',
            '--ro-bind', '/etc/localtime', '/etc/localtime', '--ro-bind', str(ROOT), str(ROOT),
            '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp', '--chdir', str(ROOT),
            '--setenv', 'HOME', '/tmp', '--setenv', 'PYTHONDONTWRITEBYTECODE', '1']
        if args.output_new:
            if not target.is_relative_to(ROOT / 'results/local'):
                raise ValueError('New local-only output required')
            target.mkdir(parents=True, exist_ok=False)
            cmd += ['--bind', str(target), str(target)]
        cmd += [str(ROOT / '.venv/bin/python'), '-B', str(Path(__file__).resolve()), '--inside-sandbox',
                '--output-new' if args.output_new else '--check', str(target)]
        return subprocess.run(cmd).returncode
    summary, rows = build_features()
    if args.check:
        if json.loads(target.read_text()) != summary:
            raise ValueError('Published physical feature report differs from original evidence')
        print('PHYSICAL_FEATURES_VERIFIED; no calibration/inference; historical rejections unchanged')
    else:
        for name, data in rows.items():
            with (target / name).open('xb') as f: f.write(data)
        with (target / 'features.resumen.json').open('x') as f:
            json.dump(summary, f, ensure_ascii=False, allow_nan=False, indent=2); f.write('\n')
        print('FEATURES_ONLY; four independent RX/session results; no calibration/inference')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
