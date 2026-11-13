#!/usr/bin/env python3
"""Build a self-contained C01/C03 replay. No network, UART, model or reserve input.

Optional HTTP serving binds 127.0.0.1 and exposes only the generated artifact.
"""
import argparse
import hashlib
import html
import json
import math
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools')]
from presence_offline import ACTIVE, INDICES
from csi_chart_bundle import chart_module
from eligible_presence_features import extract_eligible_window

SESSIONS={'C01':'results/local/piloto-rx02-r1-C01',
          'C03':'results/local/piloto-rx02-r1-C03-checkpoint-r1'}
DEFAULT=ROOT/'results/local/demo-offline-c01-c03-shared-live-r1'


def fingerprint(path):
    data=Path(path).read_bytes()
    return dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())


def guard(event,args):
    if event=='open' and isinstance(args[0],(str,bytes)):
        path=str(args[0])
        if re.search(r'C0[456]',path,re.I) or path.startswith(('/dev/serial','/dev/ttyACM','/dev/ttyUSB')):
            raise PermissionError('Forbidden input: reserved data or serial device')


def cumulative_sigma(values):
    n=0;mean=m2=0.;out=[];incomplete=False
    for value in values:
        if value is None:incomplete=True
        if incomplete:out.append(None);continue
        n+=1;delta=value-mean;mean+=delta/n;m2+=delta*(value-mean)
        out.append(math.sqrt(max(0,m2/n)) if n>=2 else None)
    return out


def build_data():
    from presence_rx02_journal import audit_rx02
    from rx02_c03.checkpoint import audit_c03_checkpoints
    from consolidar_c03_comparar_c01 import describe_windows
    sessions=[];protected={};all_amplitudes=[];all_rssi=[];all_sigma=[]
    for sid,relative in SESSIONS.items():
        root=ROOT/relative
        # Only explicitly allowlisted connections; no discovery of other data.
        manifest=json.loads((root/'manifest.json').read_text())
        before={str(p.relative_to(ROOT)):fingerprint(p) for p in root.rglob('*') if p.is_file()}
        audit=audit_rx02(root) if sid=='C01' else audit_c03_checkpoints(root)
        windows,observations,traces=describe_windows(root,audit)
        state=audit['state'];entries=[]
        for condition in ('E','S'):
            w=windows[condition];frames=traces[condition]
            feature=extract_eligible_window(audit,w['slot_id'],frames)
            if feature['feature_status']!='evaluable':raise ValueError(feature['reasons'])
            rows=[]
            for frame,scalar in zip(frames,feature['row_features']):
                block=frame['blocks'][0];ref=frame['window_reference']
                amplitudes=[block['amplitude'][INDICES.index(k)] if block['cfr_usable'][INDICES.index(k)] else None
                            for k in sorted(ACTIVE)]
                rows.append(dict(t_ns=str(ref['returned_ns']),
                    first_read_ns=str(ref['first_read_started_ns']),local_timestamp_us=str(ref['local_timestamp']),
                    callback_id=ref['id'],reference=ref,rssi=int(frame['original_fields']['rssi']),
                    amplitudes=amplitudes,hardware_valid=block['hardware_valid'],cfr_usable=block['cfr_usable'],
                    mean=scalar['value']))
                all_amplitudes.extend(x for x in amplitudes if x is not None);all_rssi.append(rows[-1]['rssi'])
            sigma=cumulative_sigma([row['mean'] for row in rows])
            for row,value in zip(rows,sigma):row['sigma_prefix']=value
            all_sigma.extend(x for x in sigma if x is not None)
            entries.append(dict(condition=condition,id=w['slot_id'],T0_ns=w['T0_ns'],T1_ns=w['T1_ns'],
                label=w['label'],coverage=w['coverage'],eligibility=w['exploratory'],
                window_quality_ok=w['window_quality_ok'],strict_eligible=w['original_strict_eligible'],
                masks_complete=w['mask_status']=='complete',features=feature['features'],rows=rows))
        sessions.append(dict(id=sid,connection_id=state['connection_id'],receiver='RX-02',usb_serial='5C93200689',
            partition_group=state['partition_group'],connection=state['connection'],
            integrity_ok=audit['integrity_ok'],replay_ok=audit['replay_ok'],windows=entries,
            source_bundle=relative,source_manifest=fingerprint(root/'manifest.json'),
            acquisition_provenance=json.loads((root/'provenance.json').read_text())))
        assert before=={name:fingerprint(ROOT/name) for name in before}
        protected.update(before)
    return dict(schema='offline-replay-C01-C03-1',mode='REPRODUCCIÓN OFFLINE',detector='SIN DETECTOR CALIBRADO',
        tone_indices=sorted(ACTIVE),mask_index_order=INDICES,sessions=sessions,
        scales=dict(amplitude=[0,max(all_amplitudes)],rssi=[min(all_rssi)-1,max(all_rssi)+1],
                    sigma=[0,max(all_sigma)*1.05],time=[0,30]),
        definitions=dict(amplitude='hypot(Re,Im), int8 sin calibrar; 52 tonos LLTF activos, DC/guardas excluidos.',
            rssi='RSSI original por fila, dBm; puntos sin unir ni remuestrear.',
            variability='Desviación estándar poblacional acumulada de las medias LLTF52 por fila observada hasta t; no evaluable con menos de dos filas.',
            timestamps='Tiempo host de retorno, relativo al T0 original; no es reloj RF.',
            heatmap='CSI, no ubicación humana. Cada marca ocupa un instante observado; espacios vacíos no se rellenan.'),
        protected_sources=protected,calibration_executed=False,inference_executed=False,reserve_opened=False)


def build(output):
    output=Path(output).resolve()
    if not output.is_relative_to(ROOT/'results/local'):raise ValueError('Use salida local dentro de results/local')
    if output.exists():
        manifest=json.loads((output/'manifest.json').read_text())
        if any(fingerprint(output/name)!=value for name,value in manifest['artifacts'].items()):raise ValueError('Artefacto alterado; conservar y usar --output-new')
        if any(fingerprint(ROOT/name)!=value for name,value in manifest['sources'].items()):raise ValueError('Fuentes cambiaron; use --output-new para regenerar sin sobrescribir')
        if any(fingerprint(ROOT/name)!=value for name,value in manifest['original_data'].items()):raise ValueError('Un original cambió; conservar y revisar antes de reproducir')
        return output/'index.html'
    data=build_data()
    source_names=['tools/demo_offline.py','src/eligible_presence_features.py','src/presence_offline.py',
        'src/ruview_presence_port.py','src/canonical_csi.py','src/csi_correspondence.py',
        'src/offline_view.mjs','src/csi_charts.mjs','src/csi_chart_bundle.py','src/replay_demo.html','src/replay_demo.mjs',
        'tools/consolidar_rx02_c01.py','tools/consolidar_c03_comparar_c01.py']
    sources={name:fingerprint(ROOT/name) for name in source_names}
    reused=chart_module()
    payload=json.dumps(data,ensure_ascii=False,allow_nan=False,separators=(',',':')).replace('<','\\u003c')
    template=(ROOT/'src/replay_demo.html').read_text()
    page=template.replace('__REPLAY_DATA__',payload).replace('__REPLAY_JS__',reused+'\n'+(ROOT/'src/replay_demo.mjs').read_text())
    output.mkdir(parents=True,exist_ok=False)
    with (output/'index.html').open('x') as f:f.write(page)
    with (output/'data.json').open('x') as f:json.dump(data,f,ensure_ascii=False,allow_nan=False);f.write('\n')
    with (output/'manifest.json').open('x') as f:json.dump(dict(sources=sources,
        original_data=data['protected_sources'],artifacts={n:fingerprint(output/n) for n in ('index.html','data.json')},
        transformation='Existing offline_view.mjs helpers embedded without automatic initialize; no external imports.',
        physical_UART_opened=False,inference_executed=False),f,ensure_ascii=False,indent=2);f.write('\n')
    return output/'index.html'


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-new',type=Path,default=DEFAULT)
    ap.add_argument('--serve',action='store_true',help='Opcional: solo 127.0.0.1, sin exponer el repositorio')
    ap.add_argument('--port',type=int,default=8765)
    args=ap.parse_args(argv)
    sys.addaudithook(guard)
    page=build(args.output_new)
    print('REPRODUCCIÓN OFFLINE · SIN DETECTOR CALIBRADO\n'+page.as_uri(),flush=True)
    if args.serve:
        from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
        from functools import partial
        server=ThreadingHTTPServer(('127.0.0.1',args.port),partial(SimpleHTTPRequestHandler,directory=str(page.parent)))
        print(f'http://127.0.0.1:{server.server_port}/index.html',flush=True)
        try:server.serve_forever()
        except KeyboardInterrupt:pass
        finally:server.server_close()
    return 0


if __name__=='__main__':raise SystemExit(main())
