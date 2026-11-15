"""Synthetic UART tests using Linux PTYs; no physical boards or experiment files."""
import csv
import io
import json
import os
import pty
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import capture_csi_multi as capture


def sample(ident, timestamp, **overrides):
    values = {key: '0' for key in capture.FIELDS}
    values.update(type='CSI_DATA', id=str(ident), mac=capture.SOURCE,
                  rssi='-50', channel='11', len='4',
                  local_timestamp=str(timestamp), data='[-128,127,0,1]')
    values.update(overrides)
    output = io.StringIO()
    csv.writer(output, lineterminator='\n').writerow([values[key] for key in capture.FIELDS])
    return output.getvalue().encode()


def udev_properties(receiver):
    return f'ID_BUS=usb\nID_VENDOR_ID=1a86\nID_SERIAL_SHORT={capture.RECEIVERS[receiver]}\n'


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.devices = Path(temporary.name)
        self.by_id = self.devices / 'serial' / 'by-id'
        self.by_id.mkdir(parents=True)
        self.properties = {}
        for name, value in [('USB_BY_ID', self.by_id), ('SERIAL_DEVICE_DIR', self.devices)]:
            patcher = patch.object(capture, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch.object(capture.subprocess, 'run', side_effect=self.udev)
        self.query = patcher.start()
        self.addCleanup(patcher.stop)

    def udev(self, arguments, **kwargs):
        self.assertEqual(arguments[:4], ['udevadm', 'info', '--query=property', '--name'])
        return SimpleNamespace(stdout=self.properties[arguments[-1]])

    def add_device(self, receiver, name, target, persistent=True):
        node = self.devices / name
        node.symlink_to(target)
        self.properties[target] = udev_properties(receiver)
        link = self.by_id / f'usb-CH343_{capture.RECEIVERS[receiver]}-if00'
        if persistent:
            link.symlink_to(node)
        return node, link

    def resolve(self):
        return capture.resolve_ports(list(capture.RECEIVERS), {})

    def assert_main_rejects(self, message, extra=()):
        directory = self.devices / 'output'
        arguments = ['capture_csi_multi.py', '--output-dir', str(directory), *extra]
        error = io.StringIO()
        with patch('sys.argv', arguments), patch('serial.Serial') as serial_open, \
                redirect_stderr(error), self.assertRaises(SystemExit) as raised:
            capture.main()
        self.assertEqual(raised.exception.code, 2)
        self.assertIn(message, error.getvalue())
        serial_open.assert_not_called()
        self.assertFalse(directory.exists())

    def test_swapped_ports_are_resolved_by_serial_using_by_id_first(self):
        self.add_device('RX-01', 'ttyACM1', '/dev/zero')
        self.add_device('RX-02', 'ttyACM0', '/dev/null')
        self.assertEqual(self.resolve(), {'RX-01': '/dev/zero', 'RX-02': '/dev/null'})
        # by-id aliases and numbered nodes must not count as duplicate receivers.
        self.assertEqual([call.args[0][-1] for call in self.query.call_args_list],
                         ['/dev/zero', '/dev/null'])

    def test_numbered_devices_are_discovered_when_by_id_is_absent(self):
        self.add_device('RX-01', 'ttyUSB23', '/dev/zero', persistent=False)
        self.add_device('RX-02', 'ttyACM17', '/dev/null', persistent=False)
        self.by_id.rmdir()
        self.assertEqual(self.resolve(), {'RX-01': '/dev/zero', 'RX-02': '/dev/null'})

    def test_missing_receiver_aborts_before_opening_or_creating_output(self):
        self.add_device('RX-02', 'ttyACM0', '/dev/null')
        self.assert_main_rejects('RX-01: USB receiver not found; expected serial 5C93199744')

    def test_duplicate_serial_hidden_by_one_by_id_link_aborts(self):
        self.add_device('RX-01', 'ttyACM0', '/dev/null')
        self.add_device('RX-01', 'ttyACM1', '/dev/zero', persistent=False)
        self.assert_main_rejects('RX-01: duplicate USB serial 5C93199744')

    def test_by_id_link_with_wrong_identity_aborts(self):
        self.add_device('RX-01', 'ttyACM0', '/dev/null')
        self.properties['/dev/null'] = udev_properties('RX-02')
        self.assert_main_rejects('USB identity mismatch')

    def test_missing_or_wrong_vendor_bus_and_serial_abort(self):
        self.add_device('RX-01', 'ttyACM1', '/dev/zero')
        self.add_device('RX-02', 'ttyACM0', '/dev/null')
        correct = udev_properties('RX-01')
        for properties in (correct.replace('1a86', 'ffff'), correct.replace('usb', 'pci'),
                           correct.replace('ID_SERIAL_SHORT=5C93199744\n', '')):
            with self.subTest(properties=properties):
                self.properties['/dev/zero'] = properties
                self.assert_main_rejects('USB identity mismatch')

    def test_explicit_wrong_port_cannot_override_serial(self):
        self.add_device('RX-01', 'ttyACM1', '/dev/zero')
        wrong, _ = self.add_device('RX-02', 'ttyACM0', '/dev/null')
        self.assert_main_rejects('USB identity mismatch', ['--rx01-port', str(wrong)])

    def test_valid_explicit_path_is_supported(self):
        node, _ = self.add_device('RX-01', 'ttyACM1', '/dev/zero')
        self.add_device('RX-02', 'ttyACM0', '/dev/null')
        self.assertEqual(capture.resolve_ports(list(capture.RECEIVERS), {'RX-01': str(node)}),
                         {'RX-01': '/dev/zero', 'RX-02': '/dev/null'})

    def test_dangling_persistent_link_aborts(self):
        (self.by_id / 'usb-CH343_5C93199744-if00').symlink_to(self.devices / 'ttyACM1')
        self.assert_main_rejects('cannot read USB identity')

    def test_udev_failure_aborts(self):
        self.add_device('RX-01', 'ttyACM1', '/dev/zero')
        with patch.object(capture.subprocess, 'run', side_effect=FileNotFoundError('udevadm')):
            self.assert_main_rejects('cannot read USB identity')

    def test_regular_file_is_rejected(self):
        (self.devices / 'ttyACM1').write_text('not a device')
        self.assert_main_rejects('not a character device')


class CaptureTests(unittest.TestCase):
    def run_capture(self, directory, streams, disconnect=False, swapped=False):
        devices = {rx: pty.openpty() for rx in streams}
        paths = {rx: os.ttyname(pair[1]) for rx, pair in devices.items()}
        def produce():
            time.sleep(0.2)
            for receiver, payload in streams.items():
                master = devices[receiver][0]
                # Split a CSV row across reads to exercise serial framing.
                os.write(master, payload[:31])
                time.sleep(0.02)
                os.write(master, payload[31:])
            if disconnect:
                time.sleep(0.1)
                for master, _ in devices.values():
                    os.close(master)
        producer = threading.Thread(target=produce)
        arguments = ['capture_csi_multi.py', '--receivers', *streams, '--seconds', '0.65',
                     '--output-dir', str(directory)]
        producer.start()
        try:
            with tempfile.TemporaryDirectory() as temporary:
                dev = Path(temporary)
                by_id = dev / 'serial' / 'by-id'
                by_id.mkdir(parents=True)
                for receiver, path in paths.items():
                    index = int(receiver[-1]) - 1
                    node = dev / f'ttyACM{1 - index if swapped else index}'
                    node.symlink_to(path)
                    (by_id / f'usb-CH343_{capture.RECEIVERS[receiver]}-if00').symlink_to(node)
                identities = {path: udev_properties(rx) for rx, path in paths.items()}
                with patch('sys.argv', arguments), \
                        patch.object(capture, 'USB_BY_ID', by_id), \
                        patch.object(capture, 'SERIAL_DEVICE_DIR', dev), \
                        patch.object(capture.subprocess, 'run', side_effect=lambda args, **kwargs:
                                     SimpleNamespace(stdout=identities[args[-1]])), \
                        redirect_stdout(io.StringIO()):
                    result = capture.main()
            producer.join()
            return result, json.loads((directory / 'session.json').read_text())
        finally:
            producer.join()
            for master, slave in devices.values():
                for descriptor in (master, slave):
                    try:
                        os.close(descriptor)
                    except OSError:
                        pass

    def test_two_receivers_preserve_independent_clocks_and_csv(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / 'dual'
            streams = {rx: (f'{rx} READY\n'.encode() + b''.join(
                sample(i, offset + i * 200000) for i in range(5)))
                for rx, offset in [('RX-01', 1000000), ('RX-02', 800000000)]}
            code, session = self.run_capture(directory, streams)
            self.assertEqual(code, 0)
            self.assertEqual(session['status'], 'completed')
            for receiver, offset in [('RX-01', 1000000), ('RX-02', 800000000)]:
                summary = session['results'][receiver]
                self.assertEqual(summary['valid_rows'], 5)
                self.assertEqual(summary['first_device_timestamp'], offset)
                self.assertTrue(summary['ready_seen'])
                with (directory / f'{receiver.lower()}.csv').open(newline='') as stream:
                    reader = csv.DictReader(stream)
                    self.assertEqual(reader.fieldnames, capture.EXTRA_FIELDS + capture.FIELDS)
                    rows = list(reader)
                self.assertEqual(len(rows), 5)
                self.assertTrue(all(row['receiver_id'] == receiver and row['session_id'] == 'dual'
                                    and row['usb_serial'] == capture.RECEIVERS[receiver]
                                    and row['mac'] == capture.SOURCE for row in rows))
                self.assertEqual((directory / f'{receiver.lower()}.serial.log').read_bytes(), streams[receiver])

    def test_swapped_ports_preserve_receiver_csv_logs_and_statistics(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / 'swapped'
            streams = {'RX-01': sample(10, 1000000),
                       'RX-02': sample(20, 800000000) + sample(21, 800200000)}
            code, session = self.run_capture(directory, streams, swapped=True)
            self.assertEqual(code, 0)
            self.assertEqual(session['status'], 'completed')
            self.assertNotEqual(session['receivers']['RX-01'], session['receivers']['RX-02'])
            for receiver, count, first_id in [('RX-01', 1, 10), ('RX-02', 2, 20)]:
                summary = session['results'][receiver]
                self.assertEqual(summary['usb_serial'], capture.RECEIVERS[receiver])
                self.assertEqual(summary['valid_rows'], count)
                self.assertEqual(summary['first_id'], first_id)
                self.assertTrue(summary['format_reception_ok'])
                with (directory / f'{receiver.lower()}.csv').open(newline='') as stream:
                    reader = csv.DictReader(stream)
                    self.assertEqual(reader.fieldnames, capture.EXTRA_FIELDS + capture.FIELDS)
                    rows = list(reader)
                self.assertEqual(len(rows), count)
                for row in rows:
                    self.assertEqual(row['receiver_id'], receiver)
                    self.assertEqual(row['usb_serial'], capture.RECEIVERS[receiver])
                    self.assertEqual(row['session_id'], 'swapped')
                    self.assertGreaterEqual(int(row['host_monotonic_ns']),
                                            session['capture_start_monotonic_ns'])
                    self.assertTrue(row['host_timestamp_utc'].endswith('+00:00'))
                self.assertEqual((directory / f'{receiver.lower()}.serial.log').read_bytes(),
                                 streams[receiver])

    def test_invalid_records_and_boot_error_are_reported(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / 'bad'
            data = (sample(0, 2**32 - 100000) + sample(2, 100000, queue_drops='1')
                    + sample(3, 300000, len='6')
                    + sample(3, 300000, mac='00:00:00:00:00:00')
                    + sample(3, 300000, channel='6')
                    + b'ESP_ERROR_CHECK failed: esp_err_t 0x1\n')
            code, session = self.run_capture(directory, {'RX-02': data})
            self.assertEqual(code, 1)
            summary = session['results']['RX-02']
            for key in ['malformed_rows', 'unexpected_source_rows', 'unexpected_metadata_rows',
                        'boot_error_count', 'callback_id_gaps', 'device_clock_wraps', 'queue_drop_increment']:
                self.assertEqual(summary[key], 1, key)
            self.assertEqual(summary['valid_rows'], 2)
            self.assertFalse(summary['format_reception_ok'])

    def test_disconnection_preserves_partial_files_and_returns_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / 'disconnected'
            code, session = self.run_capture(directory, {'RX-02': sample(0, 100000)}, disconnect=True)
            self.assertEqual(code, 1)
            self.assertEqual(session['status'], 'error')
            self.assertEqual(session['results']['RX-02']['valid_rows'], 1)
            self.assertIsNotNone(session['results']['RX-02']['error'])
            self.assertTrue((directory / 'rx-02.summary.json').exists())

    def test_udev_rejects_swapped_or_incomplete_identity(self):
        correct = 'ID_BUS=usb\nID_VENDOR_ID=1a86\nID_SERIAL_SHORT=5C93200689\n'
        with patch.object(capture.subprocess, 'run', return_value=SimpleNamespace(stdout=correct)):
            self.assertEqual(capture.verify_port('RX-02', '/dev/null'), '/dev/null')
            with self.assertRaises(ValueError):
                capture.verify_port('RX-01', '/dev/null')
        with patch.object(capture.subprocess, 'run', return_value=SimpleNamespace(stdout='ID_BUS=usb\n')):
            with self.assertRaises(ValueError):
                capture.verify_port('RX-02', '/dev/null')

    def test_existing_session_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            sentinel = Path(temporary) / 'rx-02.csv'
            sentinel.write_text('prior data\n')
            args = ['capture_csi_multi.py', '--receivers', 'RX-02', '--output-dir', temporary]
            with patch('sys.argv', args), \
                    patch.object(capture, 'resolve_ports', return_value={'RX-02': '/dev/null'}), \
                    patch('serial.Serial') as serial_open, redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    capture.main()
                self.assertEqual(raised.exception.code, 2)
                serial_open.assert_not_called()
            self.assertEqual(sentinel.read_text(), 'prior data\n')

    def test_identity_is_rechecked_before_opening_and_failure_is_recorded(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / 'changed'
            args = ['capture_csi_multi.py', '--receivers', 'RX-01', '--output-dir', str(directory)]
            with patch('sys.argv', args), \
                    patch.object(capture, 'resolve_ports', return_value={'RX-01': '/dev/null'}), \
                    patch.object(capture, 'verify_port', side_effect=ValueError('USB identity mismatch')) \
                    as verify, patch('serial.Serial') as serial_open, redirect_stdout(io.StringIO()):
                self.assertEqual(capture.main(), 1)
            verify.assert_called_once_with('RX-01', '/dev/null')
            serial_open.assert_not_called()
            session = json.loads((directory / 'session.json').read_text())
            self.assertEqual(session['status'], 'error')
            self.assertIn('USB identity mismatch', session['error'])
            self.assertFalse((directory / 'rx-01.csv').exists())


if __name__ == '__main__':
    unittest.main()
