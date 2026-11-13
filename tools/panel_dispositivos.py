#!/usr/bin/env python3
"""Serve separate current-metadata and historical-replay pages on localhost."""
import argparse
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from device_metadata import catalogue,snapshot
from demo_offline import DEFAULT,build,guard as replay_guard
from csi_sqlite_view import DEFAULT_DATABASE, read_sessions


def no_serial_open(event,args):
    if event=='open' and isinstance(args[0],(str,bytes)):
        path=args[0].decode() if isinstance(args[0],bytes) else args[0]
        if path.startswith(('/dev/serial','/dev/tty')):
            raise PermissionError('El panel solo consulta metadatos; abrir UART está prohibido')


def handler(collect=snapshot,replay_html=None,session_collect=read_sessions):
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
            elif self.path=='/api/sessions':
                try:
                    result=session_collect()
                except (OSError,ValueError,sqlite3.Error):
                    self.send_error(503,'SQLite o CSV no disponibles/verificables; no se importan datos');return
                data=json.dumps(result,ensure_ascii=False,allow_nan=False).encode();kind='application/json'
            elif self.path in ('/','/panel.mjs','/panel.css','/sessions','/sessions.mjs'):
                name,kind={'/':('device_panel.html','text/html'),'/panel.mjs':('device_panel.mjs','text/javascript'),
                    '/panel.css':('device_panel.css','text/css'),'/sessions':('sqlite_sessions.html','text/html'),
                    '/sessions.mjs':('sqlite_sessions.mjs','text/javascript')}[self.path]
                data=(ROOT/'src'/name).read_bytes()
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
                "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")
            self.send_header('Content-Security-Policy',policy)
            self.end_headers();self.wfile.write(data)
        def do_POST(self):self.send_error(405,'Solo lectura')
    return PanelHandler


def make_server(port,collect=snapshot,replay_html=None,database_path=DEFAULT_DATABASE):
    return ThreadingHTTPServer(('127.0.0.1',port),handler(collect,replay_html,lambda:read_sessions(database_path)))


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--port',type=int,default=8766)
    ap.add_argument('--snapshot',action='store_true',help='JSON de consulta única, sin servidor')
    ap.add_argument('--database',type=Path,default=DEFAULT_DATABASE,help='SQLite derivado; solo lectura, nunca crea/importa')
    ap.add_argument('--sin-replay',action='store_true',help='Omitir la preparación C01/C03; consultar /sessions sin leer esos bundles')
    args=ap.parse_args(argv)
    if not 0<=args.port<=65535:ap.error('El puerto debe estar entre 0 y 65535')
    sys.addaudithook(no_serial_open)
    if args.snapshot:
        print(json.dumps(snapshot(),ensure_ascii=False,indent=2));return 0
    sys.addaudithook(replay_guard)
    try:
        replay_html=None if args.sin_replay else build(DEFAULT).read_bytes()
        server=make_server(args.port,replay_html=replay_html,database_path=args.database)
    except (OSError,ValueError) as exc:
        print('No se pudo iniciar el servidor localhost: '+str(exc),file=sys.stderr);return 1
    print(f'Panel de metadatos: http://127.0.0.1:{server.server_port}/\nSesiones SQLite: http://127.0.0.1:{server.server_port}/sessions\nReproducción histórica: '+
          (f'http://127.0.0.1:{server.server_port}/replay' if replay_html is not None else 'omitida (--sin-replay)')+
          '\nSin UART ni recepción CSI actual. Ctrl-C para cerrar.',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
    return 0


if __name__=='__main__':raise SystemExit(main())
