"""Explicit selection, unchanged campaign semantics, metadata-only gates and PTY replay."""
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'tools')]
import campana_rx02_checkpoint as cli
from rx02_c03.contract import validate_plan,C03Presence
from rx02_c03.checkpoint import C03CheckpointSession,audit_c03_checkpoints
from presence_rx02 import Rx02Presence
from presence_rx02_uart import Rx02Session
from presence_rx02_journal import audit_rx02
from persistent_presence_v4 import POLICY
from test_presence_rx02 import Rig,boot,PREFIX,plan as old_plan
ROOT=Path(__file__).resolve().parents[1]


def plan():
    return json.loads((ROOT/'config/piloto_rx02_C03_checkpoint2.integrated.review.json').read_text())


def current_plan():
    p=plan();p.update(execution_mode='physical_after_approval',review_only=False,
        actor='Synthetic declared operator',mounting_reference='Synthetic fixture, no physical mount verified')
    p['environment']={k:'Synthetic declaration' for k in p['environment']}
    p['unused_receiver']['operator_confirmation']='confirmed_current'
    return p


def plan_file(folder,p):
    path=Path(folder)/'plan.json';path.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n')
    return path


def complete(rig):
    p=plan();rig.pair.fixture_write(PREFIX+boot('RX-02'))
    with C03CheckpointSession(rig.output,p,test_backend=rig.backend,clock=rig.clock) as s:
        s.step()
        for _ in range(1400):
            rig.step(s);m=s.machine
            if m.fatal:raise AssertionError(m.fatal)
            if m.initial_available is not None:
                if m.windows:
                    w=m.windows[-1]
                    if w['end_signal'] is not None and m.signals[w['end_signal']]['ack_ns'] is not None and w['label']['status']=='pending':
                        cli.historical.operator_command(s,['declare',w['id'],'yes'])
                if not m.close_requested and len(m.windows)<2 and (not m.windows or m.windows[-1]['label']['status']=='declared'):
                    words=['slot',p['slots'][len(m.windows)]['id']]
                    if len(m.windows)==1:words.append('last')
                    cli.historical.operator_command(s,words)
            if s.read_loop_stopped:break
        else:raise AssertionError('No bounded fixture completion')
    return audit_c03_checkpoints(rig.output)


class IntegrationTests(unittest.TestCase):
    def rig(self):
        rig=Rig();self.addCleanup(rig.dispose);return rig

    def test_historical_path_is_exact_default_and_unknown_revision_cannot_fallback(self):
        self.assertEqual(cli.select_path(old_plan()),(Rx02Session,audit_rx02))
        for change in (dict(persistence_revision='unknown'),dict(persistence_revision=None),dict(integration_revision='orphan')):
            with self.subTest(change=change),self.assertRaises(ValueError):cli.select_path(dict(old_plan(),**change))

    def test_new_cli_delegates_unselected_historical_preparation_without_discovery(self):
        with patch('serial.Serial',side_effect=AssertionError('No UART')),patch('presence_rx02_uart.identity',side_effect=AssertionError('No metadata')),contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(cli.main(['--plan',str(ROOT/'config/piloto_rx02_r1_C01.review.json')]),0)
        self.assertEqual(json.loads(out.getvalue())['plan']['connection_id'],'RX02-C01')

    def test_explicit_opt_in_preserves_C03_order_partition_and_every_policy(self):
        p=plan();validate_plan(p)
        self.assertEqual(p['policy'],POLICY)
        self.assertEqual([s['condition'] for s in p['slots']],['E','S'])
        for change in (dict(connection_id='RX02-C02'),dict(partition_group='replacement'),dict(future_partition='evaluation_future_sealed'),
            dict(slots=list(reversed(p['slots']))),dict(policy=dict(POLICY,freshness_ns=2_000_000_000)),dict(integration_revision=''),dict(persistence_revision='legacy')):
            with self.subTest(change=change),self.assertRaises(ValueError):validate_plan(dict(p,**change))
        for name in ('apply','summary','validate_request','close_ack','selected_closed'):
            self.assertIs(getattr(C03Presence,name),getattr(Rx02Presence,name))

    def test_prepare_does_not_query_metadata_or_construct_UART(self):
        with patch.object(cli,'preflight_rx02',side_effect=AssertionError('No metadata')),patch.object(C03CheckpointSession,'__init__',side_effect=AssertionError('No session')),contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(cli.main(['--plan',str(ROOT/'config/piloto_rx02_C03_checkpoint2.integrated.review.json')]),0)
        result=json.loads(out.getvalue());self.assertEqual(result['session_class'],'C03CheckpointSession')
        self.assertEqual(result['auditor'],'audit_c03_checkpoints')
        self.assertFalse(result['physical_UART_opened'])

    def test_missing_current_declarations_blocks_preflight_and_capture(self):
        for flag in ('--preflight-only','--execute-after-approval'):
            with patch.object(cli,'preflight_rx02',side_effect=AssertionError('No metadata')),self.assertRaises(ValueError):
                cli.main(['--plan',str(ROOT/'config/piloto_rx02_C03_checkpoint2.integrated.review.json'),flag])

    def test_current_conditions_are_not_grant_and_old_authorization_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=plan_file(tmp,current_plan())
            with patch.object(cli,'preflight_rx02',side_effect=AssertionError('No metadata')),patch.object(C03CheckpointSession,'__init__',side_effect=AssertionError('No UART')),self.assertRaisesRegex(ValueError,'New explicit C03'):
                cli.main(['--plan',str(path),'--execute-after-approval','--authorization-reference','RX02-DIAG-CP-R1:old'])
        with patch('rx02_c03.uart.identity',side_effect=AssertionError('No metadata')),self.assertRaisesRegex(ValueError,'New explicit single C03'):
            C03CheckpointSession(cli.OUTPUT,current_plan(),authorization_reference='OLD-C02')

    def test_preflight_queries_only_RX02_metadata_and_preserves_exclusive_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=plan_file(tmp,current_plan());receipt=Path(tmp)/'preflight.json'
            snapshot=dict(by_id=plan()['ports']['RX-02'],serial='5C93200689')
            with patch.object(cli,'PREFLIGHT',receipt),patch('rx02_c03.uart.identity',return_value=snapshot) as meta,patch('serial.Serial',side_effect=AssertionError('No UART')),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main(['--plan',str(path),'--preflight-only']),0)
                meta.assert_called_once_with('RX-02')
                data=json.loads(receipt.read_text());self.assertFalse(data['physical_UART_opened'])
                self.assertEqual(data['sources'],cli.source_hashes())
                with self.assertRaisesRegex(ValueError,'already recorded'):cli.main(['--plan',str(path),'--preflight-only'])

    def test_preflight_conditions_bind_everything_except_new_grant_fields(self):
        p=current_plan();original=cli.condition_hash(p)
        p.update(authorization_granted=True,review_state='authorized_single_attempt')
        self.assertEqual(original,cli.condition_hash(p))
        p['environment']['movement']='different'
        self.assertNotEqual(original,cli.condition_hash(p))

    def test_stale_sources_or_changed_conditions_block_before_metadata_or_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=current_plan();p.update(authorization_granted=True,review_state='authorized_single_attempt');path=plan_file(tmp,p)
            receipt=Path(tmp)/'preflight.json';output=Path(tmp)/'new-output'
            evidence=dict(state='PREFLIGHT_METADATA_ONLY',physical_UART_opened=False,
                persistence_revision=p['persistence_revision'],integration_revision=p['integration_revision'],
                conditions_sha256=cli.condition_hash(p),sources={'stale':'hash'})
            receipt.write_text(json.dumps(evidence))
            ref='RX02-C03-CHECKPOINT-R1:'+cli.digest(path)
            with patch.object(cli,'PREFLIGHT',receipt),patch.object(cli,'OUTPUT',output),patch.object(cli,'preflight_rx02',side_effect=AssertionError('No metadata')),self.assertRaisesRegex(ValueError,'sources changed'):
                cli.main(['--plan',str(path),'--execute-after-approval','--authorization-reference',ref,'--output-new',str(output)])

    def test_exclusive_output_existing_blocks_even_valid_grant(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=current_plan();p.update(authorization_granted=True,review_state='authorized_single_attempt');path=plan_file(tmp,p)
            output=Path(tmp)/'existing';output.mkdir()
            with patch.object(cli,'OUTPUT',output),patch.object(cli,'preflight_rx02',side_effect=AssertionError('No metadata')),self.assertRaisesRegex(ValueError,'Fixed new C03 output'):
                cli.main(['--plan',str(path),'--execute-after-approval','--authorization-reference','RX02-C03-CHECKPOINT-R1:'+cli.digest(path),'--output-new',str(output)])

    def test_two_ES_windows_replay_provenance_persistence_and_close(self):
        rig=self.rig();report=complete(rig)
        self.assertTrue(report['integrity_ok'] and report['replay_ok'])
        self.assertTrue(all(w['eligible'] for w in report['exploratory_eligibility']['windows']))
        self.assertFalse(report['state']['connection']['quality_ok'])
        self.assertEqual([w['condition'] for w in report['state']['windows']],['E','S'])
        self.assertEqual(report['state']['future_partition'],'development_future')
        self.assertEqual(report['state']['unused_receiver']['action'],'remain_disconnected_uart_unopened')
        self.assertEqual(report['persistence_status']['pending_ops_bytes'],0)
        self.assertTrue(report['state']['closed']['RX-02']['confirmed'])
        self.assertFalse((rig.output/'rx-01.serial.log').exists())
        provenance=json.loads((rig.output/'provenance.json').read_text())
        self.assertEqual(provenance['persistence_revision'],plan()['persistence_revision'])
        self.assertEqual(provenance['integration_revision'],plan()['integration_revision'])
        self.assertEqual(len(provenance['sources']),25)
        self.assertIn('tools/campana_rx02_checkpoint.py',{e['path'] for e in provenance['sources']})
        with self.assertRaises(ValueError):audit_rx02(rig.output)

    def test_raw_sync_precedes_reducer_and_tick_defers_operations_sync(self):
        rig=self.rig();s=C03CheckpointSession(rig.output,plan(),test_backend=rig.backend,clock=rig.clock)
        raw=s.journal.raw['RX-02'].fileno();ops=s.journal.ops.fileno();calls=[];sync=os.fsync;apply=s.machine.apply
        def flush(fd):calls.append(('sync',fd));return sync(fd)
        def reduce(op,now_ns,**data):calls.append(('apply',op));return apply(op,now_ns,**data)
        with patch('os.fsync',side_effect=flush),patch.object(s.machine,'apply',side_effect=reduce):
            s.command('chunk',receiver='RX-02',chunk=boot('RX-02'),started_ns=0,returned_ns=0);s.command('tick')
        self.assertLess(calls.index(('sync',raw)),calls.index(('apply','chunk')))
        self.assertNotIn(('sync',ops),calls)
        s.close();s.finalize()
        self.assertTrue(audit_c03_checkpoints(rig.output)['replay_ok'])

    def test_ops_sync_failure_releases_resource_without_success_receipt(self):
        rig=self.rig();s=C03CheckpointSession(rig.output,plan(),test_backend=rig.backend,clock=rig.clock)
        ops=s.journal.ops.fileno();sync=os.fsync
        def fail(fd):
            if fd==ops:raise OSError('injected fsync failure')
            return sync(fd)
        with patch('os.fsync',side_effect=fail):
            with self.assertRaises(OSError):s.command('close_request')
            s.close()
        self.assertTrue(s.read_loop_stopped and s.machine.selected_closed())
        self.assertFalse(s.receipt_persisted)
        with self.assertRaises(RuntimeError):s.finalize()
        s.journal.close_files();s._finish_notifier()
        self.assertFalse((rig.output/'manifest.json').exists())

    def test_watchdog_still_fails_without_rearm_and_closes(self):
        rig=self.rig();rig.pair.fixture_write(boot('RX-02'))
        with C03CheckpointSession(rig.output,plan(),test_backend=rig.backend,clock=rig.clock) as s:
            s.step()
            for _ in range(4):rig.step(s)
            self.assertIsNotNone(s.machine.initial_available)
            rig.clock.advance(1_000_000_001);s.step()
            self.assertTrue(s.read_loop_stopped)
        report=audit_c03_checkpoints(rig.output)
        self.assertIn(report['state']['fatal'],('availability_lost:RX-02','availability_gap:RX-02'))

    def test_rehashed_false_provenance_and_durability_cannot_downgrade_audit(self):
        import shutil
        rig=self.rig();complete(rig)
        for name,key,value in [('provenance.json','persistence_revision','legacy'),('checkpoint-status.json','pending_ops_bytes',1)]:
            with tempfile.TemporaryDirectory() as tmp:
                copy=Path(tmp)/'copy';shutil.copytree(rig.output,copy)
                path=copy/name;data=json.loads(path.read_text());data[key]=value;path.write_text(json.dumps(data))
                manifest=json.loads((copy/'manifest.json').read_text())
                for entry in manifest['files']:
                    if entry['path']==name:entry.update(bytes=path.stat().st_size,sha256=cli.digest(path))
                (copy/'manifest.json').write_text(json.dumps(manifest))
                with self.assertRaises(ValueError):audit_c03_checkpoints(copy)
