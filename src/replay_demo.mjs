// Existing relativeSeconds/observedStd helpers from offline_view.mjs are embedded first.
const replay=JSON.parse(document.getElementById('replay-data').textContent);
const $=id=>document.getElementById(id);
let cursor=30,playing=false,lastTick=null;
let speed=Number($('speed').value);
let mountedPanels=[],mountedKey=null;
const {heatmap,series}=makeCsiCharts(replay,()=>cursor);
function panel(session){const w=session.windows.find(x=>x.condition===$('condition').value),node=document.createElement('section');node.className='panel';
 node.innerHTML=`<h2>${session.id} · ${w.condition==='E'?'Vacío declarado':'Sentado declarado'}</h2><div class="metadata">${session.receiver} · USB ${session.usb_serial} · ${w.id}</div><div class="states"><span class="state rejected">Conexión completa: ${session.connection.quality_ok?'conforme':'rechazada'}</span><span class="state eligible">Ventana: ${w.eligibility.eligible?'elegible exploratoria':'no elegible'}</span><span class="state">Etiqueta humana: ${w.label.status}</span></div><div class="stats"><div>Filas observadas hasta el cursor<strong class="count"></strong></div><div>Cobertura de ventana completa<strong>${w.coverage.included_rows} filas / 30 s</strong></div><div>Hueco máximo, bordes incluidos<strong>${(w.coverage.max_gap_ns/1e6).toFixed(1)} ms</strong></div></div><p class="chart-title">Amplitud LLTF52 · tiempo × subportadora</p><div class="legend">0 <span class="gradient"></span> ${replay.scales.amplitude[1].toFixed(1)} · int8 sin calibrar · gris = máscara inválida</div><canvas class="heat" aria-label="Mapa de calor CSI LLTF52; no ubicación humana" role="img"></canvas><div class="sample">Pasa el puntero por el mapa para consultar una fila original.</div><p class="chart-title">RSSI original por fila</p><canvas class="rssi" role="img" aria-label="RSSI original en dBm"></canvas><p class="chart-title">σ temporal acumulada de las medias LLTF52</p><canvas class="sigma" role="img" aria-label="Variabilidad temporal acumulada, población de filas observadas"></canvas><p class="note">Bins originales de 5 s: ${w.coverage.bins_5s.join(' / ')}. Máscaras LLTF52: ${w.masks_complete?'completas':'incompletas'}. Sin fusión entre receptores o sesiones.</p><details><summary>Timestamps, etiqueta y calidad original</summary><pre></pre></details>`;
 node.querySelector('pre').textContent=JSON.stringify({T0_ns:w.T0_ns,T1_ns:w.T1_ns,label:w.label,coverage:w.coverage,connection:session.connection,window_eligibility:w.eligibility,strict_eligible:w.strict_eligible,full_window_features:w.features,source_manifest:session.source_manifest},null,2);
 const view={node,w,heat:node.querySelector('.heat'),rssi:node.querySelector('.rssi'),
  sigma:node.querySelector('.sigma'),count:node.querySelector('.count'),sample:node.querySelector('.sample'),hoverTime:null};
 view.heat.addEventListener('mousemove',e=>{const rect=view.heat.getBoundingClientRect();if(rect.width<=0)return;
  view.hoverTime=Math.max(0,Math.min(30,((e.clientX-rect.left)/rect.width*1100-68)/(1080-68)*30));updateSample(view);});
 return view;}
function updateSample(view){if(view.hoverTime===null)return;const {w,hoverTime:t}=view;
 const visible=w.rows.filter(r=>relativeSeconds(r.t_ns,w.T0_ns)<=cursor);
 if(!visible.length){view.sample.textContent='Sin filas observadas hasta el cursor.';return;}
 const row=visible.reduce((a,b)=>Math.abs(relativeSeconds(a.t_ns,w.T0_ns)-t)<Math.abs(relativeSeconds(b.t_ns,w.T0_ns)-t)?a:b);
 view.sample.textContent=`Fila bruta ${row.reference.line_1based} · callback ${row.callback_id} · host ${row.t_ns} ns · t=${relativeSeconds(row.t_ns,w.T0_ns).toFixed(6)} s · RSSI ${row.rssi} dBm · inicio de lectura ${row.first_read_ns} ns · RX uint32 ${row.local_timestamp_us} μs. Muestra más cercana, sin interpolar.`;}
function paintPanel(view){const {w}=view;
 const count=w.rows.filter(row=>relativeSeconds(row.t_ns,w.T0_ns)<=cursor).length;view.count.textContent=`${count} / ${w.rows.length}`;
 heatmap(view.heat,w);series(view.rssi,w,'rssi',replay.scales.rssi,'RSSI dBm');
 series(view.sigma,w,'sigma_prefix',replay.scales.sigma,'σ, int8 sin calibrar');updateSample(view);}
function render(){const selected=$('session').value,compare=$('compare').checked;
 const key=JSON.stringify([selected,$('condition').value,compare]);
 if(key!==mountedKey){
  mountedPanels=replay.sessions.filter(s=>compare||s.id===selected).sort((a,b)=>a.id===selected?-1:1).map(panel);
  $('views').classList.toggle('single',!compare);$('views').replaceChildren(...mountedPanels.map(view=>view.node));mountedKey=key;
 }
 for(const view of mountedPanels)paintPanel(view);
 $('clock').textContent=`${cursor.toFixed(2).replace('.',',')} / 30 s`;$('time').value=cursor;$('play').textContent=playing?'Pausar':'Reproducir';
 document.documentElement.dataset.rendered='true';document.documentElement.dataset.time=String(cursor);}
function advance(now){now=Math.max(now,lastTick??now);
 if(playing&&lastTick!==null)cursor=Math.min(30,cursor+(now-lastTick)/1000*speed);
 if(cursor>=30)playing=false;lastTick=now;}
function tick(now){if(playing){advance(now);render();}requestAnimationFrame(tick);}
$('play').addEventListener('click',()=>{const wasPlaying=playing;advance(performance.now());
 if(wasPlaying)playing=false;else{if(cursor>=30)cursor=0;playing=true;}render();});
$('restart').addEventListener('click',()=>{cursor=0;playing=false;lastTick=performance.now();render();});
$('time').addEventListener('input',()=>{cursor=Number($('time').value);lastTick=performance.now();playing=playing&&cursor<30;render();});
$('speed').addEventListener('change',()=>{advance(performance.now());speed=Number($('speed').value);render();});
for(const id of ['session','condition','compare'])$(id).addEventListener('change',render);
document.addEventListener('visibilitychange',()=>{if(document.hidden){advance(performance.now());playing=false;render();}});
if(typeof location!=='undefined'&&['http:','https:'].includes(location.protocol)&&location.pathname==='/replay')$('devices-nav').href='/';
$('definitions').replaceChildren(...Object.entries(replay.definitions).map(([key,value])=>{const p=document.createElement('p');p.className='note';p.textContent=value;return p;}));
$('provenance').textContent=JSON.stringify(replay.sessions.map(s=>({session:s.id,bundle:s.source_bundle,manifest:s.source_manifest,partition_group:s.partition_group,integrity_ok:s.integrity_ok,replay_ok:s.replay_ok,provenance:s.acquisition_provenance})),null,2);
// A descriptive view only: no classifier, confidence, person count or floor plan.
window.replayState=()=>({cursor,playing,session:$('session').value,condition:$('condition').value,compare:$('compare').checked,
 scales:replay.scales,rows:replay.sessions.map(s=>({id:s.id,windows:s.windows.map(w=>({id:w.id,n:w.rows.length}))}))});
render();requestAnimationFrame(tick);
