"""Prospective v3 gate. Pure bytes/clocks; no serial discovery or opening.

Readers publish one whole returned chunk under a common lock. Decisions take
that same lock; never decide between two lines of an already published chunk.
Late publication remains visible and can invalidate (never move) an activation.
"""
import csv
import hashlib
import re
import threading
import time

import capture_csi_multi as capture
from controlled_protocol import AVAILABILITY_V3

SGR = re.compile(r'\x1b\[[0-9;]*m')
RESET = re.compile(r'ESP-ROM:|\brst:')
LOG = re.compile(r'[IWE] \([0-9]+\) [A-Za-z0-9_]+: [\x20-\x7e]*')
TAGS = {'RX-01': 'csi_recv', 'RX-02': 'csi_recv_02'}
HEADER = ','.join(capture.FIELDS)


def classify_line(data, rx):
    """Strict UTF-8/LF and exact READY; original bytes are never normalized."""
    if not data.endswith(b'\n') or len(data) - 1 > 65536:
        return {'kind': 'invalid', 'reason': 'incomplete_or_oversized'}
    try:
        text = SGR.sub('', data[:-1].removesuffix(b'\r').decode('utf-8', 'strict'))
    except UnicodeDecodeError:
        info = {'kind': 'invalid', 'reason': 'invalid_utf8'}
        if RESET.search(data.decode('ascii', errors='replace')):
            info['fatal_if_ready'] = 'post_ready_reset'
        return info
    if text in ('', HEADER):
        return {'kind': 'neutral'}
    ready = (rf'I \([0-9]+\) {TAGS[rx]}: {rx} READY channel=11 HT20 '
             rf'UART0=115200 raw CSI; source={re.escape(capture.SOURCE)}')
    if re.fullmatch(ready, text):
        return {'kind': 'ready'}
    if RESET.search(text):
        if not text.startswith(('ESP-ROM:', 'rst:')):
            return {'kind': 'invalid', 'reason': 'embedded_boot_marker', 'fatal_if_ready': 'post_ready_reset'}
        return {'kind': 'reset', 'reason': 'observed_boot_marker'}
    if capture.ERROR.search(text):
        return {'kind': 'error', 'reason': 'observed_error_message'}
    if 'READY' in text:
        return {'kind': 'invalid', 'reason': 'nonconforming_ready', 'fatal_if_ready': 'conflicting_ready'}
    if text.startswith('CSI_DATA,'):
        try:
            _, record, n = capture.validate_sample(text)
            if record['mac'].lower() != capture.SOURCE or any(n[k] != value for k, value in
                    {'channel': 11, 'bandwidth': 0, 'rx_state': 0, 'len': 256,
                     'first_word_invalid': 0, 'sig_mode': 1, 'mcs': 0, 'stbc': 0}.items()):
                raise ValueError('profile')
        except (ValueError, TypeError, csv.Error, StopIteration):
            return {'kind': 'invalid', 'reason': 'csi_format_or_profile'}
        return {'kind': 'row', 'id': n['id'], 'local_timestamp': n['local_timestamp'],
                'queue_drops': n['queue_drops']}
    if LOG.fullmatch(text) or text.startswith(('Build:', 'Saved PC:', 'SPIWP:', 'mode:', 'load:', 'entry ')):
        return {'kind': 'info'}
    return {'kind': 'invalid', 'reason': 'unrecognized_bytes'}


class LineFramer:
    """Bounded parser memory, unbounded evidence length/offset; raw owner keeps all bytes."""
    def __init__(self, rx):
        self.rx, self.offset, self.number = rx, 0, 0
        self.prefix, self.length = bytearray(), 0
        self.first = None
        self.hash = hashlib.sha256()

    def feed(self, chunk, read_index, event):
        found = []
        parts = chunk.split(b'\n')
        for index, part in enumerate(parts):
            complete = index < len(parts) - 1
            piece = part + (b'\n' if complete else b'')
            if not piece:
                continue
            if self.first is None:
                self.first = {'first_read_index': read_index, 'first_read_started_ns': event['started_ns'],
                              'byte_offset': self.offset}
            self.prefix.extend(piece[:max(0, 65538 - len(self.prefix))])
            self.hash.update(piece)
            self.length += len(piece)
            self.offset += len(piece)
            if complete:
                self.number += 1
                info = classify_line(bytes(self.prefix), self.rx) if self.length <= 65537 else {
                    'kind': 'invalid', 'reason': 'incomplete_or_oversized'}
                found.append(dict(info, **self.first, line_1based=self.number, byte_end=self.offset,
                    byte_length=self.length, line_sha256=self.hash.hexdigest(), last_read_index=read_index,
                    returned_ns=event['returned_ns']))
                self.prefix.clear(); self.length = 0; self.first = None
                self.hash = hashlib.sha256()
        return found


def transition_error(previous, current):
    if previous is None:
        return None
    if current['id'] <= previous['id']:
        return 'callback_restart'
    if current['id'] != previous['id'] + 1:
        return 'callback_gap'
    if not 0 < (current['local_timestamp'] - previous['local_timestamp']) % 2**32 <= 10_000_000:
        return 'local_clock_discontinuity'
    if current['queue_drops'] != previous['queue_drops']:
        return 'queue_drop_change'
    return None


class AvailabilityCoordinator:
    def __init__(self, *, clock=time.monotonic_ns, sink=None, window_ns=None, wait_ns=None):
        self.clock, self.sink = clock, sink
        self.window_ns = AVAILABILITY_V3['window_ns'] if window_ns is None else window_ns
        self.wait_ns = AVAILABILITY_V3['max_wait_ns'] if wait_ns is None else wait_ns
        self.lock = threading.RLock()
        self.events = []
        self.framers = {rx: LineFramer(rx) for rx in capture.RECEIVERS}
        self.states = {rx: {'active': False, 'ready': None, 'streak': [], 'previous': None,
                            'last_read_index': -1} for rx in capture.RECEIVERS}
        self.a = self.d = self.t0 = self.t1 = self.stop_deadline = None
        self.fatal = None
        self.activation_conflicts = []
        self.timed_out = False

    def emit(self, kind, **data):
        event = dict(seq=len(self.events), kind=kind, processed_ns=str(self.clock()), **data)
        self.events.append(event)
        if self.sink is not None:
            self.sink(event)
        return event

    def begin(self):
        with self.lock:
            if self.a is not None:
                raise ValueError('Already begun')
            self.a = self.clock(); self.d = self.a + self.wait_ns
            self.emit('begin', A_ns=str(self.a), D_ns=str(self.d))

    def reader_active(self, rx):
        with self.lock:
            self.states[rx]['active'] = True
            self.emit('reader_active', receiver=rx)

    def fail(self, reason, rx=None):
        with self.lock:
            if self.fatal is None:
                self.fatal = reason
            self.emit('fatal', receiver=rx, reason=reason)

    def publish(self, rx, chunk, event):
        with self.lock:
            state = self.states[rx]
            read_index = state['last_read_index'] + 1
            state['last_read_index'] = read_index
            batch = self.emit('chunk', receiver=rx, read_index=read_index, read=dict(event),
                              chunk_sha256=hashlib.sha256(chunk).hexdigest())
            for line in self.framers[rx].feed(chunk, read_index, event):
                self.consume(rx, line, batch['seq'])
            self.emit('batch_complete', receiver=rx, chunk_seq=batch['seq'])

    def consume(self, rx, line, chunk_seq):
        state = self.states[rx]
        if state['streak'] and self.t0 is None:
            last = self.events[state['streak'][-1]]['evidence']
            if self.clock() - int(last['returned_ns']) > AVAILABILITY_V3['freshness_ns']:
                self.emit('freshness_expired', receiver=rx, streak=list(state['streak']))
                state['streak'] = []
        kind = line['kind']
        error = transition_error(state['previous'], line) if kind == 'row' else None
        if error:
            line = dict(line, continuity_error=error)
        evidence = self.emit('line', receiver=rx, chunk_seq=chunk_seq, evidence=line)
        bad = kind in ('invalid', 'error', 'reset') or error is not None or (
            kind == 'ready' and state['ready'] is not None) or (kind == 'info' and state['ready'] is not None)
        if self.t0 is not None and int(line['returned_ns']) < self.t0 and bad:
            self.activation_conflicts.append(evidence['seq'])
            self.emit('activation_inconsistent', receiver=rx, evidence_seq=evidence['seq'])
        if line.get('fatal_if_ready') and state['ready'] is not None:
            self.fail(line['fatal_if_ready'], rx)
        if kind == 'ready':
            if state['ready'] is not None:
                self.fail('duplicate_ready', rx)
            else:
                state['ready'] = evidence['seq']; state['streak'] = []
        elif kind == 'row':
            if error == 'callback_restart' and state['ready'] is not None:
                self.fail(error, rx)
            if error:
                state['streak'] = []
            elif state['ready'] is not None:
                state['streak'] = (state['streak'] + [evidence['seq']])[-3:]
            state['previous'] = line
        elif kind != 'neutral':
            state['streak'] = []
            if kind in ('reset', 'error') and state['ready'] is not None:
                self.fail('post_ready_' + kind, rx)

    def evaluate(self):
        with self.lock:
            if self.a is None or self.t0 is not None or self.timed_out or self.fatal:
                return
            now = self.clock()
            if now >= self.d:
                self.timed_out = True; self.stop_deadline = self.d
                self.emit('availability_timeout', deadline_ns=str(self.d))
                return
            eligible = True
            for rx, state in self.states.items():
                if state['streak']:
                    last = self.events[state['streak'][-1]]['evidence']
                    if now - int(last['returned_ns']) > AVAILABILITY_V3['freshness_ns']:
                        self.emit('freshness_expired', receiver=rx, streak=list(state['streak']))
                        state['streak'] = []
                eligible &= state['active'] and state['ready'] is not None and len(state['streak']) == 3
            if eligible:
                # All evidence and pending published batches are locked. The actual
                # decision time is sampled again; never backdate to a row's time.
                now = self.clock()
                if now >= self.d or any(now - int(self.events[s['streak'][-1]]['evidence']['returned_ns']) >
                                        AVAILABILITY_V3['freshness_ns'] for s in self.states.values()):
                    return
                self.t0, self.t1 = now, now + self.window_ns
                self.stop_deadline = self.t1
                self.emit('armed', T0_ns=str(self.t0), T1_ns=str(self.t1), evidence={rx: {
                    'ready_seq': state['ready'], 'row_seqs': list(state['streak'])} for rx, state in self.states.items()})

    def reader_finished(self, rx, reason, stopped_ns=None):
        with self.lock:
            self.states[rx]['active'] = False
            when = self.clock() if stopped_ns is None else int(stopped_ns)
            event = self.emit('reader_finished', receiver=rx, reason=reason, stopped_ns=str(when))
            if self.t0 is not None and when < self.t0:
                self.activation_conflicts.append(event['seq'])
                self.emit('activation_inconsistent', receiver=rx, evidence_seq=event['seq'])
            if self.t0 is not None and when < self.t1:
                self.fail('reader_termination_before_T1', rx)
            elif self.t0 is None and not self.timed_out and not self.fatal:
                self.fail('reader_termination_before_availability', rx)

    def snapshot(self):
        with self.lock:
            return {'A_ns': None if self.a is None else str(self.a),
                    'D_ns': None if self.d is None else str(self.d),
                    'T0_ns': None if self.t0 is None else str(self.t0),
                    'T1_ns': None if self.t1 is None else str(self.t1),
                    'stop_deadline_ns': None if self.stop_deadline is None else str(self.stop_deadline),
                    'fatal': self.fatal, 'timed_out': self.timed_out,
                    'activation_conflicts': list(self.activation_conflicts)}
