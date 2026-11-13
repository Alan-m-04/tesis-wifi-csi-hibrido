"""Prospective RX-02 lifecycle with fabricated files and no serial devices."""

from contextlib import ExitStack, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import visor_rx02_240s as cli
from csi_live_observer import Observer, atomic_json
from presence_v4_journal import digest, write_new
from rx02_diagnostic.checkpoint import CheckpointJournal
from rx02_diagnostic.contract import HISTORICAL_CONNECTION, validate_plan
from rx02_diagnostic.journal import Rx02Journal
from rx02_live_view import ATTEMPT, Rx02Observer, clock_binding, current_rx02_snapshot
from rx02_physical_report import compare
from test_presence_rx02 import boot, fixture_row


IDENTITY = dict(by_id='/dev/serial/by-id/usb-1a86_USB_Single_Serial_5C93200689-if00',
                resolved='/dev/ttyUSB-fixture', serial='5C93200689', vid='1a86', pid='55d3',
                bus='usb', node_fingerprint=[1, 2, 3], permissions=dict(mode='0o660', uid=0, gid=0))


def fixture_paths(root):
    preparation = root / 'preparation'
    return dict(LOCAL=root, PREPARATION=preparation, PREFLIGHT=preparation / 'preflight.json',
                ORIGINAL_PREFLIGHT=root / 'original' / 'preflight.json',
                AUTHORIZATION=preparation / 'authorization.json', BUNDLE=root / 'bundle', VIEW=root / 'view')


class PhysicalViewTests(unittest.TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        self.root = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        stack.enter_context(patch.multiple(cli, **fixture_paths(self.root)))
        self.metadata = stack.enter_context(patch.object(cli, 'preflight_rx02', return_value={'RX-02': IDENTITY}))
        stack.enter_context(patch.object(cli, 'verify_serial_runtime'))
        self.serial = stack.enter_context(patch('serial.Serial', side_effect=AssertionError('No UART')))
        self.conditions = self.root / 'conditions.json'
        template = json.loads(cli.CONDITIONS_TEMPLATE.read_text())
        template.update(actor='Fixture', mounting_reference='Fixture', rx01_disconnected=True)
        template['environment'] = {name: 'Fixture declarada' for name in template['environment']}
        write_new(self.conditions, template)

    def prepare(self):
        cli.prepare(self.conditions)
        return cli.reviewed_preflight()

    def grant(self, reference):
        write_new(cli.AUTHORIZATION, dict(schema='rx02-live-authorization-1', attempt_id=ATTEMPT,
                  authorization_granted=True, single_attempt=True, reference=reference,
                  human_statement='Fixture de autorización'))

    def test_preflight_is_metadata_only_and_refuses_pending_or_overwrite(self):
        with self.assertRaises(ValueError):
            cli.prepare(cli.CONDITIONS_TEMPLATE)
        self.metadata.assert_not_called()
        plan, _ = self.prepare()
        self.metadata.assert_called_once()
        self.assertFalse(cli.BUNDLE.exists() or cli.VIEW.exists())
        self.assertEqual(plan['slots'], [])
        self.assertFalse(any(plan['permitted_uses'].values()))
        self.assertEqual(plan['live_view']['attempt_id'], ATTEMPT)
        self.assertEqual(plan['connection_id'], ATTEMPT)
        self.assertEqual(plan['partition_group'], ATTEMPT)
        self.assertEqual(plan['duration_ns'], 240_000_000_000)
        self.assertFalse(plan['authorization_granted'])
        self.serial.assert_not_called()
        with self.assertRaises(ValueError):
            cli.prepare(self.conditions)

    def test_review_and_new_preflight_preserve_exact_original(self):
        previous = json.loads(cli.NATIVE_TEMPLATE.read_text())
        previous['live_view'] = dict(attempt_id=ATTEMPT)
        cli.ORIGINAL_PREFLIGHT.parent.mkdir()
        write_new(cli.ORIGINAL_PREFLIGHT, dict(schema='rx02-live-preflight-1', attempt_id=ATTEMPT,
                  physical_UART_opened=False, plan=previous))
        original = cli.ORIGINAL_PREFLIGHT.read_bytes()
        review = cli.review_plan(self.conditions)
        self.metadata.assert_not_called()
        self.assertFalse(review['metadata_checked_now'])
        self.assertNotIn('identity', review['plan']['live_view'])
        with self.assertRaises(FileNotFoundError):
            cli.reviewed_preflight()
        plan, _ = self.prepare()
        self.metadata.assert_called_once()
        self.assertEqual(plan['live_view']['previous_preflight']['sha256'], hashlib.sha256(original).hexdigest())
        self.assertEqual(cli.ORIGINAL_PREFLIGHT.read_bytes(), original)
        self.assertEqual(json.loads(cli.PREFLIGHT.read_text())['schema'], 'rx02-live-preflight-2')

    def test_viewer_plan_cannot_alias_historical_id_or_group(self):
        plan, _ = self.prepare()
        for changes in (dict(connection_id=HISTORICAL_CONNECTION), dict(partition_group=HISTORICAL_CONNECTION),
                        dict(connection_id=HISTORICAL_CONNECTION, partition_group=HISTORICAL_CONNECTION),
                        dict(authorization_granted=True, review_state='authorized_single_attempt')):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_plan(dict(plan, **changes), allow_physical=True, execution=True)
        cli.BUNDLE.mkdir()
        write_new(cli.BUNDLE / 'plan.json', plan)
        with self.assertRaisesRegex(ValueError, 'Historical RX02-DIAG-CP-R1'):
            compare(cli.BUNDLE, self.root / 'unused', Mock(side_effect=AssertionError('Wrong auditor')))

    def test_approval_is_bound_to_exact_preflight_and_runtime(self):
        plan, reference = self.prepare()
        with self.assertRaises(FileNotFoundError):
            cli.approved()
        self.grant(reference)
        self.assertEqual(cli.approved(), (plan, reference))
        with patch.object(cli, 'clock_domain', return_value={'boot_id': 'wrong'}):
            with self.assertRaisesRegex(ValueError, 'arranque'):
                cli.approved()
        cli.PREFLIGHT.write_bytes(cli.PREFLIGHT.read_bytes() + b'\n')
        with self.assertRaisesRegex(ValueError, 'autorización explícita'):
            cli.approved()

    def test_changed_identity_or_existing_view_prevents_spawn(self):
        _, reference = self.prepare()
        self.grant(reference)
        self.metadata.return_value = {'RX-02': dict(IDENTITY, node_fingerprint=[1, 2, 4])}
        with patch.object(cli, 'spawn') as spawn, self.assertRaisesRegex(ValueError, 'Cambió'):
            cli.run_attempt()
        spawn.assert_not_called()
        cli.VIEW.mkdir()
        with self.assertRaisesRegex(ValueError, 'ya existe'):
            cli.run_attempt()

    def test_constructor_rechecks_its_native_snapshot_before_begin(self):
        plan, _ = self.prepare()
        session = cli.ReviewedSession.__new__(cli.ReviewedSession)
        session.machine = SimpleNamespace(plan=plan)
        session.endpoints = {'RX-02': SimpleNamespace(expected=dict(IDENTITY, node_fingerprint=[1, 2, 4]))}
        with patch.object(cli.CheckpointRx02Session, 'command') as command:
            with self.assertRaisesRegex(ValueError, 'Apertura cancelada'):
                session.command('begin')
            command.assert_not_called()

    def test_supervisor_audits_after_capture_exit_even_if_view_exits(self):
        _, reference = self.prepare()
        self.grant(reference)
        source, observer, auditor = Mock(), Mock(), Mock()
        source.poll.side_effect = [None, 0, 0]
        observer.poll.return_value = 1
        auditor.poll.return_value = 0
        source.wait.return_value = auditor.wait.return_value = 0
        observer.wait.return_value = 1
        children = {'--observer-worker': observer, '--capture-worker': source, '--audit-worker': auditor}

        def spawn(worker):
            if worker == '--audit-worker':
                source.wait.assert_called_once()
                self.assertEqual(json.loads((cli.VIEW / 'source-exit.json').read_text())['exit_code'], 0)
            return children[worker]

        server = Mock()
        server.__enter__ = Mock(return_value=server)
        server.__exit__ = Mock(return_value=False)
        with (patch.object(cli, 'ViewServer', return_value=server), patch.object(cli, 'spawn', side_effect=spawn),
              patch.object(cli, 'Thread'), patch.object(cli.time, 'sleep'), redirect_stdout(io.StringIO())):
            self.assertEqual(cli.run_attempt(), 1)
        source.send_signal.assert_not_called()
        self.serial.assert_not_called()

    def bundle(self, *, correct_open=True):
        plan, reference = self.prepare()
        cli.VIEW.mkdir()
        backend = dict(backend='UART', identities={'RX-02': IDENTITY}, authorization_reference=reference,
                       storage_policy=plan['storage_policy'], initial_free_bytes_observed=1024**3)
        original = Rx02Journal(cli.BUNDLE, plan, allow_physical=True, evidence_type='physical_capture',
                               extra_provenance=backend)
        journal = CheckpointJournal(original)
        self.addCleanup(journal.close_files)
        write_new(cli.BUNDLE / 'authorization-consumed.json', dict(protocol=plan['protocol'],
            connection_id=plan['connection_id'], reference=reference, consumed=True, retry_allowed=False))
        start = time.monotonic_ns() - 241_000_000_000
        journal.command('begin', start)
        journal.command('storage_check', start, free_bytes=1024**3, raw_bytes=0, size_bytes=0,
                        final_extra=0, guard_started_ns=start)
        fingerprint = IDENTITY['node_fingerprint'] if correct_open else [4, 5, 6]
        journal.command('opened', start, receiver='RX-02',
                        identity_binding=dict(identity=IDENTITY, opened_fingerprint=fingerprint))
        journal.command('chunk', start, receiver='RX-02', chunk=b'\xffresiduo original\n' + boot('RX-02'),
                        started_ns=start, returned_ns=start)
        for i in range(1200):
            now = start + (i + 1) * 200_000_000
            journal.command('chunk', now, receiver='RX-02', chunk=fixture_row(i, 100000 + i * 200000),
                            started_ns=now, returned_ns=now)
            journal.command('tick', now)
        journal.command('close_request', now)
        journal.command('closing', now)
        journal.command('closed', now, receiver='RX-02', confirmed=True, reader_stopped=True,
                        proof='pyserial_close_returned_and_all_fds_released')
        journal.receipt()
        journal.command('storage_check', now, free_bytes=1024**3, raw_bytes=journal.raw['RX-02'].tell(),
                        size_bytes=0, final_extra=65536, guard_started_ns=start)
        endpoint = dict(open_attempts=1, close_attempts=1, is_open=False, fd=None)
        journal.finalize(dict(startup_reader_stopped=True, receivers={'RX-02': endpoint}))
        atomic_json(cli.VIEW / 'clock-binding.json', clock_binding(cli.BUNDLE, reference))
        write_new(cli.VIEW / 'source-exit.json', dict(attempt_id=ATTEMPT, reference=reference, exit_code=0))
        return plan, reference

    def test_offline_observer_and_native_audit_of_fabricated_bundle(self):
        _, reference = self.bundle()
        before = {p: digest(p) for p in cli.BUNDLE.iterdir() if p.is_file()}
        with self.assertRaisesRegex(ValueError, 'Physical/historical'):
            Observer(cli.BUNDLE)
        with patch.object(cli.time, 'sleep'):
            self.assertEqual(cli.observer_worker(), 0)
        path = cli.VIEW / 'latest.json'
        snapshot = current_rx02_snapshot(path)
        self.assertIsNone(snapshot['observer_error'])
        self.assertEqual(snapshot['rows_seen'], 1200)
        self.assertLessEqual(len(snapshot['rows']), 8)
        self.assertEqual(snapshot['backlog_bytes'], 0)
        self.assertTrue(snapshot['source_stopped'])
        self.assertFalse(snapshot['physical_close_verified'])
        self.assertEqual(json.loads((cli.VIEW / 'observer-result.json').read_text())['rows_seen'], 1200)
        # Audit in a separate interpreter. The fabricated journal is finalized above.
        code = ('from pathlib import Path; import sys; import visor_rx02_240s as cli; '
                'from test_rx02_live_view import fixture_paths; from csi_live_observer import guard; '
                'sys.addaudithook(guard); vars(cli).update(fixture_paths(Path(sys.argv[1]))); '
                'raise SystemExit(cli.audit_worker())')
        audit = subprocess.run([sys.executable, '-B', '-c', code, str(self.root)], cwd=cli.ROOT,
                               capture_output=True, text=True, timeout=15)
        self.assertEqual(audit.returncode, 0, audit.stdout + audit.stderr)
        result = json.loads((cli.VIEW / 'audit-result.json').read_text())
        self.assertTrue(result['close_verified'])
        self.assertEqual(result['connection_id'], ATTEMPT)
        self.assertEqual(result['partition_group'], ATTEMPT)
        native = json.loads((cli.VIEW / 'audit-native.json').read_text())
        self.assertEqual(native['state']['connection_id'], ATTEMPT)
        self.assertEqual(native['state']['partition_group'], ATTEMPT)
        for filename in ('authorization-consumed.json', 'close-receipt.json'):
            self.assertEqual(json.loads((cli.BUNDLE / filename).read_text())['connection_id'], ATTEMPT)
        self.assertEqual(result['reference'], reference)
        self.assertFalse(result['quality_ok'])
        self.assertTrue(current_rx02_snapshot(path)['physical_close_verified'])
        self.assertEqual(before, {p: digest(p) for p in before})
        self.serial.assert_not_called()

    def test_auditor_preserves_incomplete_bundle_and_never_confirms_close(self):
        _, reference = self.prepare()
        cli.VIEW.mkdir()
        cli.BUNDLE.mkdir()
        prefix = cli.BUNDLE / 'operations.jsonl'
        prefix.write_bytes(b'incomplete fixture')
        write_new(cli.VIEW / 'source-exit.json', dict(attempt_id=ATTEMPT, reference=reference, exit_code=1))
        with redirect_stdout(io.StringIO()):
            self.assertEqual(cli.audit_worker(), 1)
        result = json.loads((cli.VIEW / 'audit-result.json').read_text())
        self.assertFalse(result['close_verified'])
        self.assertIn('incompleto', result['error'])
        self.assertEqual(prefix.read_bytes(), b'incomplete fixture')

    def test_view_rejects_open_fingerprint_and_altered_clock(self):
        plan, reference = self.bundle(correct_open=False)
        with self.assertRaisesRegex(ValueError, 'apertura nativa'):
            Rx02Observer(cli.BUNDLE, cli.VIEW, plan, reference)
        path = cli.VIEW / 'clock-binding.json'
        proof = json.loads(path.read_text())
        proof['domain']['boot_id'] = 'other'
        atomic_json(path, proof)
        with self.assertRaisesRegex(ValueError, 'Constancia de reloj'):
            Rx02Observer(cli.BUNDLE, cli.VIEW, plan, reference)
