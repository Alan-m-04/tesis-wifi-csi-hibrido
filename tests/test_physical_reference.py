"""Offline replay of a real reference; never acquires new physical data."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

import validate_capture as audit

ROOT=Path(__file__).resolve().parents[1]
SOURCE=os.environ.get('CSI_PHYSICAL_CAPTURE_DIR')


@unittest.skipUnless(SOURCE, 'Set CSI_PHYSICAL_CAPTURE_DIR to the local ignored physical reference')
class PhysicalReferenceTests(unittest.TestCase):
    def test_real_reference_hashes_counts_and_failure_are_preserved(self):
        manifest=json.loads((ROOT/'data/dual_60s_20261024.manifest.json').read_text())
        r=audit.audit_capture(Path(SOURCE),manifest)
        self.assertTrue(r['manifest_ok']);self.assertFalse(r['new_physical_capture'])
        self.assertEqual(r['source_evidence_type'],'physical_capture');self.assertFalse(r['quality_ok'])
        for rx,count in [('RX-01',292),('RX-02',291)]:
            item=r['receivers'][rx];self.assertEqual(item['valid_rows'],count)
            self.assertTrue(item['integrity_ok']);self.assertTrue(item['raw_frames_equal_csv'])
        self.assertEqual(r['receivers']['RX-01']['counts']['malformed_rows'],1)
        self.assertFalse(r['receivers']['RX-01']['collector_quality_recorded'])
        self.assertTrue(r['receivers']['RX-02']['collector_quality_recorded'])
    def test_real_cli_keeps_failure_exit_code(self):
        p=subprocess.run([sys.executable,'-B',str(ROOT/'src/validate_capture.py'),SOURCE,
                          '--manifest',str(ROOT/'data/dual_60s_20261024.manifest.json')],capture_output=True,text=True)
        self.assertEqual(p.returncode,1);self.assertFalse(json.loads(p.stdout)['quality_ok'])


if __name__=='__main__':unittest.main()
