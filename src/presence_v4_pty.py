"""Persistent lifecycle implemented exclusively with PTYs owned by this process.

No UART paths, discovery, serial.Serial, firmware, physical or replay transport.
The reducer's logical seconds remain fixed; acceleration is synthetic evidence.
"""
import errno
import os
import select
import time
import tty

from capture_csi_multi import RECEIVERS
from persistent_presence_v4 import POLICY
from presence_v4_audio import RecordingNotifier
from presence_v4_journal import V4Journal


class SyntheticClock:
    def __init__(self, speed=1):
        if type(speed) is not int or not 1 <= speed <= 100:
            raise ValueError('Synthetic clock speed must be an integer in [1,100]')
        self.speed = speed
        self.origin = time.monotonic_ns()

    def __call__(self):
        return (time.monotonic_ns()-self.origin)*self.speed


class SteppedFixtureClock:
    """Deterministic PTY test clock. This is never a physical/real-time clock."""
    speed = None

    def __init__(self):
        self.now = 0

    def __call__(self):
        return self.now

    def advance(self, ns):
        self.now += ns


class OwnedPty:
    def __init__(self, receiver):
        self.receiver = receiver
        self.master, self.slave = os.openpty()
        try:
            tty.setraw(self.slave)
            os.set_blocking(self.slave, False)
            os.set_blocking(self.master, False)
        except BaseException:
            os.close(self.master); os.close(self.slave)
            raise
        self.close_attempts = 0
        self.receiver_fd_open = self.master_fd_open = True

    def fixture_write(self, data):
        if os.write(self.master, data) != len(data):
            raise OSError('Partial synthetic producer write; fixture failed')

    def close_receiver(self):
        self.close_attempts += 1
        os.close(self.slave)
        self.receiver_fd_open = False
        try:
            os.fstat(self.slave)
        except OSError as exc:
            if exc.errno == errno.EBADF:
                return True
            raise
        return False

    def dispose_fixture(self):
        # Test fixture cleanup, separate from (and never reported as) protocol close.
        for attribute, fd in (('receiver_fd_open', self.slave), ('master_fd_open', self.master)):
            if not getattr(self, attribute):
                continue
            try:
                os.close(fd)
            except OSError:
                pass
            setattr(self, attribute, False)


class PtySession:
    def __init__(self, output, plan, *, clock=None, endpoint_type=OwnedPty, notifier=None):
        if not issubclass(endpoint_type, OwnedPty):
            raise ValueError('Only process-owned PTY endpoints are implemented')
        self.clock = clock or SyntheticClock()
        self.journal = V4Journal(output, plan)
        self.machine = self.journal.machine
        self.notifier = notifier or RecordingNotifier()
        self.endpoints, self.started_signals = {}, set()
        self.read_loop_stopped = False
        self.receipt_persisted = False
        self.storage_failed = False
        self.finalized = False
        try:
            self.command('begin')
            for rx in RECEIVERS:
                self.endpoints[rx] = endpoint_type(rx)
                self.command('opened', receiver=rx)
        except BaseException:
            try:
                self.command('io_error')
                self.close()
                self.finalize()
            finally:
                self.journal.close_files()
                for endpoint in self.endpoints.values():
                    endpoint.dispose_fixture()
            raise

    def command(self, op, **data):
        try:
            self.journal.command(op, self.clock(), **data)
        except OSError:
            # Storage failure cannot be turned into a successful receipt or cue.
            self.machine.apply('storage_error', self.clock())
            self.storage_failed = True
            self.machine.close_requested = True
            raise

    def read_ready(self, receivers=None, close_budget=False):
        if self.read_loop_stopped:
            raise RuntimeError('Reads are forbidden after the stop acknowledgement')
        candidates = list(self.endpoints) if receivers is None else list(receivers)
        fds = {self.endpoints[rx].slave: rx for rx in candidates if rx not in self.machine.closed}
        if not fds:
            return
        ready, _, _ = select.select(list(fds), [], [], 0)
        for fd in ready:
            rx = fds[fd]
            limit = min(16384, POLICY['close_bytes']-self.machine.close_bytes[rx]) if close_budget else 16384
            if limit <= 0:
                continue
            start = self.clock()
            try:
                chunk = os.read(fd, limit)
            except BlockingIOError:
                continue
            except OSError:
                self.command('io_error', receiver=rx)
                continue
            end = self.clock()
            if chunk:
                self.command('chunk', receiver=rx, chunk=chunk, started_ns=start, returned_ns=end)
            else:
                self.command('reader_ended', receiver=rx)

    def pump_signals(self):
        for cue in self.machine.signals:
            if cue['id'] in self.started_signals:
                continue
            if cue['kind'] == 'both_ports_closed_confirmed' and not self.receipt_persisted:
                continue
            self.started_signals.add(cue['id'])
            try:
                self.notifier.start(cue)
            except Exception:
                self.command('cue_ack', signal_id=cue['id'], success=False)
        for signal_id, success in self.notifier.poll():
            self.command('cue_ack', signal_id=signal_id, success=success)

    def step(self):
        if not self.read_loop_stopped:
            self.read_ready()
        self.command('tick')
        self.pump_signals()
        if self.machine.close_requested and self.machine.closing_since is None:
            self.close()

    def close(self):
        if self.machine.closing_since is not None:
            return
        if not self.machine.close_requested:
            self.command('close_request')
        try:
            self.command('closing')
        except OSError:
            # Durable logging can fail; resource cleanup must still run.
            if self.machine.closing_since is None:
                self.machine.apply('closing', self.clock())
        try:
            if not self.machine.fatal:
                deadline = self.machine.closing_since+POLICY['close_wait_ns']
                while self.clock() < deadline:
                    pending = [rx for rx in self.endpoints if self.machine.framers[rx].length and
                               self.machine.close_bytes[rx] < POLICY['close_bytes']]
                    if not pending or self.machine.fatal:
                        break
                    self.read_ready(pending, close_budget=True)
                    if isinstance(self.clock, SteppedFixtureClock):
                        self.clock.advance(1_000_000)
                    time.sleep(.0002)
        finally:
            # One synchronous reader: leaving its loop is observed, not inferred
            # from a timer or a thread join timeout. No later read can execute.
            self.read_loop_stopped = True
            storage_exception = None
            for rx in RECEIVERS:
                confirmed, error = False, None
                try:
                    if rx in self.endpoints:
                        confirmed = self.endpoints[rx].close_receiver()
                    else:
                        error = 'not_opened'
                except BaseException as exc:
                    error = type(exc).__name__+': '+str(exc)
                try:
                    self.command('closed', receiver=rx, confirmed=confirmed,
                                 reader_stopped=self.read_loop_stopped, error=error,
                                 proof='owned_PTY_fstat_EBADF_after_os_close' if confirmed else 'unconfirmed')
                except OSError as exc:
                    storage_exception = exc
                    self.machine.apply('closed', self.clock(), receiver=rx, confirmed=confirmed,
                                       reader_stopped=True, error=error,
                                       proof='owned_PTY_fstat_EBADF_after_os_close' if confirmed else 'unconfirmed')
            if storage_exception is not None:
                raise storage_exception
            self.journal.receipt()
            self.receipt_persisted = True
            self.pump_signals()

    def finalize(self):
        if not self.read_loop_stopped:
            self.close()
        if self.storage_failed:
            raise RuntimeError('Storage failure; no finalized evidence or success claim')
        # Completion is observed through cue results. No timer grants success.
        deadline = time.monotonic()+15
        while any(c['ack_ns'] is None for c in self.machine.signals):
            self.pump_signals()
            if time.monotonic() >= deadline:
                raise RuntimeError('Unconfirmed notification; no success claim')
            time.sleep(.001)
        self.notifier.finish()
        self.journal.finalize(dict(transport='process_owned_PTY_only',
            synthetic_clock_speed=getattr(self.clock, 'speed', None), notifier=self.notifier.name,
            clock_kind=type(self.clock).__name__,
            bubblewrap_isolation_claimed=False, audibility_verified=False,
            opens_per_receiver={rx: int(s['opened']) for rx,s in self.machine.states.items()},
            close_attempts={rx: e.close_attempts for rx,e in self.endpoints.items()}))
        self.finalized = True
        for endpoint in self.endpoints.values():
            endpoint.dispose_fixture()

    def __enter__(self):
        return self

    def __exit__(self, kind, value, traceback):
        try:
            if kind is not None:
                try:
                    self.command('interrupt')
                finally:
                    self.close()
            if not self.finalized:
                self.finalize()
        finally:
            self.journal.close_files()
            for endpoint in self.endpoints.values():
                endpoint.dispose_fixture()
