#!/usr/bin/env python3
"""Analyze recorded v4 availability timing offline; never open a transport."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from presence_v4_diagnostics import analyze_availability


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--output-new', type=Path, required=True)
    parser.add_argument('--control', type=Path, help='Optional recorded launcher claim/result directory')
    args = parser.parse_args(argv)
    report = analyze_availability(args.bundle, args.control)
    with args.output_new.open('x') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2); stream.write('\n')
    print(json.dumps(dict(output=str(args.output_new), fatal=report['suspension']['reason'],
        integrity_ok=report['integrity_ok'], replay_ok=report['replay_ok'], UART_opened=False),indent=2))
    return 0


if __name__ == '__main__':raise SystemExit(main())
