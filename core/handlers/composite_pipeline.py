# -*- coding: utf-8 -*-
"""core/handlers/composite_pipeline.py - Composite Pipeline Task Handler.

Liberates the DNA design agent from rigid single-task templates by allowing
arbitrary composite, multi-step construction workflows orchestrated through
atomic biological tools.
"""
from __future__ import annotations

import hashlib
import pathlib
from typing import Any

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from core.errors import PlanningError, TaskValidationError
from core.guardrails.checklist import quick_biological_sanity_check
from core.handlers.base import TaskHandler
from core.tools import (
    annotate_feature,
    check_reading_frame,
    export_snapgene,
    extract_subsequence,
    find_restriction_sites,
    fuse_in_frame,
    get_feature,
    inspect_dna,
    mutate_sequence,
    reverse_complement,
    silent_mutation_remove_site,
    simulate_digest_ligation,
    simulate_overlap_assembly,
    simulate_pcr,
    translate_dna,
)


def _resolve_param_val(val: Any, env: dict[str, Any], sources_map: dict[str, str]) -> Any:
    """Resolve step parameter value referencing source_id or previous step_id output."""
    if isinstance(val, str):
        if val.startswith("$"):
            var_name = val[1:]
            if var_name in env:
                return env[var_name]
            if var_name in sources_map:
                return sources_map[var_name]
        elif val in sources_map:
            return sources_map[val]
    elif isinstance(val, list):
        return [_resolve_param_val(item, env, sources_map) for item in val]
    elif isinstance(val, dict):
        return {k: _resolve_param_val(v, env, sources_map) for k, v in val.items()}
    return val


def run_pipeline_steps(steps: list[dict], sources_map: dict[str, str]) -> tuple[str, list[dict], dict[str, Any]]:
    """Execute pipeline steps sequentially in an in-memory environment."""
    env: dict[str, Any] = {}
    step_records: list[dict] = []

    for step in steps:
        step_id = step.get("step_id")
        tool = step.get("tool")
        raw_params = step.get("params", {})
        params = _resolve_param_val(raw_params, env, sources_map)

        if tool == "extract_subsequence":
            res = extract_subsequence(
                file_path_or_record=params["source"],
                start=params["start"],
                end=params["end"],
                strand=params.get("strand", 1),
                topology=params.get("topology", "linear"),
                wraps_origin=params.get("wraps_origin", True),
            )
            out_seq = res["sequence"]
        elif tool == "simulate_pcr":
            res = simulate_pcr(
                template_path_or_seq=params["template"],
                f_primer=params["f_primer"],
                r_primer=params["r_primer"],
                topology=params.get("topology", "linear"),
            )
            out_seq = res["amplicon"]
        elif tool == "fuse_in_frame":
            res = fuse_in_frame(
                partner5_seq=params["partner5"],
                partner3_seq=params["partner3"],
                linker_seq=params.get("linker", ""),
                strip_p5_stop=params.get("strip_p5_stop", True),
                add_terminal_stop=params.get("add_terminal_stop", True),
            )
            out_seq = res["fusion_sequence"]
        elif tool == "silent_mutation_remove_site":
            res = silent_mutation_remove_site(
                cds_seq=params["cds_seq"],
                enzyme_name=params["enzyme"],
                frame_offset=params.get("frame_offset", 0),
            )
            out_seq = res["mutated_seq"]
        elif tool == "mutate_sequence":
            res = mutate_sequence(
                dna_seq=params["dna_seq"],
                mutations=params["mutations"],
            )
            out_seq = res["sequence"]
        elif tool == "simulate_overlap_assembly":
            res = simulate_overlap_assembly(
                fragments=params["fragments"],
                min_overlap=params.get("min_overlap", 15),
                circular=params.get("circular", True),
            )
            out_seq = res["product_sequence"]
        elif tool == "simulate_digest_ligation":
            res = simulate_digest_ligation(
                vector_source=params["vector"],
                insert_source=params["insert"],
                vector_enzymes=params["vector_enzymes"],
                insert_enzymes=params.get("insert_enzymes"),
                orientation=params.get("orientation", "forward"),
            )
            out_seq = res["product_sequence"]
        elif tool == "reverse_complement":
            out_seq = reverse_complement(params["seq"])
            res = {"sequence": out_seq}
        else:
            raise PlanningError(
                "UNSUPPORTED_PIPELINE_TOOL",
                f"Atomic tool '{tool}' is not recognized in composite pipeline"
            )

        env[step_id] = out_seq
        step_records.append({
            "step_id": step_id,
            "tool": tool,
            "output_length": len(out_seq),
            "output_sha256": hashlib.sha256(out_seq.encode("utf-8")).hexdigest().upper(),
            "details": res,
        })

    final_seq = out_seq if steps else ""
    return final_seq, step_records, env


class CompositePipelineHandler(TaskHandler):
    """General-purpose TaskHandler executing multi-step composite construction workflows."""

    kind = "composite_pipeline"
    handler_id = "handler-composite-pipeline-v1"
    handler_version = "1.0.0"
    method_maturity = "validated"
    default_topology = "circular"

    def validate_contract(self, task: dict) -> None:
        pipe = task.get("pipeline")
        if not pipe:
            raise TaskValidationError("PIPELINE_REQUIRED", "composite_pipeline task requires 'pipeline' block")
        steps = pipe.get("steps")
        if not steps or not isinstance(steps, list):
            raise TaskValidationError("PIPELINE_STEPS_REQUIRED", "pipeline must contain a non-empty list of steps")

    def clarify(self, task: dict) -> list[dict]:
        return task.get("pipeline", {}).get("questions", [])

    def _sources_map(self, task: dict) -> dict[str, str]:
        smap = {}
        for s in task.get("sources", []):
            sid = s.get("source_id")
            resolved = s.get("_resolved_path") or s.get("filepath")
            if sid and resolved:
                smap[sid] = str(resolved)
        return smap

    def plan(self, task: dict) -> dict:
        self.validate_contract(task)
        sources_map = self._sources_map(task)
        steps = task["pipeline"]["steps"]

        final_seq, step_records, _env = run_pipeline_steps(steps, sources_map)
        topo = task.get("product", {}).get("topology") or "circular"

        return {
            "task_kind": self.kind,
            "product_topology": topo,
            "product_sequence": final_seq,
            "product_sequence_sha256": hashlib.sha256(final_seq.encode("utf-8")).hexdigest().upper(),
            "steps": step_records,
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
            record_or_seq=prod_seq,
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
        final_seq, _, _ = run_pipeline_steps(steps, sources_map)
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

        if len(product_seq) == 0:
            errors.append("Product sequence is empty")

        exp_sha = plan.get("product_sequence_sha256")
        act_sha = hashlib.sha256(product_seq.encode("utf-8")).hexdigest().upper()
        if exp_sha and act_sha != exp_sha:
            errors.append(f"Sequence SHA256 mismatch: expected {exp_sha}, got {act_sha}")

        # Run lightweight biological sanity check
        sanity = quick_biological_sanity_check(product_seq)
        traces.append({
            "check": "quick_biological_sanity_check",
            "result": sanity,
        })

        return (len(errors) == 0), traces, errors

    def delivery_policy(self, task: dict, validation: dict) -> dict:
        return {
            "allow_delivery": (validation.get("overall") == "verified"),
            "target_format": "dna",
            "delivery_tier": "authoritative",
        }
