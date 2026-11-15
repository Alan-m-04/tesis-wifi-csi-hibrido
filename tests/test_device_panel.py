"""Metadata fixtures and HTTP over memory streams; no UART or capture."""
import copy
import io
import json
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools')]
import device_metadata as dm
import panel_dispositivos as cli

STAMP='2026-11-09T12:34:56+00:00'
def props(rx):return dict(ID_SERIAL_SHORT=dm.RECEIVERS[rx],ID_VENDOR_ID='1a86',ID_MODEL_ID='55d3',ID_BUS='usb')
PERMISSIONS=dict(mode='0o660',uid=1000,gid=20,effective_read=True,effective_write=False)
FULL_MOUNT='1 0 0:1 / /dev rw,nosuid - devtmpfs devtmpfs rw\n'


class Probe:
    def __init__(self,records=None,complete=True,permissions=None):
        self.records=records or {};self.complete=complete;self.perms=permissions or PERMISSIONS
    def scan(self):return dict(paths=list(self.records),complete=self.complete,notes=[] if self.complete else ['Vista limitada de /dev'])
    def identity(self,path):
        value=self.records[path]
        if isinstance(value,Exception):raise value
        return value
    def permissions(self,node):
        if isinstance(self.perms,Exception):raise self.perms
        return copy.deepcopy(self.perms)


def collect(probe):
    with patch('serial.Serial',side_effect=AssertionError('UART forbidden')):
        return dm.snapshot(probe,now=lambda:STAMP)


class MetadataTests(unittest.TestCase):
    def test_usb_identity_permissions_timestamp_and_unknown_READY_CSI(self):
        records={dm.PORTS[rx]:(f'/dev/ttyACM{i}',props(rx)) for i,rx in enumerate(dm.RECEIVERS)}
        with patch.object(dm.capture,'require_identity',wraps=dm.capture.require_identity) as identify:
            data=collect(Probe(records))
        self.assertEqual(identify.call_count,2)
        for rx,device in zip(dm.RECEIVERS,data['devices']):
            self.assertEqual(device['status'],'detectado')
            self.assertEqual(device['usb_serial'],dm.RECEIVERS[rx]);self.assertEqual(device['by_id'],dm.PORTS[rx])
            self.assertEqual(device['permissions'],PERMISSIONS);self.assertTrue(device['by_id_observed'])
            self.assertEqual(device['queried_at_utc'],STAMP)
            self.assertIsNone(device['ready']);self.assertIsNone(device['csi_received'])
        self.assertFalse(data['UART_opened']);self.assertFalse(data['replay_data_accessed'])
        self.assertEqual(data['devices'][2]['status_text'],'no verificable por USB')

    def test_missing_UART_access_does_not_erase_USB_detection(self):
        perms=dict(PERMISSIONS,effective_read=False,effective_write=False)
        d=collect(Probe({dm.PORTS['RX-02']:('/dev/ttyACM9',props('RX-02'))},permissions=perms))
        self.assertEqual(d['devices'][1]['status'],'detectado')
        self.assertFalse(d['devices'][1]['permissions']['effective_read'])

    def test_absence_requires_complete_local_inventory(self):
        for complete,state in ((True,'ausente'),(False,'no_verificable')):
            with self.subTest(complete=complete):
                d=collect(Probe(complete=complete))
                self.assertEqual([r['status'] for r in d['devices'][:2]],[state,state])

    def test_udev_failure_node_permission_failure_and_invalid_identity_are_unknown(self):
        bad=[PermissionError('No udev'),ValueError('Cannot resolve'),('/dev/ttyACM0',dict(props('RX-02'),ID_MODEL_ID='wrong')),
             ('/dev/ttyACM0',dict(props('RX-02'),ID_VENDOR_ID='other')),('/dev/ttyACM0',props('RX-01'))]
        for value in bad:
            with self.subTest(value=str(value)):
                d=collect(Probe({dm.PORTS['RX-02']:value}))
                self.assertEqual(d['devices'][1]['status'],'no_verificable');self.assertFalse(d['inventory_complete'])
        d=collect(Probe({dm.PORTS['RX-02']:('/dev/ttyACM0',props('RX-02'))},permissions=PermissionError('stat denied')))
        self.assertEqual(d['devices'][1]['status'],'no_verificable')

    def test_duplicate_serials_and_alias_deduplication(self):
        a={dm.PORTS['RX-02']:('/dev/ttyACM0',props('RX-02')),'/dev/ttyACM0':('/dev/ttyACM0',props('RX-02'))}
        self.assertEqual(collect(Probe(a))['devices'][1]['status'],'detectado')
        a['/dev/ttyACM1']=('/dev/ttyACM1',props('RX-02'))
        d=collect(Probe(a))['devices'][1]
        self.assertEqual(d['status'],'no_verificable');self.assertIsNone(d['node'])
        self.assertIn('duplicada',d['notes'][0])

    def test_detected_by_serial_never_depends_on_a_fixed_numbered_node(self):
        d=collect(Probe({'/dev/ttyUSB7':('/dev/ttyUSB7',props('RX-01'))}))
        self.assertEqual(d['devices'][0]['node'],'/dev/ttyUSB7')
        self.assertFalse(d['devices'][0]['by_id_observed'])

    def test_unreadable_dev_scan_never_means_absent(self):
        p=Probe()
        with patch.object(p,'scan',side_effect=PermissionError('/dev denied')):
            d=collect(p)
        self.assertEqual([r['status'] for r in d['devices'][:2]],['no_verificable']*2)

    def test_USB_serial_without_a_tty_node_is_unknown_not_absent(self):
        probe=Probe()
        with patch.object(probe,'scan',return_value=dict(paths=[],complete=True,notes=[],usb_serials=[dm.RECEIVERS['RX-02']])):
            d=collect(probe)
        self.assertEqual(d['devices'][1]['status'],'no_verificable')
        self.assertIn('USB/sysfs',d['devices'][1]['notes'][0])

    def test_existing_metadata_helper_is_reused_without_port_open(self):
        with patch.object(dm.capture,'port_identity',return_value=('/dev/ttyACM5',props('RX-02'))) as identify:
            self.assertEqual(dm.LocalMetadata().identity(dm.PORTS['RX-02'])[0],'/dev/ttyACM5')
        identify.assert_called_once_with(dm.PORTS['RX-02'])

    def test_mount_visibility_is_conservative(self):
        self.assertTrue(dm.dev_mount_complete(FULL_MOUNT))
        for text in ('',FULL_MOUNT.replace('rw,nosuid','rw,nodev'),FULL_MOUNT.replace('devtmpfs','tmpfs'),
                     FULL_MOUNT+'2 1 0:2 / /dev/serial ro - tmpfs tmpfs ro\n',
                     FULL_MOUNT+'2 1 0:2 / /dev/ttyACM0 ro - tmpfs tmpfs ro\n'):
            with self.subTest(text=text):self.assertFalse(dm.dev_mount_complete(text))

    def test_sysfs_node_without_dev_node_is_not_an_empty_complete_view(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for rel in ('dev','sys/class/tty','sys/bus/usb/devices','proc/self'):(root/rel).mkdir(parents=True,exist_ok=True)
            (root/'sys/class/tty/ttyACM0').mkdir()
            (root/'proc/self/mountinfo').write_text(FULL_MOUNT)
            with patch.object(dm,'Path',side_effect=lambda p:root/str(p).lstrip('/')):
                scan=dm.LocalMetadata().scan()
            self.assertFalse(scan['complete']);self.assertIn('sin nodo',scan['notes'][0])

    def test_permissions_are_stat_and_effective_access_only(self):
        info=SimpleNamespace(st_mode=stat.S_IFCHR|0o660,st_uid=1000,st_gid=20)
        with patch.object(dm.os,'stat',return_value=info),patch.object(dm.os,'access',side_effect=[True,False]) as access:
            self.assertEqual(dm.LocalMetadata().permissions('/fake/tty'),PERMISSIONS)
        self.assertEqual(access.call_count,2)

    def test_serial_open_guard_rejects_device_open_events(self):
        for p in ('/dev/ttyACM0','/dev/ttyUSB0','/dev/serial/by-id/example'):
            with self.assertRaises(PermissionError):cli.no_serial_open('open',(p,'r',0))


class FakeSocket:
    def __init__(self,request):self.request=request;self.output=bytearray()
    def makefile(self,*_):return io.BytesIO(self.request)
    def sendall(self,data):self.output.extend(data)


class HttpTests(unittest.TestCase):
    def request(self,path='/',host='127.0.0.1:8766',method='GET',replay_html=None,collect_fn=None):
        sock=FakeSocket(f'{method} {path} HTTP/1.0\r\nHost: {host}\r\n\r\n'.encode())
        collect_fn=collect_fn or (lambda:collect(Probe()))
        cls=cli.handler(collect_fn,replay_html)
        with patch.object(cls,'log_message'):
            cls(sock,('127.0.0.1',1234),SimpleNamespace(server_port=8766))
        return bytes(sock.output)

    def test_panel_module_and_fresh_metadata_API(self):
        page=self.request();self.assertIn(b'200 OK',page)
        self.assertNotIn(b'__DEVICE_CATALOGUE__',page);self.assertIn(b'5C93199744',page)
        self.assertIn(b'export async function refresh',self.request('/panel.mjs'))
        response=self.request('/api/devices');headers,body=response.split(b'\r\n\r\n',1)
        self.assertIn(b'Cache-Control: no-store',headers);self.assertNotIn(b'Access-Control-Allow-Origin',headers)
        self.assertEqual(json.loads(body)['queried_at_utc'],STAMP)

    def test_no_replay_files_or_mutation_routes_and_local_host_only(self):
        for p in ('/../README.md','/data.json','/api/devices?capture=1','/results/local/'):
            self.assertIn(b'404',self.request(p).split(b'\r\n')[0])
        self.assertIn(b'403',self.request(host='external.example:8766').split(b'\r\n')[0])
        self.assertIn(b'405',self.request('/api/devices',method='POST').split(b'\r\n')[0])

    def test_server_always_binds_loopback(self):
        with patch.object(cli,'ThreadingHTTPServer') as server:cli.make_server(8766)
        self.assertEqual(server.call_args.args[0],('127.0.0.1',8766))

    def test_navigation_reuses_readonly_replay_without_querying_USB(self):
        replay=b'<html>REPRODUCCION OFFLINE fixture</html>'
        with patch('serial.Serial',side_effect=AssertionError('UART forbidden')):
            response=self.request('/replay',replay_html=replay,collect_fn=lambda: self.fail('Replay must not query metadata'))
        headers,body=response.split(b'\r\n\r\n',1)
        self.assertEqual(body,replay);self.assertIn(b"connect-src 'none'",headers)
        self.assertIn(b"script-src 'unsafe-inline'",headers)
        self.assertIn(b'href="/replay"',self.request())
        self.assertIn(b'503',self.request('/replay').split(b'\r\n')[0])

    def test_snapshot_mode_does_not_build_replay_or_open_server(self):
        from contextlib import redirect_stdout
        with patch.object(cli,'snapshot',return_value={'metadata_fixture':True}),patch.object(cli,'build') as build, \
             patch.object(cli,'make_server') as server,patch.object(cli.sys,'addaudithook'),redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(['--snapshot']),0)
        build.assert_not_called();server.assert_not_called()

    def test_server_startup_builds_once_and_reuses_the_existing_artifact(self):
        from contextlib import redirect_stdout
        server=SimpleNamespace(server_port=8766,serve_forever=lambda: (_ for _ in ()).throw(KeyboardInterrupt()),server_close=lambda:None)
        with patch.object(cli,'build',return_value=SimpleNamespace(read_bytes=lambda:b'historical fixture')) as build, \
             patch.object(cli,'make_server',return_value=server) as make,patch.object(cli.sys,'addaudithook'),redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main([]),0)
        build.assert_called_once_with(cli.DEFAULT)
        make.assert_called_once_with(8766,replay_html=b'historical fixture',database_path=cli.DEFAULT_DATABASE)


if __name__=='__main__':unittest.main()
