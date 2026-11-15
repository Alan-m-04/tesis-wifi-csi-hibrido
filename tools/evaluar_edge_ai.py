#!/usr/bin/env python3
"""Evaluate labeled whole sessions offline, or generate an explicitly synthetic QA report."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tools')]
from edge_presence_evaluation import evaluate, markdown, read_dataset, safe_path, sha
from edge_presence_synthetic import write_dataset, write_json


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    synthetic = sub.add_parser('synthetic', help='Invented I/Q only; no physical inputs')
    synthetic.add_argument('--output-new', type=Path, required=True)
    evaluation = sub.add_parser('evaluate', help='Explicit session manifest; no discovery or acquisition')
    evaluation.add_argument('--manifest', type=Path, required=True)
    evaluation.add_argument('--output-new', type=Path, required=True)
    args = parser.parse_args(argv)
    output = safe_path(args.output_new)
    if not output.is_relative_to(ROOT / 'results/local') or output == ROOT / 'results/local':
        parser.error('Use una salida NUEVA dentro de results/local/')
    if output.exists():
        parser.error('La salida ya existe; se conserva. Elija otra revisión')
    try:
        # Guard is active for every file access made by reused components too.
        from demo_offline import guard
        sys.addaudithook(guard)
        if args.command == 'synthetic':
            output.mkdir(parents=True)
            manifest_path = write_dataset(output / 'dataset-synthetic')
        else:
            manifest_path = safe_path(args.manifest)
            if output.is_relative_to(manifest_path.parent) or manifest_path.parent.is_relative_to(output):
                raise ValueError('Separar salida y datos originales')
        manifest, records, inputs = read_dataset(manifest_path)
        report = evaluate(manifest, records)
        changed = [name for name, digest in inputs.items() if sha(name) != digest]
        if changed:
            raise ValueError('Fuentes cambiaron durante la evaluación: ' + str(changed))
        report['inputs_sha256'] = inputs
        report['sources_unchanged'] = True
        report['implementation_sha256'] = {name: sha(ROOT / name) for name in (
            'src/edge_presence_evaluation.py', 'src/edge_presence_synthetic.py',
            'src/eligible_presence_features.py', 'src/presence_offline.py', 'src/ruview_presence_port.py',
            'tools/consolidar_rx02_c01.py', 'src/canonical_csi.py', 'src/csi_correspondence.py',
            'src/capture_csi_multi.py', 'vendor/ruview/presence/PROVENANCE.json',
            'vendor/ruview/presence/LICENSE', 'tools/evaluar_edge_ai.py')}
        output.mkdir(parents=True, exist_ok=args.command == 'synthetic')
        write_json(output / 'report.json', report)
        with (output / 'report.md').open('x', encoding='utf-8') as stream:
            stream.write(markdown(report))
        print(json.dumps(dict(report=str(output / 'report.json'), title=report['title'],
                              metrics=report['metrics']), ensure_ascii=False, allow_nan=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print('Evaluación bloqueada: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
