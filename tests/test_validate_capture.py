"""Synthetic contract/mutation tests. No physical UART or experimental fixtures."""
import csv
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import capture_csi_multi as capture
import validate_capture as audit
from test_capture_csi_multi import sample

ROOT = Path(__file__).resolve().parents[1]


def frame(ident=0, timestamp=100000, **changes):
    return sample(ident, timestamp, sig_mode='1', len='256', data=json.dumps([3, 4] * 128), **changes)


def fixture(parent, streams=None):
    streams = streams or {rx: b''.join(frame(i, 100000+i*200000) for i in range(3)) for rx in capture.RECEIVERS}
    ports = {rx: 'SYNTHETIC-'+rx for rx in streams}
    class MemoryPort:
        def __init__(self, **kw): self.port=None; self.pending=b''; self.dtr=None; self.rts=None
        def open(self): self.pending=streams[next(rx for rx, p in ports.items() if p==self.port)]
        def close(self): pass
        @property
        def in_waiting(self): return len(self.pending)
        def read(self, size):
            data=self.pending[:size];self.pending=self.pending[size:]
            if not data: time.sleep(.0005)
            return data
    folder=parent/'synthetic'
    args=['capture_csi_multi.py','--seconds','0.03','--output-dir',str(folder)]
    with patch('sys.argv',args), patch.object(capture,'resolve_ports',return_value=ports), \
         patch.object(capture,'verify_port',side_effect=lambda rx,p:p), \
         patch('serial.Serial',MemoryPort), redirect_stdout(io.StringIO()):
        capture.main()
    session=json.loads((folder/'session.json').read_text())
    session['evidence_type']='synthetic_fixture'
    (folder/'session.json').write_text(json.dumps(session))
    return folder


def repin_csv(folder, rx):
    p=folder/(rx.lower()+'.summary.json');s=json.loads(p.read_text())
    s['csv_sha256']=audit.sha(folder/(rx.lower()+'.csv'));p.write_text(json.dumps(s))
    p=folder/'session.json';session=json.loads(p.read_text());session['results'][rx]=s;p.write_text(json.dumps(session))


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.parent=Path(self.tmp.name)
    def run_fixture(self, streams=None):return fixture(self.parent,streams)
    def test_valid_roundtrip_preserves_all_fields(self):
        r=audit.audit_capture(self.run_fixture());self.assertTrue(r['quality_ok']);self.assertFalse(r['new_physical_capture'])
        self.assertTrue(all(x['raw_frames_equal_csv'] for x in r['receivers'].values()))
    def test_startup_malformed_line_is_not_silenced(self):
        f=self.run_fixture({'RX-01':b'CSI_DATA,broken\n'+frame(), 'RX-02':frame()})
        r=audit.audit_capture(f);self.assertFalse(r['quality_ok']);self.assertEqual(r['receivers']['RX-01']['counts']['malformed_rows'],1)
    def test_unterminated_tail_is_preserved_not_a_sample(self):
        f=self.run_fixture({'RX-01':frame()+b'CSI_DATA,partial','RX-02':frame()})
        r=audit.audit_capture(f);self.assertEqual(r['receivers']['RX-01']['valid_rows'],1)
        self.assertEqual(r['receivers']['RX-01']['trailing_bytes'],len(b'CSI_DATA,partial'))
    def test_wrong_source_remains_rejected(self):
        r=audit.audit_capture(self.run_fixture({'RX-01':frame(mac='00:00:00:00:00:00'),'RX-02':frame()}))
        self.assertFalse(r['quality_ok']);self.assertEqual(r['receivers']['RX-01']['counts']['unexpected_source_rows'],1)
    def test_wrong_channel_remains_rejected(self):
        r=audit.audit_capture(self.run_fixture({'RX-01':frame(channel='6'),'RX-02':frame()}))
        self.assertFalse(r['quality_ok']);self.assertEqual(r['receivers']['RX-01']['counts']['unexpected_metadata_rows'],1)
    def test_invalid_matrix_bool_and_range_are_rejected(self):
        for value in ('true','128'):
            with self.subTest(value=value):
                # Separate temporary roots keep independent exclusive capture outputs.
                root=self.parent/value;root.mkdir()
                data=frame().replace(b'[3, 4', ('['+value+', 4').encode(),1)
                r=audit.audit_capture(fixture(root,{'RX-01':data,'RX-02':frame()}));self.assertFalse(r['quality_ok'])
    def test_raw_tamper_is_detected(self):
        f=self.run_fixture();p=f/'rx-01.serial.log';p.write_bytes(p.read_bytes().replace(b'CSI_DATA,0,',b'CSI_DATA,8,',1))
        r=audit.audit_capture(f);self.assertFalse(r['receivers']['RX-01']['integrity_ok'])
    def test_forged_usb_identity_even_with_updated_hash_is_rejected(self):
        f=self.run_fixture();p=f/'rx-01.csv';p.write_text(p.read_text().replace(capture.RECEIVERS['RX-01'],'WRONG'))
        repin_csv(f,'RX-01');self.assertFalse(audit.audit_capture(f)['receivers']['RX-01']['integrity_ok'])
    def test_csv_csi_change_even_with_updated_hash_is_rejected(self):
        f=self.run_fixture();p=f/'rx-01.csv';s=p.read_text();p.write_text(s.replace(',-50,',',-51,',1))
        repin_csv(f,'RX-01');self.assertFalse(audit.audit_capture(f)['receivers']['RX-01']['raw_frames_equal_csv'])
    def test_duplicate_callback_ids_are_reported(self):
        r=audit.audit_capture(self.run_fixture({'RX-01':frame()+frame(),'RX-02':frame()}))
        self.assertFalse(r['quality_ok']);self.assertEqual(r['receivers']['RX-01']['counts']['nonincreasing_ids'],1)
    def test_callback_gap_is_not_called_RF_loss(self):
        r=audit.audit_capture(self.run_fixture({'RX-01':frame()+frame(2,500000),'RX-02':frame()}))
        x=r['receivers']['RX-01'];self.assertEqual(x['counts']['callback_id_gaps'],1)
        self.assertTrue(x['collector_quality_recomputed']);self.assertFalse(x['additional_checks_ok'])
    def test_uint32_device_wrap_is_preserved(self):
        r=audit.audit_capture(self.run_fixture({'RX-01':frame(0,2**32-100000)+frame(1,100000),'RX-02':frame()}))
        self.assertTrue(r['quality_ok']);self.assertEqual(r['receivers']['RX-01']['counts']['device_clock_wraps'],1)
    def test_midstream_reset_is_an_additional_failure(self):
        r=audit.audit_capture(self.run_fixture({'RX-01':frame()+b'rst:0x1 (POWERON)\n'+frame(1,300000),'RX-02':frame()}))
        self.assertFalse(r['quality_ok']);self.assertEqual(r['receivers']['RX-01']['midstream_boot_markers'],1)
    def test_forged_host_timestamp_outside_gate_is_rejected(self):
        f=self.run_fixture();session=json.loads((f/'session.json').read_text())
        p=f/'rx-01.csv'
        with p.open(newline='') as stream:
            reader=csv.DictReader(stream);names=reader.fieldnames;rows=list(reader)
        rows[-1]['host_monotonic_ns']=str(session['capture_deadline_monotonic_ns']+1)
        with p.open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=names);writer.writeheader();writer.writerows(rows)
        repin_csv(f,'RX-01');r=audit.audit_capture(f)
        self.assertFalse(r['quality_ok']);self.assertFalse(r['receivers']['RX-01']['host_frames_inside_requested_gate'])
    def test_timezone_missing_from_host_UTC_is_rejected(self):
        f=self.run_fixture();p=f/'rx-01.csv';p.write_text(p.read_text().replace('+00:00',''))
        repin_csv(f,'RX-01');self.assertFalse(audit.audit_capture(f)['receivers']['RX-01']['integrity_ok'])
    def test_wrong_csv_header_is_an_input_error(self):
        f=self.run_fixture();(f/'rx-01.csv').write_text('unexpected,header\n')
        with self.assertRaises(ValueError):audit.audit_capture(f)
    def test_manifest_traversal_is_rejected(self):
        f=self.run_fixture()
        with self.assertRaises(ValueError):audit.audit_capture(f,{'files':[{'name':'../outside','sha256':'0'*64,'bytes':1}]})
    def test_offline_validation_never_opens_UART(self):
        f=self.run_fixture()
        with patch('serial.Serial',side_effect=AssertionError('No UART')) as opened, patch.object(capture,'port_identity',side_effect=AssertionError('No discovery')):
            self.assertTrue(audit.audit_capture(f)['quality_ok']);opened.assert_not_called()
    def test_audit_does_not_modify_inputs(self):
        f=self.run_fixture();before={p.name:audit.sha(p)for p in f.iterdir()};audit.audit_capture(f)
        self.assertEqual(before,{p.name:audit.sha(p)for p in f.iterdir()})
    def test_cli_returns_one_for_rejected_quality(self):
        f=self.run_fixture({'RX-01':b'CSI_DATA,bad\n'+frame(),'RX-02':frame()})
        p=subprocess.run([sys.executable,'-B',str(ROOT/'src/validate_capture.py'),str(f)],capture_output=True,text=True)
        self.assertEqual(p.returncode,1);self.assertFalse(json.loads(p.stdout)['quality_ok'])


if __name__=='__main__':unittest.main()
