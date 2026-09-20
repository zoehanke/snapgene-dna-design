"""Human-readable projection of a saved process. Scientific organization stays upstream."""
from __future__ import annotations

import copy
from pathlib import Path

from evidence_trace.reader import check_status
from evidence_trace.details import readable_details, handoff_text, filename, CHECKS, ROLES, result_text, ORIGINS, applicability_text

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
    def record_at(ref):
        record = records.get(ref, {})
        return record.get('payload', {}) if record.get('event_type') == 'node_recorded' else record
    if active:
        order = list(dict.fromkeys([key for section in plan.get("sections", []) for key in section["step_refs"]]
                                  + [key for stage in active["stages"] for key in stage["step_ids"]]
                                  + list(active["steps"])))
        for key in order:
            step = copy.deepcopy(active["steps"][key])
            refs = step["source_refs"]
            label = LABELS[step["kind"]]
            decision = record_at(step.get("subject_ref")) or next((record_at(r) for r in refs if record_at(r).get("kind") == "decision"), {})
            if step["kind"] == "choice":
                who = decision.get("decision_actor", "unknown")
                if decision.get('kind') == 'requirement' and decision.get('request_action') in {'choose', 'selection', 'confirm', 'reject'}:
                    who = 'user'
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
                           "run_id": node.get("run_id"),
                           "status": "not_requested" if node.get("result") in ("not_requested", "N/A", "not_applicable") else check_status(node.get("result"))[0]})
        elif node["kind"] == "artifact":
            artifacts.append({"ref": node["key"], **{k: node.get(k) for k in
                ("path", "sha256", "role", "run_id", "result_event_ref", "generation_observation", "validated_by")}})
    reviews = [{"text": u["text"], "source_refs": u["source_refs"], "step_refs": u["step_refs"],
                "category": "authored_unresolved"} for u in active["unresolved"]] if active else []
    gaps = []
    for finding in graph['findings']:
        category = finding['category']
        item = {'text': finding.get('message', finding.get('text', '')),
                'source_refs': finding.get('refs', []), 'category': category}
        if category == 'handoff':
            item['text'] = filename(finding['path']) + '：' + handoff_text(finding)
            (reviews if finding['status'] in {'missing', 'changed'} else gaps).append(item)
        elif category in {'capture', 'coverage', 'explanation_gap', 'unexplained_design_choice', 'missing_explanation'}:
            gaps.append(item)
        elif finding.get('domain') == 'review' or category in {'review', 'execution_failure', 'validation_failure', 'change_impact',
                                                            'program_check', 'missing_evidence', 'evidence_conflict', 'change'}:
            reviews.append(item)
        else:
            # Keep unfamiliar diagnostics visible without inventing a scientific verdict.
            gaps.append(item)
    context = plan.get("context") if active else None
    sources = readable_details(records)
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
    # Build detail evidence for every recorded choice, independent of which
    # choices the authored report elects to show in its main narrative.
    branches = {}
    for old in graph['reader']['steps']:
        if old.get('kind') != 'choice':
            continue
        for owner in old.get('record_refs', []):
            if record_at(owner).get('kind') != 'decision':
                continue
            owner = record_at(owner)['key']
            branch = copy.deepcopy(old.get('branches', {}))
            for evidence in branch.get('evidence', []):
                evidence.update(decision_ref=owner, decision_title=old['title'])
                assessment = evidence.get('assessment') or {}
                if assessment:
                    assessment['reason'] = applicability_text(assessment)
                for ref in dict.fromkeys(evidence.get('record_refs', []) + [owner]):
                    if ref not in sources:
                        continue
                    detail = sources[ref]
                    if evidence not in detail['evidence']:
                        detail['evidence'].append(copy.deepcopy(evidence))
                    for evidence_ref in evidence.get('record_refs', []):
                        link = {'label': '依据与判断', 'ref': evidence_ref}
                        if evidence_ref != ref and evidence_ref in sources and link not in detail['related']:
                            detail['related'].append(link)
            branches[owner] = branch
    for ref, record in records.items():
        if record.get('event_type') == 'node_recorded':
            sources[ref]['evidence'] = sources[record['payload']['key']]['evidence']
    for step in steps:
        ref_list = list(dict.fromkeys(step['source_refs'] + step.get('outcome_refs', [])))
        ref_set = set(ref_list)
        step['checks'] = [c for c in checks if c['ref'] in ref_set]
        step['artifacts'] = [a for a in artifacts if a['ref'] in ref_set]
        step['program_records'] = [r for r in ref_list if records.get(r, {}).get('event_type') in {
            'stage_completed', 'stage_failed', 'file_operation_completed', 'file_operation_failed'}]
        step['evidence'] = []
        subjects = [step['subject_ref']] if step.get('subject_ref') else step['source_refs']
        owners = list(dict.fromkeys(record_at(r)['key'] for r in subjects
                     if step['kind'] == 'choice' and record_at(r).get('kind') == 'decision'))
        for owner in owners:
            branch = branches.get(owner, {})
            step['evidence'].extend(copy.deepcopy(branch.get('evidence', [])))
            step.setdefault('recorded_explanations', []).extend(copy.deepcopy(branch.get('supplements', [])))
    presented_artifacts = artifacts
    if graph.get("handoff"):
        selected_refs = {ref for item in graph["handoff"]["files"] for ref in item["artifact_refs"]}
        presented_artifacts = [a for a in artifacts if a["ref"] in selected_refs]
        for index, item in enumerate(graph['handoff']['files']):
            if item['artifact_refs']:
                for ref in item['artifact_refs']:
                    if item.get('purpose') and ref in sources:
                        sources[ref]['fields'].insert(0, {'label': '交付用途', 'text': item['purpose']})
                continue
            ref = 'handoff-file:' + str(index)
            presented_artifacts.append({'ref': ref, 'path': item['path'], 'role': '交付清单中的文件',
                                        'purpose': item.get('purpose'), 'handoff_status': item['status']})
            sources[ref] = readable_details({ref: dict(kind='artifact', **item)})[ref]
            sources[ref]['fields'].insert(0, {'label': '交付记录', 'text': handoff_text(item)})
    for item in artifacts + presented_artifacts:
        item['display_role'] = ROLES.get(item.get('role'), item.get('role') or '身份未记录')
        item['name'] = filename(item['path'])
    for item in checks:
        item['display_check'] = CHECKS.get(item['check'], item['check'])
        item['display_result'] = result_text(item['result'])
    change_details = readable_changes(graph, sources)
    def changes_for(owned):
        return [dict(c, impacts=[i for i in c['impacts'] if i['target_ref'] in owned])
                for c in change_details if any(i['target_ref'] in owned for i in c['impacts'])]
    for ref, source in sources.items():
        source['changes'] = changes_for([record_at(ref).get('key', ref)])
    for step in steps:
        owned = [step['subject_ref']] if step.get('subject_ref') else step['source_refs']
        step['changes'] = changes_for([record_at(ref).get('key', ref) for ref in owned])
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
            "recording_gaps": gaps,
            "change_details": change_details,
            "sources": sources, "coverage": graph["coverage"], "findings": graph["findings"],
            "handoff": graph.get("handoff"), "organization_history": graph["organization_history"],
            "historical_process": process if state == "stale" else None,
            "changes": graph.get("changes", []), "impacts": graph.get("impacts", []),
            "fact_relations": graph["fact_relations"]}


def readable_changes(graph, sources):
    fields = {'host': '宿主', 'organism': '物种', 'strain': '菌株', 'temperature': '温度',
              'sequence': '序列', 'method': '方法', 'intended_use': '用途', 'medium': '培养基'}
    actions = {'REASSESS':'重新判断', 'RECHECK':'重新检查依据', 'RERUN':'建议重新运行检查',
               'STALE':'属于旧上下文', 'NEEDS REVIEW':'需要人工复核'}
    judgments = {'AFFECTED':'明确受到影响', 'NEEDS REVIEW':'可能受到影响',
                 'UNKNOWN':'信息不足，影响未知', 'UNAFFECTED':'在已声明范围内无关'}
    def value(v):
        if v is None:
            return '未记录'
        if isinstance(v, (str, int, float, bool)):
            return str(v)
        if isinstance(v, list) and all(isinstance(x, (str, int, float)) for x in v):
            return ', '.join(str(x) for x in v)
        if isinstance(v, dict) and 'value' in v and 'unit' in v:
            return value(v['value']) + ' ' + str(v['unit'])
        return '结构化内容已变更，完整值见技术记录'
    result = []
    for c in graph.get('changes', []):
        field = c.get('changed_field', '').rsplit('.', 1)[-1]
        impacts = []
        for impact in graph.get('impacts', []):
            if impact['change_id'] != c['id']:
                continue
            target = impact['target']
            impacts.append({'target_ref': target, 'target_title': sources.get(target, {}).get('title', '相关依据的适用性'),
                            'judgment': judgments.get(impact['judgment'], '影响尚未分类'),
                            'reason': applicability_text({'reason': impact.get('reason', '')}),
                            'actions': [actions.get(a, a) for a in impact['actions']]})
        result.append({'id': c['id'], 'field': fields.get(field, field), 'before': '未提供此条件' if c.get('old_present') is False else '明确留空' if c.get('old_present') is True and c.get('old_value') is None else value(c.get('old_value')),
                       'after': '未提供此条件' if c.get('new_present') is False else '明确留空' if c.get('new_present') is True and c.get('new_value') is None else value(c.get('new_value')), 'recorded_at': c.get('recorded_at'), 'impacts': impacts})
    return result


def markdown(report):
    def safe(value):
        text = str(value or "")
        for char in ("\\", "`", "*", "_", "[", "]", "<", ">", "#", "|"):
            text = text.replace(char, "\\" + char)
        return text
    def source_names(refs):
        return ', '.join(safe(report['sources'][r]['title']) for r in refs if r in report['sources'])
    lines = ["# " + safe(report["title"]), ""]
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
            lines += [ORIGINS.get(step['reason']['origin'], '说明来源未确认') + "：" + safe(step["reason"]["text"]), ""]
        lines += ["来源：" + source_names(step['source_refs']), ""]
        for field, label in (("input_refs", "输入"), ("outcome_refs", "输出与检查对象")):
            if step.get(field):
                lines += [label + "：" + source_names(step[field]), ""]
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
        lines += [safe(a['display_role']) + "：" + safe(a['name']), ""]
        lines += ['[' + safe(link['label']) + '](<' + link['href'] + '>)' for link in report['sources'][a['ref']]['links']]
    if not report["artifacts"]:
        lines += ["未记录产物。", ""]
    lines += [safe(c['display_check']) + "：" + safe(c['display_result']) + "\n" for c in report["checks"]]
    if report["review"]:
        lines += ["## 需要处理", ""] + [safe(r["text"]) + "\n" for r in report["review"]]
    if report.get("handoff"):
        lines += ["交付清单核对：", ""] + [safe(filename(f['path'])) + "：" + safe(handoff_text(f)) + "\n" for f in report["handoff"]["files"]]
    if report['recording_gaps']:
        lines += ['## 记录完整性', ''] + [safe(gap['text']) + '\n' for gap in report['recording_gaps']]
    if report['change_details']:
        lines += ['## 变化与影响', '', '以下为重查建议，不修改原来的科学判断或程序结果。', '']
        for change in report['change_details']:
            lines += ['### ' + safe(change['field']), '', safe(change['before']) + ' → ' + safe(change['after']), '']
            for impact in change['impacts']:
                lines += [safe(impact['target_title']) + '：' + safe(impact['judgment']) + '；' + safe(', '.join(impact['actions'])), '']
    lines += ["## 查看详细记录", "", "完整原记录、条件、关系和历史见同目录 graph.json。", ""]
    for ref, source in report["sources"].items():
        lines += ["### " + safe(source['title']), ""]
        lines += [safe(f['label']) + '：' + safe(f['text']) + '\n' for f in source['fields']]
        lines += ['[' + safe(link['label']) + '](<' + link['href'] + '>)' for link in source['links']]
        for e in source['evidence']:
            lines += ['用于选择：' + safe(e['decision_title']),
                      safe(e.get('label', e['relation'])) + '：' + safe(e['statement']),
                      '对应判断：' + safe(e['claim']), '']
            lines += ['适用边界：' + safe(v) for v in e.get('limitations', [])]
    return "\n".join(lines)
