"""Offline, rebuildable views. No LLM summaries, network calls or design edits."""
import json
import pathlib

from evidence_trace import __version__


def render(directory, graph):
    directory = pathlib.Path(directory)
    payload = json.dumps(graph, ensure_ascii=False, indent=2)
    (directory / "graph.json").write_text(payload, encoding="utf-8")
    manifest = {"schema_version": graph["schema_version"], "trace_version": __version__,
                "integrity": graph["integrity"], "issues": graph["issues"],
                "coverage": graph["coverage"], "runs": [r["id"] for r in graph["runs"]],
                "artifacts": [{k: n.get(k) for k in ("path", "sha256", "run_id", "role")}
                              for n in graph["nodes"] if n["kind"] == "artifact"],
                "derived_files": ["graph.json", "index.html"]}
    (directory / "TRACE-MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    # Escaping '<' prevents source text from closing the inert JSON script element.
    document = PAGE.replace("__TRACE_DATA__", payload.replace("<", "\\u003c").replace("&", "\\u0026"))
    (directory / "index.html").write_text(document, encoding="utf-8")


PAGE = r'''<!doctype html>
<html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Evidence Trace · 设计溯源</title>
<style>
:root{color-scheme:light;--bg:#f4f5f2;--card:#fff;--ink:#182b30;--muted:#596a6b;--line:#d9e1dd;--accent:#086a65;--amber:#8b4b11}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.65 system-ui,"Microsoft YaHei",sans-serif}button,select,input{font:inherit}button,a,select{touch-action:manipulation}button{cursor:pointer}header{padding:30px 4vw 22px;border-bottom:1px solid var(--line);background:var(--card)}header p{margin:5px 0;max-width:980px;color:var(--muted)}.brand{font-size:12px;letter-spacing:.12em;color:var(--accent);font-weight:700}h1{font-size:30px;margin:6px 0}h2{font-size:21px;margin:0 0 14px}h3{font-size:16px;margin:22px 0 8px}.toolbar{display:flex;gap:10px;flex-wrap:wrap;padding:18px 4vw}.toolbar select,.toolbar input{padding:9px 12px;border:1px solid var(--line);border-radius:6px;max-width:100%;background:white}.toolbar input{flex:1;min-width:160px}nav{display:flex;gap:6px;padding:0 4vw 16px;flex-wrap:wrap}nav button{padding:8px 16px;border:1px solid var(--line);border-radius:6px;background:#fff;color:var(--ink)}nav button[aria-selected=true]{background:var(--ink);color:#fff}main{display:grid;grid-template-columns:minmax(300px,1fr) minmax(350px,1.1fr);gap:24px;padding:0 4vw 40px;align-items:start}.panel{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:24px;min-width:0}.detail{position:sticky;top:16px;max-height:88vh;overflow:auto}.item{display:block;width:100%;text-align:left;border:1px solid var(--line);border-left:3px solid var(--accent);border-radius:6px;background:#fff;padding:12px 15px;margin:0 0 10px;color:var(--ink);overflow-wrap:anywhere}.item:hover,.item:focus-visible{background:#edf6f2;outline:2px solid var(--accent)}.item[aria-current=true]{background:#edf6f2}.type{font-size:12px;color:var(--muted);display:block}.label{font-weight:650;display:block}.badge{display:inline-block;font-size:12px;background:#eef2ef;color:var(--accent);padding:2px 8px;border-radius:4px;margin:3px 5px 3px 0}.warn{background:#fff2df;color:var(--amber)}.muted{color:var(--muted)}.note{border-left:3px solid #d1ab70;background:#fff8ed;padding:10px 14px;margin:12px 0;overflow-wrap:anywhere}dl{margin:0}dt{font-size:12px;color:var(--muted);margin-top:12px}dd{margin:2px 0;overflow-wrap:anywhere;white-space:pre-wrap}a{color:var(--accent)}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;background:#f6f8f6;padding:12px;border-radius:5px}.empty{padding:25px 0;color:var(--muted)}.flow{display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:12px 0;border-bottom:1px solid var(--line)}.flow button{border:1px solid var(--line);border-radius:5px;padding:6px 9px;background:#f3f7f4;color:var(--ink);max-width:100%;overflow-wrap:anywhere}.flow small{color:var(--muted)}.integrity{display:flex;gap:10px;align-items:center;margin-top:15px;flex-wrap:wrap}details summary{cursor:pointer}footer{padding:10px 4vw 30px;color:var(--muted);font-size:12px}@media(max-width:800px){main{grid-template-columns:1fr}.detail{position:static;max-height:none}.panel{padding:18px}h1{font-size:25px}.toolbar select{width:100%}}
</style>
<header><div class="brand">SNAPGENE DNA DESIGN / EVIDENCE TRACE 0.1</div><h1>看清每个设计决定的来路</h1><p>用户要求、来源报告了什么、当前任务如何解释、实际选择，以及程序检查和产物。</p><div class="integrity"><strong id="integrity"></strong><span class="muted">记录完整不等于证据充分、设计安全或湿实验成功。</span></div></header>
<div class="toolbar"><select id="run" aria-label="选择运行"></select><input id="search" type="search" placeholder="查找决定、来源、产物…" aria-label="搜索记录"></div>
<nav aria-label="溯源视图"><button data-view="timeline" aria-selected="true">Design Timeline</button><button data-view="review" aria-selected="false">Review Queue</button><button data-view="artifacts" aria-selected="false">构建产物</button><button data-view="graph" aria-selected="false">Evidence Graph</button></nav>
<main><section class="panel"><h2 id="view-title">Design Timeline</h2><div id="items"></div></section><aside class="panel detail" id="detail" aria-live="polite"><h2>Decision Detail</h2><p class="muted">选择决定查看理由，或从构建产物反向追溯。</p></aside></main>
<footer>范围：已提交的科研决策与接入入口的真实运行。适用性与强弱为声明者记录，未自动评判。离线页面，不发送数据。</footer>
<script id="trace-data" type="application/json">__TRACE_DATA__</script>
<script>
const G=JSON.parse(document.getElementById('trace-data').textContent), byKey=new Map(G.nodes.map(n=>[n.key,n]));
const labels={requirement:'用户要求',source:'来源',statement:'来源陈述',claim:'当前任务判断',decision:'设计决定',validation:'程序验证',artifact:'构建产物'};
const $=id=>document.getElementById(id), esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=v=>typeof v==='object'?JSON.stringify(v,null,2):String(v??'');
let view='timeline', selected=null;
const checkNames={biological_sanity:'序列与生物学自检',requested_components:'指定组件检查',artifact_valid:'产物文件验证',computation_valid:'反应计算验证',goal_valid:'任务目标验证'};
function title(n){return n.text||n.title||checkNames[n.check]||n.check||n.relative_path||n.id}
function scopedEdges(){const r=G.runs.find(r=>r.id===$('run').value);return r?G.edges.filter(e=>e.recorded_sequence<=r.event_count_at_start||byKey.get(e.to)?.run_id===r.id):G.edges}
function refs(n){return Object.values(n.references||{}).flat()}
function activeKeys(){const r=G.runs.find(r=>r.id===$('run').value);if(!r)return new Set(G.nodes.map(n=>n.key));const keys=new Set(r.context_refs||[]);G.nodes.filter(n=>n.run_id===r.id).forEach(n=>keys.add(n.key));let change=true;while(change){change=false;scopedEdges().filter(e=>e.relation!=='revised'&&keys.has(e.to)).forEach(e=>{if(!keys.has(e.from)){keys.add(e.from);change=true}})}return keys}
function visible(){const keys=activeKeys(),q=$('search').value.toLowerCase();return G.nodes.filter(n=>keys.has(n.key)&&(!q||JSON.stringify(n).toLowerCase().includes(q)))}
function badge(n){if(n.kind==='source')return '<span class="badge '+(n.verification_status==='verified'?'':'warn')+'">'+(n.verification_status==='verified'?'来源已核验':'来源未核验')+'</span>';if(n.kind==='validation')return '<span class="badge '+([true,'PASS','passed','verified'].includes(n.result)?'':'warn')+'">'+esc(n.result===true?'程序检查通过':n.result==='not_requested'?'未请求此项检查':'程序结果：'+fmt(n.result))+'</span>';return ''}
function button(n){return '<button class="item" data-node="'+esc(n.key)+'" aria-current="'+(selected===n.key)+'"><span class="type">'+esc(labels[n.kind])+' · '+esc(['artifact','validation'].includes(n.kind)?'程序记录':n.id)+' · 修订 '+n.revision+'</span><span class="label">'+esc(title(n))+'</span>'+badge(n)+'</button>'}
function redraw(){const nodes=visible(),keys=new Set(nodes.map(n=>n.key));$('view-title').textContent={timeline:'Design Timeline',review:'Review Queue',artifacts:'构建产物',graph:'Evidence Graph'}[view];let html='';if(G.issues.length)html+='<details class="note"><summary>记录缺口 '+G.issues.length+'</summary>'+G.issues.map(x=>'<p>'+esc(x)+'</p>').join('')+'</details>';
if(view==='review'){html+=(G.runs.find(r=>r.id===$('run').value)?.review_queue||G.review_queue).filter(q=>keys.has(q.node)).map(q=>'<p class="note">'+esc(q.reason)+'</p>'+button(byKey.get(q.node))).join('')}
else if(view==='graph'){html+='<p class="muted">来源 → 陈述 → 当前判断 → 设计决定 → 程序检查 / 产物。点击任一记录查看详情。</p>';html+=scopedEdges().filter(e=>keys.has(e.from)&&keys.has(e.to)).map(e=>'<div class="flow"><button data-node="'+esc(e.from)+'">'+esc(title(byKey.get(e.from)))+'</button><small>→ '+esc(({responds_to:'回应要求',source_id:'来源报告',claim_ids:'采用判断',decision_ids:'关联决定',validated_by:'关联程序检查',revised:'前一修订',support:'支持',oppose:'反对',constrain:'限制',contextualize:'提供背景'})[e.relation]||e.relation)+' →</small><button data-node="'+esc(e.to)+'">'+esc(title(byKey.get(e.to)))+'</button></div>').join('')}
else{html+=nodes.filter(n=>view==='artifacts'?n.kind==='artifact':(['requirement','decision','validation'].includes(n.kind)||(n.kind==='artifact'&&n.path.endsWith('.dna')&&(n.role==='authoritative'||!nodes.some(x=>x.kind==='artifact'&&x.role==='authoritative'))))).map(button).join('');if(view==='timeline'){const runs=G.runs.filter(r=>!$('run').value||r.id===$('run').value);html+=runs.map(r=>'<details><summary>实际运行 '+esc(r.id.slice(0,8))+' · '+esc(r.route)+' · '+esc(r.status)+'</summary>'+r.stages.map(s=>'<p class="muted">'+esc(s.stage||s.event_type)+' · '+esc(s.event_type)+'</p>').join('')+'</details>').join('')}}
$('items').innerHTML=html||'<p class="empty">此范围没有记录。缺少记录不代表检查通过。</p>';}
function list(keys){return keys.map(k=>byKey.has(k)?button(byKey.get(k)):'<p class="note">缺失 '+esc(k)+'</p>').join('')}
function link(url,label){try{const u=new URL(url);if(!['https:','http:'].includes(u.protocol))return esc(url);return '<a href="'+esc(url)+'" target="_blank" rel="noopener noreferrer">'+esc(label||url)+'</a>'}catch{return esc(url)}}
function show(key){const n=byKey.get(key);if(!n)return;selected=key;let html='<span class="type">'+esc(labels[n.kind])+' · '+esc(n.key)+'</span><h2>'+esc(title(n))+'</h2>'+badge(n)+'<dl>';const names={targets:'涉及的输入或参数',rationale:'决策说明',decision_kind:'决定分类',actor:'记录者',recorded_at:'记录时间',context:'上下文',conditions:'条件',limitations:'限制',verification:'来源核验记录',locator:'原文定位',result:'实际程序结果',sha256:'文件 SHA-256',validation_scope:'检查关联范围'};
for(const [k,label] of Object.entries(names))if(n[k]!==undefined)html+='<dt>'+esc(label)+'</dt><dd>'+esc(fmt(n[k]))+'</dd>';html+='</dl>';
if(n.url)html+='<p>'+link(n.url,'打开来源')+'</p>';if(n.doi)html+='<p>'+link('https://doi.org/'+n.doi,'DOI '+n.doi)+'</p>';if(n.pmid)html+='<p>'+link('https://pubmed.ncbi.nlm.nih.gov/'+encodeURIComponent(n.pmid)+'/','PMID '+n.pmid)+'</p>';
if(n.path){html+='<h3>文件位置</h3><p style="overflow-wrap:anywhere">'+esc(n.path)+'</p>';if(/^(?:[A-Za-z]:[\\/]|\/)/.test(n.path)&&!n.path.startsWith('//'))html+='<a href="'+esc('file:///'+n.path.replaceAll('\\','/').replace(/^\//,''))+'">打开产物文件</a>'}
const incoming=scopedEdges().filter(e=>e.to===key),outgoing=scopedEdges().filter(e=>e.from===key);
if(incoming.length){html+='<h3>依据与前序</h3>';incoming.forEach(e=>{html+='<p class="type">'+esc(({responds_to:'回应要求',source_id:'来源报告',claim_ids:'采用判断',decision_ids:'关联决定',validated_by:'关联程序检查',revised:'前一修订',support:'支持',oppose:'反对',constrain:'限制',contextualize:'提供背景'})[e.relation]||e.relation)+'</p>';if(e.statement_id)html+='<dl>'+['aspect','strength','applicability','conditions','limitations','declared_by'].filter(k=>e[k]!==undefined).map(k=>'<dt>'+esc(k)+'</dt><dd>'+esc(fmt(e[k]))+'</dd>').join('')+'</dl>';html+=list([e.from])})}
if(outgoing.length)html+='<h3>关联判断、决定与产物</h3>'+list([...new Set(outgoing.map(e=>e.to))]);
if(n.details)html+='<details><summary>程序检查详情</summary><pre>'+esc(fmt(n.details))+'</pre></details>';
$('detail').innerHTML=html;redraw();if(innerWidth<801)$('detail').scrollIntoView({behavior:'smooth',block:'start'})}
$('integrity').textContent='记录完整性：'+(G.integrity==='complete'?'完整':'不完整');$('run').innerHTML='<option value="">全部历史与修订</option>'+G.runs.map(r=>'<option value="'+esc(r.id)+'">'+esc(r.route)+' / '+esc(r.id.slice(0,8))+' / '+esc(r.status)+'</option>').join('');if(G.runs.length)$('run').value=G.runs[G.runs.length-1].id;
document.addEventListener('click',e=>{const node=e.target.closest('[data-node]');if(node){show(node.dataset.node);return}const tab=e.target.closest('[data-view]');if(tab){view=tab.dataset.view;document.querySelectorAll('[data-view]').forEach(b=>b.setAttribute('aria-selected',b===tab));redraw()}});$('search').addEventListener('input',redraw);$('run').addEventListener('change',()=>{selected=null;$('detail').innerHTML='<h2>Decision Detail</h2><p class="muted">选择此运行的记录。</p>';redraw()});redraw();
</script></html>'''
