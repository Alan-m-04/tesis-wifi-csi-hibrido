"""Condition instructions and real WAV generation; no physical UART or labels."""
import copy
import json
import os
from pathlib import Path
import pty
import sys
import tempfile
import unittest
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'tools'), str(ROOT/'tests')]
from devrep_guided_prompt_v2 import Guidance, LEAVE, STAY_OUT, RETURN, SIT, operate
from devrep_keyboard_prompt import KeyboardInput, PROMPT_TEXT, SECOND, declaration_status
from practica_guiada_devrep_v2 import PracticeTimeline, practice
from presence_v4_audio import create_wav, PATTERNS
from test_devrep_keyboard_prompt import MemoryConsole


def plan():
    return json.loads((ROOT/'config/devrep_r4_N01.review.json').read_text())


class GuidanceTests(unittest.TestCase):
    def setUp(self):
        self.m = PracticeTimeline(plan())
        self.g = Guidance()
        self.cursor = 0

    def update(self):
        for event in self.m.events[self.cursor:]:
            self.g.event(event, self.m)
        self.cursor = len(self.m.events)
        return self.g.current(self.m)

    def tick(self, seconds):
        self.m.tick(int(seconds*SECOND))
        return self.update()

    def ack(self, ident, success=True):
        self.m.ack(ident, success)
        return self.update()

    def test_complete_event_instruction_and_sound_sequence_preserves_deadlines(self):
        original = copy.deepcopy(self.m.plan)
        self.assertIn(LEAVE, self.tick(30))
        self.assertIn(STAY_OUT, self.tick(60))
        self.assertIn(STAY_OUT, self.ack(0))
        self.assertIn(STAY_OUT, self.tick(90))
        self.assertIn(STAY_OUT, self.tick(120))
        self.assertNotIn(RETURN, self.g.current(self.m))
        self.assertIn(STAY_OUT, self.tick(129.9))
        self.assertIn(STAY_OUT, self.tick(130))
        self.assertIn(RETURN, self.ack(1))
        self.m.command(['declare','PRACTICA-GUIADA-E','yes'])
        self.assertIn(SIT, self.update())
        self.assertIn(SIT, self.tick(240))
        self.assertIn(SIT, self.tick(270))
        self.ack(2)
        self.assertIn(SIT, self.tick(300))
        self.assertIn(SIT, self.tick(330))
        self.assertIn(SIT, self.tick(340))
        self.assertIn(SIT, self.ack(3))
        # A recorded closure event alone is not completed playback of three long tones.
        self.assertIsNone(self.m.pending())
        premature = declaration_status('PRACTICA-GUIADA-S',420*SECOND,340*SECOND)
        self.assertNotIn(PROMPT_TEXT, self.g.render(premature,self.m))
        self.assertIn('CIERRE CONFIRMADO', self.ack(4))
        self.assertIsNotNone(self.m.pending())
        self.m.command(['declare','PRACTICA-GUIADA-S','yes'])
        self.assertTrue(self.m.done)
        self.assertEqual(self.m.plan, original)
        self.assertEqual(self.m.plan['schedule']['label_due_offsets_ns'], [210*SECOND,420*SECOND])
        self.assertEqual([cue['kind'] for cue in self.m.signals],
            ['establish_condition','window_finished_connection_open','establish_condition',
             'window_finished_connection_open','selected_port_closed_confirmed'])

    def test_missing_E_stops_at_original_deadline_before_S(self):
        self.tick(30);self.tick(60);self.ack(0);self.tick(90);self.tick(120);self.tick(130);self.ack(1)
        self.assertIn(RETURN, self.g.current(self.m))
        self.assertIn('DETENIDO', self.tick(210.001))
        self.assertEqual(len(self.m.windows),1)
        self.assertEqual(self.m.windows[0]['label']['status'],'pending')
        self.assertFalse(self.m.done)

    def test_audio_failure_never_invites_return_or_yes(self):
        self.tick(30);self.tick(60)
        self.assertIn('DETENIDO',self.ack(0,False))
        self.assertNotIn(RETURN,self.g.current(self.m))
        self.assertIsNone(self.m.pending())

    def test_window_end_before_final_sound_never_invites_return(self):
        self.tick(30);self.tick(60);self.ack(0);self.tick(90)
        self.assertNotIn(RETURN,self.tick(120))
        self.assertNotIn(RETURN,self.tick(130))
        self.assertIsNone(self.m.pending())

    def test_directly_receiving_native_start_cue_state_updates_persistent_instruction(self):
        self.tick(30)
        self.m.tick(60*SECOND)
        # Frozen v1 forwards only selected JSON events; state still carries start_signal.
        self.assertIn(STAY_OUT,self.g.current(self.m))


class SoundPracticeTests(unittest.TestCase):
    def test_complete_practice_generates_five_original_WAVs_and_recognizes_inputs(self):
        clock=[0];console=MemoryConsole()
        with tempfile.TemporaryDirectory() as directory:
            class Audio:
                def __init__(self):self.pending=[];self.kinds=[];self.finished=False
                def start(self,cue):
                    path=Path(directory)/(str(cue['id'])+'-'+cue['kind']+'.wav')
                    create_wav(path,cue['kind'])
                    with wave.open(str(path),'rb') as wav:
                        self_test.assertEqual(wav.getframerate(),16000)
                        self_test.assertEqual(wav.getnchannels(),1)
                        duration=wav.getnframes()/wav.getframerate()
                    count,length,_=PATTERNS[cue['kind']]
                    self_test.assertAlmostEqual(duration,count*(length+.15),places=3)
                    self.pending.append((clock[0]+int(duration*SECOND),cue['id']))
                    self.kinds.append(cue['kind'])
                def poll(self):
                    ready=[(ident,True) for due,ident in self.pending if due<=clock[0]]
                    self.pending=[(due,ident) for due,ident in self.pending if due>clock[0]]
                    return ready
                def finish(self):self.finished=True
            class Commands:
                text='';eof=False
                def __init__(self):self.started=False;self.sent=set()
                def poll(self):
                    if not self.started:self.started=True;return [['practicar']]
                    status=console.statuses[-1]
                    for c in ('E','S'):
                        slot='PRACTICA-GUIADA-'+c
                        if PROMPT_TEXT in status and slot in status and c not in self.sent:
                            self.sent.add(c);return [['declare',slot,'yes']]
                    return []
            def pause(_):clock[0]+=200_000_000
            self_test=self;audio=Audio();commands=Commands()
            rc=practice(commands,console,audio,plan(),clock=lambda:clock[0],pause=pause)
            self.assertEqual(rc,0)
            self.assertEqual(commands.sent,{'E','S'})
            self.assertTrue(audio.finished)
            self.assertEqual(audio.kinds,['establish_condition','window_finished_connection_open',
                'establish_condition','window_finished_connection_open','both_ports_closed_confirmed'])
            statuses='\n'.join(console.statuses)
            self.assertLess(statuses.index(LEAVE),statuses.index(STAY_OUT))
            self.assertLess(statuses.index(STAY_OUT),statuses.index(RETURN))
            self.assertLess(statuses.index(RETURN),statuses.index(SIT))
            self.assertIn('PRACTICA-GUIADA-S', '\n'.join(console.messages))
            self.assertTrue(any('PRÁCTICA TERMINADA' in message for message in console.messages))


class NativeIntegrationTests(unittest.TestCase):
    def test_native_CSI_and_keyboard_PTY_use_guidance_without_changing_timing_or_replay(self):
        from test_presence_rx02 import Rig, PREFIX, boot, fixture_row
        from rx02_devrep_r4_n01.contract import runtime_plan
        from rx02_devrep_r4_n01.session import DevrepSession,audit_devrep
        from preflight_devrep_r4 import template
        rig=Rig();self.addCleanup(rig.dispose)
        master,slave=pty.openpty()
        self.addCleanup(os.close,master);self.addCleanup(os.close,slave)
        keyboard=KeyboardInput(slave);self.addCleanup(keyboard.close)
        rig.pair.fixture_write(PREFIX+boot('RX-02'))
        session=DevrepSession(rig.output,runtime_plan(template()),test_backend=rig.backend,clock=rig.clock)
        self.addCleanup(session._finish_notifier);self.addCleanup(session.journal.close_files)
        console=MemoryConsole();sent=set();steps=[]
        def pause(_):
            steps.append(1);self.assertLess(len(steps),2300)
            status=console.statuses[-1] if console.statuses else ''
            for c in ('E','S'):
                slot='RX02-DEVREP-R4-N01-'+c
                if PROMPT_TEXT in status and slot in status and c not in sent:
                    os.write(master,('declare '+slot+' yes\n').encode());sent.add(c)
            rig.clock.advance(200_000_000)
            if not session.read_loop_stopped and not session.machine.close_requested:
                rig.pair.fixture_write(fixture_row(rig.ident,100000+rig.ident*200000));rig.ident+=1
        pause(0)
        operate(session,commands=keyboard,console=console,pause=pause)
        report=audit_devrep(rig.output)
        self.assertTrue(report['integrity_ok'] and report['replay_ok'] and report['series_can_continue'])
        self.assertEqual(sent,{'E','S'})
        self.assertEqual(sum(call[0]=='open' for call in rig.calls),1)
        self.assertTrue(report['state']['closed']['RX-02']['confirmed'])
        text='\n'.join(console.statuses)
        for phrase in (LEAVE,STAY_OUT,RETURN,SIT):self.assertIn(phrase,text)
        self.assertLess(text.index(LEAVE),text.index(STAY_OUT))
        self.assertLess(text.index(STAY_OUT),text.index(RETURN))
        self.assertLess(text.index(RETURN),text.index(SIT))
        self.assertEqual(session.machine.plan['schedule']['label_due_offsets_ns'],[210*SECOND,420*SECOND])


if __name__=='__main__':unittest.main()
