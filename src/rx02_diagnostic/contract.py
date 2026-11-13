# Derived from presence_rx02.py at 1bb7619; separate diagnostic contract.
"""Prospective singleton RX-02 contract; historical dual reducers are unchanged.

Topology/close/eligibility are explicit here. Framing, startup, watchdog, labels
and conservative temporal checks reuse v4; no fake RX-01 state or acknowledgments.
"""
import copy
import hashlib
import json
from pathlib import Path

from capture_csi_multi import SOURCE
from persistent_presence_v4 import (PersistentPresenceV4, _StartupSequenceFramer,
    STARTUP_SEQUENCE_POLICY, POLICY)
from presence_v4_exploratory import ExploratoryPresenceV4, STORAGE_POLICY, outside_window

PROTOCOL = 'rx02_service_diagnostic_1'
ELIGIBILITY = 'rx02-diagnostic-only-1'
HISTORICAL_CONNECTION = 'RX02-DIAG-CP-R1'
VIEW_CONNECTION = 'RX02-DIAG-VISOR-240S-R1'
VIEW_IDENTITY_REVISION = 'rx02-live-identity-2'
RECEIVERS = {'RX-02': '5C93200689'}
PORTS = {'RX-02': '/dev/serial/by-id/usb-1a86_USB_Single_Serial_5C93200689-if00'}
UNUSED_RX = dict(receiver='RX-01', action='leave_connected_fixed_uart_unopened',
                 operator_confirmation='PENDIENTE')


def validate_plan(plan, *, allow_physical=False, execution=False):
    from rx02_checkpoint_journal import PERSISTENCE_REVISION
    if (plan.get('protocol') != PROTOCOL or plan.get('eligibility_revision') != ELIGIBILITY or
        plan.get('line_policy_revision') != STARTUP_SEQUENCE_POLICY or
        plan.get('receivers') != RECEIVERS or plan.get('ports') != PORTS or
        plan.get('baud') != 115200 or plan.get('policy') != POLICY or
        plan.get('storage_policy') != STORAGE_POLICY or
        plan.get('persistence_revision') != PERSISTENCE_REVISION or
        plan.get('execution_mode') not in (('offline_only','physical_after_approval') if allow_physical else ('offline_only',))):
        raise ValueError('Exact diagnostic protocol, persistence, identities and unchanged thresholds required')
    connection = plan.get('connection_id')
    live = plan.get('live_view')
    historical = connection == HISTORICAL_CONNECTION and live is None
    viewer = (connection == VIEW_CONNECTION and isinstance(live, dict) and
              live.get('attempt_id') == VIEW_CONNECTION and live.get('identity_revision') == VIEW_IDENTITY_REVISION and
              plan.get('authorization_granted') is False and plan.get('review_state') == 'prepared_not_authorized')
    if (not (historical or viewer) or plan.get('partition_group') != connection or
        plan.get('future_partition') != 'diagnostic_only' or
        plan.get('slots') != [] or plan.get('duration_ns') != 240_000_000_000 or
        plan.get('transmitter') != dict(identity='TX-01',source_mac=SOURCE) or
        plan.get('selection_revision') != 'rx02-continuity-selection-1' or
        plan.get('permitted_uses') != dict(calibration=False,training=False,production=False) or
        plan.get('unused_receiver') != dict(receiver='RX-01',action='remain_disconnected_uart_unopened',
            operator_confirmation=plan.get('unused_receiver',{}).get('operator_confirmation')) or
        plan['unused_receiver']['operator_confirmation'] not in ('PENDIENTE','confirmed_current')):
        raise ValueError('Diagnostic identity, no slots, fixed duration, exclusion and RX-01 disposition required')
    if execution:
        from controlled_capture import ENVIRONMENT_FIELDS
        if plan['execution_mode'] != 'physical_after_approval' or plan['unused_receiver']['operator_confirmation'] != 'confirmed_current':
            raise ValueError('Current physical declarations required')
        for key in (*ENVIRONMENT_FIELDS,'mounting_confirmation','sound_practice_reference',
                    'laptop_power_lid','suspension_ac_battery','serial_readers_absent'):
            value=plan.get('environment',{}).get(key)
            if not isinstance(value,str) or not value.strip() or 'PENDIENTE' in value.upper():
                raise ValueError('Complete current declaration: '+key)
        for key in ('actor','mounting_reference'):
            value=plan.get(key)
            if not isinstance(value,str) or not value.strip() or 'PENDIENTE' in value.upper():
                raise ValueError('Complete current declaration: '+key)
    return copy.deepcopy(plan)


class Rx02Presence(ExploratoryPresenceV4):
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

    def apply(self, op, now_ns, **data):
        if 'receiver' in data and data['receiver'] not in RECEIVERS:
            raise ValueError('Only the selected RX-02 may participate; no fallback')
        return super().apply(op, now_ns, **data)

    def validate_request(self, slot_id, last=False):
        window = super().validate_request(slot_id, last)
        if last != (len(self.windows) == len(self.plan['slots'])-1):
            raise ValueError('Only the second and final preregistered slot must be last')
        return window

    def close_ack(self, receiver, confirmed, reader_stopped, error=None, proof='synthetic_memory_ack'):
        if receiver not in RECEIVERS or self.closing_since is None or receiver in self.closed:
            raise ValueError('Close selected RX-02 exactly once after stopping reads')
        self.close_counts[receiver] += 1
        ok = confirmed is True and reader_stopped is True and self.states[receiver]['opened']
        self.closed[receiver] = dict(confirmed=ok, reader_stopped=reader_stopped,
            at_ns=self.now, error=error, proof=proof)
        if self.framers[receiver].length:
            self.fail('incomplete_tail:'+receiver)
        if not ok or error:
            self.fail('close_unconfirmed:'+receiver)
        self.emit('port_close_result', receiver=receiver, confirmed=ok, error=error)
        if self.selected_closed():
            self.emit('selected_port_closed_confirmed', receiver=receiver)
            self.signal('selected_port_closed_confirmed')

    def selected_closed(self):
        return set(self.closed) == set(RECEIVERS) and all(
            c['confirmed'] and not c['error'] for c in self.closed.values())

    def summary(self):
        # Base coverage iterates actual states. Only topology-dependent fields
        # are computed here; all thresholds and exploratory exclusions remain.
        result = PersistentPresenceV4.summary(self)
        result['protocol'] = PROTOCOL
        result['connection']['quality_ok'] = not self.connection_reasons and self.selected_closed()
        result['partition_group'] = self.plan['partition_group']
        result['future_partition'] = self.plan['future_partition']
        result['unused_receiver'] = copy.deepcopy(self.plan['unused_receiver'])
        for w in result['windows']:
            w['eligible'] = bool(not self.fatal and result['connection']['quality_ok'] and
                w['window_quality_ok'] and w['pilot_coverage_ok'] and w['label_quality_ok'])
        anomalies = copy.deepcopy(self.anomalies)
        for rx, f in self.framers.items():
            if f.length:
                anomalies.append(dict(receiver=rx, kind='incomplete_tail', start_ns=int(f.first['first_read_started_ns']),
                    end_ns=None, byte_offset=f.offset-f.length, byte_end=f.offset, sha256=f.hash.hexdigest()))
        processed = {(e['receiver'], e['evidence']['line_1based']): e['now_ns']
                     for e in self.events if e['kind'] == 'line'}
        candidates = []
        closed = self.selected_closed()
        for w in result['windows']:
            reasons = []
            frontier = self.window_frontiers.get(w['id'])
            temporal_receivers = {}
            if self.fatal:reasons.append('connection_suspended')
            if not closed:reasons.append('closures_not_confirmed')
            if self.preamble is None or w['T0_ns'] is None:
                reasons.append('preamble_or_window_incomplete')
            elif self.preamble['end_processed_ns'] >= w['T0_ns']:
                reasons.append('preamble_not_strictly_before_window')
            if w['T0_ns'] is not None:
                if any(not outside_window(a, w['T0_ns'], w['T1_ns']) for a in anomalies+self.failures):
                    reasons.append('anomaly_intersects_or_unlocated')
                if any(processed[(rx, r['line_1based'])] >= w['T1_ns']
                       for rx, v in w['receivers'].items() for r in v['included_line_references']):
                    reasons.append('late_row_processing')
                if frontier is None:
                    reasons.append('window_frontier_missing')
                else:
                    for rx, v in w['receivers'].items():
                        rows = [r for r in v['included_line_references'] if
                            r['byte_offset'] >= frontier['byte_ends'][rx] and
                            r['first_read_index'] > frontier['read_indices'][rx] and
                            processed[(rx, r['line_1based'])] < w['T1_ns']]
                        times = [int(r['returned_ns']) for r in rows]
                        bins = [sum(w['T0_ns']+i*5_000_000_000 <= t < w['T0_ns']+(i+1)*5_000_000_000
                                    for t in times) for i in range(6)]
                        gaps = ([times[0]-w['T0_ns']]+[b-a for a,b in zip(times,times[1:])]+
                                [w['T1_ns']-times[-1]]) if times else []
                        coverage_ok = (len(rows) >= POLICY['coverage_min_rows'] and
                            min(bins) >= POLICY['coverage_bin_rows'] and bool(gaps) and
                            max(gaps) <= POLICY['coverage_gap_ns'])
                        temporal_receivers[rx] = dict(included_line_references=copy.deepcopy(rows),
                            bins_5s=bins, gaps_ns=gaps, included_rows=len(rows), coverage_ok=bool(coverage_ok))
                        if not coverage_ok:reasons.append('conservative_coverage:'+rx)
            for field in ('window_quality_ok', 'pilot_coverage_ok', 'label_quality_ok'):
                if not w[field]:reasons.append(field)
            candidates.append(dict(slot_id=w['id'], candidate=not reasons, reasons=reasons,
                frontier=copy.deepcopy(frontier), receivers=temporal_receivers,
                eligible=None, status='requires_integrity_identity_storage_audit'))
        result['eligibility_revision'] = ELIGIBILITY
        prefix_anomalies = [a for a in self.anomalies if self.preamble is not None and
            a['line']['byte_end'] <= self.preamble['receivers'][a['receiver']]['byte_end']]
        result['exploration'] = dict(bootstrap=copy.deepcopy(self.bootstrap), preamble=copy.deepcopy(self.preamble),
            preamble_status='incomplete' if self.preamble is None else (
                'anomalous_uninterpreted' if prefix_anomalies else 'no_anomaly_recorded'),
            anomalies=anomalies, failures=copy.deepcopy(self.failures), windows=candidates,
            identity_bindings=copy.deepcopy(self.bindings), storage_checks=copy.deepcopy(self.storage_checks),
            permitted_uses=dict(calibration=False, training=False, production=False))
        return result
