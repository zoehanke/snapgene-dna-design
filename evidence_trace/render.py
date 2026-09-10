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
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Living Evidence Document</title>
<style>__STYLE__</style></head><body>
<header class="mast"><a class="brand" href="#" aria-label="Evidence Trace"><span class="mark">ET</span> Evidence Trace <small>0.3</small></a>
<div class="mode-switch" role="tablist" aria-label="阅读模式"><button data-mode="document" role="tab">Document</button><button data-mode="map" role="tab">Mind Map</button><button data-mode="split" role="tab">Split</button></div>
<select id="run" aria-label="运行版本"></select></header>
<div class="workspace"><aside class="outline"><div class="outline-head">CONTENTS <span id="chapter-count"></span></div><input id="search" type="search" placeholder="查找决定…" aria-label="查找决定"><nav id="chapters" aria-label="Decision 目录"></nav>
<div class="outline-head secondary">WORKSPACE</div><nav class="tools" aria-label="辅助阅读"><button data-panel="review">Review Queue</button><button data-panel="changes">Changes</button><button data-panel="artifacts">Artifact Trace</button><details><summary>Advanced</summary><button data-panel="graph">Advanced Graph</button><button data-panel="audit">Audit Log</button></details></nav>
<div class="outline-foot">Living Evidence Document<br><span>记录、依据与重新检查的线索。</span></div></aside>
<main><div class="reading-head"><div><p class="eyebrow" id="eyebrow">RESEARCH RECORD</p><h1 id="page-title">设计依据</h1></div><p id="status-line" aria-live="polite"></p></div>
<div id="reading" class="reading"><section id="map-pane" class="map-pane" aria-label="Decision 思维导图"></section><section id="document-pane" class="document-pane" aria-label="科研证据文档"></section></div>
<footer class="reading-foot">STALE 表示旧上下文；影响标记不修改科学结论或原始程序检查。RERUN 仅为建议。</footer></main></div>
<dialog id="drawer" aria-label="记录详情"><button id="close-drawer" aria-label="关闭详情">×</button><div id="drawer-body"></div></dialog>
<script id="trace-data" type="application/json">__TRACE_DATA__</script><script>__SCRIPT__</script></body></html>'''
