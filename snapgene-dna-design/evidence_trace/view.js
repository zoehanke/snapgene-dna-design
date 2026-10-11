/* Fixed offline renderer: all scientific content comes from saved records/organization. */
'use strict';
const graph=JSON.parse(document.getElementById('trace-data').textContent);
const data=graph.report;
const state={mode:'document',selected:data.steps[0]?.id,expanded:new Set(data.default_expanded_refs||[]),pane:'map'};
const escape=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const h=escape;
const sources=data.sources;
const stepById=Object.fromEntries(data.steps.map(s=>[s.id,s]));
const icons={
goal:'<path d="M6 2h8l5 5v15H6z"/><path d="M14 2v6h5M9 12h6M9 16h6" fill="none" stroke="white" stroke-width="1.4"/>',
process:'<g fill="none" stroke="currentColor" stroke-width="1.7"><circle cx="12" cy="4" r="2.5"/><circle cx="4" cy="20" r="2.5"/><circle cx="12" cy="20" r="2.5"/><circle cx="20" cy="20" r="2.5"/><path d="M12 7v10M4 17v-5h16v5"/></g>',
outcome:'<path d="M2 6h8l2 2h10v13H2z" fill="none" stroke="currentColor" stroke-width="1.8"/>',
review:'<path d="M9 2h6M10 2v8L4 21h16l-6-11V2" fill="none" stroke="currentColor" stroke-width="1.8"/>',
records:'<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 4 16 4 16 0V5M4 12c0 4 16 4 16 0" fill="none" stroke="currentColor" stroke-width="1.6"/>'};
function icon(name){return '<svg viewBox="0 0 24 24" aria-hidden="true">'+icons[name]+'</svg>';}
function button(ref,label){return '<button class="source-link" data-source="'+h(ref)+'">'+h(label||sources[ref]?.label||ref)+'</button>';}
function refList(refs){return [...new Set(refs||[])].filter(r=>sources[r]).map(r=>button(r)).join(' ');}
function chapter(id,title,body,extra=''){return '<section id="'+id+'" class="chapter"><header><h2>'+h(title)+'</h2>'+extra+'</header><div class="chapter-body">'+body+'</div></section>';}
function classification(step){return step.kind==='choice'?'ai':step.kind==='program_result'?'program':'neutral';}
function sourceValue(ref){return sources[ref]||{};}
function relationLinks(step){return data.relations.filter(r=>r.from===step.id||r.to===step.id).map(r=>'<p class="relation">'+h(r.meaning)+' · '+h(stepById[r.from]?.title||r.from)+' → '+h(stepById[r.to]?.title||r.to)+'</p>').join('');}
function inputs(step){const rows=[['输入',step.input_refs],['输出 / 检查对象',step.outcome_refs]].filter(([,refs])=>refs?.length);return rows.length?'<dl class="io">'+rows.map(([label,refs])=>'<dt>'+h(label)+'</dt><dd>'+refList(refs)+'</dd>').join('')+'</dl>':'';}
function check(c){return '<div class="check '+h(c.status)+'"><strong>'+h(c.display_check||c.check)+'</strong><span>'+h(c.display_result||c.result)+'</span>'+button(c.ref,'查看对象与范围')+'</div>';}
function artifact(a){return '<div class="artifact"><strong>'+h(a.display_role||a.role)+'</strong><span>'+h(a.name||a.path)+'</span>'+button(a.ref,'文件与来源')+'</div>';}
const originLabels={original_statement:'原始公开说明',organized_summary:'根据记录整理',later_interpretation:'后来补充解释',unknown:'原始理由未记录'};
function evidenceBody(e){return '<section class="evidence-entry"><p>'+h(e.label||e.relation)+'：'+h(e.statement)+'</p><p>对应判断：'+h(e.claim)+'</p>'+(e.aspect?'<p>适用方面：'+h(e.aspect)+'</p>':'')+(e.assessment?'<p>'+h(e.assessment.reason)+'</p>':'')+(e.conditions||[]).map(v=>'<p>条件：'+h(v)+'</p>').join('')+(e.limitations||[]).map(v=>'<p class="limit">'+h(v)+'</p>').join('')+refList(e.record_refs)+'</section>';}
function changeBody(c){return '<section class="change-entry"><h3>'+h(c.field)+'</h3><p>'+h(c.before)+' → '+h(c.after)+'</p>'+c.impacts.map(i=>'<div class="evidence-entry"><p><strong>'+h(i.target_title)+'</strong>：'+h(i.judgment)+'</p><p>'+h(i.actions.join('；'))+'</p><p class="note">'+h(i.reason)+'</p>'+refList([i.target_ref])+'</div>').join('')+'</section>';}
function stepBody(step,detail=false){
 const reason=step.reason?'<p class="reason"><small>'+h(originLabels[step.reason.origin]||'说明来源未知')+'</small>'+h(step.reason.text)+'</p>':'';
 const limits=(step.limitations||[]).map(l=>'<p class="limit">'+h(l.text)+'</p>').join('');
 const evidence=(step.evidence||[]).map(evidenceBody).join('');
 const expansions=(step.recorded_explanations||[]).map(e=>'<p>事后补充：'+h(e.text)+'</p>').join('');
 const body='<p>'+h(step.content===step.title?'':step.content)+'</p>'+reason+limits+(step.changes||[]).map(changeBody).join('')+(step.checks||[]).map(check).join('')+(step.artifacts||[]).map(artifact).join('')+(step.program_records||[]).map(r=>button(r,'查看实际程序返回')).join('');
 return '<article class="step '+classification(step)+'" data-step="'+h(step.id)+'"><div class="step-title"><span>'+h(step.label)+'</span><h3>'+h(step.title)+'</h3></div>'+inputs(step)+body+
 '<details data-expand="'+h(step.id)+'" '+(state.expanded.has(step.id)?'open':'')+'><summary>查看依据与完整记录</summary><div class="evidence">'+refList(step.source_refs)+evidence+expansions+relationLinks(step)+'</div></details></article>';
}
function requirement(r){return '<div class="requirement"><p>'+h(r.text)+'</p>'+button(r.key,'查看请求来源')+'</div>';}
const status=data.snapshot.organization_status;
const caution=status==='current'?'':status==='stale'?'新记录尚未纳入原组织。以下显示有限事实，旧组织保存在详细记录。':'尚未提交设计过程组织。以下为已采集事实，不是完整设计解释。';
const failed=data.checks.filter(c=>c.status==='failed').length;
const unknown=data.checks.filter(c=>c.status==='unknown').length;
const actualChecked=data.checks.filter(c=>c.status!=='not_requested').length;
const nFiles=data.artifacts.length;
const header='<div class="report-meta">'+(data.available_formats.includes('markdown')?'<a href="report.md" download>下载 Markdown</a>':'')+'<button data-special="scope">记录范围</button></div><header class="report-head"><div class="heading"><h1>'+h(data.title)+'</h1>'+
 (data.context?'<p>'+h(data.context.text)+'</p>':'')+'</div><dl class="overview"><div><dt>得到什么</dt><dd>'+(data.outcome_summary?h(data.outcome_summary):(nFiles?h(nFiles)+' 条产物版本记录':'未记录产物'))+'<a href="#outcome">查看文件 →</a></dd></div><div><dt>程序检查</dt><dd>'+h(actualChecked)+' 项已请求的检查；'+h(failed)+' 项未通过，'+h(unknown)+' 项结果未知。<a href="#outcome">检查范围 →</a></dd></div><div><dt>尚需复核</dt><dd>'+(data.review.length?h(data.review.length)+' 项记录中的问题，见具体对象与范围。':'未记录当前待办；不代表全部科学问题已验证。')+'</dd></div></dl></header>';
const scope='<p class="scope">记录完整性：'+(data.integrity==='complete'?'完整':'有缺口')+' · 过程组织'+(status==='current'?'与记录版本一致':status==='stale'?'已陈旧':'尚未提供')+'</p>';
const modes='<div class="modes" role="group" aria-label="阅读方式"><button data-mode="document" aria-pressed="true">正文</button><button data-mode="map" aria-pressed="false">过程图</button><button data-mode="split" aria-pressed="false">图文对照</button></div>';
const goal=chapter('goal','任务与要求',(data.requirements.length?data.requirements.map(requirement).join(''):'<p>未记录用户要求。请查看已有程序记录。</p>')+'<p class="note">记录区分用户要求、公开选择与程序结果，供人复核；不作安全判定或展示隐藏思维。</p>');
const reading=chapter('process','设计怎样形成',scope+(caution?'<p class="notice">'+h(caution)+'</p>':'')+'<div id="document-view"></div><div id="visual-view" hidden><div class="mobile-panes"><button data-pane="map">图</button><button data-pane="detail">详情</button></div><div class="visual-inner"><div id="chain"></div><div id="detail-pane"></div></div></div>',modes);
const outcome=chapter('outcome','交付文件与检查',(nFiles?data.artifacts.map(artifact).join(''):'<p>未记录文件产物。</p>')+'<h3>程序检查范围</h3>'+(data.checks.length?data.checks.map(check).join(''):'<p>未记录程序验证。</p>')+((data.unverified_scope||[]).length?'<h3>程序未验证的范围</h3><ul>'+data.unverified_scope.map(value=>'<li>'+h(value)+'</li>').join('')+'</ul>':'')+(data.handoff?'<h3>交付清单核对</h3>'+data.handoff.files.map(f=>'<p>'+h(f.path.replace(/\\/g,'/').split('/').pop())+' · '+h(({linked:'已关联生成记录',untraced:'缺少生成过程记录',missing:'交付时文件不存在',changed:'文件版本已变化',ambiguous:'生成来源尚未确定'})[f.status])+'</p>').join(''):''));
const reviews=data.review.length?chapter('review','当前需要处理',data.review.map(r=>'<div class="review"><p>'+h(r.text)+'</p>'+refList(r.source_refs)+'</div>').join('')):'';
function group(label,refs){return '<details><summary>'+h(label)+' · '+refs.length+'</summary><div>'+refList(refs)+'</div></details>';}
const keys=Object.keys(sources);
const records=chapter('records','来源与详细记录',group('要求与选择',keys.filter(k=>['requirement','decision'].includes(sourceValue(k).kind)))+
group('来源、陈述与判断',keys.filter(k=>['source','statement','claim'].includes(sourceValue(k).kind)))+
group('程序与文件',keys.filter(k=>['validation','artifact'].includes(sourceValue(k).kind)))+
group('尚未归类的记录',data.coverage.unassigned_refs)+(data.recording_gaps.length?'<h3>记录完整性</h3>'+data.recording_gaps.map(g=>'<p>'+h(g.text)+'</p>').join(''):'')+
'<div class="record-tools"><button data-special="relations">完整关系记录</button><button data-special="changes">变化与影响</button><button data-special="history">组织版本</button><button data-special="audit">原始日志</button><button data-special="scope">采集与组织缺口</button></div>');
document.getElementById('report').innerHTML=header+goal+reading+outcome+reviews+records;
document.title=data.title+' · Evidence Trace';
const names={goal:'任务与要求',process:'设计形成过程',outcome:'交付文件与检查',review:'当前需要处理',records:'来源记录'};
document.getElementById('chapters').innerHTML=Object.entries(names).filter(([id])=>document.getElementById(id)).map(([id,title])=>'<a href="#'+id+'" aria-label="'+title+'" title="'+title+'">'+icon(id)+'<span>'+title+'</span></a>').join('');
function renderDocument(){
 const used=new Set();let html='';
 const sections=data.sections.length?data.sections:data.stages.map(s=>({title:s.title,summary:s.purpose,step_refs:s.step_ids}));
 for(const section of sections){const ids=section.step_refs.filter(k=>stepById[k]&&!used.has(k));if(!ids.length)continue;
 html+='<div class="stage"><h3>'+h(section.title)+'</h3>'+(section.summary?'<p>'+h(section.summary)+'</p>':'')+'</div>';
 for(const id of ids){used.add(id);html+=stepBody(stepById[id]);}}
 for(const s of data.steps)if(!used.has(s.id))html+=stepBody(s);
 document.getElementById('document-view').innerHTML=html||'<p>尚无可显示的步骤。</p>';
}
function renderChain(){
 const order=[...new Set([...(data.diagram.reading_order||[]),...data.steps.map(s=>s.id)])];
 const html=order.filter(id=>stepById[id]).map((id,i)=>{const s=stepById[id];const groups=data.stages.flatMap(stage=>(stage.branches||[]).filter(b=>b.step_ids.includes(id)).map(b=>b.label));const outgoing=data.relations.filter(r=>r.from===id).map(r=>'<p class="relation">'+h(r.meaning)+' → <button data-select="'+h(r.to)+'">'+h(stepById[r.to]?.title||r.to)+'</button></p>').join('');return '<article class="trace-node '+classification(s)+'" data-node="'+h(id)+'">'+(groups.length?'<p class="branch-label">'+groups.map(h).join(' / ')+'</p>':'')+'<button class="node-select" data-select="'+h(id)+'" aria-pressed="'+(id===state.selected)+'"><span>'+h(i+1)+' · '+h(s.label)+'</span><strong>'+h(data.diagram.short_labels?.[id]||s.title)+'</strong></button>'+inputs(s)+'<div class="node-sources">'+refList(s.source_refs)+'</div>'+outgoing+'</article>';}).join('');
 // Relations appear by their recorded meaning, not inferred from vertical proximity.
 document.getElementById('chain').innerHTML=html;
}
function selected(){
 document.querySelectorAll('.node-select').forEach(b=>{const active=b.dataset.select===state.selected;b.setAttribute('aria-pressed',String(active));b.closest('.trace-node').dataset.selected=String(active);});
 const s=stepById[state.selected];document.getElementById('detail-pane').innerHTML=s?'<header class="selection '+classification(s)+'"><span>'+h(data.steps.indexOf(s)+1)+' · '+h(s.label)+'</span><h3>'+h(s.title)+'</h3></header>'+stepBody(s,true):'<p>没有步骤。</p>';
}
function mode(value){
 state.mode=value;document.getElementById('document-view').hidden=value!=='document';
 const visual=document.getElementById('visual-view');visual.hidden=value==='document';visual.className='mode-'+value;visual.dataset.pane=state.pane;
 document.querySelectorAll('[data-mode]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.mode===value)));
 selected();if(value==='document'&&state.selected){const target=[...document.querySelectorAll('#document-view [data-step]')].find(e=>e.dataset.step===state.selected);target?.scrollIntoView({block:'center'});}
}
const drawer=document.getElementById('drawer');
function openSource(ref){
 const source=sources[ref];if(!source)return;
 const fields=source.fields.map(f=>'<section class="detail-section"><h3>'+h(f.label)+'</h3><p>'+h(f.text)+'</p></section>').join('');
 const links=source.links.map(l=>'<p><a href="'+h(l.href)+'" target="_blank" rel="noopener noreferrer">'+h(l.label)+' ↗</a></p>').join('');
 const related=source.related.filter(r=>sources[r.ref]).map(r=>'<p>'+h(r.label)+'：'+button(r.ref)+'</p>').join('');
 document.getElementById('drawer-body').innerHTML='<p class="note">'+h(source.type_label)+'</p><h2>'+h(source.title)+'</h2>'+fields+(source.evidence||[]).map(e=>'<h3>用于选择：'+h(e.decision_title)+'</h3>'+evidenceBody(e)).join('')+(source.changes||[]).map(changeBody).join('')+links+related+'<footer class="technical-link"><a href="graph.json" target="_blank">技术记录（完整机器数据）</a></footer>';
 if(!drawer.open)drawer.showModal();
}
function special(name){
 const descriptions={relations:'完整关系保留在机器结果中。关系的含义由原记录注明，阅读顺序不表示因果。',changes:'这里显示实际变化、受影响对象及需要重查的内容。',history:'组织版本及对应的记录范围保留在机器结果中。',audit:'追加日志保存原始采集内容和失败记录。',scope:'记录完整性只指已采集记录；未观测的宿主活动不在覆盖范围内。'};
 let body='<p>'+h(descriptions[name])+'</p>';
 if(name==='changes')body+=(data.change_details.length?'<p>以下为重查建议，不修改原判断或检查结果。</p>'+data.change_details.map(changeBody).join(''):'<p>未记录设计变化。</p>');
 if(name==='scope')body+=data.recording_gaps.map(g=>'<p>'+h(g.text)+'</p>').join('');
 document.getElementById('drawer-body').innerHTML='<h2>'+h({relations:'关系技术记录',changes:'变化与影响',history:'组织版本',audit:'原始日志',scope:'记录范围与缺口'}[name])+'</h2>'+body+'<p><a href="'+(name==='audit'?'events.jsonl':'graph.json')+'" target="_blank">打开完整技术文件</a></p>';
 if(!drawer.open)drawer.showModal();
}
document.addEventListener('click',e=>{
 const m=e.target.closest('[data-mode]');if(m){mode(m.dataset.mode);return;}
 const p=e.target.closest('button[data-pane]');if(p){state.pane=p.dataset.pane;document.getElementById('visual-view').dataset.pane=state.pane;document.querySelectorAll('button[data-pane]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.pane===state.pane)));return;}
 const b=e.target.closest('[data-select]');if(b){state.selected=b.dataset.select;state.pane='detail';selected();document.getElementById('visual-view').dataset.pane='detail';return;}
 const ref=e.target.closest('[data-source]');if(ref){openSource(ref.dataset.source);return;}
 const sp=e.target.closest('[data-special]');if(sp){special(sp.dataset.special);return;}
 const step=e.target.closest('#document-view [data-step]');if(step)state.selected=step.dataset.step;
});
document.addEventListener('toggle',e=>{const d=e.target;if(!d.matches?.('details[data-expand]'))return;
 d.open?state.expanded.add(d.dataset.expand):state.expanded.delete(d.dataset.expand);
 document.querySelectorAll('details[data-expand]').forEach(other=>{if(other!==d&&other.dataset.expand===d.dataset.expand&&other.open!==d.open)other.open=d.open;});
},true);
document.getElementById('close-drawer').onclick=()=>drawer.close();
document.getElementById('collapse').onclick=()=>{const collapsed=document.body.classList.toggle('collapsed');document.getElementById('collapse').setAttribute('aria-expanded',String(!collapsed));};
const directory=document.getElementById('directory');
directory.onclick=()=>{const open=document.body.classList.toggle('menu-open');directory.setAttribute('aria-expanded',String(open));};
document.querySelectorAll('#chapters a').forEach(a=>a.onclick=()=>{document.body.classList.remove('menu-open');directory.setAttribute('aria-expanded','false');});
function locate(){let current='goal';document.querySelectorAll('main>.chapter').forEach(s=>{if(s.getBoundingClientRect().top<=105)current=s.id;});
 document.getElementById('current').textContent=names[current];
 document.querySelectorAll('#chapters a').forEach(a=>{const on=a.hash==='#'+current;a.classList.toggle('active',on);on?a.setAttribute('aria-current','location'):a.removeAttribute('aria-current');});
}
let ticking=false;addEventListener('scroll',()=>{if(!ticking){ticking=true;requestAnimationFrame(()=>{locate();ticking=false;});}},{passive:true});
renderDocument();renderChain();selected();locate();
