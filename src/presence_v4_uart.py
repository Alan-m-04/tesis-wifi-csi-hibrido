"""Explicitly gated UART transport for v4; imports/preflight never open ports.

Synthetic backends are supplied only through the Python test API, never CLI.
The reducer and lifecycle signals are shared with the verified v4 PTY runner.
"""
import copy
import os
from pathlib import Path
import select
import shutil
import threading
import time

import capture_csi_multi as capture
from controlled_capture import PORTS, ROOT, ENVIRONMENT_FIELDS
from persistent_presence_v4 import POLICY, validate_plan, EXPLORATORY_ELIGIBILITY
from presence_v4_journal import V4Journal, digest, write_new
from presence_v4_pty import PtySession, SteppedFixtureClock
from preserving_serial import preserving_serial_type

STORAGE = dict(initial_free_bytes=100*1024**2, reserve_bytes=32*1024**2,
               max_raw_bytes=64*1024**2, max_bundle_bytes=256*1024**2,
               max_connection_ns=3600*1_000_000_000)


def validate_uart_plan(plan, *, execution=False):
    validate_plan(plan, allow_physical=True)
    if plan.get('ports') != PORTS or plan.get('baud') != 115200 or plan.get('storage_policy') != STORAGE:
        raise ValueError('Fixed by-id paths, 115200 baud and exact UART storage policy required')
    if execution:
        if plan['execution_mode'] != 'physical_after_approval':
            raise ValueError('Physical execution requires a physical plan')
        for name in (*ENVIRONMENT_FIELDS, 'mounting_confirmation', 'sound_practice_reference'):
            value = plan.get('environment', {}).get(name)
            if not isinstance(value, str) or not value.strip() or 'PENDIENTE' in value.upper():
                raise ValueError('Complete declaration before physical execution: '+name)
        if any('PENDIENTE' in plan[key].upper() for key in ('actor','connection_id','partition_group','mounting_reference')):
            raise ValueError('Actor, connection ID, partition and mounting reference must be completed')
    return copy.deepcopy(plan)


def check_authorization(reference):
    if (not isinstance(reference, str) or not reference.strip() or
            any(word in reference.upper() for word in ('PENDIENTE', 'COMPLETAR', 'EJEMPLO', 'SYNTHETIC'))):
        raise ValueError('New explicit human authorization reference required; this task grants no physical authorization')


def verify_serial_runtime():
    import json
    import serial, serial.serialposix, serial.serialutil
    lock=json.loads((ROOT/'config/pyserial_uart_v4.lock.json').read_text())
    if (serial.__version__ != lock['version'] or os.name != 'posix' or
            serial.Serial is not serial.serialposix.Serial):
        raise ValueError('Audited pySerial POSIX implementation required')
    for name,module in (('serialposix.py',serial.serialposix),('serialutil.py',serial.serialutil)):
        if digest(Path(module.__file__)) != lock['files'][name]:
            raise ValueError('pySerial source differs from the inspected lock: '+name)
    return serial


def identity(rx):
    node, props = capture.port_identity(PORTS[rx])
    capture.require_identity(rx, PORTS[rx], props)
    if props.get('ID_MODEL_ID') != '55d3':
        raise ValueError(rx+': USB PID mismatch')
    if not os.access(node, os.R_OK | os.W_OK, effective_ids=True):
        raise PermissionError(rx+': effective read/write permissions missing; no chmod/sudo attempted')
    st = os.stat(node)
    return dict(by_id=PORTS[rx], resolved=node, serial=props['ID_SERIAL_SHORT'],
                vid=props['ID_VENDOR_ID'], pid=props['ID_MODEL_ID'], bus=props['ID_BUS'],
                node_fingerprint=[st.st_dev, st.st_ino, st.st_rdev],
                permissions=dict(mode=oct(st.st_mode & 0o7777), uid=st.st_uid, gid=st.st_gid))


def preflight_uart(plan):
    """Only udev/stat/access. No Serial construction, open, ioctl or reads."""
    validate_uart_plan(plan)
    resolved = capture.resolve_ports(list(PORTS), PORTS)
    result = {rx: identity(rx) for rx in PORTS}
    if any(result[rx]['resolved'] != resolved[rx] for rx in PORTS):
        raise ValueError('USB changed during preflight')
    return result


def revalidate(rx, expected):
    current = identity(rx)
    if current != expected:
        raise ValueError(rx+': USB node/identity/permissions changed; no retry')
    return current


def audited_serial_type(base):
    """Observe actual driver update attempts without changing pySerial ordering."""
    class AuditedSerial(preserving_serial_type(base)):
        def __init__(self, **kwargs):
            self.line_requests = []
            super().__init__(**kwargs)

        def _line(self, name, action):
            item = dict(line=name, requested=getattr(self, name), outcome='requested')
            self.line_requests.append(item)
            try:
                result = action()
            except BaseException as exc:
                item.update(outcome='error', error=type(exc).__name__+': '+str(exc), errno=getattr(exc, 'errno', None))
                raise
            item['outcome'] = 'ioctl_returned'
            return result

        def _update_dtr_state(self):
            return self._line('dtr', super()._update_dtr_state)

        def _update_rts_state(self):
            return self._line('rts', super()._update_rts_state)

        def __del__(self):
            # Session owns cleanup. A failed close must not silently be retried
            # later by Serial/IOBase destruction; preserve its unconfirmed state.
            pass
    return AuditedSerial


class UartEndpoint:
    def __init__(self, rx, expected, factory, checker):
        self.receiver, self.expected, self.checker = rx, expected, checker
        self.serial = factory(port=None, baudrate=115200, timeout=0, write_timeout=0,
                              exclusive=True, rtscts=False, dsrdtr=False, xonxoff=False)
        self.serial.dtr = False; self.serial.rts = False
        self.open_attempts = self.close_attempts = 0
        self.opened = False
        self.readable = False

    def open(self):
        self.checker(self.receiver, self.expected)
        if self.open_attempts:
            raise RuntimeError('UART cannot reopen')
        self.serial.port = self.expected['by_id']
        self.open_attempts += 1
        self.serial.open()
        self.opened = True
        self.checker(self.receiver, self.expected)
        # Compare the actual opened fd to the metadata verified before opening.
        st = os.fstat(self.serial.fileno())
        if [st.st_dev, st.st_ino, st.st_rdev] != self.expected['node_fingerprint']:
            raise ValueError('Opened fd differs from verified USB node')

    def close_receiver(self):
        if self.close_attempts:
            raise RuntimeError('No automatic close retries')
        self.close_attempts += 1
        self.serial.close()
        aux = [getattr(self.serial, name, None) for name in
               ('fd', 'pipe_abort_read_r', 'pipe_abort_read_w', 'pipe_abort_write_r', 'pipe_abort_write_w')]
        return self.serial.is_open is False and all(fd is None for fd in aux)

    def details(self):
        return dict(open_attempts=self.open_attempts, close_attempts=self.close_attempts,
            dtr_requested=False, rts_requested=False,
            actual_line_update_attempts=copy.deepcopy(getattr(self.serial, 'line_requests', [])),
            serial_settings=self.serial.get_settings(),
            open_flush_suppressed=getattr(self.serial, 'open_flush_suppressed', None),
            is_open=self.serial.is_open, fd=getattr(self.serial, 'fd', None),
            electrical_transients_or_resets_excluded=False)

    def dispose_fixture(self):
        # Physical resources are never silently retried by fixture cleanup.
        pass


class StorageLimit(RuntimeError):
    pass


class StorageGuard:
    def __init__(self, root, journal, clock, *, disk_usage=shutil.disk_usage, record=None, lock=None):
        self.root, self.journal, self.clock, self.disk_usage = Path(root), journal, clock, disk_usage
        self.started = clock(); self.checked = None
        self.record, self.lock = record, lock

    def check(self, *, final_extra=0):
        if self.lock is not None:
            with self.lock:
                return self._check(final_extra=final_extra)
        return self._check(final_extra=final_extra)

    def _check(self, *, final_extra=0):
        now = self.clock()
        raw = sum(f.tell() for f in self.journal.raw.values())
        if not final_extra and raw >= STORAGE['max_raw_bytes']:
            raise StorageLimit('raw_byte_limit')
        if not final_extra and now-self.started >= STORAGE['max_connection_ns']:
            raise StorageLimit('connection_duration_limit')
        if final_extra or self.checked is None or now-self.checked >= 250_000_000:
            self.checked = now
            free = self.disk_usage(self.root).free
            if free-final_extra < STORAGE['reserve_bytes']:
                raise StorageLimit('free_space_reserve')
            size = sum(p.stat().st_size for p in self.root.rglob('*') if p.is_file())
            if size+final_extra >= STORAGE['max_bundle_bytes']:
                raise StorageLimit('bundle_byte_limit')
            if self.record is not None:
                self.record('storage_check', free_bytes=free, raw_bytes=raw, size_bytes=size,
                            final_extra=final_extra, guard_started_ns=self.started)


class UartSession(PtySession):
    """Share v4 command/signals/context lifecycle; override only transport ownership."""
    def __init__(self, output, plan, *, authorization_reference=None, notifier=None,
                 test_backend=None, clock=None):
        from presence_v4_audio import RecordingNotifier
        self._state_lock = threading.RLock()
        self._startup_stop = threading.Event()
        self._startup_reader = None
        validate_uart_plan(plan, execution=test_backend is None)
        exploratory = plan.get('eligibility_revision') == EXPLORATORY_ELIGIBILITY
        if test_backend is None:
            check_authorization(authorization_reference)
            if notifier is not None and notifier.name == RecordingNotifier.name:
                raise ValueError('Physical operation requires configured laptop audio; audibility remains human-declared')
            if clock is not None:
                raise ValueError('No synthetic clock in physical execution')
            out = Path(output).resolve()
            if not out.is_relative_to(ROOT/'results/local'):
                raise ValueError('New physical output must be inside results/local')
            snapshots = preflight_uart(plan)
            checker = revalidate
        else:
            out = Path(output)
            snapshots, checker = test_backend['identities'], test_backend['checker']
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
        transport = dict(implementation_base_commit='414b461410fec83f83a149d6e88cf323bb69fe96',
            backend='UART' if test_backend is None else 'synthetic_serial_backend', identities=snapshots,
            authorization_reference=authorization_reference if test_backend is None else None,
            pyserial_version=serial.__version__, serialposix_sha256=digest(Path(serial.serialposix.__file__)),
            serialutil_sha256=digest(Path(serial.serialutil.__file__)),
            storage_policy=STORAGE, dtr_requested=False, rts_requested=False,
            decision_clock_sampled_after_raw_persistence=True,
            electrical_behavior_verified=False, installed_firmware_attested=False,
            sources={name:digest(ROOT/name) for name in ('src/presence_v4_uart.py','src/preserving_serial.py',
                'tools/campana_presencia_uart_v4.py','config/pyserial_uart_v4.lock.json')})
        if exploratory:
            transport['initial_free_bytes_observed'] = initial_free
        self.journal = V4Journal(out, plan, allow_physical=True,
            evidence_type='synthetic_fixture' if test_backend is not None else 'physical_capture',
            extra_provenance=transport, decision_clock=self.clock)
        self.machine = self.journal.machine
        try:
            if notifier is None and test_backend is None:
                from presence_v4_audio import LaptopNotifier
                notifier = LaptopNotifier(out/'audio')
            self.notifier = notifier or RecordingNotifier()
        except BaseException:
            self.journal.close_files()
            raise
        self.endpoints, self.started_signals = {}, set()
        self.read_loop_stopped = self.receipt_persisted = self.storage_failed = self.finalized = False
        self.notifier_finished = self.finalization_attempted = False
        self.guard = StorageGuard(out, self.journal, self.clock, disk_usage=disk,
            record=self.command if exploratory else None, lock=self._state_lock if exploratory else None)
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
                    binding = {}
                    if exploratory:
                        st = os.fstat(endpoint.serial.fileno())
                        binding['identity_binding'] = dict(identity=copy.deepcopy(snapshots[rx]),
                            opened_fingerprint=[st.st_dev, st.st_ino, st.st_rdev])
                    self.command('opened', receiver=rx, serial_configuration=endpoint.details(), **binding)
                    endpoint.readable = True
                if self._startup_reader is None:
                    self._startup_reader = threading.Thread(target=self._pump_startup, name='v4-uart-startup-reader')
                    self._startup_reader.start()
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

    def command(self, op, **data):
        with self._state_lock:
            return super().command(op, **data)

    def _pump_startup(self):
        # Drain RX-01 immediately while the caller configures RX-02. The shared
        # journal/reducer stays serialized; no slots can be requested until init
        # finishes and the startup reader has actually joined.
        try:
            while not self._startup_stop.is_set():
                with self._state_lock:
                    self.read_ready()
                    self.command('tick')
                    if self.machine.fatal:
                        return
                self._startup_stop.wait(.001)
        except BaseException as exc:
            self._record('io_error', detail='startup_reader: '+type(exc).__name__+': '+str(exc))

    def _stop_startup_reader(self):
        self._startup_stop.set()
        if self._startup_reader is not None:
            self._startup_reader.join()  # completion observed, never inferred from a timeout

    def _record(self, op, **data):
        with self._state_lock:
            try:
                self.command(op, **data)
            except OSError:
                # Evidence storage failure must not prevent releasing either port.
                self.storage_failed = True
                if not self.journal.last_command_applied:
                    self.machine.apply(op, self.clock(), **data)

    def read_ready(self, receivers=None, close_budget=False):
        if self.read_loop_stopped:
            raise RuntimeError('Reader already stopped')
        try:
            self.guard.check()
        except (StorageLimit, OSError) as exc:
            self.command('storage_error', detail=str(exc)); return
        selected = self.endpoints if receivers is None else {rx:self.endpoints[rx] for rx in receivers}
        try:
            fds = {e.serial.fileno():rx for rx,e in selected.items() if e.readable and rx not in self.machine.closed}
            ready, _, _ = select.select(list(fds), [], [], 0)
        except (OSError, ValueError) as exc:
            self.command('io_error', detail=str(exc)); return
        for fd in ready:
            if self.machine.fatal:
                break
            rx = fds[fd]
            limit = min(16384, POLICY['close_bytes']-self.machine.close_bytes[rx]) if close_budget else 16384
            if limit <= 0:
                continue
            start = self.clock()
            try:
                chunk = self.endpoints[rx].serial.read(limit)
            except (OSError, ValueError) as exc:
                self.command('io_error', receiver=rx, detail=str(exc)); break
            end = self.clock()
            if chunk:
                # Persist the entire returned chunk, including a budget crossing.
                self.command('chunk', receiver=rx, chunk=chunk, started_ns=start, returned_ns=end)
            else:
                self.command('reader_ended', receiver=rx); break

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

    def finalize(self):
        if self.finalization_attempted:
            raise RuntimeError('Finalization is attempted once; partial artifacts are preserved')
        self.finalization_attempted = True
        if not self.read_loop_stopped:
            self.close()
        if self.storage_failed:
            raise RuntimeError('Storage failed; no finalized bundle claim')
        deadline = time.monotonic()+15
        while any(c['ack_ns'] is None for c in self.machine.signals):
            self.pump_signals()
            if time.monotonic() >= deadline:
                raise RuntimeError('Notification result unconfirmed')
            time.sleep(.001)
        self._finish_notifier()
        import json
        runtime=dict(transport='UART' if self.machine.evidence_type=='physical_capture' else 'synthetic_serial_backend',
            receivers={rx:e.details() for rx,e in self.endpoints.items()},
            notifier=self.notifier.name, audibility_verified_automatically=False,
            bubblewrap_isolation_claimed=False, retry_count=0)
        runtime['startup_reader_stopped'] = self._startup_reader is None or not self._startup_reader.is_alive()
        estimated = sum(len(json.dumps(value,ensure_ascii=False,allow_nan=False,indent=2).encode())+1
                        for value in (dict(state=self.machine.summary(),runtime=runtime),self.machine.events))+65536
        try:
            self.guard.check(final_extra=estimated)
        except StorageLimit:
            # Keep raw/journal/receipt. A failed budget is not an approved bundle.
            self.journal.close_files()
            raise
        self.journal.finalize(runtime)
        self.finalized = True

    def _finish_notifier(self):
        if not self.notifier_finished:
            self.notifier_finished = True
            self.notifier.finish()

    def __exit__(self, kind, value, traceback):
        try:
            if kind is not None:
                self._record('interrupt', detail=kind.__name__+': '+str(value))
            if not self.read_loop_stopped:
                self.close()
            if not self.finalization_attempted:
                self.finalize()
        finally:
            self.journal.close_files()
            self._finish_notifier()
