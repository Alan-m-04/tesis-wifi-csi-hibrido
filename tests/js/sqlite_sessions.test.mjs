// DOM behavior with synthetic API responses. Python separately checks the real CSV/SQLite.
import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
class Element{
 constructor(){this.textContent='';this.children=[];this.dataset={};this.events={};this.disabled=false;this.hidden=false;}
 append(...nodes){this.children.push(...nodes);}replaceChildren(...nodes){this.children=nodes;this.textContent='';}
 addEventListener(name,fn){this.events[name]=fn;}
}
const elements=Object.fromEntries(['refresh','status','time','comparison','sessions','validation-details','quality-alert'].map(id=>[id,new Element()]));
const document={getElementById:id=>elements[id],createElement:()=>new Element()};
const text=node=>[node.textContent,...node.children.map(text)].join(' ');
const row={session_id:'RX02-DIAG-VISOR-240S-R1',receiver_id:'RX-02',duration_s:240.005564743,rows:1192,
 capture_frequency_hz:4.9792637522332885,max_host_gap_ms:614.782902,quality_status:'rejected',strict_quality_ok:0,
 preamble_rejected:true,quality_reasons:[{reason:'format:RX-02',count:20},{reason:'preamble_anomaly:RX-02',count:1}],
 integrity_ok:1,replay_ok:1,close_ok:1,diagnostic_ok:1};
const validPayload={schema:'csi-sqlite-dashboard-1',read_only:true,historical:true,live_capture:false,
 queried_at_utc:'2026-11-11T12:00:00+00:00',pilot_csv_comparison:{state:'matched'},sessions:[row]};
let payload=structuredClone(validPayload),error=null,httpStatus=200,hang=false;
const requests=[],timers=new Map();let timerId=0;
const fetch=async(url,options)=>{requests.push([url,options]);if(error)throw error;
 if(hang)return new Promise((_,reject)=>options.signal.addEventListener('abort',()=>reject(Error('Consulta vencida'))));
 return {ok:httpStatus===200,status:httpStatus,json:async()=>payload};};
const sandbox={document,fetch,AbortController,console,setTimeout:(fn,ms)=>{assert.equal(ms,12000);timers.set(++timerId,fn);return timerId;},clearTimeout:id=>timers.delete(id)};
vm.createContext(sandbox);
const source=fs.readFileSync('src/sqlite_sessions.mjs','utf8');
assert(!source.includes('innerHTML'),'Source strings must render as text');
await vm.runInContext(source.replace('export async function','async function'),sandbox);
assert.equal(elements.sessions.children.length,1);
const initial=text(elements.sessions);
for(const value of ['RX02-DIAG-VISOR-240S-R1','RX-02','240,005564743','1192','4,9792637522332885','614,782902','RECHAZADA · PREÁMBULO'])assert(initial.includes(value),value);
assert(!elements['quality-alert'].hidden);assert.match(elements['quality-alert'].textContent,/RECHAZADA POR PREÁMBULO/);
const details=text(elements['validation-details']);
assert.match(details,/format:RX-02.*×20/);assert.match(details,/preamble_anomaly:RX-02.*×1/);
assert.match(details,/Integridad: verificada.*Replay: verificado.*Cierre: confirmado.*Diagnóstico: conforme/);
assert.match(elements.comparison.textContent,/coinciden con su CSV/);
assert.match(elements.time.textContent,/2026-11-11T12:00:00/);assert(!elements.refresh.disabled);
// Other imported receivers remain separate rows; no merging by receiver alone.
payload={...validPayload,pilot_csv_comparison:{state:'not_present'},sessions:[{...row,session_id:'SYNTHETIC-SECOND'},row]};
await elements.refresh.events.click();assert.equal(elements.sessions.children.length,2);
// Unknown quality, insufficient cadence and empty databases are explicit, never approved.
payload={...validPayload,sessions:[{...row,quality_status:'unknown',strict_quality_ok:null,preamble_rejected:false,quality_reasons:[],capture_frequency_hz:null}]};
await elements.refresh.events.click();assert.match(text(elements.sessions),/NO REGISTRADA/);assert.match(text(elements.sessions),/No disponible/);
assert(elements['quality-alert'].hidden);
payload={...validPayload,pilot_csv_comparison:{state:'not_present'},sessions:[]};
await elements.refresh.events.click();assert.equal(elements.sessions.children.length,0);assert.match(elements.status.textContent,/base está vacía/);
assert.match(elements.comparison.textContent,/no está presente/);
// Source metadata is treated as plain text, including hostile markup.
payload={...validPayload,sessions:[{...row,quality_reasons:[...row.quality_reasons,{reason:'<img src=x onerror=alert(1)>',count:1}]}]};
await elements.refresh.events.click();assert(text(elements['validation-details']).includes('<img src=x onerror=alert(1)>'));
// Invalid responses and backend errors cannot leave a stale successful consultation visible.
for(const invalid of [
 {...validPayload,read_only:false}, {...validPayload,live_capture:true},
 {...validPayload,sessions:[row,row]}, {...validPayload,sessions:[{...row,strict_quality_ok:1}]},
 {...validPayload,sessions:[{...row,max_host_gap_ms:-1}]},
 {...validPayload,sessions:[{...row,preamble_rejected:false}]},
 {...validPayload,pilot_csv_comparison:{state:'mismatch'}},
]){
 payload=invalid;await elements.refresh.events.click();assert.equal(elements.sessions.children.length,0);
 assert.match(elements.status.textContent,/Sin datos verificables/);assert(elements['quality-alert'].hidden);
 assert.match(elements.comparison.textContent,/no verificado/);assert(!elements.refresh.disabled);
}
for(const failure of ['HTTP','network']){
 payload=validPayload;await elements.refresh.events.click();assert.equal(elements.sessions.children.length,1);
 httpStatus=failure==='HTTP'?503:200;error=failure==='network'?Error('backend unavailable'):null;
 await elements.refresh.events.click();assert.equal(elements.sessions.children.length,0);
 assert.equal(elements['validation-details'].children.length,0);assert.match(elements.status.textContent,/Sin datos verificables/);
 assert(!elements.refresh.disabled);
 httpStatus=200;error=null;
}
// A stalled request times out and concurrent clicks never start another request.
hang=true;const pending=elements.refresh.events.click();assert(elements.refresh.disabled);
const before=requests.length;await elements.refresh.events.click();assert.equal(requests.length,before);
assert.equal(timers.size,1);[...timers.values()][0]();await pending;
assert.equal(timers.size,0);assert(!elements.refresh.disabled);assert.equal(elements.sessions.children.length,0);
assert(requests.every(([url,options])=>url==='/api/sessions'&&options.cache==='no-store'&&!options.method));
const html=fs.readFileSync('src/sqlite_sessions.html','utf8');
for(const value of ['href="/panel.css"','href="/"','href="/replay"','SOLO LECTURA','MIPYME','R5-N01','C04–C06'])assert(html.includes(value),value);
console.log(JSON.stringify({checks:'passed',exact_metrics_display:true,preamble_rejection_visible:true,separate_validation_scopes:true,
 empty_and_unknown_states:true,stale_values_cleared:true,timeout_and_concurrency:true,text_rendering:true,
 manual_readonly_requests:true,shared_panel_navigation:true,actual_browser:false}));
