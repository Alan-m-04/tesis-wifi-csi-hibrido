const $=id=>document.getElementById(id);
function number(value){return value===null?'No disponible':String(value).replace('.',',');}
function node(tag,text){const element=document.createElement(tag);element.textContent=text;return element;}
function valid(data){return data?.schema==='csi-sqlite-dashboard-1'&&data.read_only===true&&data.historical===true&&
 data.live_capture===false&&typeof data.queried_at_utc==='string'&&
 ['matched','not_present'].includes(data.pilot_csv_comparison?.state)&&Array.isArray(data.sessions)&&
 new Set(data.sessions.map(r=>`${r?.session_id}\0${r?.receiver_id}`)).size===data.sessions.length&&data.sessions.every(r=>
 typeof r.session_id==='string'&&typeof r.receiver_id==='string'&&Number.isSafeInteger(r.rows)&&r.rows>=0&&
 [r.duration_s,r.capture_frequency_hz,r.max_host_gap_ms].every(v=>v===null||(typeof v==='number'&&Number.isFinite(v)&&v>=0))&&
 ['accepted','rejected','unknown'].includes(r.quality_status)&&
 (r.quality_status==='accepted'?r.strict_quality_ok===1:r.quality_status==='rejected'?r.strict_quality_ok===0:r.strict_quality_ok===null)&&
 typeof r.preamble_rejected==='boolean'&&Array.isArray(r.quality_reasons)&&r.quality_reasons.every(reason=>
 typeof reason.reason==='string'&&Number.isSafeInteger(reason.count)&&reason.count>0)&&
 r.preamble_rejected===(r.strict_quality_ok===0&&r.quality_reasons.some(reason=>reason.reason.startsWith('preamble_anomaly:')))&&
 [r.integrity_ok,r.replay_ok,r.close_ok,r.diagnostic_ok].every(value=>value===0||value===1||value===null));}
function quality(row){return row.preamble_rejected?'RECHAZADA · PREÁMBULO':
 row.quality_status==='rejected'?'RECHAZADA':row.quality_status==='accepted'?'ACEPTADA':'NO REGISTRADA';}
function check(value,positive){return value===1?positive:value===0?'No conforme':'Sin registrar';}
function clear(){ $('sessions').replaceChildren();$('validation-details').replaceChildren();
 $('quality-alert').hidden=true;$('quality-alert').textContent=''; }
function render(data){
 clear();
 for(const row of data.sessions){
  const tr=document.createElement('tr');
  const identity=node('th',`${row.session_id} · ${row.receiver_id}`);identity.scope='row';tr.append(identity);
  for(const value of [row.duration_s,row.rows,row.capture_frequency_hz,row.max_host_gap_ms])tr.append(node('td',number(value)));
  const status=node('td',quality(row));status.className='quality';status.dataset.state=row.quality_status;tr.append(status);
  $('sessions').append(tr);
  const detail=document.createElement('section');detail.className='card';
  detail.append(node('h2',`${row.session_id} · ${row.receiver_id}`),node('p',quality(row)));
  const reasons=document.createElement('ul');
  for(const reason of row.quality_reasons){const item=document.createElement('li');
   const explanation=reason.reason.startsWith('preamble_anomaly:')?'Anomalía en el preámbulo':
    reason.reason.startsWith('format:')?'Línea con formato inválido':'Motivo original';
   item.append(node('span',`${explanation} · `),node('code',reason.reason),node('span',` ×${reason.count}`));reasons.append(item);}
  if(row.quality_reasons.length)detail.append(reasons);
  detail.append(node('p',`Integridad: ${check(row.integrity_ok,'verificada')} · Replay: ${check(row.replay_ok,'verificado')} · Cierre: ${check(row.close_ok,'confirmado')} · Diagnóstico: ${check(row.diagnostic_ok,'conforme')}`));
  $('validation-details').append(detail);
 }
 const rejected=data.sessions.filter(row=>row.quality_status==='rejected');
 if(rejected.length){$('quality-alert').hidden=false;
  $('quality-alert').textContent=rejected.some(row=>row.preamble_rejected)?
   'CALIDAD ESTRICTA RECHAZADA POR PREÁMBULO. Las anomalías originales de arranque/formato se conservan. No utilizar esta sesión como una captura aprobada.':
   'CALIDAD ESTRICTA RECHAZADA. Revisa los motivos originales antes de utilizar los datos.';}
 $('time').textContent='Consulta de datos guardados (UTC): '+data.queried_at_utc;
 $('comparison').textContent=data.pilot_csv_comparison.state==='matched'?
  'Piloto RX02-DIAG-VISOR-240S-R1 / RX-02: indicadores y calidad coinciden con su CSV.':
  'CSV piloto: la sesión piloto no está presente en esta consulta.';
 $('status').textContent=data.sessions.length?`${data.sessions.length} sesión(es)/receptor(es). Consulta offline de solo lectura.`:
  'La base está vacía: no hay sesiones importadas. No se importan datos automáticamente.';
}
export async function refresh(){
 if($('refresh').disabled)return;
 $('refresh').disabled=true;$('status').textContent='Consultando SQLite local…';clear();
 $('time').textContent='Hora de consulta: pendiente.';$('comparison').textContent='CSV piloto: pendiente de contraste.';
 const controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),12000);
 try{const response=await fetch('/api/sessions',{cache:'no-store',signal:controller.signal});
  if(!response.ok)throw Error(`Consulta no disponible (HTTP ${response.status}).`);
  const data=await response.json();if(!valid(data))throw Error('Respuesta de sesiones no verificable.');render(data);
 }catch(error){clear();$('status').textContent='Sin datos verificables. '+error.message+' Revisa la base y el backend local; esta vista no crea ni reimporta datos.';
  $('time').textContent='Hora de consulta: no hay una respuesta verificada.';$('comparison').textContent='CSV piloto: no verificado.';
 }finally{clearTimeout(timeout);$('refresh').disabled=false;}
}
$('refresh').addEventListener('click',refresh);refresh();
