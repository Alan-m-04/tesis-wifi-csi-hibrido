#!/usr/bin/env python3
"""Build a new local-only diagnostic bundle inside a network/device sandbox."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--inside-sandbox',action='store_true',help=argparse.SUPPRESS);args=ap.parse_args()
    out=args.output.resolve()
    if not out.is_relative_to(ROOT/'results/local'):
        raise SystemExit('Choose a NEW directory inside results/local; originals are read-only')
    if not args.inside_sandbox:
        out.mkdir(parents=True,exist_ok=False)
        cmd=['bwrap','--unshare-all','--die-with-parent','--ro-bind','/usr','/usr','--ro-bind','/lib','/lib','--ro-bind','/lib64','/lib64',
             '--ro-bind','/etc/ld.so.cache','/etc/ld.so.cache','--ro-bind','/etc/localtime','/etc/localtime',
             '--ro-bind',str(ROOT),str(ROOT),'--bind',str(out),str(out),'--proc','/proc','--dev','/dev','--tmpfs','/tmp',
             '--chdir',str(ROOT),'--setenv','HOME','/tmp','--setenv','PYTHONDONTWRITEBYTECODE','1',
             str(ROOT/'.venv/bin/python'),'-B',str(Path(__file__).resolve()),'--inside-sandbox','--output',str(out)]
        raise SystemExit(subprocess.run(cmd).returncode)
    if list(out.iterdir()):raise SystemExit('Output must be empty; refusing overwrites')
    sys.path.insert(0,str(ROOT/'src'))
    from canonical_csi import canonicalize
    manifest=json.loads((ROOT/'data/dual_60s_20261024.manifest.json').read_text())
    profile=json.loads((ROOT/'config/csi_esp32s3.json').read_text())
    source=ROOT/manifest['local_ignored_copy']
    canonical=canonicalize(source,manifest,profile)
    def write_json(name,data):
        with (out/name).open('x') as f:json.dump(data,f,ensure_ascii=False,allow_nan=False,separators=(',',':'))
    write_json('canonical.json',canonical)
    node=ROOT/'.tools/node-v22.20.0/bin/node'
    provenance=json.loads((ROOT/'vendor/ruview/PROVENANCE.json').read_text())
    for file,expected in [(ROOT/'vendor/ruview/esp32.js',provenance['sha256']),(node,provenance['node_binary_sha256'])]:
        with file.open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=expected:raise ValueError('Runtime or official module hash mismatch')
    p=subprocess.run([str(node),str(ROOT/'tools/consume_canonical.mjs'),str(out/'canonical.json')],capture_output=True,text=True,check=True)
    consumer=json.loads(p.stdout);write_json('ruview-consumer.json',consumer)
    originals=out/'originals';originals.mkdir()
    for item in manifest['files']:
        data=(source/item['name']).read_bytes()
        if hashlib.sha256(data).hexdigest()!=item['sha256']:raise ValueError('Original changed during export')
        with (originals/item['name']).open('xb') as f:f.write(data)
    script=(ROOT/'src/offline_view.mjs').read_text()
    data=json.dumps({'canonical':canonical,'consumer':consumer},ensure_ascii=False,allow_nan=False,separators=(',',':')).replace('<','\\u003c').replace('&','\\u0026')
    page='''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; connect-src 'none'; base-uri 'none'; form-action 'none'">
<title>CSI real · diagnóstico offline</title><style>
*{box-sizing:border-box}body{margin:0;background:#081220;color:#e6f0ff;font:14px system-ui,sans-serif}main{max-width:1450px;margin:auto;padding:24px}h1{font-size:25px;margin:0 0 10px}.status{background:#53252e;border:1px solid #ff8f9e;border-radius:8px;padding:12px;font-weight:700;color:#ffced5}p{line-height:1.5;color:#b6c9df}select,input{background:#17283e;color:#fff;border:1px solid #68809c;padding:8px;border-radius:5px}label{margin-right:20px}.toolbar{display:flex;align-items:center;flex-wrap:wrap;gap:12px;margin:15px 0}.toolbar input{flex:1;min-width:200px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:15px}svg{width:100%;border:1px solid #31465e;border-radius:8px}details{margin-top:16px;padding:12px;background:#111c2d;border:1px solid #31465e;border-radius:8px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;max-height:380px;overflow:auto}a{color:#7fdacf}.note{font-size:12px}.legend{color:#a6bbd3}.legend b{font-weight:400;color:#ffcc6a}@media(max-width:800px){.grid{grid-template-columns:1fr}}
</style><main><h1>CSI real · diagnóstico offline</h1><div id="status" class="status">captura histórica con validación estricta rechazada</div>
<p>Referencia dual de 60 s · 292 filas RX-01 / 291 RX-02. Sin presencia, entrenamiento ni conclusiones de precisión. El modelo LTF es documental y condicionado; no certifica el binario histórico ni sincronización RF.</p>
<div class="toolbar"><label>Receptor <select id="rx"><option>RX-01</option><option>RX-02</option></select></label><label>LTF <select id="ltf"><option>LLTF</option><option>HT-LTF</option></select></label><label for="frame">Fila registrada</label><input id="frame" type="range" min="0" value="0" step="1"></div>
<p id="identity"></p><p id="sample" class="note"></p><div class="grid"><svg id="rssi"></svg><svg id="amplitude"></svg><svg id="variability"></svg><svg id="history"></svg></div>
<p class="legend">Cian: tono activo · gris: guarda nominal · <b>amarillo: DC</b> · magenta: invalidez hardware. Fase desconocida en ceros. El historial sitúa cada marca en su timestamp host; no rellena intervalos ni inventa muestras. σ describe las amplitudes observadas con peso igual por fila, no estabilidad RF calibrada.</p>
<p id="official" class="note"></p><details><summary>Fila original, relojes y procedencia</summary><pre id="rowmeta"></pre></details>
<p class="note">Archivos completos locales: <a href="canonical.json">envoltorio canónico</a> · <a href="ruview-consumer.json">resultado oficial en memoria</a> · <a href="originals/rx-01.serial.log">bruto RX-01</a> · <a href="originals/rx-02.serial.log">bruto RX-02</a>. Nada se transmite; esta página funciona como archivo local.</p></main>
<script id="csi-data" type="application/json">'''+data+'''</script><script type="module">'''+script+'</script></html>'
    with (out/'index.html').open('x') as f:f.write(page)
    summary={'schema':'tesis-offline-view-validation-v1','status_label':canonical['status_label'],'strict_quality_ok':canonical['strict_quality_ok'],
             'node_version':subprocess.check_output([str(node),'--version'],text=True).strip(),'official_functions':consumer['official_functions'],
             'transport':'memory_buffers_only','server_started':False,'views':{},'files':{}}
    for name,v in consumer['views'].items():
        summary['views'][name]={k:v[k] for k in ('receiver_id','usb_serial','ltf','node_id','compared_amplitudes','compared_phases')}
        summary['views'][name].update(frames=len(v['frames']),shape=f"{v['frames'][0]['antennas']}x{v['frames'][0]['subcarriers']}",spectrum_frames=len(v['spectrum'][0]['frames']),rate_hz_host_span=v['spectrum'][0]['rateHz'])
    for file in [out/'canonical.json',out/'ruview-consumer.json',out/'index.html']:
        with file.open('rb') as f:summary['files'][file.name]={'bytes':file.stat().st_size,'sha256':hashlib.file_digest(f,'sha256').hexdigest()}
    write_json('validation.json',summary)
    print(out/'index.html')


if __name__=='__main__':main()
