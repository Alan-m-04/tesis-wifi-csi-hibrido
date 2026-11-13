"""Bounded LF completion used by controlled_dual_v2; never opens a stream.

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
                     utc=lambda: datetime.now(timezone.utc).isoformat(), report=None):
    """Never opens/closes a port or discards bytes; report also survives errors.

on_chunk(bytes, ledger_event) must persist all bytes, including post-deadline
data and any suffix of an in-flight read. The deadline never slides. A backend
must honor its finite timeout; OS scheduling is not a hard real-time guarantee.
An abort/error bypasses graceful completion. The caller still owns closure.
The deadline may be a getter returning None during startup and then one fixed
integer. This lets the first receiver preserve bytes before the second opens.
"""
    if ((not callable(nominal_deadline_ns) and
         (type(nominal_deadline_ns) is not int or nominal_deadline_ns < 0))
            or type(grace_ns) is not int or grace_ns < 0
            or type(max_completion_bytes) is not int or max_completion_bytes <= 0):
        raise ValueError('Fixed nonnegative deadlines and positive byte limit required')
    original_timeout = port.timeout
    if original_timeout is None or not math.isfinite(original_timeout) or original_timeout <= 0:
        raise ValueError('A finite positive backend timeout is required')
    deadline_source = nominal_deadline_ns
    deadline = hard_deadline = None
    offset = tail = completion_bytes = 0
    if report is None:
        report = {}
    report.update(started_ns=str(clock()), started_utc=utc(), nominal_deadline_ns=None,
                  completion_deadline_ns=None, max_completion_bytes=max_completion_bytes,
                  completion_started_ns=None, last_read_returned_ns=None)
    reason = 'error'
    try:
        while True:
            observed = deadline_source() if callable(deadline_source) else deadline_source
            if observed is not None:
                if type(observed) is not int or observed < 0 or (deadline is not None and observed != deadline):
                    raise ValueError('The nominal deadline must become one fixed nonnegative integer')
                deadline = observed
                hard_deadline = deadline + grace_ns
                report.update(nominal_deadline_ns=str(deadline), completion_deadline_ns=str(hard_deadline))
            elif deadline is not None:
                raise ValueError('The nominal deadline cannot be removed')
            now = clock()
            if stop.is_set():
                reason = 'aborted'
                break
            completion = deadline is not None and now >= deadline
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
                limit = deadline
            # Re-read after in_waiting/driver work; do not start with stale time.
            started = clock()
            if limit is not None and started >= limit:
                continue
            port.timeout = original_timeout if limit is None else min(original_timeout, (limit - started) / 1e9)
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
        try:
            port.timeout = original_timeout
        finally:
            last_return = report['last_read_returned_ns']
            report.update(stop_reason=reason, stopped_ns=str(clock()), stopped_utc=utc(), bytes_received=offset,
                          trailing_bytes=tail, completion_bytes=completion_bytes,
                          lf_boundary_reached=tail == 0,
                          last_return_within_budget=(hard_deadline is not None and
                              (last_return is None or int(last_return) <= hard_deadline)))
    return report
