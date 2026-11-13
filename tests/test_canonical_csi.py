"""Synthetic source/traceability regressions; no physical UART."""
import base64
import copy
import json
from pathlib import Path
import tempfile
import unittest
from canonical_csi import canonicalize, canonical_block, stringify_ns, digest
from csi_correspondence import documented_ht20_layout
from test_validate_capture import fixture

ROOT=Path(__file__).resolve().parents[1]
PROFILE=json.loads((ROOT/'config/csi_esp32s3.json').read_text())


class CanonicalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.folder=fixture(Path(self.tmp.name))
    def test_all_31_fields_and_original_csv_row_are_preserved(self):
        c=canonicalize(self.folder,None,PROFILE);f=c['receivers']['RX-01']['frames'][0]
        self.assertEqual(len(f['original_fields']),31);self.assertEqual(f['csv_line_1based'],2)
        self.assertEqual(f['receiver_id'],'RX-01');self.assertEqual(f['usb_serial'],'5C93199744')
    def test_raw_line_hash_base64_and_byte_offset_recover_exact_original(self):
        c=canonicalize(self.folder,None,PROFILE)
        for r in c['receivers'].values():
            for f in r['frames']:
                ref=f['raw_reference'];raw=(self.folder/ref['file']).read_bytes()
                segment=raw[ref['byte_offset']:ref['byte_offset']+ref['byte_length']]
                self.assertEqual(segment,base64.b64decode(ref['line_base64']));self.assertEqual(digest(segment),ref['line_sha256'])
    def test_both_ltf_blocks_keep_distinct_indices_and_offsets(self):
        f=canonicalize(self.folder,None,PROFILE)['receivers']['RX-01']['frames'][0]
        self.assertEqual([(b['ltf'],b['byte_start'],b['byte_stop']) for b in f['blocks']],[('LLTF',0,128),('HT-LTF',128,256)])
        self.assertEqual(f['blocks'][0]['indices'],f['blocks'][1]['indices'])
    def test_invalid_first_word_masks_only_two_global_pairs(self):
        m={'sig_mode':1,'bandwidth':0,'secondary_channel':0,'stbc':0,'len':256}
        blocks=documented_ht20_layout(m,PROFILE['firmware_ltf_config']);raw=[3,4]*128
        a=canonical_block(raw,blocks[0],True);b=canonical_block(raw,blocks[1],True)
        self.assertEqual(a['real'][:3],[None,None,4]);self.assertEqual(a['hardware_valid'][:3],[False,False,True])
        self.assertTrue(all(b['hardware_valid']));self.assertEqual(raw[:4],[3,4,3,4])
    def test_zero_has_no_phase_but_is_not_hardware_invalid(self):
        m={'sig_mode':1,'bandwidth':0,'secondary_channel':0,'stbc':0,'len':256}
        b=canonical_block([0]*256,documented_ht20_layout(m,PROFILE['firmware_ltf_config'])[0],False)
        self.assertTrue(all(b['hardware_valid']));self.assertTrue(all(v is None for v in b['phase_rad']))
        self.assertEqual(b['amplitude'],[0]*64)
    def test_guard_dc_and_hardware_validity_remain_distinct(self):
        f=canonicalize(self.folder,None,PROFILE)['receivers']['RX-01']['frames'][0]
        b=f['blocks'][0];self.assertEqual(b['roles'][0],'DC');self.assertTrue(b['hardware_valid'][0]);self.assertFalse(b['cfr_usable'][0])
        self.assertEqual(sum(b['cfr_usable']),52)
    def test_host_read_batch_timestamps_remain_shared_and_utc_text_unchanged(self):
        c=canonicalize(self.folder,None,PROFILE);frames=c['receivers']['RX-01']['frames']
        self.assertEqual(len({f['host_monotonic_ns'] for f in frames}),1)
        for f in frames:self.assertEqual(f['host_timestamp_utc'],f['original_fields']['host_timestamp_utc'])
    def test_nested_nanoseconds_keep_exact_integer_precision_as_strings(self):
        n=2**60+17;r=stringify_ns({'started_monotonic_ns':n,'results':[{'first_host_monotonic_ns':n}]})
        self.assertEqual(r['started_monotonic_ns'],str(n));self.assertEqual(r['results'][0]['first_host_monotonic_ns'],str(n))
    def test_source_files_are_unchanged_by_canonicalization(self):
        before={f.name:digest(f.read_bytes()) for f in self.folder.iterdir()};canonicalize(self.folder,None,PROFILE)
        self.assertEqual(before,{f.name:digest(f.read_bytes()) for f in self.folder.iterdir()})
    def test_inconsistent_raw_and_csv_cannot_be_exported_as_canonical(self):
        p=self.folder/'rx-01.serial.log';p.write_bytes(p.read_bytes()+b'tamper\n')
        with self.assertRaises(ValueError):canonicalize(self.folder,None,PROFILE)
    def test_json_roundtrip_preserves_unknowns_and_labels(self):
        c=canonicalize(self.folder,None,PROFILE);self.assertEqual(json.loads(json.dumps(c)),c)
        self.assertTrue(c['diagnostic_only']);self.assertEqual(c['evidence_type'],'synthetic_fixture')
    def test_profile_cannot_silently_relabel_target(self):
        p=copy.deepcopy(PROFILE);p['target']='other'
        with self.assertRaises(ValueError):canonicalize(self.folder,None,p)


if __name__=='__main__':unittest.main()
