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
from core.tools.result import ToolResult

from Bio.Seq import Seq
from Bio.SeqFeature import CompoundLocation, FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord


def _prepared_source(item):
    from core.tools.sequence_ops import extract_subsequence
    from core.models.molecule import as_molecule
    source=item['_source_record']
    start,end=item['source_interval']
    if start==0 and end==len(source) and int(item.get('_extraction_strand') or 1)==1:return as_molecule(source)
    return extract_subsequence(source,start,end,strand=int(item.get('_extraction_strand') or 1)).only_product()


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
    from core.tools.assembly import simulate_overlap_assembly

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
        if pcr is not None and not isinstance(pcr,ToolResult):
            raise ExecutionError('PREPARATION_RESULT_CONTRACT','Use actual molecular products, not a declared amplicon string')
        if pcr_required and (pcr is None or not pcr.products):
            raise ExecutionError(
                "PCR_PRODUCT_REQUIRED",
                "assembly fragment %r has no simulated product from its selected primers"
                % item.get("name", index),
                {"fragment": item.get("name", index)},
            )
        raw = str(str(pcr.only_product().seq) if pcr_required else item["sequence"]).upper()
        if pcr_required:
            pcr_products.append(pcr)
        raw_offsets.append(cursor)
        cursor += len(str(item["sequence"]))
        # The complete 5' tails are already present in the selected-primer
        # PCR product. Feeding the ideal source fragment here would discard
        # the delivered primer sequences.
        records.append(pcr.only_product() if pcr_required else _prepared_source(item))

    try:
        actual = simulate_overlap_assembly(records, min_overlap=overlap, circular=circular,
                                          fragment_labels=[item['name'] for item in fragments])
        product = actual.only_product()
        contributions = actual.analysis['junctions']
        warnings = []
    except Exception as error:  # AssemblyError is intentionally normalized.
        code = getattr(error, "code", "ASSEMBLY_EXECUTION_FAILED")
        raise ExecutionError(code, str(error), getattr(error, "details", {}))

    expected = "".join(str(item["sequence"]).upper() for item in fragments)
    # Homology may be carried on either primer. A circular molecule can then
    # start at a different base; rotate the actual product, never replace it.
    if circular and len(product.seq) == len(expected) and str(product.seq).upper() != expected:
        offset = (str(product.seq).upper()*2).find(expected)
        if 0 <= offset < len(product):
            from core.models.construct_model import ConstructModel
            from core.models.molecule import derived_molecule
            product = derived_molecule(ConstructModel(product).rotate(offset).to_record(),[product],operation='rotate',strandedness=product.strandedness)
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

    feature_specs = [_feature_spec(f) for f in product.features]
    return {
        "sequence": str(product.seq).upper(),
        "product_molecule": product.to_dict(),
        "feature_specs": feature_specs,
        "executor": "core.tools.assembly.simulate_overlap_assembly",
        "status": "validated",
        "method": method_name,
        "overlap_length": overlap,
        "contributions": contributions,
        "pcr_products": [
            {
                "amplicon_length": int(
                    pcr.analysis.get("amplicon_length", len(pcr.only_product()))
                ),
                "template": pcr.analysis.get("template"),
                "primers": pcr.analysis.get("primers", []),
                "template_interval_0based": pcr.analysis.get("template_interval_0based"),
                "forward_binding": pcr.analysis.get("forward_binding"),
                "reverse_binding": pcr.analysis.get("reverse_binding"),
            }
            for pcr in pcr_products
        ],
        "warnings": warnings,
        "circular": circular,
    }


def _golden_gate_product(fragments, topology_value, enzymes):
    from core.tools.assembly import simulate_golden_gate
    if not enzymes or len(enzymes)!=1:
        raise ExecutionError('GOLDEN_GATE_ENZYME_REQUIRED','One Type IIS enzyme is required')
    records=[]
    for item in fragments:
        pcr=item.get('_pcr_product')
        if item.get('_pcr_required',True) and pcr is None:
            raise ExecutionError('PCR_PRODUCT_REQUIRED','Actual PCR material is required')
        records.append(pcr.only_product() if pcr is not None else _prepared_source(item))
    try:
        result=simulate_golden_gate(records,enzyme=enzymes[0],circular=topology_value=='circular')
    except Exception as exc:
        raise ExecutionError(getattr(exc,'error_code','GOLDEN_GATE_EXECUTION_FAILED'),str(exc)) from exc
    product=result.only_product()
    return {'sequence':str(product.seq),'product_molecule':product.to_dict(),
            'feature_specs':[_feature_spec(f) for f in product.features],
            'executor':'core.tools.assembly.simulate_golden_gate','status':'validated',
            'method':'golden_gate','junctions':result.analysis['junctions'],
            'parts':result.analysis['fragments'],'notes':[],'circular':product.topology=='circular'}


def _digest_ligate_product(fragments, topology_value, enzymes):
    if len(fragments) != 2 or len(enzymes or []) not in (1, 2):
        raise ExecutionError(
            "DIGEST_LIGATE_REQUIRES_VECTOR_INSERT",
            "digest-ligate requires one vector, one insert, and one or two enzymes",
        )
    if topology_value != "circular":
        raise ExecutionError("DIGEST_PRODUCT_TOPOLOGY", "Plasmid digest-ligation produces a circular product")
    from core.io.input_resolution import resolve_sequence_record
    from core.tools.assembly import simulate_digest_ligation
    from core.tools.sequence_ops import slice_record_interval

    records = []
    for fragment in fragments:
        pcr = fragment.get("_pcr_product")
        if pcr is not None:
            record = pcr.only_product()
        else:
            source = fragment.get("_source_record")
            if source is None:
                raise ExecutionError("DIGEST_SOURCE_RECORD_REQUIRED", "Native digestion requires the actual source record")
            start, end = fragment["source_interval"]
            if start == 0 and end == len(source) and int(fragment.get("_extraction_strand") or 1) == 1:
                record = copy.deepcopy(source)
            else:
                length = end-start if end >= start else len(source)-start+end
                record = slice_record_interval(source, start, length, circular=source.annotations.get("topology") == "circular")
                if int(fragment.get("_extraction_strand") or 1) == -1:
                    record = record.reverse_complement(annotations=True)
            if str(record.seq).upper() != fragment["sequence"].upper():
                raise ExecutionError("DIGEST_FRAGMENT_RECORD_MISMATCH", "Selected fragment is not a contiguous physical digestion substrate")
        # Product identity belongs to the producing operation, not this consumer.
        records.append(record)
    try:
        result = simulate_digest_ligation(records[0], records[1], list(enzymes), orientation="forward")
    except Exception as error:
        code = getattr(error, "code", "DIGEST_LIGATE_EXECUTION_FAILED")
        raise ExecutionError(code, str(error), getattr(error, "details", {}))
    product = result.only_product()
    return {
        "sequence": str(product.seq).upper(),
        "product_molecule": product.to_dict(),
        "feature_specs": [_feature_spec(feature) for feature in product.features],
        "executor": "core.tools.assembly.simulate_digest_ligation",
        "status": "validated",
        "method": "digest-ligate",
        "junctions": result.analysis['junctions'],
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
