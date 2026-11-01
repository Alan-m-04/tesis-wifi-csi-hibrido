#!/usr/bin/env python3
"""Audit an explicitly exploratory bundle offline; never migrate old captures."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from persistent_presence_v4 import EXPLORATORY_ELIGIBILITY
from presence_v4_journal import audit_v4


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--output-new', type=Path, help='Optional full audit, exclusive creation')
    args = parser.parse_args(argv)
    if not args.bundle.is_dir() or not (args.bundle/'plan.json').is_file():
        raise ValueError('Existing regular bundle required')
    plan = json.loads((args.bundle/'plan.json').read_text())
    if plan.get('eligibility_revision') != EXPLORATORY_ELIGIBILITY:
        raise ValueError('Explicit exploratory bundle required; historical captures are not migrated')
    report = audit_v4(args.bundle)
    state = report['state']; exploration = state['exploration']
    preamble = exploration['preamble']
    compact = dict(evidence_type=state['evidence_type'], connection=state['connection'],
        preamble=dict(status=exploration['preamble_status'],
            end_processed_ns=preamble['end_processed_ns'] if preamble else None,
            receivers={rx: {k:v for k,v in value.items() if k != 'lines'}
                       for rx,value in preamble['receivers'].items()} if preamble else {},
            anomaly_count=len(exploration['anomalies'])),
        windows=[dict(id=w['id'], T0_ns=w['T0_ns'], T1_ns=w['T1_ns'],
            strict_eligible=w['eligible'], window_quality_ok=w['window_quality_ok'],
            pilot_coverage_ok=w['pilot_coverage_ok'], label_quality_ok=w['label_quality_ok'])
            for w in state['windows']], exploratory_eligibility=report['exploratory_eligibility'],
        physical_UART_opened=False)
    if args.output_new:
        with args.output_new.open('x') as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2); stream.write('\n')
    print(json.dumps(compact, ensure_ascii=False, indent=2))
    decisions = report['exploratory_eligibility']['windows']
    return int(not decisions or not all(w['eligible'] for w in decisions))


if __name__ == '__main__':raise SystemExit(main())
