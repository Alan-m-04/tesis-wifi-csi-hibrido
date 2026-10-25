#!/usr/bin/env python3
"""Prepare/preflight by default. UART opens only with --execute-after-approval."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from controlled_capture import validate_plan, preflight, run_capture


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--output-new',type=Path)
    mode=parser.add_mutually_exclusive_group();mode.add_argument('--preflight-only',action='store_true');mode.add_argument('--execute-after-approval',action='store_true')
    args=parser.parse_args();plan=json.loads(args.plan.read_text());validate_plan(plan,False)
    if args.preflight_only:
        print(json.dumps(preflight(plan),indent=2));return 0
    if not args.execute_after_approval:
        print(json.dumps({'state':'PREPARED_NOT_EXECUTED','physical_UART_opened':False,'plan':plan},ensure_ascii=False,indent=2));return 0
    validate_plan(plan,True)
    if not args.output_new:parser.error('--output-new is required for acquisition')
    return run_capture(plan,args.output_new)


if __name__=='__main__':raise SystemExit(main())
