"""Existing physical evidence stays separate from the next review-only campaign."""
import contextlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'tools')]
from diagnostico_checkpoints_rx02 import diagnostic_report
from rx02_physical_report import compare
from rx02_gap_diagnostics import inventory
import consolidar_diagnostico_checkpoints_rx02 as consolidate
import revisar_campana_checkpoint_rx02 as campaign
ROOT=Path(__file__).resolve().parents[1]
D=ROOT/'results/local/diagnostico-checkpoints-rx02-r1'
C=ROOT/'results/local/piloto-rx02-r1-C02'


class PhysicalReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before={str(p):inventory(p) for p in (D,C)}
        cls.report,cls.audits=compare(D,C,diagnostic_report)

    def test_physical_counts_lifecycle_and_historical_rejection_remain(self):
        d=self.report['diagnostic'];c=self.report['C02']
        self.assertEqual(d['cadence_full']['complete_rows'],1190)
        self.assertEqual(d['cadence_full']['worst_host_gap']['host_gap_ns'],418887511)
        self.assertEqual(d['cadence_full']['over_500ms'],0)
        self.assertTrue(d['diagnostic']['diagnostic_ok'])
        self.assertFalse(d['connection']['quality_ok'])
        self.assertEqual(d['windows'],[])
        self.assertEqual(d['checkpoint_status']['pending_ops_bytes'],0)
        self.assertEqual(c['fatal'],'availability_gap:RX-02')
        self.assertEqual(c['cadence_full']['complete_rows'],1014)
        self.assertEqual(c['cadence_full']['worst_host_gap']['host_gap_ns'],1221331818)
        self.assertEqual(c['tails']['RX-02']['bytes'],349)
        self.assertEqual(c['windows'][0]['label']['status'],'pending')
        self.assertEqual({str(p):inventory(p) for p in (D,C)},self.before)

    def test_no_resource_or_eligibility_is_fabricated(self):
        d=self.report['diagnostic'];c=self.report['C02']
        self.assertIsNone(c['service_metrics'])
        self.assertIsNone(c['checkpoint_status'])
        self.assertIsNone(d['exploratory_eligibility'])
        self.assertFalse(any(d['diagnostic']['permitted_uses'].values()))
        self.assertTrue(self.report['comparability']['common_interval'].startswith('First 180 s'))
        self.assertEqual(self.report['comparability']['historical_sources_unchanged'],18)

    def test_tampered_physical_copy_cannot_be_consolidated(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/'copy';shutil.copytree(D,dest)
            with (dest/'rx-02.serial.log').open('ab') as f:f.write(b'altered')
            with self.assertRaises(ValueError):compare(dest,C,diagnostic_report)

    def test_existing_or_parent_output_rejected_before_audit(self):
        for dest in (D,D.parent,D/'nested'):
            with patch.object(consolidate,'compare',side_effect=AssertionError('must not audit')):
                with self.assertRaises(ValueError):consolidate.main(['--output-new',str(dest)])


class CampaignReviewTests(unittest.TestCase):
    def test_review_does_not_discover_open_or_consume_authorization(self):
        with patch('serial.Serial',side_effect=AssertionError('no UART')), \
             patch('presence_rx02_uart.identity',side_effect=AssertionError('no metadata')), \
             contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(campaign.main([]),0)
        self.assertEqual(json.loads(out.getvalue())['state'],'REVIEW_ONLY_NOT_AUTHORIZED')

    def test_opt_in_id_partition_and_absent_grant_are_required(self):
        p=json.loads((ROOT/'config/piloto_rx02_C03_checkpoint2.review.json').read_text())
        for change in (dict(persistence_revision='legacy'),dict(connection_id='RX02-C02'),
                       dict(authorization_granted=True),dict(review_only=False),dict(future_partition='evaluation_future_sealed')):
            with self.subTest(change=change),self.assertRaises(ValueError):campaign.review(dict(p,**change))
