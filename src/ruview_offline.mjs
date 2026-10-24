// Offline-only bridge to the exact MIT-licensed upstream module. No socket APIs.
import { parsePacket, SpectrumCollector } from '../vendor/ruview/esp32.js';

export function blockBuffer(frame, block, nodeId) {
  const raw = JSON.parse(frame.original_fields.data);
  const selected = raw.slice(block.byte_start, block.byte_stop);
  if (selected.length !== 128 || block.indices.length !== 64 || selected.some(v => !Number.isInteger(v) || v < -128 || v > 127)) {
    throw new Error('Only the documented 64-pair LTF view is supported');
  }
  const buf = Buffer.alloc(20 + selected.length);
  buf.writeUInt32LE(0xC5110001, 0); buf[4] = nodeId; buf[5] = 1;
  buf.writeUInt16LE(64, 6);
  const channel = Number(frame.original_fields.channel);
  if (channel !== 11 || Number(frame.original_fields.bandwidth) !== 0) throw new Error('Explicit channel 11 HT20 required');
  buf.writeUInt32LE(2462, 8);
  buf.writeUInt32LE(Number(frame.callback_id), 12); // local RX callback, never TX seq
  buf.writeInt8(Number(frame.original_fields.rssi), 16);
  buf.writeInt8(Number(frame.original_fields.noise_floor), 17);
  // HT/legacy bucket and HT20. No fake sync or "zeroed first word" flag.
  buf[18] = 0; buf[19] = 0;
  selected.forEach((v,i) => buf.writeInt8(v,20+i));
  return buf;
}

export function consumeCanonical(canonical) {
  const result = { schema:'tesis-ruview-offline-v1', transport:'memory_buffers_only',
    status_label:canonical.status_label, strict_quality_ok:canonical.strict_quality_ok,
    official_functions:['parsePacket','SpectrumCollector.add','SpectrumCollector.result','binAmplitudes (transitive)'],
    metadata_and_masks:'preserved in canonical sidecar; upstream does not retain them', views:{} };
  for (const [rx, receiver] of Object.entries(canonical.receivers)) {
    const nodeId = {'RX-01':1,'RX-02':2}[rx];
    if (!nodeId || receiver.frames.length === 0) throw new Error('Two known receiver identities required');
    for (const ltf of ['LLTF','HT-LTF']) {
      // Same receiver identity for its two LTFs. Separate collector instance, not fake node/antenna.
      const collector = new SpectrumCollector(receiver.frames.length,64,1);
      const parsedFrames = []; let comparedAmplitude=0, comparedPhase=0;
      for (const frame of receiver.frames) {
        const block = frame.blocks.find(b => b.ltf === ltf);
        const packet = parsePacket(blockBuffer(frame,block,nodeId),{iq:true});
        if (packet.kind !== 'csi' || packet.antennas !== 1 || packet.subcarriers !== 64) throw new Error('Unexpected upstream shape');
        for (let k=0;k<64;k++) {
          if (block.hardware_valid[k]) {
            if (Math.abs(packet.amplitudes[k]-block.amplitude[k])>1e-10) throw new Error('Amplitude mismatch');
            comparedAmplitude++;
            if (block.phase_known[k]) {
              if (Math.abs(packet.phases[k]-block.phase_rad[k])>1e-10) throw new Error('Phase mismatch');
              comparedPhase++;
            }
          }
        }
        // Subtract exact BigInt ns first. Conversion to relative ms is only for SpectrumCollector.rateHz.
        const t = Number(BigInt(frame.host_monotonic_ns)-BigInt(canonical.capture_start_monotonic_ns))/1e6;
        collector.add(packet,t);
        parsedFrames.push(packet);
      }
      result.views[`${rx}/${ltf}`]={receiver_id:rx,usb_serial:receiver.usb_serial,ltf,node_id:nodeId,
        frames:parsedFrames, spectrum:collector.result(),compared_amplitudes:comparedAmplitude,compared_phases:comparedPhase};
    }
  }
  return result;
}
