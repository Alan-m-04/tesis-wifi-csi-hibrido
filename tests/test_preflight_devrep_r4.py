"""R4: barreras de metadatos con fixtures; ningún UART o preflight físico."""
import contextlib
import copy
import io
import itertools
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import preflight_devrep_r4 as cli


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.prep = self.root / cli.PREPARATION
        self.prep.mkdir(parents=True)
        source = self.root / 'config/devrep_r1/D01.review.json'
        source.parent.mkdir(parents=True)
        source.write_bytes((ROOT / 'config/devrep_r1/D01.review.json').read_bytes())
        interface = self.root / 'src/devrep_keyboard_prompt.py'
        interface.parent.mkdir(parents=True)
        interface.write_bytes((ROOT / 'src/devrep_keyboard_prompt.py').read_bytes())
        (self.root / cli.KEYBOARD_PRACTICE).write_text(json.dumps(dict(
            connection_id=cli.CONNECTION_ID, operator_reported_completed=True,
            interface_sha256=cli.digest(interface), authorization_granted=False,
            evidence_type='synthetic_test_only')))
        self.addCleanup(patch.stopall)
        patch.object(cli, 'ROOT', self.root).start()
        patch.object(cli, 'boot_id', return_value='synthetic-new-boot').start()
        patch.object(cli, 'source_hashes', return_value={'synthetic_source.py': '0' * 64}).start()
        self.metadata = patch.object(cli, 'metadata_snapshot', return_value={
            'identities': {'RX-02': {'serial': '5C93200689'}},
            'enumerated_tty_metadata': []}).start()
        self.runtime = patch.object(cli, 'verify_serial_runtime').start()
        patch('serial.Serial', side_effect=AssertionError('UART prohibited')).start()
        self.plan = cli.template()
        self.plan_path = self.prep / 'plan.local.json'
        self.receipt = self.prep / 'new-receipt.json'

    def save(self):
        self.plan_path.write_text(json.dumps(self.plan))

    def confirm(self):
        declaration = self.prep / 'declaration.json'
        declaration.write_text('{"evidence_type":"synthetic_test_only"}')
        self.plan.update(actor='Synthetic fixture operator', environment={
            k: 'Synthetic current declaration' for k in self.plan['environment']},
            mounting_reference=str(declaration.relative_to(self.root)),
            setup_snapshot_path=str(declaration.relative_to(self.root)),
            setup_snapshot_sha256=cli.digest(declaration))
        self.plan['unused_receiver']['operator_confirmation'] = 'confirmed_current'
        self.plan['conditions_confirmation'] = dict(
            confirmed_current=True, host_boot_id='synthetic-new-boot',
            declaration_path=str(declaration.relative_to(self.root)),
            declaration_sha256=cli.digest(declaration))
        self.save()

    def test_review_and_pending_preflight_never_query_devices(self):
        self.save()
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(cli.main(['--plan', str(self.plan_path)]), 0)
        self.assertEqual(json.loads(out.getvalue())['state'], 'PREPARED_CONDITIONS_PENDING')
        with self.assertRaisesRegex(ValueError, 'PENDIENTE'):
            cli.run_preflight(self.plan_path, self.receipt)
        self.metadata.assert_not_called()
        self.runtime.assert_not_called()
        self.assertFalse(self.receipt.exists())

    def test_success_is_metadata_only_and_never_overwrites_or_creates_capture(self):
        self.confirm()
        result = cli.run_preflight(self.plan_path, self.receipt)
        self.assertEqual(self.metadata.call_count, 2)
        self.assertFalse(result['authorization_granted'])
        self.assertFalse(result['physical_UART_opened'])
        self.assertFalse(result['acquisition_executor_enabled'])
        self.assertEqual(result['host_boot_id'], 'synthetic-new-boot')
        self.assertFalse((self.root / cli.OUTPUT).exists())
        original = self.receipt.read_bytes()
        with self.assertRaises(ValueError):
            cli.run_preflight(self.plan_path, self.receipt)
        self.assertEqual(self.receipt.read_bytes(), original)
        self.assertEqual(self.metadata.call_count, 2)

    def test_boot_change_or_modified_declaration_requires_new_confirmation(self):
        self.confirm()
        for mutation in ('boot', 'declaration'):
            with self.subTest(mutation=mutation):
                if mutation == 'boot':
                    self.plan['conditions_confirmation']['host_boot_id'] = 'old-boot'
                    self.save()
                else:
                    self.plan['conditions_confirmation']['host_boot_id'] = 'synthetic-new-boot'
                    self.save()
                    (self.prep / 'declaration.json').write_text('changed')
                with self.assertRaises(ValueError):
                    cli.run_preflight(self.plan_path, self.receipt)
        self.metadata.assert_not_called()

    def test_old_ID_authorization_output_and_thresholds_are_rejected(self):
        original = copy.deepcopy(self.plan)
        changes = [('connection_id', 'RX02-DEVREP-R1-D01'), ('authorization_granted', True),
                   ('output_new', 'results/local/devrep-rx02-r1-D01'),
                   ('predecessor', 'RX02-DEVREP-R1-D01'),
                   ('policy', dict(original['policy'], coverage_min_rows=1))]
        for key, value in changes:
            plan = dict(original, **{key: value})
            with self.subTest(key=key), self.assertRaises(ValueError):
                cli.validate(plan)

    def test_existing_capture_or_old_receipt_directory_refuses_before_metadata(self):
        self.confirm()
        with self.assertRaises(ValueError):
            cli.run_preflight(self.plan_path, self.root / 'preflight-before-reboot.json')
        (self.root / cli.OUTPUT).mkdir()
        with self.assertRaises(ValueError):
            cli.run_preflight(self.plan_path, self.receipt)
        self.metadata.assert_not_called()

    def test_metadata_change_rejects_without_success_receipt(self):
        self.confirm()
        self.metadata.side_effect = [{'serial': 'expected'}, {'serial': 'changed'}]
        with self.assertRaisesRegex(ValueError, 'cambiaron'):
            cli.run_preflight(self.plan_path, self.receipt)
        self.assertFalse(self.receipt.exists())

    def test_capture_flag_does_not_exist(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            cli.main(['--execute-after-approval'])
        self.metadata.assert_not_called()

    def test_invalid_receipt_suffix_rejects_before_confirming_or_writing(self):
        self.save()
        with patch.object(cli, 'confirm_current_conditions', side_effect=AssertionError('No confirmation')), \
             contextlib.redirect_stderr(io.StringIO()):
            result = cli.main(['--preflight-only', '--confirm-current-conditions',
                '--plan', str(self.plan_path), '--receipt-new', str(self.receipt) + '~'])
        self.assertEqual(result, 1)
        self.assertFalse((self.prep / 'declaracion-actual-terminal-r1.json').exists())
        self.metadata.assert_not_called()

    def test_changed_keyboard_practice_interface_binding_blocks_before_metadata(self):
        self.confirm()
        (self.root / 'src/devrep_keyboard_prompt.py').write_text('changed synthetic interface')
        with self.assertRaisesRegex(ValueError, 'Práctica'):
            cli.run_preflight(self.plan_path, self.receipt)
        self.metadata.assert_not_called()

    def test_terminal_declined_confirmation_never_creates_files_or_queries_metadata(self):
        self.save()
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError, 'no confirmadas'):
            cli.confirm_current_conditions(self.plan_path, ask=lambda _: 'no')
        self.metadata.assert_not_called()
        self.assertFalse((self.prep / 'declaracion-actual-terminal-r1.json').exists())

    def test_explicit_terminal_confirmation_binds_new_files_and_never_grants_capture(self):
        self.save()
        original = self.plan_path.read_bytes()
        with contextlib.redirect_stdout(io.StringIO()):
            confirmed = cli.confirm_current_conditions(self.plan_path, ask=lambda _: 'CONFIRMO')
        plan = json.loads(confirmed.read_text())
        cli.validate(plan, confirmed=True)
        self.assertTrue(plan['conditions_confirmation']['confirmed_current'])
        self.assertFalse(plan['authorization_granted'])
        self.assertFalse(plan['acquisition_executor_enabled'])
        self.assertEqual(self.plan_path.read_bytes(), original)
        self.metadata.assert_not_called()
        with self.assertRaisesRegex(ValueError, 'existente'):
            cli.confirm_current_conditions(self.plan_path, ask=lambda _: 'CONFIRMO')

    def test_existing_receipt_refuses_before_terminal_confirmation(self):
        self.save()
        self.receipt.write_text('existing evidence')
        with patch.object(cli, 'confirm_current_conditions', side_effect=AssertionError('No confirmation')), \
             contextlib.redirect_stderr(io.StringIO()):
            result = cli.main(['--preflight-only', '--confirm-current-conditions',
                '--plan', str(self.plan_path), '--receipt-new', str(self.receipt)])
        self.assertEqual(result, 1)
        self.metadata.assert_not_called()

    def test_terminal_confirmation_then_preflight_uses_new_bound_plan_without_capture(self):
        self.save()
        with patch('builtins.input', return_value='CONFIRMO'), contextlib.redirect_stdout(io.StringIO()):
            result = cli.main(['--preflight-only', '--confirm-current-conditions',
                '--plan', str(self.plan_path), '--receipt-new', str(self.receipt)])
        self.assertEqual(result, 0)
        receipt = json.loads(self.receipt.read_text())
        self.assertEqual(receipt['plan_path'], str(cli.CONFIRMED_PLAN))
        self.assertEqual(receipt['plan_sha256'], cli.digest(self.root / cli.CONFIRMED_PLAN))
        self.assertFalse(receipt['authorization_granted'])
        self.assertFalse(receipt['physical_UART_opened'])
        self.assertFalse(receipt['capture_executed'])
        self.assertFalse((self.root / cli.OUTPUT).exists())

    def links_snapshot(self, links):
        return {'identities': {'RX-02': {'serial': '5C93200689', 'pid': '55d3',
                                        'node_fingerprint': [7, 912, 42496]}},
                'enumerated_tty_metadata': [{'sysfs': '/synthetic/ttyACM0', 'properties': {
                    'DEVLINKS': ' '.join(links), 'ID_PATH': 'pci-synthetic-4',
                    'USEC_INITIALIZED': '123', 'TAGS': ':systemd:uaccess:'}}]}

    def test_DEVLINKS_all_permutations_pass_and_preserve_both_originals(self):
        self.confirm()
        links = ['/dev/serial/by-id/synthetic', '/dev/serial/by-path/a', '/dev/serial/by-path/b']
        first = self.links_snapshot(links)
        for index, permutation in enumerate(itertools.permutations(links)):
            with self.subTest(permutation=permutation):
                second = self.links_snapshot(permutation)
                originals = copy.deepcopy([first, second])
                self.metadata.side_effect = [first, second]
                receipt = self.prep / f'permutation-{index}.json'
                result = cli.run_preflight(self.plan_path, receipt)
                self.assertEqual(result['metadata_snapshots'], dict(first=originals[0], second=originals[1]))
                self.assertTrue(result['metadata_comparison']['equal_under_revision'])
                self.assertEqual(result['metadata_comparison']['raw_equal'], first == second)
                sidecar = json.loads(receipt.with_suffix('.snapshots.json').read_text())
                self.assertEqual([sidecar['first'], sidecar['second']], originals)
                self.assertEqual([first, second], originals)

    def test_DEVLINKS_added_removed_modified_or_duplicated_routes_reject(self):
        self.confirm()
        links = ['/dev/serial/by-id/synthetic', '/dev/serial/by-path/a', '/dev/serial/by-path/b']
        changes = [links + ['/dev/serial/by-path/c'], links[:-1],
                   [*links[:-1], '/dev/serial/by-path/modified'], links + [links[0]]]
        for index, changed in enumerate(changes):
            with self.subTest(changed=changed):
                first, second = self.links_snapshot(links), self.links_snapshot(changed)
                self.metadata.side_effect = [first, second]
                receipt = self.prep / f'rejected-{index}.json'
                with self.assertRaisesRegex(ValueError, 'Metadatos, boot o plan'):
                    cli.run_preflight(self.plan_path, receipt)
                self.assertFalse(receipt.exists())
                evidence = json.loads(receipt.with_suffix('.snapshots.json').read_text())
                self.assertEqual(evidence['first'], first)
                self.assertEqual(evidence['second'], second)
                self.assertFalse(evidence['metadata_comparison']['equal_under_revision'])
                self.assertFalse(evidence['authorization_granted'])

    def test_other_fields_types_missing_keys_and_enumeration_order_remain_strict(self):
        first = self.links_snapshot(['/dev/a', '/dev/b'])
        cases = []
        for key, value in [('ID_PATH', 'changed'), ('USEC_INITIALIZED', '456'),
                           ('TAGS', ':uaccess:systemd:'), ('DEVLINKS', ['/dev/a', '/dev/b'])]:
            second = copy.deepcopy(first)
            second['enumerated_tty_metadata'][0]['properties'][key] = value
            cases.append(second)
        second = copy.deepcopy(first)
        del second['enumerated_tty_metadata'][0]['properties']['DEVLINKS']
        cases.append(second)
        second = copy.deepcopy(first)
        second['identities']['RX-02']['node_fingerprint'][1] += 1
        cases.append(second)
        for second in cases:
            self.assertFalse(cli.metadata_snapshots_equal(first, second))
        multiple = copy.deepcopy(first)
        multiple['enumerated_tty_metadata'].append({'sysfs': '/synthetic/ttyACM1', 'properties': {}})
        reversed_nodes = copy.deepcopy(multiple)
        reversed_nodes['enumerated_tty_metadata'].reverse()
        self.assertFalse(cli.metadata_snapshots_equal(multiple, reversed_nodes))


class IdentityMetadataTests(unittest.TestCase):
    def check_metadata(self, serials):
        from types import SimpleNamespace
        devices = [Path('/synthetic/sysfs/ttyACM' + str(i)) for i in range(len(serials))]
        queries = [SimpleNamespace(stdout='ID_SERIAL_SHORT=' + s + '\n') for s in serials]
        with patch.object(cli, 'resolve_ports', return_value={'RX-02': '/dev/ttyACM0'}), \
             patch.object(cli, 'identity', return_value={'resolved': '/dev/ttyACM0'}), \
             patch.object(cli.Path, 'glob', side_effect=[devices, []]), \
             patch.object(cli.subprocess, 'run', side_effect=queries), \
             patch('serial.Serial', side_effect=AssertionError('UART prohibited')):
            return cli.metadata_snapshot()

    def test_duplicate_RX02_serial_or_enumerated_RX01_blocks(self):
        for serials in (['5C93200689', '5C93200689'], ['5C93200689', '5C93199744'], []):
            with self.subTest(serials=serials), self.assertRaises(ValueError):
                self.check_metadata(serials)

    def test_unique_RX02_is_resolved_without_constructing_serial(self):
        result = self.check_metadata(['5C93200689'])
        self.assertEqual(result['identities']['RX-02']['resolved'], '/dev/ttyACM0')


if __name__ == '__main__':
    unittest.main()
