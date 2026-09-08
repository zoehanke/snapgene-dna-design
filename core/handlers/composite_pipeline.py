# -*- coding: utf-8 -*-
"""core/handlers/composite_pipeline.py - Composite Pipeline Task Handler.

Liberates the DNA design agent from rigid single-task templates by allowing
arbitrary composite, multi-step construction workflows orchestrated through
atomic biological tools.
"""
from __future__ import annotations

import hashlib
import copy
import pathlib
from typing import Any

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from core.errors import PlanningError, TaskValidationError
from core.guardrails.checklist import quick_biological_sanity_check
from core.handlers.base import TaskHandler
from core.io.input_resolution import resolve_sequence_record
from core.models.construct_model import feature_to_dict
from core.tools import (
    export_snapgene,
    get_tool,
    TOOL_REGISTRY,
)


def _resolve_param_val(
    val: Any,
    env: dict[str, Any],
    sources_map: dict[str, Any],
    results: dict | None = None,
    analysis_steps: set[str] | None = None,
) -> Any:
    """Resolve step parameter value referencing source_id or previous step_id output."""
    analysis_steps = analysis_steps or set()
    if isinstance(val, str):
        if val.startswith("$"):
            var_name = val[1:]
            if var_name in env:
                if var_name in analysis_steps:
                    raise PlanningError(
                        "ANALYSIS_OUTPUT_REFERENCE",
                        f"Analysis step '{var_name}' cannot be used as a DNA sequence; reference a result field instead",
                    )
                return copy.deepcopy(env[var_name])
            if var_name in sources_map:
                return copy.deepcopy(sources_map[var_name])
            head, _, tail = var_name.partition(".")
            if tail and (head in (results or {}) or head in env):
                result = (results or {}).get(head, env.get(head))
                try:
                    for field in tail.split("."):
                        result = result[int(field)] if isinstance(result, (list, tuple)) else result[field]
                except (KeyError, IndexError, TypeError, ValueError) as exc:
                    raise PlanningError("INVALID_STEP_REFERENCE", f"Cannot resolve '{val}'") from exc
                return copy.deepcopy(result)
            raise PlanningError("UNRESOLVED_STEP_REFERENCE", f"Unknown source or earlier step: '{val}'")
        elif val in sources_map:
            return copy.deepcopy(sources_map[val])
    elif isinstance(val, list):
        return [_resolve_param_val(item, env, sources_map, results, analysis_steps) for item in val]
    elif isinstance(val, dict):
        return {
            k: _resolve_param_val(v, env, sources_map, results, analysis_steps)
            for k, v in val.items()
        }
    return val


def _resolve_source_records(sources_map: dict[str, Any]) -> dict[str, SeqRecord]:
    """Resolve every named source before dispatching a pipeline step.

    A source reference carries the complete record, including topology and
    annotations. Passing its path as a plain string lets sequence-only tools
    interpret the path itself as DNA and bypasses annotation preservation.
    """
    resolved: dict[str, SeqRecord] = {}
    for source_id, value in sources_map.items():
        try:
            resolved[source_id] = (
                copy.deepcopy(value)
                if isinstance(value, SeqRecord)
                else resolve_sequence_record(value)
            )
        except Exception as exc:
            raise PlanningError(
                "SOURCE_RESOLUTION_ERROR",
                f"Source '{source_id}' could not be resolved to a sequence record: {exc}",
            ) from exc
    return resolved


def _extract_dna_output(tool_spec, result: Any) -> str:
    """Extract DNA only from tools declared as sequence-producing.

    Pure analysis results remain available through ``results`` and dotted
    references. They must not become the selected construct sequence merely
    because a result happens to contain a field named ``sequence``.
    """
    if isinstance(result, SeqRecord):
        return tool_spec.extract_sequence(result)
    if getattr(tool_spec, "name", "") == "translate_dna":
        return ""
    if getattr(tool_spec, "result_type", None) == "protein":
        return ""
    if getattr(tool_spec, "result_type", None) in {"list", "object"}:
        return ""
    if isinstance(result, dict) and not getattr(tool_spec, "sequence_output_key", None):
        return ""
    return tool_spec.extract_sequence(result)


def _output_topology(value: Any) -> str | None:
    """Read topology emitted by a selected sequence-producing output."""
    if isinstance(value, SeqRecord):
        topology = value.annotations.get("topology")
    elif isinstance(value, dict):
        topology = value.get("product_topology") or value.get("topology")
    else:
        topology = None
    topology = str(topology).lower() if topology else None
    return topology if topology in {"linear", "circular"} else None


def run_pipeline_steps(steps: list[dict], sources_map: dict[str, Any], output_step: str | None = None) -> tuple[str, list[dict], dict[str, Any]]:
    """Execute pipeline steps sequentially in an in-memory environment."""
    env: dict[str, Any] = {}
    step_records: list[dict] = []
    results: dict[str, Any] = {}
    sequences: dict[str, str] = {}
    analysis_steps: set[str] = set()
    sources = _resolve_source_records(sources_map)

    def has_annotations(value):
        if isinstance(value, SeqRecord):
            return bool(value.features)
        if isinstance(value, dict):
            return any(has_annotations(item) for item in value.values())
        if isinstance(value, list):
            return any(has_annotations(item) for item in value)
        return False

    for step in steps:
        step_id = step.get("step_id")
        tool = step.get("tool")
        raw_params = step.get("params", {})
        if not step_id or step_id in env:
            raise PlanningError("INVALID_STEP_ID", "Pipeline step ids must be nonempty and unique")
        params = _resolve_param_val(raw_params, env, sources, results, analysis_steps)

        tool_spec = get_tool(tool)
        if not tool_spec:
            raise PlanningError(
                "UNSUPPORTED_PIPELINE_TOOL",
                f"Atomic tool '{tool}' is not registered in TOOL_REGISTRY",
            )
        if tool_spec.category not in ("compute", "inspect"):
            raise PlanningError("PIPELINE_SIDE_EFFECT", f"'{tool}' is not a computation step; export artifacts after execution")

        try:
            res = tool_spec.execute(**params)
        except Exception as exc:
            raise PlanningError(
                "TOOL_EXECUTION_ERROR",
                f"Tool '{tool}' failed during step '{step_id}': {exc}",
            )

        out_seq = _extract_dna_output(tool_spec, res)
        if out_seq and has_annotations(params) and not (
            isinstance(res, SeqRecord) or isinstance(res, dict) and "features" in res
        ):
            raise PlanningError("ANNOTATION_LOSS", f"Tool '{tool}' does not return mapped features for annotated inputs")

        if isinstance(res, SeqRecord):
            res = {
                "sequence": out_seq,
                "topology": res.annotations.get("topology", "linear"),
                "features": [feature_to_dict(f, len(res)) for f in res.features],
            }
        if out_seq and isinstance(res, dict) and "features" in res:
            env[step_id] = resolve_sequence_record({**res, "sequence": out_seq})
        else:
            env[step_id] = out_seq if out_seq else res
        if not out_seq:
            analysis_steps.add(step_id)
        results[step_id] = res
        sequences[step_id] = out_seq
        step_records.append({
            "step_id": step_id,
            "tool": tool,
            "output_length": len(out_seq),
            "output_sha256": hashlib.sha256(out_seq.encode("utf-8")).hexdigest().upper(),
            "details": res,
            "params": copy.deepcopy(raw_params),
        })

    chosen = output_step or (steps[-1]["step_id"] if steps else None)
    if chosen is not None and chosen not in sequences:
        raise PlanningError("UNKNOWN_OUTPUT_STEP", f"Unknown output_step '{chosen}'")
    final_seq = sequences.get(chosen, "")
    return final_seq, step_records, env


class CompositePipelineHandler(TaskHandler):
    """General-purpose TaskHandler executing multi-step composite construction workflows."""

    kind = "composite_pipeline"
    handler_id = "handler-composite-pipeline-v1"
    handler_version = "1.0.0"
    method_maturity = "validated"
    # Composite steps may end in a linear PCR or a circular assembly. Use a
    # conservative fallback only when an output carries no topology metadata;
    # normal plans derive topology from the selected output record.
    default_topology = "linear"

    def validate_contract(self, task: dict) -> None:
        pipe = task.get("pipeline")
        if not pipe:
            raise TaskValidationError("PIPELINE_REQUIRED", "composite_pipeline task requires 'pipeline' block")
        steps = pipe.get("steps")
        if not steps or not isinstance(steps, list):
            raise TaskValidationError("PIPELINE_STEPS_REQUIRED", "pipeline must contain a non-empty list of steps")

    def clarify(self, task: dict) -> list[dict]:
        return task.get("pipeline", {}).get("questions", [])

    def _sources_map(self, task: dict) -> dict[str, SeqRecord]:
        smap: dict[str, SeqRecord] = {}
        for s in task.get("sources", []):
            sid = s.get("source_id")
            resolved = s.get("_resolved_path") or s.get("path") or s.get("filepath")
            if sid and resolved:
                try:
                    smap[sid] = resolve_sequence_record(resolved)
                except Exception as exc:
                    raise PlanningError(
                        "SOURCE_RESOLUTION_ERROR",
                        f"Source '{sid}' could not be resolved to a sequence record: {exc}",
                    ) from exc
        return smap

    def plan(self, task: dict) -> dict:
        self.validate_contract(task)
        sources_map = self._sources_map(task)
        steps = task["pipeline"]["steps"]

        output_step = task["pipeline"].get("output_step") or steps[-1]["step_id"]
        final_seq, step_records, _env = run_pipeline_steps(steps, sources_map, output_step)
        if not final_seq:
            raise PlanningError("NO_PRODUCT_SEQUENCE", "Select a sequence-producing output_step before later analysis steps")
        final_record = _env[output_step]
        requested_topology = (task.get("product") or {}).get("topology")
        actual_topology = _output_topology(final_record)
        if actual_topology is None:
            selected_record = next(
                (row for row in step_records if row.get("step_id") == output_step),
                {},
            )
            actual_topology = _output_topology(selected_record.get("details")) or "linear"
        if requested_topology and requested_topology != actual_topology:
            raise PlanningError(
                "PRODUCT_TOPOLOGY_MISMATCH",
                "Requested product topology '%s' does not match actual output topology '%s' at output_step '%s'"
                % (requested_topology, actual_topology, output_step),
                details={
                    "requested_topology": requested_topology,
                    "actual_topology": actual_topology,
                    "output_step": output_step,
                },
            )
        topo = actual_topology

        return {
            "task_kind": self.kind,
            "product_topology": topo,
            "actual_topology": actual_topology,
            "requested_topology": requested_topology,
            "product_sequence": final_seq,
            "product_features": [feature_to_dict(f, len(final_record)) for f in final_record.features] if isinstance(final_record, SeqRecord) else [],
            "product_sequence_sha256": hashlib.sha256(final_seq.encode("utf-8")).hexdigest().upper(),
            "steps": step_records,
            "output_step": output_step,
            "expected_components": task.get("expected_components", []),
            "forbidden_components": task.get("forbidden_components", []),
            "sources": task.get("sources", []),
        }

    def execute(self, task: dict, plan: dict, out_dir: pathlib.Path) -> dict:
        inter = out_dir / "intermediate"
        inter.mkdir(parents=True, exist_ok=True)

        prod_seq = plan["product_sequence"]
        topo = plan.get("product_topology", "circular")
        name = task.get("task_id", "construct")

        exported = export_snapgene(
            record_or_seq=resolve_sequence_record({"sequence": prod_seq, "topology": topo, "features": plan.get("product_features", [])}),
            out_dir=inter,
            filename_base=name,
            topology=topo,
            features=task.get("features"),
        )

        gb_path = pathlib.Path(exported["gb_file"])
        fa_path = inter / f"{name}.fasta"
        fa_rec = SeqRecord(Seq(prod_seq), id=name, name=name, description="Construct FASTA")
        with open(fa_path, "w", encoding="utf-8") as fh:
            SeqIO.write(fa_rec, fh, "fasta")

        gb_bytes = gb_path.read_bytes()
        fa_bytes = fa_path.read_bytes()
        dna_path = pathlib.Path(exported["dna_file"])
        dna_bytes = dna_path.read_bytes() if dna_path.exists() else b""

        gb_hash = hashlib.sha256(gb_bytes).hexdigest().upper()
        fa_hash = hashlib.sha256(fa_bytes).hexdigest().upper()
        dna_hash = hashlib.sha256(dna_bytes).hexdigest().upper() if dna_bytes else ""

        return {
            "artifact_class": "intermediate",
            "method_maturity": self.method_maturity,
            "product_gb": str(gb_path),
            "product_fasta": str(fa_path),
            "product_dna": exported["dna_file"],
            "gb_sha256": gb_hash,
            "fasta_sha256": fa_hash,
            "dna_sha256": dna_hash,
            "artifact_hashes": {
                "construct.gb": gb_hash,
                "construct.fasta": fa_hash,
                "construct.dna": dna_hash,
            },
            "product_sequence_sha256": plan["product_sequence_sha256"],
            "intermediate_files": [str(gb_path), str(fa_path), exported["dna_file"]],
        }

    def recompute(self, task: dict, plan: dict) -> str:
        sources_map = self._sources_map(task)
        steps = task.get("pipeline", {}).get("steps", [])
        final_seq, _, _ = run_pipeline_steps(steps, sources_map, task.get("pipeline", {}).get("output_step"))
        return final_seq.upper()

    def validate_goal(
        self,
        task: dict,
        plan: dict,
        execution: dict,
        product_record: SeqRecord,
        product_seq: str,
    ) -> tuple[bool, list[dict], list[str]]:
        errors = []
        traces = []
        from core.runtime_validate import _validate_requested_components
        component_traces, component_errors = _validate_requested_components(task, product_record)
        traces.extend(component_traces)
        errors.extend(component_errors)

        if len(product_seq) == 0:
            errors.append("Product sequence is empty")

        exp_sha = plan.get("product_sequence_sha256")
        act_sha = hashlib.sha256(product_seq.encode("utf-8")).hexdigest().upper()
        if exp_sha and act_sha != exp_sha:
            errors.append(f"Sequence SHA256 mismatch: expected {exp_sha}, got {act_sha}")

        # Run lightweight biological sanity check
        topo = plan.get("actual_topology") or plan.get("product_topology") or task.get("product", {}).get("topology", self.default_topology)
        is_cds = bool(task.get("product", {}).get("is_cds", False))
        sanity = quick_biological_sanity_check(
            product_record,
            topology=topo,
            is_cds=is_cds,
        )
        traces.append({
            "check": "quick_biological_sanity_check",
            "result": sanity,
        })

        if not sanity.get("all_applicable_pass"):
            blocking = sanity.get("blocking_codes", [])
            errors.append(f"Biological guardrails check failed: {blocking}")

        return (len(errors) == 0), traces, errors

    def delivery_policy(self, task: dict, validation: dict) -> dict:
        return {
            "allow_delivery": (validation.get("overall") == "verified"),
            "target_format": "dna",
            "delivery_tier": "authoritative",
        }
