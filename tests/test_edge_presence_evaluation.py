"""Session isolation, wire extraction, errors and denominators using invented CSI."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tools')]
from edge_presence_evaluation import (evaluate, markdown, read_dataset, read_physical,
                                      safe_path, validate_manifest)
from edge_presence_synthetic import write_dataset
from ruview_presence_port import f32
import evaluar_edge_ai as cli


class EvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        cls.path = write_dataset(cls.root / 'original')
        cls.manifest, cls.records, cls.inputs = read_dataset(cls.path)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_wire_features_and_known_matrix_include_errors_and_abstentions(self):
        report = evaluate(self.manifest, self.records)
        self.assertEqual(report['evidence_type'], 'synthetic_fixture')
        self.assertIn('SINTÉTICA', report['title'])
        train = report['training']
        self.assertEqual(train[0]['features'], dict(n=150, mean=10, variance=0))
        self.assertEqual(train[1]['features'], dict(n=150, mean=22, variance=8/3))
        self.assertEqual(report['model']['parameters']['threshold'], f32(4/3))
        self.assertEqual(report['model']['parameters']['mean_dist_threshold'], 6.25)
        self.assertEqual(report['confusion_matrix']['counts'],
                         dict(vacio=dict(vacio=1, ocupado=1, abstencion=1),
                              ocupado=dict(vacio=1, ocupado=1, abstencion=1)))
        m = report['metrics']
        self.assertEqual((m['false_alarms'], m['false_negatives'], m['abstentions']), (1, 1, 2))
        self.assertEqual(m['false_alarm_rate_decided_empty'], 1/2)
        self.assertEqual(m['false_alarm_rate_all_empty'], 1/3)
        self.assertEqual(m['coverage'], 4/6)
        self.assertEqual(m['accuracy_decided'], 2/4)
        self.assertEqual(m['correct_over_all_windows'], 2/6)
        self.assertTrue(set(report['partitions']['train']).isdisjoint(report['partitions']['evaluation']))
        self.assertEqual(sum(r['windows'] for r in report['by_session'].values()), 6)
        self.assertTrue(all(not r['connection_full']['quality_ok'] for r in self.records))
        self.assertTrue(all(r['input_rows'] == 150 for r in self.records))
        json.dumps(report, allow_nan=False)
        self.assertIn('Abstención', markdown(report))

    def test_evaluation_labels_or_values_cannot_fit_the_model(self):
        original = copy.deepcopy(self.records)
        report = evaluate(self.manifest, self.records)
        altered = copy.deepcopy(self.records)
        for r in altered:
            if r['split'] == 'evaluation':
                r['truth'] = 'ocupado'
                r['features'] = dict(n=150, mean=100, variance=100)
        self.assertEqual(report['model'], evaluate(self.manifest, altered)['model'])
        self.assertEqual(self.records, original)

    def test_complete_connection_group_cannot_cross_partitions(self):
        manifest = copy.deepcopy(self.manifest)
        manifest['sessions'][2]['partition_group'] = manifest['sessions'][0]['partition_group']
        with self.assertRaisesRegex(ValueError, 'Fuga de grupo'):
            validate_manifest(manifest, self.path.parent)

    def test_duplicate_ids_bundles_and_insufficient_groups_are_rejected(self):
        for defect in ('id', 'bundle', 'groups'):
            manifest = copy.deepcopy(self.manifest)
            if defect in ('id', 'bundle'):
                manifest['sessions'][1][defect] = manifest['sessions'][0][defect]
            else:
                manifest['sessions'][1]['partition_group'] = manifest['sessions'][0]['partition_group']
            with self.subTest(defect=defect), self.assertRaises(ValueError):
                validate_manifest(manifest, self.path.parent)

    def test_reserve_and_device_paths_rejected_before_content_read(self):
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('No content read')):
            for name in ('/tmp/RX02-C04/raw', '/tmp/c05', '/tmp/C06', '/dev/ttyACM0'):
                with self.subTest(path=name), self.assertRaises(ValueError):
                    safe_path(name)

    def test_bad_training_features_abort_instead_of_dropping_window(self):
        rows = copy.deepcopy(self.records)
        next(r for r in rows if r['split'] == 'train')['features'] = None
        with self.assertRaisesRegex(ValueError, 'Entrenamiento incompleto'):
            evaluate(self.manifest, rows)

    def test_nonseparable_model_abstains_without_reporting_infinity(self):
        rows = copy.deepcopy(self.records)
        for row in rows:
            row['features'] = dict(n=150, mean=10, variance=1)
        report = evaluate(self.manifest, rows)
        self.assertEqual(report['model']['status'], 'no_separable_model')
        self.assertEqual(report['metrics']['abstentions'], 6)
        self.assertIsNone(report['metrics']['accuracy_decided'])
        self.assertIsNone(report['metrics']['false_alarm_rate_decided_empty'])
        self.assertEqual(report['metrics']['correct_over_all_windows'], 0)
        json.dumps(report, allow_nan=False)

    def test_tampered_raw_hash_is_fatal_and_original_dataset_is_unchanged(self):
        path = write_dataset(self.root / 'tamper')
        raw = path.parent / 'SYNTHETIC-EVAL-01/rx-02.serial.log'
        raw.write_bytes(raw.read_bytes() + b'altered\n')
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            read_dataset(path)
        for name, digest in self.inputs.items():
            self.assertEqual(hashlib.sha256(Path(name).read_bytes()).hexdigest(), digest)

    def test_mixed_evidence_types_cannot_use_synthetic_fixture_as_physical(self):
        with self.assertRaisesRegex(ValueError, 'plan original no permite training'):
            with patch('edge_presence_evaluation.load_json', return_value=dict(permitted_uses=dict(training=False))):
                read_physical(self.root, 'train', 'room')

    def test_physical_calibration_scope_and_reserve_gates_precede_raw_read(self):
        cases = [
            ('train', dict(permitted_uses=dict(training=True, calibration=False)), 'calibration'),
            ('evaluation', dict(permitted_uses=dict(evaluation=False)), 'evaluation'),
            ('evaluation', dict(permitted_uses=dict(evaluation=True), edge_scope='other'), 'Ámbito'),
            ('evaluation', dict(permitted_uses=dict(evaluation=True), edge_scope='room',
                                future_partition='evaluation_future_sealed'), 'reserva final'),
        ]
        for split, plan, message in cases:
            with self.subTest(split=split, plan=plan), patch('edge_presence_evaluation.load_json', return_value=plan):
                with self.assertRaisesRegex(ValueError, message):
                    read_physical(self.root, split, 'room')

    def test_cli_refuses_existing_output_and_can_evaluate_saved_manifest(self):
        # CLI normally restricts outputs to results/local; isolate writes in this temporary root.
        with patch.object(cli, 'ROOT', self.root), patch.object(cli.sys, 'addaudithook'):
            output = self.root / 'results/local/evaluated'
            real_sha = cli.sha
            with patch.object(cli, 'sha', wraps=cli.sha) as hashing:
                # Source provenance still refers to repository code.
                hashing.side_effect = lambda p: real_sha(ROOT / Path(p).relative_to(self.root)) if (
                    Path(p).is_relative_to(self.root) and not Path(p).exists()) else real_sha(p)
                self.assertEqual(cli.main(['evaluate', '--manifest', str(self.path), '--output-new', str(output)]), 0)
            self.assertTrue((output / 'report.json').is_file())
            before = (output / 'report.json').read_bytes()
            with self.assertRaises(SystemExit):
                cli.main(['evaluate', '--manifest', str(self.path), '--output-new', str(output)])
            self.assertEqual((output / 'report.json').read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
