"""Local control-panel foundation: draft profiles and USB inventory only.

No serial, firmware, capture, shell-execution, or model actions are implemented.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROLES = ('RX-01', 'RX-02')


def validate_draft(value):
    if not isinstance(value, dict) or set(value) != {'name', 'channel', 'bandwidth', 'source_mac', 'receivers', 'capture_seconds', 'notes'}:
        raise ValueError('El borrador contiene campos incompletos o desconocidos.')
    if not isinstance(value['name'], str) or not 1 <= len(value['name'].strip()) <= 80:
        raise ValueError('El nombre debe tener entre 1 y 80 caracteres.')
    if type(value['channel']) is not int or not 1 <= value['channel'] <= 13:
        raise ValueError('El canal debe ser un entero entre 1 y 13.')
    if value['bandwidth'] != 'HT20':
        raise ValueError('Esta primera versión admite únicamente perfiles HT20.')
    mac = value['source_mac']
    if not isinstance(mac, str) or not re.fullmatch(r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}', mac) or int(mac[:2], 16) & 1:
        raise ValueError('La MAC TX debe tener formato válido y ser unicast.')
    if mac.lower() == '00:00:00:00:00:00':
        raise ValueError('La MAC TX no puede ser cero.')
    receivers = value['receivers']
    if not isinstance(receivers, dict) or set(receivers) != set(ROLES):
        raise ValueError('Se requieren RX-01 y RX-02.')
    serials = list(receivers.values())
    if any(not isinstance(s, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', s) for s in serials) or len(set(serials)) != 2:
        raise ValueError('Las dos identidades USB deben ser válidas y distintas.')
    if type(value['capture_seconds']) is not int or not 1 <= value['capture_seconds'] <= 600:
        raise ValueError('La duración propuesta debe estar entre 1 y 600 segundos.')
    if not isinstance(value['notes'], str) or len(value['notes']) > 2000:
        raise ValueError('Las notas admiten hasta 2000 caracteres.')
    return {**value, 'name': value['name'].strip(), 'source_mac': mac.lower()}


def usb_inventory(sys_class=Path('/sys/class/tty'), dev_root=Path('/dev')):
    """Read sysfs identity attributes; never open a tty or change its state."""
    devices = []
    if not sys_class.is_dir():
        return devices
    for tty in sorted(sys_class.iterdir()):
        if not re.fullmatch(r'tty(?:ACM|USB)\d+', tty.name):
            continue
        try:
            parent = (tty / 'device').resolve(strict=True)
            for directory in (parent, *parent.parents):
                serial_file = directory / 'serial'
                if all((directory / x).is_file() for x in ('serial', 'idVendor', 'idProduct')):
                    serial = serial_file.read_text().strip()
                    devices.append({'path': str(dev_root / tty.name), 'usb_serial': serial,
                                    'vendor': (directory / 'idVendor').read_text().strip(),
                                    'product': (directory / 'idProduct').read_text().strip(),
                                    'uart_opened': False})
                    break
        except OSError:
            continue
    return devices


class Store:
    def __init__(self, profile_path, state_dir):
        self.profile_path = Path(profile_path)
        raw = self.profile_path.read_bytes()
        self.profile = json.loads(raw)
        self.source_sha256 = hashlib.sha256(raw).hexdigest()
        self.state_dir = Path(state_dir)
        self.lock = threading.Lock()

    def defaults(self):
        p = self.profile
        return {'name': 'Piloto MIPYME', 'channel': p['channel'], 'bandwidth': p['bandwidth'],
                'source_mac': p['source_mac'], 'receivers': p['receivers'], 'capture_seconds': 60, 'notes': ''}

    def save(self, payload):
        draft = validate_draft(payload)
        record = {'schema': 'tesis-control-panel-draft-v1', 'id': str(uuid.uuid4()),
                  'created_at': datetime.now(timezone.utc).isoformat(), 'status': 'DRAFT_NOT_APPLIED',
                  'source_profile_sha256': self.source_sha256,
                  'idf_version': self.profile['idf_version'], 'baud': self.profile['baud'],
                  'requires_firmware_review': draft['channel'] != self.profile['channel'] or draft['source_mac'] != self.profile['source_mac'],
                  'profile': draft, 'hardware_modified': False}
        with self.lock:
            self.state_dir.mkdir(parents=True, exist_ok=True)
            with (self.state_dir / (record['id'] + '.json')).open('x') as f:
                json.dump(record, f, indent=2, ensure_ascii=False)
                f.write('\n')
        return record

    def load(self, ident):
        if not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', ident):
            raise ValueError('Identificador no válido.')
        path = self.state_dir / (ident + '.json')
        if path.is_symlink():
            raise ValueError('No se admiten enlaces simbólicos como borradores.')
        return json.loads(path.read_text())

    def list(self):
        if not self.state_dir.exists():
            return []
        records = []
        for f in self.state_dir.glob('*.json'):
            if not f.is_symlink():
                records.append(self.load(f.stem))
        return sorted(records, key=lambda r: r['created_at'], reverse=True)


def make_server(profile_path, state_dir, port=8090, inventory=usb_inventory):
    store = Store(profile_path, state_dir)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def local_request(self):
            port = self.server.server_port
            allowed = {f'127.0.0.1:{port}', f'localhost:{port}'}
            if self.headers.get('Host', '') not in allowed:
                self.respond(403, {'error': 'Host local no válido.'})
                return False
            origin = self.headers.get('Origin')
            if origin is not None and origin not in {'http://' + host for host in allowed}:
                self.respond(403, {'error': 'Origen no permitido.'})
                return False
            return True

        def respond(self, status, content, content_type='application/json; charset=utf-8', filename=None):
            data = content.encode() if isinstance(content, str) else json.dumps(content, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; connect-src 'self'; base-uri 'none'")
            if filename:
                self.send_header('Content-Disposition', 'attachment; filename="' + filename + '"')
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if not self.local_request():
                return
            try:
                if self.path in ('/', '/panel.css', '/panel.js'):
                    filename, ctype = {'/': ('index.html', 'text/html; charset=utf-8'), '/panel.css': ('panel.css', 'text/css; charset=utf-8'), '/panel.js': ('panel.js', 'text/javascript; charset=utf-8')}[self.path]
                    self.respond(200, Path(__file__).with_name(filename).read_text(), ctype)
                elif self.path == '/api/state':
                    visible = inventory()
                    nodes = [{'name': 'TX-01', 'role': 'Transmisor', 'status': 'EXTERNAL_POWER_NOT_VERIFIED', 'usb_serial': None, 'ports': [], 'uart_opened': False}]
                    for role in ROLES:
                        serial = store.profile['receivers'][role]
                        matches = [d for d in visible if d['usb_serial'] == serial]
                        status = 'USB_IDENTITY_AMBIGUOUS' if len(matches) > 1 else 'USB_VISIBLE_UART_CLOSED' if matches else 'USB_NOT_OBSERVED'
                        nodes.append({'name': role, 'role': 'Receptor CSI', 'status': status, 'usb_serial': serial,
                                      'ports': [d['path'] for d in matches], 'uart_opened': False})
                    self.respond(200, {'service': 'tesis-local-control-panel', 'version': '0.1.0',
                                      'mode': 'CONFIGURATION_DRAFTS_ONLY', 'nodes': nodes,
                                      'defaults': store.defaults(), 'source_profile_sha256': store.source_sha256,
                                      'idf_version': store.profile['idf_version'], 'drafts': store.list(),
                                      'capabilities': {'usb_inventory_read_only': True, 'draft_profiles': True,
                                                       'capture': False, 'flash': False, 'apply_to_esp': False,
                                                       'presence_detection': False, 'csi_visualizer_connected': False}})
                elif self.path.startswith('/api/drafts/') and self.path.endswith('/export'):
                    ident = self.path[len('/api/drafts/'):-len('/export')]
                    self.respond(200, store.load(ident), filename='perfil-borrador-' + ident + '.json')
                else:
                    self.respond(404, {'error': 'Ruta no disponible.'})
            except (ValueError, OSError) as exc:
                self.respond(400, {'error': str(exc)})

        def do_POST(self):
            if not self.local_request():
                return
            if self.path != '/api/drafts':
                self.respond(404, {'error': 'Acción no implementada.'})
                return
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                self.respond(415, {'error': 'Se requiere JSON.'})
                return
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 16384:
                    raise ValueError('Tamaño de solicitud no permitido.')
                payload = json.loads(self.rfile.read(size))
                self.respond(201, store.save(payload))
            except (ValueError, OSError) as exc:
                self.respond(400, {'error': str(exc)})

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.daemon_threads = True
    server.store = store
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8090)
    parser.add_argument('--profile', type=Path, default=ROOT / 'config/csi_esp32s3.json')
    parser.add_argument('--state-dir', type=Path, default=ROOT / 'results/local/control-panel')
    args = parser.parse_args()
    try:
        server = make_server(args.profile, args.state_dir, args.port)
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(2, str(exc) + '\n')
    print(f'Panel local: http://127.0.0.1:{server.server_port} | solo borradores; UART cerradas', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
