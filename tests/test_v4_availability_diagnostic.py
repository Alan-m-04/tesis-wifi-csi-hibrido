"""Offline timing/report regression; pipe examples do not attest physical stdin."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import select
import tempfile
import threading
import unittest
from unittest.mock import patch

from test_persistent_presence_v4 import ROOT
from test_v4_exploratory import ExploratoryMemory
from campana_presencia_v4 import fixture_row
from persistent_presence_v4 import POLICY, SECOND
from presence_v4_diagnostics import acquisition_activity, analyze_availability, compare_wall_monotonic
from auditar_exploratorio_v4 import main as audit_main

BUNDLE = ROOT/'results/local/exp-v4-c02-ES-20261101T222444Z-intento-unico'
CONTROL = ROOT/'results/local/preparacion-exp-v4-c02-20261101T222444Z/final-20261103T155915Z'


class AcquisitionContextTests(unittest.TestCase):
    def test_physical_opening_and_offline_audit_are_different_scopes(self):
        report = dict(state=dict(evidence_type='physical_capture',
            closed={}, exploration=dict(identity_bindings={'RX-01': {}, 'RX-02': {}})))
        result = acquisition_activity(report)
        self.assertTrue(result['physical_capture'] and result['physical_UART_opened'])
        self.assertEqual(result['physical_UART_opened_by_receiver'], {'RX-01': True, 'RX-02': True})

    def test_synthetic_opened_pty_is_never_a_physical_uart(self):
        report = dict(state=dict(evidence_type='synthetic_fixture',
            closed={'RX-01': dict(confirmed=True), 'RX-02': dict(confirmed=True)}))
        self.assertFalse(acquisition_activity(report)['physical_UART_opened'])

    def test_physical_intention_without_open_proof_stays_unknown(self):
        report = dict(state=dict(evidence_type='physical_capture', closed={}))
        self.assertTrue(acquisition_activity(report)['physical_capture'])
        self.assertIsNone(acquisition_activity(report)['physical_UART_opened'])

    def test_wall_comparison_does_not_label_unmeasured_time_as_suspend(self):
        result = compare_wall_monotonic(dict(begin_ns=100, last_operation_sample_ns=900000100),
            dict(claimed_utc='2026-11-03T16:00:00+00:00'),
            dict(finished_utc='2026-11-03T16:00:01+00:00'))
        self.assertEqual(result['wall_minus_monotonic_span_ns'], 100_000_000)
        self.assertIn('startup/finalization', result['limitation'])
        self.assertNotIn('suspend_confirmed', result)


class WatchdogTimingTests(unittest.TestCase):
    def test_incomplete_row_near_deadline_does_not_refresh_availability(self):
        h = ExploratoryMemory(); last = h.m.states['RX-01']['last_valid']
        row = fixture_row(h.ids['RX-01'], 700000)
        h.t = last+999_000_000; h.send('RX-01', row[:-1]); h.row('RX-02'); h.call('tick')
        self.assertIsNone(h.m.fatal)
        self.assertEqual(h.m.states['RX-01']['last_valid'], last)
        h.t = last+1_006_375_455; h.row('RX-02'); h.call('tick')
        self.assertEqual(h.m.fatal, 'availability_lost:RX-01')
        self.assertEqual(h.t-h.m.states['RX-02']['last_valid'], 0)
        self.assertEqual(h.m.framers['RX-01'].length, len(row)-1)

    def test_complete_row_before_deadline_refreshes_without_changing_threshold(self):
        h = ExploratoryMemory(); last = h.m.states['RX-01']['last_valid']
        row = fixture_row(h.ids['RX-01'], 700000)
        h.t = last+999_000_000; h.send('RX-01', row[:-1]); h.send('RX-01', b'\n')
        h.row('RX-02'); h.call('tick')
        self.assertIsNone(h.m.fatal)
        self.assertEqual(h.m.states['RX-01']['last_valid'], h.t)
        self.assertEqual(POLICY['freshness_ns'], SECOND)

    def test_exact_threshold_still_uses_strict_greater_than(self):
        h = ExploratoryMemory(); last = h.m.states['RX-01']['last_valid']
        h.t = last+SECOND; h.row('RX-02'); h.call('tick')
        self.assertIsNone(h.m.fatal)
        h.t += 1; h.call('tick')
        self.assertEqual(h.m.fatal, 'availability_lost:RX-01')

    def test_synthetic_host_pause_can_produce_same_reason_without_proving_actual_cause(self):
        h = ExploratoryMemory(); last = h.m.states['RX-01']['last_valid']
        # No host operations at all for >1 s, unlike the recorded attempt.
        h.t = last+1_006_375_455; h.call('tick')
        self.assertEqual(h.m.fatal, 'availability_lost:RX-01')
        self.assertGreater(h.t-h.m.states['RX-02']['last_valid'], SECOND)

    def test_freshness_uses_read_return_not_later_processing_sample(self):
        h = ExploratoryMemory(); last = h.m.states['RX-01']['last_valid']
        h.t = last+1_100_000_001
        h.row('RX-01', start=last+100_000_000, end=last+100_000_000)
        h.call('tick')
        self.assertEqual(h.m.states['RX-01']['last_valid'], last+100_000_000)
        self.assertEqual(h.m.fatal, 'availability_lost:RX-01')

    def test_select_readiness_does_not_guarantee_readline_completeness(self):
        # Process-owned pipe only. This demonstrates a potential blocking
        # mechanism; native TTY mode and stdin calls were not logged physically.
        readfd, writefd = os.pipe(); stream = os.fdopen(readfd, 'r')
        entered, done = threading.Event(), threading.Event(); lines = []
        def reader():
            entered.set(); lines.append(stream.readline()); done.set()
        thread = threading.Thread(target=reader)
        try:
            os.write(writefd, b'slot EXP02')
            self.assertTrue(select.select([stream], [], [], 0)[0])
            thread.start(); self.assertTrue(entered.wait(1))
            self.assertFalse(done.wait(.05))
            os.write(writefd, b'-E\n'); self.assertTrue(done.wait(1))
            self.assertEqual(lines, ['slot EXP02-E\n'])
        finally:
            os.close(writefd)
            if thread.ident is not None:thread.join(1)
            stream.close()


@unittest.skipUnless(BUNDLE.is_dir() and (CONTROL/'intento-consumido.json').is_file(),
                     'Local rejected EXP02 bundle and consumed authorization not available')
class RecordedAvailabilityTests(unittest.TestCase):
    def setUp(self):
        self.before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                       for directory in (BUNDLE, CONTROL) for p in directory.rglob('*') if p.is_file()}

    def tearDown(self):
        self.assertEqual(self.before, {name: hashlib.sha256(Path(name).read_bytes()).hexdigest()
                                      for name in self.before})

    def test_exact_trigger_clocks_progress_and_partial_header(self):
        with patch('serial.Serial', side_effect=AssertionError('No UART')):
            result = analyze_availability(BUNDLE, CONTROL)
        self.assertTrue(result['integrity_ok'] and result['replay_ok'])
        self.assertEqual(result['suspension']['reason'], 'availability_lost:RX-01')
        self.assertEqual(result['suspension']['now_ns'], 173530748851912)
        rx1, rx2 = result['receivers']['RX-01'], result['receivers']['RX-02']
        self.assertEqual(rx1['last_valid_age_at_suspension_ns'], 1_006_375_455)
        self.assertEqual(rx2['last_valid_age_at_suspension_ns'], 5_673_129)
        self.assertEqual(rx1['valid_complete_rows'], 17)
        self.assertEqual(rx2['valid_complete_rows'], 32)
        self.assertEqual(len(rx1['reads_after_last_valid']), 4)
        self.assertEqual(rx1['residual_after_last_valid']['bytes'], 768)
        partial = rx1['residual_after_last_valid']['literal_partial_header']
        self.assertEqual(partial['id'], 17); self.assertEqual(partial['local_timestamp'], 6864325)
        self.assertFalse(partial['validated_as_CSI'] or partial['complete_row_counted'])
        self.assertEqual(result['causal_interval']['ticks'], 107)
        self.assertEqual(result['causal_interval']['operation_gaps']['max_ns'], 10_926_942)
        self.assertEqual(result['windows'], [])
        wall = result['wall_monotonic_comparison']
        self.assertEqual(wall['wall_span_ns'], 11_108_848_000)
        self.assertEqual(wall['recorded_monotonic_span_ns'], 10_965_198_560)
        self.assertEqual(wall['wall_minus_monotonic_span_ns'], 143_649_440)

    def test_new_report_amends_scopes_without_overwriting_original(self):
        original = json.loads((CONTROL/'auditoria-compacta.json').read_text())
        self.assertEqual(original['evidence_type'], 'physical_capture')
        self.assertFalse(original['physical_UART_opened'])
        output = io.StringIO()
        with contextlib.redirect_stdout(output), patch('serial.Serial', side_effect=AssertionError('No UART')):
            self.assertEqual(audit_main(['--bundle', str(BUNDLE)]), 1)
        corrected = json.loads(output.getvalue())
        self.assertEqual(corrected['reporting_schema'], 'tesis-v4-exploratory-audit-report-v2')
        self.assertTrue(corrected['acquisition']['physical_capture'])
        self.assertTrue(corrected['acquisition']['physical_UART_opened'])
        self.assertFalse(corrected['audit_activity']['physical_UART_opened'])
        self.assertNotIn('physical_UART_opened', corrected)
        self.assertEqual(corrected['connection'], original['connection'])
        self.assertEqual(corrected['exploratory_eligibility'], original['exploratory_eligibility'])


if __name__ == '__main__':unittest.main()
