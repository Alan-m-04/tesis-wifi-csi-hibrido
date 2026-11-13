"""Dual v2 coordinator, actual private PTYs, audit and offline consumer."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import controlled_capture as control
from canonical_csi import canonicalize
from validate_capture import audit_capture
from pty_dual_v2_fixture import run_pty_dual, plan_v2

ROOT = Path(__file__).resolve().parents[1]


class DualV2Tests(unittest.TestCase):
    def run_case(self, scenario='complete'):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        result = run_pty_dual(Path(tmp.name), scenario=scenario)
        self.assertTrue(result['all_ports_closed'])
        self.assertFalse(result['writer_errors'])
        self.assertEqual({e['receiver'] for e in result['close_events']}, {'RX-01', 'RX-02'})
        self.assertTrue(all(not e['read_active'] for e in result['close_events']))
        return result, json.loads((result['run'] / 'quality.json').read_text())

    def test_completion_pty_preserves_late_row_but_excludes_it_from_common_window(self):
        result, quality = self.run_case()
        self.assertEqual(result['returncode'], 0, quality)
        session = json.loads((result['run'] / 'capture/session.json').read_text())
        self.assertEqual(int(session['controlled']['common_deadline_ns']) - int(session['controlled']['common_start_ns']), 120_000_000)
        self.assertEqual(session['protocol'], 'controlled_dual_v2')
        for rx in control.PORTS:
            item = quality['full_session']['receivers'][rx]
            self.assertEqual(item['valid_rows'], 2)
            self.assertEqual(item['common_window_rows'], 1)
            self.assertEqual(item['post_deadline_rows'], 1)
            self.assertEqual(item['stop']['stop_reason'], 'lf_boundary')
            self.assertTrue(item['stop_metadata_ok'])
            self.assertEqual(item['trailing_bytes'], 0)
            self.assertGreater(item['stop']['completion_bytes'], 0)

    def test_timeout_keeps_tail_and_rejects_session_with_integrity_preserved(self):
        result, quality = self.run_case('timeout')
        self.assertEqual(result['returncode'], 1)
        for item in quality['full_session']['receivers'].values():
            self.assertEqual(item['stop']['stop_reason'], 'time_limit_incomplete')
            self.assertEqual(item['trailing_bytes'], 129)
            self.assertTrue(item['integrity_ok'])
            self.assertFalse(item['quality_ok'])

    def test_continuous_no_lf_flow_terminates_with_fixed_budget(self):
        result, quality = self.run_case('continuous_no_lf')
        self.assertEqual(result['returncode'], 1)
        for item in quality['full_session']['receivers'].values():
            self.assertIn(item['stop']['stop_reason'], ('time_limit_incomplete', 'byte_limit_incomplete'))
            self.assertGreater(item['trailing_bytes'], 129)
            self.assertLessEqual(item['stop']['completion_bytes'], 65536)
            self.assertTrue(item['integrity_ok'])

    def test_abort_closes_both_without_completing_or_approving_tail(self):
        result, quality = self.run_case('abort')
        self.assertEqual(result['returncode'], 1)
        self.assertEqual(quality['full_session']['session_status'], 'interrupted')
        for item in quality['full_session']['receivers'].values():
            self.assertEqual(item['stop']['stop_reason'], 'aborted')
            self.assertGreater(item['trailing_bytes'], 0)
            self.assertTrue(item['integrity_ok'])

    def test_one_receiver_read_error_stops_peer_and_preserves_recorded_bytes(self):
        result, quality = self.run_case('read_error')
        self.assertEqual(result['returncode'], 1)
        self.assertEqual(result['injected_read_errors'], 1)
        audit = quality['full_session']
        self.assertEqual(audit['session_status'], 'error')
        self.assertEqual(audit['receivers']['RX-01']['stop']['stop_reason'], 'error')
        self.assertEqual(audit['receivers']['RX-02']['stop']['stop_reason'], 'aborted')
        self.assertTrue(all(item['integrity_ok'] for item in audit['receivers'].values()))
        self.assertFalse(audit['quality_ok'])

    def test_residual_startup_still_rejected_after_successful_lf_completion(self):
        result, quality = self.run_case('startup_residue')
        self.assertEqual(result['returncode'], 1)
        for rx, item in quality['full_session']['receivers'].items():
            self.assertEqual(item['stop']['stop_reason'], 'lf_boundary')
            self.assertEqual(item['embedded_boot_lines'], [1])
            self.assertTrue(item['integrity_ok'])
            self.assertTrue((result['run'] / 'capture' / (rx.lower() + '.serial.log')).read_bytes().startswith(b'\x4c\x13\x00ESP-ROM:synthetic'))

    def test_bad_complete_csi_stays_rejected_after_completion(self):
        result, quality = self.run_case('malformed')
        self.assertEqual(result['returncode'], 1)
        for item in quality['full_session']['receivers'].values():
            self.assertEqual(item['counts']['malformed_rows'], 1)
            self.assertFalse(item['complete_rows_quality_ok'])
            self.assertTrue(item['integrity_ok'])

    def test_second_open_failure_keeps_first_startup_and_closes_both_objects(self):
        result, quality = self.run_case('second_open_error')
        self.assertEqual(result['returncode'], 1)
        self.assertIn('audit_error', quality)
        self.assertIn(b'SYNTHETIC STARTUP', (result['run'] / 'capture/rx-01.serial.log').read_bytes())

    def test_keyboard_interrupt_in_startup_joins_reader_before_both_closes(self):
        result, quality = self.run_case('second_open_interrupt')
        session = json.loads((result['run'] / 'capture/session.json').read_text())
        self.assertEqual(result['returncode'], 1)
        self.assertEqual(session['status'], 'interrupted')
        self.assertFalse(quality['session_quality_ok'])
        self.assertEqual(session['results']['RX-01']['stop']['stop_reason'], 'aborted')

    def test_canonical_and_official_consumer_keep_v2_counts_times_and_synthetic_label(self):
        result, _ = self.run_case('startup_residue')
        manifest = json.loads((result['run'] / 'capture-manifest.json').read_text())
        profile = json.loads((ROOT / 'config/csi_esp32s3.json').read_text())
        canonical = canonicalize(result['run'] / 'capture', manifest, profile)
        self.assertEqual(canonical['status_label'], 'prueba sintética controlada v2 con validación estricta rechazada')
        for rx, item in canonical['receivers'].items():
            self.assertEqual([f['timing_phase'] for f in item['frames']], ['nominal', 'after_deadline'])
            self.assertEqual([f['received_in_common_window'] for f in item['frames']], [True, False])
            self.assertEqual(canonical['nominal_window']['counts_and_stops'][rx]['common_window_rows'], 1)
        process = subprocess.run([str(ROOT / '.tools/node-v22.20.0/bin/node'), str(ROOT / 'tools/consume_canonical.mjs')],
            input=json.dumps(canonical), capture_output=True, text=True, check=True)
        official = json.loads(process.stdout)
        self.assertFalse(official['strict_quality_ok'])
        self.assertEqual(len(official['views']), 4)
        self.assertTrue(all(len(view['frames']) == 2 for view in official['views'].values()))

    def test_forged_stop_reason_rejected_even_with_recomputed_hashes(self):
        result, _ = self.run_case('timeout')
        root = result['run'] / 'capture'
        manifest = json.loads((result['run'] / 'capture-manifest.json').read_text())
        session = json.loads((root / 'session.json').read_text())
        summary = json.loads((root / 'rx-01.summary.json').read_text())
        summary['stop']['stop_reason'] = 'lf_boundary'
        session['results']['RX-01'] = summary
        (root / 'rx-01.summary.json').write_text(json.dumps(summary))
        (root / 'session.json').write_text(json.dumps(session))
        for entry in manifest['files']:
            path = root / entry['name']
            entry.update(bytes=path.stat().st_size, sha256=control.sha(path))
        audit = audit_capture(root, manifest)
        self.assertFalse(audit['receivers']['RX-01']['stop_metadata_ok'])
        self.assertFalse(audit['quality_ok'])

    def test_forged_late_read_phase_rejected_even_with_recomputed_ledger_hash(self):
        result, _ = self.run_case()
        root = result['run'] / 'capture'
        manifest = json.loads((result['run'] / 'capture-manifest.json').read_text())
        path = root / 'rx-01.reads.jsonl'
        reads = [json.loads(line) for line in path.read_text().splitlines()]
        index = next(i for i, event in enumerate(reads) if event['phase'] == 'completion')
        reads[index]['phase'] = 'nominal'
        path.write_text(''.join(json.dumps(event) + '\n' for event in reads))
        entry = next(item for item in manifest['read_ledgers'] if item['name'] == path.name)
        entry.update(bytes=path.stat().st_size, sha256=control.sha(path))
        audit = audit_capture(root, manifest)
        self.assertFalse(audit['receivers']['RX-01']['stop_metadata_ok'])
        self.assertFalse(audit['quality_ok'])

    def test_template_limits_and_default_cli_require_separate_execution_and_environment(self):
        plan = plan_v2()
        for key, value in [('grace_ns', 251000000), ('max_completion_bytes', 65537)]:
            forged = copy.deepcopy(plan)
            forged['stop_policy'][key] = value
            with self.assertRaises(ValueError):
                control.validate_plan(forged)
        template = ROOT / 'config/captura_dual_v2_30s.template.json'
        with self.assertRaises(ValueError):
            control.validate_plan(json.loads(template.read_text()), True)
        spec = importlib.util.spec_from_file_location('cli_v2', ROOT / 'tools/captura_dual_controlada.py')
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        with patch('sys.argv', ['capture', '--plan', str(template)]), redirect_stdout(io.StringIO()), \
                patch('serial.Serial', side_effect=AssertionError('No UART')) as opened:
            self.assertEqual(cli.main(), 0)
            opened.assert_not_called()


if __name__ == '__main__':
    unittest.main()
