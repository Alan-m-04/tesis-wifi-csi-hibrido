// Shared original CSI charts; no transport or model.
export function makeCsiCharts(replay,getCursor){
const colors=['#172b62','#117c98','#44d5b0','#f0e778'];
function color(value,max){if(value===null)return '#8c8292';const p=Math.max(0,Math.min(1,value/max))*3,i=Math.min(2,Math.floor(p)),f=p-i;
 const rgb=h=>[1,3,5].map(k=>parseInt(h.slice(k,k+2),16));const x=rgb(colors[i]),y=rgb(colors[i+1]);return `rgb(${x.map((v,j)=>Math.round(v+(y[j]-v)*f)).join(',')})`;}
function base(canvas,height,xlabel,ylabel){canvas.width=1100;canvas.height=height;const ctx=canvas.getContext('2d');ctx.fillStyle='#0d1723';ctx.fillRect(0,0,1100,height);
 const left=68,right=1080,top=22,bottom=height-36,X=t=>left+(right-left)*t/30;
 ctx.font='13px system-ui';ctx.strokeStyle='#31465e';ctx.fillStyle='#b5c4d6';ctx.beginPath();ctx.moveTo(left,top);ctx.lineTo(left,bottom);ctx.lineTo(right,bottom);ctx.stroke();
 for(let t=0;t<=30;t+=5){ctx.fillText(String(t),X(t)-5,height-16);ctx.strokeStyle='#25374b';ctx.beginPath();ctx.moveTo(X(t),top);ctx.lineTo(X(t),bottom);ctx.stroke();}
 ctx.fillText(xlabel,600,height-2);ctx.fillText(ylabel,8,13);return {ctx,left,right,top,bottom,X};}
function playhead(chart){const cursor=getCursor();const {ctx,X,top,bottom}=chart;ctx.strokeStyle='#fff';ctx.lineWidth=1.5;ctx.beginPath();ctx.moveTo(X(cursor),top);ctx.lineTo(X(cursor),bottom);ctx.stroke();}
function heatmap(canvas,w){const cursor=getCursor();const chart=base(canvas,360,'Segundos host desde T0','Tono LLTF'),{ctx,left,top,bottom,X}=chart;
 const h=(bottom-top)/52;
 for(const row of w.rows){const t=relativeSeconds(row.t_ns,w.T0_ns);if(t>cursor)break;
  for(let k=0;k<52;k++){ctx.fillStyle=color(row.amplitudes[k],replay.scales.amplitude[1]);ctx.fillRect(X(t)-.7,top+(51-k)*h,1.4,Math.max(.8,h-.4));}}
 ctx.fillStyle='#b5c4d6';ctx.font='12px system-ui';for(const k of [-26,-13,-1,1,13,26]){const i=replay.tone_indices.indexOf(k);ctx.fillText(String(k),left-35,top+(51-i)*h+7);}
 playhead(chart);}
function series(canvas,w,key,range,label){const cursor=getCursor();const chart=base(canvas,175,'Segundos desde T0',label),{ctx,left,right,top,bottom,X}=chart;
 const Y=v=>bottom-(v-range[0])/(range[1]-range[0]||1)*(bottom-top);
 ctx.fillStyle='#b5c4d6';ctx.font='12px system-ui';for(let i=0;i<=3;i++){const v=range[0]+(range[1]-range[0])*i/3;ctx.fillText(v.toFixed(1),7,Y(v)+4);}
 ctx.fillStyle=key==='rssi'?'#5edbd0':'#ffcf78';for(const row of w.rows){const t=relativeSeconds(row.t_ns,w.T0_ns);if(t>cursor)break;if(row[key]===null)continue;ctx.beginPath();ctx.arc(X(t),Y(row[key]),2.7,0,2*Math.PI);ctx.fill();}playhead(chart);}
return {heatmap,series};
}
