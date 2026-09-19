"""Human-readable projection of a saved process. Scientific organization stays upstream."""
from __future__ import annotations

import copy
from pathlib import Path

from evidence_trace.reader import check_status

LABELS = {"requirement": "用户要求", "choice": "设计选择", "program_result": "程序结果", "artifact": "产物"}


def record_title(record):
    if "event_type" in record:
        p = record["payload"]
        return p.get("stage") or p.get("text") or record["event_type"]
    return record.get("title") or record.get("text") or record.get("check") or record.get("path") or record.get("key", "记录")


def build_report(graph):
    records = graph["source_records"]
    process, plan = graph.get("design_process"), graph.get("report_plan") or {}
    state = graph["snapshot"]["organization_status"]
    # Stale organization remains available as history, but does not narrate newer facts.
    active = process if state == "current" else None
    steps = []
    if active:
        order = list(dict.fromkeys([key for section in plan.get("sections", []) for key in section["step_refs"]]
                                  + [key for stage in active["stages"] for key in stage["step_ids"]]
                                  + list(active["steps"])))
        for key in order:
            step = copy.deepcopy(active["steps"][key])
            refs = step["source_refs"]
            label = LABELS[step["kind"]]
            decision = next((records[r] for r in refs if records[r].get("kind") == "decision"), {})
            if step["kind"] == "choice":
                who = decision.get("decision_actor", "unknown")
                label = "AI 选择" if who in {"ai", "host-assistant", "assistant", "model"} else "用户选择" if who in {"user", "human", "researcher"} else "选择者未记录"
            # Title is authored or the full content; never an invented summary.
            step.update(id=key, label=label, title=step.get("title", step["content"]), authored=True)
            steps.append(step)
    else:
        for item in graph["reader"]["steps"]:
            refs = list(dict.fromkeys(item.get("record_refs", []) + item.get("event_refs", [])))
            steps.append({"id": item["id"], "kind": item["kind"], "label": item["label"],
                          "title": item["title"], "content": item.get("text", ""),
                          "source_refs": refs, "input_refs": [], "outcome_refs": [], "authored": False})
        shown = {r for s in steps for r in s["source_refs"]}
        for ref, record in records.items():
            if ref not in shown and record.get("event_type") in {"file_operation_completed", "file_operation_failed"}:
                p = record["payload"]
                steps.append({"id": "file-operation:" + ref, "kind": "program_result", "label": "程序结果",
                              "title": p["stage"], "content": "实际调用返回" if record["event_type"].endswith("completed") else "实际调用失败：" + p["error"],
                              "source_refs": [ref], "input_refs": [p["stage_ref"]] if p.get("stage_ref") else [],
                              "outcome_refs": [ref], "authored": False})
    checks = []
    artifacts = []
    for node in graph["nodes"]:
        if node["kind"] == "validation":
            checks.append({"ref": node["key"], "check": node["check"], "result": node.get("result"),
                           "scope": node.get("details"), "run_id": node.get("run_id"),
                           "status": "not_requested" if node.get("result") in ("not_requested", "N/A", "not_applicable") else check_status(node.get("result"))[0]})
        elif node["kind"] == "artifact":
            artifacts.append({"ref": node["key"], **{k: node.get(k) for k in
                ("path", "sha256", "role", "run_id", "result_event_ref", "generation_observation", "validated_by")}})
    reviews = [{"text": u["text"], "source_refs": u["source_refs"], "step_refs": u["step_refs"],
                "category": "authored_unresolved"} for u in active["unresolved"]] if active else []
    reviews.extend({"text": f.get("message", f.get("text", "")), "source_refs": f.get("refs", []),
                    "category": f["category"], "details": f} for f in graph["findings"] if f["category"] in {"review", "handoff"})
    context = plan.get("context") if active else None
    source_labels = {"requirement": "用户要求", "decision": "设计选择", "source": "原始来源",
                     "statement": "证据陈述", "claim": "任务判断", "validation": "程序检查", "artifact": "文件记录"}
    sources = {ref: {"title": str(record_title(value)), "label": source_labels.get(value.get("kind"),
                    value.get("payload", {}).get("stage", "原始记录")), "data": value} for ref, value in records.items()}
    stage_labels = {"inspect": "材料检查", "annotate_primers": "引物标注", "convert": "格式转换",
                    "export_delivery_bundle": "预览文件包", "goal_check": "目标检查", "sanity": "注释与序列检查"}
    for ref, record in records.items():
        if record.get("kind") == "artifact":
            p = Path(record["path"])
            sources[ref]["label"] = p.parent.parent.name + "/" + p.name
        elif record.get("payload", {}).get("stage"):
            payload = record["payload"]
            label = stage_labels.get(payload["stage"], payload["stage"])
            result = payload.get("result")
            if isinstance(result, dict) and isinstance(result.get("file_name"), str):
                label += " · " + result["file_name"]
            sources[ref]["label"] = label
    for step in steps:
        ref_set = set(step["source_refs"] + step.get("outcome_refs", []))
        step["checks"] = [c for c in checks if c["ref"] in ref_set]
        step["artifacts"] = [a for a in artifacts if a["ref"] in ref_set]
        step["program_records"] = [r for r in ref_set if records.get(r, {}).get("event_type") in {
            "stage_completed", "stage_failed", "file_operation_completed", "file_operation_failed"}]
        step["evidence"] = []
        # Preserve the already-derived evidence/applicability and later explanations for exactly referenced decisions.
        for old in graph["reader"]["steps"]:
            if ref_set.intersection(old.get("record_refs", [])):
                step["evidence"].extend(copy.deepcopy(old.get("branches", {}).get("evidence", [])))
                step.setdefault("recorded_explanations", []).extend(copy.deepcopy(old.get("branches", {}).get("supplements", [])))
    presented_artifacts = artifacts
    if graph.get("handoff"):
        selected_refs = {ref for item in graph["handoff"]["files"] for ref in item["artifact_refs"]}
        presented_artifacts = [a for a in artifacts if a["ref"] in selected_refs]
    return {"title": plan.get("title", "生物设计记录") if active else "生物设计记录",
            "context": context, "requirements": graph["task"]["requirements"],
            "snapshot": graph["snapshot"], "integrity": graph["integrity"],
            "steps": steps, "stages": active["stages"] if active else [],
            "sections": plan.get("sections", []) if active else [],
            "relations": active["relations"] if active else [],
            "paths": active["paths"] if active else [],
            "diagram": plan.get("diagram", {}) if active else {},
            "default_expanded_refs": plan.get("default_expanded_refs", []) if active else [],
            "checks": checks, "artifacts": presented_artifacts, "all_artifacts": artifacts, "review": reviews,
            "sources": sources, "coverage": graph["coverage"], "findings": graph["findings"],
            "handoff": graph.get("handoff"), "organization_history": graph["organization_history"],
            "historical_process": process if state == "stale" else None,
            "changes": graph.get("changes", []), "impacts": graph.get("impacts", []),
            "runs": graph["runs"], "fact_relations": graph["fact_relations"]}


def markdown(report):
    def safe(value):
        text = str(value or "")
        for char in ("\\", "`", "*", "_", "[", "]", "<", ">", "#", "|"):
            text = text.replace(char, "\\" + char)
        return text
    lines = ["# " + safe(report["title"]), "", "记录范围：截至事件 " + str(report["snapshot"]["through_sequence"]), ""]
    if report["snapshot"]["organization_status"] != "current":
        lines += ["设计过程尚未整理或组织已陈旧。以下为有限事实记录。", ""]
    lines += ["## 任务与要求", ""]
    if report["context"]:
        lines += [safe(report["context"]["text"]), ""]
    lines += [safe(r["text"]) + "\n" for r in report["requirements"]] or ["未记录任务要求。"]
    lines += ["", "## 设计形成过程", ""]
    for stage in report["stages"]:
        lines += [safe(stage["title"]) + "：" + safe(stage["purpose"]), ""]
        for branch in stage.get("branches", []):
            lines += ["分支：" + safe(branch["label"]) + "（" + ", ".join(safe(r) for r in branch["step_ids"]) + "）", ""]
    for i, step in enumerate(report["steps"], 1):
        lines += [f"### {i} · {step['label']}｜{safe(step['title'])}", ""]
        if step["content"] != step["title"]:
            lines += [safe(step["content"]), ""]
        if step.get("reason"):
            lines += [safe(step["reason"]["origin"]) + "：" + safe(step["reason"]["text"]), ""]
        lines += ["来源：" + ", ".join(safe(r) for r in step["source_refs"]), ""]
        for field, label in (("input_refs", "输入"), ("outcome_refs", "输出与检查对象")):
            if step.get(field):
                lines += [label + "：" + ", ".join(safe(r) for r in step[field]), ""]
        for e in step.get("evidence", []):
            lines += [safe(e.get("label", e.get("relation"))) + "：" + safe(e.get("statement")),
                      "当前判断：" + safe(e.get("claim")), safe(e.get("assessment", {}).get("reason")), ""]
        for e in step.get("recorded_explanations", []):
            lines += ["事后补充：" + safe(e.get("text")), ""]
        for c in step["checks"]:
            lines += [safe(c["check"]) + "：" + safe(c["result"]), ""]
        for item in step.get("limitations", []):
            lines += ["限制：" + safe(item["text"]), ""]
    lines += ["## 交付文件与检查", ""]
    for a in report["artifacts"]:
        lines += [safe(a["role"]) + "：" + safe(a["path"]) + "（" + safe(a["ref"]) + "）", ""]
    if not report["artifacts"]:
        lines += ["未记录产物。", ""]
    lines += [safe(c["check"]) + "：" + safe(c["result"]) + "（" + safe(c["ref"]) + "）\n" for c in report["checks"]]
    if report["review"]:
        lines += ["## 需要处理", ""] + [safe(r["text"]) + "\n" for r in report["review"]]
    if report.get("handoff"):
        lines += ["交付清单核对：", ""] + [safe(f["status"]) + "：" + safe(f["path"]) + "\n" for f in report["handoff"]["files"]]
    lines += ["## 查看详细记录", "", "完整原记录、条件、关系和历史见同目录 graph.json。", ""]
    for ref, source in report["sources"].items():
        lines += ["### " + safe(ref), "", safe(source["title"]), ""]
    return "\n".join(lines)
