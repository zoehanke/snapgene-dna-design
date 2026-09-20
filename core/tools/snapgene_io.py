# -*- coding: utf-8 -*-
"""core/tools/snapgene_io.py - Atomic SnapGene export and launcher tool.

Exports native SnapGene .dna and standard GenBank (.gb) files, and launches
the official desktop SnapGene viewer to inspect the generated plasmid map.
"""
from __future__ import annotations

import copy
import json
import os
import pathlib
import shutil
import subprocess
from collections.abc import Mapping
from typing import Any

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import CompoundLocation, ExactPosition, FeatureLocation, Reference, SeqFeature
from Bio.SeqRecord import SeqRecord


def _strand_char(strand: int | None) -> str:
    return "-" if strand == -1 else "+"


def _strand_int(strand: int | str | None) -> int:
    if strand in (-1, "-", "reverse"):
        return -1
    if strand in (1, "+", "forward", None):
        return 1
    raise ValueError("Primer strand must be '+', '-', 1, or -1; got %r" % (strand,))


def _normalise_dna(value: Any, field: str) -> str:
    sequence = "".join(str(value).split()).upper()
    if not sequence:
        raise ValueError("Primer %s must not be empty" % field)
    invalid = sorted(set(sequence) - set("ACGTRYSWKMBDHVN"))
    if invalid:
        raise ValueError(
            "Primer %s contains non-DNA/IUPAC symbols: %s"
            % (field, ", ".join(invalid))
        )
    return sequence


def _first_qualifier(feature: SeqFeature, *keys: str) -> str | None:
    for key in keys:
        values = feature.qualifiers.get(key)
        if values:
            value = values[0] if isinstance(values, list) else values
            if value is not None and str(value).strip():
                return str(value)
    return None


def _parse_interval(value: Any) -> tuple[int, int] | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            pieces = [piece.strip() for piece in text.split(",")]
            if len(pieces) != 2:
                raise ValueError("binding_interval_0based must contain [start, end]")
            value = pieces
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("binding_interval_0based must contain [start, end]")
    try:
        return int(value[0]), int(value[1])
    except (TypeError, ValueError) as exc:
        raise ValueError("binding_interval_0based coordinates must be integers") from exc


def _extract_reference_interval(
    sequence: str,
    start: int,
    end: int,
    topology: str,
) -> str:
    n = len(sequence)
    if n <= 0:
        raise ValueError("Cannot place a primer on an empty template")
    if start < 0 or start >= n or end < 0 or end > n:
        raise ValueError("Primer binding interval [%d, %d) is outside template length %d" % (start, end, n))
    if start < end:
        return sequence[start:end]
    if start == end:
        raise ValueError("Primer binding interval must not be zero width")
    if topology != "circular":
        raise ValueError("Primer binding interval wraps origin on a linear template")
    return sequence[start:] + sequence[:end]


def _interval_end(start: int, length: int, sequence_length: int, topology: str) -> int:
    if length <= 0:
        raise ValueError("Primer binding core must not be empty")
    raw_end = start + length
    if raw_end <= sequence_length:
        return raw_end
    if topology != "circular":
        raise ValueError("Primer binding interval exceeds a linear template")
    if raw_end > sequence_length * 2:
        raise ValueError("Primer binding core is longer than one circular template")
    return raw_end % sequence_length


def _find_unique_binding(
    sequence: str,
    core: str,
    topology: str,
) -> tuple[int, int, int]:
    n = len(sequence)
    if len(core) > n:
        raise ValueError("Primer binding core is longer than the template")
    circular = topology == "circular"
    search = sequence + (sequence[: len(core) - 1] if circular else "")
    max_start = n if circular else n - len(core) + 1
    matches: list[tuple[int, int, int]] = []
    for strand in (1, -1):
        needle = core if strand == 1 else str(Seq(core).reverse_complement())
        for start in range(max_start):
            if search[start : start + len(core)] == needle:
                matches.append((start, _interval_end(start, len(core), n, topology), strand))
    if not matches:
        raise ValueError(
            "Primer binding core '%s' has 0 binding sites on the template" % core
        )
    if len(matches) > 1:
        rendered = ", ".join("[%d,%d) (%s)" % (s, e, _strand_char(st)) for s, e, st in matches)
        raise ValueError(
            "Ambiguous primer binding core '%s': found %d sites (%s)"
            % (core, len(matches), rendered)
        )
    return matches[0]


def _derive_core_from_full(
    sequence: str,
    full_oligo: str,
    start: int,
    strand: int,
    topology: str,
    expected_length: int | None = None,
) -> str:
    n = len(sequence)
    candidate_lengths: list[int] = []
    upper_full = full_oligo.upper()
    max_length = min(len(upper_full), n)
    for length in range(1, max_length + 1):
        end = _interval_end(start, length, n, topology)
        reference = _extract_reference_interval(sequence, start, end, topology)
        observed = reference if strand == 1 else str(Seq(reference).reverse_complement())
        if upper_full[-length:] == observed:
            candidate_lengths.append(length)
    if expected_length is not None:
        if expected_length not in candidate_lengths:
            raise ValueError(
                "Primer binding_core_length %d does not match the template at [%d,...]"
                % (expected_length, start)
            )
        return upper_full[-expected_length:]
    if not candidate_lengths:
        raise ValueError(
            "Cannot derive a 3' binding core for primer at position %d; provide binding_sequence"
            % start
        )
    # A legacy definition has no explicit tail boundary. Use the longest exact
    # 3' match, while newer callers should provide binding_sequence explicitly.
    return upper_full[-max(candidate_lengths) :]


def _location_interval(location, sequence_length: int) -> tuple[int, int]:
    parts = list(getattr(location, "parts", [location]))
    if len(parts) == 1:
        return int(parts[0].start), int(parts[0].end)
    # Rotation/extraction can leave adjacent parts of a former origin-spanning
    # site. Native stores that now-contiguous site as one interval.
    ordered = sorted(parts, key=lambda part: int(part.start))
    if (len({part.strand for part in parts}) == 1
            and all(int(a.end) == int(b.start) for a, b in zip(ordered, ordered[1:]))):
        return int(ordered[0].start), int(ordered[-1].end)
    high = [part for part in parts if int(part.end) == sequence_length]
    low = [part for part in parts if int(part.start) == 0]
    if len(high) == 1 and len(low) == 1:
        return int(high[0].start), int(low[0].end)
    raise ValueError("Primer feature has unsupported compound location")


def _primer_location(
    start: int,
    end: int,
    strand: int,
    sequence_length: int,
    topology: str,
):
    if end >= start:
        return FeatureLocation(start, end, strand=strand)
    if topology != "circular":
        raise ValueError("Primer feature wraps origin on a linear record")
    # End zero is the exact boundary at the origin, and can be represented by
    # the single reference segment [start, length).
    if end == 0:
        return FeatureLocation(start, sequence_length, strand=strand)
    if strand == -1:
        # Biopython CompoundLocation parts are biological order for reverse
        # features so extract() returns the primer-oriented core.
        parts = [
            FeatureLocation(0, end, strand=-1),
            FeatureLocation(start, sequence_length, strand=-1),
        ]
    else:
        parts = [
            FeatureLocation(start, sequence_length, strand=1),
            FeatureLocation(0, end, strand=1),
        ]
    return CompoundLocation(parts, operator="join")


def normalize_primer_definition(record: SeqRecord, primer: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize a primer into full oligo, core, reference interval and strand.

    ``sequence`` is the complete primer in its own 5' to 3' orientation.
    ``binding_sequence`` is the actual annealing core in that same orientation.
    Coordinates are 0-based half-open on the reference sequence; a circular
    interval may use ``start > end``.
    """
    if not isinstance(primer, Mapping):
        raise TypeError("Primer definition must be a mapping")
    name = str(primer.get("name") or primer.get("label") or "primer")
    full_value = (
        primer.get("sequence")
        or primer.get("seq")
        or primer.get("primer_sequence")
        or primer.get("full_sequence")
    )
    if full_value is None:
        raise ValueError("Primer definition requires sequence")
    full = _normalise_dna(full_value, "sequence")
    topology = str(record.annotations.get("topology", "linear")).lower()
    if topology not in ("linear", "circular"):
        topology = "linear"
    n = len(record.seq)

    interval = _parse_interval(
        primer.get("binding_interval_0based")
        or primer.get("binding_interval")
    )
    start_value = primer.get("bind_position")
    if start_value is None:
        start_value = primer.get("bind_start")
    if interval is not None:
        start, end = interval
    else:
        start = int(start_value) if start_value is not None else None
        end_value = primer.get("bind_end_exclusive")
        if end_value is None:
            end_value = primer.get("bind_end")
        end = int(end_value) if end_value is not None else None

    strand_value = primer.get("strand")
    strand = _strand_int(strand_value) if strand_value is not None else None
    core_value = (
        primer.get("binding_sequence")
        or primer.get("binding_core")
        or primer.get("binding")
    )
    core = _normalise_dna(core_value, "binding_sequence") if core_value else None
    expected_length = primer.get("binding_core_length")
    if expected_length is None:
        expected_length = primer.get("binding_core_length_bp")
    if expected_length is not None:
        expected_length = int(expected_length)

    if interval is not None and start is not None and end is not None:
        if start != interval[0] or end != interval[1]:
            raise ValueError("Primer binding interval fields disagree")

    if core is not None and start is None:
        if strand is not None:
            start, end, _ = _find_unique_binding(str(record.seq).upper(), core, topology)
        else:
            start, end, strand = _find_unique_binding(str(record.seq).upper(), core, topology)
    elif core is None and start is None:
        core = full
        start, end, strand = _find_unique_binding(str(record.seq).upper(), core, topology)
    elif start is None:
        raise ValueError("Primer definition requires binding start or a searchable core")

    if strand is None:
        if core is not None:
            candidates = []
            for candidate_strand in (1, -1):
                try:
                    candidate_end = _interval_end(start, len(core), n, topology)
                    reference = _extract_reference_interval(str(record.seq).upper(), start, candidate_end, topology)
                    observed = reference if candidate_strand == 1 else str(Seq(reference).reverse_complement())
                    if observed == core:
                        candidates.append(candidate_strand)
                except ValueError:
                    pass
            if len(candidates) != 1:
                raise ValueError("Primer strand is missing or ambiguous at binding position %d" % start)
            strand = candidates[0]
        else:
            strand = 1

    if core is None:
        if end is not None:
            interval_core = _extract_reference_interval(str(record.seq).upper(), start, end, topology)
            core = interval_core if strand == 1 else str(Seq(interval_core).reverse_complement())
        else:
            core = _derive_core_from_full(
                str(record.seq).upper(), full, start, strand, topology, expected_length
            )
    if end is None:
        end = _interval_end(start, len(core), n, topology)
    elif _extract_reference_interval(str(record.seq).upper(), start, end, topology):
        actual = _extract_reference_interval(str(record.seq).upper(), start, end, topology)
        observed = actual if strand == 1 else str(Seq(actual).reverse_complement())
        if observed != core:
            raise ValueError(
                "Primer binding_sequence does not match template at [%d,%d)"
                % (start, end)
            )
    if expected_length is not None and len(core) != expected_length:
        raise ValueError("Primer binding core length does not match binding_core_length")
    if len(full) < len(core) or not full.endswith(core):
        raise ValueError("Primer sequence must end with its binding_sequence")
    if start < 0 or start >= n or end < 0 or end > n:
        raise ValueError("Primer binding interval is outside the template")
    if start == end:
        raise ValueError("Primer binding interval must not be zero width")
    if topology == "circular" and end == 0:
        end = n  # The origin endpoint is the right edge of this non-wrapping interval.
    _primer_location(start, end, strand, n, topology)
    return {
        "name": name,
        "sequence": full,
        "binding_sequence": core,
        "binding_interval_0based": [start, end],
        "strand": _strand_char(strand),
        "strand_int": strand,
        "tail_5prime": full[: -len(core)] if len(full) > len(core) else "",
        "topology": topology,
    }


def _primer_qualifiers(payload: Mapping[str, Any]) -> dict[str, list[str]]:
    full = str(payload["sequence"])
    core = str(payload["binding_sequence"])
    start, end = payload["binding_interval_0based"]
    strand = str(payload["strand"])
    qualifiers = {
        "label": [str(payload["name"])],
        "primer_sequence": [full],
        "binding_sequence": [core],
        "binding_core_length": [str(len(core))],
        "binding_interval": [json.dumps([start, end], separators=(",", ":"))],
        "binding_strand": [strand],
        "note": ["sequence: %s" % full, "binding sequence: %s" % core],
    }
    if payload.get("tail_5prime"):
        qualifiers["tail_5prime"] = [str(payload["tail_5prime"])]
    return qualifiers


def annotate_record_primers(
    record: SeqRecord,
    primers: list[Mapping[str, Any]],
) -> SeqRecord:
    """Return a copy of ``record`` with explicit, lossless primer features.

    The input record is never modified. Each feature location represents only
    the actual binding core; the complete ordered oligo is stored separately in
    ``primer_sequence`` and is used by Native export.
    """
    result = copy.deepcopy(record)
    sequence_length = len(result.seq)
    topology = str(result.annotations.get("topology", "linear")).lower()
    for definition in primers:
        payload = normalize_primer_definition(result, definition)
        start, end = payload["binding_interval_0based"]
        location = _primer_location(
            start,
            end,
            payload["strand_int"],
            sequence_length,
            topology,
        )
        result.features.append(
            SeqFeature(
                location,
                type="primer_bind",
                qualifiers=_primer_qualifiers(payload),
            )
        )
    return result


def _ensure_annotations(record: SeqRecord) -> SeqRecord:
    record.annotations["molecule_type"] = "DNA"
    if "topology" not in record.annotations:
        record.annotations["topology"] = record.annotations.get("topology", "linear")
    from core.models.construct_model import feature_to_dict
    for feature in record.features:
        if feature.type == "CDS" and feature.location is not None and any(
                not isinstance(part.start, ExactPosition) or not isinstance(part.end, ExactPosition)
                for part in feature.location.parts):
            feature.qualifiers = feature_to_dict(feature, len(record))["qualifiers"]
    return record


def _snapgene_annotated(record: SeqRecord) -> SeqRecord:
    """Return the record annotated for the GenBank-SnapGene dialect."""
    _ensure_annotations(record)
    record.name = "Exported"
    ref = Reference()
    ref.title = "Direct Submission"
    ref.journal = "Exported from snapgene-dna-design (SnapGene)"
    ref.authors = "."
    refs = list(record.annotations.get("references", []))
    refs.append(ref)
    record.annotations["references"] = refs
    return record


def write_native_dna(record: SeqRecord, out_path: str | pathlib.Path) -> str | pathlib.Path:
    """Write a native SnapGene .dna file via sgffp (0-based coords)."""
    record = _ensure_annotations(copy.deepcopy(record))
    from sgffp import (
        SgffBindingSite,
        SgffFeature,
        SgffObject,
        SgffPrimer,
        SgffSegment,
        SgffWriter,
    )
    topo = record.annotations.get("topology", "linear")
    sg = SgffObject.new(str(record.seq), topology=topo)
    for f in record.features:
        if "primer" in f.type.lower():
            payload = _primer_payload_from_feature(record, f)
            start, end = payload["binding_interval_0based"]
            primer = SgffPrimer(
                name=payload["name"],
                sequence=payload["sequence"],
                binding_sites=[
                    SgffBindingSite(
                        start=start,
                        end=end,
                        bound_strand=payload["strand"],
                        annealed_bases=payload["binding_sequence"],
                    )
                ],
            )
            sg.primers.add(primer)
            continue
        name = f.qualifiers.get(
            "label", f.qualifiers.get("gene", [f.id or "feature"])
        )[0]
        parts = getattr(f.location, "parts", [f.location])
        # SnapGene stores segments in reference order and reverses them when
        # reading a reverse-strand feature into Biopython.
        if f.location.strand == -1:
            parts = list(reversed(parts))
        segments = []
        for part in parts:
            current = SgffSegment(start=int(part.start), end=int(part.end))
            if segments:
                previous = segments[-1]
                # Native SnapGene collapses adjacent standard segments across
                # an omitted reference interval unless that interval is
                # encoded explicitly as a gap segment. Do not add a gap for
                # true circular adjacency [start,n] followed by [0,end].
                if previous.end < current.start:
                    segments.append(
                        SgffSegment(
                            start=previous.end,
                            end=current.start,
                            type="gap",
                        )
                    )
                elif (
                    topo == "circular"
                    and previous.end > current.start
                    and not (previous.end == len(record.seq) and current.start == 0)
                ):
                    # A discontinuity itself can cross the circular origin.
                    # SGFF accepts the wrapped range as start > end.
                    segments.append(
                        SgffSegment(
                            start=previous.end,
                            end=current.start,
                            type="gap",
                        )
                    )
            segments.append(current)
        feature = SgffFeature(
            name=name,
            type=f.type,
            strand=_strand_char(f.location.strand),
            segments=segments,
            qualifiers=copy.deepcopy(f.qualifiers),
            color=f.qualifiers.get("ApEinfo_fcolor", [None])[0],
        )
        sg.features.add(feature)
    SgffWriter.to_file(sg, out_path)
    return out_path


def _sequence_from_note(feature: SeqFeature) -> str | None:
    values = feature.qualifiers.get("note", [])
    if not isinstance(values, list):
        values = [values]
    joined = " ".join(str(value) for value in values)
    for value in values:
        text = str(value)
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.lower().startswith("sequence:"):
                candidate = stripped.split(":", 1)[1]
                try:
                    return _normalise_dna(candidate, "sequence")
                except ValueError:
                    continue
    lower_joined = joined.lower()
    cursor = 0
    while True:
        marker = lower_joined.find("sequence:", cursor)
        if marker < 0:
            break
        prefix = lower_joined[max(0, marker - 8) : marker]
        if not prefix.endswith("binding "):
            try:
                return _normalise_dna(joined[marker + len("sequence:") :], "sequence")
            except ValueError:
                pass
        cursor = marker + len("sequence:")
    return None


def _primer_payload_from_feature(record: SeqRecord, feature: SeqFeature) -> dict[str, Any]:
    """Recover a lossless primer payload from a GenBank feature."""
    sequence_length = len(record.seq)
    start, end = _location_interval(feature.location, sequence_length)
    strand = _strand_char(feature.location.strand)
    full = _first_qualifier(
        feature, "primer_sequence", "primer_seq", "full_sequence", "sequence"
    )
    if full is None:
        full = _sequence_from_note(feature)
    extracted = str(feature.extract(record.seq)).upper()
    if full is None:
        full = extracted
    else:
        full = _normalise_dna(full, "sequence")

    core = _first_qualifier(feature, "binding_sequence", "binding_seq", "binding_core")
    if core is not None:
        core = _normalise_dna(core, "binding_sequence")
    # SeqFeature.location follows slice/shift/reverse-complement operations;
    # redundant qualifiers do not. Validate the retained core at this location.
    definition: dict[str, Any] = {
        "name": _first_qualifier(feature, "label", "gene") or feature.id or "primer",
        "sequence": full,
        "bind_position": start,
        "strand": strand,
        "binding_interval_0based": [start, end],
        "binding_sequence": core if core is not None else extracted,
    }
    core_length = _first_qualifier(feature, "binding_core_length", "binding_core_length_bp", "binding_length")
    if core_length is not None:
        definition["binding_core_length"] = int(core_length)
    return normalize_primer_definition(record, definition)


def _native_site_location(start: int, end: int, strand: int, sequence_length: int, topology: str):
    return _primer_location(start, end, strand, sequence_length, topology)


def enrich_native_primer_features(record: SeqRecord, source_path: str | pathlib.Path) -> SeqRecord:
    """Restore full Native primer metadata omitted by Biopython's parser.

    The returned record is a deep copy. Non-primer features and ordinary
    annotations from Biopython are preserved; primer features are rebuilt from
    the sgffp Primer block so ``primer_sequence`` and ``binding_sequence`` are
    available to later GenBank and Native conversions.
    """
    result = copy.deepcopy(record)
    try:
        from sgffp import SgffReader

        sg = SgffReader.from_file(str(source_path))
    except Exception:
        return result
    if not sg.primers:
        return result

    topology = str(result.annotations.get("topology", "linear")).lower()
    sequence_length = len(result.seq)
    non_primers = [f for f in result.features if "primer" not in f.type.lower()]
    primer_features: list[SeqFeature] = []
    for primer in sg.primers:
        for site in primer.binding_sites:
            start = int(site.start)
            end = int(site.end)
            strand_int = -1 if site.bound_strand == "-" else 1
            core = str(site.annealed_bases or "").upper()
            if not core:
                reference = _extract_reference_interval(
                    str(result.seq).upper(), start, end, topology
                )
                core = reference if strand_int == 1 else str(Seq(reference).reverse_complement())
            location = _native_site_location(
                start, end, strand_int, sequence_length, topology
            )
            payload = {
                "name": primer.name or "primer",
                "sequence": _normalise_dna(primer.sequence, "sequence"),
                "binding_sequence": _normalise_dna(core, "binding_sequence"),
                "binding_interval_0based": [start, end],
                "strand": _strand_char(strand_int),
            }
            if payload["sequence"].endswith(payload["binding_sequence"]):
                payload["tail_5prime"] = payload["sequence"][: -len(payload["binding_sequence"])]
            primer_features.append(
                SeqFeature(
                    location,
                    type="primer_bind",
                    qualifiers=_primer_qualifiers(payload),
                )
            )
    result.features = non_primers + primer_features
    return result


def normalize_primer_qualifiers(record: SeqRecord) -> SeqRecord:
    """Normalize sequence-valued primer qualifiers after GenBank wrapping."""
    result = copy.deepcopy(record)
    for feature in result.features:
        if "primer" not in feature.type.lower():
            continue
        for key in ("primer_sequence", "primer_seq", "binding_sequence", "binding_seq", "tail_5prime"):
            values = feature.qualifiers.get(key)
            if values is None:
                continue
            if not isinstance(values, list):
                values = [values]
            cleaned = []
            for value in values:
                text = "".join(str(value).split()).upper()
                cleaned.append(text)
            feature.qualifiers[key] = cleaned
        notes = feature.qualifiers.get("note")
        if notes is not None:
            if not isinstance(notes, list):
                notes = [notes]
            cleaned_notes = []
            for value in notes:
                text = str(value)
                lower = text.lower()
                if lower.startswith("sequence:"):
                    text = "sequence: " + "".join(text.split(":", 1)[1].split()).upper()
                elif lower.startswith("binding sequence:"):
                    text = "binding sequence: " + "".join(text.split(":", 1)[1].split()).upper()
                cleaned_notes.append(text)
            feature.qualifiers["note"] = cleaned_notes
    return result


def read_native_dna_record(source_path: str | pathlib.Path) -> SeqRecord:
    """Read a Native file and restore primer oligo/core metadata."""
    path = pathlib.Path(source_path)
    try:
        with path.open("rb") as handle:
            record = SeqIO.read(handle, "snapgene")
    except Exception:
        from snapgene_reader import snapgene_file_to_seqrecord

        with path.open("rb") as handle:
            record = snapgene_file_to_seqrecord(fileobject=handle)
    return normalize_primer_qualifiers(enrich_native_primer_features(record, path))

def find_snapgene_executable() -> pathlib.Path | None:
    """Locate SnapGene desktop application across platforms."""
    # 1. Explicit environment variable override
    env_path = os.environ.get("SNAPGENE_PATH") or os.environ.get("SNAPGENE_EXE")
    if env_path and pathlib.Path(env_path).exists():
        return pathlib.Path(env_path)

    # 2. PATH resolution
    for cmd in ["SnapGene", "SnapGene.exe", "snapgene"]:
        found = shutil.which(cmd)
        if found:
            return pathlib.Path(found)

    # 3. Known default installation locations
    candidates = [
        pathlib.Path(r"C:\Program Files\SnapGene\SnapGene.exe"),
        pathlib.Path(r"C:\Program Files (x86)\SnapGene\SnapGene.exe"),
        pathlib.Path(r"C:\Program Files\GSL Biotech\SnapGene\SnapGene.exe"),
        pathlib.Path(r"D:\SnapGene\SnapGene.exe"),
        pathlib.Path("/Applications/SnapGene.app/Contents/MacOS/SnapGene"),
        pathlib.Path("/usr/bin/snapgene"),
        pathlib.Path("/usr/local/bin/snapgene"),
    ]
    for c in candidates:
        if c.exists():
            return c

    return None


_detected_exe = find_snapgene_executable()
SNAPGENE_EXE_PATH = str(_detected_exe) if _detected_exe else "SnapGene"

SNAPGENE_DEFAULT_COLORS: dict[str, str] = {
    "cds": "#ff8080",
    "gene": "#ff8080",
    "promoter": "#80ff80",
    "terminator": "#ff80c0",
    "rep_origin": "#8080ff",
    "origin": "#8080ff",
    "primer_bind": "#ffff80",
    "tag": "#fdbf6f",
    "misc_feature": "#c0c0c0",
}


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
        rec = copy.deepcopy(record_or_seq)
    else:
        rec = SeqRecord(Seq(str(record_or_seq).upper()), id=filename_base, name=filename_base)
        rec.annotations["molecule_type"] = "DNA"
        rec.annotations["topology"] = topology

    if "topology" not in rec.annotations:
        rec.annotations["topology"] = topology

    # Attach features if provided
    if features:
        from core.io.input_resolution import resolve_sequence_record
        for f in features:
            ft = f.get("type", "misc_feature")
            color = f.get("color") or SNAPGENE_DEFAULT_COLORS.get(ft.lower(), "#c0c0c0")
            added = resolve_sequence_record({"sequence": str(rec.seq), "features": [f]}).features[0]
            added.qualifiers.setdefault("ApEinfo_fcolor", [color])
            rec.features.append(added)

    gb_path = out_path / f"{filename_base}.gb"
    dna_path = out_path / f"{filename_base}.dna"

    # 1. Write GenBank with SnapGene annotations
    sg_rec = _snapgene_annotated(rec)
    for feature in sg_rec.features:
        if "primer" in feature.type.lower():
            feature.qualifiers.update(_primer_qualifiers(_primer_payload_from_feature(sg_rec, feature)))
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


export_plasmid = export_snapgene


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

    exe = find_snapgene_executable()
    if exe is None or not exe.exists():
        return {
            "success": False,
            "message": "SnapGene desktop executable not found on this system. Constructed files (.dna, .gb) remain available for manual opening.",
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
