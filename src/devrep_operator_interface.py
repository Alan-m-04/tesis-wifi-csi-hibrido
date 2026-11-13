"""Reusable acquisition UI adapter; no new protocol, executor, plan or grant.

Select explicitly in a future reviewed entry. Historical R1-R4 sources stay frozen.
"""
import sys
from devrep_keyboard_prompt import KeyboardInput,PromptConsole,operate as native_keyboard_operate
from devrep_operation_view import render


class PresentationConsole:
    def __init__(self,base,session,keyboard):self.base,self.session,self.keyboard=base,session,keyboard
    def message(self,text):self.base.message(text)
    def update(self,_):self.base.update(render(self.session.machine,'physical',self.session.clock(),self.keyboard.text))
    def flush(self):self.base.flush()


class FeedbackInput:
    def __init__(self,base,session,console):self.base,self.session,self.console=base,session,console
    @property
    def text(self):return self.base.text
    @property
    def eof(self):return self.base.eof
    def poll(self):
        commands=self.base.poll()
        for words in commands:
            if words==['abort']:continue
            slots=self.session.machine.windows
            slot=slots[-1]['id'] if slots else None
            form=(len(words)==3 and words[:2]==['declare',slot] and words[2]=='yes') or (
                len(words)>=4 and words[:2]==['declare',slot] and words[2]=='uncertain')
            if not form:
                expected=(f'declare {slot} yes | declare {slot} uncertain MOTIVO | abort' if slot else 'abort; espera la solicitud automática')
                self.console.message('[ADQUISICIÓN FÍSICA] ENTRADA INVÁLIDA. Se esperaba: '+expected+
                    '. El validador nativo conserva su política de parada.')
        # Never repair, shorten, auto-submit or replace the original input.
        return commands


def operate(session,commands=None,console=None,**kwargs):
    own_keyboard=commands is None;own_console=console is None
    keyboard=commands
    try:
        if own_keyboard:keyboard=KeyboardInput(sys.stdin.fileno())
        if own_console:console=PromptConsole(sys.stdout.fileno())
        feedback=FeedbackInput(keyboard,session,console)
        return native_keyboard_operate(session,commands=feedback,
            console=PresentationConsole(console,session,keyboard),**kwargs)
    finally:
        try:
            if own_console and console is not None:console.close()
        finally:
            if own_keyboard and keyboard is not None:keyboard.close()
