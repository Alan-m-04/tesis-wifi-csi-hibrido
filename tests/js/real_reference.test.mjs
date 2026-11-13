// Physical historical data regression, offline only. This is not new acquisition.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import dgram from 'node:dgram';
import {consumeCanonical} from '../../src/ruview_offline.mjs';
const source=process.env.CSI_CANONICAL_PATH;
const skip=!source?'Set CSI_CANONICAL_PATH to the generated local physical envelope':false;
dgram.createSocket=()=>{throw new Error('UDP forbidden in offline regression');};
let canonical,result;
function load(){if(!canonical){canonical=JSON.parse(fs.readFileSync(source,'utf8'));result=consumeCanonical(canonical);}return result;}
for(const rx of ['RX-01','RX-02'])for(const ltf of ['LLTF','HT-LTF']){
 test(`physical historical ${rx}/${ltf}: official arrays match canonical, own masks and clocks remain`,{skip},()=>{
  const r=load(),v=r.views[`${rx}/${ltf}`],n=rx==='RX-01'?292:291;
  assert.equal(v.frames.length,n);assert.equal(v.spectrum[0].framesSeen,n);
  assert.equal(v.compared_amplitudes,n*64);assert.ok(v.compared_phases>n*45);
  assert.equal(v.frames[0].antennas,1);assert.equal(v.frames[0].subcarriers,64);
  assert.equal(v.usb_serial,rx==='RX-01'?'5C93199744':'5C93200689');
  const frames=canonical.receivers[rx].frames;
  for(let i=0;i<n;i++){
   const f=frames[i],b=f.blocks.find(x=>x.ltf===ltf);
   assert.equal(typeof f.host_monotonic_ns,'string');assert.equal(f.host_monotonic_ns,f.original_fields.host_monotonic_ns);
   for(let k=0;k<64;k++)if(b.amplitude[k]===0){assert.equal(b.phase_rad[k],null);assert.equal(b.phase_known[k],false);}
   assert.equal(f.raw_reference.line_sha256.length,64);
  }
 });
}
test('physical historical session remains strictly rejected and original startup file survives',{skip},()=>{
 const r=load();assert.equal(canonical.evidence_type,'physical_capture');assert.equal(r.strict_quality_ok,false);
 assert.equal(r.status_label,'captura histórica con validación estricta rechazada');
 assert.equal(canonical.strict_audit.receivers['RX-01'].counts.malformed_rows,1);
 const raw=path.join(path.dirname(source),'originals/rx-01.serial.log');assert.ok(fs.statSync(raw).size>0);
 assert.equal(Object.keys(r.views).length,4);
});
