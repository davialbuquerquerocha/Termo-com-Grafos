#!/usr/bin/env python3
"""Gera um HTML interativo (árvore colapsável) a partir do JSON de jogos do Termo.

Uso:  python gerar_arvore.py entrada.json [saida.html]
"""
import json, sys

src = sys.argv[1]
dst = sys.argv[2] if len(sys.argv) > 2 else "arvore_termo.html"

with open(src, encoding="utf-8") as f:
    games = json.load(f)["games"]

# Trie de prefixos: nó = palpite; aresta = feedback recebido nesse palpite
def novo(g, fb):
    return {"g": g, "f": fb, "n": 0, "c": {}}

root = None
paths = {}
for game in games:
    gs = game["guesses"]
    if root is None:
        root = novo(gs[0]["guess"], "")
    node = root
    node["n"] += 1
    fbs = []
    for i, s in enumerate(gs):
        fbs.append(s["feedback"])
        if i + 1 < len(gs):
            nxt = gs[i + 1]
            child = node["c"].get(s["feedback"])
            if child is None:
                child = node["c"][s["feedback"]] = novo(nxt["guess"], s["feedback"])
            child["n"] += 1
            node = child
        else:
            node["a"] = game["answer"]  # último palpite = acerto
    paths[game["answer"]] = fbs

def conv(n):
    out = {"g": n["g"], "f": n["f"], "n": n["n"]}
    if "a" in n:
        out["a"] = n["a"]
    if n["c"]:
        out["c"] = [conv(c) for c in n["c"].values()]
    return out

data = json.dumps(conv(root), ensure_ascii=False, separators=(",", ":"))
idx = json.dumps({a: "/".join(p) for a, p in paths.items()},
                 ensure_ascii=False, separators=(",", ":"))

HTML = r"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>Árvore de estratégia - Termo</title>
<style>
 html,body{margin:0;height:100%;font-family:system-ui,sans-serif;background:#fafafa}
 #bar{position:fixed;top:8px;left:8px;z-index:2;background:#fff;border:1px solid #ccc;
      border-radius:8px;padding:8px 10px;box-shadow:0 1px 4px #0002;font-size:13px}
 input{padding:4px 6px;text-transform:uppercase;width:110px}
 button{padding:4px 8px;cursor:pointer}
 svg{width:100%;height:100%}
 .node circle{stroke:#555;stroke-width:1.2px;cursor:pointer}
 .node text{font-size:11px;font-family:monospace}
 .link{fill:none;stroke:#bbb;stroke-width:1px}
 .link.hl{stroke:#d33;stroke-width:2.5px}
 .lbl{font-size:9px;fill:#444}
</style></head><body>
<div id="bar">
  Palavra-alvo: <input id="q" placeholder="ex.: ABACO">
  <button onclick="buscar()">Mostrar caminho</button>
  <button onclick="expandirTudo()">Expandir tudo</button>
  <button onclick="recolher()">Recolher</button>
  <div id="msg" style="margin-top:4px;color:#555">Clique num nó para expandir/recolher. Número = jogos que passam pelo nó.</div>
</div>
<svg id="svg"><g id="g"></g></svg>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js"></script>
<script>
const DATA=__DATA__;
const IDX=__IDX__;
const EMO={V:"🟩",A:"🟨",P:"⬛"};
const fb=s=>[...s].map(c=>EMO[c]||c).join("");
const svg=d3.select("#svg"), g=d3.select("#g");
const zoom=d3.zoom().scaleExtent([0.05,3]).on("zoom",e=>g.attr("transform",e.transform));
svg.call(zoom);

const root=d3.hierarchy(DATA,d=>d.c);
const layout=d3.tree().nodeSize([18,190]);
const link=d3.linkHorizontal().x(d=>d.y).y(d=>d.x);

function collapse(d){ if(d.children){d._children=d.children;d.children=null;d._children.forEach(collapse);} }
function expand(d){ if(d._children){d.children=d._children;d._children=null;} }
function clearHl(){ root.each(d=>d.hl=false); }

function render(){
  layout(root);
  const nodes=root.descendants(), links=root.links();
  g.selectAll("*").remove();
  g.append("g").selectAll("path").data(links).join("path")
    .attr("class",d=>"link"+(d.target.hl?" hl":"")).attr("d",link);
  g.append("g").selectAll("text").data(links).join("text").attr("class","lbl")
    .attr("x",d=>(d.source.y+d.target.y)/2).attr("y",d=>(d.source.x+d.target.x)/2-2)
    .attr("text-anchor","middle").text(d=>fb(d.target.data.f));
  const nd=g.append("g").selectAll("g").data(nodes).join("g").attr("class","node")
    .attr("transform",d=>`translate(${d.y},${d.x})`)
    .on("click",(e,d)=>{ if(d.children){d._children=d.children;d.children=null;}
                         else if(d._children){d.children=d._children;d._children=null;}
                         render(); });
  nd.append("circle").attr("r",d=>d.data.a?5:Math.max(4,Math.min(10,2+Math.log2(d.data.n))))
    .attr("fill",d=>d.data.a?"#6aaa64":(d._children?"#69b3e7":"#fff"))
    .attr("stroke",d=>d.hl?"#d33":"#555");
  nd.append("text").attr("dx",12).attr("dy",4)
    .attr("font-weight",d=>d.hl?"bold":"normal")
    .text(d=>d.data.g+(d.data.a?"":"  ("+d.data.n+")"));
  nd.append("title").text(d=>d.data.g+" - "+d.data.n+" jogo(s)");
}
function center(d){
  const k=0.9, w=innerWidth, h=innerHeight;
  svg.transition().duration(500).call(zoom.transform,
    d3.zoomIdentity.translate(w/2-d.y*k,h/2-d.x*k).scale(k));
}
function recolher(){ clearHl(); collapse(root); expand(root); render();
  svg.call(zoom.transform,d3.zoomIdentity.translate(60,innerHeight/2).scale(0.8)); }
function expandirTudo(){
  if(!confirm("São ~22 mil nós; pode ficar pesado. Continuar?"))return;
  root.each(expand); render(); }
function buscar(){
  const q=document.getElementById("q").value.trim().toUpperCase(), msg=document.getElementById("msg");
  if(!IDX[q]){ msg.textContent="Palavra não encontrada no arquivo."; return; }
  clearHl();
  const fbs=IDX[q].split("/"); let n=root; n.hl=true;
  for(let i=0;i<fbs.length-1;i++){
    expand(n);
    n=(n.children||[]).find(c=>c.data.f===fbs[i]); n.hl=true;
  }
  msg.textContent=q+": "+fbs.length+" tentativa(s)";
  render(); center(n);
}
document.getElementById("q").addEventListener("keydown",e=>{if(e.key==="Enter")buscar();});
collapse(root); expand(root); render();
svg.call(zoom.transform,d3.zoomIdentity.translate(60,innerHeight/2).scale(0.8));
</script></body></html>"""

with open(dst, "w", encoding="utf-8") as f:
    f.write(HTML.replace("__DATA__", data).replace("__IDX__", idx))
print("Gerado:", dst)
