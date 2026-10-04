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
from core.models.molecule import Molecule, as_molecule
from core.tools.result import ToolResult
from core.tools import (
    export_snapgene,
    get_tool,
    TOOL_REGISTRY,
)


def _resolve_param_val(val, env, sources_map, results=None, analysis_steps=None):
    """Resolve JSON references to typed products or explicitly named analysis."""
    if isinstance(val, str):
        if val in sources_map:
            return sources_map[val]
        if not val.startswith('$'):
            return val
        reference = val[1:]
        if reference in sources_map:
            return sources_map[reference]
        head, _, tail = reference.partition('.')
        if head not in env:
            raise PlanningError('UNRESOLVED_STEP_REFERENCE', f'Unknown source or earlier step: {val}')
        result = env[head]
        if not tail:
            if not result.products:
                raise PlanningError('ANALYSIS_OUTPUT_REFERENCE', f'{head} has no molecular product; reference its analysis field')
            try:
                return result.only_product()
            except ValueError as exc:
                raise PlanningError('EXPLICIT_PRODUCT_REQUIRED', str(exc)) from exc
        current = result
        try:
            for field in tail.split('.'):
                if isinstance(current, ToolResult):
                    if field not in ('products', 'analysis', 'checks'):
                        raise KeyError(field)
                    current = getattr(current, field)
                elif isinstance(current, (list, tuple)):
                    current = current[int(field)]
                elif isinstance(current, Molecule):
                    raise KeyError('Material internals are not scalar references; pass the product object')
                else:
                    current = current[field]
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise PlanningError('INVALID_STEP_REFERENCE', f'Cannot resolve {val}') from exc
        return current
    if isinstance(val, list):
        return [_resolve_param_val(v, env, sources_map) for v in val]
    if isinstance(val, dict):
        return {k: _resolve_param_val(v, env, sources_map) for k, v in val.items()}
    return val


def _resolve_source_records(sources_map):
    resolved = {}
    for key, value in sources_map.items():
        try:
            resolved[key] = as_molecule(value, default_topology='linear')
        except Exception as exc:
            raise PlanningError('SOURCE_RESOLUTION_ERROR', f'Source {key} is invalid: {exc}') from exc
    return resolved


def run_pipeline_steps(steps, sources_map, output_step=None):
    """Carry one molecular contract without result-field guessing or recopying."""
    sources = _resolve_source_records(sources_map)
    env, rows = {}, []
    for step in steps:
        step_id, tool_name = step.get('step_id'), step.get('tool')
        if not step_id or step_id in env or step_id in sources:
            raise PlanningError('INVALID_STEP_ID', 'Step ids must be nonempty, unique and distinct from sources')
        specification = get_tool(tool_name)
        if specification is None:
            raise PlanningError('UNSUPPORTED_PIPELINE_TOOL', f'Unknown atomic tool: {tool_name}')
        if specification.category not in ('compute', 'inspect'):
            raise PlanningError('PIPELINE_SIDE_EFFECT', f'{tool_name} has side effects; use a file/output boundary')
        params = _resolve_param_val(step.get('params', {}), env, sources)
        try:
            result = specification.execute(**params)
        except Exception as exc:
            raise PlanningError('TOOL_EXECUTION_ERROR', f'{tool_name} failed in {step_id}: {exc}') from exc
        if not isinstance(result, ToolResult):
            raise PlanningError('INVALID_TOOL_RESULT', f'{tool_name} does not implement the molecular tool contract')
        env[step_id] = result
        rows.append({'step_id': step_id, 'tool': tool_name,
                     'output_length': len(result.products[0]) if len(result.products) == 1 else None,
                     'output_sha256': result.products[0].sequence_sha256 if len(result.products)==1 else None,
                     'product_count': len(result.products), 'details': result.to_dict(),
                     'params': copy.deepcopy(step.get('params', {}))})
    chosen = output_step or (steps[-1]['step_id'] if steps else None)
    if chosen is None:
        raise PlanningError('EMPTY_PIPELINE', 'Pipeline has no selected product')
    product = _resolve_param_val('$' + chosen.lstrip('$'), env, sources)
    if not isinstance(product, Molecule):
        raise PlanningError('NON_MOLECULAR_OUTPUT', 'The selected output must be a molecular product')
    return product, rows, env


def _preparation_check(product, rows, sources):
    """Follow actual product versions, not tool names or an expected final DNA."""
    records, checked = {}, set()
    roots = {as_molecule(source).record_version for source in sources.values()}
    for row in rows:
        details = row['details']
        for material in details['products']:
            records[material['record_version']] = material
        for material in details['analysis'].get('reaction_products',[]):
            records[material['record_version']]=material
        checked.update(c['subject_version'] for c in details['checks']
                       if c.get('scope')=='preparation_model' and c.get('status')=='PASSED')
        for preparation in details['analysis'].get('preparation', []):
            material = preparation['product']
            records[material['record_version']] = material
            # prepare_pcr_fragment owns and replay-checks these PCR products.
            if material.get('operation') == 'simulate_pcr':
                checked.add(material['record_version'])
    gaps=[]
    visited=set()
    def visit(version):
        if version in visited or version in roots:return
        visited.add(version)
        material=records.get(version)
        if material is not None and version not in checked:
            parents=[r['record_version'] for r in material['source_refs']]
            if len(parents)==1 and parents[0] in records:
                parent=records[parents[0]]
                if all(material.get(k)==parent.get(k) for k in ('sequence','topology','strandedness','ends')):
                    visit(parents[0])
                    return
        if material is None or version not in checked:
            gaps.append(version)
            return
        for reference in material['source_refs']:
            parent=reference['record_version']
            # A literal template/oligo declared in the real reaction input is
            # an input to that simulation, not proof of physical stock.
            if parent in records:visit(parent)
    visit(product.record_version)
    if not visited:gaps.append('selected supplied material has no reaction check')
    return {'status':'INCOMPLETE' if gaps else 'PASSED',
            'details':{'unestablished_versions':gaps,'reaction_versions':sorted(visited),
                       'scope':'computed reaction chain from declared inputs',
                       'physical_stock':'NOT_CHECKED','wet_lab':'NOT_CHECKED'}}


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
        final_record, step_records, _env = run_pipeline_steps(steps, sources_map, output_step)
        final_seq = str(final_record.seq)
        if not final_seq:
            raise PlanningError('NO_PRODUCT_SEQUENCE', 'Selected molecular product is empty')
        requested_topology = (task.get('product') or {}).get('topology')
        selected_output_version = final_record.record_version
        actual_topology = final_record.topology
        if actual_topology is None:
            if not requested_topology:
                raise PlanningError('UNKNOWN_PRODUCT_TOPOLOGY', 'Selected material has unknown topology; declare product topology')
            final_record = copy.deepcopy(final_record)
            final_record.annotations['topology'] = requested_topology
            if requested_topology == 'circular':
                if final_record.left_end is not None or final_record.right_end is not None:
                    raise PlanningError('UNSIMULATED_CIRCULARIZATION','Exposed ends require an actual circularization reaction')
            actual_topology = requested_topology
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
            "product_molecule": final_record.to_dict(),
            'selected_output_version': selected_output_version,
            "product_features": [feature_to_dict(f, len(final_record)) for f in final_record.features] if isinstance(final_record, SeqRecord) else [],
            "product_sequence_sha256": hashlib.sha256(final_seq.encode("utf-8")).hexdigest().upper(),
            "steps": step_records,
            "output_step": output_step,
            "expected_components": task.get("expected_components", []),
            "forbidden_components": task.get("forbidden_components", []),
            "sources": task.get("sources", []),
            'preparation_check': _preparation_check(final_record,step_records,sources_map),
        }

    def execute(self, task: dict, plan: dict, out_dir: pathlib.Path) -> dict:
        if 'product_molecule' not in plan:
            raise PlanningError('PLAN_REGENERATION_REQUIRED','Regenerate the legacy plan with the complete molecular product')
        inter = out_dir / "intermediate"
        inter.mkdir(parents=True, exist_ok=True)

        prod_seq = plan["product_sequence"]
        topo = plan.get("product_topology", "circular")
        name = task.get("task_id", "construct")

        exported = export_snapgene(
            record_or_seq=as_molecule(plan["product_molecule"]),
            out_dir=inter,
            filename_base=name,
            topology=topo,
            features=task.get("features"),
        ).analysis

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
        final_product, _, _ = run_pipeline_steps(steps, sources_map, task.get("pipeline", {}).get("output_step"))
        return str(final_product.seq).upper()

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
        from core.models.molecule import as_molecule
        target_version = as_molecule(plan.get('product_molecule',product_record)).record_version
        for step in plan.get('steps', []):
            for check in step.get('details', {}).get('checks', []):
                if check.get('subject_version') in (target_version,plan.get('selected_output_version')):
                    traces.append({'check':'scoped_program_check','result':check})
                    if check.get('status') not in ('PASSED','NOT_APPLICABLE'):
                        errors.append(f"PROGRAM_CHECK_FAILED: {check.get('name')} on the selected material")
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
