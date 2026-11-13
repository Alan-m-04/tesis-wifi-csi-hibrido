"""Independent v2 policy audit; byte preservation and stop quality are separate."""
import json
from datetime import datetime

from controlled_protocol import STOP_POLICY_V2


def audit_bounded_stop(root, rx, summary, parsed, session):
    """Return (metadata/transport integrity, boundary policy quality)."""
    try:
        common = session['controlled']
        value = common.get('stop_deadline_ns', common.get('common_deadline_ns'))
        nominal = None if value is None else int(value)
        hard = None if nominal is None else nominal + STOP_POLICY_V2['grace_ns']
        raw = (root / (rx.lower() + '.serial.log')).read_bytes()
        events = [json.loads(line) for line in (root / (rx.lower() + '.reads.jsonl')).read_text().splitlines()]
        report = summary['stop']
        lifecycle = session['lifecycle']
        def event_time(name, receiver=None):
            found = [e for e in lifecycle if e['event'] == name and e.get('receiver') == receiver]
            if len(found) != 1:
                raise ValueError('Exactly one lifecycle event required')
            return int(found[0]['monotonic_ns'])
        opening, opened = (event_time(name, rx) for name in ('opening', 'opened'))
        closing, closed = (event_time(name, rx) for name in ('closing', 'closed'))
        joined, all_closed = (event_time(name) for name in ('readers_joined', 'ports_closed'))
        started, stopped = int(report['started_ns']), int(report['stopped_ns'])
        if not (int(session['capture_start_monotonic_ns']) <= opening <= opened <= started <= stopped
                <= joined <= closing <= closed <= all_closed <= int(session['capture_deadline_monotonic_ns'])):
            return False, False
        for name in ('started_utc', 'stopped_utc'):
            if datetime.fromisoformat(report[name]).utcoffset() is None:
                return False, False
        if (common['stop_policy'] != STOP_POLICY_V2
                or report['nominal_deadline_ns'] != (None if nominal is None else str(nominal))
                or report['completion_deadline_ns'] != (None if hard is None else str(hard))
                or report['max_completion_bytes'] != STOP_POLICY_V2['max_completion_bytes']
                or report['bytes_received'] != len(raw)
                or report['trailing_bytes'] != parsed['trailing_bytes']
                or report['lf_boundary_reached'] is not (parsed['trailing_bytes'] == 0)):
            return False, False
        offset = tail = extra = 0
        last_return = None
        completion_start = report['completion_started_ns']
        if completion_start is not None and (nominal is None or not nominal <= int(completion_start) < hard):
            return False, False
        for event in events:
            start, end = int(event['started_ns']), int(event['returned_ns'])
            size, requested = event['size'], event['requested_size']
            if (event['offset'] != offset or type(requested) is not int or not 0 < size <= requested <= 16384
                    or not started <= start <= end <= stopped):
                return False, False
            if nominal is not None and start >= nominal:
                if (event['phase'] != 'completion' or requested != 1 or tail == 0 or start >= hard
                        or completion_start is None or start < int(completion_start)):
                    return False, False
                extra += size
                if extra > STOP_POLICY_V2['max_completion_bytes']:
                    return False, False
            elif event['phase'] != 'nominal':
                return False, False
            chunk = raw[offset:offset + size]
            tail = len(chunk.rsplit(b'\n', 1)[-1]) if b'\n' in chunk else tail + size
            offset += size
            last_return = event['returned_ns']
        within_budget = hard is not None and (last_return is None or int(last_return) <= hard)
        if (offset != len(raw) or tail != parsed['trailing_bytes'] or report['completion_bytes'] != extra
                or report['last_read_returned_ns'] != last_return
                or report['last_return_within_budget'] is not within_budget):
            return False, False
        reason = report['stop_reason']
        if reason == 'lf_boundary':
            metadata_ok = nominal is not None and tail == 0 and stopped >= nominal
        elif reason == 'time_limit_incomplete':
            metadata_ok = hard is not None and tail > 0 and stopped >= hard
        elif reason == 'byte_limit_incomplete':
            metadata_ok = tail > 0 and extra == STOP_POLICY_V2['max_completion_bytes']
        elif reason in ('aborted', 'error'):
            metadata_ok = session['status'] != 'completed' or bool(summary.get('error'))
        else:
            metadata_ok = False
        return metadata_ok, metadata_ok and reason == 'lf_boundary' and within_budget and not summary.get('error')
    except (KeyError, ValueError, TypeError, OSError):
        return False, False
