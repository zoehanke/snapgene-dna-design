"""Separate supplied authorship and explanation from tool-input observations."""


def decision_provenance(node):
    source = node.get("decision_source") or {}
    actor = node.get("decision_actor", "unknown")
    attributed = actor in {"user", "ai"} and isinstance(source, dict) and bool(source.get("reference"))
    rationale = str(node.get("rationale") or "").strip()
    origin = node.get("explanation_origin", "unknown") if rationale else "missing"
    if origin == "user_statement" and not (attributed and actor == "user"):
        origin = "unknown"
    if origin == "ai_concurrent" and not (attributed and actor == "ai"):
        origin = "unknown"
    labels = {"user_statement": "用户说明", "ai_concurrent": "AI 当时说明",
              "missing": "仅记录选择，没有原始说明", "unknown": "已记录说明，来源未确认"}
    return {"decision_actor": actor if attributed else "unknown",
            "decision_source": source, "explanation_origin": origin,
            "explanation_label": labels.get(origin, labels["unknown"]),
            "rationale": rationale, "mode_at_capture": node.get("mode_at_capture", "unknown"),
            "original_explanation_recorded": origin in {"user_statement", "ai_concurrent"}}


def validate_provenance(node):
    if node.get("kind") == "requirement":
        source = node.get("requirement_source")
        if source is not None:
            if not isinstance(source, dict) or not isinstance(source.get("reference"), str) or not source["reference"].strip():
                raise ValueError("requirement_source needs a supplied reference")
            if source.get("form", "unknown") not in {"verbatim", "summary", "unknown"}:
                raise ValueError("requirement_source.form must be verbatim, summary or unknown")
            if source.get("form") == "verbatim" and source.get("excerpt", node["text"]) != node["text"]:
                raise ValueError("Verbatim requirement must preserve the supplied excerpt")
        action = node.get("request_action", "request")
        if not isinstance(action, str) or not action.strip():
            raise ValueError("request_action must be a nonblank classification")
        if action in {"change", "confirm", "reject"} and (not source or not node.get("basis_refs")):
            raise ValueError("User intervention needs its source and exact affected record/event basis_refs")
        return
    if node.get("kind") != "decision":
        return
    actor = node.get("decision_actor", "unknown")
    origin = node.get("explanation_origin", "unknown")
    if actor not in {"user", "ai", "unknown"}:
        raise ValueError("decision_actor must be user, ai or unknown; program results are not decisions")
    if origin not in {"user_statement", "ai_concurrent", "unknown"}:
        raise ValueError("Original explanation_origin must be user_statement, ai_concurrent or unknown; append assistance separately")
    source = node.get("decision_source") or {}
    if not isinstance(source, dict):
        raise ValueError("decision_source must contain a supplied reference")
    if actor != "unknown" and not str(source.get("reference") or "").strip():
        raise ValueError("Attributed decision needs decision_source.reference")
    if origin in {"user_statement", "ai_concurrent"}:
        if not str(node.get("rationale") or "").strip() or actor != ("user" if origin == "user_statement" else "ai"):
            raise ValueError("Original explanation needs nonblank rationale and matching decision_actor")


def requirement_provenance(node):
    source = node.get("requirement_source") or {}
    return {"request_action": node.get("request_action", "request"),
            "requirement_source": source,
            "origin": "supplied_user_source" if source.get("reference") else "unknown",
            "text_form": source.get("form", "unknown")}
