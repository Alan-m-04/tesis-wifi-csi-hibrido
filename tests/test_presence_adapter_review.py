"""Additional adapter edge cases on explicit synthetic anchors only."""
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools'),str(ROOT/'tests')]
from test_presence_offline import anchors
from ruview_presence_port import calibrate_synthetic,infer_synthetic,CONTRACT


class AdapterReviewTests(unittest.TestCase):
    def test_generator_anchors_are_not_exhausted_before_training(self):
        a=anchors()
        list_model=calibrate_synthetic(a,receiver='RX-01',scope='synthetic-room')
        generator_model=calibrate_synthetic((x for x in a),receiver='RX-01',scope='synthetic-room')
        self.assertEqual(generator_model,list_model)
        self.assertEqual(generator_model['status'],'calibración sintética')

    def test_malformed_calibration_abstains(self):
        base=dict(receiver='RX-01',scope='synthetic-room',contract=CONTRACT,evidence_type='synthetic_fixture')
        for calibration in (object(),base,dict(base,status='calibración sintética',model=object())):
            with self.subTest(calibration=type(calibration)):
                result=infer_synthetic(12,3,receiver='RX-01',scope='synthetic-room',calibration=calibration)
                self.assertFalse(result['inference_executed']);self.assertIsNone(result['presence'])

    def test_physical_features_are_never_accepted_as_synthetic_anchors_or_queries(self):
        a=anchors();a[0]['evidence_type']='physical_capture'
        with self.assertRaises(ValueError):calibrate_synthetic(iter(a),receiver='RX-01',scope='synthetic-room')
        with self.assertRaises(ValueError):infer_synthetic(12,3,receiver='RX-01',scope='synthetic-room',evidence_type='physical_capture')

    def test_no_separability_remains_no_decision(self):
        calibration=calibrate_synthetic(anchors(empty=(10,4),occupied=(10,1)),receiver='RX-01',scope='synthetic-room')
        result=infer_synthetic(10,4,receiver='RX-01',scope='synthetic-room',calibration=calibration)
        self.assertEqual(result['status'],'sin separabilidad');self.assertFalse(result['inference_executed'])


if __name__=='__main__':unittest.main()
