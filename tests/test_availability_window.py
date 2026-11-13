"""Deterministic memory tests: prospective decisions, timing and races, no UART."""
from concurrent.futures import ThreadPoolExecutor
import threading
import unittest

from availability_window import AvailabilityCoordinator, classify_line, transition_error
from audit_availability import inclusion, coverage, intersects
from test_validate_capture import frame


def ready(rx):
    tag = 'csi_recv' if rx == 'RX-01' else 'csi_recv_02'
    return f'I (123) {tag}: {rx} READY channel=11 HT20 UART0=115200 raw CSI; source=1a:00:00:00:00:00\r\n'.encode()


class Clock:
    def __init__(self): self.now = 1_000_000_000
    def __call__(self): return self.now


def publish(c, rx, chunk, *, started=None, returned=None):
    offset = c.framers[rx].offset
    c.publish(rx, chunk, {'offset': offset, 'size': len(chunk), 'requested_size': len(chunk),
        'started_ns': str((c.clock() if returned is None else returned) if started is None else started),
        'returned_ns': str(c.clock() if returned is None else returned),
        'host_timestamp_utc': '2026-10-25T00:00:00+00:00', 'phase': 'nominal'})


def startup(rx):
    return ready(rx) + b''.join(frame(i, 100000 + 200000 * i) for i in range(3))


class AvailabilityMemoryTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.c = AvailabilityCoordinator(clock=self.clock)
        self.c.begin()
        for rx in self.c.states: self.c.reader_active(rx)

    def both_ready(self):
        for rx in self.c.states: publish(self.c, rx, startup(rx))

    def test_strict_ready_requires_rx_tag_configuration_utf8_and_clean_line(self):
        for rx in self.c.states:
            self.assertEqual(classify_line(ready(rx), rx)['kind'], 'ready')
            self.assertEqual(classify_line(b'\x1b[0;32m' + ready(rx)[:-2] + b'\x1b[0m\r\n', rx)['kind'], 'ready')
            for bad in (b'\x00' + ready(rx), ready(rx).replace(b'channel=11', b'channel=6'),
                        ready(rx).replace(b'source=1a:', b'source=2a:'), ready(rx).replace(b'HT20', b'HT40'),
                        ready(rx).replace(b'115200', b'9600'), ready(rx)[:-2], b'\xff' + ready(rx),
                        ready('RX-02' if rx == 'RX-01' else 'RX-01')):
                with self.subTest(bad=bad): self.assertNotEqual(classify_line(bad, rx)['kind'], 'ready')

    def test_ready_split_across_reads_keeps_first_and_final_references(self):
        rx = 'RX-01'; data = ready(rx)
        publish(self.c, rx, data[:10])
        self.assertIsNone(self.c.states[rx]['ready'])
        self.clock.now += 10
        publish(self.c, rx, data[10:])
        evidence = self.c.events[self.c.states[rx]['ready']]['evidence']
        self.assertEqual((evidence['first_read_index'], evidence['last_read_index']), (0, 1))
        self.assertEqual(evidence['first_read_started_ns'], '1000000000')

    def test_three_rows_without_ready_never_trigger(self):
        for rx in self.c.states:
            publish(self.c, rx, b''.join(frame(i, 100000 + i * 200000) for i in range(3)))
        self.c.evaluate(); self.assertIsNone(self.c.t0)

    def test_neutral_header_and_empty_lines_keep_streak_but_other_text_interrupts(self):
        from capture_csi import FIELDS
        for rx in self.c.states:
            publish(self.c, rx, ready(rx) + frame() + (','.join(FIELDS) + '\n\r\n').encode() + frame(1, 300000) + frame(2, 500000))
        self.c.evaluate(); self.assertIsNotNone(self.c.t0)
        c = AvailabilityCoordinator(clock=self.clock); c.begin()
        for rx in c.states:
            c.reader_active(rx)
            publish(c, rx, ready(rx) + frame() + b'I (5) log: neutral-looking message\n' + frame(1, 300000) + frame(2, 500000))
        c.evaluate(); self.assertIsNone(c.t0)

    def test_duplicate_ready_and_callback_restart_after_ready_are_fatal(self):
        for suffix in (ready('RX-01'), frame(0, 700000)):
            c = AvailabilityCoordinator(clock=self.clock); c.begin(); c.reader_active('RX-01')
            publish(c, 'RX-01', startup('RX-01') + suffix)
            self.assertIn(c.fatal, ('duplicate_ready', 'callback_restart'))

    def test_conflicting_ready_or_embedded_reset_after_ready_cannot_rearm(self):
        for bad in (ready('RX-01').replace(b'channel=11', b'channel=6'),
                    b'\x00ESP-ROM:synthetic\n', b'\xffESP-ROM:synthetic\n'):
            c = AvailabilityCoordinator(clock=self.clock); c.begin()
            for rx in c.states:
                c.reader_active(rx)
                publish(c, rx, startup(rx))
            publish(c, 'RX-01', bad + b''.join(frame(i, 100000 + 200000 * i) for i in range(3, 6)))
            c.evaluate()
            self.assertIsNone(c.t0)
            self.assertIn(c.fatal, ('conflicting_ready', 'post_ready_reset'))

    def test_multirow_read_crossing_start_excludes_every_row_without_interpolation(self):
        self.both_ready(); self.c.evaluate()
        t0 = self.c.t0
        self.clock.now += 10
        publish(self.c, 'RX-01', frame(3, 700000) + frame(4, 900000), started=t0 - 1)
        lines = [e['evidence'] for e in self.c.events if e['kind'] == 'line' and e['receiver'] == 'RX-01'][-2:]
        self.assertEqual([inclusion(x, t0, self.c.t1) for x in lines], ['crosses_start', 'crosses_start'])
        self.assertEqual(lines[0]['returned_ns'], lines[1]['returned_ns'])

    def test_invalid_profile_or_nonconsecutive_rows_do_not_complete_streak(self):
        for rx in self.c.states:
            publish(self.c, rx, ready(rx) + frame() + frame(1, 300000, first_word_invalid='1') + frame(2, 500000))
        self.c.evaluate(); self.assertIsNone(self.c.t0)
        self.assertTrue(all(len(s['streak']) <= 1 for s in self.c.states.values()))

    def test_same_chunk_reset_or_error_after_third_row_prevents_trigger(self):
        for suffix in (b'ESP-ROM:synthetic\n', b'E (1) csi_recv: failure\n', b'CSI_DATA,broken\n'):
            with self.subTest(suffix=suffix):
                c = AvailabilityCoordinator(clock=self.clock); c.begin()
                for rx in c.states: c.reader_active(rx)
                publish(c, 'RX-01', startup('RX-01'))
                publish(c, 'RX-02', startup('RX-02') + suffix)
                c.evaluate(); self.assertIsNone(c.t0)
                if not suffix.startswith(b'CSI_DATA'): self.assertIsNotNone(c.fatal)

    def test_delayed_processing_uses_real_decision_time_and_rejects_stale_evidence(self):
        read_time = self.clock.now
        self.clock.now += 500_000_000
        for rx in self.c.states: publish(self.c, rx, startup(rx), returned=read_time)
        self.c.evaluate()
        self.assertEqual(self.c.t0, self.clock.now)
        self.assertGreater(self.c.t0, read_time)
        frozen = self.c.t0
        self.clock.now += 20
        self.c.evaluate(); self.assertEqual(self.c.t0, frozen)
        c = AvailabilityCoordinator(clock=self.clock); c.begin()
        for rx in c.states: c.reader_active(rx)
        self.clock.now += 1_000_000_001
        for rx in c.states: publish(c, rx, startup(rx), returned=c.a)
        c.evaluate(); self.assertIsNone(c.t0)

    def test_freshness_expiry_resets_streak_without_sliding_wait_deadline(self):
        self.both_ready(); deadline = self.c.d
        self.clock.now += 1_000_000_001
        for rx in self.c.states: publish(self.c, rx, frame(3, 700000))
        self.c.evaluate()
        self.assertIsNone(self.c.t0)
        self.assertTrue(all(len(s['streak']) == 1 for s in self.c.states.values()))
        self.assertEqual(self.c.d, deadline)

    def test_timeout_exactly_at_deadline_prevents_activation(self):
        self.clock.now = self.c.d
        self.both_ready(); self.c.evaluate()
        self.assertTrue(self.c.timed_out); self.assertIsNone(self.c.t0)
        self.assertEqual(self.c.stop_deadline, self.c.d)

    def test_late_reset_evidence_rejects_activation_without_backdating_or_rearming(self):
        self.both_ready(); self.clock.now += 100
        self.c.evaluate(); original = (self.c.t0, self.c.t1)
        publish(self.c, 'RX-01', b'ESP-ROM:synthetic\n', returned=self.c.t0 - 1)
        self.assertTrue(self.c.activation_conflicts)
        self.clock.now += 1000; self.c.evaluate()
        self.assertEqual((self.c.t0, self.c.t1), original)
        self.assertIsNotNone(self.c.fatal)

    def test_concurrent_publish_and_evaluations_arm_once(self):
        barrier = threading.Barrier(2)
        def task(rx):
            barrier.wait(); publish(self.c, rx, startup(rx)); self.c.evaluate()
        with ThreadPoolExecutor(2) as pool: list(pool.map(task, self.c.states))
        barrier = threading.Barrier(8)
        def evaluate(_): barrier.wait(); self.c.evaluate()
        with ThreadPoolExecutor(8) as pool: list(pool.map(evaluate, range(8)))
        self.assertEqual(sum(e['kind'] == 'armed' for e in self.c.events), 1)
        armed = next(e for e in self.c.events if e['kind'] == 'armed')
        self.assertTrue(all(self.c.events[refs['row_seqs'][-1]]['seq'] < armed['seq'] for refs in armed['evidence'].values()))
        self.assertEqual(self.c.t1 - self.c.t0, 30_000_000_000)

    def test_abort_or_reader_termination_is_flow_drop_without_replacement_window(self):
        self.both_ready(); self.c.evaluate(); original = self.c.t0
        self.c.reader_finished('RX-01', 'aborted')
        self.assertEqual(self.c.fatal, 'reader_termination_before_T1')
        self.c.evaluate(); self.assertEqual(self.c.t0, original)

    def test_late_finish_notification_keeps_actual_early_reader_stop(self):
        self.both_ready(); self.c.evaluate()
        stopped = self.c.t1 - 1
        self.clock.now = self.c.t1 + 1_000_000_000
        self.c.reader_finished('RX-01', 'aborted', stopped_ns=stopped)
        self.assertEqual(self.c.fatal, 'reader_termination_before_T1')

    def test_reader_already_stopped_before_t0_is_late_activation_conflict(self):
        self.both_ready(); self.clock.now += 100; self.c.evaluate()
        t0 = self.c.t0
        self.clock.now += 100
        self.c.reader_finished('RX-01', 'error', stopped_ns=t0 - 1)
        self.assertTrue(self.c.activation_conflicts)
        self.c.evaluate(); self.assertEqual(self.c.t0, t0)

    def test_frontiers_are_half_open_and_first_read_is_conservative(self):
        for s, e, expected in [(9, 11, 'crosses_start'), (10, 19, 'included'),
                               (10, 20, 'at_or_after_deadline'), (9, 9, 'preamble'),
                               (9, 21, 'crosses_both_boundaries')]:
            line = {'kind': 'row', 'first_read_started_ns': str(s), 'returned_ns': str(e)}
            self.assertEqual(inclusion(line, 10, 20), expected)
        self.assertTrue(intersects({'first_read_started_ns': '9', 'returned_ns': '10'}, 10, 20))
        self.assertFalse(intersects({'first_read_started_ns': '20', 'returned_ns': '21'}, 10, 20))

    def test_sparse_single_row_reports_coverage_without_hidden_gap_threshold(self):
        line = {'kind': 'row', 'returned_ns': '15000000000', 'inclusion': 'included'}
        result = coverage([line], 0, 30_000_000_000)
        self.assertTrue(result['minimum_rows_ok']); self.assertIsNone(result['max_gap_limit_ns'])
        self.assertEqual(result['max_observed_gap_ns'], '15000000000')
        self.assertFalse(result['continuous_observation_claimed'])
        self.assertFalse(coverage([], 0, 30_000_000_000)['minimum_rows_ok'])

    def test_local_uint32_wrap_allowed_but_not_callback_gap_or_drop_change(self):
        first = {'id': 12, 'local_timestamp': 2**32 - 100, 'queue_drops': 4}
        current = {'id': 13, 'local_timestamp': 100, 'queue_drops': 4}
        self.assertIsNone(transition_error(first, current))
        self.assertEqual(transition_error(first, dict(current, id=14)), 'callback_gap')
        self.assertEqual(transition_error(first, dict(current, queue_drops=5)), 'queue_drop_change')


if __name__ == '__main__': unittest.main()
