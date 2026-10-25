"""Offline replay of a real reference; never acquires new physical data."""
import json
import csv
from csi_correspondence import idf_complex, documented_ht20_layout
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
        self.assertIsNone(r['postflight_identity_ok']);self.assertIsNone(r['receivers']['RX-01']['read_ledger_ok'])
        self.assertEqual(r['source_evidence_type'],'physical_capture');self.assertFalse(r['quality_ok'])
        for rx,count in [('RX-01',292),('RX-02',291)]:
            item=r['receivers'][rx];self.assertEqual(item['valid_rows'],count)
            self.assertTrue(item['integrity_ok']);self.assertTrue(item['raw_frames_equal_csv'])
        self.assertEqual(r['receivers']['RX-01']['counts']['malformed_rows'],1)
        self.assertFalse(r['receivers']['RX-01']['collector_quality_recorded'])
        self.assertTrue(r['receivers']['RX-02']['collector_quality_recorded'])
    def test_real_matrices_keep_byte_order_and_metadata_conditional_blocks(self):
        config=json.loads((ROOT/'config/csi_esp32s3.json').read_text())['firmware_ltf_config']
        for rx,count in [('rx-01',292),('rx-02',291)]:
            with (Path(SOURCE)/(rx+'.csv')).open(newline='') as stream:
                rows=list(csv.DictReader(stream))
            self.assertEqual(len(rows),count)
            for row in rows:
                raw=json.loads(row['data']);z=idf_complex(raw,bool(int(row['first_word_invalid'])))
                self.assertEqual([v for pair in z for v in (int(pair.imag),int(pair.real))],raw)
                blocks=documented_ht20_layout({k:int(row[k]) for k in ('len','sig_mode','bandwidth','secondary_channel','stbc')},config)
                self.assertEqual(len(blocks),2)
    def test_real_cli_keeps_failure_exit_code(self):
        p=subprocess.run([sys.executable,'-B',str(ROOT/'src/validate_capture.py'),SOURCE,
                          '--manifest',str(ROOT/'data/dual_60s_20261024.manifest.json')],capture_output=True,text=True)
        self.assertEqual(p.returncode,1);self.assertFalse(json.loads(p.stdout)['quality_ok'])


if __name__=='__main__':unittest.main()
