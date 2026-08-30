# -*- coding: utf-8 -*-
"""planning/manual_render.py - JSON plan -> human-readable build manual."""
import html
import json


def render_html(plan):
    """Minimal dependency-free HTML build manual.

    The HTML is generated from the same plan object as Markdown, so content
    consistency is structural: headings, fragment table, primer table,
    feasibility items and steps are all rendered from the plan fields.
    """
    esc = html.escape
    rows = []
    for item in plan.get("fragment_assignments", []):
        rows.append("<tr><td>%s</td><td>%s</td><td>%s</td>"
                    "<td>%d</td><td>%s</td></tr>" % (
                        esc(item["name"]), esc(item["role"]),
                        esc(str(item["source_path"])), item["length"],
                        esc(str(item["source_interval_0based"]))))
    fragment_table = ("<table><tr><th>name</th><th>role</th><th>source</th>"
                      "<th>length</th><th>interval</th></tr>%s</table>"
                      % "".join(rows))
    primer_rows = []
    for item in plan.get("primers", []):
        if "error" in item:
            primer_rows.append("<tr><td>%s</td><td colspan='4'>%s</td></tr>"
                               % (esc(item["fragment"]),
                                  esc(item["error"])))
            continue
        fwd = item.get("forward", {})
        rev = item.get("reverse", {})
        primer_rows.append(
            "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
            % (esc(item["fragment"]), esc(fwd.get("name") or "-"),
               esc(fwd.get("sequence") or "-"), esc(str(fwd.get("tm") or "-")),
               esc(str(fwd.get("gc") or "-"))))
        primer_rows.append(
            "<tr><td></td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
            % (esc(rev.get("name") or "-"),
               esc(rev.get("sequence") or "-"), esc(str(rev.get("tm") or "-")),
               esc(str(rev.get("gc") or "-"))))
    primer_table = ("<table><tr><th>fragment</th><th>primer</th>"
                    "<th>sequence</th><th>Tm</th><th>GC%%</th></tr>%s</table>"
                    % "".join(primer_rows))
    feas = plan.get("feasibility", {})
    feas_rows = []
    for kind in ("errors", "warnings"):
        for hit in feas.get(kind, []):
            feas_rows.append("<li>[%s] %s: %s (%s)</li>" % (
                esc(hit["severity"]), esc(hit["rule_id"]),
                esc(hit["suggestion"]), esc(hit["source"])))
    steps = plan.get("steps") or _default_steps(plan)
    steps_html = "".join("<li>%s</li>" % esc(step) for step in steps)
    pending = plan.get("consent", {}).get("pending", [])
    pending_html = "".join(
        "<li>%s (%s): %s</li>" % (esc(item.get("operation", "-")),
                                  esc(item.get("category", "-")),
                                  esc(item.get("description", "-")))
        for item in pending)
    strategy = plan.get("assembly_strategy", {})
    return """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>%s</title>
<style>
body{font-family:-apple-system,Segoe UI,Arial,sans-serif;margin:2rem;color:#222}
table{border-collapse:collapse;margin:1rem 0}th,td{border:1px solid #ccc;padding:.35rem .6rem;font-size:.9rem}
th{background:#f4f4f4}li{margin:.2rem 0}.grade{font-weight:700}
</style></head><body>
<h1>%s</h1><p>goal: %s</p><p>status: %s · method: %s · grade: <span class="grade">%s</span></p>
<h2>片段分配</h2>%s
<h2>引物</h2>%s
<h2>可行性</h2><ul>%s</ul>
<h2>待确认</h2><ul>%s</ul>
<h2>步骤</h2><ol>%s</ol>
</body></html>""" % (
        esc(plan.get("construct_name", "assembly-plan")),
        esc(plan.get("construct_name", "assembly-plan")),
        esc(plan.get("goal", "")), esc(plan.get("status", "")),
        esc(strategy.get("method", "-")), esc(feas.get("grade", "-")),
        fragment_table, primer_table, "".join(feas_rows), pending_html,
        steps_html)


def render_markdown(plan):
    lines = ["# %s 构建手册" % plan.get("construct_name", "assembled-construct"),
             "", "goal: %s" % plan.get("goal", ""),
             "status: %s" % plan.get("status", "unknown"),
             "topology: %s" % plan.get("topology", "circular"), ""]
    strategy = plan.get("assembly_strategy", {})
    lines += ["## 组装策略", "",
              "- method: %s" % strategy.get("method"),
              "- requested: %s" % strategy.get("requested_method"),
              "- reason: %s" % strategy.get("reason", ""),
              "- enzymes: %s" % (", ".join(strategy.get("enzymes") or []) or "-"),
              ""]
    if strategy.get("overlap_junctions"):
        lines.append("### overlap junctions")
        for item in strategy["overlap_junctions"]:
            lines.append("- %s <- %d bp (GC %.1f%%, Tm %s) %s" % (
                " | ".join(item["between"]), item["length"],
                item.get("gc_percent") or 0.0, item.get("tm"),
                "; ".join(item.get("problems") or [])))
        lines.append("")
    if strategy.get("alternatives"):
        lines.append("### alternatives")
        for item in strategy["alternatives"]:
            lines.append("- %s: %s" % (item["method"], item["reason"]))
        lines.append("")

    lines += ["## 片段分配表", ""]
    for item in plan.get("fragment_assignments", []):
        lines.append("- %s (%s): source[%d] %s, 0-based [%s,%s), 1-based [%s,%s], %d bp"
                     % (item["name"], item["role"], item["source_index"],
                        item["source_path"], item["source_interval_0based"][0],
                        item["source_interval_0based"][1],
                        item["source_interval_1based"][0],
                        item["source_interval_1based"][1], item["length"]))
    lines.append("")

    lines += ["## 引物清单", ""]
    for item in plan.get("primers", []):
        if "error" in item:
            lines.append("- %s: ERROR %s" % (item.get("fragment"), item["error"]))
            continue
        for side in ("forward", "reverse"):
            primer = item.get(side)
            lines.append("- %s: %s (Tm %s C, GC %s%%, tail=%s)" % (
                primer.get("name"), primer.get("sequence") or "N/A",
                primer.get("tm"), primer.get("gc"),
                primer.get("tail") or "无"))
        lines.append("  backend=%s" % item.get("backend"))
    lines.append("")

    feas = plan.get("feasibility", {})
    lines += ["## 可行性", "",
              "- grade: %s" % feas.get("grade", "unknown")]
    for kind in ("errors", "warnings"):
        for hit in feas.get(kind, []):
            lines.append("- [%s] %s: %s (%s)" % (
                hit["severity"], hit["rule_id"], hit["suggestion"],
                hit["source"]))
    lines.append("")

    pending = plan.get("consent", {}).get("pending", [])
    lines += ["## 待确认", ""]
    if pending:
        for item in pending:
            lines.append("- [%s] %s：%s" % (
                item.get("category"), item.get("operation"),
                item.get("description")))
    else:
        lines.append("- 无待确认项（本次自动确认决策已记录在 operation_log）")
    lines.append("")

    lines += ["## 逐步操作", ""]
    steps = plan.get("steps") or _default_steps(plan)
    for index, step in enumerate(steps, 1):
        lines.append("Step %d. %s" % (index, step))
    lines.append("")

    frame = plan.get("fusion_frame_check", {})
    if frame.get("checked"):
        lines.append("fusion frame check: %s (offset mod3=%s)" % (
            "in-frame" if frame.get("in_frame") else "OUT OF FRAME",
            frame.get("frame_offset_mod3")))
    lines.append("")
    return "\n".join(lines) + "\n"


def _default_steps(plan):
    fragments = plan.get("fragment_assignments", [])
    method = plan.get("assembly_strategy", {}).get("method")
    steps = ["解析 %d 个来源质粒并确认片段区间" % len(plan.get("sources", []))]
    for item in fragments:
        primer_names = [p for p in plan.get("primers", [])
                        if p.get("fragment") == item["name"] and "error" not in p]
        if primer_names:
            steps.append("PCR 扩增 %s（模板 %s，引物见引物清单）" % (
                item["name"], item["source_path"]))
    if method in ("overlap", "gibson"):
        steps.append("按 overlap junction 做 overlap/Gibson 组装")
    elif method == "golden_gate":
        steps.append("Golden Gate 酶切连接（酶：%s）" % ", ".join(
            plan.get("assembly_strategy", {}).get("enzymes") or ["BsaI"]))
    elif method == "digest-ligate":
        steps.append("限制酶切 + T4 连接")
    steps.append("转化感受态大肠杆菌并涂抗性板")
    steps.append("挑克隆、菌落 PCR / 测序验证 junction")
    return steps
