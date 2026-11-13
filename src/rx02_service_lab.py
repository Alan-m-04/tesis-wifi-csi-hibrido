"""Owned-PTY laboratory, synthetic int8 CSI at 5 Hz; never discovers UARTs."""
from array import array
from collections import Counter
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import resource
import statistics
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch

import serial
from capture_csi_multi import FIELDS,SOURCE
from presence_rx02 import PORTS,RECEIVERS
from presence_rx02_uart import Rx02Session
from presence_rx02_journal import audit_rx02
from presence_v4_pty import OwnedPty
from presence_v4_journal import write_new

ROOT=Path(__file__).resolve().parents[1]
SIZES=(750,874,993,751)
PERIOD_NS=200_000_000
MAX_DURATION_S=900
MAX_GENERATED_ROWS=MAX_DURATION_S*1_000_000_000//PERIOD_NS+1
MAX_SAMPLES=262144


class Meter:
    """Finite exact sample budget; overflow is reported, never silent."""
    def __init__(self):
        self.samples={}
        self.overflow=Counter()
    def add(self,key,value):
        values=self.samples.setdefault(key,array('Q'))
        if len(values)<MAX_SAMPLES:values.append(max(0,int(value)))
        else:self.overflow[key]+=1
    def summary(self):
        result={}
        for key,values in self.samples.items():
            v=sorted(values);n=len(v)
            result[key]=dict(n=n,min=min(v),median=statistics.median(v),mean=statistics.fmean(v),
                p95=v[math.ceil(.95*n)-1],p99=v[math.ceil(.99*n)-1],max=max(v),
                over_500ms=sum(x>500_000_000 for x in v),over_1s=sum(x>1_000_000_000 for x in v))
        return dict(values=result,overflow=dict(self.overflow),sample_budget_per_metric=MAX_SAMPLES,
                    quantiles='nearest-rank p95/p99 of retained full samples; invalid if overflow nonzero')


def synthetic_row(ident,target_bytes):
    """Exact observed byte-length envelope, invented int8 content, no physical IQ."""
    fields=dict.fromkeys(FIELDS,'0')
    fields.update(type='CSI_DATA',id=str(ident),mac=SOURCE,rssi='-50',sig_mode='1',
                  len='256',channel='11',local_timestamp=str(100000+ident*200000))
    def encode(values):
        fields['data']=json.dumps(values,separators=(',',':'))
        output=io.StringIO();csv.writer(output,lineterminator='\r\n').writerow([fields[k] for k in FIELDS])
        return output.getvalue().encode()
    values=[0]*256;base=encode(values);extra=target_bytes-len(base)
    if not 0<=extra<=3*256:raise ValueError('Synthetic target length cannot be represented')
    threes,ones=divmod(extra,3)
    for i in range(threes):values[i]=-100
    if ones:values[threes]=10 if ones==1 else -10
    result=encode(values)
    if len(result)!=target_bytes:raise AssertionError('Synthetic byte-size mismatch')
    return result


class Producer:
    def __init__(self,pair):
        self.pair=pair;self.stop=threading.Event();self.rows=0;self.bytes=0
        self.sent_hash=hashlib.sha256()
        self.error=None;self.meter=Meter();self.thread=threading.Thread(target=self.run,name='synthetic-5Hz',daemon=True)
    def write(self,data):
        view=memoryview(data)
        while view and not self.stop.is_set():
            try:
                n=os.write(self.pair.master,view)
                self.sent_hash.update(view[:n])
                view=view[n:]
                self.bytes+=n
            except BlockingIOError:self.stop.wait(.001)
    def run(self):
        try:
            self.write(b'I (537) wifi:ic_enable_sniffer\r\n'
              b'I (10) csi_recv_02: RX-02 READY channel=11 HT20 UART0=115200 raw CSI; source=1a:00:00:00:00:00\n'
              b'I (545) main_task: Returned from app_main()\r\n')
            origin=time.monotonic_ns()+50_000_000
            for ident in range(MAX_GENERATED_ROWS):
                if self.stop.wait(max(0,(origin+ident*PERIOD_NS-time.monotonic_ns())/1e9)):return
                late=time.monotonic_ns()-(origin+ident*PERIOD_NS);self.meter.add('row_start_lateness_ns',late)
                if late>PERIOD_NS:raise RuntimeError('Synthetic producer missed a period; no catch-up or invented throughput')
                row=synthetic_row(ident,SIZES[ident%len(SIZES)])
                fragments=[row[:128],row[128:384],row[384:640],row[640:]]
                for part,fragment in enumerate(fragments):
                    target=origin+ident*PERIOD_NS+part*20_000_000
                    if self.stop.wait(max(0,(target-time.monotonic_ns())/1e9)):return
                    self.write(fragment)
                self.rows+=1
            raise RuntimeError('Synthetic source bounded row budget exhausted')
        except BaseException as exc:self.error=type(exc).__name__+': '+str(exc)
    def finish(self):
        self.stop.set();self.thread.join()


class Fixture:
    def __init__(self):
        self.pair=OwnedPty('RX-02');self.counts=Counter();fixture=self
        st=os.fstat(self.pair.slave)
        self.identity=dict(by_id=PORTS['RX-02'],resolved=os.ttyname(self.pair.slave),
            serial=RECEIVERS['RX-02'],vid='1a86',pid='55d3',bus='usb',node_fingerprint=[st.st_dev,st.st_ino,st.st_rdev])
        class SyntheticSerial(serial.Serial):
            def open(self):
                if self.port!=PORTS['RX-02']:raise AssertionError('Only synthetic logical RX-02 permitted')
                self.port=fixture.identity['resolved']
                if not self.port.startswith('/dev/pts/'):raise AssertionError('Owned PTY only')
                fixture.counts['open']+=1;super().open()
            def close(self):
                if self.is_open:fixture.counts['close']+=1
                return super().close()
        def checker(rx,expected):
            if rx!='RX-02' or expected!=self.identity:raise AssertionError('Synthetic identity mismatch')
            return expected
        self.backend=dict(identities={'RX-02':self.identity},checker=checker,serial_type=SyntheticSerial,
                          disk_usage=lambda _:SimpleNamespace(free=4*1024**3))


def run_case(output,*,variant='legacy',mechanism='none',delay_ms=0,duration=10,windows=False,request_delay=0,poll_ms=5):
    """Wall-clock injection into one named stage; same generator and policies."""
    if not 3<=duration<=MAX_DURATION_S or not 0<=delay_ms<=1500 or not 1<=poll_ms<=10:
        raise ValueError('Bounded laboratory duration/delay/poll required')
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    fixture=Fixture();meter=Meter();producer=Producer(fixture.pair)
    p=json.loads((ROOT/'config/piloto_rx02_r1_C01.review.json').read_text())
    p['actor']='SYNTHETIC PTY fixture; not a human observation'
    if variant=='checkpoint2':
        from rx02_checkpoint_journal import CheckpointRx02Session,PERSISTENCE_REVISION,audit_checkpoint_rx02
        p['persistence_revision']=PERSISTENCE_REVISION;session_type=CheckpointRx02Session;auditor=audit_checkpoint_rx02
    elif variant=='legacy':session_type=Rx02Session;auditor=audit_rx02
    else:raise ValueError('Unknown variant')
    session=None;armed=None;resources=[];start=time.monotonic_ns();cpu_start=time.process_time_ns();last_service=None
    real_fsync=os.fsync;real_dumps=json.dumps;injected=Counter();lock_thread=None
    errors=[];audit=None;service_end=None
    try:
        session=session_type(output/'bundle',p,test_backend=fixture.backend,clock=time.monotonic_ns)
        rawfd=session.journal.raw['RX-02'].fileno();opsfd=session.journal.ops.fileno()
        def active():return armed is not None
        def fsync(fd):
            stage='raw_fsync_ns' if fd==rawfd else 'ops_fsync_ns' if fd==opsfd else 'other_fsync_ns'
            begin=time.monotonic_ns()
            if active() and ((mechanism=='ops_sync' and fd==opsfd) or (mechanism=='raw_sync' and fd==rawfd)):
                injected[stage]+=1;time.sleep(delay_ms/1000)
            try:return real_fsync(fd)
            finally:meter.add(stage,time.monotonic_ns()-begin)
        def dumps(obj,*args,**kwargs):
            stage_record=isinstance(obj,dict) and 'seq' in obj and 'op' in obj and 'data' in obj
            if not stage_record:return real_dumps(obj,*args,**kwargs)
            begin=time.monotonic_ns()
            if active() and mechanism=='serialization':injected['serialization']+=1;time.sleep(delay_ms/1000)
            try:return real_dumps(obj,*args,**kwargs)
            finally:meter.add('serialization_ns',time.monotonic_ns()-begin)
        original_apply=session.machine.apply
        def apply(op,now_ns,**data):
            begin=time.monotonic_ns()
            if active() and mechanism=='processing' and op=='chunk':injected['processing']+=1;time.sleep(delay_ms/1000)
            try:return original_apply(op,now_ns,**data)
            finally:meter.add('reducer_apply_ns',time.monotonic_ns()-begin)
        session.machine.apply=apply
        original_check=session.guard.check
        def check(**kwargs):
            begin=time.monotonic_ns()
            try:return original_check(**kwargs)
            finally:meter.add('guard_total_ns',time.monotonic_ns()-begin)
        session.guard.check=check
        disk_usage=session.guard.disk_usage
        def disk(path):
            begin=time.monotonic_ns()
            if active() and mechanism=='guard':injected['guard']+=1;time.sleep(delay_ms/1000)
            try:return disk_usage(path)
            finally:meter.add('disk_usage_ns',time.monotonic_ns()-begin)
        session.guard.disk_usage=disk
        def stall_lock():
            with session._state_lock:
                begin=time.monotonic_ns();injected['lock']+=1;time.sleep(delay_ms/1000)
                meter.add('injected_lock_hold_ns',time.monotonic_ns()-begin)
        producer.thread.start();next_resource=start
        # Replacing functions directly avoids Mock.call_args_list retaining
        # every operation and corrupting long-run resource measurements.
        with patch.object(os,'fsync',new=fsync),patch.object(json,'dumps',new=dumps):
            while True:
                now=time.monotonic_ns()
                if last_service is not None:meter.add('service_interval_ns',now-last_service)
                last_service=now
                step_start=time.monotonic_ns()
                try:session.step()
                finally:meter.add('service_call_ns',time.monotonic_ns()-step_start)
                m=session.machine
                if m.initial_available is not None and armed is None and now>=m.initial_available+1_000_000_000:
                    armed=now
                    if mechanism=='lock':lock_thread=threading.Thread(target=stall_lock);lock_thread.start()
                if windows and m.initial_available is not None and not m.fatal:
                    if m.windows:
                        w=m.windows[-1]
                        if w['end_signal'] is not None and m.signals[w['end_signal']]['ack_ns'] is not None and w['label']['status']=='pending':
                            session.command('declare',slot_id=w['id'],established=True,maintained=True,heard=True,notes='')
                    if not m.close_requested and len(m.windows)<2 and now>=m.initial_available+int(request_delay*1e9) and (not m.windows or m.windows[-1]['label']['status']=='declared'):
                        session.command('request',slot_id=p['slots'][len(m.windows)]['id'],last=len(m.windows)==1)
                if now>=next_resource:
                    sample=time.monotonic_ns()
                    status=dict(line.split(':',1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
                    resources.append(dict(elapsed_s=(sample-start)/1e9,rss_kib=int(status['VmRSS'].split()[0]),
                        cpu_ns=time.process_time_ns()-cpu_start,fds=len(list(Path('/proc/self/fd').iterdir())),
                        threads=threading.active_count(),events=len(m.events),lines=len(m.states['RX-02']['lines']),
                        operations=session.journal.seq,raw_bytes=session.journal.raw['RX-02'].tell(),
                        pending_ops_bytes=getattr(session.journal,'pending_ops_bytes',0)))
                    next_resource=sample+1_000_000_000
                if producer.error:raise RuntimeError(producer.error)
                if session.read_loop_stopped:break
                if now-start>=int(duration*1e9):
                    session.command('close_request');session.close();break
                time.sleep(poll_ms/1000)
            service_end=time.monotonic_ns()
            producer.finish()
            if lock_thread is not None:lock_thread.join()
            session.finalize()
        audit=auditor(output/'bundle')
    except BaseException as exc:
        errors.append(type(exc).__name__+': '+str(exc))
        if session is not None:
            try:session._record('interrupt',detail='laboratory failure');session.close()
            except BaseException as close_exc:errors.append('cleanup: '+repr(close_exc))
    finally:
        if producer.thread.ident is not None:producer.finish()
        if lock_thread is not None:lock_thread.join()
        if session is not None:session.journal.close_files();session._finish_notifier()
        fixture.pair.dispose_fixture()
    elapsed=time.monotonic_ns()-start
    report=dict(schema='rx02-service-laboratory-2',instrumentation_revision='bounded-function-hooks-2',
        evidence_type='synthetic_owned_PTY_real_clock',
        physical_UART_opened=False,variant=variant,mechanism=mechanism,injected_delay_ms=delay_ms,
        duration_budget_s=duration,actual_elapsed_s=elapsed/1e9,clock='time.monotonic_ns, unscaled',
        active_service_duration_s=(service_end-start)/1e9 if service_end is not None else None,
        generated_rows=producer.rows,generated_bytes=producer.bytes,generated_sha256=producer.sent_hash.hexdigest(),
        producer_error=producer.error,
        row_period_ns=PERIOD_NS,synthetic_target_row_sizes=list(SIZES),fragment_sizes='128,256,256,remainder; 20 ms between fragment targets',
        poll_pause_ms=poll_ms,
        injected_calls=dict(injected),timings=meter.summary(),producer_timing=producer.meter.summary(),resources=resources,
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,cpu_ns=time.process_time_ns()-cpu_start,
        open_close_counts=dict(fixture.counts),errors=errors,
        fatal=audit['state']['fatal'] if audit else None,
        integrity_ok=audit['integrity_ok'] if audit else False,replay_ok=audit['replay_ok'] if audit else False,
        windows=[{k:v for k,v in w.items() if k!='receivers'}|{'coverage':w['receivers']['RX-02']['coverage']} for w in audit['state']['windows']] if audit else [],
        eligibility=audit.get('exploratory_eligibility') if audit else None,
        persistence_status=load_status(output/'bundle'),closed=audit['state']['closed'] if audit else None)
    write_new(output/'laboratory.json',report)
    return report


def load_status(bundle):
    path=bundle/'checkpoint-status.json'
    return json.loads(path.read_text()) if path.exists() else None
