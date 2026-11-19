#!/usr/bin/env python3
"""Árvore de estratégia do Termo em estilo "elipse" (inspirado no vídeo do 3Blue1Brown).

Centro = 1º palpite. Cada nó mostra (em cima) o palpite com o feedback recebido e
(embaixo, em preto) o PRÓXIMO palpite. Tamanho do nó ~ nº de jogos que passam por ele.
Acertos (verde) ficam no anel externo.

Uso:  python gerar_arvore_estilo.py entrada.json [saida.html]
"""
import json, sys

src = sys.argv[1]
dst = sys.argv[2] if len(sys.argv) > 2 else "arvore_termo_estilo.html"

with open(src, encoding="utf-8") as f:
    games = json.load(f)["games"]

start = games[0]["guesses"][0]["guess"]
root = {"g": "", "f": "", "n": 0, "c": {}}
for game in games:
    node = root
    node["n"] += 1
    for s in game["guesses"]:
        key = (s["guess"], s["feedback"])
        child = node["c"].get(key)
        if child is None:
            child = node["c"][key] = {"g": s["guess"], "f": s["feedback"], "n": 0, "c": {}}
        child["n"] += 1
        node = child
    node["a"] = game["answer"]

def conv(n):
    out = {"g": n["g"], "f": n["f"], "n": n["n"]}
    if "a" in n:
        out["a"] = n["a"]
    if n["c"]:
        out["c"] = [conv(c) for c in n["c"].values()]
    return out

avg = sum(len(g["guesses"]) for g in games) / len(games)
data = json.dumps(conv(root), ensure_ascii=False, separators=(",", ":"))

HTML = r"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>Árvore de estratégia - Termo</title>
<style>
 html,body{margin:0;height:100%;background:#312a2c;overflow:hidden;color:#fff;
   font-family:"Helvetica Neue",Arial,system-ui,sans-serif}
 canvas{display:block;width:100%;height:100%;cursor:grab}
 canvas:active{cursor:grabbing}
 #panel{position:fixed;top:10px;left:10px;width:330px;background:rgba(40,34,36,.94);border:1px solid #9a8b91;
   border-radius:10px;padding:10px 12px;font-size:13px;z-index:3}
 #panel input[type=text]{background:#3d3336;color:#fff;border:1px solid #9a8b91;border-radius:5px;
   padding:4px 6px;text-transform:uppercase}
 #panel button{background:#7a6a70;color:#fff;border:1px solid #9a8b91;border-radius:5px;padding:4px 8px;cursor:pointer}
 #panel button:hover{background:#8d7c83}
 #panel .row{margin-top:7px}
 #hint{position:fixed;left:10px;bottom:8px;font-size:12px;color:#ece4e6;pointer-events:none}
 #tip{position:fixed;display:none;pointer-events:none;background:rgba(40,34,36,.96);border:1px solid #9a8b91;
   border-radius:8px;padding:7px 9px;font-size:12px;z-index:5;max-width:420px}
 .mini{display:inline-block;width:15px;height:17px;line-height:17px;text-align:center;color:#fff;
   font:bold 11px monospace;margin-right:1px;border-radius:3px}
 .blk{background:#6e5c62;color:#fff;border:1px solid #4c4347;box-sizing:border-box;line-height:15px}
 .arrow{color:#d8ccd0;margin:0 3px}
</style></head><body>
<canvas id="cv"></canvas>
<div id="panel">
  <div>Palavra-alvo: <input type="text" id="q" size="9" placeholder="ex.: ABACO">
    <button onclick="buscarPalavra()">Mostrar caminho</button></div>
  <div class="row">Feedback: <input type="text" id="fb" size="6" maxlength="5" placeholder="PVPPV">
    <button onclick="buscarFb()">Buscar feedback</button>
    <button onclick="irPara(mi-1)">&#9664;</button><button onclick="irPara(mi+1)">&#9654;</button>
    <div style="color:#d8ccd0;margin-top:3px">V=verde A=amarelo P=cinza ?=qualquer</div></div>
  <div class="row">Partindo de: <span id="scopeLbl"></span>
    <button onclick="limpar()" style="margin-left:6px">Limpar</button></div>
  <div class="row" id="info" style="color:#f4eef0"></div>
</div>
<div id="hint">Roda do mouse = zoom &middot; arrastar = mover &middot; clique num nó = escolher a palavra de partida (a busca por feedback olha só os palpites logo depois dela) &middot; Esc = limpar</div>
<div id="tip"></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js"></script>
<script>
const DATA=__DATA__;
const START="__START__";
const COL={V:"#3aa394",A:"#d3ad69",P:"#1c1618"}, BG="#312a2c", NEXT="#6e5c62", NEXTTXT="#fff", NEXTLINE="#4c4347";
const PINK="#ff5fb0", CYAN="#4cc9ff";   // destaques: distintos do verde/amarelo/cinza do feedback
const cv=document.getElementById("cv"), ctx=cv.getContext("2d");
let W=innerWidth, H=innerHeight, dpr=window.devicePixelRatio||1, T=d3.zoomIdentity;
function sizeCanvas(){ W=innerWidth; H=innerHeight; cv.width=W*dpr; cv.height=H*dpr; }
sizeCanvas();

// ---------- árvore ----------
const nodes=[];
const fkey=f=>[...f].reduce((a,c)=>a*3+({P:0,A:1,V:2}[c]||0),0);
function build(d,parent,depth){
  const o={g:d.g,f:d.f,n:d.n,a:d.a,parent,depth,kids:[]};
  nodes.push(o);
  if(d.c){ d.c.sort((x,y)=>fkey(x.f)-fkey(y.f)); o.kids=d.c.map(c=>build(c,o,depth+1)); }
  return o;
}
const root=build(DATA,null,0), N=root.n;
(function assign(o,start){ o.a0=start/N; o.a1=(start+o.n)/N; let s=start;
  for(const k of o.kids){assign(k,s); s+=k.n;} })(root,0);

// ---------- layout (elipse) ----------
const cx=W/2, cy=H/2, Rx=W*0.47, Ry=H*0.46, S0=Ry*0.12;
const rLo=d=>1-0.76*Math.pow(0.78,d-1), rHi=d=>1-0.38*Math.pow(0.62,d-1);
const TWO=2*Math.PI;
// ângulo por comprimento de arco: as folhas ficam igualmente espaçadas ao longo da elipse
const NT=4096, cum=new Float64Array(NT+1);
for(let i=1;i<=NT;i++){ const t=-Math.PI/2+TWO*(i-0.5)/NT; cum[i]=cum[i-1]+Math.hypot(Rx*Math.sin(t),Ry*Math.cos(t))*TWO/NT; }
const PERIM=cum[NT];
function thOf(u){ const target=u*PERIM; let lo=0,hi=NT;
  while(hi-lo>1){ const m=(lo+hi)>>1; if(cum[m]<target) lo=m; else hi=m; }
  const f=(target-cum[lo])/Math.max(1e-9,cum[hi]-cum[lo]); return -Math.PI/2+TWO*(lo+f)/NT; }
// folhas = tiras RADIAIS (palavra ao longo do raio) em LANES faixas alternadas:
// sem sobreposição e cada ligação chega livre na ponta interna da sua folha
const SL=S0*Math.min(0.85,2.0*Math.sqrt(1/N));
const LEN=5.4*SL, GL=0.7*SL, LANES=Math.max(2,Math.ceil(1.3*SL/(PERIM/N)));
const ZONE=LANES*(LEN+GL);
let li=0;
for(const o of nodes){
  o.th=thOf((o.a0+o.a1)/2);
  if(o.depth&&!o.kids.length){                                  // folha
    const j=(li++)%LANES, dx=Rx*Math.cos(o.th), dy=Ry*Math.sin(o.th), dn=Math.hypot(dx,dy), ux=dx/dn, uy=dy/dn;
    const px=cx+0.995*dx, py=cy+0.995*dy, back=j*(LEN+GL);
    o.x=px-ux*(back+LEN/2); o.y=py-uy*(back+LEN/2);            // centro da tira
    o.ex=px-ux*(back+LEN);  o.ey=py-uy*(back+LEN);             // ponta interna (onde a ligação chega)
    o.ang=Math.atan2(uy,ux)+(ux<0?Math.PI:0);                  // lado esquerdo: gira 180° p/ o texto não ficar de cabeça p/ baixo
    o.s=SL; o.r=1; continue;
  }
  const u=Math.min(1,Math.sqrt(o.n/N)/0.32);                    // peso normalizado 0..1
  o.r=o.depth===0?0:rLo(o.depth)+(rHi(o.depth)-rLo(o.depth))*(1-u);
  o.x=cx+Rx*o.r*Math.cos(o.th); o.y=cy+Ry*o.r*Math.sin(o.th);
  const sW=S0*Math.min(0.85,2.0*Math.sqrt(o.n/N));
  if(o.depth===0) o.s=S0;
  else{
    const t0=thOf(o.a0), t1=thOf(o.a1);
    const L=Math.hypot(Rx*o.r*(Math.cos(t1)-Math.cos(t0)),Ry*o.r*(Math.sin(t1)-Math.sin(t0)));
    o.s=Math.min(sW,Math.max(L/3.4,0.55*sW));
  }
}
// ---------- anti-sobreposição: afasta retângulos que se cruzam ----------
(function relax(){
  const items=nodes.filter(o=>o.kids.length||o.depth===0);   // folhas têm posição fixa
  const HIR=1-(ZONE+22)/Math.min(Rx,Ry);
  const hw=o=>(2.75+0.3)*o.s, hh=o=>((((o.depth&&o.kids.length)?2:1)*1.1-0.1)/2+0.3)*o.s;
  items.forEach((o,i)=>{o.i=i;o.hx=o.x;o.hy=o.y;});
  const CELL=Math.max(40,S0*3.2), seen=new Int32Array(items.length);
  for(let it=0;it<1500;it++){
    const grid=new Map();
    for(const o of items){
      const x0=Math.floor((o.x-hw(o))/CELL),x1=Math.floor((o.x+hw(o))/CELL);
      const y0=Math.floor((o.y-hh(o))/CELL),y1=Math.floor((o.y+hh(o))/CELL);
      for(let gx=x0;gx<=x1;gx++)for(let gy=y0;gy<=y1;gy++){
        const key=gx*100003+gy; let c=grid.get(key); if(!c){c=[];grid.set(key,c);} c.push(o); }
    }
    seen.fill(-1); let moved=0;
    for(const a of items){
      const x0=Math.floor((a.x-hw(a))/CELL),x1=Math.floor((a.x+hw(a))/CELL);
      const y0=Math.floor((a.y-hh(a))/CELL),y1=Math.floor((a.y+hh(a))/CELL);
      for(let gx=x0;gx<=x1;gx++)for(let gy=y0;gy<=y1;gy++){
        const c=grid.get(gx*100003+gy); if(!c) continue;
        for(const b of c){
          if(b.i<=a.i||seen[b.i]===a.i) continue; seen[b.i]=a.i;
          const dx=b.x-a.x, dy=b.y-a.y;
          const ox=hw(a)+hw(b)-Math.abs(dx), oy=hh(a)+hh(b)-Math.abs(dy);
          if(ox<=0||oy<=0) continue; moved++;
          const wa=a.depth===0?0:(b.depth===0?1:b.s/(a.s+b.s)), wb=1-wa;   // o menor se move mais
          if(oy<ox){ const m=oy*1.02*(dy>=0?1:-1); a.y-=m*wa; b.y+=m*wb; }
          else     { const m=ox*1.02*(dx>=0?1:-1); a.x-=m*wa; b.x+=m*wb; }
        }
      }
    }
    for(const o of items){ if(!o.depth) continue;
      const sp=it<250?0.012:0; o.x+=(o.hx-o.x)*sp; o.y+=(o.hy-o.y)*sp;                  // mola fraca p/ a posição original
      const ex=(o.x-cx)/Rx, ey=(o.y-cy)/Ry, rr=Math.hypot(ex,ey);
      const r2=Math.min(HIR,rr);
      if(rr>0&&r2!==rr){ o.x=cx+ex*r2/rr*Rx; o.y=cy+ey*r2/rr*Ry; }
    }
    if(!moved) break;
  }
})();
for(const o of nodes){ if(o.kids.length||!o.depth){ o.ex=o.x; o.ey=o.y; } }
const order=[...nodes].sort((a,b)=>a.s-b.s);
const byAnswer=new Map(nodes.filter(o=>o.a).map(o=>[o.a,o]));
const rowsOf=o=>(o.depth&&o.kids.length)?2:1;
const anc=o=>{const r=[];for(let x=o;x;x=x.parent)r.push(x);return r;};
const desc=o=>{const r=[];(function w(x){r.push(x);x.kids.forEach(w);})(o);return r;};

// ---------- estado ----------
let focus=null, strong=new Set(), hlColor=PINK, sel=null, matches=[], mi=-1;

// ---------- desenho ----------
let raf=0; function schedule(){ if(!raf) raf=requestAnimationFrame(()=>{raf=0;draw();}); }
function draw(){
  ctx.setTransform(dpr,0,0,dpr,0,0); ctx.fillStyle=BG; ctx.fillRect(0,0,W,H);
  const k=T.k;
  ctx.setTransform(dpr*k,0,0,dpr*k,dpr*T.x,dpr*T.y);
  const vx0=-T.x/k, vy0=-T.y/k, vx1=(W-T.x)/k, vy1=(H-T.y)/k, dim=focus!==null;
  const segVis=(a,b)=>!(Math.max(a.x,b.x)<vx0||Math.min(a.x,b.x)>vx1||Math.max(a.y,b.y)<vy0||Math.min(a.y,b.y)>vy1);
  // ligações normais
  ctx.beginPath();
  for(const o of nodes){ const p=o.parent; if(!p) continue;
    if(dim&&focus.has(o)&&focus.has(p)) continue;
    if(!segVis(o,p)) continue; ctx.moveTo(p.x,p.y); ctx.lineTo(o.ex,o.ey); }
  ctx.strokeStyle=dim?"rgba(255,255,255,0.05)":"rgba(255,255,255,0.15)"; ctx.lineWidth=0.5/k; ctx.stroke();
  // ligações destacadas
  if(dim){
    ctx.beginPath();
    for(const o of nodes){ const p=o.parent; if(!p||!focus.has(o)||!focus.has(p)||!segVis(o,p)) continue;
      ctx.moveTo(p.x,p.y); ctx.lineTo(o.ex,o.ey); }
    ctx.strokeStyle=hlColor; ctx.lineWidth=Math.max(1.8/k,0.04); ctx.stroke();
  }
  // nós
  for(const o of order){
    const s=o.s, ss=s*k;
    if(o.x+3.2*s<vx0||o.x-3.2*s>vx1||o.y+2.4*s<vy0||o.y-2.4*s>vy1) continue;
    ctx.globalAlpha=(dim&&!focus.has(o))?0.18:1;
    drawNode(o,s,ss);
  }
  ctx.globalAlpha=1;
}
const RAD=0.12;     // raio do canto, como fração do lado do tile (ajuste aqui)
function rr(x,y,w,h,r){ ctx.beginPath(); ctx.moveTo(x+r,y); ctx.arcTo(x+w,y,x+w,y+h,r);
  ctx.arcTo(x+w,y+h,x,y+h,r); ctx.arcTo(x,y+h,x,y,r); ctx.arcTo(x,y,x+w,y,r); ctx.closePath(); }
function drawLeaf(o,s,ss){
  ctx.save(); ctx.translate(o.x,o.y); ctx.rotate(o.ang);
  const pitch=1.1*s, left=-(5*pitch-0.1*s)/2, y=-s/2;
  for(let i=0;i<5;i++){ ctx.fillStyle=COL[o.f[i]];
    if(ss>=3){ rr(left+i*pitch,y,s,s,RAD*s); ctx.fill(); } else ctx.fillRect(left+i*pitch,y,s,s); }
  if(ss>=7){ ctx.fillStyle="#fff"; ctx.font=`700 ${0.68*s}px "Helvetica Neue",Arial,sans-serif`;
    ctx.textAlign="center"; ctx.textBaseline="middle";
    for(let i=0;i<5;i++) ctx.fillText(o.g[i],left+i*pitch+s/2,y+s/2+0.04*s); }
  if(strong.has(o)){
    const pad=0.3*s; ctx.strokeStyle="#fff"; ctx.lineWidth=Math.max(2/T.k,0.12*s);
    rr(left-pad,y-pad,5*pitch-0.1*s+2*pad,s+2*pad,RAD*s*2.2); ctx.stroke();
  }
  ctx.restore();
}
function drawNode(o,s,ss){
  if(o.depth&&!o.kids.length){ drawLeaf(o,s,ss); return; }
  const pitch=1.1*s, left=o.x-(5*pitch-0.1*s)/2, rows=rowsOf(o);
  const top=o.y-(rows*pitch-0.1*s)/2;
  let y=top;
  if(o.depth){                       // linha colorida: palpite + feedback recebido
    for(let i=0;i<5;i++){ ctx.fillStyle=COL[o.f[i]];
      if(ss>=3){ rr(left+i*pitch,y,s,s,RAD*s); ctx.fill(); } else ctx.fillRect(left+i*pitch,y,s,s); }
    if(ss>=7){ ctx.fillStyle="#fff"; ctx.font=`700 ${0.68*s}px "Helvetica Neue",Arial,sans-serif`;
      ctx.textAlign="center"; ctx.textBaseline="middle";
      for(let i=0;i<5;i++) ctx.fillText(o.g[i],left+i*pitch+s/2,y+s/2+0.04*s); }
    y+=pitch;
  }
  if(o.kids.length){                 // linha preta: próximo palpite
    const w=o.depth===0?START:o.kids[0].g;
    for(let i=0;i<5;i++){ ctx.fillStyle=NEXT; ctx.strokeStyle=NEXTLINE; ctx.lineWidth=Math.max(0.09*s,0.7/T.k);
      if(ss>=3){ rr(left+i*pitch,y,s,s,RAD*s); ctx.fill(); ctx.stroke(); }
      else { ctx.fillRect(left+i*pitch,y,s,s); if(ss>=1.2) ctx.strokeRect(left+i*pitch,y,s,s); } }
    if(ss>=7){ ctx.fillStyle=NEXTTXT; ctx.font=`700 ${0.68*s}px "Helvetica Neue",Arial,sans-serif`;
      ctx.textAlign="center"; ctx.textBaseline="middle";
      for(let i=0;i<5;i++) ctx.fillText(w[i],left+i*pitch+s/2,y+s/2+0.04*s); }
  }
  if(strong.has(o)){
    const pad=0.3*s, h=rows*pitch-0.1*s;
    ctx.strokeStyle="#fff"; ctx.lineWidth=Math.max(2/T.k,0.12*s);
    rr(left-pad,top-pad,5*pitch-0.1*s+2*pad,h+2*pad,RAD*s*2.2); ctx.stroke();
  }
}

// ---------- zoom / interação ----------
const zoom=d3.zoom().scaleExtent([0.6,600]).on("zoom",e=>{T=e.transform;schedule();});
d3.select(cv).call(zoom).on("dblclick.zoom",null);
function zoomTo(list,kmax){
  let x0=1e9,y0=1e9,x1=-1e9,y1=-1e9;
  for(const o of list){ x0=Math.min(x0,o.x-3.2*o.s);x1=Math.max(x1,o.x+3.2*o.s);
                        y0=Math.min(y0,o.y-1.4*o.s);y1=Math.max(y1,o.y+1.4*o.s); }
  const k=Math.min(kmax||600,0.85*W/(x1-x0),0.85*H/(y1-y0));
  const tr=d3.zoomIdentity.translate(W/2-k*(x0+x1)/2,H/2-k*(y0+y1)/2).scale(k);
  d3.select(cv).transition().duration(700).call(zoom.transform,tr);
}
function hit(mx,my){
  const k=T.k, wx=(mx-T.x)/k, wy=(my-T.y)/k, tol=4/k;
  for(let i=order.length-1;i>=0;i--){ const o=order[i];
    if(o.depth&&!o.kids.length){
      const ddx=wx-o.x, ddy=wy-o.y, c=Math.cos(o.ang), sn=Math.sin(o.ang);
      const lx=ddx*c+ddy*sn, ly=-ddx*sn+ddy*c;
      const tl=Math.min(tol,1.2/k);   // tolerância menor: as folhas são finas e vizinhas
      if(Math.abs(lx)<=2.7*o.s+tl&&Math.abs(ly)<=0.5*o.s+tl) return o; continue; }
    const hw=2.7*o.s+tol, hh=(rowsOf(o)*1.1-0.1)/2*o.s+tol;
    if(Math.abs(wx-o.x)<=hw&&Math.abs(wy-o.y)<=hh) return o; }
  return null;
}
const mini=(g,f)=>[...g].map((c,i)=>`<span class="mini" style="background:${COL[f[i]]}">${c}</span>`).join("");
const miniBlk=g=>[...g].map(c=>`<span class="mini blk">${c}</span>`).join("");
const pathMinis=o=>anc(o).reverse().slice(1).map(x=>mini(x.g,x.f)).join('<span class="arrow">&rarr;</span>');
const tip=document.getElementById("tip");
cv.addEventListener("mousemove",e=>{
  const o=hit(e.offsetX,e.offsetY);
  if(!o||!o.depth){ tip.style.display="none"; return; }
  tip.innerHTML=pathMinis(o)+"<br>"+o.n+" jogo(s)"+(o.kids.length?" &middot; próximo: "+miniBlk(o.kids[0].g):"")+(o.a?" &middot; <b>"+o.a+"</b>":"");
  tip.style.display="block"; tip.style.left=Math.min(e.clientX+14,W-440)+"px"; tip.style.top=(e.clientY+14)+"px";
});
cv.addEventListener("mouseleave",()=>tip.style.display="none");
cv.addEventListener("click",e=>{ const o=hit(e.offsetX,e.offsetY); if(!o||!o.depth){limpar();return;} selecionar(o); });
addEventListener("keydown",e=>{ if(e.key==="Escape") limpar(); });
addEventListener("resize",()=>{sizeCanvas();schedule();});

const info=h=>document.getElementById("info").innerHTML=h;
function updScope(){ document.getElementById("scopeLbl").innerHTML=sel?pathMinis(sel):"palavra inicial "+miniBlk(START); }
function limpar(){ focus=null; strong=new Set(); sel=null; matches=[]; mi=-1; updScope(); info(""); schedule(); }
function selecionar(o){
  sel=o; focus=new Set([...anc(o),...desc(o)]); strong=new Set([o]); hlColor=CYAN; matches=[]; mi=-1; updScope();
  info(o.n+" jogo(s) neste ramo"+(o.kids.length?" &middot; próximo palpite: "+miniBlk(o.kids[0].g)+"<br>A busca por feedback olhará os resultados desse palpite.":
       " &middot; acerto: nada vem depois."));
  zoomTo(desc(o).concat(anc(o)));
}
function buscarPalavra(){
  const q=document.getElementById("q").value.trim().toUpperCase(), leaf=byAnswer.get(q);
  if(!leaf){ info("Palavra não encontrada no arquivo."); return; }
  const path=anc(leaf); focus=new Set(path); strong=new Set([leaf]); hlColor=PINK; matches=[];
  info("<b>"+q+"</b> em "+leaf.depth+" tentativa(s):<br>"+pathMinis(leaf));
  zoomTo(path);
}
function normFb(s){ return [...s.trim().toUpperCase()].map(c=>({"🟩":"V","🟨":"A","⬛":"P","⬜":"P","*":"?"}[c]||c)).join(""); }
function buscarFb(){
  const pat=normFb(document.getElementById("fb").value);
  if(!/^[VAP?]{5}$/.test(pat)){ info("Use 5 caracteres entre V, A, P e ? (ex.: PVPPV)."); return; }
  const from=sel||root;                                   // sem palavra escolhida: parte do palpite inicial
  const nome=sel?"depois de "+pathMinis(sel).split('<span class="arrow">&rarr;</span>').pop():"depois do palpite inicial "+miniBlk(START);
  if(!from.kids.length){ focus=null; strong=new Set(); matches=[]; mi=-1; info("A palavra escolhida é um acerto: nada vem depois dela."); schedule(); return; }
  const re=new RegExp("^"+pat.replace(/\?/g,".")+"$");
  matches=from.kids.filter(o=>re.test(o.f)).sort((a,b)=>a.th-b.th);   // só os feedbacks DIRETAMENTE após a palavra
  const prox=miniBlk(from.kids[0].g);
  if(!matches.length){
    focus=null; strong=new Set(); mi=-1;
    info("Nenhum feedback <b>"+pat+"</b> para o próximo palpite "+prox+" ("+from.kids.length+" feedbacks possíveis aqui).");
    schedule(); return;
  }
  focus=new Set([...anc(from)]); matches.forEach(m=>focus.add(m)); strong=new Set(matches); hlColor=PINK;
  irPara(0);
}
function irPara(i){
  if(!matches.length) return;
  mi=(i+matches.length)%matches.length; const o=matches[mi];
  const k=Math.min(600,26/o.s);
  d3.select(cv).transition().duration(600).call(zoom.transform,d3.zoomIdentity.translate(W/2-k*o.x,H/2-k*o.y).scale(k));
  info("<b>"+(mi+1)+" / "+matches.length+"</b> &mdash; palpite "+mini(o.g,o.f)+" ("+o.n+" jogo(s))"+(o.a?" &middot; resposta: <b>"+o.a+"</b>":"")+(o.kids.length?"<br>próximo: "+miniBlk(o.kids[0].g):""));
}
document.getElementById("q").addEventListener("keydown",e=>{if(e.key==="Enter")buscarPalavra();});
document.getElementById("fb").addEventListener("keydown",e=>{if(e.key==="Enter")buscarFb();});
draw();
</script></body></html>"""

html = HTML.replace("__DATA__", data).replace("__START__", start)
with open(dst, "w", encoding="utf-8") as f:
    f.write(html)
print("Gerado:", dst, "| média de palpites:", f"{avg:.2f}")
