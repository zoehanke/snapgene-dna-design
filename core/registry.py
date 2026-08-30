# -*- coding: utf-8 -*-
"""Task-kind registry and the strict router.

The router only:
1. looks up ``task_kind`` in this registry;
2. enforces the kind's required fields and semantic invariants.

It never guesses source roles, intervals, mutations or task kinds.
Unimplemented kinds are registered as ``not_implemented`` so a generic
planner can never become a silent fallback.
"""
from __future__ import annotations

from core.errors import TaskBlockedError, TaskValidationError
from core.task import require_resolved_selection


def _raise(code, message, missing_fields=None, questions=None):
    raise TaskValidationError(code, message, missing_fields=missing_fields,
                              questions=questions)


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
               "point_mutation requires operation.mutations; the old "
               "default 100:A is forbidden",
               missing_fields=["operation.mutations"])
    for index, mut in enumerate(mutations):
        for field in ("position_1based", "ref", "alt"):
            if field not in mut:
                _raise("MUTATION_SPEC_REQUIRED",
                       "mutation[%d] missing field: %s" % (index, field),
                       missing_fields=["operation.mutations.%d.%s"
                                       % (index, field)])


def _semantic_overlap_assembly(task):
    fragments = task.get("operation", {}).get("fragments") or []
    if not fragments:
        _raise("OVERLAP_FRAGMENTS_REQUIRED",
               "overlap_assembly requires operation.fragments with "
               "explicit source_id, interval_0based and order",
               missing_fields=["operation.fragments"])
    seen_orders = set()
    for index, frag in enumerate(fragments):
        if "source_id" not in frag or "interval_0based" not in frag                 or "order" not in frag:
            _raise("OVERLAP_FRAGMENTS_REQUIRED",
                   "fragment[%d] missing explicit source_id/"
                   "interval_0based/order" % index,
                   missing_fields=["operation.fragments.%d" % index])
        if frag["order"] in seen_orders:
            _raise("DUPLICATE_FRAGMENT_ORDER",
                   "duplicate fragment order %r" % frag["order"],
                   missing_fields=["operation.fragments"])
        seen_orders.add(frag["order"])
    overlap = task.get("operation", {}).get("overlap_length")
    if not isinstance(overlap, int) or overlap <= 0:
        _raise("OVERLAP_LENGTH_REQUIRED",
               "overlap_assembly requires a positive overlap_length",
               missing_fields=["operation.overlap_length"])


def _semantic_protein_fusion(task):
    op = task.get("operation", {})
    for key in ("partner5", "partner3"):
        partner = op.get(key) or {}
        if not partner.get("source_id"):
            _raise("FUSION_PARTNER_REQUIRED",
                   "protein_fusion requires operation.%s.source_id" % key,
                   missing_fields=["operation.%s.source_id" % key])
        if not partner.get("interval_0based"):
            _raise("FUSION_PARTNER_INTERVAL_REQUIRED",
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
    if not arms.get("left_arm") and not arms.get("right_arm"):
        _raise("INTEGRATION_ARMS_REQUIRED",
               "integration_donor requires explicit homology_arms",
               missing_fields=["operation.homology_arms"])
    locus = task.get("operation", {}).get("locus") or {}
    if not locus.get("source_id") or not locus.get("interval_0based"):
        _raise("INTEGRATION_LOCUS_REQUIRED",
               "integration_donor requires operation.locus with "
               "source_id and interval_0based",
               missing_fields=["operation.locus"])


def _semantic_gateway_recombination(task):
    op = task.get("operation", {})
    reaction = op.get("reaction")
    if reaction not in ("bp", "lr"):
        _raise("GATEWAY_REACTION_REQUIRED",
               "gateway_recombination requires operation.reaction "
               "bp|lr",
               missing_fields=["operation.reaction"])
    if op.get("stop_policy") not in ("stop", "no-stop"):
        _raise("GATEWAY_STOP_POLICY_REQUIRED",
               "gateway_recombination requires operation.stop_policy "
               "stop|no-stop",
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
    enzymes = op.get("vector_enzymes") or []
    if not isinstance(enzymes, list) or len(enzymes) not in (1, 2) or \
            not all(isinstance(e, str) and e for e in enzymes):
        _raise("RESTRICTION_ENZYMES_REQUIRED",
               "restriction_ligation requires operation.vector_enzymes "
               "with one or two enzyme names",
               missing_fields=["operation.vector_enzymes"])
    if op.get("orientation") not in ("forward", "reverse"):
        _raise("RESTRICTION_ORIENTATION_REQUIRED",
               "restriction_ligation requires operation.orientation "
               "forward|reverse",
               missing_fields=["operation.orientation"])
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
    known = set()
    for index, stage in enumerate(stages):
        if not stage.get("stage_id"):
            _raise("HIERARCHICAL_STAGE_ID_REQUIRED",
                   "stage[%d] missing stage_id" % index,
                   missing_fields=["operation.stages.%d.stage_id" % index])
        if stage["stage_id"] in known:
            _raise("DUPLICATE_STAGE_ID",
                   "duplicate stage_id %r" % stage["stage_id"])
        known.add(stage["stage_id"])
        fragments = stage.get("fragments") or []
        if not fragments:
            _raise("HIERARCHICAL_STAGE_FRAGMENTS_REQUIRED",
                   "stage %s requires fragments" % stage["stage_id"],
                   missing_fields=["operation.stages.%d.fragments" % index])
        if not isinstance(stage.get("overlap_length"), int) or \
                stage["overlap_length"] <= 0:
            _raise("HIERARCHICAL_STAGE_OVERLAP_REQUIRED",
                   "stage %s requires a positive overlap_length"
                   % stage["stage_id"],
                   missing_fields=["operation.stages.%d.overlap_length"
                                   % index])
        if stage.get("product_topology") not in ("linear", "circular"):
            _raise("HIERARCHICAL_STAGE_TOPOLOGY_REQUIRED",
                   "stage %s requires product_topology linear|circular"
                   % stage["stage_id"],
                   missing_fields=["operation.stages.%d.product_topology"
                                   % index])
        seen_orders = set()
        for frag in fragments:
            if "order" not in frag:
                _raise("HIERARCHICAL_FRAGMENT_ORDER_REQUIRED",
                       "stage %s fragment missing order" % stage["stage_id"])
            if frag["order"] in seen_orders:
                _raise("DUPLICATE_FRAGMENT_ORDER",
                       "stage %s duplicate fragment order" % stage["stage_id"])
            seen_orders.add(frag["order"])
            if "source_id" not in frag and "stage_id" not in frag:
                _raise("HIERARCHICAL_FRAGMENT_SOURCE_REQUIRED",
                       "stage %s fragment needs source_id or stage_id"
                       % stage["stage_id"])
    if task["product"]["topology"] != stages[-1]["product_topology"]:
        _raise("HIERARCHICAL_FINAL_TOPOLOGY_MISMATCH",
               "product.topology must equal the last stage topology",
               missing_fields=["product.topology"])


def _semantic_crispr_editing(task):
    op = task.get("operation", {})
    if not op.get("nuclease"):
        _raise("CRISPR_NUCLEASE_REQUIRED",
               "crispr_editing requires operation.nuclease",
               missing_fields=["operation.nuclease"])
    if not op.get("target_interval_0based"):
        _raise("CRISPR_TARGET_INTERVAL_REQUIRED",
               "crispr_editing requires operation.target_interval_0based",
               missing_fields=["operation.target_interval_0based"])
    donor = op.get("donor_strategy") or {}
    if donor.get("donor_source_id"):
        if not donor.get("replacement_interval_0based"):
            _raise("CRISPR_DONOR_INTERVAL_REQUIRED",
                   "donor_strategy.donor_source_id requires an explicit "
                   "replacement_interval_0based",
                   missing_fields=[
                       "operation.donor_strategy.replacement_interval_0based"])


def _semantic_not_implemented(task):
    _raise("TASK_KIND_NOT_IMPLEMENTED",
           "task_kind=%s is registered but has no dedicated planner yet; "
           "it must not fall back to a generic assembler"
           % task["task_kind"])


TASK_KINDS = {
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
            details={"task_kind": name, "registered": sorted(TASK_KINDS)})
    return TASK_KINDS[name]


def route_task(task):
    """Strict router: return the dedicated planner name or refuse."""
    kind = get_task_kind(task["task_kind"])
    if kind.get("status") == "not_implemented":
        _raise("TASK_KIND_NOT_IMPLEMENTED",
               "task_kind=%s is registered but has no dedicated planner yet"
               % task["task_kind"])
    return kind["planner"]
