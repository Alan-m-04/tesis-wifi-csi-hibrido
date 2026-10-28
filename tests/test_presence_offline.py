"""Synthetic formulas/masks plus read-only physical extraction; never acquire."""
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tools'))
from presence_offline import ACTIVE, INDICES, RECEIVERS, extract_window, row_mean
from ruview_presence_port import Anchor, PresenceSpecialistPort, calibrate_synthetic, f32, infer_synthetic


def canonical(values=(0, 2, 4)):
    """Explicit synthetic memory fixture; it is not a simulated physical session."""
    out = {'schema': 'tesis-canonical-csi-v1', 'evidence_type': 'synthetic_fixture', 'run_id': 'SYNTHETIC_NOT_A_CAPTURE',
           'strict_quality_ok': False, 'original_session': {'protocol': 'controlled_dual_v3'},
           'connection_full': {'quality_ok': False, 'status': 'rechazada', 'integrity_ok': True},
           'profile': {'target': 'esp32s3', 'channel': 11, 'bandwidth': 'HT20', 'receivers': dict(RECEIVERS)},
           'experimental_window': {'quality_ok': True, 'status': 'conforme', 'integrity_ok': True,
               'shared_prerequisites_ok': True, 'T0_ns': '10000000000', 'T1_ns': '40000000000', 'receivers': {}}, 'receivers': {}}
    for rx, usb in RECEIVERS.items():
        rows = []
        for i, value in enumerate(values if rx == 'RX-01' else [12]*len(values)):
            roles = ['pilot' if k in (-21, -7, 7, 21) else 'data' if k in ACTIVE else 'DC' if k == 0 else 'guard' for k in INDICES]
            b = {'ltf': 'LLTF', 'byte_start': 0, 'byte_stop': 128, 'indices': INDICES[:], 'roles': roles,
                 'hardware_valid': [True]*64, 'cfr_usable': [k in ACTIVE for k in INDICES],
                 'real': [value if k in ACTIVE else 127 for k in INDICES],
                 'imag': [0 if k in ACTIVE else 127 for k in INDICES],
                 'amplitude': [float(value) if k in ACTIVE else math.hypot(127,127) for k in INDICES]}
            synthetic_bytes = ('synthetic-memory-' + rx + '-' + str(i)).encode()
            when = str(10_000_000_000 + (i+1)*200_000_000)
            r = {'kind': 'row', 'problem': False, 'csv_record_index_0based': i, 'id': i,
                 'first_read_started_ns': str(int(when)-1), 'returned_ns': when, 'inclusion': 'included',
                 'line_sha256': hashlib.sha256(synthetic_bytes).hexdigest(), 'byte_offset': i*32, 'byte_end': i*32+len(synthetic_bytes)}
            rows.append({'receiver_id': rx, 'usb_serial': usb, 'blocks': [b], 'host_monotonic_ns': when,
                         'local_timestamp_us_uint32': str(i+1), 'callback_id': str(i), 'csv_record_index_0based': i,
                         'timing_phase': 'included', 'received_in_experimental_window': True, 'window_reference': r})
        times = [int(f['host_monotonic_ns']) for f in rows]
        gaps = [b-a for a,b in zip(times,times[1:])]
        start = times[0]-10_000_000_000 if times else 0
        end = 40_000_000_000-times[-1] if times else 0
        out['receivers'][rx] = {'usb_serial': usb, 'frames': rows}
        out['experimental_window']['receivers'][rx] = {'coverage': {'included_rows': len(rows),
            'first_ns': str(times[0]) if times else None, 'last_ns': str(times[-1]) if times else None,
            'interior_gaps_ns': [str(x) for x in gaps], 'start_gap_ns': str(start), 'end_gap_ns': str(end),
            'max_observed_gap_ns': str(max([start,end]+gaps))}}
    return out


def anchors(rx='RX-01', scope='synthetic-room', empty=(10,1), occupied=(12,3)):
    return [{'evidence_type': 'synthetic_fixture', 'receiver': rx, 'scope': scope,
             'label': label, 'mean': v[0], 'variance': v[1]} for label,v in [('Empty',empty),('Sit',occupied)]]


class ExtractionTests(unittest.TestCase):
    def test_population_formulas_zero_and_guards(self):
        data = canonical(); before = copy.deepcopy(data)
        result = extract_window(data, 'RX-01')
        self.assertEqual(result['features'], {'n': 3, 'mean': 2, 'variance': 8/3})
        self.assertEqual([r['x_mean_amplitude_LLTF52'] for r in result['row_features']], [0,2,4])
        self.assertEqual(result['presence_status'], 'sin calibración')
        self.assertIsNone(result['presence']); self.assertIsNone(result['confidence_margin'])
        self.assertFalse(result['inference_executed']); self.assertFalse(result['global_quality_ok'])
        self.assertEqual(data, before)

    def test_missing_active_tone_invalidates_whole_receiver_session(self):
        data = canonical(); b=data['receivers']['RX-01']['frames'][1]['blocks'][0]
        b['hardware_valid'][1]=b['cfr_usable'][1]=False; b['amplitude'][1]=b['real'][1]=b['imag'][1]=None
        result = extract_window(data,'RX-01')
        self.assertEqual(result['feature_status'],'no evaluable'); self.assertIsNone(result['features'])
        self.assertEqual(result['included_rows'],3); self.assertEqual(len(result['row_features']),3)
        self.assertIsNone(result['row_features'][1]['x_mean_amplitude_LLTF52'])
        self.assertEqual(extract_window(data,'RX-02')['features']['mean'],12)

    def test_missing_required_row_or_array_is_not_silently_skipped(self):
        data=canonical();data['receivers']['RX-01']['frames'].pop()
        self.assertIn('required_included_rows_incomplete',extract_window(data,'RX-01')['reasons'])
        for field in ['amplitude','real','imag','cfr_usable','roles']:
            data=canonical();data['receivers']['RX-01']['frames'][0]['blocks'][0].pop(field)
            self.assertIsNone(extract_window(data,'RX-01')['features'])

    def test_layout_shift_duplicate_LLTF_or_contradictory_mask_rejected(self):
        for change in ['indices','duplicate','mask']:
            data=canonical();f=data['receivers']['RX-01']['frames'][0];b=f['blocks'][0]
            if change=='indices':b['indices']=b['indices'][1:]+b['indices'][:1]
            elif change=='duplicate':f['blocks'].append(copy.deepcopy(b))
            else:b['cfr_usable'][0]=True
            self.assertIsNone(extract_window(data,'RX-01')['features'])

    def test_nonfinite_or_inconsistent_amplitude_not_replaced(self):
        for val in [None,float('nan'),float('inf'),-1,999]:
            data=canonical();data['receivers']['RX-01']['frames'][1]['blocks'][0]['amplitude'][1]=val
            self.assertEqual(extract_window(data,'RX-01')['feature_status'],'no evaluable')

    def test_receiver_identity_and_calibration_are_not_fused(self):
        data=canonical();a=extract_window(data,'RX-01');b=extract_window(data,'RX-02')
        self.assertEqual((a['features']['mean'],b['features']['mean']),(2,12))
        self.assertTrue(a['primary_input']);self.assertFalse(b['primary_input'])
        data['receivers']['RX-01']['frames'][0]['usb_serial']=RECEIVERS['RX-02']
        self.assertEqual(extract_window(data,'RX-01')['feature_status'],'no evaluable')

    def test_HT_LTF_does_not_enter_LLTF_features(self):
        data=canonical();expected=extract_window(data,'RX-01')['features']
        for f in data['receivers']['RX-01']['frames']:
            f['blocks'].append({'ltf':'HT-LTF','amplitude':[1e20]*64})
        self.assertEqual(extract_window(data,'RX-01')['features'],expected)

    def test_boundaries_T1_and_cross_start_never_moved(self):
        for s,e in [('9999999999','10200000000'),('10000000000','40000000000')]:
            data=canonical();f=data['receivers']['RX-01']['frames'][0]
            f['window_reference'].update(first_read_started_ns=s,returned_ns=e);f['host_monotonic_ns']=e
            result=extract_window(data,'RX-01')
            self.assertEqual(result['feature_status'],'no evaluable');self.assertEqual(result['T0_ns'],'10000000000')

    def test_repeated_timestamps_are_preserved(self):
        data=canonical();frames=data['receivers']['RX-01']['frames']
        frames[1]['host_monotonic_ns']=frames[0]['host_monotonic_ns']
        frames[1]['window_reference']['returned_ns']=frames[0]['host_monotonic_ns']
        frames[1]['window_reference']['first_read_started_ns']=frames[0]['window_reference']['first_read_started_ns']
        data['experimental_window']['receivers']['RX-01']['coverage']['interior_gaps_ns']=['0','400000000']
        result=extract_window(data,'RX-01')
        self.assertEqual(result['features']['n'],3)
        self.assertEqual(result['row_features'][0]['host_monotonic_ns'],result['row_features'][1]['host_monotonic_ns'])

    def test_coverage_is_verified_without_rewriting_history(self):
        data=canonical();coverage=data['experimental_window']['receivers']['RX-01']['coverage']
        coverage['start_gap_ns']='0'
        result=extract_window(data,'RX-01')
        self.assertEqual(result['feature_status'],'no evaluable')
        self.assertIn('coverage_trace_mismatch',result['reasons'])
        self.assertEqual(result['coverage']['start_gap_ns'],'0')

    def test_non_v3_or_nonconforming_window_not_reinterpreted(self):
        data=canonical();data['original_session']['protocol']='controlled_dual_v2'
        self.assertEqual(extract_window(data,'RX-01')['feature_status'],'no evaluable')
        data=canonical();data['experimental_window']['quality_ok']=False
        self.assertEqual(extract_window(data,'RX-01')['feature_status'],'no evaluable')

    def test_missing_history_or_schema_is_not_a_valid_window(self):
        for field in ['schema','evidence_type','strict_quality_ok','connection_full']:
            data=canonical();data.pop(field)
            self.assertEqual(extract_window(data,'RX-01')['feature_status'],'no evaluable')


class SyntheticHeadTests(unittest.TestCase):
    def test_train_and_infer_known_formulas(self):
        model=PresenceSpecialistPort.train([Anchor('Empty',10,1),Anchor('Sit',12,3)])
        self.assertEqual((model.threshold,model.empty_mean,model.occupied_var,model.mean_dist_threshold),(2,10,3,1))
        self.assertEqual(model.infer(11,2),{'value':0,'confidence_margin':0,'label':'absent'})
        self.assertEqual(model.infer(12,3),{'value':1,'confidence_margin':1,'label':'present'})

    def test_no_anonymous_pretrained_default_when_anchors_absent(self):
        for a in [[],anchors()[:1],anchors()[1:]]:
            c=calibrate_synthetic(a,receiver='RX-01',scope='synthetic-room')
            r=infer_synthetic(10,1,receiver='RX-01',scope='synthetic-room',calibration=c)
            self.assertEqual(r['status'],'sin calibración');self.assertIsNone(r['presence']);self.assertFalse(r['inference_executed'])

    def test_both_channels_disabled_abstains_instead_of_claiming_absence(self):
        c=calibrate_synthetic(anchors(empty=(10,4),occupied=(10,1)),receiver='RX-01',scope='synthetic-room')
        self.assertEqual(c['status'],'sin separabilidad');self.assertIsNone(c['model'])
        r=infer_synthetic(10,4,receiver='RX-01',scope='synthetic-room',calibration=c)
        self.assertIsNone(r['presence']);self.assertFalse(r['inference_executed'])
        raw=PresenceSpecialistPort.train([Anchor('Empty',10,4),Anchor('Sit',10,1)])
        self.assertEqual(raw.infer(10,4)['confidence_margin'],0)

    def test_mean_shift_survives_inverted_variance(self):
        c=calibrate_synthetic(anchors(empty=(10,4),occupied=(8,1)),receiver='RX-01',scope='synthetic-room')
        r=infer_synthetic(8,1,receiver='RX-01',scope='synthetic-room',calibration=c)
        self.assertTrue(r['presence']);self.assertEqual(r['status'],'resultado sintético')

    def test_scope_and_RX_mismatch_produce_no_decision(self):
        c=calibrate_synthetic(anchors(),receiver='RX-01',scope='synthetic-room')
        for rx,scope in [('RX-02','synthetic-room'),('RX-01','another-room')]:
            r=infer_synthetic(12,3,receiver=rx,scope=scope,calibration=c)
            self.assertIsNone(r['presence']);self.assertFalse(r['inference_executed'])

    def test_only_explicit_synthetic_data_may_fit_or_use_test_models(self):
        a=anchors();a[0]['evidence_type']='physical_capture'
        with self.assertRaises(ValueError):calibrate_synthetic(a,receiver='RX-01',scope='synthetic-room')
        with self.assertRaises(ValueError):infer_synthetic(12,3,receiver='RX-01',scope='synthetic-room',evidence_type='physical_capture')

    def test_invalid_required_features_do_not_return_a_decision(self):
        c=calibrate_synthetic(anchors(),receiver='RX-01',scope='synthetic-room')
        for mean,var in [(None,1),(1,None),(float('nan'),1),(1,-1),(1,float('inf'))]:
            r=infer_synthetic(mean,var,receiver='RX-01',scope='synthetic-room',calibration=c)
            self.assertEqual(r['status'],'no evaluable');self.assertIsNone(r['presence'])

    def test_first_empty_and_multiple_occupied_policy(self):
        m=PresenceSpecialistPort.train([Anchor('Empty',10,1),Anchor('Empty',100,100),Anchor('Sit',12,3),Anchor('StandStill',14,5)])
        self.assertEqual((m.empty_mean,m.threshold,m.mean_dist_threshold),(10,2.5,1.5))

    def test_threshold_guards_are_original_f32_constants(self):
        m=PresenceSpecialistPort.train([Anchor('Empty',10,1),Anchor('Sit',10,f32(1.05))])
        self.assertTrue(math.isinf(m.threshold));self.assertIsNone(m.mean_dist_threshold)
        m=PresenceSpecialistPort.train([Anchor('Empty',0,1),Anchor('Sit',f32(1e-4),1)])
        self.assertIsNone(m.mean_dist_threshold)


@unittest.skipUnless((ROOT/'results/local/preparacion-dual-v3-movimiento-libre-20261026T035823Z').is_dir(), 'Physical originals intentionally local only')
class PhysicalExtractionTests(unittest.TestCase):
    def test_physical_extraction_cannot_calibrate_classify_discover_or_mutate(self):
        import extraer_presencia_offline as tool
        baseline=json.loads((ROOT/'results/COMPARACION_FISICA_V3.resumen.json').read_text())
        paths = [p for cfg in tool.SESSIONS.values() for part in (cfg['run'], cfg['control'])
                 for p in (ROOT/cfg['base']/part).rglob('*') if p.is_file()]
        protected = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        with patch('ruview_presence_port.PresenceSpecialistPort.train',side_effect=AssertionError('No physical fit')) as fit, \
             patch('ruview_presence_port.PresenceSpecialistPort.infer',side_effect=AssertionError('No physical infer')) as infer, \
             patch('serial.Serial',side_effect=AssertionError('No UART')) as opened, \
             patch('capture_csi_multi.port_identity',side_effect=AssertionError('No discovery')) as discovery:
            report,rows=tool.build_features()
        for p in [fit,infer,opened,discovery]:p.assert_not_called()
        for key,n in [('sentado',150),('libre',149)]:
            for rx in RECEIVERS:
                r=report['sessions'][key]['receivers'][rx]
                b=baseline['sessions'][key]['receivers'][rx]['blocks']['LLTF']['frame_mean_amplitude']
                self.assertEqual(r['feature_status'],'evaluable');self.assertEqual(r['presence_status'],'sin calibración')
                self.assertIsNone(r['presence']);self.assertEqual(r['features']['n'],n)
                self.assertAlmostEqual(r['features']['mean'],b['mean'])
                self.assertAlmostEqual(r['features']['variance'],b['std_population']**2)
                self.assertFalse(r['global_quality_ok']);self.assertFalse(r['connection_full']['quality_ok'])
                self.assertEqual(r['experimental_window']['status'],'conforme')
                self.assertEqual(len(rows[r['row_features_artifact']['name']].splitlines()),n)
        self.assertEqual(json.loads(json.dumps(report,allow_nan=False)),report)
        self.assertTrue(all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in protected.items()))


if __name__=='__main__':unittest.main()
