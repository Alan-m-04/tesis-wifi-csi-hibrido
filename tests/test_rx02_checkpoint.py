"""Checkpoint durability, finite history, errors and unchanged reducer semantics."""
import copy
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from test_presence_rx02 import Rig,plan,boot,fixture_row
from presence_rx02_journal import audit_rx02
from rx02_checkpoint_journal import CheckpointRx02Session,PERSISTENCE_REVISION,LIMITS,audit_checkpoint_rx02
from rx02_service_lab import synthetic_row,SIZES
from capture_csi_multi import validate_sample


class CheckpointRig(Rig):
    def session(self,**kwargs):
        p=plan();p['persistence_revision']=PERSISTENCE_REVISION
        return CheckpointRx02Session(self.output,p,test_backend=self.backend,clock=self.clock,**kwargs)


class CheckpointTests(unittest.TestCase):
    def rig(self):
        rig=CheckpointRig();self.addCleanup(rig.dispose);return rig

    def test_explicit_opt_in_before_constructing_transport(self):
        rig=self.rig()
        with self.assertRaisesRegex(ValueError,'Explicit persistence'):
            CheckpointRx02Session(rig.output,plan(),test_backend=rig.backend,clock=rig.clock)
        self.assertFalse(rig.calls)

    def test_raw_durable_before_reducer_and_tick_only_deferred(self):
        rig=self.rig();session=rig.session();self.addCleanup(session.journal.close_files)
        rawfd=session.journal.raw['RX-02'].fileno();opsfd=session.journal.ops.fileno()
        calls=[];actual=os.fsync;apply=session.machine.apply
        def sync(fd):calls.append(('sync',fd));return actual(fd)
        def reduce(op,now,**data):calls.append(('apply',op));return apply(op,now,**data)
        with patch('os.fsync',side_effect=sync),patch.object(session.machine,'apply',side_effect=reduce):
            session.command('chunk',receiver='RX-02',chunk=boot('RX-02'),started_ns=0,returned_ns=0)
            session.command('tick')
        self.assertLess(calls.index(('sync',rawfd)),calls.index(('apply','chunk')))
        self.assertNotIn(('sync',opsfd),calls)
        self.assertGreater(session.journal.pending_ops_bytes,0)
        session.close();session.finalize()
        self.assertEqual(session.journal.pending_ops_bytes,0)
        self.assertTrue(audit_checkpoint_rx02(rig.output)['replay_ok'])

    def test_byte_checkpoint_and_control_barrier_bound_pending_suffix(self):
        rig=self.rig()
        with rig.session() as session:
            for _ in range(1500):session.command('tick')
            self.assertGreater(session.journal.checkpoints,0)
            self.assertLessEqual(session.journal.max_pending_ops_bytes,LIMITS['pending_ops_bytes'])
            session.command('close_request')
            self.assertEqual(session.journal.pending_ops_bytes,0)
        self.assertTrue(audit_checkpoint_rx02(rig.output)['replay_ok'])

    def test_two_windows_same_coverage_labels_and_close_as_legacy_reducer(self):
        rig=self.rig();rig.complete();report=audit_checkpoint_rx02(rig.output)
        self.assertTrue(report['integrity_ok'] and report['replay_ok'])
        self.assertTrue(all(w['eligible'] for w in report['exploratory_eligibility']['windows']))
        self.assertEqual([w['condition'] for w in report['state']['windows']],['E','S'])
        self.assertTrue(report['state']['closed']['RX-02']['confirmed'])
        self.assertFalse(report['state']['connection']['quality_ok'])
        self.assertFalse(any(report['exploratory_eligibility']['permitted_uses'].values()))

    def test_ops_sync_failure_prevents_receipt_and_success_cue_but_closes(self):
        rig=self.rig();session=rig.session();opsfd=session.journal.ops.fileno();sync=os.fsync
        def fail(fd):
            if fd==opsfd:raise OSError('injected operations fsync failure')
            return sync(fd)
        with patch('os.fsync',side_effect=fail):
            with self.assertRaises(OSError):session.command('close_request')
            session.close()
        self.assertTrue(session.read_loop_stopped)
        self.assertTrue(session.machine.selected_closed())
        self.assertFalse(session.receipt_persisted)
        self.assertTrue(session.storage_failed)
        with self.assertRaises(RuntimeError):session.finalize()
        session.journal.close_files();session._finish_notifier()
        self.assertFalse((rig.output/'manifest.json').exists())
        self.assertEqual(sum(c[0]=='close' and c[1] for c in rig.calls),1)

    def test_raw_sync_failure_never_runs_chunk_reducer(self):
        rig=self.rig();session=rig.session();fd=session.journal.raw['RX-02'].fileno();sync=os.fsync
        def fail(target):
            if target==fd:raise OSError('injected raw fsync failure')
            return sync(target)
        with patch('os.fsync',side_effect=fail):
            with self.assertRaises(OSError):
                session.command('chunk',receiver='RX-02',chunk=b'kept raw bytes',started_ns=0,returned_ns=0)
        self.assertFalse(session.machine.states['RX-02']['lines'])
        self.assertTrue(session.storage_failed)
        session.close();session.journal.close_files();session._finish_notifier()
        self.assertEqual((rig.output/'rx-02.serial.log').read_bytes(),b'kept raw bytes')
        self.assertFalse((rig.output/'manifest.json').exists())

    def test_short_operations_write_detected(self):
        rig=self.rig();session=rig.session()
        with patch.object(session.journal.ops,'write',return_value=0):
            with self.assertRaisesRegex(OSError,'Short operations'):session.command('tick')
        session.close();session.journal.close_files();session._finish_notifier()
        self.assertTrue(session.storage_failed)

    def test_memory_limit_preserves_entire_chunk_and_stops_without_manifest(self):
        rig=self.rig();session=rig.session();payload=boot('RX-02')
        with patch.dict(LIMITS,max_lines=1):
            with self.assertRaisesRegex(OSError,'resource limit'):
                session.command('chunk',receiver='RX-02',chunk=payload,started_ns=0,returned_ns=0)
            session.close()
        session.journal.close_files();session._finish_notifier()
        self.assertEqual((rig.output/'rx-02.serial.log').read_bytes(),payload)
        note=json.loads((rig.output/'resource-limit.json').read_text())
        self.assertEqual(note['unprocessed_raw_reference']['sha256'],hashlib.sha256(payload).hexdigest())
        self.assertFalse((rig.output/'manifest.json').exists())

    def test_invalid_operator_request_is_recoverable_before_any_append(self):
        rig=self.rig()
        with rig.session() as session:
            seq=session.journal.seq
            with self.assertRaises(ValueError):session.command('request',slot_id='unknown')
            self.assertEqual(session.journal.seq,seq)
            self.assertFalse(session.journal.failed)

    def test_serialization_failure_stops_and_closes_without_manifest(self):
        rig=self.rig();session=rig.session();dumps=json.dumps
        def fail(value,*args,**kwargs):
            if isinstance(value,dict) and value.get('op')=='tick':raise ValueError('injected serialization error')
            return dumps(value,*args,**kwargs)
        with patch('json.dumps',new=fail):
            with self.assertRaises(ValueError):session.command('tick')
        self.assertTrue(session.journal.failed)
        session.close();session.journal.close_files();session._finish_notifier()
        self.assertTrue(session.machine.selected_closed())
        self.assertTrue(session.storage_failed)
        self.assertFalse((rig.output/'manifest.json').exists())

    def test_keyboard_interrupt_in_checkpoint_cannot_leave_a_success_receipt(self):
        rig=self.rig();session=rig.session();fd=session.journal.ops.fileno();sync=os.fsync
        def interrupt(target):
            if target==fd:raise KeyboardInterrupt('injected during checkpoint')
            return sync(target)
        with patch('os.fsync',new=interrupt):
            with self.assertRaises(KeyboardInterrupt):session.command('close_request')
        session.close();session.journal.close_files();session._finish_notifier()
        self.assertTrue(session.machine.selected_closed())
        self.assertFalse(session.receipt_persisted)
        self.assertFalse((rig.output/'manifest.json').exists())

    def test_rehashed_false_durability_status_cannot_pass_revision_audit(self):
        rig=self.rig()
        with rig.session() as session:session.command('tick')
        status=json.loads((rig.output/'checkpoint-status.json').read_text())
        status['last_durable_seq']-=1
        (rig.output/'checkpoint-status.json').write_text(json.dumps(status))
        manifest=json.loads((rig.output/'manifest.json').read_text())
        for entry in manifest['files']:
            if entry['path']=='checkpoint-status.json':
                data=(rig.output/entry['path']).read_bytes()
                entry.update(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
        (rig.output/'manifest.json').write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError,'durability/resource'):audit_checkpoint_rx02(rig.output)

    def test_receipt_failure_never_announces_confirmed_close(self):
        rig=self.rig();session=rig.session()
        with patch.object(session.journal.original,'receipt',side_effect=OSError('injected receipt failure')):
            with self.assertRaises(OSError):session.close()
        self.assertTrue(session.machine.selected_closed())
        self.assertFalse(session.receipt_persisted)
        self.assertFalse(session.started_signals)
        session.journal.close_files();session._finish_notifier()

    def test_same_history_under_unchanged_original_auditor(self):
        rig=self.rig();rig.complete()
        old=audit_rx02(rig.output);new=audit_checkpoint_rx02(rig.output)
        self.assertEqual(old['state'],new['state'])
        self.assertEqual(old['exploratory_eligibility'],new['exploratory_eligibility'])

    def test_synthetic_lengths_and_cadence_envelope_without_measured_IQ(self):
        for ident in (0,9,99,999,2999):
            for size in SIZES:
                row=synthetic_row(ident,size)
                self.assertEqual(len(row),size)
                _,_,numeric=validate_sample(row.decode().strip())
                self.assertEqual(numeric['local_timestamp'],100000+ident*200000)
                self.assertEqual(numeric['len'],256)

    def test_process_kill_preserves_partial_evidence_without_manifest(self):
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp:
            code='''import pathlib,sys,time
sys.path[:0]=['src','tests']
from test_rx02_checkpoint import CheckpointRig
r=CheckpointRig();s=r.session()
s.command('tick')
pathlib.Path(sys.argv[1]).write_text(str(r.output))
time.sleep(30)
'''
            marker=Path(temp)/'ready'
            child=subprocess.Popen([sys.executable,'-B','-c',code,str(marker)],cwd=root)
            try:
                deadline=time.monotonic()+5
                while not marker.exists() and child.poll() is None and time.monotonic()<deadline:time.sleep(.01)
                self.assertTrue(marker.exists())
                bundle=Path(marker.read_text())
                os.kill(child.pid,signal.SIGKILL);child.wait(timeout=5)
                self.assertTrue((bundle/'operations.jsonl').exists())
                self.assertFalse((bundle/'manifest.json').exists())
                with self.assertRaises((OSError,ValueError)):audit_checkpoint_rx02(bundle)
            finally:
                if child.poll() is None:child.kill();child.wait()
                if marker.exists():
                    import shutil
                    shutil.rmtree(Path(marker.read_text()).parent,ignore_errors=True)

    def test_kill_between_raw_sync_and_operation_keeps_unreferenced_raw_rejected(self):
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp:
            code='''import hashlib,json,os,pathlib,sys,time
sys.path[:0]=['src','tests']
from test_rx02_checkpoint import CheckpointRig,boot
r=CheckpointRig();s=r.session();rawfd=s.journal.raw['RX-02'].fileno();actual=os.fsync
payload=boot('RX-02')
def sync(fd):
 actual(fd)
 if fd==rawfd:
  pathlib.Path(sys.argv[1]).write_text(json.dumps(dict(bundle=str(r.output),sha256=hashlib.sha256(payload).hexdigest())))
  time.sleep(30)
os.fsync=sync
s.command('chunk',receiver='RX-02',chunk=payload,started_ns=0,returned_ns=0)
'''
            marker=Path(temp)/'ready'
            child=subprocess.Popen([sys.executable,'-B','-c',code,str(marker)],cwd=root)
            try:
                deadline=time.monotonic()+5
                while not marker.exists() and child.poll() is None and time.monotonic()<deadline:time.sleep(.01)
                self.assertTrue(marker.exists())
                note=json.loads(marker.read_text());bundle=Path(note['bundle'])
                os.kill(child.pid,signal.SIGKILL);child.wait(timeout=5)
                self.assertEqual(hashlib.sha256((bundle/'rx-02.serial.log').read_bytes()).hexdigest(),note['sha256'])
                operations=[json.loads(line) for line in (bundle/'operations.jsonl').read_text().splitlines()]
                self.assertFalse(any(o['op']=='chunk' for o in operations))
                self.assertFalse((bundle/'manifest.json').exists())
                with self.assertRaises((OSError,ValueError)):audit_checkpoint_rx02(bundle)
            finally:
                if child.poll() is None:child.kill();child.wait()
                if marker.exists():
                    import shutil
                    shutil.rmtree(Path(json.loads(marker.read_text())['bundle']).parent,ignore_errors=True)
