# -*- coding: utf-8 -*-
"""Deterministic execution layer (v0.9.1-dev2).

Execution writes only ``intermediate/`` artifacts and returns an
``ExecutionResult``.  It never claims formal delivery: only the
authoritative gate may promote artifacts to ``authoritative/``.
"""
from __future__ import annotations

import hashlib
import pathlib

from core.errors import PlanningError
from core.registry import get_task_handler
from core.runtime_plan import compute_plan_sha256
from core.task import canonical_json, task_sha256


def compute_execution_sha256(exec_res: dict) -> str:
    """Compute deterministic cryptographic SHA-256 over execution result fields."""
    semantic = {
        "task_id": exec_res.get("task_id"),
        "task_revision": exec_res.get("task_revision"),
        "task_sha256": exec_res.get("task_sha256"),
        "plan_hash": exec_res.get("plan_hash"),
        "artifact_class": exec_res.get("artifact_class"),
        "method_maturity": exec_res.get("method_maturity"),
        "artifact_hashes": exec_res.get("artifact_hashes", {}),
        "product_sequence_sha256": exec_res.get("product_sequence_sha256"),
    }
    return hashlib.sha256(canonical_json(semantic).encode("utf-8")).hexdigest().upper()


def execute(task: dict, plan: dict, out_dir: pathlib.Path | str) -> dict:
    """Public seam: execute plan deterministically and write intermediate files."""
    actual_task_sha = task_sha256(task)
    if plan.get("task_sha256") != actual_task_sha:
        raise PlanningError("PLAN_TASK_HASH_MISMATCH", "plan task_sha256 does not match current task hash")

    expected_plan_sha = compute_plan_sha256(plan)
    if plan.get("plan_sha256") != expected_plan_sha:
        raise PlanningError("PLAN_HASH_MISMATCH", "plan_sha256 does not match recomputed plan hash")

    out_path = pathlib.Path(out_dir)
    intermediate = out_path / "intermediate" / task["task_id"]
    intermediate.mkdir(parents=True, exist_ok=True)

    handler = get_task_handler(task["task_kind"])
    exec_res = handler.execute(task, plan, intermediate)

    exec_res["task_id"] = task["task_id"]
    exec_res["task_revision"] = task["revision"]
    exec_res["task_sha256"] = plan["task_sha256"]
    exec_res["plan_hash"] = plan["plan_sha256"]
    exec_res["product_sequence"] = plan.get("product_sequence", "")
    exec_res["topology"] = plan.get("product_topology", "circular")
    exec_res["steps"] = plan.get("steps", [])

    e_sha = compute_execution_sha256(exec_res)
    exec_res["execution_sha256"] = e_sha

    return exec_res
