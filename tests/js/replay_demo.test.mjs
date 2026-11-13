// Dependency-free DOM/canvas contract harness. This is not a browser screenshot.
import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
const page=fs.readFileSync(process.argv[2]??'results/local/demo-offline-c01-c03-shared-live-r1/index.html','utf8');
const data=page.match(/<script id="replay-data" type="application\/json">([\s\S]*?)<\/script>/)[1];
const code=page.match(/<script type="module">([\s\S]*?)<\/script>/)[1].replace(/export /g,'');
let points=0,marks=0,frame;
const context2d=new Proxy({}, {get:(o,k)=>o[k]??((...args)=>{for(const x of args)if(typeof x==='number')assert(Number.isFinite(x));if(k==='arc')points++;if(k==='fillRect')marks++;}),set:(o,k,v)=>(o[k]=v,true)});
class Element{
 constructor(id=''){this.id=id;this.listeners={};this.children=[];this.value='';this.checked=false;this.classList={toggle(){}};this.lookup={};this.textContent='';}
 addEventListener(k,f){this.listeners[k]=f;}dispatchEvent(e){this.listeners[e.type]?.(e);}click(){if(this.id==='compare')this.checked=!this.checked;this.dispatchEvent({type:'click'});this.dispatchEvent({type:'change'});}
 append(...x){this.children.push(...x);}replaceChildren(...x){this.children=x;}setAttribute(){}getContext(){return context2d;}
 set innerHTML(s){this.html=s;for(const key of ['.heat','.rssi','.sigma','.sample','.count','pre','h2','details'])this.lookup[key]=new Element(key);this.lookup['h2'].textContent=s.match(/<h2>(.*?)<\/h2>/)[1];}
 querySelector(k){return this.lookup[k];}
 getBoundingClientRect(){return {left:0,width:1100};}
}
const elements=Object.fromEntries(['session','condition','compare','play','restart','speed','time','clock','views','definitions','provenance','replay-data','devices-nav'].map(k=>[k,new Element(k)]));
elements['devices-nav'].href='http://127.0.0.1:8766/';
elements.session.value='C01';elements.condition.value='E';elements.compare.checked=true;elements.speed.value='1';elements['replay-data'].textContent=data;
const documentEvents={};
const document={documentElement:{dataset:{}},hidden:false,getElementById:k=>elements[k],createElement:()=>new Element(),createElementNS:()=>new Element(),addEventListener:(k,f)=>{documentEvents[k]=f;}};
const clock={now:0};
const unified=Boolean(process.env.REPLAY_HTTP)&&process.env.REPLAY_HTTP!=='separate';
const window={};const sandbox={document,window,console,BigInt,URL,location:process.env.REPLAY_HTTP?{protocol:'http:',pathname:unified?'/replay':'/index.html'}:undefined,performance:{now:()=>clock.now},requestAnimationFrame:f=>{frame=f;},fetch:()=>{throw Error('No external fetch allowed');}};
vm.createContext(sandbox);vm.runInContext(code,sandbox);
const state=()=>JSON.parse(JSON.stringify(window.replayState()));
assert.equal(document.documentElement.dataset.rendered,'true');assert.equal(elements.views.children.length,2);assert(points>500&&marks>10000);
assert.equal(state().cursor,30);const scales=state().scales;
assert.equal(elements['devices-nav'].href,unified?'/':'http://127.0.0.1:8766/');
assert(page.includes('C01/C03 · datos históricos'));assert(page.includes('connect-src \'none\''));
const step=ms=>{clock.now+=ms;frame(clock.now);};
const seek=t=>{elements.time.value=String(t);elements.time.dispatchEvent({type:'input'});};
const choose=(id,value)=>{elements[id].value=value;elements[id].dispatchEvent({type:'change'});};
elements.play.click();step(0);step(1000);assert.equal(state().cursor,1);assert(state().playing);
// Reproduce lost details/hover state during playback before the fix.
const stablePanel=elements.views.children[0];stablePanel.lookup.details.open=true;
stablePanel.lookup['.heat'].dispatchEvent({type:'mousemove',clientX:68+1012/60});
assert.match(stablePanel.lookup['.sample'].textContent,/Fila bruta/);
step(1000);
assert.equal(elements.views.children[0],stablePanel,'Playback must preserve the panel and its open details');
assert.equal(stablePanel.lookup.details.open,true);
assert.match(stablePanel.lookup['.sample'].textContent,/Fila bruta/);
elements.play.click();const paused=state().cursor;step(1000);assert.equal(state().cursor,paused);assert(!state().playing);
// Every advertised speed, restart while playing and pause without drift.
for(const speed of [0.5,1,2,4]){
 elements.restart.click();choose('speed',String(speed));elements.play.click();step(0);step(2000);
 assert.equal(state().cursor,2*speed);elements.play.click();step(1000);assert.equal(state().cursor,2*speed);
}
elements.restart.click();choose('speed','1');elements.play.click();step(0);step(1000);
choose('speed','2');step(500);assert.equal(state().cursor,2);
choose('speed','4');step(250);assert.equal(state().cursor,3);
assert(state().playing);elements.restart.click();assert.equal(state().cursor,0);assert(!state().playing);
seek(12.34);assert.equal(state().cursor,12.34);assert.match(elements.clock.textContent,/12,34/);
seek(29);elements.play.click();step(0);step(1000);assert.equal(state().cursor,30);assert(!state().playing);
assert.equal(elements.play.textContent,'Reproducir');elements.play.click();assert.equal(state().cursor,0);assert(state().playing);
step(0);step(250);assert.equal(state().cursor,1);
document.hidden=true;documentEvents.visibilitychange();const hiddenTime=state().cursor;
step(2000);assert(!state().playing);assert.equal(state().cursor,hiddenTime);
document.hidden=false;documentEvents.visibilitychange();assert(!state().playing);
// All original session/condition combinations, with/without comparison.
const original=JSON.parse(data);
for(const selected of ['C01','C03'])for(const condition of ['E','S']){
 choose('session',selected);choose('condition',condition);seek(30);
 assert.equal(elements.views.children.length,2);
 assert(elements.views.children[0].lookup.h2.textContent.startsWith(selected));
 const sessions=[...original.sessions].sort((a,b)=>a.id===selected?-1:1);
 elements.views.children.forEach((node,i)=>{
  const w=sessions[i].windows.find(w=>w.condition===condition);
  assert.equal(node.lookup['.count'].textContent,`${w.rows.length} / ${w.rows.length}`);
  assert.match(node.html,/Conexión completa: rechazada/);assert.match(node.html,/elegible exploratoria/);
 });
 assert.deepEqual(state().scales,scales);elements.compare.click();assert.equal(elements.views.children.length,1);
 elements.compare.click();assert.equal(elements.views.children.length,2);
}
// Hover respects exact timestamps and never exposes a row beyond the cursor.
choose('session','C01');choose('condition','E');seek(0);
const panel=elements.views.children[0];panel.lookup['.heat'].dispatchEvent({type:'mousemove',clientX:200});
assert.match(panel.lookup['.sample'].textContent,/Sin filas/);
seek(30);const windowData=original.sessions[0].windows[0],row=windowData.rows[0];
const seconds=Number(BigInt(row.t_ns)-BigInt(windowData.T0_ns))/1e9;
panel.lookup['.heat'].dispatchEvent({type:'mousemove',clientX:68+1012*seconds/30});
assert(panel.lookup['.sample'].textContent.includes(`host ${row.t_ns} ns`));
assert(panel.lookup['.sample'].textContent.includes(`Fila bruta ${row.reference.line_1based}`));
seek(0);assert.match(panel.lookup['.sample'].textContent,/Sin filas/);
assert.deepEqual(state().scales,scales);
// Controls can occur between animation frames, not only on frame boundaries.
elements.restart.click();choose('speed','1');elements.play.click();step(0);step(1000);
clock.now+=500;elements.play.click();assert.equal(state().cursor,1.5,'Pause must account for elapsed time since the last frame');
elements.restart.click();elements.play.click();step(0);step(1000);
clock.now+=500;choose('speed','4');step(500);
assert.equal(state().cursor,3.5,'Speed changes must split elapsed time at the control event');
seek(30);assert(!state().playing,'Seeking to the end must stop immediately');
elements.restart.click();seek(29);elements.play.click();clock.now+=500;
elements.play.click();assert.equal(state().cursor,30);assert(!state().playing,'Pausing at the end must not restart playback');
console.log(JSON.stringify({checks:'passed',play_pause_restart:true,speeds:[0.5,1,2,4],speed_change_while_playing:true,seek_and_end:true,
 visibility_pause:true,all_session_condition_selections:true,comparison:true,details_preserved:true,
 sample_provenance_and_cursor:true,between_frame_controls:true,navigation_context:unified?'HTTP unified':process.env.REPLAY_HTTP?'HTTP separate':'standalone',common_scales:true,drawn_points:points,drawn_marks:marks,actual_browser:false}));
