# -*- coding: utf-8 -*-
"""core/tools/snapgene_io.py - Atomic SnapGene export and launcher tool.

Exports native SnapGene .dna and standard GenBank (.gb) files, and launches
the official desktop SnapGene viewer to inspect the generated plasmid map.
"""
from __future__ import annotations

import os
import pathlib
import subprocess
from typing import Any

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from scripts.write_dna import _snapgene_annotated, write_native_dna


SNAPGENE_EXE_PATH = r"D:\SnapGene\SnapGene.exe"


def export_snapgene(
    record_or_seq: SeqRecord | str,
    out_dir: str | pathlib.Path,
    filename_base: str = "construct",
    topology: str = "circular",
    features: list[dict[str, Any]] | None = None,
) -> dict[str, str]:
    """Export sequence to both native SnapGene .dna and standard GenBank .gb formats.

    Args:
        record_or_seq: Bio.SeqRecord or raw DNA nucleotide string.
        out_dir: Destination directory.
        filename_base: Filename without extension.
        topology: "circular" or "linear".
        features: Optional list of additional feature dicts to attach.

    Returns:
        dict with paths to the exported .dna and .gb files.
    """
    out_path = pathlib.Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    if isinstance(record_or_seq, SeqRecord):
        rec = record_or_seq
    else:
        rec = SeqRecord(Seq(str(record_or_seq).upper()), id=filename_base, name=filename_base)
        rec.annotations["molecule_type"] = "DNA"
        rec.annotations["topology"] = topology

    if "topology" not in rec.annotations:
        rec.annotations["topology"] = topology

    # Attach features if provided
    if features:
        from core.tools.feature_ops import annotate_feature
        for f in features:
            annotate_feature(
                rec,
                name=f.get("name", "feature"),
                feature_type=f.get("type", "misc_feature"),
                start=f.get("start", 0),
                end=f.get("end", 0),
                strand=f.get("strand", 1),
                qualifiers=f.get("qualifiers"),
            )

    gb_path = out_path / f"{filename_base}.gb"
    dna_path = out_path / f"{filename_base}.dna"

    # 1. Write GenBank with SnapGene annotations
    sg_rec = _snapgene_annotated(rec)
    with open(gb_path, "w", encoding="utf-8") as fh:
        SeqIO.write(sg_rec, fh, "genbank")

    # 2. Write native SnapGene binary .dna file
    write_native_dna(sg_rec, str(dna_path))

    return {
        "gb_file": str(gb_path),
        "dna_file": str(dna_path),
        "topology": rec.annotations.get("topology", "circular"),
        "sequence_length": len(rec.seq),
    }


def open_in_snapgene(file_path: str | pathlib.Path) -> dict[str, Any]:
    """Launch the local SnapGene desktop application to display the construct.

    Args:
        file_path: Path to .dna or .gb file.

    Returns:
        dict with process status.
    """
    p = pathlib.Path(file_path).resolve()
    if not p.exists():
        raise FileNotFoundError(f"File not found: {p}")

    exe = pathlib.Path(SNAPGENE_EXE_PATH)
    if not exe.exists():
        return {
            "success": False,
            "message": f"SnapGene executable not found at {SNAPGENE_EXE_PATH}",
        }

    try:
        proc = subprocess.Popen([str(exe), str(p)])
        return {
            "success": True,
            "pid": proc.pid,
            "opened_file": str(p),
            "executable": str(exe),
        }
    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
            "opened_file": str(p),
        }
