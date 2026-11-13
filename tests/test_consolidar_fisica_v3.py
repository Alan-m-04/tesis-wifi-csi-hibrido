"""Read-only consolidation checks against original local evidence, never UART."""
import copy
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('consolidation', ROOT / 'tools/consolidar_fisica_v3.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@unittest.skipUnless(module.RUN.is_dir(), 'Local physical v3 evidence is deliberately not distributed in Git')
class ConsolidationChecks(unittest.TestCase):
    def test_reconstructed_summary_matches_sources_and_does_not_open_devices_or_change_inputs(self):
        roots = [module.RUN, module.CONTROL]
        before = {p: module.ref(p)['sha256'] for root in roots for p in root.rglob('*') if p.is_file()}
        with patch('serial.Serial', side_effect=AssertionError('No UART')) as opened, \
                patch('capture_csi_multi.port_identity', side_effect=AssertionError('No discovery')):
            report = module.consolidate()
            opened.assert_not_called()
        self.assertEqual(report, module.load(ROOT / 'results/CAPTURA_FISICA_V3.resumen.json'))
        self.assertFalse(report['global_quality_ok'])
        self.assertFalse(report['connection_full']['quality_ok'])
        self.assertTrue(report['experimental_window']['quality_ok'])
        self.assertFalse(report['hash_verification']['auxiliary_control_manifest_literal_valid'])
        self.assertTrue(all(module.ref(p)['sha256'] == h for p, h in before.items()))

    def test_auxiliary_exception_does_not_waive_any_other_hash_mismatch(self):
        original = module.load
        path = module.CONTROL / 'control-manifest.json'
        def corrupt(p):
            value = original(p)
            if p == path:
                value = copy.deepcopy(value)
                next(x for x in value['files'] if x['path'] != path.name)['sha256'] = '0' * 64
            return value
        with patch.object(module, 'load', side_effect=corrupt), self.assertRaisesRegex(ValueError, 'Hash/size mismatch'):
            module.consolidate()

    def test_acquisition_bundle_byte_mismatch_stops_consolidation(self):
        original = module.load
        def corrupt(p):
            value = original(p)
            if p == module.RUN / 'bundle-manifest.json':
                value = copy.deepcopy(value); value['files'][0]['bytes'] += 1
            return value
        with patch.object(module, 'load', side_effect=corrupt), self.assertRaisesRegex(ValueError, 'Hash/size mismatch'):
            module.consolidate()

    def test_modified_published_summary_is_rejected_by_check_command(self):
        original = module.load
        target = ROOT / 'results/CAPTURA_FISICA_V3.resumen.json'
        def corrupt(p):
            value = original(p)
            if p == target:
                value = copy.deepcopy(value); value['T0_ns'] = str(int(value['T0_ns']) - 1)
            return value
        with patch.object(module, 'load', side_effect=corrupt), patch.object(sys, 'argv', ['check', '--check', str(target)]), \
                redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as stopped:
            module.main()
        self.assertEqual(stopped.exception.code, 2)


if __name__ == '__main__': unittest.main()
