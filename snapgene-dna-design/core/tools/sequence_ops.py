# -*- coding: utf-8 -*-
"""core/tools/sequence_ops.py - Atomic sequence operations tool.

Provides topology-aware sequence extraction, reading frame verification,
in-silico translation, and sequence mutagenesis.
"""
from __future__ import annotations

import copy
import hashlib
import pathlib
import re
from typing import Any

from Bio.Data import CodonTable
from Bio.Seq import Seq
from Bio.Data.CodonTable import TranslationError
from Bio.SeqFeature import CompoundLocation, ExactPosition, FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

from core.interval import extract_interval
from core.tools.inspection import _load_record
from core.models.construct_model import ConstructModel, feature_to_dict
from core.models.molecule import MoleculeInput, ProteinSequence, as_molecule, derived_molecule
from core.tools.result import ToolResult, check_result


def cds_partial_evidence(feature) -> list[str]:
    """Identify explicit partial-CDS metadata, never infer it from failed QC."""
    qualifiers = feature.qualifiers or {}
    def values(key):
        value = qualifiers.get(key, [])
        return value if isinstance(value, (list, tuple)) else [value]
    reasons = []
    if any(str(v).lower() in ("true", "1", "yes", "partial") for v in values("partial")):
        reasons.append("partial qualifier")
    parts = getattr(feature.location, "parts", [feature.location])
    if any(not isinstance(p.start, ExactPosition) or not isinstance(p.end, ExactPosition) for p in parts):
        reasons.append("fuzzy location boundary")
    text = " ".join(str(v) for key in ("product", "gene", "note", "label") for v in values(key)).lower()
    products = [str(v).strip().lower() for v in values("product")]
    if any(re.match(r"^(?:epitope|affinity|fusion) tag\b", product) for product in products):
        reasons.append("explicit peptide tag product")
    if any(re.fullmatch(r"(?:[\w-]+ )?(?:protease )?(?:recognition and )?cleavage site", product)
           for product in products):
        reasons.append("explicit protease cleavage-site product")
    if re.search(r"\b(?:n|c)-terminal\s+portion\b", text):
        reasons.append("terminal portion annotation")
    if re.search(r"\bfragment\b", text):
        reasons.append("explicit fragment annotation")
    if len(feature.location) == 3 and re.search(r"\bstart codon\b", text):
        reasons.append("single start-codon annotation")
    if len(feature.location) <= 120:
        labels = {str(v).strip().lower() for key in ("label", "gene") for v in values(key)}
        if labels & {"v5 tag", "6xhis", "6x his", "his-tag", "his tag", "ha tag", "flag tag", "myc tag"}:
            reasons.append("bounded fusion tag")
        if re.search(r"\bnuclear\s+locali[sz]ation\s+signal\b", text):
            reasons.append("bounded localization signal")
    return reasons


DNA_IUPAC_ALPHABET = frozenset("ACGTRYSWKMBDHVN")
DNA_UNAMBIGUOUS_ALPHABET = frozenset("ACGT")


def _qualifier_values(qualifiers: dict, key: str) -> list[Any]:
    value = (qualifiers or {}).get(key, [])
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _parse_single_int_qualifier(
    qualifiers: dict,
    key: str,
    default: int,
    valid_values: set[int] | None = None,
) -> tuple[int | None, dict[str, str] | None]:
    if key not in qualifiers:
        return default, None
    values = _qualifier_values(qualifiers, key)
    if not values or all(not str(value).strip() for value in values):
        return None, {
            "code": f"INVALID_{key.upper()}",
            "message": f"CDS qualifier '{key}' is present but empty",
        }
    normalized = [str(value).strip() for value in values]
    if len(set(normalized)) != 1:
        return None, {
            "code": f"INVALID_{key.upper()}",
            "message": f"CDS qualifier '{key}' has conflicting values: {normalized}",
        }
    try:
        parsed = int(normalized[0])
    except (TypeError, ValueError):
        return None, {
            "code": f"INVALID_{key.upper()}",
            "message": f"CDS qualifier '{key}' must be an integer: {normalized[0]!r}",
        }
    if valid_values is not None and parsed not in valid_values:
        return None, {
            "code": f"INVALID_{key.upper()}",
            "message": f"CDS qualifier '{key}' is outside allowed values {sorted(valid_values)}: {parsed}",
        }
    return parsed, None


def _translation_qualifier_values(qualifiers: dict) -> str | None:
    values = _qualifier_values(qualifiers, "translation")
    if not values or values == [""]:
        return None
    # GenBank readers can split a wrapped translation into multiple values or
    # preserve a comma as a line separator. Protein translations themselves do
    # not contain commas, so remove only separators and whitespace.
    return re.sub(r"[\s,]+", "", "".join(str(value) for value in values))


def _translation_compatible(
    expected: str | None,
    actual: str,
    partial: bool,
    start_codon: str = "",
    transl_table: int | None = None,
) -> tuple[bool, str | None]:
    if expected is None:
        return True, None
    expected = str(expected).upper()
    actual = str(actual).upper()
    expected_core = expected.rstrip("*")
    actual_core = actual.rstrip("*")
    if expected == actual or expected == actual_core:
        return True, None
    # A complete CDS translated with cds=True changes an initiator GTG to
    # M, while some source qualifiers were generated by generic translation
    # and retain V. Permit this single initiator representation difference.
    if (start_codon == "GTG" and transl_table == 11
            and actual_core.startswith("M") and expected_core.startswith("V")
            and expected_core[1:] == actual_core[1:]):
        return True, "source translation uses generic initiator amino acid"
    if partial and (expected_core.startswith(actual_core) or
                    expected_core.endswith(actual_core)):
        return True, "partial CDS translation matches a qualified boundary fragment"
    return False, None


def validate_cds_feature(feature, record_seq: str | Seq) -> dict[str, Any]:
    """Validate one CDS with its declared frame, codon table and translation.

    Complete CDS records must have unambiguous DNA, a valid ``codon_start`` and
    ``transl_table``, a table-specific initiator and terminal stop, no internal
    stop, and a matching translation qualifier when one is present. Explicit
    partial evidence waives only complete-ORF start/stop requirements; it never
    makes malformed metadata or ambiguous bases pass.
    """
    qualifiers = getattr(feature, "qualifiers", {}) or {}
    name_values = _qualifier_values(qualifiers, "label") or _qualifier_values(qualifiers, "gene")
    name = str(name_values[0]) if name_values else str(getattr(feature, "type", "CDS"))
    partial_evidence = cds_partial_evidence(feature)
    partial = bool(partial_evidence)
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    codon_start, codon_error = _parse_single_int_qualifier(
        qualifiers, "codon_start", 1, {1, 2, 3})
    if codon_error:
        errors.append(codon_error)
    transl_table, table_error = _parse_single_int_qualifier(
        qualifiers, "transl_table", 1)
    table = None
    if table_error:
        errors.append(table_error)
    elif transl_table not in CodonTable.unambiguous_dna_by_id:
        errors.append({
            "code": "INVALID_TRANSL_TABLE",
            "message": f"CDS qualifier 'transl_table' is not a known NCBI table: {transl_table}",
        })
    else:
        table = CodonTable.unambiguous_dna_by_id[transl_table]

    raw_sequence = ""
    try:
        raw_sequence = str(feature.extract(Seq(str(record_seq)))).upper()
    except (AttributeError, TypeError, ValueError) as exc:
        errors.append({
            "code": "CDS_EXTRACTION_FAILED",
            "message": f"CDS '{name}' could not be extracted: {exc}",
        })

    frame_offset = (codon_start - 1) if codon_start is not None else 0
    coding_sequence = raw_sequence[frame_offset:] if codon_start is not None else ""
    unknown_positions = [
        frame_offset + index
        for index, base in enumerate(coding_sequence)
        if base not in DNA_UNAMBIGUOUS_ALPHABET
    ]
    if unknown_positions:
        errors.append({
            "code": "CDS_UNKNOWN_BASES",
            "message": f"CDS '{name}' contains non-ACGT bases at extracted positions {unknown_positions[:12]}",
        })

    remainder = len(coding_sequence) % 3
    complete_coding_length = len(coding_sequence) - remainder
    if complete_coding_length == 0:
        errors.append({
            "code": "CDS_NO_COMPLETE_CODON",
            "message": f"CDS '{name}' has no complete codon after codon_start",
        })
    if remainder:
        if partial:
            warnings.append({
                "code": "CDS_PARTIAL_CODON",
                "message": f"partial CDS '{name}' has {remainder} trailing base(s) outside complete codons",
            })
        else:
            errors.append({
                "code": "CDS_FRAME_INVALID",
                "message": f"complete CDS '{name}' length after codon_start is not a multiple of 3",
            })

    start_codon = coding_sequence[:3] if len(coding_sequence) >= 3 else ""
    terminal_codon = coding_sequence[-3:] if len(coding_sequence) >= 3 else ""
    start_valid = bool(table and start_codon in table.start_codons)
    terminal_stop = bool(table and terminal_codon in table.stop_codons)
    codons = [
        coding_sequence[index:index + 3]
        for index in range(0, complete_coding_length, 3)
    ]
    generic_translation = ""
    if table is not None and complete_coding_length and not unknown_positions:
        generic_translation = str(Seq(coding_sequence[:complete_coding_length]).translate(
            table=transl_table, to_stop=False))
    premature_stop_positions = [
        frame_offset + index * 3
        for index, amino_acid in enumerate(generic_translation[:-1])
        if amino_acid == "*"
    ]
    if premature_stop_positions:
        errors.append({
            "code": "CDS_PREMATURE_STOP",
            "message": f"complete CDS '{name}' contains internal stop codon(s) at {premature_stop_positions}",
        })
    if not partial and codon_start is not None and table is not None:
        if not start_valid:
            errors.append({
                "code": "CDS_START_CODON_INVALID",
                "message": f"complete CDS '{name}' starts with {start_codon or '<missing>'}; expected one of {sorted(table.start_codons)} for table {transl_table}",
            })
        if not terminal_stop:
            errors.append({
                "code": "CDS_TERMINAL_STOP_MISSING",
                "message": f"complete CDS '{name}' lacks a terminal stop codon for table {transl_table}",
            })

    translation = ""
    if table is not None and coding_sequence and not unknown_positions:
        complete_sequence = coding_sequence[:complete_coding_length]
        if complete_sequence:
            if (not partial and not remainder and start_valid and terminal_stop
                    and not premature_stop_positions):
                try:
                    translation = str(Seq(coding_sequence).translate(
                        table=transl_table, cds=True))
                    if terminal_stop and not translation.endswith("*"):
                        translation += "*"
                except (TranslationError, ValueError) as exc:
                    errors.append({
                        "code": "CDS_TRANSLATION_FAILED",
                        "message": f"Biopython complete-CDS translation failed: {exc}",
                    })
                    translation = str(Seq(complete_sequence).translate(
                        table=transl_table, to_stop=False))
            else:
                translation = str(Seq(complete_sequence).translate(
                    table=transl_table, to_stop=False))

    expected_translation = _translation_qualifier_values(qualifiers)
    translation_qualifier_compatible, compatibility_note = _translation_compatible(
        expected_translation,
        translation,
        partial,
        start_codon=start_codon,
        transl_table=transl_table,
    )
    if not translation_qualifier_compatible:
        errors.append({
            "code": "CDS_TRANSLATION_MISMATCH",
            "message": f"qualifier translation {expected_translation} != computed translation {translation}",
        })
    elif compatibility_note:
        warnings.append({
            "code": "CDS_TRANSLATION_COMPATIBILITY",
            "message": compatibility_note,
        })

    return {
        "valid": not errors,
        "name": name,
        "partial": partial,
        "partial_evidence": partial_evidence,
        "raw_sequence": raw_sequence,
        "coding_sequence": coding_sequence,
        "codon_start": codon_start,
        "codon_start_valid": codon_start is not None,
        "transl_table": transl_table,
        "transl_table_valid": table is not None,
        "frame_offset": frame_offset,
        "is_multiple_of_three": remainder == 0,
        "remainder": remainder,
        "unknown_positions": unknown_positions,
        "has_unknown_bases": bool(unknown_positions),
        "start_codon": start_codon,
        "start_codon_valid": start_valid,
        "terminal_codon": terminal_codon,
        "terminal_stop": terminal_stop,
        "has_premature_stop": bool(premature_stop_positions),
        "premature_stop_positions": premature_stop_positions,
        "translation": translation,
        "expected_translation": expected_translation,
        "translation_qualifier_compatible": translation_qualifier_compatible,
        "compatibility_note": compatibility_note,
        "errors": errors,
        "warnings": warnings,
    }


def _clip_feature_to_interval(feature, start0: int, end0: int, *, linearized_circular: bool = False):
    """Clip feature parts to a linear interval while retaining qualifiers."""
    return _clip_feature_to_intervals(feature, [(start0, end0, 0, False)],
                                      linearized_circular=linearized_circular)


def _clip_feature_to_intervals(feature, intervals, *, linearized_circular=False):
    """Map retained source intervals, then judge the original feature once.

    Intervals contain source start/end, product offset and reverse-complement flag.
    Source feature part order remains biological order, independent of extraction order.
    """
    location = feature.location
    if location is None:
        return None
    source_parts = list(getattr(location, "parts", [location]))
    clipped_parts = []
    source_length = 0
    clipped_length = 0
    retained = []
    for part in source_parts:
        part_start = int(part.start)
        part_end = int(part.end)
        source_length += max(0, part_end - part_start)
        overlaps = []
        for start0, end0, offset, reverse in intervals:
            overlap_start, overlap_end = max(part_start,start0), min(part_end,end0)
            if overlap_start >= overlap_end:
                continue
            kwargs = {'strand':part.strand, 'ref':part.ref, 'ref_db':part.ref_db}
            local = FeatureLocation(
                part.start-start0 if overlap_start==part_start else overlap_start-start0,
                part.end-start0 if overlap_end==part_end else overlap_end-start0, **kwargs)
            if reverse: local=local._flip(end0-start0)
            overlaps.append((overlap_start,overlap_end,local._shift(offset) if offset else local))
        overlaps.sort(key=lambda item:item[0], reverse=part.strand==-1)
        clipped_parts.extend(item[2] for item in overlaps)
        # Repeated selected intervals copy bases, but cannot restore missing source bases.
        covered_end = part_start
        for a,b,_ in sorted(overlaps, key=lambda item:item[0]):
            clipped_length += max(0, b-max(a,covered_end))
            covered_end = max(covered_end,b)
        retained.append(overlaps)
    if not clipped_parts:
        return None

    updated = copy.deepcopy(feature)
    operator = getattr(location, "operator", "join") or "join"
    updated.location = (
        clipped_parts[0]
        if len(clipped_parts) == 1
        else CompoundLocation(clipped_parts, operator=operator)
    )

    # All bases may survive a circular-to-linear cut while the binding site
    # itself is broken across the two ends. Do not assert an intact primer.
    split_primer = linearized_circular and "primer" in feature.type.lower() and any(
        a.strand == b.strand and (
            (a.strand == 1 and int(a.end) == intervals[0][1]-intervals[0][0] and int(b.start) == 0)
            or (a.strand == -1 and int(a.start) == 0 and int(b.end) == intervals[0][1]-intervals[0][0])
        )
        for a, b in zip(clipped_parts, clipped_parts[1:])
    )
    if clipped_length < source_length or split_primer:
        qualifiers = copy.deepcopy(updated.qualifiers or {})
        qualifiers["partial"] = ["true"]
        note_values = qualifiers.get("note", [])
        if not isinstance(note_values, list):
            note_values = [note_values]
        note = (
            "primer binding site split by linearization; retained parts are not a contiguous binding site"
            if split_primer else
            "feature clipped at extraction boundary; complete feature is not asserted"
        )
        if note not in [str(value) for value in note_values]:
            note_values.append(note)
        qualifiers["note"] = note_values

        if "primer" in feature.type.lower():
            # Preserve the surviving annotation and original oligo metadata,
            # without claiming a truncated binding site is the original primer.
            updated.type = "misc_feature"
            qualifiers["source_feature_type"] = [feature.type]
            note_values.append("partial primer binding site; not an intact primer annotation")

        if feature.type == "CDS":
            # This qualifier described the uncut protein. Retain the source
            # record, but do not assert that whole translation for this fragment.
            qualifiers.pop("translation", None)
            codon_values = qualifiers.get("codon_start", ["1"])
            if not isinstance(codon_values, list):
                codon_values = [codon_values]
            try:
                old_codon_start = int(codon_values[0])
            except (TypeError, ValueError):
                old_codon_start = None
            if old_codon_start in (1, 2, 3):
                removed_5prime = 0
                found_first_retained_part = False
                for part, overlaps in zip(source_parts, retained):
                    part_start = int(part.start)
                    part_end = int(part.end)
                    if not overlaps:
                        if not found_first_retained_part:
                            removed_5prime += max(0, part_end - part_start)
                        continue
                    overlap_start, overlap_end, _ = overlaps[0]
                    if not found_first_retained_part:
                        if (part.strand or 1) == 1:
                            removed_5prime += max(0, overlap_start - part_start)
                        else:
                            removed_5prime += max(0, part_end - overlap_end)
                        found_first_retained_part = True
                    break
                adjusted_offset = ((old_codon_start - 1) - removed_5prime) % 3
                qualifiers["codon_start"] = [str(adjusted_offset + 1)]
        updated.qualifiers = qualifiers
    return updated


def slice_record_interval(
    record: SeqRecord,
    start0: int,
    length: int,
    circular: bool = False,
) -> SeqRecord:
    """Return a linear slice while retaining every overlapping feature part."""
    start0 = int(start0)
    length = int(length)
    if length < 0:
        raise ValueError(f"slice length must be non-negative: {length}")
    record_length = len(record.seq)
    if circular:
        if not record_length or not 0 <= start0 < record_length:
            raise ValueError(
                f"circular slice start {start0} is outside record length {record_length}"
            )
        if length > record_length:
            raise ValueError(
                f"circular slice length {length} exceeds record length {record_length}"
            )
        rotated = ConstructModel(record).rotate(start0).to_record()
        fragment = rotated[:length]
        source_record = rotated
        source_start = 0
    else:
        if not 0 <= start0 <= record_length or start0 + length > record_length:
            raise ValueError(
                f"linear slice [{start0}, {start0 + length}) is outside record length {record_length}"
            )
        fragment = copy.deepcopy(record[start0:start0 + length])
        source_record = record
        source_start = start0

    fragment.features = [
        clipped
        for feature in source_record.features
        if (clipped := _clip_feature_to_interval(
            feature, source_start, source_start + length, linearized_circular=circular
        )) is not None
    ]
    fragment.annotations = copy.deepcopy(record.annotations)
    fragment.dbxrefs = list(record.dbxrefs)
    fragment.id, fragment.name, fragment.description = record.id, record.name, record.description
    fragment.annotations["topology"] = "linear"
    from core.io.primer_annotation import sync_primer_coordinates
    return sync_primer_coordinates(fragment)


def rotate_sequence(dna_seq: MoleculeInput, origin_0based: int) -> ToolResult:
    """Change the display origin of a declared circle, preserving physical DNA."""
    source=as_molecule(dna_seq)
    if source.topology != 'circular':
        raise ValueError('Origin rotation requires an explicitly circular molecule')
    record=ConstructModel(source).rotate(origin_0based).to_record()
    product=derived_molecule(record,[source],operation='rotate_sequence',strandedness=source.strandedness,
                             mappings=[{'origin_0based':origin_0based,'length':len(source)}])
    return ToolResult(products=[product],analysis={'origin_0based':origin_0based})


def extract_subsequence(
    file_path_or_record: MoleculeInput,
    start: int,
    end: int,
    strand: int = 1,
    topology: str | None = None,
    wraps_origin: bool = True,
    whole_record_approved: bool = True,
) -> ToolResult:
    """Extract sub-sequence with rigorous topology, circular-wrap and strand handling."""
    rec = as_molecule(file_path_or_record)
    if topology is not None and rec.topology is not None and topology != rec.topology:
        raise ValueError('Declared extraction topology contradicts the material')
    topo = topology or rec.topology or "linear"

    extracted = extract_interval(
        record=rec,
        start0=start,
        end0=end,
        topology=topo,
        wraps_origin=wraps_origin,
        strand=strand,
        whole_record_approved=whole_record_approved,
    )

    seq_upper = extracted.upper()
    if start == end:
        fragment = slice_record_interval(rec, 0, len(rec), circular=(topo == 'circular'))
    else:
        fragment = slice_record_interval(
            rec,
            start,
            len(extracted),
            circular=(topo == "circular"),
        )
    if strand == -1:
        fragment = fragment.reverse_complement(id=True, name=True, description=True, annotations=True, dbxrefs=True)
    fragment.annotations['topology'] = 'linear'
    product = derived_molecule(fragment, [rec], operation='extract_subsequence', strandedness=rec.strandedness,
                               mappings=[{'start0': start, 'end0': end, 'strand': strand, 'wraps_origin': wraps_origin}])
    return ToolResult(products=[product], analysis={
        "length": len(seq_upper),
        "sha256": hashlib.sha256(seq_upper.encode("utf-8")).hexdigest().upper(),
        "interval_0based": [start, end],
        "strand": strand,
        "topology": "linear",
    })


def check_reading_frame(
    dna_seq: MoleculeInput,
    start_offset: int = 0,
    transl_table: int = 1,
) -> ToolResult:
    """Check a direct CDS sequence using the shared strict CDS contract."""
    source = as_molecule(dna_seq)
    sequence = str(source.seq).upper()
    start_offset = int(start_offset)
    if not 0 <= start_offset <= len(sequence):
        raise ValueError("start_offset must lie within the supplied DNA")
    feature = SeqFeature(
        FeatureLocation(start_offset, len(sequence), strand=1),
        type="CDS",
        qualifiers={
            "codon_start": ["1"],
            "transl_table": [str(transl_table)],
        },
    )
    audit = validate_cds_feature(feature, sequence)
    data = {
        "length_bp": len(sequence) - int(start_offset),
        "start_offset": start_offset,
        "is_multiple_of_three": audit["is_multiple_of_three"],
        "leftover_bases": audit["remainder"],
        "amino_acid_count": len(audit["translation"].rstrip("*")),
        "translation": audit["translation"],
        "has_premature_stop": audit["has_premature_stop"],
        "premature_stop_positions": [position+start_offset for position in audit["premature_stop_positions"]],
        "terminal_stop": audit["terminal_stop"],
        "start_codon_valid": audit["start_codon_valid"],
        "has_unknown_bases": audit["has_unknown_bases"],
        "valid": audit["valid"],
        "errors": audit["errors"],
        "warnings": audit["warnings"],
    }

    return ToolResult(analysis=data, checks=[check_result('reading_frame', subject=source,
               status='PASSED' if audit['valid'] else 'FAILED', scope='CDS_interval',
               conditions={'start_offset': start_offset, 'transl_table': transl_table}, details=audit)])


def mutate_sequence(
    dna_seq: MoleculeInput,
    mutations: list[dict[str, Any]],
) -> ToolResult:
    """Apply point mutations, insertions, or deletions with reference verification.

    Args:
        dna_seq: original DNA sequence.
        mutations: list of dicts with:
            - position_0based: int
            - ref_base: str (optional, verified if given)
            - alt_base: str (replacement nucleotide(s), or '' for deletion)

    Returns:
        dict with mutated sequence, updated length, and log of applied mutations.
    """
    record = as_molecule(dna_seq)
    model = ConstructModel(record)
    seq_list = list(str(record.seq).upper())
    applied = []

    # Sort mutations in descending order by position so insertions/deletions don't shift earlier indices
    sorted_muts = sorted(mutations, key=lambda x: int(x["position_0based"]), reverse=True)

    for m in sorted_muts:
        pos = int(m["position_0based"])
        ref = str(m.get("ref_base", "")).upper()
        alt = str(m.get("alt_base", "")).upper()

        if pos < 0 or pos >= len(seq_list):
            raise ValueError(f"Mutation position {pos} is out of range [0, {len(seq_list)})")

        if ref and seq_list[pos] != ref:
            raise ValueError(
                f"Reference base mismatch at position {pos}: expected {ref}, found {seq_list[pos]}"
            )

        old_base = seq_list[pos]
        if alt:
            seq_list[pos] = alt
        else:
            # Deletion
            del seq_list[pos]
        if len(alt) == 1:
            model.mutate([(pos, alt)])
        elif alt:
            model.replace(pos, pos + 1, alt)
        else:
            model.delete(pos, pos + 1)

        applied.append({
            "position_0based": pos,
            "original_base": old_base,
            "new_base": alt,
        })

    mutated_str = "".join(seq_list)
    left, right = copy.deepcopy(record.left_end), copy.deepcopy(record.right_end)
    for end, side in ((left, 'left'), (right, 'right')):
        if end is None:
            continue
        width = len(end.overhang_sequence)
        affected = any(m['position_0based'] < width if side == 'left' else
                       m['position_0based'] >= len(record)-width for m in applied)
        if width and affected:
            if side == 'left': left = None
            else: right = None
        else:
            end.cut_boundary = 0 if side == 'left' else len(mutated_str)
    product = derived_molecule(model.to_record(), [record], operation='mutate_sequence',
                               strandedness=record.strandedness,
                               left_end=left, right_end=right,
                               mappings=[{'mutations': list(reversed(applied))}])
    return ToolResult(products=[product], analysis={
        "mutated_length": len(mutated_str),
        "topology": record.annotations.get("topology", "linear"),
        "mutations_count": len(applied),
        "applied_mutations": list(reversed(applied)),
        'warnings':list(model.warnings),
    })


def strip_terminal_codons(
    cds_seq: MoleculeInput,
    strip_start: bool = False,
    strip_stop: bool = False,
) -> ToolResult:
    """Strip terminal start (ATG) or stop (TAA/TAG/TGA) codons from a coding sequence.

    Args:
        cds_seq: Nucleotide CDS sequence.
        strip_start: If True and sequence starts with ATG, strip first 3 bp.
        strip_stop: If True and sequence ends with TAA/TAG/TGA, strip last 3 bp.

    Returns:
        dict with modified sequence, original/new length, and stripped flags.
    """
    source = as_molecule(cds_seq)
    seq = str(source.seq).upper()
    n = len(seq)
    start_stripped = False
    stop_stripped = False

    if strip_start and seq.startswith("ATG"):
        seq = seq[3:]
        start_stripped = True

    STOP_CODONS = {"TAA", "TAG", "TGA"}
    if strip_stop and len(seq) >= 3 and seq[-3:] in STOP_CODONS:
        seq = seq[:-3]
        stop_stripped = True

    start = 3 if start_stripped else 0
    changed = start_stripped or stop_stripped
    record = slice_record_interval(source, start, len(seq)) if changed else copy.deepcopy(source)
    product = derived_molecule(record, [source], operation='strip_terminal_codons',
                               strandedness=source.strandedness,
                               left_end=None if changed else copy.deepcopy(source.left_end),
                               right_end=None if changed else copy.deepcopy(source.right_end),
                               mappings=[{'start0': start, 'length': len(seq), 'strand': 1}])
    return ToolResult(products=[product], analysis={
        "original_length": n,
        "new_length": len(seq),
        "start_stripped": start_stripped,
        "stop_stripped": stop_stripped,
        'scope': 'sequence_model',
    })
