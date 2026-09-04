# -*- coding: utf-8 -*-
"""core/tools/assembly.py - Atomic DNA assembly and ligation simulation tool.

Simulates homologous overlap assembly (Gibson, In-Fusion) and restriction-ligation
cloning with junction verification and circularization.
"""
from __future__ import annotations

import hashlib
import pathlib
import sys
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

from core.models.assembly_model import (
    AssemblyError,
    AssemblyFragment,
    check_sticky_junctions,
    overhang_end,
)
from core.models.construct_model import ConstructModel
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
    seqs = []
    for f in fragments:
        if isinstance(f, dict):
            seqs.append(str(f["sequence"]).upper())
        else:
            seqs.append(str(f).upper())

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

    return {
        "product_sequence": product,
        "product_length": len(product),
        "product_sha256": hashlib.sha256(product.encode("utf-8")).hexdigest().upper(),
        "product_topology": "circular" if circular else "linear",
        "fragment_count": n_frags,
        "junctions": junctions,
    }


def _arc(seq: str, start0: int, end0: int) -> str:
    n = len(seq)
    if n == 0:
        return ""
    start0 %= n
    end0 %= n
    length = (end0 - start0) % n
    if length == 0:
        return ""
    doubled = seq + seq
    return doubled[start0 : start0 + length]


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
    product.features.append(SeqFeature(
        FeatureLocation(vector_cut0, vector_cut0 + len(ins_seq), strand=1),
        type="misc_feature", qualifiers={"label": ["insert"]},
    ))
    return product, [vector_frag, insert_frag], junctions



def simulate_digest_ligation(
    vector_source: str | pathlib.Path | SeqRecord,
    insert_source: str | pathlib.Path | SeqRecord,
    vector_enzymes: list[str],
    insert_enzymes: list[str] | None = None,
    orientation: str = "forward",
) -> dict[str, Any]:
    """Simulate restriction-enzyme digestion and sticky-end ligation.

    Supports single-enzyme or double-enzyme directional cloning.
    """
    vec_rec = _load_record(vector_source)
    ins_rec = _load_record(insert_source)

    enz = vector_enzymes
    ins_enz = insert_enzymes or enz

    if len(enz) == 1 and ins_enz == enz:
        # Single enzyme digest-ligation
        prod_rec, frags, junctions = digest_ligate(vec_rec, ins_rec, enz[0])
        prod_seq = str(prod_rec.seq).upper()
        return {
            "product_sequence": prod_seq,
            "product_length": len(prod_seq),
            "product_sha256": hashlib.sha256(prod_seq.encode("utf-8")).hexdigest().upper(),
            "product_topology": "circular",
            "enzymes": enz,
            "junctions": junctions,
        }

    # Two-enzyme directional cloning
    if len(enz) != 2 or len(ins_enz) != 2:
        raise ValueError("Two-enzyme restriction ligation requires exactly two enzymes")

    if orientation == "reverse":
        ins_rec = ins_rec.reverse_complement(id=True, name=True, description=True)

    vseq = str(vec_rec.seq).upper()
    iseq = str(ins_rec.seq).upper()

    vector_hits = []
    for e in enz:
        ez = get_enzyme(e)
        hits = [h for h in restriction_hits(vseq, ez, circular=True) if h["cuts_within_sequence"]]
        if len(hits) != 1:
            raise ValueError(f"Vector enzyme {e} must cut exactly once; found {len(hits)} cuts")
        vector_hits.append(hits[0])

    insert_hits = []
    for e in ins_enz:
        ez = get_enzyme(e)
        hits = [h for h in restriction_hits(iseq, ez, circular=False) if h["cuts_within_sequence"]]
        if len(hits) != 1:
            raise ValueError(f"Insert enzyme {e} must cut exactly once; found {len(hits)} cuts")
        insert_hits.append(hits[0])

    n = len(vseq)
    t1 = vector_hits[0]["top_cut_boundary_0based"] % n
    t2 = vector_hits[1]["top_cut_boundary_0based"] % n
    if t1 > t2:
        raise ValueError("Vector cut boundaries wrap the origin; rotate vector before ligation")
    if t1 == t2:
        raise ValueError("Vector cut boundaries coincide")

    i1 = insert_hits[0]["top_cut_boundary_0based"] % len(iseq)
    i2 = insert_hits[1]["top_cut_boundary_0based"] % len(iseq)
    if i1 > i2:
        i1, i2 = i2, i1
        insert_hits[0], insert_hits[1] = insert_hits[1], insert_hits[0]
    if i1 == i2:
        raise ValueError("Insert cut boundaries coincide")

    ins_frag = iseq[i1:i2]
    backbone = vseq[:t1] + vseq[t2:]

    l_kind, l_ov, _ = _hit_end_sequences(vseq, vector_hits[1])
    r_kind, _, r_ov = _hit_end_sequences(vseq, vector_hits[0])
    backbone_frag = AssemblyFragment(
        "vector", backbone, topology="linear",
        left_end=overhang_end(l_kind, l_ov, 0, source_cut_boundary=t2),
        right_end=overhang_end(r_kind, r_ov, len(backbone), source_cut_boundary=t1),
        source=vec_rec.id,
    )

    il_kind, il_ov, _ = _hit_end_sequences(iseq, insert_hits[0])
    ir_kind, _, ir_ov = _hit_end_sequences(iseq, insert_hits[1])
    insert_frag = AssemblyFragment(
        "insert", ins_frag, topology="linear",
        left_end=overhang_end(il_kind, il_ov, 0, source_cut_boundary=i1),
        right_end=overhang_end(ir_kind, ir_ov, len(ins_frag), source_cut_boundary=i2),
        source=ins_rec.id,
    )

    junctions = check_sticky_junctions([backbone_frag, insert_frag], circular=True)
    if any(j["compatibility"] == "MISMATCH" for j in junctions):
        raise ValueError(f"Sticky ends are not complementary: {junctions}")

    product = ConstructModel(vec_rec).replace(t1, t2, ins_frag)
    product.set_topology("circular")
    prod_seq = str(product.to_record().seq).upper()

    return {
        "product_sequence": prod_seq,
        "product_length": len(prod_seq),
        "product_sha256": hashlib.sha256(prod_seq.encode("utf-8")).hexdigest().upper(),
        "product_topology": "circular",
        "vector_cuts_0based": [t1, t2],
        "insert_cuts_0based": [i1, i2],
        "junctions": junctions,
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
    digested_frags = []

    for idx, f in enumerate(fragments):
        if isinstance(f, dict):
            seq = str(f.get("sequence", "")).upper()
            fid = f.get("id", f"frag_{idx+1}")
            rec = SeqRecord(Seq(seq), id=fid, name=fid)
        else:
            from core.io.input_resolution import resolve_sequence_input
            rec, seq = resolve_sequence_input(f, record_id=f"frag_{idx+1}")
            fid = rec.id or f"frag_{idx+1}"

        hits = restriction_hits(seq, enz, circular=False)
        if len(hits) < 2:
            raise ValueError(f"Fragment {fid} has {len(hits)} {enzyme} cut sites; expected 2 flanking sites")

        hits.sort(key=lambda h: h["recognition_start0"])
        h_left, h_right = hits[0], hits[-1]

        t_left = h_left["top_cut_boundary_0based"]
        b_left = h_left["bottom_cut_boundary_0based"]
        t_right = h_right["top_cut_boundary_0based"]
        b_right = h_right["bottom_cut_boundary_0based"]

        left_cut = min(t_left, b_left)
        left_cut_max = max(t_left, b_left)
        left_ov = seq[left_cut:left_cut_max]

        right_cut = min(t_right, b_right)
        right_cut_max = max(t_right, b_right)
        right_ov = seq[right_cut:right_cut_max]

        insert_core = seq[left_cut:right_cut_max]

        digested_frags.append({
            "id": fid,
            "original_length": len(seq),
            "insert_core": insert_core,
            "left_overhang": left_ov,
            "right_overhang": right_ov,
            "left_cut": left_cut,
            "right_cut": right_cut_max,
        })

    num = len(digested_frags)
    junctions = []
    for i in range(num if circular else num - 1):
        curr_frag = digested_frags[i]
        next_frag = digested_frags[(i + 1) % num]
        r_ov = curr_frag["right_overhang"]
        l_ov = next_frag["left_overhang"]

        ov_match = (r_ov == l_ov)
        junctions.append({
            "junction_index": i,
            "from_fragment": curr_frag["id"],
            "to_fragment": next_frag["id"],
            "from_overhang": r_ov,
            "to_overhang": l_ov,
            "compatible": ov_match,
        })
        if not ov_match:
            raise ValueError(
                f"Golden Gate overhang mismatch between {curr_frag['id']} ({r_ov}) "
                f"and {next_frag['id']} ({l_ov})"
            )

    assembled_parts = []
    for i, df in enumerate(digested_frags):
        core = df["insert_core"]
        ov_len = len(df["right_overhang"])
        assembled_parts.append(core[:-ov_len] if ov_len > 0 else core)

    prod_seq = "".join(assembled_parts)
    return {
        "product_sequence": prod_seq,
        "product_length": len(prod_seq),
        "product_sha256": hashlib.sha256(prod_seq.encode("utf-8")).hexdigest().upper(),
        "product_topology": "circular" if circular else "linear",
        "enzyme": enzyme,
        "fragment_count": num,
        "junctions": junctions,
        "fragments": digested_frags,
    }
