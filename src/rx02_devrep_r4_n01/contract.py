"""R4-N01 E→S exclusivamente; reductor/agenda congelados de R1 con identidad nueva."""
import copy
import hashlib
import json
import re
from capture_csi_multi import SOURCE
from persistent_presence_v4 import STARTUP_SEQUENCE_POLICY,POLICY,_StartupSequenceFramer
from presence_v4_exploratory import STORAGE_POLICY
from presence_rx02 import PROTOCOL,ELIGIBILITY,RECEIVERS,PORTS,Rx02Presence
from rx02_checkpoint_journal import PERSISTENCE_REVISION
INTEGRATION_REVISION='rx02-devrep-r4-n01-entry-1'
OPERATOR_INTERFACE_REVISION='devrep-visible-keyboard-prompt-1'
SCHEDULE_REVISION='rx02-devrep-fixed-agenda-1'
CONNECTIONS={'RX02-DEVREP-R4-N01': {'order': ['E', 'S'], 'output_new': 'results/local/devrep-rx02-r4-N01', 'ordinal': 1}}
SCHEDULE={'request_offsets_ns': [30000000000, 240000000000], 'request_lateness_limit_ns': 2000000000, 'T0_ranges_ns': [[90000000000, 120000000000], [300000000000, 330000000000]], 'label_due_offsets_ns': [210000000000, 420000000000], 'close_ceiling_ns': 390000000000, 'inter_connection_gap_ns': 300000000000, 'inter_connection_lateness_ns': 5000000000}

# La transformación administrativa se liga a una autorización nueva fuera del plan preparado.
RUNTIME_FIELDS = dict(execution_mode='physical_after_approval', authorization_granted=True,
    review_only=False, review_state='authorized_single_attempt', ready_risk_reviewed=True,
    acquisition_executor_enabled=True, integration_revision=INTEGRATION_REVISION)


def runtime_plan(prepared):
    from preflight_devrep_r4 import validate
    validate(prepared)
    plan = copy.deepcopy(prepared)
    plan.update(RUNTIME_FIELDS)
    return plan


def prepared_plan(runtime):
    from preflight_devrep_r4 import template
    base = template()
    prepared = copy.deepcopy(runtime)
    for key, value in RUNTIME_FIELDS.items():
        if runtime.get(key) != value:
            raise ValueError('R4-N01 runtime requires the exact reviewed administrative transition')
        prepared[key] = base[key]
    return prepared


def validate_plan(plan, *, allow_physical=False, execution=False):
    from preflight_devrep_r4 import validate
    if not allow_physical:
        raise ValueError('R4-N01 runtime is separate from offline preparation')
    validate(prepared_plan(plan), confirmed=execution)
    return copy.deepcopy(plan)


class DevrepPresence(Rx02Presence):
    def __init__(self, plan, *, allow_physical=False, evidence_type=None, series_context=None):
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
        self.series_context=copy.deepcopy(series_context)
        self.admin_failures=[]

    def _admin_fail(self,reason,now_ns):
        if self.admin_failures:return
        self.admin_failures.append(dict(reason=reason,at_ns=now_ns))
        super().apply('interrupt',now_ns,detail='DEVREP administrative stop: '+reason)
        self.emit('devrep_schedule_failed',reason=reason)

    def apply(self,op,now_ns,**data):
        if type(now_ns)is not int or (self.now is not None and now_ns<self.now):
            raise ValueError('Original monotonic decision clock required')
        a=self.initial_available
        if a is not None and not self.fatal:
            if op=='request':
                index=len(self.windows)
                if index<2:
                    due=a+SCHEDULE['request_offsets_ns'][index]
                    if not due<=now_ns<=due+SCHEDULE['request_lateness_limit_ns']:
                        self._admin_fail('request_outside_fixed_time',now_ns);return
            if op=='declare':
                index=next((i for i,s in enumerate(self.plan['slots']) if s['id']==data['slot_id']),None)
                if index is not None and now_ns>a+SCHEDULE['label_due_offsets_ns'][index]:
                    self._admin_fail('late_declaration',now_ns);return
        super().apply(op,now_ns,**data)
        if op=='opened' and not self.fatal:
            ordinal=CONNECTIONS[self.plan['connection_id']]['ordinal']
            context=self.series_context
            if ordinal==1:
                if context is not None:self._admin_fail('unexpected_predecessor',now_ns)
            elif context is None:
                self._admin_fail('missing_predecessor',now_ns)
            else:
                target=context['previous_close_ns']+SCHEDULE['inter_connection_gap_ns']
                if not target<=now_ns<=target+SCHEDULE['inter_connection_lateness_ns']:
                    self._admin_fail('opening_outside_fixed_gap',now_ns)
        self._limits(now_ns)

    def _limits(self,now_ns):
        a=self.initial_available
        if a is None or self.fatal:return
        for index in range(2):
            if len(self.windows)<=index:
                if now_ns>a+SCHEDULE['request_offsets_ns'][index]+SCHEDULE['request_lateness_limit_ns']:
                    self._admin_fail('missing_scheduled_request',now_ns)
                break
            w=self.windows[index]
            if w['T0_ns'] is not None:
                lo,hi=SCHEDULE['T0_ranges_ns'][index]
                if not a+lo<=w['T0_ns']<=a+hi:
                    self._admin_fail('T0_outside_fixed_band',now_ns);return
            if w['label']['status']=='pending' and now_ns>a+SCHEDULE['label_due_offsets_ns'][index]:
                self._admin_fail('missing_declaration_by_deadline',now_ns);return
        if self.closing_since is None and now_ns>a+SCHEDULE['close_ceiling_ns']:
            self._admin_fail('close_deadline',now_ns)

    def summary(self):
        state=super().summary()
        state['devrep_schedule']=dict(revision=SCHEDULE_REVISION,anchor_ns=self.initial_available,
            failures=copy.deepcopy(self.admin_failures),series_context=copy.deepcopy(self.series_context),
            administrative_ok=not self.admin_failures,
            complete=len(self.windows)==2 and all(w['label']['status']=='declared' for w in self.windows),
            native_fatal=self.fatal)
        return state


def setup_fingerprint(plan):
    keys=('actor','mounting_reference','setup_snapshot_path','setup_snapshot_sha256','environment','receivers','ports','baud',
        'transmitter','policy','storage_policy','persistence_revision','unused_receiver')
    return hashlib.sha256(json.dumps({k:plan.get(k) for k in keys},sort_keys=True,separators=(',',':')).encode()).hexdigest()
