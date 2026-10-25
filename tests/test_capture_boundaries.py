"""Synthetic streams and private PTYs only. No hardware discovery/open calls."""
import json
import os
from pathlib import Path
import pty
import tempfile
import threading
import time
import tty
import unittest
from unittest.mock import patch

import serial
import capture_csi_multi as capture
from bounded_frame_reader import read_to_boundary
from preserving_serial import preserving_serial_type
from test_validate_capture import frame
from validate_capture import scan_raw


class ScriptPort:
    """Deterministic chunks/return times, with real read-size/timeout contracts."""
    port = 'SYNTHETIC'
    timeout = .1

    def __init__(self, chunks):
        self.chunks = list(chunks)
        self.now = 0
        self.requests = []

    @property
    def in_waiting(self):
        return len(self.chunks[0][1]) if self.chunks else 0

    def read(self, size):
        self.requests.append((size, self.timeout))
        if not self.chunks:
            self.now += max(1, int(self.timeout * 1e9))
            return b''
        when, chunk = self.chunks[0]
        available_at = max(when, self.now + 1)
        if available_at > self.now + int(self.timeout * 1e9):
            self.now += max(1, int(self.timeout * 1e9))
            return b''
        self.now = available_at
        result = chunk[:size]
        if len(result) == len(chunk):
            self.chunks.pop(0)
        else:
            self.chunks[0] = (when, chunk[size:])
        return result


class OriginalBoundaryTests(unittest.TestCase):
    def record(self, port, deadline=100):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        folder = Path(tmp.name)
        with patch.object(capture.time, 'monotonic_ns', side_effect=lambda: port.now):
            summary = capture.capture_receiver(port, 'RX-01', folder, 'synthetic-boundary',
                threading.Event(), threading.Event(), {'seconds': deadline / 1e9,
                'deadline_ns': deadline, 'read_from_open': True, 'record_reads': True})
        return folder, summary

    def test_original_stop_preserves_129_and_leaves_valid_remainder_unread(self):
        complete, next_line = frame(), frame(1, 300000)
        port = ScriptPort([(10, complete), (20, next_line[:1]), (30, next_line[1:128]),
                           (110, next_line[128:129]), (111, next_line[129:])])
        folder, summary = self.record(port)
        self.assertEqual((folder / 'rx-01.serial.log').read_bytes(), complete + next_line[:129])
        self.assertEqual(summary['trailing_bytes'], 129)
        self.assertEqual(summary['valid_rows'], 1)
        self.assertIsNone(summary['error'])
        self.assertEqual(b''.join(chunk for _, chunk in port.chunks), next_line[129:])
        reads = [json.loads(x) for x in (folder / 'rx-01.reads.jsonl').read_text().splitlines()]
        self.assertEqual([e['size'] for e in reads[-3:]], [1, 127, 1])
        self.assertLess(int(reads[-1]['started_ns']), 100)
        self.assertGreater(int(reads[-1]['returned_ns']), 100)

    def test_original_tail_size_is_not_fixed_to_129(self):
        for cut in (17, 128, 129, 257):
            with self.subTest(cut=cut):
                line = frame(1, 300000)
                port = ScriptPort([(10, frame()), (110, line[:cut]), (111, line[cut:])])
                folder, summary = self.record(port)
                self.assertEqual(summary['trailing_bytes'], cut)
                self.assertEqual((folder / 'rx-01.serial.log').read_bytes(), frame() + line[:cut])

    def test_original_full_line_returning_late_keeps_its_real_timestamp(self):
        port = ScriptPort([(110, frame())])
        folder, summary = self.record(port)
        self.assertEqual(summary['trailing_bytes'], 0)
        self.assertEqual(summary['valid_rows'], 1)
        self.assertEqual(summary['last_host_monotonic_ns'], 110)


class ProposedBoundaryTests(unittest.TestCase):
    def collect(self, chunks, **kwargs):
        port = ScriptPort(chunks)
        seen = []
        report = read_to_boundary(port, 100, lambda data, event: seen.append((data, event)),
                                  threading.Event(), clock=lambda: port.now,
                                  utc=lambda: '2026-01-01T00:00:00+00:00', **kwargs)
        return port, b''.join(data for data, _ in seen), seen, report

    def test_proposal_finishes_only_current_line_and_keeps_following_frame_unread(self):
        line, following = frame(), frame(1, 300000)
        port, raw, seen, report = self.collect([(10, line[:129]), (120, line[129:] + following)], grace_ns=10000)
        self.assertEqual(raw, line)
        self.assertEqual(report['stop_reason'], 'lf_boundary')
        self.assertEqual(report['trailing_bytes'], 0)
        self.assertEqual(b''.join(data for _, data in port.chunks), following)
        self.assertEqual(report['completion_deadline_ns'], '10100')
        completion = [e for _, e in seen if e['phase'] == 'completion']
        self.assertTrue(completion)
        self.assertTrue(all(e['requested_size'] == 1 for e in completion))
        self.assertGreater(int(completion[-1]['returned_ns']), 100)
        self.assertEqual(port.timeout, .1)

    def test_proposal_time_budget_expires_preserving_incomplete_tail(self):
        _, raw, _, report = self.collect([(10, b'CSI_DATA,partial')], grace_ns=50)
        self.assertEqual(raw, b'CSI_DATA,partial')
        self.assertEqual(report['stop_reason'], 'time_limit_incomplete')
        self.assertEqual(report['stopped_ns'], '150')
        self.assertFalse(report['lf_boundary_reached'])

    def test_proposal_byte_budget_stops_continuous_no_lf_stream(self):
        _, raw, _, report = self.collect([(10, b'x'), (120, b'z' * 500)],
                                         grace_ns=10000, max_completion_bytes=7)
        self.assertEqual(raw, b'x' + b'z' * 7)
        self.assertEqual(report['stop_reason'], 'byte_limit_incomplete')
        self.assertEqual(report['completion_bytes'], 7)

    def test_proposal_does_not_wait_for_new_frame_at_clean_boundary(self):
        port, raw, _, report = self.collect([(10, frame()), (200, frame(1, 300000))], grace_ns=1000)
        self.assertEqual(raw, frame())
        self.assertEqual(report['completion_bytes'], 0)
        self.assertEqual(report['stop_reason'], 'lf_boundary')
        self.assertTrue(port.chunks)

    def test_proposal_keeps_entire_inflight_chunk_including_next_partial_frame(self):
        # No truncation of a returned chunk, even if its suffix begins a new line.
        first, second = frame(), frame(1, 300000)
        port, raw, _, report = self.collect([(90, first[:129]),
                (100, first[129:] + second[:17]), (110, second[17:])], grace_ns=10000)
        self.assertEqual(raw, first + second)
        self.assertEqual(report['trailing_bytes'], 0)
        self.assertFalse(port.chunks)

    def test_lf_framing_does_not_repair_bad_startup_or_corrupt_csi(self):
        bad = b'\x4c\x13\x00ESP-ROM:synthetic\nCSI_DATA,broken\n' + frame()
        _, raw, _, report = self.collect([(10, bad)], grace_ns=50)
        self.assertTrue(report['lf_boundary_reached'])
        self.assertEqual(raw, bad)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'synthetic.log'
            path.write_bytes(raw)
            parsed = scan_raw(path)
        self.assertEqual(parsed['embedded_boot_lines'], [1])
        self.assertEqual(parsed['counts']['malformed_rows'], 1)
        self.assertFalse(parsed['collector_quality_ok'])

    def test_abort_bypasses_completion_and_restores_timeout(self):
        stop = threading.Event()
        port = ScriptPort([(10, b'CSI_DATA,part'), (120, b'ial\n')])
        seen = []
        def accept(data, event):
            seen.append(data)
            stop.set()
        report = read_to_boundary(port, 100, accept, stop, clock=lambda: port.now)
        self.assertEqual(report['stop_reason'], 'aborted')
        self.assertEqual(b''.join(seen), b'CSI_DATA,part')
        self.assertEqual(port.timeout, .1)

    def test_read_error_propagates_without_retry_or_flush(self):
        port = ScriptPort([])
        def fail(size):
            raise OSError('synthetic disconnect')
        port.read = fail
        with self.assertRaisesRegex(OSError, 'disconnect'):
            read_to_boundary(port, 100, lambda *args: None, threading.Event(), clock=lambda: 0)
        self.assertEqual(port.timeout, .1)

    def test_rejects_unbounded_timeout_and_invalid_budgets(self):
        for timeout in (None, 0, float('inf')):
            port = ScriptPort([])
            port.timeout = timeout
            with self.assertRaises(ValueError):
                read_to_boundary(port, 100, lambda *args: None, threading.Event())
        for changes in ({'grace_ns': -1}, {'max_completion_bytes': 0}):
            with self.assertRaises(ValueError):
                read_to_boundary(ScriptPort([]), 100, lambda *args: None, threading.Event(), **changes)


class PrivatePtyBoundaryTests(unittest.TestCase):
    def make_port(self, prequeued=b''):
        master, slave = pty.openpty()
        self.addCleanup(os.close, master)
        self.addCleanup(os.close, slave)
        tty.setraw(slave)
        if prequeued:
            os.write(master, prequeued)
        device = preserving_serial_type(serial.Serial)(port=None, timeout=.025, exclusive=True)
        device.dtr = False
        device.rts = False
        device.port = os.ttyname(slave)
        device.open()
        self.addCleanup(device.close)
        return master, device

    def test_pending_bytes_before_pty_open_remain_separate_first_read_then_rom(self):
        prefix = b'\x4c\x13\x00'
        master, port = self.make_port(prefix)
        self.assertEqual(port.read(len(prefix)), prefix)
        # Known writer schedule demonstrates one possible origin, not the physical cause.
        following = b'ESP-ROM:synthetic\r\n' + frame()
        os.write(master, following)
        self.assertEqual(port.read(len(following)), following)
        self.assertEqual(port.open_flush_suppressed, 1)

    def test_current_collector_stops_midline_while_writer_can_finish_afterward(self):
        first, next_line = frame(), frame(1, 300000)
        master, port = self.make_port(first + next_line[:129])
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            summary = capture.capture_receiver(port, 'RX-01', folder, 'synthetic-pty',
                threading.Event(), threading.Event(), {'seconds': .015, 'read_from_open': True,
                'record_reads': True, 'deadline_ns': time.monotonic_ns() + 15_000_000})
            self.assertEqual(summary['trailing_bytes'], 129)
            self.assertEqual((folder / 'rx-01.serial.log').read_bytes(), first + next_line[:129])
            os.write(master, next_line[129:])
            self.assertEqual(port.read(len(next_line) - 129), next_line[129:])
            self.assertEqual(summary['valid_rows'], 1)

    def test_proposal_finishes_pty_line_after_deadline_without_reading_next_line(self):
        line, following = frame(), frame(1, 300000)
        master, port = self.make_port(line[:129])
        deadline = time.monotonic_ns() + 40_000_000
        def writer():
            while time.monotonic_ns() < deadline + 10_000_000:
                threading.Event().wait(.001)
            os.write(master, line[129:] + following)
        thread = threading.Thread(target=writer)
        thread.start()
        self.addCleanup(thread.join)
        seen = []
        report = read_to_boundary(port, deadline, lambda data, event: seen.append((data, event)),
                                  threading.Event(), grace_ns=500_000_000)
        thread.join()
        self.assertEqual(b''.join(data for data, _ in seen), line)
        self.assertEqual(report['stop_reason'], 'lf_boundary')
        self.assertGreater(int(seen[-1][1]['returned_ns']), deadline)
        self.assertEqual(port.read(len(following)), following)

    def test_proposal_no_lf_times_out_on_pty_without_dropping_tail(self):
        _, port = self.make_port(b'CSI_DATA,partial')
        seen = []
        begin = time.monotonic_ns()
        report = read_to_boundary(port, begin + 10_000_000,
                lambda data, event: seen.append(data), threading.Event(), grace_ns=25_000_000)
        self.assertEqual(b''.join(seen), b'CSI_DATA,partial')
        self.assertEqual(report['stop_reason'], 'time_limit_incomplete')
        self.assertGreaterEqual(int(report['stopped_ns']), begin + 35_000_000)
        self.assertLess(int(report['stopped_ns']) - begin, 2_000_000_000)


if __name__ == '__main__':
    unittest.main()
