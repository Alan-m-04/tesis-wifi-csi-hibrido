"""Use the unchanged bounded checkpoint decorator with C03 transport/replay."""
import json
from pathlib import Path
from rx02_checkpoint_journal import CheckpointJournal,PERSISTENCE_REVISION,LIMITS,policy_metadata
from presence_v4_journal import digest
from rx02_c03.uart import C03UartSession
from rx02_c03.journal import audit_c03_replay
from rx02_c03.contract import INTEGRATION_REVISION

class C03CheckpointSession(C03UartSession):
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


def audit_c03_checkpoints(directory):
    """Validate revision metadata AND unchanged historical acceptance reducer."""
    root=Path(directory)
    metadata=json.loads((root/'persistence-policy.json').read_text())
    plan=json.loads((root/'plan.json').read_text())
    if (plan.get('persistence_revision')!=PERSISTENCE_REVISION or
        metadata!=policy_metadata(digest(root/'plan.json'))):
        raise ValueError('Checkpoint policy/source provenance mismatch')
    report=audit_c03_replay(root)
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
    report['integration_revision']=INTEGRATION_REVISION
    report['persistence_revision']=PERSISTENCE_REVISION
    report['persistence_status']=status
    return report
