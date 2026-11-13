#!/usr/bin/env python3
"""Prepare/metadata preflight by default. Physical execution needs fresh approval."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from dual_continuity import ContinuitySession, audit, preflight, validate_plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, default=ROOT/'config/continuidad_dual_60s_r1.review.json')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--preflight-only', action='store_true')
    mode.add_argument('--execute-after-approval', action='store_true')
    mode.add_argument('--audit', type=Path)
    parser.add_argument('--authorization-reference')
    parser.add_argument('--output-new', type=Path)
    args = parser.parse_args(argv)
    if args.audit:
        result = audit(args.audit)
    else:
        plan = validate_plan(json.loads(args.plan.read_text()))
        if args.preflight_only:
            result = dict(state='PREFLIGHT_METADATA_ONLY', physical_UART_opened=False,
                          identities=preflight(plan))
        elif not args.execute_after_approval:
            result = dict(state='PREPARED_NOT_AUTHORIZED', physical_UART_opened=False, plan=plan)
        else:
            if args.output_new is None:
                parser.error('--output-new required; never reuse an attempt')
            # This string records approval; it cannot authenticate a human decision.
            # The operator must obtain explicit authorization before running this mode.
            session = ContinuitySession(args.output_new, plan,
                                        authorization_reference=args.authorization_reference)
            result = session.run()
    # Never print during acquisition: a blocked terminal cannot stall the readers.
    shown = result
    if args.execute_after_approval or args.audit:
        r = result.get('report', {})
        shown = dict(integrity_ok=result['integrity_ok'], replay_ok=result['replay_ok'],
            output=str(args.audit or args.output_new), fatal=r.get('fatal', result.get('fatal')),
            acquisition=r.get('acquisition'), audit_activity=dict(physical_UART_opened=False),
            completed_nominal_duration=r.get('completed_nominal_duration', False),
            both_ports_closed_confirmed=r.get('both_ports_closed_confirmed', False),
            quality_approval=False, receivers={rx:dict(rows=len(x['rows']), bytes=x['bytes'],
                incidents=x['incidents'], tail=x['tail']) for rx,x in r.get('receivers', {}).items()})
    print(json.dumps(shown, ensure_ascii=False, indent=2))
    if args.execute_after_approval:
        r = result.get('report', {})
        return int(not (result['integrity_ok'] and result['replay_ok'] and
                       r.get('completed_nominal_duration') and r.get('both_ports_closed_confirmed')))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
