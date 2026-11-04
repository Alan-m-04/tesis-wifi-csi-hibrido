#!/usr/bin/env python3
"""Real-time synthetic PTY experiment; no physical transport CLI."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from rx02_service_lab import run_case


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-new',type=Path,required=True)
    p.add_argument('--variant',choices=('legacy','checkpoint2'),default='legacy')
    p.add_argument('--mechanism',choices=('none','ops_sync','raw_sync','lock','serialization','processing','guard'),default='none')
    p.add_argument('--delay-ms',type=float,default=0)
    p.add_argument('--duration',type=float,default=10)
    p.add_argument('--windows',action='store_true')
    p.add_argument('--request-delay',type=float,default=0)
    p.add_argument('--poll-ms',type=float,default=5)
    a=p.parse_args();out=a.output_new.resolve()
    if not out.is_relative_to(ROOT/'results/local'):p.error('New local laboratory output required')
    r=run_case(out,variant=a.variant,mechanism=a.mechanism,delay_ms=a.delay_ms,duration=a.duration,
               windows=a.windows,request_delay=a.request_delay,poll_ms=a.poll_ms)
    print(json.dumps({k:r[k] for k in ('variant','mechanism','actual_elapsed_s','fatal','integrity_ok','replay_ok','errors','generated_rows')},indent=2))
    return int(bool(r['errors']) or not r['integrity_ok'] or not r['replay_ok'])


if __name__=='__main__':raise SystemExit(main())
