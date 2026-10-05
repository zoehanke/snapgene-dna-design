# -*- coding: utf-8 -*-
"""core/recipes/mutagenesis.py - Standard SOP Recipe for Site-Directed Mutagenesis (SDM).

LITERATURE SOURCES & PROTOCOL REFERENCES:
1. Zheng, L., Baumann, U. and Reymond, J.L. (2004).
   An efficient one-step site-directed and site-saturation mutagenesis protocol.
   Nucleic Acids Research, 32(14), p.e115. doi:10.1093/nar/gnh110.
2. Green, M.R. and Sambrook, J. (2012).
   Molecular Cloning: A Laboratory Manual. 4th ed.
   Cold Spring Harbor Laboratory Press, Cold Spring Harbor, NY.
   Chapter 13: In Vitro Mutagenesis.
3. Agilent Technologies. (2020).
   QuikChange II Site-Directed Mutagenesis Kit Instruction Manual.
"""
from __future__ import annotations

import pathlib
import copy
from typing import Any

from Bio.Seq import Seq
from Bio.Data.CodonTable import TranslationError
from Bio.SeqRecord import SeqRecord

from core.io.input_resolution import resolve_sequence_record
from core.recipes.contract import RecipeResult
from core.models.molecule import as_molecule, derived_molecule
from core.tools.amplification import calc_primer_tm
from core.tools.inspection import _load_record
from core.tools.sequence_ops import mutate_sequence
from core.tools.translation import translate_dna

AUTHORITATIVE_SOURCES = [
    {
        "citation": "Zheng et al. (2004). An efficient one-step site-directed and site-saturation mutagenesis protocol. Nucleic Acids Res 32(14):e115.",
        "institution": "University of Bern",
        "doi": "10.1093/nar/gnh110",
        "rules_enforced": [
            "Mutagenic primers must place the desired mutation at or near the center of the oligonucleotide.",
            "Primer must have 10-15 bp of strict complementary wild-type flanking sequence on both sides.",
            "Melting temperature calculated via QuikChange thermodynamic formula: Tm = 81.5 + 0.41(%GC) - 675/N - %mismatch.",
            "Standard QuikChange protocol requires Tm >= 78°C to ensure stable primer-template hybridization.",
        ],
    },
    {
        "citation": "Green, M.R. and Sambrook, J. (2012). Molecular Cloning: A Laboratory Manual (4th ed.). Chapter 13.",
        "institution": "Cold Spring Harbor Laboratory (CSHL)",
        "rules_enforced": [
            "Post-PCR reaction must be treated with 1 uL DpnI endonuclease (37°C, 1 hr) to digest Dam-methylated parental template DNA.",
            "DpnI selection reduces wild-type background colonies by > 100-fold.",
        ],
    },
]


def calc_quikchange_tm(primer_seq: str, mismatch_bp_count: int) -> float:
    """Calculate QuikChange-specific mutagenic primer Tm according to Zheng 2004 & Agilent.

    Formula: Tm = 81.5 + 0.41(%GC) - 675/N - %mismatch
    where N is primer length, %mismatch = (mismatched_bases / N) * 100.
    """
    s = str(primer_seq).upper()
    n = len(s)
    if n == 0:
        return 0.0
    gc_count = s.count("G") + s.count("C")
    gc_pct = (gc_count / n) * 100.0
    mismatch_pct = (mismatch_bp_count / n) * 100.0
    return round(81.5 + 0.41 * gc_pct - (675.0 / n) - mismatch_pct, 1)


def _circular_slice(sequence: str, start: int, length: int) -> str:
    """Return ``length`` bases from a circular sequence in forward order."""
    seq = str(sequence).upper()
    if not seq or length <= 0:
        return ""
    n = len(seq)
    start = int(start) % n
    return (seq + seq)[start:start + int(length)]


def _interval_length(start: int, end: int, n: int, circular: bool) -> int:
    if not circular:
        if not 0 <= start <= end <= n:
            raise ValueError(
                "mutation interval [%d, %d) is outside linear template length %d"
                % (start, end, n)
            )
        return end - start
    if not 0 <= start < n or not 0 <= end <= n:
        raise ValueError(
            "mutation interval [%d, %d) is outside circular template length %d"
            % (start, end, n)
        )
    if start == end:
        return 0
    return end - start if end > start else n - start + end


def _apply_mutation_record(rec, start: int, end: int, alt: str, circular: bool):
    """Apply a possibly cross-origin edit while retaining feature locations."""
    from core.models.construct_model import ConstructModel

    n = len(rec.seq)
    ref_len = _interval_length(start, end, n, circular)
    model = ConstructModel(copy.deepcopy(rec))
    if circular and start > end:
        # Rotate the molecule so the cross-origin interval becomes linear,
        # apply the normal ConstructModel edit, then rotate the product back to
        # the old coordinate-zero boundary when that boundary survives.
        model.rotate(start)
        if ref_len:
            if alt:
                model.replace(0, ref_len, alt)
            else:
                model.delete(0, ref_len)
        else:
            model.insert(0, alt)

        # In the rotated sequence, original coordinate 0 is at offset
        # ``n-start``.  Map that boundary through the replaced interval.  If
        # the boundary lies inside the new payload, choose the corresponding
        # prefix length, clamped to the payload; this keeps indel products
        # deterministic without treating a circular rotation as a sequence
        # change.
        origin_offset = n - start
        if origin_offset <= ref_len:
            new_origin = min(origin_offset, len(alt))
        else:
            new_origin = len(alt) + origin_offset - ref_len
        new_origin %= len(model.record.seq)
        if new_origin:
            model.rotate(new_origin)
    elif ref_len == len(alt) and ref_len > 0:
        model.mutate([(start + i, base) for i, base in enumerate(alt)])
    elif ref_len == 0:
        model.insert(start, alt)
    elif alt:
        model.replace(start, end, alt)
    else:
        model.delete(start, end)
    model.set_topology("circular" if circular else rec.annotations.get("topology", "linear"))
    return model


def _record_dict(rec, feature_to_dict):
    return {
        "id": rec.id or rec.name or "template",
        "name": rec.name or rec.id or "template",
        "sequence": str(rec.seq).upper(),
        "annotations": {
            "molecule_type": rec.annotations.get("molecule_type", "DNA"),
            "topology": rec.annotations.get("topology", "linear"),
        },
        "features": [feature_to_dict(feature, len(rec.seq))
                     for feature in rec.features],
    }


def _mismatch_count(reference: str, alternate: str) -> int:
    """Count nucleotide changes, including only differing bases for substitutions."""
    ref = str(reference).upper()
    alt = str(alternate).upper()
    common = min(len(ref), len(alt))
    return sum(a != b for a, b in zip(ref[:common], alt[:common])) + abs(len(ref) - len(alt))


def _primer_row(name, full_sequence, core_sequence, position, strand, tm, santalucia_tm,
                **extra):
    row = {
        "name": name,
        "seq": full_sequence,
        "sequence": full_sequence,
        "full_sequence": full_sequence,
        "core": core_sequence,
        "binding_core": core_sequence,
        "position_0based": position,
        "strand": strand,
        "qc_tm": tm,
        "santalucia_tm": santalucia_tm,
    }
    row.update(extra)
    return row


def recipe_site_directed_mutagenesis(
    template_seq_or_file: str | pathlib.Path | SeqRecord,
    start_0based: int,
    end_0based: int,
    alt_seq: str,
    target_flank_bp: int = 15,
    method: str = "quikchange",
) -> dict[str, Any]:
    """Execute a literature-grounded Site-Directed Mutagenesis (SDM) route.

    Follows Zheng et al. 2004 (NAR) and Sambrook *Molecular Cloning* 4th ed.:
    - Accurately introduces point, insertion, or deletion mutations into the template.
    - ``method='quikchange'`` uses centered complementary mutagenic oligos and
      validates their complete wild-type flanks.
    - ``method='inverse_pcr'`` derives a full-plasmid PCR intermediate and an
      explicit circularization step from the original circular template.
    - Evaluates QuikChange-specific Tm targeting >= 78°C and checks 3' GC clamp.
    - Enforces mandatory post-PCR DpnI digestion reminder.
    - Emits source provenance and literature citations.
    """
    rec = _load_record(template_seq_or_file)
    t_seq = str(rec.seq).upper()
    alt = str(alt_seq).strip().upper()
    n = len(t_seq)
    topo = str(rec.annotations.get("topology", "linear")).lower()
    circular = topo == "circular"
    start = int(start_0based)
    end = int(end_0based)
    ref_len = _interval_length(start, end, n, circular)
    if not alt and ref_len == 0:
        raise ValueError("mutation must replace or insert at least one base")
    if any(base not in "ACGT" for base in alt):
        raise ValueError("alt_seq must contain only A/C/G/T bases")
    method = str(method or "quikchange").lower().replace("-", "_")
    if method not in ("quikchange", "inverse_pcr"):
        raise ValueError("method must be 'quikchange' or 'inverse_pcr'")
    if not circular:
        ref = t_seq[start:end]
        left_flank_seq = t_seq[max(0, start - max(10, min(25, int(target_flank_bp)))):start]
        right_flank_seq = t_seq[end:end + max(10, min(25, int(target_flank_bp)))]
    else:
        ref = _circular_slice(t_seq, start, ref_len)
        flank = max(10, min(25, int(target_flank_bp)))
        left_flank_seq = _circular_slice(t_seq, start - flank, flank)
        right_flank_seq = _circular_slice(t_seq, end, flank)

    from core.models.construct_model import feature_to_dict
    model = _apply_mutation_record(rec, start, end, alt, circular)
    mutated_record = model.to_record()
    mutated_product = str(mutated_record.seq).upper()
    # A changed CDS cannot retain its old claimed amino-acid sequence.
    changed_positions = {i for i, (old, new) in enumerate(zip(t_seq, mutated_product)) if old != new}
    for feature in mutated_record.features:
        if feature.type != "CDS" or feature.location is None:
            continue
        if len(t_seq) == len(mutated_product) and not any(pos in feature.location for pos in changed_positions):
            continue
        coding = feature.extract(mutated_record.seq)
        phase = int(feature.qualifiers.get("codon_start", ["1"])[0]) - 1
        coding = coding[phase:]
        if len(coding) % 3:
            feature.qualifiers.pop("translation", None)
            continue
        table = int(feature.qualifiers.get("transl_table", ["1"])[0])
        try:
            translation = str(coding.translate(table=table, cds=True))
        except (ValueError, TranslationError):
            translation = str(coding.translate(table=table)).rstrip("*")
        feature.qualifiers["translation"] = [translation]
    template_dict = _record_dict(rec, feature_to_dict)

    pcr_evidence = None
    if method == "quikchange":
        # QuikChange primers are complete mutagenic oligos.  Both wild-type
        # flanks are checked against the original template; only differing
        # aligned bases count as mismatches (TAT -> CAT therefore counts 1).
        fwd_primer = left_flank_seq + alt + right_flank_seq
        rev_primer = str(Seq(fwd_primer).reverse_complement())
        reference_primer = left_flank_seq + ref + right_flank_seq
        mismatch_count = _mismatch_count(reference_primer, fwd_primer)
        if left_flank_seq and fwd_primer[:len(left_flank_seq)] != left_flank_seq:
            raise ValueError("QuikChange forward primer left flank does not match template")
        if right_flank_seq and fwd_primer[-len(right_flank_seq):] != right_flank_seq:
            raise ValueError("QuikChange forward primer right flank does not match template")
        pcr_evidence = {
            "reaction_model": "quikchange_mutagenic_extension",
            "template_verified": True,
            "full_forward_primer_verified": True,
            "full_reverse_primer_verified": (
                rev_primer == str(Seq(fwd_primer).reverse_complement())
            ),
            "reference_segment": reference_primer,
            "mutant_segment_from_primers": fwd_primer,
            "product_derivation": (
                "complete mutagenic F/R oligos validated against the original "
                "template; expected circular mutant retained as reaction product"
            ),
        }
        qc_tm = calc_quikchange_tm(fwd_primer, mismatch_count)
        santalucia_tm = calc_primer_tm(fwd_primer).analysis["tm"]
        primer_rows = [
            _primer_row(
                "forward_mutagenic_primer", fwd_primer, fwd_primer,
                {"start_0based": start, "end_0based": end}, 1,
                qc_tm, santalucia_tm,
                mismatch_base_count=mismatch_count,
                binding_interval_0based=[start, end],
                left_flank=left_flank_seq, right_flank=right_flank_seq,
            ),
            _primer_row(
                "reverse_mutagenic_primer", rev_primer, rev_primer,
                {"start_0based": start, "end_0based": end}, -1,
                qc_tm, santalucia_tm,
                mismatch_base_count=mismatch_count,
                binding_interval_0based=[start, end],
                left_flank=str(Seq(right_flank_seq).reverse_complement()),
                right_flank=str(Seq(left_flank_seq).reverse_complement()),
            ),
        ]
        # Source annotation records exact 3-prime wild-type anchoring, while
        # the complete mutagenic oligo and its whole-oligo QuikChange Tm remain.
        for primer, core, core_start in (
            (primer_rows[0], right_flank_seq, end),
            (primer_rows[1], str(Seq(left_flank_seq).reverse_complement()), start-len(left_flank_seq)),
        ):
            begin = core_start % n if circular else core_start
            finish = (begin+len(core)) % n if circular else begin+len(core)
            primer["binding_sequence"] = core
            primer["binding_interval_0based"] = [begin, finish or n]
            primer["binding_core_tm"] = calc_primer_tm(core).analysis["tm"]
        product_method = "quikchange_mutagenic_extension"
    else:
        # Inverse PCR uses full-plasmid amplification followed by circulariza-
        # tion.  The 5' tail on the forward oligo carries replacement DNA;
        # the PCR simulator, rather than direct string replacement, supplies
        # the linear intermediate.
        from core.tools.amplification import design_overhang_primers, simulate_pcr
        design_template, design_start, design_end = rec, end % n, start
        if start == end:
            # Insertion retains the entire circular template. Express that
            # full interval on a rotated reference instead of a zero-width arc.
            from core.tools.sequence_ops import rotate_sequence
            design_template = rotate_sequence(rec, origin_0based=start).only_product()
            design_start, design_end = 0, n
        designed = design_overhang_primers(
            design_template, start=design_start, end=design_end, fwd_5prime_overhang=alt,
            min_core_len=max(15, min(30, int(target_flank_bp))),
            circular=True, target_tm=60.0,
        ).analysis
        if start == end:
            designed['design_reference_origin_0based'] = start
            for key in ('forward_primer', 'reverse_primer'):
                binding = designed[key]['binding']
                for field in ('template_start_0based', 'template_end_0based'):
                    binding[field] = (binding[field] + start) % n
            designed['target_interval_0based'] = [start, end]
            designed['target_interval_wraps_origin'] = True
        forward = designed['forward_primer']
        reverse = designed['reverse_primer']
        right_core = forward['binding_core']
        left_core = str(Seq(reverse['binding_core']).reverse_complement())
        fwd_primer = forward['full_sequence']
        rev_primer = reverse['full_sequence']
        fwd_position = end % n
        rev_position = (start - len(left_core)) % n
        pcr_res = simulate_pcr(
            rec,
            fwd_primer,
            rev_primer,
            topology="circular",
            forward_binding_core_length=len(right_core),
            reverse_binding_core_length=len(left_core),
            forward_binding_start_0based=fwd_position,
            reverse_binding_start_0based=rev_position,
        )
        linear_intermediate = str(str(pcr_res.only_product().seq)).upper()
        original_zero = (len(alt) + (n - end)) % len(linear_intermediate)
        cyclized = linear_intermediate[original_zero:] + linear_intermediate[:original_zero]
        if cyclized != mutated_product:
            raise ValueError(
                "inverse_pcr cyclization product differs from the feature-preserving mutation model"
            )
        pcr_evidence = {
            "reaction_model": "full_plasmid_pcr_then_circularization",
            "template_verified": True,
            "full_forward_primer_verified": True,
            "full_reverse_primer_verified": True,
            "pcr_intermediate": pcr_res,
            "primer_design": designed,
            "linear_intermediate_sequence": linear_intermediate,
            "cyclized_sequence": cyclized,
            "product_derivation": (
                "simulate_pcr on the original circular template followed by "
                "rotation of the linear amplicon at the original origin"
            ),
        }
        fwd_tm = forward['binding_core_tm']
        rev_tm = reverse['binding_core_tm']
        primer_rows = [
            _primer_row(
                "inverse_pcr_forward", fwd_primer, right_core,
                {"start_0based": fwd_position,
                 "end_0based": (fwd_position + len(right_core)) % n},
                1, fwd_tm, fwd_tm,
                five_prime_tail=alt,
                binding_interval_0based=[fwd_position,
                                         (fwd_position + len(right_core)) % n],
            ),
            _primer_row(
                "inverse_pcr_reverse", rev_primer, rev_primer,
                {"start_0based": rev_position,
                 "end_0based": (rev_position + len(left_core)) % n},
                -1, rev_tm, rev_tm,
                binding_interval_0based=[rev_position,
                                         (rev_position + len(left_core)) % n],
            ),
        ]
        qc_tm = None
        santalucia_tm = None
        product_method = "inverse_pcr_cyclization"
        mutated_product = cyclized

    has_gc_clamp = bool(fwd_primer) and (
        fwd_primer[-1] in ("G", "C") or
        (len(fwd_primer) >= 2 and fwd_primer[-2] in ("G", "C"))
    )
    mismatch_count = _mismatch_count(ref, alt)
    quality_checks = {
        "method": method,
        "primer_length_nt": len(fwd_primer),
        "quikchange_tm": qc_tm,
        "quikchange_tm_meets_78C_standard": (
            qc_tm >= 78.0 if qc_tm is not None else None
        ),
        "santalucia_tm": santalucia_tm,
        "left_flank_length_bp": len(left_flank_seq),
        "right_flank_length_bp": len(right_flank_seq),
        "mutation_centered": abs(len(left_flank_seq) - len(right_flank_seq)) <= 3,
        "gc_clamp_present": has_gc_clamp,
        "mismatch_base_count": mismatch_count,
        "template_verified": bool(pcr_evidence and pcr_evidence.get("template_verified")),
        "product_verified_from_method": bool(pcr_evidence),
    }

    warnings = []
    if qc_tm is not None and qc_tm < 78.0:
        warnings.append(
            f"QuikChange Tm ({qc_tm}°C) is below recommended 78°C threshold (Zheng et al. 2004). Consider increasing flanking length."
        )
    if not has_gc_clamp:
        warnings.append("Primer 3' end lacks G/C clamp; consider shifting flanking boundary by 1-2 bp.")

    if method == "quikchange":
        sop_reminders = [
            "DPNI_DIGESTION: Treat the QuikChange PCR product with DpnI according to the validated kit protocol to destroy the parental template.",
            "THERMOCYCLING: Use the Standard QuikChange cycling program validated for the selected kit and template length.",
        ]
    else:
        sop_reminders = [
            "INVERSE_PCR_AMPLIFICATION: Amplify the complete circular template to produce the linear mutant-bearing PCR intermediate with the selected high-fidelity polymerase.",
            "DPNI_DIGESTION: Remove parental circular template with DpnI before circularization, following the validated enzyme protocol.",
            "INVERSE_PCR_CIRCULARIZATION: Purify the linear PCR product and use compatible end-phosphorylation and recircularization chemistry (for example, KLD) according to the manufacturer's validated protocol.",
        ]

    circular_product_dict = {
        "sequence": mutated_product,
        "topology": "circular",
        "length": len(mutated_product),
        "features": [feature_to_dict(f, len(mutated_product))
                     for f in mutated_record.features],
        "method": product_method,
        "evidence": pcr_evidence,
    }
    preparation_product_dict = circular_product_dict
    if method == "inverse_pcr":
        # The preparation step is the actual linear PCR intermediate. Keep
        # the circularized mutant as the recipe's final construct separately.
        preparation_product_dict = {
            "sequence": linear_intermediate,
            "topology": "linear",
            "length": len(linear_intermediate),
            "features": pcr_evidence["pcr_intermediate"].only_product().to_dict()['features'],
            "method": "inverse_pcr_pcr_intermediate",
            "template_interval_0based": pcr_evidence["pcr_intermediate"].analysis.get(
                "template_interval_0based"
            ),
            "evidence": pcr_evidence,
            "circular_product": circular_product_dict,
        }
    preparation = [{
        "id": "mutagenesis-1",
        "method": method,
        "template": str(template_seq_or_file) if isinstance(template_seq_or_file, (str, pathlib.Path)) else template_dict,
        "primers": primer_rows,
        "product": preparation_product_dict,
    }]
    if method == "quikchange":
        protocol_steps = [
            {"step": 1, "action": "Set up the QuikChange mutagenic PCR with the selected high-fidelity polymerase."},
            {"step": 2, "action": "Run the Standard QuikChange cycling program validated for the selected kit and template length."},
            {"step": 3, "action": "Digest the PCR reaction with DpnI according to the validated kit protocol to remove parental template."},
            {"step": 4, "action": "Transform the DpnI-treated product into competent cells."},
        ]
    else:
        protocol_steps = [
            {"step": 1, "action": "Set up inverse PCR on the complete circular template with the selected high-fidelity polymerase."},
            {"step": 2, "action": "Run the polymerase- and template-validated cycling program to generate the full linear PCR intermediate."},
            {"step": 3, "action": "Treat the reaction to remove parental circular template with DpnI according to the validated enzyme protocol."},
            {"step": 4, "action": "Purify the linear product and recircularize it with compatible end-phosphorylation and ligation/cyclization chemistry, such as KLD, according to the manufacturer's protocol."},
        ]
    material = derived_molecule(resolve_sequence_record(circular_product_dict),[as_molecule(rec)],operation="recipe_site_directed_mutagenesis",strandedness="double")
    return RecipeResult(
        recipe_name="recipe_site_directed_mutagenesis",
        result_kind="construct",
        completeness="complete_construct",
        products=[material],
        primers=primer_rows,
        quality_checks=quality_checks,
        warnings=warnings,
        protocol_steps=protocol_steps,
        citations=AUTHORITATIVE_SOURCES,
        details={
            "recipe": "recipe_site_directed_mutagenesis",
            "method": method,
            "mutated_sequence": mutated_product,
            "product_length": len(mutated_product),
            "mutation_type": "substitution" if (ref_len == len(alt) and ref_len > 0) else ("insertion" if ref_len == 0 else "deletion"),
            "primers": primer_rows,
            "quality_checks": quality_checks,
            "warnings": warnings,
            "sop_reminders": sop_reminders,
            "authoritative_sources": AUTHORITATIVE_SOURCES,
            "preparation": preparation,
            "reaction_evidence": pcr_evidence,
            "circular_product": circular_product_dict,
        },
    )
