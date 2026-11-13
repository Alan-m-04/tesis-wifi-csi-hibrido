"""DEVREP uses the existing UART loop/close and checkpoint decorator, without reopening."""
import copy
import os
from pathlib import Path
import shutil
import threading
import time
from controlled_capture import ROOT
from persistent_presence_v4 import POLICY
from presence_v4_uart import (UartEndpoint,StorageGuard,StorageLimit,STORAGE,audited_serial_type,
    check_authorization,verify_serial_runtime,identity,revalidate)
from rx02_c03.uart import C03UartSession,Rx02LaptopNotifier
from rx02_devrep_r4_n01.contract import RECEIVERS,PORTS,validate_plan
from rx02_devrep_r4_n01.journal import DevrepJournal,audit_devrep_replay
from rx02_checkpoint_journal import CheckpointJournal,PERSISTENCE_REVISION,LIMITS,policy_metadata
from presence_v4_journal import digest,write_new
import json


def preflight_rx02(plan):
    validate_plan(plan,allow_physical=True,execution=True)
    snapshot=identity('RX-02')
    if snapshot['serial']!=RECEIVERS['RX-02'] or snapshot['by_id']!=PORTS['RX-02']:
        raise ValueError('Fixed RX-02 metadata required')
    return {'RX-02':snapshot}


class DevrepUartSession(C03UartSession):
    def __init__(self, output, plan, *, authorization_reference=None, notifier=None,
                 test_backend=None, clock=None, entry_evidence=None):
        from presence_v4_audio import RecordingNotifier
        self._state_lock = threading.RLock()
        self._startup_stop = threading.Event()
        self._startup_reader = None
        validate_plan(plan, allow_physical=True, execution=test_backend is None)
        if test_backend is None:
            from rx02_devrep_r4_n01.series import validate_entry
            validate_entry(entry_evidence, plan, current_boot=True)
            check_authorization(authorization_reference)
            import json,hashlib
            expected=hashlib.sha256((json.dumps(plan,ensure_ascii=False,indent=2)+'\n').encode()).hexdigest()
            if (plan.get('authorization_granted') is not True or plan.get('review_only') is not False or
                plan.get('review_state')!='authorized_single_attempt' or
                authorization_reference!=plan['connection_id']+':'+expected):
                raise ValueError('New explicit single DEVREP authorization bound to plan required')
            if Path(output).resolve()!=ROOT/plan['output_new']:
                raise ValueError('Only the exclusive DEVREP output is permitted')
            if notifier is not None and notifier.name == RecordingNotifier.name:
                raise ValueError('Physical operation requires configured laptop audio; audibility remains human-declared')
            if clock is not None:
                raise ValueError('No synthetic clock in physical execution')
            out = Path(output).resolve()
            if not out.is_relative_to(ROOT/'results/local'):
                raise ValueError('New physical output must be inside results/local')
            from rx02_devrep_r4_n01.series import validate_setup_snapshot
            validate_setup_snapshot(plan)
            snapshots = preflight_rx02(plan)
            if entry_evidence is None or entry_evidence['identities'] != snapshots:
                raise ValueError('R4 receipt identity changed immediately before opening')
            checker = revalidate
        else:
            out = Path(output)
            snapshots, checker = test_backend['identities'], test_backend['checker']
            if set(snapshots) != set(RECEIVERS):
                raise ValueError('Synthetic topology must also contain RX-02 only')
        self.clock = clock or time.monotonic_ns
        if test_backend is None:
            from rx02_devrep_r4_n01.series import predecessor_context,boot_id,wait_for_open_target
            series_context=predecessor_context(plan)
            current_boot=boot_id()
            if series_context is not None and series_context['host_boot_id']!=current_boot:
                raise ValueError('Host boot changed; monotonic interval is not comparable')
            wait_for_open_target(series_context,self.clock)
        else:
            series_context=test_backend.get('series_context')
            current_boot=test_backend.get('host_boot_id','synthetic-host')
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
        transport = dict(series_context=series_context,host_boot_id=current_boot,implementation_base_commit='9b28addc221468ed1c38e6480a6cf153e5a00c70',
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
        transport['entry_evidence'] = copy.deepcopy(entry_evidence)
        self.journal = DevrepJournal(out, plan, allow_physical=True,
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


class DevrepSession(DevrepUartSession):
    """Reuse transport/error/close ownership; install revision before service.

    Inherited UART loop and actual-close proof are unchanged. This adapter
    requires a per-connection grant and never starts the next connection.
    """
    def __init__(self,output,plan,**kwargs):
        if plan.get('persistence_revision')!=PERSISTENCE_REVISION:
            raise ValueError('Explicit persistence revision 2 required; no implicit migration')
        super().__init__(output,plan,**kwargs)
        try:
            self.journal=CheckpointJournal(self.journal)
        except BaseException:
            try:self._record('storage_error',detail='checkpoint activation failed');self.close()
            finally:self.journal.close_files();self._finish_notifier()
            raise


def audit_devrep(directory):
    """Validate revision metadata AND unchanged historical acceptance reducer."""
    root=Path(directory)
    metadata=json.loads((root/'persistence-policy.json').read_text())
    plan=json.loads((root/'plan.json').read_text())
    if (plan.get('persistence_revision')!=PERSISTENCE_REVISION or
        metadata!=policy_metadata(digest(root/'plan.json'))):
        raise ValueError('Checkpoint policy/source provenance mismatch')
    report=audit_devrep_replay(root)
    status=json.loads((root/'checkpoint-status.json').read_text())
    if (status['revision']!=PERSISTENCE_REVISION or status['limits']!=LIMITS or
        status['final_operations']!=report['operations'] or status['last_durable_seq']!=report['operations']-1 or
        status['pending_ops_bytes']!=0 or status['max_pending_ops_bytes']>LIMITS['pending_ops_bytes'] or
        status['operations_prefix_bytes']!=(root/'operations.jsonl').stat().st_size or
        status['operations_sha256']!=digest(root/'operations.jsonl') or not status['no_inflight_writer'] or
        status['events']>LIMITS['max_events'] or status['lines']>LIMITS['max_lines'] or report['operations']>LIMITS['max_operations']):
        raise ValueError('Checkpoint final durability/resource evidence mismatch')
    runtime=json.loads((root/'summary.json').read_text())['runtime']
    if runtime.get('persistence_revision')!=PERSISTENCE_REVISION:
        raise ValueError('Runtime persistence revision missing')
    from rx02_devrep_r4_n01.contract import INTEGRATION_REVISION
    report['integration_revision']=INTEGRATION_REVISION
    report['persistence_revision']=PERSISTENCE_REVISION
    report['persistence_status']=status
    schedule=report['state']['devrep_schedule']
    report['series_can_continue']=bool(schedule['administrative_ok'] and schedule['complete'] and
        report['state']['fatal'] is None and report['state']['closed'].get('RX-02',{}).get('confirmed') and
        len(report['exploratory_eligibility']['windows'])==2 and all(w['eligible'] for w in report['exploratory_eligibility']['windows']))
    if report['state']['evidence_type']=='physical_capture':
        from rx02_devrep_r4_n01.series import verify_recorded_predecessor
        verify_recorded_predecessor(root,report)
    return report
