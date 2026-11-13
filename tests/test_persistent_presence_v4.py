"""v4 contract tests: in-memory clocks and process-owned PTYs only."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'tools'))
from campana_presencia_v4 import fixture_ready, fixture_row, run_demo
from capture_csi_multi import RECEIVERS
from persistent_presence_v4 import POLICY, PersistentPresenceV4, SECOND, validate_plan
from presence_v4_audio import PATTERNS, LaptopNotifier, RecordingNotifier, create_wav
from presence_v4_journal import audit_v4, digest
from presence_v4_pty import OwnedPty, PtySession, SyntheticClock


def plan():
    return json.loads((ROOT/'config/campana_presencia_v4.template.json').read_text())


class Memory:
    def __init__(self, available=True):
        self.m = PersistentPresenceV4(plan())
        self.t = SECOND
        self.ids = dict.fromkeys(RECEIVERS, 0)
        self.call('begin')
        for rx in RECEIVERS:
            self.call('opened', receiver=rx)
            if available:
                self.send(rx, fixture_ready(rx))
        if available:
            self.advance(.6)
            assert self.m.initial_available is not None

    def call(self, op, **data):
        self.m.apply(op, self.t, **data)

    def send(self, rx, data, start=None, end=None):
        self.call('chunk', receiver=rx, chunk=data, started_ns=self.t if start is None else start,
                  returned_ns=self.t if end is None else end)

    def row(self, rx, **kwargs):
        i = self.ids[rx]; self.ids[rx] += 1
        self.send(rx, fixture_row(i, 100000+i*200000), **kwargs)

    def signals(self):
        for cue in list(self.m.signals):
            if cue['ack_ns'] is None:
                self.call('cue_ack', signal_id=cue['id'], success=True)

    def step(self, ns=200_000_000):
        self.t += ns
        for rx in RECEIVERS:
            self.row(rx)
        self.call('tick'); self.signals()

    def advance(self, seconds):
        remaining = int(seconds*SECOND)
        while remaining:
            n = min(200_000_000, remaining)
            self.step(n); remaining -= n

    def until(self, predicate, max_steps=700):
        for _ in range(max_steps):
            if predicate():
                return
            self.step()
        raise AssertionError('Memory fixture did not reach expected state')

    def request(self, index=0, last=False):
        self.call('request', slot_id=plan()['slots'][index]['id'], last=last)

    def running(self):
        self.request()
        self.until(lambda: self.m.windows[-1]['state'] == 'running')
        return self.m.windows[-1]

    def finished(self):
        self.until(lambda: self.m.windows[-1]['end_signal'] is not None)

    def declare(self, **overrides):
        data=dict(slot_id=self.m.windows[-1]['id'], established=True, maintained=True, heard=True, notes='')
        data.update(overrides); self.call('declare', **data)

    def close(self):
        self.call('close_request'); self.call('closing')
        for rx in RECEIVERS:
            self.call('closed', receiver=rx, confirmed=True, reader_stopped=True)
        self.signals()


class MemoryProtocolTests(unittest.TestCase):
    def test_two_windows_reuse_ready_but_require_new_gate_rows_and_fixed_30s(self):
        h=Memory(); first=h.running(); h.finished(); h.declare()
        t0,t1=first['T0_ns'],first['T1_ns']
        h.request(1,last=True)
        h.until(lambda:h.m.windows[-1]['state']=='gate')
        self.assertTrue(all(not s['gate_rows'] for s in h.m.states.values()))
        self.assertIsNone(h.m.windows[-1]['T0_ns'])
        h.until(lambda:h.m.windows[-1]['state']=='running')
        second=h.m.windows[-1]
        self.assertGreater(second['T0_ns'],t1)
        self.assertEqual(second['T1_ns']-second['T0_ns'],30*SECOND)
        self.assertEqual((first['T0_ns'],first['T1_ns']),(t0,t1))
        self.assertEqual(sum(e['kind']=='opened' for e in h.m.events),2)
        self.assertEqual(sum(e['kind']=='line' and e['evidence']['kind']=='ready' for e in h.m.events),2)
        h.finished();h.declare();h.close()
        s=h.m.summary()
        self.assertTrue(all(w['eligible'] for w in s['windows']),s['fatal'])

    def test_initial_ready_is_not_invented_and_deadline_does_not_slide(self):
        h=Memory(available=False);h.advance(10)
        self.assertEqual(h.m.fatal,'initial_availability_timeout')
        self.assertFalse(h.m.windows)
        with self.assertRaises(ValueError):h.request()

    def test_same_chunk_reset_after_third_row_never_establishes_availability(self):
        h=Memory(available=False)
        for rx in RECEIVERS:
            h.send(rx,fixture_ready(rx)+b''.join(fixture_row(i,100000+i*200000) for i in range(3))+
                   (b'ESP-ROM:synthetic-reset\n' if rx=='RX-02' else b''))
        h.call('tick')
        self.assertIsNone(h.m.initial_available)
        self.assertIsNotNone(h.m.fatal)

    def test_delay_is_from_actual_ack_not_nominal_cue_time(self):
        h=Memory();h.request()
        for _ in range(170):
            h.t+=200_000_000
            for rx in RECEIVERS:h.row(rx)
            h.call('tick')
        self.assertIsNone(h.m.windows[-1]['gate_ns'])
        h.signals();ack=h.t
        h.advance(29.8)
        self.assertIsNone(h.m.windows[-1]['gate_ns'])
        h.advance(.2)
        self.assertGreaterEqual(h.m.windows[-1]['gate_ns'],ack+30*SECOND)

    def test_exact_freshness_limit_and_loss_during_delay_or_between_windows(self):
        for phase in ('idle','delay','window','between'):
            with self.subTest(phase=phase):
                h=Memory()
                if phase=='delay':h.request()
                if phase in ('window','between'):h.running()
                if phase=='between':h.finished();h.declare()
                h.t+=SECOND;h.call('tick')
                self.assertIsNone(h.m.fatal)
                h.t+=1;h.call('tick')
                self.assertTrue(h.m.fatal.startswith('availability_lost'))
                with self.assertRaises(ValueError):h.request(1)

    def test_duplicate_ready_reset_invalid_utf8_and_info_suspend_connection(self):
        for bad in (fixture_ready('RX-01'),b'ESP-ROM:reset\n',b'\xff\n',b'I (12) csi_recv: changed\n'):
            h=Memory();h.send('RX-01',bad);h.call('tick')
            self.assertIsNotNone(h.m.fatal)
            self.assertTrue(h.m.close_requested)

    def test_callback_gap_restart_clock_and_queue_changes_are_fatal(self):
        for what in ('gap','restart','clock','drops'):
            h=Memory();rx='RX-01';i=h.ids[rx]
            raw=fixture_row(i+1 if what=='gap' else 0 if what=='restart' else i,
                            1 if what=='clock' else 100000+i*200000)
            if what=='drops':
                from capture_csi_multi import FIELDS
                import csv,io
                row=next(csv.reader(io.StringIO(raw.decode())))
                row[FIELDS.index('queue_drops')]='1'
                s=io.StringIO();csv.writer(s,lineterminator='\n').writerow(row);raw=s.getvalue().encode()
            h.send(rx,raw)
            self.assertIsNotNone(h.m.fatal,what)

    def test_uint32_wrap_remains_valid_and_reset_does_not_rearm(self):
        h=Memory(available=False)
        for rx in RECEIVERS:
            h.send(rx,fixture_ready(rx))
            for i,t in enumerate((2**32-300000,2**32-100000,100000)):
                h.t+=1;h.send(rx,fixture_row(i,t))
        h.call('tick');self.assertIsNotNone(h.m.initial_available)
        h.send('RX-01',b'rst:synthetic\n');h.send('RX-01',fixture_ready('RX-01'))
        self.assertIsNotNone(h.m.fatal)
        with self.assertRaises(ValueError):h.call('begin')

    def test_T1_exact_is_excluded_and_T0_is_never_extended(self):
        h=Memory();w=h.running();t0,t1=w['T0_ns'],w['T1_ns']
        h.until(lambda:h.t>=t1-200_000_000)
        h.step(t1-h.t)
        s=h.m.summary()['windows'][0]
        for rx,r in s['receivers'].items():
            self.assertTrue(all(int(v['returned_ns'])<t1 for v in r['included_line_references']))
        self.assertEqual((w['T0_ns'],w['T1_ns']),(t0,t1))

    def test_T0_exact_is_inclusive_and_repeated_host_timestamps_remain_repeated(self):
        h=Memory();w=h.running();rx='RX-01';t0=w['T0_ns']
        h.row(rx,start=t0,end=t0);h.row(rx,start=t0,end=t0)
        r=h.m.summary()['windows'][0]['receivers'][rx]
        included=r['included_line_references']
        self.assertGreaterEqual(sum(int(v['returned_ns'])==t0 for v in included),2)
        self.assertIn(0,r['coverage']['gaps_ns'])

    def test_read_chronology_failure_does_not_erase_its_bytes_or_move_window(self):
        h=Memory();w=h.running();t0=w['T0_ns'];f=h.m.framers['RX-01'];before=f.offset
        raw=b'chronology-evidence\n'
        h.send('RX-01',raw,start=h.t+1,end=h.t)
        self.assertEqual(f.offset-before,len(raw))
        self.assertTrue(h.m.fatal.startswith('read_chronology:'))
        self.assertEqual(w['T0_ns'],t0)

    def test_no_overlapping_request_or_silent_slot_replacement(self):
        h=Memory();h.running();self.assertEqual(len(h.m.windows),1)
        with self.assertRaises(ValueError):h.request(1)
        h.call('interrupt')
        with self.assertRaises(ValueError):h.request()
        self.assertEqual(len(h.m.windows),1)

    def test_cross_start_partial_line_is_kept_but_not_selected(self):
        h=Memory();h.request();h.until(lambda:h.m.windows[-1]['state']=='gate')
        # Supply three complete gate rows, then a partial fourth before decision.
        for _ in range(3):
            h.t+=200_000_000
            for rx in RECEIVERS:h.row(rx)
        rx='RX-01';i=h.ids[rx];h.ids[rx]+=1
        line=fixture_row(i,100000+i*200000)
        h.send(rx,line[:80]);h.t+=1;h.call('tick');h.signals()
        t0=h.m.windows[-1]['T0_ns'];self.assertIsNotNone(t0)
        h.t+=100000000;h.send(rx,line[80:]);h.call('tick')
        refs=h.m.summary()['windows'][0]['receivers'][rx]['included_line_references']
        self.assertNotIn(i,[r['id'] for r in refs])
        self.assertEqual(h.m.states[rx]['lines'][-1]['byte_length'],len(line))

    def test_late_contradiction_rejects_gate_without_replacing_T0(self):
        h=Memory();h.request();h.until(lambda:h.m.windows[-1]['state']=='gate')
        for _ in range(3):
            h.t+=200000000
            for rx in RECEIVERS:h.row(rx)
        last_read=h.t;h.t+=10;h.call('tick')
        w=h.m.windows[-1];t0=w['T0_ns'];h.t+=100
        h.send('RX-01',b'broken\n',start=last_read,end=t0-1)
        self.assertIsNotNone(h.m.fatal)
        self.assertEqual(w['T0_ns'],t0)
        self.assertEqual(w['state'],'aborted')

    def test_resets_and_discontinuities_between_windows_cannot_use_old_READY(self):
        for bad in (b'ESP-ROM:reset\n',fixture_row(0,100000)):
            h=Memory();h.running();h.finished();h.declare();first=copy.deepcopy(h.m.windows[0])
            h.send('RX-02',bad);h.call('tick')
            self.assertIsNotNone(h.m.fatal)
            self.assertEqual(h.m.windows[0]['T0_ns'],first['T0_ns'])
            self.assertTrue(h.m.summary()['windows'][0]['window_quality_ok'])
            with self.assertRaises(ValueError):h.request(1)

    def test_cue_failure_during_delay_suspends_without_false_start_or_label(self):
        h=Memory();h.request()
        for _ in range(150):
            h.t+=200000000
            for rx in RECEIVERS:h.row(rx)
            h.call('tick')
        signal=h.m.windows[-1]['start_signal']
        h.call('cue_ack',signal_id=signal,success=False)
        self.assertEqual(h.m.fatal,'notification_failed')
        self.assertIsNone(h.m.windows[-1]['T0_ns'])
        self.assertEqual(h.m.windows[-1]['label']['status'],'pending')

    def test_uncertain_label_preserves_data_quality_but_suspends_remaining_slots(self):
        h=Memory();h.running();h.finished();h.declare(heard=False)
        h.close();s=h.m.summary()
        self.assertTrue(s['connection']['quality_ok'])
        self.assertTrue(s['windows'][0]['window_quality_ok'])
        self.assertEqual(s['windows'][0]['label']['status'],'uncertain')
        self.assertFalse(s['windows'][0]['eligible'])
        self.assertEqual(s['remaining_slots'][0]['state'],'suspended')

    def test_pending_label_blocks_next_request_and_timer_does_not_confirm_label(self):
        h=Memory();h.running();h.finished()
        with self.assertRaises(ValueError):h.request(1)
        self.assertEqual(h.m.summary()['windows'][0]['label']['status'],'pending')

    def test_sparse_coverage_suspends_separately_from_transport_and_window(self):
        h=Memory();h.running()
        while h.m.windows[-1]['state']=='running':h.step(SECOND)
        self.assertEqual(h.m.fatal,'pilot_coverage_failed')
        h.close();s=h.m.summary()
        self.assertTrue(s['connection']['quality_ok'])
        self.assertTrue(s['windows'][0]['window_quality_ok'])
        self.assertFalse(s['windows'][0]['pilot_coverage_ok'])

    def test_interrupt_and_close_failure_never_invent_confirmed_close(self):
        h=Memory();h.running();h.call('interrupt');h.call('closing')
        h.call('closed',receiver='RX-01',confirmed=False,reader_stopped=True,error='fixture')
        h.call('closed',receiver='RX-02',confirmed=True,reader_stopped=True)
        self.assertFalse(any(s['kind']=='both_ports_closed_confirmed' for s in h.m.signals))
        self.assertEqual(h.m.close_counts,dict.fromkeys(RECEIVERS,1))

    def test_plan_mutations_physical_transport_and_duplicate_opens_are_rejected(self):
        for name in POLICY:
            p=plan();p['policy'][name]+=1
            with self.assertRaises(ValueError):validate_plan(p)
        h=Memory()
        with self.assertRaises(ValueError):h.call('opened',receiver='RX-01')
        p=plan();p['execution_mode']='physical'
        with self.assertRaises(ValueError):validate_plan(p)
        with self.assertRaises(ValueError):SyntheticClock(0)


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.out=Path(self.tmp.name)/'new'

    def test_real_PTY_two_windows_full_evidence_single_open_and_replay(self):
        with patch('serial.Serial',side_effect=AssertionError('No UART')), \
             patch('capture_csi_multi.port_identity',side_effect=AssertionError('No discovery')):
            report=run_demo(plan(),self.out,stepped=True)
        self.assertTrue(report['replay_ok'])
        self.assertIsNone(report['state']['fatal'])
        self.assertEqual(len(report['state']['windows']),2)
        self.assertTrue(all(w['eligible'] for w in report['state']['windows']))
        metadata=json.loads((self.out/'summary.json').read_text())['runtime']
        self.assertEqual(metadata['opens_per_receiver'],dict.fromkeys(RECEIVERS,1))
        self.assertEqual(metadata['close_attempts'],dict.fromkeys(RECEIVERS,1))
        self.assertFalse(metadata['audibility_verified'])
        for rx in RECEIVERS:
            raw=(self.out/(rx.lower()+'.serial.log')).read_bytes()
            self.assertEqual(raw.count(b'READY'),1)
            rows=[r for w in report['state']['windows'] for r in w['receivers'][rx]['included_line_references']]
            self.assertTrue(all(hashlib.sha256(raw[r['byte_offset']:r['byte_end']]).hexdigest()==r['line_sha256'] for r in rows))

    def test_fixture_cleanup_never_recloses_an_already_closed_or_reused_descriptor(self):
        endpoint=OwnedPty('RX-01')
        try:
            self.assertTrue(endpoint.close_receiver())
            with patch('presence_v4_pty.os.close',wraps=os.close) as closed:
                endpoint.dispose_fixture();endpoint.dispose_fixture()
                closed.assert_called_once_with(endpoint.master)
        finally:endpoint.dispose_fixture()

    def test_rehashed_forged_summary_or_raw_reference_fails_replay(self):
        # Small failed connection still contains raw bytes and a complete receipt.
        with PtySession(self.out,plan()) as s:
            s.endpoints['RX-01'].fixture_write(b'original\n');s.step()
            s.command('interrupt');s.step()
        path=self.out/'summary.json';v=json.loads(path.read_text());v['state']['connection']['quality_ok']=True
        path.write_text(json.dumps(v))
        manifest=json.loads((self.out/'manifest.json').read_text())
        e=next(e for e in manifest['files'] if e['path']=='summary.json');e.update(bytes=path.stat().st_size,sha256=digest(path))
        (self.out/'manifest.json').write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError,'Replayed summary'):audit_v4(self.out)

    def test_no_timer_or_one_close_result_plays_the_confirmed_close_cue(self):
        with PtySession(self.out,plan()) as s:
            self.assertFalse(s.machine.signals)
            s.command('tick')
            self.assertFalse(any(x['kind']=='both_ports_closed_confirmed' for x in s.machine.signals))
            s.close()
            receipt=json.loads((self.out/'close-receipt.json').read_text())
            self.assertTrue(receipt['both_confirmed'])
            self.assertFalse(receipt['timer_is_close_proof'])
            cue=next(x for x in s.machine.signals if x['kind']=='both_ports_closed_confirmed')
            self.assertIsNotNone(cue['ack_ns'])
            with self.assertRaises(RuntimeError):s.read_ready()

    def test_close_error_attempts_other_port_and_withholds_receipt_success_sound(self):
        class FailingClose(OwnedPty):
            def close_receiver(self):
                if self.receiver=='RX-01':
                    self.close_attempts+=1;raise OSError('synthetic close failure')
                return super().close_receiver()
        with PtySession(self.out,plan(),endpoint_type=FailingClose) as s:
            s.command('interrupt');s.step()
            self.assertEqual({rx:e.close_attempts for rx,e in s.endpoints.items()},dict.fromkeys(RECEIVERS,1))
            self.assertFalse(s.receipt_persisted and json.loads((self.out/'close-receipt.json').read_text())['both_confirmed'])
            self.assertFalse(any(c['kind']=='both_ports_closed_confirmed' for c in s.machine.signals))

    def test_partial_tail_wait_is_bounded_and_all_bytes_remain(self):
        with PtySession(self.out,plan(),clock=SyntheticClock(50)) as s:
            s.endpoints['RX-01'].fixture_write(b'incomplete-without-LF');s.step()
            before=time.monotonic();s.close()
            self.assertLess(time.monotonic()-before,.2)
            self.assertIn('incomplete_tail:RX-01',s.machine.connection_reasons)
        self.assertEqual((self.out/'rx-01.serial.log').read_bytes(),b'incomplete-without-LF')
        self.assertTrue(audit_v4(self.out)['integrity_ok'])

    def test_close_completes_pending_LF_and_keeps_complete_raw(self):
        with PtySession(self.out,plan()) as s:
            s.endpoints['RX-01'].fixture_write(b'prefix');s.step()
            def finish_line():
                time.sleep(.01);s.endpoints['RX-01'].fixture_write(b'-suffix\n')
            worker=threading.Thread(target=finish_line);worker.start()
            try:s.close()
            finally:worker.join(1)
            self.assertFalse(s.machine.framers['RX-01'].length)
            self.assertNotIn('incomplete_tail:RX-01',s.machine.connection_reasons)
        self.assertEqual((self.out/'rx-01.serial.log').read_bytes(),b'prefix-suffix\n')
        self.assertTrue(audit_v4(self.out)['replay_ok'])

    def test_close_byte_budget_preserves_limit_and_rejects_remaining_tail(self):
        with PtySession(self.out,plan(),clock=SyntheticClock(10)) as s:
            s.endpoints['RX-01'].fixture_write(b'x');s.step()
            stopped=threading.Event()
            def produce():
                while not stopped.is_set():
                    try:s.endpoints['RX-01'].fixture_write(b'x'*1024)
                    except BlockingIOError:pass
                    except OSError:return
                    time.sleep(.0001)
            worker=threading.Thread(target=produce);worker.start()
            try:s.close()
            finally:stopped.set();worker.join(1)
            self.assertLessEqual(s.machine.close_bytes['RX-01'],POLICY['close_bytes'])
            self.assertIn('incomplete_tail:RX-01',s.machine.connection_reasons)

    def test_second_open_failure_closes_first_without_reopening_and_records_failure(self):
        devices=[]
        class FailSecond(OwnedPty):
            def __init__(self,rx):
                if rx=='RX-02':raise OSError('synthetic second open failure')
                super().__init__(rx);devices.append(self)
        with self.assertRaisesRegex(OSError,'second open'):
            PtySession(self.out,plan(),endpoint_type=FailSecond)
        self.assertEqual(devices[0].close_attempts,1)
        state=audit_v4(self.out)['state']
        self.assertFalse(state['closed']['RX-02']['confirmed'])
        self.assertFalse(any(c['kind']=='both_ports_closed_confirmed' for c in state['signals']))

    def test_read_error_and_abort_in_manual_scope_close_both(self):
        with PtySession(self.out,plan()) as s:
            s.endpoints['RX-01'].fixture_write(b'input\n')
            with patch('presence_v4_pty.os.read',side_effect=OSError('synthetic read failure')):
                s.step()
            self.assertTrue(s.read_loop_stopped)
            self.assertTrue(s.machine.fatal.startswith('io_error'))
        self.assertTrue(audit_v4(self.out)['replay_ok'])

    def test_invalid_operator_request_leaves_auditable_journal(self):
        with PtySession(self.out,plan()) as s:
            with self.assertRaises(ValueError):s.command('request',slot_id='wrong')
            s.command('interrupt');s.step()
        self.assertTrue(audit_v4(self.out)['replay_ok'])

    def test_rehashed_forged_read_hash_or_close_receipt_is_rejected(self):
        with PtySession(self.out,plan()) as s:
            s.endpoints['RX-01'].fixture_write(b'original\n');s.step()
            s.command('interrupt');s.step()
        for filename in ('operations.jsonl','close-receipt.json'):
            with self.subTest(filename=filename):
                path=self.out/filename;original=path.read_bytes()
                manifest_path=self.out/'manifest.json';old_manifest=manifest_path.read_bytes()
                if filename=='operations.jsonl':
                    rows=[json.loads(line) for line in original.splitlines()]
                    next(r for r in rows if r['op']=='chunk')['data']['sha256']='0'*64
                    path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
                else:
                    v=json.loads(original);v['timer_is_close_proof']=True
                    path.write_text(json.dumps(v))
                manifest=json.loads(old_manifest)
                e=next(e for e in manifest['files'] if e['path']==filename)
                e.update(bytes=path.stat().st_size,sha256=digest(path));manifest_path.write_text(json.dumps(manifest))
                with self.assertRaises(ValueError):audit_v4(self.out)
                path.write_bytes(original);manifest_path.write_bytes(old_manifest)

    def test_storage_failure_still_attempts_both_closes_without_success_cue(self):
        s=PtySession(self.out,plan())
        try:
            with patch.object(s.journal.ops,'write',side_effect=OSError('disk failure')):
                with self.assertRaises(OSError):s.command('tick')
                with self.assertRaises(OSError):s.close()
            self.assertEqual({rx:e.close_attempts for rx,e in s.endpoints.items()},dict.fromkeys(RECEIVERS,1))
            self.assertFalse(s.receipt_persisted)
            self.assertFalse(any(c['kind']=='both_ports_closed_confirmed' and c['ack_ns'] is not None for c in s.machine.signals))
        finally:
            s.journal.close_files()
            for e in s.endpoints.values():e.dispose_fixture()

    def test_exception_in_operator_scope_closes_both_and_is_recorded(self):
        with self.assertRaises(KeyboardInterrupt):
            with PtySession(self.out,plan()) as s:raise KeyboardInterrupt()
        state=audit_v4(self.out)['state']
        self.assertEqual(state['fatal'],'interrupt')
        self.assertTrue(all(c['confirmed'] for c in state['closed'].values()))

    def test_existing_output_and_default_cli_cannot_open_hardware(self):
        self.out.mkdir()
        with self.assertRaises(FileExistsError):PtySession(self.out,plan())
        with patch('serial.Serial',side_effect=AssertionError('No UART')):
            result=subprocess.run([sys.executable,'-B',str(ROOT/'tools/campana_presencia_v4.py')],
                                  text=True,capture_output=True,check=True)
        self.assertFalse(json.loads(result.stdout)['physical_execution_enabled'])


class NotificationTests(unittest.TestCase):
    def test_patterns_are_distinct_valid_WAVs_without_claiming_audibility(self):
        with tempfile.TemporaryDirectory() as tmp:
            signatures=[]
            for kind in PATTERNS:
                p=Path(tmp)/(kind+'.wav');create_wav(p,kind)
                with wave.open(str(p),'rb') as w:
                    self.assertEqual((w.getnchannels(),w.getsampwidth(),w.getframerate()),(1,2,16000))
                    signatures.append(w.getnframes())
            self.assertEqual(len(set(signatures)),4)

    def test_audio_worker_does_not_block_caller_and_playback_failure_is_explicit(self):
        entered,release=threading.Event(),threading.Event()
        def player(*args,**kwargs):
            entered.set();release.wait(2)
            return subprocess.CompletedProcess(args[0],1)
        with tempfile.TemporaryDirectory() as tmp,patch('presence_v4_audio.subprocess.run',side_effect=player):
            n=LaptopNotifier(Path(tmp)/'audio',player='/synthetic/player')
            try:
                n.start(dict(id=0,kind='establish_condition'))
                self.assertTrue(entered.wait(1));self.assertEqual(n.poll(),[])
                release.set();deadline=time.monotonic()+1
                found=[]
                while not found and time.monotonic()<deadline:
                    found=n.poll();time.sleep(.001)
                self.assertEqual(found,[(0,False)])
            finally:
                release.set();n.finish()


if __name__=='__main__':unittest.main()
