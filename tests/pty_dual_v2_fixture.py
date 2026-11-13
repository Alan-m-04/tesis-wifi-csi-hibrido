"""Explicit synthetic dual coordinator fixture; only allocates private PTYs."""
import os
from pathlib import Path
import pty
import threading
import time
import tty
from unittest.mock import patch

import serial
import controlled_capture as control
from controlled_protocol import V2, STOP_POLICY_V2
from preserving_serial import preserving_serial_type
from test_validate_capture import frame


def plan_v2():
    return {'protocol': V2, 'seconds': 30, 'baud': 115200, 'ports': dict(control.PORTS),
            'stable_window': None, 'stop_policy': dict(STOP_POLICY_V2),
            'environment': {key: 'SYNTHETIC PRIVATE PTY; no physical measurement'
                            for key in control.ENVIRONMENT_FIELDS}}


def run_pty_dual(root, name='synthetic-v2', scenario='complete', duration=.12):
    """Shorter nominal time is injected only through the synthetic backend."""
    root = Path(root)
    (root / 'results/local').mkdir(parents=True, exist_ok=True)
    pairs = {}
    devices, writers, close_events, writer_errors = [], [], [], []
    finished = threading.Event()
    abort = threading.Event()
    shared = {}
    reader = control.capture.capture_receiver
    prefix = b'\x4c\x13\x00' if scenario == 'startup_residue' else b''
    if scenario in ('second_open_error', 'second_open_interrupt'):
        prefix = b'SYNTHETIC STARTUP\r\n'
    first, last = frame(), frame(1, 300000)
    for rx in control.PORTS:
        master, slave = pty.openpty()
        tty.setraw(slave)
        os.set_blocking(master, False)
        if prefix:
            os.write(master, prefix)
        pairs[rx] = (master, slave, os.ttyname(slave))

    def reader_wrapper(*args, **kwargs):
        shared['timing'] = args[-1]
        return reader(*args, **kwargs)

    def send(master, data):
        while data and not finished.is_set():
            try:
                count = os.write(master, data)
                data = data[count:]
            except BlockingIOError:
                finished.wait(.001)

    def produce(rx):
        try:
            while not finished.is_set():
                timing = shared.get('timing')
                if timing is not None and timing['deadline_ns'] is not None:
                    break
                finished.wait(.001)
            if finished.is_set():
                return
            master = pairs[rx][0]
            deadline = timing['deadline_ns']
            rom = b'ESP-ROM:synthetic\r\n' if prefix and scenario == 'startup_residue' else b''
            malformed = b'CSI_DATA,broken\r\n' if scenario == 'malformed' else b''
            send(master, rom + first + malformed + last[:129])
            if scenario == 'abort':
                finished.wait(duration / 3)
                abort.set()
            elif scenario == 'continuous_no_lf':
                while not finished.is_set():
                    send(master, b'x' * 256)
                    finished.wait(.001)
            elif scenario not in ('timeout', 'read_error'):
                while time.monotonic_ns() < deadline + 10_000_000 and not finished.is_set():
                    finished.wait(.001)
                send(master, last[129:] + frame(2, 500000))
        except Exception as exc:
            writer_errors.append(repr(exc))

    base = preserving_serial_type(serial.Serial)
    class PtyPort(base):
        def __init__(self, **kwargs):
            self.rx = None
            self.in_read = False
            self.injected_errors = 0
            super().__init__(**kwargs)
            devices.append(self)

        def open(self):
            self.rx = next(rx for rx, link in control.PORTS.items() if link == self.port)
            if self.rx == 'RX-02' and scenario in ('second_open_error', 'second_open_interrupt'):
                # Ensure first reader has actually preserved its prequeued bytes.
                until = time.monotonic() + 1
                raw = root / 'results/local' / name / 'capture/rx-01.serial.log'
                while (not raw.exists() or raw.stat().st_size == 0) and time.monotonic() < until:
                    finished.wait(.001)
                if scenario == 'second_open_interrupt':
                    raise KeyboardInterrupt()
                raise OSError('synthetic second open failure')
            self.port = pairs[self.rx][2]
            super().open()
            thread = threading.Thread(target=produce, args=(self.rx,))
            writers.append(thread)
            thread.start()

        def read(self, size=1):
            self.in_read = True
            try:
                timing = shared.get('timing', {})
                deadline = timing.get('deadline_ns')
                if (scenario == 'read_error' and self.rx == 'RX-01'
                        and deadline is not None and time.monotonic_ns() >= deadline):
                    self.injected_errors += 1
                    raise serial.SerialException('synthetic RX-01 read failure')
                return super().read(size)
            finally:
                self.in_read = False

        def close(self):
            if self.rx:
                close_events.append({'receiver': self.rx, 'read_active': self.in_read})
            super().close()

    identities = {rx: {'by_id': link, 'resolved': pairs[rx][2], 'synthetic': True}
                  for rx, link in control.PORTS.items()}
    try:
        with patch.object(control, 'ROOT', root), patch.object(control, 'provenance', return_value={
                'evidence_type': 'synthetic_fixture', 'installed_firmware_sha256': None,
                'note': 'Private PTY coordinator fixture; not physical acquisition'}), \
                patch.object(control.capture, 'capture_receiver', side_effect=reader_wrapper):
            code = control.run_capture(plan_v2(), root / 'results/local' / name,
                test_backend={'factory': PtyPort, 'identities': identities, 'stop_event': abort}, seconds=duration)
        return {'run': root / 'results/local' / name, 'returncode': code,
                'close_events': list(close_events), 'all_ports_closed': all(not d.is_open for d in devices),
                'injected_read_errors': sum(d.injected_errors for d in devices),
                'writer_errors': list(writer_errors), 'synthetic_duration': duration}
    finally:
        finished.set()
        for thread in writers:
            thread.join(timeout=2)
            if thread.is_alive():
                raise RuntimeError('Synthetic producer did not stop')
        for device in devices:
            serial.Serial.close(device)
        for master, slave, _ in pairs.values():
            os.close(master)
            os.close(slave)
