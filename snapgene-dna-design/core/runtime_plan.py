# -*- coding: utf-8 -*-
"""Deterministic planning layer (v0.9.1-dev2).

Plans are constructed by dedicated TaskHandlers registered in core.registry.
Every plan is frozen into a canonical hash-bound PlanResult.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

from core.errors import PlanningError, TaskValidationError
from core.registry import get_task_handler, get_task_kind
from core.task import canonical_json, task_sha256, validate_construction_task


def compute_plan_sha256(plan: dict) -> str:
    """Compute deterministic cryptographic SHA-256 over semantic plan fields."""
    semantic = {
        "task_id": plan.get("task_id"),
        "task_revision": plan.get("task_revision"),
        "task_sha256": plan.get("task_sha256"),
        "task_kind": plan.get("task_kind"),
        "handler_id": plan.get("handler_id"),
        "handler_version": plan.get("handler_version"),
        "method_maturity": plan.get("method_maturity"),
        "sources": [
            {
                "source_id": s.get("source_id"),
                "sha256": s.get("sha256"),
                "role": s.get("role"),
                "topology": s.get("topology"),
            }
            for s in plan.get("sources", [])
        ],
        "product_topology": plan.get("product_topology"),
        "product_sequence_sha256": plan.get("product_sequence_sha256"),
        "expected_components": plan.get("expected_components", []),
        "forbidden_components": plan.get("forbidden_components", []),
        "steps": plan.get("steps", []),
        "scope_note": plan.get("scope_note"),
        "preparation_check": plan.get('preparation_check'),
        'selected_output_version':plan.get('selected_output_version'),
    }
    if "product_features" in plan:
        semantic["product_features"] = plan["product_features"]
    if 'product_molecule' in plan:
        semantic['product_molecule'] = plan['product_molecule']
    return hashlib.sha256(canonical_json(semantic).encode("utf-8")).hexdigest().upper()


def plan(task: dict, base_dir: str | None = None) -> tuple[dict, dict]:
    """Public seam: validate task and invoke dedicated TaskHandler.plan."""
    vtask = validate_construction_task(task, base_dir=base_dir)
    t_sha = task_sha256(vtask)

    handler = get_task_handler(vtask["task_kind"])
    raw_plan = handler.plan(vtask)

    raw_plan["task_id"] = vtask["task_id"]
    raw_plan["task_revision"] = vtask["revision"]
    raw_plan["task_sha256"] = t_sha
    raw_plan["task_kind"] = vtask["task_kind"]
    raw_plan["handler_id"] = handler.handler_id
    raw_plan["handler_version"] = handler.handler_version
    raw_plan["method_maturity"] = handler.method_maturity
    if vtask["task_kind"] not in ("composite_pipeline", "pipeline"):
        raw_plan["scope_note"] = (
            "Deterministic sequence and annotation model. Experimental preparation "
            "has not been simulated; use a Recipe or explicit reaction Pipeline for that evidence."
        )

    p_sha = compute_plan_sha256(raw_plan)
    raw_plan["plan_sha256"] = p_sha

    # Compatibility keys expected by legacy inspections
    raw_plan.setdefault("product", {})
    raw_plan["product"]["topology"] = raw_plan.get("product_topology", "circular")
    raw_plan["product"]["sequence"] = raw_plan.get("product_sequence", "")
    raw_plan["product"]["expected_length"] = len(raw_plan.get("product_sequence", ""))

    return vtask, raw_plan


# Compatibility mapping for tests inspecting registered planners
from core.handlers import HANDLERS  # noqa: E402
_PLANNERS = {kind: h.plan for kind, h in HANDLERS.items()}
