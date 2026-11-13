"""Read the new RX-02 diagnostic only after its native open is bound to this host."""

from collections import deque
import hashlib
import json
import os
from pathlib import Path
import time
import uuid

from csi_live_observer import (MAX_OPS_PER_POLL, MAX_RECORD, ROOT, STALE_NS, Observer, binding,
                               boot_id, read_bounded, regular, small_json)
from persistent_presence_v4 import _StartupSequenceFramer
from rx02_diagnostic.contract import VIEW_CONNECTION, VIEW_IDENTITY_REVISION


ATTEMPT = VIEW_CONNECTION
METADATA_LIMIT = 128 * 1024


def clock_domain():
    return dict(clock='host_monotonic_ns', boot_id=boot_id(), time_namespace=os.readlink('/proc/self/ns/time'))


def clock_binding(bundle, reference):
    return dict(schema='rx02-live-clock-1', attempt_id=ATTEMPT, bundle=str(bundle.resolve()),
                domain=clock_domain(), reference=reference,
                hashes={name: hashlib.sha256(read_bounded(bundle / name, METADATA_LIMIT)).hexdigest()
                        for name in ('plan.json', 'provenance.json', 'authorization-consumed.json')})


class Rx02Observer(Observer):
    def __init__(self, bundle, view, plan, reference):
        self.root = Path(bundle).resolve()
        self.view = Path(view).resolve()
        if self.view.is_relative_to(self.root) or self.root.is_relative_to(self.view):
            raise ValueError('La salida de la vista debe estar fuera del bundle')
        self.proof_path = self.view / 'clock-binding.json'
        self.proof = small_json(self.proof_path, METADATA_LIMIT)
        if self.proof != clock_binding(self.root, reference):
            raise ValueError('Constancia de reloj, procedencia o ruta incompatible')
        self.plan = small_json(self.root / 'plan.json', METADATA_LIMIT)
        provenance = small_json(self.root / 'provenance.json', METADATA_LIMIT)
        consumed = small_json(self.root / 'authorization-consumed.json', METADATA_LIMIT)
        transport = provenance.get('transport', {})
        identity = plan['live_view']['identity']
        if (self.plan != plan or plan['connection_id'] != ATTEMPT or plan['partition_group'] != ATTEMPT or
                plan['live_view']['attempt_id'] != ATTEMPT or
                plan['live_view']['identity_revision'] != VIEW_IDENTITY_REVISION or
                plan['live_view']['clock_domain'] != self.proof['domain'] or
                provenance.get('plan_sha256') != self.proof['hashes']['plan.json'] or
                provenance.get('evidence_type') != 'physical_capture' or
                provenance.get('physical_transport_enabled') is not True or
                transport.get('backend') != 'UART' or
                transport.get('identities') != {'RX-02': identity} or
                transport.get('authorization_reference') != reference or
                consumed.get('reference') != reference or consumed.get('consumed') is not True or
                consumed.get('retry_allowed') is not False or
                consumed.get('protocol') != plan['protocol'] or
                consumed.get('connection_id') != plan['connection_id']):
            raise ValueError('El bundle no pertenece al intento RX-02 revisado')

        self.paths = [regular(self.root / name) for name in ('operations.jsonl', 'rx-02.serial.log')]
        self.bindings = [binding(path) for path in self.paths]
        self.source_meta = {name: read_bounded(self.root / name, METADATA_LIMIT) for name in self.proof['hashes']}
        if any(hashlib.sha256(data).hexdigest() != self.proof['hashes'][name]
               for name, data in self.source_meta.items()):
            raise ValueError('Los metadatos de origen cambiaron')
        self.host_boot_id = self.proof['domain']['boot_id']
        self.clock_binding_origin = 'rx02_live_capture_worker'
        self.clock, self.stale_ns, self.budget = time.monotonic_ns, STALE_NS, MAX_OPS_PER_POLL
        self.rows, self.framer = deque(maxlen=8), _StartupSequenceFramer('RX-02')
        self.config = small_json(ROOT / 'config/csi_esp32s3.json', METADATA_LIMIT)['firmware_ltf_config']
        self.offset = self.raw_offset = self.seq = self.total = self.dropped = self.invalid = self.reads = self.revision = 0
        self.last_sample = self.error = None
        self.source_stopped = self.observer_stopped = False
        self.reason = 'Esperando una fila CSI válida'
        self.id = str(uuid.uuid4())
        self.ops = self.paths[0].open('rb')
        try:
            self.raw = self.paths[1].open('rb')
            for stream, expected in zip((self.ops, self.raw), self.bindings, strict=True):
                stat = os.fstat(stream.fileno())
                if (stat.st_dev, stat.st_ino) != expected:
                    raise ValueError('Archivo de origen reemplazado durante la apertura')
            self._verify_open(identity)
        except BaseException:
            self.ops.close()
            if hasattr(self, 'raw'):
                self.raw.close()
            raise

    def _verify_open(self, identity):
        # The capture worker publishes its binding after the native constructor
        # has recorded opened. No chunk may precede that record.
        for seq in range(self.budget):
            line = self.ops.readline(MAX_RECORD + 1)
            if not line.endswith(b'\n') or len(line) > MAX_RECORD:
                break
            record = json.loads(line)
            if record['seq'] != seq:
                break
            if record['op'] == 'opened':
                data = record['data']
                if (data['receiver'] == 'RX-02' and data['identity_binding'] ==
                        dict(identity=identity, opened_fingerprint=identity['node_fingerprint'])):
                    self.open_prefix_bytes = self.ops.tell()
                    self.ops.seek(0)
                    self.open_prefix_sha256 = hashlib.sha256(self.ops.read(self.open_prefix_bytes)).hexdigest()
                    return
                break
            if record['op'] not in ('begin', 'tick', 'storage_check'):
                break
        raise ValueError('Falta la apertura nativa ligada a la identidad del preflight')

    def poll(self):
        if not self.error:
            try:
                if small_json(self.proof_path, METADATA_LIMIT) != self.proof:
                    raise ValueError('Cambió la constancia de reloj')
                self.ops.seek(0)
                if hashlib.sha256(self.ops.read(self.open_prefix_bytes)).hexdigest() != self.open_prefix_sha256:
                    raise ValueError('Cambió la apertura nativa del journal')
            except (OSError, ValueError) as exc:
                self.error = str(exc)[:512]
        super().poll()
        if self.source_stopped:
            self.reason = 'Detención registrada en el journal RX-02. Cierre sujeto a auditoría.'

    def snapshot(self):
        result = super().snapshot()
        result.update(mode='CSI PROVISIONAL · RX-02', evidence_type='physical_capture',
                      attempt_id=ATTEMPT, physical_input_enabled=True, detector='SIN DECISIONES DE PRESENCIA',
                      capture_reference=self.proof['reference'], clock_domain=self.proof['domain'])
        return result


def current_rx02_snapshot(path):
    data = small_json(path)
    if (data.get('schema') != 'csi-live-preview-1' or data.get('attempt_id') != ATTEMPT or
            data.get('connection_id') != ATTEMPT or
            data.get('evidence_type') != 'physical_capture' or data.get('clock_domain') != clock_domain()):
        raise ValueError('Vista RX-02 o reloj incompatible')
    now = time.monotonic_ns()
    stamp = data['last_sample_ns']
    age = None if stamp is None else (now - int(stamp)) / 1e6
    if age is not None and age < 0:
        raise ValueError('Muestra fuera del reloj de observación')
    data.update(sample_age_ms=age, window_T0_ns=str(max(0, now - 30_000_000_000)), physical_close_verified=False)
    if data['flow_state'] != 'detenido' and age is not None and age >= data['stale_after_ms']:
        data.update(flow_state='datos_antiguos', reason='Sin muestra reciente. Cierre sujeto a auditoría.')
    try:
        audit = small_json(Path(path).parent / 'audit-result.json', METADATA_LIMIT)
    except FileNotFoundError:
        return data
    if audit.get('attempt_id') != ATTEMPT or audit.get('reference') != data['capture_reference']:
        raise ValueError('Auditoría de otro intento')
    closed = all(audit.get(key) is True for key in ('close_verified', 'integrity_ok', 'replay_ok'))
    data.update(audit_status='completed', physical_close_verified=closed)
    return data
