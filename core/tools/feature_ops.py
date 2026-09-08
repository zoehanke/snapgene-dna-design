# -*- coding: utf-8 -*-
"""core/tools/feature_ops.py - Atomic feature extraction, annotation, and migration tools.

Allows finding, filtering, attaching, and migrating biological features (promoters, CDS,
tags, terminators, origins) across recombinant DNA records.
"""
from __future__ import annotations

import pathlib
import copy
from typing import Any

from Bio.SeqFeature import CompoundLocation, FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

from core.tools.inspection import _load_record
from core.models.construct_model import feature_to_dict


FEATURE_ALIASES: dict[str, list[str]] = {
    "amp": ["amp", "ampr", "bla", "ampicillin", "beta-lactamase"],
    "kan": ["kan", "kanr", "aph", "kanamycin", "neomycin", "neo"],
    "cm": ["cm", "cmr", "cat", "chloramphenicol"],
    "tet": ["tet", "tetr", "tetracycline"],
    "ori": ["ori", "origin", "rep_origin", "pucc_ori", "colie1_ori"],
    "gfp": ["gfp", "egfp", "sfgfp"],
    "mcherry": ["mcherry", "rfp", "dsred"],
    "his": ["his", "6xhis", "polyhistidine", "his-tag"],
    "flag": ["flag", "3xflag", "flag-tag"],
}


def canonical_location_parts(location):
    """Treat contiguous join segments as one interval; preserve order and real gaps."""
    operator = getattr(location, "operator", None) or ""
    parts = []
    for part in location.parts:
        current = (int(part.start), int(part.end), part.strand or 0)
        if operator == "join" and parts and parts[-1][2] == current[2]:
            previous = parts[-1]
            adjacent = (previous[0] == current[1] if current[2] == -1 else previous[1] == current[0])
            if adjacent:
                parts[-1] = (min(previous[0], current[0]), max(previous[1], current[1]), current[2])
                continue
        parts.append(current)
    return (operator if len(parts) > 1 else "", tuple(parts))


def get_feature(
    file_path_or_record: str | pathlib.Path | SeqRecord,
    name_or_type: str,
    return_all: bool = False,
) -> dict[str, Any] | list[dict[str, Any]] | None:
    """Find and extract specific feature(s) by label/gene/product name, feature type, or alias.

    Args:
        file_path_or_record: Input sequence file or SeqRecord
        name_or_type: Name, type, or alias (e.g. "AmpR", "CDS", "ori")
        return_all: If True, returns a list of all matching features. If False, returns the first match or None.

    Returns:
        dict or list[dict] with name, type, interval_0based, strand, sequence, qualifiers.
    """
    rec = _load_record(file_path_or_record)
    query_lower = str(name_or_type).strip().lower()

    # Expand query terms using alias dictionary
    search_terms = {query_lower}
    for key, aliases in FEATURE_ALIASES.items():
        if query_lower == key or query_lower in aliases:
            search_terms.update(aliases)

    matches = []
    for f in getattr(rec, "features", []):
        if f.type == "source":
            continue

        names = []
        for q in ("label", "gene", "product", "note", "locus_tag"):
            vals = f.qualifiers.get(q)
            if vals and isinstance(vals, list):
                names.extend(str(v) for v in vals)
            elif vals:
                names.append(str(vals))

        type_match = (f.type.lower() in search_terms)
        name_match = any(any(st in n.lower() for st in search_terms) for n in names)

        if name_match or type_match:
            s0 = int(f.location.start)
            e0 = int(f.location.end)
            strand = int(f.location.strand or 1)
            seq = str(f.extract(rec.seq))
            matched_name = names[0] if names else f.type
            extracted_feature = copy.deepcopy(f)
            extracted_feature.location = FeatureLocation(0, len(seq), strand=1)

            feat_dict = {
                "name": matched_name,
                "type": f.type,
                "interval_0based": [s0, e0],
                "strand": strand,
                "length": len(seq),
                "sequence": seq.upper(),
                "qualifiers": {k: v for k, v in f.qualifiers.items()},
                "features": [feature_to_dict(extracted_feature, len(seq))],
                "topology": "linear",
            }
            if not return_all:
                return feat_dict
            matches.append(feat_dict)

    if return_all:
        return matches
    return None


def annotate_feature(
    record: SeqRecord | str | pathlib.Path,
    name: str,
    feature_type: str = "misc_feature",
    start: int = 0,
    end: int = 0,
    strand: int = 1,
    color: str = "",
    qualifiers: dict[str, Any] | None = None,
) -> SeqRecord:
    """Add a new annotated feature to a SeqRecord with optional color."""
    if not isinstance(record, SeqRecord):
        from core.io.input_resolution import resolve_sequence_record
        record = resolve_sequence_record(record)

    q: dict[str, list[str]] = {"label": [name], "gene": [name]}
    if color:
        q["ApEinfo_fcolor"] = [color]
        q["note"] = [f"color: {color}"]
    if qualifiers:
        for k, v in qualifiers.items():
            if isinstance(v, list):
                q[k] = [str(item) for item in v]
            else:
                q[k] = [str(v)]

    loc = FeatureLocation(start, end, strand=strand)
    feat = SeqFeature(loc, type=feature_type, qualifiers=q)
    record.features.append(feat)
    return record


def migrate_features_after_assembly(
    fragments: list[dict[str, Any]],
    total_length: int,
    circular: bool = True,
) -> list[dict[str, Any]]:
    """Recalculate and migrate feature coordinates after multi-fragment assembly.

    Args:
        fragments: List of fragments, each with:
            - "offset_in_product": starting 0-based index of this fragment in product
            - "length": fragment length in product (after overlap trimming)
            - "features": list of feature dicts from the source fragment
            - "strand": 1 if forward in product, -1 if reverse complemented
        total_length: Total length of assembled product
        circular: Whether product is circular

    Returns:
        List of updated feature dicts with 'interval_0based' remapped to product.
    """
    migrated = []
    for frag in fragments:
        frag_offset = frag.get("offset_in_product", 0)
        frag_len = frag.get("length", 0)
        frag_strand = frag.get("strand", 1)

        from core.io.input_resolution import resolve_sequence_record
        record = resolve_sequence_record({"sequence": "N" * frag_len, "features": frag.get("features", [])})
        if frag_strand == -1:
            record = record.reverse_complement()
        for feature in record.features:
            parts = []
            for part in feature.location.parts:
                start = frag_offset + int(part.start)
                end = start + len(part)
                if circular and total_length > 0:
                    start %= total_length
                    end = start + len(part)
                    if len(part) > total_length:
                        raise ValueError("Feature exceeds assembled molecule length")
                    if end > total_length:
                        split = [FeatureLocation(start, total_length, strand=part.strand), FeatureLocation(0, end - total_length, strand=part.strand)]
                        parts.extend(reversed(split) if part.strand == -1 else split)
                        continue
                if not 0 <= start <= end <= total_length:
                    raise ValueError("Feature falls outside assembled molecule")
                parts.append(FeatureLocation(start, end, strand=part.strand))
            feature.location = parts[0] if len(parts) == 1 else CompoundLocation(parts, operator=getattr(feature.location, "operator", "join"))
            new_feat = feature_to_dict(feature, total_length)
            new_feat["interval_0based"] = [int(feature.location.start), int(feature.location.end)]
            if new_feat not in migrated:
                migrated.append(new_feat)

    return migrated
