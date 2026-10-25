"""Only private PTYs. Synthetic durations are explicit, never physical evidence."""
import os
from pathlib import Path
import pty
import threading
import time
import tty
from unittest.mock import patch

import serial
import controlled_capture as control
from controlled_protocol import V3, STOP_POLICY_V2, AVAILABILITY_V3
from preserving_serial import preserving_serial_type
from test_validate_capture import frame
from test_availability_window import ready


def plan_v3():
    return {'protocol': V3, 'seconds': 30, 'baud': 115200, 'ports': dict(control.PORTS),
            'stable_window': None, 'stop_policy': dict(STOP_POLICY_V2),
            'availability_policy': dict(AVAILABILITY_V3),
            'environment': {key: 'SYNTHETIC PRIVATE PTY; no physical measurement'
                            for key in control.ENVIRONMENT_FIELDS}}


def run_pty_v3(root, name='synthetic-v3', scenario='accepted', duration=.16, wait_ns=700_000_000):
    root = Path(root)
    (root / 'results/local').mkdir(parents=True, exist_ok=True)
    pairs, devices, writers, close_events, writer_errors = {}, [], [], [], []
    finished, abort = threading.Event(), threading.Event()
    shared = {}
    delayed = threading.Event()
    for rx in control.PORTS:
        master, slave = pty.openpty(); tty.setraw(slave); os.set_blocking(master, False)
        pairs[rx] = (master, slave, os.ttyname(slave))

    def created(coordinator, timing):
        shared.update(coordinator=coordinator, timing=timing)
        if scenario == 'late_error':
            original_publish = coordinator.publish
            initial_end = len(ready('RX-01')) + sum(len(frame(i, 100000 + i * 200000)) for i in range(3))
            error_end = initial_end + len(b'CSI_DATA,broken\r\n')
            def delayed_publish(rx, chunk, event):
                if rx == 'RX-01' and event['offset'] < error_end <= event['offset'] + event['size']:
                    delayed.set()
                    until = time.monotonic() + 1
                    while coordinator.t0 is None and time.monotonic() < until and not finished.is_set(): finished.wait(.0005)
                original_publish(rx, chunk, event)
            coordinator.publish = delayed_publish

    def send(master, data):
        while data and not finished.is_set():
            try:
                n = os.write(master, data); data = data[n:]
            except BlockingIOError:
                finished.wait(.001)

    def wait_until(ns):
        while time.monotonic_ns() < ns and not finished.is_set(): finished.wait(.0005)

    def produce(rx):
        try:
            master = pairs[rx][0]
            c = shared['coordinator']
            if scenario == 'silent': return
            prefix = b'\x00ESP-ROM:synthetic\r\n' if scenario == 'startup_residue' else b''
            rows = b''.join(frame(i, 100000 + i * 200000) for i in range(3))
            initial = prefix + (b'' if scenario == 'missing_ready' else ready(rx)) + rows
            if scenario == 'same_chunk_reset' and rx == 'RX-02':
                initial += b'ESP-ROM:synthetic\r\n'
            if scenario == 'conflicting_ready' and rx == 'RX-02':
                initial += ready(rx).replace(b'channel=11', b'channel=6')
            if scenario == 'late_error' and rx == 'RX-02':
                if not delayed.wait(1): raise RuntimeError('Late-error test did not reach held publication')
            send(master, initial)
            if scenario == 'late_error' and rx == 'RX-01':
                until = time.monotonic() + 1
                while len(c.states[rx]['streak']) != 3 and time.monotonic() < until: finished.wait(.0005)
                send(master, b'CSI_DATA,broken\r\n')
            while c.t0 is None and not finished.is_set() and not c.fatal and not c.timed_out:
                finished.wait(.0005)
            if c.t0 is None or finished.is_set(): return
            if scenario == 'empty_window': return
            # More than one reader timeout from T0, so first-read-before-T0
            # exclusion is exercised without starving all included rows.
            wait_until(c.t0 + min(70_000_000, int(duration * 1e9 / 3)))
            send(master, frame(3, 700000))
            wait_until(c.t0 + min(110_000_000, int(duration * 1e9 * 2 / 3)))
            send(master, frame(4, 900000))
            if scenario == 'window_error': send(master, b'CSI_DATA,broken\r\n')
            if scenario == 'window_reset' and rx == 'RX-01': send(master, b'ESP-ROM:synthetic\r\n')
            if scenario == 'abort': abort.set(); return
            if scenario in ('completion', 'stop_timeout', 'no_lf', 'read_error'):
                wait_until(c.t1 - 15_000_000)
                line = frame(5, 1100000)
                send(master, line[:129])
                if scenario == 'completion':
                    wait_until(c.t1 + 10_000_000); send(master, line[129:])
                elif scenario == 'no_lf':
                    while not finished.is_set():
                        send(master, b'x' * 256); finished.wait(.001)
        except Exception as exc:
            writer_errors.append(repr(exc))

    base = preserving_serial_type(serial.Serial)
    class PtyPort(base):
        def __init__(self, **kwargs):
            self.rx = None; self.in_read = False; self.injected_errors = 0; self.close_error_raised = False
            super().__init__(**kwargs); devices.append(self)
        def open(self):
            self.rx = next(rx for rx, link in control.PORTS.items() if link == self.port)
            if self.rx == 'RX-02' and scenario == 'second_open_error':
                raise OSError('synthetic second open failure')
            self.port = pairs[self.rx][2]; super().open()
            thread = threading.Thread(target=produce, args=(self.rx,)); writers.append(thread); thread.start()
        def read(self, size=1):
            self.in_read = True
            try:
                c = shared.get('coordinator')
                if (scenario == 'read_error' and self.rx == 'RX-01' and c is not None
                        and c.t0 is not None and time.monotonic_ns() >= c.t1):
                    self.injected_errors += 1
                    raise serial.SerialException('synthetic RX-01 read error')
                return super().read(size)
            finally: self.in_read = False
        def close(self):
            if self.rx: close_events.append({'receiver': self.rx, 'read_active': self.in_read})
            super().close()
            if self.rx == 'RX-01' and scenario == 'close_error' and not self.close_error_raised:
                self.close_error_raised = True
                raise OSError('synthetic close error after closing fd')

    identities = {rx: {'by_id': link, 'resolved': pairs[rx][2], 'synthetic': True}
                  for rx, link in control.PORTS.items()}
    try:
        with patch.object(control, 'ROOT', root), patch.object(control, 'provenance', return_value={
                'evidence_type': 'synthetic_fixture', 'note': 'Private PTY; no physical acquisition',
                'installed_firmware_sha256': None}):
            code = control.run_capture(plan_v3(), root / 'results/local' / name, seconds=duration,
                test_backend={'factory': PtyPort, 'identities': identities, 'stop_event': abort,
                              'coordinator_created': created, 'availability_wait_ns': wait_ns})
        return {'run': root / 'results/local' / name, 'returncode': code, 'close_events': list(close_events),
                'all_ports_closed': all(not d.is_open for d in devices), 'writer_errors': list(writer_errors),
                'injected_read_errors': sum(d.injected_errors for d in devices),
                'synthetic_duration_seconds': duration, 'synthetic_wait_ns': wait_ns}
    finally:
        finished.set()
        for thread in writers:
            thread.join(timeout=2)
            if thread.is_alive(): raise RuntimeError('Synthetic producer did not stop')
        for device in devices: serial.Serial.close(device)
        for master, slave, _ in pairs.values(): os.close(master); os.close(slave)
