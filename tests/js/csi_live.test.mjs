// Actual shared charts with a simulated DOM/network; not a real browser check.
import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
let clears=0,marks=0;
const ctx=new Proxy({}, {get:(o,k)=>o[k]??((...args)=>{for(const x of args)if(typeof x==='number')assert(Number.isFinite(x));if(k==='clearRect')clears++;if(k==='fillRect')marks++;}),set:(o,k,v)=>(o[k]=v,true)});
class Element{constructor(){this.textContent='';this.dataset={};this.hidden=false;this.width=1100;this.height=360;this.events={};}addEventListener(k,f){this.events[k]=f;}getContext(){return ctx;}}
const physical=process.env.CSI_PHYSICAL==='1';
const evidence=physical?'physical_capture':'synthetic_fixture';
const elements=Object.fromEntries(['heat','rssi','state','reason','last','loss','blank','details','pause','refresh','audit'].map(k=>[k,new Element()]));
const events={};const document={hidden:false,body:{dataset:{source:evidence}},getElementById:k=>elements[k],addEventListener:(k,f)=>events[k]=f};
let clock=0,payload={schema:'csi-live-preview-1',mode:physical?'CSI PROVISIONAL · RX-02':'SIMULADO · SIN ESP',evidence_type:evidence,attempt_id:physical?'RX02-DIAG-VISOR-240S-R1':undefined,observer_id:'observer-1',revision:1,
 flow_state:'esperando',reason:'Waiting for fixture',last_sample_ns:null,sample_age_ms:null,stale_after_ms:2000,rows:[],rows_discarded_view:0,invalid_lines:0,window_T0_ns:'10000000000'};
const requests=[];let failure=false,hang=false;const timers=new Map();let serial=0,interval;
const sandbox={document,console,BigInt,performance:{now:()=>clock},AbortController,
 setTimeout:f=>{timers.set(++serial,f);return serial;},clearTimeout:id=>timers.delete(id),setInterval:f=>{interval=f;},
 fetch:async(url,options)=>{requests.push([url,options]);if(failure)throw Error('browser disconnected');
  if(hang)return new Promise((_,reject)=>options.signal.addEventListener('abort',()=>reject(Error('timeout'))));
  return {ok:true,json:async()=>structuredClone(payload)};}};
vm.createContext(sandbox);
const legacy=fs.readFileSync('src/offline_view.mjs','utf8').replace("if(typeof document!=='undefined'){initialize(JSON.parse(document.getElementById('csi-data').textContent));}",'');
const code=legacy+'\n'+fs.readFileSync('src/csi_charts.mjs','utf8')+'\n'+fs.readFileSync('src/csi_live.mjs','utf8').replace("import {makeCsiCharts} from '/charts.mjs';",'');
await vm.runInContext(code.replace(/export /g,''),sandbox);
const poll=()=>vm.runInContext('poll()',sandbox),paint=()=>vm.runInContext('paint()',sandbox);
assert.equal(elements.state.dataset.state,'esperando');assert(!elements.blank.hidden);assert.equal(marks,0);
const row={t_ns:'39900000000',rssi:-51,amplitudes:Array(52).fill(5),hardware_valid:Array(64).fill(true),cfr_usable:Array(64).fill(true)};
payload={...payload,revision:2,flow_state:'recibiendo',rows:[row],last_sample_ns:row.t_ns,sample_age_ms:100};
await poll();assert.equal(elements.state.dataset.state,'recibiendo');assert(elements.blank.hidden);assert(marks>=52);
const originalStamp=elements.last.textContent;clock+=2100;const beforeClears=clears;paint();
assert.equal(elements.state.dataset.state,'datos_antiguos');assert(!elements.blank.hidden);assert(clears>beforeClears);
assert(elements.last.textContent.includes(row.t_ns));assert.notEqual(elements.last.textContent,originalStamp);
failure=true;await poll();assert(!elements.blank.hidden);assert.equal(elements.state.dataset.state,'datos_antiguos');
failure=false;payload={...payload,revision:7,sample_age_ms:0,rows_discarded_view:12};
await poll();assert.equal(elements.state.dataset.state,'recibiendo');assert.match(elements.loss.textContent,/12.*4/);
elements.pause.events.click();assert.equal(elements.state.dataset.state,'datos_antiguos');assert(!elements.blank.hidden);
const n=requests.length;await poll();assert.equal(requests.length,n,'Paused view cannot control or poll producer');
payload={...payload,revision:10};elements.pause.events.click();await new Promise(setImmediate);
assert.equal(elements.state.dataset.state,'recibiendo');assert(elements.blank.hidden);
document.hidden=true;clock+=2500;events.visibilitychange();const hiddenCalls=requests.length;await poll();
assert.equal(requests.length,hiddenCalls);assert.equal(elements.state.dataset.state,'datos_antiguos');
document.hidden=false;payload={...payload,revision:15,sample_age_ms:0};events.visibilitychange();await new Promise(setImmediate);
assert.equal(elements.state.dataset.state,'recibiendo');
// A restarted observer replaying old samples must never freshen their age.
payload={...payload,observer_id:'observer-2',revision:1,sample_age_ms:4000};await poll();
assert.equal(elements.state.dataset.state,'datos_antiguos');assert(!elements.blank.hidden);
payload={...payload,revision:2,sample_age_ms:0,flow_state:'detenido',reason:'Synthetic source closed'};await poll();
assert.equal(elements.state.dataset.state,'detenido');assert(!elements.blank.hidden);
payload={...payload,flow_state:'recibiendo',evidence_type:physical?'synthetic_fixture':'physical_capture'};await poll();assert(!elements.blank.hidden);
payload={...payload,evidence_type:evidence,rows:[{...row,t_ns:'invalid'}]};await poll();assert(!elements.blank.hidden);
payload={...payload,revision:3,rows:[row],sample_age_ms:0};await poll();assert(elements.blank.hidden,'Valid preview recovers after malformed response');
hang=true;const pending=poll(),nRequests=requests.length;await poll();assert.equal(requests.length,nRequests);
clock+=2100;paint();assert(!elements.blank.hidden,'Freshness must expire while a request is stalled');
[...timers.values()][0]();await pending;assert(!elements.blank.hidden);
assert(requests.every(([url])=>url==='/api/stream'));assert.equal(timers.size,0);
if(physical){
 hang=false;payload={...payload,attempt_id:'OTHER'};await poll();assert(!elements.blank.hidden);
 payload={...payload,attempt_id:'RX02-DIAG-VISOR-240S-R1',flow_state:'detenido',physical_close_verified:true};await poll();
 assert.match(elements.audit.textContent,/Cierre verificado/);
 assert(fs.readFileSync('src/rx02_live.html','utf8').includes('data-source="physical_capture"'));
}
const html=fs.readFileSync('src/csi_live.html','utf8');
assert(html.includes('SIMULADO · SIN ESP'));assert(html.includes('futura adquisición física está deshabilitada'));
assert(html.includes('reproducción histórica'));assert(!html.includes('id="capture"'));
console.log(JSON.stringify({checks:'passed',shared_charts:true,waiting_receiving_stale_stopped:true,
 stale_traces_cleared:true,pause_resume:true,browser_disconnect_recovery:true,old_samples_after_observer_restart:true,
 visual_drop_counters:true,source_mode: evidence,other_source_rejected:true,malformed_response_recovery:true,timeout:true,actual_browser:false}));
