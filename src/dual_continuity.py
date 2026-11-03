"""continuity-dual-1: observational transport diagnosis, never presence/v4 approval."""
import copy
import hashlib
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import threading
import time

from availability_window import LineFramer
import presence_v4_uart as transport
from presence_v4_journal import digest, write_new

PROTOCOL = 'continuity-dual-1'
POLICY = dict(duration_ns=60_000_000_000, incident_ns=1_000_000_000,
              poll_ns=10_000_000, read_bytes=16384)
SOURCES = ('src/dual_continuity.py', 'tools/diagnostico_continuidad_dual.py',
           'src/presence_v4_uart.py', 'src/preserving_serial.py',
           'src/availability_window.py', 'src/capture_csi_multi.py',
           'src/capture_csi.py', 'config/pyserial_uart_v4.lock.json')
FORBIDDEN_USES = dict(eligible_windows=False, presence_labels=False,
                      calibration=False, training=False, production=False)


def clocks():
    return dict(monotonic_ns=time.monotonic_ns(),
                boottime_ns=time.clock_gettime_ns(time.CLOCK_BOOTTIME),
                realtime_ns=time.time_ns())


def validate_plan(plan, *, execution=False):
    required = dict(protocol=PROTOCOL, policy=POLICY, ports=transport.PORTS,
                    receivers=transport.capture.RECEIVERS, baud=115200,
                    storage_policy=transport.STORAGE, permitted_uses=FORBIDDEN_USES)
    if set(plan) != set(required) | {'diagnostic_id', 'operator', 'declarations'}:
        raise ValueError('Exact diagnostic plan fields required; no slots or v4 policies')
    if any(plan[k] != v for k, v in required.items()):
        raise ValueError('Fixed continuity protocol, profile, identities and storage required')
    if set(plan['declarations']) != {'mounting', 'power', 'host', 'environment'}:
        raise ValueError('Explicit diagnostic declarations required')
    for value in (plan['diagnostic_id'], plan['operator'], *plan['declarations'].values()):
        if not isinstance(value, str) or not value.strip():
            raise ValueError('Nonempty declarations required')
        if execution and 'PENDIENTE' in value.upper():
            raise ValueError('Current declarations pending; no physical authorization implied')
    return copy.deepcopy(plan)


def preflight(plan):
    """Metadata only. Never constructs a serial object."""
    validate_plan(plan)
    resolved = transport.capture.resolve_ports(list(transport.PORTS), transport.PORTS)
    identities = {rx: transport.identity(rx) for rx in transport.PORTS}
    if any(identities[rx]['resolved'] != resolved[rx] for rx in identities):
        raise ValueError('Identity changed during metadata preflight')
    return identities


class Journal:
    def __init__(self, output, metadata, plan):
        self.root = Path(output)
        self.root.mkdir(parents=True, exist_ok=False)
        self.raw, self.ops, self.seq = {}, None, 0
        try:
            write_new(self.root/'plan.json', plan)
            write_new(self.root/'metadata.json', metadata)
            # Exclusive creation consumes authorization even when opening fails.
            write_new(self.root/'authorization-consumed.json', dict(
                reference=metadata['authorization_reference'], consumed=True,
                evidence_type=metadata['evidence_type'], reattempt_permitted=False))
            for rx in transport.PORTS:
                self.raw[rx] = (self.root/(rx.lower()+'.serial.log')).open('xb')
            self.ops = (self.root/'ledger.jsonl').open('x')
            fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
            try: os.fsync(fd)
            finally: os.close(fd)
        except BaseException:
            self.close_files()
            raise

    def record(self, kind, **data):
        event = dict(seq=self.seq, kind=kind, clocks=clocks(), **data)
        if kind == 'dual_observation_started':
            event['deadline_ns'] = event['clocks']['monotonic_ns']+POLICY['duration_ns']
        self.ops.write(json.dumps(event, allow_nan=False, sort_keys=True)+'\n')
        self.ops.flush(); os.fsync(self.ops.fileno())
        self.seq += 1
        return event

    def read(self, rx, chunk, started, returned):
        raw = self.raw[rx]
        offset = raw.tell()
        persist_started = clocks()
        if raw.write(chunk) != len(chunk):
            raise OSError('Short raw write')
        raw.flush(); os.fsync(raw.fileno())
        persisted = clocks()
        return dict(receiver=rx, offset=offset, size=len(chunk),
                    sha256=hashlib.sha256(chunk).hexdigest(), started=started,
                    returned=returned, persist_started=persist_started, persisted=persisted)

    def close_files(self):
        for f in (*self.raw.values(), self.ops):
            if f is not None and not f.closed:
                f.close()


def analyze(root):
    """Reconstruct only host/firmware observations, verifying byte and row references."""
    root = Path(root)
    plan = validate_plan(json.loads((root/'plan.json').read_text()))
    metadata = json.loads((root/'metadata.json').read_text())
    if metadata['evidence_type'] not in ('physical_capture', 'synthetic_fixture'):
        raise ValueError('Unknown evidence type')
    for rx, expected_serial in transport.capture.RECEIVERS.items():
        ident = metadata['identities'][rx]
        if (ident['serial'] != expected_serial or ident['by_id'] != transport.PORTS[rx] or
                ident['vid'] != '1a86' or ident['pid'] != '55d3' or ident['bus'] != 'usb'):
            raise ValueError('Identity provenance changed')
    consumed = json.loads((root/'authorization-consumed.json').read_text())
    if consumed != dict(reference=metadata['authorization_reference'], consumed=True,
                        evidence_type=metadata['evidence_type'], reattempt_permitted=False):
        raise ValueError('Authorization provenance changed')
    if metadata['evidence_type'] == 'physical_capture':
        validate_plan(plan, execution=True)
        transport.check_authorization(metadata['authorization_reference'])
    events = [json.loads(line) for line in (root/'ledger.jsonl').read_text().splitlines()]
    framers = {rx: LineFramer(rx) for rx in transport.PORTS}
    raw = {rx: (root/(rx.lower()+'.serial.log')).read_bytes() for rx in transport.PORTS}
    states = {rx: dict(bytes=0, reads=0, lines=[], rows=[], incidents=[],
                      opened_ns=None, last_row_ns=None, last_service_ns=None,
                      max_service_gap_ns=0, max_read_gap_ns=0, last_read_ns=None,
                      host_service_incidents=[],
                      max_read_duration_ns=0, max_persistence_ns=0,
                      max_persistence_wait_ns=0, max_processing_ns=0,
                      callback_transitions=[]) for rx in transport.PORTS}
    opened = set(); closed = set(); begin = end = dual = None
    previous_now = None

    def gap(state, now):
        anchor = state['last_row_ns'] if state['last_row_ns'] is not None else state['opened_ns']
        if anchor is None or now-anchor <= POLICY['incident_ns']:
            return
        if not state['incidents'] or state['incidents'][-1]['recovered_ns'] is not None:
            state['incidents'].append(dict(anchor_ns=anchor, first_observed_ns=now,
                recovered_ns=None, duration_ns=now-anchor, quality_approval=False))
        else:
            state['incidents'][-1]['duration_ns'] = now-anchor

    for seq, event in enumerate(events):
        if event['seq'] != seq:
            raise ValueError('Ledger sequence changed')
        kind = event['kind']; rx = event.get('receiver')
        now = event['clocks']['monotonic_ns']
        if previous_now is not None and now < previous_now:
            raise ValueError('Ledger clock moved backwards')
        previous_now = now
        state = states.get(rx)
        if kind == 'begin':
            if begin is not None: raise ValueError('Duplicate begin')
            begin = event
        elif kind == 'opened':
            if rx in opened: raise ValueError('Duplicate opening')
            opened.add(rx); state['opened_ns'] = now; state['last_service_ns'] = now
        elif kind == 'dual_observation_started':
            if dual is not None or len(opened) != 2:
                raise ValueError('Invalid common observation start')
            dual = event
            if event['deadline_ns'] != now+POLICY['duration_ns']:
                raise ValueError('Common deadline changed')
        elif kind == 'service':
            if rx not in opened or rx in closed: raise ValueError('Service outside open lifecycle')
            if state['last_service_ns'] is not None:
                delta = now-state['last_service_ns']
                state['max_service_gap_ns'] = max(state['max_service_gap_ns'], delta)
                if delta > POLICY['incident_ns']:
                    state['host_service_incidents'].append(dict(
                        from_ns=state['last_service_ns'], to_ns=now, gap_ns=delta, ledger_seq=seq))
            state['last_service_ns'] = now
            gap(state, now)
        elif kind == 'read':
            if rx not in opened or rx in closed: raise ValueError('Read outside open lifecycle')
            start, ret = event['started']['monotonic_ns'], event['returned']['monotonic_ns']
            ps, persisted = event['persist_started']['monotonic_ns'], event['persisted']['monotonic_ns']
            if not start <= ret <= ps <= persisted <= event['processed']['monotonic_ns'] <= now:
                raise ValueError('Inconsistent read/persistence/processing times')
            offset, size = event['offset'], event['size']
            chunk = raw[rx][offset:offset+size]
            if (offset != state['bytes'] or size <= 0 or len(chunk) != size or
                    hashlib.sha256(chunk).hexdigest() != event['sha256']):
                raise ValueError('Raw read coverage/hash changed')
            lines = framers[rx].feed(chunk, state['reads'],
                                   dict(started_ns=str(start), returned_ns=str(ret)))
            if lines != event['lines']:
                raise ValueError('Row references or parsing changed')
            state['bytes'] += size; state['reads'] += 1
            state['max_read_duration_ns'] = max(state['max_read_duration_ns'], ret-start)
            state['max_persistence_ns'] = max(state['max_persistence_ns'], persisted-ps)
            state['max_persistence_wait_ns'] = max(state['max_persistence_wait_ns'], ps-ret)
            state['max_processing_ns'] = max(state['max_processing_ns'], event['processed']['monotonic_ns']-persisted)
            if state['last_read_ns'] is not None:
                state['max_read_gap_ns'] = max(state['max_read_gap_ns'], ret-state['last_read_ns'])
            state['last_read_ns'] = ret
            gap(state, ret)
            for line in lines:
                ref = dict(line, ledger_seq=seq)
                state['lines'].append(ref)
                if line['kind'] != 'row': continue
                if state['rows']:
                    previous = state['rows'][-1]
                    delta = line['id']-previous['id']
                    local = (line['local_timestamp']-previous['local_timestamp']) % 2**32
                    drops = line['queue_drops']-previous['queue_drops']
                    state['callback_transitions'].append(dict(
                        from_line=previous['line_1based'], to_line=line['line_1based'],
                        host_return_gap_ns=ret-int(previous['returned_ns']),
                        callback_id_delta=delta, callback_restart=delta <= 0,
                        callback_gap=delta != 1, local_delta_us_mod32=local,
                        local_gap_over_1s=local > 1_000_000,
                        local_discontinuity=not 0 < local <= 10_000_000,
                        queue_drops_delta=drops, queue_drops_changed=drops != 0))
                if state['incidents'] and state['incidents'][-1]['recovered_ns'] is None:
                    state['incidents'][-1].update(recovered_ns=ret, recovery_line=line['line_1based'],
                        duration_ns=ret-state['incidents'][-1]['anchor_ns'])
                state['last_row_ns'] = ret; state['rows'].append(ref)
        elif kind == 'closed':
            if rx in closed: raise ValueError('Close repeated')
            if event['confirmed'] and (event['details'].get('is_open') is not False or
                    event['details'].get('fd') is not None or event['details'].get('close_attempts') != 1):
                raise ValueError('Unproven closure confirmation')
            closed.add(rx)
        elif kind == 'end':
            if end is not None: raise ValueError('Duplicate end')
            if closed != set(transport.PORTS): raise ValueError('End without both close attempts')
            end = event
            for st in states.values():
                stop_ns = event['acquisition_stopped']['monotonic_ns']
                gap(st, stop_ns)
                if st['last_service_ns'] is not None:
                    delta = stop_ns-st['last_service_ns']
                    st['max_service_gap_ns'] = max(st['max_service_gap_ns'], delta)
                    if delta > POLICY['incident_ns']:
                        st['host_service_incidents'].append(dict(from_ns=st['last_service_ns'],
                            to_ns=stop_ns, gap_ns=delta, ledger_seq=seq, boundary='observation_end'))
        elif kind != 'storage_check':
            raise ValueError('Unknown diagnostic ledger event')
    if begin is None or end is None:
        raise ValueError('Incomplete diagnostic ledger')
    if begin['seq'] != 0:
        raise ValueError('Begin must precede acquisition')
    for rx, state in states.items():
        if len(raw[rx]) != state['bytes']: raise ValueError('Unreferenced raw bytes')
        framer = framers[rx]
        state['tail'] = dict(byte_offset=framer.offset-framer.length, byte_length=framer.length,
            sha256=framer.hash.hexdigest(), first_read=framer.first,
            last_read_index=state['reads']-1 if framer.length else None)
    first, last = begin['clocks'], end['acquisition_stopped']
    mono = last['monotonic_ns']-first['monotonic_ns']
    boot = last['boottime_ns']-first['boottime_ns']
    wall = last['realtime_ns']-first['realtime_ns']
    dual_elapsed = None if dual is None else last['monotonic_ns']-dual['clocks']['monotonic_ns']
    receipt = json.loads((root/'closure.json').read_text())
    expected_receipt = {e['receiver']: dict(confirmed=e['confirmed'], details=e['details'], error=e['error'],
                        resource_observed_open_before_close=e['resource_observed_open_before_close'])
                        for e in events if e['kind']=='closed'}
    if receipt != expected_receipt or set(receipt) != set(transport.PORTS):
        raise ValueError('Closure receipt mismatch')
    physically_observed_open = sorted(set(opened) | {rx for rx, item in receipt.items()
                                                    if item['resource_observed_open_before_close']})
    return dict(schema=PROTOCOL+'-report-1', evidence_type=metadata['evidence_type'],
        acquisition=dict(physical_UART_opened=metadata['evidence_type']=='physical_capture' and bool(physically_observed_open),
                         opened_receivers=physically_observed_open),
        audit_activity=dict(physical_UART_opened=False),
        diagnostic_id=plan['diagnostic_id'], permitted_uses=FORBIDDEN_USES,
        quality_approval=False, eligible_windows=[], presence_labels=[],
        completed_nominal_duration=not end['error'] and dual_elapsed is not None and dual_elapsed >= POLICY['duration_ns'],
        dual_observation=dict(start=dual['clocks'] if dual else None,
                              deadline_ns=dual['deadline_ns'] if dual else None,
                              actual_elapsed_ns=dual_elapsed),
        fatal=end['error'], both_ports_closed_confirmed=all(x['confirmed'] for x in receipt.values()),
        elapsed=dict(monotonic_ns=mono, boottime_ns=boot, realtime_ns=wall,
                     boottime_minus_monotonic_ns=boot-mono, realtime_minus_monotonic_ns=wall-mono),
        receivers=states, closure=receipt,
        interpretation='Host observations and firmware counters; RF loss not demonstrated')


def audit(root):
    root = Path(root)
    manifest = json.loads((root/'manifest.json').read_text())
    expected = {'plan.json', 'metadata.json', 'authorization-consumed.json', 'ledger.jsonl',
                'rx-01.serial.log', 'rx-02.serial.log', 'closure.json', 'report.json'}
    if set(manifest) != expected:
        raise ValueError('Manifest coverage changed')
    if any(digest(root/name) != sha for name, sha in manifest.items()):
        raise ValueError('Manifest hash mismatch')
    report = analyze(root)
    if report != json.loads((root/'report.json').read_text()):
        raise ValueError('Diagnostic replay mismatch')
    return dict(integrity_ok=True, replay_ok=True, audit_activity=dict(physical_UART_opened=False), report=report)


class ContinuitySession:
    """One independent nonblocking reader per RX; no interactive/acoustic loop."""
    def __init__(self, output, plan, *, authorization_reference=None, test_backend=None):
        self.plan = validate_plan(plan, execution=test_backend is None)
        out = Path(output).resolve()
        if test_backend is None:
            transport.check_authorization(authorization_reference)
            if not out.is_relative_to(transport.ROOT/'results/local'):
                raise ValueError('New physical output must be inside results/local')
            snapshots, checker = preflight(plan), transport.revalidate
        else:
            snapshots, checker = test_backend['identities'], test_backend['checker']
        serial = transport.verify_serial_runtime()
        self.disk = shutil.disk_usage if test_backend is None else test_backend['disk_usage']
        ancestor = out.parent
        while not ancestor.exists(): ancestor = ancestor.parent
        if self.disk(ancestor).free < transport.STORAGE['initial_free_bytes']:
            raise transport.StorageLimit('initial_free_bytes')
        metadata = dict(evidence_type='physical_capture' if test_backend is None else 'synthetic_fixture',
            authorization_reference=authorization_reference if test_backend is None else None,
            identities=snapshots, sources={name:digest(transport.ROOT/name) for name in SOURCES},
            electrical_transients_or_resets_excluded=False, installed_firmware_attested=False)
        metadata['git_commit'] = subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'], cwd=transport.ROOT, text=True).strip()
        metadata['working_tree_status'] = subprocess.check_output(
            ['git', 'status', '--porcelain'], cwd=transport.ROOT, text=True)
        self.journal = Journal(out, metadata, self.plan)
        self.lock = threading.RLock(); self.stop = threading.Event()
        self.endpoints, self.threads, self.framers, self.reads = {}, [], {}, {}
        self.error = None; self.finished = False; self.storage_failed = False
        self.guard = transport.StorageGuard(out, self.journal, time.monotonic_ns,
            disk_usage=self.disk, record=self.journal.record, lock=self.lock)
        factory = transport.audited_serial_type(serial.Serial if test_backend is None else test_backend['serial_type'])
        try:
            for rx in transport.PORTS:
                self.endpoints[rx] = transport.UartEndpoint(rx, snapshots[rx], factory, checker)
                self.framers[rx] = LineFramer(rx); self.reads[rx] = 0
            begin = self.journal.record('begin')
            self.deadline = begin['clocks']['monotonic_ns']+POLICY['duration_ns']
            for rx, endpoint in self.endpoints.items():
                if self.stop.is_set() or time.monotonic_ns() >= self.deadline: break
                with self.lock: self.guard.check()
                endpoint.open()
                with self.lock: self.journal.record('opened', receiver=rx)
                thread = threading.Thread(target=self._reader, args=(rx,), name='continuity-'+rx)
                self.threads.append(thread); thread.start()
            with self.lock:
                if not self.stop.is_set():
                    if len(self.threads) != 2 or time.monotonic_ns() >= self.deadline:
                        raise TimeoutError('Dual startup not completed within 60 s; no retry')
                    # Sampling is inside record, so the ledger owns the exact deadline.
                    self.deadline = self.journal.record('dual_observation_started')['deadline_ns']
        except BaseException as exc:
            self._fail(exc)
            self.finish()
            raise

    def _fail(self, exc):
        self.stop.set()
        with self.lock:
            if self.error is None: self.error = type(exc).__name__+': '+str(exc)

    def _reader(self, rx):
        endpoint = self.endpoints[rx]
        try:
            while not self.stop.is_set():
                with self.lock:
                    if self.stop.is_set() or time.monotonic_ns() >= self.deadline: break
                    self.guard.check()
                    self.journal.record('service', receiver=rx)
                if not select.select([endpoint.serial.fileno()], [], [], POLICY['poll_ns']/1e9)[0]: continue
                started = clocks()
                if self.stop.is_set() or started['monotonic_ns'] >= self.deadline: break
                chunk = endpoint.serial.read(POLICY['read_bytes'])
                returned = clocks()
                if not chunk: raise OSError(rx+': transport EOF')
                with self.lock:
                    evidence = self.journal.read(rx, chunk, started, returned)
                    lines = self.framers[rx].feed(chunk, self.reads[rx], dict(
                        started_ns=str(started['monotonic_ns']), returned_ns=str(returned['monotonic_ns'])))
                    self.reads[rx] += 1
                    self.journal.record('read', **evidence, lines=lines, processed=clocks())
                    self.guard.check()
        except BaseException as exc:
            self._fail(exc)

    def run(self):
        try:
            while not self.stop.is_set() and time.monotonic_ns() < self.deadline:
                self.stop.wait(.01)
        except BaseException as exc:
            self._fail(exc)
        return self.finish()

    def finish(self):
        if self.finished: return self.result
        self.stop.set()
        for thread in self.threads: thread.join()
        stopped = clocks()
        receipt = {}
        # Cleanup never depends on successful logging or closing the other RX.
        for rx, endpoint in self.endpoints.items():
            confirmed, error = False, None
            resource_observed_open = endpoint.serial.is_open or getattr(endpoint.serial, 'fd', None) is not None
            try: confirmed = endpoint.close_receiver()
            except BaseException as exc:
                error = type(exc).__name__+': '+str(exc)
                if self.error is None: self.error = error
            try: details = endpoint.details()
            except BaseException as exc:
                details = dict(error=type(exc).__name__+': '+str(exc))
                confirmed = False
            receipt[rx] = dict(confirmed=confirmed, error=error, details=details,
                              resource_observed_open_before_close=resource_observed_open)
        try:
            for rx, result in receipt.items(): self.journal.record('closed', receiver=rx, **result)
            self.journal.record('end', error=self.error, acquisition_stopped=stopped)
            # Report repeats line references plus transitions. Reserve conservatively
            # from the actual ledger size, rather than assuming a small JSON report.
            final_budget = 1024**2 + 4*(self.journal.root/'ledger.jsonl').stat().st_size
            self.guard.check(final_extra=final_budget)
            write_new(self.journal.root/'closure.json', receipt)
            report = analyze(self.journal.root)
            write_new(self.journal.root/'report.json', report)
            self.guard.check(final_extra=1024**2)
            # No more ledger writes after the manifest is constructed.
            write_new(self.journal.root/'manifest.json', {
                p.name:digest(p) for p in self.journal.root.iterdir() if p.is_file()})
            self.result = audit(self.journal.root)
        except BaseException as exc:
            self.storage_failed = True
            # A fresh best-effort receipt never overwrites primary evidence.
            try: write_new(self.journal.root/'finalization-failure.json', dict(
                error=type(exc).__name__+': '+str(exc), closure=receipt,
                integrity_ok=False, acquisition_error=self.error))
            except BaseException: pass
            self.result = dict(integrity_ok=False, replay_ok=False,
                               fatal=self.error or str(exc), closure=receipt)
        finally:
            self.finished = True
            self.journal.close_files()
        return self.result
