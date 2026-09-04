# -*- coding: utf-8 -*-
"""Shared helpers for the snapgene-dna-design skill scripts.

Coordinate convention: all outward-facing positions are 1-based closed
intervals (matching SnapGene). Internal BioPython locations remain 0-based
half-open; conversion happens only at the boundary.
"""
import argparse
import io
import json
import os
import sys

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

KNOWN_EXTS = (
    ".dna", ".gb", ".genbank", ".fa", ".fasta", ".fna", ".fsa", ".embl", ".emb",
)
DNA_IUPAC = frozenset("ACGTRYSWKMBDHVN")
JSON_SCHEMA_VERSION = "0.5.0"


def jprint(obj, ok=None):
    """Print a versioned success envelope while preserving legacy dict keys.

    v0.2.1 commands exposed result fields at the root.  v0.3 keeps those keys
    and additionally provides a stable envelope under ``data``.  A single
    legacy command (translation) returns a root array; arrays remain unchanged
    until the next major version because JSON cannot add root metadata without
    breaking existing consumers.

    ``ok`` defaults to ``payload["passed"]`` when the payload has a ``passed``
    field (e.g. validate_roundtrip), otherwise True.
    """
    if isinstance(obj, dict):
        payload = dict(obj)
        schema_version = payload.get("schema_version")
        if isinstance(schema_version, str) and schema_version.startswith("0.8"):
            # v0.8 commands emit their native v0.8 schema directly.  The
            # v0.5 success envelope is reserved for legacy commands.
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return
        warnings = payload.get("warnings", [])
        if warnings is None:
            warnings = []
        elif not isinstance(warnings, list):
            warnings = [str(warnings)]
        if ok is None:
            ok = bool(payload.get("passed", True))
        envelope = {
            "schema_version": JSON_SCHEMA_VERSION,
            "ok": ok,
            "command": os.path.basename(sys.argv[0]),
            "data": payload,
            "warnings": warnings,
        }
        obj = envelope
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def jfail(code, message, details=None, warnings=None):
    """Print the unified failure envelope and exit non-zero.

    Error shape mirrors the success envelope::

        {"schema_version": ..., "ok": false, "command": ...,
         "data": null, "warnings": [...],
         "error": {"code": "...", "message": "...", ...}}

    Used by assembly tools so callers never mistake a failed simulation for a
    successful product.
    """
    error = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    if warnings is None:
        warnings = []
    elif not isinstance(warnings, list):
        warnings = [str(warnings)]
    print(json.dumps({
        "schema_version": JSON_SCHEMA_VERSION,
        "ok": False,
        "command": os.path.basename(sys.argv[0]),
        "data": None,
        "warnings": warnings,
        "error": error,
    }, ensure_ascii=False, indent=2))
    sys.exit(1)


def looks_like_path(s):
    """Heuristic: does this string look like a file path rather than raw sequence?"""
    return ("/" in s or "\\" in s) or s.lower().endswith(KNOWN_EXTS)


def normalize_dna(text, label="sequence"):
    """Normalize a raw DNA string and reject non-IUPAC symbols."""
    seq = "".join(str(text).split()).upper()
    if not seq:
        raise ValueError("Empty %s" % label)
    invalid = sorted(set(seq) - DNA_IUPAC)
    if invalid:
        raise ValueError(
            "%s contains non-DNA/IUPAC symbol(s): %s"
            % (label, ", ".join(invalid))
        )
    return seq


def _read_one(path, fmt):
    """Read exactly one record while ensuring the file handle is closed."""
    if fmt == "snapgene":
        with open(path, "rb") as handle:
            return SeqIO.read(handle, fmt)
    try:
        with open(path, "r", encoding="utf-8-sig") as handle:
            return SeqIO.read(handle, fmt)
    except UnicodeDecodeError:
        # Legacy INSDC files are sometimes stored as a single-byte encoding.
        with open(path, "r", encoding="latin-1") as handle:
            return SeqIO.read(handle, fmt)


def load_seq(source):
    """Load a sequence from a file path or a raw sequence string.

    Returns (SeqRecord, source_type). source_type in
    {'snapgene', 'genbank', 'fasta', 'embl', 'raw-fasta', 'raw'}.

    Raises FileNotFoundError when source looks like a path but does not exist.
    """
    if not source or not isinstance(source, str):
        raise ValueError("Empty source")
    s = source.strip()
    if not s:
        raise ValueError("Empty source")

    if looks_like_path(s) and not os.path.isfile(s):
        raise FileNotFoundError("sequence file not found: %s" % source)

    if os.path.isfile(s):
        path = s
        ext = os.path.splitext(path)[1].lower()
        # Native SnapGene binary
        if ext == ".dna":
            try:
                rec = _read_one(path, "snapgene")
                return rec, "snapgene"
            except Exception:
                # fallback: snapgene_reader -> SeqRecord.  The reader itself
                # opens ``filepath`` without closing it, so pass an explicit
                # file object owned by this context manager.
                try:
                    from snapgene_reader import snapgene_file_to_seqrecord
                    with open(path, "rb") as handle:
                        rec = snapgene_file_to_seqrecord(fileobject=handle)
                    return rec, "snapgene"
                except Exception as e:
                    raise ValueError(
                        "Cannot parse SnapGene file %s: %s" % (path, e)
                    )
        if ext in (".gb", ".genbank"):
            return _read_one(path, "genbank"), "genbank"
        if ext in (".fa", ".fasta", ".fna", ".fsa"):
            return _read_one(path, "fasta"), "fasta"
        if ext in (".embl", ".emb"):
            return _read_one(path, "embl"), "embl"
        # unknown extension: try several formats
        for fmt in ("genbank", "fasta", "embl", "snapgene"):
            try:
                return _read_one(path, fmt), fmt
            except Exception:
                continue
        raise ValueError("Cannot determine format of %s" % path)

    # raw string input (sequence or fasta text)
    text = s
    if text.startswith(">"):
        records = list(SeqIO.parse(io.StringIO(text), "fasta"))
        if len(records) != 1:
            raise ValueError(
                "inline FASTA must contain exactly one record; found %d" % len(records)
            )
        rec = records[0]
        rec.seq = Seq(normalize_dna(rec.seq, "FASTA sequence"))
        return rec, "raw-fasta"
    seq = normalize_dna(text)
    rec = SeqRecord(Seq(seq), id="seq", name="seq")
    return rec, "raw"


def features_to_dict(record):
    """Serialize features with both legacy and lossless v0.3 locations."""
    # Lazy import avoids making the canonical model depend on file I/O helpers.
    from construct_model import feature_to_dict
    return [feature_to_dict(feature, len(record.seq)) for feature in record.features]


def topology(record):
    """Return 'circular' or 'linear' from annotations; default is 'linear'.

    Deliberately conservative: only trust an explicit topology annotation.
    Raw sequences and plain FASTA are linear unless stated otherwise.
    """
    ann = getattr(record, "annotations", {})
    topo = ann.get("topology")
    return topo if topo in ("circular", "linear") else "linear"


def gc_percent(seq):
    """GC percentage, compatible with biopython <1.80 (GC) and >=1.80 (gc_fraction)."""
    try:
        from Bio.SeqUtils import gc_fraction
        return gc_fraction(seq) * 100
    except ImportError:
        s = str(seq).upper()
        if not s:
            return 0.0
        return (s.count("G") + s.count("C")) / len(s) * 100


import pathlib
import sys

_ROOT = str(pathlib.Path(__file__).resolve().parents[1])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Re-export pure restriction primitives from core.tools.restriction
from core.tools.restriction import (
    enzyme_sites,
    get_enzyme,
    restriction_hits,
)

