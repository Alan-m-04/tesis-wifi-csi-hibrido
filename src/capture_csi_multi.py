"""Capture one or both identified CSI receivers, with a shared host clock."""
import argparse
import csv
import hashlib
import json
import math
import re
import subprocess
import threading
import time
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path

from capture_csi import FIELDS, parse_sample
from preserving_serial import preserving_serial_type

RECEIVERS = {
    'RX-01': '5C93199744',
    'RX-02': '5C93200689',
}
USB_BY_ID = Path('/dev/serial/by-id')
SERIAL_DEVICE_DIR = Path('/dev')
EXTRA_FIELDS = ['session_id', 'receiver_id', 'usb_serial',
                'host_timestamp_utc', 'host_monotonic_ns']
SOURCE = '1a:00:00:00:00:00'
ANSI = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')
ERROR = re.compile(r'ESP_ERROR_CHECK failed|Guru Meditation|abort\(\)|panic|'
                   r'watchdog|^E \(', re.IGNORECASE)
NOTE = ('Device clocks and callback IDs are independent per receiver. Host times '
        'mark serial reads, not RF arrival; buffering and scheduling add delay. '
        'These statistics do not measure RF packet loss or one-way latency.')


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def port_identity(port):
    """Read udev properties without opening or resetting the UART."""
    try:
        resolved = str(Path(port).resolve(strict=True))
        if not Path(resolved).is_char_device():
            raise ValueError(f'not a character device: {port}')
        result = subprocess.run(['udevadm', 'info', '--query=property', '--name', resolved],
                                check=True, capture_output=True, text=True)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError(f'cannot read USB identity for {port}: {exc}') from exc
    properties = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
    return resolved, properties


def require_identity(receiver, port, properties):
    expected = RECEIVERS[receiver]
    if (properties.get('ID_SERIAL_SHORT') != expected
            or properties.get('ID_VENDOR_ID') != '1a86'
            or properties.get('ID_BUS') != 'usb'):
        raise ValueError(
            f'{receiver}: USB identity mismatch at {port}; expected serial {expected}, '
            f'VID 1a86, bus usb; found serial {properties.get("ID_SERIAL_SHORT", "<missing>")}, '
            f'VID {properties.get("ID_VENDOR_ID", "<missing>")}, '
            f'bus {properties.get("ID_BUS", "<missing>")}')


def verify_port(receiver, port):
    resolved, properties = port_identity(port)
    require_identity(receiver, port, properties)
    return resolved


def resolve_ports(receivers, overrides):
    """Find unique USB serials, preferring by-id links over numbered devices.

    Also inspect numbered devices to detect duplicate serials even if udev's
    single by-id link hides one of them. Aliases of one device are counted once.
    Explicit CLI paths remain supported, but cannot bypass identity checks.
    """
    explicit_ports = {rx: verify_port(rx, overrides[rx])
                      for rx in receivers if overrides.get(rx)}
    candidates = sorted(USB_BY_ID.glob('*'))
    for pattern in ('ttyACM*', 'ttyUSB*'):
        candidates.extend(sorted(SERIAL_DEVICE_DIR.glob(pattern)))
    candidates.extend(Path(overrides[rx]) for rx in receivers if overrides.get(rx))
    matches = {rx: set() for rx in receivers}
    identities = {}
    for candidate in candidates:
        resolved = str(candidate.resolve(strict=False))
        if resolved not in identities:
            resolved, properties = port_identity(candidate)
            identities[resolved] = properties
        properties = identities[resolved]
        for receiver in receivers:
            expected = RECEIVERS[receiver]
            # A persistent link claiming this serial must agree with udev.
            if expected in candidate.name or properties.get('ID_SERIAL_SHORT') == expected:
                require_identity(receiver, candidate, properties)
                matches[receiver].add(resolved)
    verified = {}
    for receiver in receivers:
        devices = matches[receiver]
        expected = RECEIVERS[receiver]
        if not devices:
            raise ValueError(f'{receiver}: USB receiver not found; expected serial {expected} '
                             f'in {USB_BY_ID} or {SERIAL_DEVICE_DIR}/ttyACM*, ttyUSB*')
        if len(devices) > 1:
            raise ValueError(f'{receiver}: duplicate USB serial {expected}; devices: '
                             + ', '.join(sorted(devices)))
        verified[receiver] = next(iter(devices))
        if receiver in explicit_ports:
            if explicit_ports[receiver] != verified[receiver]:
                raise ValueError(f'{receiver}: USB device changed during discovery')
    if len(set(verified.values())) != len(verified):
        raise ValueError('receivers must use different devices')
    return verified


def validate_sample(line):
    row = parse_sample(line)
    record = dict(zip(FIELDS, row))
    numeric = {key: int(value) for key, value in record.items()
               if key not in ('type', 'mac', 'data')}
    if not (0 <= numeric['id'] < 2**32
            and 0 <= numeric['local_timestamp'] < 2**32
            and 0 <= numeric['queue_drops'] < 2**32
            and 0 < numeric['len'] <= 1024 and numeric['len'] % 2 == 0
            and numeric['first_word_invalid'] in (0, 1)):
        raise ValueError('invalid CSI metadata')
    return row, record, numeric


def capture_receiver(port, receiver, directory, session_id, gate, stop, timing):
    summary = dict(session_id=session_id, receiver_id=receiver, usb_serial=RECEIVERS[receiver],
                   port=port.port, baud=115200, requested_seconds=timing['seconds'],
                   valid_rows=0, malformed_rows=0, unexpected_source_rows=0,
                   unexpected_metadata_rows=0, callback_id_gaps=0,
                   nonincreasing_ids=0, device_clock_wraps=0,
                   device_time_discontinuities=0, queue_drop_increment=0,
                   queue_counter_decreases=0, first_queue_drops=None,
                   last_queue_drops=None, first_id=None, last_id=None,
                   first_device_timestamp=None, last_device_timestamp=None,
                   first_host_monotonic_ns=None, last_host_monotonic_ns=None,
                   rssi_min=None, rssi_max=None, ready_seen=False,
                   boot_error_lines=[], boot_error_count=0,
                   oversized_lines=0, trailing_bytes=0, bytes_received=0,
                   error=None, note=NOTE)
    csv_path = directory / f'{receiver.lower()}.csv'
    raw_path = directory / f'{receiver.lower()}.serial.log'
    summary_path = directory / f'{receiver.lower()}.summary.json'
    pending = bytearray()
    dropping_line = False
    tail_length = 0
    immediate = timing.get('read_from_open', False)
    if not immediate:
        gate.wait()
    summary['started_utc'] = utc_now()
    summary['started_monotonic_ns'] = time.monotonic_ns()
    try:
        with csv_path.open('x', newline='') as output, raw_path.open('xb') as raw, ExitStack() as auxiliaries:
            writer = csv.writer(output)
            writer.writerow(EXTRA_FIELDS + FIELDS)
            reads = (auxiliaries.enter_context((directory / f'{receiver.lower()}.reads.jsonl').open('x'))
                     if timing.get('record_reads') else None)
            if timing.get('reader_started'):
                timing['reader_started'][receiver].set()
            while not stop.is_set() and (timing.get('deadline_ns') is None or time.monotonic_ns() < timing['deadline_ns']):
                read_started_ns = time.monotonic_ns()
                chunk = port.read(min(port.in_waiting or 1, 16384))
                host_ns, host_utc = time.monotonic_ns(), utc_now()
                if not chunk:
                    continue
                raw.write(chunk)
                raw.flush()
                offset = summary['bytes_received']
                summary['bytes_received'] += len(chunk)
                if reads is not None:
                    reads.write(json.dumps(dict(offset=offset, size=len(chunk), started_ns=str(read_started_ns),
                                                returned_ns=str(host_ns), host_timestamp_utc=host_utc))+'\n')
                    reads.flush()
                tail_length = len(chunk.rsplit(b'\n', 1)[-1]) if b'\n' in chunk else tail_length + len(chunk)
                pending.extend(chunk)
                while b'\n' in pending:
                    line, _, rest = pending.partition(b'\n')
                    pending = bytearray(rest)
                    if dropping_line or len(line) > 65536:
                        if not dropping_line:
                            summary['oversized_lines'] += 1
                        dropping_line = False
                        continue
                    text = ANSI.sub('', line.decode('utf-8', errors='replace')).strip()
                    if f'{receiver} READY' in text:
                        summary['ready_seen'] = True
                    if ERROR.search(text):
                        summary['boot_error_count'] += 1
                        if len(summary['boot_error_lines']) < 10:
                            summary['boot_error_lines'].append(text)
                    if not text.startswith('CSI_DATA,'):
                        continue
                    try:
                        row, record, numeric = validate_sample(text)
                    except (ValueError, TypeError, csv.Error, StopIteration):
                        summary['malformed_rows'] += 1
                        continue
                    if record['mac'].lower() != SOURCE:
                        summary['unexpected_source_rows'] += 1
                        continue
                    if (numeric['channel'], numeric['bandwidth'], numeric['rx_state']) != (11, 0, 0):
                        summary['unexpected_metadata_rows'] += 1
                        continue
                    ident, timestamp, drops = (numeric[k] for k in ('id', 'local_timestamp', 'queue_drops'))
                    if summary['last_id'] is not None:
                        if ident <= summary['last_id']:
                            summary['nonincreasing_ids'] += 1
                        else:
                            summary['callback_id_gaps'] += max(0, ident - summary['last_id'] - 1)
                            previous_ts = summary['last_device_timestamp']
                            delta = (timestamp - previous_ts) % 2**32
                            if delta == 0 or delta > 10_000_000:
                                summary['device_time_discontinuities'] += 1
                            elif timestamp < previous_ts:
                                summary['device_clock_wraps'] += 1
                        difference = drops - summary['last_queue_drops']
                        if difference < 0:
                            summary['queue_counter_decreases'] += 1
                        else:
                            summary['queue_drop_increment'] += difference
                    else:
                        summary.update(first_id=ident, first_device_timestamp=timestamp,
                                       first_queue_drops=drops, first_host_monotonic_ns=host_ns)
                    summary.update(last_id=ident, last_device_timestamp=timestamp,
                                   last_queue_drops=drops, last_host_monotonic_ns=host_ns)
                    rssi = numeric['rssi']
                    summary['rssi_min'] = min(summary['rssi_min'], rssi) if summary['rssi_min'] is not None else rssi
                    summary['rssi_max'] = max(summary['rssi_max'], rssi) if summary['rssi_max'] is not None else rssi
                    writer.writerow([session_id, receiver, RECEIVERS[receiver], host_utc, host_ns] + row)
                    summary['valid_rows'] += 1
                output.flush()
                if len(pending) > 65536:
                    if not dropping_line:
                        summary['oversized_lines'] += 1
                    pending.clear()
                    dropping_line = True
    except Exception as exc:
        summary['error'] = f'{type(exc).__name__}: {exc}'
        stop.set()
    finally:
        summary['trailing_bytes'] = tail_length
        summary['finished_utc'] = utc_now()
        summary['elapsed_host_seconds'] = (time.monotonic_ns() - summary['started_monotonic_ns']) / 1e9
        summary['rows_per_elapsed_second'] = summary['valid_rows'] / summary['elapsed_host_seconds']
        first, last = summary['first_host_monotonic_ns'], summary['last_host_monotonic_ns']
        summary['sample_interval_rate_hz'] = ((summary['valid_rows'] - 1) * 1e9 / (last - first)
                                              if first is not None and last > first else None)
        summary['format_reception_ok'] = summary['valid_rows'] > 0 and not any(
            summary[key] for key in ('malformed_rows', 'unexpected_source_rows',
                                    'unexpected_metadata_rows', 'boot_error_count',
                                    'oversized_lines', 'queue_drop_increment',
                                    'nonincreasing_ids', 'device_time_discontinuities',
                                    'queue_counter_decreases', 'error'))
        for path, key in ((csv_path, 'csv_sha256'), (raw_path, 'serial_log_sha256')):
            if path.exists():
                with path.open('rb') as stream:
                    summary[key] = hashlib.file_digest(stream, 'sha256').hexdigest()
        with summary_path.open('x') as output:
            json.dump(summary, output, indent=2)
            output.write('\n')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receivers', choices=list(RECEIVERS), nargs='+', default=list(RECEIVERS))
    parser.add_argument('--rx01-port', help='Optional RX-01 path; default: discover by USB serial')
    parser.add_argument('--rx02-port', help='Optional RX-02 path; default: discover by USB serial')
    parser.add_argument('--seconds', type=float, default=10)
    parser.add_argument('--output-dir', required=True, type=Path,
                        help='New session directory; existing directories are rejected')
    args = parser.parse_args()
    if not math.isfinite(args.seconds) or args.seconds <= 0:
        parser.error('--seconds must be positive and finite')
    if len(set(args.receivers)) != len(args.receivers):
        parser.error('duplicate receiver IDs')
    ports = {'RX-01': args.rx01_port, 'RX-02': args.rx02_port}
    try:
        verified = resolve_ports(args.receivers, ports)
        # Atomic reservation prevents overwriting any previous session.
        args.output_dir.mkdir(parents=True, exist_ok=False)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.exit(2, f'{exc}\n')
    session = dict(session_id=args.output_dir.name, started_utc=utc_now(),
                   requested_seconds=args.seconds, receivers=verified, note=NOTE,
                   status='opening_ports', results={})
    gate, stop = threading.Event(), threading.Event()
    timing = {'seconds': args.seconds}
    results = session['results']
    threads = []
    try:
        import serial
        with ExitStack() as stack:
            try:
                opened = {}
                for receiver, path in verified.items():
                    if verify_port(receiver, path) != path:
                        raise ValueError(f'{receiver}: USB device changed before opening {path}')
                    device = preserving_serial_type(serial.Serial)(port=None, baudrate=115200, timeout=0.1, exclusive=True)
                    stack.callback(device.close)
                    # No deliberate reset pulse; some USB drivers may still glitch on open.
                    device.dtr = False
                    device.rts = False
                    device.port = path
                    device.open()
                    opened[receiver] = device
                def worker(receiver, device):
                    try:
                        results[receiver] = capture_receiver(device, receiver, args.output_dir,
                                                             session['session_id'], gate, stop, timing)
                    except Exception as exc:
                        results[receiver] = {'error': f'{type(exc).__name__}: {exc}', 'format_reception_ok': False}
                        stop.set()
                for receiver, device in opened.items():
                    thread = threading.Thread(target=worker, args=(receiver, device))
                    threads.append(thread)
                    thread.start()
                timing['deadline_ns'] = time.monotonic_ns() + int(args.seconds * 1e9)
                session['capture_start_monotonic_ns'] = timing['deadline_ns'] - int(args.seconds * 1e9)
                session['capture_deadline_monotonic_ns'] = timing['deadline_ns']
                session['status'] = 'capturing'
                gate.set()
                try:
                    for thread in threads:
                        if thread.ident is not None:
                            thread.join()
                finally:
                    stop.set()
                    for thread in threads:
                        if thread.ident is not None:
                            thread.join()
            finally:
                stop.set()
                gate.set()
                for thread in threads:
                    if thread.ident is not None:
                        thread.join()
        session['status'] = 'error' if any(r.get('error') for r in results.values()) else 'completed'
    except KeyboardInterrupt:
        session['status'] = 'interrupted'
    except Exception as exc:
        session.update(status='error', error=f'{type(exc).__name__}: {exc}')
    finally:
        stop.set()
        gate.set()
        for thread in threads:
            if thread.ident is not None:
                thread.join()
        session['finished_utc'] = utc_now()
        with (args.output_dir / 'session.json').open('x') as output:
            json.dump(session, output, indent=2)
            output.write('\n')
    print(json.dumps(session, indent=2))
    return 0 if (session['status'] == 'completed' and len(results) == len(verified)
                 and all(r['format_reception_ok'] for r in results.values())) else 1


if __name__ == '__main__':
    raise SystemExit(main())
