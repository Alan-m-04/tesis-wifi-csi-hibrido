"""Keyboard/terminal PTYs owned by tests; native synthetic CSI uses a separate PTY."""
import fcntl
import json
import os
from pathlib import Path
import pty
import select
import subprocess
import sys
import termios
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tools'), str(ROOT / 'tests')]
from devrep_keyboard_prompt import (KeyboardInput, PromptConsole, declaration_status,
                                   pending_declaration, operate, PROMPT_TEXT, SECOND)
from practica_teclado_devrep import practice


class KeyboardTests(unittest.TestCase):
    def setUp(self):
        self.master, self.slave = pty.openpty()
        self.original = termios.tcgetattr(self.slave)
        self.flags = fcntl.fcntl(self.slave, fcntl.F_GETFL)
        self.keyboard = KeyboardInput(self.slave)
        self.addCleanup(os.close, self.master)
        self.addCleanup(os.close, self.slave)
        self.addCleanup(self.keyboard.close)

    def send(self, data):
        os.write(self.master, data)
        self.assertTrue(select.select([self.slave], [], [], .5)[0])
        return self.keyboard.poll()

    def test_no_bytes_or_partial_line_do_not_block_or_submit(self):
        start = time.monotonic()
        for _ in range(100):
            self.assertEqual(self.keyboard.poll(), [])
        self.assertLess(time.monotonic() - start, .25)
        self.assertEqual(self.send(b'declare PRACTICA-TECLADO-E yes'), [])
        self.assertEqual(self.keyboard.text, 'declare PRACTICA-TECLADO-E yes')
        self.assertEqual(self.send(b'\n'), [['declare', 'PRACTICA-TECLADO-E', 'yes']])
        self.assertEqual(self.keyboard.poll(), [])

    def test_utf8_split_backspace_and_ctrl_u(self):
        self.assertEqual(self.send(b'\xc3'), [])
        self.assertEqual(self.send(b'\xa1\x7fno'), [])
        self.assertEqual(self.keyboard.text, 'no')
        self.assertEqual(self.send(b'\x15declare ID uncertain no sal\xc3\xad\n'),
                         [['declare', 'ID', 'uncertain', 'no', 'salí']])

    def test_crlf_submits_exactly_once_and_keeps_multiple_lines(self):
        self.assertEqual(self.send(b'abort\r\n'), [['abort']])
        self.assertEqual(self.send(b'first\nsecond\n'), [['first'], ['second']])

    def test_ctrl_d_does_not_submit_partial_yes(self):
        self.assertEqual(self.send(b'declare ID yes\x04'), [])
        self.assertTrue(self.keyboard.eof)

    def test_ctrl_c_without_controlling_tty_is_abort(self):
        # ISIG consumes this byte on a real controlling terminal; the main loop
        # catches KeyboardInterrupt. Disable ISIG only in this private fixture.
        settings = termios.tcgetattr(self.slave)
        settings[3] &= ~termios.ISIG
        termios.tcsetattr(self.slave, termios.TCSANOW, settings)
        self.assertEqual(self.send(b'\x03'), [['abort']])

    def test_terminal_settings_restore_even_after_invalid_utf8(self):
        with self.assertRaises(UnicodeError):
            self.send(b'\xff\n')
        self.keyboard.close()
        self.assertEqual(termios.tcgetattr(self.slave), self.original)
        self.assertEqual(fcntl.fcntl(self.slave, fcntl.F_GETFL), self.flags)

    def test_overlong_unsubmitted_input_is_bounded(self):
        with self.assertRaises(ValueError):
            for _ in range(20):
                self.send(b'x' * 1024)
        self.assertLessEqual(len(self.keyboard.buffer), 8193)


class ConsoleTests(unittest.TestCase):
    def test_keyboard_preview_and_countdown_repaint_in_place(self):
        master, slave = pty.openpty()
        # A real terminal has nonzero dimensions; give this private PTY 80 columns.
        import struct
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 24, 80, 0, 0))
        console = PromptConsole(slave)
        try:
            console.update(declaration_status('E', 210*SECOND, 150*SECOND, 'decl'))
            console.flush()
            self.assertTrue(select.select([master], [], [], .5)[0])
            first = os.read(master, 65536)
            self.assertIn(PROMPT_TEXT.encode(), first)
            console.update(declaration_status('E', 210*SECOND, 151*SECOND, 'declare'))
            console.flush()
            self.assertTrue(select.select([master], [], [], .5)[0])
            second = os.read(master, 65536)
            self.assertIn(b'\x1b[1A', second)
            self.assertIn(b'tiempo restante: 59 s', second)
            self.assertIn(b'> declare', second)
        finally:
            console.close(); os.close(master); os.close(slave)

    def test_full_pipe_output_returns_without_blocking_and_latest_status_replaces_stale(self):
        read_fd, write_fd = os.pipe()
        console = PromptConsole(write_fd)
        try:
            while True:
                try:
                    os.write(write_fd, b'x' * 4096)
                except BlockingIOError:
                    break
            start = time.monotonic()
            for index in range(1000):
                console.update(f'Latest countdown: {index}')
                console.flush()
            self.assertLess(time.monotonic() - start, .5)
            self.assertEqual(console.message_bytes, 0)
            self.assertEqual(console.status, 'Latest countdown: 999')
            self.assertLess(len(console.pending), 16384)
        finally:
            console.close(); os.close(read_fd); os.close(write_fd)

    def test_long_input_preview_never_hides_prompt_or_remaining_time(self):
        line = declaration_status('SLOT', 210*SECOND, 150*SECOND, 'x'*8192)
        self.assertIn(PROMPT_TEXT, line)
        self.assertIn('tiempo restante: 60 s', line)
        self.assertLess(len(line), 1000)

    def test_deadline_comes_from_anchor_not_prompt_opening(self):
        m = SimpleNamespace(fatal=None, initial_available=7*SECOND,
            plan={'schedule': {'label_due_offsets_ns': [210*SECOND, 420*SECOND]}},
            windows=[dict(id='E', end_signal=0, label=dict(status='pending'))],
            signals=[dict(software_playback_ok=True)])
        self.assertEqual(pending_declaration(m), ('E', 217*SECOND))
        self.assertIn('0 s', declaration_status('E', 217*SECOND, 218*SECOND))
        m.fatal = 'interrupt'
        self.assertIsNone(pending_declaration(m))


class MemoryConsole:
    def __init__(self):
        self.messages, self.statuses = [], []
    def message(self, text):
        self.messages.append(text)
    def update(self, text):
        self.statuses.append(text)
    def flush(self):
        pass


class NativeIntegrationTests(unittest.TestCase):
    def run_native(self, mode):
        from test_presence_rx02 import Rig, PREFIX, boot, fixture_row
        from rx02_devrep_r3_n01.contract import runtime_plan
        from rx02_devrep_r3_n01.session import DevrepSession, audit_devrep
        from preflight_devrep_r3 import template
        rig = Rig()
        self.addCleanup(rig.dispose)
        master, slave = pty.openpty()
        self.addCleanup(os.close, master)
        self.addCleanup(os.close, slave)
        keyboard = KeyboardInput(slave)
        self.addCleanup(keyboard.close)
        rig.pair.fixture_write(PREFIX + boot('RX-02'))
        session = DevrepSession(rig.output, runtime_plan(template()),
                               test_backend=rig.backend, clock=rig.clock)
        self.addCleanup(session._finish_notifier)
        self.addCleanup(session.journal.close_files)
        console = MemoryConsole()
        sent, steps = set(), []
        def pause(_):
            steps.append(1)
            self.assertLess(len(steps), 3000)
            active = pending_declaration(session.machine)
            if active:
                slot, deadline = active
                if slot not in sent:
                    text = f'declare {slot} yes'
                    if mode == 'valid': text += '\n'
                    elif mode == 'uncertain': text = f'declare {slot} uncertain No oí el aviso\n'
                    elif mode == 'abort': text = 'abort\n'
                    elif mode == 'wrong': text = 'declare OTRO yes\n'
                    elif mode == 'eof': text += '\x04'
                    os.write(master, text.encode())
                    sent.add(slot)
            rig.clock.advance(200_000_000)
            if active and mode == 'late' and rig.clock() > active[1] and 'late' not in sent:
                os.write(master, b'\n'); sent.add('late')
            if not session.read_loop_stopped and not session.machine.close_requested:
                rig.pair.fixture_write(fixture_row(rig.ident, 100000 + rig.ident*200000))
                rig.ident += 1
        # Seed service, then use the exact same nonblocking keyboard as practice.
        pause(0)
        operate(session, commands=keyboard, console=console, pause=pause)
        if mode == 'late':
            self.assertIn('late', sent, 'Fixture must actually press Enter after the deadline')
        report = audit_devrep(rig.output)
        self.assertTrue(report['integrity_ok'] and report['replay_ok'])
        self.assertTrue(report['state']['closed']['RX-02']['confirmed'])
        self.assertEqual(sum(call[0] == 'open' for call in rig.calls), 1)
        self.assertEqual(sum(call[0] == 'close' and call[1] for call in rig.calls), 1)
        self.assertTrue(any(PROMPT_TEXT in value for value in console.statuses))
        self.assertEqual(session.machine.plan['schedule']['label_due_offsets_ns'], [210*SECOND, 420*SECOND])
        return report, console

    def test_actual_enter_on_keyboard_pty_confirms_E_and_S_without_stopping_service(self):
        report, console = self.run_native('valid')
        self.assertTrue(report['series_can_continue'])
        self.assertEqual([w['label']['status'] for w in report['state']['windows']], ['declared', 'declared'])
        self.assertTrue(any('tiempo restante:' in value for value in console.statuses))

    def test_partial_line_keeps_CSI_service_alive_until_original_deadline(self):
        report, _ = self.run_native('partial')
        self.assertFalse(report['series_can_continue'])
        self.assertEqual(report['state']['devrep_schedule']['failures'][0]['reason'], 'missing_declaration_by_deadline')
        self.assertEqual(len(report['state']['windows']), 1)
        self.assertEqual(report['state']['windows'][0]['label']['status'], 'pending')
        self.assertGreater(report['operations'], 1000)

    def test_late_enter_never_repairs_expired_label(self):
        report, _ = self.run_native('late')
        self.assertFalse(report['series_can_continue'])
        self.assertEqual(report['state']['devrep_schedule']['failures'][0]['reason'], 'missing_declaration_by_deadline')
        self.assertEqual(report['state']['windows'][0]['label']['status'], 'pending')

    def test_uncertain_abort_wrong_slot_and_EOF_stop_without_implicit_yes(self):
        for mode in ('uncertain', 'abort', 'wrong', 'eof'):
            with self.subTest(mode=mode):
                report, _ = self.run_native(mode)
                self.assertFalse(report['series_can_continue'])
                self.assertEqual(len(report['state']['windows']), 1)
                self.assertNotEqual(report['state']['windows'][0]['label']['status'], 'declared')


class PracticePtyTests(unittest.TestCase):
    def test_practice_timeout_and_uncertainty_never_report_success(self):
        for response in (None, ['declare', 'PRACTICA-TECLADO-E', 'uncertain', 'duda']):
            with self.subTest(response=response):
                now = [0]
                class Commands:
                    text = ''
                    eof = False
                    def poll(self):
                        return [] if response is None else [response]
                console = MemoryConsole()
                def pause(_):
                    now[0] += SECOND
                result = practice(Commands(), console, clock=lambda: now[0], pause=pause, seconds=2)
                self.assertEqual(result, 1)
                self.assertFalse(any('PRÁCTICA TERMINADA' in message for message in console.messages))
                self.assertTrue(any(PROMPT_TEXT in message for message in console.statuses))

    def test_real_practice_process_reads_E_and_S_and_restores_terminal(self):
        master, slave = pty.openpty()
        original = termios.tcgetattr(slave)
        flags = fcntl.fcntl(slave, fcntl.F_GETFL)
        process = subprocess.Popen([sys.executable, '-B', str(ROOT/'tools/practica_teclado_devrep.py'),
            '--seconds-per-prompt', '5'], stdin=slave, stdout=slave, stderr=slave, cwd=ROOT)
        transcript = bytearray(); sent = set(); deadline = time.monotonic() + 10
        try:
            while time.monotonic() < deadline:
                if select.select([master], [], [], .1)[0]:
                    transcript.extend(os.read(master, 65536))
                for condition in ('E', 'S'):
                    marker = f'PRACTICA-TECLADO-{condition}'.encode()
                    if marker in transcript and condition not in sent:
                        os.write(master, f'declare PRACTICA-TECLADO-{condition} yes\n'.encode())
                        sent.add(condition)
                if process.poll() is not None:
                    while select.select([master], [], [], 0)[0]:
                        transcript.extend(os.read(master, 65536))
                    break
            else:
                self.fail('Keyboard practice failed to finish within 10 s')
            self.assertEqual(process.returncode, 0, transcript.decode(errors='replace'))
            text = transcript.decode()
            self.assertIn(PROMPT_TEXT, text)
            self.assertIn('tiempo restante:', text)
            self.assertIn('PRÁCTICA TERMINADA', text)
            self.assertEqual(sent, {'E', 'S'})
            self.assertEqual(termios.tcgetattr(slave), original)
            self.assertEqual(fcntl.fcntl(slave, fcntl.F_GETFL), flags)
        finally:
            if process.poll() is None:
                process.kill(); process.wait()
            os.close(master); os.close(slave)

    def test_practice_has_no_hardware_import_or_capture_argument(self):
        source = (ROOT/'tools/practica_teclado_devrep.py').read_text()
        self.assertNotIn('serial', source)
        self.assertNotIn('DevrepSession', source)
        run = subprocess.run([sys.executable, '-B', 'tools/practica_teclado_devrep.py',
            '--execute-after-approval'], cwd=ROOT, capture_output=True, text=True)
        self.assertNotEqual(run.returncode, 0)

    def test_pipe_EOF_preserves_incomplete_input(self):
        read_fd, write_fd = os.pipe()
        keyboard = KeyboardInput(read_fd)
        try:
            os.write(write_fd, b'declare PRACTICA-TECLADO-E yes')
            os.close(write_fd); write_fd = None
            self.assertEqual(keyboard.poll(), [])
            self.assertEqual(keyboard.poll(), [])
            self.assertTrue(keyboard.eof)
        finally:
            keyboard.close(); os.close(read_fd)
            if write_fd is not None: os.close(write_fd)


if __name__ == '__main__':
    unittest.main()
