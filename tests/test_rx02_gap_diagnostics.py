"""C02 forensic regression: distinguish trigger, late tail and original label."""
import copy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from rx02_gap_diagnostics import adjacent_gaps,compare_c01_c02,incident_details,inventory,phase,ROOT


def row(seq,returned,local,callback):
    return dict(seq=seq,now_ns=returned+1,kind='line',evidence=dict(kind='row',returned_ns=str(returned),
        local_timestamp=local,id=callback,queue_drops=0))


class IntervalTests(unittest.TestCase):
    def test_same_chunk_host_zero_retains_distinct_local_intervals(self):
        gaps=adjacent_gaps([row(0,100,1000,1),row(1,100,201000,2)])
        self.assertEqual(gaps[0]['host_gap_ns'],0)
        self.assertEqual(gaps[0]['local_gap_us'],200000)
        self.assertEqual(gaps[0]['callback_id_delta'],1)

    def test_uint32_local_wrap_is_not_negative_pause(self):
        gaps=adjacent_gaps([row(0,1,2**32-100,1),row(1,2,100,2)])
        self.assertEqual(gaps[0]['local_gap_us'],200)

    def test_phase_is_half_open_and_does_not_add_edges_as_row_intervals(self):
        values=[row(0,99,1,1),row(1,100,2,2),row(2,199,3,3),row(3,200,4,4)]
        result=phase(values,[],100,200)
        self.assertEqual(result['complete_rows_by_return'],2)
        self.assertEqual(result['host_row_gap_ns']['count'],1)
        self.assertEqual(result['host_row_gap_ns']['max'],99)


class OriginalC02Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.paths={c:ROOT/'results/local'/('piloto-rx02-r1-'+c) for c in ('C01','C02')}
        if not all(p.exists() for p in cls.paths.values()):
            raise unittest.SkipTest('Original local C01/C02 unavailable; do not fabricate measurements')
        cls.before={c:inventory(p) for c,p in cls.paths.items()}
        with patch('presence_rx02_uart.preflight_rx02',side_effect=AssertionError('No device metadata query')), \
             patch('presence_rx02_uart.UartEndpoint.open',side_effect=AssertionError('No physical UART')):
            cls.result,cls.audits=compare_c01_c02(cls.paths['C01'],cls.paths['C02'])

    def test_bundles_and_original_decisions_unchanged(self):
        for c,p in self.paths.items():self.assertEqual(self.before[c],inventory(p))
        b=self.result['bundles']['C02']
        self.assertEqual(b['fatal'],'availability_gap:RX-02')
        self.assertFalse(b['connection']['quality_ok'])
        self.assertFalse(b['exploratory_eligibility']['windows'][0]['eligible'])

    def test_trigger_uses_1008_to_1009_not_final_row_1013(self):
        i=self.result['incident'];g=i['triggering_row_pair']
        self.assertEqual((g['previous']['evidence']['id'],g['following']['evidence']['id']),(1008,1009))
        self.assertEqual(g['host_gap_ns'],1221331818)
        self.assertEqual(g['local_gap_us'],199978)
        self.assertEqual(i['final_complete_row']['evidence']['id'],1013)
        self.assertEqual(len(i['parsed_rows_after_suspension_event_in_same_chunk']),4)

    def test_failure_post_window_does_not_approve_label_or_empty(self):
        i=self.result['incident'];b=self.result['bundles']['C02'];w=b['windows'][0]
        self.assertEqual(i['suspension_after_T1_ns'],9524027744)
        self.assertTrue(i['row_pair_gap_is_post_window'])
        self.assertTrue(w['window_quality_ok'] and w['pilot_coverage_ok'])
        self.assertEqual(w['label'],dict(status='pending',declaration_ns=None,timing_uncertainty='unknown'))
        self.assertFalse(w['label_quality_ok']);self.assertIsNone(w['end_signal'])
        self.assertEqual(b['operation_counts'].get('declare',0),0)
        self.assertEqual(b['remaining_slots'],[dict(id='RX02-C02-E',condition='E',state='suspended')])

    def test_tail_is_literal_unvalidated_not_a_1015th_row(self):
        i=self.result['incident'];t=i['tail']
        self.assertEqual(t['bytes'],349);self.assertFalse(t['contains_LF'])
        self.assertFalse(t['validated_as_CSI']);self.assertFalse(t['complete_row_counted'])
        self.assertEqual(t['literal_partial_header']['literal_fields']['id'],1014)
        self.assertEqual(self.result['bundles']['C02']['complete_CSI_rows'],1014)
        raw=(self.paths['C02']/'rx-02.serial.log').read_bytes()
        self.assertEqual(hashlib.sha256(raw[t['byte_offset']:t['byte_end']]).hexdigest(),t['sha256'])

    def test_latency_intervals_are_separate_and_sum_correctly(self):
        i=self.result['incident'];parts=i['recorded_time_portions']
        self.assertEqual(i['trigger_read_duration_ns'],69163)
        self.assertEqual(i['trigger_read_to_decision_ns'],485252012)
        self.assertEqual(sum(p['elapsed_ns'] for p in parts[:-1]),1221331818)
        self.assertEqual(sum(p['elapsed_ns'] for p in parts),1706583830)

    def test_continuity_comparison_keeps_unequal_durations_and_zero_gaps(self):
        a,b=(self.result['bundles'][c] for c in ('C01','C02'))
        self.assertNotEqual(a['open_to_close_ns'],b['open_to_close_ns'])
        self.assertEqual((a['host_row_gaps_over_1s'],b['host_row_gaps_over_1s']),(0,1))
        self.assertEqual((a['host_zero_gaps'],b['host_zero_gaps']),(0,14))
        self.assertTrue(self.result['comparability']['acquisition_sources_identical'])

    def test_permissions_consumed_selected_closed_and_no_replacement(self):
        refs=[]
        for b in self.result['bundles'].values():
            auth=b['authorization_consumed'];refs.append(auth['reference'])
            self.assertTrue(auth['consumed']);self.assertFalse(auth['retry_allowed'])
            self.assertTrue(b['close_receipt']['selected_confirmed'])
            self.assertEqual(set(b['close_receipt']['closed']),{'RX-02'})
        self.assertNotEqual(*refs)
        self.assertFalse(self.result['diagnostic_activity']['replacement_prepared'])
