"""Synthetic exploratory windows; old physical data are never promoted."""
import copy
import hashlib
import contextlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from test_persistent_presence_v4 import Memory, ROOT
from test_uart_v4 import Rig as UartRig, plan as uart_plan
from test_v4_startup_sequence import boot, SNIFFER, RETURN, modified_row
from campana_presencia_v4 import fixture_ready, fixture_row
from persistent_presence_v4 import (EXPLORATORY_ELIGIBILITY, STARTUP_SEQUENCE_POLICY,
                                    PersistentPresenceV4, SECOND, validate_plan)
from presence_v4_exploratory import make_v4_machine, outside_window, STORAGE_POLICY
from presence_v4_journal import audit_v4, digest
from presence_v4_uart import UartSession, STORAGE

PREFIX = b'\xff\x00ESP-ROM:esp32s3-20210327\r\n'


def plan():
    return dict(uart_plan(), eligibility_revision=EXPLORATORY_ELIGIBILITY,
                line_policy_revision=STARTUP_SEQUENCE_POLICY)


class ExploratoryMemory(Memory):
    def __init__(self, *, start=True, prefix=PREFIX, journal=None):
        self.journal = journal
        self.m = journal.machine if journal is not None else make_v4_machine(plan())
        self.t = SECOND
        self.ids = dict.fromkeys(('RX-01', 'RX-02'), 0)
        self.call('begin')
        for rx in self.ids:
            self.call('opened', receiver=rx)
        if start:
            for rx in self.ids:
                self.send(rx, prefix+boot(rx))
            self.advance(.6)
            assert self.m.initial_available is not None

    def call(self, op, **data):
        if self.journal is not None:self.journal.command(op, self.t, **data)
        else:super().call(op, **data)

    def request(self, index=0, last=False):
        self.call('request', slot_id=plan()['slots'][index]['id'], last=last)


def generate_serial_bundle(output):
    """Actual pySerial over process-owned PTYs, with synthetic bytes/clocks only."""
    rig = UartRig()
    try:
        with UartSession(rig.output, plan(), test_backend=rig.backend, clock=rig.clock) as session:
            for rx, endpoint in rig.pairs.items():
                endpoint.fixture_write(PREFIX+boot(rx))
            session.step()
            for _ in range(4400):
                rig.step(session); m = session.machine
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
                raise AssertionError('Synthetic fixture did not finish')
        report = audit_v4(rig.output)
        shutil.copytree(rig.output, output)
        return report
    finally:
        rig.finish_fixture()


class ExploratoryProtocolTests(unittest.TestCase):
    def completed(self, **kwargs):
        h = ExploratoryMemory(**kwargs)
        h.running(); h.finished(); h.declare(); h.close()
        return h

    def test_anomalous_preamble_and_future_window_are_separate_results(self):
        h = self.completed(); s = h.m.summary()
        self.assertFalse(s['connection']['quality_ok'])
        self.assertFalse(s['windows'][0]['eligible'])
        self.assertTrue(s['exploration']['windows'][0]['candidate'])
        self.assertIsNone(s['exploration']['windows'][0]['eligible'])
        self.assertEqual(s['exploration']['preamble_status'], 'anomalous_uninterpreted')
        for rx, pre in s['exploration']['preamble']['receivers'].items():
            self.assertEqual(pre['byte_offset'], 0)
            self.assertEqual(pre['lines'][0]['kind'], 'invalid')
            self.assertEqual(pre['lines'][0]['line_sha256'], hashlib.sha256(PREFIX).hexdigest())
            self.assertTrue(all(r['byte_offset'] >= pre['byte_end'] for r in
                                s['windows'][0]['receivers'][rx]['included_line_references']))
        self.assertEqual(s['exploration']['permitted_uses'], dict(calibration=False, training=False, production=False))

    def test_bootstrap_chunk_rows_are_not_new_evidence(self):
        h = ExploratoryMemory(start=False)
        for rx in h.ids:
            h.send(rx, PREFIX+boot(rx)+b''.join(fixture_row(i, 100000+i*200000) for i in range(3)))
            h.ids[rx] = 3
        h.call('tick')
        self.assertIsNone(h.m.initial_available)
        self.assertTrue(all(not s['streak'] for s in h.m.states.values()))
        for i in range(3):
            h.step()
            self.assertEqual(h.m.initial_available is not None, i == 2)

    def test_read_started_before_global_barrier_cannot_supply_initial_rows(self):
        h = ExploratoryMemory(start=False)
        h.send('RX-01', boot('RX-01')); h.t += 100_000_000
        h.send('RX-02', boot('RX-02'))
        barrier = h.t
        rows = b''.join(fixture_row(i, 100000+i*200000) for i in range(3))
        h.send('RX-01', rows, start=barrier-1, end=barrier)
        h.send('RX-02', rows)
        h.call('tick')
        self.assertIsNone(h.m.fatal)
        self.assertIsNone(h.m.initial_available)
        self.assertFalse(h.m.states['RX-01']['streak'])

    def test_pending_line_prevents_initial_gate_and_times_out(self):
        h = ExploratoryMemory(start=False)
        for rx in h.ids:h.send(rx, boot(rx))
        h.advance(.4)
        h.send('RX-01', b'I')
        h.row('RX-02'); h.call('tick')
        self.assertIsNone(h.m.initial_available)
        h.t = h.m.a+10*SECOND; h.call('tick')
        self.assertEqual(h.m.fatal, 'initial_availability_timeout')

    def test_pending_line_prevents_prospective_slot_start(self):
        h = ExploratoryMemory(); h.request()
        h.until(lambda: h.m.windows[-1]['state'] == 'gate')
        h.advance(.4); h.send('RX-01', b'CSI_DATA,')
        h.row('RX-02'); h.call('tick')
        self.assertIsNone(h.m.windows[-1]['T0_ns'])

    def test_uncertainty_intervals_touch_cross_and_unknown(self):
        for interval, expected in ((dict(start_ns=1, end_ns=9), True),
            (dict(start_ns=1, end_ns=10), False), (dict(start_ns=9, end_ns=11), False),
            (dict(start_ns=19, end_ns=20), False), (dict(start_ns=20, end_ns=21), True),
            (dict(start_ns=None, end_ns=9), False), (dict(start_ns=1, end_ns=None), False),
            (dict(start_ns=8, end_ns=7), False)):
            self.assertEqual(outside_window(interval, 10, 20), expected)

    def test_late_processing_keeps_anomaly_inside_window(self):
        h = ExploratoryMemory(); w = h.running(); t0 = w['T0_ns']
        h.t += 100_000_000
        h.send('RX-01', b'I (900) other: unknown\n', start=t0, end=t0)
        a = h.m.summary()['exploration']['anomalies'][-1]
        self.assertEqual(a['start_ns'], t0)
        self.assertEqual(a['end_ns'], h.t)
        self.assertFalse(h.m.summary()['exploration']['windows'][0]['candidate'])
        self.assertIn('anomaly_intersects_or_unlocated', h.m.summary()['exploration']['windows'][0]['reasons'])

    def test_anomaly_completed_across_window_start_is_not_trimmed(self):
        h = ExploratoryMemory(); w = h.running(); t0 = w['T0_ns']
        h.send('RX-01', b'\xff', start=t0, end=t0)
        h.t += 200_000_000; h.send('RX-01', b'error\n')
        a = h.m.summary()['exploration']['anomalies'][-1]
        self.assertEqual(a['start_ns'], t0)
        self.assertEqual(a['end_ns'], h.t)
        self.assertFalse(h.m.summary()['exploration']['windows'][0]['candidate'])

    def test_resets_errors_generic_text_and_discontinuities_suspend_without_rearm(self):
        for data in (b'ESP-ROM:esp32s3-20210327\n', b'rst:0x1 (POWERON)\n',
                     b'E (999) main_task: error\n', b'I (999) other: hello\n',
                     fixture_row(0, 100000), modified_row(channel=6),
                     modified_row(queue_drops=1), modified_row(local_timestamp=0),
                     fixture_ready('RX-01'), SNIFFER, RETURN):
            h = ExploratoryMemory(); h.send('RX-01', data)
            self.assertIsNotNone(h.m.fatal)
            with self.assertRaises(ValueError):h.request()
            with self.assertRaises(ValueError):h.call('opened', receiver='RX-01')

    def test_late_failure_revokes_earlier_window_and_unknown_failure_is_not_outside(self):
        h = self.completed()
        self.assertTrue(h.m.summary()['exploration']['windows'][0]['candidate'])
        h.call('storage_error')
        self.assertFalse(h.m.summary()['exploration']['windows'][0]['candidate'])
        self.assertIsNone(h.m.summary()['exploration']['failures'][-1]['start_ns'])

    def test_error_after_clean_preamble_does_not_relabel_the_sealed_preamble(self):
        h = ExploratoryMemory(prefix=b'')
        before = h.m.summary()['exploration']
        self.assertEqual(before['preamble_status'], 'no_anomaly_recorded')
        h.send('RX-01', b'E (999) main_task: error\n')
        after = h.m.summary()['exploration']
        self.assertEqual(after['preamble_status'], 'no_anomaly_recorded')
        self.assertEqual(before['preamble'], after['preamble'])
        self.assertIsNotNone(h.m.fatal)

    def test_lost_availability_and_unconfirmed_closure_prevent_candidate(self):
        h = ExploratoryMemory(); h.t += SECOND+1; h.call('tick')
        self.assertIsNotNone(h.m.fatal)
        h = ExploratoryMemory(); h.running(); h.finished(); h.declare()
        h.call('close_request'); h.call('closing')
        for rx in h.ids:h.call('closed', receiver=rx, confirmed=rx != 'RX-01', reader_stopped=True)
        self.assertFalse(h.m.summary()['exploration']['windows'][0]['candidate'])

    def test_label_coverage_and_storage_failures_remain_mandatory(self):
        h = ExploratoryMemory(); h.running(); h.finished(); h.declare(heard=False); h.close()
        self.assertFalse(h.m.summary()['exploration']['windows'][0]['candidate'])
        h = ExploratoryMemory(); h.running(); h.step(ns=600_000_000)
        h.until(lambda: h.m.fatal is not None)
        self.assertEqual(h.m.fatal, 'pilot_coverage_failed')
        self.assertFalse(h.m.summary()['exploration']['windows'][0]['candidate'])
        h = ExploratoryMemory()
        h.call('storage_check', free_bytes=0, raw_bytes=0, size_bytes=0, final_extra=1, guard_started_ns=0)
        self.assertEqual(h.m.fatal, 'storage_assurance_failed')

    def test_rows_processed_after_T1_cannot_support_exploratory_coverage(self):
        h = ExploratoryMemory(); w = h.running()
        h.until(lambda: h.t >= w['T1_ns']-200_000_000)
        h.t = w['T1_ns']; h.row('RX-02'); h.call('tick'); h.signals()
        self.assertEqual(w['state'], 'complete')
        h.t += 200_000_000
        h.row('RX-01', start=w['T1_ns']-100_000_000, end=w['T1_ns']-50_000_000)
        self.assertIsNone(h.m.fatal)
        h.finished(); h.declare(); h.close()
        self.assertIn('late_row_processing', h.m.summary()['exploration']['windows'][0]['reasons'])

    def test_journal_never_certifies_candidates_without_transport_assurances(self):
        from presence_v4_journal import V4Journal
        with tempfile.TemporaryDirectory() as tmp:
            j = V4Journal(Path(tmp)/'new', plan()); self.addCleanup(j.close_files)
            h = ExploratoryMemory(journal=j)
            h.running(); h.finished(); h.declare(); h.close()
            j.receipt(); j.finalize(dict(transport='synthetic_memory_only'))
            self.assertTrue(j.machine.summary()['exploration']['windows'][0]['candidate'])
            proof = audit_v4(Path(tmp)/'new')['exploratory_eligibility']
            self.assertFalse(proof['identity_ok'] or proof['storage_ok'])
            self.assertFalse(proof['windows'][0]['eligible'])

    def test_gate_rows_are_excluded_by_recorded_read_and_byte_frontiers(self):
        h = self.completed(); s = h.m.summary()
        w = s['exploration']['windows'][0]
        for rx, receiver in w['receivers'].items():
            self.assertEqual(receiver['included_rows'], 149)
            self.assertTrue(all(r['first_read_index'] > w['frontier']['read_indices'][rx] and
                                r['byte_offset'] >= w['frontier']['byte_ends'][rx]
                                for r in receiver['included_line_references']))

    def test_revision_requires_explicit_compatible_plan_and_fixed_profile(self):
        self.assertEqual(STORAGE_POLICY, STORAGE)
        for revision in (None, '', 'v4-exploratory-2', 'ignore-preamble'):
            with self.assertRaises(ValueError):validate_plan(dict(plan(), eligibility_revision=revision))
        with self.assertRaises(ValueError):validate_plan(dict(plan(), line_policy_revision='v4-app-main-return-1'))
        with self.assertRaises(ValueError):PersistentPresenceV4(plan())
        p = plan(); del p['eligibility_revision']
        self.assertNotIn('exploration', make_v4_machine(p).summary())
        p = plan(); p['policy']['coverage_min_rows'] -= 1
        with self.assertRaises(ValueError):make_v4_machine(p)


class ExploratoryAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.baseline = Path(cls.temp.name)/'baseline'
        cls.report = generate_serial_bundle(cls.baseline)

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)/'copy'; shutil.copytree(self.baseline, self.root)

    def rewrite(self, name, value):
        (self.root/name).write_text(json.dumps(value)+'\n')
        manifest = json.loads((self.root/'manifest.json').read_text())
        for e in manifest['files']:
            p = self.root/e['path']; e.update(bytes=p.stat().st_size, sha256=digest(p))
        (self.root/'manifest.json').write_text(json.dumps(manifest)+'\n')

    def test_two_anomalous_startup_windows_certified_only_as_synthetic_exploration(self):
        report = audit_v4(self.root)
        self.assertTrue(report['integrity_ok'] and report['replay_ok'])
        self.assertFalse(report['state']['connection']['quality_ok'])
        self.assertTrue(all(not w['eligible'] for w in report['state']['windows']))
        proof = report['exploratory_eligibility']
        self.assertEqual(proof['evidence_type'], 'synthetic_fixture')
        self.assertTrue(proof['identity_ok'] and proof['storage_ok'])
        self.assertEqual(len(proof['windows']), 2)
        self.assertTrue(all(w['eligible'] for w in proof['windows']))
        for rx, pre in report['state']['exploration']['preamble']['receivers'].items():
            raw = (self.root/(rx.lower()+'.serial.log')).read_bytes()
            self.assertEqual(hashlib.sha256(raw[:pre['byte_end']]).hexdigest(), pre['sha256'])
            self.assertTrue(raw.startswith(PREFIX))

    def test_rehashed_preamble_offsets_or_hash_cannot_forge_traceability(self):
        original = json.loads((self.root/'summary.json').read_text())
        for key, value in (('byte_end', 1), ('sha256', '0'*64)):
            data = copy.deepcopy(original)
            data['state']['exploration']['preamble']['receivers']['RX-01'][key] = value
            self.rewrite('summary.json', data)
            with self.assertRaisesRegex(ValueError, 'Replayed summary differs'):audit_v4(self.root)

    def test_corrupted_raw_or_missing_revision_fails_audit(self):
        p = self.root/'rx-01.serial.log'; data = p.read_bytes(); p.write_bytes(b'X'+data[1:])
        with self.assertRaisesRegex(ValueError, 'integrity failure'):audit_v4(self.root)
        p.write_bytes(data)
        prov = json.loads((self.root/'provenance.json').read_text()); del prov['eligibility_revision']
        self.rewrite('provenance.json', prov)
        with self.assertRaisesRegex(ValueError, 'Eligibility provenance'):audit_v4(self.root)

    def test_identity_and_storage_evidence_are_required_even_with_valid_replay(self):
        original = json.loads((self.root/'provenance.json').read_text())
        for mutation in ('identity', 'storage'):
            data = copy.deepcopy(original)
            if mutation == 'identity':data['transport']['identities']['RX-01']['serial'] = 'wrong'
            else:del data['transport']['initial_free_bytes_observed']
            self.rewrite('provenance.json', data)
            result = audit_v4(self.root)['exploratory_eligibility']
            self.assertFalse(all(w['eligible'] for w in result['windows']))

    def test_rehashed_changed_clock_or_anomaly_reference_fails_replay(self):
        data = json.loads((self.root/'events.json').read_text())
        event = next(e for e in data if e['kind'] == 'line')
        event['evidence']['first_read_started_ns'] = str(int(event['evidence']['first_read_started_ns'])+1)
        self.rewrite('events.json', data)
        with self.assertRaisesRegex(ValueError, 'Replayed events differ'):audit_v4(self.root)

    def test_new_audit_cli_separates_results_and_refuses_historical_selection(self):
        from auditar_exploratorio_v4 import main
        out = io.StringIO()
        with contextlib.redirect_stdout(out), patch('serial.Serial', side_effect=AssertionError('No UART')):
            self.assertEqual(main(['--bundle', str(self.root)]), 0)
        result = json.loads(out.getvalue())
        self.assertFalse(result['connection']['quality_ok'])
        self.assertTrue(all(w['eligible'] for w in result['exploratory_eligibility']['windows']))
        self.assertFalse(result['physical_UART_opened'])
        p = json.loads((self.root/'plan.json').read_text()); del p['eligibility_revision']
        self.rewrite('plan.json', p)
        with self.assertRaisesRegex(ValueError, 'historical captures are not migrated'):
            main(['--bundle', str(self.root)])

    def test_missing_or_changed_source_provenance_is_rejected(self):
        p = json.loads((self.root/'provenance.json').read_text())
        item = next(s for s in p['sources'] if s['path'] == 'src/presence_v4_exploratory.py')
        item['sha256'] = '0'*64; self.rewrite('provenance.json', p)
        with self.assertRaisesRegex(ValueError, 'Exploratory source provenance'):audit_v4(self.root)


if __name__ == '__main__':unittest.main()
