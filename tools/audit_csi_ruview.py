#!/usr/bin/env python3
"""Read-only local CSI audit. Emits JSON on stdout; never opens devices or sockets."""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from csi_correspondence import idf_complex, documented_ht20_layout, amplitude_phase
from validate_capture import audit_capture, scan_raw
from capture_csi import FIELDS

ROOT = Path(__file__).resolve().parents[1]


def file_hash(p):
    with p.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def matrix_stats(rows, config):
    hist = {key:dict(Counter(r[key] for r in rows)) for key in
            ('len','sig_mode','bandwidth','secondary_channel','stbc','first_word_invalid',
             'mcs','ant','rate','channel','mac','rx_state','noise_floor','smoothing',
             'not_sounding','aggregation','sgi','fec_coding','sig_len','queue_drops')}
    host = Counter(r['host_monotonic_ns'] for r in rows)
    scalar_min, scalar_max, saturation, zero_pairs, valid_pairs, swapped_phase_changes = 127, -128, 0, 0, 0, 0
    model_rows = 0
    for row in rows:
        raw = json.loads(row['data'])
        if len(raw) != int(row['len']):
            raise ValueError('Byte count mismatch')
        z = idf_complex(raw, bool(int(row['first_word_invalid'])))
        scalar_min=min(scalar_min,min(raw)); scalar_max=max(scalar_max,max(raw))
        saturation += sum(v in (-128,127) for v in raw)
        for pair in z:
            if pair is None:
                continue
            valid_pairs += 1
            zero_pairs += pair == 0
            if pair != 0 and abs(amplitude_phase(pair)[1]-amplitude_phase(complex(pair.imag,pair.real))[1]) > 1e-12:
                swapped_phase_changes += 1
        try:
            documented_ht20_layout({k:int(row[k]) for k in ('len','sig_mode','bandwidth','secondary_channel','stbc')}, config)
            model_rows += 1
        except ValueError:
            pass
    timestamps = [int(r['local_timestamp']) for r in rows]
    deltas = [(b-a) % 2**32 for a,b in zip(timestamps,timestamps[1:])]
    return {'rows':len(rows),'metadata_histograms':hist,'scalar_min':scalar_min,'scalar_max':scalar_max,
            'saturated_scalars':saturation,'valid_complex_pairs':valid_pairs,'zero_pairs':zero_pairs,
            'pairs_whose_phase_changes_if_swapped':swapped_phase_changes,
            'rows_consistent_with_documented_HT20_model':model_rows,
            'model_does_not_certify_installed_firmware':True,
            'host_unique_timestamps':len(host),'shared_host_timestamp_groups':sum(n>1 for n in host.values()),
            'largest_host_timestamp_group':max(host.values(),default=0),
            'first_callback_id':int(rows[0]['id']),'last_callback_id':int(rows[-1]['id']),
            'first_device_timestamp_us':timestamps[0],'last_device_timestamp_us':timestamps[-1],
            'device_interval_us_min':min(deltas,default=None),'device_interval_us_max':max(deltas,default=None),
            'rssi_dbm_min':min(int(r['rssi']) for r in rows),'rssi_dbm_max':max(int(r['rssi']) for r in rows)}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--capture',type=Path,default=ROOT/'data/raw/dual-60s-20261024T205854Z/captura')
    ap.add_argument('--historical-uart', type=Path)
    ap.add_argument('--incomplete-log', type=Path)
    args=ap.parse_args()
    manifest=json.loads((ROOT/'data/dual_60s_20261024.manifest.json').read_text())
    original=audit_capture(args.capture,manifest)
    if not original['manifest_ok'] or not all(x['integrity_ok'] for x in original['receivers'].values()):
        raise ValueError('Historical reference integrity failed')
    config=json.loads((ROOT/'config/csi_esp32s3.json').read_text())['firmware_ltf_config']
    report={'schema':'tesis-csi-correspondence-audit-v1','operation':'offline','new_physical_capture':False,
            'strict_historical_result':original,'receivers':{}}
    for rx in ('RX-01','RX-02'):
        path=args.capture/(rx.lower()+'.csv')
        with path.open(newline='') as stream:
            report['receivers'][rx]=matrix_stats(list(csv.DictReader(stream)),config)
        report['receivers'][rx]['csv_sha256']=file_hash(path)
    report['other_historical_references']=[]
    candidates=[]
    if args.historical_uart:
        for rx,serial,expected in [('RX-01','5C93199744','481d8c3747f1a92ee367268193efdf80a9b3eeac84d89bcee50edb4f097709d4'),('RX-02','5C93200689','d237c1827c6c2629b70a63ebdcaec82a8a1b81b7d952eda0eadab906d21daec1')]:
            candidates.append((rx,args.historical_uart/('usb_'+serial+'.log'),'historical_15s_fragment',expected))
    if args.incomplete_log:
        candidates.append(('RX-02',args.incomplete_log,'experimental_incomplete_no_host_UART_chain','e6cd5c00747852bf39eaef24b2ef6a9ba3e8bf6644144f6ad81ec1aebb7c9ff1'))
    for rx,path,category,expected in candidates:
        digest=file_hash(path)
        if digest != expected:
            raise ValueError('Historical source hash mismatch: '+str(path))
        scan=scan_raw(path);records=[dict(zip(FIELDS,r)) for r in scan['rows']]
        report['other_historical_references'].append(dict(receiver=rx,path=str(path),sha256=digest,
            category=category,complete_valid_rows=len(records),counts=scan['counts'],trailing_bytes=scan['trailing_bytes'],
            metadata_histograms={k:dict(Counter(r[k] for r in records)) for k in ('len','sig_mode','bandwidth','secondary_channel','stbc','first_word_invalid','channel','mac','mcs','ant')},
            host_timestamps_available=False,merged_into_dual_capture=False))
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
