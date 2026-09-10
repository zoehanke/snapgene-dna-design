"""Deterministic offline renderer. Layout comes from shipped code, never host data."""
import json
import pathlib

from evidence_trace import __version__
from evidence_trace.chain import build_chains


def render(directory, graph):
    directory = pathlib.Path(directory)
    graph = build_chains(graph)
    payload = json.dumps(graph, ensure_ascii=False, indent=2)
    (directory / "graph.json").write_text(payload, encoding="utf-8")
    manifest = {"schema_version": graph["schema_version"], "trace_version": __version__,
                "projection_version": graph["projection_version"], "integrity": graph["integrity"],
                "issues": graph["issues"], "coverage": graph["coverage"],
                "runs": [r["id"] for r in graph["runs"]],
                "artifacts": [{k: n.get(k) for k in ("path", "sha256", "run_id", "role")}
                              for n in graph["nodes"] if n["kind"] == "artifact"],
                "derived_files": ["graph.json", "index.html"]}
    (directory / "TRACE-MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    assets = pathlib.Path(__file__).parent
    document = PAGE.replace("__STYLE__", (assets / "view.css").read_text(encoding="utf-8"))
    document = document.replace("__SCRIPT__", (assets / "view.js").read_text(encoding="utf-8"))
    # Host text cannot break out of this inert JSON element.
    document = document.replace("__TRACE_DATA__", payload.replace("<", "\\u003c").replace("&", "\\u0026"))
    (directory / "index.html").write_text(document, encoding="utf-8")
    return graph


PAGE = '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Evidence Chain · 设计依据</title>
<style>__STYLE__</style></head><body>
<header><strong>Evidence Trace <small>0.2</small></strong><nav aria-label="视图">
<button data-view="chain" aria-selected="true">Evidence Chain</button><button data-view="review">Review Queue</button>
<button data-view="artifacts">Artifacts</button><button data-view="graph">Advanced Graph</button></nav></header>
<div class="intro"><div><p class="eyebrow">DNA DESIGN / SCIENTIFIC DECISIONS</p><h1>Design Evidence Chain</h1><p>先看设计主干，再展开证据条件与记录缺口。</p></div>
<div class="controls"><select id="run" aria-label="选择运行"></select><input id="search" type="search" aria-label="搜索决定" placeholder="搜索决定或实际选择…"></div></div>
<section class="stats" aria-label="三个独立状态"><div><span>Trace Integrity</span><strong id="integrity"></strong><small>记录完整性，不代表安全</small></div>
<div><span>Decision Coverage</span><strong id="coverage"></strong><small>实际输入的记录覆盖，不是安全分数</small></div>
<div><span>Evidence Applicability</span><strong id="applicability"></strong><small>上下文比较，不验证 Claim</small></div></section>
<main><section class="canvas"><div class="canvas-head"><h2 id="view-title">Main Chain</h2><label><input type="checkbox" id="focus" checked> Focus Mode</label></div>
<div id="decision-picker"></div><div id="content"></div></section>
<aside><section id="detail" class="panel" aria-live="polite"><h2>Decision Details</h2><p>选择记录查看依据。</p></section><section class="panel"><h2>Review Queue</h2><div id="queue"></div></section></aside></main>
<footer>主干表示阅读顺序。Validation / Artifact 为运行级关联，不表示程序证明了相邻 Claim。来源核验、上下文匹配与适用性分别展示。页面离线运行。</footer>
<script id="trace-data" type="application/json">__TRACE_DATA__</script><script>__SCRIPT__</script></body></html>'''
