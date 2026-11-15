"""Versioned v4 line policy: synthetic bytes/clocks and immutable offline replay.

All candidate inputs are synthetic bytes and clocks. The optional historical
test only reads the existing rejected bundle; it never replays a transport.
"""
import hashlib
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_persistent_presence_v4 import ROOT, plan
from campana_presencia_v4 import fixture_ready, fixture_row
from persistent_presence_v4 import (PersistentPresenceV4, SECOND, validate_plan,
                                    STRICT_LINE_POLICY, APP_MAIN_RETURN_POLICY)
from presence_v4_journal import audit_v4, V4Journal, digest
from capture_csi_multi import FIELDS

RETURN = b'I (545) main_task: Returned from app_main()\r\n'
BUNDLE = ROOT/'results/local/v4-c01-vacia-sentado-20261028T014057Z'


class Rig:
    def __init__(self, cls):
        self.m = cls(plan())
        self.now = SECOND
        self.call('begin')
        for rx in ('RX-01', 'RX-02'):
            self.call('opened', receiver=rx)

    def call(self, op, **data):
        self.m.apply(op, self.now, **data)

    def send(self, data, rx='RX-02'):
        if data:
            self.call('chunk', receiver=rx, chunk=data,
                      started_ns=self.now, returned_ns=self.now)


def revised_machine(p):
    return PersistentPresenceV4(dict(p, line_policy_revision=APP_MAIN_RETURN_POLICY))


class AppMainReturnPolicyTests(unittest.TestCase):
    candidate = staticmethod(revised_machine)

    def test_original_rejects_exact_observed_message(self):
        for explicit in (False, True):
            r = Rig(lambda p: PersistentPresenceV4(
                dict(p, line_policy_revision=STRICT_LINE_POLICY) if explicit else p))
            r.send(fixture_ready('RX-02')+RETURN)
            self.assertEqual(r.m.fatal, 'post_ready_info:RX-02')
            self.assertNotIn('startup_app_main_return', r.m.states['RX-02']['lines'][-1])
            self.assertNotIn('line_policy_revision', r.m.summary())

    def test_candidate_all_byte_boundaries_both_receivers(self):
        for rx in ('RX-01', 'RX-02'):
            stream = fixture_ready(rx)+RETURN
            for cut in range(len(stream)+1):
                with self.subTest(rx=rx, cut=cut):
                    r = Rig(self.candidate)
                    r.send(stream[:cut], rx); r.send(stream[cut:], rx)
                    self.assertIsNone(r.m.fatal)
                    self.assertIsNone(r.m.initial_available)
                    self.assertEqual(r.m.states[rx]['streak'], [])
                    lines = r.m.states[rx]['lines']
                    self.assertEqual([x['kind'] for x in lines], ['ready', 'info'])
                    v = lines[1]
                    self.assertTrue(v['startup_app_main_return'])
                    self.assertEqual(v['line_policy_exception'], APP_MAIN_RETURN_POLICY)
                    self.assertEqual(r.m.events[-1]['evidence'], v)
                    self.assertEqual(v['byte_offset'], len(fixture_ready(rx)))
                    self.assertEqual(v['byte_end'], len(stream))
                    self.assertEqual(v['line_sha256'], hashlib.sha256(RETURN).hexdigest())

    def test_requires_three_fresh_rows_per_rx(self):
        r = Rig(self.candidate)
        for rx in ('RX-01', 'RX-02'):
            r.send(fixture_ready(rx)+RETURN, rx)
        for i in range(3):
            r.now += 200_000_000
            for rx in ('RX-01', 'RX-02'):
                r.send(fixture_row(i, 100000+i*200000), rx)
            r.call('tick')
            self.assertEqual(r.m.initial_available is not None, i == 2)
        self.assertIsNone(r.m.fatal)
        self.assertEqual(r.m.windows, [])

    def test_missing_ready_still_times_out(self):
        r = Rig(self.candidate)
        r.send(RETURN)
        r.now += 10*SECOND
        r.call('tick')
        self.assertIsNotNone(r.m.fatal)
        self.assertIsNone(r.m.states['RX-02']['ready'])
        self.assertIsNone(r.m.initial_available)

    def test_return_without_rows_still_times_out(self):
        r = Rig(self.candidate)
        for rx in ('RX-01', 'RX-02'):
            r.send(fixture_ready(rx)+RETURN, rx)
        r.now += 10*SECOND
        r.call('tick')
        self.assertIsNotNone(r.m.fatal)
        self.assertIsNone(r.m.initial_available)

    def test_duplicate_or_intervening_line_is_rejected(self):
        for middle in (RETURN, b'\n', b'I (544) other: hello\n', fixture_row(0, 100000)):
            with self.subTest(middle=middle[:50]):
                r = Rig(self.candidate)
                r.send(fixture_ready('RX-02')+middle+RETURN)
                self.assertEqual(r.m.fatal, 'post_ready_info:RX-02')

    def test_no_broad_whitelist_or_error_reset_exception(self):
        variants = [b'E (545) main_task: Returned from app_main()\r\n',
                    b'W (545) main_task: Returned from app_main()\r\n',
                    RETURN.replace(b'main_task', b'other'),
                    RETURN.replace(b'app_main()', b'app_main() reset'),
                    RETURN.replace(b'\r\n', b' trailing\r\n'),
                    b'I (545) main_task: Calling app_main()\n',
                    b'I (545) wifi: channel changed=6\n',
                    b'rst:0x1 (POWERON),boot:0x8 (SPI_FAST_FLASH_BOOT)\r\n',
                    b'ESP-ROM:esp32s3-20210327\r\n',
                    b'I (545) csi_recv_02: RX-02 READY channel=6\n',
                    b'\x1b[0;32m'+RETURN[:-2]+b'\x1b[0m\r\n',
                    b'\xff'+RETURN, RETURN.replace(b'545', b'-1'),
                    RETURN.replace(b'545', b'\xd9\xa1'),
                    RETURN.replace(b'\r\n', b'\r\r\n'), RETURN.replace(b'I (', b'I  (')]
        for data in variants:
            with self.subTest(data=data):
                r = Rig(self.candidate)
                r.send(fixture_ready('RX-02')+data)
                self.assertIsNotNone(r.m.fatal)

    def test_duplicate_ready_still_rejected(self):
        r = Rig(self.candidate)
        r.send(fixture_ready('RX-02')+RETURN+fixture_ready('RX-02'))
        self.assertEqual(r.m.fatal, 'duplicate_ready:RX-02')

    def test_initial_invalid_bytes_still_reject_connection(self):
        r = Rig(self.candidate)
        r.send(b'\xff\n'+fixture_ready('RX-02')+RETURN)
        self.assertIsNone(r.m.fatal)
        self.assertIn('format:RX-02', r.m.connection_reasons)
        self.assertFalse(r.m.summary()['connection']['quality_ok'])

    def test_oversized_line_not_hidden(self):
        r = Rig(self.candidate)
        r.send(fixture_ready('RX-02'))
        r.send(b'x'*70000)
        r.send(RETURN)
        self.assertEqual(r.m.fatal, 'format:RX-02')

    def test_availability_watchdog_is_unchanged(self):
        r = Rig(self.candidate)
        for rx in ('RX-01', 'RX-02'):
            r.send(fixture_ready(rx)+RETURN, rx)
            for i in range(3):
                r.send(fixture_row(i, 100000+i*200000), rx)
        r.call('tick')
        self.assertIsNotNone(r.m.initial_available)
        r.now += SECOND+1
        r.call('tick')
        self.assertIsNotNone(r.m.fatal)

    def test_exact_wait_boundary_is_not_extended(self):
        r = Rig(self.candidate)
        r.send(fixture_ready('RX-02'))
        r.now += 10*SECOND
        r.send(RETURN)
        self.assertEqual(r.m.fatal, 'post_ready_info:RX-02')

    def test_lf_crlf_and_ascii_timestamps(self):
        for data in (RETURN, RETURN.replace(b'\r\n', b'\n'),
                     RETURN.replace(b'545', b'0'), RETURN.replace(b'545', b'1234567890')):
            r = Rig(self.candidate)
            r.send(fixture_ready('RX-02')+data)
            self.assertIsNone(r.m.fatal)
            self.assertEqual(r.m.states['RX-02']['lines'][-1]['line_policy_exception'], APP_MAIN_RETURN_POLICY)

    def test_one_byte_reads_preserve_framing_and_hash(self):
        r = Rig(self.candidate)
        for byte in fixture_ready('RX-02')+RETURN:
            r.send(bytes([byte]))
        self.assertIsNone(r.m.fatal)
        v = r.m.states['RX-02']['lines'][-1]
        self.assertEqual(v['line_sha256'], hashlib.sha256(RETURN).hexdigest())
        self.assertEqual(v['last_read_index']-v['first_read_index']+1, len(RETURN))

    def test_prior_csi_or_availability_or_suspension_or_close_blocks_exception(self):
        for phase in ('csi_before_ready', 'available', 'fatal', 'closing'):
            with self.subTest(phase=phase):
                r = Rig(self.candidate)
                if phase == 'csi_before_ready':
                    r.send(fixture_row(0, 100000))
                elif phase == 'available':
                    for rx in ('RX-01', 'RX-02'):
                        r.send(fixture_ready(rx), rx)
                        for i in range(3):
                            r.send(fixture_row(i, 100000+i*200000), rx)
                    r.call('tick')
                    self.assertIsNotNone(r.m.initial_available)
                    r.send(RETURN)
                    self.assertEqual(r.m.fatal, 'post_ready_info:RX-02')
                    continue
                elif phase == 'fatal':
                    r.call('io_error', receiver='RX-01')
                elif phase == 'closing':
                    r.call('close_request'); r.call('closing')
                r.send(fixture_ready('RX-02')+RETURN)
                self.assertIsNotNone(r.m.fatal)
                self.assertNotIn('line_policy_exception', r.m.states['RX-02']['lines'][-1])

    def test_pending_return_does_not_gain_exception_without_lf(self):
        r = Rig(self.candidate)
        r.send(fixture_ready('RX-02')+RETURN[:-1])
        self.assertEqual(len(r.m.states['RX-02']['lines']), 1)
        r.call('close_request'); r.call('closing')
        r.call('closed', receiver='RX-02', confirmed=True, reader_stopped=True)
        self.assertIn('incomplete_tail:RX-02', r.m.connection_reasons)

    def test_unknown_revision_is_rejected(self):
        for revision in (None, '', 'v4-app-main-return-2', 'allow-all-info', 1, [], {}):
            with self.subTest(revision=revision), self.assertRaises(ValueError):
                validate_plan(dict(plan(), line_policy_revision=revision))

    def test_errors_resets_and_configuration_after_exception_remain_fatal(self):
        variants = [b'E (546) main_task: error\n', b'abort() was called\n',
                    b'rst:0x1 (POWERON),boot:0x8 (SPI_FAST_FLASH_BOOT)\n',
                    b'ESP-ROM:esp32s3-20210327\n',
                    b'I (546) wifi: channel changed=6\n',
                    fixture_ready('RX-02').replace(b'channel=11', b'channel=6')]
        for field, value in (('channel', '6'), ('bandwidth', '1'), ('sig_mode', '0'),
                             ('first_word_invalid', '1'), ('mac', '00:00:00:00:00:00')):
            values = next(csv.reader(io.StringIO(fixture_row(0, 100000).decode())))
            values[FIELDS.index(field)] = value
            out = io.StringIO(); csv.writer(out, lineterminator='\n').writerow(values)
            variants.append(out.getvalue().encode())
        for data in variants:
            for rx in ('RX-01', 'RX-02'):
                with self.subTest(data=data[:80], rx=rx):
                    r = Rig(self.candidate)
                    r.send(fixture_ready(rx)+RETURN+data, rx)
                    self.assertIsNotNone(r.m.fatal)
                    self.assertFalse(r.m.summary()['connection']['quality_ok'])

    def test_callback_restart_after_exception_remains_fatal(self):
        r = Rig(self.candidate)
        r.send(fixture_ready('RX-02')+RETURN+fixture_row(0, 100000)+fixture_row(0, 300000))
        self.assertEqual(r.m.fatal, 'callback_restart:RX-02')

    @unittest.skipUnless(BUNDLE.exists(), 'Local historical bundle not available')
    def test_original_bundle_stays_rejected_and_unchanged(self):
        before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in BUNDLE.rglob('*') if p.is_file()}
        result = audit_v4(BUNDLE)
        self.assertTrue(result['integrity_ok'] and result['replay_ok'])
        self.assertEqual(result['state']['fatal'], 'post_ready_info:RX-02')
        self.assertEqual(result['state']['windows'], [])
        after = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in BUNDLE.rglob('*') if p.is_file()}
        self.assertEqual(before, after)


class LinePolicyReplayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/'bundle'

    def bundle(self, revision=APP_MAIN_RETURN_POLICY):
        p = dict(plan(), line_policy_revision=revision)
        with patch('serial.Serial', side_effect=AssertionError('No UART')):
            j = V4Journal(self.root, p)
            self.addCleanup(j.close_files)
            now = SECOND
            j.command('begin', now)
            for rx in ('RX-01', 'RX-02'):
                j.command('opened', now, receiver=rx)
            for rx in ('RX-01', 'RX-02'):
                j.command('chunk', now, receiver=rx, chunk=fixture_ready(rx)+RETURN,
                          started_ns=now, returned_ns=now)
                for i in range(3):
                    j.command('chunk', now, receiver=rx, chunk=fixture_row(i, 100000+i*200000),
                              started_ns=now, returned_ns=now)
            j.command('tick', now)
            j.command('close_request', now)
            j.command('closing', now)
            for rx in ('RX-01', 'RX-02'):
                j.command('closed', now, receiver=rx, confirmed=True, reader_stopped=True)
            j.receipt()
            j.finalize(dict(test='synthetic-memory-only'))

    def rewrite(self, name, value):
        (self.root/name).write_text(json.dumps(value)+'\n')
        manifest = json.loads((self.root/'manifest.json').read_text())
        for entry in manifest['files']:
            p = self.root/entry['path']
            entry.update(bytes=p.stat().st_size, sha256=digest(p))
        (self.root/'manifest.json').write_text(json.dumps(manifest)+'\n')

    def test_new_bundle_records_revision_and_replays(self):
        self.bundle()
        report = audit_v4(self.root)
        self.assertTrue(report['integrity_ok'] and report['replay_ok'])
        self.assertTrue(report['state']['connection']['quality_ok'])
        self.assertIsNotNone(report['state']['initial_available_ns'])
        self.assertEqual(report['state']['windows'], [])
        self.assertEqual(report['state']['line_policy_revision'], APP_MAIN_RETURN_POLICY)
        provenance = json.loads((self.root/'provenance.json').read_text())
        self.assertEqual(provenance['line_policy_revision'], APP_MAIN_RETURN_POLICY)

    def test_explicit_strict_bundle_keeps_rejection_and_replays(self):
        self.bundle(STRICT_LINE_POLICY)
        report = audit_v4(self.root)
        self.assertTrue(report['replay_ok'])
        self.assertEqual(report['state']['fatal'], 'post_ready_info:RX-01')

    def test_missing_or_mismatched_provenance_cannot_enable_exception(self):
        self.bundle()
        provenance = json.loads((self.root/'provenance.json').read_text())
        for value in (None, STRICT_LINE_POLICY, 'unknown'):
            edited = dict(provenance)
            if value is None:
                del edited['line_policy_revision']
            else:
                edited['line_policy_revision'] = value
            self.rewrite('provenance.json', edited)
            with self.assertRaisesRegex(ValueError, 'Line policy provenance'):
                audit_v4(self.root)

    def test_removing_revision_does_not_silently_select_new_policy(self):
        self.bundle()
        p = json.loads((self.root/'plan.json').read_text())
        del p['line_policy_revision']
        self.rewrite('plan.json', p)
        provenance = json.loads((self.root/'provenance.json').read_text())
        provenance['plan_sha256'] = digest(self.root/'plan.json')
        self.rewrite('provenance.json', provenance)
        with self.assertRaisesRegex(ValueError, 'Line policy provenance'):
            audit_v4(self.root)
        # Even removing both declarations cannot rehash an accepted summary
        # into a historical bundle: the original strict decision is replayed.
        del provenance['line_policy_revision']
        self.rewrite('provenance.json', provenance)
        with self.assertRaisesRegex(ValueError, 'Replayed summary differs'):
            audit_v4(self.root)

    def test_uart_adapter_uses_explicit_policy_with_owned_ptys_and_replay(self):
        # The existing double maps every by-id request to its own PTY before
        # serial.open; no physical UART or identity discovery is reachable.
        from test_uart_v4 import Rig as UartRig, plan as uart_plan
        from presence_v4_uart import UartSession
        rig = UartRig()
        self.addCleanup(rig.finish_fixture)
        p = dict(uart_plan(), line_policy_revision=APP_MAIN_RETURN_POLICY)
        with UartSession(rig.output, p, test_backend=rig.backend, clock=rig.clock) as s:
            for rx, endpoint in rig.pairs.items():
                endpoint.fixture_write(fixture_ready(rx)+RETURN+b''.join(
                    fixture_row(i, 100000+i*200000) for i in range(3)))
            s.step()
            self.assertIsNone(s.machine.fatal)
            self.assertIsNotNone(s.machine.initial_available)
            s.command('close_request'); s.step()
        report = audit_v4(rig.output)
        self.assertTrue(report['integrity_ok'] and report['replay_ok'])
        self.assertTrue(report['state']['connection']['quality_ok'])
        self.assertEqual(report['state']['line_policy_revision'], APP_MAIN_RETURN_POLICY)
        self.assertEqual([obj.protocol_closes for obj in rig.objects], [1, 1])


if __name__ == '__main__':
    unittest.main()
