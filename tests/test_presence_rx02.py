"""RX-02 pilot tests: pure reducer and pySerial over one process-owned PTY.

No physical bytes are used for acceptance, tuning or fixture generation.
"""
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'tools'))
import serial
from campana_presencia_v4 import fixture_row, fixture_ready
from test_persistent_presence_v4 import Memory
from test_v4_startup_sequence import boot, modified_row, SNIFFER, RETURN
from persistent_presence_v4 import POLICY, SECOND, validate_plan as validate_dual
from presence_v4_exploratory import STORAGE_POLICY
from presence_v4_pty import OwnedPty, SteppedFixtureClock
from presence_v4_audio import RecordingNotifier
from presence_rx02 import Rx02Presence, RECEIVERS, PORTS, PARTITIONS, validate_plan
from presence_rx02_journal import audit_rx02
from presence_rx02_uart import Rx02Session, preflight_rx02
from piloto_presencia_rx02 import main, CommandInput, operator_command

PREFIX = b'\xff\x00uninterpreted startup\r\n'


def plan(index=1):
    return json.loads((ROOT/f'config/piloto_rx02_r1_C{index:02d}.review.json').read_text())


class SingleMemory(Memory):
    def __init__(self, *, start=True, prefix=PREFIX, index=1):
        self.p = plan(index)
        self.m = Rx02Presence(self.p)
        self.t = SECOND
        self.ids = dict.fromkeys(RECEIVERS, 0)
        self.call('begin')
        self.call('opened', receiver='RX-02')
        if start:
            self.send('RX-02', prefix+boot('RX-02'))
            self.advance(.6)
            assert self.m.initial_available is not None

    def step(self, ns=200_000_000):
        self.t += ns
        self.row('RX-02')
        self.call('tick')
        self.signals()

    def request(self, index=0, last=False):
        self.call('request', slot_id=self.p['slots'][index]['id'], last=last)

    def close(self, confirmed=True):
        self.call('close_request')
        self.call('closing')
        self.call('closed', receiver='RX-02', confirmed=confirmed, reader_stopped=True)
        self.signals()

    def complete(self):
        self.running(); self.finished(); self.declare()
        self.request(1, last=True)
        self.until(lambda: self.m.windows[-1]['state'] == 'running')
        self.finished(); self.declare(); self.close()
        return self.m.summary()


class Rig:
    def __init__(self, scenario=None):
        self.tmp = tempfile.TemporaryDirectory()
        self.output = Path(self.tmp.name)/'bundle'
        self.pair = OwnedPty('RX-02')
        self.clock = SteppedFixtureClock()
        self.calls, self.objects = [], []
        self.free, self.ident = 1024**3, 0
        st = os.fstat(self.pair.slave)
        self.identity = dict(by_id=PORTS['RX-02'], resolved=os.ttyname(self.pair.slave),
            serial=RECEIVERS['RX-02'], vid='1a86', pid='55d3', bus='usb',
            node_fingerprint=[st.st_dev, st.st_ino, st.st_rdev])
        rig = self

        class SerialDouble(serial.Serial):
            def __init__(self, **kwargs):
                rig.calls.append(('construct', kwargs))
                super().__init__(**kwargs)
                rig.objects.append(self)

            def open(self):
                assert self.port == PORTS['RX-02'], 'Never open a real UART or substitute RX-01'
                rig.calls.append(('open', self.port))
                self.port = rig.identity['resolved']
                super().open()
                if scenario == 'open_failure':
                    raise OSError('Synthetic failure after allocating PTY fd')

            def read(self, size=1):
                if scenario == 'read_failure':
                    raise OSError('Synthetic read error')
                return super().read(size)

            def close(self):
                rig.calls.append(('close', self.is_open))
                if scenario == 'close_failure' and self.is_open:
                    raise OSError('Synthetic unconfirmed close')
                return super().close()

        def checker(rx, expected):
            assert rx == 'RX-02'
            rig.calls.append(('identity', rx))
            if scenario == 'identity_failure':
                raise ValueError('Synthetic USB identity change')
            return expected

        self.backend = dict(identities={'RX-02': self.identity}, checker=checker,
            serial_type=SerialDouble, disk_usage=lambda _: SimpleNamespace(free=self.free))

    def session(self, **kwargs):
        return Rx02Session(self.output, plan(), test_backend=self.backend, clock=self.clock, **kwargs)

    def step(self, session):
        self.clock.advance(200_000_000)
        if not session.read_loop_stopped and not session.machine.close_requested:
            self.pair.fixture_write(fixture_row(self.ident, 100000+self.ident*200000))
            self.ident += 1
        session.step()

    def complete(self):
        # Queue before open to prove input preservation; no ROM/unknown byte is
        # removed or relabelled as valid CSI.
        self.pair.fixture_write(PREFIX+boot('RX-02'))
        with self.session() as session:
            session.step()
            for _ in range(1200):
                self.step(session)
                m = session.machine
                if m.fatal:
                    raise AssertionError(m.fatal)
                if m.initial_available is not None:
                    if m.windows:
                        w = m.windows[-1]
                        if w['end_signal'] is not None and m.signals[w['end_signal']]['ack_ns'] is not None and w['label']['status'] == 'pending':
                            session.command('declare', slot_id=w['id'], established=True,
                                            maintained=True, heard=True, notes='')
                    if not m.close_requested and len(m.windows) < 2 and (not m.windows or m.windows[-1]['label']['status'] == 'declared'):
                        session.command('request', slot_id=plan()['slots'][len(m.windows)]['id'], last=len(m.windows) == 1)
                if session.read_loop_stopped:
                    break
            else:
                raise AssertionError('Synthetic pilot did not complete')
        return audit_rx02(self.output)

    def dispose(self):
        for obj in self.objects:
            serial.Serial.close(obj)  # Fixture cleanup is not protocol close proof.
        self.pair.dispose_fixture()
        self.tmp.cleanup()


class ContractTests(unittest.TestCase):
    def test_six_connections_repeated_labels_and_whole_connection_partitions(self):
        campaign = json.loads((ROOT/'config/piloto_rx02_r1.campaign.review.json').read_text())
        self.assertFalse(campaign['authorization_granted'])
        self.assertFalse(campaign['automatic_replacement'])
        self.assertEqual(len(campaign['connections']), 6)
        for index, (cid, partition) in enumerate(PARTITIONS.items(), 1):
            p = validate_plan(plan(index))
            self.assertEqual(p['connection_id'], p['partition_group'])
            self.assertEqual(p['future_partition'], partition)
            self.assertEqual([s['condition'] for s in p['slots']], ['E', 'S'] if index % 2 else ['S', 'E'])
            self.assertEqual(p['policy'], POLICY)
            self.assertEqual(p['storage_policy'], STORAGE_POLICY)
            with self.assertRaises(ValueError):
                validate_plan(p, allow_physical=True, execution=True)
            with self.assertRaises(ValueError):
                validate_dual(p)

    def test_identity_policy_profile_partition_and_selection_cannot_change(self):
        changes = [dict(receivers={'RX-01': '5C93199744'}), dict(ports={'RX-02': '/dev/ttyACM0'}),
            dict(policy=dict(POLICY, freshness_ns=2*SECOND)), dict(storage_policy={}),
            dict(line_policy_revision='allow_any_info'), dict(eligibility_revision='v4-exploratory-1'),
            dict(future_partition='development_future', partition_group='row-split'),
            dict(transmitter=dict(identity='TX-02', source_mac='other')), dict(selection_revision=''),
            dict(permitted_uses=dict(calibration=True, training=False, production=False))]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_plan(dict(plan(), **change))

    def test_prepare_never_discovers_or_constructs_serial(self):
        with patch('serial.Serial', side_effect=AssertionError('No UART')), \
             patch('presence_rx02_uart.identity', side_effect=AssertionError('No discovery')), \
             contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(main([]), 0)
        self.assertEqual(json.loads(out.getvalue())['state'], 'PREPARED_NOT_AUTHORIZED')

    def test_preflight_only_queries_rx02_metadata(self):
        snapshot = dict(by_id=PORTS['RX-02'], serial=RECEIVERS['RX-02'])
        with patch('presence_rx02_uart.identity', return_value=snapshot) as meta, \
             patch('serial.Serial', side_effect=AssertionError('No UART')):
            self.assertEqual(preflight_rx02(plan()), {'RX-02': snapshot})
        meta.assert_called_once_with('RX-02')
        with patch('presence_rx02_uart.identity', return_value=dict(snapshot, serial='5C93199744')):
            with self.assertRaises(ValueError):
                preflight_rx02(plan())

    def test_execution_requires_new_declarations_rx01_confirmation_and_authorization(self):
        with patch('serial.Serial', side_effect=AssertionError('No UART')):
            with self.assertRaises(ValueError):
                main(['--execute-after-approval'])
            with self.assertRaises(ValueError):
                main(['--execute-after-approval', '--authorization-reference', 'NEW-REFERENCE'])
        p = plan()
        p.update(execution_mode='physical_after_approval', actor='SYNTHETIC-DECLARATION',
                 mounting_reference='synthetic-no-physical-verification')
        p['environment'] = {key: 'Synthetic declaration only' for key in p['environment']}
        with self.assertRaises(ValueError):
            validate_plan(p, allow_physical=True, execution=True)
        p['unused_receiver']['operator_confirmation'] = 'confirmed_current'
        validate_plan(p, allow_physical=True, execution=True)  # Validation alone never opens UART.

    def test_partial_operator_command_never_waits_for_newline(self):
        reader, writer = os.pipe()
        try:
            commands = CommandInput(reader)
            os.write(writer, b'slot RX02-C01-')
            self.assertEqual(commands.poll(), [])
            os.write(writer, b'E\n')
            self.assertEqual(commands.poll(), [['slot', 'RX02-C01-E']])
            os.close(writer); writer = None
            commands.poll()
            self.assertTrue(commands.eof)
        finally:
            os.close(reader)
            if writer is not None:
                os.close(writer)


class ReducerTests(unittest.TestCase):
    def test_anomalous_preamble_two_future_windows_and_truth_are_separate(self):
        h = SingleMemory(); s = h.complete()
        self.assertIsNone(s['fatal'])
        self.assertFalse(s['connection']['quality_ok'])
        self.assertFalse(any(w['eligible'] for w in s['windows']))
        self.assertTrue(all(w['candidate'] for w in s['exploration']['windows']))
        self.assertEqual(s['exploration']['preamble_status'], 'anomalous_uninterpreted')
        self.assertEqual(set(s['closed']), {'RX-02'})
        self.assertEqual(set(s['startup_messages']), {'RX-02'})
        pre = s['exploration']['preamble']['receivers']['RX-02']
        self.assertEqual(pre['lines'][0]['line_sha256'], hashlib.sha256(PREFIX).hexdigest())
        self.assertEqual(pre['lines'][0]['kind'], 'invalid')
        self.assertEqual(s['exploration']['permitted_uses'], dict(calibration=False, training=False, production=False))
        self.assertEqual(sum(e['kind'] == 'opened' for e in h.m.events), 1)
        self.assertNotIn('both_ports_closed_confirmed', [c['kind'] for c in s['signals']])
        self.assertEqual(s['signals'][-1]['kind'], 'selected_port_closed_confirmed')

    def test_clean_complete_connection_uses_same_coverage(self):
        s = SingleMemory(prefix=b'').complete()
        self.assertTrue(s['connection']['quality_ok'])
        self.assertTrue(all(w['eligible'] for w in s['windows']))
        for w in s['exploration']['windows']:
            coverage = w['receivers']['RX-02']
            self.assertGreaterEqual(coverage['included_rows'], 120)
            self.assertGreaterEqual(min(coverage['bins_5s']), 15)
            self.assertLessEqual(max(coverage['gaps_ns']), 500_000_000)

    def test_se_order_prespecified_in_second_connection(self):
        s = SingleMemory(index=2).complete()
        self.assertEqual([w['condition'] for w in s['windows']], ['S', 'E'])

    def test_bootstrap_chunk_cannot_supply_new_rows(self):
        h = SingleMemory(start=False)
        h.send('RX-02', boot('RX-02')+b''.join(fixture_row(i, 100000+i*200000) for i in range(3)))
        h.ids['RX-02'] = 3
        h.call('tick')
        self.assertIsNone(h.m.initial_available)
        for i in range(3):
            h.step()
            self.assertEqual(h.m.initial_available is not None, i == 2)

    def test_missing_return_or_fragment_cannot_become_available(self):
        for data in (fixture_ready('RX-02'), boot('RX-02')+b'CSI_DATA,'):
            h = SingleMemory(start=False)
            h.send('RX-02', data)
            if data == fixture_ready('RX-02'):
                h.advance(.6)
            else:
                h.call('tick')  # Keep the fragment pending; do not append a fixture row to it.
            self.assertIsNone(h.m.initial_available)
            h.t = h.m.a+10*SECOND; h.call('tick')
            self.assertEqual(h.m.fatal, 'initial_availability_timeout')

    def test_reset_errors_generic_info_profile_and_discontinuity_never_rearm(self):
        cases = (b'ESP-ROM:esp32s3-20210327\n', b'E (999) other: error\n',
            b'I (999) other: normal-looking text\n', SNIFFER, RETURN,
            fixture_ready('RX-02'), fixture_row(0, 100000), modified_row(id=3, local_timestamp=700000, channel=6),
            modified_row(id=3, local_timestamp=700000, queue_drops=1), modified_row(id=3, local_timestamp=0),
            modified_row(id=3, local_timestamp=700000, mac='00:00:00:00:00:00'))
        for data in cases:
            with self.subTest(data=data[:60]):
                h = SingleMemory(); h.send('RX-02', data)
                self.assertIsNotNone(h.m.fatal)
                with self.assertRaises(ValueError):
                    h.request()
                with self.assertRaises(ValueError):
                    h.call('opened', receiver='RX-02')

    def test_exact_watchdog_and_gap_after_recovery_still_suspend(self):
        for recovery in (False, True):
            h = SingleMemory()
            h.t += SECOND+1
            if recovery:
                h.row('RX-02')
            else:
                h.call('tick')
            self.assertIn(h.m.fatal, ('availability_lost:RX-02', 'availability_gap:RX-02'))
            h.row('RX-02'); h.call('tick')
            with self.assertRaises(ValueError):
                h.request()

    def test_anomaly_crossing_window_and_unknown_tail_are_ineligible(self):
        h = SingleMemory(); w = h.running()
        h.send('RX-02', b'\xff', start=w['T0_ns'], end=w['T0_ns'])
        self.assertFalse(h.m.summary()['exploration']['windows'][0]['candidate'])
        h.t += 100_000_000; h.send('RX-02', b'bad\n')
        s = h.m.summary()
        self.assertIn('anomaly_intersects_or_unlocated', s['exploration']['windows'][0]['reasons'])

    def test_unlocated_anomaly_and_boundary_touch_are_conservatively_excluded(self):
        for mode in ('touch', 'cross', 'unknown'):
            h = SingleMemory(); w = h.running()
            anomaly = copy.deepcopy(h.m.anomalies[0])
            anomaly.update(start_ns=None if mode == 'unknown' else w['T0_ns']-1,
                           end_ns=w['T0_ns']+(1 if mode == 'cross' else 0))
            h.m.anomalies.append(anomaly)
            reasons = h.m.summary()['exploration']['windows'][0]['reasons']
            self.assertIn('anomaly_intersects_or_unlocated', reasons)

    def test_read_begun_before_barrier_and_late_processed_rows_are_excluded(self):
        h = SingleMemory(start=False)
        h.send('RX-02', boot('RX-02'), start=h.t-1, end=h.t-1)
        barrier = h.t
        h.send('RX-02', b''.join(fixture_row(i, 100000+i*200000) for i in range(3)), start=barrier-1)
        h.ids['RX-02'] = 3; h.call('tick')
        self.assertIsNone(h.m.initial_available)
        h.advance(.6); w = h.running()
        h.finished(); h.declare(); h.close()
        line = next(e for e in h.m.events if e['kind'] == 'line' and
            e['evidence']['kind'] == 'row' and int(e['evidence']['returned_ns']) > w['T0_ns'])
        line['now_ns'] = w['T1_ns']
        self.assertIn('late_row_processing', h.m.summary()['exploration']['windows'][0]['reasons'])

    def test_low_coverage_is_not_rescued_by_singleton(self):
        h = SingleMemory(); h.running()
        for _ in range(50):
            h.step(600_000_000)
        self.assertEqual(h.m.fatal, 'pilot_coverage_failed')
        self.assertFalse(h.m.summary()['windows'][0]['pilot_coverage_ok'])

    def test_no_early_last_or_skipped_slot_or_rx01_substitution(self):
        h = SingleMemory()
        for args in (dict(index=0, last=True), dict(index=1, last=True)):
            with self.assertRaises(ValueError):
                h.request(**args)
        with self.assertRaises(ValueError):
            h.call('opened', receiver='RX-01')
        self.assertEqual(set(h.m.states), {'RX-02'})

    def test_uncertain_label_and_audio_failure_suspend(self):
        h = SingleMemory(); h.running(); h.finished(); h.declare(heard=False)
        self.assertEqual(h.m.fatal, 'uncertain_label')
        h = SingleMemory(); h.request()
        h.until(lambda: bool(h.m.signals))
        # A later failed cue also revokes eligibility, even after a prior ack.
        cue = h.m.signal('failure')
        h.call('cue_ack', signal_id=cue, success=False)
        self.assertEqual(h.m.fatal, 'notification_failed')

    def test_unconfirmed_close_and_late_storage_failure_revoke(self):
        h = SingleMemory(); h.running(); h.finished(); h.declare(); h.close(confirmed=False)
        self.assertFalse(h.m.summary()['exploration']['windows'][0]['candidate'])
        h = SingleMemory(); h.complete(); h.call('storage_error')
        self.assertFalse(any(w['candidate'] for w in h.m.summary()['exploration']['windows']))


class TransportTests(unittest.TestCase):
    def rig(self, scenario=None):
        rig = Rig(scenario)
        self.addCleanup(rig.dispose)
        return rig

    def test_single_endpoint_input_preserved_and_close_receipt_before_final_cue(self):
        rig = self.rig()
        rig.pair.fixture_write(PREFIX+boot('RX-02'))
        with rig.session() as s:
            s.step()
            self.assertEqual(set(s.endpoints), {'RX-02'})
            self.assertTrue((rig.output/'rx-02.serial.log').read_bytes().startswith(PREFIX))
            s.close()
            self.assertTrue(s.receipt_persisted)
            self.assertEqual(s.machine.signals[-1]['kind'], 'selected_port_closed_confirmed')
        report = audit_rx02(rig.output)
        self.assertTrue(report['integrity_ok'] and report['replay_ok'])
        self.assertEqual(sum(c[0] == 'construct' for c in rig.calls), 1)
        self.assertEqual(sum(c[0] == 'open' for c in rig.calls), 1)
        self.assertFalse((rig.output/'rx-01.serial.log').exists())
        runtime = json.loads((rig.output/'summary.json').read_text())['runtime']['receivers']['RX-02']
        self.assertEqual(runtime['open_attempts'], 1)
        self.assertEqual(runtime['close_attempts'], 1)
        self.assertFalse(runtime['is_open'])

    def test_open_and_identity_failure_close_once_without_fallback(self):
        for scenario in ('open_failure', 'identity_failure'):
            rig = self.rig(scenario)
            with self.assertRaises((OSError, ValueError)):
                rig.session()
            self.assertLessEqual(sum(c[0] == 'open' for c in rig.calls), 1)
            self.assertEqual(sum(c[0] == 'construct' for c in rig.calls), 1)
            self.assertTrue((rig.output/'close-receipt.json').exists())
            self.assertTrue(audit_rx02(rig.output)['replay_ok'])

    def test_read_error_closes_selected_port(self):
        rig = self.rig('read_failure')
        with rig.session() as s:
            rig.pair.fixture_write(b'x')
            s.step()
            self.assertTrue(s.read_loop_stopped)
            self.assertEqual(s.machine.fatal, 'io_error:RX-02')
        self.assertTrue(audit_rx02(rig.output)['replay_ok'])

    def test_close_failure_is_not_confirmed_or_retried(self):
        rig = self.rig('close_failure')
        with rig.session() as s:
            s.close()
            self.assertFalse(s.machine.selected_closed())
            self.assertNotIn('selected_port_closed_confirmed', [c['kind'] for c in s.machine.signals])
        self.assertEqual(sum(c[0] == 'close' and c[1] for c in rig.calls), 1)
        self.assertTrue(audit_rx02(rig.output)['replay_ok'])

    def test_storage_reserve_stops_and_closes_without_quality_approval(self):
        rig = self.rig()
        with rig.session() as s:
            rig.free = STORAGE_POLICY['reserve_bytes']-1
            rig.clock.advance(SECOND)
            s.step()
            self.assertEqual(s.machine.fatal, 'storage_error')
            self.assertTrue(s.machine.selected_closed())
            rig.free = 1024**3  # Only synthetic disk stub recovers for final artifacts.
        self.assertFalse(audit_rx02(rig.output)['state']['connection']['quality_ok'])

    def test_journal_storage_failure_still_closes_and_never_finalizes(self):
        rig = self.rig()
        s = rig.session()
        with patch.object(s.journal.ops, 'write', side_effect=OSError('synthetic disk failure')):
            with self.assertRaises(OSError):
                s.command('tick')
            s.close()
        self.assertTrue(s.read_loop_stopped)
        self.assertFalse(s.receipt_persisted)
        self.assertTrue(s.machine.selected_closed())
        with self.assertRaises(RuntimeError):
            s.finalize()
        s.journal.close_files(); s._finish_notifier()
        self.assertFalse((rig.output/'manifest.json').exists())

    def test_close_sound_waits_for_durable_receipt(self):
        rig = self.rig()
        with rig.session() as s:
            original = s.journal.receipt
            def receipt():
                self.assertNotIn('selected_port_closed_confirmed',
                    [c['kind'] for c in s.machine.signals if c['id'] in s.started_signals])
                return original()
            with patch.object(s.journal, 'receipt', side_effect=receipt):
                s.close()
            self.assertTrue(s.receipt_persisted)
            self.assertIn(s.machine.signals[-1]['id'], s.started_signals)


class BundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rig = Rig()
        try:
            cls.report = cls.rig.complete()
        except BaseException:
            cls.rig.dispose()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.rig.dispose()

    def test_two_labeled_windows_require_replay_identity_storage_and_close(self):
        report = self.report
        self.assertTrue(report['integrity_ok'] and report['replay_ok'])
        self.assertEqual(report['state']['evidence_type'], 'synthetic_fixture')
        self.assertFalse(report['state']['connection']['quality_ok'])
        cert = report['exploratory_eligibility']
        self.assertTrue(cert['identity_ok'] and cert['storage_ok'])
        self.assertEqual(len(cert['windows']), 2)
        self.assertTrue(all(w['eligible'] for w in cert['windows']))
        self.assertFalse(any(cert['permitted_uses'].values()))

    def test_tampered_raw_operations_summary_receipt_and_sources_reject(self):
        for name in ('rx-02.serial.log', 'operations.jsonl', 'summary.json', 'close-receipt.json', 'provenance.json'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp)/'copy'; shutil.copytree(self.rig.output, out)
                with (out/name).open('ab') as f:
                    f.write(b'\nX')
                with self.assertRaises(ValueError):
                    audit_rx02(out)

    def rewrite_manifest(self, root):
        manifest = json.loads((root/'manifest.json').read_text())
        for item in manifest['files']:
            data = (root/item['path']).read_bytes()
            item.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        (root/'manifest.json').write_text(json.dumps(manifest))

    def test_rehashed_summary_and_provenance_do_not_bypass_replay(self):
        for name in ('summary.json', 'provenance.json', 'close-receipt.json'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp)/'copy'; shutil.copytree(self.rig.output, out)
                obj = json.loads((out/name).read_text())
                if name == 'summary.json':
                    obj['state']['exploration']['preamble']['receivers']['RX-02']['sha256'] = '0'*64
                elif name == 'provenance.json':
                    obj['sources'][0]['sha256'] = '0'*64
                else:
                    obj['selected_confirmed'] = False
                (out/name).write_text(json.dumps(obj)); self.rewrite_manifest(out)
                with self.assertRaises(ValueError):
                    audit_rx02(out)

    def test_missing_identity_or_storage_evidence_cannot_certify_windows(self):
        from presence_rx02 import certify_rx02
        for mode in ('identity', 'storage', 'extra_receiver'):
            provenance = json.loads((self.rig.output/'provenance.json').read_text())
            state = copy.deepcopy(self.report['state'])
            if mode == 'identity':
                provenance['transport']['identities']['RX-02']['serial'] = '5C93199744'
            elif mode == 'storage':
                state['exploration']['storage_checks'][-1]['final_extra'] = 0
            else:
                provenance['transport']['identities']['RX-01'] = {}
            cert = certify_rx02(self.rig.output, provenance, state)
            self.assertFalse(any(w['eligible'] for w in cert['windows']))
