"""Descriptive comparison invariants; memory and read-only original evidence."""
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('physical_comparison', ROOT / 'tools/comparar_fisicas_v3.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def frames(values):
    """Synthetic amplitudes with deliberately huge guards, never observations."""
    indices = list(range(32)) + list(range(-32, 0))
    roles = ['data' if 1 <= abs(k) <= 26 else 'DC' if k == 0 else 'guard' for k in indices]
    return [{'blocks': [{'ltf': 'LLTF', 'indices': indices[:], 'roles': roles[:],
                         'hardware_valid': [True]*64,
                         'cfr_usable': [r == 'data' for r in roles],
                         'amplitude': [value if r == 'data' else 1e8 for r in roles]}]} for value in values]


class MaskAndBoundaryChecks(unittest.TestCase):
    def test_guards_dc_excluded_and_valid_zero_retained(self):
        source = frames([0, 2, 4]); before = copy.deepcopy(source)
        result, means = module.describe_block(source, 'LLTF')
        self.assertEqual(means, [0, 2, 4])
        self.assertEqual(result['mask_counts']['zero_active_amplitudes'], 52)
        self.assertEqual(result['mask_counts']['excluded_by_cfr_mask_pairs'], 12*3)
        self.assertEqual(result['frame_mean_amplitude']['mean'], 2)
        self.assertAlmostEqual(result['mean_per_tone_temporal_std'], math.sqrt(8/3))
        self.assertEqual(source, before)

    def test_missing_tone_changes_support_without_filling_or_removing_acquisition_row(self):
        source = frames([0, 2, 4]); b = source[2]['blocks'][0]
        b['hardware_valid'][1] = b['cfr_usable'][1] = False; b['amplitude'][1] = None
        result, means = module.describe_block(source, 'LLTF')
        self.assertEqual(means, [0, 2, None])
        self.assertEqual(result['rows_in_window'], 3)
        self.assertEqual(result['rows_not_describable_as_full_tone_mean'], 1)
        tone = next(x for x in result['per_tone'] if x['index'] == 1)
        self.assertEqual((tone['n'], tone['mean'], tone['std_population']), (2, 1, 1))
        self.assertEqual(result['mask_counts']['hardware_invalid_pairs'], 1)

    def test_nonfinite_usable_amplitude_is_rejected(self):
        source = frames([1, 2]); source[1]['blocks'][0]['amplitude'][1] = float('nan')
        with self.assertRaisesRegex(ValueError, 'Invalid usable amplitude'):
            module.describe_block(source, 'LLTF')

    def test_all_masked_is_unknown_instead_of_zero_measurements(self):
        source = frames([1, 2])
        for f in source:
            b = f['blocks'][0]
            b['hardware_valid'] = [False]*64; b['cfr_usable'] = [False]*64
            b['amplitude'] = [None]*64
        result, means = module.describe_block(source, 'LLTF')
        self.assertEqual(means, [None, None])
        self.assertIsNone(result['frame_mean_amplitude']['mean'])
        self.assertIsNone(result['mean_per_tone_temporal_std'])
        self.assertTrue(all(t['n'] == 0 and t['mean'] is None for t in result['per_tone']))

    def test_contradictory_mask_is_rejected(self):
        source = frames([1]); source[0]['blocks'][0]['cfr_usable'][0] = True
        with self.assertRaisesRegex(ValueError, 'CFR mask contradicts'):
            module.describe_block(source, 'LLTF')

    def test_changed_tone_roles_are_rejected_instead_of_dynamic_selection(self):
        source = frames([1, 2]); source[1]['blocks'][0]['roles'][1] = 'guard'
        with self.assertRaisesRegex(ValueError, 'layout changed'):
            module.describe_block(source, 'LLTF')

    def test_prospective_boundaries_not_last_row_window_or_inclusive_T1(self):
        t0, t1 = 1000, 30_000_001_000
        def frame(s, e, phase):
            return {'window_reference': {'first_read_started_ns': str(s), 'returned_ns': str(e)},
                    'timing_phase': phase, 'received_in_experimental_window': phase == 'included'}
        source = {'experimental_window': {'T0_ns': str(t0), 'T1_ns': str(t1),
                   'receivers': {'RX-01': {'coverage': {'included_rows': 2}}}},
                  'receivers': {'RX-01': {'frames': [frame(t0-1, t0+1, 'crosses_start'),
                     frame(t0, t0+2, 'included'), frame(t0+1, t1-1, 'included'),
                     frame(t1-1, t1, 'at_or_after_deadline')]}}}
        self.assertEqual(len(module.window_frames(source, 'RX-01')), 2)
        source['receivers']['RX-01']['frames'][-1].update(timing_phase='included', received_in_experimental_window=True)
        with self.assertRaisesRegex(ValueError, 'boundary/inclusion mismatch'):
            module.window_frames(source, 'RX-01')

    def test_repeated_host_timestamps_remain_repeated(self):
        f = {'window_reference': {'first_read_started_ns': '1000', 'returned_ns': '2000'},
             'timing_phase': 'included', 'received_in_experimental_window': True}
        source = {'experimental_window': {'T0_ns': '1000', 'T1_ns': '30000001000',
                   'receivers': {'RX-01': {'coverage': {'included_rows': 2}}}},
                  'receivers': {'RX-01': {'frames': [copy.deepcopy(f), copy.deepcopy(f)]}}}
        result = module.window_frames(source, 'RX-01')
        self.assertEqual([x['window_reference']['returned_ns'] for x in result], ['2000', '2000'])


@unittest.skipUnless((ROOT / module.SESSIONS['libre']['base']).is_dir(), 'Physical originals intentionally not distributed in Git')
class PhysicalEvidenceChecks(unittest.TestCase):
    def test_originals_reproduce_separate_windows_without_UART_discovery_or_mutation(self):
        paths = [p for cfg in module.SESSIONS.values() for p in
                 (ROOT / cfg['base'] / cfg['run']).rglob('*') if p.is_file()]
        before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        with patch('serial.Serial', side_effect=AssertionError('No UART')) as opened, \
                patch('capture_csi_multi.port_identity', side_effect=AssertionError('No discovery')) as discovery:
            movement, report, data = module.reports()
        opened.assert_not_called(); discovery.assert_not_called()
        self.assertEqual(json.loads(json.dumps(report, allow_nan=False)), report)
        self.assertEqual(json.loads(json.dumps(movement, allow_nan=False)), movement)
        self.assertFalse(movement['global_quality_ok'])
        for key, expected in [('sentado', 150), ('libre', 149)]:
            s = report['sessions'][key]
            self.assertFalse(s['connection_full']['quality_ok']); self.assertFalse(s['global_quality_ok'])
            self.assertEqual(s['experimental_window_status'], 'conforme')
            for rx in module.RX:
                r = s['receivers'][rx]
                self.assertEqual(r['included_rows'], expected)
                self.assertEqual(len(data[key][rx]['times']), expected)
                c = r['coverage']
                self.assertEqual(sum(map(int, c['interior_gaps_ns'])) + int(c['start_gap_ns']) + int(c['end_gap_ns']), 30_000_000_000)
                self.assertEqual(r['blocks']['LLTF']['nominal_active_tones'], 52)
                self.assertEqual(r['blocks']['HT-LTF']['nominal_active_tones'], 56)
                for ltf in module.LTF:
                    b = r['blocks'][ltf]
                    self.assertTrue(all(t['n'] == expected for t in b['per_tone']))
                    self.assertLessEqual(b['frame_mean_amplitude']['max'], report['common_axes']['frame_mean_amplitude'][1])
        self.assertTrue(report['comparability']['pinned_acquisition_sources_equal'])
        self.assertFalse(report['comparability']['measured_geometry_equality_attested'])
        self.assertTrue(all(hashlib.sha256(p.read_bytes()).hexdigest() == h for p, h in before.items()))

    def test_manifest_tamper_is_not_waived_by_existing_global_rejection(self):
        original_load = module.load
        target = ROOT / module.SESSIONS['libre']['base'] / module.SESSIONS['libre']['run'] / 'bundle-manifest.json'
        def altered(path):
            value = original_load(path)
            if path == target:
                value = copy.deepcopy(value); value['files'][0]['bytes'] += 1
            return value
        with patch.object(module, 'load', side_effect=altered), self.assertRaisesRegex(ValueError, 'Hash/size mismatch'):
            module.source_session('libre')


if __name__ == '__main__':
    unittest.main()
