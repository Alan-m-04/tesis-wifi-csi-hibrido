#!/usr/bin/env python3
"""Serve separate current-metadata and historical-replay pages on localhost."""
import argparse
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from device_metadata import catalogue,snapshot
from demo_offline import DEFAULT,build,guard as replay_guard


def no_serial_open(event,args):
    if event=='open' and isinstance(args[0],(str,bytes)):
        path=args[0].decode() if isinstance(args[0],bytes) else args[0]
        if path.startswith(('/dev/serial','/dev/tty')):
            raise PermissionError('El panel solo consulta metadatos; abrir UART está prohibido')


def handler(collect=snapshot,replay_html=None):
    class PanelHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            host=self.headers.get('Host','')
            if host not in (f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'):
                self.send_error(403,'Solo localhost');return
            replay=self.path=='/replay'
            if replay:
                if replay_html is None:self.send_error(503,'Prepare la reproducción offline antes de servirla');return
                data=replay_html;kind='text/html'
            elif self.path=='/api/devices':
                data=json.dumps(collect(),ensure_ascii=False,allow_nan=False).encode();kind='application/json'
            elif self.path in ('/','/panel.mjs'):
                name='device_panel.html' if self.path=='/' else 'device_panel.mjs'
                data=(ROOT/'src'/name).read_bytes();kind='text/html' if self.path=='/' else 'text/javascript'
                if self.path=='/':
                    expected=json.dumps(catalogue(),ensure_ascii=False).replace('<','\\u003c').encode()
                    data=data.replace(b'__DEVICE_CATALOGUE__',expected)
            else:self.send_error(404);return
            self.send_response(200)
            self.send_header('Content-Type',kind+'; charset=utf-8')
            self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            policy=("default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; connect-src 'none'; base-uri 'none'; frame-ancestors 'none'" if replay else
                "default-src 'none'; script-src 'self'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")
            self.send_header('Content-Security-Policy',policy)
            self.end_headers();self.wfile.write(data)
        def do_POST(self):self.send_error(405,'Solo lectura de metadatos')
    return PanelHandler


def make_server(port,collect=snapshot,replay_html=None):
    return ThreadingHTTPServer(('127.0.0.1',port),handler(collect,replay_html))


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--port',type=int,default=8766)
    ap.add_argument('--snapshot',action='store_true',help='JSON de consulta única, sin servidor')
    args=ap.parse_args(argv)
    if not 0<=args.port<=65535:ap.error('El puerto debe estar entre 0 y 65535')
    sys.addaudithook(no_serial_open)
    if args.snapshot:
        print(json.dumps(snapshot(),ensure_ascii=False,indent=2));return 0
    sys.addaudithook(replay_guard)
    try:
        replay_html=build(DEFAULT).read_bytes()
        server=make_server(args.port,replay_html=replay_html)
    except (OSError,ValueError) as exc:
        print('No se pudo iniciar el servidor localhost: '+str(exc),file=sys.stderr);return 1
    print(f'Panel de metadatos: http://127.0.0.1:{server.server_port}/\nReproducción histórica: http://127.0.0.1:{server.server_port}/replay\nSin UART ni recepción CSI actual. Ctrl-C para cerrar.',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
    return 0


if __name__=='__main__':raise SystemExit(main())
