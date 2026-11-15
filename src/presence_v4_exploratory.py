"""Explicit exploratory eligibility; no transport, calibration or historical migration."""
import copy
import hashlib
import json

from capture_csi_multi import RECEIVERS
from controlled_capture import PORTS
from persistent_presence_v4 import PersistentPresenceV4, EXPLORATORY_ELIGIBILITY, POLICY

STORAGE_POLICY = dict(initial_free_bytes=100*1024**2, reserve_bytes=32*1024**2,
                      max_raw_bytes=64*1024**2, max_bundle_bytes=256*1024**2,
                      max_connection_ns=3600*1_000_000_000)


def make_v4_machine(plan, **kwargs):
    cls = ExploratoryPresenceV4 if plan.get('eligibility_revision') == EXPLORATORY_ELIGIBILITY else PersistentPresenceV4
    return cls(plan, **kwargs)


def outside_window(interval, t0, t1):
    """Closed uncertainty interval versus half-open prospective window."""
    lo, hi = interval.get('start_ns'), interval.get('end_ns')
    return (type(lo) is int and type(hi) is int and 0 <= lo <= hi and
            (hi < t0 or lo >= t1))


class ExploratoryPresenceV4(PersistentPresenceV4):
    def __init__(self, plan, **kwargs):
        super().__init__(plan, **kwargs)
        if (plan.get('eligibility_revision') != EXPLORATORY_ELIGIBILITY or
                plan.get('storage_policy') != STORAGE_POLICY or plan.get('ports') != PORTS or
                plan.get('baud') != 115200):
            raise ValueError('Explicit exploratory revision and fixed transport/storage plan required')
        self.eligibility_revision = EXPLORATORY_ELIGIBILITY
        self.bootstrap = self.preamble = None
        self.window_frontiers = {}
        self.raw_hashes = {rx: hashlib.sha256() for rx in RECEIVERS}
        self.anomalies, self.failures, self.storage_checks = [], [], []
        self.bindings = {}

    def apply(self, op, now_ns, **data):
        if op == 'storage_check':
            if self.a is None or type(now_ns) is not int or now_ns < self.now:
                raise ValueError('Storage evidence requires begun monotonic connection')
            self.now = now_ns
            keys = ('free_bytes', 'raw_bytes', 'size_bytes', 'final_extra', 'guard_started_ns')
            valid = all(type(data.get(k)) is int and data[k] >= 0 for k in keys)
            if valid:
                valid = (data['raw_bytes'] == sum(f.offset for f in self.framers.values()) and
                    data['guard_started_ns'] <= self.a and
                    now_ns-data['guard_started_ns'] < STORAGE_POLICY['max_connection_ns'] and
                    data['raw_bytes'] < STORAGE_POLICY['max_raw_bytes'] and
                    data['free_bytes']-data['final_extra'] >= STORAGE_POLICY['reserve_bytes'] and
                    data['size_bytes']+data['final_extra'] < STORAGE_POLICY['max_bundle_bytes'])
            self.storage_checks.append(dict(now_ns=now_ns, valid=valid, **data))
            self.emit('storage_check', valid=valid, **data)
            if not valid:
                self.fail('storage_assurance_failed')
            return
        super().apply(op, now_ns, **data)
        if op == 'opened' and 'identity_binding' in data:
            self.bindings[data['receiver']] = copy.deepcopy(data['identity_binding'])
            self.emit('identity_binding', receiver=data['receiver'], evidence=copy.deepcopy(data['identity_binding']))

    def fail(self, reason, *, start=None, end=None, connection=True):
        self.failures.append(dict(reason=reason, start_ns=start,
                                  end_ns=self.now if end is None else max(self.now, end)))
        super().fail(reason, start=start, end=end, connection=connection)

    def feed(self, receiver, chunk, started_ns, returned_ns):
        count = len(self.states[receiver]['lines'])
        self.raw_hashes[receiver].update(chunk)
        super().feed(receiver, chunk, started_ns, returned_ns)
        s = self.states[receiver]
        for line in s['lines'][count:]:
            if ((line['kind'] in ('invalid', 'reset', 'error', 'info') and
                 not line.get('line_policy_exception')) or line['continuity_error']):
                lo, hi = int(line['first_read_started_ns']), max(int(line['returned_ns']), self.now)
                if not 0 <= lo <= int(line['returned_ns']) <= self.now:
                    lo = hi = None
                self.anomalies.append(dict(receiver=receiver, line=copy.deepcopy(line),
                                            start_ns=lo, end_ns=hi, processed_ns=self.now))
                reason = 'preamble_anomaly:'+receiver
                if s['ready'] is None or line['line_1based'] < s['ready']:
                    if reason not in self.connection_reasons:
                        self.connection_reasons.append(reason)
        if self.bootstrap is None and all(v['returned'] for v in self.startup_messages.values()):
            self.bootstrap = dict(processed_ns=self.now,
                read_indices={rx: state.get('read_count', 0)-1 for rx, state in self.states.items()},
                byte_ends={rx: f.offset for rx, f in self.framers.items()})
            for state in self.states.values():
                state['streak'] = []
            self.emit('bootstrap_barrier', evidence=copy.deepcopy(self.bootstrap))
        if self.initial_available is None:
            for rx, state in self.states.items():
                state['streak'] = [r for r in state['streak'] if self.bootstrap is not None and
                    r['first_read_index'] > self.bootstrap['read_indices'][rx] and
                    int(r['first_read_started_ns']) >= self.bootstrap['processed_ns']]

    def tick(self):
        pending = any(f.length for f in self.framers.values())
        if pending and self.initial_available is None and not self.fatal:
            if self.now >= self.a+POLICY['availability_wait_ns']:
                self.fail('initial_availability_timeout')
            return
        if pending and self.windows and self.windows[-1]['state'] == 'gate' and not self.fatal:
            for rx, s in self.states.items():
                if self.now-s['last_valid'] > POLICY['freshness_ns']:
                    self.fail('availability_lost:'+rx)
                    return
            if self.now >= self.windows[-1]['gate_deadline_ns']:
                self.fail('slot_availability_timeout')
            return
        super().tick()
        if self.initial_available is not None and self.preamble is None:
            ends = {rx: f.offset for rx, f in self.framers.items()}
            self.preamble = dict(end_processed_ns=self.initial_available, receivers={rx: dict(
                byte_offset=0, byte_end=ends[rx], sha256=self.raw_hashes[rx].hexdigest(),
                lines=copy.deepcopy([r for r in s['lines'] if r['byte_end'] <= ends[rx]]))
                for rx, s in self.states.items()})
            self.emit('preamble_sealed', evidence=copy.deepcopy(self.preamble))
        for w in self.windows:
            if w['T0_ns'] is not None and w['id'] not in self.window_frontiers:
                self.window_frontiers[w['id']] = dict(processed_ns=w['T0_ns'],
                    read_indices={rx: s.get('read_count', 0)-1 for rx, s in self.states.items()},
                    byte_ends={rx: f.offset for rx, f in self.framers.items()})
                self.emit('exploratory_window_frontier', slot_id=w['id'],
                          evidence=copy.deepcopy(self.window_frontiers[w['id']]))

    def summary(self):
        result = super().summary()
        anomalies = copy.deepcopy(self.anomalies)
        for rx, f in self.framers.items():
            if f.length:
                anomalies.append(dict(receiver=rx, kind='incomplete_tail', start_ns=int(f.first['first_read_started_ns']),
                    end_ns=None, byte_offset=f.offset-f.length, byte_end=f.offset, sha256=f.hash.hexdigest()))
        processed = {(e['receiver'], e['evidence']['line_1based']): e['now_ns']
                     for e in self.events if e['kind'] == 'line'}
        candidates = []
        closed = len(self.closed) == 2 and all(c['confirmed'] and not c['error'] for c in self.closed.values())
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
        result['eligibility_revision'] = EXPLORATORY_ELIGIBILITY
        prefix_anomalies = [a for a in self.anomalies if self.preamble is not None and
            a['line']['byte_end'] <= self.preamble['receivers'][a['receiver']]['byte_end']]
        result['exploration'] = dict(bootstrap=copy.deepcopy(self.bootstrap), preamble=copy.deepcopy(self.preamble),
            preamble_status='incomplete' if self.preamble is None else (
                'anomalous_uninterpreted' if prefix_anomalies else 'no_anomaly_recorded'),
            anomalies=anomalies, failures=copy.deepcopy(self.failures), windows=candidates,
            identity_bindings=copy.deepcopy(self.bindings), storage_checks=copy.deepcopy(self.storage_checks),
            permitted_uses=dict(calibration=False, training=False, production=False))
        return result


def certify_exploration(root, provenance, state):
    """Called only after integrity, deterministic replay and receipt validation."""
    plan = json.loads((root/'plan.json').read_text())
    transport = provenance.get('transport', {})
    evidence_type = state['evidence_type']
    expected_backend = 'UART' if evidence_type == 'physical_capture' else 'synthetic_serial_backend'
    identity_ok = transport.get('backend') == expected_backend
    identities = transport.get('identities', {})
    fingerprints = []
    for rx in RECEIVERS:
        identity = identities.get(rx, {})
        binding = state['exploration']['identity_bindings'].get(rx, {})
        valid = (identity.get('serial') == RECEIVERS[rx] and identity.get('by_id') == PORTS[rx] and
                 identity.get('vid') == '1a86' and identity.get('pid') == '55d3' and identity.get('bus') == 'usb' and
                 binding.get('identity') == identity and binding.get('opened_fingerprint') == identity.get('node_fingerprint') and
                 isinstance(identity.get('node_fingerprint'), list) and len(identity['node_fingerprint']) == 3 and
                 all(type(v) is int and v >= 0 for v in identity['node_fingerprint']))
        identity_ok = identity_ok and valid
        fingerprints.append(identity.get('node_fingerprint'))
    identity_ok = identity_ok and fingerprints[0] != fingerprints[1]
    checks = state['exploration']['storage_checks']
    initial = transport.get('initial_free_bytes_observed')
    storage_ok = (plan.get('storage_policy') == STORAGE_POLICY and transport.get('storage_policy') == STORAGE_POLICY and
        type(initial) is int and initial >= STORAGE_POLICY['initial_free_bytes'] and
        bool(checks) and all(c['valid'] for c in checks) and checks[-1]['final_extra'] > 0 and
        sum(p.stat().st_size for p in root.rglob('*') if p.is_file()) < STORAGE_POLICY['max_bundle_bytes'])
    windows = []
    for item in state['exploration']['windows']:
        reasons = list(item['reasons'])
        if not identity_ok:reasons.append('identity_evidence_missing_or_inconsistent')
        if not storage_ok:reasons.append('storage_evidence_missing_or_inconsistent')
        windows.append(dict(slot_id=item['slot_id'], eligible=not reasons, reasons=reasons,
                            status='eligible_exploratory' if not reasons else 'ineligible_exploratory'))
    return dict(revision=EXPLORATORY_ELIGIBILITY, evidence_type=evidence_type,
                integrity_ok=True, replay_ok=True, identity_ok=bool(identity_ok), storage_ok=bool(storage_ok),
                windows=windows, permitted_uses=dict(calibration=False, training=False, production=False))
