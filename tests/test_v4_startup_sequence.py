"""Recorded-byte inspection and explicitly synthetic source-permitted orders."""
import csv
import hashlib
import io
import json
import re
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_v4_line_policy import Rig, RETURN, ROOT
import test_v4_line_policy as prior
from test_persistent_presence_v4 import plan
from campana_presencia_v4 import fixture_ready, fixture_row
from capture_csi_multi import FIELDS
from availability_window import HEADER, classify_line
from persistent_presence_v4 import (PersistentPresenceV4, STARTUP_SEQUENCE_POLICY,
                                    APP_MAIN_RETURN_POLICY, SECOND)
from presence_v4_journal import audit_v4
from revisar_arranque_v4 import inspect_log, inspect_existing, LOG_DIRECTORIES

SNIFFER = b'I (537) wifi:ic_enable_sniffer\r\n'
HEADER_BYTES = HEADER.encode()+b'\r\n'


def machine(p):
    return PersistentPresenceV4(dict(p, line_policy_revision=STARTUP_SEQUENCE_POLICY))


def boot(rx):
    return (fixture_ready(rx)+SNIFFER+RETURN if rx == 'RX-01' else
            SNIFFER+fixture_ready(rx)+RETURN)


def modified_row(**changes):
    values = next(csv.reader(io.StringIO(fixture_row(1, 300000).decode())))
    for key, value in changes.items():
        values[FIELDS.index(key)] = str(value)
    out = io.StringIO()
    csv.writer(out, lineterminator='\n').writerow(values)
    return out.getvalue().encode()


class StartupSequenceTests(unittest.TestCase):
    def test_previous_revision_still_rejects_recorded_rx01_sniffer(self):
        r = Rig(lambda p: PersistentPresenceV4(dict(p, line_policy_revision=APP_MAIN_RETURN_POLICY)))
        r.send(boot('RX-01'), 'RX-01')
        self.assertEqual(r.m.fatal, 'format:RX-01')
        self.assertEqual(classify_line(SNIFFER, 'RX-01')['kind'], 'invalid')

    def test_observed_orders_at_all_chunk_boundaries(self):
        for rx in ('RX-01', 'RX-02'):
            stream = boot(rx)
            for cut in range(len(stream)+1):
                with self.subTest(rx=rx, cut=cut):
                    r = Rig(machine)
                    r.send(stream[:cut], rx); r.send(stream[cut:], rx)
                    self.assertIsNone(r.m.fatal)
                    self.assertIsNone(r.m.initial_available)
                    self.assertEqual(r.m.startup_messages[rx], dict(sniffer=True, returned=True))
                    for line in r.m.states[rx]['lines']:
                        data = stream[line['byte_offset']:line['byte_end']]
                        self.assertEqual(line['line_sha256'], hashlib.sha256(data).hexdigest())
                        if line['kind'] == 'info':
                            self.assertEqual(line['line_policy_exception'], STARTUP_SEQUENCE_POLICY)
                    sniffer = next(l for l in r.m.states[rx]['lines'] if l.get('startup_sniffer_enable'))
                    self.assertEqual(sniffer['shared_kind'], 'invalid')

    def test_lf_crlf_and_single_byte_reads(self):
        for rx in ('RX-01', 'RX-02'):
            for ending in (b'\n', b'\r\n'):
                r = Rig(machine)
                stream = boot(rx).replace(b'\r\n', b'\n').replace(b'\n', ending)
                for byte in stream:
                    r.send(bytes([byte]), rx)
                self.assertIsNone(r.m.fatal)
                self.assertTrue(r.m.startup_messages[rx]['returned'])

    def test_source_permitted_header_and_csi_interleavings(self):
        # Generated orders are synthetic scheduling possibilities, not new
        # physical observations. CSI can run once enabled, before SDK return.
        for count in (0, 1, 3):
            for header_pos in range(4):
                for rx in ('RX-01', 'RX-02'):
                    parts = ([fixture_ready(rx), SNIFFER] if rx == 'RX-01' else
                             [SNIFFER, fixture_ready(rx)])
                    parts += [b''.join(fixture_row(i, 100000+i*200000) for i in range(count)), RETURN]
                    parts.insert(header_pos, HEADER_BYTES)
                    with self.subTest(rx=rx, rows=count, header=header_pos):
                        r = Rig(machine); r.send(b''.join(parts), rx)
                        self.assertIsNone(r.m.fatal)
                        self.assertTrue(r.m.startup_messages[rx]['returned'])
                        self.assertEqual(r.m.states[rx]['streak'], [])

    def test_rx02_csi_before_ready_is_source_permitted_and_still_checked(self):
        r = Rig(machine)
        r.send(SNIFFER+fixture_row(0, 100000)+fixture_ready('RX-02')+
               fixture_row(1, 300000)+RETURN)
        self.assertIsNone(r.m.fatal)
        self.assertTrue(r.m.startup_messages['RX-02']['returned'])
        r.send(fixture_row(1, 500000))
        self.assertEqual(r.m.fatal, 'callback_restart:RX-02')

    def test_rx02_return_does_not_require_receiving_pre_ready_sniffer(self):
        r = Rig(machine); r.send(fixture_ready('RX-02')+RETURN)
        self.assertIsNone(r.m.fatal)
        self.assertEqual(r.m.startup_messages['RX-02'], dict(sniffer=False, returned=True))

    def test_gate_waits_for_both_returns_and_three_fresh_rows_after_them(self):
        r = Rig(machine)
        for rx in ('RX-01', 'RX-02'):
            prefix = fixture_ready(rx)+SNIFFER if rx == 'RX-01' else SNIFFER+fixture_ready(rx)
            r.send(prefix, rx)
            for i in range(3):
                r.send(fixture_row(i, 100000+i*200000), rx)
        r.call('tick')
        self.assertIsNone(r.m.initial_available)
        for rx in ('RX-01', 'RX-02'):
            r.send(RETURN, rx)
        for i in range(3, 6):
            r.now += 200_000_000
            for rx in ('RX-01', 'RX-02'):
                r.send(fixture_row(i, 100000+i*200000), rx)
            r.call('tick')
            self.assertEqual(r.m.initial_available is not None, i == 5)
        self.assertEqual(r.m.windows, [])
        r.now += SECOND+1; r.call('tick')
        self.assertIsNotNone(r.m.fatal)

    def test_missing_messages_keep_original_timeout(self):
        for rx, data in (('RX-01', fixture_ready('RX-01')),
                         ('RX-01', fixture_ready('RX-01')+SNIFFER),
                         ('RX-02', SNIFFER+fixture_ready('RX-02'))):
            r = Rig(machine); r.send(data, rx)
            for i in range(3):
                r.send(fixture_row(i, 100000+i*200000), rx)
            r.now += 10*SECOND; r.call('tick')
            self.assertEqual(r.m.fatal, 'initial_availability_timeout')

    def test_duplicate_or_wrong_order_patterns_suspend(self):
        cases = [('RX-01', SNIFFER+fixture_ready('RX-01')),
                 ('RX-01', fixture_ready('RX-01')+RETURN),
                 ('RX-01', fixture_ready('RX-01')+SNIFFER+SNIFFER),
                 ('RX-01', fixture_ready('RX-01')+fixture_row(0, 100000)+SNIFFER),
                 ('RX-02', fixture_row(0, 100000)+SNIFFER),
                 ('RX-01', boot('RX-01')+SNIFFER),
                 ('RX-02', fixture_ready('RX-02')+SNIFFER),
                 ('RX-02', SNIFFER+SNIFFER), ('RX-02', RETURN),
                 ('RX-01', boot('RX-01')+RETURN), ('RX-02', boot('RX-02')+RETURN)]
        for rx, data in cases:
            with self.subTest(rx=rx, data=data):
                r = Rig(machine); r.send(data, rx)
                self.assertEqual(r.m.fatal, 'startup_message_order:'+rx)

    def test_exact_deadline_and_closing_forbid_pattern(self):
        for phase in ('deadline', 'close_requested', 'closing', 'suspended'):
            r = Rig(machine); r.send(fixture_ready('RX-01'), 'RX-01')
            if phase == 'deadline':r.now += 10*SECOND
            elif phase == 'suspended':r.call('io_error', receiver='RX-02')
            else:
                r.call('close_request')
                if phase == 'closing':r.call('closing')
            r.send(SNIFFER, 'RX-01')
            self.assertIsNotNone(r.m.fatal)
            self.assertFalse(r.m.startup_messages['RX-01']['sniffer'])

    def test_no_generic_info_no_disable_no_ansi_no_binary_prefix(self):
        variants = [SNIFFER.replace(b'enable', b'disable'), SNIFFER.replace(b'wifi:', b'wifi: '),
                    SNIFFER.replace(b'537', b'-1'), SNIFFER.replace(b'I (', b'W ('),
                    SNIFFER.replace(b'I (', b'E ('), SNIFFER.replace(b'\r\n', b' trailing\n'),
                    b'\x1b[0;32m'+SNIFFER[:-2]+b'\x1b[0m\n', b'\xff'+SNIFFER,
                    SNIFFER.replace(b'537', b'\xd9\xa1'), b'I (540) other: hello\n',
                    b'I (540) wifi: channel changed=6\n', b'I (540) wifi:enable tsf\n']
        for data in variants:
            with self.subTest(data=data):
                r = Rig(machine); r.send(fixture_ready('RX-01')+data, 'RX-01')
                self.assertIsNotNone(r.m.fatal)

    def test_reset_error_and_bad_ready_are_never_exempted(self):
        for data in (b'rst:0x1 (POWERON),boot:0x8 (SPI_FAST_FLASH_BOOT)\n',
                     b'ESP-ROM:esp32s3-20210327\n', b'E (540) wifi: error\n',
                     b'abort() was called\n', fixture_ready('RX-01'),
                     fixture_ready('RX-01').replace(b'channel=11', b'channel=6')):
            r = Rig(machine); r.send(fixture_ready('RX-01')+SNIFFER+data+RETURN, 'RX-01')
            self.assertIsNotNone(r.m.fatal)
            self.assertFalse(r.m.startup_messages['RX-01']['returned'])

    def test_csi_profile_and_continuity_remain_strict_during_startup(self):
        cases = [modified_row(**{key: value}) for key, value in (
            ('channel', 6), ('bandwidth', 1), ('len', 128), ('first_word_invalid', 1),
            ('sig_mode', 0), ('mcs', 1), ('stbc', 1), ('rx_state', 1),
            ('mac', '00:00:00:00:00:00'), ('id', 0), ('id', 2),
            ('local_timestamp', 99999), ('queue_drops', 1))]
        for row in cases:
            r = Rig(machine)
            r.send(fixture_ready('RX-01')+SNIFFER+fixture_row(0, 100000)+row+RETURN, 'RX-01')
            self.assertIsNotNone(r.m.fatal)
            self.assertFalse(r.m.startup_messages['RX-01']['returned'])

    def test_torn_csi_or_oversized_line_is_not_repaired(self):
        for data in (fixture_row(0, 100000)[:-2]+RETURN, b'x'*70000+RETURN):
            r = Rig(machine); r.send(fixture_ready('RX-01')+SNIFFER+data, 'RX-01')
            self.assertEqual(r.m.fatal, 'format:RX-01')

    def test_partial_sniffer_remains_an_incomplete_tail(self):
        r = Rig(machine); r.send(fixture_ready('RX-01')+SNIFFER[:-1], 'RX-01')
        self.assertFalse(r.m.startup_messages['RX-01']['sniffer'])
        r.call('close_request'); r.call('closing')
        r.call('closed', receiver='RX-01', confirmed=True, reader_stopped=True)
        self.assertEqual(r.m.fatal, 'incomplete_tail:RX-01')

    def test_initial_other_formats_and_non_utf8_remain_rejected(self):
        for data in (b'\xffESP-ROM:esp32s3-20210327\r\n',
                     b'I (33) boot.esp32s3: Boot SPI Speed : 80MHz\r\n',
                     b'I (548) wifi:enable tsf\r\n'):
            r = Rig(machine); r.send(data+boot('RX-01'), 'RX-01')
            self.assertIn('format:RX-01', r.m.connection_reasons)
            self.assertFalse(r.m.summary()['connection']['quality_ok'])

    def test_new_revision_is_recorded_and_replayed_without_hardware(self):
        # Reuse the bundle builder, replacing only the plan's explicit policy
        # and inserting the required RX-01 sniffer into synthetic READY bytes.
        helper = prior.LinePolicyReplayTests(methodName='test_new_bundle_records_revision_and_replays')
        helper.setUp(); self.addCleanup(helper.doCleanups)
        original = fixture_ready
        with patch('test_v4_line_policy.fixture_ready',
                   side_effect=lambda rx: original(rx)+(SNIFFER if rx == 'RX-01' else b'')):
            helper.bundle(STARTUP_SEQUENCE_POLICY)
        report = audit_v4(helper.root)
        self.assertTrue(report['replay_ok'] and report['state']['connection']['quality_ok'])
        self.assertEqual(report['state']['line_policy_revision'], STARTUP_SEQUENCE_POLICY)
        self.assertTrue(all(v['returned'] for v in report['state']['startup_messages'].values()))
        provenance = json.loads((helper.root/'provenance.json').read_text())
        del provenance['line_policy_revision']; helper.rewrite('provenance.json', provenance)
        with self.assertRaisesRegex(ValueError, 'Line policy provenance'):
            audit_v4(helper.root)

    def test_two_complete_pty_windows_use_new_gate_and_replay(self):
        import campana_presencia_v4 as campaign
        original_source = campaign.FixtureSource

        class StartupSource(original_source):
            def advance(self, session):
                if not self.ready_sent:
                    for rx, endpoint in session.endpoints.items():
                        endpoint.fixture_write(boot(rx))
                    self.ready_sent = True
                return super().advance(session)

        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(campaign, 'FixtureSource', StartupSource), \
                patch('serial.Serial', side_effect=AssertionError('No UART')), \
                patch('capture_csi_multi.port_identity', side_effect=AssertionError('No USB discovery')):
            report = campaign.run_demo(dict(plan(), line_policy_revision=STARTUP_SEQUENCE_POLICY),
                                       Path(tmp)/'new', stepped=True)
        self.assertTrue(report['integrity_ok'] and report['replay_ok'])
        self.assertEqual(len(report['state']['windows']), 2)
        self.assertTrue(all(w['eligible'] for w in report['state']['windows']))
        self.assertEqual(report['state']['line_policy_revision'], STARTUP_SEQUENCE_POLICY)

    def test_serial_adapter_on_owned_ptys_records_new_revision(self):
        from test_uart_v4 import Rig as UartRig, plan as uart_plan
        from presence_v4_uart import UartSession
        rig = UartRig(); self.addCleanup(rig.finish_fixture)
        p = dict(uart_plan(), line_policy_revision=STARTUP_SEQUENCE_POLICY)
        with UartSession(rig.output, p, test_backend=rig.backend, clock=rig.clock) as session:
            for rx, endpoint in rig.pairs.items():
                endpoint.fixture_write(boot(rx)+b''.join(
                    fixture_row(i, 100000+i*200000) for i in range(3)))
            session.step()
            self.assertIsNotNone(session.machine.initial_available)
            self.assertIsNone(session.machine.fatal)
            session.command('close_request'); session.step()
        report = audit_v4(rig.output)
        self.assertTrue(report['replay_ok'] and report['state']['connection']['quality_ok'])
        self.assertEqual(report['state']['line_policy_revision'], STARTUP_SEQUENCE_POLICY)
        self.assertEqual([obj.protocol_closes for obj in rig.objects], [1, 1])


class ExistingLogInspectionTests(unittest.TestCase):
    def test_inspection_uses_lf_only_and_preserves_tail_and_offsets(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'log'
            raw = b'\xff\x0bROM\r\n'+SNIFFER+b'I'
            path.write_bytes(raw)
            result = inspect_log(path, 'RX-02')
            self.assertEqual(result['complete_lines'], 2)
            self.assertEqual(result['initial_invalid_lines'], 2)
            self.assertEqual(result['tail']['raw_hex'], '49')
            self.assertEqual(result['selected_lines'][1]['byte_offset'], 7)
            self.assertEqual(result['sha256'], hashlib.sha256(raw).hexdigest())
            self.assertEqual(path.read_bytes(), raw)

    def test_inspection_rejects_character_devices_without_opening(self):
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('No device reads')):
            with self.assertRaises(ValueError):inspect_log('/dev/null', 'RX-01')

    @unittest.skipUnless(all((ROOT/rel/'rx-01.serial.log').is_file() and
                            (ROOT/rel/'rx-02.serial.log').is_file() for rel in map(Path, LOG_DIRECTORIES)),
                         'Local historical logs not available')
    def test_existing_observed_orders_are_read_only_and_initial_formats_remain_rejected(self):
        report = inspect_existing()
        self.assertEqual(len(report['logs']), 12)
        self.assertEqual(report['missing'], [])
        for log in report['logs']:
            path = ROOT/log['path']; before = path.read_bytes()
            rx = log['receiver']
            # Counterfactual reducer with SYNTHETIC clocks over recorded bytes;
            # not historical replay and not a newly acquired physical session.
            r = Rig(machine); r.send(before, rx)
            self.assertIn('format:'+rx, r.m.connection_reasons)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), log['sha256'])
            if log['ready_line'] is not None:
                lines = log['selected_lines']; ready = log['ready_line']
                after = [bytes.fromhex(l['raw_hex']) for l in lines if l['line_1based'] > ready]
                self.assertEqual(len(after), 2 if rx == 'RX-01' else 1)
                if rx == 'RX-01':
                    self.assertIsNotNone(re.fullmatch(rb'I \([0-9]+\) wifi:ic_enable_sniffer\r\n', after[0]))
                self.assertIsNotNone(re.fullmatch(rb'I \([0-9]+\) main_task: Returned from app_main\(\)\r\n', after[-1]))
                self.assertTrue(r.m.startup_messages[rx]['returned'])


if __name__ == '__main__':
    unittest.main()
