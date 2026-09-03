# -*- coding: utf-8 -*-
"""core/tools/assembly.py - Atomic DNA assembly and ligation simulation tool.

Simulates homologous overlap assembly (Gibson, In-Fusion) and restriction-ligation
cloning with junction verification and circularization.
"""
from __future__ import annotations

import hashlib
import pathlib
import sys
from typing import Any

_SCRIPTS_DIR = str(pathlib.Path(__file__).resolve().parents[2] / "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from scripts.assembly_model import (
    AssemblyFragment,
    check_sticky_junctions,
    overhang_end,
)
from scripts.construct_model import ConstructModel
from scripts.sg_common import get_enzyme, restriction_hits
from scripts.simulate_cloning import digest_ligate
from core.tools.inspection import _load_record


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


def _hit_end_sequences(seq: str, hit: dict) -> tuple[str, str, str]:
    kind = hit["overhang_type"]
    ov_seq = hit.get("overhang_sequence", "")
    if kind == "5prime":
        return kind, ov_seq, ""
    elif kind == "3prime":
        return kind, "", ov_seq
    return "blunt", "", ""


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
    from scripts.sg_common import get_enzyme, restriction_hits

    enz = get_enzyme(enzyme)
    digested_frags = []

    for idx, f in enumerate(fragments):
        if isinstance(f, SeqRecord):
            rec = f
            seq = str(f.seq).upper()
            fid = f.id or f"frag_{idx+1}"
        elif isinstance(f, dict):
            seq = str(f.get("sequence", "")).upper()
            fid = f.get("id", f"frag_{idx+1}")
            rec = SeqRecord(Seq(seq), id=fid, name=fid)
        elif isinstance(f, (str, pathlib.Path)) and pathlib.Path(f).exists():
            rec = _load_record(f)
            seq = str(rec.seq).upper()
            fid = rec.id or f"frag_{idx+1}"
        else:
            seq = str(f).upper()
            fid = f"frag_{idx+1}"
            rec = SeqRecord(Seq(seq), id=fid, name=fid)

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
