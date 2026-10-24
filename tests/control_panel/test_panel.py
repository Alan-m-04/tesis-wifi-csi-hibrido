import importlib.util
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('control_panel_server', ROOT / 'apps/control_panel/server.py')
panel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(panel)


class PanelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.profile = self.root / 'source.json'
        self.source = (ROOT / 'config/csi_esp32s3.json').read_bytes()
        self.profile.write_bytes(self.source)
        self.devices = []
        self.server = panel.make_server(self.profile, self.root / 'drafts', 0, lambda: self.devices)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = 'http://127.0.0.1:' + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.assertEqual(self.profile.read_bytes(), self.source)
        self.temp.cleanup()

    def request(self, path, value=None, headers=None, raw=None):
        headers = headers or {}
        if value is not None:
            raw = json.dumps(value).encode()
            headers = {'Content-Type': 'application/json', **headers}
        req = urllib.request.Request(self.base + path, data=raw, headers=headers)
        try:
            response = urllib.request.urlopen(req, timeout=3)
        except urllib.error.HTTPError as response:
            return response.code, json.load(response)
        with response:
            return response.status, response.read()

    def test_no_physical_state_fabricated(self):
        status, body = self.request('/api/state')
        data = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(data['mode'], 'CONFIGURATION_DRAFTS_ONLY')
        self.assertEqual([n['status'] for n in data['nodes']], ['EXTERNAL_POWER_NOT_VERIFIED', 'USB_NOT_OBSERVED', 'USB_NOT_OBSERVED'])
        self.assertFalse(any(n['uart_opened'] for n in data['nodes']))
        self.assertFalse(data['capabilities']['capture'])
        self.assertFalse(data['capabilities']['flash'])
        self.assertFalse(data['capabilities']['apply_to_esp'])
        self.assertFalse((self.root / 'drafts').exists())
        self.assertEqual(self.server.server_address[0], '127.0.0.1')

    def test_draft_append_only_and_export(self):
        payload = self.server.store.defaults()
        code, body = self.request('/api/drafts', value=payload)
        saved = json.loads(body)
        self.assertEqual(code, 201)
        self.assertEqual(saved['status'], 'DRAFT_NOT_APPLIED')
        self.assertFalse(saved['hardware_modified'])
        self.assertEqual(saved['profile'], payload)
        self.assertEqual(json.loads(self.request('/api/drafts/' + saved['id'] + '/export')[1]), saved)
        code, body = self.request('/api/drafts', value=payload)
        self.assertEqual(code, 201)
        self.assertNotEqual(json.loads(body)['id'], saved['id'])
        self.assertEqual(len(self.server.store.list()), 2)

    def test_invalid_profile_no_writes(self):
        bad = [{'channel': True}, {'channel': 14}, {'channel': 0}, {'bandwidth': 'HT40'},
               {'source_mac': 'ff:ff:ff:ff:ff:ff'}, {'source_mac': '00:00:00:00:00:00'},
               {'capture_seconds': 0}, {'capture_seconds': 601}, {'name': ' '},
               {'receivers': {'RX-01': 'same', 'RX-02': 'same'}},
               {'receivers': {'RX-01': '../../bad', 'RX-02': 'good'}}]
        for change in bad:
            with self.subTest(change=change):
                payload = self.server.store.defaults()
                payload.update(change)
                self.assertEqual(self.request('/api/drafts', value=payload)[0], 400)
        self.assertEqual(self.server.store.list(), [])

    def test_unknown_fields_and_invalid_json_rejected(self):
        payload = self.server.store.defaults()
        payload['apply_to_esp'] = True
        self.assertEqual(self.request('/api/drafts', value=payload)[0], 400)
        self.assertEqual(self.request('/api/drafts', raw=b'{', headers={'Content-Type': 'application/json'})[0], 400)

    def test_no_hardware_or_shell_endpoints(self):
        for path in ('/api/flash', '/api/capture', '/api/apply', '/api/shell'):
            with self.subTest(path=path):
                self.assertEqual(self.request(path, value={})[0], 404)

    def test_host_and_origin_checks(self):
        self.assertEqual(self.request('/api/state', headers={'Host': 'evil.example'})[0], 403)
        self.assertEqual(self.request('/api/drafts', value=self.server.store.defaults(), headers={'Origin': 'https://evil.example'})[0], 403)
        self.assertEqual(self.request('/api/drafts', value=self.server.store.defaults(), headers={'Origin': self.base})[0], 201)
        self.assertEqual(self.request('/api/drafts', raw=b'name=test', headers={'Content-Type': 'application/x-www-form-urlencoded'})[0], 415)

    def test_unknown_or_traversal_export_rejected(self):
        self.assertEqual(self.request('/api/drafts/../../source.json/export')[0], 400)
        self.assertEqual(self.request('/api/drafts/not-a-uuid/export')[0], 400)

    def test_usb_visible_does_not_mean_uart_open(self):
        serial = self.server.store.profile['receivers']['RX-01']
        self.devices = [{'usb_serial': serial, 'path': '/SYNTHETIC/ttyACM0'}]
        data = json.loads(self.request('/api/state')[1])
        self.assertEqual(data['nodes'][1]['status'], 'USB_VISIBLE_UART_CLOSED')
        self.assertFalse(data['nodes'][1]['uart_opened'])
        self.devices.append({'usb_serial': serial, 'path': '/SYNTHETIC/ttyACM1'})
        data = json.loads(self.request('/api/state')[1])
        self.assertEqual(data['nodes'][1]['status'], 'USB_IDENTITY_AMBIGUOUS')

    def test_usb_inventory_reads_only_fake_sysfs(self):
        sysclass = self.root / 'sys/tty'
        sysclass.mkdir(parents=True)
        device = self.root / 'fake-usb'
        device.mkdir()
        for name, value in {'serial': 'SYNTHETIC_USB', 'idVendor': '1a86', 'idProduct': '55d3'}.items():
            (device / name).write_text(value)
        tty = sysclass / 'ttyACM0'
        tty.mkdir()
        (tty / 'device').symlink_to(device, target_is_directory=True)
        found = panel.usb_inventory(sysclass, self.root / 'NO_PHYSICAL_DEVICES')
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]['usb_serial'], 'SYNTHETIC_USB')
        self.assertFalse(found[0]['uart_opened'])

    def test_static_assets_and_source_profile_not_modified(self):
        for path in ('/', '/panel.css', '/panel.js'):
            self.assertEqual(self.request(path)[0], 200)
        self.assertEqual(self.request('/api/does-not-exist')[0], 404)


if __name__ == '__main__':
    unittest.main(verbosity=2)
