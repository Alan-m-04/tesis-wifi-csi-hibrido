// Local diagnostic rendering only. No fetch, sockets, timers, inference or resampling.
export function relativeSeconds(ns, origin) { return Number(BigInt(ns)-BigInt(origin))/1e9; }
export function observedStd(frames, ltf) {
  return Array.from({length:64},(_,k)=>{
    let n=0,mean=0,m2=0;
    for(const f of frames){const b=f.blocks.find(x=>x.ltf===ltf);if(!b.cfr_usable[k]||b.amplitude[k]===null)continue;
      const x=b.amplitude[k];n++;const delta=x-mean;mean+=delta/n;m2+=delta*(x-mean);}
    return n?Math.sqrt(m2/n):null;
  });
}
export function historyPoints(frames, origin) {
  return frames.map(f=>({t:relativeSeconds(f.host_monotonic_ns,origin),row:f.csv_line_1based,rssi:Number(f.original_fields.rssi)}));
}
const NS='http://www.w3.org/2000/svg';
function el(tag,attrs={},text){const x=document.createElementNS(NS,tag);for(const[k,v]of Object.entries(attrs))x.setAttribute(k,v);if(text!==undefined)x.textContent=text;return x;}
function chart(id,title,xlabel,ylabel){const svg=document.getElementById(id);svg.replaceChildren();svg.setAttribute('viewBox','0 0 650 250');svg.setAttribute('role','img');svg.setAttribute('aria-label',title);
 svg.append(el('rect',{width:650,height:250,fill:'#111c2d'}),el('text',{x:18,y:23,fill:'#f5f8ff','font-size':15},title),el('text',{x:320,y:242,fill:'#afc1d9','font-size':12},xlabel),el('text',{x:16,y:44,fill:'#afc1d9','font-size':11},ylabel));return svg;}
function axes(svg,xmin,xmax,ymin,ymax,xTicks=null){const X=v=>55+(v-xmin)/(xmax-xmin||1)*565,Y=v=>210-(v-ymin)/(ymax-ymin||1)*153;
 svg.append(el('path',{d:'M55 55V210H620',fill:'none',stroke:'#48637e'}));
 for(let i=0;i<=4;i++){const x=xTicks?xTicks[i]:xmin+(xmax-xmin)*i/4,y=ymin+(ymax-ymin)*i/4;svg.append(el('text',{x:X(x),y:226,fill:'#afc1d9','font-size':10,'text-anchor':'middle'},xTicks?String(x):x.toFixed(1)),el('text',{x:49,y:Y(y)+3,fill:'#afc1d9','font-size':10,'text-anchor':'end'},y.toFixed(1)));}
 return{X,Y};}
function marker(svg,x,y,role,invalid,label){const color=invalid?'#ff68c5':role==='DC'?'#ffcc6a':role==='guard'?'#64788f':'#45d9c9';
 const c=el('circle',{cx:x,cy:y,r:invalid?4:2.4,fill:invalid?'none':color,stroke:color});c.append(el('title',{},label));svg.append(c);}
function spectrum(id,title,block,values){const svg=chart(id,title,'Índice nominal de subportadora','Unidades relativas CSI, sin calibrar');
 const max=Math.max(1,...values.filter(x=>x!==null));const{X,Y}=axes(svg,-32,31,0,max*1.1,[-32,-16,0,16,31]);
 for(let k=0;k<64;k++){const role=block.roles[k],idx=block.indices[k];if(role==='guard'||role==='DC')svg.append(el('rect',{x:X(idx)-4.3,y:55,width:8.6,height:155,fill:role==='DC'?'#ffcc6a':'#8998aa',opacity:.12}));
 if(values[k]===null){if(!block.hardware_valid[k])svg.append(el('text',{x:X(idx),y:50,fill:'#ff68c5','text-anchor':'middle'},'×'));continue;}
 marker(svg,X(idx),Y(values[k]),role,!block.hardware_valid[k],`${idx}: ${role}; ${values[k]}`);}}
export function initialize(bundle) {
 const c=bundle.canonical,official=bundle.consumer,rxSelect=document.getElementById('rx'),ltfSelect=document.getElementById('ltf'),slider=document.getElementById('frame');
 const indices=new Map();
 if(typeof location!=='undefined'){
   const q=new URL(location.href).searchParams;
   if(c.receivers[q.get('rx')])rxSelect.value=q.get('rx');
   if(['LLTF','HT-LTF'].includes(q.get('ltf')))ltfSelect.value=q.get('ltf');
 }

 function render(){const rx=rxSelect.value,ltf=ltfSelect.value,key=`${rx}/${ltf}`,receiver=c.receivers[rx],frames=receiver.frames;
   const n=frames.length,i=Math.min(indices.get(key)??n-1,n-1);slider.max=n-1;slider.value=i;
   const f=frames[i],block=f.blocks.find(x=>x.ltf===ltf),hist=historyPoints(frames,c.capture_start_monotonic_ns),times=hist.map(x=>x.t);
   document.getElementById('status').textContent=c.status_label;
   document.getElementById('identity').textContent=`${rx} · USB ${receiver.usb_serial} · ${ltf} · ${n} muestras originales; bloque de entrenamiento, no antena adicional`;
   document.getElementById('sample').textContent=`Fila CSV ${f.csv_line_1based} · callback ${f.callback_id} · UTC lectura ${f.host_timestamp_utc} · host_ns ${f.host_monotonic_ns} · RX_us ${f.local_timestamp_us_uint32}`;
   document.getElementById('rowmeta').textContent=JSON.stringify({campos_originales:f.original_fields,referencia_bruta:f.raw_reference,referencia_csv:f.csv_reference,perfil:c.profile.firmware_ltf_config,limite:c.ltf_evidence},null,2);
   document.getElementById('official').textContent=`Oficial ejecutado: parsePacket + SpectrumCollector; ${official.views[key].spectrum[0].framesSeen} vistas ${ltf}, misma identidad RX; tasa por span host ${official.views[key].spectrum[0].rateHz} Hz. El colector no conserva tiempos por fila ni máscaras; envoltorio propio intacto.`;
   spectrum('amplitude',`Amplitud · ${rx}/${ltf} · fila ${f.csv_line_1based}`,block,block.amplitude);
   spectrum('variability','Variabilidad temporal σ poblacional por tono · muestras observadas',block,observedStd(frames,ltf));
   const rs=chart('rssi','RSSI del paquete · un punto por fila registrada','Segundos host desde inicio de ventana','dBm');const vals=hist.map(p=>p.rssi),a=axes(rs,Math.min(...times),Math.max(...times),Math.min(...vals)-2,Math.max(...vals)+2);
   hist.forEach((p,j)=>marker(rs,a.X(p.t),a.Y(p.rssi),'data',false,`fila ${p.row}; t=${p.t}s; RSSI=${p.rssi}`));marker(rs,a.X(hist[i].t),a.Y(hist[i].rssi),'DC',false,'fila seleccionada');
   const hs=chart('history',`Historial ${ltf} · marcas en tiempos registrados, sin rellenar huecos`,'Índice nominal de subportadora','Segundos host desde inicio de ventana');const h=axes(hs,-32,31,Math.min(...times),Math.max(...times),[-32,-16,0,16,31]);
   const ampMax=Math.max(1,...frames.flatMap(x=>x.blocks.find(b=>b.ltf===ltf).amplitude.filter(v=>v!==null)));
   for(let j=0;j<n;j++){const b=frames[j].blocks.find(x=>x.ltf===ltf);for(let k=0;k<64;k++){const valid=b.hardware_valid[k],role=b.roles[k],v=b.amplitude[k];
     const color=!valid?'#ff68c5':role==='DC'?'#ffcc6a':role==='guard'?'#354355':`hsl(${190-(v??0)/ampMax*150} 80% ${25+(v??0)/ampMax*45}%)`;
     const dot=el('rect',{x:h.X(b.indices[k])-3.5,y:h.Y(times[j])-0.65,width:7,height:1.3,fill:color});dot.append(el('title',{},`fila ${frames[j].csv_line_1based}; t=${times[j]} s; índice ${b.indices[k]}; ${role}; amplitud ${v??'inválida'}`));hs.append(dot);}}
   hs.append(el('line',{x1:55,x2:620,y1:h.Y(times[i]),y2:h.Y(times[i]),stroke:'#ffffff','stroke-width':.6}));
 }
 slider.addEventListener('input',()=>{indices.set(`${rxSelect.value}/${ltfSelect.value}`,Number(slider.value));render();});
 rxSelect.addEventListener('change',render);ltfSelect.addEventListener('change',render);render();
 document.documentElement.dataset.rendered='true';
}
if(typeof document!=='undefined'){initialize(JSON.parse(document.getElementById('csi-data').textContent));}
