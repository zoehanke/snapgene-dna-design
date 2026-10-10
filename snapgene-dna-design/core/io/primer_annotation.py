"""Primer annotation file operations; CLI and preparation share one implementation."""
from __future__ import annotations
import hashlib
import json
import os
import pathlib
import sys
from typing import Any, Tuple
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import SeqFeature
from Bio.SeqRecord import SeqRecord
from core.tools.snapgene_io import _primer_location, annotate_record_primers, normalize_primer_definition


def sync_primer_coordinates(record: SeqRecord) -> SeqRecord:
    """Refresh redundant coordinates from the current Feature locations.

    Called when an actual product is formed, not while exporting it. The
    oligo and declared binding core are never rewritten to fit a new DNA.
    A partial site's original full binding metadata belongs to its source;
    the surviving parts are recorded separately and are not an intact primer.
    """
    import copy
    from core.tools.snapgene_io import _location_interval, _strand_char
    replacements = {}
    binding_fields = ('binding_interval', 'binding_interval_0based', 'binding_strand',
                      'binding_sequence', 'binding_core_length')
    for index, feature in enumerate(record.features):
        active = 'primer' in feature.type.lower()
        source_type = feature.qualifiers.get('source_feature_type', [])
        if isinstance(source_type, str):
            source_type = [source_type]
        partial = not active and any('primer' in str(value).lower() for value in source_type)
        if not active and not partial:
            continue
        qualifiers = copy.deepcopy(feature.qualifiers)
        if partial:
            original_binding = {key: qualifiers.pop(key) for key in binding_fields if key in qualifiers}
            if original_binding:
                existing = qualifiers.get('source_binding', [])
                if not isinstance(existing, list):
                    existing = [existing]
                qualifiers['source_binding'] = existing + [json.dumps(original_binding, separators=(',', ':'))]
            qualifiers['binding_retained'] = [json.dumps([
                {'start0': int(part.start), 'end0': int(part.end), 'strand': part.strand}
                for part in feature.location.parts], separators=(',', ':'))]
        elif any(key in qualifiers for key in ('binding_interval', 'binding_interval_0based', 'binding_strand')) or (
                feature.location.strand in (1, -1) and not any(key in qualifiers for key in ('binding_sequence', 'binding_seq', 'binding_core'))):
            start, end = _location_interval(feature.location, len(record))
            if not any(key in qualifiers for key in ('binding_sequence', 'binding_seq', 'binding_core')) and feature.location.strand in (1, -1):
                # A known complete location establishes this binding core,
                # but cannot establish an unspecified full ordered oligo.
                core = str(feature.extract(record.seq)).upper()
                qualifiers['binding_sequence'] = [core]
                qualifiers.setdefault('binding_core_length', [str(len(core))])
                qualifiers.setdefault('binding_interval', [json.dumps([start, end], separators=(',', ':'))])
                qualifiers.setdefault('binding_strand', [_strand_char(feature.location.strand)])
            if 'binding_interval' in qualifiers:
                qualifiers['binding_interval'] = [json.dumps([start, end], separators=(',', ':'))]
            if 'binding_interval_0based' in qualifiers:
                old = qualifiers['binding_interval_0based']
                qualifiers['binding_interval_0based'] = ([start, end] if isinstance(old, list) and all(type(v) is int for v in old)
                    else [json.dumps([start, end], separators=(',', ':'))])
            if 'binding_strand' in qualifiers:
                qualifiers['binding_strand'] = [_strand_char(feature.location.strand)]
        if qualifiers != feature.qualifiers:
            updated = copy.deepcopy(feature)
            updated.qualifiers = qualifiers
            replacements[index] = updated
    if not replacements:
        return record
    result = copy.copy(record)
    result.features = [replacements.get(i, feature) for i, feature in enumerate(record.features)]
    return result

def _strand_char(strand: int | str | None) -> str:
    if strand in (-1, "-", "reverse"):
        return "-"
    return "+"


def _strand_int(strand: int | str | None) -> int:
    if strand in (-1, "-", "reverse"):
        return -1
    return 1


def _circular_matches(template_seq: str, primer_seq: str) -> list[Tuple[int, str]]:
    tpl = template_seq.upper()
    p = primer_seq.upper()
    if not p or len(p) > len(tpl):
        return []
    search = tpl + tpl[: len(p) - 1]
    matches: list[Tuple[int, str]] = []
    for strand, needle in (
        ("+", p),
        ("-", str(Seq(p).reverse_complement()).upper()),
    ):
        for pos in range(len(tpl)):
            if search[pos : pos + len(p)] == needle:
                matches.append((pos, strand))
    return matches


def find_unique_binding_site(
    template_seq: str,
    primer_seq: str,
    circular: bool = False,
) -> Tuple[int, str]:
    """Find unique binding site on forward or reverse complement strand.

    Rules:
      0 matches  -> raises ValueError (no match)
      1 match    -> returns (start_0based, strand) where strand is '+' or '-'
      >1 matches -> raises ValueError (ambiguous across strands)
    """
    tpl = template_seq.upper()
    p = primer_seq.upper()
    if circular:
        matches = _circular_matches(tpl, p)
    else:
        p_rc = str(Seq(p).reverse_complement()).upper()
        matches = []
        for strand, needle in (("+", p), ("-", p_rc)):
            idx = 0
            while True:
                pos = tpl.find(needle, idx)
                if pos == -1:
                    break
                matches.append((pos, strand))
                idx = pos + 1

    if len(matches) == 0:
        raise ValueError(
            f"Primer sequence '{primer_seq}' (len {len(primer_seq)}) has 0 binding sites on the template."
        )
    if len(matches) > 1:
        match_desc = ", ".join(f"pos {m[0]} ({m[1]})" for m in matches)
        raise ValueError(
            f"Ambiguous binding for primer '{primer_seq}': found {len(matches)} matches ({match_desc})."
        )

    return matches[0]


def _get_gb_primer_name(feat: SeqFeature) -> str:
    for q in ("label", "note", "gene"):
        vals = feat.qualifiers.get(q)
        if vals:
            return str(vals[0])
    return str(feat.id or "")


def _read_genbank_utf8(path: str | pathlib.Path) -> SeqRecord:
    with open(str(path), "r", encoding="utf-8-sig") as handle:
        from core.models.molecule import as_molecule
        from core.io.molecule_codec import restore_file_metadata
        return as_molecule(restore_file_metadata(SeqIO.read(handle, "genbank")))


def _gb_add_primer(record: SeqRecord, definition: dict[str, Any]) -> tuple[SeqRecord, dict[str, Any]]:
    payload = normalize_primer_definition(record, definition)
    return annotate_record_primers(record, [payload]), payload


def _assert_gb_primer_payloads(record: SeqRecord, payloads: list[dict[str, Any]]) -> None:
    for payload in payloads:
        matches = [
            feature
            for feature in record.features
            if feature.type in ("primer_bind", "primer")
            and _get_gb_primer_name(feature) == payload["name"]
        ]
        if len(matches) != 1:
            raise RuntimeError(
                "GenBank primer read-back expected one '%s', found %d"
                % (payload["name"], len(matches))
            )
        feature = matches[0]
        full = _first_qualifier_for_feature(feature, "primer_sequence", "primer_seq")
        core = _first_qualifier_for_feature(feature, "binding_sequence", "binding_seq")
        if full is None or "".join(full.split()).upper() != payload["sequence"].upper():
            raise RuntimeError(
                "GenBank primer '%s' full sequence changed during write"
                % payload["name"]
            )
        if core is None or "".join(core.split()).upper() != payload["binding_sequence"].upper():
            raise RuntimeError(
                "GenBank primer '%s' binding sequence changed during write"
                % payload["name"]
            )
        expected_location = _primer_location(
            payload["binding_interval_0based"][0],
            payload["binding_interval_0based"][1],
            payload["strand_int"],
            len(record.seq),
            payload["topology"],
        )
        if str(feature.location) != str(expected_location):
            raise RuntimeError(
                "GenBank primer '%s' binding location changed during write"
                % payload["name"]
            )


def _first_qualifier_for_feature(feature: SeqFeature, *keys: str) -> str | None:
    for key in keys:
        values = feature.qualifiers.get(key)
        if values:
            value = values[0] if isinstance(values, list) else values
            return str(value)
    return None


def _native_add_primer(sg, record: SeqRecord, definition: dict[str, Any]) -> dict[str, Any]:
    from sgffp import SgffBindingSite, SgffPrimer

    payload = normalize_primer_definition(record, definition)
    start, end = payload["binding_interval_0based"]
    sg.primers.add(
        SgffPrimer(
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
    )
    return payload


def _assert_native_primer_payloads(check_obj, payloads: list[dict[str, Any]]) -> None:
    for payload in payloads:
        matches = [primer for primer in check_obj.primers if primer.name == payload["name"]]
        if len(matches) != 1:
            raise RuntimeError(
                "Native primer read-back expected one '%s', found %d"
                % (payload["name"], len(matches))
            )
        primer = matches[0]
        if primer.sequence.upper() != payload["sequence"].upper():
            raise RuntimeError(
                "Native primer '%s' full sequence changed during write"
                % payload["name"]
            )
        sites = [site for site in primer.binding_sites if not site.simplified]
        if len(sites) != 1:
            raise RuntimeError(
                "Native primer '%s' read-back has %d binding sites"
                % (payload["name"], len(sites))
            )
        site = sites[0]
        start, end = payload["binding_interval_0based"]
        if (
            site.start != start
            or site.end != end
            or site.bound_strand != payload["strand"]
            or site.annealed_bases.upper() != payload["binding_sequence"].upper()
        ):
            raise RuntimeError(
                "Native primer '%s' binding metadata changed during write"
                % payload["name"]
            )


def annotate_primers_dna(
    source_path: str | pathlib.Path,
    out_path: str | pathlib.Path,
    op: str,
    primers_to_add: list[dict[str, Any]],
    target_name: str | None = None,
    new_primer: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """In-place primer modification for native SnapGene .dna files."""
    from sgffp import SgffReader, SgffWriter

    sg = SgffReader.from_file(str(source_path))
    from core.io.molecule_codec import MARKER, metadata_text
    from core.tools.snapgene_io import read_native_dna_record, _read_native_data
    original_material=read_native_dna_record(source_path) if MARKER in str(sg.notes.description) else None
    seq_str = str(sg.sequence.data.value).upper()
    hash_before = hashlib.sha256(seq_str.encode("ascii")).hexdigest()

    prev_primers_count = len(sg.primers)
    prev_features_count = len(sg.features)

    topology = getattr(sg.sequence.data, "topology", None) or "linear"
    record = SeqRecord(
        Seq(seq_str),
        id="native",
        annotations={"molecule_type": "DNA", "topology": topology},
    )
    pending_payloads: list[dict[str, Any]] = []

    if op == "add":
        for p_def in primers_to_add:
            pending_payloads.append(_native_add_primer(sg, record, p_def))

    elif op == "remove":
        if not target_name:
            raise ValueError("Operation 'remove' requires primer --name.")
        matches = [i for i, p in enumerate(sg.primers) if p.name == target_name]
        if len(matches) == 0:
            raise ValueError(f"Primer '{target_name}' not found for removal (0 matches).")
        if len(matches) > 1:
            raise ValueError(
                f"Ambiguous primer name '{target_name}': found {len(matches)} matches. Refusing to remove."
            )
        sg.primers.remove(matches[0])

    elif op == "replace":
        if not target_name:
            raise ValueError("Operation 'replace' requires primer --name.")
        if not new_primer:
            raise ValueError("Operation 'replace' requires new primer definition (--seq).")

        matches = [i for i, p in enumerate(sg.primers) if p.name == target_name]
        if len(matches) == 0:
            raise ValueError(f"Primer '{target_name}' not found for replacement (0 matches).")
        if len(matches) > 1:
            raise ValueError(
                f"Ambiguous primer name '{target_name}': found {len(matches)} matches. Refusing to replace."
            )

        sg.primers.remove(matches[0])
        replacement = dict(new_primer)
        replacement["name"] = replacement.get("name") or target_name
        pending_payloads.append(_native_add_primer(sg, record, replacement))

    elif op == "clear":
        sg.primers.clear()
    else:
        raise ValueError(f"Unsupported operation: {op}")

    # Write output
    SgffWriter.to_file(sg, str(out_path))

    if original_material is not None:
        import copy
        from core.models.molecule import derived_molecule
        actual,_=_read_native_data(out_path)
        updated=copy.deepcopy(original_material)
        updated.features=[f for f in updated.features if f.type not in ('primer','primer_bind')]
        updated.features.extend(copy.deepcopy(f) for f in actual.features if f.type in ('primer','primer_bind'))
        updated=derived_molecule(updated,[original_material],operation='primer_annotation_'+op,
            strandedness=original_material.strandedness,left_end=original_material.left_end,right_end=original_material.right_end)
        sg.notes.description=metadata_text(updated,actual,native=True)
        SgffWriter.to_file(sg,str(out_path))

    # Re-read output and enforce sequence invariance
    check_obj = SgffReader.from_file(str(out_path))
    seq_after = str(check_obj.sequence.data.value).upper()
    hash_after = hashlib.sha256(seq_after.encode("ascii")).hexdigest()

    if hash_before != hash_after:
        if os.path.exists(str(out_path)):
            os.remove(str(out_path))
        raise RuntimeError(
            f"Hard invariant violated: sequence altered during primer {op}! "
            f"Expected {hash_before[:12]}..., got {hash_after[:12]}..."
        )
    if pending_payloads:
        _assert_native_primer_payloads(check_obj, pending_payloads)

    return {
        "status": "success",
        "op": op,
        "format": "dna",
        "source": str(source_path),
        "output": str(out_path),
        "length": len(seq_after),
        "features_count": len(check_obj.features),
        "primers_count": len(check_obj.primers),
        "previous_primers_count": prev_primers_count,
        "previous_features_count": prev_features_count,
    }


def annotate_primers_gb(
    source_path: str | pathlib.Path,
    out_path: str | pathlib.Path,
    op: str,
    primers_to_add: list[dict[str, Any]],
    target_name: str | None = None,
    new_primer: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """In-place primer modification for GenBank (.gb/.gbk) files."""
    record = _read_genbank_utf8(source_path)
    seq_str = str(record.seq).upper()
    hash_before = hashlib.sha256(seq_str.encode("ascii")).hexdigest()

    prev_features_count = len(record.features)
    prev_primers = [f for f in record.features if f.type in ("primer_bind", "primer")]
    prev_primers_count = len(prev_primers)
    pending_payloads: list[dict[str, Any]] = []

    if op == "add":
        for p_def in primers_to_add:
            record, payload = _gb_add_primer(record, p_def)
            pending_payloads.append(payload)

    elif op == "remove":
        if not target_name:
            raise ValueError("Operation 'remove' requires primer --name.")
        matches = [
            (idx, f)
            for idx, f in enumerate(record.features)
            if f.type in ("primer_bind", "primer") and _get_gb_primer_name(f) == target_name
        ]
        if len(matches) == 0:
            raise ValueError(f"Primer '{target_name}' not found for removal (0 matches).")
        if len(matches) > 1:
            raise ValueError(
                f"Ambiguous primer name '{target_name}': found {len(matches)} matches. Refusing to remove."
            )
        del record.features[matches[0][0]]

    elif op == "replace":
        if not target_name:
            raise ValueError("Operation 'replace' requires primer --name.")
        if not new_primer:
            raise ValueError("Operation 'replace' requires new primer definition (--seq).")

        matches = [
            (idx, f)
            for idx, f in enumerate(record.features)
            if f.type in ("primer_bind", "primer") and _get_gb_primer_name(f) == target_name
        ]
        if len(matches) == 0:
            raise ValueError(f"Primer '{target_name}' not found for replacement (0 matches).")
        if len(matches) > 1:
            raise ValueError(
                f"Ambiguous primer name '{target_name}': found {len(matches)} matches. Refusing to replace."
            )

        replacement = dict(new_primer)
        replacement["name"] = replacement.get("name") or target_name
        updated_record, payload = _gb_add_primer(record, replacement)
        # Preserve the original feature position in the feature list while
        # replacing only that primer definition.
        added_feature = updated_record.features.pop()
        updated_record.features[matches[0][0]] = added_feature
        record = updated_record
        pending_payloads.append(payload)

    elif op == "clear":
        record.features = [
            f for f in record.features if f.type not in ("primer_bind", "primer")
        ]
    else:
        raise ValueError(f"Unsupported operation: {op}")

    # Write output
    with open(str(out_path), "w", encoding="utf-8") as fh:
        from core.io.molecule_codec import genbank_record
        SeqIO.write(genbank_record(record), fh, "genbank")

    # Re-read output and enforce sequence invariance
    check_rec = _read_genbank_utf8(out_path)
    seq_after = str(check_rec.seq).upper()
    hash_after = hashlib.sha256(seq_after.encode("ascii")).hexdigest()

    if hash_before != hash_after:
        if os.path.exists(str(out_path)):
            os.remove(str(out_path))
        raise RuntimeError(
            f"Hard invariant violated: sequence altered during primer {op}! "
            f"Expected {hash_before[:12]}..., got {hash_after[:12]}..."
        )
    if pending_payloads:
        _assert_gb_primer_payloads(check_rec, pending_payloads)

    current_primers = [
        f for f in check_rec.features if f.type in ("primer_bind", "primer")
    ]
    return {
        "status": "success",
        "op": op,
        "format": "genbank",
        "source": str(source_path),
        "output": str(out_path),
        "length": len(seq_after),
        "features_count": len(check_rec.features),
        "primers_count": len(current_primers),
        "previous_primers_count": prev_primers_count,
        "previous_features_count": prev_features_count,
    }
