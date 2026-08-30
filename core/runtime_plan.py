# -*- coding: utf-8 -*-
"""Dedicated planners.  Each planner emits an explicit, deterministic plan
or raises a structured refusal.  No planner guesses source roles, intervals,
mutations or operation types."""
from __future__ import annotations

import pathlib
import uuid

from Bio import SeqIO
from Bio.Seq import Seq

from core.errors import PlanningError
from core.registry import NEAR_FULL_RATIO, get_task_kind
from core.task import canonical_json, sha256_text, task_sha256


def _load_record(task_source):
    from core.task import read_record
    return read_record(task_source["_resolved_path"])


def _source_by_role(task, role):
    matches = [s for s in task["sources"] if s["role"] == role]
    if not matches:
        raise PlanningError("SOURCE_ROLE_MISSING",
                            "no source with role=%s" % role,
                            missing_fields=["sources"],
                            questions=["哪个文件承担角色 %s？" % role])
    return matches[0]


def _arc(record, start0, end0):
    seq = str(record.seq)
    n = len(seq)
    start0 = int(start0) % n
    end0 = int(end0) % n
    if start0 == end0:
        # whole-record selection is returned in full so callers can apply
        # the explicit whole-template guard; zero-length intervals other
        # than the trivial [0,0] are rejected by interval validation.
        return seq
    if start0 < end0:
        return seq[start0:end0]
    return seq[start0:] + seq[:end0]


def _resolve_selection(task, record):
    """Return {'interval_0based':[a,b), 'strand':s, 'feature':...,
    'extracted_sequence':..., 'resolution_evidence':[...]} or raise a
    structured refusal.  Negative-strand selections yield the reverse
    complement of the stored strand, matching the biological component."""
    selection = task["target"].get("selection") or {}
    if selection.get("kind") == "interval":
        interval = selection.get("interval_0based")
        if not isinstance(interval, list) or len(interval) != 2:
            raise PlanningError(
                "COMPONENT_BOUNDARY_REQUIRED",
                "interval selection requires interval_0based [start, end)",
                missing_fields=["target.selection.interval_0based"])
        a, b = int(interval[0]), int(interval[1])
        n = len(record)
        if a < 0 or b < 0 or a > n or b > n:
            raise PlanningError("INTERVAL_OUT_OF_RANGE",
                                "interval [%d,%d) outside record length %d"
                                % (a, b, n),
                                missing_fields=["target.selection.interval_0based"])
        topo = record.annotations.get("topology", "linear")
        if a == b and topo == "circular":
            raise PlanningError(
                "WHOLE_TEMPLATE_SELECTED_FOR_COMPONENT",
                "a zero-width wrap interval selects the whole circular "
                "template; this is forbidden for component operations")
        strand = int(selection.get("strand", 1))
        extracted = _arc(record, a, b)
        if strand == -1:
            extracted = str(Seq(extracted).reverse_complement())
        return {
            "interval_0based": [a, b],
            "strand": strand,
            "feature": None,
            "extracted_sequence": extracted,
            "resolution_evidence": [
                {"kind": "user-interval", "interval_0based": [a, b]}],
        }
    if selection.get("kind") == "feature":
        candidates = []
        wanted_id = selection.get("feature_id")
        wanted_name = selection.get("feature_name")
        for feature in record.features:
            q = feature.qualifiers
            fid = (q.get("id") or [None])[0]
            labels = list(q.get("label") or []) + list(q.get("note") or [])
            fname = (q.get("name") or q.get("gene") or [None])[0]
            if wanted_id and fid == wanted_id:
                candidates.append(feature)
            elif wanted_name and (fname == wanted_name or
                                  wanted_name in labels or
                                  feature.type == wanted_name):
                candidates.append(feature)
        if not candidates:
            available = sorted({str((f.qualifiers.get("label") or
                                     f.qualifiers.get("gene") or
                                     [f.type])[0]) for f in record.features
                                if f.type != "source"})
            raise PlanningError(
                "COMPONENT_BOUNDARY_REQUIRED",
                "feature not found; whole-record default is forbidden",
                missing_fields=["target.selection.feature_id"],
                questions=["目标组件对应哪个 feature？候选：%s"
                           % ", ".join(available[:12])],
                details={"candidates": available})
        if len(candidates) > 1:
            raise PlanningError(
                "AMBIGUOUS_FEATURE_SELECTION",
                "multiple features match the requested component",
                missing_fields=["target.selection.feature_id"],
                questions=["请给出唯一 feature id 或坐标区间。"],
                details={"candidates": [
                    {"type": f.type, "location": str(f.location)}
                    for f in candidates]})
        feature = candidates[0]
        strand = int(getattr(feature.location, "strand", 1) or 1)
        parts = list(getattr(feature.location, "parts",
                             [feature.location]))
        span = [min(int(p.start) for p in parts),
                max(int(p.end) for p in parts)]
        # BioPython extract() resolves compound locations and applies the
        # reverse complement for minus-strand features.
        extracted = str(feature.extract(record).seq)
        return {
            "interval_0based": span,
            "strand": strand,
            "feature": {
                "type": feature.type,
                "location": str(feature.location),
                "labels": (list(feature.qualifiers.get("label") or []) +
                           list(feature.qualifiers.get("gene") or [])),
            },
            "extracted_sequence": extracted,
            "resolution_evidence": [
                {"kind": "computed-unique-feature",
                 "interval_0based": span,
                 "strand": strand,
                 "feature_type": feature.type}],
        }
    raise PlanningError(
        "COMPONENT_BOUNDARY_REQUIRED",
        "selection.kind must be feature or interval",
        missing_fields=["target.selection.kind"])


def _whole_template_guard(task, record, selected_length):
    if task["task_kind"] != "component_amplification":
        return
    n = len(record)
    if n == 0:
        return
    if selected_length >= n:
        approval = task.get("approvals", {}).get("whole_record") or {}
        if not approval.get("value"):
            raise PlanningError(
                "WHOLE_TEMPLATE_SELECTED_FOR_COMPONENT",
                "component selection covers the whole template; user must "
                "explicitly approve whole-record use",
                missing_fields=["target.selection.interval_0based"],
                questions=["目标组件边界是什么 feature 或坐标区间？"])
    elif selected_length >= NEAR_FULL_RATIO * n:
        approval = task.get("approvals", {}).get("near_whole_record") or {}
        if not approval.get("value"):
            raise PlanningError(
                "NEAR_FULL_TEMPLATE_SELECTED_FOR_COMPONENT",
                "component selection covers %.1f%% of the template; "
                "near-full-length selection risks carrying backbone "
                "elements and requires explicit approval"
                % (100.0 * selected_length / n),
                missing_fields=["target.selection.interval_0based"],
                questions=["为什么需要近乎全长模板作为组件？哪些骨架元件"
                           "必须排除？请给出更小的组件边界或明确批准。"])


def _record_id(path):
    try:
        record = SeqIO.read(str(path), "genbank" if
                            str(path).lower().endswith((".gb", ".gbk"))
                            else "fasta")
        return record.id or record.name or None
    except Exception:
        return None


def _plan_common(task):
    from core.registry import route_task
    route_task(task)
    kind = get_task_kind(task["task_kind"])
    plan = {
        "schema_version": "construction-plan-v1",
        "plan_id": "plan-" + uuid.uuid4().hex[:12],
        "task_id": task["task_id"],
        "task_revision": task["revision"],
        "task_sha256": task_sha256(task),
        "task_kind": task["task_kind"],
        "method_maturity": kind.get("maturity", "validated"),
        "sources": [{
            "source_id": s["source_id"],
            "path": s["_resolved_path"],
            "sha256": s["sha256"],
            "role": s["role"],
            "topology": s["topology"],
            "record_id": _record_id(s["_resolved_path"]),
            "evidence": s["evidence"],
        } for s in task["sources"]],
        "steps": [],
        "product": dict(task["product"]),
    }
    return plan


# ----------------------------------------------------------------------
def plan_component_amplification(task):
    plan = _plan_common(task)
    template = _source_by_role(task, "template")
    record = _load_record(template)
    selection = _resolve_selection(task, record)
    component = selection["extracted_sequence"]
    _whole_template_guard(task, record, len(component))
    arms = task.get("operation", {}).get("homology_arms") or {}
    left = str(arms.get("left_arm") or "")
    right = str(arms.get("right_arm") or "")
    product_seq = left + component + right
    plan["steps"].append({
        "step": "extract-component",
        "source_id": template["source_id"],
        "interval_0based": selection["interval_0based"],
        "strand": selection["strand"],
        "length": len(component),
    })
    plan["selection"] = selection
    plan["component_length"] = len(component)
    plan["arms"] = {"left": left, "right": right}
    plan["product"]["topology"] = "linear"
    plan["product"]["expected_length"] = len(product_seq)
    plan["product_sequence"] = product_seq
    plan["product"]["component_interval_on_template"] = \
        selection["interval_0based"]
    return plan


def _replacement_fragment(task, record_for_interval=None):
    replace = task["operation"]["replace"]
    source = _source_by_role(task, "replacement") or \
        _source_by_role(task, "insert")
    record = _load_record(source)
    interval = replace.get("replacement_interval_0based")
    if not isinstance(interval, list) or len(interval) != 2:
        raise PlanningError(
            "COMPONENT_BOUNDARY_REQUIRED",
            "replacement requires an explicit "
            "replacement_interval_0based; whole-file defaults are forbidden",
            missing_fields=["operation.replace.replacement_interval_0based"])
    a, b = int(interval[0]), int(interval[1])
    if a < 0 or b < 0 or a > len(record) or b > len(record):
        raise PlanningError("INTERVAL_OUT_OF_RANGE",
                            "replacement interval outside source length")
    return source, record, _arc(record, a, b), interval


def plan_plasmid_replace(task):
    plan = _plan_common(task)
    backbone = _source_by_role(task, "backbone")
    record = _load_record(backbone)
    replace = task["operation"]["replace"]
    interval = replace["interval_0based"]
    a, b = int(interval[0]), int(interval[1])
    n = len(record)
    if not (0 <= a < b <= n):
        raise PlanningError(
            "REPLACE_INTERVAL_REQUIRED",
            "replace interval must be [a,b) with 0<=a<b<=len(backbone)",
            missing_fields=["operation.replace.interval_0based"])
    source, repl_record, repl_seq, repl_interval = _replacement_fragment(task)
    product = str(record.seq)[:a] + repl_seq + str(record.seq)[b:]
    plan["steps"].append({
        "step": "replace",
        "source_id": backbone["source_id"],
        "interval_0based": interval,
        "replacement_source_id": source["source_id"],
        "replacement_interval_0based": repl_interval,
        "replacement_length": len(repl_seq),
    })
    plan["product"]["topology"] = "circular"
    plan["product"]["expected_length"] = len(product)
    plan["product_sequence"] = product
    plan["replaced_interval"] = interval
    return plan


def plan_plasmid_insert(task):
    plan = _plan_common(task)
    backbone = _source_by_role(task, "backbone")
    record = _load_record(backbone)
    insert_spec = task["operation"]["insert"]
    boundary = int(insert_spec["boundary_0based"])
    if not (0 <= boundary <= len(record)):
        raise PlanningError("INSERT_BOUNDARY_OUT_OF_RANGE",
                            "insert boundary outside backbone")
    source = _source_by_role(task, "insert")
    repl_record = _load_record(source)
    interval = insert_spec["interval_0based"]
    a, b = int(interval[0]), int(interval[1])
    if not (0 <= a < b <= len(repl_record)):
        raise PlanningError("INSERT_INTERVAL_REQUIRED",
                            "explicit insert interval required")
    insert_seq = _arc(repl_record, a, b)
    product = str(record.seq)[:boundary] + insert_seq + \
        str(record.seq)[boundary:]
    plan["steps"].append({
        "step": "insert",
        "source_id": backbone["source_id"],
        "boundary_0based": boundary,
        "insert_source_id": source["source_id"],
        "insert_interval_0based": interval,
        "insert_length": len(insert_seq),
    })
    plan["product"]["topology"] = "circular"
    plan["product"]["expected_length"] = len(product)
    plan["product_sequence"] = product
    plan["insert_boundary"] = boundary
    return plan


def plan_point_mutation(task):
    plan = _plan_common(task)
    template = _source_by_role(task, "template")
    record = _load_record(template)
    seq = str(record.seq)
    mutations = []
    for mut in task["operation"]["mutations"]:
        pos1 = int(mut["position_1based"])
        ref = str(mut["ref"]).upper()
        alt = str(mut["alt"]).upper()
        if not (1 <= pos1 <= len(seq)):
            raise PlanningError("MUTATION_POSITION_OUT_OF_RANGE",
                                "position %d outside sequence" % pos1)
        actual = seq[pos1 - 1].upper()
        if actual != ref:
            raise PlanningError(
                "REFERENCE_RESIDUE_MISMATCH",
                "position %d: input has %s but mutation.ref=%s"
                % (pos1, actual, ref),
                missing_fields=["operation.mutations"],
                details={"position_1based": pos1, "actual": actual,
                         "ref": ref})
        if len(alt) != 1:
            raise PlanningError("INVALID_MUTATION_ALT",
                                "alt must be one base")
        mutations.append({"position_1based": pos1, "pos0": pos1 - 1,
                          "ref": ref, "alt": alt})
    product = list(seq)
    for mut in mutations:
        product[mut["pos0"]] = mut["alt"]
    product = "".join(product)
    plan["steps"].append({
        "step": "point-mutation",
        "source_id": template["source_id"],
        "mutations": [{"position_1based": m["position_1based"],
                       "ref": m["ref"], "alt": m["alt"]}
                      for m in mutations],
    })
    plan["product"]["topology"] = record.annotations.get(
        "topology", "circular")
    plan["product"]["expected_length"] = len(product)
    plan["product_sequence"] = product
    plan["mutations"] = mutations
    return plan


def _assemble_overlap(fragments, overlap, circular):
    """Join fragments by exact overlap; refuse any mismatch.

    ``fragments`` is a list of dicts with keys source_id, order, sequence.
    Returns (product_sequence, junctions).
    """
    mismatches = []
    pairs = (list(range(len(fragments)))
             if circular else list(range(len(fragments) - 1)))
    for idx in pairs:
        left = fragments[idx]["sequence"][-overlap:]
        right = fragments[(idx + 1) % len(fragments)]["sequence"][:overlap]
        if left.upper() != right.upper():
            mismatches.append({
                "between": "fragment-%d -> fragment-%d" % (idx, (idx + 1) %
                                                          len(fragments)),
                "left": left, "right": right})
    if mismatches:
        raise PlanningError(
            "OVERLAP_MISMATCH",
            "explicit fragment overlaps do not match; refusing to assemble",
            details={"mismatches": mismatches})
    if circular:
        product = "".join(f["sequence"][overlap:] for f in fragments)
    else:
        product = fragments[0]["sequence"] + "".join(
            f["sequence"][overlap:] for f in fragments[1:])
    junctions = [
        {"between": "fragment-%d -> fragment-%d" % (
            idx, (idx + 1) % len(fragments)),
         "overlap": fragments[idx]["sequence"][-overlap:]}
        for idx in pairs]
    return product, junctions


def plan_overlap_assembly(task):
    """Explicit-only overlap assembly (Gibson-style fragment joining).

    Every fragment must carry an explicit source_id + interval_0based +
    order.  The whole-record default is impossible here because the
    semantic check requires the interval field before this planner runs.
    """
    plan = _plan_common(task)
    overlap = int(task["operation"]["overlap_length"])
    fragments = []
    for spec in sorted(task["operation"]["fragments"],
                       key=lambda item: int(item["order"])):
        source = next(s for s in task["sources"]
                      if s["source_id"] == spec["source_id"])
        record = _load_record(source)
        a, b = int(spec["interval_0based"][0]), int(spec["interval_0based"][1])
        if a < 0 or b < 0 or a > len(record) or b > len(record):
            raise PlanningError("FRAGMENT_INTERVAL_OUT_OF_RANGE",
                                "fragment interval outside source length")
        seq = _arc(record, a, b)
        if int(spec.get("strand", 1)) == -1:
            seq = str(Seq(seq).reverse_complement())
        if not seq:
            raise PlanningError("FRAGMENT_SEQUENCE_EMPTY",
                                "fragment %s resolved to an empty sequence"
                                % source["source_id"])
        if len(seq) <= overlap:
            raise PlanningError("OVERLAP_TOO_LONG",
                                "fragment %s length %d is not longer than "
                                "overlap %d" % (source["source_id"],
                                                len(seq), overlap))
        fragments.append({
            "source_id": source["source_id"],
            "order": int(spec["order"]),
            "interval_0based": [a, b],
            "strand": int(spec.get("strand", 1)),
            "sequence": seq,
        })
    circular = task["product"]["topology"] == "circular"
    product, junctions = _assemble_overlap(fragments, overlap, circular)
    plan["steps"] = [{
        "step": "overlap-join",
        "source_id": f["source_id"],
        "order": f["order"],
        "interval_0based": f["interval_0based"],
        "overlap_length": overlap,
    } for f in fragments]
    plan["fragments"] = fragments
    plan["overlap_length"] = overlap
    plan["junctions"] = junctions
    plan["product"]["topology"] = task["product"]["topology"]
    plan["product"]["expected_length"] = len(product)
    plan["product_sequence"] = product
    return plan


_STOP_CODONS = ("TAA", "TAG", "TGA")


def _host_translation_table(task):
    host = str(task.get("host") or "").lower()
    return 11 if "coli" in host else 1


def plan_protein_fusion(task):
    """Deterministic CDS fusion: strip 5' partner stop, join optional
    in-frame linker, append 3' partner, verify frame and translation."""
    plan = _plan_common(task)
    op = task["operation"]
    table = int(op.get("translation_table") or
                _host_translation_table(task))
    linker = str((op.get("linker") or {}).get("dna") or "")

    def load_partner(key):
        spec = op[key]
        source = next(s for s in task["sources"]
                      if s["source_id"] == spec["source_id"])
        record = _load_record(source)
        a, b = int(spec["interval_0based"][0]), int(spec["interval_0based"][1])
        if a < 0 or b < 0 or a > len(record) or b > len(record):
            raise PlanningError("FUSION_PARTNER_INTERVAL_OUT_OF_RANGE",
                                "%s interval outside source length" % key)
        seq = _arc(record, a, b)
        if int(spec.get("strand", 1)) == -1:
            seq = str(Seq(seq).reverse_complement())
        return seq, source

    p5, p5_source = load_partner("partner5")
    p3, p3_source = load_partner("partner3")
    if not p5.upper().startswith("ATG"):
        raise PlanningError("FUSION_PARTNER5_START_MISSING",
                            "partner5 must supply the start codon ATG")
    p5_stripped, stop_removed = p5, False
    if p5[-3:].upper() in _STOP_CODONS:
        p5_stripped, stop_removed = p5[:-3], True
    if len(p5_stripped) % 3:
        raise PlanningError("FUSION_PARTNER5_NOT_IN_FRAME",
                            "partner5 (after stop removal) is not a "
                            "multiple of 3 nt")
    p3_final = p3
    p3_stop_removed = False
    if op["stop_policy"] == "no-stop" and p3[-3:].upper() in _STOP_CODONS:
        p3_final, p3_stop_removed = p3[:-3], True
    if op["stop_policy"] == "stop" and \
            p3_final[-3:].upper() not in _STOP_CODONS:
        raise PlanningError("FUSION_STOP_CODON_REQUIRED",
                            "stop_policy=stop requires partner3 to end "
                            "with a stop codon")
    if not p3_final.upper().startswith("ATG"):
        raise PlanningError("FUSION_PARTNER3_START_MISSING",
                            "partner3 must start with ATG")
    if len(p3_final) % 3:
        raise PlanningError("FUSION_PARTNER3_NOT_IN_FRAME",
                            "partner3 is not a multiple of 3 nt")
    product = p5_stripped + linker + p3_final
    if len(product) % 3:
        raise PlanningError("FUSION_NOT_IN_FRAME",
                            "fusion product is not a multiple of 3 nt")
    expected_translation = (
        str(Seq(p5_stripped).translate(table=table, to_stop=False)) +
        str(Seq(linker).translate(table=table, to_stop=False)) +
        str(Seq(p3_final).translate(table=table, to_stop=False)))
    translation = str(Seq(product).translate(table=table, to_stop=False))
    if translation != expected_translation:
        raise PlanningError("FUSION_TRANSLATION_MISMATCH",
                            "translation of the joined product does not "
                            "equal the partner translations")
    stops = [i for i, aa in enumerate(translation) if aa == "*"]
    if op["stop_policy"] == "no-stop":
        if stops:
            raise PlanningError("FUSION_INTERNAL_STOP",
                                "no-stop fusion contains an internal stop "
                                "codon at residue %d" % (stops[0] + 1))
    else:
        if any(i != len(translation) - 1 for i in stops):
            raise PlanningError("FUSION_INTERNAL_STOP",
                                "fusion contains an internal stop codon")
    plan["steps"].append({
        "step": "protein-fusion",
        "partner5_source_id": p5_source["source_id"],
        "partner5_interval_0based": op["partner5"]["interval_0based"],
        "partner3_source_id": p3_source["source_id"],
        "partner3_interval_0based": op["partner3"]["interval_0based"],
        "linker_dna": linker,
        "stop_policy": op["stop_policy"],
        "translation_table": table,
    })
    plan["fusion"] = {
        "partner5_stop_removed": stop_removed,
        "partner3_stop_removed": p3_stop_removed,
        "translation_table": table,
        "translation": translation,
        "stop_policy": op["stop_policy"],
        "linker_dna": linker,
    }
    plan["product"]["topology"] = "linear"
    plan["product"]["expected_length"] = len(product)
    plan["product_sequence"] = product
    return plan


def plan_integration_donor(task):
    """Linear integration donor: explicit component + homology arms that
    must match the declared locus flanks."""
    plan = _plan_common(task)
    template = _source_by_role(task, "template")
    record = _load_record(template)
    selection = _resolve_selection(task, record)
    component = selection["extracted_sequence"]
    _whole_template_guard(task, record, len(component))
    arms = task["operation"]["homology_arms"]
    left = str(arms.get("left_arm") or "")
    right = str(arms.get("right_arm") or "")
    locus_spec = task["operation"]["locus"]
    ref_source = next(s for s in task["sources"]
                      if s["source_id"] == locus_spec["source_id"])
    ref = _load_record(ref_source)
    la, lb = int(locus_spec["interval_0based"][0]), \
        int(locus_spec["interval_0based"][1])
    if la < 0 or lb < 0 or la > len(ref) or lb > len(ref):
        raise PlanningError("INTEGRATION_LOCUS_OUT_OF_RANGE",
                            "locus interval outside reference length")
    if la > lb:
        raise PlanningError("INTEGRATION_LOCUS_WRAP_UNSUPPORTED",
                            "locus interval must not wrap the reference")
    strand = int(locus_spec.get("strand", 1))
    upstream = _arc(ref, la - len(left), la) if left else ""
    downstream = _arc(ref, lb, lb + len(right)) if right else ""
    expected_left = (upstream if strand == 1
                     else str(Seq(downstream).reverse_complement())
                     if downstream else "")
    expected_right = (downstream if strand == 1
                      else str(Seq(upstream).reverse_complement())
                      if upstream else "")
    if left and left.upper() != expected_left.upper():
        raise PlanningError(
            "INTEGRATION_ARM_MISMATCH",
            "left homology arm does not match the declared locus flank",
            details={"expected": expected_left, "given": left})
    if right and right.upper() != expected_right.upper():
        raise PlanningError(
            "INTEGRATION_ARM_MISMATCH",
            "right homology arm does not match the declared locus flank",
            details={"expected": expected_right, "given": right})
    product_seq = left + component + right
    plan["steps"].append({
        "step": "build-integration-donor",
        "source_id": template["source_id"],
        "interval_0based": selection["interval_0based"],
        "strand": selection["strand"],
        "length": len(component),
        "left_arm": left,
        "right_arm": right,
        "locus_source_id": locus_spec["source_id"],
        "locus_interval_0based": [la, lb],
        "locus_strand": strand,
    })
    plan["selection"] = selection
    plan["component_length"] = len(component)
    plan["arms"] = {"left": left, "right": right}
    plan["locus"] = {"source_id": locus_spec["source_id"],
                     "interval_0based": [la, lb], "strand": strand}
    plan["product"]["topology"] = "linear"
    plan["product"]["expected_length"] = len(product_seq)
    plan["product_sequence"] = product_seq
    return plan


def _scripts_path():
    import sys
    root = pathlib.Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    return root


def plan_gateway_recombination(task):
    """Gateway BP/LR via the validated strict att-pair algorithm."""
    plan = _plan_common(task)
    _scripts_path()
    from simulate_advanced import gateway_bp, gateway_lr  # noqa: E402
    op = task["operation"]
    try:
        if op["reaction"] == "lr":
            entry = next(s for s in task["sources"]
                         if s["source_id"] == op["entry_source_id"])
            dest = next(s for s in task["sources"]
                        if s["source_id"] == op["destination_source_id"])
            product, body, notes = gateway_lr(
                _load_record(entry), _load_record(dest))
        else:
            insert = next(s for s in task["sources"]
                          if s["source_id"] == op["entry_source_id"])
            donor = next(s for s in task["sources"]
                         if s["source_id"] == op["donor_vector_source_id"])
            product, body, notes = gateway_bp(
                _load_record(donor), _load_record(insert))
    except Exception as exc:  # noqa: BLE001
        code = getattr(exc, "code", None) or "GATEWAY_ASSEMBLY_FAILED"
        raise PlanningError(code, str(exc),
                            details=getattr(exc, "details", None))
    plan["steps"].append({
        "step": "gateway-%s" % op["reaction"],
        "reaction": op["reaction"],
        "body_length": len(body),
        "stop_policy": op["stop_policy"],
    })
    plan["gateway"] = {"reaction": op["reaction"], "body": body,
                       "notes": notes, "stop_policy": op["stop_policy"]}
    plan["_gateway_product_record"] = product
    plan["product"]["topology"] = "circular"
    plan["product"]["expected_length"] = len(product.seq)
    plan["product_sequence"] = str(product.seq)
    return plan


def _digest_ligate_plan(plan, task):
    """Single-enzyme digest-ligation reusing the shared-end model."""
    _scripts_path()
    from simulate_cloning import digest_ligate  # noqa: E402
    from sg_common import topology as record_topology  # noqa: E402
    op = task["operation"]
    vector = _load_record(_source_by_role(task, "backbone"))
    insert = _load_record(_source_by_role(task, "insert"))
    if record_topology(vector) != "circular":
        raise PlanningError("RESTRICTION_VECTOR_NOT_CIRCULAR",
                            "digest-ligate requires a circular vector")
    enzyme = op["vector_enzymes"][0]
    if op["orientation"] == "reverse":
        insert = insert.reverse_complement(id=True, name=True,
                                           description=True)
    try:
        product, fragments, junctions = digest_ligate(
            vector, insert, enzyme)
    except Exception as exc:  # noqa: BLE001
        code = getattr(exc, "code", None) or "RESTRICTION_LIGATION_FAILED"
        raise PlanningError(code, str(exc),
                            details=getattr(exc, "details", None))
    plan["steps"].append({
        "step": "digest-ligate",
        "enzyme": enzyme,
        "vector_source_id": op["vector_source_id"],
        "insert_source_id": op["insert_source_id"],
        "orientation": op["orientation"],
    })
    plan["restriction"] = {"enzymes": [enzyme], "junctions": junctions}
    plan["_restriction_product_record"] = product
    plan["product"]["topology"] = "circular"
    plan["product"]["expected_length"] = len(product.seq)
    plan["product_sequence"] = str(product.seq)
    return plan


def _two_enzyme_ligate_plan(plan, task):
    """Two-enzyme digest-ligation with the shared-end model.

    Each vector enzyme must cut exactly once; the removed arc between the
    two top-cut boundaries must not wrap the origin.  Insert is excised
    between its two unique sites (reverse orientation flips the insert
    record before excision) and sticky ends must be complementary.
    """
    _scripts_path()
    from Bio import SeqIO as _SeqIO  # noqa: E402
    from assembly_model import (  # noqa: E402
        AssemblyFragment, check_sticky_junctions, overhang_end)
    from construct_model import ConstructModel  # noqa: E402
    from sg_common import (get_enzyme, restriction_hits,  # noqa: E402
                           topology as record_topology)
    from simulate_cloning import (_arc as cl_arc,  # noqa: E402
                                  _hit_end_sequences)
    op = task["operation"]
    vector = _load_record(_source_by_role(task, "backbone"))
    insert = _load_record(_source_by_role(task, "insert"))
    if record_topology(vector) != "circular":
        raise PlanningError("RESTRICTION_VECTOR_NOT_CIRCULAR",
                            "two-enzyme ligation requires a circular vector")
    if record_topology(insert) != "linear":
        raise PlanningError("RESTRICTION_INSERT_MUST_BE_LINEAR",
                            "two-enzyme ligation requires a linear insert")
    enzymes = [str(e) for e in op["vector_enzymes"]]
    insert_enzymes = [str(e) for e in (op.get("insert_enzymes") or enzymes)]
    if len(enzymes) != 2 or len(insert_enzymes) != 2:
        raise PlanningError("RESTRICTION_ENZYME_PAIR_REQUIRED",
                            "two-enzyme ligation requires exactly two "
                            "vector enzymes and two insert enzymes")
    if op["orientation"] == "reverse":
        insert = insert.reverse_complement(id=True, name=True,
                                           description=True)
    vseq = str(vector.seq).upper()
    iseq = str(insert.seq).upper()
    vector_hits = []
    for enzyme_name in enzymes:
        enzyme = get_enzyme(enzyme_name)
        hits = [h for h in restriction_hits(vseq, enzyme, circular=True)
                if h["cuts_within_sequence"]]
        if len(hits) != 1:
            raise PlanningError("RESTRICTION_SITE_COUNT",
                                "vector enzyme %s must cut exactly once; "
                                "found %d" % (enzyme_name, len(hits)))
        vector_hits.append(hits[0])
    insert_hits = []
    for enzyme_name in insert_enzymes:
        enzyme = get_enzyme(enzyme_name)
        hits = [h for h in restriction_hits(iseq, enzyme, circular=False)
                if h["cuts_within_sequence"]]
        if len(hits) != 1:
            raise PlanningError("RESTRICTION_SITE_COUNT",
                                "insert enzyme %s must cut exactly once; "
                                "found %d" % (enzyme_name, len(hits)))
        insert_hits.append(hits[0])
    n = len(vseq)
    t1 = vector_hits[0]["top_cut_boundary_0based"] % n
    t2 = vector_hits[1]["top_cut_boundary_0based"] % n
    if t1 > t2:
        raise PlanningError("RESTRICTION_WRAP_UNSUPPORTED",
                            "vector cut boundaries wrap the origin; rotate "
                            "the vector before ligation")
    if t1 == t2:
        raise PlanningError("RESTRICTION_ZERO_LENGTH_EXCISION",
                            "vector cut boundaries coincide")
    i1 = insert_hits[0]["top_cut_boundary_0based"] % len(iseq)
    i2 = insert_hits[1]["top_cut_boundary_0based"] % len(iseq)
    if i1 > i2:
        i1, i2 = i2, i1
        insert_hits[0], insert_hits[1] = insert_hits[1], insert_hits[0]
    if i1 == i2:
        raise PlanningError("RESTRICTION_ZERO_LENGTH_EXCISION",
                            "insert cut boundaries coincide")
    ins_frag = iseq[i1:i2]
    for enzyme_name in set(enzymes + insert_enzymes):
        site = str(get_enzyme(enzyme_name).site).upper()
        rc_site = str(Seq(site).reverse_complement()).upper()
        if site in ins_frag or rc_site in ins_frag:
            raise PlanningError("INSERT_EXCISION_FAILED",
                                "excised insert still contains an intact "
                                "%s recognition site" % enzyme_name)
    backbone = vseq[:t1] + vseq[t2:]
    # backbone fragment: left end = cut at t2, right end = cut at t1
    l_kind, l_ov, _l_right = _hit_end_sequences(vseq, vector_hits[1])
    r_kind, _r_left, r_ov = _hit_end_sequences(vseq, vector_hits[0])
    backbone_frag = AssemblyFragment(
        "vector", backbone, topology="linear",
        left_end=overhang_end(l_kind, l_ov, 0, source_cut_boundary=t2),
        right_end=overhang_end(r_kind, r_ov, len(backbone),
                               source_cut_boundary=t1),
        source=vector.id)
    il_kind, il_ov, _il_right = _hit_end_sequences(iseq, insert_hits[0])
    ir_kind, _ir_left, ir_ov = _hit_end_sequences(iseq, insert_hits[1])
    insert_frag = AssemblyFragment(
        "insert", ins_frag, topology="linear",
        left_end=overhang_end(il_kind, il_ov, 0,
                              source_cut_boundary=i1),
        right_end=overhang_end(ir_kind, ir_ov, len(ins_frag),
                               source_cut_boundary=i2),
        source=insert.id)
    junctions = check_sticky_junctions([backbone_frag, insert_frag],
                                       circular=True)
    if any(j["compatibility"] == "MISMATCH" for j in junctions):
        raise PlanningError(
            "STICKY_END_MISMATCH",
            "digest-ligation sticky ends are not complementary",
            details=junctions)
    product = ConstructModel(vector).replace(t1, t2, ins_frag)
    product.set_topology("circular")
    product_record = product.to_record()
    from Bio.SeqFeature import FeatureLocation, SeqFeature
    product_record.features.append(SeqFeature(
        FeatureLocation(t1, t1 + len(ins_frag), strand=1),
        type="misc_feature", qualifiers={"label": ["insert"]}))
    plan["steps"].append({
        "step": "digest-ligate-two-enzyme",
        "vector_enzymes": enzymes,
        "insert_enzymes": insert_enzymes,
        "vector_cuts_0based": [t1, t2],
        "insert_cuts_0based": [i1, i2],
        "orientation": op["orientation"],
    })
    plan["restriction"] = {"enzymes": enzymes,
                           "junctions": junctions}
    plan["_restriction_product_record"] = product_record
    plan["product"]["topology"] = "circular"
    plan["product"]["expected_length"] = len(product_record.seq)
    plan["product_sequence"] = str(product_record.seq)
    return plan


def plan_restriction_ligation(task):
    plan = _plan_common(task)
    op = task["operation"]
    enzymes = op["vector_enzymes"]
    insert_enzymes = op.get("insert_enzymes") or enzymes
    if len(enzymes) == 1 and insert_enzymes == enzymes:
        return _digest_ligate_plan(plan, task)
    return _two_enzyme_ligate_plan(plan, task)


def _string_arc(seq, a, b):
    n = len(seq)
    a, b = int(a) % n, int(b) % n
    if a <= b:
        return seq[a:b]
    return seq[a:] + seq[:b]


def plan_hierarchical_assembly(task):
    """Staged assembly: every stage is an explicit overlap assembly whose
    fragments come from input sources or previous stage products."""
    plan = _plan_common(task)
    stage_products = {}
    stages = []
    for stage in task["operation"]["stages"]:
        overlap = int(stage["overlap_length"])
        circular = stage["product_topology"] == "circular"
        fragments = []
        for spec in sorted(stage["fragments"],
                           key=lambda item: int(item["order"])):
            if spec.get("source_id"):
                source = next(s for s in task["sources"]
                              if s["source_id"] == spec["source_id"])
                record = _load_record(source)
                a, b = (int(spec["interval_0based"][0]),
                        int(spec["interval_0based"][1]))
                if a < 0 or b < 0 or a > len(record) or b > len(record):
                    raise PlanningError(
                        "FRAGMENT_INTERVAL_OUT_OF_RANGE",
                        "stage %s fragment interval outside source"
                        % stage["stage_id"])
                seq = _arc(record, a, b)
            else:
                if spec["stage_id"] not in stage_products:
                    raise PlanningError(
                        "HIERARCHICAL_STAGE_REFERENCE_MISSING",
                        "stage %s references unknown stage %s"
                        % (stage["stage_id"], spec["stage_id"]))
                parent = stage_products[spec["stage_id"]]
                interval = spec.get("interval_0based")
                if interval:
                    seq = _string_arc(parent, interval[0], interval[1])
                else:
                    seq = parent
            if int(spec.get("strand", 1)) == -1:
                seq = str(Seq(seq).reverse_complement())
            if not seq:
                raise PlanningError("FRAGMENT_SEQUENCE_EMPTY",
                                    "stage %s fragment is empty"
                                    % stage["stage_id"])
            if len(seq) <= overlap:
                raise PlanningError(
                    "OVERLAP_TOO_LONG",
                    "stage %s fragment length %d is not longer than "
                    "overlap %d" % (stage["stage_id"], len(seq), overlap))
            fragments.append({"source_id": spec.get("source_id") or
                              ("stage:" + spec["stage_id"]),
                              "order": int(spec["order"]),
                              "interval_0based": spec.get("interval_0based"),
                              "strand": int(spec.get("strand", 1)),
                              "sequence": seq})
        product, junctions = _assemble_overlap(fragments, overlap, circular)
        stage_products[stage["stage_id"]] = product
        stages.append({
            "stage_id": stage["stage_id"],
            "fragments": fragments,
            "junctions": junctions,
            "overlap_length": overlap,
            "product_topology": stage["product_topology"],
            "product_sequence": product,
        })
    final = stages[-1]
    plan["stages"] = stages
    plan["fragments"] = final["fragments"]
    plan["overlap_length"] = final["overlap_length"]
    plan["junctions"] = final["junctions"]
    plan["steps"] = [{
        "step": "hierarchical-stage",
        "stage_id": s["stage_id"],
        "fragments": len(s["fragments"]),
        "product_topology": s["product_topology"],
        "product_length": len(s["product_sequence"]),
    } for s in stages]
    plan["product"]["topology"] = task["product"]["topology"]
    plan["product"]["expected_length"] = len(final["product_sequence"])
    plan["product_sequence"] = final["product_sequence"]
    return plan


def plan_crispr_editing(task):
    """CRISPR editing design: deterministic guide scan + optional HDR
    donor model.  Method maturity is experimental, so products stay
    experimental-preview."""
    plan = _plan_common(task)
    root = _scripts_path()
    import json
    import subprocess
    import sys
    op = task["operation"]
    ref = _source_by_role(task, "reference")
    ref_rec = _load_record(ref)
    ref_seq = str(ref_rec.seq)
    n = len(ref_seq)
    a, b = int(op["target_interval_0based"][0]), \
        int(op["target_interval_0based"][1])
    if a < 0 or b < 0 or a > n or b > n or a >= b:
        raise PlanningError("CRISPR_TARGET_INTERVAL_INVALID",
                            "target interval must be [a,b) with 0<=a<b<=len")
    completed = subprocess.run(
        [sys.executable, "-X", "utf8", "-B",
         str(root / "scripts" / "design_guides.py"),
         ref["_resolved_path"], "--nuclease", str(op["nuclease"]),
         "--region", str(a), str(b), "--json"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if completed.returncode != 0:
        raise PlanningError("CRISPR_GUIDE_SCAN_FAILED",
                            (completed.stderr or completed.stdout)[-500:])
    try:
        scan = json.loads(completed.stdout)
    except Exception:  # noqa: BLE001
        raise PlanningError("CRISPR_GUIDE_SCAN_FAILED",
                            "guide scan returned non-JSON output")
    candidates = scan.get("candidates") or scan.get("guides") or \
        scan.get("data", {}).get("candidates") or []
    if not candidates:
        raise PlanningError("CRISPR_NO_GUIDES_IN_TARGET",
                            "no guide candidates in the target window")
    guides = []
    for candidate in candidates[:5]:
        coordinates = candidate.get("coordinates") or {}
        guides.append({
            "id": candidate.get("id") or candidate.get("name"),
            "protospacer": str(candidate.get("protospacer_sequence") or
                               candidate.get("protospacer") or
                               candidate.get("sequence")),
            "reference_sequence": str(candidate.get(
                "protospacer_reference_sequence") or
                candidate.get("protospacer_sequence") or ""),
            "pam": candidate.get("pam_sequence") or candidate.get("pam"),
            "start_0based": coordinates.get("protospacer_start"),
            "end_0based": coordinates.get("protospacer_end"),
            "pam_start": coordinates.get("pam_start"),
            "pam_end": coordinates.get("pam_end"),
            "wraps_origin": bool(coordinates.get("wraps_origin")),
            "strand": 1 if candidate.get("strand") == "forward" else -1,
            "position": candidate.get("position"),
        })
    product_seq = ref_seq
    donor = op.get("donor_strategy") or {}
    if donor.get("donor_source_id"):
        dsrc = next(s for s in task["sources"]
                    if s["source_id"] == donor["donor_source_id"])
        drec = _load_record(dsrc)
        ra, rb = (int(donor["replacement_interval_0based"][0]),
                  int(donor["replacement_interval_0based"][1]))
        if ra < 0 or rb < 0 or ra > len(drec) or rb > len(drec) or ra >= rb:
            raise PlanningError("CRISPR_DONOR_INTERVAL_INVALID",
                                "donor replacement interval invalid")
        repl = _arc(drec, ra, rb)
        arms = donor.get("homology_arms") or {}
        left = str(arms.get("left_arm") or "")
        right = str(arms.get("right_arm") or "")
        upstream = _arc(ref_rec, a - len(left), a) if left else ""
        downstream = _arc(ref_rec, b, b + len(right)) if right else ""
        if left and left.upper() != upstream.upper():
            raise PlanningError("CRISPR_ARM_MISMATCH",
                                "left donor arm does not match the "
                                "reference flank",
                                details={"expected": upstream,
                                         "given": left})
        if right and right.upper() != downstream.upper():
            raise PlanningError("CRISPR_ARM_MISMATCH",
                                "right donor arm does not match the "
                                "reference flank",
                                details={"expected": downstream,
                                         "given": right})
        product_seq = ref_seq[:a] + repl + ref_seq[b:]
        plan["donor"] = {"donor_source_id": donor["donor_source_id"],
                         "replacement_length": len(repl),
                         "left_arm": left, "right_arm": right,
                         "target_interval_0based": [a, b]}
    plan["steps"].append({
        "step": "crispr-design",
        "nuclease": op["nuclease"],
        "target_interval_0based": [a, b],
        "guides": [g["id"] for g in guides],
        "donor": bool(donor.get("donor_source_id")),
    })
    plan["guides"] = guides
    plan["crispr"] = {
        "nuclease": op["nuclease"],
        "target_interval_0based": [a, b],
        "offtarget_assessment": "not-assessed",
    }
    plan["product"]["topology"] = ref_rec.annotations.get(
        "topology", "linear")
    plan["product"]["expected_length"] = len(product_seq)
    plan["product_sequence"] = product_seq
    return plan


_PLANNERS = {
    "component_amplification": plan_component_amplification,
    "plasmid_replace": plan_plasmid_replace,
    "plasmid_insert": plan_plasmid_insert,
    "point_mutation": plan_point_mutation,
    "overlap_assembly": plan_overlap_assembly,
    "protein_fusion": plan_protein_fusion,
    "integration_donor": plan_integration_donor,
    "gateway_recombination": plan_gateway_recombination,
    "restriction_ligation": plan_restriction_ligation,
    "hierarchical_assembly": plan_hierarchical_assembly,
    "crispr_editing": plan_crispr_editing,
}


def plan(task, base_dir=None):
    """Public seam: validate task then route to a dedicated planner."""
    from core.task import validate_construction_task
    task = validate_construction_task(task, base_dir=base_dir)
    from core.registry import route_task
    planner_name = route_task(task)
    planner = _PLANNERS[planner_name]
    plan = planner(task)
    plan["plan_sha256"] = sha256_text(canonical_json({
        "task_sha256": plan["task_sha256"],
        "steps": plan["steps"],
        "product_sequence": plan["product_sequence"],
    }))
    return task, plan
