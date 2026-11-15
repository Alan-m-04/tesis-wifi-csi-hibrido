# Derived from rx02_checkpoint_journal.py at 1bb7619; checkpoint algorithm unchanged.
"""Opt-in RX-02 persistence revision 2; historical modules remain frozen.

Raw bytes retain fsync-before-reducer. The operations journal checkpoints at
64 KiB and on operator/control barriers, rather than fsyncing every tick.
No claim of a wall-clock fsync deadline or power-loss recovery of a full bundle.
"""
import hashlib
import json
import os
from pathlib import Path

from rx02_diagnostic.uart import Rx02Session
from rx02_diagnostic.journal import audit_rx02
from presence_v4_journal import digest,write_new

ROOT=Path(__file__).resolve().parents[2]
PERSISTENCE_REVISION='rx02-raw-sync-control-checkpoint-2'
LIMITS=dict(pending_ops_bytes=65536,max_record_bytes=16384,max_chunk_bytes=16384,
            max_events=100000,max_lines=25000,max_operations=500000)
BARRIERS=frozenset(('begin','opened','request','declare','interrupt','io_error','storage_error',
                    'reader_ended','close_request','closed'))


def policy_metadata(plan_sha256):
    return dict(schema='tesis-rx02-persistence-policy-2',revision=PERSISTENCE_REVISION,
        plan_sha256=plan_sha256,limits=LIMITS,barrier_operations=sorted(BARRIERS),
        raw='write/flush/fsync each entire returned chunk before reducer decision sample',
        operations='write/flush every record; fsync before byte budget would be exceeded and after barrier operations',
        periodic_wall_clock_durability_guaranteed=False,
        power_loss='Up to 65536 bytes of operations since the last successful checkpoint may be lost/torn; raw may be ahead. No complete manifest means no eligible bundle.',
        receipt='Checkpoint all preceding operations before durable original close receipt; closed cue gated by receipt',
        sources={'src/rx02_diagnostic/checkpoint.py':dict(sha256=digest(Path(__file__)),bytes=Path(__file__).stat().st_size)})


class CheckpointJournal:
    """Bounded decorator around the unchanged, already-opened RX-02 journal."""
    def __init__(self,original):
        self.original=original
        self.machine,self.root,self.raw,self.ops=original.machine,original.root,original.raw,original.ops
        self.pending_ops_bytes=0;self.max_pending_ops_bytes=0;self.checkpoints=0
        self.raw_syncs=0;self.last_durable_seq=original.seq-1
        self.failed=False
        metadata=policy_metadata(digest(self.root/'plan.json'))
        write_new(self.root/'persistence-policy.json',metadata)

    @property
    def seq(self):return self.original.seq

    @property
    def last_command_applied(self):return self.original.last_command_applied

    def checkpoint(self):
        try:
            self.ops.flush();os.fsync(self.ops.fileno())
            self.last_durable_seq=self.seq-1;self.pending_ops_bytes=0;self.checkpoints+=1
        except BaseException:
            self.failed=True
            raise

    def _resource_error(self,reason,reference=None):
        # A rejected chunk has already been durably retained in the raw file.
        # No complete manifest can be produced after this bounded-resource stop.
        self.failed=True
        try:
            write_new(self.root/'resource-limit.json',dict(revision=PERSISTENCE_REVISION,
                reason=reason,unprocessed_raw_reference=reference,finalized=False))
        except OSError:
            pass
        raise OSError('checkpoint journal resource limit: '+reason)

    def command(self,op,now_ns,**data):
        self.original.last_command_applied=False
        if self.failed:raise OSError('checkpoint journal is failed; no more acceptance')
        if op in ('request','declare'):getattr(self.machine,'validate_'+op)(**data)
        try:
            return self._append(op,now_ns,**data)
        except BaseException:
            self.failed=True
            raise

    def _append(self,op,now_ns,**data):
        stored=dict(data);reference=None
        if op=='chunk':
            chunk=stored.pop('chunk');raw=self.raw[data['receiver']];offset=raw.tell()
            if raw.write(chunk)!=len(chunk):self.failed=True;raise OSError('Short raw write')
            raw.flush();os.fsync(raw.fileno());self.raw_syncs+=1
            reference=dict(offset=offset,size=len(chunk),sha256=hashlib.sha256(chunk).hexdigest())
            stored.update(reference)
            if len(chunk)>LIMITS['max_chunk_bytes']:self._resource_error('chunk_bytes',reference)
        worst_new_lines=len(data.get('chunk',b''))
        if (self.seq>=LIMITS['max_operations'] or
            len(self.machine.events)+worst_new_lines+8>LIMITS['max_events'] or
            len(self.machine.states['RX-02']['lines'])+worst_new_lines>LIMITS['max_lines']):
            self._resource_error('history_or_operation_budget',reference)
        if self.original.decision_clock is not None:
            now_ns=self.original.decision_clock()
            self.machine.apply(op,now_ns,**data)
            self.original.last_command_applied=True
        record=dict(seq=self.seq,op=op,now_ns=now_ns,data=stored)
        text=json.dumps(record,ensure_ascii=False,allow_nan=False)+'\n'
        size=len(text.encode('utf-8'))
        if size>LIMITS['max_record_bytes']:self._resource_error('record_bytes',reference)
        if self.pending_ops_bytes+size>LIMITS['pending_ops_bytes']:self.checkpoint()
        try:
            if self.ops.write(text)!=len(text):raise OSError('Short operations write')
            self.ops.flush()
            self.pending_ops_bytes+=size
            self.max_pending_ops_bytes=max(self.max_pending_ops_bytes,self.pending_ops_bytes)
            self.original.seq+=1
            if op in BARRIERS:self.checkpoint()
            if not self.original.last_command_applied:
                self.machine.apply(op,now_ns,**data);self.original.last_command_applied=True
        except BaseException:
            self.failed=True
            raise

    def receipt(self):
        if self.failed:raise OSError('No receipt after journal failure')
        self.checkpoint()
        return self.original.receipt()

    def finalize(self,runtime):
        if self.failed:raise OSError('No finalized bundle after journal failure')
        self.checkpoint()
        write_new(self.root/'checkpoint-status.json',dict(revision=PERSISTENCE_REVISION,
            final_operations=self.seq,last_durable_seq=self.last_durable_seq,pending_ops_bytes=self.pending_ops_bytes,
            max_pending_ops_bytes=self.max_pending_ops_bytes,operations_prefix_bytes=self.ops.tell(),
            operations_sha256=digest(self.root/'operations.jsonl'),checkpoints=self.checkpoints,raw_syncs=self.raw_syncs,
            events=len(self.machine.events),lines=len(self.machine.states['RX-02']['lines']),
            limits=LIMITS,no_inflight_writer=True))
        self.original.finalize(dict(runtime,persistence_revision=PERSISTENCE_REVISION))

    def close_files(self):return self.original.close_files()


class CheckpointRx02Session(Rx02Session):
    """Reuse transport/error/close ownership; install revision before service.

    The existing physical CLI is intentionally unchanged. A future physical
    integration needs explicit review/authorization and this plan opt-in.
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


def audit_checkpoint_rx02(directory):
    """Validate revision metadata AND unchanged historical acceptance reducer."""
    root=Path(directory)
    metadata=json.loads((root/'persistence-policy.json').read_text())
    plan=json.loads((root/'plan.json').read_text())
    if (plan.get('persistence_revision')!=PERSISTENCE_REVISION or
        metadata!=policy_metadata(digest(root/'plan.json'))):
        raise ValueError('Checkpoint policy/source provenance mismatch')
    report=audit_rx02(root)
    status=json.loads((root/'checkpoint-status.json').read_text())
    if (status['revision']!=PERSISTENCE_REVISION or status['limits']!=LIMITS or
        status['final_operations']!=report['operations'] or status['last_durable_seq']!=report['operations']-1 or
        status['pending_ops_bytes']!=0 or status['max_pending_ops_bytes']>LIMITS['pending_ops_bytes'] or
        status['operations_prefix_bytes']!=(root/'operations.jsonl').stat().st_size or
        status['operations_sha256']!=digest(root/'operations.jsonl') or not status['no_inflight_writer'] or
        status['events']>LIMITS['max_events'] or status['lines']>LIMITS['max_lines'] or report['operations']>LIMITS['max_operations']):
        raise ValueError('Checkpoint final durability/resource evidence mismatch')
    report['persistence_revision']=PERSISTENCE_REVISION
    report['persistence_status']=status
    return report
