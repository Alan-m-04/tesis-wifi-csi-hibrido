"""v3 PTY integration, immutable audit and offline exports."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import subprocess

import controlled_capture as control
from pty_dual_v3_fixture import run_pty_v3, plan_v3
from validate_capture import audit_capture
from canonical_csi import canonicalize

ROOT = Path(__file__).resolve().parents[1]


class DualV3Tests(unittest.TestCase):
    def run_case(self, scenario='accepted'):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        result = run_pty_v3(Path(tmp.name), scenario=scenario)
        self.assertTrue(result['all_ports_closed'])
        self.assertFalse(result['writer_errors'])
        self.assertEqual({e['receiver'] for e in result['close_events']}, set(control.PORTS))
        self.assertTrue(all(not e['read_active'] for e in result['close_events']))
        quality = json.loads((result['run'] / 'quality.json').read_text())
        self.assertNotIn('audit_error', quality, quality)
        return result, quality

    def test_accepted_connection_and_window_are_prospective_and_distinct(self):
        result, q = self.run_case()
        self.assertEqual(result['returncode'], 0, q)
        self.assertTrue(q['connection_full']['quality_ok'])
        self.assertTrue(q['experimental_window']['quality_ok'])
        w = q['experimental_window']
        self.assertEqual(int(w['T1_ns']) - int(w['T0_ns']), 160_000_000)
        self.assertEqual(w['campaign_model_suitability'], 'not_evaluated')
        self.assertTrue(q['full_session']['coordination_trace_ok'])
        for rx, item in w['receivers'].items():
            self.assertGreater(item['coverage']['included_rows'], 0)
            self.assertIsNone(item['coverage']['max_gap_limit_ns'])
            self.assertGreater(sum(x['inclusion'] in ('preamble', 'crosses_start') for x in item['index']), 0)

    def test_startup_rejection_is_visible_even_when_window_conforms(self):
        result, q = self.run_case('startup_residue')
        self.assertEqual(result['returncode'], 1)
        self.assertFalse(q['connection_full']['quality_ok'])
        self.assertTrue(q['experimental_window']['quality_ok'], q)
        self.assertTrue(q['connection_full']['integrity_ok'])

    def test_missing_ready_times_out_with_no_fabricated_window(self):
        result, q = self.run_case('missing_ready')
        self.assertEqual(result['returncode'], 1)
        self.assertEqual(q['experimental_window']['status'], 'no_iniciada')
        self.assertTrue(q['experimental_window']['availability']['timed_out'])
        self.assertIsNone(q['experimental_window']['T0_ns'])

    def test_reset_in_startup_batch_never_arms(self):
        result, q = self.run_case('same_chunk_reset')
        self.assertEqual(result['returncode'], 1)
        self.assertIsNone(q['experimental_window']['T0_ns'])
        self.assertIsNotNone(q['experimental_window']['availability']['fatal'])

    def test_conflicting_ready_after_strict_ready_aborts_without_rearming(self):
        result, q = self.run_case('conflicting_ready')
        self.assertEqual(result['returncode'], 1)
        self.assertIsNone(q['experimental_window']['T0_ns'])
        self.assertEqual(q['experimental_window']['availability']['fatal'], 'conflicting_ready')

    def test_no_bytes_timeout_preserves_empty_records_without_manufacturing_rows(self):
        result, q = self.run_case('silent')
        self.assertEqual(result['returncode'], 1)
        self.assertEqual(q['experimental_window']['status'], 'no_iniciada')
        self.assertTrue(q['connection_full']['integrity_ok'])
        for rx in control.PORTS:
            self.assertEqual((result['run'] / 'capture' / (rx.lower() + '.serial.log')).read_bytes(), b'')
            self.assertEqual(q['full_session']['receivers'][rx]['valid_rows'], 0)
        manifest = json.loads((result['run'] / 'capture-manifest.json').read_text())
        canonical = canonicalize(result['run'] / 'capture', manifest, json.loads((ROOT / 'config/csi_esp32s3.json').read_text()))
        p = subprocess.run([str(ROOT / '.tools/node-v22.20.0/bin/node'), str(ROOT / 'tools/consume_canonical.mjs')],
            input=json.dumps(canonical), capture_output=True, text=True, check=True)
        consumer = json.loads(p.stdout)
        self.assertTrue(all(not v['frames'] and not v['spectrum'] for v in consumer['views'].values()))

    def test_zero_included_rows_rejects_coverage_even_without_silence_threshold(self):
        result, q = self.run_case('empty_window')
        self.assertEqual(result['returncode'], 1)
        self.assertTrue(q['connection_full']['quality_ok'])
        self.assertFalse(q['experimental_window']['quality_ok'])
        self.assertFalse(q['experimental_window']['coverage_minimum_ok'])
        self.assertTrue(q['experimental_window']['format_continuity_ok'])

    def test_late_processed_error_invalidates_used_gate_and_never_replaces_interval(self):
        result, q = self.run_case('late_error')
        self.assertEqual(result['returncode'], 1)
        self.assertTrue(q['full_session']['coordination_trace_ok'], q)
        self.assertFalse(q['experimental_window']['quality_ok'])
        self.assertTrue(q['experimental_window']['availability']['activation_conflicts'])
        trace = [json.loads(x) for x in (result['run'] / 'capture/availability.events.jsonl').read_text().splitlines()]
        armed = [e for e in trace if e['kind'] == 'armed']
        self.assertEqual(len(armed), 1)
        self.assertEqual(armed[0]['T0_ns'], q['experimental_window']['T0_ns'])
        conflict = q['experimental_window']['availability']['activation_conflicts'][0]
        self.assertLess(int(trace[conflict]['evidence']['returned_ns']), int(armed[0]['T0_ns']))
        self.assertGreaterEqual(int(trace[conflict]['processed_ns']), int(armed[0]['T0_ns']))

    def test_second_open_failure_and_close_error_preserve_errors_and_attempt_both_closes(self):
        for scenario in ('second_open_error', 'close_error'):
            tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
            result = run_pty_v3(Path(tmp.name), scenario=scenario)
            self.assertEqual(result['returncode'], 1)
            self.assertTrue(result['all_ports_closed'])
            self.assertTrue(all(not e['read_active'] for e in result['close_events']))
            self.assertEqual({e['receiver'] for e in result['close_events']}, set(control.PORTS))
            q = json.loads((result['run'] / 'quality.json').read_text())
            self.assertFalse(q['session_quality_ok'])

    def test_error_inside_window_rejects_without_replacing_t0(self):
        result, q = self.run_case('window_error')
        self.assertEqual(result['returncode'], 1)
        self.assertFalse(q['experimental_window']['format_continuity_ok'])
        self.assertFalse(q['experimental_window']['quality_ok'])
        events = [json.loads(x) for x in (result['run'] / 'capture/availability.events.jsonl').read_text().splitlines()]
        self.assertEqual(sum(e['kind'] == 'armed' for e in events), 1)

    def test_pending_line_completes_late_and_is_preserved_but_excluded(self):
        result, q = self.run_case('completion')
        self.assertEqual(result['returncode'], 0, q)
        for rx, item in q['experimental_window']['receivers'].items():
            self.assertTrue(item['stop_quality_ok'])
            self.assertTrue(any(x['inclusion'] == 'at_or_after_deadline' for x in item['index']))
            self.assertGreater(q['full_session']['receivers'][rx]['stop']['completion_bytes'], 0)

    def test_incomplete_stop_preserves_tail_and_rejects_window(self):
        for scenario in ('stop_timeout', 'no_lf'):
            with self.subTest(scenario=scenario):
                result, q = self.run_case(scenario)
                self.assertEqual(result['returncode'], 1)
                self.assertFalse(q['experimental_window']['stop_quality_ok'])
                self.assertTrue(q['connection_full']['integrity_ok'])
                self.assertTrue(all(x['index'][-1]['kind'] == 'fragment' for x in q['experimental_window']['receivers'].values()))

    def test_abort_and_one_receiver_error_close_both_and_reject(self):
        for scenario in ('abort', 'read_error', 'window_reset'):
            with self.subTest(scenario=scenario):
                result, q = self.run_case(scenario)
                self.assertEqual(result['returncode'], 1)
                self.assertFalse(q['experimental_window']['quality_ok'])
                self.assertFalse(q['connection_full']['quality_ok'])

    def test_plan_rejects_changed_parameters_and_v1_v2_fallback(self):
        plan = plan_v3(); control.validate_plan(plan)
        for key in plan['availability_policy']:
            forged = copy.deepcopy(plan); forged['availability_policy'][key] = 'changed'
            with self.subTest(key=key), self.assertRaises(ValueError): control.validate_plan(forged)
        forged = copy.deepcopy(plan); forged['protocol'] = 'controlled_dual_v2'
        with self.assertRaises(ValueError): control.validate_plan(forged)

    def test_forged_t0_with_rehashed_session_does_not_pass_audit(self):
        result, _ = self.run_case()
        root = result['run'] / 'capture'
        manifest = json.loads((result['run'] / 'capture-manifest.json').read_text())
        path = root / 'session.json'; session = json.loads(path.read_text())
        session['controlled']['T0_ns'] = str(int(session['controlled']['T0_ns']) - 1)
        path.write_text(json.dumps(session))
        entry = next(x for x in manifest['files'] if x['name'] == 'session.json')
        entry.update(bytes=path.stat().st_size, sha256=control.sha(path))
        audit = audit_capture(root, manifest)
        self.assertFalse(audit['coordination_trace_ok'])
        self.assertFalse(audit['experimental_window']['quality_ok'])

    def test_canonical_consumer_and_index_keep_both_states_and_all_rows(self):
        result, q = self.run_case('startup_residue')
        manifest = json.loads((result['run'] / 'capture-manifest.json').read_text())
        profile = json.loads((ROOT / 'config/csi_esp32s3.json').read_text())
        canonical = canonicalize(result['run'] / 'capture', manifest, profile)
        self.assertIn('sintética controlada v3', canonical['status_label'])
        self.assertFalse(canonical['strict_quality_ok'])
        self.assertFalse(canonical['connection_full']['quality_ok'])
        self.assertTrue(canonical['experimental_window']['quality_ok'])
        index = json.loads((result['run'] / 'window-index.json').read_text())
        self.assertEqual(index['T0_ns'], q['experimental_window']['T0_ns'])
        for rx, item in canonical['receivers'].items():
            self.assertEqual(len(item['frames']), 5)
            self.assertEqual(index['receivers'][rx], q['experimental_window']['receivers'][rx]['index'])
            self.assertTrue(any(f['received_in_experimental_window'] for f in item['frames']))
            self.assertTrue(any(not f['received_in_experimental_window'] for f in item['frames']))
        p = subprocess.run([str(ROOT / '.tools/node-v22.20.0/bin/node'), str(ROOT / 'tools/consume_canonical.mjs')],
            input=json.dumps(canonical), text=True, capture_output=True, check=True)
        official = json.loads(p.stdout)
        self.assertFalse(official['strict_quality_ok'])
        self.assertEqual(len(official['views']), 4)
        self.assertTrue(all(len(v['frames']) == 5 for v in official['views'].values()))

    def test_default_cli_prepares_v3_without_accessing_devices_or_requiring_environment(self):
        p = subprocess.run([str(ROOT / '.venv/bin/python'), '-B', str(ROOT / 'tools/captura_dual_controlada.py'),
                            '--plan', str(ROOT / 'config/captura_dual_v3_30s.template.json')],
                           text=True, capture_output=True, check=True)
        prepared = json.loads(p.stdout)
        self.assertFalse(prepared['physical_UART_opened'])
        self.assertEqual(prepared['state'], 'PREPARED_NOT_EXECUTED')

    def test_tampered_trace_even_rehashed_cannot_hide_wrong_byte_evidence(self):
        result, _ = self.run_case()
        root = result['run'] / 'capture'
        manifest = json.loads((result['run'] / 'capture-manifest.json').read_text())
        path = root / 'availability.events.jsonl'
        trace = [json.loads(x) for x in path.read_text().splitlines()]
        next(e for e in trace if e['kind'] == 'chunk')['chunk_sha256'] = '0' * 64
        path.write_text(''.join(json.dumps(x) + '\n' for x in trace))
        manifest['coordination_trace'].update(bytes=path.stat().st_size, sha256=control.sha(path))
        audited = audit_capture(root, manifest)
        self.assertFalse(audited['coordination_trace_ok'])
        self.assertFalse(audited['quality_ok'])


if __name__ == '__main__': unittest.main()
