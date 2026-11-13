"""Specific practice exits and scoped notices; no physical acquisition entry."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools'),str(ROOT/'tests')]
from devrep_practice_diagnostics_v3 import DiagnosticPractice,stop_message,practice_instruction
from practica_guiada_devrep_v3 import PracticeLog,practice
from test_devrep_keyboard_prompt import MemoryConsole
from devrep_keyboard_prompt import SECOND
from devrep_operation_view import PROMPT_TEXT


def plan():return json.loads((ROOT/'config/devrep_r4_N01.review.json').read_text())


def ready_E():
    m=DiagnosticPractice(plan())
    for t in (30,60):m.tick(t*SECOND)
    m.ack(0,True)
    for t in (90,120,130):m.tick(t*SECOND)
    m.ack(1,True)
    return m


class ClassificationTests(unittest.TestCase):
    def test_invalid_uncertain_cancelled_and_expired_have_distinct_messages(self):
        examples=[(['no'],'invalid_input','ENTRADA INVÁLIDA'),
                  (['declare','PRACTICA-GUIADA-E','uncertain','No','salí'],'uncertain','INCERTIDUMBRE'),
                  (['abort'],'cancelled','CANCELADA')]
        for words,code,text in examples:
            with self.subTest(code=code):
                m=ready_E();m.command(words)
                self.assertEqual(m.termination['code'],code)
                self.assertIn(text,stop_message(m.termination))
                self.assertIn('[PRÁCTICA]',stop_message(m.termination))
                self.assertEqual(m.windows[0]['label']['status'],'pending')
        m=ready_E();m.tick(210*SECOND+1)
        self.assertEqual(m.termination['code'],'expired')
        self.assertIn('A+210 s',stop_message(m.termination))

    def test_wrong_ID_blank_input_and_missing_uncertainty_reason_are_invalid(self):
        for words in ([],['declare','RX02-DEVREP-R4-N01-E','yes'],
                      ['declare','PRACTICA-GUIADA-E','uncertain'],
                      ['declare','PRACTICA-GUIADA-E','yes','nota']):
            with self.subTest(words=words):
                m=ready_E();m.command(words)
                self.assertEqual(m.termination['code'],'invalid_input')
                self.assertIn('Se esperaba:',stop_message(m.termination))
                self.assertIn('PRACTICA-GUIADA-E',stop_message(m.termination))

    def test_premature_yes_has_specific_reason(self):
        m=DiagnosticPractice(plan());m.tick(30*SECOND)
        m.command(['declare','PRACTICA-GUIADA-E','yes'])
        self.assertEqual(m.termination['origin'],'premature_declaration')
        self.assertIn('aún no está habilitada',m.termination['detail'])

    def test_physical_ID_in_practice_is_explained_as_wrong_scope(self):
        m=ready_E();m.command(['declare','RX02-DEVREP-R4-N01-E','yes'])
        self.assertEqual(m.termination['origin'],'physical_ID_in_practice')
        self.assertIn('Usa el ID PRACTICA-GUIADA',stop_message(m.termination))

    def test_deadline_and_primary_reason_are_not_reset_by_late_input_or_audio_failure(self):
        m=ready_E();schedule=copy.deepcopy(m.plan['schedule'])
        m.tick(210*SECOND+1)
        m.command(['declare','PRACTICA-GUIADA-E','yes'])
        m.fail('practice_audio_failed')
        self.assertEqual(m.termination['code'],'expired')
        self.assertEqual(m.plan['schedule'],schedule)
        self.assertFalse(m.done)

    def test_practice_stops_do_not_emit_physical_failure_alarm(self):
        m=ready_E();m.command(['abort'])
        self.assertFalse(any(s['kind']=='failure' for s in m.signals))

    def test_practice_wording_never_claims_physical_failure_or_close(self):
        m=ready_E();m.close_cue=None
        self.assertNotIn('CIERRE CONFIRMADO',practice_instruction(m))
        m.command(['abort'])
        self.assertNotIn('INTENTO DETENIDO',practice_instruction(m))


class RunTests(unittest.TestCase):
    def run_practice(self,mode):
        now=[0];console=MemoryConsole()
        class Audio:
            def __init__(self):self.requests=[];self.finished=False
            def start(self,cue):self.requests.append(cue)
            def poll(self):
                cues,self.requests=self.requests,[]
                return [(c['id'],mode!='audio_error') for c in cues]
            def finish(self):self.finished=True
        class Keyboard:
            text='';eof=False
            def __init__(self):self.started=False;self.sent=set()
            def poll(self):
                if not self.started:
                    self.started=True
                    if mode=='startup_invalid':return [['empezar']]
                    if mode=='startup_abort':return [['abort']]
                    if mode=='EOF':self.text='declaración sin Enter';self.eof=True;return []
                    return [['practicar']]
                if mode=='ctrl_c':raise KeyboardInterrupt
                status=console.statuses[-1]
                for c in ('E','S'):
                    slot='PRACTICA-GUIADA-'+c
                    if PROMPT_TEXT in status and slot in status and c not in self.sent:
                        self.sent.add(c)
                        if mode=='expired':self.text='declare '+slot+' yes';return []
                        if mode=='invalid_input':return [['declare','OTRO','yes']]
                        if mode=='uncertain':return [['declare',slot,'uncertain','No','oí']]
                        return [['declare',slot,'yes']]
                return []
        def pause(_):now[0]+=200_000_000
        with tempfile.TemporaryDirectory() as d:
            log=PracticeLog(d);audio=Audio()
            result=practice(Keyboard(),console,audio,plan(),clock=lambda:now[0],pause=pause,log=log)
            saved=json.loads((log.root/'resultado-practica.json').read_text())
            self.assertEqual(saved['code'],result['code'])
            self.assertTrue(saved['practice_only'])
            self.assertFalse(saved['physical_capture_executed'])
            self.assertTrue(audio.finished)
            events=[json.loads(line) for line in (log.root/'eventos-practica.jsonl').read_text().splitlines()]
            self.assertEqual(events[-1]['kind'],'practice_finished')
            self.assertTrue(all(e['practice_only'] for e in events))
            return result,'\n'.join(console.messages+console.statuses)

    def test_specific_startup_errors_EOF_ctrl_C_uncertainty_expiration_and_audio_errors(self):
        cases={'startup_invalid':'invalid_input','startup_abort':'cancelled','EOF':'cancelled',
               'ctrl_c':'cancelled','invalid_input':'invalid_input','uncertain':'uncertain',
               'expired':'expired','audio_error':'audio_error'}
        for mode,expected in cases.items():
            with self.subTest(mode=mode):
                result,text=self.run_practice(mode)
                self.assertEqual(result['code'],expected)
                self.assertNotEqual(result['exit_code'],0)
                self.assertNotIn('EJERCICIO COMPLETADO',text)
                self.assertNotIn('INTENTO DETENIDO',text)
                self.assertNotIn('CIERRE CONFIRMADO',text)
        result,text=self.run_practice('expired')
        self.assertEqual(result['unsubmitted_input'],'declare PRACTICA-GUIADA-E yes')

    def test_complete_run_is_practice_only_with_simulated_final_notice(self):
        result,text=self.run_practice('completed')
        self.assertEqual(result['exit_code'],0)
        self.assertEqual(result['recognized_practice_slots'],['PRACTICA-GUIADA-E','PRACTICA-GUIADA-S'])
        self.assertIn('FIN SIMULADO',text)
        self.assertIn('[PRÁCTICA] EJERCICIO COMPLETADO',text)
        self.assertNotIn('CIERRE CONFIRMADO',text)

    def test_actual_CLI_invalid_startup_prints_reason_and_saves_log(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'config').mkdir()
            (root/'config/devrep_r4_N01.review.json').write_text(json.dumps(plan()))
            code=('import sys; from pathlib import Path; sys.path[:0]=["src","tools"]; '
                  'import practica_guiada_devrep_v3 as cli; cli.ROOT=Path(sys.argv[1]); '
                  'cli.shutil.which=lambda _: "/unused/aplay"; '
                  'raise SystemExit(cli.main([]))')
            run=subprocess.run([sys.executable,'-B','-c',code,str(root)],input='empezar\n',
                capture_output=True,text=True,timeout=5,cwd=ROOT)
            self.assertEqual(run.returncode,2,run.stderr)
            self.assertIn('ENTRADA INVÁLIDA EN PRÁCTICA',run.stdout)
            results=list((root/'results/local').glob('practica-guiada-v3-*/resultado-practica.json'))
            self.assertEqual(len(results),1)
            self.assertEqual(json.loads(results[0].read_text())['origin'],'startup_input')

    def test_missing_player_is_audio_error_not_invalid_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            code=('import sys; from pathlib import Path; sys.path[:0]=["src","tools"]; '
                  'import practica_guiada_devrep_v3 as cli; cli.ROOT=Path(sys.argv[1]); '
                  'cli.shutil.which=lambda _: None; raise SystemExit(cli.main([]))')
            run=subprocess.run([sys.executable,'-B','-c',code,str(root)],
                capture_output=True,text=True,timeout=5,cwd=ROOT)
            self.assertEqual(run.returncode,5)
            self.assertIn('FALLO DE AUDIO EN PRÁCTICA',run.stdout)
            result=next((root/'results/local').glob('*/resultado-practica.json'))
            self.assertEqual(json.loads(result.read_text())['code'],'audio_error')


if __name__=='__main__':unittest.main()
