"""C03-only opt-in validation; inherited reducer/coverage/labels/close unchanged."""
import copy
import hashlib
from capture_csi_multi import SOURCE
from persistent_presence_v4 import STARTUP_SEQUENCE_POLICY,POLICY,_StartupSequenceFramer
from presence_v4_exploratory import STORAGE_POLICY
from presence_rx02 import (PROTOCOL,ELIGIBILITY,RECEIVERS,PORTS,UNUSED_RX,PARTITIONS,Rx02Presence)
from rx02_checkpoint_journal import PERSISTENCE_REVISION

INTEGRATION_REVISION='rx02-c03-checkpoint-entry-1'
OUTPUT_RELATIVE='results/local/piloto-rx02-r1-C03-checkpoint-r1'

def validate_plan(plan, *, allow_physical=False, execution=False):
    if (plan.get('protocol') != PROTOCOL or plan.get('eligibility_revision') != ELIGIBILITY or
        plan.get('line_policy_revision') != STARTUP_SEQUENCE_POLICY or
        plan.get('receivers') != RECEIVERS or plan.get('ports') != PORTS or
        plan.get('baud') != 115200 or plan.get('policy') != POLICY or
        plan.get('storage_policy') != STORAGE_POLICY or
        plan.get('execution_mode') not in (('offline_only', 'physical_after_approval')
            if allow_physical else ('offline_only',))):
        raise ValueError('Exact RX-02 singleton protocol, identities, revisions and thresholds required')
    if (plan.get('transmitter') != dict(identity='TX-01', source_mac=SOURCE) or
        plan.get('selection_revision') != 'rx02-continuity-selection-1'):
        raise ValueError('Prospective TX-01/RX-02 selection required')
    for key in ('connection_id', 'actor', 'mounting_reference', 'partition_group'):
        if not isinstance(plan.get(key), str) or not plan[key].strip():
            raise ValueError('Missing declaration: '+key)
    cid = plan['connection_id']
    if cid not in PARTITIONS or plan['partition_group'] != cid or plan.get('future_partition') != PARTITIONS[cid]:
        raise ValueError('Fixed whole-connection partition required; no window/row split')
    index = int(cid[-2:])
    conditions = ['E', 'S'] if index % 2 else ['S', 'E']
    if plan.get('slots') != [dict(id=cid+'-'+c, condition=c) for c in conditions]:
        raise ValueError('Two prospective E/S slots in the preregistered order required')
    unused = plan.get('unused_receiver', {})
    if (unused.get('receiver') != 'RX-01' or
        unused.get('action') not in (UNUSED_RX['action'], 'remain_disconnected_uart_unopened') or
        unused.get('operator_confirmation') not in ('PENDIENTE', 'confirmed_current')):
        raise ValueError('Explicit unchanged RX-01 disposition required')
    if plan.get('permitted_uses') != dict(calibration=False, training=False, production=False):
        raise ValueError('No calibration/training/production authorization')
    if execution:
        from controlled_capture import ENVIRONMENT_FIELDS
        if plan['execution_mode'] != 'physical_after_approval' or unused['operator_confirmation'] != 'confirmed_current':
            raise ValueError('Physical plan and current RX-01 confirmation required')
        fields = (*ENVIRONMENT_FIELDS, 'mounting_confirmation', 'sound_practice_reference',
                  'laptop_power_lid', 'suspension_ac_battery', 'serial_readers_absent')
        for key in fields:
            value = plan.get('environment', {}).get(key)
            if not isinstance(value, str) or not value.strip() or 'PENDIENTE' in value.upper():
                raise ValueError('Complete current declaration: '+key)
        if any('PENDIENTE' in plan[key].upper() for key in ('actor', 'mounting_reference')):
            raise ValueError('Complete current actor and mounting reference')
    if (plan.get('connection_id')!='RX02-C03' or plan.get('integration_revision')!=INTEGRATION_REVISION or
        plan.get('persistence_revision')!=PERSISTENCE_REVISION or plan.get('output_new')!=OUTPUT_RELATIVE):
        raise ValueError('Explicit C03 integration, checkpoint revision and exclusive output required')
    return copy.deepcopy(plan)


class C03Presence(Rx02Presence):
    def __init__(self, plan, *, allow_physical=False, evidence_type=None):
            # Initialize the actual singleton topology, rather than adapting a dual
            # plan or constructing a fictitious receiver to satisfy dual checks.
            self.plan = validate_plan(plan, allow_physical=allow_physical)
            self.line_policy_revision = STARTUP_SEQUENCE_POLICY
            self.eligibility_revision = ELIGIBILITY
            self.evidence_type = evidence_type or ('physical_capture' if
                plan['execution_mode'] == 'physical_after_approval' else 'synthetic_fixture')
            if self.evidence_type not in ('synthetic_fixture', 'physical_capture') or (
                self.evidence_type == 'physical_capture' and plan['execution_mode'] != 'physical_after_approval'):
                raise ValueError('Evidence type contradicts execution mode')
            self.now = self.a = self.initial_available = None
            self.states = {rx: dict(opened=False, ready=None, previous=None, streak=[], gate_rows=[],
                last_valid=None, last_read=None, lines=[]) for rx in RECEIVERS}
            self.framers = {rx: _StartupSequenceFramer(rx) for rx in RECEIVERS}
            self.startup_messages = {rx: dict(sniffer=False, returned=False) for rx in RECEIVERS}
            self.events, self.windows, self.signals = [], [], []
            self.fatal = None
            self.connection_reasons = []
            self.close_requested = False
            self.closing_since = None
            self.close_counts = dict.fromkeys(RECEIVERS, 0)
            self.close_bytes = dict.fromkeys(RECEIVERS, 0)
            self.closed = {}
            self.bootstrap = self.preamble = None
            self.window_frontiers = {}
            self.raw_hashes = {rx: hashlib.sha256() for rx in RECEIVERS}
            self.anomalies, self.failures, self.storage_checks = [], [], []
            self.bindings = {}
