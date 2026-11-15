"""Exclusividad R3-N01, grants nuevos y adquisición/replay sobre PTY propio."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tools')]
import ejecutar_devrep_r3_n01 as cli
from rx02_devrep_r3_n01.contract import runtime_plan, validate_plan, prepared_plan, SCHEDULE
from rx02_devrep_r3_n01.session import DevrepSession, audit_devrep
from rx02_devrep_r3_n01.series import validate_entry
from rx02_devrep.coordinator import Coordinator
from rx02_devrep.contract import SCHEDULE as R1_SCHEDULE
from test_presence_rx02 import Rig, boot, PREFIX, fixture_row


class EntryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='synthetic-r3-entry-', dir=ROOT / 'results/local')
        self.addCleanup(self.tmp.cleanup)
        directory = Path(self.tmp.name)
        self.addCleanup(patch.stopall)
        patch.object(cli.prep, 'PREPARATION', directory).start()
        patch.object(cli.prep, 'boot_id', return_value='synthetic-r3-boot').start()
        patch.object(cli, 'PLAN', directory / 'plan.json').start()
        patch.object(cli, 'RECEIPT', directory / 'receipt.json').start()
        declaration = directory / 'synthetic-declaration.json'
        declaration.write_text('{"evidence_type":"synthetic_fixture_only"}\n')
        plan = cli.prep.template()
        plan.update(actor='Synthetic R3 operator',
            environment={key: 'Synthetic current condition' for key in plan['environment']},
            mounting_reference=str(declaration), setup_snapshot_path=str(declaration),
            setup_snapshot_sha256=cli.digest(declaration))
        plan['unused_receiver']['operator_confirmation'] = 'confirmed_current'
        plan['conditions_confirmation'] = dict(confirmed_current=True, host_boot_id='synthetic-r3-boot',
            declaration_path=str(declaration), declaration_sha256=cli.digest(declaration))
        cli.PLAN.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n')
        metadata = dict(identities={'RX-02': dict(by_id=cli.prep.PORTS['RX-02'],
            serial='5C93200689', vid='1a86', pid='55d3', bus='usb',
            node_fingerprint=[1, 2, 3])}, enumerated_tty_metadata=[])
        comparison = dict(revision=cli.prep.METADATA_COMPARISON_REVISION,
            raw_equal=True, equal_under_revision=True)
        receipt = dict(schema='devrep-r3-preparation-metadata-1', state='PREFLIGHT_METADATA_ONLY',
            connection_id=cli.prep.CONNECTION_ID, series_id=cli.prep.SERIES_ID,
            plan_sha256=cli.digest(cli.PLAN), sources=cli.base_sources(),
            physical_UART_opened=False, capture_executed=False, authorization_granted=False,
            acquisition_executor_enabled=False, conditions_confirmed_current=True,
            host_boot_id='synthetic-r3-boot', metadata=metadata,
            metadata_snapshots=dict(first=metadata, second=metadata), metadata_comparison=comparison,
            free_bytes=200*1024**2, evidence_type='synthetic_fixture_only')
        sidecar = dict(state='SNAPSHOTS_ONLY_NOT_APPROVAL',
            connection_id=cli.prep.CONNECTION_ID, plan_sha256=receipt['plan_sha256'],
            host_boot_id=receipt['host_boot_id'], sources=receipt['sources'],
            first=metadata, second=metadata, metadata_comparison=comparison)
        cli.RECEIPT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
        cli.RECEIPT.with_suffix('.snapshots.json').write_text(
            json.dumps(sidecar, ensure_ascii=False, indent=2) + '\n')

    def entry_fixture(self):
        prepared = json.loads((ROOT / cli.PLAN).read_text())
        receipt = json.loads((ROOT / cli.RECEIPT).read_text())
        sidecar = json.loads((ROOT / cli.RECEIPT).with_suffix('.snapshots.json').read_text())
        request = cli.make_request()
        request_hash = cli.serialized_hash(request)
        authorization = dict(schema='r3-n01-new-human-authorization-1', connection_id=cli.prep.CONNECTION_ID,
            request_sha256=request_hash, authorization_granted=True, ready_risk_reviewed=True,
            max_attempts=1, retry_allowed=False, operator_terminal_only=True,
            user_statement='Synthetic fixture only: no persisted authorization or physical access')
        entry = dict(request=request, request_sha256=request_hash, authorization=authorization,
                     receipt=receipt, sidecar=sidecar, prepared_plan=prepared,
                     identities=receipt['metadata']['identities'])
        return runtime_plan(prepared), entry

    def test_receipt_matches_current_sources_without_metadata_or_UART(self):
        with patch.object(cli.prep, 'metadata_snapshot', side_effect=AssertionError('No physical metadata')), \
             patch('serial.Serial', side_effect=AssertionError('No physical UART')):
            request = cli.make_request()
        self.assertEqual(request['connection_id'], 'RX02-DEVREP-R3-N01')
        self.assertEqual(request['order'], ['E', 'S'])
        self.assertFalse(request['authorization_granted'])
        self.assertEqual(request['output_new'], 'results/local/devrep-rx02-r3-N01')

    def test_old_or_missing_authorization_blocks_before_metadata_and_session(self):
        for connection in ('devrep-rx02-r1-D01', 'devrep-rx02-r2-N01'):
            old = json.loads((ROOT / 'results/local' / connection / 'authorization-consumed.json').read_text())
            with self.subTest(connection=connection), self.assertRaises(ValueError):
                cli.validate_authorization(old, '0' * 64)
        with patch.object(cli.prep, 'metadata_snapshot', side_effect=AssertionError('No metadata')), \
             patch.object(cli, 'DevrepSession', side_effect=AssertionError('No session')):
            # El caso ausente es sintético: nunca leer/usar un grant físico real.
            with patch.object(Path, 'read_text', side_effect=FileNotFoundError('synthetic missing grant')), \
                 self.assertRaises(FileNotFoundError):
                cli.execute(ROOT / cli.AUTHORIZATION, ROOT / cli.prep.OUTPUT)
            with self.assertRaises(ValueError):
                cli.execute(ROOT / 'results/local/preparacion-devrep-r1-D01/plan.autorizado.json', ROOT / cli.prep.OUTPUT)

    def test_wrong_ID_order_output_and_runtime_transition_are_rejected(self):
        base = json.loads((ROOT / cli.PLAN).read_text())
        runtime = runtime_plan(base)
        self.assertEqual(prepared_plan(runtime), base)
        self.assertEqual(SCHEDULE, R1_SCHEDULE)
        for key, value in [('connection_id', 'RX02-DEVREP-R1-D01'),
                           ('output_new', 'results/local/devrep-rx02-r1-D01'),
                           ('slots', list(reversed(runtime['slots']))),
                           ('ready_risk_reviewed', False), ('authorization_granted', False)]:
            changed = copy.deepcopy(runtime)
            changed[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_plan(changed, allow_physical=True)

    def test_changed_plan_sources_boot_or_sidecar_rejected_offline(self):
        plan = json.loads((ROOT / cli.PLAN).read_text())
        receipt = json.loads((ROOT / cli.RECEIPT).read_text())
        sidecar = json.loads((ROOT / cli.RECEIPT).with_suffix('.snapshots.json').read_text())
        for mutation in ('plan_hash', 'source', 'boot', 'sidecar'):
            r, s = copy.deepcopy(receipt), copy.deepcopy(sidecar)
            if mutation == 'plan_hash': r['plan_sha256'] = '0' * 64
            elif mutation == 'source': r['sources']['tools/preflight_devrep_r3.py'] = '0' * 64
            elif mutation == 'boot': r['host_boot_id'] = 'other'
            else: s['second']['identities']['RX-02']['pid'] = 'other'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                cli.review_receipt(plan, r, s)

    def test_R2_receipt_cannot_substitute_for_R3_preflight(self):
        plan = json.loads(cli.PLAN.read_text())
        directory = ROOT / 'results/local/preparacion-devrep-r2-N01'
        receipt = json.loads((directory / 'preflight-devlinks-rutas-v2.json').read_text())
        sidecar = json.loads((directory / 'preflight-devlinks-rutas-v2.snapshots.json').read_text())
        with self.assertRaises(ValueError):
            cli.review_receipt(plan, receipt, sidecar)

    def test_full_entry_binding_and_tampering_rejected_without_UART(self):
        runtime, entry = self.entry_fixture()
        with patch('serial.Serial', side_effect=AssertionError('No UART')):
            validate_entry(entry, runtime)
            for mutation in ('authorization', 'receipt', 'prepared_plan', 'identity', 'runtime'):
                e, p = copy.deepcopy(entry), copy.deepcopy(runtime)
                if mutation == 'authorization': e['authorization']['connection_id'] = 'RX02-DEVREP-R1-D01'
                elif mutation == 'receipt': e['receipt']['plan_sha256'] = '0' * 64
                elif mutation == 'prepared_plan': e['prepared_plan']['environment']['geometry'] = 'changed'
                elif mutation == 'identity': e['identities']['RX-02']['pid'] = 'other'
                else: p['actor'] += 'changed'
                with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                    validate_entry(e, p)

    def test_identity_change_immediately_before_open_blocks_before_serial(self):
        runtime, entry = self.entry_fixture()
        wrong = copy.deepcopy(entry['identities'])
        wrong['RX-02']['node_fingerprint'][1] += 1
        with patch('rx02_devrep_r3_n01.session.preflight_rx02', return_value=wrong), \
             patch('serial.Serial', side_effect=AssertionError('No UART')), \
             self.assertRaisesRegex(ValueError, 'identity changed'):
            DevrepSession(ROOT / cli.prep.OUTPUT, runtime,
                          authorization_reference=cli.prep.CONNECTION_ID + ':' + cli.serialized_hash(runtime),
                          entry_evidence=entry)
        self.assertFalse((ROOT / cli.prep.OUTPUT).exists())


class PtyTests(unittest.TestCase):
    def fixture(self, ready=True):
        rig = Rig()
        self.addCleanup(rig.dispose)
        plan = runtime_plan(cli.prep.template())
        if ready:
            rig.pair.fixture_write(PREFIX + boot('RX-02'))
        session = DevrepSession(rig.output, plan, test_backend=rig.backend, clock=rig.clock)
        self.addCleanup(session.journal.close_files)
        self.addCleanup(session._finish_notifier)
        def close_if_needed():
            if not session.read_loop_stopped: session.close()
        self.addCleanup(close_if_needed)
        return rig, session, Coordinator(session)

    def run_fixture(self, *, ready=True, skip_labels=False):
        rig, session, coordinator = self.fixture(ready)
        for _ in range(2300):
            rig.clock.advance(200_000_000)
            if not session.read_loop_stopped and not session.machine.close_requested:
                rig.pair.fixture_write(fixture_row(rig.ident, 100000 + rig.ident * 200000))
                rig.ident += 1
            coordinator.poll()
            for window in session.machine.windows:
                if (not skip_labels and window['label']['status'] == 'pending' and window['end_signal'] is not None and
                        session.machine.signals[window['end_signal']]['software_playback_ok'] is True):
                    coordinator.operator(['declare', window['id'], 'yes'])
            if coordinator.done: break
        else:
            self.fail('Bounded synthetic fixture did not terminate')
        session.finalize()
        return rig, audit_devrep(rig.output)

    def test_R3_exact_E_S_labels_replay_checkpoints_and_single_close(self):
        rig, report = self.run_fixture()
        self.assertTrue(report['integrity_ok'] and report['replay_ok'] and report['series_can_continue'])
        state = report['state']
        self.assertEqual([w['id'] for w in state['windows']], ['RX02-DEVREP-R3-N01-E', 'RX02-DEVREP-R3-N01-S'])
        self.assertTrue(all(w['label']['status'] == 'declared' for w in state['windows']))
        self.assertTrue(state['closed']['RX-02']['confirmed'])
        self.assertEqual(report['persistence_status']['pending_ops_bytes'], 0)
        self.assertEqual(sum(c[0] == 'open' for c in rig.calls), 1)
        self.assertEqual(sum(c[0] == 'close' and c[1] for c in rig.calls), 1)
        provenance = json.loads((rig.output / 'provenance.json').read_text())
        self.assertEqual({s['path']: s['sha256'] for s in provenance['sources']}, cli.all_sources())

    def test_missing_READY_stops_without_reopening(self):
        rig, report = self.run_fixture(ready=False)
        self.assertEqual(report['state']['fatal'], 'initial_availability_timeout')
        self.assertFalse(report['series_can_continue'])
        self.assertEqual(sum(c[0] == 'open' for c in rig.calls), 1)
        self.assertTrue(report['state']['closed']['RX-02']['confirmed'])

    def test_missing_E_declaration_stops_before_S(self):
        rig, report = self.run_fixture(skip_labels=True)
        self.assertFalse(report['series_can_continue'])
        self.assertEqual(len(report['state']['windows']), 1)
        self.assertEqual(report['state']['devrep_schedule']['failures'][0]['reason'], 'missing_declaration_by_deadline')


if __name__ == '__main__':
    unittest.main()
