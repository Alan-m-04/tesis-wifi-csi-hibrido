"""Offline C01 description: boundaries, raw references, masks and immutability."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('consolidar_c01',ROOT/'tools/consolidar_rx02_c01.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def reference(start, returned):
    return dict(first_read_started_ns=str(start),returned_ns=str(returned))


class BoundaryAndRawChecks(unittest.TestCase):
    def test_coverage_includes_edges_and_empty_bins(self):
        result=module.coverage_from_refs([reference(0,10),reference(5_000_000_000,5_000_000_000)],0,30_000_000_000)
        self.assertEqual(result['bins_5s'],[1,1,0,0,0,0])
        self.assertEqual(result['max_gap_ns'],25_000_000_000)
        self.assertEqual(result['gaps_ns'],[10,4_999_999_990,25_000_000_000])

    def test_pre_T0_start_and_exact_T1_are_rejected(self):
        for ref in (reference(-1,1),reference(0,30_000_000_000)):
            with self.subTest(ref=ref),self.assertRaisesRegex(ValueError,'boundary'):
                module.coverage_from_refs([ref],0,30_000_000_000)

    def test_no_empty_shortened_or_reversed_window(self):
        for refs,t1 in (([],30_000_000_000),([reference(0,1)],29_000_000_000),
                        ([reference(0,10),reference(0,2)],30_000_000_000)):
            with self.assertRaises(ValueError):
                module.coverage_from_refs(refs,0,t1)

    def test_raw_hash_and_extent_cannot_be_changed(self):
        raw=b'prefix\nCSI_DATA,test\n'
        line=raw[7:]
        ref=dict(byte_offset=7,byte_end=len(raw),byte_length=len(line),line_sha256=hashlib.sha256(line).hexdigest())
        self.assertEqual(module.verify_reference(raw,ref),line)
        for key,value in (('byte_offset',0),('byte_end',len(raw)+1),('byte_length',1),('line_sha256','0'*64)):
            bad=dict(ref,**{key:value})
            with self.subTest(key=key),self.assertRaises(ValueError):module.verify_reference(raw,bad)


class PhysicalOfflineRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle=ROOT/'results/local/piloto-rx02-r1-C01'
        if not cls.bundle.exists():
            raise unittest.SkipTest('Local physical C01 unavailable; never fabricate or download observations')
        cls.before=module.inventory(cls.bundle)
        # This regression exercises no physical transport path. Opening a UART
        # or discovering devices would fail the test immediately.
        with patch('presence_rx02_uart.preflight_rx02',side_effect=AssertionError('No metadata query during offline audit')), \
             patch('presence_rx02_uart.UartEndpoint.open',side_effect=AssertionError('No UART during offline audit')):
            cls.summary,cls.data,cls.traces,cls.audit=module.consolidate(cls.bundle)

    def test_integrity_replay_and_originals_unchanged(self):
        self.assertTrue(self.audit['integrity_ok'] and self.audit['replay_ok'])
        self.assertEqual(self.before,module.inventory(self.bundle))
        self.assertEqual(self.summary['connection']['total_CSI_rows'],3299)
        self.assertEqual(self.summary['connection']['outside_windows'],3001)

    def test_rejection_is_separate_from_exploratory_windows(self):
        self.assertFalse(self.summary['connection']['result']['quality_ok'])
        self.assertEqual(self.summary['preamble']['status'],'anomalous_uninterpreted')
        for condition,n in (('E',148),('S',150)):
            w=self.summary['windows'][condition]
            self.assertEqual(w['coverage']['included_rows'],n)
            self.assertFalse(w['original_strict_eligible'])
            self.assertTrue(w['exploratory']['eligible'])
            self.assertEqual(w['label']['observation_method'],'operator_declaration')
        self.assertEqual(self.summary['permitted_uses'],dict(calibration=False,training=False,production=False))

    def test_required_mask_missing_does_not_become_zero_or_partial_mean(self):
        frame=copy.deepcopy(self.traces['E'][0]);block=frame['blocks'][0]
        k=block['indices'].index(1)
        block['hardware_valid'][k]=block['cfr_usable'][k]=False
        block['real'][k]=block['imag'][k]=block['amplitude'][k]=None
        mean,reason=module.row_mean(frame,'RX-02')
        self.assertIsNone(mean);self.assertEqual(reason,'required_tone_invalid')

    def test_guard_amplitudes_do_not_change_LLTF52_mean(self):
        frame=copy.deepcopy(self.traces['E'][0]);expected,_=module.row_mean(frame,'RX-02')
        for k,role in enumerate(frame['blocks'][0]['roles']):
            if role in ('guard','DC'):
                frame['blocks'][0]['amplitude'][k]=1e9
        self.assertEqual(module.row_mean(frame,'RX-02'),(expected,None))

    def test_original_authorization_consumed_and_single_selected_close(self):
        self.assertTrue(self.summary['authorization_consumed']['consumed'])
        self.assertFalse(self.summary['authorization_consumed']['retry_allowed'])
        self.assertTrue(self.summary['close_receipt']['selected_confirmed'])
        self.assertEqual(set(self.summary['close_receipt']['closed']),{'RX-02'})
        self.assertEqual(self.summary['runtime']['retry_count'],0)

    def test_plots_preserve_common_axes_and_support(self):
        with tempfile.TemporaryDirectory() as temp:
            summary=copy.deepcopy(self.summary)
            result=module.render_plots(summary,self.data,Path(temp)/'figures')
            self.assertEqual(len(result['figures']),10)
            for figure in result['figures']:
                axes=figure['axes'];self.assertEqual(len(axes),2)
                self.assertEqual(axes[0]['xlim'],axes[1]['xlim'])
                self.assertEqual(axes[0]['ylim'],axes[1]['ylim'])
            self.assertEqual(len(self.data['E']['mean_amplitude']),148)
            self.assertEqual(len(self.data['S']['mean_amplitude']),150)


if __name__=='__main__':unittest.main()
