#!/usr/bin/env python3
"""Audit existing RX02-C02/C01 and save new offline forensics only."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from rx02_gap_diagnostics import compare_c01_c02,inventory,require


def write_new(path,value):
    with path.open('x') as f:
        json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--c01',type=Path,default=ROOT/'results/local/piloto-rx02-r1-C01')
    p.add_argument('--c02',type=Path,default=ROOT/'results/local/piloto-rx02-r1-C02')
    p.add_argument('--output-new',type=Path,required=True)
    args=p.parse_args(argv);out=args.output_new.resolve()
    require(not out.exists() and not any(out.is_relative_to(b.resolve()) for b in (args.c01,args.c02)),
            'New output outside both original bundles required')
    report,audits=compare_c01_c02(args.c01,args.c02)
    out.mkdir(parents=True,exist_ok=False)
    write_new(out/'diagnostic.json',report)
    for key,audit in audits.items():write_new(out/('audit-'+key+'.json'),audit)
    write_new(out/'files.json',inventory(out))
    print(json.dumps(dict(output=str(out),fatal=report['bundles']['C02']['fatal'],
        label=report['bundles']['C02']['windows'][0]['label'],
        triggering_host_gap_ns=report['incident']['triggering_row_pair']['host_gap_ns'],
        triggering_local_gap_us=report['incident']['triggering_row_pair']['local_gap_us'],
        physical_UART_opened=False),ensure_ascii=False,indent=2))
    return 0


if __name__=='__main__':raise SystemExit(main())
