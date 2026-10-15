"""Visionneuse d'échographie : zoom, loupe, comparaison, Netteté et navigation entre zones à inspecter."""
from __future__ import annotations

import base64
import io
import json

import streamlit.components.v1 as components
from PIL import Image


def data_uri(img: Image.Image, fmt: str = "PNG", quality: int = 92) -> str:
    buf = io.BytesIO()
    if fmt == "JPEG":
        img.convert("RGB").save(buf, format="JPEG", quality=quality)
    else:
        img.save(buf, format="PNG", optimize=True)
    return f"data:image/{fmt.lower()};base64," + base64.b64encode(buf.getvalue()).decode()


TEMPLATE = r"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<style>
@font-face{font-family:'Inter';src:url('/app/static/fonts/Inter-var.woff2') format('woff2');font-weight:100 900}
@font-face{font-family:'IBM Plex Mono';src:url('/app/static/fonts/IBMPlexMono-500.woff2') format('woff2');font-weight:500}
:root{--wine:#8E1D4A;--line:#EFE1EA;--ink:#2A1F2C;--muted:#6F6271;--lav:#F4EAF5;--lvl:__LEVEL__}
*{box-sizing:border-box}
html,body{margin:0;height:100%;font-family:'Inter',system-ui,sans-serif;color:var(--ink);background:transparent}
.wrap{height:100%;display:flex;flex-direction:column;gap:10px}
.stage{position:relative;flex:1;min-height:240px;border-radius:16px;overflow:hidden;background:#151015;cursor:grab;touch-action:none;
  box-shadow:0 18px 40px -24px rgba(60,10,35,.7)}
.stage.drag{cursor:grabbing}
.view{position:absolute;left:0;top:0;transform-origin:0 0}
.view.anim{transition:transform .55s cubic-bezier(.2,.8,.2,1)}
.view img{position:absolute;inset:0;width:100%;height:100%;user-select:none;-webkit-user-drag:none}
.view svg{position:absolute;inset:0;width:100%;height:100%;overflow:visible;pointer-events:none}
.hidden{display:none !important}
/* barre d'outils flottante */
.tools{position:absolute;left:12px;right:12px;top:12px;display:flex;flex-wrap:wrap;gap:4px;align-items:center;z-index:5;pointer-events:none}
.tb{pointer-events:auto;display:flex;align-items:center;gap:2px;background:rgba(22,14,20,.78);backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,.08);
  border-radius:12px;padding:4px}
.b{border:0;background:transparent;color:#EDE3EA;border-radius:9px;padding:7px 10px;font:500 13px 'Inter',sans-serif;cursor:pointer;display:inline-flex;
  align-items:center;gap:6px;min-height:34px;white-space:nowrap}
.b:hover{background:rgba(255,255,255,.08)}
.b[aria-pressed="true"]{background:var(--wine);color:#fff;box-shadow:0 0 16px -2px rgba(214,51,132,.55)}
.b:focus-visible{outline:2px solid #F4A6C6;outline-offset:1px}
.zv{font:500 12px 'IBM Plex Mono',monospace;color:#fff;min-width:46px;text-align:center}
.sep{width:1px;height:20px;background:rgba(255,255,255,.12);margin:0 3px}
/* vue globale */
.mini{position:absolute;left:12px;top:64px;width:118px;border-radius:10px;overflow:hidden;background:rgba(22,14,20,.78);
  border:1px solid rgba(255,255,255,.1);padding:6px;z-index:4;opacity:0;transition:opacity .25s;pointer-events:none}
.mini.on{opacity:1}
.mini .t{font:500 9px 'IBM Plex Mono',monospace;color:#C9B8C3;letter-spacing:.08em;margin-bottom:4px;display:flex;justify-content:space-between}
.mini .t i{width:6px;height:6px;border-radius:50%;background:#E0457B;display:inline-block}
.mini .box{position:relative}.mini img{display:block;width:100%;border-radius:4px}
.mini .r{position:absolute;border:1.5px solid #fff;border-radius:3px;box-shadow:0 0 0 999px rgba(0,0,0,.35)}
/* étiquettes de zone */
.tags{position:absolute;inset:0;pointer-events:none;z-index:3}
.tag{position:absolute;transform:translate(-50%,-100%);pointer-events:auto;cursor:pointer;display:flex;align-items:center;gap:6px;
  padding:4px 10px 4px 5px;border-radius:999px;background:var(--c);color:#fff;font:600 12px 'Inter';white-space:nowrap;
  box-shadow:0 0 18px -2px var(--c);margin-top:-12px;transition:opacity .2s}
.tag .n{width:18px;height:18px;border-radius:50%;background:rgba(255,255,255,.25);display:grid;place-items:center;font-size:11px}
.tag::after{content:"";position:absolute;left:50%;top:100%;width:1.5px;height:12px;background:var(--c);opacity:.8}
.tag.att{background:rgba(22,14,20,.8);color:#F4C6DA;border:1px dashed #F472B6;box-shadow:none}
.tag.att::after{background:#F472B6}
/* loupe */
.loupe{position:absolute;right:12px;bottom:44px;display:flex;gap:10px;align-items:flex-end;z-index:4;pointer-events:none;opacity:0;transition:opacity .25s}
.loupe.on{opacity:1}
.loupe canvas{width:150px;height:150px;border-radius:50%;border:2px solid rgba(255,255,255,.85);box-shadow:0 10px 30px rgba(0,0,0,.55),0 0 0 6px rgba(142,29,74,.35);background:#000}
.loupe .lt{color:#fff;font:600 13px 'Inter';text-shadow:0 1px 4px #000;max-width:150px}
.loupe .lt small{display:block;font:500 11px 'IBM Plex Mono';color:#D9C6D1;margin-top:3px}
/* comparaison */
.cmp{position:absolute;inset:0;overflow:hidden;pointer-events:none}
.cmp .clip{position:absolute;inset:0;clip-path:inset(0 0 0 50%)}
.split{position:absolute;top:0;bottom:0;width:2px;background:#fff;z-index:4;cursor:ew-resize;box-shadow:0 0 12px rgba(0,0,0,.6)}
.split::before{content:"‹ ›";position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);background:#fff;color:var(--wine);
  font:700 13px 'Inter';border-radius:999px;padding:6px 9px;box-shadow:0 4px 14px rgba(0,0,0,.4)}
.lbl{position:absolute;top:64px;z-index:4;font:500 11px 'IBM Plex Mono';color:#fff;background:rgba(22,14,20,.75);padding:4px 8px;border-radius:8px}
/* notes bas */
.note{position:absolute;left:12px;bottom:12px;z-index:4;display:flex;gap:6px;align-items:center;font:500 12px 'Inter';color:#E9DDE4;
  background:rgba(22,14,20,.7);padding:5px 10px;border-radius:999px;backdrop-filter:blur(6px)}
.note.vis{background:rgba(142,29,74,.9);color:#fff}
/* panneau des zones */
.panel{background:#fff;border:1px solid var(--line);border-radius:16px;padding:12px 14px;display:flex;flex-direction:column;gap:9px}
.zrow{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.nav{border:1px solid var(--line);background:#fff;border-radius:10px;width:34px;height:34px;cursor:pointer;color:var(--ink);font-size:16px}
.nav:hover{background:var(--lav);color:var(--wine)}
.zc{font:600 14px 'Inter';margin-right:4px}
.chips{display:flex;gap:6px;flex-wrap:wrap}
.chip{border:1px solid transparent;background:#FAF5FA;border-radius:10px;padding:7px 11px;cursor:pointer;font:500 13px 'Inter';color:var(--ink);
  display:flex;align-items:center;gap:7px;min-height:36px}
.chip .d{width:8px;height:8px;border-radius:50%;background:var(--c);box-shadow:0 0 8px var(--c)}
.chip[aria-current="true"]{background:color-mix(in srgb,var(--c) 14%,#fff);border-color:color-mix(in srgb,var(--c) 45%,transparent);color:var(--c)}
.keys{display:flex;gap:12px;flex-wrap:wrap;font:400 12px 'IBM Plex Mono';color:var(--muted)}
.keys kbd{font:500 11px 'IBM Plex Mono';border:1px solid var(--line);border-bottom-width:2px;border-radius:5px;padding:1px 5px;background:#fff;margin-right:4px}
.cap{font-size:13.5px;color:var(--muted);line-height:1.5}.cap b{color:var(--ink)}
@keyframes dash{to{stroke-dashoffset:-24}}.att-path{animation:dash 1.6s linear infinite}
@keyframes breathe{0%,100%{opacity:.5}50%{opacity:1}}.halo{animation:breathe 2.6s ease-in-out infinite}
@media (prefers-reduced-motion:reduce){.att-path,.halo{animation:none}.view.anim{transition:none}}
@media (max-width:560px){.b .tx{display:none}.loupe canvas{width:104px;height:104px}.loupe .lt{display:none}.mini{display:none}}
</style></head><body>
<div class="wrap" id="wrap">
 <div class="stage" id="stage" aria-label="Échographie : molette ou pincement pour zoomer, glisser pour se déplacer">
  <div class="view" id="view">
    <img id="imgBase" src="__BASE__" alt="Échographie">
    <img id="imgSharp" class="hidden" alt="">
    <img id="imgHeat" class="hidden" alt="">
    <div class="cmp hidden" id="cmp"><div class="clip" id="clip"><img id="imgCmp" alt="" style="position:absolute;inset:0;width:100%;height:100%"></div></div>
    <svg id="ov" viewBox="0 0 __W__ __H__" preserveAspectRatio="none">
      <defs><filter id="glow" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="__BLUR__" result="b"/>
        <feMerge><feMergeNode in="b"/><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>
      <g id="gZones"></g>
    </svg>
  </div>
  <div class="tags" id="tags"></div>
  <div class="split hidden" id="split"></div>
  <span class="lbl hidden" id="lblL" style="left:12px">ORIGINALE</span><span class="lbl hidden" id="lblR" style="right:12px">NETTETÉ</span>
  <div class="tools">
    <div class="tb" role="group" aria-label="Zoom">
      <button class="b" id="zOut" aria-label="Dézoomer">−</button><span class="zv" id="zv">100 %</span>
      <button class="b" id="zIn" aria-label="Zoomer">+</button><span class="sep"></span>
      <button class="b" id="zFit" title="Ajuster à la fenêtre"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2"/><rect x="8" y="8" width="8" height="8" rx="1"/></svg><span class="tx">Ajuster</span></button>
      <button class="b" id="fs" title="Plein écran" aria-label="Plein écran"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/></svg></button>
    </div>
    <div class="tb" role="group" aria-label="Calques">
      <button class="b" id="tContour" aria-pressed="true"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M20 6 9 17l-5-5"/></svg><span class="tx">Contour</span></button>
      <button class="b" id="tAtt" aria-pressed="false"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="1"/><circle cx="5" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="12" cy="5" r="1"/><circle cx="12" cy="19" r="1"/></svg><span class="tx">Attention du modèle</span></button>
      <button class="b" id="tSharp" aria-pressed="false" title="Amélioration visuelle uniquement"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="m21.64 3.64-1.28-1.28a1.21 1.21 0 0 0-1.72 0L2.36 18.64a1.21 1.21 0 0 0 0 1.72l1.28 1.28a1.2 1.2 0 0 0 1.72 0L21.64 5.36a1.2 1.2 0 0 0 0-1.72"/><path d="m14 7 3 3"/><path d="M5 6v4M19 14v4M10 2v2M7 8H3M21 16h-4M11 3H9"/></svg><span class="tx">Netteté</span></button>
      <button class="b" id="tCmp" aria-pressed="false"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M12 3v18"/></svg><span class="tx">Comparer</span></button>
    </div>
  </div>
  <div class="mini" id="mini"><div class="t">VUE GLOBALE <i></i></div><div class="box"><img src="__BASE__" alt=""><div class="r" id="miniR"></div></div></div>
  <div class="loupe" id="loupe"><div class="lt" id="lt"></div><canvas id="lc" width="300" height="300"></canvas></div>
  <span class="note" id="note"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg><span id="noteT">Vue originale</span></span>
 </div>
 <div class="panel">
  <div class="zrow"><button class="nav" id="prev" aria-label="Zone précédente">‹</button><span class="zc" id="zc"></span>
    <button class="nav" id="next" aria-label="Zone suivante">›</button></div>
  <div class="chips" id="chips"></div>
  <div class="keys"><span><kbd>←</kbd><kbd>→</kbd>Changer de zone</span><span><kbd>Z</kbd>Zoomer</span><span><kbd>L</kbd>Loupe</span><span><kbd>0</kbd>Réinitialiser</span></div>
  <div class="cap" id="cap"></div>
 </div>
</div>
<script>
const W=__W__, H=__H__, ZONES=__ZONES__, LVL='__LEVEL__', SHARP='__SHARP__', HEAT='__HEAT__';
const $=id=>document.getElementById(id), stage=$('stage'), view=$('view'), NS='http://www.w3.org/2000/svg';
let fit=1, s=1, tx=0, ty=0, cur=-1, split=.5, loupeOn=true, hover=null;
const imgBase=$('imgBase'), imgSharp=$('imgSharp');
const zoneColor=z=>z.kind==='lesion'?LVL:'#F472B6';
const zoneName=(z,i)=>z.kind==='lesion'?`Zone suspecte ${i+1}`:`Zone d'attention ${i+1}`;
const pressed=id=>$(id).getAttribute('aria-pressed')==='true';
function rect(){return stage.getBoundingClientRect();}
function layout(){const th=document.querySelector('.tools').offsetHeight+20; $('mini').style.top=th+'px'; $('lblL').style.top=th+'px'; $('lblR').style.top=th+'px'; const r=rect(); fit=Math.min(r.width/W,r.height/H); view.style.width=(W*fit)+'px'; view.style.height=(H*fit)+'px';}
function clampPan(){const r=rect(),vw=W*fit*s,vh=H*fit*s;
  tx=vw<=r.width?(r.width-vw)/2:Math.min(0,Math.max(r.width-vw,tx)); ty=vh<=r.height?(r.height-vh)/2:Math.min(0,Math.max(r.height-vh,ty));}
function apply(anim){
  clampPan(); view.classList.toggle('anim',!!anim);
  view.style.transform=`translate(${tx}px,${ty}px) scale(${s})`;
  $('zv').textContent=Math.round(s*100)+' %';
  const r=rect(),vw=W*fit*s,vh=H*fit*s; $('mini').classList.toggle('on',s>1.05);
  const x0=Math.max(0,-tx/vw),y0=Math.max(0,-ty/vh),x1=Math.min(1,(r.width-tx)/vw),y1=Math.min(1,(r.height-ty)/vh);
  Object.assign($('miniR').style,{left:x0*100+'%',top:y0*100+'%',width:(x1-x0)*100+'%',height:(y1-y0)*100+'%'});
  const place=()=>{document.querySelectorAll('.tag').forEach(t=>{const z=ZONES[+t.dataset.i],[x,y,w]=z.bbox;
    t.style.left=(tx+(x+w/2)*fit*s)+'px'; t.style.top=(ty+y*fit*s)+'px';});
    const sx=tx+split*W*fit*s; $('split').style.left=(sx-1)+'px'; drawLoupe();};
  if(anim){setTimeout(place,560);} place();
}
function zoomAt(f,cx,cy,anim){const ns=Math.min(10,Math.max(1,s*f)); tx=cx-(cx-tx)*ns/s; ty=cy-(cy-ty)*ns/s; s=ns; apply(anim);}
function focusZone(i){
  cur=i; renderChips();
  if(i<0){s=1;tx=0;ty=0;apply(true);caption();return;}
  if(ZONES[i].kind==='attention'&&!pressed('tAtt')) $('tAtt').click();
  const [x,y,w,h]=ZONES[i].bbox,r=rect(),pad=2.4;
  s=Math.min(8,Math.max(1.4,Math.min(r.width/(w*fit*pad),r.height/(h*fit*pad))));
  tx=r.width/2-(x+w/2)*fit*s; ty=r.height/2-(y+h/2)*fit*s; apply(true); caption();
}
function caption(){
  const c=$('cap'); $('zc').textContent=ZONES.length?(cur<0?`Vue d'ensemble · ${ZONES.length} zone(s)`:`Zone ${cur+1} sur ${ZONES.length}`):'Aucune zone signalée';
  if(!ZONES.length){c.innerHTML='Le modèle ne signale aucune zone particulière sur cette image.';return;}
  if(cur<0){c.innerHTML='Cliquez une zone, une étiquette sur l’image, ou utilisez ‹ › pour zoomer dessus.';return;}
  const z=ZONES[cur];
  c.innerHTML=z.kind==='lesion'
   ?`<b>Zone ${cur+1} · contour détecté</b> — ${z.area_pct.toFixed(1)} % de l'image. Taille réelle non mesurable (échelle inconnue).`
   :`<b>Zone ${cur+1} · attention du modèle</b> — hors contour : région qui a pesé dans la décision, à vérifier visuellement. Ce n'est pas une lésion confirmée.`;
}
function renderChips(){
  const box=$('chips'); box.innerHTML='';
  [{l:"Vue d'ensemble",i:-1,c:'#8E1D4A'}].concat(ZONES.map((z,i)=>({l:zoneName(z,i),i,c:zoneColor(z)}))).forEach(o=>{
    const b=document.createElement('button'); b.className='chip'; b.style.setProperty('--c',o.c); b.setAttribute('aria-current',o.i===cur);
    b.innerHTML=(o.i<0?'':'<span class="d"></span>')+o.l; b.onclick=()=>focusZone(o.i); box.appendChild(b);});
}
function drawZones(){
  const g=$('gZones'), tags=$('tags'), sw=Math.max(W,H)/260; g.innerHTML=''; tags.innerHTML='';
  ZONES.forEach((z,i)=>{
    const col=zoneColor(z), grp=document.createElementNS(NS,'g'); grp.dataset.kind=z.kind;
    z.paths.forEach(p=>{
      const d='M'+p.map(q=>q.join(',')).join('L')+'Z';
      if(z.kind==='lesion'){const h=document.createElementNS(NS,'path'); h.setAttribute('d',d);
        Object.entries({fill:col,'fill-opacity':.08,stroke:col,'stroke-width':sw*2.6,'stroke-opacity':.35,filter:'url(#glow)',class:'halo','stroke-linejoin':'round'}).forEach(([k,v])=>h.setAttribute(k,v)); grp.appendChild(h);}
      const e=document.createElementNS(NS,'path'); e.setAttribute('d',d);
      const a={fill:'none',stroke:col,'stroke-linejoin':'round','vector-effect':'non-scaling-stroke'};
      if(z.kind!=='lesion'){a['stroke-dasharray']='7 5';a['class']='att-path';}
      Object.entries(a).forEach(([k,v])=>e.setAttribute(k,v)); e.style.strokeWidth=(z.kind==='lesion'?2.4:2)+'px'; grp.appendChild(e);});
    g.appendChild(grp);
    const t=document.createElement('div'); t.className='tag'+(z.kind==='lesion'?'':' att'); t.dataset.i=i; t.dataset.kind=z.kind;
    t.style.setProperty('--c',col); t.innerHTML=`<span class="n">${i+1}</span>${z.kind==='lesion'?'Zone suspecte':'Attention'}`;
    t.onclick=()=>focusZone(i); tags.appendChild(t);
  });
}
function setVisible(kind,on){document.querySelectorAll(`#gZones g[data-kind="${kind}"], .tag[data-kind="${kind}"]`).forEach(e=>e.classList.toggle('hidden',!on));}
/* loupe */
const lc=$('lc'), ctx=lc.getContext('2d');
function drawLoupe(){
  let pt=hover;
  if(!pt&&cur>=0){const [x,y,w,h]=ZONES[cur].bbox; pt={x:x+w/2,y:y+h/2};}
  const on=loupeOn&&pt&&!pressed('tCmp'); $('loupe').classList.toggle('on',!!on); if(!on) return;
  const src=pressed('tSharp')?imgSharp:imgBase; if(!src.complete||!src.naturalWidth) return;
  const k=src.naturalWidth/W; let half=75/(fit*s*2.5);
  if(!hover&&cur>=0){const [,,w,h]=ZONES[cur].bbox; half=Math.max(w,h)*0.7;}
  const mag=75/(half*fit*s);
  ctx.save(); ctx.clearRect(0,0,lc.width,lc.height); ctx.beginPath(); ctx.arc(150,150,150,0,Math.PI*2); ctx.clip();
  ctx.drawImage(src,(pt.x-half)*k,(pt.y-half)*k,2*half*k,2*half*k,0,0,lc.width,lc.height);
  const sc=lc.width/(2*half); ctx.translate(-(pt.x-half)*sc,-(pt.y-half)*sc); ctx.scale(sc,sc);
  ZONES.forEach(z=>{ if(z.kind==='attention'&&!pressed('tAtt')) return; if(z.kind==='lesion'&&!pressed('tContour')) return;
    ctx.strokeStyle=zoneColor(z); ctx.lineWidth=3/sc; ctx.setLineDash(z.kind==='lesion'?[]:[8/sc,6/sc]); ctx.shadowColor=zoneColor(z); ctx.shadowBlur=8;
    z.paths.forEach(p=>{ctx.beginPath(); p.forEach((q,j)=>j?ctx.lineTo(q[0],q[1]):ctx.moveTo(q[0],q[1])); ctx.closePath(); ctx.stroke();});});
  ctx.restore();
  const mt='×'+mag.toFixed(1).replace('.',',');
  $('lt').innerHTML=hover?`Loupe ${mt}<small>suit le curseur</small>`:`${zoneName(ZONES[cur],cur)}<small>aperçu de la zone</small>`;
}
/* boutons */
function tog(id){const on=!pressed(id); $(id).setAttribute('aria-pressed',on); return on;}
function note(){const vis=pressed('tSharp')||pressed('tCmp'); $('note').classList.toggle('vis',vis);
  $('noteT').textContent=vis?'Amélioration visuelle uniquement — l’analyse utilise l’image originale':'Vue originale';}
$('tContour').onclick=()=>{setVisible('lesion',tog('tContour')); drawLoupe();};
$('tAtt').onclick=()=>{const on=tog('tAtt'); const im=$('imgHeat'); if(on&&!im.src) im.src=HEAT; im.classList.toggle('hidden',!on); setVisible('attention',on); drawLoupe();};
$('tSharp').onclick=()=>{const on=tog('tSharp'); if(on&&!imgSharp.src){imgSharp.src=SHARP; imgSharp.onload=drawLoupe;} imgSharp.classList.toggle('hidden',!on||pressed('tCmp')); note(); drawLoupe();};
$('tCmp').onclick=()=>{const on=tog('tCmp'); const im=$('imgCmp'); if(on&&!im.src) im.src=SHARP;
  ['cmp','split','lblL','lblR'].forEach(k=>$(k).classList.toggle('hidden',!on)); imgSharp.classList.toggle('hidden',on||!pressed('tSharp')); note(); apply(false);};
$('zIn').onclick=()=>{const r=rect(); zoomAt(1.5,r.width/2,r.height/2,true);};
$('zOut').onclick=()=>{const r=rect(); zoomAt(1/1.5,r.width/2,r.height/2,true);};
$('zFit').onclick=()=>focusZone(-1);
$('fs').onclick=()=>{const el=$('wrap'); if(document.fullscreenElement) document.exitFullscreen(); else if(el.requestFullscreen) el.requestFullscreen().catch(()=>{});};
if(!document.fullscreenEnabled) $('fs').classList.add('hidden');
$('prev').onclick=()=>{if(ZONES.length) focusZone(cur<=0?ZONES.length-1:cur-1);};
$('next').onclick=()=>{if(ZONES.length) focusZone(cur>=ZONES.length-1?0:cur+1);};
/* interactions */
stage.addEventListener('wheel',e=>{e.preventDefault(); const r=rect(); zoomAt(e.deltaY<0?1.15:1/1.15,e.clientX-r.left,e.clientY-r.top);},{passive:false});
stage.addEventListener('dblclick',e=>{if(e.target.closest('button,.tag'))return; const r=rect(); zoomAt(2,e.clientX-r.left,e.clientY-r.top,true);});
const pts=new Map(); let last=null,pinch=null,dragSplit=false;
$('split').addEventListener('pointerdown',e=>{dragSplit=true; e.stopPropagation(); $('split').setPointerCapture(e.pointerId);});
$('split').addEventListener('pointermove',e=>{if(!dragSplit)return; const r=rect(); split=Math.min(1,Math.max(0,((e.clientX-r.left)-tx)/(W*fit*s)));
  $('clip').style.clipPath=`inset(0 0 0 ${split*100}%)`; apply(false);});
$('split').addEventListener('pointerup',()=>dragSplit=false);
stage.addEventListener('pointerdown',e=>{if(e.target.closest('button,.tag,.split'))return; stage.setPointerCapture(e.pointerId); pts.set(e.pointerId,{x:e.clientX,y:e.clientY}); stage.classList.add('drag'); last={x:e.clientX,y:e.clientY};});
stage.addEventListener('pointermove',e=>{
  const r=rect();
  if(e.pointerType==='mouse'&&!pts.size&&!e.target.closest('.tools')){hover={x:((e.clientX-r.left)-tx)/(fit*s),y:((e.clientY-r.top)-ty)/(fit*s)};
    if(hover.x<0||hover.y<0||hover.x>W||hover.y>H) hover=null; drawLoupe();}
  if(!pts.has(e.pointerId))return; pts.set(e.pointerId,{x:e.clientX,y:e.clientY});
  if(pts.size===2){const [a,b]=[...pts.values()],d=Math.hypot(a.x-b.x,a.y-b.y); if(pinch) zoomAt(d/pinch,(a.x+b.x)/2-r.left,(a.y+b.y)/2-r.top); pinch=d; return;}
  if(last){tx+=e.clientX-last.x; ty+=e.clientY-last.y; last={x:e.clientX,y:e.clientY}; apply(false);}
});
stage.addEventListener('pointerleave',()=>{hover=null; drawLoupe();});
['pointerup','pointercancel'].forEach(t=>stage.addEventListener(t,e=>{pts.delete(e.pointerId); pinch=null; if(!pts.size){last=null; stage.classList.remove('drag');}}));
document.addEventListener('keydown',e=>{const k=e.key.toLowerCase();
  if(k==='arrowright')$('next').click(); if(k==='arrowleft')$('prev').click(); if(k==='+')$('zIn').click(); if(k==='-')$('zOut').click();
  if(k==='0')focusZone(-1); if(k==='z'){ if(cur<0&&ZONES.length) focusZone(0); else {const r=rect(); zoomAt(1.6,r.width/2,r.height/2,true);} }
  if(k==='l'){loupeOn=!loupeOn; drawLoupe();}});
window.addEventListener('resize',()=>{layout(); apply(false);});
document.addEventListener('fullscreenchange',()=>setTimeout(()=>{layout(); apply(false);},50));
imgBase.onload=drawLoupe;
drawZones(); setVisible('attention',false); layout(); s=1; apply(false); renderChips(); caption(); note();
</script></body></html>"""


def render_viewer(base: Image.Image, sharp: Image.Image, heat: Image.Image | None, zones: list[dict],
                  natural_size: tuple[int, int], level_color: str, height: int = 720):
    w, h = natural_size
    page = (TEMPLATE.replace("__BASE__", data_uri(base, "JPEG"))
            .replace("__SHARP__", data_uri(sharp, "JPEG"))
            .replace("__HEAT__", data_uri(heat) if heat is not None else "")
            .replace("__ZONES__", json.dumps(zones))
            .replace("__LEVEL__", level_color)
            .replace("__BLUR__", f"{max(w, h) / 160:.1f}")
            .replace("__W__", str(w)).replace("__H__", str(h)))
    components.html(page, height=height)
