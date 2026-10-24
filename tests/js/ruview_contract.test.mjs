import test from 'node:test';
import assert from 'node:assert/strict';
import dgram from 'node:dgram';
import { parsePacket, SpectrumCollector } from '../../vendor/ruview/esp32.js';
import { blockBuffer, consumeCanonical } from '../../src/ruview_offline.mjs';

// Fail closed if any audited/test path accidentally attempts a socket.
dgram.createSocket=()=>{throw new Error('UDP forbidden in contract tests');};
function packet(raw=[-4,3],antennas=1,count=raw.length/2/antennas) {
 const b=Buffer.alloc(20+raw.length);b.writeUInt32LE(0xC5110001);b[4]=9;b[5]=antennas;b.writeUInt16LE(count,6);
 b.writeUInt32LE(2462,8);b.writeUInt32LE(17,12);b.writeInt8(-52,16);b.writeInt8(-96,17);
 raw.forEach((v,i)=>b.writeInt8(v,20+i));return b;
}
function parsed(raw) {return parsePacket(packet(raw),{iq:true});}
function canonical() {
 const raw=Array.from({length:128},()=>[-4,3]).flat();
 const block=ltf=>({ltf,byte_start:ltf==='LLTF'?0:128,byte_stop:ltf==='LLTF'?128:256,indices:Array.from({length:64},(_,i)=>i<32?i:i-64),
  hardware_valid:Array(64).fill(true),amplitude:Array(64).fill(5),phase_known:Array(64).fill(true),phase_rad:Array(64).fill(Math.atan2(-4,3))});
 const frame=(n)=>({original_fields:{data:JSON.stringify(raw),channel:'11',bandwidth:'0',rssi:'-52',noise_floor:'-96'},callback_id:String(n),host_monotonic_ns:String(2n**60n+BigInt(n)*200000000n),blocks:[block('LLTF'),block('HT-LTF')]});
 return {status_label:'synthetic fixture only',strict_quality_ok:true,capture_start_monotonic_ns:String(2n**60n),receivers:{'RX-01':{usb_serial:'5C93199744',frames:[frame(0),frame(1)]},'RX-02':{usb_serial:'5C93200689',frames:[frame(0),frame(1)]}}};
}

test('official Im/Re: signed amplitude and phase, not only magnitude',()=>{const p=parsed([-4,3]);assert.equal(p.amplitudes[0],5);assert.equal(p.phases[0],Math.atan2(-4,3));assert.notEqual(p.phases[0],Math.atan2(3,-4));});
test('four quadrants and signed int8 extremes',()=>{for(const [im,re] of [[4,3],[4,-3],[-4,-3],[-4,3],[-128,127],[127,-128]]){const p=parsed([im,re]);assert.equal(p.amplitudes[0],Math.hypot(im,re));assert.equal(p.phases[0],Math.atan2(im,re));}});
test('header offsets, little endian and signed metadata',()=>{const p=parsed([-4,3]);assert.deepEqual([p.nodeId,p.antennas,p.subcarriers,p.freqMhz,p.seq,p.rssi,p.noiseFloor],[9,1,1,2462,17,-52,-96]);});
test('nonzero byteOffset views are decoded correctly',()=>{const b=Buffer.concat([Buffer.alloc(7),packet([-4,3]),Buffer.alloc(5)]).subarray(7,-5);assert.equal(parsePacket(b,{iq:true}).phases[0],Math.atan2(-4,3));});
test('arrays require opts.iq',()=>{const p=parsePacket(packet());assert.equal(p.amplitudes,null);assert.equal(p.phases,null);});
test('upstream numerical zero phase is not a validity mask',()=>{const p=parsed([0,0]);assert.equal(p.amplitudes[0],0);assert.equal(p.phases[0],0);assert.equal(p.hardware_valid,undefined);});
test('flags expose zeroed word but do not mask IQ',()=>{const b=packet();b[19]=0x21;const p=parsePacket(b,{iq:true});assert.equal(p.firstWordZeroed,true);assert.equal(p.bw40,true);assert.equal(p.amplitudes[0],5);});
test('truncated header, truncated payload and empty dimensions are malformed',()=>{assert.equal(parsePacket(packet().subarray(0,19)).kind,'malformed');assert.equal(parsePacket(packet().subarray(0,21)).kind,'malformed');const b=packet();b[5]=0;assert.equal(parsePacket(b).kind,'malformed');b[5]=1;b.writeUInt16LE(0,6);assert.equal(parsePacket(b).kind,'malformed');});
test('wrong magic is unknown and trailing bytes are accepted',()=>{const b=packet();b.writeUInt32LE(0x12345678);assert.equal(parsePacket(b).kind,'unknown');assert.equal(parsePacket(Buffer.concat([packet(),Buffer.from([99])])).kind,'csi');});
test('multi-antenna does not return full phase arrays and firstChain is distinct',()=>{const b=packet([-4,3,12,5],2,1);let p=parsePacket(b,{iq:true});assert.equal(p.phases,null);p=parsePacket(b,{iq:true,firstChain:true});assert.deepEqual(p.chain0Amplitudes,[5]);assert.equal(p.antennas,2);});
test('spectrum rounds amplitude to one decimal and loses phase/times/masks',()=>{const c=new SpectrumCollector(4,1);c.add(parsed([1,1]),2);const r=c.result()[0];assert.deepEqual(r.frames,[[1.4]]);for(const k of ['phases','timestamps','hardware_valid'])assert.equal(r[k],undefined);});
test('spectrum bins average adjacent positions rather than physical frequencies',()=>{const c=new SpectrumCollector(4,1);c.add(parsed([0,2,0,4]),0);assert.deepEqual(c.result()[0].frames,[[3]]);});
test('spectrum keeps latest ring rows but framesSeen and rate use all seen',()=>{const c=new SpectrumCollector(2,1);for(const [n,t] of [[1,0],[2,200],[3,600]])c.add(parsed([0,n]),t);const r=c.result()[0];assert.deepEqual(r.frames,[[2],[3]]);assert.equal(r.framesSeen,3);assert.equal(r.rateHz,3.33);});
test('spectrum accepts shared and irregular registered timestamps',()=>{const c=new SpectrumCollector(4,1);for(const t of [0,0,400])c.add(parsed(),t);assert.equal(c.result()[0].rateHz,5);assert.equal(c.result()[0].framesSeen,3);});
test('independent collectors separate same-shape LTF history',()=>{const a=new SpectrumCollector(4,1),b=new SpectrumCollector(4,1);a.add(parsed([0,2]),0);b.add(parsed([0,8]),0);assert.deepEqual(a.result()[0].frames,[[2]]);assert.deepEqual(b.result()[0].frames,[[8]]);});
test('memory bridge creates four LTF histories, not fake receivers or antennas',()=>{const c=canonical(),r=consumeCanonical(c);assert.equal(Object.keys(r.views).length,4);for(const [key,v]of Object.entries(r.views)){assert.equal(v.frames.length,2);assert.equal(v.frames[0].antennas,1);assert.equal(v.frames[0].subcarriers,64);assert.equal(v.spectrum[0].rateHz,5);assert.equal(v.node_id,key.startsWith('RX-01')?1:2);}});
test('whole raw LTF payload stays Im/Re byte for byte',()=>{const c=canonical(),f=c.receivers['RX-01'].frames[0],b=blockBuffer(f,f.blocks[0],1);assert.deepEqual([...new Int8Array(b.buffer,b.byteOffset+20,128)],JSON.parse(f.original_fields.data).slice(0,128));});
test('own wrapper ignores invalid and unknown-phase comparisons without zero filling',()=>{const c=canonical();for(const r of Object.values(c.receivers))for(const f of r.frames){f.blocks[0].hardware_valid[0]=false;f.blocks[0].amplitude[0]=null;f.blocks[0].phase_known[0]=false;}const r=consumeCanonical(c);assert.equal(r.views['RX-01/LLTF'].compared_amplitudes,126);assert.equal(r.views['RX-01/LLTF'].frames[0].amplitudes[0],5);});
test('mask or metadata loss never rewrites strict rejection label',()=>{const c=canonical();c.strict_quality_ok=false;c.status_label='captura histórica con validación estricta rechazada';const r=consumeCanonical(c);assert.equal(r.strict_quality_ok,false);assert.equal(r.status_label,c.status_label);assert.equal(c.receivers['RX-01'].usb_serial,'5C93199744');});
test('unexpected bandwidth is rejected instead of inferring from byte count',()=>{const c=canonical(),f=c.receivers['RX-01'].frames[0];f.original_fields.bandwidth='1';assert.throws(()=>blockBuffer(f,f.blocks[0],1),/HT20/);});
test('bridge does not mix LLTF and HT-LTF of the same receiver',()=>{
 const c=canonical();for(const r of Object.values(c.receivers))for(const f of r.frames){
  const raw=JSON.parse(f.original_fields.data);for(let i=128;i<256;i+=2){raw[i]=12;raw[i+1]=5;}
  f.original_fields.data=JSON.stringify(raw);const b=f.blocks[1];b.amplitude.fill(13);b.phase_rad.fill(Math.atan2(12,5));
 }
 const v=consumeCanonical(c).views;
 assert.equal(v['RX-01/LLTF'].node_id,v['RX-01/HT-LTF'].node_id);
 assert.equal(v['RX-01/LLTF'].spectrum[0].frames[0][0],5);
 assert.equal(v['RX-01/HT-LTF'].spectrum[0].frames[0][0],13);
});
test('official parser accepts 128 raw pairs: splitting LTF is semantic, not a parser size requirement',()=>{
 const raw=Array.from({length:128},()=>[-4,3]).flat();const p=parsePacket(packet(raw),{iq:true});
 assert.equal(p.subcarriers,128);assert.equal(p.antennas,1);assert.equal(p.amplitudes.length,128);
 assert.equal(p.bw40,false);assert.equal(p.phases[127],Math.atan2(-4,3));
});
