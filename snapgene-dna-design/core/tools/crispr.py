# -*- coding: utf-8 -*-
"""core/tools/crispr.py - Atomic CRISPR/Cas Gene Editing and HDR Donor Design Tools.

Provides deterministic, side-effect free tools for:
1. sgRNA candidate scanning with PAM recognition, GC content, and Pol III poly-T termination checks.
2. sgRNA forward/reverse cloning oligo duplex preparation for U6 plasmids (pX458, pX459, lentiCRISPR).
3. Homology-Directed Repair (HDR) donor template design (ssODN or plasmid arms) with silent PAM mutation to prevent re-cleavage.
"""
from __future__ import annotations
from core.models.molecule import MoleculeInput, as_molecule, derived_molecule
from core.tools.result import ToolResult

import pathlib
import re
from typing import Any

from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from core.tools.inspection import _load_record
from core.tools.translation import get_codon_synonyms, reverse_complement


def design_crispr_grna(
    target_seq_or_file: str | pathlib.Path | SeqRecord,
    nuclease: str = "SpCas9",
    start: int | None = None,
    end: int | None = None,
    circular: bool = False,
    vector_seq_or_file: MoleculeInput | None = None,
    max_mismatches: int = 3,
    transcription_promoter: str = 'unspecified',
) -> ToolResult:
    """Scan DNA sequence for CRISPR sgRNA candidate target sites.

    Args:
        target_seq_or_file: Target DNA sequence or file.
        nuclease: 'SpCas9' (NGG, 3' side, 20 nt spacer) or 'AsCas12a' (TTTV, 5' side, 23 nt spacer).
        start: Optional 0-based start coordinate to restrict scan.
        end: Optional 0-based end coordinate to restrict scan.
        circular: Whether sequence is circular.

    Returns:
        Candidate evidence profiles and transparent screening ranks. No calibrated
        activity score. Optional supplied-vector NGG check supports SpCas9 only.
    """
    from core.io.input_resolution import resolve_sequence_input
    rec, seq = resolve_sequence_input(target_seq_or_file)

    n = len(seq)
    scan_start = 0 if start is None else max(0, start)
    scan_end = n if end is None else min(n, end)

    nuc_lower = nuclease.lower()
    is_cas12 = "cas12" in nuc_lower or "cpf1" in nuc_lower

    candidates = []
    search_seq = (seq + seq[:30]) if circular else seq

    if not is_cas12:
        # SpCas9: 20 nt spacer + NGG PAM (3' PAM)
        # Search top strand (+1): [spacer: 20 nt][PAM: .GG]
        pat_top = re.compile(r"(?=([ACGT]{20}[ACGT]GG))")
        for m in pat_top.finditer(search_seq):
            pos = m.start()
            if pos >= n:
                break
            full_hit = m.group(1)
            spacer = full_hit[:20]
            pam = full_hit[20:23]
            cut_pos = (pos + 17) % n

            if (scan_start <= pos and (pos + 23) <= scan_end) or (circular and pos < n):
                candidates.append(_evaluate_grna_candidate(spacer, pam, pos, (pos + 23) % n, 1, cut_pos, n))

        # Search bottom strand (-1): reverse complement of target has NGG PAM
        # Top strand contains CCN + 20 nt spacer_rc: [CCN: 3 nt][spacer_rc: 20 nt]
        pat_bottom = re.compile(r"(?=(CC[ACGT]([ACGT]{20})))")
        for m in pat_bottom.finditer(search_seq):
            pos = m.start()
            if pos >= n:
                break
            pam_rc = m.group(1)[:3]
            spacer_rc = m.group(1)[3:23]
            pam = str(Seq(pam_rc).reverse_complement())
            spacer = str(Seq(spacer_rc).reverse_complement())
            cut_pos = (pos + 6) % n

            if (scan_start <= pos and (pos + 23) <= scan_end) or (circular and pos < n):
                candidates.append(_evaluate_grna_candidate(spacer, pam, pos, (pos + 23) % n, -1, cut_pos, n))
    else:
        # AsCas12a: TTTV PAM on 5' end + 23 nt spacer
        # Top strand: [TTT[ACG]: 4 nt][spacer: 23 nt]
        pat_top = re.compile(r"(?=(TTT[ACG]([ACGT]{23})))")
        for m in pat_top.finditer(search_seq):
            pos = m.start()
            if pos >= n:
                break
            pam = m.group(1)[:4]
            spacer = m.group(1)[4:27]
            cut_pos = (pos + 22) % n

            if (scan_start <= pos and (pos + 27) <= scan_end) or (circular and pos < n):
                candidates.append(_evaluate_grna_candidate(spacer, pam, pos, (pos + 27) % n, 1, cut_pos, n))

        # Bottom strand: reverse complement has TTTV PAM
        # Top strand contains [spacer_rc: 23 nt][CGT]AAA: 4 nt]
        pat_bottom = re.compile(r"(?=(([ACGT]{23})[CGT]AAA))")
        for m in pat_bottom.finditer(search_seq):
            pos = m.start()
            if pos >= n:
                break
            spacer_rc = m.group(1)[:23]
            pam_rc = m.group(1)[23:27]
            pam = str(Seq(pam_rc).reverse_complement())
            spacer = str(Seq(spacer_rc).reverse_complement())
            cut_pos = (pos + 5) % n

            if (scan_start <= pos and (pos + 27) <= scan_end) or (circular and pos < n):
                candidates.append(_evaluate_grna_candidate(spacer, pam, pos, (pos + 27) % n, -1, cut_pos, n))

    from core.tools.grna_evaluation import evaluate_candidates
    return ToolResult(analysis=evaluate_candidates(candidates, seq, circular, is_cas12,
        vector_seq_or_file, max_mismatches, transcription_promoter))


def _evaluate_grna_candidate(
    spacer: str,
    pam: str,
    start_0b: int,
    end_0b: int,
    strand: int,
    cut_pos: int,
    total_len: int,
) -> dict[str, Any]:
    n = len(spacer)
    gc_count = spacer.count("G") + spacer.count("C")
    gc_pct = round((gc_count / n) * 100.0, 1)

    has_poly_t = ("TTTT" in spacer)

    return {
        "spacer": spacer,
        "pam": pam,
        "strand": strand,
        "target_interval_0based": [start_0b, end_0b],
        "cut_position_0based": cut_pos,
        "gc_percent": gc_pct,
        "has_poly_t": has_poly_t,
        "quality_score": None,
        "warnings": [],
    }


def prepare_grna_oligos(
    spacer_seq: str,
    vector_type: str = "BbsI",
) -> ToolResult:
    """Prepare top and bottom forward/reverse oligos with cloning overhangs for sgRNA vectors.

    For BbsI/BsmBI plasmids (e.g. pX458, pX459, lentiCRISPRv2):
    - Top oligo: CACC + [optional G] + spacer
    - Bottom oligo: AAAC + reverse_complement([optional G] + spacer)
    An extra 'G' is automatically prepended if the 20 nt spacer does not start with G,
    as human U6 RNA Pol III promoter requires a 5' Guanine for high-efficiency transcription.
    """
    clean_spacer = str(spacer_seq).strip().upper()
    vec = str(vector_type).strip().lower()

    u6_needs_g = not clean_spacer.startswith("G")
    init_g = "G" if u6_needs_g else ""

    top_seq = init_g + clean_spacer
    bottom_rc = str(Seq(top_seq).reverse_complement())

    if "bsmbi" in vec or "lenti" in vec:
        # lentiCRISPRv2 (BsmBI cut): 5' CACC on top, 5' AAAC on bottom
        fwd_oligo = "CACC" + top_seq
        rev_oligo = "AAAC" + bottom_rc
        overhang_5p = "CACC"
        overhang_3p = "AAAC"
    else:
        # Standard pX330 / pX458 / pX459 (BbsI cut): 5' CACC on top, 5' AAAC on bottom
        fwd_oligo = "CACC" + top_seq
        rev_oligo = "AAAC" + bottom_rc
        overhang_5p = "CACC"
        overhang_3p = "AAAC"

    data = {
        "spacer": clean_spacer,
        "vector_type": vector_type,
        "u6_5prime_g_added": u6_needs_g,
        "forward_oligo": {
            "sequence": fwd_oligo,
            "length": len(fwd_oligo),
            "description": f"Top strand oligo with {overhang_5p} sticky overhang",
        },
        "reverse_oligo": {
            "sequence": rev_oligo,
            "length": len(rev_oligo),
            "description": f"Bottom strand oligo with {overhang_3p} sticky overhang",
        },
    }

    products = []
    for key in ('forward_oligo','reverse_oligo'):
        value = data[key]
        record = SeqRecord(Seq(value['sequence']),id=key,annotations={'molecule_type':'DNA','topology':'linear'})
        products.append(derived_molecule(record,operation='prepare_grna_oligos',strandedness='single'))
    return ToolResult(products=products,analysis=data)


def prepare_pml104_guide(
    vector_record_or_seq: str | pathlib.Path | SeqRecord,
    spacer_seq: str,
) -> ToolResult:
    """Prepare a pML104 guide plasmid by template PCR and KLD circularization.

    The unmodified pML104 cloning cassette does not contain the complete sgRNA
    scaffold. The forward primer restores its missing 5-prime sequence.
    Vector-specific method: Hu et al. 2018, doi:10.21767/2471-8084.100058.
    This is not the BbsI/U6 oligo protocol and does not prepend a transcription G.
    """
    from Bio.SeqFeature import FeatureLocation, SeqFeature
    from core.io.input_resolution import resolve_sequence_record
    from core.models.construct_model import feature_to_dict
    from core.tools.amplification import simulate_pcr

    spacer = str(spacer_seq).strip().upper()
    if len(spacer) != 20 or set(spacer) - set("ACGT"):
        raise ValueError("pML104 requires an explicit 20 nt A/C/G/T spacer")
    source = _load_record(vector_record_or_seq)
    if source.annotations.get("topology", "circular") != "circular":
        raise ValueError("pML104 PCR requires the complete circular vector template")
    # Express the same double-stranded template in sgRNA transcription orientation.
    template = source.reverse_complement(id=source.id, name=source.name,
                                         description=source.description, annotations=True)
    forward = "GTTTTAGAGCTAGAAATAGCAAGTTAAAATAAGGC"
    reverse = str(Seq(spacer).reverse_complement()) + "GATCATTTATCTTTCACTGC"
    amplified = simulate_pcr(template, forward, reverse, topology="circular")
    sequence = str(amplified.only_product().seq)
    prefix = "GTTTTAGAGCTAGAAATAGCAAGTTAAAATAAGGC"
    scaffold = "GTTTTAGAGCTAGAAATAGCAAGTTAAAATAAGGCTAGTCCGTTATCAACTTGAAAAAGTGGCACCGAGTCGGTGGTGC"
    if not sequence.startswith(scaffold + "TTTTTT") or not sequence.endswith(spacer):
        raise ValueError("Template does not match the published pML104 PCR cassette layout")
    import copy
    from core.tools.assembly import ligate_fragments
    circularized = ligate_fragments([amplified.only_product()], circular=True)
    product = copy.deepcopy(circularized.only_product())
    product.id = "pML104_guide"
    product.features.append(SeqFeature(FeatureLocation(len(sequence)-20, len(sequence), strand=1),
        type="misc_RNA", qualifiers={"label": ["guide spacer"], "note": [spacer]}))
    terminator = len(scaffold)
    product.features.append(SeqFeature(FeatureLocation(0, terminator, strand=1),
        type="misc_RNA", qualifiers={"label": ["sgRNA scaffold"],
                                    "note": ["Complete scaffold retained; PCR restores missing 5-prime segment"]}))
    primers = []
    n = len(source)
    for name, oligo, binding in (
        ("pML104_scaffold_F", forward, amplified.analysis['forward_binding']),
        ("pML104_guide_R", reverse, amplified.analysis['reverse_binding']),
    ):
        length = binding["binding_core_length"]
        start = (n - binding["template_end_0based"]) % n
        end = (start + length) % n
        primers.append({"name": name, "sequence": oligo, "seq": oligo,
            "binding_sequence": oligo[-length:], "binding_interval_0based": [start, end or n],
            "strand": -binding["strand"], "role": "pML104 inverse PCR"})
    template_data = {"sequence": str(source.seq), "topology": "circular",
                     "features": [feature_to_dict(f, n) for f in source.features], "id": source.id}
    material = derived_molecule(product,[circularized.only_product()],operation="annotate_guide_cassette",strandedness="double")
    return ToolResult(products=[material],checks=circularized.checks,analysis={"product_topology": "circular", "topology": "circular",
        "product_length": len(sequence),
        "spacer": spacer, "scaffold_prefix": prefix, "scaffold_complete": True,
        "primers": primers,
        "preparation": [{"id": "pML104_inverse_PCR", "method": "inverse_pcr",
                         "template": template_data, "template_orientation": -1,
                         "primers": primers, "product": amplified.only_product()}],
        "reaction_products": circularized.products,
        "circularization": {"method": "KLD", "sequence_change": "none",
                            "steps": ["high-fidelity blunt PCR", "kinase and ligase circularization", "DpnI parental-template removal"]},
        "citation": "https://pmc.ncbi.nlm.nih.gov/articles/PMC5868978/"})


def _normalise_hdr_edit(
    sequence: str,
    cut_position_0based: int,
    edit_dna: str,
    edit_start_0based: int | None,
    edit_end_0based: int | None,
) -> dict[str, Any]:
    """Validate one HDR edit and return its source-to-product coordinate map."""
    seq = str(sequence).strip().upper()
    n = len(seq)
    if not (0 <= int(cut_position_0based) <= n):
        raise ValueError(f"cut_position_0based must be a boundary in [0, {n}]")
    if (edit_start_0based is None) != (edit_end_0based is None):
        raise ValueError("edit_start_0based and edit_end_0based must be provided together")

    edit = str(edit_dna).strip().upper()
    if set(edit) - set("ACGT"):
        raise ValueError("edit_dna must contain only A/C/G/T")

    if edit_start_0based is None:
        # Legacy API: edit is an insertion at the Cas cut boundary.
        start = end = int(cut_position_0based)
        mode = "insert"
    else:
        start, end = int(edit_start_0based), int(edit_end_0based)
        if not (0 <= start <= end <= n):
            raise ValueError(f"replacement interval must satisfy 0 <= start <= end <= {n}")
        mode = "insert" if start == end else "replace"

    if mode == "replace" and start == end:
        raise ValueError("replacement interval must be half-open; use equal boundaries for an insertion")
    if mode == "insert" and not edit:
        raise ValueError("edit_dna must not be empty for an HDR insertion")

    product = seq[:start] + edit + seq[end:]
    delta = len(edit) - (end - start)
    cut_product = _map_hdr_boundary(int(cut_position_0based), start, end, len(edit))
    return {
        "original_sequence": seq,
        "edited_target_sequence": product,
        "edit_dna": edit,
        "edit_start_0based": start,
        "edit_end_0based": end,
        "edit_mode": mode,
        "replacement_length": end - start,
        "edit_length": len(edit),
        "length_delta": delta,
        "cut_position_0based": int(cut_position_0based),
        "edited_cut_position_0based": cut_product,
    }


def _map_hdr_boundary(boundary: int, start: int, end: int, replacement_length: int) -> int:
    """Map a source boundary into a sequence after one half-open edit."""
    if boundary <= start:
        return boundary
    if boundary >= end:
        return start + replacement_length + (boundary - end)
    # A cut inside a replacement is retained at the corresponding point in
    # the replacement. This keeps a same-length codon replacement centred at
    # the original Cas cut and gives deterministic behaviour for indels.
    return start + min(boundary - start, replacement_length)


def _map_hdr_interval(start: int, end: int, edit_start: int, edit_end: int, replacement_length: int) -> list[int]:
    return [
        _map_hdr_boundary(start, edit_start, edit_end, replacement_length),
        _map_hdr_boundary(end, edit_start, edit_end, replacement_length),
    ]


def _extract_arms_from_sequence(
    sequence: str,
    cut_position_0based: int,
    left_arm_length: int,
    right_arm_length: int,
    circular: bool,
) -> dict[str, Any]:
    """Extract arms from one concrete sequence at one concrete cut boundary."""
    if left_arm_length < 0 or right_arm_length < 0:
        raise ValueError("homology arm lengths must be non-negative")
    n = len(sequence)
    if n == 0:
        raise ValueError("target sequence must not be empty")
    cut = (cut_position_0based % n) if circular else cut_position_0based
    if not (0 <= cut <= n):
        raise ValueError(f"cut_position_0based must be in [0, {n}]")
    warnings: list[str] = []

    if circular:
        left_start = (cut - left_arm_length) % n
        right_end = (cut + right_arm_length) % n
        left_arm = "".join(sequence[(left_start + i) % n] for i in range(left_arm_length))
        right_arm = "".join(sequence[(cut + i) % n] for i in range(right_arm_length))
        left_interval = [left_start, cut]
        right_interval = [cut, right_end]
    else:
        s_left = max(0, cut - left_arm_length)
        e_right = min(n, cut + right_arm_length)
        if cut - left_arm_length < 0:
            warnings.append(
                f"Left homology arm truncated by 5' template boundary (requested {left_arm_length} nt, obtained {cut - s_left} nt)"
            )
        if cut + right_arm_length > n:
            warnings.append(
                f"Right homology arm truncated by 3' template boundary (requested {right_arm_length} nt, obtained {e_right - cut} nt)"
            )
        left_arm = sequence[s_left:cut]
        right_arm = sequence[cut:e_right]
        left_interval = [s_left, cut]
        right_interval = [cut, e_right]

    return {
        "cut_position_0based": cut,
        "left_homology_arm": left_arm,
        "left_arm_interval": left_interval,
        "left_arm_length": len(left_arm),
        "right_homology_arm": right_arm,
        "right_arm_interval": right_interval,
        "right_arm_length": len(right_arm),
        "circular": circular,
        "warnings": warnings,
    }


def _spcas9_guide_match(
    sequence: str,
    grna_seq: str,
    grna_strand: int,
    cut_position_0based: int,
    circular: bool = False,
) -> dict[str, Any]:
    """Resolve an exact SpCas9 guide/PAM/cut match on the source sequence."""
    g = str(grna_seq).strip().upper()
    if len(g) != 20 or set(g) - set("ACGT"):
        raise ValueError("grna_seq must be an explicit 20 nt A/C/G/T spacer")
    if grna_strand not in (1, -1):
        raise ValueError("grna_strand must be 1 or -1")

    seq = str(sequence).upper()
    n = len(seq)
    search_limit = n if circular else max(0, n - 22)
    hits: list[dict[str, Any]] = []

    def take(start: int, length: int) -> str:
        if circular:
            return "".join(seq[(start + i) % n] for i in range(length))
        return seq[start:start + length]

    for start in range(search_limit):
        if grna_strand == 1:
            protospacer = take(start, 20)
            pam_plus = take(start + 20, 3)
            if protospacer != g or not pam_plus.endswith("GG"):
                continue
            cut = (start + 17) % n if circular else start + 17
            pam_interval = [(start + 20) % n, (start + 23) % n] if circular else [start + 20, start + 23]
        else:
            pam_plus = take(start, 3)
            protospacer_plus = take(start + 3, 20)
            if not pam_plus.startswith("CC") or str(Seq(protospacer_plus).reverse_complement()) != g:
                continue
            cut = (start + 6) % n if circular else start + 6
            pam_interval = [start % n, (start + 3) % n] if circular else [start, start + 3]
            protospacer = g

        hits.append({
            "spacer": g,
            "strand": grna_strand,
            "target_interval_0based": [start % n, (start + 23) % n] if circular else [start, start + 23],
            "protospacer_interval_0based": [
                start % n, (start + 20) % n
            ] if grna_strand == 1 and circular else (
                [(start + 3) % n, (start + 23) % n] if circular else ([start, start + 20] if grna_strand == 1 else [start + 3, start + 23])
            ),
            "pam_interval_0based": pam_interval,
            "pam_plus_strand": pam_plus,
            "pam_sequence": str(Seq(pam_plus).reverse_complement()) if grna_strand == -1 else pam_plus,
            "cut_position_0based": cut,
        })

    expected_cut = cut_position_0based % n if circular and n else cut_position_0based
    if len(hits) > 1:
        raise ValueError("grna_seq/PAM matches multiple target sites; guide/cut is ambiguous")
    matching_cut = [h for h in hits if h["cut_position_0based"] == expected_cut]
    if not matching_cut:
        if not hits:
            raise ValueError("grna_seq/PAM does not match target sequence")
        raise ValueError(
            f"grna_seq matches target but no SpCas9 cut at cut_position_0based={cut_position_0based}"
        )
    if len(matching_cut) > 1:
        raise ValueError("grna_seq/PAM/cut match is ambiguous on target sequence")
    return matching_cut[0]


def _edited_guide_view(
    guide: dict[str, Any],
    edited_sequence: str,
    edit_start: int,
    edit_end: int,
    replacement_length: int,
    circular: bool,
) -> dict[str, Any]:
    """Project source guide/PAM intervals onto the edited sequence."""
    n = len(edited_sequence)
    start = int(guide["target_interval_0based"][0])
    if circular:
        # The current HDR replacement contract is linear within a circular
        # record. Keep projected metadata conservative at an origin wrap.
        return {"edited_target_interval_0based": guide["target_interval_0based"]}
    target = _map_hdr_interval(start, start + 23, edit_start, edit_end, replacement_length)
    protospacer = _map_hdr_interval(
        int(guide["protospacer_interval_0based"][0]),
        int(guide["protospacer_interval_0based"][1]),
        edit_start,
        edit_end,
        replacement_length,
    )
    pam = _map_hdr_interval(
        int(guide["pam_interval_0based"][0]),
        int(guide["pam_interval_0based"][1]),
        edit_start,
        edit_end,
        replacement_length,
    )
    pam_plus = edited_sequence[pam[0]:pam[1]]
    protospacer_plus = edited_sequence[protospacer[0]:protospacer[1]]
    edited_spacer = protospacer_plus if guide["strand"] == 1 else str(Seq(protospacer_plus).reverse_complement())
    edited_pam = str(Seq(pam_plus).reverse_complement()) if guide["strand"] == -1 else pam_plus
    return {
        "edited_target_interval_0based": target,
        "edited_protospacer_interval_0based": protospacer,
        "edited_pam_interval_0based": pam,
        "edited_spacer": edited_spacer,
        "edited_pam_plus_strand": pam_plus,
        "edited_pam_sequence": edited_pam,
        "edited_guide_matches": edited_spacer == guide["spacer"] and edited_pam.endswith("GG"),
    }


def _cds_covering_interval(record: SeqRecord, start: int, end: int):
    """Return a CDS feature covering all bases in a genomic interval."""
    for feature in record.features:
        if feature.type != "CDS" or feature.location is None:
            continue
        parts = list(getattr(feature.location, "parts", [feature.location]))
        covered = any(int(part.start) <= start and end <= int(part.end) for part in parts)
        if covered:
            return feature
    return None


def _record_cds_frame(feature, fallback: int = 0) -> int:
    """Read CDS frame metadata without confusing strand with phase."""
    qualifiers = feature.qualifiers or {}
    for key, one_based in (("codon_start", True), ("phase", False)):
        value = qualifiers.get(key)
        if value:
            try:
                parsed = int(value[0] if isinstance(value, list) else value)
                parsed = parsed - 1 if one_based else parsed
                if parsed in (0, 1, 2):
                    return parsed
            except (TypeError, ValueError):
                pass
    return int(fallback) % 3


def _pam_candidate_rank(reference_codon: str, candidate_codon: str, pam_in_guide_orientation: str):
    """Rank silent PAM edits, rejecting both NGG and the common NAG residual."""
    pam = str(pam_in_guide_orientation).upper()
    if len(pam) != 3 or pam.endswith("GG") or pam[1:] == "AG":
        return None
    changes = [
        (old, new)
        for old, new in zip(str(reference_codon).upper(), str(candidate_codon).upper())
        if old != new
    ]
    if not changes:
        return None
    single_g_to_ct = len(changes) == 1 and changes[0][0] == "G" and changes[0][1] in "CT"
    return (int(single_g_to_ct), int(len(changes) == 1), -len(changes))


def _try_synonymous_pam_edit(
    record: SeqRecord,
    source_sequence: str,
    edited_sequence: str,
    guide: dict[str, Any],
    edit_start: int,
    edit_end: int,
    replacement_length: int,
    fallback_frame: int = 0,
    target_is_cds: bool = False,
) -> tuple[str, dict[str, Any] | None, str | None]:
    """Try one CDS-aware synonymous PAM mutation on the source target.

    This is deliberately a small PAM-only helper. It uses the annotated CDS
    orientation and codon frame, and never substitutes a missense base when no
    synonymous option is available. Callers with a precomputed synonymous PAM
    edit can include it in ``edit_dna`` and the helper then does nothing.
    """
    pam_interval = guide["pam_interval_0based"]
    pam_start, pam_end = int(pam_interval[0]), int(pam_interval[1])
    if pam_end < pam_start or guide["strand"] not in (1, -1):
        return edited_sequence, None, None
    pam_plus = source_sequence[pam_start:pam_end]
    if len(pam_plus) != 3:
        return edited_sequence, None, None
    pam_guide = guide["pam_sequence"]
    if not pam_guide.endswith("GG"):
        return edited_sequence, None, None
    # A replacement already covering the PAM is an explicit caller decision.
    if edit_start < pam_end and pam_start < edit_end:
        return edited_sequence, None, "PAM remains NGG inside explicit replacement; provide the synonymous PAM edit in edit_dna"

    feature = _cds_covering_interval(record, pam_start, pam_end)
    if feature is None and target_is_cds:
        # Legacy sequence-only callers may still declare a CDS. Reconstruct
        # the local coding frame from the cut and guide strand, while keeping
        # annotated records on the feature-aware path above.
        if guide["strand"] == 1:
            oriented = source_sequence
            oriented_cut = int(guide["cut_position_0based"])
            oriented_pam_start = pam_start
            oriented_pam_end = pam_end
            oriented_positions = [pam_end - 1, pam_end - 2]
            to_product = lambda pos: _map_hdr_boundary(pos, edit_start, edit_end, replacement_length)
            plus_positions = lambda codon_start, i: codon_start + i
            changed_plus = lambda codon: codon
        else:
            oriented = str(Seq(source_sequence).reverse_complement())
            oriented_cut = len(source_sequence) - int(guide["cut_position_0based"])
            oriented_pam_start = len(source_sequence) - pam_end
            oriented_pam_end = len(source_sequence) - pam_start
            oriented_positions = [oriented_pam_end - 1, oriented_pam_end - 2]

            def to_product(pos):
                genomic = len(source_sequence) - 1 - pos
                return _map_hdr_boundary(genomic, edit_start, edit_end, replacement_length)

            def plus_positions(codon_start, i):
                # ``changed_plus`` is written in increasing genomic order.
                return len(source_sequence) - 1 - (codon_start + 2 - i)

            def changed_plus(codon):
                return str(Seq(codon).reverse_complement())

        frame = int(fallback_frame) % 3
        best_candidate = None
        for oriented_pos in oriented_positions:
            codon_start = oriented_cut + frame + ((oriented_pos - oriented_cut - frame) // 3) * 3
            if codon_start < 0 or codon_start + 3 > len(oriented):
                continue
            codon = oriented[codon_start:codon_start + 3]
            try:
                synonyms = get_codon_synonyms(codon).analysis.get("synonymous_codons", [])
            except ValueError:
                continue
            base_in_codon = oriented_pos - codon_start
            for synonym in synonyms:
                if synonym[base_in_codon] == codon[base_in_codon]:
                    continue
                replacement_plus = changed_plus(synonym)
                trial = list(edited_sequence)
                valid = True
                for i, base in enumerate(replacement_plus):
                    genomic = plus_positions(codon_start, i)
                    product_pos = to_product(genomic)
                    if edit_start <= genomic < edit_end and trial[product_pos] != base:
                        valid = False
                        break
                    trial[product_pos] = base
                if not valid:
                    continue
                if guide["strand"] == 1:
                    new_pam = "".join(trial[to_product(pam_start + i)] for i in range(3))
                else:
                    new_pam_plus = "".join(trial[to_product(pam_start + i)] for i in range(3))
                    new_pam = str(Seq(new_pam_plus).reverse_complement())
                rank = _pam_candidate_rank(codon, synonym, new_pam)
                if rank is None:
                    continue
                candidate = (rank, "".join(trial), {
                    "location": "CDS",
                    "position_0based": oriented_pos,
                    "ref_codon": codon,
                    "alt_codon": synonym,
                    "amino_acid": get_codon_synonyms(codon).analysis["amino_acid"],
                    "synonymous": True,
                    "cds_strand": guide["strand"],
                    "cds_frame_offset": frame,
                    "cds_annotated": False,
                })
                if best_candidate is None or candidate[0] > best_candidate[0]:
                    best_candidate = candidate
        if best_candidate is not None:
            return best_candidate[1], best_candidate[2], None
        return edited_sequence, None, "PAM is declared CDS but no synonymous PAM mutation was found"

    if feature is None:
        # In non-coding sequence, changing the PAM's distal G is the old,
        # explicit behaviour. It is only used when no CDS annotation covers it.
        genomic_pos = pam_end - 1 if guide["strand"] == 1 else pam_start
        product_pos = _map_hdr_boundary(genomic_pos, edit_start, edit_end, replacement_length)
        old = edited_sequence[product_pos]
        new = "A" if old == "G" else "T" if old == "C" else "A"
        updated = edited_sequence[:product_pos] + new + edited_sequence[product_pos + 1:]
        return updated, {
            "location": "edited_target",
            "position_0based": product_pos,
            "ref": old,
            "alt": new,
            "synonymous": False,
            "cds_annotated": False,
        }, None

    feature_start, feature_end = int(feature.location.start), int(feature.location.end)
    cds = str(feature.extract(source_sequence)).upper()
    frame = _record_cds_frame(feature, fallback_frame)
    best_candidate = None
    # Try the PAM's two G bases in guide orientation, preferring the distal
    # base. Map genomic positions into CDS orientation for either strand.
    candidate_genomic = [pam_end - 1, pam_end - 2] if guide["strand"] == 1 else [pam_start, pam_start + 1]
    for genomic_pos in candidate_genomic:
        if not (feature_start <= genomic_pos < feature_end):
            continue
        cds_index = feature_end - 1 - genomic_pos if feature.location.strand == -1 else genomic_pos - feature_start
        codon_start = frame + ((cds_index - frame) // 3) * 3
        if codon_start < 0 or codon_start + 3 > len(cds):
            continue
        codon = cds[codon_start:codon_start + 3]
        try:
            synonyms = get_codon_synonyms(codon).analysis.get("synonymous_codons", [])
        except ValueError:
            continue
        base_in_codon = cds_index - codon_start
        for synonym in synonyms:
            if synonym[base_in_codon] == codon[base_in_codon]:
                continue
            changed_codon = synonym
            # Convert the entire coding codon back to the genomic plus strand.
            if feature.location.strand == -1:
                changed_plus = str(Seq(changed_codon).reverse_complement())
                positions = [feature_end - 1 - (codon_start + 2 - i) for i in range(3)]
            else:
                changed_plus = changed_codon
                positions = [feature_start + codon_start + i for i in range(3)]
            trial = list(edited_sequence)
            valid = True
            for pos, base in zip(positions, changed_plus):
                product_pos = _map_hdr_boundary(pos, edit_start, edit_end, replacement_length)
                if product_pos < 0 or product_pos >= len(trial):
                    valid = False
                    break
                # Explicit edits are never silently overwritten.
                if edit_start <= pos < edit_end and trial[product_pos] != base:
                    valid = False
                    break
                trial[product_pos] = base
            if not valid:
                continue
            if guide["strand"] == 1:
                new_pam = "".join(trial[_map_hdr_boundary(pam_start + i, edit_start, edit_end, replacement_length)] for i in range(3))
                silenced = not new_pam.endswith("GG")
            else:
                new_pam_plus = "".join(trial[_map_hdr_boundary(pam_start + i, edit_start, edit_end, replacement_length)] for i in range(3))
                silenced = not str(Seq(new_pam_plus).reverse_complement()).endswith("GG")
            candidate_pam = (
                new_pam
                if guide["strand"] == 1
                else str(Seq(new_pam_plus).reverse_complement())
            )
            rank = _pam_candidate_rank(codon, changed_codon, candidate_pam)
            if rank is None:
                continue
            candidate = (rank, "".join(trial), {
                "location": "CDS",
                "position_0based": genomic_pos,
                "ref_codon": codon,
                "alt_codon": changed_codon,
                "amino_acid": get_codon_synonyms(codon).analysis["amino_acid"],
                "synonymous": True,
                "cds_strand": feature.location.strand,
                "cds_frame_offset": frame,
            })
            if best_candidate is None or candidate[0] > best_candidate[0]:
                best_candidate = candidate
    if best_candidate is not None:
        return best_candidate[1], best_candidate[2], None
    return edited_sequence, None, "PAM is in an annotated CDS but no synonymous PAM mutation was found"


def design_hdr_donor(
    target_seq_or_file: str | pathlib.Path | SeqRecord,
    cut_position_0based: int,
    edit_dna: str,
    left_arm_length: int = 50,
    right_arm_length: int = 50,
    grna_seq: str = "",
    grna_strand: int = 1,
    edit_start_0based: int | None = None,
    edit_end_0based: int | None = None,
    donor_type: str | None = None,
    target_is_cds: bool = False,
    cds_frame_offset: int = 0,
    require_pam_disruption: bool = False,
) -> ToolResult:
    """Design one HDR donor from the unedited target record.

    Omitted edit boundaries retain the original insertion API and insert
    ``edit_dna`` at the cut. Supplying both boundaries performs one explicit
    half-open replacement. The source sequence is always guide-checked before
    editing, and the donor window is then taken from the computed edited target
    so a replacement payload cannot be inserted a second time.
    """
    from core.io.input_resolution import resolve_sequence_input

    rec, seq = resolve_sequence_input(target_seq_or_file)
    is_circular = rec.annotations.get("topology") == "circular"
    edit_info = _normalise_hdr_edit(
        seq,
        cut_position_0based,
        edit_dna,
        edit_start_0based,
        edit_end_0based,
    )
    edit_start = edit_info["edit_start_0based"]
    edit_end = edit_info["edit_end_0based"]
    edit_length = edit_info["edit_length"]
    edited_target = edit_info["edited_target_sequence"]

    guide = None
    if grna_seq:
        guide = _spcas9_guide_match(seq, grna_seq, grna_strand, cut_position_0based, is_circular)

    mutations_applied: list[dict[str, Any]] = []
    warnings: list[str] = []
    if guide:
        view = _edited_guide_view(guide, edited_target, edit_start, edit_end, edit_length, is_circular)
        pam_is_ngg = bool(view.get("edited_pam_sequence", "").endswith("GG"))
        if pam_is_ngg:
            edited_target, mutation, warning = _try_synonymous_pam_edit(
                rec,
                seq,
                edited_target,
                guide,
                edit_start,
                edit_end,
                edit_length,
                cds_frame_offset,
                target_is_cds,
            )
            if mutation:
                mutations_applied.append(mutation)
            if warning:
                warnings.append(warning)
            edit_info["edited_target_sequence"] = edited_target

    if require_pam_disruption:
        if not guide:
            raise ValueError("PAM_DISRUPTION_REQUIRED: provide the actual guide to check its PAM")
        final_view = _edited_guide_view(guide, edited_target, edit_start, edit_end, edit_length, is_circular)
        if final_view.get("edited_pam_sequence", "").endswith("GG"):
            raise ValueError("PAM_DISRUPTION_REQUIRED: the selected guide retains an NGG PAM after the edit; review coding context or select another guide instead of dropping the requirement")

    # The requested arm lengths are measured outside the edit interval. This
    # keeps replacement and insertion on one geometry: donor = left arm +
    # edited payload + right arm. The Cas cut can fall within the payload.
    if not is_circular:
        product_edit_start = _map_hdr_boundary(edit_start, edit_start, edit_end, edit_length)
        product_edit_end = (
            product_edit_start + edit_length
            if edit_start == edit_end
            else _map_hdr_boundary(edit_end, edit_start, edit_end, edit_length)
        )
        product_cut = edit_info["edited_cut_position_0based"]
        product_left_start = max(0, product_edit_start - left_arm_length)
        product_right_end = min(len(edited_target), product_edit_end + right_arm_length)
        arm_warnings: list[str] = []
        if product_edit_start - left_arm_length < 0:
            arm_warnings.append(
                f"Left homology arm truncated by 5' template boundary (requested {left_arm_length} nt, obtained {product_edit_start - product_left_start})"
            )
        if product_edit_end + right_arm_length > len(edited_target):
            arm_warnings.append(
                f"Right homology arm truncated by 3' template boundary (requested {right_arm_length} nt, obtained {product_right_end - product_edit_end})"
            )
        left_arm = edited_target[product_left_start:product_edit_start]
        payload = edited_target[product_edit_start:product_edit_end]
        right_arm = edited_target[product_edit_end:product_right_end]
        arms = {
            "cut_position_0based": product_cut,
            "left_homology_arm": left_arm,
            "left_arm_interval": [product_left_start, product_edit_start],
            "left_arm_length": len(left_arm),
            "right_homology_arm": right_arm,
            "right_arm_interval": [product_edit_end, product_right_end],
            "right_arm_length": len(right_arm),
            "circular": False,
            "warnings": arm_warnings,
        }
        donor_seq = left_arm + payload + right_arm
    else:
        arms = _extract_arms_from_sequence(
            edited_target,
            edit_info["edited_cut_position_0based"],
            left_arm_length,
            right_arm_length,
            is_circular,
        )
        donor_seq = arms["left_homology_arm"] + arms["right_homology_arm"]
    total_len = len(donor_seq)

    guide_view = None
    if guide:
        guide_view = {**guide}
        guide_view.update(_edited_guide_view(guide, edited_target, edit_start, edit_end, edit_length, is_circular))
        guide_view["pam"] = guide_view["pam_sequence"]
        guide_view["pam_reference"] = guide_view["pam_sequence"]
        guide_view["pam_edited"] = guide_view.get("edited_pam_sequence", guide_view["pam_sequence"])
        guide_view["pam_silenced"] = not guide_view.get("edited_pam_sequence", guide["pam_sequence"]).endswith("GG")

    requested_type = (str(donor_type).strip() if donor_type is not None else "").lower()
    if requested_type in {"dsdna", "double-stranded dna", "double-stranded donor"}:
        resolved_donor_type = "dsDNA"
    elif requested_type in {"plasmid", "double-stranded plasmid donor"}:
        resolved_donor_type = "double-stranded plasmid donor"
    elif requested_type in {"ssodn", "single-stranded dna", "single-stranded donor"}:
        resolved_donor_type = "ssODN"
    else:
        resolved_donor_type = "ssODN" if total_len <= 200 else "double-stranded plasmid donor"

    pam_silenced = bool(guide_view and guide_view.get("pam_silenced"))
    silencing_details = ""
    if guide_view:
        silencing_details = (
            f"PAM {guide_view['pam_sequence']} -> {guide_view.get('edited_pam_sequence', guide_view['pam_sequence'])}; "
            f"source target matched at cut {guide_view['cut_position_0based']}"
        )

    from Bio.SeqFeature import FeatureLocation, SeqFeature
    from core.models.construct_model import ConstructModel, feature_to_dict
    import copy
    if edit_info["edit_mode"] == "insert":
        edited_record = ConstructModel(rec).insert(edit_start, edit_info["edit_dna"]).to_record()
    elif len(edited_target) == len(rec):
        edited_record = copy.deepcopy(rec)
    else:
        edited_record = ConstructModel(rec).replace(edit_start, edit_end, edit_info["edit_dna"]).to_record()
    edited_record.seq = Seq(edited_target)
    for feature in edited_record.features:
        if feature.type == "CDS" and feature.location is not None:
            coding = feature.extract(edited_record.seq)
            phase = int(feature.qualifiers.get("codon_start", ["1"])[0]) - 1
            if (len(coding) - phase) % 3 == 0:
                table = int(feature.qualifiers.get("transl_table", ["1"])[0])
                feature.qualifiers["translation"] = [str(coding[phase:].translate(table=table)).rstrip("*")]
            else:
                feature.qualifiers.pop("translation", None)
    donor_features = []
    left_length = arms["left_arm_length"]
    for label, a, b in (("left homology arm", 0, left_length),
                        ("edit payload", left_length, left_length + edit_length),
                        ("right homology arm", left_length + edit_length, total_len)):
        if b > a:
            donor_features.append(feature_to_dict(SeqFeature(FeatureLocation(a, b, strand=1),
                type="misc_feature", qualifiers={"label": [label]}), total_len))
    result: dict[str, Any] = {
        "donor_sequence": donor_seq,
        "total_length": total_len,
        "donor_type": resolved_donor_type,
        "left_homology_arm": arms["left_homology_arm"],
        "left_arm_length": arms["left_arm_length"],
        "right_homology_arm": arms["right_homology_arm"],
        "right_arm_length": arms["right_arm_length"],
        "edit_payload": edit_info["edit_dna"],
        "edit_length": edit_info["edit_length"],
        "replacement_length": edit_info["replacement_length"],
        "edit_mode": edit_info["edit_mode"],
        "edit_start_0based": edit_start,
        "edit_end_0based": edit_end,
        "replacement_interval_0based": [edit_start, edit_end],
        "original_target_sequence": seq,
        "edited_target_sequence": edited_target,
        "edited_target_record": {"sequence": edited_target,
                                 "topology": rec.annotations.get("topology", "linear"),
                                 "features": [feature_to_dict(f, len(edited_record)) for f in edited_record.features]},
        "features": donor_features,
        "topology": "linear",
        "cut_position_0based": edit_info["cut_position_0based"],
        "edited_cut_position_0based": edit_info["edited_cut_position_0based"],
        "donor_edit_interval_0based": [
            arms["left_arm_length"],
            arms["left_arm_length"] + edit_length,
        ],
        "donor_cut_position_0based": edit_info["edited_cut_position_0based"] - arms["left_arm_interval"][0],
        "left_arm_interval": arms["left_arm_interval"],
        "right_arm_interval": arms["right_arm_interval"],
        "pam_silenced_in_donor": pam_silenced,
        "guide_match": bool(guide),
        "silencing_details": silencing_details,
        "mutations_applied": mutations_applied,
        "guide": guide_view,
        "warnings": list(arms["warnings"]) + warnings,
    }

    if resolved_donor_type == "dsDNA" and total_len <= 200:
        top = donor_seq
        bottom = str(Seq(top).reverse_complement())
        result["top_oligo"] = top
        result["bottom_oligo"] = bottom
        result["annealing"] = {
            "top_oligo": top,
            "bottom_oligo": bottom,
            "top_length": len(top),
            "bottom_length": len(bottom),
            "instructions": [
                "Order complete top and bottom donor oligos in the displayed 5-prime-to-3-prime orientations.",
                "Mix equimolar oligos, heat-denature, then cool slowly to anneal the full duplex.",
                "Use the annealed dsDNA donor with the validated Cas9 guide reaction.",
            ],
        }
        result["protocol_mode"] = "short_dsDNA_annealed"
    elif resolved_donor_type == "ssODN":
        result["protocol_mode"] = "ssODN"
    else:
        result["protocol_mode"] = "plasmid_donor"

    from core.io.input_resolution import resolve_sequence_record
    donor_record = resolve_sequence_record({'sequence':donor_seq,'features':donor_features,'topology':'linear','id':'donor'})
    donor = derived_molecule(donor_record,[as_molecule(rec)],operation='design_hdr_donor',
                strandedness='single' if resolved_donor_type=='ssODN' else 'double',
                mappings=[{'edit_start0':edit_start,'edit_end0':edit_end,'arm_intervals':[arms['left_arm_interval'],arms['right_arm_interval']]}])
    edited = derived_molecule(edited_record,[as_molecule(rec)],operation='edited_locus_model')
    result.pop('donor_sequence',None)
    result.pop('features',None)
    result['edited_target_record'] = edited
    return ToolResult(products=[donor],analysis=result)


def extract_homology_arms(
    target_seq_or_file: str | pathlib.Path | SeqRecord,
    cut_position_0based: int,
    left_arm_length: int = 50,
    right_arm_length: int = 50,
    circular: bool | None = None,
    edit_dna: str | None = None,
    edit_start_0based: int | None = None,
    edit_end_0based: int | None = None,
) -> ToolResult:
    """Extract homology arms from an original or explicitly edited target.

    With no edit interval this preserves the original cut-centered insertion
    behaviour. With both edit boundaries it applies ``edit_dna`` once and
    returns arms outside the mapped replacement interval. This shared path
    prevents recipe and atomic HDR calculations from diverging.
    """
    from core.io.input_resolution import resolve_sequence_input

    rec = as_molecule(target_seq_or_file,default_topology="linear")
    seq = str(rec.seq)
    topo = rec.annotations.get("topology")
    is_circular = circular if circular is not None else topo == "circular"
    if (edit_start_0based is None) != (edit_end_0based is None):
        raise ValueError("edit_start_0based and edit_end_0based must be provided together")
    if edit_start_0based is None:
        result = _extract_arms_from_sequence(
            seq,
            cut_position_0based,
            left_arm_length,
            right_arm_length,
            bool(is_circular),
        )
        result.update({"edit_mode": "insert", "edited_target_sequence": seq})
        return _arm_products(rec,result)

    info = _normalise_hdr_edit(
        seq,
        cut_position_0based,
        "" if edit_dna is None else edit_dna,
        edit_start_0based,
        edit_end_0based,
    )
    if not is_circular:
        product_edit_start = _map_hdr_boundary(
            info["edit_start_0based"],
            info["edit_start_0based"],
            info["edit_end_0based"],
            info["edit_length"],
        )
        product_edit_end = (
            product_edit_start + info["edit_length"]
            if info["edit_start_0based"] == info["edit_end_0based"]
            else _map_hdr_boundary(
                info["edit_end_0based"],
                info["edit_start_0based"],
                info["edit_end_0based"],
                info["edit_length"],
            )
        )
        product = info["edited_target_sequence"]
        left_start = max(0, product_edit_start - left_arm_length)
        right_end = min(len(product), product_edit_end + right_arm_length)
        warnings = []
        if product_edit_start - left_arm_length < 0:
            warnings.append(
                f"Left homology arm truncated by 5' template boundary (requested {left_arm_length} nt, obtained {product_edit_start - left_start})"
            )
        if product_edit_end + right_arm_length > len(product):
            warnings.append(
                f"Right homology arm truncated by 3' template boundary (requested {right_arm_length} nt, obtained {right_end - product_edit_end})"
            )
        result = {
            "cut_position_0based": info["edited_cut_position_0based"],
            "left_homology_arm": product[left_start:product_edit_start],
            "left_arm_interval": [left_start, product_edit_start],
            "left_arm_length": product_edit_start - left_start,
            "right_homology_arm": product[product_edit_end:right_end],
            "right_arm_interval": [product_edit_end, right_end],
            "right_arm_length": right_end - product_edit_end,
            "circular": False,
            "warnings": warnings,
        }
        result.update({
            "edit_mode": info["edit_mode"],
            "edit_dna": info["edit_dna"],
            "edit_start_0based": info["edit_start_0based"],
            "edit_end_0based": info["edit_end_0based"],
            "edited_target_sequence": product,
            "edited_cut_position_0based": info["edited_cut_position_0based"],
        })
        return _arm_products(rec,result)
    result = _extract_arms_from_sequence(
        info["edited_target_sequence"],
        info["edited_cut_position_0based"],
        left_arm_length,
        right_arm_length,
        bool(is_circular),
    )
    result.update({
        "edit_mode": info["edit_mode"],
        "edit_start_0based": info["edit_start_0based"],
        "edit_end_0based": info["edit_end_0based"],
        "edited_target_sequence": info["edited_target_sequence"],
        "edited_cut_position_0based": info["edited_cut_position_0based"],
    })
    return _arm_products(rec,result)


def _arm_products(source, data):
    from core.models.construct_model import ConstructModel
    from core.tools.sequence_ops import slice_record_interval
    record = source
    if data.get('edit_mode') == 'replace' or 'edit_start_0based' in data:
        a,b = data['edit_start_0based'],data['edit_end_0based']
        model = ConstructModel(source)
        model.replace(a,b,data.get('edit_dna',''))
        record = model.to_record()
    products = []
    for side in ('left','right'):
        a,b = data[side+'_arm_interval']
        length = data[side+'_arm_length']
        clipped = slice_record_interval(record,a,length,circular=data.get('circular',False))
        products.append(derived_molecule(clipped,[source],operation='extract_homology_arms',
                    strandedness=source.strandedness,mappings=[{'start0':a,'length':length,'arm':side}]))
    return ToolResult(products=products,analysis=data)
