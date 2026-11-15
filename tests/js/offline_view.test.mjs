import test from 'node:test';
import assert from 'node:assert/strict';
import {relativeSeconds,observedStd,historyPoints,scopeStates,experimentalBounds} from '../../src/offline_view.mjs';
function frame(ns,values,usable=[true,true]){return{host_monotonic_ns:String(ns),csv_line_1based:2,original_fields:{rssi:'-51'},blocks:[{ltf:'LLTF',amplitude:values,cfr_usable:usable}]};}
test('time differences are taken as BigInt before converting to chart seconds',()=>{const t=2n**60n;assert.equal(relativeSeconds(String(t+17n),String(t)),17e-9);});
test('duplicate timestamps remain duplicate chart points',()=>{const f=[frame(100,[1,2]),frame(100,[3,4]),frame(110,[5,6])];const p=historyPoints(f,'100');assert.equal(p.length,3);assert.deepEqual(p.map(x=>x.t),[0,0,1e-8]);});
test('variability excludes invalid and guard/DC values instead of filling zeros',()=>{const f=[frame(1,[2,999],[true,false]),frame(2,[4,null],[true,false])];const s=observedStd(f,'LLTF');assert.equal(s[0],1);assert.equal(s[1],null);});
test('variability is observed population sigma, not a uniform time model',()=>{const f=[frame(0,[2,3]),frame(400,[4,3])];const s=observedStd(f,'LLTF');assert.equal(s[0],1);assert.equal(s[1],0);});
test('v3 conforming window keeps whole connection rejection visible',()=>{
 const c={connection_full:{status:'rechazada'},experimental_window:{status:'conforme'}};
 assert.deepEqual(scopeStates(c),{connection:'Conexión completa: rechazada',window:'Ventana experimental: conforme'});
 assert.equal(scopeStates({}),null);
});
test('v3 charts retain the entire fixed window even with sparse rows',()=>{
 const base=2n**60n;
 assert.deepEqual(experimentalBounds({capture_start_monotonic_ns:String(base),experimental_window:{T0_ns:String(base+10n),T1_ns:String(base+30000000010n)}}),[1e-8,30.00000001]);
 assert.equal(experimentalBounds({experimental_window:{T0_ns:null}}),null);
});
