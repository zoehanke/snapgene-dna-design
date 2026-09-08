# -*- coding: utf-8 -*-
"""Deterministic execution layer for the v0.9 assembly planner.

The planner chooses a route and designs candidate primers.  This module is the
separate execution gate: it must build the method-specific product before a
plan is allowed to write a ``final construct`` file.  A fragment-order
concatenation is never accepted as an executed product.

All coordinates in this module are 0-based, half-open.  The returned feature
specifications are JSON-safe and are consumed by ``scripts/plan_assembly.py``.
"""
import copy

from Bio.Seq import Seq
from Bio.SeqFeature import CompoundLocation, FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord


class ExecutionError(ValueError):
    """A method-specific execution or feature-migration failure."""

    def __init__(self, code, message, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def _record(name, sequence, topology_value):
    record = SeqRecord(Seq(str(sequence).upper()), id=str(name), name=str(name))
    record.annotations["molecule_type"] = "DNA"
    record.annotations["topology"] = topology_value
    return record


def _parts(location):
    return list(getattr(location, "parts", [location]))


def _qualifiers(feature):
    result = {}
    for key, values in (feature.qualifiers or {}).items():
        values = values if isinstance(values, list) else [values]
        result[str(key)] = [str(value) for value in values]
    return result


def _feature_spec(feature, offset=0, strand_override=None, note=None):
    parts = []
    for part in _parts(feature.location):
        strand = part.strand if strand_override is None else strand_override
        parts.append({
            "start0": int(part.start) + int(offset),
            "end0": int(part.end) + int(offset),
            "strand": 0 if strand is None else int(strand),
        })
    qualifiers = _qualifiers(feature)
    if note:
        qualifiers.setdefault("note", []).append(str(note))
    label = qualifiers.get("label") or qualifiers.get("gene") or [
        feature.id or "feature"
    ]
    return {
        "type": str(feature.type),
        "label": str(label[0]),
        "operator": getattr(feature.location, "operator", None),
        "segments": parts,
        "qualifiers": qualifiers,
    }


def _misc_spec(name, start0, end0, role, source_path):
    return {
        "type": "misc_feature",
        "label": str(name),
        "operator": None,
        "segments": [{"start0": int(start0), "end0": int(end0), "strand": 1}],
        "qualifiers": {
            "label": [str(name)],
            "note": ["role=%s source=%s" % (role, source_path)],
        },
    }


def _feature_spec_reversed(feature, source_start, source_end, product_offset):
    """Map a complete feature through reverse-complemented fragment space."""
    parts = _parts(feature.location)
    mapped = []
    for part in reversed(parts):
        start = int(part.start)
        end = int(part.end)
        mapped.append({
            "start0": int(product_offset + source_end - end),
            "end0": int(product_offset + source_end - start),
            "strand": (None if part.strand in (None, 0)
                       else -int(part.strand)),
        })
    qualifiers = _qualifiers(feature)
    label = qualifiers.get("label") or qualifiers.get("gene") or [
        feature.id or "feature"]
    return {
        "type": str(feature.type),
        "label": str(label[0]),
        "operator": getattr(feature.location, "operator", None),
        "segments": mapped,
        "qualifiers": qualifiers,
    }


def _overlap_source_specs(fragment, product_offset, raw_length):
    """Map source annotations for a planner fragment.

    Planner fragments are either a full record, a contiguous interval, or one
    selected feature.  We migrate complete simple/compound features and fail
    on a partially clipped feature instead of silently emitting a misleading
    annotation.
    """
    source = fragment.get("_source_record")
    selected = fragment.get("_source_feature")
    region_start, region_end = fragment.get("source_interval", [0, 0])
    extraction_strand = int(fragment.get("_extraction_strand") or 1)
    result = []

    if fragment.get("_source_wrap") and source is not None:
        n = len(source.seq)
        # The sequence arc itself is deterministic, but feature coordinates
        # need a split-at-origin mapping.  Refuse only when an annotation
        # intersects the arc; an unannotated wrap can still be executed.
        for feature in source.features:
            if feature.location is None:
                continue
            if any(
                (int(part.start) < n and int(part.end) > region_start) or
                (int(part.start) < region_end and int(part.end) > 0)
                for part in _parts(feature.location)
            ):
                raise ExecutionError(
                    "FEATURE_MAPPING_CIRCULAR_INTERVAL",
                    "circular interval crosses the origin and intersects a source feature",
                    {"feature": feature.id or feature.type,
                     "interval": [region_start, region_end]},
                )

    if selected is not None:
        if len(_parts(selected.location)) > 1:
            raise ExecutionError(
                "FEATURE_MAPPING_COMPLEX_SELECTED",
                "selected compound feature needs an explicit origin-aware mapping",
                {"feature": selected.id or selected.type,
                 "parts": len(_parts(selected.location))},
            )
        # A feature extraction is already in the feature's biological 5'->3'
        # orientation.  Its product orientation is therefore +1.  Preserve
        # the original strand as auditable metadata, not as a contradictory
        # product coordinate.
        # ``selected`` is extracted into a new fragment sequence.  Its source
        # coordinates therefore must be localized to the selected interval;
        # carrying the original chromosome/plasmid coordinates into the
        # product would create out-of-range features (especially for a reverse
        # strand feature).
        local_selected = copy.deepcopy(selected)
        local_parts = []
        for part in _parts(selected.location):
            local_parts.append(FeatureLocation(
                int(part.start) - int(region_start),
                int(part.end) - int(region_start),
                strand=part.strand))
        local_selected.location = local_parts[0]
        result.append(_feature_spec(
            local_selected, product_offset,
            strand_override=1 if extraction_strand == -1 else None,
            note="source_strand=%s; source_feature_extraction=true" % (
                selected.location.strand,)))
        return result

    if source is None:
        return result
    for feature in source.features:
        if feature.location is None:
            continue
        parts = _parts(feature.location)
        if any(int(part.start) < region_end and int(part.end) > region_start
               for part in parts):
            if not all(region_start <= int(part.start) and
                       int(part.end) <= region_end for part in parts):
                raise ExecutionError(
                    "FEATURE_MAPPING_PARTIAL",
                    "feature %r is clipped by planner interval %d..%d"
                    % (feature.id or feature.type, region_start, region_end),
                    {"feature": feature.id or feature.type,
                     "interval": [region_start, region_end]},
                )
            result.append(_feature_spec(feature, product_offset - region_start))
    return result


def _gibson_product(fragments, topology_value, junctions, method_name="gibson"):
    from scripts.simulate_cloning import gibson

    if len(fragments) < 2:
        raise ExecutionError("ASSEMBLY_REQUIRES_TWO_FRAGMENTS",
                             "Gibson/overlap execution requires at least two fragments")
    lengths = {int(item.get("length", len(item["sequence"])))
               for item in fragments}
    overlap_lengths = {int(item.get("length", 0)) for item in junctions}
    if not junctions or len(overlap_lengths) != 1:
        raise ExecutionError(
            "OVERLAP_LENGTH_NOT_UNIFORM",
            "method executor requires one common overlap length for all junctions",
            {"junction_lengths": sorted(overlap_lengths)},
        )
    overlap = next(iter(overlap_lengths))
    if overlap < 12:
        raise ExecutionError(
            "OVERLAP_TOO_SHORT_FOR_EXECUTION",
            "overlap %d bp is below the hard execution floor of 12 bp" % overlap,
            {"overlap_length": overlap},
        )
    circular = topology_value == "circular"
    n = len(fragments)
    records = []
    pcr_products = []
    raw_offsets = []
    cursor = 0
    for index, item in enumerate(fragments):
        pcr_required = bool(item.get("_pcr_required", True))
        pcr = item.get("_pcr_product") or item.get("pcr_product")
        if pcr_required and (not pcr or not pcr.get("amplicon")):
            raise ExecutionError(
                "PCR_PRODUCT_REQUIRED",
                "assembly fragment %r has no simulated product from its selected primers"
                % item.get("name", index),
                {"fragment": item.get("name", index)},
            )
        raw = str(pcr["amplicon"] if pcr_required else item["sequence"]).upper()
        if pcr_required:
            pcr_products.append(pcr)
        raw_offsets.append(cursor)
        cursor += len(str(item["sequence"]))
        # The complete 5' tails are already present in the selected-primer
        # PCR product. Feeding the ideal source fragment here would discard
        # the delivered primer sequences.
        records.append(_record(item["name"], raw, "linear"))

    try:
        product, _fragments, contributions, warnings = gibson(
            records, overlap=overlap, circular=circular)
    except Exception as error:  # AssemblyError is intentionally normalized.
        code = getattr(error, "code", "ASSEMBLY_EXECUTION_FAILED")
        raise ExecutionError(code, str(error), getattr(error, "details", {}))

    expected = "".join(str(item["sequence"]).upper() for item in fragments)
    # Homology may be carried on either primer. A circular molecule can then
    # start at a different base; rotate the actual product, never replace it.
    if circular and len(product.seq) == len(expected) and str(product.seq).upper() != expected:
        offset = (str(product.seq).upper()*2).find(expected)
        if 0 <= offset < len(product):
            product = product[offset:] + product[:offset]
            product.annotations["topology"] = "circular"
    # The selected overlap is already present at the end of the preceding
    # source fragment.  The downstream PCR product receives a synthetic left
    # tail, which the simulator removes.  Therefore each raw source fragment
    # contributes exactly once to this product sequence.
    if str(product.seq).upper() != expected.upper():
        raise ExecutionError(
            "EXECUTOR_SEQUENCE_MISMATCH",
            "Gibson executor returned a sequence different from unique contributions",
            {"expected_length": len(expected), "actual_length": len(product.seq)},
        )

    feature_specs = []
    cursor = 0
    for index, item in enumerate(fragments):
        raw_length = len(str(item["sequence"]))
        contribution_length = raw_length
        raw_start_in_product = cursor
        feature_specs.append(_misc_spec(
            item["name"], raw_start_in_product,
            raw_start_in_product + raw_length, item["role"],
            item["source_path"]))
        feature_specs.extend(_overlap_source_specs(
            item, raw_start_in_product, raw_length))
        cursor += contribution_length

    return {
        "sequence": str(product.seq).upper(),
        "feature_specs": feature_specs,
        "executor": "scripts.simulate_cloning.gibson",
        "status": "validated",
        "method": method_name,
        "overlap_length": overlap,
        "contributions": contributions,
        "pcr_products": [
            {
                "amplicon_length": int(
                    pcr.get("amplicon_length", len(pcr.get("amplicon", "")))
                ),
                "template": pcr.get("template"),
                "primers": pcr.get("primers", []),
                "template_interval_0based": pcr.get("template_interval_0based"),
                "forward_binding": pcr.get("forward_binding"),
                "reverse_binding": pcr.get("reverse_binding"),
            }
            for pcr in pcr_products
        ],
        "warnings": warnings,
        "circular": circular,
    }


def _golden_gate_product(fragments, topology_value, enzymes):
    if not enzymes:
        raise ExecutionError("GOLDEN_GATE_ENZYME_REQUIRED",
                             "Golden Gate execution requires a Type IIS enzyme")

    records = []
    for index, item in enumerate(fragments):
        pcr_required = bool(item.get("_pcr_required", True))
        pcr = item.get("_pcr_product") or item.get("pcr_product")
        if pcr_required and (not pcr or not pcr.get("amplicon")):
            raise ExecutionError(
                "PCR_PRODUCT_REQUIRED",
                "Golden Gate fragment %r has no simulated product from its selected primers"
                % item.get("name", index),
                {"fragment": item.get("name", index)},
            )
        topo = "circular" if index == 0 else "linear"
        sequence = pcr["amplicon"] if pcr_required else item["sequence"]
        records.append(_record(item["name"], sequence, topo))
    from scripts.golden_gate import assemble
    from scripts.sg_common import get_enzyme
    try:
        final, junctions, parts, notes, _models = assemble(
            records, [item["name"] for item in fragments],
            get_enzyme(enzymes[0]) if isinstance(enzymes[0], str) else enzymes[0],
            vector_idx=0, reverse=(), vector_topology="circular")
    except Exception as error:
        code = getattr(error, "code", "GOLDEN_GATE_EXECUTION_FAILED")
        raise ExecutionError(code, str(error), getattr(error, "details", {}))

    # The low-level Golden Gate implementation returns cut fragments, not a
    # planner interval.  Part-level annotations are honest and exact; source
    # features are only migrated when their simple interval is fully contained
    # in the excised fragment.  A clipped/compound feature is blocked rather
    # than silently flattened.
    feature_specs = []
    cursor = 0
    for part in parts:
        length = int(part["fragment_length"])
        source_index = int(part["part_index"])
        item = fragments[source_index]
        feature_specs.append(_misc_spec(
            item["name"], cursor, cursor + length, item["role"],
            item["source_path"]))
        source = item.get("_source_record")
        if source is not None:
            source_interval = item.get("source_interval", [0, len(source.seq)])
            if ((item.get("_source_feature") is not None or
                 source_interval != [0, len(source.seq)]) and
                    source.features):
                raise ExecutionError(
                    "FEATURE_MAPPING_INTERVAL_GOLDEN_GATE",
                    "Golden Gate feature migration for a clipped/selected source interval "
                    "requires an explicit local-coordinate mapping",
                    {"part": item["name"],
                     "source_interval": source_interval},
                )
            start0 = int(part["top_cut_start0"])
            end0 = int(part["top_cut_end0"])
            wraps = bool(part.get("wraps_origin"))
            if wraps:
                # Mapping a wrapped cut arc requires an origin-aware split;
                # refuse only when an annotation actually intersects it.
                n = len(source.seq)
                def _arc_intersects(part_start, part_end):
                    """Whether a source interval intersects the selected wrap arc."""
                    return ((part_start < n and part_end > start0) or
                            (part_start < end0 and part_end > 0))
                for feature in source.features:
                    if feature.location is None:
                        continue
                    fparts = _parts(feature.location)
                    intersects = any(
                        _arc_intersects(int(part.start), int(part.end))
                        for part in fparts
                    )
                    if intersects:
                        raise ExecutionError(
                            "FEATURE_MAPPING_WRAPPED_GOLDEN_GATE",
                            "wrapped Golden Gate part contains an annotation that needs explicit origin mapping",
                            {"part": item["name"], "feature": feature.id or feature.type},
                        )
            else:
                for feature in source.features:
                    if feature.location is None:
                        continue
                    fparts = _parts(feature.location)
                    if all(start0 <= int(p.start) and int(p.end) <= end0
                           for p in fparts):
                        if part.get("reversed"):
                            feature_specs.append(_feature_spec_reversed(
                                feature, start0, end0, cursor))
                        else:
                            feature_specs.append(_feature_spec(
                                feature, cursor - start0))
                    elif any(int(p.start) < end0 and int(p.end) > start0
                             for p in fparts):
                        raise ExecutionError(
                            "FEATURE_MAPPING_PARTIAL_GOLDEN_GATE",
                            "Golden Gate cut clips a source feature; refusing to flatten it",
                            {"part": item["name"], "feature": feature.id or feature.type},
                        )
        cursor += length

    product = _record("golden_gate_product", final, "circular")
    return {
        "sequence": str(final).upper(),
        "feature_specs": feature_specs,
        "executor": "scripts.golden_gate.assemble",
        "status": "validated",
        "method": "golden_gate",
        "junctions": junctions,
        "parts": parts,
        "notes": notes,
        "circular": True,
    }


def _digest_ligate_product(fragments, topology_value, enzymes):
    if len(fragments) != 2 or not enzymes:
        raise ExecutionError(
            "DIGEST_LIGATE_REQUIRES_VECTOR_INSERT",
            "digest-ligate requires exactly one vector, one insert, and one enzyme",
        )
    from scripts.simulate_cloning import digest_ligate

    vector_source = fragments[0].get("_source_record")
    vector_interval = fragments[0].get("source_interval", [0, 0])
    if vector_source is not None:
        if vector_interval != [0, len(vector_source.seq)]:
            if vector_source.features:
                raise ExecutionError(
                    "DIGEST_VECTOR_FEATURE_MAPPING_UNSUPPORTED",
                    "digest-ligate vector interval is not the complete annotated record",
                    {"interval": vector_interval,
                     "feature_count": len(vector_source.features)},
                )
            vector = _record(fragments[0]["name"], fragments[0]["sequence"], "circular")
        else:
            vector = copy.deepcopy(vector_source)
            vector.id = fragments[0]["name"]
            vector.name = fragments[0]["name"]
            vector.annotations["topology"] = "circular"
    else:
        vector = _record(fragments[0]["name"], fragments[0]["sequence"], "circular")
    insert = _record(fragments[1]["name"], fragments[1]["sequence"], "linear")
    try:
        product, _parts, junctions = digest_ligate(vector, insert, enzymes[0])
    except Exception as error:
        code = getattr(error, "code", "DIGEST_LIGATE_EXECUTION_FAILED")
        raise ExecutionError(code, str(error), getattr(error, "details", {}))

    feature_specs = [_feature_spec(feature) for feature in product.features]
    # The simulator inserts the fragment at the vector top-cut boundary.  Add
    # a simple insert feature only after the real product has been obtained.
    insert_length = len(insert.seq)
    insert_start = next((int(f.location.start) for f in product.features
                         if f.qualifiers.get("label") == ["insert"]), 0)
    insert_end = next((int(f.location.end) for f in product.features
                       if f.qualifiers.get("label") == ["insert"]),
                      insert_start + insert_length)
    insert_feature = _misc_spec(
        fragments[1]["name"],
        insert_start, insert_end,
        fragments[1]["role"], fragments[1]["source_path"])
    feature_specs.append(insert_feature)
    # Preserve complete insert annotations in product coordinates.  A clipped
    # or compound feature is rejected rather than silently dropped.
    feature_specs.extend(_overlap_source_specs(
        fragments[1], insert_start, insert_length))
    return {
        "sequence": str(product.seq).upper(),
        "feature_specs": feature_specs,
        "executor": "scripts.simulate_cloning.digest_ligate",
        "status": "validated",
        "method": "digest-ligate",
        "junctions": junctions,
        "circular": True,
    }


def execute_assembly(fragments, method, topology_value, enzymes=None,
                     junctions=None):
    """Execute a planned method and return a validated product payload."""
    method = str(method or "").lower()
    if method in ("overlap", "gibson"):
        return _gibson_product(
            fragments, topology_value, junctions or [], method_name=method)
    if method == "golden_gate":
        return _golden_gate_product(fragments, topology_value, enzymes or [])
    if method == "digest-ligate":
        return _digest_ligate_product(fragments, topology_value, enzymes or [])
    raise ExecutionError("UNSUPPORTED_EXECUTION_METHOD",
                         "no deterministic executor for method %r" % method)
