// Offline DOM contract checks; this is not a visual browser test.
import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
class Element{
 constructor(){this.textContent='';this.children=[];this.dataset={};this.disabled=false;this.events={};}
 append(...x){this.children.push(...x);}replaceChildren(...x){this.children=x;}
 addEventListener(name,fn){this.events[name]=fn;}
}
const elements=Object.fromEntries(['refresh','status','time','scope','devices','catalogue'].map(id=>[id,new Element()]));
const document={getElementById:id=>elements[id],createElement:()=>new Element()};
const stamp='2026-11-09T15:00:00+00:00';
const rx={id:'RX-01',usb_serial:'5C93199744',by_id:'/dev/serial/by-id/RX01',by_id_observed:true,
 status:'detectado',node:'/dev/ttyACM7',permissions:{mode:'0o660',uid:1000,gid:20,effective_read:true,effective_write:false},
 queried_at_utc:stamp,notes:['USB identity only'],ready:null,csi_received:null};
let payload={schema:'local-device-metadata-1',queried_at_utc:stamp,query_finished_at_utc:stamp,
 view:'Synthetic local metadata fixture',inventory_complete:true,inventory_notes:[],devices:[rx,
 {...rx,id:'RX-02',usb_serial:'5C93200689',by_id:'/dev/serial/by-id/RX02',status:'ausente',node:null,permissions:null},
 {...rx,id:'TX-01',usb_serial:null,by_id:null,status:'no_verificable',status_text:'no verificable por USB',node:null,permissions:null}]};
const requests=[];let error=null,httpStatus=200,hang=false;
const validPayload=JSON.parse(JSON.stringify(payload));
elements.catalogue.textContent=JSON.stringify(payload.devices.map(d=>({...d,status:'no_verificable',by_id_observed:false,node:null,permissions:null,queried_at_utc:null})));
const fetch=async(url,options)=>{requests.push([url,options]);if(error)throw error;
 if(hang)return new Promise((_,reject)=>options.signal.addEventListener('abort',()=>reject(Error('Consulta vencida'))));
 return {ok:httpStatus===200,status:httpStatus,json:async()=>payload};};
const timers=new Map();let timerId=0;
const sandbox={document,fetch,console,AbortController,setTimeout:(fn,ms)=>{assert.equal(ms,12000);timers.set(++timerId,fn);return timerId;},clearTimeout:id=>timers.delete(id)};vm.createContext(sandbox);
await vm.runInContext(fs.readFileSync('src/device_panel.mjs','utf8').replace('export async function','async function'),sandbox);
const text=node=>[node.textContent,...node.children.map(text)].join(' ');
assert.equal(elements.devices.children.length,3);
assert.match(text(elements.devices.children[0]),/RX-01.*Detectado.*5C93199744.*ttyACM7.*0o660.*escritura: no/);
assert.match(text(elements.devices.children[1]),/Ausente en la vista local/);
assert.match(text(elements.devices.children[2]),/no verificable por USB/);
assert.match(text(elements.devices.children[0]),/Sin observar; UART no abierta/);
assert(elements.time.textContent.includes(stamp));assert(!elements.refresh.disabled);
assert.equal(requests[0][0],'/api/devices');assert.equal(requests[0][1].cache,'no-store');
// A later query replaces the observation; unavailable metadata is never absent.
payload={...payload,inventory_complete:false,inventory_notes:['/dev denied'],devices:payload.devices.map(d=>({...d,status:'no_verificable',node:null,permissions:null}))};
await elements.refresh.events.click();assert.match(text(elements.devices.children[0]),/No verificable/);
assert(!text(elements.devices.children[0]).includes('ttyACM7'));assert.match(elements.scope.textContent,/\/dev denied/);
// Network/HTTP/schema errors erase stale detected cards and explicitly stay unknown.
for(const failure of ['network','http','schema']){
 error=failure==='network'?new Error('localhost unavailable'):null;httpStatus=failure==='http'?500:200;
 if(failure==='schema')payload={schema:'unexpected',devices:[]};
 await elements.refresh.events.click();assert.equal(elements.devices.children.length,3);
 assert.match(text(elements.devices.children[0]),/No verificable/);assert(!text(elements.devices.children[0]).includes('ttyACM7'));
 assert.match(elements.status.textContent,/No verificable/);assert.match(elements.status.textContent,/No se deduce ausencia/);
 assert.match(elements.time.textContent,/no hay una respuesta actual/);assert(!elements.refresh.disabled);
}
assert(requests.every(([url])=>url==='/api/devices'));
error=null;httpStatus=200;
for(const devices of [[],[validPayload.devices[0],validPayload.devices[0],validPayload.devices[2]],validPayload.devices.map(d=>({...d,ready:true}))]){
 payload={...validPayload,devices};await elements.refresh.events.click();
 assert.equal(elements.devices.children.length,3,'Incomplete inventories must fall back to unknown expected devices');
 assert.match(elements.status.textContent,/No verificable/);
}
// A stalled server must release the button and clear observations after timeout.
payload=validPayload;hang=true;const pending=elements.refresh.events.click();
assert(elements.refresh.disabled);const before=requests.length;
await elements.refresh.events.click();assert.equal(requests.length,before,'No concurrent refreshes');
assert.equal(timers.size,1);[...timers.values()][0]();await pending;
assert.equal(timers.size,0);assert(!elements.refresh.disabled);assert.match(elements.status.textContent,/No verificable/);
assert(!text(elements.devices.children[0]).includes('ttyACM7'));
const html=fs.readFileSync('src/device_panel.html','utf8');assert(html.includes('href="/replay"'));
assert(html.includes('metadatos actuales'));assert(html.includes('datos históricos'));
console.log(JSON.stringify({checks:'passed',metadata_fields:true,three_states:true,external_TX_unknown:true,
 manual_refresh:true,timeout_and_concurrency:true,incomplete_inventory_rejected:true,navigation:true,
 stale_detection_cleared_on_error:true,no_ready_or_CSI_claim:true,actual_browser:false}));
