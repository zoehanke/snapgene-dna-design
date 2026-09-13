"""Decision-centered navigation; displayed order is not an inferred causal proof."""
from __future__ import annotations

import copy

from evidence_trace.applicability import assess
from evidence_trace.coverage import choices_for_run, match_choices


def build_chains(graph):
    """Project run-frozen local chains without altering stored facts or Core results."""
    result = copy.deepcopy(graph)
    by_key = {n["key"]: n for n in result["nodes"]}
    views = []
    scopes = result["runs"] or [{"id": None, "context_refs": list(by_key), "decision_refs": [
        n["key"] for n in result["nodes"] if n["kind"] == "decision"], "event_count_at_start": float("inf")}]
    for run in scopes:
        scope = set(run.get("context_refs", []))
        scope.update(n["key"] for n in result["nodes"] if n.get("run_id") == run["id"] and run["id"] is not None)
        edges = [e for e in result["edges"] if e.get("recorded_sequence", 0) <= run.get("event_count_at_start", 0)
                 or (run["id"] is not None and by_key.get(e["to"], {}).get("run_id") == run["id"])]
        chains = []
        for key in run.get("decision_refs", []):
            decision = by_key.get(key)
            if not decision:
                continue
            claims = decision.get("references", {}).get("claim_ids", [])
            evidence = []
            for edge in edges:
                if edge["to"] in claims and "statement_id" in edge:
                    statement = by_key.get(edge["from"], {})
                    evidence.append({"link": edge, "statement": edge["from"], "claim": edge["to"],
                        "sources": statement.get("references", {}).get("source_id", []),
                        "assessment": assess(statement.get("context", {}), by_key.get(edge["to"], {}).get("context", {}),
                                             edge.get("required_dimensions"))})
            validations = [n["key"] for n in result["nodes"] if n["kind"] == "validation"
                           and n.get("run_id") == run["id"] and key in n.get("references", {}).get("decision_ids", [])]
            artifacts = [n["key"] for n in result["nodes"] if n["kind"] == "artifact"
                         and n.get("run_id") == run["id"] and key in n.get("references", {}).get("decision_ids", [])]
            related = {key, *claims, *validations, *artifacts}
            for branch in evidence:
                related.update([branch["statement"], *branch["sources"]])
            queue = [q for q in run.get("review_queue", result.get("review_queue", [])) if q["node"] in related]
            queue = [q for q in queue if not (by_key.get(q["node"], {}).get("kind") == "validation"
                     and by_key[q["node"]].get("result") in {"not_requested", "N/A", "not_applicable"})]
            for branch in evidence:
                if branch["assessment"]["status"] != "direct":
                    queue.append({"node": key, "reason": "Evidence applicability: " + branch["assessment"]["status"] + " · " + branch["assessment"]["reason"]})
            chains.append({"decision": key, "requirements": decision.get("references", {}).get("responds_to", []),
                "claims": claims, "validations": validations, "artifacts": artifacts, "evidence": evidence,
                "basis_refs": decision.get("basis_refs", []),
                "explanation_gaps": [g for g in run.get("explanation_gaps", result.get("explanation_gaps", [])) if g["node"] == key],
                "review": queue, "association_scope": "Validation/Artifact association is run-level, not proof of this Claim."})
        coverage = match_choices(choices_for_run(run), [by_key[k] for k in run.get("decision_refs", []) if k in by_key])
        for c in chains:
            c["choices"] = [o for o in coverage if c["decision"] in o["decision_refs"]]
            c["association_gaps"] = [o for o in c["choices"] if c["decision"] not in o["matched_decision_refs"]]
        views.append({"run_id": run["id"], "chains": chains,
            "edges": edges,
            "artifacts": [n["key"] for n in result["nodes"] if n["kind"] == "artifact" and n.get("run_id") == run["id"]],
            "validations": [n["key"] for n in result["nodes"] if n["kind"] == "validation" and n.get("run_id") == run["id"]],
            "choices": coverage, "unexplained_choices": [o for o in coverage if not o["decision_refs"]],
            "coverage_gaps": run.get("coverage_gaps", result.get("coverage_gaps", [])),
            "explanation_gaps": run.get("explanation_gaps", result.get("explanation_gaps", [])),
            "association_gaps": [o for o in coverage if o["target_match"] != "matched"],
            "coverage": {"observed": len(coverage), "explained": sum(o["status"] == "explained" for o in coverage),
                         "target_matched": sum(o["target_match"] == "matched" for o in coverage),
                         "original_explanation_recorded": sum(o["original_explanation_recorded"] for o in coverage),
                         "need_review": sum(o["target_match"] != "matched" for o in coverage),
                         "scope": "Known structured input fields; not complete biological reasoning coverage."}})
    result["chain_views"] = views
    result["projection_version"] = "0.3.0"
    from evidence_trace.impact import attach_impacts
    return attach_impacts(result)
