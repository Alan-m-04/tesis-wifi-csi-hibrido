"""Finite fixture over an owned PTY, recorded by the existing RX-02 journal.

No slot requests or experimental declarations. Not a physical capture executor.
"""
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import select
import time
import uuid

from campana_presencia_v4 import fixture_row,fixture_ready
from capture_csi_multi import FIELDS,validate_sample
from presence_v4_pty import OwnedPty
from presence_rx02_journal import Rx02Journal,audit_rx02
from csi_live_observer import ROOT,atomic_json,boot_id,guard


def sample(ident):
    """Invented int8 waves, never an empty/occupied human condition."""
    _,record,_=validate_sample(fixture_row(ident,100000+ident*100000).decode().strip())
    record['rssi']=str(-55+ident%9)
    record['data']=json.dumps([int(25*math.sin(ident*.13+k*.09)) for k in range(256)],separators=(',',':'))
    output=io.StringIO();csv.writer(output,lineterminator='\n').writerow([record[k] for k in FIELDS])
    return output.getvalue().encode()


def produce(bundle,ready,stop,*,seconds=18,rate=10,initial_wait=1,pauses=((5,9),),fragment=False):
    import sys
    sys.addaudithook(guard)
    if not 0<seconds<=120 or not 0<rate<=50:raise ValueError('Finite bounded synthetic fixture required')
    bundle=Path(bundle);plan=json.loads((ROOT/'config/piloto_rx02_r1_C01.review.json').read_text())
    if (bundle.parent/'producer-result.json').exists():raise ValueError('Preserve previous producer evidence; use a new directory')
    # The native offline fixture contract fixes RX02-C01. This is NOT historical C01.
    plan['actor']='SYNTHETIC_FIXTURE_NO_HUMAN';plan['mounting_reference']='SYNTHETIC_NO_HARDWARE'
    journal=Rx02Journal(bundle,plan,evidence_type='synthetic_fixture',extra_provenance=dict(
        clock_domain='host_monotonic_ns',host_boot_id=boot_id(),synthetic_run_id=str(uuid.uuid4()),
        fixture_only=True,no_physical_UART=True))
    endpoint=None;sent=hashlib.sha256();ident=0;failed=None;origin=time.monotonic()
    def record(op,**data):journal.command(op,time.monotonic_ns(),**data)
    def drain():
        while select.select([endpoint.slave],[],[],.02)[0]:
            start=time.monotonic_ns()
            try:chunk=os.read(endpoint.slave,16384)
            except BlockingIOError:break
            returned=time.monotonic_ns()
            if not chunk:break
            record('chunk',receiver='RX-02',chunk=chunk,started_ns=start,returned_ns=returned)
    def write(data):
        sent.update(data)
        pieces=[data[:len(data)//2],data[len(data)//2:]] if fragment else [data]
        for piece in pieces:endpoint.fixture_write(piece);drain()
    try:
        endpoint=OwnedPty('RX-02');record('begin');record('opened',receiver='RX-02')
        write(fixture_ready('RX-02'));ready.set();next_sample=origin+initial_wait
        while not stop.is_set() and time.monotonic()-origin<seconds:
            elapsed=time.monotonic()-origin
            if elapsed>=initial_wait and not any(a<=elapsed<b for a,b in pauses) and time.monotonic()>=next_sample:
                write(sample(ident));ident+=1;next_sample=time.monotonic()+1/rate
            stop.wait(.003)
        if stop.is_set():record('interrupt',detail='synthetic fixture interrupted')
    except BaseException as exc:
        failed=type(exc).__name__+': '+str(exc)
        try:record('io_error',detail=failed)
        except Exception:pass
        raise
    finally:
        ready.set()
        try:
            if endpoint is not None:
                drain();record('close_request');record('closing')
                confirmed=endpoint.close_receiver()
                record('closed',receiver='RX-02',confirmed=confirmed,reader_stopped=True,proof='owned_synthetic_PTY',error=None)
                journal.receipt()
            journal.finalize(dict(synthetic_fixture=True,physical_UART_opened=False,experimental_windows_requested=False))
        finally:
            journal.close_files()
            if endpoint is not None:endpoint.dispose_fixture()
        actual=hashlib.sha256((bundle/'rx-02.serial.log').read_bytes()).hexdigest()
        audit=audit_rx02(bundle)
        atomic_json(bundle.parent/'producer-result.json',dict(rows_generated=ident,expected_raw_sha256=sent.hexdigest(),
            actual_raw_sha256=actual,all_sent_bytes_preserved=actual==sent.hexdigest(),integrity_ok=audit['integrity_ok'],
            replay_ok=audit['replay_ok'],error=failed,physical_UART_opened=False,experimental_labels_created=False))
