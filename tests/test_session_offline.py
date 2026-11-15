"""Synthetic gates and real replay artifact invariants; no training/inference on physical rows."""
import copy
import json
from pathlib import Path
import statistics
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools'),str(ROOT/'tests')]
from devrep_operation_view import render,phase,LEAVE,STAY_OUT,RETURN,SIT,PROMPT_TEXT,sound_pattern
from eligible_presence_features import extract_eligible_window
from test_presence_offline import canonical


def fixture():
    c=canonical();frames=c['receivers']['RX-02']['frames']
    refs=[f['window_reference'] for f in frames]
    w=dict(id='SYNTHETIC-E',condition='E',T0_ns=10_000_000_000,T1_ns=40_000_000_000,
        label=dict(status='declared'),label_quality_ok=True,
        receivers={'RX-02':dict(included_line_references=refs,coverage=dict(included_rows=len(refs)))})
    audit=dict(integrity_ok=True,replay_ok=True,state=dict(protocol='presence_rx02_persistent_1',
        connection=dict(quality_ok=False),windows=[w]),
        exploratory_eligibility=dict(windows=[dict(slot_id=w['id'],eligible=True)]))
    return audit,frames


class FeatureTests(unittest.TestCase):
    def test_complete_mask_features_keep_rejected_connection_and_never_infer(self):
        audit,frames=fixture();before=copy.deepcopy((audit,frames))
        with patch('ruview_presence_port.PresenceSpecialistPort.train',side_effect=AssertionError('No fit')), \
             patch('ruview_presence_port.PresenceSpecialistPort.infer',side_effect=AssertionError('No inference')):
            result=extract_eligible_window(audit,'SYNTHETIC-E',frames)
        self.assertEqual(result['features'],dict(n=3,mean=12,variance=0))
        self.assertFalse(result['connection_full']['quality_ok'])
        self.assertFalse(result['inference_executed'])
        self.assertEqual((audit,frames),before)

    def test_ineligible_missing_reference_mask_and_boundary_abstain(self):
        for change in ('eligibility','missing','mask','time','audit'):
            audit,frames=fixture()
            if change=='eligibility':audit['exploratory_eligibility']['windows'][0]['eligible']=False
            elif change=='missing':frames.pop()
            elif change=='mask':
                b=frames[0]['blocks'][0];b['hardware_valid'][1]=b['cfr_usable'][1]=False
            elif change=='time':frames[0]['window_reference']['returned_ns']='40000000000'
            else:audit['replay_ok']=False
            with self.subTest(change=change):
                result=extract_eligible_window(audit,'SYNTHETIC-E',frames)
                self.assertEqual(result['feature_status'],'no evaluable')
                self.assertIsNone(result['features'])

    def test_scope_cannot_silently_become_dual_v3_or_other_window(self):
        audit,frames=fixture();audit['state']['protocol']='controlled_dual_v3'
        self.assertIsNone(extract_eligible_window(audit,'SYNTHETIC-E',frames)['features'])
        audit,frames=fixture()
        self.assertIsNone(extract_eligible_window(audit,'different',frames)['features'])


class SharedViewTests(unittest.TestCase):
    def machine(self):
        return SimpleNamespace(fatal=None,initial_available=0,closed={},signals=[],
            plan={'schedule':{'label_due_offsets_ns':[210_000_000_000,420_000_000_000]}},
            windows=[dict(id='ID-E',condition='E',start_signal=None,end_signal=None,label={'status':'pending'})])

    def test_both_domains_share_actions_full_commands_and_response_counter(self):
        m=self.machine()
        for domain in ('practice','physical'):self.assertIn(LEAVE,render(m,domain,30_000_000_000))
        m.signals=[dict(kind='establish_condition',software_playback_ok=True)];m.windows[0]['start_signal']=0
        for domain in ('practice','physical'):self.assertIn(STAY_OUT,render(m,domain,60_000_000_000))
        m.signals.append(dict(kind='window_finished_connection_open',software_playback_ok=True));m.windows[0]['end_signal']=1
        for domain in ('practice','physical'):
            view=render(m,domain,150_000_000_000)
            self.assertIn(RETURN,view);self.assertIn(PROMPT_TEXT,view)
            self.assertIn('Tiempo disponible para responder: 60 s',view)
            self.assertIn('declare ID-E yes',view);self.assertIn('declare ID-E uncertain MOTIVO',view)
        m.windows[0]['label']['status']='declared'
        self.assertIn(SIT,render(m,'physical',160_000_000_000))

    def test_physical_closure_requires_proof_even_after_label_or_playback(self):
        m=self.machine();m.windows[0].update(condition='S',id='ID-S')
        m.signals=[dict(kind='selected_port_closed_confirmed',software_playback_ok=True)]
        self.assertIn('FIN SIMULADO',render(m,'practice',340_000_000_000))
        self.assertNotIn('CIERRE FÍSICO COMPROBADO',render(m,'physical',340_000_000_000))
        m.windows[0]['label']['status']='declared'
        self.assertNotIn('CIERRE FÍSICO COMPROBADO',render(m,'physical',340_000_000_000))
        m.closed={'RX-02':dict(confirmed=True,reader_stopped=True)}
        self.assertIn('CIERRE FÍSICO COMPROBADO',render(m,'physical',340_000_000_000))

    def test_mapping_reuses_exact_original_waveforms(self):
        self.assertEqual(sound_pattern('selected_port_closed_confirmed'),'both_ports_closed_confirmed')
        self.assertEqual(sound_pattern('establish_condition'),'establish_condition')


class ReplayArtifactTests(unittest.TestCase):
    def test_four_real_windows_exact_counts_scales_and_feature_definitions(self):
        from demo_offline import DEFAULT
        d=json.loads((DEFAULT/'data.json').read_text())
        expected={'C01':[148,150],'C03':[143,146]}
        for session in d['sessions']:
            self.assertFalse(session['connection']['quality_ok'])
            self.assertEqual([len(w['rows']) for w in session['windows']],expected[session['id']])
            for w in session['windows']:
                self.assertTrue(w['eligibility']['eligible'])
                values=[r['mean'] for r in w['rows']]
                self.assertAlmostEqual(statistics.pvariance(values),w['features']['variance'])
                self.assertAlmostEqual(w['rows'][-1]['sigma_prefix']**2,w['features']['variance'])
                self.assertTrue(all(len(r['amplitudes'])==52 for r in w['rows']))
                self.assertTrue(all(int(w['T0_ns'])<=int(r['first_read_ns'])<=int(r['t_ns'])<int(w['T1_ns']) for r in w['rows']))
                self.assertTrue(all(len(r['cfr_usable'])==64 for r in w['rows']))
                self.assertIsNone(w['rows'][0]['sigma_prefix'])
        self.assertFalse(d['inference_executed']);self.assertFalse(d['reserve_opened'])

    def test_reserved_and_serial_paths_are_rejected_without_opening_them(self):
        from demo_offline import guard,cumulative_sigma
        for path in ('/not-opened/C04/raw.csv','/not-opened/C05','/not-opened/C06','/dev/ttyACM0'):
            with self.assertRaises(PermissionError):guard('open',(path,'r',0))
        self.assertEqual(cumulative_sigma([1,None,3]),[None,None,None])


if __name__=='__main__':unittest.main()
