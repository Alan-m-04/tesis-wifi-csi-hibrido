"""Bounded, read-only provisional CSI observer. Current input is synthetic only.

No UART constructor, capture coordinator, labels or model execution lives here.
The native journal remains the sole owner of the original records.
"""
from collections import deque
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time
import uuid

from persistent_presence_v4 import _StartupSequenceFramer
from presence_rx02 import validate_plan
from consolidar_rx02_c01 import frame_from_reference
from presence_offline import ACTIVE,INDICES

MAX_RECORD=16384
MAX_CHUNK=16384
MAX_ROWS=300
MAX_OPS_PER_POLL=64
MAX_SNAPSHOT=2*1024*1024
STALE_NS=2_000_000_000  # Display freshness only, never an experimental criterion.
ROOT=Path(__file__).resolve().parents[1]


class SharedFlag:
    """One shared byte, with no process-owned mutex to poison on hard interruption."""
    def __init__(self,context):self.value=context.RawValue('b',0)
    def set(self):self.value.value=1
    def is_set(self):return bool(self.value.value)
    def wait(self,seconds):
        deadline=time.monotonic()+seconds
        while not self.is_set():
            left=deadline-time.monotonic()
            if left<=0:return False
            time.sleep(min(.01,left))
        return True


def boot_id():return Path('/proc/sys/kernel/random/boot_id').read_text().strip()


def guard(event,args):
    if event=='open' and isinstance(args[0],(str,bytes)):
        p=os.fsdecode(args[0])
        if re.search(r'C0[456]',p,re.I) or p.startswith(('/dev/serial','/dev/tty')):
            raise PermissionError('Reserved data and physical UART are forbidden in this demo')


def regular(path):
    p=Path(path)
    if re.search(r'C0[456]',str(p.resolve()),re.I) or str(p.resolve()).startswith('/dev/'):
        raise PermissionError('Forbidden source')
    if p.is_symlink() or not stat.S_ISREG(p.stat().st_mode):raise ValueError('Regular non-symlink file required')
    return p


def small_json(path,limit=MAX_SNAPSHOT):
    return json.loads(read_bounded(path,limit))


def read_bounded(path,limit):
    p=regular(path)
    with p.open('rb') as f:data=f.read(limit+1)
    if len(data)>limit:raise ValueError('JSON size limit exceeded')
    return data


def atomic_json(path,value):
    data=json.dumps(value,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()
    if len(data)>MAX_SNAPSHOT:raise ValueError('Snapshot size limit exceeded')
    path=Path(path);temp=path.with_suffix('.pending')
    with temp.open('wb') as f:f.write(data)
    os.replace(temp,path)  # One replaceable slot, no consumer acknowledgement.


def binding(path):
    s=Path(path).stat();return (s.st_dev,s.st_ino)


class Observer:
    def __init__(self,bundle,*,clock=time.monotonic_ns,stale_ns=STALE_NS,max_rows=MAX_ROWS,budget=MAX_OPS_PER_POLL,clock_binding=None):
        if not 1<=max_rows<=MAX_ROWS or not 1<=budget<=MAX_OPS_PER_POLL or stale_ns<=0:raise ValueError('Invalid display limits')
        self.root=Path(bundle).resolve()
        if re.search(r'C0[456]',str(self.root),re.I):raise PermissionError('Reserved bundle')
        self.plan=small_json(self.root/'plan.json',131072)
        provenance=small_json(self.root/'provenance.json',131072)
        if provenance.get('evidence_type')!='synthetic_fixture' or provenance.get('physical_transport_enabled') is not False:
            raise ValueError('Physical/historical sources are disabled; use the synthetic fixture')
        validate_plan(self.plan)
        if provenance.get('plan_sha256')!=hashlib.sha256(read_bounded(self.root/'plan.json',131072)).hexdigest():raise ValueError('Plan hash mismatch')
        transport=provenance.get('transport',{})
        self.clock_binding_origin='embedded_synthetic_provenance'
        clock_meta=transport
        if clock_binding is not None:
            # Only the owned-PTY laboratory may attest its explicitly injected
            # monotonic clock externally. Never alter native capture provenance.
            expected=dict(schema='synthetic-PTY-clock-binding-1',bundle=str(self.root),
                clock_domain='host_monotonic_ns',host_boot_id=boot_id(),
                plan_sha256=hashlib.sha256(read_bounded(self.root/'plan.json',131072)).hexdigest(),
                provenance_sha256=hashlib.sha256(read_bounded(self.root/'provenance.json',131072)).hexdigest())
            if transport.get('backend')!='synthetic_serial_backend' or clock_binding!=expected:
                raise ValueError('Invalid synthetic PTY clock binding')
            clock_meta=clock_binding;self.clock_binding_origin='external_synthetic_PTY_attestation'
        if clock_meta.get('clock_domain')!='host_monotonic_ns' or clock_meta.get('host_boot_id')!=boot_id():
            raise ValueError('Sample freshness requires this host boot and monotonic clock')
        self.host_boot_id=clock_meta['host_boot_id']
        self.clock,self.stale_ns,self.budget=clock,stale_ns,budget
        self.rows=deque(maxlen=max_rows);self.framer=_StartupSequenceFramer('RX-02')
        self.config=json.loads((ROOT/'config/csi_esp32s3.json').read_text())['firmware_ltf_config']
        self.paths=[regular(self.root/n) for n in ('operations.jsonl','rx-02.serial.log')]
        self.bindings=[binding(p) for p in self.paths]
        self.source_meta={n:read_bounded(self.root/n,131072) for n in ('plan.json','provenance.json')}
        self.ops=self.paths[0].open('rb');self.raw=self.paths[1].open('rb')
        self.offset=self.raw_offset=self.seq=self.total=self.dropped=self.invalid=self.reads=self.revision=0
        self.last_sample=None;self.source_stopped=False;self.observer_stopped=False;self.error=None
        self.reason='Esperando una fila CSI válida';self.id=str(uuid.uuid4())

    def close(self):self.ops.close();self.raw.close()

    def stop(self,reason):self.observer_stopped=True;self.reason=reason

    def poll(self):
        if self.error or self.observer_stopped:return
        try:
            if [binding(p) for p in self.paths]!=self.bindings:raise ValueError('Source replaced or rotated')
            if self.paths[0].stat().st_size<self.offset or self.paths[1].stat().st_size<self.raw_offset:raise ValueError('Source truncated')
            if any(read_bounded(self.root/n,131072)!=b for n,b in self.source_meta.items()):raise ValueError('Source metadata changed')
            for _ in range(self.budget):
                self.ops.seek(self.offset);line=self.ops.readline(MAX_RECORD+1)
                if len(line)>MAX_RECORD:raise ValueError('Operation record exceeds limit')
                if not line or not line.endswith(b'\n'):break
                record=json.loads(line)
                if record['seq']!=self.seq:raise ValueError('Operation sequence mismatch')
                if type(record['now_ns']) is not int:raise ValueError('Integer operation time required')
                data=record['data'];op=record['op']
                if op=='chunk':
                    size=data['size'];offset=data['offset']
                    if data['receiver']!='RX-02' or type(size) is not int or not 0<size<=MAX_CHUNK or type(offset) is not int or offset!=self.raw_offset:
                        raise ValueError('Chunk reference mismatch')
                    self.raw.seek(offset);chunk=self.raw.read(size)
                    if len(chunk)<size:break  # Original writer may still be publishing; do not invent bytes.
                    if hashlib.sha256(chunk).hexdigest()!=data['sha256']:raise ValueError('Raw chunk hash mismatch')
                    started,returned=data['started_ns'],data['returned_ns']
                    if not 0<=started<=returned<=record['now_ns'] or returned>self.clock():raise ValueError('Incompatible sample clock')
                    if self.last_sample is not None and returned<self.last_sample:raise ValueError('Nonmonotonic source')
                    for ref in self.framer.feed(chunk,self.reads,dict(started_ns=str(started),returned_ns=str(returned))):
                        if ref['kind']=='row':
                            self.raw.seek(ref['byte_offset']);wire=self.raw.read(ref['byte_length'])
                            local=dict(ref,byte_offset=0,byte_end=len(wire))
                            frame,mean,reason=frame_from_reference(wire,local,self.config)
                            if reason:self.invalid+=1;continue
                            b=frame['blocks'][0]
                            row=dict(t_ns=str(returned),first_read_ns=ref['first_read_started_ns'],reference=ref,
                                rssi=int(frame['original_fields']['rssi']),callback_id=ref['id'],mean=mean,
                                amplitudes=[b['amplitude'][INDICES.index(k)] for k in sorted(ACTIVE)],
                                hardware_valid=b['hardware_valid'],cfr_usable=b['cfr_usable'])
                            if len(self.rows)==self.rows.maxlen:self.dropped+=1
                            self.rows.append(row);self.total+=1;self.last_sample=returned
                        elif ref['kind'] in ('invalid','error','reset'):self.invalid+=1
                    self.reads+=1;self.raw_offset+=size
                elif op in ('closed','interrupt','reader_ended','io_error','storage_error'):
                    self.source_stopped=True;self.reason='Detención registrada en la fuente sintética: '+op
                elif op not in ('begin','opened','tick','storage_check','request','declare','cue_ack','close_request','closing'):
                    raise ValueError('Unsupported operation')
                self.offset+=len(line);self.seq+=1
        except (OSError,ValueError,KeyError,TypeError,RecursionError) as exc:
            self.error=(type(exc).__name__+': '+str(exc))[:512];self.reason='Observador detenido por error; original intacto'

    def snapshot(self):
        now=self.clock();self.revision+=1
        while self.rows and now-int(self.rows[0]['t_ns'])>30_000_000_000:self.rows.popleft();self.dropped+=1
        age=None if self.last_sample is None else max(0,(now-self.last_sample)/1e6)
        state=('detenido' if self.error or self.observer_stopped or self.source_stopped else
               'esperando' if age is None else 'datos_antiguos' if age>=self.stale_ns/1e6 else 'recibiendo')
        reason=(self.error or self.reason) if state=='detenido' else {
            'esperando':'Esperando una fila CSI válida',
            'recibiendo':'Filas CSI recientes en un journal provisional',
            'datos_antiguos':'Sin muestra reciente; el silencio no demuestra cierre'}[state]
        try:backlog=max(0,self.paths[0].stat().st_size-self.offset)
        except OSError:backlog=0
        return dict(schema='csi-live-preview-1',mode='SIMULADO · SIN ESP',evidence_type='synthetic_fixture',
            host_boot_id=self.host_boot_id,clock_binding_origin=self.clock_binding_origin,
            observer_id=self.id,revision=self.revision,flow_state=state,reason=reason,
            connection_id=self.plan['connection_id'],receiver='RX-02',usb_serial='5C93200689',
            last_sample_ns=None if self.last_sample is None else str(self.last_sample),sample_age_ms=age,
            stale_after_ms=self.stale_ns/1e6,published_ns=str(now),published_at_utc=datetime.now(timezone.utc).isoformat(),
            window_T0_ns=str(max(0,now-30_000_000_000)),rows=list(self.rows),rows_seen=self.total,
            rows_discarded_view=self.dropped,invalid_lines=self.invalid,seq=self.seq,operations_offset=self.offset,
            backlog_bytes=backlog,
            bounded=dict(rows=self.rows.maxlen,ops_per_poll=self.budget,record_bytes=MAX_RECORD,chunk_bytes=MAX_CHUNK),
            source_stopped=self.source_stopped,observer_stopped=self.observer_stopped,observer_error=self.error,
            original_modified=False,physical_close_verified=False,physical_input_enabled=False,detector='SIN DETECTOR CALIBRADO')


def current_snapshot(path,*,now=time.monotonic_ns):
    data=small_json(path)
    if data.get('schema')!='csi-live-preview-1' or data.get('evidence_type')!='synthetic_fixture' or data.get('host_boot_id')!=boot_id():raise ValueError('Invalid preview or clock domain')
    stamp=data['last_sample_ns'];data['sample_age_ms']=None if stamp is None else max(0,(now()-int(stamp))/1e6)
    if data['flow_state']!='detenido' and stamp is not None and data['sample_age_ms']>=data['stale_after_ms']:
        data['flow_state']='datos_antiguos';data['reason']='Sin muestra reciente; el cierre de la fuente no se deduce del silencio'
    data['window_T0_ns']=str(max(0,now()-30_000_000_000))
    return data


def observe(bundle,view,stop,*,interval=.25,stale_ns=STALE_NS,max_rows=MAX_ROWS):
    import sys
    sys.addaudithook(guard)
    view=Path(view).resolve();bundle=Path(bundle).resolve()
    if view.is_relative_to(bundle) or bundle.is_relative_to(view):raise ValueError('View output must be outside the original bundle')
    view.mkdir(parents=True,exist_ok=True)
    observer=Observer(bundle,stale_ns=stale_ns,max_rows=max_rows)
    try:
        while not stop.is_set():
            observer.poll();atomic_json(view/'latest.json',observer.snapshot());stop.wait(interval)
        observer.stop('Proceso observador detenido; esto no ordena detener el productor')
        atomic_json(view/'latest.json',observer.snapshot())
    finally:observer.close()
