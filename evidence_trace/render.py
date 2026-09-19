"""Deterministic offline renderer. Layout comes from shipped code, never host data."""
import json
import pathlib

from evidence_trace import __version__
from evidence_trace.process import assemble
from evidence_trace.report import build_report, markdown


def render(directory, graph, formats="both"):
    directory = pathlib.Path(directory)
    if formats not in {"html", "markdown", "both"}:
        raise ValueError("Unknown report format")
    if graph.get("schema_version") != "design-process-v1":
        graph = assemble(graph.get("audit_events", []), graph.get("issues", []))
    graph["report"] = build_report(graph)
    graph["report"]["available_formats"] = ["html", "markdown"] if formats == "both" else [formats]
    payload = json.dumps(graph, ensure_ascii=False, indent=2)
    (directory / "graph.json").write_text(payload, encoding="utf-8")
    manifest = {"schema_version": graph["schema_version"], "trace_version": __version__,
                "projection_version": graph["projection_version"], "integrity": graph["integrity"],
                "issues": graph["issues"], "coverage": graph["coverage"],
                "runs": [r["id"] for r in graph["runs"]],
                "artifacts": [{k: n.get(k) for k in ("path", "sha256", "run_id", "role")}
                              for n in graph["nodes"] if n["kind"] == "artifact"],
                "snapshot": graph["snapshot"],
                "derived_files": ["graph.json"] + (["index.html"] if formats in {"html", "both"} else [])
                                 + (["report.md"] if formats in {"markdown", "both"} else [])}
    (directory / "TRACE-MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    assets = pathlib.Path(__file__).parent
    document = PAGE.replace("__STYLE__", (assets / "view.css").read_text(encoding="utf-8"))
    document = document.replace("__SCRIPT__", (assets / "view.js").read_text(encoding="utf-8"))
    # Host text cannot break out of this inert JSON element.
    document = document.replace("__TRACE_DATA__", payload.replace("<", "\\u003c").replace("&", "\\u0026"))
    if formats in {"html", "both"}:
        (directory / "index.html").write_text(document, encoding="utf-8")
    if formats in {"markdown", "both"}:
        (directory / "report.md").write_text(markdown(graph["report"]), encoding="utf-8")
    return graph


PAGE = '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Living Evidence Document</title>
<style>__STYLE__</style></head><body>
<aside class="sidebar"><header><strong>Evidence Trace</strong><p>生物设计记录</p></header>
<button id="collapse" aria-label="折叠目录" aria-expanded="true">‹</button><nav id="chapters" aria-label="报告章节"></nav>
<footer>记录范围与来源可回查</footer></aside>
<div class="mobile-nav"><button id="directory" aria-expanded="false" aria-controls="chapters"><span id="current">任务与要求</span><span>目录 ▾</span></button></div>
<main id="report"></main>
<dialog id="drawer" aria-label="来源与详细记录"><button id="close-drawer" aria-label="关闭详情">×</button><div id="drawer-body"></div></dialog>
<script id="trace-data" type="application/json">__TRACE_DATA__</script><script>__SCRIPT__</script></body></html>'''
