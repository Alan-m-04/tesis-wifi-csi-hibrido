#!/usr/bin/env python3
"""Review-only C03 opt-in; no discovery, preflight or physical execution route."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from presence_rx02 import validate_plan
from rx02_checkpoint_journal import PERSISTENCE_REVISION


def review(plan):
    validate_plan(plan)
    if (plan.get('connection_id')!='RX02-C03' or plan.get('partition_group')!='RX02-C03' or
        plan.get('future_partition')!='development_future' or
        plan.get('persistence_revision')!=PERSISTENCE_REVISION or
        plan.get('authorization_granted') is not False or plan.get('review_only') is not True):
        raise ValueError('Only unapproved C03 development review with explicit checkpoint revision is allowed')
    return dict(state='REVIEW_ONLY_NOT_AUTHORIZED',physical_UART_opened=False,
        physical_preflight_performed=False,authorization_granted=False,
        physical_execution_implemented_here=False,persistence_revision=PERSISTENCE_REVISION,
        session_class_for_future_review='rx02_checkpoint_journal.CheckpointRx02Session',plan=plan)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,default=ROOT/'config/piloto_rx02_C03_checkpoint2.review.json')
    args=parser.parse_args(argv)
    print(json.dumps(review(json.loads(args.plan.read_text())),ensure_ascii=False,indent=2))
    return 0


if __name__=='__main__':raise SystemExit(main())
