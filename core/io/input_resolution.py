# -*- coding: utf-8 -*-
"""core/io/input_resolution.py - Unified, sequence-first input resolution.

Prevents cross-platform filesystem errors (such as POSIX ENAMETOOLONG on Linux)
by resolving biological inputs using strict sequence-first heuristics rather than
speculative filesystem stat calls.
"""
from __future__ import annotations

import io
import os
import pathlib
from typing import Any

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import CompoundLocation, FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

# Standard IUPAC nucleotide alphabet (including ambiguity codes)
DNA_ALPHABET = set("ACGTRYSWKMBDHVN")


def _read_record_from_file(p: pathlib.Path) -> SeqRecord:
    """Read a sequence file (.dna, .gb, .fasta) into a SeqRecord."""
    suffix = p.suffix.lower()
    if suffix in (".dna",):
        try:
            return SeqIO.read(str(p), "snapgene")
        except Exception:
            try:
                from snapgene_reader import snapgene_file_to_seqrecord
                return snapgene_file_to_seqrecord(str(p))
            except Exception as exc:
                raise ValueError(f"Failed to parse SnapGene .dna file '{p}': {exc}") from exc
    elif suffix in (".gb", ".gbk", ".genbank"):
        try:
            with p.open(encoding="utf-8") as handle:
                return SeqIO.read(handle, "genbank")
        except Exception as exc:
            raise ValueError(f"Failed to parse GenBank file '{p}': {exc}") from exc
    else:
        # Default to FASTA or auto-detect
        try:
            with p.open(encoding="utf-8") as handle:
                return SeqIO.read(handle, "fasta")
        except Exception:
            try:
                with p.open(encoding="utf-8") as handle:
                    return SeqIO.read(handle, "genbank")
            except Exception as exc:
                raise ValueError(f"Failed to parse sequence file '{p}': {exc}") from exc


def resolve_sequence_input(
    value: Any,
    default_topology: str = "linear",
    record_id: str = "seq",
) -> tuple[SeqRecord, str]:
    """Resolve an input value that could be a SeqRecord, file path, or raw sequence string.

    Resolution order (sequence-first & filesystem-safe):
    1. SeqRecord: Return (value, str(value.seq).upper()).
    2. pathlib.Path: Must be a file; load record from disk.
    3. str:
       a) Starts with '>' or contains standard FASTA header: parse in-memory.
       b) Cleaned of whitespace, all characters in IUPAC DNA alphabet:
          Treat as raw sequence string with default_topology (defaults to 'linear').
       c) Otherwise: Attempt filesystem check safely within try-except block to
          prevent OSError (ENAMETOOLONG) on POSIX platforms.
          If file exists and is file, load record.
          Otherwise raise ValueError/FileNotFoundError.

    Returns:
        tuple[SeqRecord, str]: (SeqRecord instance, upper-case sequence string)
    """
    if isinstance(value, SeqRecord):
        seq_str = str(value.seq).upper()
        return value, seq_str

    if isinstance(value, dict):
        # Existing tool/Recipe results use sequence plus serialized features.
        sequence = value.get("sequence", value.get("product_sequence", value.get("amplicon")))
        if not isinstance(sequence, str):
            raise ValueError("Sequence result must contain a sequence string")
        rec = SeqRecord(Seq(sequence.upper()), id=record_id, annotations={
            "molecule_type": "DNA",
            "topology": value.get("product_topology", value.get("topology", default_topology)),
        })
        for feature in value.get("features", []):
            location = feature.get("location") or {}
            parts = location.get("parts")
            if parts:
                locations = [FeatureLocation(p["start0"], p["end0"], strand=p.get("strand") or None) for p in parts]
                loc = locations[0] if len(locations) == 1 else CompoundLocation(locations, operator=location.get("operator") or "join")
            else:
                start, end = feature.get("interval_0based", [feature.get("start", 0), feature.get("end", 0)])
                loc = FeatureLocation(start, end, strand=feature.get("strand", 1))
            qualifiers = {k: list(v) if isinstance(v, list) else [str(v)] for k, v in feature.get("qualifiers", {}).items()}
            qualifiers.setdefault("label", [feature.get("name", "feature")])
            rec.features.append(SeqFeature(loc, type=feature.get("type", "misc_feature"), qualifiers=qualifiers))
        return rec, str(rec.seq)

    if isinstance(value, pathlib.Path):
        if not value.exists():
            raise FileNotFoundError(f"Sequence file not found: {value}")
        rec = _read_record_from_file(value)
        return rec, str(rec.seq).upper()

    if isinstance(value, str):
        val_strip = value.strip()
        if not val_strip:
            empty_rec = SeqRecord(Seq(""), id=record_id, annotations={"topology": default_topology})
            return empty_rec, ""

        # Check if in-memory FASTA text
        if val_strip.startswith(">"):
            try:
                rec = SeqIO.read(io.StringIO(val_strip), "fasta")
                if "topology" not in rec.annotations:
                    rec.annotations["topology"] = default_topology
                return rec, str(rec.seq).upper()
            except Exception:
                pass

        # Sequence-first check: if all non-whitespace characters belong to IUPAC DNA alphabet
        cleaned_seq = "".join(val_strip.split()).upper()
        if all(c in DNA_ALPHABET for c in cleaned_seq):
            rec = SeqRecord(
                Seq(cleaned_seq),
                id=record_id,
                annotations={"molecule_type": "DNA", "topology": default_topology},
            )
            return rec, cleaned_seq

        # Fallback: Safely check if string points to an existing file on disk
        # We catch OSError / ValueError to prevent ENAMETOOLONG when string is long
        try:
            p = pathlib.Path(val_strip)
            if p.is_file():
                rec = _read_record_from_file(p)
                return rec, str(rec.seq).upper()
        except (OSError, ValueError):
            pass

        raise ValueError(
            f"Input could not be resolved to a valid DNA sequence, FASTA text, or existing file: {val_strip[:80]}..."
            if len(val_strip) > 80 else
            f"Input could not be resolved to a valid DNA sequence, FASTA text, or existing file: {val_strip}"
        )

    raise TypeError(f"Unsupported sequence input type: {type(value)} (expected SeqRecord, Path, or str)")


def resolve_sequence_string(value: Any, default_topology: str = "linear") -> str:
    """Convenience helper: returns sequence string directly."""
    _, seq_str = resolve_sequence_input(value, default_topology=default_topology)
    return seq_str


def resolve_sequence_record(value: Any, default_topology: str = "linear", record_id: str = "seq") -> SeqRecord:
    """Convenience helper: returns SeqRecord directly."""
    rec, _ = resolve_sequence_input(value, default_topology=default_topology, record_id=record_id)
    return rec
