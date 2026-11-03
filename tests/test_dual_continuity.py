"""Only process-owned PTY transport; accelerated time is synthetic evidence."""
import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'tools')]
import dual_continuity as dc
from diagnostico_continuidad_dual import main
from test_uart_v4 import Rig
from campana_presencia_v4 import fixture_row


def plan():
    return json.loads((ROOT/'config/continuidad_dual_60s_r1.review.json').read_text())


class ContinuityTests(unittest.TestCase):
    def setUp(self):
        self.rig = Rig()
        self.addCleanup(self.rig.finish_fixture)
        # Contract stays exactly 60 logical seconds; physical code has no clock override.
        self.origin = time.monotonic_ns()
        self.clock_patch = patch.object(dc, 'clocks', side_effect=self.clocks)
        self.clock_patch.start(); self.addCleanup(self.clock_patch.stop)
        self.mono_patch = patch.object(dc.time, 'monotonic_ns', side_effect=self.mono)
        self.mono_patch.start(); self.addCleanup(self.mono_patch.stop)

    # Capture real function before patching the shared time module.
    real_mono = staticmethod(time.monotonic_ns)

    def mono(self):
        return (self.real_mono()-self.origin)*100

    def clocks(self):
        now = self.mono()
        return dict(monotonic_ns=now, boottime_ns=now+7_000_000, realtime_ns=now+2_000_000_000)

    def session(self):
        s = dc.ContinuitySession(self.rig.output, plan(), test_backend=self.rig.backend)
        self.addCleanup(s.finish)
        return s

    def wait(self, predicate, limit=1.5):
        deadline = self.real_mono()+int(limit*1e9)
        while self.real_mono() < deadline:
            if predicate(): return
            time.sleep(.003)
        self.fail('Synthetic fixture condition did not occur')

    def test_silence_recovery_nominal_duration_and_no_approval(self):
        s = self.session()
        time.sleep(.03)  # >1 logical second, both readers continue
        for pair in self.rig.pairs.values(): pair.fixture_write(fixture_row(0, 100_000))
        self.wait(lambda: all(n >= 1 for n in s.reads.values()))
        for pair in self.rig.pairs.values(): pair.fixture_write(fixture_row(1, 300_000))
        result = s.run(); report = result['report']
        self.assertTrue(result['integrity_ok']); self.assertTrue(result['replay_ok'])
        self.assertTrue(report['completed_nominal_duration'])
        self.assertTrue(report['both_ports_closed_confirmed'])
        self.assertFalse(report['quality_approval']); self.assertEqual(report['eligible_windows'], [])
        self.assertFalse(any(report['permitted_uses'].values()))
        for state in report['receivers'].values():
            self.assertEqual(len(state['rows']), 2)
            self.assertTrue(any(i['recovered_ns'] is not None for i in state['incidents']))
            self.assertEqual(state['callback_transitions'][0]['callback_id_delta'], 1)
        self.assertEqual([o.protocol_closes for o in self.rig.objects], [1, 1])
        self.assertTrue(all(e.open_attempts == 1 for e in s.endpoints.values()))
        self.assertTrue(all(e.serial.open_flush_suppressed == 1 for e in s.endpoints.values()))

    def test_partial_without_lf_does_not_recover_and_tail_preserved(self):
        s = self.session()
        fragment = fixture_row(0, 100_000)[:-1]
        for pair in self.rig.pairs.values(): pair.fixture_write(fragment[:100])
        self.wait(lambda: all(n >= 1 for n in s.reads.values()))
        time.sleep(.025)
        for pair in self.rig.pairs.values(): pair.fixture_write(fragment[100:])
        self.wait(lambda: all(n >= 2 for n in s.reads.values()))
        report = s.finish()['report']
        for rx, state in report['receivers'].items():
            self.assertFalse(state['rows']); self.assertFalse(state['lines'])
            self.assertIsNone(state['incidents'][0]['recovered_ns'])
            self.assertEqual(state['tail']['byte_length'], len(fragment))
            self.assertEqual(state['tail']['first_read']['first_read_index'], 0)
            self.assertEqual(state['tail']['last_read_index'], 1)
            self.assertEqual((self.rig.output/(rx.lower()+'.serial.log')).read_bytes(), fragment)

    def test_one_rx_transport_failure_stops_and_closes_both(self):
        s = self.session()
        import os
        pair = self.rig.pairs['RX-01']
        os.close(pair.master); pair.master_fd_open = False
        self.wait(s.stop.is_set)
        result = s.run(); r = result['report']
        self.assertIsNotNone(r['fatal']); self.assertFalse(r['completed_nominal_duration'])
        self.assertTrue(r['both_ports_closed_confirmed'])
        self.assertEqual([o.protocol_closes for o in self.rig.objects], [1, 1])
        self.assertTrue(all(not o.is_open and o.fd is None for o in self.rig.objects))
        self.assertEqual(s.finish(), result)  # No close retry

    def test_observed_firmware_anomalies_never_accepted_or_hidden(self):
        s = self.session()
        data = (b'\xffunknown\nESP-ROM:synthetic\nE (1) csi_recv: synthetic error\n'+
                fixture_row(5, 1_000_000)+fixture_row(2, 500_000)+fixture_row(9, 700_000))
        for pair in self.rig.pairs.values(): pair.fixture_write(data)
        self.wait(lambda: all(n for n in s.reads.values()))
        r = s.finish()['report']
        for state in r['receivers'].values():
            self.assertEqual([x['kind'] for x in state['lines'][:3]], ['invalid', 'reset', 'error'])
            self.assertTrue(state['callback_transitions'][0]['callback_restart'])
            self.assertTrue(state['callback_transitions'][0]['local_discontinuity'])
            self.assertTrue(state['callback_transitions'][1]['callback_gap'])
        self.assertFalse(r['quality_approval'])

    def test_altered_traceability_rejected_even_with_rehashed_manifest(self):
        s = self.session()
        for pair in self.rig.pairs.values(): pair.fixture_write(fixture_row(0, 100_000))
        self.wait(lambda: all(n for n in s.reads.values()))
        s.finish()
        path = self.rig.output/'ledger.jsonl'
        events = [json.loads(x) for x in path.read_text().splitlines()]
        next(x for x in events if x['kind']=='read')['lines'][0]['byte_offset'] += 1
        path.write_text(''.join(json.dumps(x)+'\n' for x in events))
        manifest = json.loads((self.rig.output/'manifest.json').read_text())
        manifest['ledger.jsonl'] = dc.digest(path)
        (self.rig.output/'manifest.json').write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'references'): dc.audit(self.rig.output)

    def test_storage_failure_stops_both_and_retains_bytes(self):
        s = self.session()
        self.rig.free = 0
        self.wait(s.stop.is_set)
        result = s.run()
        self.assertFalse(result['integrity_ok'])
        self.assertEqual([o.protocol_closes for o in self.rig.objects], [1, 1])
        self.assertTrue((self.rig.output/'finalization-failure.json').exists())

    def test_default_cli_and_metadata_preflight_never_construct_serial(self):
        with patch('serial.Serial', side_effect=AssertionError('No UART')), contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(main([]), 0)
        self.assertFalse(json.loads(out.getvalue())['physical_UART_opened'])
        with patch.object(dc.transport.capture, 'resolve_ports', return_value={
                rx: d['resolved'] for rx, d in self.rig.identities.items()}), \
             patch.object(dc.transport, 'identity', side_effect=lambda rx:self.rig.identities[rx]), \
             patch('serial.Serial', side_effect=AssertionError('No UART')):
            self.assertEqual(dc.preflight(plan()), self.rig.identities)

    def test_fixed_policy_and_pending_authorization_gate(self):
        p = plan()
        with self.assertRaises(ValueError): dc.validate_plan(p, execution=True)
        for key in ('duration_ns', 'incident_ns', 'read_bytes'):
            changed = copy.deepcopy(p); changed['policy'][key] += 1
            with self.assertRaises(ValueError): dc.validate_plan(changed)
        changed = copy.deepcopy(p); changed['slots'] = []
        with self.assertRaises(ValueError): dc.validate_plan(changed)
        for key in p['declarations']: p['declarations'][key] = 'current declaration'
        with patch('serial.Serial', side_effect=AssertionError('No UART')):
            with self.assertRaises(ValueError): dc.ContinuitySession(self.rig.output, p)

    def test_second_open_failure_closes_both_once_preserving_first(self):
        r = Rig('second_open_slow'); self.addCleanup(r.finish_fixture)
        r.initial_bytes()
        with self.assertRaisesRegex(OSError, 'second open'):
            dc.ContinuitySession(r.output, plan(), test_backend=r.backend)
        self.assertTrue((r.output/'rx-01.serial.log').read_bytes())
        self.assertEqual([o.protocol_closes for o in r.objects], [1, 1])

    def test_profile_wrong_is_not_a_row_and_drop_changes_remain_visible(self):
        s = self.session()
        import csv
        import capture_csi_multi as capture
        fields = next(csv.reader([fixture_row(2, 400_000).decode().strip()]))
        fields[capture.FIELDS.index('queue_drops')] = '3'
        altered = io.StringIO(); csv.writer(altered, lineterminator='\n').writerow(fields)
        bad_fields = fields.copy(); bad_fields[capture.FIELDS.index('channel')] = '6'
        bad = io.StringIO(); csv.writer(bad, lineterminator='\n').writerow(bad_fields)
        data = fixture_row(1, 200_000)+bad.getvalue().encode()+altered.getvalue().encode()
        for pair in self.rig.pairs.values(): pair.fixture_write(data)
        self.wait(lambda: all(n for n in s.reads.values()))
        report = s.finish()['report']
        for state in report['receivers'].values():
            self.assertEqual(len(state['rows']), 2)
            self.assertEqual(state['lines'][1]['reason'], 'csi_format_or_profile')
            self.assertEqual(state['callback_transitions'][0]['queue_drops_delta'], 3)

    def test_fragment_completed_after_silence_has_both_read_references(self):
        s = self.session()
        line = fixture_row(0, 10_000)
        for pair in self.rig.pairs.values(): pair.fixture_write(line[:-1])
        self.wait(lambda: all(n for n in s.reads.values()))
        time.sleep(.025)
        for pair in self.rig.pairs.values(): pair.fixture_write(b'\ntrailing')
        self.wait(lambda: all(n >= 2 for n in s.reads.values()))
        report = s.finish()['report']
        for state in report['receivers'].values():
            row = state['rows'][0]
            self.assertEqual((row['first_read_index'], row['last_read_index']), (0, 1))
            self.assertEqual(state['tail']['byte_length'], len(b'trailing'))
            self.assertIsNotNone(state['incidents'][0]['recovered_ns'])

    def test_identity_failure_no_second_open_or_retry(self):
        r = Rig('identity_changed'); self.addCleanup(r.finish_fixture)
        with self.assertRaisesRegex(ValueError, 'identity changed'):
            dc.ContinuitySession(r.output, plan(), test_backend=r.backend)
        self.assertEqual(len([x for x in r.calls if x[0]=='open']), 1)
        report = dc.audit(r.output)['report']
        self.assertEqual([x['details']['close_attempts'] for x in report['closure'].values()], [1, 1])
        self.assertTrue(report['both_ports_closed_confirmed'])

    def test_failed_close_does_not_prevent_other_close_or_claim_confirmation(self):
        r = Rig('close_error'); self.addCleanup(r.finish_fixture)
        s = dc.ContinuitySession(r.output, plan(), test_backend=r.backend)
        report = s.finish()['report']
        self.assertFalse(report['both_ports_closed_confirmed'])
        self.assertEqual([o.protocol_closes for o in r.objects], [1, 1])
        self.assertFalse(report['closure']['RX-01']['confirmed'])
        self.assertTrue(report['closure']['RX-02']['confirmed'])

    def test_raw_tampering_and_output_reuse_rejected(self):
        s = self.session()
        s.finish()
        with (self.rig.output/'rx-01.serial.log').open('ab') as f: f.write(b'changed')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'): dc.audit(self.rig.output)
        with self.assertRaises(FileExistsError):
            dc.ContinuitySession(self.rig.output, plan(), test_backend=self.rig.backend)
        self.assertEqual(len([x for x in self.rig.calls if x[0]=='open']), 2)

    def test_identity_provenance_alteration_detected_after_rehash(self):
        s = self.session(); s.finish()
        path = self.rig.output/'metadata.json'
        data = json.loads(path.read_text()); data['identities']['RX-01']['serial'] = 'wrong'
        path.write_text(json.dumps(data))
        manifest = json.loads((self.rig.output/'manifest.json').read_text())
        manifest['metadata.json'] = dc.digest(path)
        (self.rig.output/'manifest.json').write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'Identity provenance'): dc.audit(self.rig.output)

    def test_partial_storage_write_fails_integrity_and_closes_both(self):
        s = self.session()
        def failed_read(rx, chunk, started, returned):
            f = s.journal.raw[rx]; f.write(chunk[:10]); f.flush()
            raise OSError('Synthetic disk write failure')
        with patch.object(s.journal, 'read', side_effect=failed_read):
            self.rig.pairs['RX-01'].fixture_write(fixture_row(0, 100_000))
            self.wait(s.stop.is_set)
            result = s.run()
        self.assertFalse(result['integrity_ok'])
        self.assertIn('disk write', result['fatal'])
        self.assertEqual((self.rig.output/'rx-01.serial.log').stat().st_size, 10)
        self.assertTrue(all(x['confirmed'] for x in result['closure'].values()))


if __name__ == '__main__': unittest.main()
