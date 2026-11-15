"""Reusable presentation with native synthetic CSI service and an owned keyboard PTY."""
import os
from pathlib import Path
import pty
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools'),str(ROOT/'tests')]
from devrep_operator_interface import operate
from devrep_keyboard_prompt import KeyboardInput
from devrep_operation_view import PROMPT_TEXT,LEAVE,STAY_OUT,RETURN,SIT
from test_devrep_keyboard_prompt import MemoryConsole


class SharedOperatorPtyTests(unittest.TestCase):
    def run_fixture(self,invalid=False):
        from test_presence_rx02 import Rig,PREFIX,boot,fixture_row
        from rx02_devrep_r4_n01.contract import runtime_plan
        from rx02_devrep_r4_n01.session import DevrepSession,audit_devrep
        from preflight_devrep_r4 import template
        rig=Rig();self.addCleanup(rig.dispose)
        master,slave=pty.openpty();self.addCleanup(os.close,master);self.addCleanup(os.close,slave)
        keyboard=KeyboardInput(slave);self.addCleanup(keyboard.close)
        rig.pair.fixture_write(PREFIX+boot('RX-02'))
        session=DevrepSession(rig.output,runtime_plan(template()),test_backend=rig.backend,clock=rig.clock)
        self.addCleanup(session.journal.close_files);self.addCleanup(session._finish_notifier)
        console=MemoryConsole();sent=set();steps=[]
        def pause(_):
            steps.append(1);self.assertLess(len(steps),2300)
            status=console.statuses[-1] if console.statuses else ''
            for c in ('E','S'):
                slot='RX02-DEVREP-R4-N01-'+c
                if PROMPT_TEXT in status and slot in status and c not in sent:
                    text='guiada-e' if invalid else 'declare '+slot+' yes'
                    os.write(master,(text+'\n').encode());sent.add(c)
            rig.clock.advance(200_000_000)
            if not session.read_loop_stopped and not session.machine.close_requested:
                rig.pair.fixture_write(fixture_row(rig.ident,100000+rig.ident*200000));rig.ident+=1
        pause(0);operate(session,commands=keyboard,console=console,pause=pause)
        report=audit_devrep(rig.output)
        self.assertTrue(report['integrity_ok'] and report['replay_ok'])
        self.assertTrue(report['state']['closed']['RX-02']['confirmed'])
        return report,console

    def test_shared_instructions_full_cycle_native_deadlines_and_closure(self):
        report,console=self.run_fixture()
        self.assertTrue(report['series_can_continue'])
        text='\n'.join(console.statuses)
        for instruction in (LEAVE,STAY_OUT,RETURN,SIT,PROMPT_TEXT):self.assertIn(instruction,text)
        self.assertIn('Tiempo disponible para responder:',text)
        self.assertIn('CIERRE FÍSICO COMPROBADO',text)
        self.assertNotIn('FIN SIMULADO',text)

    def test_shorthand_is_explained_then_passed_unchanged_to_native_stop(self):
        report,console=self.run_fixture(invalid=True)
        self.assertFalse(report['series_can_continue'])
        self.assertEqual(report['state']['windows'][0]['label']['status'],'pending')
        text='\n'.join(console.messages)
        self.assertIn('ENTRADA INVÁLIDA',text)
        self.assertIn('declare RX02-DEVREP-R4-N01-E yes',text)


if __name__=='__main__':unittest.main()
