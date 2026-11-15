"""Practice keyboard PTY and original audio workers, without UART or audio devices."""
import json
import os
from pathlib import Path
import pty
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools'),str(ROOT/'tests')]
from devrep_keyboard_prompt import KeyboardInput, SECOND
from devrep_operation_view import LEAVE,STAY_OUT,RETURN,SIT,PROMPT_TEXT,sound_pattern
from practica_guiada_devrep_v3 import practice
from presence_v4_audio import LaptopNotifier
from rx02_c03.uart import Rx02LaptopNotifier
from test_devrep_keyboard_prompt import MemoryConsole


class SharedPracticePtyTests(unittest.TestCase):
    def test_complete_practice_keyboard_sequence_and_unchanged_schedule(self):
        master,slave=pty.openpty()
        self.addCleanup(os.close,master);self.addCleanup(os.close,slave)
        keyboard=KeyboardInput(slave);self.addCleanup(keyboard.close)
        console=MemoryConsole();now=[0];sent=set();cues=[];pending=[]
        class Audio:
            def start(self,cue):cues.append((now[0],cue));pending.append((cue['id'],True))
            def poll(self):result=pending[:];pending.clear();return result
            def finish(self):pass
        os.write(master,b'practicar\n')
        def pause(_):
            self.assertLess(now[0],430*SECOND)
            status=console.statuses[-1] if console.statuses else ''
            for condition in ('E','S'):
                slot='PRACTICA-GUIADA-'+condition
                if PROMPT_TEXT in status and slot in status and condition not in sent:
                    os.write(master,('declare '+slot+' yes\n').encode());sent.add(condition)
            now[0]+=200_000_000
        plan=json.loads((ROOT/'config/devrep_r4_N01.review.json').read_text())
        before=json.dumps(plan,sort_keys=True)
        result=practice(keyboard,console,Audio(),plan,clock=lambda:now[0],pause=pause)
        self.assertEqual(result['exit_code'],0)
        self.assertEqual(json.dumps(plan,sort_keys=True),before)
        text='\n'.join(console.statuses)
        for phrase in (LEAVE,STAY_OUT,RETURN,SIT,PROMPT_TEXT,'FIN SIMULADO'):
            self.assertIn(phrase,text)
        self.assertLess(text.index(LEAVE),text.index(STAY_OUT))
        self.assertLess(text.index(STAY_OUT),text.index(RETURN))
        self.assertLess(text.index(RETURN),text.index(SIT))
        self.assertNotIn('CIERRE FÍSICO COMPROBADO',text)
        self.assertEqual([c['kind'] for _,c in cues],[
            'establish_condition','window_finished_connection_open',
            'establish_condition','window_finished_connection_open','both_ports_closed_confirmed'])
        self.assertGreaterEqual(cues[0][0],60*SECOND)
        self.assertGreaterEqual(cues[2][0],270*SECOND)

    def test_practice_and_native_workers_generate_identical_sound_bytes(self):
        # Mock only the external player; actual workers and WAV synthesis run.
        # This verifies software waveforms, never human audibility.
        kinds=['establish_condition','window_finished_connection_open','selected_port_closed_confirmed']
        with tempfile.TemporaryDirectory() as tmp,patch('subprocess.run',return_value=SimpleNamespace(returncode=0)) as player:
            native=Rx02LaptopNotifier(Path(tmp)/'native',player='/fixture/not-a-player')
            simulated=LaptopNotifier(Path(tmp)/'practice',player='/fixture/not-a-player')
            for ident,kind in enumerate(kinds):
                native.start(dict(id=ident,kind=kind))
                simulated.start(dict(id=ident,kind=sound_pattern(kind)))
            native.finish();simulated.finish()
            self.assertEqual(native.poll(),[(i,True) for i in range(3)])
            self.assertEqual(simulated.poll(),[(i,True) for i in range(3)])
            self.assertEqual(player.call_count,6)
            for ident,kind in enumerate(kinds):
                a=(Path(tmp)/'native'/f'{ident}-{kind}.wav').read_bytes()
                b=(Path(tmp)/'practice'/f'{ident}-{sound_pattern(kind)}.wav').read_bytes()
                self.assertEqual(a,b)


if __name__=='__main__':unittest.main()
