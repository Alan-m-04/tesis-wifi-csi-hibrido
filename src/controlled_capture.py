"""Prepared 30-second dual acquisition. Import/preflight never opens a UART.

Only run_capture() opens receivers, and the CLI requires a separate execute flag.
"""
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import threading
import time

import capture_csi_multi as capture
from preserving_serial import preserving_serial_type
from controlled_protocol import V1, V2, V3, STOP_POLICY_V2, AVAILABILITY_V3

ROOT=Path(__file__).resolve().parents[1]
PORTS={rx:f'/dev/serial/by-id/usb-1a86_USB_Single_Serial_{serial}-if00' for rx,serial in capture.RECEIVERS.items()}
ENVIRONMENT_FIELDS=('condition','occupancy','movement','geometry','tx_power')


def dump_new(path,value):
    with Path(path).open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def validate_plan(plan, require_environment=True):
    if plan.get('protocol') not in (V1, V2, V3) or plan.get('seconds')!=30 or plan.get('ports')!=PORTS or plan.get('baud')!=115200:
        raise ValueError('Expected fixed dual protocol, 30 seconds and both stable by-id paths')
    if plan['protocol'] in (V2, V3) and plan.get('stop_policy') != STOP_POLICY_V2:
        raise ValueError('v2 requires exactly 250 ms and 65536 completion bytes')
    if plan['protocol'] == V1 and plan.get('stop_policy') is not None:
        raise ValueError('v1 has no bounded completion policy')
    if plan['protocol'] == V3 and plan.get('availability_policy') != AVAILABILITY_V3:
        raise ValueError('v3 requires the exact prospectively fixed availability/coverage contract')
    if plan['protocol'] != V3 and plan.get('availability_policy') is not None:
        raise ValueError('v1/v2 do not define availability windows')
    if plan.get('stable_window') is not None:
        raise ValueError('This protocol approves no derived stable window; preserve the entire session')
    if require_environment:
        for field in ENVIRONMENT_FIELDS:
            value=plan.get('environment',{}).get(field)
            if not isinstance(value,str) or not value.strip() or 'PENDIENTE' in value.upper():
                raise ValueError('Record the environmental condition before opening UART: '+field)
    return plan


def preflight(plan):
    """udev/stat metadata only; no serial constructor, read or open."""
    validate_plan(plan,False)
    resolved=capture.resolve_ports(list(PORTS),PORTS)
    identities={}
    for rx,link in PORTS.items():
        node,props=capture.port_identity(link);capture.require_identity(rx,link,props)
        if props.get('ID_MODEL_ID')!='55d3':raise ValueError(rx+': unexpected USB PID')
        if node!=resolved[rx]:raise ValueError('Device changed during preflight')
        identities[rx]={'by_id':link,'resolved':node,'serial':props['ID_SERIAL_SHORT'],
                        'vid':props['ID_VENDOR_ID'],'pid':props['ID_MODEL_ID'],'bus':props['ID_BUS']}
    return identities


def provenance(plan):
    import serial
    import serial.serialposix
    files=['src/capture_csi_multi.py','src/preserving_serial.py','src/controlled_capture.py',
           'src/validate_capture.py','config/csi_esp32s3.json','firmware/csi_send/main/app_main.c',
           'firmware/csi_recv/main/app_main.c','firmware/csi_recv_02/main/app_main.c']
    if plan['protocol'] in (V2, V3):
        files += ['src/bounded_frame_reader.py', 'src/controlled_protocol.py', 'src/audit_bounded_stop.py']
    if plan['protocol'] == V3:
        files += ['src/availability_window.py', 'src/controlled_capture_v3.py', 'src/audit_availability.py']
    return {'git_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'files':{name:sha(ROOT/name) for name in files},'pyserial_version':serial.__version__,
            'serialposix_sha256':sha(serial.serialposix.__file__),'installed_firmware_sha256':None,
            'firmware_evidence':'source files only; installed binary not attested',
            'environment_evidence':'operator declaration, not automatically measured',
            'startup_policy':'whole recording retained; no flush, no ignored warmup, no derived approved window',
            'exclusive_scope':'POSIX advisory flock among cooperating processes; no global exclusivity claim'}


def run_capture(plan,output,*,test_backend=None,seconds=None):
    """Execute only after external human authorization; test injection is explicitly synthetic."""
    validate_plan(plan)
    if plan['protocol'] == V3:
        from controlled_capture_v3 import run_capture_v3
        return run_capture_v3(plan, output, test_backend=test_backend, seconds=seconds)
    identities=preflight(plan) if test_backend is None else test_backend['identities']
    import serial
    if serial.__version__!='3.5':raise ValueError('Audited pySerial 3.5 required')
    if test_backend is None and seconds is not None:raise ValueError('Physical duration must be the fixed protocol value')
    duration=plan['seconds'] if seconds is None else seconds
    v2 = plan['protocol'] == V2
    out=Path(output).resolve()
    if not out.is_relative_to(ROOT/'results/local'):raise ValueError('Output must be a NEW internal results/local directory')
    if shutil.disk_usage(out.parent if out.parent.exists() else ROOT).free<100*1024*1024:raise ValueError('Need at least 100 MiB free internally')
    out.mkdir(parents=True,exist_ok=False);directory=out/'capture';directory.mkdir()
    dump_new(out/'plan.json',plan);dump_new(out/'provenance.json',provenance(plan))
    dump_new(out/'preflight.json',identities)
    session={'protocol':plan['protocol'],'session_id':out.name,'requested_seconds':duration,
             'evidence_type':'physical_capture' if test_backend is None else 'synthetic_fixture',
             'receivers':dict(PORTS),'results':{},'status':'opening_ports','note':capture.NOTE,
             'started_utc':capture.utc_now(),'capture_start_monotonic_ns':time.monotonic_ns(),
             'controlled':{'seconds':duration,'stable_window':None,'common_start_ns':None,'common_deadline_ns':None},
             'lifecycle':[]}
    gate,stop=threading.Event(),threading.Event();threads=[];opened={}
    if v2:
        session['controlled']['stop_policy'] = dict(STOP_POLICY_V2)
        if test_backend is not None and 'stop_event' in test_backend:
            stop = test_backend['stop_event']
    timing={'seconds':duration,'read_from_open':True,'record_reads':True,'deadline_ns':None,
            'reader_started':{rx:threading.Event() for rx in PORTS}}
    if v2:
        timing.update(protocol=V2, stop_policy=dict(STOP_POLICY_V2))
    factory=preserving_serial_type(serial.Serial) if test_backend is None else test_backend['factory']
    def worker(rx,device):
        try:session['results'][rx]=capture.capture_receiver(device,rx,directory,session['session_id'],gate,stop,timing)
        except Exception as exc:
            session['results'][rx]={'error':f'{type(exc).__name__}: {exc}','format_reception_ok':False};stop.set()
    def close_receiver(rx, device):
        if v2:
            session['lifecycle'].append({'event':'closing','receiver':rx,
                'monotonic_ns':str(time.monotonic_ns()),'utc':capture.utc_now()})
        try:
            device.close()
        except Exception as exc:
            session['lifecycle'].append({'event':'close_error','receiver':rx,
                'monotonic_ns':str(time.monotonic_ns()),'utc':capture.utc_now(),'error':str(exc)})
            raise
        if v2:
            session['lifecycle'].append({'event':'closed','receiver':rx,
                'monotonic_ns':str(time.monotonic_ns()),'utc':capture.utc_now()})
    try:
        with ExitStack() as stack:
            try:
                for rx,link in PORTS.items():
                    if test_backend is None and capture.verify_port(rx,link)!=identities[rx]['resolved']:
                        raise ValueError('USB changed before opening '+rx)
                    device=factory(port=None,baudrate=115200,timeout=.1,exclusive=True)
                    # Close only AFTER all reader threads finish, including interrupted startup.
                    stack.callback(close_receiver, rx, device)
                    device.dtr=False;device.rts=False;device.port=link
                    if v2:
                        session['lifecycle'].append({'event':'opening','receiver':rx,
                            'monotonic_ns':str(time.monotonic_ns()),'utc':capture.utc_now()})
                    device.open();opened[rx]=device
                    session['lifecycle'].append({'event':'opened','receiver':rx,'monotonic_ns':str(time.monotonic_ns()),
                                                 'dtr_requested':False,'rts_requested':False,
                                                 'open_input_flush_suppressed':getattr(device,'open_flush_suppressed',None)})
                    if v2:
                        session['lifecycle'][-1]['utc'] = capture.utc_now()
                    thread=threading.Thread(target=worker,args=(rx,device));threads.append(thread);thread.start()
                    if not timing['reader_started'][rx].wait(2) or stop.is_set():raise RuntimeError('Reader did not start '+rx)
                start=time.monotonic_ns();timing['deadline_ns']=start+int(duration*1e9)
                session['controlled'].update(common_start_ns=str(start),common_deadline_ns=str(timing['deadline_ns']))
                session['status']='capturing';gate.set()
                for thread in threads:
                    if thread.ident is not None:thread.join()
                session['status']='error' if any(r.get('error') for r in session['results'].values()) else 'completed'
                if v2 and stop.is_set() and session['status'] == 'completed':
                    session['status'] = 'interrupted'
            finally:
                stop.set();gate.set()
                for thread in threads:
                    if thread.ident is not None:thread.join()
                session['lifecycle'].append({'event':'readers_joined','monotonic_ns':str(time.monotonic_ns())})
        session['lifecycle'].append({'event':'ports_closed','monotonic_ns':str(time.monotonic_ns())})
    except KeyboardInterrupt:session['status']='interrupted'
    except Exception as exc:session.update(status='error',error=f'{type(exc).__name__}: {exc}')
    finally:
        session['capture_deadline_monotonic_ns']=time.monotonic_ns()
        session['finished_utc']=capture.utc_now();dump_new(directory/'session.json',session)
    postflight={}
    for rx,link in PORTS.items():
        try:
            if test_backend is None:
                node,props=capture.port_identity(link);capture.require_identity(rx,link,props)
                postflight[rx]={'identity_ok':node==identities[rx]['resolved'] and props.get('ID_MODEL_ID')=='55d3'}
            else:postflight[rx]={'identity_ok':True,'synthetic':True}
        except Exception as exc:postflight[rx]={'identity_ok':False,'error':str(exc)}
    dump_new(out/'postflight.json',postflight)
    files=[{'name':f.name,'bytes':f.stat().st_size,'sha256':sha(f)} for f in sorted(directory.iterdir()) if f.name in {'session.json'}|{rx.lower()+ext for rx in PORTS for ext in ('.serial.log','.csv','.summary.json')}]
    ledgers=[{'name':f.name,'bytes':f.stat().st_size,'sha256':sha(f)} for f in sorted(directory.glob('*.reads.jsonl'))]
    manifest={'schema':'tesis-controlled-capture-v2' if v2 else 'tesis-controlled-capture-v1',
              'source_run_kind':plan['protocol'],'source_run_id':out.name,
              'evidence_type':session['evidence_type'],'files':files,'read_ledgers':ledgers,'postflight':postflight,
              'source_directory':str(directory),'local_ignored_copy':str(directory.relative_to(ROOT)),
              'operator_environment':plan['environment'],'source_provenance':json.loads((out/'provenance.json').read_text())}
    dump_new(out/'capture-manifest.json',manifest)
    from validate_capture import audit_capture
    try:
        audit=audit_capture(directory,manifest)
        ok=audit['quality_ok'] and all(v['identity_ok'] for v in postflight.values())
        quality={'session_quality_ok':ok,'full_session':audit,'stable_window':None,'derived_window_created':False}
    except Exception as exc:quality={'session_quality_ok':False,'audit_error':f'{type(exc).__name__}: {exc}','stable_window':None}
    dump_new(out/'quality.json',quality)
    bundle={'scope':'immutable acquisition files; no derived window; no self hash','files':[
        {'path':str(f.relative_to(out)),'bytes':f.stat().st_size,'sha256':sha(f)} for f in sorted(out.rglob('*')) if f.is_file()]}
    dump_new(out/'bundle-manifest.json',bundle)
    return 0 if quality['session_quality_ok'] else 1
