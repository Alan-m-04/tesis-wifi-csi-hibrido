"""Offline series comparison and common plotting scales; never touches UART."""
import contextlib
import copy
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools')]
from antenna_aba_analysis import quantile,rssi_description,contrasts,build_series,render_plots,PHASES
from comparar_antena_aba import consolidate,main
from presence_v4_journal import digest


class StatisticalTests(unittest.TestCase):
    def test_RSSI_quantiles_keep_negative_values_and_sample_count(self):
        values=[-60]*3+[-58]*5+[-56]*2
        d=rssi_description(values)
        self.assertEqual((d['count'],d['p10'],d['median'],d['p90']),(10,-60,-58,-56))
        self.assertEqual(sum(d['histogram'].values()),10)
        for values,p in (([],.5),([1],0),([1],1.1)):
            with self.assertRaises(ValueError):quantile(values,p)

    def test_descriptive_contrast_keeps_both_A_results(self):
        result=contrasts(dict(A1=294,B=213,A2=201))
        self.assertEqual((result['B_minus_A1'],result['A2_minus_A1'],result['A2_minus_B']),(-81,-93,-12))
        self.assertEqual(result['B_minus_mean_of_A1_A2'],-34.5)
        self.assertIn('neither causal',result['interpretation'])

    def test_distinct_bundles_required_before_reading(self):
        with self.assertRaises(ValueError):build_series(dict(A1='/tmp/same',B='/tmp/same',A2='/tmp/third'))

    def test_output_inside_original_bundle_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp,contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                main(['--bundles-root',tmp,'--output-new',tmp+'/continuidad-antena-aba-r3-B/analysis'])
            self.assertFalse((Path(tmp)/'continuidad-antena-aba-r3-B').exists())

    def test_existing_report_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp,contextlib.redirect_stderr(io.StringIO()):
            p=Path(tmp)/'report';p.write_text('original')
            with self.assertRaises(SystemExit):main(['--output-new',str(p)])
            self.assertEqual(p.read_text(),'original')


AVAILABLE=all((ROOT/'results/local'/('continuidad-antena-aba-r3-'+p)/'manifest.json').exists() for p in PHASES)


@unittest.skipUnless(AVAILABLE,'Physical bundles local only; tests never acquire or download them')
class ExistingSeriesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundles={p:ROOT/'results/local'/('continuidad-antena-aba-r3-'+p) for p in PHASES}
        cls.summary,cls.data=consolidate(ROOT/'results/local',ROOT/'results/local/preparacion-antena-aba-r3')

    def test_real_series_counts_gaps_RSSI_and_independent_clocks(self):
        summary=self.summary
        self.assertEqual([summary['phases'][p]['receivers']['RX-01']['valid_complete_rows_common'] for p in PHASES],[294,213,201])
        self.assertEqual([summary['phases'][p]['receivers']['RX-02']['valid_complete_rows_common'] for p in PHASES],[296,291,291])
        self.assertTrue(summary['A2_did_not_reproduce_A1'])
        self.assertFalse(summary['causal_orientation_effect_established'])
        for phase in PHASES:
            self.assertTrue(summary['phases'][phase]['authorization']['consumed'])
            for rx in ('RX-01','RX-02'):
                s=summary['phases'][phase]['receivers'][rx];data=self.data[phase][rx];n=s['valid_complete_rows_common']
                self.assertEqual((len(data['points']),len(data['host_gaps_ms']),len(data['local_gaps_ms'])),(n,n-1,n-1))
                self.assertEqual(s['rssi']['count'],n)
                self.assertEqual(s['callback_ids'],dict(first=0,last=n-1,deltas={'1':n-1}))
                self.assertEqual(s['queue_drops_values'],[0])
                self.assertFalse(any(s['continuity_flags'].values()))
                self.assertEqual(s['tail']['byte_length'],0)
        self.assertGreater(summary['contrasts']['RX-01']['RSSI_mean_dBm']['A2_minus_A1'],7)
        self.assertGreater(summary['contrasts']['RX-02']['RSSI_mean_dBm']['A2_minus_A1'],3)

    def test_read_only_no_serial_construction_or_original_change(self):
        before={str(p):digest(p) for b in self.bundles.values() for p in b.iterdir() if p.is_file()}
        with patch('serial.Serial',side_effect=AssertionError('No UART')), \
             patch('presence_v4_uart.identity',side_effect=AssertionError('No discovery')):
            summary,_=build_series(self.bundles)
        self.assertFalse(summary['analysis_activity']['physical_UART_opened'])
        self.assertEqual(before,{str(p):digest(p) for b in self.bundles.values() for p in b.iterdir() if p.is_file()})

    def test_tampered_B_prevents_series_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            tampered=Path(tmp)/'B';shutil.copytree(self.bundles['B'],tampered)
            with (tampered/'rx-01.serial.log').open('ab') as f:f.write(b'changed')
            bundles=dict(self.bundles,B=tampered)
            with self.assertRaisesRegex(ValueError,'hash mismatch'):build_series(bundles)

    def test_rendered_common_axes_and_figure_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'figures';manifest=render_plots(self.summary,self.data,folder)
            self.assertEqual(len(manifest['files']),10)
            for item in manifest['files']:
                self.assertEqual(digest(folder/item['path']),item['sha256'])
                if item['path'].endswith('.svg'):
                    self.assertTrue(ET.parse(folder/item['path']).getroot().tag.endswith('svg'))
            axes=next(x['axes'] for x in manifest['files'] if x['path']=='huecos_tiempo.svg')
            self.assertTrue(all(a['xlim']==[0,60] and a['ylim']==[0,1500] for a in axes))
            rssi=next(x['axes'] for x in manifest['files'] if x['path']=='rssi.svg')
            self.assertEqual(rssi[0]['ylim'],rssi[2]['ylim'])
            self.assertEqual(rssi[1]['xlim'],rssi[3]['xlim'])

    def test_plot_refuses_silently_clipped_observation(self):
        data=copy.deepcopy(self.data);data['A2']['RX-01']['host_gaps_ms'].append(1600)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,'exceed common gap'):
                render_plots(self.summary,data,Path(tmp)/'figures')
            self.assertFalse((Path(tmp)/'figures').exists())


if __name__=='__main__':unittest.main()
