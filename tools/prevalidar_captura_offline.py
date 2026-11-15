#!/usr/bin/env python3
"""Audit/extract one recorded E/S session; no UART, capture, model or minimum dataset size."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tools')]
from edge_presence_evaluation import safe_path
from edge_session_prevalidation import prevalidate


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--output-new', type=Path, required=True)
    parser.add_argument('--synthetic-fixture', action='store_true',
                        help='Explicit decision fixture only; never claim native/physical validation')
    args = parser.parse_args(argv)
    # No serial initialization, metadata, sound or acquisition subprocess exists here.
    from demo_offline import guard
    from panel_dispositivos import no_serial_open
    sys.addaudithook(guard)
    sys.addaudithook(no_serial_open)
    try:
        output = safe_path(args.output_new)
        if output.exists() or not output.is_relative_to(ROOT / 'results/local'):
            raise ValueError('Use una carpeta NUEVA dentro de results/local/')
        bundle = safe_path(args.bundle)
        if output.is_relative_to(bundle) or bundle.is_relative_to(output):
            raise ValueError('La salida debe estar separada del bundle original')
        report = prevalidate(bundle, synthetic_fixture=args.synthetic_fixture)
        output.mkdir(parents=True)
        with (output / 'prevalidation.json').open('x', encoding='utf-8') as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write('\n')
        print(json.dumps(report, ensure_ascii=False, allow_nan=False))
        return 0 if report['accepted'] else 2
    except (OSError, ValueError) as exc:
        print(json.dumps(dict(accepted=False, stage='command', reason=str(exc)), ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
