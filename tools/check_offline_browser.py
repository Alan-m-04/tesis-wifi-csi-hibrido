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
                state=call('WebDriver:ExecuteScript',{'script':'''return {rendered:document.documentElement.dataset.rendered,status:document.getElementById('status').textContent,rx:document.getElementById('rx').value,ltf:document.getElementById('ltf').value,max:document.getElementById('frame').max,charts:[...document.querySelectorAll('svg')].map(s=>s.children.length),sigmaPoints:document.querySelectorAll('#variability circle').length};''','args':[]})
                if state.get('rendered')!='true' or state['status']!='captura histórica con validación estricta rechazada' or state['rx']!=rx or state['ltf']!=ltf or not all(x>10 for x in state['charts']) or state['sigmaPoints']!=(52 if ltf=='LLTF' else 56):raise RuntimeError('UI assertion failed: '+str(state))
                # Exercise sample selection; input events must not create or resample rows.
                moved=call('WebDriver:ExecuteScript',{'script':"const s=document.getElementById('frame');s.value=0;s.dispatchEvent(new Event('input'));return {value:s.value,sample:document.getElementById('sample').textContent};",'args':[]})
                if moved['value']!='0' or 'Fila CSV 2' not in moved['sample']:raise RuntimeError('Slider did not preserve original row mapping')
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
