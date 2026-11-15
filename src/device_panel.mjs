const $=id=>document.getElementById(id);
const states={detectado:'Detectado',ausente:'Ausente en la vista local',no_verificable:'No verificable'};
const expected=JSON.parse($('catalogue').textContent);
function valid(data){return data?.schema==='local-device-metadata-1'&&Array.isArray(data.devices)&&
 data.devices.length===expected.length&&new Set(data.devices.map(d=>d?.id)).size===expected.length&&
 typeof data.queried_at_utc==='string'&&typeof data.query_finished_at_utc==='string'&&Array.isArray(data.inventory_notes)&&
 expected.every(e=>data.devices.some(d=>d.id===e.id&&d.usb_serial===e.usb_serial&&d.by_id===e.by_id&&
  Object.hasOwn(states,d.status)&&Array.isArray(d.notes)&&d.notes.every(n=>typeof n==='string')&&
  typeof d.queried_at_utc==='string'&&d.ready===null&&d.csi_received===null&&
  (e.id!=='TX-01'||d.status==='no_verificable')));}
function field(list,name,value){const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=name;dd.textContent=value??'No verificable';list.append(dt,dd);}
function card(device){const node=document.createElement('section');node.className='card';
 const title=document.createElement('h2');title.textContent=device.id;
 const state=document.createElement('div');state.className='state';state.dataset.state=device.status;
 state.textContent=device.id==='TX-01'?'no verificable por USB':states[device.status]??states.no_verificable;
 const list=document.createElement('dl');
 field(list,'Serie USB esperada',device.usb_serial??'No aplica (alimentación externa)');
 field(list,'Ruta by-id esperada',device.by_id??'No aplica');
 if(device.by_id)field(list,'Ruta by-id observada',device.by_id_observed?'Sí':'No observada en esta consulta');
 field(list,'Nodo actual comprobado',device.node);
 const p=device.permissions;
 field(list,'Permisos del nodo',p?`${p.mode} · uid ${p.uid} · gid ${p.gid}`:null);
 field(list,'Acceso efectivo del proceso',p?`Lectura: ${p.effective_read?'sí':'no'} · escritura: ${p.effective_write?'sí':'no'}`:null);
 field(list,'Hora de consulta (UTC)',device.queried_at_utc);
 field(list,'READY / CSI','Sin observar; UART no abierta');
 const notes=document.createElement('p');notes.className='fine';notes.textContent=device.notes.join(' ');
 node.append(title,state,list,notes);return node;}
export async function refresh(){
 if($('refresh').disabled)return;
 $('refresh').disabled=true;$('status').textContent='Consultando metadatos locales…';
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),12000);
 try{
  const response=await fetch('/api/devices',{cache:'no-store',credentials:'same-origin',signal:controller.signal});
  if(!response.ok)throw Error(`HTTP ${response.status}`);
  const data=await response.json();
  if(!valid(data))throw Error('Respuesta de metadatos incompleta o inválida');
  $('devices').replaceChildren(...data.devices.map(card));
  $('time').textContent=`Hora de consulta (UTC): ${data.queried_at_utc} · fin: ${data.query_finished_at_utc}`;
  $('scope').textContent=[data.view,`Inventario completo en esta vista: ${data.inventory_complete?'sí':'no'}`,...data.inventory_notes].join('\n');
  $('status').textContent='Consulta terminada. USB y permisos solamente; READY y CSI siguen sin observar.';
 }catch(error){
  $('devices').replaceChildren(...expected.map(device=>card({...device,notes:[...device.notes,'No hay una respuesta actual verificable.']})));
  $('time').textContent='Hora de consulta: no hay una respuesta actual verificable.';
  $('scope').textContent=String(error);
  $('status').textContent='No verificable: no se pudo consultar el servidor local. No se deduce ausencia o desconexión.';
 }finally{clearTimeout(timer);$('refresh').disabled=false;}
}
$('devices').replaceChildren(...expected.map(card));
$('refresh').addEventListener('click',refresh);
refresh();
