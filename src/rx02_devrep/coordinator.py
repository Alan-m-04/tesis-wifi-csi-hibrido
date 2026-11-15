"""Fixed agenda emits existing commands; truth declarations always come from the operator."""
import json
import time
from rx02_devrep.contract import SCHEDULE


class Coordinator:
    def __init__(self,session):self.session=session

    def stop(self,reason,words=None):
        s=self.session
        if not s.machine.fatal:
            s.command('interrupt',detail=json.dumps(dict(scope='DEVREP',reason=reason,operator_input=words)))
        if not s.read_loop_stopped:s.close()

    def poll(self):
        s=self.session;m=s.machine
        # Native step preserves read/tick/audio/actual-close ordering and the strict watchdog.
        s.step()
        if m.fatal:
            if not s.read_loop_stopped:s.close()
            return
        if m.initial_available is None or m.close_requested:return
        index=len(m.windows)
        if index<2 and s.clock()>=m.initial_available+SCHEDULE['request_offsets_ns'][index]:
            try:s.command('request',slot_id=m.plan['slots'][index]['id'],last=index==1)
            except (ValueError,StopIteration) as exc:self.stop('scheduled_request_rejected: '+str(exc))
        if m.close_requested and not s.read_loop_stopped:s.close()

    def operator(self,words):
        s=self.session
        if s.machine.fatal:return
        if words==['abort']:
            self.stop('operator_abort',words);return
        if len(words)>=3 and words[0]=='declare' and words[2] in ('yes','uncertain'):
            if words[2]=='yes' and len(words)!=3:
                self.stop('invalid_yes_with_notes',words);return
            ok=words[2]=='yes'
            try:s.command('declare',slot_id=words[1],established=ok,maintained=ok,heard=ok,notes='' if ok else ' '.join(words[3:]))
            except (ValueError,StopIteration) as exc:self.stop('declaration_rejected: '+str(exc),words)
            if s.machine.close_requested and not s.read_loop_stopped:s.close()
            return
        self.stop('only_declare_or_abort_allowed; slots are scheduled',words)

    @property
    def done(self):
        m=self.session.machine
        return self.session.read_loop_stopped and (bool(m.fatal) or (len(m.windows)==2 and all(w['label']['status']!='pending' for w in m.windows)))


def operate(session,commands=None):
    from piloto_presencia_rx02 import CommandInput
    import sys
    coordinator=Coordinator(session);commands=commands or CommandInput(sys.stdin.fileno());cursor=0;notices=set()
    print('DEVREP: solicitudes automáticas según agenda. Solo declare ID yes|uncertain MOTIVO o abort. No escriba slot.',flush=True)
    try:
        while not coordinator.done:
            coordinator.poll()
            for event in session.machine.events[cursor:]:
                if event['kind'] in ('initial_available','slot_requested','window_started','window_ended_connection_open','selected_port_closed_confirmed','suspended','devrep_schedule_failed','signal_result'):
                    print(json.dumps(event,ensure_ascii=False),flush=True)
            cursor=len(session.machine.events)
            for index,w in enumerate(session.machine.windows):
                cue=w['end_signal']
                if (w['id'] not in notices and w['label']['status']=='pending' and cue is not None and
                    session.machine.signals[cue]['software_playback_ok'] is True and not session.machine.fatal):
                    notices.add(w['id'])
                    print('Declaración humana: declare '+w['id']+' yes SOLO si se cumplió y oyó los avisos; si hay duda: declare '+w['id']+' uncertain MOTIVO. Límite A+'+str(SCHEDULE['label_due_offsets_ns'][index]//1_000_000_000)+' s.',flush=True)
            if coordinator.done:break
            for words in commands.poll():
                coordinator.operator(words)
                if session.machine.fatal:break
            if commands.eof:coordinator.stop('operator_EOF; labels unconfirmed')
            time.sleep(.005)
    except KeyboardInterrupt:
        coordinator.stop('operator_keyboard_interrupt')
    session.finalize()
