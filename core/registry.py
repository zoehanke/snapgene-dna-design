# -*- coding: utf-8 -*-
"""Task-kind registry and the strict router (v0.9.1-dev2).

The router only:
1. looks up ``task_kind`` in this registry / handlers;
2. enforces the kind's required fields and semantic invariants.

It never guesses source roles, intervals, mutations or task kinds.
Unimplemented kinds raise TaskBlockedError so a generic planner can never
become a silent fallback.
"""
from __future__ import annotations

from core.errors import TaskBlockedError, TaskValidationError
from core.handlers import HANDLERS, TaskHandler
from core.task import require_resolved_selection


def _raise(code, message, missing_fields=None, questions=None):
    raise TaskValidationError(code, message, missing_fields=missing_fields,
                              questions=questions)


def get_task_handler(name: str) -> TaskHandler:
    """Retrieve the registered TaskHandler for task_kind."""
    if name not in HANDLERS:
        raise TaskBlockedError(
            "TASK_KIND_NOT_REGISTERED",
            "unknown task_kind %r; no generic fallback is allowed" % name,
            details={"task_kind": name, "registered": sorted(HANDLERS)},
        )
    return HANDLERS[name]


def list_task_handlers() -> dict[str, TaskHandler]:
    """Return all registered task handlers."""
    return dict(HANDLERS)


NEAR_FULL_RATIO = 0.95


def _semantic_component_amplification(task):
    require_resolved_selection(task)
    if task["product"]["topology"] != "linear":
        _raise("PRODUCT_TOPOLOGY_MUST_BE_LINEAR",
               "component_amplification produces a linear component",
               missing_fields=["product.topology"])
    selection = task["target"]["selection"]
    if selection.get("kind") == "interval":
        interval = selection.get("interval_0based") or []
        if len(interval) == 2:
            from Bio import SeqIO
            source = [s for s in task["sources"] if s["role"] == "template"][0]
            record = SeqIO.read(source["_resolved_path"], "genbank"
                                if source["_resolved_path"].lower().endswith(
                                    (".gb", ".gbk")) else "fasta")
            a, b = int(interval[0]), int(interval[1])
            seq = str(record.seq)
            if a == b and source.get("topology") == "linear":
                approval = task.get("approvals", {}).get("whole_record") or {}
                if not approval.get("value"):
                    _raise("ZERO_WIDTH_INTERVAL_REJECTED",
                           "zero-width interval [%d,%d) rejected on linear record" % (a, b),
                           missing_fields=["target.selection.interval_0based"])
            if a > b and source.get("topology", "linear") == "linear":
                _raise("REVERSE_INTERVAL_REJECTED",
                       "reverse interval [%d,%d) rejected on linear record" % (a, b),
                       missing_fields=["target.selection.interval_0based"])
            if a <= b:
                selected_len = b - a
            else:
                selected_len = (len(seq) - a) + b
            if selected_len >= len(seq):
                approval = task.get("approvals", {}).get("whole_record") or {}
                if not approval.get("value"):
                    _raise("WHOLE_TEMPLATE_SELECTED_FOR_COMPONENT",
                           "component selection covers the whole template; "
                           "user must explicitly approve whole-record use",
                           missing_fields=["target.selection.interval_0based"])
            elif len(seq) and selected_len >= NEAR_FULL_RATIO * len(seq):
                approval = (task.get("approvals", {})
                            .get("near_whole_record") or {})
                if not approval.get("value"):
                    _raise("NEAR_FULL_TEMPLATE_SELECTED_FOR_COMPONENT",
                           "component selection covers %.1f%% of the "
                           "template; near-full-length selection risks "
                           "carrying backbone elements and requires "
                           "explicit approval"
                           % (100.0 * selected_len / len(seq)),
                           missing_fields=["target.selection.interval_0based"])


def _semantic_plasmid_replace(task):
    require_resolved_selection(task, "REPLACE_INTERVAL_REQUIRED")
    replace = task.get("operation", {}).get("replace") or {}
    if "interval_0based" not in replace:
        _raise("REPLACE_INTERVAL_REQUIRED",
               "plasmid_replace requires operation.replace.interval_0based",
               missing_fields=["operation.replace.interval_0based"])
    if not replace.get("replacement_source_id"):
        _raise("REPLACEMENT_SOURCE_REQUIRED",
               "plasmid_replace requires "
               "operation.replace.replacement_source_id",
               missing_fields=["operation.replace.replacement_source_id"])


def _semantic_plasmid_insert(task):
    insert = task.get("operation", {}).get("insert") or {}
    if "boundary_0based" not in insert:
        _raise("INSERT_BOUNDARY_REQUIRED",
               "plasmid_insert requires operation.insert.boundary_0based",
               missing_fields=["operation.insert.boundary_0based"])
    if not insert.get("insert_source_id"):
        _raise("INSERT_SOURCE_REQUIRED",
               "plasmid_insert requires operation.insert.insert_source_id",
               missing_fields=["operation.insert.insert_source_id"])
    if not insert.get("interval_0based"):
        _raise("INSERT_INTERVAL_REQUIRED",
               "plasmid_insert requires an explicit insert interval; "
               "whole-file defaults are forbidden",
               missing_fields=["operation.insert.interval_0based"])


def _semantic_point_mutation(task):
    mutations = task.get("operation", {}).get("mutations") or []
    if not mutations:
        _raise("MUTATION_SPEC_REQUIRED",
               "point_mutation requires operation.mutations; default 100:A "
               "is forbidden",
               missing_fields=["operation.mutations"],
               questions=["要在哪个位点引入什么突变？请提供 position_1based, "
                          "ref 和 alt"])
    for m in mutations:
        for field in ("position_1based", "ref", "alt"):
            if field not in m:
                _raise("MUTATION_SPEC_INCOMPLETE",
                       "mutation entry missing %s" % field,
                       missing_fields=["operation.mutations.%s" % field])


def _semantic_overlap_assembly(task):
    frags = task.get("operation", {}).get("fragments") or []
    if len(frags) < 2:
        _raise("OVERLAP_FRAGMENTS_REQUIRED",
               "overlap_assembly requires at least two fragments in "
               "operation.fragments",
               missing_fields=["operation.fragments"])
    for i, frag in enumerate(frags):
        if not frag.get("source_id"):
            _raise("FRAGMENT_SOURCE_REQUIRED",
                   "fragment %d missing source_id" % i,
                   missing_fields=["operation.fragments.%d.source_id" % i])
        if not frag.get("interval_0based"):
            _raise("OVERLAP_FRAGMENTS_REQUIRED",
                   "fragment %d missing interval_0based; whole-file "
                   "defaults are forbidden",
                   missing_fields=["operation.fragments.%d.interval_0based"
                                   % i])


def _semantic_protein_fusion(task):
    op = task.get("operation") or {}
    for key in ("partner5", "partner3"):
        spec = op.get(key) or {}
        if not spec.get("source_id"):
            _raise("FUSION_PARTNER_REQUIRED",
                   "protein_fusion requires operation.%s.source_id" % key,
                   missing_fields=["operation.%s.source_id" % key])
        if not spec.get("interval_0based"):
            _raise("FUSION_INTERVAL_REQUIRED",
                   "protein_fusion requires an explicit "
                   "operation.%s.interval_0based" % key,
                   missing_fields=["operation.%s.interval_0based" % key])
    if op.get("stop_policy") not in ("stop", "no-stop"):
        _raise("FUSION_STOP_POLICY_REQUIRED",
               "protein_fusion requires operation.stop_policy "
               "stop|no-stop",
               missing_fields=["operation.stop_policy"],
               questions=["融合产物是否需要终止密码子（stop/no-stop）？"])
    linker = op.get("linker") or {}
    if linker.get("dna") is not None and \
            len(str(linker["dna"])) % 3 != 0:
        _raise("FUSION_LINKER_NOT_IN_FRAME",
               "linker DNA length must be a multiple of 3",
               missing_fields=["operation.linker.dna"])


def _semantic_integration_donor(task):
    require_resolved_selection(task, "COMPONENT_BOUNDARY_REQUIRED")
    if task["product"]["topology"] != "linear":
        _raise("PRODUCT_TOPOLOGY_MUST_BE_LINEAR",
               "integration_donor produces a linear donor",
               missing_fields=["product.topology"])
    arms = task.get("operation", {}).get("homology_arms") or {}
    single_arm_approved = bool(task.get("approvals", {}).get("single_arm_donor", {}).get("value"))
    if not single_arm_approved and not (arms.get("left_arm") and arms.get("right_arm")):
        locus = task.get("operation", {}).get("locus") or {}
        if not (locus.get("source_id") and locus.get("interval_0based") and arms.get("arm_length")):
            _raise("INTEGRATION_ARMS_REQUIRED",
                   "integration_donor requires both left_arm and right_arm homology arms by default",
                   missing_fields=["operation.homology_arms"])
    locus = task.get("operation", {}).get("locus") or {}
    if locus.get("interval_0based"):
        loc_int = locus.get("interval_0based")
        if len(loc_int) == 2 and loc_int[0] > loc_int[1]:
            _raise("REVERSE_INTERVAL_REJECTED",
                   "locus interval cannot be reverse on linear chromosome",
                   missing_fields=["operation.locus.interval_0based"])


def _semantic_gateway_recombination(task):
    op = task.get("operation", {})
    reaction = op.get("reaction")
    if reaction not in ("bp", "lr"):
        _raise("GATEWAY_REACTION_REQUIRED",
               "gateway_recombination requires operation.reaction "
               "bp|lr",
               missing_fields=["operation.reaction"])
    if op.get("stop_policy") not in ("stop", "no-stop", "require_stop"):
        _raise("GATEWAY_STOP_POLICY_REQUIRED",
               "gateway_recombination requires operation.stop_policy "
               "stop|no-stop|require_stop",
               missing_fields=["operation.stop_policy"])
    if reaction == "lr":
        if not op.get("entry_source_id") or \
                not op.get("destination_source_id"):
            _raise("GATEWAY_LR_SOURCES_REQUIRED",
                   "gateway lr requires operation.entry_source_id and "
                   "operation.destination_source_id",
                   missing_fields=["operation.entry_source_id",
                                   "operation.destination_source_id"])
    else:
        if not op.get("entry_source_id") or \
                not op.get("donor_vector_source_id"):
            _raise("GATEWAY_BP_SOURCES_REQUIRED",
                   "gateway bp requires operation.entry_source_id "
                   "(attB insert) and operation.donor_vector_source_id "
                   "(attP donor vector)",
                   missing_fields=["operation.entry_source_id",
                                   "operation.donor_vector_source_id"])


def _semantic_restriction_ligation(task):
    op = task.get("operation", {})
    if not op.get("vector_source_id") or not op.get("insert_source_id"):
        _raise("RESTRICTION_SOURCES_REQUIRED",
               "restriction_ligation requires operation.vector_source_id "
               "and operation.insert_source_id",
               missing_fields=["operation.vector_source_id",
                               "operation.insert_source_id"])
    enzymes = op.get("vector_enzymes") or op.get("enzymes") or []
    if not isinstance(enzymes, list) or len(enzymes) not in (1, 2) or \
            not all(isinstance(e, str) and e for e in enzymes):
        _raise("RESTRICTION_ENZYMES_REQUIRED",
               "restriction_ligation requires operation.vector_enzymes "
               "with one or two enzyme names",
               missing_fields=["operation.vector_enzymes"])
    if task["product"]["topology"] != "circular":
        _raise("PRODUCT_TOPOLOGY_MUST_BE_CIRCULAR",
               "restriction_ligation produces a circular product",
               missing_fields=["product.topology"])


def _semantic_hierarchical_assembly(task):
    stages = task.get("operation", {}).get("stages") or []
    if not stages:
        _raise("HIERARCHICAL_STAGES_REQUIRED",
               "hierarchical_assembly requires operation.stages",
               missing_fields=["operation.stages"])
    final_topo = task.get("product", {}).get("topology")
    if final_topo and stages:
        last_stage_topo = stages[-1].get("product_topology")
        if last_stage_topo and last_stage_topo != final_topo:
            _raise("HIERARCHICAL_FINAL_TOPOLOGY_MISMATCH",
                   f"final stage topology ({last_stage_topo}) does not match product topology ({final_topo})",
                   missing_fields=["product.topology"])


def _semantic_crispr_editing(task):
    op = task.get("operation", {})
    if not op.get("nuclease"):
        _raise("CRISPR_NUCLEASE_REQUIRED",
               "crispr_editing requires operation.nuclease",
               missing_fields=["operation.nuclease"])


def _semantic_composite_pipeline(task):
    pipe = task.get("pipeline")
    if not pipe or not pipe.get("steps"):
        _raise("PIPELINE_STEPS_REQUIRED",
               "composite_pipeline requires a non-empty pipeline.steps list",
               missing_fields=["pipeline.steps"])


TASK_KINDS = {
    "composite_pipeline": {
        "planner": "composite_pipeline",
        "maturity": "validated",
        "required_fields": ["pipeline.steps"],
        "missing_code": "PIPELINE_STEPS_REQUIRED",
        "semantic_checks": _semantic_composite_pipeline,
    },
    "pipeline": {
        "planner": "composite_pipeline",
        "maturity": "validated",
        "required_fields": ["pipeline.steps"],
        "missing_code": "PIPELINE_STEPS_REQUIRED",
        "semantic_checks": _semantic_composite_pipeline,
    },
    "component_amplification": {
        "planner": "component_amplification",
        "maturity": "validated",
        "required_fields": ["target.selection"],
        "missing_code": "COMPONENT_BOUNDARY_REQUIRED",
        "semantic_checks": _semantic_component_amplification,
    },
    "plasmid_replace": {
        "planner": "plasmid_replace",
        "maturity": "validated",
        "required_fields": ["target.selection"],
        "missing_code": "REPLACE_INTERVAL_REQUIRED",
        "semantic_checks": _semantic_plasmid_replace,
    },
    "plasmid_insert": {
        "planner": "plasmid_insert",
        "maturity": "validated",
        "required_fields": ["target.source_id"],
        "missing_code": "TASK_REQUIRED_FIELD_MISSING",
        "semantic_checks": _semantic_plasmid_insert,
    },
    "point_mutation": {
        "planner": "point_mutation",
        "maturity": "validated",
        "required_fields": ["target.source_id"],
        "missing_code": "MUTATION_SPEC_REQUIRED",
        "semantic_checks": _semantic_point_mutation,
    },
    "overlap_assembly": {
        "planner": "overlap_assembly",
        "maturity": "validated",
        "required_fields": ["operation.fragments"],
        "missing_code": "OVERLAP_FRAGMENTS_REQUIRED",
        "semantic_checks": _semantic_overlap_assembly,
    },
    "protein_fusion": {
        "planner": "protein_fusion",
        "maturity": "validated",
        "required_fields": ["operation.partner5"],
        "missing_code": "FUSION_PARTNER_REQUIRED",
        "semantic_checks": _semantic_protein_fusion,
    },
    "integration_donor": {
        "planner": "integration_donor",
        "maturity": "validated",
        "required_fields": ["target.selection"],
        "missing_code": "COMPONENT_BOUNDARY_REQUIRED",
        "semantic_checks": _semantic_integration_donor,
    },
    "gateway_recombination": {
        "planner": "gateway_recombination",
        "maturity": "validated",
        "required_fields": ["operation.reaction"],
        "missing_code": "GATEWAY_REACTION_REQUIRED",
        "semantic_checks": _semantic_gateway_recombination,
    },
    "restriction_ligation": {
        "planner": "restriction_ligation",
        "maturity": "experimental",
        "required_fields": ["operation.vector_source_id"],
        "missing_code": "RESTRICTION_SOURCES_REQUIRED",
        "semantic_checks": _semantic_restriction_ligation,
    },
    "hierarchical_assembly": {
        "planner": "hierarchical_assembly",
        "maturity": "validated",
        "required_fields": ["operation.stages"],
        "missing_code": "HIERARCHICAL_STAGES_REQUIRED",
        "semantic_checks": _semantic_hierarchical_assembly,
    },
    "crispr_editing": {
        "planner": "crispr_editing",
        "maturity": "experimental",
        "required_fields": ["operation.nuclease"],
        "missing_code": "CRISPR_NUCLEASE_REQUIRED",
        "semantic_checks": _semantic_crispr_editing,
    },
}


def get_task_kind(name):
    if name not in TASK_KINDS:
        raise TaskBlockedError(
            "TASK_KIND_NOT_REGISTERED",
            "unknown task_kind %r; no generic fallback is allowed" % name,
            details={"task_kind": name, "registered": sorted(TASK_KINDS)},
        )
    return TASK_KINDS[name]


def route_task(task):
    """Strict router: return the dedicated planner name or refuse."""
    kind = get_task_kind(task["task_kind"])
    return kind["planner"]
