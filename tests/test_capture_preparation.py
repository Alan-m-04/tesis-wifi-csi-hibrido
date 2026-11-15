"""Capture fixes, mocked serial backends and private PTYs only; never physical UART."""
import io
import json
import os
from pathlib import Path
import pty
import tempfile
import termios
import threading
import time
import tty
import unittest
from unittest.mock import patch
import serial
import capture_csi_multi as capture
from preserving_serial import preserving_serial_type
from test_validate_capture import frame, fixture


class PreservingSerialTests(unittest.TestCase):
    def test_pending_input_survives_posix_open_without_tcflush(self):
        # Demonstrates the actual hidden pySerial 3.5 flush and its suppression.
        master,slave=pty.openpty();self.addCleanup(os.close,master);self.addCleanup(os.close,slave)
        tty.setraw(slave);path=os.ttyname(slave);os.write(master,b'BEFORE_OPEN\n')
        with patch('serial.serialposix.termios.tcflush',wraps=termios.tcflush) as flush:
            port=preserving_serial_type(serial.Serial)(port=None,baudrate=115200,timeout=.05,exclusive=True)
            self.addCleanup(port.close);port.dtr=False;port.rts=False;port.port=path;port.open()
            self.assertEqual(port.read(12),b'BEFORE_OPEN\n');flush.assert_not_called()
            self.assertEqual(port.open_flush_suppressed,1)
    def test_original_pyserial_open_really_calls_input_flush_on_private_pty(self):
        master,slave=pty.openpty();self.addCleanup(os.close,master);self.addCleanup(os.close,slave)
        with patch('serial.serialposix.termios.tcflush',wraps=termios.tcflush) as flush:
            port=serial.Serial(port=None,timeout=.01);self.addCleanup(port.close)
            port.dtr=False;port.rts=False;port.port=os.ttyname(slave);port.open()
            self.assertTrue(any(c.args[1]==termios.TCIFLUSH for c in flush.call_args_list))
    def test_explicit_flushes_fail_instead_of_discarding_bytes(self):
        p=preserving_serial_type(serial.Serial)(port=None)
        for fn in (p.reset_input_buffer,p.reset_output_buffer,p._reset_input_buffer):
            with self.assertRaises(RuntimeError):fn()
    def test_exclusive_open_is_enforced_between_cooperating_posix_openers(self):
        master,slave=pty.openpty();self.addCleanup(os.close,master);self.addCleanup(os.close,slave)
        cls=preserving_serial_type(serial.Serial);a=cls(port=None,exclusive=True);b=cls(port=None,exclusive=True)
        self.addCleanup(a.close);self.addCleanup(b.close)
        for p in (a,b):p.dtr=False;p.rts=False;p.port=os.ttyname(slave)
        a.open()
        with self.assertRaises(serial.SerialException):b.open()


class FramingFixTests(unittest.TestCase):
    def record(self,chunks):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);root=Path(tmp.name)
        class Port:
            port='SYNTHETIC';pending=list(chunks)
            @property
            def in_waiting(self):return len(self.pending[0]) if self.pending else 0
            def read(self,size):
                if self.pending:
                    data=self.pending[0][:size];self.pending[0]=self.pending[0][size:]
                    if not self.pending[0]:self.pending.pop(0)
                    return data
                time.sleep(.0005);return b''
        gate=threading.Event();gate.set()
        summary=capture.capture_receiver(Port(),'RX-01',root,'synthetic',gate,threading.Event(),{'seconds':.025,'deadline_ns':time.monotonic_ns()+25_000_000,'record_reads':True})
        return root,summary
    def test_oversized_unterminated_tail_counts_all_bytes_not_only_last_fragment(self):
        data=frame()+b'x'*150000;root,s=self.record([data])
        self.assertEqual(s['trailing_bytes'],150000);self.assertEqual(s['oversized_lines'],1)
        self.assertEqual((root/'rx-01.serial.log').read_bytes(),data);self.assertFalse(s['format_reception_ok'])
    def test_oversized_line_recovery_retains_raw_and_marks_error(self):
        data=b'x'*150000+b'\n'+frame();root,s=self.record([data])
        self.assertEqual(s['valid_rows'],1);self.assertEqual(s['trailing_bytes'],0);self.assertEqual(s['oversized_lines'],1)
        self.assertEqual((root/'rx-01.serial.log').read_bytes(),data)
    def test_one_byte_reads_do_not_repair_or_create_frames(self):
        data=frame();root,s=self.record([bytes([b]) for b in data])
        self.assertEqual(s['valid_rows'],1);self.assertEqual((root/'rx-01.serial.log').read_bytes(),data)
    def test_read_ledger_is_contiguous_and_preserves_shared_chunk_time(self):
        root,s=self.record([frame()+frame(1,300000)])
        events=[json.loads(x) for x in (root/'rx-01.reads.jsonl').read_text().splitlines()]
        self.assertEqual(sum(e['size'] for e in events),s['bytes_received']);self.assertEqual(events[0]['offset'],0)
        self.assertEqual(len(events),1)
    def test_historical_bad_prefix_stays_rejected_for_every_split(self):
        from capture_csi_multi import validate_sample
        line=b'CSI_DATA,3927,1a:00:00:00:00:00,-53,11,1,0,0,1,1,0,0,0,0,-90,,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,ESP-ROM:esp32s3-20210327\r\n'
        for i in (1,9,40,len(line)-1):
            root,s=self.record([line[:i],line[i:],frame()]);self.assertEqual(s['malformed_rows'],1)
            self.assertFalse(s['format_reception_ok']);self.assertEqual((root/'rx-01.serial.log').read_bytes(),line+frame())



class ControlledProtocolTests(unittest.TestCase):
    def plan(self):
        import controlled_capture as control
        return {'protocol':'controlled_dual_v1','seconds':30,'baud':115200,'ports':dict(control.PORTS),
                'stable_window':None,'environment':{k:'synthetic test declaration' for k in control.ENVIRONMENT_FIELDS}}
    def run_synthetic(self,second_fails=False,tail=b'',malformed=False,second_interrupt=False,startup_prefix=b''):
        import controlled_capture as control
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);root=Path(tmp.name)
        (root/'results/local').mkdir(parents=True)
        log=[];first_read=threading.Event()
        class MemoryPort:
            def __init__(self,**kw):self.port=None;self.sent=False;self.counter=0;self.active=False;self.open_flush_suppressed=1
            def open(self):
                self.rx=next(rx for rx,link in control.PORTS.items() if link==self.port)
                log.append(('open',self.rx))
                if self.rx=='RX-02' and (second_interrupt or second_fails):first_read.wait(.1)
                if second_interrupt and self.rx=='RX-02':raise KeyboardInterrupt()
                if second_fails and self.rx=='RX-02':raise OSError('synthetic second open failure')
            def close(self):
                if hasattr(self,'rx'):log.append(('close',self.rx,self.active))
            @property
            def in_waiting(self):return 10000
            def read(self,size):
                self.active=True
                try:
                    time.sleep(.003)
                    prefix=(b'CSI_DATA,broken\n' if malformed and self.rx=='RX-01' else startup_prefix) if not self.sent else b''
                    self.sent=True;i=self.counter;self.counter+=2
                    if self.rx=='RX-01':first_read.set()
                    return prefix+frame(i,100000+i*200000)+frame(i+1,300000+i*200000)+tail
                finally:self.active=False
        identities={rx:{'by_id':link,'resolved':'SYNTHETIC-'+rx}for rx,link in control.PORTS.items()}
        with patch.object(control,'ROOT',root),patch.object(control,'provenance',return_value={'synthetic':True,'installed_firmware_sha256':None}):
            code=control.run_capture(self.plan(),root/'results/local/run',test_backend={'factory':MemoryPort,'identities':identities},seconds=.025)
        return root/'results/local/run',code,log
    def test_plan_requires_operator_environment_and_rejects_duration_or_window_changes(self):
        from controlled_capture import validate_plan
        p=self.plan();p['environment']['geometry']=None
        with self.assertRaises(ValueError):validate_plan(p)
        p=self.plan();p['seconds']=31
        with self.assertRaises(ValueError):validate_plan(p)
        p=self.plan();p['stable_window']={'start':5}
        with self.assertRaises(ValueError):validate_plan(p)
    def test_default_cli_is_preparation_and_never_opens_serial(self):
        import importlib.util,sys
        spec=importlib.util.spec_from_file_location('prepare_cli',Path(__file__).resolve().parents[1]/'tools/captura_dual_controlada.py')
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);plan=Path(tmp.name)/'plan.json';plan.write_text(json.dumps(self.plan()))
        from contextlib import redirect_stdout
        with patch.object(sys,'argv',['prepare','--plan',str(plan)]),patch('serial.Serial',side_effect=AssertionError('No UART')) as serial_open,redirect_stdout(io.StringIO()):
            self.assertEqual(mod.main(),0);serial_open.assert_not_called()
    def test_complete_synthetic_dual_session_and_read_ledgers_validate(self):
        root,code,log=self.run_synthetic();quality=json.loads((root/'quality.json').read_text())
        self.assertEqual(code,0,quality);self.assertTrue(quality['session_quality_ok'])
        session=json.loads((root/'capture/session.json').read_text());self.assertEqual(session['evidence_type'],'synthetic_fixture')
        self.assertEqual(len(session['results']),2)
        self.assertTrue(all(not item[2] for item in log if item[0]=='close'))
        for rx in ('RX-01','RX-02'):self.assertTrue(quality['full_session']['receivers'][rx]['read_ledger_ok'])
    def test_second_open_failure_keeps_first_reader_bytes_and_closes_after_reader(self):
        root,code,log=self.run_synthetic(second_fails=True)
        self.assertEqual(code,1);self.assertGreater((root/'capture/rx-01.serial.log').stat().st_size,0)
        self.assertTrue(all(not item[2] for item in log if item[0]=='close'))
        self.assertEqual(json.loads((root/'capture/session.json').read_text())['status'],'error')
    def test_incomplete_tail_is_not_silently_approved_by_controlled_validator(self):
        root,code,_=self.run_synthetic(tail=b'CSI_DATA,partial')
        self.assertEqual(code,1);q=json.loads((root/'quality.json').read_text());self.assertFalse(q['session_quality_ok'])
        self.assertGreater(q['full_session']['receivers']['RX-01']['trailing_bytes'],0)
    def test_bad_startup_keeps_full_rejection_no_derived_window(self):
        root,code,_=self.run_synthetic(malformed=True);self.assertEqual(code,1)
        q=json.loads((root/'quality.json').read_text());self.assertFalse(q['session_quality_ok']);self.assertIsNone(q['stable_window'])
        self.assertEqual(q['full_session']['receivers']['RX-01']['counts']['malformed_rows'],1)
    def test_read_ledger_tamper_is_detected_even_without_changing_raw_csv(self):
        from validate_capture import audit_capture
        root,_,_=self.run_synthetic();manifest=json.loads((root/'capture-manifest.json').read_text())
        path=root/'capture/rx-01.reads.jsonl';path.write_text(path.read_text().replace('"offset": 0','"offset": 1',1))
        from controlled_capture import sha
        entry=next(x for x in manifest['read_ledgers'] if x['name']==path.name);entry['bytes']=path.stat().st_size;entry['sha256']=sha(path)
        self.assertFalse(audit_capture(root/'capture',manifest)['quality_ok'])
    def test_controlled_canonical_label_matches_strict_result_and_stays_synthetic(self):
        from canonical_csi import canonicalize
        root,_,_=self.run_synthetic(malformed=True);manifest=json.loads((root/'capture-manifest.json').read_text())
        profile=json.loads((Path(__file__).resolve().parents[1]/'config/csi_esp32s3.json').read_text())
        c=canonicalize(root/'capture',manifest,profile);self.assertEqual(c['evidence_type'],'synthetic_fixture')
        self.assertIn('sintética',c['status_label']);self.assertIn('rechazada',c['status_label'])

    def test_interrupt_during_second_open_joins_first_reader_before_closing(self):
        root,code,log=self.run_synthetic(second_interrupt=True)
        self.assertEqual(code,1);self.assertTrue(all(not item[2] for item in log if item[0]=='close'))
        self.assertEqual(json.loads((root/'capture/session.json').read_text())['status'],'interrupted')

    def test_embedded_boot_after_unprefixed_fragment_fails_new_protocol(self):
        root,code,_=self.run_synthetic(startup_prefix=b',truncated,ESP-ROM:esp32s3-20210327\r\n')
        self.assertEqual(code,1);q=json.loads((root/'quality.json').read_text())
        self.assertFalse(q['session_quality_ok'])
        self.assertEqual(q['full_session']['receivers']['RX-01']['embedded_boot_lines'],[1])


class LegacyInterruptedStartupTests(unittest.TestCase):
    def test_legacy_startup_interrupt_also_joins_readers_before_close(self):
        from contextlib import redirect_stdout
        import sys
        finished=threading.Event();base_thread=threading.Thread;real_reader=capture.capture_receiver
        class InterruptThread(base_thread):
            def start(self):super().start();raise KeyboardInterrupt()
        class Port:
            def __init__(self,**kwargs):self.port=None
            def open(self):pass
            def close(self):
                if not finished.is_set():raise AssertionError('close before reader finished')
        def reader(*args,**kwargs):
            try:return real_reader(*args,**kwargs)
            finally:finished.set()
        with tempfile.TemporaryDirectory() as tmp:
            args=['capture','--seconds','0.02','--output-dir',str(Path(tmp)/'new')]
            with patch.object(sys,'argv',args),patch.object(capture,'resolve_ports',return_value={'RX-01':'SYNTHETIC-01','RX-02':'SYNTHETIC-02'}),patch.object(capture,'verify_port',side_effect=lambda rx,path:path),patch('serial.Serial',Port),patch.object(capture,'capture_receiver',side_effect=reader),patch.object(capture.threading,'Thread',InterruptThread),redirect_stdout(io.StringIO()):
                self.assertEqual(capture.main(),1)
            session=json.loads((Path(tmp)/'new/session.json').read_text())
            self.assertEqual(session['status'],'interrupted');self.assertTrue(finished.is_set())

    def test_legacy_thread_start_failure_still_closes_and_writes_error_session(self):
        from contextlib import redirect_stdout
        import sys
        base_thread=threading.Thread;closed=[]
        class FailedThread(base_thread):
            def start(self):raise RuntimeError('synthetic thread allocation failure')
        class Port:
            def __init__(self,**kwargs):self.port=None
            def open(self):pass
            def close(self):closed.append(self.port)
        with tempfile.TemporaryDirectory() as tmp:
            args=['capture','--seconds','0.02','--output-dir',str(Path(tmp)/'new')]
            with patch.object(sys,'argv',args),patch.object(capture,'resolve_ports',return_value={'RX-01':'SYNTHETIC-01','RX-02':'SYNTHETIC-02'}),patch.object(capture,'verify_port',side_effect=lambda rx,path:path),patch('serial.Serial',Port),patch.object(capture.threading,'Thread',FailedThread),redirect_stdout(io.StringIO()):
                self.assertEqual(capture.main(),1)
            session=json.loads((Path(tmp)/'new/session.json').read_text())
            self.assertEqual(session['status'],'error');self.assertEqual(set(closed),{'SYNTHETIC-01','SYNTHETIC-02'})


if __name__=='__main__':unittest.main()
