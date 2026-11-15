import {makeCsiCharts} from '/charts.mjs';
const $=id=>document.getElementById(id);
const physical=document.body?.dataset.source==='physical_capture';
const expectedSource=physical?'physical_capture':'synthetic_fixture';
const charts=makeCsiCharts({tone_indices:Array.from({length:26},(_,i)=>i-26).concat(Array.from({length:26},(_,i)=>i+1)),scales:{amplitude:[0,Math.hypot(128,128)]}},()=>30);
const labels={esperando:'Esperando',recibiendo:'Recibiendo',datos_antiguos:'Datos antiguos',detenido:'Detenido'};
let data=null,received=0,baseAge=null,paused=false,busy=false,network=false,skipped=0,lastId=null,lastRevision=null;
const stamp=value=>typeof value==='string'&&/^\d{1,24}$/.test(value);
const validRow=r=>stamp(r.t_ns)&&Number.isFinite(r.rssi)&&Array.isArray(r.amplitudes)&&r.amplitudes.length===52&&
 r.amplitudes.every(a=>a===null||Number.isFinite(a)&&a>=0)&&Array.isArray(r.hardware_valid)&&r.hardware_valid.length===64&&
 Array.isArray(r.cfr_usable)&&r.cfr_usable.length===64;
function clear(){for(const id of ['heat','rssi']){const c=$(id);c.getContext('2d').clearRect(0,0,c.width,c.height);}}
export function paint(){
 const age=baseAge===null?null:baseAge+performance.now()-received;
 let state=data?.flow_state??'esperando';
 if(state!=='detenido'&&(paused||!network||age!==null&&age>=data.stale_after_ms))state=data?.last_sample_ns?'datos_antiguos':'esperando';
 $('state').textContent=labels[state];$('state').dataset.state=state;
 $('reason').textContent=paused?'Vista en pausa; la adquisición sigue su propio curso.':!network?'Sin respuesta actual del visor; no se deduce cierre físico.':state==='datos_antiguos'?'La última muestra ya no es reciente. No se deduce cierre físico.':data.reason;
 $('last').textContent=data?.last_sample_ns?`Última muestra host: ${data.last_sample_ns} ns · edad ${((age??0)/1000).toFixed(2)} s`:'Última muestra host: sin muestra.';
 $('loss').textContent=`Filas descartadas del buffer visual: ${data?.rows_discarded_view??0} · actualizaciones omitidas por este navegador: ${skipped} · líneas inválidas: ${data?.invalid_lines??0}`;
 if(physical)$('audit').textContent=data?.physical_close_verified?'Cierre verificado por la auditoría nativa.':data?.audit_status==='completed'?'Auditoría terminada sin cierre confirmado.':'Cierre pendiente de auditoría nativa.';
 if(state==='recibiendo'&&network&&!paused){
  const origin=BigInt(data.window_T0_ns),rows=data.rows.filter(r=>BigInt(r.t_ns)>=origin&&BigInt(r.t_ns)<=origin+30_000_000_000n);
  charts.heatmap($('heat'),{T0_ns:data.window_T0_ns,rows});charts.series($('rssi'),{T0_ns:data.window_T0_ns,rows},'rssi',[-128,0],'RSSI dBm');
  $('blank').hidden=true;
 }else{clear();$('blank').hidden=false;}
}
export async function poll(){
 if(paused||busy||document.hidden)return;
 busy=true;const started=performance.now(),controller=new AbortController(),timer=setTimeout(()=>controller.abort(),2000);
 try{
  const response=await fetch('/api/stream',{cache:'no-store',signal:controller.signal});if(!response.ok)throw Error('Preview unavailable');
  const value=await response.json();
  if(value.schema!=='csi-live-preview-1'||value.evidence_type!==expectedSource||!Array.isArray(value.rows)||value.rows.length>(physical?8:300)||!Object.hasOwn(labels,value.flow_state))throw Error('Unsupported preview');
  if(physical&&value.attempt_id!=='RX02-DIAG-VISOR-240S-R1')throw Error('Unexpected physical attempt');
  if(!stamp(value.window_T0_ns)||value.rows.some(r=>!validRow(r))||!Number.isFinite(value.stale_after_ms)||value.stale_after_ms<=0||
   value.last_sample_ns!==null&&!stamp(value.last_sample_ns)||
   value.last_sample_ns!==null&&(!Number.isFinite(value.sample_age_ms)||value.sample_age_ms<0)||
   value.flow_state==='recibiendo'&&value.last_sample_ns===null)throw Error('Incomplete CSI preview');
  if(lastId===value.observer_id&&lastRevision!==null)skipped+=Math.max(0,value.revision-lastRevision-1);
  lastId=value.observer_id;lastRevision=value.revision;
  data=value;received=performance.now();baseAge=value.sample_age_ms===null?null:value.sample_age_ms+received-started;network=true;
  $('details').textContent=JSON.stringify({...value,rows:`${value.rows.length} filas acotadas; original en solo lectura`},null,2);
 }catch{network=false;}finally{clearTimeout(timer);busy=false;paint();}
}
$('pause').addEventListener('click',()=>{paused=!paused;$('pause').textContent=paused?'Reanudar vista':'Pausar vista';paint();if(!paused)poll();});
$('refresh').addEventListener('click',poll);
document.addEventListener('visibilitychange',()=>{paint();if(!document.hidden)poll();});
setInterval(()=>{paint();poll();},250);paint();poll();
