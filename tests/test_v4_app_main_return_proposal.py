"""Review-only patch: apply in a temporary copy, never to the UART backend.

All candidate inputs are synthetic bytes and clocks. The optional historical
test only reads the existing rejected bundle; it never replays a transport.
"""
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_persistent_presence_v4 import ROOT, plan
from campana_presencia_v4 import fixture_ready, fixture_row
from persistent_presence_v4 import PersistentPresenceV4, SECOND
from presence_v4_journal import audit_v4

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


class AppMainReturnProposal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        root = Path(cls.temp.name)
        (root/'src').mkdir()
        source = ROOT/'src/persistent_presence_v4.py'
        (root/'src/persistent_presence_v4.py').write_bytes(source.read_bytes())
        subprocess.run(['patch', '--batch', '--forward', '-p1', '-i',
                        str(ROOT/'proposals/v4-app-main-return.patch')],
                       cwd=root, capture_output=True, check=True)
        spec = importlib.util.spec_from_file_location(
            'review_only_v4_app_main_return', root/'src/persistent_presence_v4.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cls.candidate = module.PersistentPresenceV4

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_original_rejects_exact_observed_message(self):
        r = Rig(PersistentPresenceV4)
        r.send(fixture_ready('RX-02')+RETURN)
        self.assertEqual(r.m.fatal, 'post_ready_info:RX-02')

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
                    b'\xff'+RETURN, RETURN.replace(b'545', b'-1')]
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


if __name__ == '__main__':
    unittest.main()
