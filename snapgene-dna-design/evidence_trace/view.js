/* Fixed offline reader. All scientific content belongs to the saved projection. */
'use strict';
const graph = JSON.parse(document.getElementById('trace-data').textContent);
const data = graph.report;
const sources = data.sources;
const state = {mode:'document', focus:false, selected:data.steps[0]?.id, expanded:new Set(data.default_expanded_refs || []), pane:'map'};
const h = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const stepById = Object.fromEntries(data.steps.map(step => [step.id, step]));
const rank = Object.fromEntries(data.steps.map((step, i) => [step.id, i + 1]));
const sourceRank = Object.fromEntries(Object.keys(sources).map((ref, i) => [ref, i + 1]));
const relations = new Map();
const branches = new Map();
const nodeElements = new Map();
const detailHTML = new Map();
const programLabels = new Map();
let chainReady = false;
let detailSelected;
let sourceCurrent;
let stepCurrent;
let drawerOpener;
const sourceHistory = [];

// Format an already-linked program record using its saved reading step. This is
// a display alias, not a new relationship, interpretation or scientific claim.
for (const step of data.steps) if (step.kind === 'program_result') {
  for (const [refs,prefix] of [[step.input_refs,'调用输入'],[step.source_refs,'实际返回']]) for (const ref of refs || []) {
    if (sources[ref]?.type_label !== '程序记录') continue;
    const text = prefix + ' · ' + step.title;
    if (!programLabels.has(ref)) programLabels.set(ref,new Set());
    programLabels.get(ref).add(text);
  }
}
function sourceTitle(ref) {
  const aliases = programLabels.get(ref);
  return aliases?.size === 1 ? [...aliases][0] : sources[ref]?.title || sources[ref]?.label || '记录 ' + sourceRank[ref];
}

for (const relation of data.relations) {
  for (const id of new Set([relation.from, relation.to])) {
    if (!relations.has(id)) relations.set(id, []);
    relations.get(id).push(relation);
  }
}
for (const stage of data.stages) for (const branch of stage.branches || []) for (const id of branch.step_ids) {
  if (!branches.has(id)) branches.set(id, []);
  branches.get(id).push(branch.label);
}
const icons = {
  goal:'<path d="M6 2h8l5 5v15H6z"/><path d="M14 2v6h5M9 12h6M9 16h6" fill="none" stroke="white" stroke-width="1.4"/>',
  process:'<g fill="none" stroke="currentColor" stroke-width="1.7"><circle cx="12" cy="4" r="2.5"/><circle cx="4" cy="20" r="2.5"/><circle cx="12" cy="20" r="2.5"/><circle cx="20" cy="20" r="2.5"/><path d="M12 7v10M4 17v-5h16v5"/></g>',
  outcome:'<path d="M2 6h8l2 2h10v13H2z" fill="none" stroke="currentColor" stroke-width="1.8"/>',
  review:'<path d="M9 2h6M10 2v8L4 21h16l-6-11V2" fill="none" stroke="currentColor" stroke-width="1.8"/>',
  records:'<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 4 16 4 16 0V5M4 12c0 4 16 4 16 0" fill="none" stroke="currentColor" stroke-width="1.6"/>'
};
const icon = name => '<svg viewBox="0 0 24 24" aria-hidden="true">' + icons[name] + '</svg>';
function button(ref, label) {
  if (!sources[ref]) return '<span class="record-unavailable">来源记录不可用</span>';
  return '<button class="source-link" data-source="' + h(ref) + '">' + h(label || (programLabels.has(ref) ? sourceTitle(ref) : sources[ref].label || sourceTitle(ref))) + '</button>';
}
const refList = refs => [...new Set(refs || [])].filter(ref => sources[ref]).map(ref => button(ref)).join(' ');
const chapter = (id, title, body, extra='') => '<section id="' + id + '" class="chapter"><header><h2>' + h(title) + '</h2>' + extra + '</header><div class="chapter-body">' + body + '</div></section>';
function classification(step) {
  if (step.kind === 'program_result' || step.kind === 'program') return 'program';
  if (step.kind === 'choice') return step.label === 'AI 选择' ? 'ai' : step.label === '用户选择' ? 'user' : 'neutral';
  return step.kind === 'artifact' ? 'output' : 'neutral';
}
function referenceTarget(ref) {
  if (stepById[ref]) return '<button class="step-link" data-select="' + h(ref) + '">' + h(stepById[ref].title) + '</button>';
  return sources[ref] ? button(ref) : '<span>关联对象未记录可读名称</span>';
}
function relationStanding(relation) {
  const ids = new Set(relation.fact_relation_ids || []);
  // An existing fact ID may still name a declaration or structural association.
  // Only computed file-content equality backs a line in this reader.
  const backed = relation.kind === 'grouped_with' && (data.fact_relations || []).some(fact =>
    ids.has(fact.id) && fact.origin === 'program_derived' && fact.kind === 'input_reference' &&
    fact.scope === 'same_file_content' && fact.verification_method === 'sha256_equality' &&
    /^[0-9a-f]{64}$/i.test(fact.sha256 || ''));
  return {backed, standing:backed ? '程序验证：输出与声明输入文件的SHA-256相等；不证明科学支持、物理使用或因果' : '声明，程序未验证'};
}
function relationLinks(step) {
  return (relations.get(step.id) || []).map(relation => '<p class="relation">' + h(relation.meaning) + ' · ' + referenceTarget(relation.from) + ' → ' + referenceTarget(relation.to) + ' <small class="standing">' + h(relationStanding(relation).standing) + '</small></p>').join('');
}
function inputs(step) {
  const rows = [['输入',step.input_refs],['输出 / 检查对象',step.outcome_refs]].filter(([,refs]) => refs?.length);
  return rows.length ? '<dl class="io">' + rows.map(([label,refs]) => '<dt>' + h(label) + '</dt><dd>' + refList(refs) + '</dd>').join('') + '</dl>' : '';
}
const check = item => '<div class="check ' + h(item.status) + '"><strong>' + h(item.display_check || item.check) + '</strong><span>' + h(item.display_result || item.result) + '</span>' + button(item.ref,'查看对象与范围') + '</div>';
const artifact = item => '<div class="artifact"><strong>' + h(item.display_role || item.role) + '</strong><span>' + h(item.name || item.path) + '</span>' + button(item.ref,'文件与来源') + '</div>';
const originLabels = {original_statement:'原始公开说明', organized_summary:'根据记录整理', later_interpretation:'后来补充解释', unknown:'原始理由未记录'};
function evidenceBody(item) {
  return '<section class="evidence-entry"><p>' + h(item.label || item.relation) + '：' + h(item.statement) + '</p><p>对应判断：' + h(item.claim) + '</p>' + (item.aspect ? '<p>适用方面：' + h(item.aspect) + '</p>' : '') + (item.assessment ? '<p>' + h(item.assessment.reason) + '</p>' : '') + (item.conditions || []).map(value => '<p>条件：' + h(value) + '</p>').join('') + (item.limitations || []).map(value => '<p class="limit">' + h(value) + '</p>').join('') + refList(item.record_refs) + '</section>';
}
function impactGroups(change) {
  const groups = new Map();
  for (const item of change.impacts || []) {
    const key = item.code + '|' + item.actions.join('；');
    if (!groups.has(key)) groups.set(key, {code:item.code, judgment:item.judgment, actions:item.actions, reason:item.reason, items:[]});
    groups.get(key).items.push(item);
  }
  return [...groups.values()];
}
// Impacts that share one judgment are listed once; "unknown" ones carry no finding and are folded.
function changeBody(change) {
  const rows = impactGroups(change).map(group => {
    const list = group.items.map(item => sources[item.target_ref] ? button(item.target_ref, item.target_title) : '<span>' + h(item.target_title) + '</span>').join(' ');
    const head = '<strong>' + h(group.judgment) + '</strong>' + (group.actions.length ? '（' + h(group.actions.join('；')) + '）' : '') + ' · ' + group.items.length + ' 项';
    if (group.code === 'UNKNOWN') return '<details class="impact-group"><summary>' + head + '</summary><p class="note">' + h(group.reason) + '</p><div>' + list + '</div></details>';
    return '<div class="impact-group"><p>' + head + '</p><p class="note">' + h(group.reason) + '</p><div>' + list + '</div></div>';
  }).join('');
  return '<section class="change-entry"><h3>' + h(change.field) + '</h3><p class="change-diff"><span>' + h(change.before) + '</span><b>→</b><span>' + h(change.after) + '</span></p>' + rows + '</section>';
}
const loudCheck = item => item.status === 'failed' || item.status === 'unknown';
function stepBadges(step) {
  const count = value => (step.checks || []).filter(item => item.status === value).length;
  const parts = [];
  if (count('passed')) parts.push('<i class="b-pass">✓ ' + count('passed') + ' 项检查通过</i>');
  if (count('failed')) parts.push('<i class="b-fail">✗ ' + count('failed') + ' 项未通过</i>');
  if (count('unknown')) parts.push('<i class="b-unknown">? ' + count('unknown') + ' 项未知</i>');
  if ((step.artifacts || []).length) parts.push('<i class="b-file">文件 ' + step.artifacts.length + '</i>');
  if ((step.changes || []).length) parts.push('<i class="b-change">变化 ' + step.changes.length + '</i>');
  const pending = data.review.filter(item => (item.step_refs || []).includes(step.id)).length;
  if (pending) parts.push('<i class="b-open">待处理 ' + pending + '</i>');
  return parts.join('');
}
function routineRows(step) {
  return inputs(step) + (step.checks || []).filter(item => !loudCheck(item)).map(check).join('') + (step.artifacts || []).map(artifact).join('') + (step.changes || []).map(changeBody).join('') + (step.program_records || []).map(ref => button(ref,'查看实际程序返回')).join('');
}
function expandedContent(step, flat=false) {
  const base = refList(step.source_refs) + (step.evidence || []).map(evidenceBody).join('') + (step.recorded_explanations || []).map(item => '<p>事后补充：' + h(item.text) + '</p>').join('') + relationLinks(step);
  if (flat) return base;
  if (!detailHTML.has(step.id)) detailHTML.set(step.id, routineRows(step) + base);
  return detailHTML.get(step.id);
}
function stepBody(step, flat=false) {
  const reason = step.reason ? '<p class="reason"><small>' + h(originLabels[step.reason.origin] || '说明来源未知') + '</small>' + h(step.reason.text) + '</p>' : '';
  const limits = (step.limitations || []).map(item => '<p class="limit">' + h(item.text) + '</p>').join('');
  const open = state.expanded.has(step.id);
  const loud = (step.checks || []).filter(loudCheck);
  const folded = [];
  const routine = (step.checks || []).filter(item => !loudCheck(item)).length;
  if (routine) folded.push('检查 ' + routine);
  if ((step.artifacts || []).length) folded.push('文件 ' + step.artifacts.length);
  if ((step.changes || []).length) folded.push('变化 ' + step.changes.length);
  const summary = flat || !folded.length ? '查看依据与完整记录' : '展开：' + folded.join(' · ') + ' · 依据与完整记录';
  // The side pane and the drawer show everything at once; the reading flow folds routine rows.
  const body = flat ? inputs(step) + (step.content !== step.title ? '<p>' + h(step.content) + '</p>' : '') + reason + limits + (step.changes || []).map(changeBody).join('') + (step.checks || []).map(check).join('') + (step.artifacts || []).map(artifact).join('') + (step.program_records || []).map(ref => button(ref,'查看实际程序返回')).join('')
    : (step.content !== step.title ? '<p>' + h(step.content) + '</p>' : '') + reason + limits + loud.map(check).join('') + '<div class="step-badges">' + stepBadges(step) + '</div>';
  return '<article class="step ' + classification(step) + '" data-step="' + h(step.id) + '"><div class="step-title"><span class="step-number">' + h(rank[step.id]) + '</span><div><span class="step-kind">' + h(step.label) + '</span><h3>' + h(step.title) + '</h3></div></div>' + body + '<details data-expand="' + h(step.id) + '" ' + (open ? 'open' : '') + '><summary>' + summary + '</summary><div class="evidence" data-detail-for="' + h(step.id) + '">' + (open ? expandedContent(step, flat) : '') + '</div></details></article>';
}
const status = data.snapshot.organization_status;
const caution = status === 'current' ? '' : status === 'stale' ? '新记录尚未纳入原组织。以下显示有限事实，旧组织保存在详细记录。' : '尚未提交设计过程组织。以下为已采集事实，不是完整设计解释。';
const failed = data.checks.filter(item => item.status === 'failed').length;
const unknown = data.checks.filter(item => item.status === 'unknown').length;
const actualChecked = data.checks.filter(item => item.status !== 'not_requested').length;
const nFiles = data.artifacts.length;
const unverified = data.unverified_scope || [];
const overviewReview = data.review.length ? '<div class="overview-review"><dt>当前待处理</dt><dd>' + h(data.review.length) + ' 项记录中的问题。<a href="#review">查看具体问题 →</a></dd></div>' : unverified.length ? '<div class="overview-review"><dt>程序未验证</dt><dd>' + h(unverified[0]) + '<a href="#outcome">查看全部确认边界 →</a></dd></div>' : unknown ? '<div class="overview-review"><dt>结果尚未确定</dt><dd>存在未知的程序检查结果。<a href="#outcome">查看对象与范围 →</a></dd></div>' : '';
const header = '<div class="report-meta"><span>Design decision trace</span><div>' + (data.available_formats.includes('markdown') ? '<a href="report.md" download>下载 Markdown</a>' : '') + '<button data-special="scope">记录范围</button></div></div><header class="report-head"><div class="heading"><p class="eyebrow">EVIDENCE TRACE / 生物设计记录</p><h1>' + h(data.title) + '</h1>' + (data.context ? '<p>' + h(data.context.text) + '</p>' : '') + '</div><dl class="overview"><div><dt>本次结果</dt><dd>' + (data.outcome_summary ? h(data.outcome_summary) : nFiles ? h(nFiles) + ' 条产物版本记录' : '未记录产物') + '<a href="#outcome">查看文件 →</a></dd></div><div><dt>程序检查</dt><dd>' + h(actualChecked) + ' 项已请求检查；' + h(failed) + ' 项未通过，' + h(unknown) + ' 项结果未知。<a href="#outcome">对象与检查范围 →</a></dd></div>' + overviewReview + '</dl></header>';
const goal = chapter('goal','任务与要求',(data.requirements.length ? data.requirements.map(item => '<div class="requirement"><p>' + h(item.text) + '</p>' + button(item.key,'查看请求来源') + '</div>').join('') : '<p>未记录用户要求。请查看已有程序记录。</p>') + '<p class="note trace-purpose">记录区分用户要求、公开选择与程序结果，供人复核；不作安全判定或展示隐藏思维。</p>');
const scope = '<p class="scope">记录完整性：' + (data.integrity === 'complete' ? '完整' : '有缺口') + ' · 过程组织' + (status === 'current' ? '与记录版本一致' : status === 'stale' ? '已陈旧' : '尚未提供') + '</p>';
const modes = '<div class="modes" role="group" aria-label="阅读方式"><button data-mode="document" aria-pressed="true">正文</button><button data-mode="map" aria-pressed="false">过程图</button><button data-mode="split" aria-pressed="false">图文对照</button></div>';
const reading = chapter('process','设计怎样形成',scope + (caution ? '<p class="notice">' + h(caution) + '</p>' : '') + '<div id="document-view"></div><div id="visual-view" hidden><div class="mobile-panes"><button data-pane="map" aria-pressed="true">图</button><button data-pane="detail" aria-pressed="false">详情</button></div><div class="visual-inner"><div id="chain"></div><div id="detail-pane"></div></div></div>',modes);
const handoffLabels = {linked:'已关联生成记录', untraced:'缺少生成过程记录', missing:'交付时文件不存在', changed:'文件版本已变化', ambiguous:'生成来源尚未确定'};
const outcome = chapter('outcome','交付文件与检查',(nFiles ? data.artifacts.map(artifact).join('') : '<p>未记录文件产物。</p>') + '<h3>程序检查范围</h3>' + (data.checks.length ? data.checks.map(check).join('') : '<p>未记录程序验证。</p>') + ((data.unverified_scope || []).length ? '<h3>程序未验证的范围</h3><ul>' + data.unverified_scope.map(value => '<li>' + h(value) + '</li>').join('') + '</ul>' : '') + (data.handoff ? '<details class="handoff-detail"><summary>交付清单与生成记录</summary><div>' + data.handoff.files.map(item => '<p>' + h(item.path.replace(/\\/g,'/').split('/').pop()) + ' · ' + h(handoffLabels[item.status] || '记录中尚未解释的交付状态') + '</p>').join('') + '</div></details>' : ''));
const reviews = data.review.length ? chapter('review','当前需要处理',data.review.map(item => '<div class="review"><p>' + h(item.text) + '</p>' + refList(item.source_refs) + '</div>').join('')) : '';
function group(label, refs) { return '<details><summary>' + h(label) + ' · ' + refs.length + '</summary><div>' + refList(refs) + '</div></details>'; }
const keys = Object.keys(sources);
const records = chapter('records','来源与详细记录',group('要求与选择',keys.filter(key => ['requirement','decision'].includes(sources[key].kind))) + group('来源、陈述与判断',keys.filter(key => ['source','statement','claim'].includes(sources[key].kind))) + group('程序与文件',keys.filter(key => ['validation','artifact'].includes(sources[key].kind))) + group('尚未归类的记录',data.coverage.unassigned_refs) + (data.recording_gaps.length ? '<h3>记录完整性</h3>' + data.recording_gaps.map(item => '<p>' + h(item.text) + '</p>').join('') : '') + '<div class="record-tools"><button data-special="relations">完整关系记录</button><button data-special="changes">变化与影响</button><button data-special="history">组织版本</button><button data-special="audit">原始日志</button><button data-special="scope">采集与组织缺口</button></div>');
document.getElementById('report').innerHTML = header + goal + reading + outcome + reviews + records;
document.title = data.title + ' · Evidence Trace';
const names = {goal:'任务与要求', process:'设计形成过程', outcome:'交付文件与检查', review:'当前需要处理', records:'来源记录'};
document.getElementById('chapters').innerHTML = Object.entries(names).filter(([id]) => document.getElementById(id)).map(([id,title], index) => '<a href="#' + id + '" aria-label="' + title + '">' + icon(id) + '<span>' + title + '</span><small>' + (index + 1) + '</small></a>').join('');

function renderDocument() {
  const used = new Set(); let html = '';
  const sections = data.sections.length ? data.sections : data.stages.map(stage => ({title:stage.title, summary:stage.purpose, step_refs:stage.step_ids}));
  for (const section of sections) {
    const ids = section.step_refs.filter(id => stepById[id] && !used.has(id));
    if (!ids.length) continue;
    html += '<div class="stage"><h3>' + h(section.title) + '</h3>' + (section.summary ? '<p>' + h(section.summary) + '</p>' : '') + '</div>';
    for (const id of ids) { used.add(id); html += stepBody(stepById[id]); }
  }
  for (const step of data.steps) if (!used.has(step.id)) html += stepBody(step);
  document.getElementById('document-view').innerHTML = html || '<p>尚无可显示的步骤。</p>';
}
const LANES = [{key:'requirement',label:'用户要求'},{key:'choice',label:'设计选择'},{key:'program',label:'程序结果'},{key:'artifact',label:'产物与文件'}];
const laneOf = step => step.kind === 'requirement' ? 'requirement' : step.kind === 'choice' ? 'choice' : step.kind === 'artifact' ? 'artifact' : 'program';
let flowEdges = [];
function flowOrder() {
  const staged = data.stages.length > 1 ? data.stages.flatMap(stage => stage.step_ids) : [];
  return [...new Set([...staged, ...(data.diagram.reading_order || []), ...data.steps.map(step => step.id)])].filter(id => stepById[id]);
}
function flowGraph() {
  const order = flowOrder();
  const total = {}, seen = {};
  const label = id => data.diagram.short_labels?.[id] || stepById[id].title;
  order.forEach(id => { total[label(id)] = (total[label(id)] || 0) + 1; });
  const nodes = order.map(id => {
    const step = stepById[id], base = label(id);
    seen[base] = (seen[base] || 0) + 1;
    return {id, step, lane:laneOf(step), title:total[base] > 1 ? base + '（第' + seen[base] + '次）' : base};
  });
  const known = new Set(order);
  const edges = data.relations.filter(item => known.has(item.from) && known.has(item.to) && item.from !== item.to)
    .map(item => ({...item, ...relationStanding(item)}));
  // Declared "responds to" records connect a choice to the request it answers even when no step relation was authored.
  const byRef = {};
  data.steps.forEach(step => (step.source_refs || []).forEach(ref => { (byRef[ref] = byRef[ref] || []).push(step.id); }));
  const pair = new Set(edges.map(item => item.from + '>' + item.to));
  (data.fact_relations || []).filter(item => item.kind === 'responds_to' && item.origin === 'declared').forEach(item => {
    const a = (byRef[String(item.from).replace(/^record:/, '')] || [])[0], b = (byRef[String(item.to).replace(/^record:/, '')] || [])[0];
    if (a && b && a !== b && known.has(a) && known.has(b) && !pair.has(a + '>' + b) && !pair.has(b + '>' + a)) { pair.add(a + '>' + b); edges.push({from:a, to:b, kind:'responds_to', meaning:'回应该要求', backed:false}); }
  });
  return {nodes, edges};
}
function renderChain() {
  const host = document.getElementById('chain');
  const width = Math.floor(host.clientWidth || host.parentElement.clientWidth || 0);
  if (!width || host.dataset.width === String(width)) return;
  const {nodes, edges} = flowGraph();
  flowEdges = edges;
  const used = LANES.filter(lane => nodes.some(node => node.lane === lane.key));
  const L = used.length || 1, laneIndex = Object.fromEntries(used.map((lane, i) => [lane.key, i]));
  const wide = width >= Math.max(620, L * 190 + (L - 1) * 70);
  const gutter = wide ? 0 : 48, nodeH = 80, pitch = 92, bandH = 40;
  let nw, gap, indent = 0;
  if (wide) { nw = Math.min(260, Math.floor((width - (L - 1) * 64) / L)); gap = L > 1 ? Math.min(110, (width - L * nw) / (L - 1)) : 0; if (L === 1) nw = Math.min(420, width); }
  else { indent = L > 1 ? Math.min(22, Math.floor((width - gutter - 210) / (L - 1))) : 0; nw = width - gutter - indent * (L - 1); gap = 0; }
  const xOf = node => { const i = laneIndex[node.lane]; return wide ? (L === 1 ? 0 : i * (nw + gap)) : i * indent; };
  let y = wide && L > 1 ? 40 : 8, lastStage = null;
  const place = {}, bands = [], stageOf = {};
  data.stages.forEach(stage => stage.step_ids.forEach(id => { if (!(id in stageOf)) stageOf[id] = stage; }));
  nodes.forEach(node => {
    const stage = data.stages.length > 1 ? stageOf[node.id] : null;
    if (stage && stage !== lastStage) { bands.push({title:stage.title, purpose:stage.purpose, y}); y += bandH; lastStage = stage; }
    place[node.id] = {x:xOf(node), y, node}; y += pitch;
  });
  const gaps = [...(data.unverified_scope || []), ...data.recording_gaps.map(item => item.text)];
  const gapY = y + 6, total = y + (gaps.length ? 24 + gaps.length * 34 + 38 : 0);
  const connected = new Set(); edges.forEach(item => { connected.add(item.from); connected.add(item.to); });
  const heads = wide && L > 1 ? used.map((lane, i) => '<span class="lane-head lane-' + lane.key + '" style="left:' + (i * (nw + gap)) + 'px;width:' + nw + 'px">' + lane.label + '</span>').join('') : '';
  const track = {};
  const paths = edges.map((item, i) => {
    const a = place[item.from], b = place[item.to], ya = a.y + nodeH / 2, yb = b.y + nodeH / 2;
    const la = laneIndex[a.node.lane], lb = laneIndex[b.node.lane];
    let d;
    if (wide && la !== lb) {
      const right = la < lb, x1 = right ? a.x + nw : a.x, x2 = right ? b.x : b.x + nw, dx = Math.max(24, Math.abs(x2 - x1) / 2);
      d = 'M' + x1 + ' ' + ya + ' C' + (x1 + (right ? dx : -dx)) + ' ' + ya + ' ' + (x2 - (right ? dx : -dx)) + ' ' + yb + ' ' + x2 + ' ' + yb;
    } else {
      const k = Math.min(a.y, b.y) + '|' + Math.max(a.y, b.y); track[k] = (track[k] || 0) + 1;
      const edge = Math.max(a.x, b.x) + nw, out = 18 + Math.min(5, Math.floor(Math.abs(b.y - a.y) / pitch)) * 5 + (track[k] - 1) * 7;
      d = 'M' + (a.x + nw) + ' ' + ya + ' C' + (edge + out) + ' ' + ya + ' ' + (edge + out) + ' ' + yb + ' ' + (b.x + nw + 2) + ' ' + yb;
    }
    return '<path class="flow-edge ' + (item.backed ? 'is-backed' : 'is-declared') + '" data-from="' + h(item.from) + '" data-to="' + h(item.to) + '" d="' + d + '" marker-end="url(#arrow)"><title>' + h(item.standing || '声明，程序未验证') + '：' + h(item.meaning || '') + '</title></path>';
  }).join('');
  const bandHtml = bands.map(band => '<div class="flow-band" style="top:' + band.y + 'px" title="' + h(band.purpose || '') + '"><span>' + h(band.title) + '</span></div>').join('');
  const nodeHtml = nodes.map(node => {
    const p = place[node.id], failed = (node.step.checks || []).some(item => item.status === 'failed');
    return '<button class="flow-node k-' + node.lane + (failed ? ' is-failed' : '') + (connected.has(node.id) ? ' has-edge' : '') + '" data-select="' + h(node.id) + '" data-node="' + h(node.id) + '" aria-pressed="false" style="left:' + p.x + 'px;top:' + p.y + 'px;width:' + nw + 'px;height:' + nodeH + 'px"><span class="fn-type">' + h(rank[node.id]) + ' · ' + h(node.step.label) + '</span><strong class="fn-title">' + h(node.title) + '</strong><span class="fn-badges">' + stepBadges(node.step) + '</span></button>';
  }).join('');
  const gapHtml = gaps.length ? '<aside class="flow-gaps" style="top:' + gapY + 'px"><strong>没有覆盖的范围</strong>' + gaps.map(text => '<p>' + h(text) + '</p>').join('') + '</aside>' : '';
  const legend = '<div class="flow-legend">' + LANES.filter(lane => used.some(item => item.key === lane.key)).map(lane => '<span class="lg lg-' + lane.key + '">' + lane.label + '</span>').join('') + '<span class="lg lg-declared">虚线：声明或结构性关系，程序未验证其含义</span>' + (flowEdges.some(item => item.backed) ? '<span class="lg lg-backed">实线：程序核验文件SHA-256相等</span>' : '') + '<span class="lg-note">纵向是实际记录顺序，不表示因果。点击一步，高亮它的上下游。</span></div>';
  const none = edges.length ? '' : '<p class="flow-none">本次记录没有声明步骤之间的依据关系，所以图中没有连线。每一步的来源见“查看依据与完整记录”。</p>';
  host.innerHTML = legend + none + '<div class="flow" style="height:' + total + 'px">' + heads + bandHtml + '<svg class="flow-edges" width="' + width + '" height="' + total + '" aria-hidden="true"><defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerUnits="userSpaceOnUse" markerWidth="10" markerHeight="10" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z"/></marker></defs>' + paths + '</svg>' + nodeHtml + gapHtml + '</div>';
  host.dataset.width = String(width);
  markSelected();
}
function chainClosure(id) {
  const up = new Set([id]), down = new Set([id]);
  for (let changed = true; changed;) {
    changed = false;
    for (const item of flowEdges) {
      if (up.has(item.to) && !up.has(item.from)) { up.add(item.from); changed = true; }
      if (down.has(item.from) && !down.has(item.to)) { down.add(item.to); changed = true; }
    }
  }
  return new Set([...up, ...down]);
}
function markSelected() {
  const chain = state.selected ? chainClosure(state.selected) : new Set();
  const focus = state.focus && chain.size > 1;
  document.querySelectorAll('.flow-node').forEach(node => {
    const id = node.dataset.select, active = id === state.selected;
    node.setAttribute('aria-pressed', String(active));
    node.classList.toggle('is-linked', chain.has(id) && !active && focus);
    node.classList.toggle('is-dim', focus && !chain.has(id));
  });
  document.querySelectorAll('.flow-edge').forEach(path => {
    const on = chain.has(path.dataset.from) && chain.has(path.dataset.to);
    path.classList.toggle('is-on', focus && on); path.classList.toggle('is-dim', focus && !on);
  });
}
function selected() {
  markSelected();
  if (state.mode !== 'split' || detailSelected === state.selected) return;
  const step = stepById[state.selected];
  document.getElementById('detail-pane').innerHTML = step ? '<header class="selection ' + classification(step) + '"><span>' + h(rank[step.id]) + ' · ' + h(step.label) + '</span><h3>' + h(step.title) + '</h3></header>' + stepBody(step, true) : '<p>没有步骤。</p>';
  detailSelected = state.selected;
}
function mode(value) {
  state.mode = value;
  document.getElementById('document-view').hidden = value !== 'document';
  const visual = document.getElementById('visual-view');
  visual.hidden = value === 'document'; visual.className = 'mode-' + value; visual.dataset.pane = state.pane;
  document.querySelectorAll('[data-mode]').forEach(item => item.setAttribute('aria-pressed',String(item.dataset.mode === value)));
  if (value !== 'document') renderChain();
  selected();
  if (value === 'document' && state.selected) [...document.querySelectorAll('#document-view [data-step]')].find(item => item.dataset.step === state.selected)?.scrollIntoView({block:'center',behavior:'instant'});
}
const drawer = document.getElementById('drawer');
const back = document.getElementById('back-source');
function showDrawer() {
  if (drawer.open) return;
  drawerOpener = document.activeElement;
  drawer.showModal();
}
function openSource(ref, navigateBack=false) {
  const source = sources[ref]; if (!source) return;
  if (!navigateBack && drawer.open) {
    if (sourceCurrent && sourceCurrent !== ref) sourceHistory.push({kind:'source',id:sourceCurrent});
    else if (stepCurrent) sourceHistory.push({kind:'step',id:stepCurrent});
  }
  stepCurrent = undefined;
  sourceCurrent = ref;
  back.hidden = !sourceHistory.length;
  const fields = source.fields.map(item => '<section class="detail-section"><h3>' + h(item.label) + '</h3><p>' + h(item.text) + '</p></section>').join('');
  const links = source.links.map(item => '<p><a href="' + h(item.href) + '" target="_blank" rel="noopener noreferrer">' + h(item.label) + ' ↗</a></p>').join('');
  const related = source.related.filter(item => sources[item.ref]).map(item => '<p>' + h(item.label) + '：' + button(item.ref) + '</p>').join('');
  document.getElementById('drawer-body').innerHTML = '<p class="note">' + h(source.type_label) + '</p><h2>' + h(sourceTitle(ref)) + '</h2>' + fields + (source.evidence || []).map(item => '<h3>用于选择：' + h(item.decision_title) + '</h3>' + evidenceBody(item)).join('') + (source.changes || []).map(changeBody).join('') + links + related + '<footer class="technical-link"><a href="graph.json" target="_blank">技术记录（完整机器数据）</a></footer>';
  showDrawer(); drawer.scrollTop = 0;
}
function showStep(id, navigateBack=false) {
  const step = stepById[id]; if (!step) return;
  if (!navigateBack && drawer.open) {
    if (sourceCurrent) sourceHistory.push({kind:'source',id:sourceCurrent});
    else if (stepCurrent && stepCurrent !== id) sourceHistory.push({kind:'step',id:stepCurrent});
  }
  sourceCurrent = undefined; stepCurrent = id; back.hidden = !sourceHistory.length;
  document.getElementById('drawer-body').innerHTML = '<div class="drawer-step"><header class="selection ' + classification(step) + '"><span>' + h(rank[id]) + ' · ' + h(step.label) + '</span><h3>' + h(step.title) + '</h3></header>' + stepBody(step, true) + '</div>';
  showDrawer(); drawer.scrollTop = 0;
}
function special(name) {
  sourceCurrent = undefined; stepCurrent = undefined; sourceHistory.length = 0; back.hidden = true;
  const descriptions = {relations:'完整关系保留在机器结果中。关系的含义由原记录注明，阅读顺序不表示因果。', changes:'这里显示实际变化、受影响对象及需要重查的内容。', history:'组织版本及对应的记录范围保留在机器结果中。', audit:'追加日志保存原始采集内容和失败记录。', scope:'记录完整性只指已采集记录；未观测的宿主活动不在覆盖范围内。'};
  let body = '<p>' + h(descriptions[name]) + '</p>';
  if (name === 'changes') body += data.change_details.length ? '<p>以下为重查建议，不修改原判断或检查结果。</p>' + data.change_details.map(changeBody).join('') : '<p>未记录设计变化。</p>';
  if (name === 'scope') body += data.recording_gaps.map(item => '<p>' + h(item.text) + '</p>').join('');
  document.getElementById('drawer-body').innerHTML = '<h2>' + h({relations:'关系技术记录',changes:'变化与影响',history:'组织版本',audit:'原始日志',scope:'记录范围与缺口'}[name]) + '</h2>' + body + '<p><a href="' + (name === 'audit' ? 'events.jsonl' : 'graph.json') + '" target="_blank">打开完整技术文件</a></p>';
  showDrawer(); drawer.scrollTop = 0;
}
document.addEventListener('click',event => {
  const control = event.target.closest('[data-mode]'); if (control) { mode(control.dataset.mode); return; }
  const pane = event.target.closest('button[data-pane]'); if (pane) { state.pane = pane.dataset.pane; document.getElementById('visual-view').dataset.pane = state.pane; document.querySelectorAll('button[data-pane]').forEach(item => item.setAttribute('aria-pressed',String(item.dataset.pane === state.pane))); return; }
  const selection = event.target.closest('[data-select]'); if (selection) {
    if (!stepById[selection.dataset.select]) return;
    state.selected = selection.dataset.select; state.focus = !!selection.closest('.flow'); state.pane = 'detail'; detailSelected = undefined; selected();
    document.getElementById('visual-view').dataset.pane = 'detail';
    if (state.mode === 'map' || drawer.open) showStep(state.selected);
    else if (state.mode === 'document') [...document.querySelectorAll('#document-view [data-step]')].find(item => item.dataset.step === state.selected)?.scrollIntoView({block:'center',behavior:'instant'});
    return;
  }
  const ref = event.target.closest('[data-source]'); if (ref) { openSource(ref.dataset.source); return; }
  const tool = event.target.closest('[data-special]'); if (tool) { special(tool.dataset.special); return; }
  const step = event.target.closest('#document-view [data-step]'); if (step) state.selected = step.dataset.step;
});
document.addEventListener('toggle',event => {
  const detail = event.target; if (!detail.matches?.('details[data-expand]')) return;
  detail.open ? state.expanded.add(detail.dataset.expand) : state.expanded.delete(detail.dataset.expand);
  if (detail.open && !detail.firstElementChild.nextElementSibling.childElementCount) detail.firstElementChild.nextElementSibling.innerHTML = expandedContent(stepById[detail.dataset.expand], !!detail.closest('#detail-pane, .drawer-step'));
  document.querySelectorAll('details[data-expand]').forEach(other => { if (other !== detail && other.dataset.expand === detail.dataset.expand && other.open !== detail.open) other.open = detail.open; });
},true);
back.onclick = () => { const item = sourceHistory.pop(); if (item) item.kind === 'source' ? openSource(item.id,true) : showStep(item.id,true); };
document.getElementById('close-drawer').onclick = () => drawer.close();
drawer.addEventListener('close',() => { sourceCurrent = undefined; stepCurrent = undefined; sourceHistory.length = 0; back.hidden = true; if (drawerOpener?.isConnected) drawerOpener.focus(); });
document.getElementById('collapse').onclick = () => { const collapsed = document.body.classList.toggle('collapsed'); document.getElementById('collapse').setAttribute('aria-expanded',String(!collapsed)); };
const directory = document.getElementById('directory');
directory.onclick = () => { const open = document.body.classList.toggle('menu-open'); directory.setAttribute('aria-expanded',String(open)); };
document.querySelectorAll('#chapters a').forEach(item => item.onclick = () => { document.body.classList.remove('menu-open'); directory.setAttribute('aria-expanded','false'); });
document.addEventListener('keydown',event => { if (event.key === 'Escape' && document.body.classList.contains('menu-open')) { document.body.classList.remove('menu-open'); directory.setAttribute('aria-expanded','false'); directory.focus(); } });
const chapters = [...document.querySelectorAll('main > .chapter')];
function locate() {
  let current = 'goal';
  for (const chapter of chapters) if (chapter.getBoundingClientRect().top <= 105) current = chapter.id;
  document.getElementById('current').textContent = names[current];
  document.querySelectorAll('#chapters a').forEach(item => { const active = item.hash === '#' + current; item.classList.toggle('active',active); active ? item.setAttribute('aria-current','location') : item.removeAttribute('aria-current'); });
}
let ticking = false;
addEventListener('scroll',() => { if (!ticking) { ticking = true; requestAnimationFrame(() => { locate(); ticking = false; }); } },{passive:true});
renderDocument(); locate();
if (window.ResizeObserver) new ResizeObserver(() => { if (state.mode !== 'document') renderChain(); }).observe(document.getElementById('chain'));
