# -*- coding: utf-8 -*-
"""agent/pipeline_agent.py - Liberated ReAct & Tool-Calling Agent for SnapGene DNA Design.

Replaces the legacy keyword/regex heuristic parser with a modern Agent workflow:
1. Inspects input plasmid files using atomic tools (giving the LLM full visibility).
2. Generates context-grounded planning prompt including Foundational Checklist & Lab Experience.
3. Accepts LLM-generated composite construction pipeline steps.
4. Deterministically executes, validates, and finalizes the construct into SnapGene (.dna/.gb).
"""
from __future__ import annotations

import json
import pathlib
from typing import Any

from evidence_trace.runtime import (observe, observe_value, traced_run, add_trace_arguments, trace_options, TraceStopped)

from core import execute, finalize, plan, validate, validate_construction_task
from core.guardrails.checklist import (
    get_biological_self_audit_checklist,
    quick_biological_sanity_check,
)
from core.tools import GET_TOOL_DEFINITIONS, inspect_dna, open_in_snapgene


def inspect_workspace_files(file_paths: list[str | pathlib.Path]) -> dict[str, Any]:
    """Inspect all input sequence files and extract structural features and metadata."""
    results = {}
    for p in file_paths:
        path_obj = pathlib.Path(p)
        if path_obj.exists():
            try:
                results[str(path_obj)] = inspect_dna(path_obj).analysis
            except Exception as exc:
                results[str(path_obj)] = {"error": str(exc)}
    return results


def build_agent_planning_prompt(
    user_request: str,
    file_paths: list[str | pathlib.Path],
    experience_rules: list[dict] | None = None,
) -> dict[str, Any]:
    """Assemble complete biological reasoning prompt for the LLM.

    Includes:
    - User goal
    - Ground truth file inspections (features, topology, lengths)
    - Available atomic tools
    - Foundational biological self-audit checklist
    - Relevant laboratory experience rules
    """
    file_inspections = inspect_workspace_files(file_paths)
    tools_def = GET_TOOL_DEFINITIONS()
    checklist = get_biological_self_audit_checklist()

    system_instruction = (
        "You are an expert Molecular Biologist and DNA Design Agent. "
        "Your task is to analyze the user's natural language construction goal, inspect the input plasmids, "
        "and formulate an ordered composite pipeline of atomic steps to synthesize the final plasmid.\n\n"
        "Guidelines:\n"
        "1. DO NOT guess coordinates; use the exact intervals from the inspected file features.\n"
        "2. Ensure all CDS coding regions remain in-frame (multiple of 3) without premature stop codons.\n"
        "3. When adding C-terminal tags, strip the 5' partner's stop codon and ensure the tag ends with a stop codon.\n"
        "4. Check for internal restriction site conflicts before choosing cloning enzymes.\n"
        "5. Output a structured JSON composite pipeline with 'steps' referencing atomic tools."
    )

    return {
        "system_instruction": system_instruction,
        "user_request": user_request,
        "file_inspections": file_inspections,
        "available_atomic_tools": tools_def,
        "foundational_checklist": checklist,
        "laboratory_experience_rules": experience_rules or [],
        "expected_output_format": {
            "task_id": "construct-name",
            "topology": "circular",
            "steps": [
                {"step_id": "step1", "tool": "simulate_pcr", "params": "..."},
                {"step_id": "step2", "tool": "simulate_overlap_assembly", "params": "..."}
            ]
        }
    }


@traced_run("pipeline")
def execute_agent_pipeline(
    task_id: str,
    pipeline_steps: list[dict[str, Any]],
    source_files: list[str | pathlib.Path | dict[str, Any]],
    product_topology: str = "circular",
    out_dir: str | pathlib.Path = "./build",
    auto_open_snapgene: bool = False,
    user_confirmed: bool = False,
    expected_components: list | None = None,
    forbidden_components: list | None = None,
    output_step: str | None = None,
    validation_requirements: list[str] | None = None,
    requirements: dict | None = None,
    original_request: str | None = None,
    result_kind: str = 'component',
) -> dict[str, Any]:
    """Execute actual steps; default to a sequence-design component, not proven preparation.

    Request result_kind='construct' for complete preparation and delivery checks.
    """
    out_path = pathlib.Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    sources = []
    for idx, f in enumerate(source_files):
        if isinstance(f, dict):
            sid = f.get("source_id") or f"src_{idx + 1}"
            raw_p = f.get("path") or f.get("file") or f.get("filepath")
            p = pathlib.Path(raw_p).resolve()
            role = f.get("role") or ("template" if idx == 0 else "donor_component")
            evidence = f.get("evidence") or {"source_evidence_class": "user-provided"}
            sources.append({
                "source_id": sid,
                "path": str(p),
                "role": role,
                "evidence": evidence,
            })
        else:
            p = pathlib.Path(f).resolve()
            sources.append({
                "source_id": f"src_{idx + 1}",
                "path": str(p),
                "role": "template" if idx == 0 else "donor_component",
                "evidence": {"source_evidence_class": "user-provided"},
            })

    from core.requirements import inherit_requirements
    from core.requirements import validate_validation_options
    validate_validation_options(validation_requirements,result_kind)
    if result_kind not in ('construct','component'):
        raise ValueError('Pipeline DNA delivery supports construct or component; use the step interface for QC/oligo/protocol subjects.')
    if result_kind=='construct':
        validation_requirements=list(dict.fromkeys(
            ['sequence_model','preparation_model','file','user_goal']+(validation_requirements or [])))
    context={'topology':product_topology}
    if expected_components is not None:context['expected_components']=expected_components
    if forbidden_components is not None:context['forbidden_components']=forbidden_components
    if original_request is not None:context['original_request']=original_request
    request=inherit_requirements([{'requirements':context}],requirements)
    task = {
        "schema_version": "construction-task-v1",
        "task_id": task_id,
        "revision": 1,
        "mode": "formal",
        "task_kind": "composite_pipeline",
        "expected_components": request.get('expected_components',[]),
        "forbidden_components": request.get('forbidden_components',[]),
        'requirements':request,'raw_request':request.get('original_request',''),
        "pipeline": {
            "steps": pipeline_steps,
            "output_step": output_step,
        },
        "sources": sources,
        "target": {},
        "operation": {},
        "product": {
            "topology": product_topology,
            "formats": ["gb", "fasta", "dna"],
        },
        "method_constraints": {},
        "approvals": {"user_confirmed_task": {"value": user_confirmed}},
        "assumptions": [],
        "provenance": [],
    }
    if validation_requirements is not None:
        task['validation_requirements'] = validation_requirements

    # 1. Validate
    vtask = observe("task", validate_construction_task, task)

    # 2. Plan
    vtask, p = observe("plan", plan, vtask)
    (out_path / "task.json").write_text(json.dumps(vtask, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (out_path / "plan.json").write_text(json.dumps(p, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    # 3. Execute
    exec_res = observe("execute", execute, vtask, p, out_path)

    # 4. Three-layer Validate
    report = observe("validate", validate, vtask, p, exec_res)

    preparation = []
    source_paths = {s["source_id"]: s["path"] for s in sources}
    for step in p.get("steps", []):
        outcome = step.get("details", {})
        details = outcome.get("analysis", {})
        if not isinstance(details, dict):
            continue
        if details.get("preparation"):
            preparation.extend(details["preparation"])
        elif step.get("tool") == "simulate_pcr" and details.get("template") and details.get("primers"):
            raw = step.get("params", {}).get("template_path_or_seq", step.get("params", {}).get("template"))
            template = source_paths.get(raw.lstrip("$"), details["template"]) if isinstance(raw, str) else details["template"]
            preparation.append({"id": step["step_id"], "method": "PCR", "template": template,
                                "primers": details["primers"], "product": outcome["products"][0]})
    # The same application-level writer serves both entry points. A failure
    # producing source primer maps occurs before authoritative promotion.
    from scripts.run_recipe import write_preparation_artifacts
    preparation_files = observe("preparation", write_preparation_artifacts, preparation, out_path)

    # Save the actual material products consumed by later steps. PCR export
    # alone omits digested fragments and other intermediates in real workflows.
    products_by_step = [
        (step, step.get("details", {}).get("products", []))
        for step in p.get("steps", [])
    ]
    used_versions = {
        ref.get("record_version")
        for _, products in products_by_step for product in products
        for ref in product.get("source_refs", [])
    }
    from core.models.molecule import as_molecule
    from core.tools.snapgene_io import export_snapgene
    saved_products = []
    for step_index, (step, products) in enumerate(products_by_step, 1):
        for product_index, product in enumerate(products):
            version = product.get("record_version")
            if version not in used_versions or version == p.get("selected_output_version"):
                continue
            files = observe("intermediate_export", export_snapgene,
                as_molecule(product), out_path / "intermediates",
                f"step_{step_index:03d}_product_{product_index:03d}").analysis
            saved_products.append({"step_id": step["step_id"], "product_index": product_index,
                                   "record_version": version, **files})
    preparation_files["step_products"] = saved_products

    delivery = None
    if report["overall"] == "verified":
        if user_confirmed:
            # 5. Authoritative Finalize
            from core.workflow_delivery import deliver_result
            steps=[row['execution'] for row in p['steps']]
            sources_map={source['source_id']:as_molecule(source.get('_resolved_path') or source['path']) for source in vtask['sources']}
            selected=output_step or pipeline_steps[-1]['step_id']
            head,_,tail=selected.lstrip('$').partition('.')
            product_index=int(tail.split('.')[1]) if tail.startswith('products.') else None
            delivery=observe('finalize',deliver_result,request,sources_map,steps,as_molecule(p['product_molecule']),out_path,
                required_scopes=vtask.get('validation_requirements',['sequence_model','file','user_goal']),
                result_kind=result_kind,output_step=head,product_index=product_index,
                provenance={'task_id':task_id,'task_sha256':p['task_sha256'],'plan_sha256':p['plan_sha256']})
            status = delivery["status"]
        else:
            status = "verified-candidate"
    else:
        status = report["overall"]

    # 6. Optional SnapGene launch
    snapgene_status = None
    if delivery and auto_open_snapgene:
        dna_file = out_path / "authoritative" / "construct.dna"
        if dna_file.exists():
            snapgene_status = open_in_snapgene(dna_file).analysis

    return {
        "status": status,
        "result_kind": result_kind,
        "scope_note": ('Actual preparation, sequence, files and declared goals are required.' if result_kind=='construct'
                       else 'Sequence-design component; preparation and experimental readiness are not certified.'),
        'requirements':request,'goal_coverage':delivery['goal_coverage'] if delivery else report['goal_coverage'],
        'task_completion':delivery['task_completion'] if delivery else report['task_completion'],
        "task_id": task_id,
        "product_length": len(p["product_sequence"]),
        "product_topology": product_topology,
        "validation_report": report,
        "delivery": delivery,
        "present_files": delivery.get('present_files', []) if delivery else [],
        "snapgene_status": snapgene_status,
        "authoritative_dir": str(out_path / "authoritative") if delivery else None,
        "task_file": str(out_path / "task.json"),
        "plan_file": str(out_path / "plan.json"),
        "preparation_files": preparation_files,
    }
