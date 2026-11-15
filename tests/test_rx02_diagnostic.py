"""Offline diagnostic gates, independent identity, transport and replay."""
import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_presence_rx02 import Rig,boot,fixture_row
from rx02_diagnostic.contract import validate_plan
from rx02_diagnostic.checkpoint import CheckpointRx02Session,audit_checkpoint_rx02
from presence_rx02 import validate_plan as historical_validate
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import diagnostico_checkpoints_rx02 as cli

ROOT=Path(__file__).resolve().parents[1]


def plan():
    return json.loads((ROOT/'config/diagnostico_checkpoints_rx02_r1.review.json').read_text())


def current_plan():
    p=plan();p.update(execution_mode='physical_after_approval',actor='Synthetic operator declaration',
        mounting_reference='Synthetic fixture only')
    p['environment']={k:'Synthetic declared condition' for k in p['environment']}
    p['unused_receiver']['operator_confirmation']='confirmed_current'
    return p


class DiagnosticTests(unittest.TestCase):
    def test_separate_identity_partition_slots_and_unchanged_thresholds(self):
        p=plan();validate_plan(p)
        with self.assertRaises(ValueError):historical_validate(p)
        for change in (dict(connection_id='RX02-C02'),dict(future_partition='development_future'),
            dict(slots=[dict(id='E',condition='E')]),dict(duration_ns=241_000_000_000),
            dict(policy=dict(p['policy'],freshness_ns=2_000_000_000)),
            dict(permitted_uses=dict(calibration=True,training=False,production=False)),
            dict(persistence_revision='legacy')):
            with self.subTest(change=change),self.assertRaises(ValueError):validate_plan(dict(p,**change))

    def test_prepare_cannot_discover_or_construct_uart(self):
        with patch.object(cli,'preflight_rx02',side_effect=AssertionError('No metadata')) as meta, \
             patch('serial.Serial',side_effect=AssertionError('No UART')), \
             contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(cli.main(['--plan',str(ROOT/'config/diagnostico_checkpoints_rx02_r1.review.json')]),0)
        self.assertFalse(meta.called)
        self.assertEqual(json.loads(out.getvalue())['state'],'PREPARED_NOT_AUTHORIZED')

    def test_incomplete_declarations_block_preflight_and_acquisition(self):
        for flag in ('--preflight-only','--execute-after-approval'):
            with patch.object(cli,'preflight_rx02',side_effect=AssertionError('No metadata')), \
                 patch.object(cli,'CheckpointRx02Session',side_effect=AssertionError('No session')):
                with self.assertRaises(ValueError):
                    cli.main(['--plan',str(ROOT/'config/diagnostico_checkpoints_rx02_r1.review.json'),flag])

    def test_complete_declarations_without_grant_still_cannot_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'plan.json';path.write_text(json.dumps(current_plan()))
            with patch.object(cli,'preflight_rx02',side_effect=AssertionError('No metadata')), \
                 patch.object(cli,'CheckpointRx02Session',side_effect=AssertionError('No UART')):
                with self.assertRaisesRegex(ValueError,'explicit grant'):
                    cli.main(['--plan',str(path),'--execute-after-approval',
                              '--authorization-reference','RX02-C02-old-consumed-reference'])

    def test_metadata_preflight_never_constructs_session_and_cannot_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'plan.json';path.write_text(json.dumps(current_plan()))
            receipt=Path(tmp)/'preflight.json'
            with patch.object(cli,'PREFLIGHT',receipt),patch.object(cli,'preflight_rx02',return_value={'RX-02':{'serial':'fixture'}}), \
                 patch.object(cli,'CheckpointRx02Session',side_effect=AssertionError('No UART')), \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main(['--plan',str(path),'--preflight-only']),0)
                self.assertFalse(json.loads(receipt.read_text())['physical_UART_opened'])
                with self.assertRaisesRegex(ValueError,'already exists'):
                    cli.main(['--plan',str(path),'--preflight-only'])

    def test_preflight_binds_conditions_but_not_later_grant(self):
        p=current_plan();h=cli.condition_hash(p)
        p.update(authorization_granted=True,review_state='authorized_single_attempt')
        self.assertEqual(h,cli.condition_hash(p))
        p['environment']['occupancy']='changed'
        self.assertNotEqual(h,cli.condition_hash(p))

    def test_sustained_synthetic_connection_checkpoint_replay_and_close(self):
        rig=Rig();self.addCleanup(rig.dispose)
        rig.pair.fixture_write(boot('RX-02'))
        with CheckpointRx02Session(rig.output,plan(),test_backend=rig.backend,clock=rig.clock) as s:
            s.step()
            ident=0;step=s.step
            def next_step():
                nonlocal ident
                rig.clock.advance(200_000_000)
                rig.pair.fixture_write(fixture_row(ident,100000+ident*200000));ident+=1
                step()
                if s.machine.fatal:raise AssertionError(s.machine.fatal)
            with patch.object(s,'step',side_effect=next_step),patch.object(cli.time,'sleep'):
                cli.serve(s)
            self.assertTrue(s.receipt_persisted)
        report=cli.diagnostic_report(rig.output)
        self.assertTrue(report['integrity_ok'] and report['replay_ok'])
        self.assertTrue(report['diagnostic']['diagnostic_ok'])
        self.assertFalse(report['diagnostic']['windows_requested'])
        self.assertEqual(report['state']['windows'],[])
        self.assertEqual(report['persistence_status']['pending_ops_bytes'],0)
        self.assertGreater(report['persistence_status']['checkpoints'],0)
        self.assertFalse(any(report['diagnostic']['permitted_uses'].values()))
        self.assertFalse((rig.output/'rx-01.serial.log').exists())

    def test_missing_ready_and_early_close_cannot_pass_sustained_diagnostic(self):
        rig=Rig();self.addCleanup(rig.dispose)
        with CheckpointRx02Session(rig.output,plan(),test_backend=rig.backend,clock=rig.clock) as s:
            s.command('close_request');s.close()
        report=cli.diagnostic_report(rig.output)
        self.assertTrue(report['replay_ok'])
        self.assertFalse(report['diagnostic']['diagnostic_ok'])
        self.assertTrue(report['diagnostic']['close_ok'])

    def test_original_watchdog_still_suspends_and_closes(self):
        rig=Rig();self.addCleanup(rig.dispose)
        rig.pair.fixture_write(boot('RX-02'))
        with CheckpointRx02Session(rig.output,plan(),test_backend=rig.backend,clock=rig.clock) as s:
            s.step()
            for ident in range(4):
                rig.clock.advance(200_000_000)
                rig.pair.fixture_write(fixture_row(ident,100000+ident*200000));s.step()
            self.assertIsNotNone(s.machine.initial_available)
            rig.clock.advance(1_000_000_001);s.step()
            self.assertTrue(s.read_loop_stopped)
        report=cli.diagnostic_report(rig.output)
        self.assertIn(report['state']['fatal'],('availability_lost:RX-02','availability_gap:RX-02'))
        self.assertFalse(report['diagnostic']['diagnostic_ok'])
        self.assertTrue(report['diagnostic']['close_ok'])

    def test_tampered_raw_cannot_pass_diagnostic_audit(self):
        rig=Rig();self.addCleanup(rig.dispose)
        with CheckpointRx02Session(rig.output,plan(),test_backend=rig.backend,clock=rig.clock) as s:s.close()
        with (rig.output/'rx-02.serial.log').open('ab') as f:f.write(b'x')
        with self.assertRaises(ValueError):audit_checkpoint_rx02(rig.output)

    def test_operations_sync_failure_closes_without_success_manifest(self):
        import os
        rig=Rig();self.addCleanup(rig.dispose)
        s=CheckpointRx02Session(rig.output,plan(),test_backend=rig.backend,clock=rig.clock)
        fd=s.journal.ops.fileno();sync=os.fsync
        def fail(target):
            if target==fd:raise OSError('synthetic fsync failure')
            return sync(target)
        with patch('os.fsync',side_effect=fail):
            with self.assertRaises(OSError):s.command('close_request')
            s.close()
        self.assertTrue(s.read_loop_stopped and s.machine.selected_closed())
        self.assertFalse(s.receipt_persisted)
        with self.assertRaises(RuntimeError):s.finalize()
        s.journal.close_files();s._finish_notifier()
        self.assertFalse((rig.output/'manifest.json').exists())
