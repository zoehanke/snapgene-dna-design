"""One deterministic reading projection. No new events, DNA operations or model calls."""
from __future__ import annotations

import copy
from pathlib import PurePosixPath

from evidence_trace.applicability import assess
from evidence_trace.provenance import decision_provenance, requirement_provenance

VERSION = "reader-v0.3.1"
NOT_REQUESTED = ("not_requested", "not_applicable", "N/A")
CHECK_NAMES = {"artifact_valid": "产物文件检查", "computation_valid": "构建计算检查",
               "goal_valid": "任务目标检查", "biological_sanity": "序列与注释规则检查",
               "requested_components": "指定元件检查"}
RELATION_NAMES = {"support": "支持", "oppose": "反对", "constrain": "限制", "contextualize": "背景"}
INPUT_NAMES = {"source": "来源", "boundary": "边界", "method": "构建方法", "component": "元件",
               "mutation": "变更位点", "orientation": "方向", "topology": "拓扑", "order": "顺序",
               "context": "背景条件", "stop_policy": "终止位置", "parameter": "制备参数"}


def check_status(value):
    if value is True or value in ("PASS", "passed", "verified"):
        return "passed", "通过"
    if value is False or value in ("FAIL", "failed"):
        return "failed", "未通过"
    return "unknown", "结果待确认"


def file_inputs(value):
    """Read existing file snapshots only; a matching path alone cannot identify a version."""
    if isinstance(value, dict):
        if value.get("source_path"):
            yield value["source_path"], value.get("source_sha256")
        for child in value.values():
            yield from file_inputs(child)
    elif isinstance(value, list):
        for child in value:
            yield from file_inputs(child)


def build_reader(graph):
    """Consume projected facts plus existing chain/impact assessments; return detached data."""
    nodes = {n["key"]: n for n in graph["nodes"]}
    events = {e["event_id"]: e for e in graph.get("audit_events", [])}
    runs = graph["runs"]
    chains = {v["run_id"]: v for v in graph.get("chain_views", [])}
    steps, ref_steps, order, relations, reviews = {}, {}, {}, [], {}
    memberships = {r["id"]: set() for r in runs}
    basis_event_refs = {ref for n in nodes.values() for ref in n.get("basis_refs", []) if ref in events}
    scopes = list(runs)
    orphan_ids = {n.get("run_id") for n in nodes.values() if n["kind"] in {"validation", "artifact"}
                  and n.get("run_id") not in memberships}
    orphan_ids.update(e.get("run_id") for e in events.values() if e["event_id"] in basis_event_refs
                      and e.get("run_id") not in memberships)
    for rid in sorted(orphan_ids, key=str):
        stages = [{**e["payload"], "event_type": e["event_type"], "event_id": e["event_id"],
                   "recorded_sequence": e["sequence"]} for e in events.values()
                  if e.get("run_id") == rid and e["event_type"] in {"stage_started", "stage_completed", "stage_failed"}]
        scopes.append({"id": rid, "stages": stages})

    def add(key, kind, label, title, record_refs=(), event_refs=(), run_ids=(), sequence=0, **extra):
        item = {"id": key, "kind": kind, "label": label, "title": title,
                "record_refs": list(record_refs), "event_refs": list(event_refs),
                "run_ids": [rid for rid in run_ids if rid in memberships], **extra}
        steps[key] = item
        order[key] = sequence
        for ref in [*record_refs, *event_refs]:
            ref_steps.setdefault(ref, key)
        for run_id in item["run_ids"]:
            memberships[run_id].add(key)
        return item

    def link(source, target, kind, refs, run_id=None, scope="recorded"):
        if source and target and source != target:
            edge = {"from": source, "to": target, "kind": kind, "refs": list(refs), "scope": scope, "run_id": run_id}
            if edge not in relations:
                relations.append(edge)

    def review(step_id, category, message, refs, run_ids, action):
        identity = (step_id, category, message, tuple(refs))
        if identity not in reviews:
            reviews[identity] = {"step_id": step_id, "category": category, "message": message,
                                 "action": action, "refs": [], "run_ids": []}
        item = reviews[identity]
        for field, values in (("refs", refs), ("run_ids", [rid for rid in run_ids if rid in memberships])):
            item[field] = list(dict.fromkeys([*item[field], *values]))

    # Declarations occur once in the whole history, even when reused by several runs.
    for n in nodes.values():
        if n["kind"] not in {"requirement", "decision"}:
            continue
        active_runs = [r["id"] for r in runs if n["key"] in r.get(
            "decision_refs" if n["kind"] == "decision" else "context_refs", [])]
        if n["kind"] == "requirement":
            provenance = requirement_provenance(n)
            action = provenance["request_action"]
            known_user = provenance["origin"] == "supplied_user_source"
            kind = "choice" if action in {"confirm", "reject"} else "requirement"
            label = "用户要求" if kind == "requirement" else "用户选择" if known_user else "选择者未记录"
            provenance["label"] = "用户提供的来源" if known_user else "原始来源未记录"
            add("record:" + n["key"], kind, label, n["text"], [n["key"]], run_ids=active_runs,
                sequence=n.get("recorded_sequence", 0), source=provenance, action=action, phase="declared")
        else:
            provenance = decision_provenance(n)
            label = {"user": "用户选择", "ai": "AI 选择"}.get(provenance["decision_actor"], "选择者未记录")
            branches = {}
            if provenance["rationale"]:
                branches["reason"] = {"text": provenance["rationale"], "label": provenance["explanation_label"],
                                      "record_refs": [n["key"]]}
            if n.get("limitations"):
                branches["limitations"] = n["limitations"]
            add("record:" + n["key"], "choice", label, n["text"], [n["key"]], run_ids=active_runs,
                sequence=n.get("recorded_sequence", 0), source={"actor": provenance["decision_actor"],
                "reference": provenance["decision_source"], "explanation_label": provenance["explanation_label"]},
                phase="declared", **({"branches": branches} if branches else {}))

    # Evidence remains conditional on its original Claim and on run-time availability.
    for n in nodes.values():
        if n["kind"] != "decision":
            continue
        step = steps[ref_steps[n["key"]]]
        evidence = []
        claim_refs = n.get("references", {}).get("claim_ids", [])
        for claim_ref in claim_refs:
            claim = nodes.get(claim_ref, {})
            edges = [e for e in graph["edges"] if e["to"] == claim_ref and "statement_id" in e]
            for edge in edges:
                statement = nodes.get(edge["from"], {})
                available = [r["id"] for r in runs if any(
                    c["decision"] == n["key"] and any(b["link"]["id"] == edge["id"] for b in c["evidence"])
                    for c in chains.get(r["id"], {}).get("chains", []))]
                entry = {"id": edge["id"], "relation": edge.get("relation", "unknown"),
                         "label": RELATION_NAMES.get(edge.get("relation"), "关系未确认"),
                         "statement": statement.get("text", ""), "claim": claim.get("text", ""),
                         "aspect": edge.get("aspect", ""), "run_ids": available,
                         "record_refs": [edge["from"], claim_ref, *statement.get("references", {}).get("source_id", [])],
                         "assessment": assess(statement.get("context", {}), claim.get("context", {}), edge.get("required_dimensions")),
                         "sources": [{"ref": k, "title": nodes[k].get("title", "来源"),
                                      "verification_status": nodes[k].get("verification_status", "unverified")}
                                     for k in statement.get("references", {}).get("source_id", []) if k in nodes]}
                for field in ("conditions", "limitations", "strength", "applicability"):
                    if edge.get(field):
                        entry[field] = edge[field]
                evidence.append(entry)
                if edge.get("relation") == "oppose":
                    review(step["id"], "evidence_conflict", "这个选择引用了反对当前判断的依据，需复核其适用方面。",
                           [edge["id"], *entry["record_refs"]], available, "比较具体陈述、条件和所支持的判断。")
            # Missing evidence at a past run is not repaired by a later link.
            missing_at = [r["id"] for r in runs if n["key"] in r.get("decision_refs", []) and not any(
                c["decision"] == n["key"] and any(b["claim"] == claim_ref for b in c["evidence"])
                for c in chains.get(r["id"], {}).get("chains", []))]
            direct_basis = claim.get("basis_refs") or any(claim.get("references", {}).get(f) for f in ("responds_to", "validated_by", "source_id"))
            if not direct_basis and (missing_at or (not runs and not edges)):
                review(step["id"], "missing_evidence", "这个选择引用的判断缺少当时已记录的依据。",
                       [claim_ref], missing_at, "核对该判断的依据或明确其仍是待验证判断。")
        if evidence:
            step.setdefault("branches", {})["evidence"] = evidence
        supplements = []
        for explanation in graph.get("explanations", []):
            if explanation["decision_ref"] == n["key"]:
                supplements.append({**explanation, "run_ids": [r["id"] for r in runs
                    if n["key"] in r.get("decision_refs", []) and explanation["recorded_sequence"] <= r.get("event_count_at_start", 0)]})
        if supplements:
            step.setdefault("branches", {})["supplements"] = supplements

    for run in scopes:
        rid = run["id"]
        view = chains.get(rid, {})
        observations = [o for o in view.get("choices", []) if o["target_match"] != "matched"]
        # Unattributed inputs are program facts, including partially documented runs.
        if observations:
            input_groups = {}
            for observation in observations:
                input_groups.setdefault(observation.get("stage_ref") or "legacy", []).append(observation)
            for stage_ref, choices in input_groups.items():
                refs = list(dict.fromkeys(o["observation_event_ref"] for o in choices if o.get("observation_event_ref")))
                start = events.get(stage_ref)
                anchor = start["sequence"] if start else events.get(run.get("started_event_ref"), {}).get("sequence", 0)
                if start:
                    refs.append(stage_ref)
                categories = list(dict.fromkeys(INPUT_NAMES.get(o["choice_kind"], "设计参数") for o in choices))
                add("inputs:" + rid + ":" + stage_ref, "program", "程序结果", "接收构建设计输入", event_refs=refs,
                    run_ids=[rid], sequence=anchor, summary="已记录" + "、".join(categories) + "输入。",
                    phase="submitted_inputs", order_basis="stage_reference" if start else "run_start_summary",
                    details={"observations": choices})

        validations = [n for n in nodes.values() if n["kind"] == "validation" and n.get("run_id") == rid]
        groups = {}
        for n in validations:
            groups.setdefault(n.get("result_event_ref") or n["key"], []).append(n)
        for result_ref, group in groups.items():
            visible = [n for n in group if n.get("result") not in NOT_REQUESTED]
            if not visible:
                continue
            checks = []
            for n in visible:
                status, label = check_status(n.get("result"))
                checks.append({"record_ref": n["key"], "name": CHECK_NAMES.get(n.get("check"), "程序检查"),
                               "status": status, "result": n.get("result"), "summary": label})
            event = events.get(result_ref, {})
            step = add("checks:" + result_ref, "program", "程序结果", "检查本次构建结果",
                       [n["key"] for n in group], [result_ref] if event else [], [rid],
                       event.get("sequence", min(n.get("recorded_sequence", 0) for n in group)),
                       checks=checks, phase="returned_value" if event else "unknown",
                       association_scope="same_run" if rid in memberships else "unscoped",
                       summary="；".join(c["name"] + c["summary"] for c in checks))
            for check in checks:
                if check["status"] != "passed":
                    review(step["id"], "program_check", check["name"] + check["summary"], [check["record_ref"]],
                           [rid], "打开这项实际检查，处理失败或确认检查结果。")

        for stage in run.get("stages", []):
            event_id = stage.get("event_id")
            if not event_id or event_id in ref_steps:
                continue
            failed = stage["event_type"] == "stage_failed"
            consequential = stage.get("stage") in {"execute", "recipe_execute"}
            referenced = event_id in basis_event_refs
            if not failed and not (stage["event_type"] == "stage_completed" and (consequential or referenced)) and not referenced:
                continue
            if event_id in groups:  # Not-requested checks stay in detailed records.
                continue
            title = "程序执行未完成" if failed else "返回构建计算结果" if consequential else "记录被引用的程序结果"
            phase = "failed" if failed else stage.get("observation_phase", "unknown")
            if stage["event_type"] == "stage_started":
                title, phase = "提交被引用的程序输入", "submitted_inputs"
            step = add("event:" + event_id, "program", "程序结果", title, event_refs=[event_id], run_ids=[rid],
                       sequence=stage.get("recorded_sequence", 0), phase=phase,
                       **({"summary": stage["error"]} if failed and stage.get("error") else {}))
            if failed:
                review(step["id"], "execution_failure", "这一步没有完成执行。", [event_id], [rid], "查看程序错误并处理本次未完成的步骤。")

    # Group only representations with the same run, role, file stem and production event.
    files = [n for n in nodes.values() if n["kind"] == "artifact"]
    consumed, material_refs, material_gaps = set(), [], []
    for event in events.values():
        if event["event_type"] != "stage_started":
            continue
        for path, digest in file_inputs(event["payload"].get("input", {})):
            matches = [n for n in files if n.get("path") == path and digest and n.get("sha256", "").lower() == digest.lower()
                       and n.get("recorded_sequence", 0) < event["sequence"]]
            if len(matches) == 1:
                consumed.add(matches[0]["key"])
                material_refs.append((matches[0]["key"], event["event_id"], event.get("run_id")))
            elif len(matches) > 1:
                material_gaps.append({"event_ref": event["event_id"], "run_id": event.get("run_id"),
                                      "record_refs": [n["key"] for n in matches],
                                      "reason": "路径和内容对应多条产物记录，未猜测生成版本。"})
    declared_records = {ref for n in nodes.values() for ref in n.get("basis_refs", []) if ref in nodes}
    formal_runs = {n.get("run_id") for n in files if n.get("role") == "authoritative"}
    file_groups = {}
    for n in files:
        path = PurePosixPath(n.get("relative_path", n.get("path", "")).replace("\\", "/"))
        if path.name == "DELIVERY-MANIFEST.json":
            continue
        candidate_result = n.get("run_id") not in formal_runs and str(path).startswith("candidate/")
        if n.get("role") != "authoritative" and n["key"] not in consumed | declared_records and not candidate_result:
            continue
        key = (n["run_id"], n.get("role"), str(path.parent), path.stem, n.get("result_event_ref") or n["key"])
        file_groups.setdefault(key, []).append(n)
    generations = {}
    for (rid, role, parent, stem, result_ref), group in file_groups.items():
        number = next((i + 1 for i, r in enumerate(runs) if r["id"] == rid), None)
        run_label = f"第 {number} 次运行" if number is not None else "运行未记录"
        label = "最终产物" if role == "authoritative" else "中间产物"
        generation_key = (rid, role, stem)
        generations[generation_key] = generations.get(generation_key, 0) + 1
        generation = generations[generation_key]
        repeated_name = sum(k[0] == rid and k[1] == role and k[3] == stem for k in file_groups) > 1
        name_detail = f"，产物记录 {generation}" if repeated_name else ""
        event = events.get(result_ref, {})
        producer = ref_steps.get(result_ref)
        if producer and steps[producer]["kind"] != "program":
            producer = None
        step = add("artifact:" + group[0]["key"], "artifact", label, f"{stem}（{run_label}{name_detail}）",
                   [n["key"] for n in group], [result_ref] if event else [], run_ids=[rid], sequence=min(n.get("recorded_sequence", 0) for n in group),
                   role=role, delivery_state="authoritative" if role == "authoritative" else "not_authoritative",
                   files=[{"record_ref": n["key"], "name": PurePosixPath(n.get("path", "").replace("\\", "/")).name,
                                     "path": n.get("path")} for n in group])
        link(producer, step["id"], "produced", [result_ref, *step["record_refs"]], rid)

    # Only supported relationships get edges; no synthetic arrows between adjacent steps.
    for n in nodes.values():
        target = ref_steps.get(n["key"])
        if not target:
            continue
        if n.get("previous"):
            link(ref_steps.get(n["previous"]), target, "revision", [n["previous"], n["key"]])
        for ref in n.get("references", {}).get("responds_to", []):
            link(ref_steps.get(ref), target, "responds_to", [ref, n["key"]], scope="declared")
        for ref in n.get("basis_refs", []):
            link(ref_steps.get(ref), target, "declared_basis", [ref, n["key"]], scope="declared")
        if n["kind"] in {"requirement", "decision"}:
            basis = [*n.get("basis_refs", []), *n.get("references", {}).get("responds_to", []),
                     *n.get("references", {}).get("claim_ids", [])]
            if basis:
                steps[target].setdefault("branches", {})["basis_refs"] = list(dict.fromkeys(basis))
    for record_ref, start_ref, rid in material_refs:
        # A submitted material reference does not establish that it was incorporated.
        targets = [ref_steps[s["event_id"]] for r in runs if r["id"] == rid for s in r["stages"]
                   if s.get("stage_ref") == start_ref and s.get("event_id") in ref_steps]
        for target in dict.fromkeys(targets):
            link(ref_steps.get(record_ref), target, "input_reference", [record_ref, start_ref], rid, "same_file_content")

    for run in runs:
        for stage in run["stages"]:
            if stage.get("stage_ref"):
                link(ref_steps.get(stage["stage_ref"]), ref_steps.get(stage.get("event_id")), "stage_result",
                     [stage["stage_ref"], stage.get("event_id")], run["id"], "call_lifecycle")

    changes = {c["id"]: c for c in graph.get("changes", [])}
    for rid, view in chains.items():
        run = next((r for r in runs if r["id"] == rid), None)
        cutoff = events.get(run.get("finished_event_ref"), {}).get("sequence") if run else None
        if cutoff is None and run:
            cutoff = max((e["sequence"] for e in events.values() if e.get("run_id") == rid), default=run.get("event_count_at_start", 0))
        for chain in view["chains"]:
            step = steps.get(ref_steps.get(chain["decision"]))
            if not step:
                continue
            if chain.get("choices"):
                step.setdefault("branches", {}).setdefault("observed_inputs", []).append({"run_id": rid, "choices": chain["choices"]})
            by_change = {}
            for impact in chain.get("impacts", []):
                if impact["judgment"] != "UNAFFECTED":
                    by_change.setdefault(impact["change_id"], []).append(impact)
            for change_id, impacts in by_change.items():
                available = [rid] if cutoff is not None and changes.get(change_id, {}).get("event_sequence", float("inf")) <= cutoff else []
                entry = {"change_id": change_id, "change": changes.get(change_id), "run_ids": available, "impacts": impacts,
                         "summary": "相关旧记录受变化影响，需重新检查。" if any(i["judgment"] == "AFFECTED" for i in impacts)
                         else "变化与相关记录的关系仍需确认。"}
                branches = step.setdefault("branches", {}).setdefault("changes", [])
                previous = next((b for b in branches if b["change_id"] == change_id), None)
                if previous:
                    previous["run_ids"] = list(dict.fromkeys([*previous["run_ids"], *available]))
                else:
                    branches.append(entry)
                review(step["id"], "change", entry["summary"], [change_id], available, "查看变化前后及具体影响；重跑只是建议。")

    ordered_steps = sorted(steps.values(), key=lambda s: (order[s["id"]], s["id"]))
    for index, step in enumerate(ordered_steps):
        step["position"] = {"anchor_sequence": order[step["id"]], "basis": step.pop("order_basis", "recorded_order")}
        step["ordinal"] = index + 1
    def contexts_for(keys):
        return [{"record_ref": n["key"], "request": n["text"], "source": requirement_provenance(n),
                     "background": {k: n.get("context", {}).get(k) for k in ("project_background", "research_question", "task_goal", "purpose")
                                    if isinstance(n.get("context"), dict) and n["context"].get(k)}}
                    for n in nodes.values() if n["kind"] == "requirement" and n["key"] in keys
                    and n.get("request_action") not in {"confirm", "reject"}]
    run_views = []
    for run in runs:
        contexts = contexts_for(run.get("context_refs", []))
        step_ids = [s["id"] for s in ordered_steps if s["id"] in memberships[run["id"]]]
        has_output = any(steps[k].get("role") == "authoritative" for k in step_ids)
        run_views.append({"id": run["id"], "context": contexts, "step_ids": step_ids, "status": run["status"],
                          "authoritative_output_recorded": has_output,
                          "outcome_summary": "已有正式产物记录" if has_output else "程序报告交付，但产物记录缺失" if run["status"] == "delivered"
                          else "本次执行未完成" if run["status"] in {"failed", "trace-stopped", "unfinished"} else "未记录正式交付，查看已有程序结果或候选材料",
                          "file_refs": [n["key"] for n in files if n.get("run_id") == run["id"]],
                          "diagnostics": {**{k: run.get(k, []) for k in ("coverage_gaps", "explanation_gaps")},
                                          "association_gaps": chains.get(run["id"], {}).get("association_gaps", [])}})
    review_groups = {}
    for item in reviews.values():
        group = review_groups.setdefault(item["step_id"], {"step_id": item["step_id"], "items": [], "run_ids": []})
        group["items"].append(item)
        group["run_ids"] = list(dict.fromkeys([*group["run_ids"], *item["run_ids"]]))
    return copy.deepcopy({"version": VERSION, "context": contexts_for(graph["latest"].values()),
                          "steps": ordered_steps, "runs": run_views, "relations": relations,
                          "review": list(review_groups.values()), "integrity": graph["integrity"],
                          "diagnostics": {**{k: graph.get(k, []) for k in
                          ("issues", "coverage_gaps", "explanation_gaps")}, "material_reference_gaps": material_gaps,
                          "association_gaps": [{"run_id": rid, "observations": v["association_gaps"]}
                                               for rid, v in chains.items() if v.get("association_gaps")]}})


def reader_for_run(reader, run_id):
    """Select a frozen run without bringing later evidence or supplements into its view."""
    result = copy.deepcopy(reader)
    run = next((r for r in result["runs"] if r["id"] == run_id), None)
    if run is None:
        raise ValueError("Unknown recorded run")
    selected = set(run["step_ids"])
    known_runs = {r["id"] for r in result["runs"][:result["runs"].index(run) + 1]}
    result["runs"] = [run]
    result["context"] = run["context"]
    result["steps"] = [s for s in result["steps"] if s["id"] in selected]
    for step in result["steps"]:
        step["run_ids"] = [run_id]
        branches = step.get("branches", {})
        for name in ("evidence", "supplements", "changes"):
            if name in branches:
                branches[name] = [b for b in branches[name] if run_id in b["run_ids"]]
                if not branches[name]:
                    del branches[name]
        if "observed_inputs" in branches:
            branches["observed_inputs"] = [b for b in branches["observed_inputs"] if b["run_id"] == run_id]
            if not branches["observed_inputs"]:
                del branches["observed_inputs"]
        if not branches:
            step.pop("branches", None)
    result["relations"] = [e for e in result["relations"] if e["to"] in selected and e["run_id"] in (None, run_id)]
    external = {e["from"] for e in result["relations"] if e["from"] not in selected}
    if external:
        result["related_steps"] = [{**{k: copy.deepcopy(s[k]) for k in
                                    ("id", "kind", "label", "title", "source", "phase", "association_scope",
                                     "record_refs", "event_refs", "files") if k in s},
                                    "run_ids": [rid for rid in s["run_ids"] if rid in known_runs], "reference_only": True}
                                   for s in reader["steps"] if s["id"] in external]
    result["review"] = [r for r in result["review"] if run_id in r["run_ids"] and r["step_id"] in selected]
    for group in result["review"]:
        group["run_ids"] = [run_id]
        group["items"] = [item for item in group["items"] if run_id in item["run_ids"]]
        for item in group["items"]:
            item["run_ids"] = [run_id]
    result["diagnostics"] = {**run["diagnostics"], "issues": reader["diagnostics"]["issues"],
                             "material_reference_gaps": [g for g in reader["diagnostics"]["material_reference_gaps"] if g["run_id"] == run_id],
                             "scope": "coverage/explanations are run-scoped; issues concern the whole event log"}
    for i, step in enumerate(result["steps"]):
        step["ordinal"] = i + 1
    return result
