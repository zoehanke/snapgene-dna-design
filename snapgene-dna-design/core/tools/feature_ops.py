# -*- coding: utf-8 -*-
"""core/tools/feature_ops.py - Atomic feature extraction, annotation, and migration tools.

Allows finding, filtering, attaching, and migrating biological features (promoters, CDS,
tags, terminators, origins) across recombinant DNA records.
"""
from __future__ import annotations

import pathlib
import copy
import re
from Bio.Seq import Seq
from typing import Any

from Bio.SeqFeature import CompoundLocation, FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

from core.tools.inspection import _load_record
from core.models.construct_model import feature_to_dict
from core.models.molecule import MoleculeInput, as_molecule, derived_molecule
from core.tools.result import ToolResult


FEATURE_ALIASES: dict[str, list[str]] = {
    "amp": ["amp", "ampr", "bla", "ampicillin", "ampicillin_res", "ampicillin resistance", "beta-lactamase"],
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


def get_feature(file_path_or_record: MoleculeInput, name_or_type: str,
                return_all: bool = False) -> ToolResult:
    """Select feature identities, never arbitrary substrings or annotation order."""
    source = as_molecule(file_path_or_record)
    query = str(name_or_type).strip().casefold()
    if not query:
        raise ValueError('Feature query must be nonempty')
    terms = {query}
    for canonical, aliases in FEATURE_ALIASES.items():
        if query == canonical or query in aliases:
            terms.update(aliases)
    # Controlled resistance labels are aliases, not substrings of protein names.
    if terms & {'kan', 'neo'}:
        terms.update({'neor', 'kanr'})
    candidates = []
    for index, feature in enumerate(source.features):
        if feature.type == 'source':
            continue
        values = []
        for key in ('label', 'gene', 'locus_tag', 'product'):
            item = feature.qualifiers.get(key, [])
            values.extend(str(v) for v in (item if isinstance(item, list) else [item]))
        if feature.id and feature.id != '<unknown id>':
            values.append(str(feature.id))
        folded = [v.strip().casefold() for v in values]
        tokens = {t.strip() for v in folded for t in re.split(r'[/;|+,]', v)}
        exact = query in folded
        alias = bool(terms & (set(folded) | tokens))
        type_match = feature.type.casefold() == query
        if exact or alias or type_match:
            candidates.append((0 if exact else 1 if alias else 2, index, feature, values))
    if not return_all and candidates:
        best_rank = min(c[0] for c in candidates)
        candidates = [c for c in candidates if c[0] == best_rank]
    if not return_all and len(candidates) != 1:
        reason = 'not found' if not candidates else 'ambiguous'
        raise ValueError(f'Feature selection {reason}: {name_or_type!r}; {len(candidates)} candidates; use return_all and explicit selection')
    products, matches = [], []
    from core.tools.sequence_ops import _clip_feature_to_interval
    for _, selected_index, selected, values in candidates:
        sequence = selected.extract(source.seq)
        record = SeqRecord(sequence, id=source.id, name=source.name,
                           description=source.description,
                           dbxrefs=list(source.dbxrefs),
                           annotations=copy.deepcopy(source.annotations))
        record.annotations['topology'] = 'linear'
        own_feature = copy.deepcopy(selected)
        own_parts=[]
        own_offset=0
        for part in selected.location.parts:
            length=len(part)
            local=FeatureLocation(part.start+(-int(part.start)),part.end+(-int(part.start)),strand=part.strand)
            if part.strand == -1:local=local._flip(length)
            own_parts.append(FeatureLocation(local.start+own_offset,local.end+own_offset,strand=1))
            own_offset+=length
        own_feature.location = own_parts[0] if len(own_parts)==1 else CompoundLocation(own_parts,operator=getattr(selected.location,'operator','join'))
        record.features = [own_feature]
        for key,values in source.letter_annotations.items():
            gathered=[]
            for part in selected.location.parts:
                piece=list(values[int(part.start):int(part.end)])
                gathered.extend(piece[::-1] if part.strand == -1 else piece)
            record.letter_annotations[key]=gathered
        mapping, offset = [], 0
        for part in selected.location.parts:
            start, end = int(part.start), int(part.end)
            mapping.append({'start0': start, 'end0': end, 'strand': part.strand})
            for index, feature in enumerate(source.features):
                if index == selected_index:
                    continue
                clipped = _clip_feature_to_interval(feature, start, end)
                if clipped is not None:
                    if part.strand == -1:
                        clipped = clipped._flip(end - start)
                    record.features.append(clipped._shift(offset))
            offset += end - start
        products.append(derived_molecule(record, [source], operation='get_feature',
                        strandedness=source.strandedness, mappings=[{'parts': mapping}]))
        matches.append({'name': values[0] if values else selected.type, 'type': selected.type,
                        'feature_index': selected_index, 'interval_0based': [int(selected.location.start), int(selected.location.end)],
                        'source_parts': mapping, 'strand': selected.location.strand,
                        'length': len(sequence), 'qualifiers': copy.deepcopy(selected.qualifiers)})
    return ToolResult(products=products, analysis={'matches': matches, 'match_count': len(matches)})


def annotate_feature(
    record: MoleculeInput,
    name: str,
    feature_type: str = "misc_feature",
    start: int = 0,
    end: int = 0,
    strand: int = 1,
    color: str = "",
    qualifiers: dict[str, Any] | None = None,
) -> ToolResult:
    """Add a new annotated feature to a SeqRecord with optional color."""
    source = as_molecule(record)
    if not 0 <= start < end <= len(source):
        raise ValueError('Feature interval must satisfy 0 <= start < end <= molecule length')
    record = copy.deepcopy(source)

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
    product = derived_molecule(record, [source], operation="annotate_feature",
                               strandedness=source.strandedness, left_end=source.left_end, right_end=source.right_end)
    return ToolResult(products=[product])


def migrate_features_after_assembly(
    fragments: list[dict[str, Any]],
    total_length: int,
    circular: bool = True,
) -> ToolResult:
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
                shift = frag_offset
                start = frag_offset + int(part.start)
                end = frag_offset + int(part.end)
                if part.ref is not None:
                    parts.append(copy.deepcopy(part))
                    continue
                if circular and total_length > 0:
                    shift -= (start // total_length) * total_length
                    start %= total_length
                    end = start + len(part)
                    if len(part) > total_length:
                        raise ValueError("Feature exceeds assembled molecule length")
                    if end > total_length:
                        split = [FeatureLocation(part.start + shift, total_length, strand=part.strand), FeatureLocation(0, part.end + shift-total_length, strand=part.strand)]
                        parts.extend(reversed(split) if part.strand == -1 else split)
                        continue
                if not 0 <= start <= end <= total_length:
                    raise ValueError("Feature falls outside assembled molecule")
                parts.append(FeatureLocation(part.start + shift, part.end + shift, strand=part.strand))
            feature.location = parts[0] if len(parts) == 1 else CompoundLocation(parts, operator=getattr(feature.location, "operator", "join"))
            new_feat = feature_to_dict(feature, total_length)
            new_feat["interval_0based"] = [int(feature.location.start), int(feature.location.end)]
            if new_feat not in migrated:
                migrated.append(new_feat)

    return ToolResult(analysis={'features': migrated})
