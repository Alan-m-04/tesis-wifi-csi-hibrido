#!/usr/bin/env python3
"""Consolidate existing physical bundles into a new offline output only."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools')]
from diagnostico_checkpoints_rx02 import diagnostic_report
from rx02_physical_report import compare
from rx02_gap_diagnostics import inventory,require
from presence_v4_journal import write_new


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--diagnostic',type=Path,default=ROOT/'results/local/diagnostico-checkpoints-rx02-r1')
    parser.add_argument('--c02',type=Path,default=ROOT/'results/local/piloto-rx02-r1-C02')
    parser.add_argument('--output-new',type=Path,required=True)
    args=parser.parse_args(argv)
    out=args.output_new.resolve()
    require(not out.exists() and not any(out.is_relative_to(p.resolve()) or p.resolve().is_relative_to(out)
        for p in (args.diagnostic,args.c02)),'New output outside originals required')
    report,audits=compare(args.diagnostic,args.c02,diagnostic_report)
    out.mkdir(parents=True,exist_ok=False)
    write_new(out/'summary.json',report)
    for name,audit in audits.items():write_new(out/('audit-'+name+'.json'),audit)
    write_new(out/'files.json',inventory(out))
    print(json.dumps(dict(output=str(out),diagnostic=report['diagnostic']['diagnostic'],
        cadence=report['diagnostic']['cadence_full'],C02_cadence=report['C02']['cadence_full']),indent=2))
    return 0


if __name__=='__main__':raise SystemExit(main())
