"""Offline regression on preserved capture, only when the local files exist."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from diagnose_capture_boundaries import diagnose

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'results/local/captura-dual-30s-post-reinicio-20261025-intento01'


@unittest.skipUnless((RUN / 'bundle-manifest.json').is_file(), 'Local rejected capture unavailable')
class PreservedBoundaryTests(unittest.TestCase):
    def test_offline_diagnosis_preserves_rejection_bytes_and_never_opens_uart(self):
        files = [p for p in RUN.rglob('*') if p.is_file()]
        before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        with patch('serial.Serial', side_effect=AssertionError('No UART')) as opened:
            result = diagnose(RUN)
            opened.assert_not_called()
        self.assertFalse(result['session_quality_ok'])
        self.assertTrue(result['acquisition_unchanged'])
        self.assertEqual(before, {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
        for rx, offset, prefix in [('RX-01', 129476, '4c1300'), ('RX-02', 130463, '31f2')]:
            item = result['receivers'][rx]
            self.assertEqual(item['prefix_before_rom']['hex'], prefix)
            self.assertEqual(item['tail']['offset'], offset)
            self.assertEqual(item['tail']['bytes'], 129)
            self.assertEqual([e['size'] for e in item['tail']['reads']], [1, 127, 1])
            self.assertEqual(item['non_csi_complete_lines_after_first_csi'], [])
            self.assertEqual(item['invalid_utf8_complete_lines_after_first_csi'], [])
            self.assertTrue(item['classification']['host_stopped_with_line_pending'])
            self.assertTrue(result['audit']['receivers'][rx]['integrity_ok'])

    def test_bundle_mutation_is_refused_before_interpretation(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp)
            (copy / 'bundle-manifest.json').write_bytes((RUN / 'bundle-manifest.json').read_bytes())
            entry = json.loads((copy / 'bundle-manifest.json').read_text())['files'][0]
            target = copy / entry['path']
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b'altered')
            with self.assertRaisesRegex(ValueError, 'integrity mismatch'):
                diagnose(copy)


if __name__ == '__main__':
    unittest.main()
