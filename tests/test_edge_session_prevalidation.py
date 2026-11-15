"""Synthetic native R5 replay and explicit fixtures; no physical data or UART."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tools'), str(ROOT / 'tests')]
from edge_session_prevalidation import prevalidate
from edge_presence_synthetic import write_dataset
import prevalidar_captura_offline as cli


def native_r5_fixture(output, *, preamble=False):
    """Owned PTY, invented CSI, stepped clock and recorded sounds, no real hardware."""
    from test_presence_rx02 import Rig, boot, PREFIX
    from rx02_devrep_r5_n01.contract import runtime_plan
    from rx02_devrep_r5_n01.session import DevrepSession
    from rx02_devrep.coordinator import Coordinator
    from devrep_keyboard_prompt import pending_declaration
    from preflight_devrep_r5 import template
    rig = Rig()
    session = None
    try:
        rig.pair.fixture_write((PREFIX if preamble else b'') + boot('RX-02'))
        session = DevrepSession(rig.output, runtime_plan(template()), test_backend=rig.backend, clock=rig.clock)
        coordinator = Coordinator(session)
        for _ in range(2300):
            rig.step(session)
            coordinator.poll()
            pending = pending_declaration(session.machine)
            if pending:
                coordinator.operator(['declare', pending[0], 'yes'])
            if coordinator.done: break
        else: raise AssertionError('Synthetic R5 did not finish')
        session.finalize()
        shutil.copytree(rig.output, output)
    finally:
        if session:
            if not session.read_loop_stopped: session.close()
            session.journal.close_files()
            session._finish_notifier()
        rig.dispose()


class PrevalidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='edge-prevalidation-')
        cls.root = Path(cls.tmp.name)
        native_r5_fixture(cls.root / 'valid')
        native_r5_fixture(cls.root / 'preamble', preamble=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def fixture(self, name):
        path = self.root / name
        shutil.copytree(self.root / 'valid', path)
        return path

    def test_one_native_synthetic_connection_runs_end_to_end_without_model_permission(self):
        path = self.root / 'valid'
        with patch('serial.Serial', side_effect=AssertionError('No UART during reading')):
            result = prevalidate(path)
        self.assertTrue(result['accepted'], result['rejection_reasons'])
        self.assertTrue(result['native_audit_executed'])
        self.assertEqual(result['evidence_type'], 'synthetic_fixture')
        self.assertTrue(result['sources_unchanged'])
        self.assertTrue(result['integrity_ok'] and result['replay_ok'] and result['labels_ok'])
        self.assertTrue(result['strict_quality_ok'] and result['close_ok'] and result['eligibility_ok'])
        self.assertFalse(result['original_permitted_uses']['training'])
        self.assertFalse(result['model_training_executed'] or result['inference_executed'])
        self.assertFalse(result['model_evaluation_ready'])
        self.assertEqual({w['condition'] for w in result['windows']}, {'E', 'S'})
        self.assertTrue(all(w['features']['n'] >= 120 for w in result['windows']))

    def test_preamble_rejection_remains_exact_even_when_features_and_integrity_pass(self):
        result = prevalidate(self.root / 'preamble')
        self.assertFalse(result['accepted'])
        reason = next(r for r in result['rejection_reasons'] if r['code'] == 'strict_connection_rejected')
        self.assertIn('preamble_anomaly:RX-02', reason['detail'])
        self.assertTrue(result['features_ok'] and result['integrity_ok'])
        self.assertTrue(result['sources_unchanged'])

    def test_altered_raw_reports_native_manifest_failure_without_changing_inputs(self):
        path = self.fixture('tampered')
        raw = path / 'rx-02.serial.log'; raw.write_bytes(raw.read_bytes() + b'altered\n')
        before = raw.read_bytes()
        result = prevalidate(path)
        self.assertFalse(result['accepted'])
        self.assertEqual(result['rejection_reasons'][0]['code'], 'native_audit_failed')
        self.assertIn('Manifest integrity failure: rx-02.serial.log', result['rejection_reasons'][0]['detail'])
        self.assertEqual(before, raw.read_bytes())

    def test_missing_bundle_unsupported_revision_and_reserve_are_explicit(self):
        missing = prevalidate(self.root / 'missing')
        self.assertFalse(missing['accepted'])
        path = self.fixture('unsupported')
        source = path / 'provenance.json'; p = json.loads(source.read_text())
        p['integration_revision'] = 'unsupported'; source.write_text(json.dumps(p))
        result = prevalidate(path)
        self.assertIn('unsupported_native_revision:unsupported', result['rejection_reasons'][0]['detail'])
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('Reserve must not open')):
            result = prevalidate(self.root / 'RX02-C04')
        self.assertFalse(result['accepted'])
        self.assertEqual(result['rejection_reasons'][0]['code'], 'input_failed')

    def decision_fixture(self, name, *, bad_mask=False):
        manifest = write_dataset(self.root / name)
        path = manifest.parent / ('SYNTHETIC-EVAL-03' if bad_mask else 'SYNTHETIC-EVAL-01')
        audit = json.loads((path / 'audit-fixture.json').read_text())
        audit['state']['connection']['quality_ok'] = True
        audit['state']['closed'] = {'RX-02': dict(confirmed=True, reader_stopped=True, error=None)}
        for window in audit['state']['windows']: window['eligible'] = True
        return path, audit

    def test_renamed_reserved_session_is_blocked_before_raw_inventory(self):
        path = self.fixture('renamed-reserve')
        source = path / 'plan.json'; plan = json.loads(source.read_text())
        for change in (dict(connection_id='RX02-C04'), dict(future_partition='evaluation_future_sealed')):
            source.write_text(json.dumps(dict(plan, **change)))
            with patch('edge_session_prevalidation.inventory', side_effect=AssertionError('No raw read')):
                result = prevalidate(path)
            self.assertFalse(result['accepted'])
            self.assertEqual(result['rejection_reasons'][0]['code'], 'input_failed')

    def save_decision_fixture(self, path, audit):
        source = path / 'audit-fixture.json'; source.write_text(json.dumps(audit))
        p = path / 'sources.json'; data = json.loads(p.read_text())
        data['audit']['sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
        p.write_text(json.dumps(data))

    def test_uncertain_labels_ineligibility_and_missing_masks_never_fit_model(self):
        for defect in ('label', 'eligibility', 'mask'):
            path, audit = self.decision_fixture(defect, bad_mask=defect == 'mask')
            if defect == 'label': audit['state']['windows'][0]['label']['status'] = 'uncertain'
            elif defect == 'eligibility': audit['exploratory_eligibility']['windows'][0].update(eligible=False, reasons=['synthetic_coverage_failed'])
            self.save_decision_fixture(path, audit)
            with patch('ruview_presence_port.PresenceSpecialistPort.train', side_effect=AssertionError('No training')):
                result = prevalidate(path, synthetic_fixture=True)
            self.assertFalse(result['accepted'])
            self.assertFalse(result['native_audit_executed'])
            self.assertTrue(result['sources_unchanged'])
            if defect == 'eligibility': self.assertIn('synthetic_coverage_failed', str(result['rejection_reasons']))
            if defect == 'mask': self.assertIn('required_tone_invalid', str(result['rejection_reasons']))

    def test_native_mode_never_promotes_an_injected_audit_fixture(self):
        path, audit = self.decision_fixture('synthetic-only')
        self.save_decision_fixture(path, audit)
        self.assertFalse(prevalidate(path)['accepted'])
        result = prevalidate(path, synthetic_fixture=True)
        self.assertTrue(result['accepted'], result['rejection_reasons'])
        self.assertFalse(result['native_audit_executed'])

    def test_cli_emits_rejection_report_and_preserves_existing_output(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'results/local', prefix='prevalidate-cli-') as tmp:
            output = Path(tmp) / 'new'
            with patch.object(sys, 'addaudithook'), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main(['--bundle', str(self.root / 'preamble'), '--output-new', str(output)]), 2)
                before = (output / 'prevalidation.json').read_bytes()
                self.assertEqual(cli.main(['--bundle', str(self.root / 'valid'), '--output-new', str(output)]), 2)
            self.assertEqual(before, (output / 'prevalidation.json').read_bytes())


if __name__ == '__main__': unittest.main()
