#!/usr/bin/env python3
"""Local Firefox/Marionette QA of the standalone replay, with localhost-only control.

Reuses the protocol of check_offline_browser.py. No WebDriver installation,
web server or external browsing is needed. Does not disable the browser sandbox.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time


def check(page,output,browser):
    output.mkdir(parents=True,exist_ok=False)
    profile=output/'profile';profile.mkdir()
    with socket.socket() as probe:probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
    prefs={'marionette.port':port,'marionette.host':'127.0.0.1',
        'browser.shell.checkDefaultBrowser':False,'browser.startup.firstrunSkipsHomepage':True,
        'network.captive-portal-service.enabled':False,'network.connectivity-service.enabled':False,
        'datareporting.policy.dataSubmissionEnabled':False,'toolkit.telemetry.enabled':False,
        'network.proxy.type':1,'network.proxy.http':'127.0.0.1','network.proxy.http_port':9,
        'network.proxy.ssl':'127.0.0.1','network.proxy.ssl_port':9,'network.proxy.no_proxies_on':'localhost,127.0.0.1'}
    (profile/'user.js').write_text(''.join('user_pref('+json.dumps(k)+','+json.dumps(v)+');\n' for k,v in prefs.items()))
    log=(output/'browser.log').open('x')
    proc=subprocess.Popen([browser,'--headless','--no-remote','--marionette','--profile',str(profile.resolve()),'about:blank'],stdout=log,stderr=log,env=dict(os.environ,MOZ_HEADLESS='1',NO_AT_BRIDGE='1'))
    client=None
    try:
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            try:client=socket.create_connection(('127.0.0.1',port),timeout=.5);break
            except OSError:time.sleep(.1)
        if client is None:raise RuntimeError('Firefox did not start localhost Marionette; see browser.log')
        client.settimeout(20)
        def receive():
            length=b''
            while (c:=client.recv(1))!=b':':
                if not c:raise RuntimeError('Browser connection closed')
                length+=c
            data=b''
            while len(data)<int(length):data+=client.recv(int(length)-len(data))
            return json.loads(data)
        receive();serial=0
        def call(name,params=None):
            nonlocal serial
            serial+=1;data=json.dumps([0,serial,name,params or {}]).encode();client.sendall(str(len(data)).encode()+b':'+data)
            reply=receive()
            if reply[2]:raise RuntimeError(str(reply[2]))
            value=reply[3];return value.get('value',value) if isinstance(value,dict) else value
        call('WebDriver:NewSession',{'capabilities':{'alwaysMatch':{}}})
        call('WebDriver:SetWindowRect',{'width':1500,'height':1200})
        call('WebDriver:Navigate',{'url':page.resolve().as_uri()})
        def js(script):return call('WebDriver:ExecuteScript',{'script':script,'args':[]})
        state=js('return {rendered:document.documentElement.dataset.rendered,state:window.replayState(),panels:document.querySelectorAll(".panel").length,canvases:document.querySelectorAll("canvas").length,text:document.body.innerText};')
        assert state['rendered']=='true' and state['panels']==2 and state['canvases']==6,state
        assert 'REPRODUCCIÓN OFFLINE' in state['text'] and 'SIN DETECTOR CALIBRADO' in state['text']
        assert 'Conexión completa: rechazada' in state['text'] and 'Ventana: elegible exploratoria' in state['text']
        shot=call('WebDriver:TakeScreenshot',{'id':None,'highlights':[],'full':True})
        (output/'demo-desktop.png').write_bytes(base64.b64decode(shot))
        js('document.getElementById("restart").click();document.getElementById("play").click();return true;')
        time.sleep(.3)
        advancing=js('return window.replayState();');assert advancing['playing'] and advancing['cursor']>0,advancing
        js('document.getElementById("play").click();return true;')
        paused=js('return window.replayState();');time.sleep(.15)
        assert js('return window.replayState().cursor;')==paused['cursor']
        js('const s=document.getElementById("speed");s.value="4";document.getElementById("play").click();return true;')
        time.sleep(.25)
        fast=js('return window.replayState();');assert fast['cursor']>paused['cursor']+.5
        js('document.getElementById("play").click();document.getElementById("session").value="C03";document.getElementById("session").dispatchEvent(new Event("change"));document.getElementById("condition").value="S";document.getElementById("condition").dispatchEvent(new Event("change"));document.getElementById("time").value=30;document.getElementById("time").dispatchEvent(new Event("input"));return true;')
        switched=js('return {state:window.replayState(),first:document.querySelector(".panel h2").textContent,counts:[...document.querySelectorAll(".count")].map(x=>x.textContent)};')
        assert switched['first'].startswith('C03') and switched['counts']==['146 / 146','150 / 150'],switched
        assert switched['state']['scales']==state['state']['scales']
        js('document.getElementById("compare").click();return true;')
        assert js('return document.querySelectorAll(".panel").length;')==1
        js('document.getElementById("restart").click();return true;')
        assert js('return window.replayState().cursor;')==0
        call('WebDriver:SetWindowRect',{'width':430,'height':900})
        js('document.getElementById("time").value=30;document.getElementById("time").dispatchEvent(new Event("input"));return true;')
        assert js('return document.documentElement.scrollWidth<=window.innerWidth+1;')
        shot=call('WebDriver:TakeScreenshot',{'id':None,'highlights':[],'full':True})
        (output/'demo-mobile.png').write_bytes(base64.b64decode(shot))
        report=dict(browser='Firefox',control_host='127.0.0.1',http_server=False,external_browsing=False,
            initial=state['state'],play_pause_verified=True,speed_verified=True,switching_verified=switched,
            common_scales_verified=True,restart_verified=True,mobile_overflow=False,screenshots=['demo-desktop.png','demo-mobile.png'])
        (output/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(report,ensure_ascii=False))
    finally:
        if client:client.close()
        proc.terminate()
        try:proc.wait(timeout=5)
        except subprocess.TimeoutExpired:proc.kill();proc.wait()
        log.close()


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('page',type=Path);ap.add_argument('--output-new',type=Path,required=True)
    ap.add_argument('--browser',default='/snap/firefox/current/usr/lib/firefox/firefox');a=ap.parse_args()
    check(a.page,a.output_new,a.browser)


if __name__=='__main__':main()
