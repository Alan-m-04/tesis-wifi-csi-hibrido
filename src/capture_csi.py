"""Capture RX-01 UART CSV without transforming raw CSI. Uses IDF pyserial."""
import argparse
import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path

FIELDS = 'type,id,mac,rssi,rate,sig_mode,mcs,bandwidth,smoothing,not_sounding,aggregation,stbc,fec_coding,sgi,noise_floor,ampdu_cnt,channel,secondary_channel,local_timestamp,ant,sig_len,rx_state,len,first_word_invalid,queue_drops,data'.split(',')


def parse_sample(line):
    row = next(csv.reader([line]))
    if len(row) != len(FIELDS) or row[0] != 'CSI_DATA':
        raise ValueError('wrong CSV fields')
    values = json.loads(row[-1])
    if not isinstance(values, list) or len(values) != int(row[-4]):
        raise ValueError('CSI length mismatch')
    if any(type(v) is not int or not -128 <= v <= 127 for v in values):
        raise ValueError('CSI bytes outside int8 range')
    return row


def main():
    import serial
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True)
    parser.add_argument('--seconds', type=float, default=60)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    raw_path = args.output.with_suffix('.serial.log')
    summary_path = args.output.with_suffix('.summary.json')
    count = malformed = 0
    first_id = last_id = first_ts = last_ts = drops = None
    id_gaps = 0
    started = datetime.now(timezone.utc).isoformat()
    # Exclusive files prevent overwriting an earlier experiment.
    with args.output.open('x', newline='') as out, raw_path.open('xb') as raw:
        writer = csv.writer(out)
        writer.writerow(['host_timestamp_utc', 'host_monotonic_ns'] + FIELDS)
        with serial.Serial(args.port, 115200, timeout=0.25, exclusive=True) as port:
            deadline = time.monotonic() + args.seconds
            pending = bytearray()
            try:
                while time.monotonic() < deadline:
                    chunk = port.read(port.in_waiting or 1)
                    if not chunk:
                        continue
                    raw.write(chunk)
                    raw.flush()
                    pending.extend(chunk)
                    while b'\n' in pending:
                        line, _, rest = pending.partition(b'\n')
                        pending = bytearray(rest)
                        line = line.decode('utf-8', errors='replace').strip()
                        if not line.startswith('CSI_DATA,'):
                            continue
                        try:
                            row = parse_sample(line)
                            sample_id = int(row[1])
                            ts = int(row[FIELDS.index('local_timestamp')])
                            drops = int(row[FIELDS.index('queue_drops')])
                        except (ValueError, TypeError, csv.Error, StopIteration):
                            malformed += 1
                            continue
                        if last_id is not None and sample_id > last_id + 1:
                            id_gaps += sample_id - last_id - 1
                        if first_id is None:
                            first_id, first_ts = sample_id, ts
                        last_id, last_ts = sample_id, ts
                        writer.writerow([datetime.now(timezone.utc).isoformat(), time.monotonic_ns()] + row)
                        out.flush()
                        count += 1
            except KeyboardInterrupt:
                pass
    summary = dict(started_utc=started, finished_utc=datetime.now(timezone.utc).isoformat(),
                   port=args.port, baud=115200, requested_seconds=args.seconds,
                   valid_rows=count, malformed_rows=malformed, first_id=first_id,
                   last_id=last_id, callback_id_gaps=id_gaps, last_queue_drops=drops,
                   first_device_timestamp=first_ts, last_device_timestamp=last_ts,
                   note='Callback IDs are local RX counts, not TX sequence numbers. These are not RF packet loss or one-way latency measurements.')
    with summary_path.open('x') as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
