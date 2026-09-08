# -*- coding: utf-8 -*-
"""core/tools/inspection.py - Atomic DNA inspection tool.

Allows AI agents and deterministic pipelines to inspect sequence structure,
topology, GC content, annotations, and open reading frames from any input file.
"""
from __future__ import annotations

import hashlib
import pathlib
from typing import Any

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord


from core.io.input_resolution import resolve_sequence_input, resolve_sequence_record


def _load_record(file_path_or_record: str | pathlib.Path | SeqRecord) -> SeqRecord:
    try:
        return resolve_sequence_record(file_path_or_record, default_topology="linear")
    except (ValueError, FileNotFoundError) as exc:
        raise FileNotFoundError(f"Sequence file not found or invalid sequence: {file_path_or_record}") from exc


def inspect_dna(file_path_or_record: str | pathlib.Path | SeqRecord) -> dict[str, Any]:
    """Inspect sequence file and return structured metadata and features.

    Returns:
        dict with sequence_length, topology, gc_content, sequence_sha256,
        and structured features list.
    """
    rec = _load_record(file_path_or_record)
    seq_str = str(rec.seq).upper()
    n = len(seq_str)
    gc = (seq_str.count("G") + seq_str.count("C")) / n * 100.0 if n > 0 else 0.0
    topo = rec.annotations.get("topology", "linear")

    features = []
    for f in getattr(rec, "features", []):
        if f.type == "source":
            continue
        # Extract name from common qualifiers
        name = ""
        for q in ("label", "gene", "product", "note", "locus_tag"):
            vals = f.qualifiers.get(q)
            if vals and isinstance(vals, list) and vals[0]:
                name = str(vals[0])
                break
            elif vals and isinstance(vals, str):
                name = vals
                break
        if not name:
            name = f"{f.type}_{int(f.location.start)}"

        start0 = int(f.location.start)
        end0 = int(f.location.end)
        strand = int(f.location.strand or 1)

        translation = ""
        trans_vals = f.qualifiers.get("translation")
        if trans_vals:
            translation = trans_vals[0] if isinstance(trans_vals, list) else str(trans_vals)

        # Extract color if present in qualifiers
        color = ""
        for cq in ("ApEinfo_fcolor", "color", "label_color", "note"):
            cval = f.qualifiers.get(cq)
            if cval and isinstance(cval, list) and str(cval[0]).startswith("#"):
                color = str(cval[0])
                break
            elif cval and str(cval).startswith("#"):
                color = str(cval)
                break

        features.append({
            "name": name,
            "type": f.type,
            "interval_0based": [start0, end0],
            "length": len(f),
            "parts_0based": [[int(part.start), int(part.end)] for part in f.location.parts],
            "strand": strand,
            "translation": translation,
            "color": color,
            "qualifiers": {k: v for k, v in f.qualifiers.items() if k != "translation"},
        })

    return {
        "name": getattr(rec, "name", "") or getattr(rec, "id", "") or "unnamed",
        "sequence_length": n,
        "topology": topo,
        "gc_content": round(gc, 2),
        "sequence_sha256": hashlib.sha256(seq_str.encode("utf-8")).hexdigest().upper(),
        "feature_count": len(features),
        "features": features,
    }


def summarize_backbone(file_path_or_record: str | pathlib.Path | SeqRecord) -> dict[str, Any]:
    """Identify key vector backbone components: origins, resistance markers, promoters."""
    ins = inspect_dna(file_path_or_record)
    origins = []
    resistances = []
    promoters = []

    res_keywords = {
        "amp": "Ampicillin (AmpR / bla)",
        "bla": "Ampicillin (AmpR / bla)",
        "kan": "Kanamycin (KanR / aph)",
        "neo": "Neomycin / Kanamycin (NeoR)",
        "chlor": "Chloramphenicol (CmR / cat)",
        "cam": "Chloramphenicol (CmR / cat)",
        "tet": "Tetracycline (TetR)",
        "hyg": "Hygromycin B (HygR)",
        "zeo": "Zeocin (ZeoR / ble)",
        "spec": "Spectinomycin (SpecR / aadA)",
        "gent": "Gentamicin (GmR / aac)",
        "puro": "Puromycin (PuroR)",
        "bsd": "Blasticidin S (BsdR)",
    }

    for f in ins.get("features", []):
        fn = f["name"].lower()
        ft = f["type"].lower()

        if ft in ("rep_origin", "origin"):
            origins.append({
                "name": f["name"],
                "interval_0based": f["interval_0based"],
                "strand": f["strand"],
            })
        elif ft == "promoter" or (ft in ("misc_feature", "regulatory") and "promoter" in fn):
            promoters.append({
                "name": f["name"],
                "interval_0based": f["interval_0based"],
                "strand": f["strand"],
            })
        elif ft in ("cds", "gene"):
            for kw, desc in res_keywords.items():
                if kw in fn:
                    resistances.append({
                        "name": f["name"],
                        "marker_type": desc,
                        "interval_0based": f["interval_0based"],
                        "strand": f["strand"],
                    })
                    break

    return {
        "name": ins["name"],
        "topology": ins["topology"],
        "sequence_length": ins["sequence_length"],
        "origins_of_replication": origins,
        "selection_markers": resistances,
        "promoters": promoters,
    }


def find_open_reading_frames(
    file_path_or_seq: str | pathlib.Path | SeqRecord,
    min_length_aa: int = 30,
    transl_table: int = 1,
) -> list[dict[str, Any]]:
    """Scan all 6 reading frames for ATG-initiated ORFs with terminal stop codons."""
    rec, seq_str = resolve_sequence_input(file_path_or_seq)

    n = len(seq_str)
    orfs = []

    for strand, s in ((1, seq_str), (-1, str(Seq(seq_str).reverse_complement()))):
        for frame in (0, 1, 2):
            for i in range(frame, n - 2, 3):
                if s[i : i + 3] == "ATG":
                    # Find downstream stop codon in frame
                    for j in range(i + 3, n - 2, 3):
                        codon = s[j : j + 3]
                        if codon in ("TAA", "TAG", "TGA"):
                            dna_orf = s[i : j + 3]
                            aa = str(Seq(dna_orf).translate(table=transl_table))
                            if len(aa) >= min_length_aa:
                                if strand == 1:
                                    s0, e0 = i, j + 3
                                else:
                                    s0, e0 = n - (j + 3), n - i
                                orfs.append({
                                    "start_0based": s0,
                                    "end_0based": e0,
                                    "strand": strand,
                                    "frame": (frame + 1) if strand == 1 else -(frame + 1),
                                    "length_bp": len(dna_orf),
                                    "length_aa": len(aa),
                                    "translation": aa,
                                })
                            break
    return sorted(orfs, key=lambda x: x["length_aa"], reverse=True)
