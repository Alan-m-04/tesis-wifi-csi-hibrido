#!/usr/bin/env python3
"""Read existing bundles only; create exclusive new forensic JSON."""
import argparse
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from continuity_diagnostics import analyze_continuity
from presence_v4_journal import write_new


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--output-new',type=Path,required=True)
    args=parser.parse_args()
    output=args.output_new.resolve()
    if output.is_relative_to(args.bundle.resolve()):
        parser.error('Forensic artifact must be outside the original bundle')
    if output.exists():
        parser.error('New output required; original reports are never overwritten')
    result=analyze_continuity(args.bundle)
    write_new(output,result)
    print(str(output))


if __name__=='__main__': main()
