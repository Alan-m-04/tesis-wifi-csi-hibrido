#!/usr/bin/env python3
"""Synthetic CSI over an owned PTY; observer and GUI run separately. No ESP needed."""
from collections import deque
from http.server import BaseHTTPRequestHandler,HTTPServer
import argparse
import json
import multiprocessing as mp
from pathlib import Path
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools')]
from csi_live_observer import observe,current_snapshot,atomic_json,guard,SharedFlag
from csi_synthetic_producer import produce
from csi_chart_bundle import chart_module


class ViewServer(HTTPServer):
    """One bounded response at a time; slow clients cannot spawn an unbounded queue."""
    request_queue_size=4
    def get_request(self):
        request,address=super().get_request();request.settimeout(1)
        return request,address


def handler(view, *, snapshot_reader=current_snapshot, page='csi_live.html'):
    class LiveHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.headers.get('Host') not in (f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'):
                self.send_error(403);return
            if self.path=='/api/stream':
                try:data=json.dumps(snapshot_reader(Path(view)/'latest.json'),ensure_ascii=False,allow_nan=False).encode()
                except (OSError,ValueError,KeyError,TypeError,RecursionError):self.send_error(503,'Preview unavailable');return
                kind='application/json'
            elif self.path=='/charts.mjs':data=chart_module().encode();kind='text/javascript'
            elif self.path in ('/','/live.mjs'):
                name=page if self.path=='/' else 'csi_live.mjs'
                data=(ROOT/'src'/name).read_bytes();kind='text/html' if self.path=='/' else 'text/javascript'
            else:self.send_error(404);return
            self.send_response(200);self.send_header('Content-Type',kind+'; charset=utf-8')
            self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store')
            self.send_header('Content-Security-Policy',"default-src 'none'; script-src 'self'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")
            try:self.end_headers();self.wfile.write(data)
            except OSError:pass  # Slow/disconnected browser never affects producer/observer.
        def do_POST(self):self.send_error(405,'Read-only viewer')
    return LiveHandler


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-new',type=Path)
    ap.add_argument('--seconds',type=float,default=18)
    ap.add_argument('--headless',action='store_true',help='Sin HTTP; verifica la demo y guarda instantáneas/resultados')
    ap.add_argument('--port',type=int,default=8767)
    ap.add_argument('--observe-synthetic',type=Path,help='Solo observar un bundle sintético de esta demo, nunca fuentes físicas')
    args=ap.parse_args(argv)
    if not 0<args.seconds<=120 or not 0<=args.port<=65535:ap.error('Duración 0..120 s y puerto válido requeridos')
    sys.addaudithook(guard)
    parent=ROOT/'results/local';parent.mkdir(exist_ok=True)
    selected=args.observe_synthetic.resolve() if args.observe_synthetic else None
    if args.output_new:
        out=args.output_new.resolve()
        if not out.is_relative_to(parent):ap.error('Use una ruta nueva dentro de results/local')
        if selected and (out.is_relative_to(selected) or selected.is_relative_to(out)):
            ap.error('La salida del visor debe estar fuera del original')
        out.mkdir(parents=True,exist_ok=False)
    else:
        if selected and parent.is_relative_to(selected):ap.error('La salida del visor debe estar fuera del original')
        out=Path(tempfile.mkdtemp(prefix='demo-csi-sintetico-',dir=parent))
    bundle=selected or out/'original'
    view=out/'view';view.mkdir()
    server=None
    if not args.headless:
        try:server=ViewServer(('127.0.0.1',args.port),handler(view));server.timeout=.1
        except OSError as exc:
            print('No se pudo abrir localhost: '+str(exc)+'; use --headless para la prueba sin servidor.',file=sys.stderr);return 1
    context=mp.get_context('spawn');stop_source=SharedFlag(context);stop_view=SharedFlag(context);ready=SharedFlag(context)
    producer=observer=None;states=set();transitions=deque(maxlen=32);last_state=None;finished_at=None
    started=time.monotonic();observer_restarts=0
    try:
        if args.observe_synthetic:
            from csi_live_observer import Observer
            check=Observer(bundle);check.close()  # Refuse physical/historical input before starting any worker.
        else:
            producer=context.Process(target=produce,args=(bundle,ready,stop_source),kwargs=dict(seconds=args.seconds),name='synthetic-PTY-producer')
            producer.start()
            if not ready.wait(10) or not (bundle/'provenance.json').is_file():raise RuntimeError('Synthetic producer did not initialize')
        observer=context.Process(target=observe,args=(bundle,view,stop_view),name='read-only-CSI-observer');observer.start()
        print('SIMULADO · SIN ESP · SIN DETECTOR CALIBRADO\nSalida: '+str(out),flush=True)
        if server:print(f'http://127.0.0.1:{server.server_port}/ · Ctrl-C cierra la demo; cerrar el navegador no detiene el productor.',flush=True)
        while True:
            if server:server.handle_request()
            else:time.sleep(.05)
            try:
                data=current_snapshot(view/'latest.json');state=data['flow_state'];states.add(state)
                if state!=last_state:
                    transitions.append(dict(state=state,at_seconds=time.monotonic()-started));last_state=state
                    print(state+' · filas='+str(data['rows_seen'])+' · descartes visor='+str(data['rows_discarded_view']),flush=True)
            except (OSError,ValueError,KeyError,TypeError,RecursionError):pass
            if not observer.is_alive() and observer_restarts<2:
                observer.join();observer_restarts+=1
                print('Reiniciando solo el observador; productor sin cambios.',flush=True)
                observer=context.Process(target=observe,args=(bundle,view,stop_view),name='read-only-CSI-observer')
                observer.start()
            if producer is not None and not producer.is_alive():
                if finished_at is None:finished_at=time.monotonic()
                if args.headless and time.monotonic()-finished_at>1:break
            if args.headless and time.monotonic()-started>args.seconds+12:break
    except KeyboardInterrupt:pass
    finally:
        stop_source.set()
        if producer is not None:
            producer.join(6)
            if producer.is_alive():producer.terminate();producer.join()
        stop_view.set()
        if observer is not None:
            observer.join(5)
            if observer.is_alive():observer.terminate();observer.join()
        if server:server.server_close()
        atomic_json(out/'demo-report.json',dict(mode='synthetic_fixture',states_seen=sorted(states),transitions=list(transitions),
            producer_exitcode=producer.exitcode if producer else None,observer_exitcode=observer.exitcode if observer else None,
            observer_restarts=observer_restarts,
            physical_UART_opened=False,physical_source_enabled=False,original=str(bundle),view=str(view)))
    return 0 if (producer is None or producer.exitcode==0) and observer is not None and observer.exitcode==0 else 1


if __name__=='__main__':raise SystemExit(main())
