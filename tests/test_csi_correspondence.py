"""Synthetic mathematical contracts and reviewed upstream pure-parser regression.

JS/Rust formulas are checked as mathematical contracts, not executed runtimes.
No transport or physical acquisition is implemented by these tests.
"""
import importlib.util
import math
from pathlib import Path
import struct
import tempfile
import csv
from test_validate_capture import fixture
from validate_capture import audit_capture
import unittest
from csi_correspondence import (idf_complex, amplitude_phase, documented_ht20_layout,
                                FFT64_ORDER, carrier_role)

SPEC=importlib.util.spec_from_file_location('reviewed_ruview_parser',Path(__file__).parent/'fixtures/ruview_record_parser.py')
RECORDER=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RECORDER)


def synthetic_packet(raw, antennas=1, count=None, freq=2462):
    # Synthetic packet for parser tests only. No serializer or transport for real data.
    count=len(raw)//2//antennas if count is None else count
    return struct.pack('<IBBHIIbbBB',0xC5110001,1,antennas,count,freq,7,-51,-90,0,0)+struct.pack(f'{len(raw)}b',*raw)


class CorrespondenceTests(unittest.TestCase):
    def setUp(self):
        self.meta={'len':256,'sig_mode':1,'bandwidth':0,'secondary_channel':0,'stbc':0}
        self.config=dict(lltf_en=True,htltf_en=True,stbc_htltf2_en=True,ltf_merge_en=True,channel_filter_en=True,manu_scale=False)
    def test_idf_imaginary_first_is_not_real_first(self):
        self.assertEqual(idf_complex([-4,3]),(3-4j,))
        a,p=amplitude_phase(idf_complex([-4,3])[0]);self.assertEqual(a,5);self.assertAlmostEqual(p,math.atan2(-4,3))
    def test_swapping_axes_keeps_amplitude_but_changes_phase(self):
        z=idf_complex([-4,3])[0];wrong=complex(-4,3)
        self.assertEqual(amplitude_phase(z)[0],amplitude_phase(wrong)[0])
        self.assertNotAlmostEqual(amplitude_phase(z)[1],amplitude_phase(wrong)[1])
    def test_conjugation_is_also_hidden_by_amplitude(self):
        z=3-4j;self.assertEqual(abs(z),abs(z.conjugate()))
        self.assertAlmostEqual(amplitude_phase(z)[1],-amplitude_phase(z.conjugate())[1])
    def test_four_quadrants_and_signed_boundaries(self):
        for raw in ([4,3],[4,-3],[-4,-3],[-4,3],[-128,127],[127,-128]):
            with self.subTest(raw=raw):
                z=idf_complex(raw)[0];self.assertEqual(z,complex(raw[1],raw[0]))
                self.assertAlmostEqual(abs(z),math.hypot(*raw))
    def test_invalid_word_masks_two_pairs_without_shifting(self):
        z=idf_complex([1,2,3,4,5,6],True);self.assertEqual(z,(None,None,6+5j))
    def test_zero_has_no_measurable_phase(self):
        self.assertEqual(amplitude_phase(0j),(0,None));self.assertEqual(amplitude_phase(None),(None,None))
    def test_rejects_odd_empty_boolean_and_out_of_range_scalars(self):
        for raw in ([],[1],[True,2],[128,0],[-129,0],[1.,2]):
            with self.subTest(raw=raw),self.assertRaises(ValueError):idf_complex(raw)
    def test_blocks_follow_metadata_and_enabled_fields(self):
        blocks=documented_ht20_layout(self.meta,self.config)
        self.assertEqual([(b['name'],b['byte_start'],b['byte_stop']) for b in blocks],[('LLTF',0,128),('HT-LTF',128,256)])
        self.assertEqual(blocks[0]['indices'],FFT64_ORDER)
    def test_same_length_cannot_establish_phy_or_ltf(self):
        for key,value in [('sig_mode',0),('bandwidth',1),('secondary_channel',1),('stbc',1)]:
            with self.subTest(key=key),self.assertRaises(ValueError):documented_ht20_layout(dict(self.meta,**{key:value}),self.config)
        with self.assertRaises(ValueError):documented_ht20_layout(self.meta,dict(self.config,htltf_en=False))
        with self.assertRaises(ValueError):documented_ht20_layout(self.meta,{})
    def test_index_order_keeps_dc_and_wrap_not_symmetric_no_dc(self):
        self.assertEqual(FFT64_ORDER[0],0);self.assertEqual(FFT64_ORDER[32],-32);self.assertEqual(FFT64_ORDER[-1],-1)
        # Rust generic parser's generated -32..-1,1..32 is not this grid.
        rust_grid=tuple(range(-32,0))+tuple(range(1,33));self.assertNotEqual(rust_grid,FFT64_ORDER)
    def test_nominal_active_guard_pilot_counts_per_ltf(self):
        for name,total,data in [('LLTF',52,48),('HT-LTF',56,52)]:
            roles=[carrier_role(name,k) for k in FFT64_ORDER]
            self.assertEqual(roles.count('data'),data);self.assertEqual(roles.count('pilot'),4)
            self.assertEqual(roles.count('DC'),1);self.assertEqual(roles.count('guard'),63-total)
    def test_upstream_recorder_preserves_payload_and_signed_amplitude(self):
        raw=[-4,3,127,-128];r=RECORDER.parse_csi_packet(synthetic_packet(raw))
        self.assertEqual(r['iq_hex'],struct.pack('4b',*raw).hex());self.assertEqual(r['amplitudes'],[5.,round(math.hypot(127,-128),2)])
        self.assertEqual((r['channel'],r['freq_mhz'],r['n_antennas']),(11,2462,1))
    def test_upstream_recorder_amplitude_cannot_certify_phase(self):
        raw=[-4,3];r=RECORDER.parse_csi_packet(synthetic_packet(raw));self.assertNotIn('phase',r)
        self.assertEqual(r['amplitudes'][0],abs(idf_complex(raw)[0]))
        # Rust/archived Python binary formulas: first byte as I, second as Q.
        wrong_phase=math.atan2(raw[1],raw[0]);self.assertNotAlmostEqual(wrong_phase,amplitude_phase(idf_complex(raw)[0])[1])
    def test_upstream_recorder_rejects_truncated_and_wrong_magic(self):
        packet=synthetic_packet([-4,3]);self.assertIsNone(RECORDER.parse_csi_packet(packet[:-1]))
        self.assertIsNone(RECORDER.parse_csi_packet(b'BAD!'+packet[4:]))
    def test_upstream_antennas_are_count_not_factory_index(self):
        self.assertIsNone(RECORDER.parse_csi_packet(synthetic_packet([1,2],count=1)[:5]+b'\0'+synthetic_packet([1,2])[6:]))
        self.assertEqual(RECORDER.parse_csi_packet(synthetic_packet([1,2]))['n_antennas'],1)
    def test_two_ltf_blocks_are_not_two_antennas(self):
        r=RECORDER.parse_csi_packet(synthetic_packet([1,2]*128));self.assertEqual((r['n_antennas'],r['n_subcarriers']),(1,128))
        # A wire count does not prove 128 unique frequencies. The IDF table model has two 64-bin LTFs.
        b=documented_ht20_layout(self.meta,self.config);self.assertEqual(b[0]['indices'],b[1]['indices'])
    def test_integer_ns_shared_read_is_not_interpolated(self):
        # Multiple frames read in one block legitimately share the same host timestamp.
        stamp=2**54+17;read_times=[stamp,stamp,stamp+1]
        self.assertEqual(read_times[0],read_times[1]);self.assertNotEqual(read_times[-1],int(float(stamp+1)))
    def test_shared_host_read_timestamps_are_valid_without_interpolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=fixture(Path(tmp))
            with (folder/'rx-01.csv').open(newline='') as stream:
                rows=list(csv.DictReader(stream))
            self.assertEqual(len(rows),3)
            self.assertEqual(len({r['host_monotonic_ns'] for r in rows}),1)
            self.assertTrue(audit_capture(folder)['quality_ok'])
    def test_literal_copy_would_reflect_phase(self):
        for imag,real in [(-4,3),(2,-7),(11,5)]:
            true=math.atan2(imag,real);literal=math.atan2(real,imag)
            difference=(literal-(math.pi/2-true)+math.pi)%(2*math.pi)-math.pi
            self.assertAlmostEqual(difference,0)


if __name__=='__main__':unittest.main()
