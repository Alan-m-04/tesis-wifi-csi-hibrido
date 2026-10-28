"""Exclusive append-only evidence and deterministic offline replay for v4."""
import hashlib
import json
import os
import sys
from pathlib import Path

from capture_csi_multi import RECEIVERS
from persistent_presence_v4 import PersistentPresenceV4


def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def write_new(path, value):
    with Path(path).open('x') as f:
        json.dump(value, f, ensure_ascii=False, allow_nan=False, indent=2)
        f.write('\n'); f.flush(); os.fsync(f.fileno())
    fd = os.open(Path(path).parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class V4Journal:
    def __init__(self, output, plan, *, allow_physical=False, evidence_type=None, extra_provenance=None,
                 decision_clock=None):
        self.machine = PersistentPresenceV4(plan, allow_physical=allow_physical, evidence_type=evidence_type)
        self.root = Path(output)
        self.root.mkdir(parents=True, exist_ok=False)
        self.raw, self.ops = {}, None
        self.seq = 0
        self.decision_clock = decision_clock
        self.last_command_applied = False
        try:
            write_new(self.root/'plan.json', plan)
            repository = Path(__file__).resolve().parents[1]
            sources = ['src/'+name for name in ('persistent_presence_v4.py', 'presence_v4_journal.py',
                'presence_v4_pty.py', 'presence_v4_audio.py', 'availability_window.py',
                'capture_csi_multi.py', 'capture_csi.py', 'preserving_serial.py', 'controlled_protocol.py')]
            sources += ['tools/campana_presencia_v4.py', 'config/csi_esp32s3.json']
            provenance = dict(
                implementation_base_commit='51246df4f288ede695b81f8eca8336820e6cb126',
                evidence_type=self.machine.evidence_type, python_version=sys.version,
                physical_transport_enabled=self.machine.evidence_type=='physical_capture', plan_sha256=digest(self.root/'plan.json'),
                sources=[dict(path=name, sha256=digest(repository/name), bytes=(repository/name).stat().st_size)
                         for name in sources])
            if extra_provenance:
                provenance['transport'] = extra_provenance
            write_new(self.root/'provenance.json', provenance)
            for rx in RECEIVERS:
                self.raw[rx] = (self.root/(rx.lower()+'.serial.log')).open('xb')
            self.ops = (self.root/'operations.jsonl').open('x')
        except BaseException:
            self.close_files()
            raise

    def command(self, op, now_ns, **data):
        self.last_command_applied = False
        if op in ('request', 'declare'):
            # Invalid operator input is rejected without corrupting the journal.
            getattr(self.machine, 'validate_'+op)(**data)
        stored = dict(data)
        if op == 'chunk':
            chunk = stored.pop('chunk')
            raw = self.raw[data['receiver']]
            offset = raw.tell()
            raw.write(chunk); raw.flush(); os.fsync(raw.fileno())
            stored.update(offset=offset, size=len(chunk), sha256=hashlib.sha256(chunk).hexdigest())
        if self.decision_clock is not None:
            # UART: raw data is durable first, then sample the actual decision
            # time. Persist the chosen operation afterwards; failure rejects the
            # attempt, never backdates or replaces an already chosen T0.
            now_ns = self.decision_clock()
            self.machine.apply(op, now_ns, **data)
            self.last_command_applied = True
        record = dict(seq=self.seq, op=op, now_ns=now_ns, data=stored)
        self.ops.write(json.dumps(record, ensure_ascii=False, allow_nan=False)+'\n')
        self.ops.flush(); os.fsync(self.ops.fileno())
        self.seq += 1
        if not self.last_command_applied:
            self.machine.apply(op, now_ns, **data)
            self.last_command_applied = True

    def receipt(self):
        m = self.machine
        if len(m.closed) != 2:
            raise ValueError('Both close attempts must have completed')
        receipt = dict(protocol=m.plan['protocol'], connection_id=m.plan['connection_id'],
            closed=m.closed, both_confirmed=all(c['confirmed'] and not c['error'] for c in m.closed.values()),
            read_loop_stopped=True, timer_is_close_proof=False,
            raw_sha256={rx: digest(self.root/(rx.lower()+'.serial.log')) for rx in RECEIVERS})
        receipt['operations_prefix_bytes'] = (self.root/'operations.jsonl').stat().st_size
        receipt['operations_prefix_sha256'] = digest(self.root/'operations.jsonl')
        write_new(self.root/'close-receipt.json', receipt)
        return receipt

    def finalize(self, runtime):
        for f in self.raw.values():
            f.flush(); os.fsync(f.fileno())
        self.ops.flush(); os.fsync(self.ops.fileno())
        write_new(self.root/'summary.json', dict(state=self.machine.summary(), runtime=runtime))
        write_new(self.root/'events.json', self.machine.events)
        files = [p for p in self.root.rglob('*') if p.is_file()]
        write_new(self.root/'manifest.json', {'schema': 'tesis-presence-persistent-v4-bundle-v1',
            'files': [dict(path=str(p.relative_to(self.root)),
            bytes=p.stat().st_size, sha256=digest(p)) for p in sorted(files)]})
        self.close_files()

    def close_files(self):
        for f in [*self.raw.values(), self.ops]:
            if f is not None and not f.closed:
                f.close()


def audit_v4(directory):
    """Replay recorded inputs from raw bytes; do not accept recorded quality flags."""
    root = Path(directory)
    manifest = json.loads((root/'manifest.json').read_text())
    names = [e['path'] for e in manifest['files']]
    required = {'plan.json','provenance.json','rx-01.serial.log','rx-02.serial.log',
                'operations.jsonl','summary.json','events.json','close-receipt.json'}
    if manifest.get('schema') != 'tesis-presence-persistent-v4-bundle-v1' or not required.issubset(names):
        raise ValueError('Required v4 bundle files or schema missing')
    expected = {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and p.name != 'manifest.json'}
    if len(set(names)) != len(names) or set(names) != expected:
        raise ValueError('Manifest file set differs')
    for e in manifest['files']:
        p = (root/e['path']).resolve()
        if not p.is_relative_to(root.resolve()) or p.stat().st_size != e['bytes'] or digest(p) != e['sha256']:
            raise ValueError('Manifest integrity failure: '+e['path'])
    provenance = json.loads((root/'provenance.json').read_text())
    m = PersistentPresenceV4(json.loads((root/'plan.json').read_text()), allow_physical=True,
                             evidence_type=provenance['evidence_type'])
    if (provenance['physical_transport_enabled'] != (m.evidence_type=='physical_capture') or
            provenance['plan_sha256'] != digest(root/'plan.json')):
        raise ValueError('Provenance contradicts plan or evidence type')
    raw = {rx: (root/(rx.lower()+'.serial.log')).read_bytes() for rx in RECEIVERS}
    offsets = dict.fromkeys(RECEIVERS, 0)
    operations = [json.loads(line) for line in (root/'operations.jsonl').read_text().splitlines()]
    for index, record in enumerate(operations):
        if record['seq'] != index:
            raise ValueError('Operation sequence differs')
        data = dict(record['data'])
        if record['op'] == 'chunk':
            rx = data['receiver']; offset = data.pop('offset'); size = data.pop('size'); sha = data.pop('sha256')
            if offset != offsets[rx] or size <= 0:
                raise ValueError('Non-contiguous raw reference')
            chunk = raw[rx][offset:offset+size]
            if len(chunk) != size or hashlib.sha256(chunk).hexdigest() != sha:
                raise ValueError('Raw chunk hash differs')
            offsets[rx] += size; data['chunk'] = chunk
        m.apply(record['op'], record['now_ns'], **data)
    if any(offsets[rx] != len(raw[rx]) for rx in RECEIVERS):
        raise ValueError('Unreferenced raw bytes')
    result = m.summary()
    if result != json.loads((root/'summary.json').read_text())['state']:
        raise ValueError('Replayed summary differs')
    if m.events != json.loads((root/'events.json').read_text()):
        raise ValueError('Replayed events differ')
    receipt = json.loads((root/'close-receipt.json').read_text())
    operations_bytes = (root/'operations.jsonl').read_bytes()
    if (receipt['closed'] != result['closed'] or not receipt['read_loop_stopped'] or
            receipt['timer_is_close_proof'] or
            not 0 < receipt['operations_prefix_bytes'] <= len(operations_bytes) or
            hashlib.sha256(operations_bytes[:receipt['operations_prefix_bytes']]).hexdigest() != receipt['operations_prefix_sha256'] or
            receipt['both_confirmed'] != (len(m.closed) == 2 and all(c['confirmed'] and not c['error'] for c in m.closed.values())) or
            any(receipt['raw_sha256'][rx] != hashlib.sha256(raw[rx]).hexdigest() for rx in RECEIVERS)):
        raise ValueError('Close receipt differs')
    return dict(integrity_ok=True, replay_ok=True, operations=len(operations), state=result)
