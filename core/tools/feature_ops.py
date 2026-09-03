# -*- coding: utf-8 -*-
"""core/tools/feature_ops.py - Atomic feature extraction, annotation, and migration tools.

Allows finding, filtering, attaching, and migrating biological features (promoters, CDS,
tags, terminators, origins) across recombinant DNA records.
"""
from __future__ import annotations

import pathlib
from typing import Any

from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

from core.tools.inspection import _load_record
from core.interval import extract_interval


FEATURE_ALIASES: dict[str, list[str]] = {
    "amp": ["amp", "ampr", "bla", "ampicillin", "beta-lactamase"],
    "kan": ["kan", "kanr", "aph", "kanamycin", "neomycin", "neo"],
    "cm": ["cm", "cmr", "cat", "chloramphenicol"],
    "tet": ["tet", "tetr", "tetracycline"],
    "ori": ["ori", "origin", "rep_origin", "pucc_ori", "colie1_ori"],
    "gfp": ["gfp", "egfp", "sfgfp", "mneongreen"],
    "mcherry": ["mcherry", "rfp", "dsred"],
    "his": ["his", "6xhis", "polyhistidine", "his-tag"],
    "flag": ["flag", "3xflag", "flag-tag"],
}


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
            topo = rec.annotations.get("topology", "linear")

            seq = extract_interval(rec, s0, e0, topology=topo, strand=strand, whole_record_approved=True)
            matched_name = names[0] if names else f.type

            feat_dict = {
                "name": matched_name,
                "type": f.type,
                "interval_0based": [s0, e0],
                "strand": strand,
                "length": len(seq),
                "sequence": seq.upper(),
                "qualifiers": {k: v for k, v in f.qualifiers.items()},
            }
            if not return_all:
                return feat_dict
            matches.append(feat_dict)

    if return_all:
        return matches
    return None


def annotate_feature(
    record: SeqRecord,
    name: str,
    feature_type: str = "misc_feature",
    start: int = 0,
    end: int = 0,
    strand: int = 1,
    color: str = "",
    qualifiers: dict[str, Any] | None = None,
) -> SeqRecord:
    """Add a new annotated feature to a SeqRecord with optional color."""
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

        for feat in frag.get("features", []):
            orig_s0, orig_e0 = feat["interval_0based"]
            orig_strand = feat.get("strand", 1)

            if frag_strand == 1:
                # Forward insertion
                new_s0 = frag_offset + orig_s0
                new_e0 = frag_offset + orig_e0
                new_strand = orig_strand
            else:
                # Reverse complemented insertion
                new_s0 = frag_offset + (frag_len - orig_e0)
                new_e0 = frag_offset + (frag_len - orig_s0)
                new_strand = -orig_strand

            # Circular wrap handling
            if circular and total_length > 0:
                new_s0 = new_s0 % total_length
                new_e0 = new_e0 % total_length

            new_feat = dict(feat)
            new_feat["interval_0based"] = [new_s0, new_e0]
            new_feat["strand"] = new_strand
            migrated.append(new_feat)

    return migrated
