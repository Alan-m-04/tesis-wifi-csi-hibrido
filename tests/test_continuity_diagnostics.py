"""Forensic statistics and preservation; no port construction, including real bundle replay."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools')]
from continuity_diagnostics import distribution, gap_distribution, service_gaps, partial_header, analyze_continuity
from presence_v4_journal import digest
from campana_presencia_v4 import fixture_row
from analizar_continuidad_dual import main


class StatisticsTests(unittest.TestCase):
    def test_empty_and_nearest_rank_with_conventional_median(self):
        self.assertEqual(distribution([])['count'],0)
        self.assertIsNone(distribution([])['max'])
        result=distribution(list(range(1,101)))
        self.assertEqual((result['median'],result['p95'],result['p99']),(50.5,95,99))
        self.assertEqual(distribution([7])['p99'],7)

    def test_histogram_boundaries_do_not_change_strict_one_second_incident(self):
        result=gap_distribution([0,249999999,250000000,1000000000,1000000001,1500000000])
        self.assertEqual(result['over_1s'],2)
        self.assertEqual([x['count'] for x in result['histogram']],[2,1,0,0,2,0,1])
        self.assertEqual(sum(x['count'] for x in result['histogram']),6)

    def test_service_gaps_include_both_boundaries_and_only_target_rx(self):
        events=[dict(kind='service',receiver=rx,clocks=dict(monotonic_ns=t))
                for rx,t in [('RX-01',5),('RX-01',15),('RX-02',25),('RX-01',35),('RX-01',45)]]
        self.assertEqual(service_gaps(events,'RX-01',10,40),[5,20,5])
        self.assertEqual(service_gaps(events,'RX-02',10,40),[15,15])
        self.assertEqual(service_gaps([],'RX-01',10,40),[30])

    def test_partial_header_never_becomes_valid_row(self):
        result=partial_header(fixture_row(171,59949062)[:200])
        self.assertFalse(result['validated_as_CSI']);self.assertFalse(result['complete_row_counted'])
        self.assertEqual(result['literal_fields']['id'],171)
        self.assertNotIn('literal_fields',partial_header(b'CSI_DATA,broken'))

    def test_cli_forbids_output_inside_bundle_without_read_or_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(sys,'argv',['forensics','--bundle',tmp,'--output-new',tmp+'/new.json']), \
                 patch('analizar_continuidad_dual.analyze_continuity',side_effect=AssertionError('No analysis')), \
                 contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit): main()
            self.assertEqual(list(Path(tmp).iterdir()),[])

    def test_cli_never_overwrites_an_existing_external_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'old.json';output.write_text('original')
            with patch.object(sys,'argv',['forensics','--bundle',tmp+'/bundle','--output-new',str(output)]), \
                 contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):main()
            self.assertEqual(output.read_text(),'original')


class ExistingBundleTests(unittest.TestCase):
    @unittest.skipUnless((ROOT/'results/local/continuidad-dual-01-60s-intento-unico/manifest.json').exists(),
                         'Physical bundle is local only; never acquired or downloaded by tests')
    def test_real_bundle_171_296_three_incidents_and_untouched_tails(self):
        bundle=ROOT/'results/local/continuidad-dual-01-60s-intento-unico'
        before={p.name:digest(p) for p in bundle.iterdir() if p.is_file()}
        with patch('serial.Serial',side_effect=AssertionError('No UART construction')), \
             patch('presence_v4_uart.identity',side_effect=AssertionError('No device discovery')):
            result=analyze_continuity(bundle)
        a,b=result['receivers']['RX-01'],result['receivers']['RX-02']
        self.assertEqual((a['valid_complete_rows_common'],b['valid_complete_rows_common']),(171,296))
        self.assertEqual((a['host_row_gaps_ns']['over_1s'],b['host_row_gaps_ns']['over_1s']),(3,0))
        self.assertEqual(a['local_row_gaps_ns']['over_1s'],4)
        self.assertEqual(len(result['incidents']),3)
        self.assertTrue(all(x['callback_id_delta']==1 and x['queue_drops_delta']==0 for x in result['incidents']))
        for s,n in ((a,171),(b,296)):
            self.assertEqual(s['tail']['byte_length'],640)
            self.assertEqual(s['tail']['literal_header']['literal_fields']['id'],n)
            self.assertFalse(s['tail']['literal_header']['complete_row_counted'])
            self.assertEqual(s['callback_ids']['deltas'],{'1':n-1})
            self.assertEqual(s['queue_drops_values'],[0])
        self.assertEqual(a['valid_rows_per_10s'],[22,31,32,28,27,31])
        self.assertEqual(b['valid_rows_per_10s'],[47,50,50,50,50,49])
        self.assertEqual(before,{p.name:digest(p) for p in bundle.iterdir() if p.is_file()})
        self.assertTrue(result['authorization']['consumed'])
        self.assertFalse(result['analysis_activity']['physical_UART_opened'])


if __name__=='__main__':unittest.main()
