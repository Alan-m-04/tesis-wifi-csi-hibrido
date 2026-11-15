"""Explicit RX-02-only UART lifecycle. Import/preparation never open devices."""
import copy
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time

from controlled_capture import ROOT
from persistent_presence_v4 import POLICY
from presence_v4_uart import (UartSession, UartEndpoint, StorageGuard, StorageLimit, STORAGE,
    audited_serial_type, check_authorization, verify_serial_runtime, identity, revalidate)
from presence_v4_pty import SteppedFixtureClock
from presence_v4_journal import digest, write_new
from presence_v4_audio import LaptopNotifier, create_wav
from presence_rx02 import RECEIVERS, PORTS, validate_plan
from presence_rx02_journal import Rx02Journal


def preflight_rx02(plan):
    """Only RX-02 udev/stat/access. No UART construction, opening or RX-01 lookup."""
    validate_plan(plan, allow_physical=True)
    snapshot = identity('RX-02')
    if snapshot['by_id'] != PORTS['RX-02'] or snapshot['serial'] != RECEIVERS['RX-02']:
        raise ValueError('RX-02 metadata does not match the prospectively fixed identity')
    return {'RX-02': snapshot}


class Rx02LaptopNotifier(LaptopNotifier):
    """Same waveforms, singleton close name; software result is not audibility."""
    def _work(self):
        while True:
            cue = self.requests.get()
            if cue is None:
                return
            try:
                path = self.output/(str(cue['id'])+'-'+cue['kind']+'.wav')
                create_wav(path, 'both_ports_closed_confirmed' if
                    cue['kind'] == 'selected_port_closed_confirmed' else cue['kind'])
                result = subprocess.run([self.player, '--quiet', str(path)],
                                        timeout=10, capture_output=True, check=False)
                ok = result.returncode == 0
            except (OSError, ValueError, subprocess.SubprocessError):
                ok = False
            self.results.put((cue['id'], ok))



class Rx02Session(UartSession):
    def __init__(self, output, plan, *, authorization_reference=None, notifier=None,
                 test_backend=None, clock=None):
        from presence_v4_audio import RecordingNotifier
        self._state_lock = threading.RLock()
        self._startup_stop = threading.Event()
        self._startup_reader = None
        validate_plan(plan, allow_physical=True, execution=test_backend is None)
        if test_backend is None:
            check_authorization(authorization_reference)
            if notifier is not None and notifier.name == RecordingNotifier.name:
                raise ValueError('Physical operation requires configured laptop audio; audibility remains human-declared')
            if clock is not None:
                raise ValueError('No synthetic clock in physical execution')
            out = Path(output).resolve()
            if not out.is_relative_to(ROOT/'results/local'):
                raise ValueError('New physical output must be inside results/local')
            snapshots = preflight_rx02(plan)
            checker = revalidate
        else:
            out = Path(output)
            snapshots, checker = test_backend['identities'], test_backend['checker']
            if set(snapshots) != set(RECEIVERS):
                raise ValueError('Synthetic topology must also contain RX-02 only')
        self.clock = clock or time.monotonic_ns
        disk = shutil.disk_usage if test_backend is None else test_backend.get('disk_usage', shutil.disk_usage)
        ancestor = out.parent
        while not ancestor.exists():
            ancestor = ancestor.parent
        initial_free = disk(ancestor).free
        if initial_free < STORAGE['initial_free_bytes']:
            raise StorageLimit('Need at least 100 MiB free before opening')
        import serial, serial.serialposix, serial.serialutil
        verify_serial_runtime()
        factory = audited_serial_type(serial.Serial if test_backend is None else test_backend['serial_type'])
        transport = dict(implementation_base_commit='9b28addc221468ed1c38e6480a6cf153e5a00c70',
            backend='UART' if test_backend is None else 'synthetic_serial_backend', identities=snapshots,
            authorization_reference=authorization_reference if test_backend is None else None,
            initial_free_bytes_observed=initial_free,
            pyserial_version=serial.__version__, serialposix_sha256=digest(Path(serial.serialposix.__file__)),
            serialutil_sha256=digest(Path(serial.serialutil.__file__)),
            storage_policy=STORAGE, dtr_requested=False, rts_requested=False,
            decision_clock_sampled_after_raw_persistence=True,
            electrical_behavior_verified=False, installed_firmware_attested=False,
            sources={name:digest(ROOT/name) for name in ('src/presence_rx02_uart.py','src/presence_v4_uart.py',
                'src/preserving_serial.py','tools/piloto_presencia_rx02.py','config/pyserial_uart_v4.lock.json')})
        self.journal = Rx02Journal(out, plan, allow_physical=True,
            evidence_type='synthetic_fixture' if test_backend is not None else 'physical_capture',
            extra_provenance=transport, decision_clock=self.clock)
        self.machine = self.journal.machine
        try:
            if test_backend is None:
                write_new(out/'authorization-consumed.json', dict(protocol=plan['protocol'],
                    connection_id=plan['connection_id'], reference=authorization_reference,
                    consumed=True, retry_allowed=False,
                    meaning='consumed_before_open_attempt; actual opens recorded in operations'))
            if notifier is None and test_backend is None:
                notifier = Rx02LaptopNotifier(out/'audio')
            self.notifier = notifier or RecordingNotifier()
        except BaseException:
            self.journal.close_files()
            raise
        self.endpoints, self.started_signals = {}, set()
        self.read_loop_stopped = self.receipt_persisted = self.storage_failed = self.finalized = False
        self.notifier_finished = self.finalization_attempted = False
        self.guard = StorageGuard(out, self.journal, self.clock, disk_usage=disk,
            record=self.command, lock=self._state_lock)
        try:
            for rx in PORTS:
                self.endpoints[rx] = UartEndpoint(rx, snapshots[rx], factory, checker)
            self.command('begin')
            for rx, endpoint in self.endpoints.items():
                self.guard.check()
                self.command('tick')
                if self.machine.fatal:
                    raise RuntimeError('Initial availability deadline expired before next open')
                endpoint.open()
                with self._state_lock:
                    st = os.fstat(endpoint.serial.fileno())
                    binding = dict(identity=copy.deepcopy(snapshots[rx]),
                        opened_fingerprint=[st.st_dev, st.st_ino, st.st_rdev])
                    self.command('opened', receiver=rx, serial_configuration=endpoint.details(), identity_binding=binding)
                    endpoint.readable = True
            self._stop_startup_reader()
            if self.machine.fatal:
                raise RuntimeError('Startup suspended: '+self.machine.fatal)
        except BaseException as exc:
            try:
                self._stop_startup_reader()
                if self.machine.a is None:
                    self._record('begin')
                self._record('io_error', detail=type(exc).__name__+': '+str(exc),
                             resources={rx:e.details() for rx,e in self.endpoints.items()})
                self.close()
                if not self.storage_failed:
                    self.finalize()
            finally:
                self.journal.close_files()
                self._finish_notifier()
            raise

    def pump_signals(self):
        for cue in self.machine.signals:
            if cue['id'] in self.started_signals:
                continue
            if cue['kind'] == 'selected_port_closed_confirmed' and not self.receipt_persisted:
                continue
            self.started_signals.add(cue['id'])
            try:
                self.notifier.start(cue)
            except Exception:
                self.command('cue_ack', signal_id=cue['id'], success=False)
        for signal_id, success in self.notifier.poll():
            self.command('cue_ack', signal_id=signal_id, success=success)

    def close(self):
        self._stop_startup_reader()
        if self.machine.closing_since is not None:
            return
        if not self.machine.close_requested:
            self._record('close_request')
        self._record('closing')
        try:
            deadline = self.machine.closing_since+POLICY['close_wait_ns']
            while not self.machine.fatal and self.clock() < deadline:
                pending = [rx for rx in self.endpoints if self.machine.framers[rx].length and
                           self.machine.close_bytes[rx] < POLICY['close_bytes']]
                if not pending:
                    break
                self.read_ready(pending, close_budget=True)
                if isinstance(self.clock, SteppedFixtureClock):
                    self.clock.advance(1_000_000)
                time.sleep(.0002)
        finally:
            self.read_loop_stopped = True
            for rx in PORTS:
                confirmed, error = False, None
                try:
                    if rx in self.endpoints:
                        confirmed = self.endpoints[rx].close_receiver()
                    else:
                        error = 'resource_not_constructed'
                except BaseException as exc:
                    error = type(exc).__name__+': '+str(exc)
                self._record('closed', receiver=rx, confirmed=confirmed, reader_stopped=True, error=error,
                             proof='pyserial_close_returned_and_all_fds_released' if confirmed else 'unconfirmed')
            if not self.storage_failed:
                try:
                    self.journal.receipt()
                except OSError as exc:
                    self.storage_failed = True
                    self._record('storage_error', detail='close_receipt: '+str(exc))
                    raise
                self.receipt_persisted = True
                self.pump_signals()
