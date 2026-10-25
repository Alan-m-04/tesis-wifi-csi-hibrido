#!/usr/bin/env python3
"""Optional Firefox/Marionette smoke test; TCP control binds only 127.0.0.1.

Run inside the documented isolated browser sandbox. No UDP, HTTP server or downloads.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import socket
import subprocess
import time


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('bundle',type=Path);ap.add_argument('--browser',default='/snap/firefox/current/usr/lib/firefox/firefox');args=ap.parse_args()
    bundle=args.bundle.resolve();qa=bundle/'browser-qa';qa.mkdir(exist_ok=False)
    canonical=json.loads((bundle/'canonical.json').read_text())
    expected_status=canonical['status_label']
    expected_rows={rx:len(value['frames']) for rx,value in canonical['receivers'].items()}
    profile=qa/'profile';profile.mkdir()
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
    prefs={'marionette.port':port,'marionette.host':'127.0.0.1','browser.shell.checkDefaultBrowser':False,
           'browser.startup.homepage_override.mstone':'ignore','browser.startup.firstrunSkipsHomepage':True,
           'network.captive-portal-service.enabled':False,'network.connectivity-service.enabled':False,
           'datareporting.policy.dataSubmissionEnabled':False,'toolkit.telemetry.enabled':False,
           'security.sandbox.content.level':0,'layers.acceleration.disabled':True,
           'gfx.webrender.force-disabled':True,'gfx.canvas.accelerated':False}
    (profile/'user.js').write_text(''.join('user_pref('+json.dumps(k)+','+json.dumps(v)+');\n' for k,v in prefs.items()))
    env=dict(os.environ,MOZ_HEADLESS='1',MOZ_DISABLE_CONTENT_SANDBOX='1',MOZ_DISABLE_RDD_SANDBOX='1',MOZ_DISABLE_GPU_SANDBOX='1',NO_AT_BRIDGE='1')
    log=(qa/'firefox.log').open('w')
    proc=subprocess.Popen([args.browser,'--headless','--no-remote','--marionette','--profile',str(profile),'about:blank'],env=env,stdout=log,stderr=log)
    client=None
    try:
        end=time.monotonic()+20
        while time.monotonic()<end:
            try:client=socket.create_connection(('127.0.0.1',port),timeout=.5);break
            except OSError:time.sleep(.1)
        if client is None:raise RuntimeError('Firefox did not expose localhost Marionette in 20 s')
        client.settimeout(25)
        def receive():
            length=b''
            while (char:=client.recv(1))!=b':':
                if not char:raise RuntimeError('Browser connection closed')
                length+=char
            payload=b''
            while len(payload)<int(length):payload+=client.recv(int(length)-len(payload))
            return json.loads(payload)
        receive();serial=0
        def call(name,params=None):
            nonlocal serial
            serial+=1;raw=json.dumps([0,serial,name,params or {}]).encode();client.sendall(str(len(raw)).encode()+b':'+raw)
            response=receive()
            if response[2]:raise RuntimeError(str(response[2]))
            value=response[3]
            return value.get('value',value) if isinstance(value,dict) else value
        session=call('WebDriver:NewSession',{'capabilities':{'alwaysMatch':{'acceptInsecureCerts':False}}})
        call('WebDriver:SetWindowRect',{'width':1500,'height':1200})
        report={'control_host':'127.0.0.1','http_server':False,'udp':False,'views':{},'browser_session':session}
        for rx in ('RX-01','RX-02'):
            for ltf in ('LLTF','HT-LTF'):
                url=(bundle/'index.html').as_uri()+'?rx='+rx+'&ltf='+ltf
                call('WebDriver:Navigate',{'url':url})
                state=call('WebDriver:ExecuteScript',{'script':'''return {rendered:document.documentElement.dataset.rendered,status:document.getElementById('status').textContent,rx:document.getElementById('rx').value,ltf:document.getElementById('ltf').value,max:document.getElementById('frame').max,charts:[...document.querySelectorAll('svg')].map(s=>s.children.length),sigmaPoints:document.querySelectorAll('#variability circle').length,identity:document.getElementById('identity').textContent,sample:document.getElementById('sample').textContent,connection:document.getElementById('connection-state')?.textContent,window:document.getElementById('window-state')?.textContent,coverage:document.getElementById('coverage')?.textContent};''','args':[]})
                populated=expected_rows[rx]>0
                if (state.get('rendered')!='true' or state['status']!=expected_status or
                        int(state['max'])!=max(0,expected_rows[rx]-1) or state['rx']!=rx or state['ltf']!=ltf or
                        not all(x>(10 if populated else 3) for x in state['charts']) or
                        state['sigmaPoints']!=((52 if ltf=='LLTF' else 56) if populated else 0)):
                    raise RuntimeError('UI assertion failed: '+str(state))
                if canonical.get('nominal_window'):
                    count=canonical['nominal_window']['counts_and_stops'][rx]
                    last=canonical['receivers'][rx]['frames'][-1]
                    if (f"ventana nominal: {count['common_window_rows']} filas" not in state['identity'] or
                            f"fase: {last['timing_phase']}" not in state['sample'] or
                            f"dentro de {canonical['nominal_window']['seconds']} s nominales: {'sí' if last['received_in_common_window'] else 'no'}" not in state['sample']):
                        raise RuntimeError('Nominal/late row display mismatch: '+str(state))
                if canonical.get('experimental_window'):
                    w=canonical['experimental_window'];last=canonical['receivers'][rx]['frames'][-1] if populated else None
                    if (state['connection'] != 'Conexión completa: '+canonical['connection_full']['status'] or
                            state['window'] != 'Ventana experimental: '+w['status'] or
                            (last is not None and f"inclusión: {last['timing_phase']}" not in state['sample']) or
                            f"{w['receivers'][rx]['coverage']['included_rows']} filas incluidas" not in state['coverage']):
                        raise RuntimeError('Separate v3 scopes not visible: '+str(state))
                # Exercise sample selection; input events must not create or resample rows.
                moved=call('WebDriver:ExecuteScript',{'script':"const s=document.getElementById('frame');s.value=0;s.dispatchEvent(new Event('input'));return {value:s.value,sample:document.getElementById('sample').textContent};",'args':[]})
                if moved['value']!='0' or (populated and 'Fila CSV 2' not in moved['sample']) or (not populated and 'Sin muestras' not in moved['sample']):raise RuntimeError('Slider did not preserve original row mapping')
                shot=call('WebDriver:TakeScreenshot',{'id':None,'highlights':[],'full':True})
                name=rx.lower()+'-'+ltf.lower()+'.png';(qa/name).write_bytes(base64.b64decode(shot))
                report['views'][rx+'/'+ltf]=dict(state,screenshot=name,slider=moved)
        (qa/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps({k:v for k,v in report.items() if k!='browser_session'},indent=2))
    finally:
        if client:client.close()
        proc.terminate()
        try:proc.wait(timeout=5)
        except subprocess.TimeoutExpired:proc.kill();proc.wait()
        log.close()


if __name__=='__main__':main()
