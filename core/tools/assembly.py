# -*- coding: utf-8 -*-
"""core/tools/assembly.py - Atomic DNA assembly and ligation simulation tool.

Simulates homologous overlap assembly (Gibson, In-Fusion) and restriction-ligation
cloning with junction verification and circularization.
"""
from __future__ import annotations

import hashlib
import pathlib
import sys
import copy
from typing import Any
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import CompoundLocation, FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

from core.models.assembly_model import (
    AssemblyError,
    AssemblyFragment,
    check_sticky_junctions,
    overhang_end,
)
from core.models.construct_model import ConstructModel, feature_to_dict
from core.tools.feature_ops import migrate_features_after_assembly
from core.tools.inspection import _load_record
from core.tools.restriction import get_enzyme, restriction_hits


def simulate_overlap_assembly(
    fragments: list[str | dict[str, Any]],
    min_overlap: int = 15,
    circular: bool = True,
) -> dict[str, Any]:
    """Simulate homologous overlap assembly (Gibson / In-Fusion).

    Args:
        fragments: List of DNA sequence strings, or dicts with 'sequence' field.
        min_overlap: Minimum overlap homology in base pairs.
        circular: Whether the assembled construct forms a closed circular plasmid.

    Returns:
        dict containing assembled product sequence, length, junctions, and topology.
    """
    records = [_load_record(f) for f in fragments]
    circular_inputs = [
        index + 1
        for index, record in enumerate(records)
        if str(record.annotations.get("topology", "linear")).lower() == "circular"
    ]
    if circular_inputs:
        raise ValueError(
            "Overlap assembly requires physically linear fragments; "
            "explicitly circular input fragment(s): %s"
            % ", ".join("fragment_%d" % index for index in circular_inputs)
        )
    seqs = [str(record.seq).upper() for record in records]

    if len(seqs) < 2:
        raise ValueError("Overlap assembly requires at least 2 fragments")

    n_frags = len(seqs)
    junctions = []

    # Check overlaps between adjacent fragments: seqs[i] and seqs[i+1]
    # For circular: also check seqs[-1] and seqs[0]
    num_junctions = n_frags if circular else (n_frags - 1)

    assembled_parts = []
    for i in range(num_junctions):
        f_left = seqs[i]
        f_right = seqs[(i + 1) % n_frags]

        # Find longest matching overlap at the junction
        best_ov = 0
        max_possible = min(len(f_left), len(f_right), 60)
        for ov_len in range(max_possible, min_overlap - 1, -1):
            if f_left[-ov_len:] == f_right[:ov_len]:
                best_ov = ov_len
                break

        if best_ov < min_overlap:
            between_desc = f"fragment_{i} and fragment_{(i + 1) % n_frags}"
            raise ValueError(
                f"Overlap mismatch between {between_desc}: required >= {min_overlap} bp homology, "
                f"found {best_ov} bp (tail: '{f_left[-min_overlap:]}' vs head: '{f_right[:min_overlap]}')"
            )

        junctions.append({
            "between": [i, (i + 1) % n_frags],
            "overlap_length": best_ov,
            "overlap_sequence": f_left[-best_ov:],
        })

    # Assemble sequence by trimming the shared overlap from each subsequent part
    product = seqs[0]
    for i in range(1, n_frags):
        ov = junctions[i - 1]["overlap_length"]
        product += seqs[i][ov:]

    if circular:
        # For circular assembly, the closing overlap between the last fragment and fragment 0
        # is already present at the start of fragment 0, so trim it from the end
        closing_ov = junctions[-1]["overlap_length"]
        product = product[:-closing_ov]

    feature_fragments = []
    offset = 0
    for i, record in enumerate(records):
        feature_fragments.append({
            "offset_in_product": offset, "length": len(record),
            "features": [feature_to_dict(f, len(record)) for f in record.features],
        })
        if i < len(junctions):
            offset += len(record) - junctions[i]["overlap_length"]

    return {
        "product_sequence": product,
        "product_length": len(product),
        "product_sha256": hashlib.sha256(product.encode("utf-8")).hexdigest().upper(),
        "product_topology": "circular" if circular else "linear",
        "features": migrate_features_after_assembly(feature_fragments, len(product), circular=circular),
        "fragment_count": n_frags,
        "junctions": junctions,
    }


def _arc(seq: str, start0: int, end0: int) -> str:
    n = len(seq)
    if n == 0:
        return ""
    raw_span = int(end0) - int(start0)
    start0 %= n
    end0 %= n
    length = n if raw_span and raw_span % n == 0 else (end0 - start0) % n
    if length == 0:
        return ""
    doubled = seq + seq
    return doubled[start0 : start0 + length]


def _arc_indices(length: int, start0: int, end0: int) -> list[int]:
    """Return source indices visited by a clockwise interval.

    Coordinates are boundaries, not bases.  Keeping this small helper next to
    ``_arc`` makes feature migration use exactly the same circular geometry as
    sequence extraction.
    """
    if length <= 0:
        return []
    raw_span = int(end0) - int(start0)
    start0 %= length
    end0 %= length
    span = length if raw_span and raw_span % length == 0 else (end0 - start0) % length
    return [(start0 + i) % length for i in range(span)]


def _feature_dicts_for_arc(record: SeqRecord, start0: int, end0: int) -> list[dict[str, Any]]:
    """Extract source features that survive a circular/linear arc.

    ``SeqRecord[start:end]`` cannot represent an origin-spanning interval and
    silently drops the useful mapping in that case.  This mapper keeps
    qualifiers and strands, splitting only the portions actually retained by
    the reaction.
    """
    source_len = len(record.seq)
    indices = _arc_indices(source_len, start0, end0)
    source_to_product = {source: i for i, source in enumerate(indices)}
    migrated: list[dict[str, Any]] = []
    for feature in getattr(record, "features", []):
        if feature.location is None:
            continue
        mapped_parts = []
        for part in getattr(feature.location, "parts", [feature.location]):
            run: list[int] = []
            runs: list[tuple[int, int]] = []
            for source in range(int(part.start), int(part.end)):
                mapped = source_to_product.get(source % source_len) if source_len else None
                if mapped is None:
                    if run:
                        runs.append((run[0], run[-1] + 1))
                        run = []
                    continue
                if run and mapped != run[-1] + 1:
                    runs.append((run[0], run[-1] + 1))
                    run = []
                run.append(mapped)
            if run:
                runs.append((run[0], run[-1] + 1))
            mapped_parts.extend(
                FeatureLocation(a, b, strand=part.strand) for a, b in runs if b > a
            )
        if not mapped_parts:
            continue
        copied = copy.deepcopy(feature)
        copied.location = (
            mapped_parts[0]
            if len(mapped_parts) == 1
            else CompoundLocation(mapped_parts, operator=getattr(feature.location, "operator", "join"))
        )
        migrated.append(feature_to_dict(copied, len(indices)))
    return migrated


def _shift_feature_dict(feature: dict[str, Any], offset: int, total_length: int) -> dict[str, Any]:
    """Shift a serialized feature while preserving lossless location parts."""
    shifted = copy.deepcopy(feature)
    location = shifted.get("location", {})
    parts = location.get("parts") or []
    for part in parts:
        part["start0"] = int(part["start0"]) + offset
        part["end0"] = int(part["end0"]) + offset
        part["start"] = int(part["start0"]) + 1
        part["end"] = int(part["end0"])
    if parts:
        shifted["start"] = min(int(p["start"]) for p in parts)
        shifted["end"] = max(int(p["end"]) for p in parts)
        shifted["interval_0based"] = [
            min(int(p["start0"]) for p in parts),
            max(int(p["end0"]) for p in parts),
        ]
    return shifted


def _type_iis_overhang(seq: str, hit: dict[str, Any]) -> tuple[str, str]:
    """Return (end kind, top-strand overhang motif) for one Type IIS cut."""
    raw_t = int(hit.get("raw_top_cut_boundary_0based", hit["top_cut_boundary_0based"]))
    raw_b = int(hit.get("raw_bottom_cut_boundary_0based", hit["bottom_cut_boundary_0based"]))
    if raw_t == raw_b:
        return "blunt", ""
    if raw_t < raw_b:
        return "5'-overhang", _arc(seq, hit["top_cut_boundary_0based"], hit["bottom_cut_boundary_0based"])
    return "3'-overhang", _arc(seq, hit["bottom_cut_boundary_0based"], hit["top_cut_boundary_0based"])


def _contains_recognition_site(fragment: str, enzyme: Any) -> bool:
    site = str(enzyme.site).upper()
    reverse = str(Seq(site).reverse_complement()).upper()
    upper = str(fragment).upper()
    return site in upper or reverse in upper


def type_iis_fragment(
    record: SeqRecord,
    enzyme: Any,
    topology_override: str | None = None,
    hits: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Excise one physically oriented Type IIS part from a complete template.

    A part is intentionally limited to exactly two in-sequence recognition
    sites.  This fail-closed default makes an internal site an explicit design
    error instead of silently choosing the outermost pair.  The returned
    sequence includes both cohesive overhangs once, so downstream ligation can
    assemble it without manufacturing bases.
    """
    from core.io.input_resolution import resolve_sequence_input

    rec, sequence = resolve_sequence_input(record)
    seq = str(sequence).upper()
    n = len(seq)
    part_topology = topology_override or rec.annotations.get("topology", "linear")
    if part_topology not in ("linear", "circular"):
        part_topology = "linear"
    circular = part_topology == "circular"
    all_hits = list(hits) if hits is not None else restriction_hits(seq, enzyme, circular=circular)
    all_hits = [h for h in all_hits if h.get("cuts_within_sequence", True)]
    if len(all_hits) != 2:
        reason = (
            "expected exactly 2 in-sequence %s recognition sites; found %d"
            % (getattr(enzyme, "__name__", str(enzyme)), len(all_hits))
        )
        if len(all_hits) > 2:
            reason += "; internal Type IIS site(s) require explicit redesign"
        return {"ok": False, "reason": reason, "hit_count": len(all_hits)}

    # Real restriction_hits supplies strand.  Test doubles and old callers did
    # not, so infer the conventional forward-left/reverse-right orientation
    # only when metadata is absent.
    ordered = sorted(all_hits, key=lambda h: int(h.get("recognition_start0", h.get("start", 1) - 1)))
    if hits is not None and not any(int(h.get("strand", 0)) == -1 for h in ordered):
        # Legacy CLI test doubles predate strand-aware restriction hits.  The
        # adapter supplies an explicit hit list, so infer its conventional
        # inward pair without weakening the real scan above.
        ordered[0]["strand"], ordered[1]["strand"] = 1, -1
    for index, hit in enumerate(ordered):
        hit.setdefault("strand", 1 if index == 0 else -1)

    candidates: list[dict[str, Any]] = []
    wrap_candidates = 0
    for left in ordered:
        if int(left.get("strand", 1)) != 1:
            continue
        for right in ordered:
            if right is left or int(right.get("strand", -1)) != -1:
                continue
            left_t_raw = int(left.get("raw_top_cut_boundary_0based", left["top_cut_boundary_0based"]))
            right_b_raw = int(right.get("raw_bottom_cut_boundary_0based", right["bottom_cut_boundary_0based"]))
            left_t = int(left["top_cut_boundary_0based"])
            right_b = int(right["bottom_cut_boundary_0based"])
            if not circular:
                if not (0 <= left_t_raw <= n and 0 <= right_b_raw <= n):
                    wrap_candidates += 1
                    continue
                if right_b_raw <= left_t_raw:
                    wrap_candidates += 1
                    continue
                start0, end0 = left_t_raw, right_b_raw
            else:
                start0, end0 = left_t % n, right_b % n
                if start0 >= end0:
                    wrap_candidates += 1

            fragment = _arc(seq, start0, end0)
            left_kind, left_overhang = _type_iis_overhang(seq, left)
            right_kind, right_overhang = _type_iis_overhang(seq, right)
            if not fragment:
                continue
            if _contains_recognition_site(fragment, enzyme):
                continue
            unique_length = len(fragment) - len(left_overhang) - len(right_overhang)
            if unique_length <= 0:
                return {
                    "ok": False,
                    "reason": "excised fragment (%d bp) is not longer than its overhang" % len(fragment),
                    "hit_count": len(all_hits),
                }
            candidates.append({
                "fragment": fragment,
                "insert_core": fragment,
                "left_overhang": left_overhang,
                "right_overhang": right_overhang,
                "left_kind": left_kind,
                "right_kind": right_kind,
                "overhang_length": len(left_overhang),
                "top_cut_start0": start0,
                "top_cut_end0": end0,
                "wraps_origin": bool(circular and start0 >= end0),
                "left_hit": left,
                "right_hit": right,
                "features": _feature_dicts_for_arc(rec, start0, end0),
            })

    if len(candidates) != 1:
        if wrap_candidates and not circular:
            reason = "the only inward-facing Type IIS fragment wraps the origin; linear input cannot use a wrap-around fragment"
        elif not candidates:
            reason = "no inward-facing fragment free of intact %s recognition sites" % getattr(enzyme, "__name__", str(enzyme))
        else:
            reason = "found multiple clean Type IIS fragment candidates; internal cut geometry is ambiguous"
        return {
            "ok": False,
            "reason": reason,
            "hit_count": len(all_hits),
            "clean_candidates": len(candidates),
            "wrap_candidates": wrap_candidates,
        }

    chosen = candidates[0]
    chosen.update({
        "ok": True,
        "topology": part_topology,
        "recognition_sites": [
            {
                "start_1based": h.get("start", int(h.get("recognition_start0", 0)) + 1),
                "end_1based": h.get("end"),
                "strand": h.get("strand"),
                "top_cut_boundary_0based": h.get("top_cut_boundary_0based"),
                "bottom_cut_boundary_0based": h.get("bottom_cut_boundary_0based"),
                "raw_top_cut_boundary_0based": h.get("raw_top_cut_boundary_0based", h.get("top_cut_boundary_0based")),
                "raw_bottom_cut_boundary_0based": h.get("raw_bottom_cut_boundary_0based", h.get("bottom_cut_boundary_0based")),
                "wraps_origin": h.get("wraps_origin", False),
            }
            for h in all_hits
        ],
    })
    return chosen


def _hit_end_sequences(seq: str, hit: dict) -> tuple[str, str, str]:
    """Return (kind, left_sequence, right_sequence) for one cut pair."""
    raw_t = hit.get("raw_top_cut_boundary_0based", hit["top_cut_boundary_0based"])
    raw_b = hit.get("raw_bottom_cut_boundary_0based", hit["bottom_cut_boundary_0based"])
    t = hit["top_cut_boundary_0based"]
    b = hit["bottom_cut_boundary_0based"]
    if raw_t == raw_b:
        return "blunt", "", ""
    if raw_t < raw_b:
        region = _arc(seq, t, b)
        return "5'-overhang", region, str(Seq(region).reverse_complement())
    region = _arc(seq, b, t)
    return "3'-overhang", str(Seq(region).reverse_complement()), region


_hit_end_sequences_three = _hit_end_sequences


def _vector_fragment(vector_rec: SeqRecord, enzyme: Any) -> tuple[AssemblyFragment, int]:
    seq = str(vector_rec.seq).upper()
    hits = restriction_hits(seq, enzyme, circular=True)
    hits = [h for h in hits if h["cuts_within_sequence"]]
    top = vector_rec.annotations.get("topology", "linear")
    if top != "circular":
        raise AssemblyError(
            "INVALID_TOPOLOGY",
            f"digest-ligate requires a circular vector; got {top}",
        )
    if len(hits) != 1:
        raise AssemblyError(
            "SITE_COUNT",
            f"digest-ligate requires exactly 1 vector recognition site; found {len(hits)}",
        )
    hit = hits[0]
    kind, left_ov, right_ov = _hit_end_sequences_three(seq, hit)
    source_cut = hit["top_cut_boundary_0based"] % len(seq)
    vector_frag = AssemblyFragment(
        vector_rec.name or "vector", seq, topology="linear",
        left_end=overhang_end(kind, left_ov, 0, source_cut_boundary=source_cut),
        right_end=overhang_end(kind, right_ov, len(seq), source_cut_boundary=source_cut),
        source=vector_rec.id,
    )
    return vector_frag, source_cut


def _restriction_insert_fragment(insert_rec: SeqRecord, enzyme: Any) -> AssemblyFragment:
    seq = str(insert_rec.seq).upper()
    circular = insert_rec.annotations.get("topology", "linear") == "circular"
    hits = restriction_hits(seq, enzyme, circular=circular)
    hits = [h for h in hits if h["cuts_within_sequence"]]
    if len(hits) != 2:
        raise AssemblyError(
            "SITE_COUNT",
            f"digest-ligate requires exactly 2 insert recognition sites with in-sequence cuts; found {len(hits)}",
        )
    site = str(enzyme.site).upper()
    rc_site = str(Seq(site).reverse_complement()).upper()
    h1, h2 = hits
    t1 = h1["top_cut_boundary_0based"] % len(seq)
    t2 = h2["top_cut_boundary_0based"] % len(seq)
    frag_a = _arc(seq, t1, t2)
    frag_b = _arc(seq, t2, t1)
    chosen = None
    for fragment, left_hit, right_hit in ((frag_a, h1, h2), (frag_b, h2, h1)):
        up = fragment.upper()
        if fragment and site not in up and rc_site not in up:
            chosen = (fragment, left_hit, right_hit)
            break
    if chosen is None:
        raise AssemblyError(
            "INSERT_EXCISION_FAILED",
            f"no internal insert fragment free of intact {enzyme} recognition sites",
        )
    fragment, left_hit, right_hit = chosen
    left_kind, left_ov, _left_right = _hit_end_sequences_three(seq, left_hit)
    right_kind, _right_left, right_ov = _hit_end_sequences_three(seq, right_hit)
    insert_frag = AssemblyFragment(
        insert_rec.name or "insert", fragment, topology="linear",
        left_end=overhang_end(
            left_kind, left_ov, 0,
            source_cut_boundary=left_hit["top_cut_boundary_0based"] % len(seq)),
        right_end=overhang_end(
            right_kind, right_ov, len(fragment),
            source_cut_boundary=right_hit["top_cut_boundary_0based"] % len(seq)),
        source=insert_rec.id,
    )
    return insert_frag


def digest_ligate(
    vector_rec: SeqRecord,
    insert_rec: SeqRecord,
    enzyme_name: str,
) -> tuple[SeqRecord, list[AssemblyFragment], list[dict[str, Any]]]:
    """Sticky-end ligation using the shared end model."""
    enzyme = get_enzyme(enzyme_name)
    vector_frag, vector_cut0 = _vector_fragment(vector_rec, enzyme)
    insert_frag = _restriction_insert_fragment(insert_rec, enzyme)

    junctions = check_sticky_junctions([vector_frag, insert_frag], circular=True)
    if any(j["compatibility"] == "MISMATCH" for j in junctions):
        raise AssemblyError(
            "STICKY_END_MISMATCH",
            "digest-ligation sticky ends are not complementary: %s"
            % "; ".join("%s: %s" % (j["between"], j["compatibility"]) for j in junctions),
            details=junctions,
        )

    ins_seq = insert_frag.sequence
    model = ConstructModel(vector_rec).insert(vector_cut0, ins_seq)
    model.set_topology("circular")
    product = model.to_record()
    product.id = "product"
    product.name = "product"
    product.description = "digest-ligation product"
    from core.tools.sequence_ops import extract_subsequence
    start = insert_frag.left_end.source_cut_boundary
    end = insert_frag.right_end.source_cut_boundary
    insert_record = _load_record(extract_subsequence(insert_rec, start, end, topology=insert_rec.annotations.get("topology", "linear")))
    product.features.extend(f._shift(vector_cut0) for f in insert_record.features)
    product.features.append(SeqFeature(
        FeatureLocation(vector_cut0, vector_cut0 + len(ins_seq), strand=1),
        type="misc_feature", qualifiers={"label": ["insert"]},
    ))
    return product, [vector_frag, insert_frag], junctions


def _reverse_feature_dicts(features: list[dict[str, Any]], length: int) -> list[dict[str, Any]]:
    """Reverse-complement serialized features without losing qualifiers."""
    from core.io.input_resolution import resolve_sequence_record

    record = resolve_sequence_record({"sequence": "N" * length, "features": features})
    record = record.reverse_complement(id=True, name=True, description=True, annotations=True)
    return [feature_to_dict(feature, length) for feature in record.features]


def _restriction_product_record(
    vector_rec: SeqRecord,
    vector_start: int,
    vector_end: int,
    insert_rec: SeqRecord,
    insert_start: int,
    insert_end: int,
    orientation: str = "forward",
) -> tuple[SeqRecord, list[dict[str, Any]], int]:
    """Build double-digest product while mapping retained source features.

    ``vector_start`` to ``vector_end`` is the clockwise vector interval
    replaced by the insert.  For a circular vector this may cross the origin.
    Product sequence keeps the original coordinate-zero representation when
    possible and records every retained source feature portion.
    """
    vseq = str(vector_rec.seq).upper()
    n = len(vseq)
    if not n:
        raise ValueError("Vector sequence is empty")
    vector_start %= n
    vector_end %= n
    if vector_start == vector_end:
        raise ValueError("Vector cut boundaries coincide")

    insert_seq = _arc(str(insert_rec.seq).upper(), insert_start, insert_end)
    if orientation == "reverse":
        insert_seq = str(Seq(insert_seq).reverse_complement())
        insert_features = _reverse_feature_dicts(
            _feature_dicts_for_arc(insert_rec, insert_start, insert_end),
            len(insert_seq),
        )
    else:
        insert_features = _feature_dicts_for_arc(insert_rec, insert_start, insert_end)

    if vector_start < vector_end:
        product_seq = vseq[:vector_start] + insert_seq + vseq[vector_end:]
        left_arc = (0, vector_start, 0)
        right_arc = (vector_end, n, vector_start + len(insert_seq))
        insert_offset = vector_start
    else:
        # The removed vector interval is [vector_start:n) + [0:vector_end).
        # The retained backbone is the complementary arc [vector_end,
        # vector_start).  Start the circular product at that retained arc so
        # no bases from the removed interval are copied into the result.  A
        # circular sequence has no privileged origin, and this representation
        # keeps source feature coordinates lossless for both arcs.
        product_seq = vseq[vector_end:vector_start] + insert_seq
        left_arc = (vector_end, vector_start, 0)
        right_arc = (0, 0, 0)
        insert_offset = vector_start - vector_end

    product = SeqRecord(
        Seq(product_seq),
        id="product",
        name="product",
        description="double restriction digest-ligation product",
        annotations={"molecule_type": "DNA", "topology": "circular"},
    )
    migrated: list[dict[str, Any]] = []
    for source_start, source_end, offset in (left_arc, right_arc):
        if source_end <= source_start:
            continue
        for feature in _feature_dicts_for_arc(vector_rec, source_start, source_end):
            migrated.append(_shift_feature_dict(feature, offset, len(product_seq)))
    migrated.extend(_shift_feature_dict(feature, insert_offset, len(product_seq)) for feature in insert_features)
    return product, migrated, insert_offset


def _restriction_backbone_score(record: SeqRecord, start0: int, end0: int) -> tuple[int, int]:
    """Score a retained vector arc by maintenance features, then length."""
    indices = set(_arc_indices(len(record.seq), start0, end0))
    maintenance_hits = 0
    for feature in getattr(record, "features", []):
        if feature.location is None:
            continue
        positions = {
            position % len(record.seq)
            for part in getattr(feature.location, "parts", [feature.location])
            for position in range(int(part.start), int(part.end))
        }
        if not positions or not positions.issubset(indices):
            continue
        text = " ".join(
            str(value)
            for key in ("label", "gene", "product", "note", "locus_tag")
            for value in feature.qualifiers.get(key, [])
        ).lower()
        if feature.type.lower() in {"rep_origin", "replication_origin"} or any(
            token in text
            for token in ("ori", "origin", "amp", "kan", "bla", "resistance", "marker", "neo", "tet", "cat")
        ):
            maintenance_hits += 1
    return maintenance_hits, len(indices)



def simulate_digest_ligation(
    vector_source: str | pathlib.Path | SeqRecord,
    insert_source: str | pathlib.Path | SeqRecord,
    vector_enzymes: list[str],
    insert_enzymes: list[str] | None = None,
    orientation: str = "auto",
) -> dict[str, Any]:
    """Simulate restriction-enzyme digestion and sticky-end ligation.

    Supports single-enzyme or double-enzyme directional cloning.
    """
    vec_rec = _load_record(vector_source)
    ins_rec = _load_record(insert_source)
    if orientation not in ("auto", "forward", "reverse"):
        raise ValueError("Insert orientation must be auto, forward, or reverse")

    enz = vector_enzymes
    ins_enz = insert_enzymes or enz

    if len(enz) == 1 and ins_enz == enz:
        # Single enzyme digest-ligation
        single_insert = ins_rec
        if orientation == "reverse":
            single_insert = ins_rec.reverse_complement(id=True, name=True, description=True, annotations=True)
        prod_rec, frags, junctions = digest_ligate(vec_rec, single_insert, enz[0])
        prod_seq = str(prod_rec.seq).upper()
        return {
            "product_sequence": prod_seq,
            "product_length": len(prod_seq),
            "product_sha256": hashlib.sha256(prod_seq.encode("utf-8")).hexdigest().upper(),
            "product_topology": "circular",
            "features": [feature_to_dict(f, len(prod_rec)) for f in prod_rec.features],
            "enzymes": enz,
            "junctions": junctions,
        }

    # Two-enzyme directional cloning.  Enzyme order is meaningful: enzyme5
    # defines the left side of the insert and enzyme3 the right side.  Do not
    # sort coordinates and accidentally swap those identities.
    if len(enz) != 2 or len(ins_enz) != 2:
        raise ValueError("Two-enzyme restriction ligation requires exactly two enzymes")
    if len(set(enz)) != 2:
        raise ValueError("Two-enzyme restriction ligation requires two distinct vector enzymes")

    vseq = str(vec_rec.seq).upper()
    iseq = str(ins_rec.seq).upper()
    if not vseq or not iseq:
        raise ValueError("Vector and insert sequences must be non-empty")

    def one_hit(sequence: str, enzyme_name: str, circular: bool, label: str) -> dict[str, Any]:
        enzyme_obj = get_enzyme(enzyme_name)
        hits = [h for h in restriction_hits(sequence, enzyme_obj, circular=circular)
                if h.get("cuts_within_sequence", True)]
        if len(hits) != 1:
            raise ValueError(f"{label} enzyme {enzyme_name} must cut exactly once; found {len(hits)} cuts")
        return hits[0]

    # A vector source denotes a plasmid in this recipe.  Explicitly annotated
    # linear records are still rejected; raw sequence compatibility is kept by
    # treating an unannotated string as a circular plasmid here.
    vector_topology = vec_rec.annotations.get("topology")
    source_path = None
    if isinstance(vector_source, (str, pathlib.Path)):
        try:
            source_path = pathlib.Path(str(vector_source))
        except (OSError, ValueError):
            source_path = None
    try:
        source_is_raw_sequence = isinstance(vector_source, str) and not (source_path and source_path.is_file())
    except OSError:
        source_is_raw_sequence = True
    if vector_topology == "linear" and not source_is_raw_sequence:
        raise ValueError("Two-enzyme restriction ligation requires a circular vector")
    vector_hits = [one_hit(vseq, e, True, "Vector") for e in enz]
    insert_hits = [one_hit(iseq, e, False, "Insert") for e in ins_enz]

    t5 = int(vector_hits[0]["top_cut_boundary_0based"]) % len(vseq)
    t3 = int(vector_hits[1]["top_cut_boundary_0based"]) % len(vseq)
    if t5 == t3:
        raise ValueError("Vector cut boundaries coincide")
    i5 = int(insert_hits[0]["top_cut_boundary_0based"]) % len(iseq)
    i3 = int(insert_hits[1]["top_cut_boundary_0based"]) % len(iseq)
    b5 = int(insert_hits[0]["bottom_cut_boundary_0based"])
    b3 = int(insert_hits[1]["bottom_cut_boundary_0based"])
    if i5 == i3:
        raise ValueError("Insert cut boundaries coincide")

    # The insert source is represented in its declared 5'->3' direction.  Its
    # two cloning sites must be inward-facing; the vector may require the
    # opposite orientation when its source record is stored in the reverse
    # direction (as happens for pET-28a(+)).
    e5_obj = get_enzyme(ins_enz[0])
    e3_obj = get_enzyme(ins_enz[1])
    e5_rc = str(Seq(str(e5_obj.site)).reverse_complement()).upper()
    e3_rc = str(Seq(str(e3_obj.site)).reverse_complement()).upper()
    orientation_error = (
        i5 >= i3
        or b5 >= b3
        or (e5_rc != str(e5_obj.site).upper() and int(insert_hits[0].get("strand", 1)) != 1)
        or (e3_rc != str(e3_obj.site).upper() and int(insert_hits[1].get("strand", -1)) != -1)
    )
    if orientation_error:
        raise ValueError(
            "Insert enzyme sites are not ordered as an inward-facing 5'->3' cloning fragment; "
            "check template orientation and enzyme assignments"
        )

    insert_forward = _arc(iseq, i5, i3)
    if _contains_recognition_site(insert_forward, e5_obj) or _contains_recognition_site(insert_forward, e3_obj):
        raise ValueError("Insert interval contains an internal cloning-enzyme recognition site")

    il_kind, il_ov, _ = _hit_end_sequences(iseq, insert_hits[0])
    ir_kind, _, ir_ov = _hit_end_sequences(iseq, insert_hits[1])
    insert_forward_frag = AssemblyFragment(
        "insert", insert_forward, topology="linear",
        left_end=overhang_end(il_kind, il_ov, 0, source_cut_boundary=i5),
        right_end=overhang_end(ir_kind, ir_ov, len(insert_forward), source_cut_boundary=i3),
        source=ins_rec.id,
    )
    insert_reverse_sequence = str(Seq(iseq[b5:b3]).reverse_complement())
    insert_reverse_frag = AssemblyFragment(
        "insert", insert_reverse_sequence, topology="linear",
        left_end=overhang_end(
            insert_forward_frag.right_end.kind,
            insert_forward_frag.right_end.overhang_sequence,
            0,
            source_cut_boundary=b3,
        ),
        right_end=overhang_end(
            insert_forward_frag.left_end.kind,
            insert_forward_frag.left_end.overhang_sequence,
            len(insert_reverse_sequence),
            source_cut_boundary=b5,
        ),
        source=ins_rec.id,
    )

    def build_orientation_candidate(candidate_orientation: str) -> dict[str, Any]:
        if candidate_orientation == "forward":
            replace_start, replace_end = t5, t3
            backbone_start, backbone_end = t3, t5
            left_hit, right_hit = vector_hits[1], vector_hits[0]
        else:
            replace_start, replace_end = t3, t5
            backbone_start, backbone_end = t5, t3
            left_hit, right_hit = vector_hits[0], vector_hits[1]
        left_kind, left_ov, _ = _hit_end_sequences(vseq, left_hit)
        right_kind, _, right_ov = _hit_end_sequences(vseq, right_hit)
        backbone_seq = _arc(vseq, backbone_start, backbone_end)
        backbone_frag = AssemblyFragment(
            "vector", backbone_seq, topology="linear",
            left_end=overhang_end(left_kind, left_ov, 0, source_cut_boundary=backbone_start),
            right_end=overhang_end(right_kind, right_ov, len(backbone_seq), source_cut_boundary=backbone_end),
            source=vec_rec.id,
        )
        insert_frag = insert_forward_frag if candidate_orientation == "forward" else insert_reverse_frag
        junctions = check_sticky_junctions([backbone_frag, insert_frag], circular=True)
        score = _restriction_backbone_score(vec_rec, backbone_start, backbone_end)
        return {
            "orientation": candidate_orientation,
            "replace_start": replace_start,
            "replace_end": replace_end,
            "backbone_start": backbone_start,
            "backbone_end": backbone_end,
            "backbone_fragment": backbone_frag,
            "insert_fragment": insert_frag,
            "junctions": junctions,
            "score": score,
            "compatible": not any(j["compatibility"] == "MISMATCH" for j in junctions),
        }

    requested_orientation = orientation
    if orientation == "auto":
        candidates = [build_orientation_candidate("forward"), build_orientation_candidate("reverse")]
        compatible = [candidate for candidate in candidates if candidate["compatible"]]
        if not compatible:
            raise ValueError(
                "Neither vector orientation yields complementary restriction ends: %s"
                % [candidate["junctions"] for candidate in candidates]
            )
        # Maintenance feature retention is the primary evidence.  When the
        # record has no maintenance annotations, auto cannot infer an intended
        # backbone from sequence length alone, so retain the historical
        # forward default.  Arc length only breaks ties after an annotated
        # maintenance signal exists.
        max_maintenance = max(candidate["score"][0] for candidate in compatible)
        if max_maintenance == 0:
            selected = next(
                (candidate for candidate in compatible if candidate["orientation"] == "forward"),
                compatible[0],
            )
        else:
            selected = max(compatible, key=lambda candidate: candidate["score"])
    else:
        selected = build_orientation_candidate(orientation)
        if not selected["compatible"]:
            raise ValueError(f"Sticky ends are not complementary: {selected['junctions']}")
    orientation = selected["orientation"]
    insert_frag = selected["insert_fragment"]
    junctions = selected["junctions"]

    # Build top-strand product with the vector's original origin.  The
    # replacement interval may cross the origin; no rotation or annotation
    # loss is needed.
    from core.io.input_resolution import resolve_sequence_record
    product_insert_sequence = insert_frag.sequence
    mapping_start, mapping_end = 0, len(product_insert_sequence)
    replacement_start = selected["replace_start"]
    replacement_end = selected["replace_end"]
    insert_feature_dicts = (
        _reverse_feature_dicts(_feature_dicts_for_arc(ins_rec, b5, b3), len(insert_reverse_sequence))
        if orientation == "reverse"
        else _feature_dicts_for_arc(ins_rec, i5, i3)
    )
    insert_rec_for_mapping = resolve_sequence_record({
        "sequence": product_insert_sequence,
        "features": insert_feature_dicts,
        "topology": "linear",
    })
    prod_rec, migrated_features, insert_offset = _restriction_product_record(
        vec_rec,
        replacement_start,
        replacement_end,
        insert_rec_for_mapping,
        mapping_start,
        mapping_end,
        orientation="forward",
    )
    prod_rec.features = []
    # ``migrated_features`` are serialized lossless locations.  Rehydrate them
    # once so every downstream recipe/export path sees the same annotations.
    prod_rec.features = resolve_sequence_record({
        "sequence": str(prod_rec.seq),
        "topology": "circular",
        "features": migrated_features,
    }).features
    prod_rec.features.append(SeqFeature(
        FeatureLocation(insert_offset, insert_offset + len(product_insert_sequence), strand=1),
        type="misc_feature",
        qualifiers={"label": ["insert"]},
    ))
    prod_seq = str(prod_rec.seq).upper()

    return {
        "product_sequence": prod_seq,
        "product_length": len(prod_seq),
        "product_sha256": hashlib.sha256(prod_seq.encode("utf-8")).hexdigest().upper(),
        "product_topology": "circular",
        "features": [feature_to_dict(f, len(prod_rec)) for f in prod_rec.features],
        "vector_cuts_0based": [t5, t3],
        "insert_cuts_0based": [i5, i3],
        "insert_bottom_cuts_0based": [b5, b3],
        "insert_retained_interval_0based": [b5, b3] if orientation == "reverse" else [i5, i3],
        "vector_cuts_by_enzyme": {enz[0]: t5, enz[1]: t3},
        "insert_cuts_by_enzyme": {ins_enz[0]: i5, ins_enz[1]: i3},
        "insert_orientation": orientation,
        "orientation_requested": requested_orientation,
        "backbone_score": selected["score"],
        "vector_replacement_interval_0based": [replacement_start, replacement_end],
        "junctions": junctions,
        "insert_sequence_after_orientation": product_insert_sequence,
        "insert_feature_offset": insert_offset,
    }


def simulate_golden_gate(
    fragments: list[str | dict[str, Any] | pathlib.Path | SeqRecord],
    enzyme: str = "BsaI",
    circular: bool = True,
) -> dict[str, Any]:
    """Simulate Type IIS Golden Gate one-pot multi-fragment assembly.

    Digests each fragment with the specified Type IIS enzyme (e.g. BsaI, BsmBI, Esp3I),
    liberating inserts between inward-facing recognition sites with 4-bp sticky overhangs,
    verifies junction complementarity, and ligates fragments.
    """
    enz = get_enzyme(enzyme)
    if len(fragments) < 2:
        raise ValueError("Golden Gate assembly requires at least 2 fragments")

    digested_frags: list[dict[str, Any]] = []
    assembly_fragments: list[AssemblyFragment] = []
    for idx, source in enumerate(fragments):
        from core.io.input_resolution import resolve_sequence_input

        rec, seq = resolve_sequence_input(source, record_id=f"frag_{idx + 1}")
        fid = (source.get("id") if isinstance(source, dict) else rec.id) or f"frag_{idx + 1}"
        # In a circular product the first part is the destination recipient in
        # the legacy API.  Raw strings have no topology annotation, so retain
        # that established convention while respecting explicit record data.
        explicit_topology = rec.annotations.get("topology")
        part_topology = explicit_topology or ("circular" if circular and idx == 0 else "linear")
        info = type_iis_fragment(rec, enz, topology_override=part_topology)
        if not info.get("ok"):
            raise ValueError(f"Fragment {fid}: {info.get('reason', 'Type IIS excision failed')}")
        info["id"] = fid
        info["original_length"] = len(seq)
        info["left_cut"] = info["top_cut_start0"]
        info["right_cut"] = info["top_cut_end0"]
        info["source_topology"] = part_topology
        # Backward-compatible key, now representing the actual cut product.
        info["insert_core"] = info["fragment"]
        digested_frags.append(info)

        right_storage = (
            str(Seq(info["right_overhang"]).reverse_complement())
            if info["right_overhang"] else ""
        )
        assembly_fragments.append(AssemblyFragment(
            fid,
            info["fragment"],
            topology="linear",
            left_end=overhang_end(info["left_kind"], info["left_overhang"], 0),
            right_end=overhang_end(info["right_kind"], right_storage, len(info["fragment"])),
            source=rec.id,
        ))

    num = len(digested_frags)
    junctions = check_sticky_junctions(assembly_fragments, circular=circular)
    for index, junction in enumerate(junctions):
        current = digested_frags[index]
        following = digested_frags[(index + 1) % num]
        compatible = junction["compatibility"] == "ok"
        junction.update({
            "junction_index": index,
            "from_fragment": current["id"],
            "to_fragment": following["id"],
            "from_overhang": current["right_overhang"],
            "to_overhang": following["left_overhang"],
            "compatible": compatible,
            "overhang_sequence": current["right_overhang"],
        })
        if not compatible:
            raise ValueError(
                f"Golden Gate overhang mismatch between {current['id']} ({current['right_overhang']}) "
                f"and {following['id']} ({following['left_overhang']})"
            )

    # Each physical fragment contains both terminal overhangs.  A junction is
    # represented once by keeping the upstream right motif and trimming the
    # downstream left motif.  Circular closure removes the final motif that is
    # already present at the product origin.
    product = digested_frags[0]["fragment"]
    feature_fragments = [{
        "offset_in_product": 0,
        "length": len(digested_frags[0]["fragment"]),
        "features": digested_frags[0].get("features", []),
    }]
    for index in range(1, num):
        current = digested_frags[index]
        left_len = len(current["left_overhang"])
        offset = len(product) - left_len
        feature_fragments.append({
            "offset_in_product": offset,
            "length": len(current["fragment"]),
            "features": current.get("features", []),
        })
        product += current["fragment"][left_len:]
    if circular:
        final_right_len = len(digested_frags[-1]["right_overhang"])
        if final_right_len:
            product = product[:-final_right_len]

    return {
        "product_sequence": product,
        "product_length": len(product),
        "product_sha256": hashlib.sha256(product.encode("utf-8")).hexdigest().upper(),
        "product_topology": "circular" if circular else "linear",
        "enzyme": enzyme,
        "features": migrate_features_after_assembly(feature_fragments, len(product), circular=circular),
        "fragment_count": num,
        "junctions": junctions,
        "fragments": digested_frags,
        "recognition_sites_remaining": [
            h for h in restriction_hits(product, enz, circular=circular)
            if h.get("cuts_within_sequence", True)
        ],
    }
