"""Offline proposal, NOT connected to controlled_dual_v1 or a physical CLI.

The caller supplies an already open stream and persists every returned chunk.
At the nominal deadline, finish only a pending LF-delimited line, with fixed
time/byte limits. LF framing is not CSV/CSI validity or session acceptance.
"""
from datetime import datetime, timezone
import math
import time


def read_to_boundary(port, nominal_deadline_ns, on_chunk, stop, *,
                     grace_ns=250_000_000, max_completion_bytes=65536,
                     clock=time.monotonic_ns,
                     utc=lambda: datetime.now(timezone.utc).isoformat()):
    """Proposed bounded stop; never opens/closes a port or discards bytes.

on_chunk(bytes, ledger_event) must persist all bytes, including post-deadline
data and any suffix of an in-flight read. The deadline never slides. A backend
must honor its finite timeout; OS scheduling is not a hard real-time guarantee.
An abort/error bypasses graceful completion. The caller still owns closure.
"""
    if (type(nominal_deadline_ns) is not int or nominal_deadline_ns < 0
            or type(grace_ns) is not int or grace_ns < 0
            or type(max_completion_bytes) is not int or max_completion_bytes <= 0):
        raise ValueError('Fixed nonnegative deadlines and positive byte limit required')
    original_timeout = port.timeout
    if original_timeout is None or not math.isfinite(original_timeout) or original_timeout <= 0:
        raise ValueError('A finite positive backend timeout is required')
    hard_deadline = nominal_deadline_ns + grace_ns
    offset = tail = completion_bytes = 0
    report = {'nominal_deadline_ns': str(nominal_deadline_ns),
              'completion_deadline_ns': str(hard_deadline),
              'max_completion_bytes': max_completion_bytes,
              'completion_started_ns': None, 'last_read_returned_ns': None}
    try:
        while True:
            now = clock()
            if stop.is_set():
                reason = 'aborted'
                break
            completion = now >= nominal_deadline_ns
            if completion:
                if tail == 0:
                    reason = 'lf_boundary'
                    break
                if now >= hard_deadline:
                    reason = 'time_limit_incomplete'
                    break
                if completion_bytes >= max_completion_bytes:
                    reason = 'byte_limit_incomplete'
                    break
                if report['completion_started_ns'] is None:
                    report['completion_started_ns'] = str(now)
                # One byte prevents reading a new line after the first LF.
                size, limit = 1, hard_deadline
            else:
                size = min(port.in_waiting or 1, 16384)
                limit = nominal_deadline_ns
            # Re-read after in_waiting/driver work; do not start with stale time.
            started = clock()
            if started >= limit:
                continue
            port.timeout = min(original_timeout, (limit - started) / 1e9)
            chunk = port.read(size)
            returned = clock()
            if not chunk:
                continue
            event = {'offset': offset, 'size': len(chunk), 'requested_size': size,
                     'started_ns': str(started), 'returned_ns': str(returned),
                     'host_timestamp_utc': utc(),
                     'phase': 'completion' if completion else 'nominal'}
            on_chunk(chunk, event)
            offset += len(chunk)
            if completion:
                completion_bytes += len(chunk)
            tail = len(chunk.rsplit(b'\n', 1)[-1]) if b'\n' in chunk else tail + len(chunk)
            report['last_read_returned_ns'] = str(returned)
    finally:
        port.timeout = original_timeout
    report.update(stop_reason=reason, stopped_ns=str(clock()), bytes_received=offset,
                  trailing_bytes=tail, completion_bytes=completion_bytes,
                  lf_boundary_reached=tail == 0)
    return report
