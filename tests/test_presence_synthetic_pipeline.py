"""In-memory wire -> LLTF52 -> PresenceSpecialist, using invented values only.

Eligibility is an explicit synthetic audit-decision fixture, not a new auditor
or evidence of protocol compliance on hardware. No file, serial or device input.
"""
import copy
import csv
import hashlib
import io
import math
from pathlib import Path
import statistics
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools')]
from capture_csi_multi import FIELDS,SOURCE
from consolidar_rx02_c01 import frame_from_reference,coverage_from_refs
from eligible_presence_features import extract_eligible_window
from presence_offline import ACTIVE,INDICES
from ruview_presence_port import calibrate_synthetic,infer_synthetic,f32

CONFIG=dict(lltf_en=True,htltf_en=True,stbc_htltf2_en=True,ltf_merge_en=True,
            channel_filter_en=True,manu_scale=False)


def synthetic_window(group,condition,values,*,invalid_word=False):
    """150 invented rows at original irregular-capable host timestamps; no resampling."""
    assert group.startswith('SYNTHETIC-')
    t0=10_000_000_000 if condition=='E' else 50_000_000_000
    slot=group+'-'+condition;raw=bytearray();refs=[];expected=[]
    for ident in range(150):
        real,imag=values[ident%len(values)]
        iq=[]
        for k in INDICES:
            iq.extend([imag,real] if k in ACTIVE else [-128,127])
        iq.extend([99,-99]*64)  # HT-LTF must never leak into LLTF52.
        fields=dict.fromkeys(FIELDS,'0')
        fields.update(type='CSI_DATA',id=str(ident),mac=SOURCE,channel='11',rssi='-50',sig_mode='1',
            len='256',first_word_invalid=str(int(invalid_word)),local_timestamp=str(ident*200000),
            data='['+','.join(map(str,iq))+']')
        stream=io.StringIO();csv.writer(stream,lineterminator='\n').writerow([fields[k] for k in FIELDS])
        line=stream.getvalue().encode();start=len(raw);raw.extend(line)
        when=t0+100_000_000+ident*200_000_000
        refs.append(dict(kind='row',problem=False,id=ident,local_timestamp=ident*200000,queue_drops=0,
            line_1based=ident+1,byte_offset=start,byte_end=len(raw),byte_length=len(line),
            line_sha256=hashlib.sha256(line).hexdigest(),first_read_started_ns=str(when-1),
            returned_ns=str(when),inclusion='included'))
        expected.append(math.hypot(real,imag))
    raw=bytes(raw)
    frames=[frame_from_reference(raw,ref,CONFIG)[0] for ref in refs]
    w=dict(id=slot,condition=condition,T0_ns=t0,T1_ns=t0+30_000_000_000,
        label=dict(status='declared',observation_method='synthetic_fixture'),label_quality_ok=True,
        receivers={'RX-02':dict(included_line_references=refs,coverage=coverage_from_refs(refs,t0,t0+30_000_000_000))})
    # Gate answers are injected: native acquisition and its audits remain separate.
    audit=dict(integrity_ok=True,replay_ok=True,
        state=dict(evidence_type='synthetic_fixture',protocol='presence_rx02_persistent_1',
            connection_id=group,partition_group=group,
            connection=dict(quality_ok=False,reasons=['synthetic_history_rejection']),windows=[w]),
        exploratory_eligibility=dict(windows=[dict(slot_id=slot,eligible=True)]))
    return dict(audit=audit,frames=frames,raw=raw,slot=slot,expected=expected,group=group)


def features(fixture):
    return extract_eligible_window(fixture['audit'],fixture['slot'],fixture['frames'])


class SyntheticPipelineTests(unittest.TestCase):
    def test_wire_IQ_masks_features_and_rejected_history_round_trip(self):
        fixture=synthetic_window('SYNTHETIC-DECODE','E',[(3,-4),(0,0),(-5,12)])
        before=copy.deepcopy(fixture);result=features(fixture)
        self.assertEqual(result['feature_status'],'evaluable')
        self.assertEqual([r['value'] for r in result['row_features']],fixture['expected'])
        self.assertAlmostEqual(result['features']['mean'],statistics.fmean(fixture['expected']))
        self.assertAlmostEqual(result['features']['variance'],statistics.pvariance(fixture['expected']))
        block=fixture['frames'][0]['blocks'][0];i=INDICES.index(1)
        self.assertEqual((block['real'][i],block['imag'][i],block['amplitude'][i]),(3,-4,5))
        self.assertEqual(sum(block['cfr_usable']),52)
        self.assertFalse(result['connection_full']['quality_ok'])
        self.assertFalse(result['calibration_executed']);self.assertFalse(result['inference_executed'])
        self.assertEqual(fixture,before)

    def test_independent_synthetic_connections_reach_head_without_leaking_queries(self):
        cal=[synthetic_window('SYNTHETIC-CAL',c,v) for c,v in
            [('E',[(10,0)]),('S',[(20,0),(22,0),(24,0)])]]
        query=[synthetic_window('SYNTHETIC-EVAL',c,v) for c,v in
            [('E',[(9,0),(10,0),(11,0)]),('S',[(21,0),(23,0),(25,0)])]]
        self.assertTrue({x['group'] for x in cal}.isdisjoint(x['group'] for x in query))
        anchors=[]
        for fixture,label in zip(cal,['Empty','Sit']):
            f=features(fixture)['features']
            anchors.append(dict(label=label,mean=f['mean'],variance=f['variance'],
                evidence_type='synthetic_fixture',receiver='RX-02',scope='synthetic-pipeline'))
        calibration=calibrate_synthetic(anchors,receiver='RX-02',scope='synthetic-pipeline')
        before=copy.deepcopy(calibration)
        self.assertEqual(calibration['model'].threshold,f32(4/3))
        self.assertEqual(calibration['model'].mean_dist_threshold,6)
        for fixture,expected in zip(query,[False,True]):
            f=features(fixture)['features']
            r=infer_synthetic(f['mean'],f['variance'],receiver='RX-02',scope='synthetic-pipeline',
                calibration=calibration,evidence_type='synthetic_fixture')
            self.assertEqual(r['status'],'resultado sintético');self.assertIs(r['presence'],expected)
        self.assertEqual(calibration,before)
        # The numerical result exercises software only; it estimates no physical accuracy.

    def test_features_alone_do_not_supply_a_calibrated_head(self):
        fixture=synthetic_window('SYNTHETIC-NO-MODEL','S',[(20,0),(22,0),(24,0)])
        f=features(fixture)['features']
        r=infer_synthetic(f['mean'],f['variance'],receiver='RX-02',scope='synthetic-pipeline')
        self.assertFalse(r['inference_executed']);self.assertIsNone(r['presence'])

    def test_missing_tone_and_gate_rejections_never_reach_head(self):
        for defect in ('invalid_word','eligibility','label','integrity','replay','identity','boundary','membership'):
            with self.subTest(defect=defect):
                fixture=synthetic_window('SYNTHETIC-REJECT','E',[(3,4)],invalid_word=defect=='invalid_word')
                a=fixture['audit'];w=a['state']['windows'][0]
                if defect=='eligibility':a['exploratory_eligibility']['windows'][0]['eligible']=False
                elif defect=='label':w['label']['status']='uncertain'
                elif defect in ('integrity','replay'):a[defect+'_ok']=False
                elif defect=='identity':fixture['frames'][0]['usb_serial']='OTHER'
                elif defect=='boundary':w['receivers']['RX-02']['included_line_references'][0]['returned_ns']=str(w['T1_ns'])
                elif defect=='membership':fixture['frames'].pop()
                with patch('ruview_presence_port.PresenceSpecialistPort.train',side_effect=AssertionError('Head forbidden')), \
                     patch('ruview_presence_port.PresenceSpecialistPort.infer',side_effect=AssertionError('Head forbidden')):
                    result=features(fixture)
                self.assertEqual(result['feature_status'],'no evaluable');self.assertIsNone(result['features'])
                self.assertFalse(result['inference_executed'])

    def test_altered_raw_reference_and_unsupported_PHY_are_not_reinterpreted(self):
        fixture=synthetic_window('SYNTHETIC-RAW','E',[(3,4)])
        ref=copy.deepcopy(fixture['frames'][0]['window_reference']);ref['line_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'hash'):frame_from_reference(fixture['raw'],ref,CONFIG)
        with self.assertRaises(ValueError):
            frame_from_reference(fixture['raw'],fixture['frames'][0]['window_reference'],dict(CONFIG,lltf_en=False))


if __name__=='__main__':unittest.main()
