"""UART backend tests, exclusively process-owned PTYs and serial doubles."""
import contextlib
import copy
import errno
import gc
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'tools'))
import serial
import presence_v4_uart as uart
from presence_v4_journal import audit_v4
from presence_v4_pty import OwnedPty,SteppedFixtureClock
from campana_presencia_v4 import fixture_ready,fixture_row
from campana_presencia_uart_v4 import main as uart_main
from practicar_sonidos_v4 import practice


def plan():
    p=json.loads((ROOT/'config/campana_presencia_uart_v4.template.json').read_text())
    p.update(execution_mode='offline_only',connection_id='SYNTHETIC-UART-TEST',actor='SYNTHETIC',
             mounting_reference='synthetic-fixture',partition_group='synthetic-connection')
    p['slots']=p['slots'][:2]
    return p


class Rig:
    def __init__(self, scenario=None, *, effective_ioctls=False):
        self.tmp=tempfile.TemporaryDirectory();self.output=Path(self.tmp.name)/'new'
        self.pairs={rx:OwnedPty(rx) for rx in uart.PORTS}
        self.clock=SteppedFixtureClock();self.objects=[];self.calls=[]
        self.free=1024**3;self.ids={rx:0 for rx in uart.PORTS};self.next=0
        self.scenario=scenario
        self.identities={}
        for rx,e in self.pairs.items():
            st=os.fstat(e.slave)
            self.identities[rx]=dict(by_id=uart.PORTS[rx],resolved=os.ttyname(e.slave),
                serial=uart.capture.RECEIVERS[rx],vid='1a86',pid='55d3',bus='usb',
                node_fingerprint=[st.st_dev,st.st_ino,st.st_rdev])
        rig=self
        class SerialDouble(serial.Serial):
            def __init__(self,**kw):
                rig.calls.append(('construct',dict(kw)));self.rx=None;self.protocol_closes=0
                super().__init__(**kw);rig.objects.append(self)
            def open(self):
                assert self.port in uart.PORTS.values(),'Never forward a real UART path'
                self.rx=next(rx for rx,p in uart.PORTS.items() if p==self.port)
                rig.calls.append(('open',self.rx,self.dtr,self.rts,self.is_open))
                self.port=rig.identities[self.rx]['resolved']
                super().open()
                if scenario=='second_open_slow' and self.rx=='RX-02':
                    time.sleep(.03)
                    raise OSError('synthetic second open failed while first reader was active')
                if scenario=='second_open' and self.rx=='RX-02':
                    raise OSError('synthetic second open failure after fd allocation')
            def _update_dtr_state(self):
                rig.calls.append(('dtr',self.rx,self.dtr))
                if not effective_ioctls:return super()._update_dtr_state()
            def _update_rts_state(self):
                rig.calls.append(('rts',self.rx,self.rts))
                if not effective_ioctls:return super()._update_rts_state()
            def close(self):
                if self.rx is not None:
                    self.protocol_closes+=1;rig.calls.append(('close',self.rx))
                if scenario=='close_error' and self.rx=='RX-01':
                    raise OSError('synthetic first close error')
                return super().close()
        self.serial_type=SerialDouble
        self.backend=dict(identities=self.identities,checker=self.checker,serial_type=SerialDouble,
                          disk_usage=lambda _:SimpleNamespace(free=self.free))

    def checker(self,rx,expected):
        self.calls.append(('identity',rx))
        if self.scenario=='identity_changed' and rx=='RX-02':
            raise ValueError('synthetic identity changed before second opening')
        return expected

    def session(self):
        return uart.UartSession(self.output,plan(),test_backend=self.backend,clock=self.clock)

    def initial_bytes(self):
        for rx,e in self.pairs.items():
            e.fixture_write(fixture_ready(rx)+b''.join(fixture_row(i,100000+i*100000) for i in range(3)))
            self.ids[rx]=3

    def step(self,s):
        self.clock.advance(50_000_000)
        if not s.read_loop_stopped and not s.machine.close_requested and self.clock()>=self.next:
            for rx,e in self.pairs.items():
                i=self.ids[rx];e.fixture_write(fixture_row(i,100000+i*100000));self.ids[rx]+=1
            self.next=self.clock()+100_000_000
        s.step()

    def finish_fixture(self):
        # Explicit test-resource cleanup, never counted as protocol retries.
        for obj in self.objects:
            serial.Serial.close(obj)
        for e in self.pairs.values():e.dispose_fixture()
        self.tmp.cleanup()


class IdentityAndGateTests(unittest.TestCase):
    def setUp(self):
        self.rig=Rig();self.addCleanup(self.rig.finish_fixture)

    def metadata(self, rx):
        return self.rig.identities[rx]['resolved'],dict(ID_SERIAL_SHORT=uart.capture.RECEIVERS[rx],
                   ID_VENDOR_ID='1a86',ID_MODEL_ID='55d3',ID_BUS='usb')

    def preflight(self):
        with patch.object(uart.capture,'resolve_ports',return_value={rx:d['resolved'] for rx,d in self.rig.identities.items()}), \
             patch.object(uart.capture,'port_identity',side_effect=lambda p:self.metadata(next(rx for rx,v in uart.PORTS.items() if v==p))), \
             patch('serial.Serial',side_effect=AssertionError('No serial construction in preflight')):
            return uart.preflight_uart(plan())

    def test_default_prepare_does_not_discover_construct_or_open(self):
        with patch.object(sys,'argv',['uart']),patch.object(uart,'preflight_uart',side_effect=AssertionError('No default preflight')), \
             patch('serial.Serial',side_effect=AssertionError('No constructor')),contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(uart_main(),0)
        self.assertFalse(json.loads(out.getvalue())['physical_UART_opened'])

    def test_preflight_uses_verified_by_id_identity_and_permissions_without_open(self):
        result=self.preflight()
        self.assertEqual(set(result),set(uart.PORTS))
        self.assertTrue(all(d['by_id']==uart.PORTS[rx] for rx,d in result.items()))
        self.assertTrue(all('node_fingerprint' in d and 'permissions' in d for d in result.values()))

    def test_permission_denial_does_not_attempt_open_or_permission_changes(self):
        with patch.object(uart.os,'access',return_value=False):
            with self.assertRaises(PermissionError):self.preflight()
        self.assertFalse(self.rig.objects)

    def test_wrong_PID_serial_or_device_change_rejected(self):
        rx='RX-01';node,props=self.metadata(rx)
        for key,value in [('ID_MODEL_ID','wrong'),('ID_SERIAL_SHORT','wrong'),('ID_BUS','pci')]:
            with patch.object(uart.capture,'port_identity',return_value=(node,dict(props,**{key:value}))):
                with self.assertRaises(ValueError):uart.identity(rx)
        with patch.object(uart,'identity',return_value=dict(changed=True)):
            with self.assertRaises(ValueError):uart.revalidate(rx,self.rig.identities[rx])

    def test_duplicate_identity_preflight_failure_is_not_retried(self):
        with patch.object(uart.capture,'resolve_ports',side_effect=ValueError('duplicate serial')) as resolve:
            with self.assertRaises(ValueError):uart.preflight_uart(plan())
            resolve.assert_called_once()

    def test_physical_gate_rejects_missing_authorization_and_incomplete_environment(self):
        for ref in (None,'','PENDIENTE','COMPLETAR-CON-AUTORIZACION-NUEVA'):
            with self.assertRaises(ValueError):uart.check_authorization(ref)
        p=json.loads((ROOT/'config/campana_presencia_uart_v4.template.json').read_text())
        with patch('serial.Serial',side_effect=AssertionError('No physical opening')):
            with self.assertRaises(ValueError):uart.UartSession(self.rig.output,p)
        with self.assertRaises(ValueError):uart.validate_uart_plan(p,execution=True)


class SerialLifecycleTests(unittest.TestCase):
    def rig(self,*args,**kwargs):
        r=Rig(*args,**kwargs);self.addCleanup(r.finish_fixture);return r

    def test_preopen_buffer_preserved_and_no_input_or_output_flush(self):
        r=self.rig();r.initial_bytes()
        with r.session() as s:
            s.step()
            self.assertIsNotNone(s.machine.initial_available)
            for e in s.endpoints.values():
                self.assertEqual(e.serial.open_flush_suppressed,1)
                with self.assertRaises(RuntimeError):e.serial.reset_input_buffer()
                with self.assertRaises(RuntimeError):e.serial.reset_output_buffer()
            s.command('interrupt');s.step()
        audited=audit_v4(r.output)
        self.assertEqual(audited['state']['evidence_type'],'synthetic_fixture')
        for rx in uart.PORTS:self.assertTrue((r.output/(rx.lower()+'.serial.log')).read_bytes().startswith(fixture_ready(rx)))

    def test_HUPCL_is_not_silently_cleared_by_serial_configuration(self):
        import termios
        r=self.rig()
        for e in r.pairs.values():
            attrs=termios.tcgetattr(e.slave);attrs[2]|=termios.HUPCL
            termios.tcsetattr(e.slave,termios.TCSANOW,attrs)
        with r.session() as s:
            for e in s.endpoints.values():self.assertTrue(termios.tcgetattr(e.serial.fileno())[2] & termios.HUPCL)
            s.command('interrupt');s.step()

    def test_nonignored_DTR_ioctl_error_is_not_retried_or_hidden(self):
        r=self.rig()
        with patch.object(r.serial_type,'_update_dtr_state',side_effect=OSError(errno.EIO,'synthetic modem-line failure')):
            with self.assertRaises(OSError):r.session()
        self.assertEqual(len([c for c in r.calls if c[0]=='open']),1)
        self.assertTrue(all(not o.is_open for o in r.objects))

    def test_dtr_rts_requests_precede_open_and_are_not_electrical_guarantees(self):
        r=self.rig(effective_ioctls=True)
        with r.session() as s:
            for call in r.calls:
                if call[0]=='open':self.assertEqual(call[2:],(False,False,False))
            for e in s.endpoints.values():
                self.assertEqual([(v['line'],v['requested'],v['outcome']) for v in e.serial.line_requests],
                                 [('dtr',False,'ioctl_returned'),('rts',False,'ioctl_returned')])
                self.assertFalse(e.details()['electrical_transients_or_resets_excluded'])
            s.command('interrupt');s.step()

    def test_actual_PTY_ENOTTY_may_skip_RTS_even_though_getter_is_false(self):
        r=self.rig()
        with r.session() as s:
            for e in s.endpoints.values():
                attempts=e.serial.line_requests
                self.assertEqual(attempts[0]['line'],'dtr')
                self.assertEqual(attempts[0]['errno'],errno.ENOTTY)
                self.assertFalse(e.serial.rts)
                self.assertFalse(any(v['line']=='rts' for v in attempts))
            s.command('interrupt');s.step()

    def test_second_open_failure_closes_both_registered_resources_once(self):
        r=self.rig('second_open')
        with self.assertRaisesRegex(OSError,'second open'):r.session()
        self.assertEqual([o.protocol_closes for o in r.objects],[1,1])
        self.assertTrue(all(not o.is_open and o.fd is None for o in r.objects))
        result=audit_v4(r.output)
        self.assertFalse(result['state']['connection']['quality_ok'])
        self.assertFalse(result['state']['physical_execution_enabled'])

    def test_first_receiver_is_drained_while_second_open_is_pending_or_fails(self):
        r=self.rig('second_open_slow');r.initial_bytes()
        with self.assertRaisesRegex(OSError,'first reader'):r.session()
        self.assertTrue((r.output/'rx-01.serial.log').read_bytes().startswith(fixture_ready('RX-01')))
        self.assertEqual([o.protocol_closes for o in r.objects],[1,1])
        report=json.loads((r.output/'summary.json').read_text())
        self.assertTrue(report['runtime']['startup_reader_stopped'])
        self.assertTrue(audit_v4(r.output)['replay_ok'])

    def test_identity_change_before_second_open_never_opens_changed_resource(self):
        r=self.rig('identity_changed')
        with self.assertRaisesRegex(ValueError,'identity changed'):r.session()
        self.assertEqual([c[1] for c in r.calls if c[0]=='open'],['RX-01'])
        self.assertTrue(all(not o.is_open for o in r.objects))

    def test_opened_fd_mismatch_suspends_and_closes_without_retry(self):
        r=self.rig();r.identities['RX-01']['node_fingerprint']=[0,0,0]
        with self.assertRaisesRegex(ValueError,'Opened fd'):r.session()
        self.assertEqual(len([c for c in r.calls if c[0]=='open']),1)
        self.assertTrue(all(not o.is_open for o in r.objects))

    def test_close_failure_attempts_other_resource_and_withholds_confirmed_sound(self):
        r=self.rig('close_error')
        with r.session() as s:
            s.command('interrupt');s.step()
            self.assertEqual([o.protocol_closes for o in r.objects],[1,1])
            self.assertTrue(r.objects[0].is_open);self.assertFalse(r.objects[1].is_open)
            self.assertFalse(any(c['kind']=='both_ports_closed_confirmed' for c in s.machine.signals))
        self.assertEqual([o.protocol_closes for o in r.objects],[1,1])

    def test_destructor_does_not_hide_close_retries(self):
        import weakref
        endpoint=OwnedPty('RX-01');calls=[];fds=[]
        class FailClose(serial.Serial):
            def close(self):
                calls.append('close');raise OSError('synthetic close failure')
        try:
            instance=uart.audited_serial_type(FailClose)(port=None)
            instance.dtr=False;instance.rts=False;instance.port=os.ttyname(endpoint.slave)
            instance.open()
            fds=[getattr(instance,k) for k in ('fd','pipe_abort_read_r','pipe_abort_read_w','pipe_abort_write_r','pipe_abort_write_w')]
            with self.assertRaises(OSError):instance.close()
            reference=weakref.ref(instance);del instance;gc.collect()
            self.assertIsNone(reference());self.assertEqual(calls,['close'])
        finally:
            for fd in fds:
                try:os.close(fd)
                except OSError:pass
            endpoint.dispose_fixture()

    def test_disconnect_closes_both_and_records_error(self):
        r=self.rig();r.initial_bytes()
        with r.session() as s:
            s.step();os.close(r.pairs['RX-01'].master);r.pairs['RX-01'].master_fd_open=False
            s.step()
            self.assertTrue(s.read_loop_stopped)
            self.assertTrue(s.machine.fatal.startswith('io_error'))
            self.assertTrue(all(not o.is_open for o in r.objects))
        self.assertTrue(audit_v4(r.output)['replay_ok'])

    def test_fileno_or_select_failure_also_closes_both(self):
        r=self.rig()
        with r.session() as s:
            with patch.object(s.endpoints['RX-01'].serial,'fileno',side_effect=OSError('synthetic fd failure')):s.step()
            self.assertTrue(s.read_loop_stopped)
            self.assertEqual([o.protocol_closes for o in r.objects],[1,1])

    def test_missing_READY_keeps_10s_timeout_and_no_windows(self):
        r=self.rig()
        with r.session() as s:
            r.clock.advance(10_000_000_000);s.step()
            self.assertEqual(s.machine.fatal,'initial_availability_timeout')
            self.assertFalse(s.machine.windows)
        self.assertEqual(len([c for c in r.calls if c[0]=='open']),2)

    def test_timeout_after_first_open_prevents_second_open(self):
        r=self.rig();original=r.checker
        def checker(rx,expected):
            result=original(rx,expected)
            if rx=='RX-01' and any(c[0]=='open' for c in r.calls):r.clock.advance(10_000_000_000)
            return result
        r.backend['checker']=checker
        with self.assertRaisesRegex(RuntimeError,'deadline'):r.session()
        self.assertEqual(len([c for c in r.calls if c[0]=='open']),1)

    def test_two_fixed_windows_through_real_pyserial_PTY_backend_and_replay(self):
        r=self.rig();r.initial_bytes()
        with r.session() as s:
            for _ in range(4300):
                r.step(s);m=s.machine
                if m.fatal:self.fail(m.fatal)
                if m.initial_available is not None:
                    if m.windows:
                        w=m.windows[-1]
                        if w['end_signal'] is not None and m.signals[w['end_signal']]['ack_ns'] is not None and w['label']['status']=='pending':
                            s.command('declare',slot_id=w['id'],established=True,maintained=True,heard=True,notes='')
                    if not m.close_requested and len(m.windows)<2 and (not m.windows or m.windows[-1]['label']['status']=='declared'):
                        s.command('request',slot_id=plan()['slots'][len(m.windows)]['id'],last=len(m.windows)==1)
                if s.read_loop_stopped:break
            else:self.fail('Synthetic two-window fixture did not finish')
        report=audit_v4(r.output)
        self.assertEqual(len(report['state']['windows']),2)
        self.assertTrue(all(w['eligible'] and w['T1_ns']-w['T0_ns']==30_000_000_000 for w in report['state']['windows']))
        self.assertTrue(all(o.protocol_closes==1 for o in r.objects))
        for rx in uart.PORTS:self.assertEqual((r.output/(rx.lower()+'.serial.log')).read_bytes().count(b'READY'),1)

    def test_KeyboardInterrupt_still_closes_both(self):
        r=self.rig()
        with self.assertRaises(KeyboardInterrupt):
            with r.session():raise KeyboardInterrupt()
        self.assertTrue(all(not o.is_open for o in r.objects))
        self.assertEqual([o.protocol_closes for o in r.objects],[1,1])


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.r=Rig();self.addCleanup(self.r.finish_fixture)

    def test_insufficient_initial_storage_never_constructs_serial(self):
        self.r.free=99*1024**2
        with self.assertRaises(uart.StorageLimit):self.r.session()
        self.assertFalse(self.r.objects)

    def test_changed_serial_source_lock_is_rejected_before_construction(self):
        with patch.object(uart,'digest',return_value='0'*64):
            with self.assertRaisesRegex(ValueError,'source differs'):self.r.session()
        self.assertFalse(self.r.objects)

    def test_storage_write_failure_still_closes_both_and_has_no_success_receipt(self):
        s=self.r.session()
        try:
            with patch.object(s.journal.ops,'write',side_effect=OSError('disk full')):
                with self.assertRaises(OSError):s.command('tick')
                s.close()
            self.assertTrue(all(not o.is_open for o in self.r.objects))
            self.assertEqual([o.protocol_closes for o in self.r.objects],[1,1])
            self.assertFalse(s.receipt_persisted)
            self.assertFalse(any(c['kind']=='both_ports_closed_confirmed' and c['ack_ns'] is not None for c in s.machine.signals))
        finally:s.journal.close_files()

    def test_receipt_failure_closes_both_but_cannot_emit_confirmed_close_audio(self):
        s=self.r.session()
        try:
            with patch.object(s.journal,'receipt',side_effect=OSError('synthetic receipt disk failure')):
                with self.assertRaises(OSError):s.close()
            self.assertTrue(all(not o.is_open for o in self.r.objects))
            self.assertFalse(s.receipt_persisted)
            self.assertFalse(any(c['kind']=='both_ports_closed_confirmed' and c['ack_ns'] is not None for c in s.machine.signals))
            self.assertEqual([o.protocol_closes for o in self.r.objects],[1,1])
        finally:s.journal.close_files();s._finish_notifier()

    def test_decision_clock_is_resampled_after_raw_persistence_latency(self):
        s=self.r.session()
        try:
            raw=s.journal.raw['RX-01'];flush=raw.flush
            def delayed_flush():
                flush();self.r.clock.advance(2_000_000_000)
            with patch.object(raw,'flush',side_effect=delayed_flush):
                s.command('chunk',receiver='RX-01',chunk=b'kept\n',started_ns=0,returned_ns=0)
            self.assertEqual(s.machine.now,2_000_000_000)
            last=json.loads((self.r.output/'operations.jsonl').read_text().splitlines()[-1])
            self.assertEqual(last['now_ns'],2_000_000_000)
            s.command('interrupt');s.step()
        finally:s.finalize()

    def test_reserve_loss_stops_reads_and_closes_both(self):
        s=self.r.session()
        try:
            self.r.free=31*1024**2;self.r.clock.advance(300_000_000);s.step()
            self.assertEqual(s.machine.fatal,'storage_error')
            self.assertTrue(all(not o.is_open for o in self.r.objects))
            with self.assertRaises(uart.StorageLimit):s.finalize()
        finally:s.journal.close_files()

    def test_returned_chunk_is_kept_even_before_budget_failure(self):
        with self.r.session() as s:
            payload=b'preserve-entire-returned-chunk\n'
            self.r.pairs['RX-01'].fixture_write(payload)
            s.step()
            with patch.object(s.guard,'check',side_effect=uart.StorageLimit('synthetic raw limit')):s.step()
            self.assertTrue(all(not o.is_open for o in self.r.objects))
        self.assertEqual((self.r.output/'rx-01.serial.log').read_bytes(),payload)
        self.assertTrue(audit_v4(self.r.output)['replay_ok'])

    def test_elapsed_raw_and_bundle_limits_are_explicit(self):
        s=self.r.session()
        try:
            self.r.clock.advance(uart.STORAGE['max_connection_ns'])
            with self.assertRaisesRegex(uart.StorageLimit,'duration'):s.guard.check()
            self.r.clock.now=0
            with patch.dict(uart.STORAGE,max_raw_bytes=0):
                with self.assertRaisesRegex(uart.StorageLimit,'raw'):s.guard.check()
            with self.assertRaisesRegex(uart.StorageLimit,'bundle'):s.guard.check(final_extra=uart.STORAGE['max_bundle_bytes'])
            s.command('interrupt');s.step()
        finally:s.finalize()

    def test_final_metadata_requires_space_for_itself_plus_reserve(self):
        s=self.r.session()
        try:
            self.r.free=uart.STORAGE['reserve_bytes']+100
            with self.assertRaisesRegex(uart.StorageLimit,'reserve'):s.guard.check(final_extra=101)
            self.r.free=1024**3;s.command('interrupt');s.step()
        finally:s.finalize()


class SoundsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.out=Path(self.tmp.name)/'sounds'

    def test_default_only_exports_without_serial_PTY_or_playback(self):
        with patch('serial.Serial',side_effect=AssertionError('No serial')),patch('os.openpty',side_effect=AssertionError('No PTY')), \
             patch('practicar_sonidos_v4.subprocess.run',side_effect=AssertionError('No playback')):
            result=practice(self.out)
        self.assertEqual(result['playback'],[])
        self.assertEqual(result['human_confirmation'],'pending')
        self.assertFalse(result['human_audibility_verified_automatically'])
        self.assertEqual(len(list(self.out.glob('*.wav'))),4)

    def test_human_answer_is_declaration_not_automatic_audibility(self):
        with patch('practicar_sonidos_v4.subprocess.run',return_value=SimpleNamespace(returncode=0)) as run:
            result=practice(self.out,delay=30,feedback=lambda _: 'sí',player='/synthetic/player',sleep=lambda _:None)
        self.assertEqual(run.call_count,4)
        self.assertEqual(result['human_confirmation'],'declared_distinguishable')
        self.assertFalse(result['human_audibility_verified_automatically'])
        self.assertTrue(result['no_real_close_confirmed'])

    def test_failed_audio_never_prompts_for_or_infers_human_confirmation(self):
        with patch('practicar_sonidos_v4.subprocess.run',return_value=SimpleNamespace(returncode=1)):
            with self.assertRaises(RuntimeError):practice(self.out,delay=30,feedback=lambda _:self.fail('No prompt on failure'),
                player='/synthetic/player',sleep=lambda _:None)
        r=json.loads((self.out/'practice.json').read_text())
        self.assertEqual(r['human_confirmation'],'pending')
        self.assertIn('error',r)


if __name__=='__main__':unittest.main()
