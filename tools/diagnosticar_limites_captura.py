#!/usr/bin/env python3
"""Offline only: diagnose bytes/ledgers; write a NEW local directory."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from diagnose_capture_boundaries import diagnose


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--output-new', required=True, type=Path)
    args = parser.parse_args()
    output = args.output_new.resolve()
    if not output.is_relative_to(ROOT / 'results/local'):
        parser.error('Output must be a new internal results/local directory')
    diagnosis = diagnose(args.run)
    output.mkdir(parents=True, exist_ok=False)
    with (output / 'diagnostico.json').open('x') as stream:
        json.dump(diagnosis, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(output / 'diagnostico.json')


if __name__ == '__main__':
    main()
