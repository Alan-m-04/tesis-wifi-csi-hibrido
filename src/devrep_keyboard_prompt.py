"""Opt-in terminal UI; frozen native coordinator owns all acquisition deadlines.

No transport, authorization, plan mutation or automatic submission lives here.
Input/output use nonblocking fds, bounded buffers and one syscall per service step.
"""
from collections import deque
import copy
import fcntl
import json
import os
import termios
import time
import unicodedata

PROMPT_TEXT = 'ESCRIBE AQUÍ LA DECLARACIÓN Y PULSA ENTER'
SECOND = 1_000_000_000


class KeyboardInput:
    """Own stdin temporarily, with visible editing supplied by PromptConsole.

    A partial UTF-8 line is never a command. Enter submits once. Backspace and
    Ctrl-U edit; Ctrl-D/pipe EOF never submits an unfinished declaration.
    """
    def __init__(self, fd):
        self.fd = fd
        self.buffer = bytearray()
        self.eof = False
        self.after_cr = False
        self.flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        self.attributes = None
        self.closed = False
        try:
            if os.isatty(fd):
                self.attributes = termios.tcgetattr(fd)
                settings = copy.deepcopy(self.attributes)
                # Handle Enter/CRLF ourselves; kernel ICRNL would turn CRLF into
                # two newlines and submit an extra empty command.
                settings[0] &= ~(termios.ICRNL | termios.INLCR | termios.IGNCR)
                settings[3] &= ~(termios.ICANON | termios.ECHO)
                settings[6][termios.VMIN] = 0
                settings[6][termios.VTIME] = 0
                termios.tcsetattr(fd, termios.TCSANOW, settings)
            fcntl.fcntl(fd, fcntl.F_SETFL, self.flags | os.O_NONBLOCK)
        except BaseException:
            self.close()
            raise

    @property
    def text(self):
        # Only the preview can contain a replacement glyph while UTF-8 is partial.
        return self.buffer.decode('utf-8', errors='replace')

    def poll(self):
        if self.eof:
            return []
        try:
            data = os.read(self.fd, 4096)
        except (BlockingIOError, InterruptedError):
            return []
        if not data:
            # VMIN=0 terminals can return zero with no input; pipes mean EOF.
            if not os.isatty(self.fd):
                self.eof = True
            return []
        commands = []
        for byte in data:
            if byte == 10 and self.after_cr:
                self.after_cr = False
                continue
            self.after_cr = byte == 13
            if byte in (10, 13):
                line = self.buffer.decode('utf-8', errors='strict').strip()
                self.buffer.clear()
                commands.append(line.split())
            elif byte in (8, 127):
                if self.buffer:
                    while self.buffer and self.buffer[-1] & 0xC0 == 0x80:
                        self.buffer.pop()
                    if self.buffer:
                        self.buffer.pop()
            elif byte == 21:  # Ctrl-U
                self.buffer.clear()
            elif byte == 4:  # Ctrl-D
                self.eof = True
                break
            elif byte == 3:  # PTY/noncontrolling stdin; real ISIG raises KeyboardInterrupt.
                commands.append(['abort'])
                break
            elif byte >= 32 or byte == 9:
                self.buffer.append(byte)
                if len(self.buffer) > 8192:
                    raise ValueError('Operator input exceeded 8192 bytes')
        return commands

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            if self.attributes is not None:
                termios.tcsetattr(self.fd, termios.TCSANOW, self.attributes)
        finally:
            fcntl.fcntl(self.fd, fcntl.F_SETFL, self.flags)


class PromptConsole:
    """One bounded nonblocking write per tick; a slow terminal cannot hold service.

    Event messages are queued with a fixed budget. Countdown/preview updates
    replace the stale status rather than forming an unbounded output queue.
    """
    def __init__(self, fd):
        self.fd = fd
        self.tty = os.isatty(fd)
        self.flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        self.messages = deque()
        self.message_bytes = 0
        self.pending = b''
        self.status = self.sent_status = ''
        self.display_rows = 0
        self.closed = False
        fcntl.fcntl(fd, fcntl.F_SETFL, self.flags | os.O_NONBLOCK)

    def message(self, text):
        data = (str(text) + '\n').encode('utf-8')
        if self.message_bytes + len(data) > 65536:
            raise ValueError('Terminal output backlog exceeded 65536 bytes')
        self.messages.extend(data[index:index+8192] for index in range(0, len(data), 8192))
        self.message_bytes += len(data)

    def update(self, status):
        self.status = status

    def _display(self):
        if not self.tty:
            return self.status[-4096:]
        # Wrap explicitly before the terminal margin so repainting can return
        # to the exact prompt start. Keystrokes update in place, without scrolling
        # a new banner into the log for every character.
        width = max(2, (os.get_terminal_size(self.fd).columns or 80) - 1)
        lines = []
        for logical in self.status.expandtabs(4).split('\n'):
            line, occupied = '', 0
            for char in logical:
                size = 0 if unicodedata.combining(char) else (2 if unicodedata.east_asian_width(char) in 'WF' else 1)
                if line and occupied + size > width:
                    lines.append(line); line, occupied = '', 0
                line += char; occupied += size
            lines.append(line)
        return '\n'.join(lines)

    def flush(self):
        if not self.pending:
            if not self.messages and self.status == self.sent_status:
                return
            parts = ([b'\r\x1b[2K' + b'\x1b[1A\r\x1b[2K' * self.display_rows]
                     if self.tty else [])
            size = 0
            while self.messages and size + len(self.messages[0]) <= 8192:
                data = self.messages.popleft()
                self.message_bytes -= len(data)
                parts.append(data)
                size += len(data)
            # Input preview is bounded separately; truncate display, never the command.
            display = self._display()
            parts.append(display.encode('utf-8'))
            self.display_rows = display.count('\n')
            if not self.tty:
                parts.append(b'\n')
            self.pending = b''.join(parts)
            self.sent_status = self.status
        try:
            count = os.write(self.fd, self.pending[:16384])
        except (BlockingIOError, InterruptedError):
            return
        self.pending = self.pending[count:]

    def close(self):
        if self.closed:
            return
        self.closed = True
        fcntl.fcntl(self.fd, fcntl.F_SETFL, self.flags)


def declaration_status(slot_id, deadline_ns, now_ns, typed=''):
    remaining = max(0, deadline_ns - now_ns) // SECOND
    return (f'{PROMPT_TEXT}\n{slot_id} | tiempo restante: {remaining} s\n'
            f'Si se cumplió: declare {slot_id} yes\n'
            f'Si hay dudas: declare {slot_id} uncertain MOTIVO\n> {typed[-512:]}')


def pending_declaration(machine):
    if machine.fatal or machine.initial_available is None:
        return None
    for index, window in enumerate(machine.windows):
        cue = window['end_signal']
        if (window['label']['status'] == 'pending' and cue is not None and
                machine.signals[cue]['software_playback_ok'] is True):
            # Read the preregistered absolute deadline; opening a prompt never resets it.
            deadline = (machine.initial_available +
                        machine.plan['schedule']['label_due_offsets_ns'][index])
            return window['id'], deadline
    return None


def operate(session, commands=None, console=None, *, pause=time.sleep):
    """Future opt-in operation; native Coordinator.poll/operator stay authoritative.

    No physical entry selects this function yet. Tests use only owned PTYs.
    """
    from rx02_devrep.coordinator import Coordinator
    import sys
    owned_input = owned_console = False
    coordinator = Coordinator(session)
    cursor = 0
    try:
        if commands is None:
            commands = KeyboardInput(sys.stdin.fileno())
            owned_input = True
        if console is None:
            console = PromptConsole(sys.stdout.fileno())
            owned_console = True
        console.message('Solicitudes automáticas. Escriba la declaración completa y pulse Enter. '
                        'Retroceso corrige; Ctrl-U borra. No escriba slot.')
        while not coordinator.done:
            coordinator.poll()
            for event in session.machine.events[cursor:]:
                if event['kind'] in ('initial_available', 'slot_requested', 'window_started',
                        'window_ended_connection_open', 'selected_port_closed_confirmed',
                        'suspended', 'devrep_schedule_failed', 'signal_result'):
                    console.message(json.dumps(event, ensure_ascii=False))
            cursor = len(session.machine.events)
            active = pending_declaration(session.machine)
            if coordinator.done:
                console.update('Intento detenido. Conserve la evidencia; no relance el comando.'
                               if session.machine.fatal else 'Lectura cerrada; declaraciones terminadas.')
            elif active:
                console.update(declaration_status(*active, session.clock(), commands.text))
            else:
                console.update('Sin declaración solicitada; la agenda continúa. > ' + commands.text)
            console.flush()
            if coordinator.done:
                break
            for words in commands.poll():
                console.message('Entrada enviada: ' + ' '.join(words))
                coordinator.operator(words)
                if session.machine.fatal:
                    break
            if commands.eof:
                coordinator.stop('operator_EOF; labels unconfirmed')
            pause(.005)
    except KeyboardInterrupt:
        coordinator.stop('operator_keyboard_interrupt')
    except (OSError, ValueError) as exc:
        coordinator.stop('operator_interface_error: ' + str(exc))
    finally:
        try:
            if not session.read_loop_stopped:
                coordinator.stop('operator_interface_exit')
            session.finalize()
        finally:
            try:
                if owned_console:
                    console.close()
            finally:
                if owned_input:
                    commands.close()
