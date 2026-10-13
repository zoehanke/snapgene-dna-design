# -*- coding: utf-8 -*-
"""core/recipes/verification.py - Standard SOP Recipe for Cloning QC, Colony PCR & Sanger Verification.

LITERATURE SOURCES & PROTOCOL REFERENCES:
1. Green, M.R. and Sambrook, J. (2012).
   Molecular Cloning: A Laboratory Manual. 4th ed.
   Cold Spring Harbor Laboratory Press, Cold Spring Harbor, NY.
   Chapter 1 (Plasmids and Their Useful Features) & Chapter 8 (PCR Analysis of Recombinant Clones).
2. Sanger, F., Nicklen, S. and Coulson, A.R. (1977).
   DNA sequencing with chain-terminating inhibitors.
   Proceedings of the National Academy of Sciences (PNAS), 74(12), pp.5463-5467.
   doi:10.1073/pnas.74.12.5463.
"""
from __future__ import annotations

import pathlib
import heapq
from typing import Any

from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from core.recipes.contract import RecipeResult
from core.errors import PlanningError
from core.models.molecule import as_molecule, derived_molecule
from core.tools.amplification import calc_primer_tm, check_primer_dimers, simulate_pcr, _find_primer_binding
from core.models.construct_model import feature_to_dict
from core.tools.inspection import _load_record
from core.tools.restriction import digest_sequence
from core.tools.primer3_backend import check_complete_oligo_pair

AUTHORITATIVE_SOURCES = [
    {
        "citation": "Green, M.R. and Sambrook, J. (2012). Molecular Cloning: A Laboratory Manual (4th ed.). Chapters 1 & 8.",
        "institution": "Cold Spring Harbor Laboratory (CSHL)",
        "rules_enforced": [
            "Place screening primers across the vector-insert junction; parental-template discrimination requires a separate control.",
            "Recommended colony PCR amplicon size is 300-800 bp for rapid high-throughput agarose gel resolution.",
            "Diagnostic restriction digest band sizes must differ by at least 15-20% to be visually distinguishable on standard 1% agarose gels.",
        ],
    },
    {
        "citation": "Sanger, F. et al. (1977). DNA sequencing with chain-terminating inhibitors. PNAS 74(12):5463-5467.",
        "institution": "MRC Laboratory of Molecular Biology, Cambridge",
        "doi": "10.1073/pnas.74.12.5463",
        "rules_enforced": [
            "Sanger sequencing primers must be placed 50-100 bp upstream of the cloning junction or mutation site.",
            "Avoids the standard 30-50 bp dye-blob / noisy chromatogram blind zone adjacent to the primer.",
        ],
    },
]


def _verification_candidates(
    seq: str,
    target_pos: int,
    strand: int = 1,
    target_tm: float = 60.0,
    search_window: int = 35,
    min_len: int = 18,
    max_len: int = 30,
    circular: bool = True,
    allowed_interval: tuple[int, int] | None = None,
    junction: int | None = None,
) -> dict[str, Any] | None:
    """Thermodynamically search and optimize a verification primer around target_pos."""
    n = len(seq)
    if n < min_len:
        return []

    if circular:
        offsets = range(-search_window, search_window + 1)
        starts = [target_pos + off for off in offsets]
    else:
        s_min = max(0, target_pos - search_window)
        s_max = min(n - min_len, target_pos + search_window)
        starts = list(range(s_min, s_max + 1))

    candidates = []
    for s in starts:
        for l in range(min_len, max_len + 1):
            if allowed_interval and not (allowed_interval[0] <= s and s + l <= allowed_interval[1]):
                continue
            distance = junction - (s + l) if strand == 1 and junction is not None else s - junction if junction is not None else None
            if distance is not None and not 50 <= distance <= 100:
                continue
            if not circular and (s + l > n):
                break
            if circular:
                pos = s % n
                chunk = (seq + seq)[pos:pos + l]
            else:
                chunk = seq[s : s + l]

            p = chunk if strand == 1 else str(Seq(chunk).reverse_complement())
            if len(_find_primer_binding(seq, p, circular=circular, binding_core_length=l)) != 1:
                continue
            info = calc_primer_tm(p).analysis
            tm = info["tm"]
            gc = info["gc_percent"]
            if not 52 <= tm <= 72:
                continue

            # Thermodynamic objective penalties
            diff = abs(tm - target_tm)
            gc_pen = abs(gc - 50.0) * 0.05
            clamp_pen = 0.0 if p[-1] in ("G", "C") else 1.2
            homo_pen = 2.0 if any(b * 4 in p for b in "ACGT") else 0.0

            score = diff + gc_pen + clamp_pen + homo_pen
            candidates.append({
                "sequence": p,
                "tm": tm,
                "gc_percent": gc,
                "interval_0based": [s if not circular else s % n, (s + l) if not circular else ((s + l) % n)],
                "interval_unwrapped_0based": [s, s + l],
                "length": l,
                "strand": strand,
                "score": score,
            })

    candidates.sort(key=lambda candidate: candidate['score'])
    return candidates


def _optimize_verification_primer(*args, **kwargs):
    for candidate in _verification_candidates(*args, **kwargs):
        structure = check_complete_oligo_pair(candidate['sequence'])
        if structure['passed']:
            return {**candidate, 'complete_oligo_structure': structure}
    return None


def _search_verification_pair(forward, reverse, max_pair_checks=None):
    """Exhaust the declared candidate combinations in objective order, lazily."""
    if max_pair_checks is not None and max_pair_checks < 1:
        raise ValueError('max_pair_checks must be positive or None')
    singles = {}
    def individually_valid(candidate):
        sequence = candidate['sequence']
        if sequence not in singles:
            singles[sequence] = check_complete_oligo_pair(sequence)
        return singles[sequence]['passed']
    if not forward or not reverse:
        raise ValueError('QC_NO_SOLUTION: no individually valid unique primers in the declared regions')
    queue = [(p['score'] + reverse[0]['score'], i, 0) for i, p in enumerate(forward)]
    heapq.heapify(queue)
    checked = 0
    while queue:
        _, i, j = heapq.heappop(queue)
        if not individually_valid(forward[i]):
            continue
        if j + 1 < len(reverse):
            heapq.heappush(queue, (forward[i]['score'] + reverse[j+1]['score'], i, j+1))
        left, right = forward[i], reverse[j]
        if abs(left['tm'] - right['tm']) > 3 or not individually_valid(right):
            continue
        if max_pair_checks is not None and checked >= max_pair_checks:
            raise ValueError('QC_SEARCH_INCOMPLETE: declared pair-check budget exhausted; not proof of no solution')
        checked += 1
        pair = check_complete_oligo_pair(left['sequence'], right['sequence'])
        dimers = check_primer_dimers(left['sequence'], right['sequence']).analysis
        if pair['passed'] and not dimers['high_dimer_risk']:
            return left, right, {'status': 'PASSED', 'pair_checks': checked,
                  'forward_candidates': len(forward), 'reverse_candidates': len(reverse),
                  'complete_oligo_structure': pair, 'dimer_analysis': dimers}
    raise ValueError('QC_NO_SOLUTION: all applicable pairs in the declared search regions failed unchanged constraints')


def _parental_pcr(templates, forward, reverse):
    """Predict each actual background independently; unknown is never negative."""
    rows = []
    for name, value in (templates or {}).items():
        record = as_molecule(value)
        sequence = str(record.seq)
        circular = record.topology == 'circular'
        fwd = _find_primer_binding(sequence, forward, circular=circular, strand=1,
                                   binding_core_length=len(forward))
        rev = _find_primer_binding(sequence, reverse, circular=circular, strand=-1,
                                   binding_core_length=len(reverse))
        row = {'template': name, 'subject_version': record.record_version,
               'product_lengths_bp': [], 'status': 'NO_PRODUCT_PREDICTED'}
        if fwd and rev:
            try:
                result = simulate_pcr(record, forward, reverse, topology=record.topology,
                    forward_binding_core_length=len(forward), reverse_binding_core_length=len(reverse))
                row.update(status='PRODUCT_PREDICTED', product_lengths_bp=[len(p) for p in result.products])
            except ValueError as exc:
                row.update(status='UNKNOWN', reason=str(exc))
        rows.append(row)
    return {'status': 'CHECKED' if rows else 'NOT_CHECKED', 'templates': rows,
            'all_negative': bool(rows) and all(r['status'] == 'NO_PRODUCT_PREDICTED' for r in rows),
            'scope': 'exact-match PCR on supplied backgrounds; not selection or wet-lab evidence'}


def _sequencing_checks(record, primers):
    from core.io.primer_annotation import find_unique_binding_site
    from core.tools.primer3_backend import Primer3CoreError
    rows, measured = [], []
    for primer in primers or []:
        if not isinstance(primer, dict) or set(primer) - {'name', 'sequence'}:
            raise ValueError('Sequencing primers require only name and complete sequence')
        name, sequence = primer.get('name'), str(primer.get('sequence', '')).upper()
        if not isinstance(name, str) or not name.strip() or not sequence or set(sequence) - set('ACGT'):
            raise ValueError('Sequencing primer name and unambiguous DNA sequence are required')
        row = {'name': name, 'sequence': sequence, 'errors': [], 'status': 'PASSED'}
        try:
            start, strand = find_unique_binding_site(str(record.seq), sequence, record.topology == 'circular')
            row.update(binding_interval_0based=[start, start + len(sequence)], strand=1 if strand == '+' else -1)
        except ValueError:
            row['errors'].append('NO_UNIQUE_BINDING')
        try:
            row['structure'] = check_complete_oligo_pair(sequence)
            if not row['structure']['passed']: row['errors'].append('STRUCTURE_SCREEN_FAILED')
        except Primer3CoreError as exc:
            row['status'] = 'INCOMPLETE'
            row['errors'].append(exc.error_code)
        if row['errors'] and row['status'] != 'INCOMPLETE': row['status'] = 'FAILED'
        rows.append(row)
        measured.append({**row, 'role': 'sanger_sequencing', 'binding_core': sequence,
                         'tm': calc_primer_tm(sequence).analysis['tm']})
    return rows, measured


def sequencing_coverage(record, primers, read_length_bp, read_trim_bp=30):
    """Geometric projection of stated usable read distances, not chromatograms."""
    if read_length_bp is None:
        return {'status': 'NOT_CHECKED', 'experimental_result': False}
    if not isinstance(read_length_bp, int) or not isinstance(read_trim_bp, int) or not 0 <= read_trim_bp < read_length_bp:
        raise ValueError('Require 0 <= read_trim_bp < read_length_bp (integer bases)')
    n = len(record)
    coverage = {1: set(), -1: set()}
    from core.io.primer_annotation import find_unique_binding_site
    for primer in primers:
        if primer.get('role') != 'sanger_sequencing': continue
        try:
            sequence = primer['sequence']
            start, side = find_unique_binding_site(str(record.seq), sequence, record.topology == 'circular')
        except ValueError:
            continue  # Unmatched/ambiguous oligos contribute no coverage.
        strand = 1 if side == '+' else -1
        positions = (start + len(sequence) + i if strand == 1 else start - 1 - i
                     for i in range(read_trim_bp, read_length_bp))
        coverage[strand].update(p % n for p in positions) if record.topology == 'circular' else coverage[strand].update(p for p in positions if 0 <= p < n)
    def gaps(covered):
        missing = [i for i in range(n) if i not in covered]
        intervals = []
        for pos in missing:
            if intervals and intervals[-1][1] == pos: intervals[-1][1] += 1
            else: intervals.append([pos, pos + 1])
        return intervals
    return {'status': 'PREDICTED', 'read_length_bp': read_length_bp, 'read_trim_bp': read_trim_bp,
            'subject_version': record.record_version, 'experimental_result': False,
            'scope': 'assumed readable distances from primer 3prime end; no observed sequencing quality',
            'forward_gaps_0based': gaps(coverage[1]), 'reverse_gaps_0based': gaps(coverage[-1]),
            'combined_gaps_0based': gaps(coverage[1] | coverage[-1])}


def recipe_cloning_verification(
    recombinant_plasmid_seq_or_file: str | pathlib.Path | SeqRecord,
    insert_start_0based: int,
    insert_end_0based: int,
    diagnostic_enzymes: list[str] | None = None,
    max_pair_checks: int | None = None,
    background_templates: dict | None = None,
    sequencing_primers: list[dict] | None = None,
    read_length_bp: int | None = None,
    read_trim_bp: int = 30,
) -> RecipeResult:
    """Design local junction PCR, Sanger primers and diagnostic digests.

    Uses conventional PCR and Sanger screening with explicit design preferences:
    - Designs colony PCR primers spanning the 5' vector-insert cloning junction (one in vector, one in insert).
    - Designs Sanger sequencing primer anchored 50-100 bp upstream of the junction, avoiding the 30-50 bp dye-blob blind zone.
    - Simulates diagnostic restriction digestion and checks whether band sizes differ by >= 15% for clean gel resolution.
    - Emits source provenance and literature citations.
    """
    rec = _load_record(recombinant_plasmid_seq_or_file)
    seq = str(rec.seq).upper()
    n = len(seq)

    if n < 80:
        raise ValueError(
            f"Template sequence length ({n} bp) is too short to design junction verification primers. "
            "Minimum required length is 80 bp. For CRISPR knock-in, provide the edited genomic locus with flanking regions."
        )

    topo = rec.annotations.get("topology")
    if topo not in ('circular', 'linear'):
        raise PlanningError('MOLECULE_TOPOLOGY_REQUIRED',
            'QC requires the actual template topology, linear or circular; unknown topology cannot define junction geometry',
            missing_fields=['recombinant_plasmid_seq_or_file.topology'],
            details={'allowed_values': ['linear', 'circular'],
                     'recovery': 'Provide the actual source topology or an annotated material that declares it'})
    is_circ = (topo == "circular")

    ins_s = insert_start_0based % n if is_circ else insert_start_0based
    ins_e = insert_end_0based % n if is_circ else insert_end_0based
    if not is_circ and not (0 <= ins_s < ins_e <= n):
        raise ValueError("Insert coordinates must define a nonempty interval within the linear template")
    if is_circ and ins_s == ins_e:
        raise ValueError("Insert occupies the whole circular template; no backbone junction is defined")
    if is_circ:
        ins_len = (n - ins_s + ins_e) if ins_e <= ins_s else (ins_e - ins_s)
    else:
        ins_len = max(1, ins_e - ins_s)

    warnings = []

    # 1. Determine optimal anchors respecting topology and physical boundaries
    if not is_circ:
        upstream_avail = ins_s
        downstream_avail = n - ins_s

        fwd_offset = min(180, max(25, upstream_avail // 2))
        rev_offset = min(220, max(25, min(ins_len, downstream_avail) // 2))
        sanger_dist = min(70, max(25, upstream_avail - 20))

        if upstream_avail < 50:
            warnings.append(
                f"Upstream sequence before junction is short ({upstream_avail} bp < 50 bp). "
                "Sanger sequencing primer is placed close to junction and may hit dye-blob noise."
            )

        fwd_anchor = max(0, ins_s - fwd_offset)
        rev_anchor = min(n - 1, ins_s + rev_offset)
        sanger_anchor = max(0, ins_s - sanger_dist - 20)
    else:
        fwd_offset = min(180, max(30, (n - ins_len) // 4))
        rev_offset = min(220, max(30, ins_len // 3))
        sanger_dist = 70

        fwd_anchor = ins_s - fwd_offset
        rev_anchor = ins_s + rev_offset
        sanger_anchor = ins_s - sanger_dist - 20

    backbone_interval = (ins_s - (n - ins_len) if is_circ else 0, ins_s)
    insert_interval = (ins_s, ins_s + ins_len)

    # 2. Thermodynamically optimize primers
    forward_candidates = _verification_candidates(
        seq=seq,
        target_pos=fwd_anchor,
        strand=1,
        target_tm=60.0,
        circular=is_circ,
        allowed_interval=backbone_interval,
    )
    reverse_candidates = _verification_candidates(
        seq=seq,
        target_pos=rev_anchor,
        strand=-1,
        target_tm=60.0,
        circular=is_circ,
        allowed_interval=insert_interval,
    )
    sanger_primer_res = _optimize_verification_primer(
        seq=seq,
        target_pos=sanger_anchor,
        strand=1,
        target_tm=58.0,
        circular=is_circ,
        allowed_interval=backbone_interval,
        junction=ins_s,
    )
    if sanger_primer_res is None:
        sanger_primer_res = _optimize_verification_primer(
            seq, ins_s + 70, strand=-1, target_tm=58.0, circular=is_circ,
            allowed_interval=insert_interval, junction=ins_s,
        )

    fwd_primer_res, rev_primer_res, pair_search = _search_verification_pair(
            forward_candidates, reverse_candidates, max_pair_checks)

    fwd_primer_seq = fwd_primer_res["sequence"]
    fwd_tm = fwd_primer_res["tm"]
    rev_primer_seq = rev_primer_res["sequence"]
    rev_tm = rev_primer_res["tm"]
    sanger_primer_seq = sanger_primer_res["sequence"] if sanger_primer_res else ""
    sanger_tm = sanger_primer_res["tm"] if sanger_primer_res else 0.0

    pcr = simulate_pcr(rec, fwd_primer_seq, rev_primer_seq, topology=topo,
                       forward_binding_core_length=len(fwd_primer_seq),
                       reverse_binding_core_length=len(rev_primer_seq))
    amplicon_size = pcr.analysis["amplicon_length"]
    f_start = pcr.analysis["template_interval_0based"][0]
    junction_offset = (ins_s - f_start) % n if is_circ else ins_s - f_start
    crosses_junction = len(fwd_primer_seq) <= junction_offset <= amplicon_size - len(rev_primer_seq)
    sanger_dist = None
    if sanger_primer_res:
        a, b = sanger_primer_res["interval_unwrapped_0based"]
        sanger_dist = ins_s - b if sanger_primer_res["strand"] == 1 else a - ins_s
    if sanger_primer_res is None:
        warnings.append("No unique Sanger primer facing the junction at 50-100 bp distance; provide more flanking sequence or an alternative sequencing strategy.")

    colony_dimers = check_primer_dimers(fwd_primer_seq, rev_primer_seq).analysis
    colony_structure = check_complete_oligo_pair(fwd_primer_seq, rev_primer_seq)
    if not colony_structure["passed"]:
        raise ValueError("QC_PRIMER_STRUCTURE: selected colony-PCR pair fails complete-oligo structural QC; choose alternative assay boundaries")

    # 3. Diagnostic Restriction Digest Simulation
    enzymes_to_test = diagnostic_enzymes or ["EcoRI", "BamHI", "HindIII"]
    diagnostic_bands = []

    for enz_name in enzymes_to_test:
        e_info = digest_sequence(seq, enz_name, circular=is_circ)
        cut_cnt = e_info.analysis.get("cut_count", 0)
        if cut_cnt >= 1:
            bands = sorted((len(fragment) for fragment in e_info.products), reverse=True)

            resolvable = True
            for i in range(len(bands) - 1):
                if bands[i] > 0 and (bands[i] - bands[i + 1]) / bands[i] < 0.15:
                    resolvable = False
                    break

            diagnostic_bands.append({
                "enzyme": enz_name,
                "cut_count": cut_cnt,
                "predicted_band_sizes_bp": bands,
                "bands_well_resolved_on_gel": resolvable,
            })

    quality_checks = {
        "pair_search": pair_search,
        "sanger_distance_from_junction_bp": sanger_dist,
        "sanger_primer_avoids_dye_blob_zone": (sanger_dist is not None and 50 <= sanger_dist <= 100),
        "colony_pcr_crosses_junction": crosses_junction,
        "colony_pcr_amplicon_length_conforming": (200 <= amplicon_size <= 850),
        "colony_pcr_delta_tm": abs(round(fwd_tm - rev_tm, 1)),
        "forward_primer_tm": fwd_tm,
        "reverse_primer_tm": rev_tm,
        "colony_pcr_primer_tm_compatible": (52 <= fwd_tm <= 72 and 52 <= rev_tm <= 72 and abs(fwd_tm-rev_tm) <= 3),
        "primer_dimers_safe": not colony_dimers["high_dimer_risk"] and colony_structure["passed"],
        "complete_oligo_structure_passed": colony_structure["passed"],
    }

    sop_reminders = [
        "COLONY_PCR_TEMPLATE: Lightly touch a colony with a 10 uL pipette tip, resuspend in 20 uL sterile H2O, heat at 95°C for 5 min to lyse bacteria, and use 2 uL as PCR template.",
        "SANGER_VERIFICATION: Ensure trace chromatogram displays single, sharp peaks across the junction without secondary baseline noise.",
    ]

    primers_dict = {
        "forward_primer_in_vector": fwd_primer_seq,
        "forward_tm": fwd_tm,
        "forward_gc_percent": fwd_primer_res["gc_percent"],
        "forward_interval_0based": fwd_primer_res["interval_0based"],
        "reverse_primer_in_insert": rev_primer_seq,
        "reverse_tm": rev_tm,
        "reverse_gc_percent": rev_primer_res["gc_percent"],
        "reverse_interval_0based": rev_primer_res["interval_0based"],
        "expected_amplicon_size_bp": amplicon_size,
        "dimer_risk": colony_dimers["high_dimer_risk"],
        "notes": "One primer in backbone, one in insert. Exact-match PCR checked on the complete recombinant template; parental-template specificity has not been tested.",
    }

    primers_list = [
        {
            "name": "Colony_PCR_Fwd_Vector",
            "sequence": fwd_primer_seq,
            "tm": fwd_tm,
            "gc_percent": fwd_primer_res["gc_percent"],
            "role": "colony_pcr_screening",
            "binding_core": fwd_primer_seq,
            "binding_interval_0based": fwd_primer_res["interval_0based"],
            "strand": 1,
        },
        {
            "name": "Colony_PCR_Rev_Insert",
            "sequence": rev_primer_seq,
            "tm": rev_tm,
            "gc_percent": rev_primer_res["gc_percent"],
            "role": "colony_pcr_screening",
            "binding_core": rev_primer_seq,
            "binding_interval_0based": rev_primer_res["interval_0based"],
            "strand": -1,
        },
    ]
    if sanger_primer_seq:
        primers_list.append({
            "name": "Sanger_Seq_Fwd" if sanger_primer_res["strand"] == 1 else "Sanger_Seq_Rev",
            "sequence": sanger_primer_seq,
            "tm": sanger_tm,
            "gc_percent": sanger_primer_res["gc_percent"] if sanger_primer_res else 0.0,
            "role": "sanger_sequencing",
            "binding_core": sanger_primer_seq,
            "binding_interval_0based": sanger_primer_res["interval_0based"],
            "strand": sanger_primer_res["strand"],
        })

    parental = _parental_pcr(background_templates, fwd_primer_seq, rev_primer_seq)
    if background_templates:
        primers_dict['notes'] = 'Exact-match PCR checked on recombinant and supplied backgrounds; parent bands are listed separately. Selection is not a PCR-negative control.'
    sequencing_checks, extra_primers = _sequencing_checks(as_molecule(rec), sequencing_primers)
    primers_list.extend(extra_primers)
    if len({p['name'] for p in primers_list}) != len(primers_list):
        raise ValueError('QC primer names must be unique within one assay')
    coverage = sequencing_coverage(as_molecule(rec), primers_list, read_length_bp, read_trim_bp)
    protocol_steps = [
        {"step": 1, "action": f"Pick candidate colonies and perform colony PCR using primers {fwd_primer_seq[:10]}... and {rev_primer_seq[:10]}... (expected size: {amplicon_size} bp)."},
        {"step": 2, "action": "Compare predicted bands on each supplied parental template; a parent may produce a band. Use other discriminating junctions and sequencing to confirm clones." if background_templates else "Parental-template discrimination has not been checked. Check the actual backgrounds before labelling them PCR-negative; confirm clones by sequencing."},
        {"step": 3, "action": "Isolate high-purity plasmid DNA from positive clones and run diagnostic restriction digests."},
        {"step": 4, "action": "Perform Sanger sequencing using primer anchored upstream of junction to confirm mutation/junction fidelity."},
    ]

    oligo_products = [derived_molecule(SeqRecord(Seq(p["sequence"]),id=p["name"],annotations={"molecule_type":"DNA","topology":"linear"}),[as_molecule(rec)],operation="verification_primer_design",strandedness="single") for p in primers_list]
    return RecipeResult(
        recipe_name="recipe_cloning_verification",
        result_kind="verification",
        completeness="qc_only",
        products=oligo_products,
        subject=as_molecule(rec),
        checks=[__import__('core.tools.result', fromlist=['check_result']).check_result(
            'junction_pcr_design', subject=as_molecule(rec), status='PASSED', scope='verification_design',
            conditions={'insert_interval_0based': [ins_s, ins_e], 'tm_range_C': [52,72], 'max_tm_delta_C':3},
            details={'expected_amplicon_size_bp': amplicon_size, 'pair_search':pair_search,
                     'parental_specificity': parental, 'wet_lab': 'NOT_CHECKED'})] + [
            __import__('core.tools.result', fromlist=['check_result']).check_result(
                'supplemental_sequencing_oligo', subject=as_molecule(rec), status=row['status'],
                scope='verification_design', details=row) for row in sequencing_checks],
        primers=primers_list,
        quality_checks=quality_checks,
        warnings=warnings,
        protocol_steps=protocol_steps,
        citations=AUTHORITATIVE_SOURCES,
        details={
            "recipe": "recipe_cloning_verification",
            "template_length": n,
            "recombinant_plasmid_length": n,
            "topology": topo,
            "insert_coordinates": {"start": ins_s, "end": ins_e, "length": ins_len},
            "sanger_sequencing_primer": {
                "sequence": sanger_primer_seq,
                "tm": sanger_tm,
                "gc_percent": sanger_primer_res["gc_percent"] if sanger_primer_res else 0.0,
                "interval_0based": sanger_primer_res["interval_0based"] if sanger_primer_res else [],
                "strand": sanger_primer_res["strand"] if sanger_primer_res else None,
                "distance_from_junction_bp": sanger_dist,
                "distance_upstream_of_junction_bp": sanger_dist if sanger_primer_res and sanger_primer_res["strand"] == 1 else None,
                "notes": f"Actual distance from primer 3' end to junction: {sanger_dist} bp." if sanger_dist is not None else "No suitable sequencing primer found.",
            },
            "colony_pcr_primers": primers_dict,
            "junction_pcr_primers": primers_dict,
            "parental_pcr": parental,
            "sequencing_checks": sequencing_checks,
            "sequencing_coverage": coverage,
            "diagnostic_restriction_digests": diagnostic_bands,
            "colony_pcr_simulation": pcr,
            "complete_oligo_structure": colony_structure,
            "sanger_oligo_structure": sanger_primer_res["complete_oligo_structure"] if sanger_primer_res else None,
            "quality_checks": quality_checks,
            "warnings": warnings,
            "sop_reminders": sop_reminders,
            "authoritative_sources": AUTHORITATIVE_SOURCES,
        },
    )
