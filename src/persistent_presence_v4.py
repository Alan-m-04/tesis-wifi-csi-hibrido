"""Offline v4 reducer: bytes and explicit host operations, no device access.

The protocol document precedes this implementation. v1/v2/v3 are imported only
for pure framing/grammar/continuity; their policies are never modified.
"""
import copy
import re

from availability_window import LineFramer, transition_error
from capture_csi_multi import RECEIVERS

SECOND = 1_000_000_000
PROTOCOL = 'presence_persistent_v4'
STRICT_LINE_POLICY = 'v4-strict-post-ready-1'
APP_MAIN_RETURN_POLICY = 'v4-app-main-return-1'
STARTUP_SEQUENCE_POLICY = 'v4-startup-sequence-1'
POLICY = dict(window_ns=30*SECOND, availability_wait_ns=10*SECOND,
              freshness_ns=SECOND, exit_delay_ns=60*SECOND,
              start_cue_delay_ns=30*SECOND, establishment_ns=30*SECOND,
              label_tail_ns=10*SECOND, close_wait_ns=250_000_000,
              close_bytes=65536, coverage_min_rows=120, coverage_bin_rows=15,
              coverage_gap_ns=500_000_000)


def validate_plan(plan, *, allow_physical=False):
    if plan.get('line_policy_revision', STRICT_LINE_POLICY) not in (
            STRICT_LINE_POLICY, APP_MAIN_RETURN_POLICY, STARTUP_SEQUENCE_POLICY):
        raise ValueError('Unknown v4 line_policy_revision')
    if (plan.get('protocol') != PROTOCOL or plan.get('policy') != POLICY or
            plan.get('execution_mode') not in (('offline_only', 'physical_after_approval') if allow_physical else ('offline_only',)) or
            plan.get('receivers') != RECEIVERS):
        raise ValueError('Exact offline v4 protocol, policy and RX identities required')
    for key in ('connection_id', 'actor', 'mounting_reference', 'partition_group'):
        if not isinstance(plan.get(key), str) or not plan[key].strip():
            raise ValueError('Missing declaration: '+key)
    slots = plan.get('slots')
    if not isinstance(slots, list) or not slots:
        raise ValueError('Prospective slots required')
    ids = set()
    for slot in slots:
        if (not isinstance(slot.get('id'), str) or not slot['id'] or slot['id'] in ids or
                slot.get('condition') not in ('E', 'S', 'W')):
            raise ValueError('Unique slot ID and E/S/W condition required')
        ids.add(slot['id'])
    return copy.deepcopy(plan)


class _StartupLineFramer(LineFramer):
    """v4-only exact byte annotation; shared grammar and raw evidence unchanged."""
    def feed(self, chunk, read_index, event):
        prefix = bytes(self.prefix)
        parts = chunk.split(b'\n')
        lines = super().feed(chunk, read_index, event)
        for index, line in enumerate(lines):
            if line['kind'] == 'info':
                raw = (prefix if index == 0 else b'') + parts[index] + b'\n'
                if re.fullmatch(rb'I \([0-9]+\) main_task: Returned from app_main\(\)\r?\n', raw):
                    line['startup_app_main_return'] = True
        return lines


class _StartupSequenceFramer(_StartupLineFramer):
    """Recognize only the observed sniffer line; no shared log grammar change."""
    def feed(self, chunk, read_index, event):
        prefix = bytes(self.prefix)
        parts = chunk.split(b'\n')
        lines = super().feed(chunk, read_index, event)
        for index, line in enumerate(lines):
            if line['kind'] == 'invalid':
                raw = (prefix if index == 0 else b'') + parts[index] + b'\n'
                if re.fullmatch(rb'I \([0-9]+\) wifi:ic_enable_sniffer\r?\n', raw):
                    line.update(shared_kind=line['kind'], shared_reason=line.pop('reason'),
                                kind='info', startup_sniffer_enable=True)
        return lines


class PersistentPresenceV4:
    def __init__(self, plan, *, allow_physical=False, evidence_type=None):
        self.plan = validate_plan(plan, allow_physical=allow_physical)
        self.line_policy_revision = self.plan.get('line_policy_revision', STRICT_LINE_POLICY)
        self.evidence_type = evidence_type or ('physical_capture' if plan['execution_mode']=='physical_after_approval' else 'synthetic_fixture')
        if self.evidence_type not in ('synthetic_fixture', 'physical_capture') or (
                self.evidence_type == 'physical_capture' and plan['execution_mode'] != 'physical_after_approval'):
            raise ValueError('Evidence type contradicts execution mode')
        self.now = self.a = self.initial_available = None
        self.states = {rx: dict(opened=False, ready=None, previous=None, streak=[],
                              gate_rows=[], last_valid=None, last_read=None, lines=[])
                       for rx in RECEIVERS}
        framer = _StartupLineFramer if self.line_policy_revision == APP_MAIN_RETURN_POLICY else LineFramer
        if self.line_policy_revision == STARTUP_SEQUENCE_POLICY:
            framer = _StartupSequenceFramer
        self.framers = {rx: framer(rx) for rx in RECEIVERS}
        self.startup_messages = {rx: dict(sniffer=False, returned=False) for rx in RECEIVERS}
        self.events, self.windows, self.signals = [], [], []
        self.fatal = None
        self.connection_reasons = []
        self.close_requested = False
        self.closing_since = None
        self.close_counts = {rx: 0 for rx in RECEIVERS}
        self.close_bytes = {rx: 0 for rx in RECEIVERS}
        self.closed = {}

    def emit(self, kind, **data):
        self.events.append(dict(seq=len(self.events), kind=kind, now_ns=self.now, **data))

    def signal(self, kind):
        item = dict(id=len(self.signals), kind=kind, requested_ns=self.now, ack_ns=None,
                    software_playback_ok=None)
        self.signals.append(item)
        self.emit('signal_requested', signal_id=item['id'], signal_kind=kind)
        return item['id']

    def fail(self, reason, *, start=None, end=None, connection=True):
        if self.fatal is None:
            self.fatal = reason
            self.emit('suspended', reason=reason)
            self.signal('failure')
        if connection and reason not in self.connection_reasons:
            self.connection_reasons.append(reason)
        lo = self.now if start is None else start
        hi = self.now if end is None else end
        for w in self.windows:
            if w['T0_ns'] is None:
                if w['state'] in ('delay', 'gate'):
                    w['state'] = 'not_started'
                    w['reasons'].append(reason)
            elif (lo < w['T1_ns'] and hi >= w['T0_ns']) or (
                    start is not None and w['gate_ns'] <= hi < w['T0_ns'] <= self.now):
                if reason not in w['reasons']:
                    w['reasons'].append(reason)
                if w['state'] == 'running':
                    w['state'] = 'aborted'
        self.close_requested = True

    def apply(self, op, now_ns, **data):
        if type(now_ns) is not int or (self.now is not None and now_ns < self.now):
            raise ValueError('Monotonic processing clock required')
        self.now = now_ns
        if op == 'begin':
            if self.a is not None:
                raise ValueError('Connection cannot be restarted')
            self.a = self.now
            self.emit('begin', connection_id=self.plan['connection_id'])
        elif self.a is None:
            raise ValueError('Begin required')
        elif op == 'opened':
            rx = data['receiver']
            if self.states[rx]['opened'] or self.close_requested:
                raise ValueError('Exactly one open per receiver')
            self.states[rx]['opened'] = True
            self.emit('opened', receiver=rx)
        elif op == 'chunk':
            self.feed(**data)
        elif op == 'tick':
            self.tick()
        elif op == 'request':
            self.request(**data)
        elif op == 'cue_ack':
            self.ack(**data)
        elif op == 'declare':
            self.declare(**data)
        elif op == 'close_request':
            if any(w['state'] in ('delay', 'gate', 'running') for w in self.windows):
                self.fail('operator_close_before_window_end')
            self.close_requested = True
            self.emit('close_requested')
        elif op == 'closing':
            if not self.close_requested or self.closing_since is not None:
                raise ValueError('One explicit close request required')
            self.closing_since = self.now
            self.emit('read_stop_requested')
        elif op == 'closed':
            self.close_ack(**data)
        elif op in ('interrupt', 'reader_ended', 'io_error', 'storage_error'):
            self.fail(op+(':'+data['receiver'] if data.get('receiver') else ''))
        else:
            raise ValueError('Unknown operation: '+op)

    def accept_startup_sequence_message(self, receiver, line):
        """Finite, per-RX initialization exception; called only by revision 1."""
        if (self.fatal is not None or self.close_requested or self.closing_since is not None or
                self.initial_available is not None or self.now >= self.a+POLICY['availability_wait_ns']):
            return False
        seen = self.startup_messages[receiver]
        ready = self.states[receiver]['ready'] is not None
        if line.get('startup_sniffer_enable'):
            if (seen['sniffer'] or seen['returned'] or self.states[receiver]['previous'] is not None or
                    ready != (receiver == 'RX-01')):
                return False
            seen['sniffer'] = True
            return True
        if line.get('startup_app_main_return'):
            if not ready or seen['returned'] or (receiver == 'RX-01' and not seen['sniffer']):
                return False
            seen['returned'] = True
            return True
        return False

    def feed(self, receiver, chunk, started_ns, returned_ns):
        s = self.states[receiver]
        f = self.framers[receiver]
        if not s['opened'] or receiver in self.closed:
            raise ValueError('Read requires its original open connection')
        if not isinstance(chunk, bytes) or not chunk:
            raise ValueError('Only actual nonempty byte chunks')
        index = s.get('read_count', 0)
        s['read_count'] = index+1
        lines = f.feed(chunk, index, dict(started_ns=str(started_ns), returned_ns=str(returned_ns)))
        if (not 0 <= started_ns <= returned_ns <= self.now or
                (s['last_read'] is not None and started_ns < s['last_read'])):
            self.fail('read_chronology:'+receiver, start=started_ns, end=returned_ns)
        s['last_read'] = returned_ns
        if self.closing_since is not None:
            self.close_bytes[receiver] += len(chunk)
            if (returned_ns > self.closing_since+POLICY['close_wait_ns'] or
                    self.close_bytes[receiver] > POLICY['close_bytes']):
                self.fail('close_budget_exceeded:'+receiver)
        for line in lines:
            error = transition_error(s['previous'], line) if line['kind'] == 'row' else None
            line['continuity_error'] = error
            startup_return = (
                self.line_policy_revision == APP_MAIN_RETURN_POLICY and
                line['kind'] == 'info' and line.get('startup_app_main_return') and
                s['ready'] is not None and line['line_1based'] == s['ready']+1 and
                s['previous'] is None and self.initial_available is None and
                self.fatal is None and not self.close_requested and self.closing_since is None and
                self.now < self.a+POLICY['availability_wait_ns'])
            sequence_pattern = self.line_policy_revision == STARTUP_SEQUENCE_POLICY and (
                line.get('startup_sniffer_enable') or line.get('startup_app_main_return'))
            sequence_exception = sequence_pattern and self.accept_startup_sequence_message(receiver, line)
            if startup_return or sequence_exception:
                line['line_policy_exception'] = self.line_policy_revision
            s['lines'].append(line)
            self.emit('line', receiver=receiver, evidence=copy.deepcopy(line))
            kind = line['kind']
            if kind == 'ready':
                if s['ready'] is not None:
                    self.fail('duplicate_ready:'+receiver,
                              start=int(line['first_read_started_ns']), end=returned_ns)
                else:
                    s['ready'] = line['line_1based']
                    s['streak'] = []
            elif kind == 'row':
                s['previous'] = line
                if error:
                    self.fail(error+':'+receiver, start=int(line['first_read_started_ns']), end=returned_ns)
                elif s['ready'] is not None:
                    if s['last_valid'] is not None and returned_ns-s['last_valid'] > POLICY['freshness_ns']:
                        s['streak'] = []
                        if self.initial_available is not None:
                            self.fail('availability_gap:'+receiver, start=s['last_valid']+POLICY['freshness_ns']+1,
                                      end=returned_ns)
                    s['last_valid'] = returned_ns
                    s['streak'] = (s['streak']+[line])[-3:]
                    if self.windows:
                        w = self.windows[-1]
                        if w['state'] == 'gate' and int(line['first_read_started_ns']) >= w['gate_ns']:
                            s['gate_rows'] = (s['gate_rows']+[line])[-3:]
            elif kind != 'neutral':
                s['streak'] = []; s['gate_rows'] = []
                if startup_return or sequence_exception:
                    # Explicit initialization messages are never readiness rows.
                    continue
                if sequence_pattern:
                    self.fail('startup_message_order:'+receiver,
                              start=int(line['first_read_started_ns']), end=returned_ns)
                    continue
                if kind == 'invalid':
                    reason = 'format:'+receiver
                    if s['ready'] is None:
                        self.connection_reasons.append(reason)
                    else:
                        self.fail(reason, start=int(line['first_read_started_ns']), end=returned_ns)
                elif s['ready'] is not None:
                    self.fail('post_ready_'+kind+':'+receiver,
                              start=int(line['first_read_started_ns']), end=returned_ns)

    def fresh(self, rows):
        return len(rows) == 3 and 0 <= self.now-int(rows[-1]['returned_ns']) <= POLICY['freshness_ns']

    def tick(self):
        if self.close_requested or self.fatal:
            return
        if self.initial_available is None:
            if self.now >= self.a+POLICY['availability_wait_ns']:
                self.fail('initial_availability_timeout'); return
            startup_complete = self.line_policy_revision != STARTUP_SEQUENCE_POLICY or all(
                seen['returned'] for seen in self.startup_messages.values())
            if startup_complete and all(s['opened'] and s['ready'] is not None and self.fresh(s['streak'])
                   for s in self.states.values()):
                self.initial_available = self.now
                self.emit('initial_available', evidence=self.gate_evidence('streak'))
        else:
            for rx, s in self.states.items():
                if self.now-s['last_valid'] > POLICY['freshness_ns']:
                    self.fail('availability_lost:'+rx,
                              start=s['last_valid']+POLICY['freshness_ns']+1)
                    return
        if not self.windows:
            return
        w = self.windows[-1]
        if w['state'] == 'delay':
            if w['start_signal'] is None and self.now >= w['requested_ns']+POLICY['start_cue_delay_ns']:
                w['start_signal'] = self.signal('establish_condition')
            cue = self.signals[w['start_signal']] if w['start_signal'] is not None else None
            if (cue and cue['software_playback_ok'] is True and
                    self.now >= max(w['requested_ns']+POLICY['exit_delay_ns'],
                                    cue['ack_ns']+POLICY['establishment_ns'])):
                w.update(state='gate', gate_ns=self.now, gate_deadline_ns=self.now+POLICY['availability_wait_ns'])
                for s in self.states.values():
                    s['gate_rows'] = []
                self.emit('gate_opened', slot_id=w['id'], gate_ns=self.now)
        elif w['state'] == 'gate':
            if self.now >= w['gate_deadline_ns']:
                self.fail('slot_availability_timeout'); return
            if all(self.fresh(s['gate_rows']) for s in self.states.values()):
                w.update(state='running', T0_ns=self.now, T1_ns=self.now+POLICY['window_ns'],
                         availability_evidence=self.gate_evidence('gate_rows'))
                self.emit('window_started', slot_id=w['id'], T0_ns=w['T0_ns'], T1_ns=w['T1_ns'])
        elif w['state'] == 'running' and self.now >= w['T1_ns']:
            w['state'] = 'complete'
            self.emit('window_ended_connection_open', slot_id=w['id'], T1_ns=w['T1_ns'])
            if not self.summary()['windows'][-1]['pilot_coverage_ok']:
                self.fail('pilot_coverage_failed', connection=False)
                return
        if w['state'] == 'complete' and w['end_signal'] is None and self.now >= w['T1_ns']+POLICY['label_tail_ns']:
            w['end_signal'] = self.signal('window_finished_connection_open')

    def gate_evidence(self, name):
        return {rx: dict(ready_line=s['ready'], row_lines=[r['line_1based'] for r in s[name]])
                for rx, s in self.states.items()}

    def validate_request(self, slot_id, last=False):
        if (type(last) is not bool or self.initial_available is None or self.fatal or
                self.close_requested or len(self.windows) >= len(self.plan['slots']) or
                any(w['label']['status'] != 'declared' or w['state'] != 'complete' or w['last']
                    for w in self.windows)):
            raise ValueError('No retry, overlap, missing declaration or replacement slot')
        slot = self.plan['slots'][len(self.windows)]
        if slot_id != slot['id']:
            raise ValueError('Prospective order required')
        return slot

    def request(self, slot_id, last=False):
        slot = self.validate_request(slot_id, last)
        self.windows.append(dict(id=slot_id, condition=slot['condition'], state='delay', last=last,
            requested_ns=self.now, gate_ns=None, gate_deadline_ns=None, T0_ns=None, T1_ns=None,
            start_signal=None, end_signal=None, reasons=[], availability_evidence=None,
            label=dict(status='pending', declaration_ns=None, timing_uncertainty='unknown')))
        self.emit('slot_requested', slot_id=slot_id, last=last)

    def ack(self, signal_id, success):
        cue = self.signals[signal_id]
        if cue['ack_ns'] is not None or type(success) is not bool:
            raise ValueError('One explicit playback result per cue')
        cue.update(ack_ns=self.now, software_playback_ok=success)
        self.emit('signal_result', signal_id=signal_id, success=success)
        if not success:
            self.fail('notification_failed', connection=False)
        if cue['kind'] == 'window_finished_connection_open' and self.windows[-1]['last']:
            self.close_requested = True

    def validate_declare(self, slot_id, established, maintained, heard, notes):
        w = next(w for w in self.windows if w['id'] == slot_id)
        if w['label']['status'] != 'pending' or w['end_signal'] is None:
            raise ValueError('Declaration requires the actual end cue, once')
        cue = self.signals[w['end_signal']]
        if cue['software_playback_ok'] is not True or any(type(v) is not bool for v in (established, maintained, heard)):
            raise ValueError('Explicit human declaration required')
        return w

    def declare(self, slot_id, established, maintained, heard, notes):
        w = self.validate_declare(slot_id, established, maintained, heard, notes)
        ok = established and maintained and heard and isinstance(notes, str) and not notes.strip()
        w['label'].update(status='declared' if ok else 'uncertain', declaration_ns=self.now,
                          established_before_cue=established, maintained_through_end_cue=maintained,
                          cues_heard=heard, notes=notes, observation_method='operator_declaration')
        self.emit('label_declared', slot_id=slot_id, status=w['label']['status'])
        if not ok:
            self.fail('uncertain_label', connection=False)

    def close_ack(self, receiver, confirmed, reader_stopped, error=None, proof='synthetic_memory_ack'):
        if self.closing_since is None or receiver in self.closed:
            raise ValueError('Close exactly once, after stopping reads')
        self.close_counts[receiver] += 1
        ok = confirmed is True and reader_stopped is True and self.states[receiver]['opened']
        self.closed[receiver] = dict(confirmed=ok, reader_stopped=reader_stopped,
                                     at_ns=self.now, error=error, proof=proof)
        if self.framers[receiver].length:
            self.fail('incomplete_tail:'+receiver)
        if not ok or error:
            self.fail('close_unconfirmed:'+receiver)
        self.emit('port_close_result', receiver=receiver, confirmed=ok, error=error)
        if len(self.closed) == 2 and all(c['confirmed'] and not c['error'] for c in self.closed.values()):
            self.emit('both_ports_closed_confirmed')
            self.signal('both_ports_closed_confirmed')

    def summary(self):
        result = dict(protocol=PROTOCOL, evidence_type=self.evidence_type, physical_execution_enabled=self.evidence_type=='physical_capture',
                      connection_id=self.plan['connection_id'], initial_available_ns=self.initial_available,
                      fatal=self.fatal, connection=dict(quality_ok=not self.connection_reasons and
                          len(self.closed) == 2 and all(c['confirmed'] and not c['error'] for c in self.closed.values()),
                          reasons=list(self.connection_reasons)), closed=copy.deepcopy(self.closed),
                      windows=[], signals=copy.deepcopy(self.signals),
                      campaign_model_suitability='not_evaluated', physical_label_truth='not_observed')
        # Keep historical JSON values exactly reproducible for strict bundles.
        if self.line_policy_revision != STRICT_LINE_POLICY:
            result['line_policy_revision'] = self.line_policy_revision
        if self.line_policy_revision == STARTUP_SEQUENCE_POLICY:
            result['startup_messages'] = copy.deepcopy(self.startup_messages)
        for original in self.windows:
            w = copy.deepcopy(original)
            w['receivers'] = {}
            for rx, s in self.states.items():
                rows = [r for r in s['lines'] if w['T0_ns'] is not None and r['kind'] == 'row' and
                        not r['continuity_error'] and int(r['first_read_started_ns']) >= w['T0_ns'] and
                        int(r['returned_ns']) < w['T1_ns']]
                times = [int(r['returned_ns']) for r in rows]
                bins = [sum(w['T0_ns']+i*5*SECOND <= t < w['T0_ns']+(i+1)*5*SECOND for t in times)
                        for i in range(6)] if w['T0_ns'] is not None else [0]*6
                gaps = ([times[0]-w['T0_ns']] + [b-a for a,b in zip(times,times[1:])] +
                        [w['T1_ns']-times[-1]]) if times else []
                coverage = dict(included_rows=len(rows), bins_5s=bins, gaps_ns=gaps,
                                max_gap_ns=max(gaps) if gaps else None, basic_ok=bool(rows),
                                pilot_ok=bool(rows) and len(rows) >= POLICY['coverage_min_rows'] and
                                  min(bins) >= POLICY['coverage_bin_rows'] and max(gaps) <= POLICY['coverage_gap_ns'])
                w['receivers'][rx] = dict(coverage=coverage, included_line_references=copy.deepcopy(rows))
            w['window_quality_ok'] = w['state'] == 'complete' and not w['reasons'] and all(
                r['coverage']['basic_ok'] for r in w['receivers'].values())
            w['pilot_coverage_ok'] = all(r['coverage']['pilot_ok'] for r in w['receivers'].values())
            w['label_quality_ok'] = w['label']['status'] == 'declared'
            w['eligible'] = not self.fatal and result['connection']['quality_ok'] and w['window_quality_ok'] and w['pilot_coverage_ok'] and w['label_quality_ok']
            result['windows'].append(w)
        result['remaining_slots'] = [dict(s, state='suspended' if self.fatal else 'not_requested')
                                     for s in self.plan['slots'][len(self.windows):]]
        result['tails'] = {rx: dict(bytes=f.length, byte_end=f.offset, sha256=f.hash.hexdigest())
                           for rx, f in self.framers.items()}
        return result
