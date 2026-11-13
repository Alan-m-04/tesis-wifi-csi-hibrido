"""Bounded observer, native synthetic journals, processes and owned PTYs only."""
import hashlib
import csv
import io
import json
import multiprocessing as mp
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools'),str(ROOT/'tests')]
from csi_live_observer import Observer,observe,atomic_json,current_snapshot,boot_id,MAX_RECORD,SharedFlag
from csi_synthetic_producer import produce,sample
from presence_rx02_journal import Rx02Journal,audit_rx02
from campana_presencia_v4 import fixture_ready
from test_device_panel import FakeSocket
from demo_csi_vivo import handler,ViewServer


def hashes(root):return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(root).iterdir() if p.is_file()}


class Fixture:
    def __init__(self,root):
        self.root=Path(root)/'original';self.now=time.monotonic_ns();self.ident=0
        plan=json.loads((ROOT/'config/piloto_rx02_r1_C01.review.json').read_text())
        self.j=Rx02Journal(self.root,plan,evidence_type='synthetic_fixture',extra_provenance={
            'clock_domain':'host_monotonic_ns','host_boot_id':boot_id()})
        self.command('begin');self.command('opened',receiver='RX-02');self.chunk(fixture_ready('RX-02'))
    def command(self,op,**d):self.j.command(op,self.now,**d)
    def chunk(self,data):self.command('chunk',receiver='RX-02',chunk=data,started_ns=self.now,returned_ns=self.now)
    def row(self):self.now+=100_000_000;self.chunk(sample(self.ident));self.ident+=1
    def observer(self,**kwargs):return Observer(self.root,clock=lambda:self.now,**kwargs)


class ObserverTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.f=Fixture(self.tmp.name);self.addCleanup(self.f.j.close_files)
        self.o=self.f.observer();self.addCleanup(self.o.close)

    def test_wait_receive_stale_recover_and_stop_without_old_signal(self):
        self.o.poll();self.assertEqual(self.o.snapshot()['flow_state'],'esperando')
        self.f.row();self.o.poll();s=self.o.snapshot()
        self.assertEqual(s['flow_state'],'recibiendo');self.assertEqual(len(s['rows'][0]['amplitudes']),52)
        self.assertEqual(len(s['rows'][0]['hardware_valid']),64)
        stamp=s['last_sample_ns'];self.f.now+=2_100_000_000
        self.assertEqual(self.o.snapshot()['flow_state'],'datos_antiguos')
        self.assertEqual(self.o.snapshot()['last_sample_ns'],stamp)
        self.f.row();self.o.poll();self.assertEqual(self.o.snapshot()['flow_state'],'recibiendo')
        self.f.command('interrupt');self.o.poll();self.assertEqual(self.o.snapshot()['flow_state'],'detenido')
        self.assertTrue(self.o.snapshot()['source_stopped']);self.assertFalse(self.o.snapshot()['observer_stopped'])
        self.assertFalse(self.o.snapshot()['physical_close_verified'])

    def test_native_storage_guard_control_is_not_an_unknown_stream_error(self):
        self.f.command('storage_check',free_bytes=4*1024**3,raw_bytes=0,size_bytes=0,
                       final_extra=0,guard_started_ns=self.f.now)
        self.f.row();self.o.poll()
        self.assertIsNone(self.o.error);self.assertEqual(self.o.snapshot()['flow_state'],'recibiendo')

    def test_external_clock_binding_is_synthetic_only_hash_bound_and_read_only(self):
        p=self.f.root/'provenance.json';v=json.loads(p.read_text())
        v['transport']=dict(backend='synthetic_serial_backend');p.write_text(json.dumps(v))
        proof=dict(schema='synthetic-PTY-clock-binding-1',bundle=str(self.f.root.resolve()),
            clock_domain='host_monotonic_ns',host_boot_id=boot_id(),
            plan_sha256=hashlib.sha256((self.f.root/'plan.json').read_bytes()).hexdigest(),
            provenance_sha256=hashlib.sha256(p.read_bytes()).hexdigest())
        before=hashes(self.f.root)
        with self.assertRaisesRegex(ValueError,'freshness'):self.f.observer()
        o=self.f.observer(clock_binding=proof)
        try:
            o.poll();self.assertIsNone(o.error)
            self.assertEqual(o.snapshot()['clock_binding_origin'],'external_synthetic_PTY_attestation')
        finally:o.close()
        self.assertEqual(hashes(self.f.root),before)
        for key in ('bundle','clock_domain','host_boot_id','plan_sha256','provenance_sha256','schema'):
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'binding'):
                self.f.observer(clock_binding=proof|{key:'incorrect'})
        v['transport']['backend']='UART';p.write_text(json.dumps(v))
        updated=proof|{'provenance_sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
        with self.assertRaisesRegex(ValueError,'binding'):self.f.observer(clock_binding=updated)
        v['evidence_type']='physical_capture';p.write_text(json.dumps(v))
        with self.assertRaisesRegex(ValueError,'disabled'):self.f.observer(clock_binding=proof)

    def test_unknown_operation_still_stops_instead_of_silently_skipping(self):
        self.o.poll()
        wire=json.dumps(dict(seq=self.f.j.seq,now_ns=self.f.now,op='unknown_control',data={}))+'\n'
        with (self.f.root/'operations.jsonl').open('ab') as stream:stream.write(wire.encode())
        self.o.poll();self.assertIn('Unsupported operation',self.o.error)

    def test_bounded_consumer_reports_view_drops_original_unchanged(self):
        o=self.f.observer(max_rows=3,budget=2);self.addCleanup(o.close)
        for _ in range(14):self.f.row()
        before=hashes(self.f.root)
        while o.seq<self.f.j.seq:o.poll()
        s=o.snapshot();self.assertEqual(s['rows_seen'],14);self.assertEqual(len(s['rows']),3)
        self.assertEqual(s['rows_discarded_view'],11);self.assertEqual(hashes(self.f.root),before)
        self.f.now+=31_000_000_000;s=o.snapshot();self.assertEqual(s['rows'],[])
        self.assertEqual(s['rows_discarded_view'],14)

    def test_fragmented_wire_keeps_original_line_references(self):
        wire=sample(0);self.f.chunk(wire[:40]);self.o.poll();self.assertEqual(self.o.total,0)
        self.f.now+=1;self.f.chunk(wire[40:]);self.o.poll();row=self.o.snapshot()['rows'][0]
        ref=row['reference'];raw=(self.f.root/'rx-02.serial.log').read_bytes()
        self.assertEqual(hashlib.sha256(raw[ref['byte_offset']:ref['byte_end']]).hexdigest(),ref['line_sha256'])
        self.assertLessEqual(int(row['first_read_ns']),int(row['t_ns']))

    def test_partial_json_waits_and_never_grows_a_queue(self):
        self.o.poll();entry=dict(seq=self.f.j.seq,op='tick',now_ns=self.f.now,data={})
        wire=(json.dumps(entry)+'\n').encode()
        with (self.f.root/'operations.jsonl').open('ab') as f:f.write(wire[:17])
        self.o.poll();self.assertIsNone(self.o.error);self.assertEqual(self.o.seq,self.f.j.seq)
        with (self.f.root/'operations.jsonl').open('ab') as f:f.write(wire[17:])
        self.o.poll();self.assertEqual(self.o.seq,self.f.j.seq+1)

    def test_raw_not_yet_available_does_not_become_fabricated_data(self):
        self.o.poll();wire=sample(0);offset=(self.f.root/'rx-02.serial.log').stat().st_size
        entry=dict(seq=self.f.j.seq,op='chunk',now_ns=self.f.now,data=dict(receiver='RX-02',offset=offset,
            size=len(wire),sha256=hashlib.sha256(wire).hexdigest(),started_ns=self.f.now,returned_ns=self.f.now))
        with (self.f.root/'operations.jsonl').open('ab') as f:f.write((json.dumps(entry)+'\n').encode())
        self.o.poll();self.assertIsNone(self.o.error);self.assertEqual(self.o.total,0)
        with (self.f.root/'rx-02.serial.log').open('ab') as f:f.write(wire)
        self.o.poll();self.assertEqual(self.o.total,1)

    def test_corrupt_hash_stops_only_the_view(self):
        self.f.row();p=self.f.root/'rx-02.serial.log';b=bytearray(p.read_bytes());b[-10]^=1;p.write_bytes(b)
        before=hashes(self.f.root);self.o.poll()
        self.assertEqual(self.o.snapshot()['flow_state'],'detenido');self.assertIn('hash',self.o.error)
        self.assertEqual(hashes(self.f.root),before)

    def test_truncation_rotation_sequence_and_record_limits_stop(self):
        for defect in ('truncate','rotate','sequence','oversize'):
            with self.subTest(defect=defect),tempfile.TemporaryDirectory() as temp:
                f=Fixture(temp);o=f.observer()
                try:
                    o.poll();p=f.root/'operations.jsonl'
                    if defect=='truncate':p.write_bytes(b'')
                    elif defect=='rotate':p.rename(p.with_suffix('.old'));p.write_bytes(b'')
                    elif defect=='sequence':
                        with p.open('ab') as stream:stream.write((json.dumps(dict(seq=999,op='tick',now_ns=f.now,data={}))+'\n').encode())
                    else:
                        with p.open('ab') as stream:stream.write(b'x'*(MAX_RECORD+1))
                    o.poll();self.assertEqual(o.snapshot()['flow_state'],'detenido')
                finally:o.close();f.j.close_files()

    def test_new_observer_and_HTTP_reader_use_sample_age_not_arrival_age(self):
        self.f.row();self.f.now+=3_000_000_000
        o=self.f.observer();self.addCleanup(o.close);o.poll();self.assertEqual(o.snapshot()['flow_state'],'datos_antiguos')
        self.o.poll();s=self.o.snapshot();s['flow_state']='recibiendo'
        p=Path(self.tmp.name)/'latest.json';atomic_json(p,s)
        result=current_snapshot(p,now=lambda:self.f.now)
        self.assertEqual(result['flow_state'],'datos_antiguos')

    def test_physical_historical_and_reserved_input_are_refused(self):
        p=self.f.root/'provenance.json';v=json.loads(p.read_text());v['evidence_type']='physical_capture';p.write_text(json.dumps(v))
        with self.assertRaisesRegex(ValueError,'disabled'):self.f.observer()
        with self.assertRaises(PermissionError):Observer(Path(self.tmp.name)/'C04-no-open')

    def test_invalid_CSI_does_not_refresh_last_valid_sample(self):
        self.f.row();self.o.poll();stamp=self.o.last_sample
        self.f.now+=3_000_000_000;self.f.chunk(b'CSI_DATA,invalid\n');self.o.poll()
        self.assertEqual(self.o.last_sample,stamp);self.assertGreater(self.o.invalid,0)
        self.assertEqual(self.o.snapshot()['flow_state'],'datos_antiguos')
        from capture_csi_multi import validate_sample,FIELDS
        _,record,_=validate_sample(sample(99).decode().strip());record['first_word_invalid']='1'
        stream=io.StringIO();csv.writer(stream,lineterminator='\n').writerow([record[k] for k in FIELDS])
        self.f.chunk(stream.getvalue().encode());self.o.poll()
        self.assertEqual(self.o.last_sample,stamp);self.assertGreaterEqual(self.o.invalid,2)


class PtyProcessTests(unittest.TestCase):
    def test_unclean_producer_death_is_stale_not_a_fabricated_close(self):
        ctx=mp.get_context('spawn')
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);ready=SharedFlag(ctx);stop=SharedFlag(ctx)
            p=ctx.Process(target=produce,args=(root/'original',ready,stop),kwargs=dict(seconds=5,initial_wait=0,pauses=()))
            p.start();self.assertTrue(ready.wait(5));o=Observer(root/'original',stale_ns=20_000_000)
            try:
                deadline=time.monotonic()+2
                while o.total==0 and time.monotonic()<deadline:o.poll();time.sleep(.01)
                self.assertGreater(o.total,0);p.terminate();p.join(3)
                before=hashes(root/'original');time.sleep(.04);o.poll()
                s=o.snapshot();self.assertEqual(s['flow_state'],'datos_antiguos')
                self.assertFalse(o.source_stopped);self.assertFalse(s['physical_close_verified'])
                self.assertEqual(hashes(root/'original'),before)
            finally:
                o.close()
                if p.is_alive():p.terminate();p.join()

    def test_slow_consumer_observer_restart_and_interruption_preserve_native_record(self):
        ctx=mp.get_context('spawn')
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);bundle=root/'original';view=root/'view';ready=SharedFlag(ctx);stop_source=SharedFlag(ctx);stop_view=SharedFlag(ctx)
            p=ctx.Process(target=produce,args=(bundle,ready,stop_source),kwargs=dict(seconds=2.8,rate=50,initial_wait=.15,pauses=((.6,1.2),),fragment=True))
            p.start();self.addCleanup(lambda: p.is_alive() and p.terminate())
            self.assertTrue(ready.wait(5))
            o=ctx.Process(target=observe,args=(bundle,view,stop_view),kwargs=dict(interval=.025,stale_ns=150_000_000,max_rows=3))
            o.start();self.addCleanup(lambda: o.is_alive() and o.terminate())
            deadline=time.monotonic()+5;states=set()
            while time.monotonic()<deadline:
                try:
                    s=current_snapshot(view/'latest.json');states.add(s['flow_state'])
                    if s['flow_state']=='datos_antiguos':break
                except (OSError,ValueError):pass
                time.sleep(.02)
            self.assertIn('recibiendo',states);self.assertIn('datos_antiguos',states)
            o.terminate();o.join(3)
            self.assertTrue(p.is_alive(),'Observer death must not stop the producer')
            time.sleep(.35)  # No browser/consumer; producer continues into the original journal.
            o=ctx.Process(target=observe,args=(bundle,view,stop_view),kwargs=dict(interval=.025,stale_ns=150_000_000,max_rows=3));o.start()
            p.join(6);self.assertFalse(p.is_alive());self.assertEqual(p.exitcode,0)
            time.sleep(.2);stop_view.set();o.join(4);self.assertEqual(o.exitcode,0)
            result=json.loads((root/'producer-result.json').read_text());self.assertTrue(result['all_sent_bytes_preserved'])
            self.assertTrue(result['integrity_ok'] and result['replay_ok'])
            s=current_snapshot(view/'latest.json');self.assertLessEqual(len(s['rows']),3)
            self.assertEqual(s['rows_seen'],result['rows_generated'])
            self.assertGreater(s['rows_discarded_view'],0);self.assertEqual(s['flow_state'],'detenido')
            before=hashes(bundle);check=Observer(bundle);check.poll();check.close();self.assertEqual(hashes(bundle),before)
            self.assertTrue(audit_rx02(bundle)['replay_ok'])

    def test_graceful_source_interruption_is_recorded_not_retried(self):
        ctx=mp.get_context('spawn')
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);ready=SharedFlag(ctx);stop=SharedFlag(ctx)
            p=ctx.Process(target=produce,args=(root/'original',ready,stop),kwargs=dict(seconds=5,initial_wait=0,pauses=()))
            p.start();self.assertTrue(ready.wait(5));stop.set();p.join(6)
            if p.is_alive():p.terminate();p.join();self.fail('Producer did not stop')
            self.assertEqual(p.exitcode,0)
            ops=[json.loads(line)['op'] for line in (root/'original/operations.jsonl').read_text().splitlines()]
            self.assertEqual(ops.count('opened'),1);self.assertIn('interrupt',ops);self.assertEqual(ops.count('closed'),1)


class HttpTests(unittest.TestCase):
    def test_CLI_rejects_view_output_inside_original_before_writing(self):
        from contextlib import redirect_stderr
        import demo_csi_vivo as cli
        with tempfile.TemporaryDirectory(dir=ROOT/'results/local') as temp:
            original=Path(temp)/'original';original.mkdir();(original/'preserve.txt').write_text('unchanged')
            before=hashes(original);target=original/'view'
            with patch.object(cli.sys,'addaudithook'),redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
                cli.main(['--observe-synthetic',str(original),'--output-new',str(target),'--headless'])
            self.assertFalse(target.exists());self.assertEqual(hashes(original),before)

    def test_HTTP_has_one_handler_bounded_backlog_and_socket_timeout(self):
        from http.server import HTTPServer
        from unittest.mock import Mock
        request=Mock();server=object.__new__(ViewServer)
        with patch.object(HTTPServer,'get_request',return_value=(request,('127.0.0.1',1234))):
            self.assertEqual(server.get_request()[0],request)
        request.settimeout.assert_called_once_with(1);self.assertEqual(ViewServer.request_queue_size,4)

    def test_browser_disconnect_and_bad_routes_never_control_original(self):
        class Gone(FakeSocket):
            def sendall(self,data):raise BrokenPipeError('browser disconnected')
        with tempfile.TemporaryDirectory() as temp:
            f=Fixture(temp);f.row();o=f.observer();o.poll();atomic_json(Path(temp)/'latest.json',o.snapshot())
            before=hashes(f.root)
            try:
                for gone,path,expected in ((False,'/',b'200'),(False,'/charts.mjs',b'200'),(False,'/api/stream',b'200'),
                                           (True,'/api/stream',None),(False,'/capture',b'404'),(False,'/original/operations.jsonl',b'404')):
                    sock=(Gone if gone else FakeSocket)(f'GET {path} HTTP/1.0\r\nHost: 127.0.0.1:8767\r\n\r\n'.encode())
                    cls=handler(Path(temp))
                    with patch.object(cls,'log_message'):cls(sock,('127.0.0.1',42),SimpleNamespace(server_port=8767))
                    if expected:self.assertIn(expected,bytes(sock.output).split(b'\r\n')[0])
                self.assertEqual(hashes(f.root),before)
                f.row();o.poll();self.assertEqual(o.total,2)
            finally:o.close();f.j.close_files()


if __name__=='__main__':unittest.main()
