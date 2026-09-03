# -*- coding: utf-8 -*-
"""core/tools/feature_ops.py - Atomic feature extraction and annotation tools.

Allows finding, filtering, and attaching biological features (promoters, CDS,
tags, terminators) to DNA records.
"""
from __future__ import annotations

import pathlib
from typing import Any

from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

from core.tools.inspection import _load_record
from core.interval import extract_interval


def get_feature(
    file_path_or_record: str | pathlib.Path | SeqRecord,
    name_or_type: str,
) -> dict[str, Any] | None:
    """Find and extract a specific feature by label/gene/product name or feature type.

    Returns:
        dict with name, type, interval_0based, strand, sequence, and qualifiers,
        or None if not found.
    """
    rec = _load_record(file_path_or_record)
    query_lower = str(name_or_type).strip().lower()

    for f in getattr(rec, "features", []):
        if f.type == "source":
            continue

        # Check label, gene, product, note
        names = []
        for q in ("label", "gene", "product", "note", "locus_tag"):
            vals = f.qualifiers.get(q)
            if vals and isinstance(vals, list):
                names.extend(str(v) for v in vals)
            elif vals:
                names.append(str(vals))

        type_match = (f.type.lower() == query_lower)
        name_match = any(query_lower in n.lower() for n in names)

        if name_match or type_match:
            s0 = int(f.location.start)
            e0 = int(f.location.end)
            strand = int(f.location.strand or 1)
            topo = rec.annotations.get("topology", "linear")

            seq = extract_interval(rec, s0, e0, topology=topo, strand=strand, whole_record_approved=True)

            matched_name = names[0] if names else f.type
            return {
                "name": matched_name,
                "type": f.type,
                "interval_0based": [s0, e0],
                "strand": strand,
                "length": len(seq),
                "sequence": seq.upper(),
                "qualifiers": {k: v for k, v in f.qualifiers.items()},
            }
    return None


def annotate_feature(
    record: SeqRecord,
    name: str,
    feature_type: str = "misc_feature",
    start: int = 0,
    end: int = 0,
    strand: int = 1,
    qualifiers: dict[str, Any] | None = None,
) -> SeqRecord:
    """Add a new annotated feature to a SeqRecord."""
    q = {"label": [name], "gene": [name]}
    if qualifiers:
        q.update(qualifiers)

    feat = SeqFeature(
        FeatureLocation(start, end, strand=strand),
        type=feature_type,
        qualifiers=q,
    )
    record.features.append(feat)
    return record
