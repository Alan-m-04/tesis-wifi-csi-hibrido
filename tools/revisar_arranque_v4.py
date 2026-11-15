#!/usr/bin/env python3
"""Inspect existing regular log files only; no transport or detector imports."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from availability_window import LineFramer

LOG_DIRECTORIES = (
    'data/raw/dual-60s-20261024T205854Z/captura',
    'results/local/captura-dual-30s-post-reinicio-20261025-intento01/capture',
    'results/local/captura-dual-v2-30s-20261025-intento01/capture',
    'results/local/preparacion-dual-v3-20261026T000758Z/'
    'captura-dual-v3-20261026T000758Z-intento-unico/capture',
    'results/local/preparacion-dual-v3-movimiento-libre-20261026T035823Z/'
    'captura-dual-v3-movimiento-libre-20261026T035823Z-intento-unico/capture',
    'results/local/v4-c01-vacia-sentado-20261028T014057Z',
)


def inspect_log(path, receiver):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Existing regular log file required')
    raw = path.read_bytes()
    framer = LineFramer(receiver)
    # Synthetic zero clocks are used ONLY to reuse byte framing. The report
    # does not claim they are timestamps from acquisition.
    lines = framer.feed(raw, 0, dict(started_ns='0', returned_ns='0'))
    ready = next((l['line_1based'] for l in lines if l['kind'] == 'ready'), None)
    first_csi = next((l['line_1based'] for l in lines if l['kind'] == 'row'), None)
    selected = [l for l in lines if (first_csi is None or l['line_1based'] < first_csi) or
                (ready is not None and l['line_1based'] > ready and l['kind'] != 'row')]
    evidence = []
    for line in selected:
        item = {k: line[k] for k in ('kind', 'line_1based', 'byte_offset', 'byte_end',
                                     'byte_length', 'line_sha256')}
        item.update({k: line[k] for k in ('reason', 'fatal_if_ready') if k in line})
        data = raw[line['byte_offset']:line['byte_end']]
        item.update(raw_hex=data.hex(), raw_repr=repr(data))
        evidence.append(item)
    invalid = [l for l in lines if l['kind'] == 'invalid' and
               (ready is None or l['line_1based'] < ready)]
    return dict(receiver=receiver, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
                complete_lines=len(lines), ready_line=ready, first_csi_line=first_csi,
                initial_invalid_lines=len(invalid), selected_lines=evidence,
                tail=dict(byte_offset=framer.offset-framer.length, bytes=framer.length,
                          sha256=framer.hash.hexdigest(), raw_hex=raw[len(raw)-framer.length:].hex()
                          if framer.length else ''))


def inspect_existing(root=ROOT):
    logs, missing = [], []
    for relative in LOG_DIRECTORIES:
        for rx in ('RX-01', 'RX-02'):
            name = str(Path(relative)/(rx.lower()+'.serial.log'))
            if not (root/name).is_file():
                missing.append(name)
                continue
            logs.append(dict(path=name, **inspect_log(root/name, rx)))
    return dict(schema='tesis-startup-log-inspection-v1', evidence_type='existing_recorded_bytes',
                acquisition_times_reconstructed=False, transports_opened=False,
                logs=logs, missing=missing)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-new', type=Path)
    args = parser.parse_args(argv)
    result = inspect_existing()
    data = json.dumps(result, ensure_ascii=False, indent=2)+'\n'
    if args.output_new:
        with args.output_new.open('x') as stream:
            stream.write(data)
    else:
        print(data, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
