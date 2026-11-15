"""RX-02-only immutable evidence and replay; independent bundle schema.

Forked topology-specific receipt/audit from v4; append/fsync command path reused.
"""
import hashlib
import json
import os
import sys
from pathlib import Path
from presence_v4_journal import V4Journal, digest, write_new
from presence_rx02 import RECEIVERS, ELIGIBILITY, Rx02Presence, certify_rx02

class Rx02Journal(V4Journal):
    def __init__(self, output, plan, *, allow_physical=False, evidence_type=None, extra_provenance=None,
                 decision_clock=None):
        self.machine = Rx02Presence(plan, allow_physical=allow_physical, evidence_type=evidence_type)
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
            if plan.get('eligibility_revision') == ELIGIBILITY:
                sources += ['src/presence_v4_exploratory.py', 'src/presence_rx02.py', 'src/presence_rx02_journal.py',
                    'src/presence_rx02_uart.py', 'src/presence_v4_uart.py', 'tools/piloto_presencia_rx02.py',
                    'config/pyserial_uart_v4.lock.json']
            provenance = dict(
                implementation_base_commit='9b28addc221468ed1c38e6480a6cf153e5a00c70',
                line_policy_revision=self.machine.line_policy_revision,
                eligibility_revision=plan.get('eligibility_revision', ELIGIBILITY),
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

    def receipt(self):
        m = self.machine
        if set(m.closed) != set(RECEIVERS):
            raise ValueError('Selected RX-02 close attempt must have completed')
        receipt = dict(protocol=m.plan['protocol'], connection_id=m.plan['connection_id'],
            closed=m.closed, selected_confirmed=all(c['confirmed'] and not c['error'] for c in m.closed.values()),
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
        write_new(self.root/'manifest.json', {'schema': 'tesis-presence-rx02-bundle-v1',
            'files': [dict(path=str(p.relative_to(self.root)),
            bytes=p.stat().st_size, sha256=digest(p)) for p in sorted(files)]})
        self.close_files()

    def close_files(self):
        for f in [*self.raw.values(), self.ops]:
            if f is not None and not f.closed:
                f.close()


def audit_rx02(directory):
    """Replay recorded inputs from raw bytes; do not accept recorded quality flags."""
    root = Path(directory)
    manifest = json.loads((root/'manifest.json').read_text())
    names = [e['path'] for e in manifest['files']]
    required = {'plan.json','provenance.json','rx-02.serial.log',
                'operations.jsonl','summary.json','events.json','close-receipt.json'}
    if manifest.get('schema') != 'tesis-presence-rx02-bundle-v1' or not required.issubset(names):
        raise ValueError('Required RX-02 bundle files or schema missing')
    if any(name.startswith('rx-') and name != 'rx-02.serial.log' for name in names):
        raise ValueError('Unexpected receiver raw stream in singleton bundle')
    expected = {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and p.name != 'manifest.json'}
    if len(set(names)) != len(names) or set(names) != expected:
        raise ValueError('Manifest file set differs')
    for e in manifest['files']:
        p = (root/e['path']).resolve()
        if not p.is_relative_to(root.resolve()) or p.stat().st_size != e['bytes'] or digest(p) != e['sha256']:
            raise ValueError('Manifest integrity failure: '+e['path'])
    provenance = json.loads((root/'provenance.json').read_text())
    plan = json.loads((root/'plan.json').read_text())
    m = Rx02Presence(plan, allow_physical=True,
                             evidence_type=provenance['evidence_type'])
    if provenance.get('line_policy_revision') != m.line_policy_revision:
        raise ValueError('Line policy provenance contradicts plan')
    if provenance.get('eligibility_revision') != ELIGIBILITY:
        raise ValueError('Eligibility provenance contradicts plan')
    exploratory = plan.get('eligibility_revision') == ELIGIBILITY
    source_root = Path(__file__).resolve().parents[1]
    required_sources = {'src/presence_rx02.py', 'src/presence_rx02_journal.py',
        'src/presence_rx02_uart.py', 'src/persistent_presence_v4.py', 'src/presence_v4_exploratory.py',
        'src/presence_v4_uart.py', 'src/presence_v4_journal.py', 'src/presence_v4_pty.py',
        'src/presence_v4_audio.py', 'src/availability_window.py', 'src/capture_csi_multi.py',
        'src/capture_csi.py', 'src/preserving_serial.py', 'src/controlled_protocol.py',
        'tools/campana_presencia_v4.py', 'tools/piloto_presencia_rx02.py',
        'config/csi_esp32s3.json', 'config/pyserial_uart_v4.lock.json'}
    entries = provenance['sources']
    if len(entries) != len(required_sources) or {s['path'] for s in entries} != required_sources:
        raise ValueError('Singleton source set differs')
    for entry in entries:
        path = source_root/entry['path']
        if entry['sha256'] != digest(path) or entry['bytes'] != path.stat().st_size:
            raise ValueError('Singleton source provenance differs: '+entry['path'])
    if (provenance['physical_transport_enabled'] != (m.evidence_type=='physical_capture') or
            provenance['plan_sha256'] != digest(root/'plan.json')):
        raise ValueError('Provenance contradicts plan or evidence type')
    if m.evidence_type == 'physical_capture':
        from presence_v4_uart import check_authorization
        reference = provenance.get('transport', {}).get('authorization_reference')
        check_authorization(reference)
        authorization = json.loads((root/'authorization-consumed.json').read_text())
        if (authorization.get('reference') != reference or authorization.get('consumed') is not True or
            authorization.get('retry_allowed') is not False or
            authorization.get('connection_id') != plan['connection_id'] or
            authorization.get('protocol') != plan['protocol']):
            raise ValueError('Consumed authorization evidence differs')
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
    if (receipt['protocol'] != plan['protocol'] or receipt['connection_id'] != plan['connection_id'] or
            receipt['closed'] != result['closed'] or receipt['read_loop_stopped'] is not True or
            receipt['timer_is_close_proof'] is not False or
            not 0 < receipt['operations_prefix_bytes'] <= len(operations_bytes) or
            hashlib.sha256(operations_bytes[:receipt['operations_prefix_bytes']]).hexdigest() != receipt['operations_prefix_sha256'] or
            receipt['selected_confirmed'] != (set(m.closed) == set(RECEIVERS) and all(c['confirmed'] and not c['error'] for c in m.closed.values())) or
            any(receipt['raw_sha256'][rx] != hashlib.sha256(raw[rx]).hexdigest() for rx in RECEIVERS)):
        raise ValueError('Close receipt differs')
    report = dict(integrity_ok=True, replay_ok=True, operations=len(operations), state=result,
                  audit_activity=dict(physical_UART_opened=False))
    if exploratory:
        report['exploratory_eligibility'] = certify_rx02(root, provenance, result)
    return report
