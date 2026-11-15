"""Descriptive comparison uses only audited original memberships and fixed LLTF52."""
import copy
import json
import math
from pathlib import Path
import statistics
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'tools')]
import consolidar_c03_comparar_c01 as m


class ExistingC03Comparison(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before={str(p):m.inventory(p) for p in (m.C01,m.C02,m.C03)}
        with patch('rx02_c03.uart.preflight_rx02',side_effect=AssertionError('No metadata')),patch('presence_v4_uart.UartEndpoint.open',side_effect=AssertionError('No UART')):
            cls.a,cls.ad,cls.at,cls.aa=m.c01.consolidate(m.C01)
            cls.b,cls.bd,cls.bt,cls.ba=m.consolidate_c03()
        cls.comparison=m.comparison(cls.a,cls.b)

    def test_counts_original_coverage_masks_and_human_labels(self):
        self.assertEqual(self.b['connection']['total_CSI_rows'],7414)
        self.assertEqual(self.b['connection']['outside_windows'],7125)
        for cond,n,bins in [('E',143,[24,24,25,22,25,23]),('S',146,[24,26,23,26,23,24])]:
            w=self.b['windows'][cond]
            self.assertEqual(w['coverage']['included_rows'],n)
            self.assertEqual(w['coverage']['bins_5s'],bins)
            self.assertEqual(sum(w['coverage']['gaps_ns']),30_000_000_000)
            self.assertTrue(w['exploratory']['eligible'])
            self.assertFalse(w['original_strict_eligible'])
            self.assertEqual(w['label']['observation_method'],'operator_declaration')
            self.assertEqual(w['label']['timing_uncertainty'],'unknown')
            self.assertEqual(w['LLTF52']['rows_with_complete_active_mask'],n)
            self.assertEqual(w['LLTF52']['frame_mean_amplitude']['n'],n)
        self.assertEqual(self.a['windows']['E']['coverage']['included_rows'],148)
        self.assertEqual(self.a['windows']['S']['coverage']['included_rows'],150)

    def test_independent_full52_amplitude_and_population_variability(self):
        frame=self.bt['E'][0];values=json.loads(frame['original_fields']['data'])
        indices=list(range(32))+list(range(-32,0));active=[i for i,k in enumerate(indices) if 1<=abs(k)<=26]
        expected=statistics.fmean(math.hypot(values[2*i],values[2*i+1]) for i in active)
        self.assertEqual(expected,self.bd['E']['mean_amplitude'][0])
        b=frame['blocks'][0];index=b['indices'].index(-26)
        tone=next(x for x in self.b['windows']['E']['LLTF52']['per_tone'] if x['index']==-26)
        self.assertEqual(tone['std_population'],statistics.pstdev(f['blocks'][0]['amplitude'][index] for f in self.bt['E']))

    def test_missing_required_tone_does_not_produce_partial_window_mean(self):
        original=m.c01.frame_from_reference;first=[True]
        def masked(*args,**kwargs):
            frame,mean,reason=original(*args,**kwargs)
            if first[0]:
                first[0]=False;block=frame['blocks'][0];i=block['indices'].index(1)
                block['hardware_valid'][i]=block['cfr_usable'][i]=False
                block['real'][i]=block['imag'][i]=block['amplitude'][i]=None
                mean,reason=None,'required_tone_invalid'
            return frame,mean,reason
        with patch.object(m.c01,'frame_from_reference',side_effect=masked):
            windows,data,_=m.describe_windows(m.C03,self.ba)
        self.assertEqual(windows['E']['mask_status'],'incomplete')
        self.assertIsNone(windows['E']['LLTF52']['frame_mean_amplitude']['mean'])
        self.assertIsNone(windows['E']['LLTF52']['mean_per_tone_temporal_std'])
        self.assertEqual(len(data['E']['mean_amplitude']),143)
        self.assertIsNone(data['E']['mean_amplitude'][0])
        self.assertEqual(windows['E']['coverage']['included_rows'],143)

    def test_comparison_keeps_separate_partitions_and_fixed_metrics(self):
        self.assertTrue(all(self.comparison['fixed_plan_fields_equal'].values()))
        self.assertEqual([p['group'] for p in self.comparison['partition_groups']],['RX02-C01','RX02-C03'])
        self.assertFalse(self.comparison['reserve_C04_C06_observations_opened'])
        self.assertFalse(self.comparison['causal_presence_effect_established'])
        self.assertEqual(self.b['captured_plan']['unused_receiver']['action'],'remain_disconnected_uart_unopened')
        self.assertEqual(self.a['captured_plan']['unused_receiver']['action'],'leave_connected_fixed_uart_unopened')
        self.assertFalse(any(self.comparison['permitted_uses'].values()))
        expected=self.b['windows']['S']['rssi_dBm']['mean']-self.a['windows']['S']['rssi_dBm']['mean']
        self.assertEqual(self.comparison['conditions']['S']['C03_minus_C01']['rssi_mean_dB'],expected)

    def test_checkpoint_consumption_close_and_all_originals_unchanged(self):
        self.assertEqual(self.b['checkpoint_status']['checkpoints'],495)
        self.assertEqual(self.b['checkpoint_status']['pending_ops_bytes'],0)
        self.assertEqual(self.b['checkpoint_status']['raw_syncs'],50885)
        self.assertTrue(self.b['close_receipt']['selected_confirmed'])
        self.assertEqual(self.b['connection']['tails']['RX-02']['bytes'],0)
        self.assertTrue(self.b['authorization_consumed']['consumed'])
        self.assertEqual({str(p):m.inventory(p) for p in (m.C01,m.C02,m.C03)},self.before)

    def test_four_panel_figures_use_identical_axes_and_preserve_support(self):
        with tempfile.TemporaryDirectory() as tmp:
            result=m.render_plots({'C01':self.a,'C03':self.b},{'C01':self.ad,'C03':self.bd},Path(tmp)/'figures')
        self.assertEqual(len(result['figures']),10)
        for figure in result['figures']:
            self.assertEqual(len(figure['axes']),4)
            self.assertTrue(all(ax['xlim']==figure['axes'][0]['xlim'] and ax['ylim']==figure['axes'][0]['ylim'] for ax in figure['axes']))

    def test_C02_remains_rejected_without_relabeling(self):
        report=m.audit_rx02(m.C02)
        self.assertEqual(report['state']['fatal'],'availability_gap:RX-02')
        self.assertEqual(report['state']['tails']['RX-02']['bytes'],349)
        self.assertEqual(report['state']['windows'][0]['label']['status'],'pending')
        self.assertEqual(report['state']['partition_group'],'RX02-C02')

    def test_existing_output_rejected_and_reserve_inputs_not_accepted(self):
        with patch.object(m.c01,'consolidate',side_effect=AssertionError('Must reject before reading')):
            with self.assertRaises(ValueError):m.main(['--output-new',str(m.C03)])
            with self.assertRaises(SystemExit):m.main(['--output-new','new','--c04','forbidden'])
