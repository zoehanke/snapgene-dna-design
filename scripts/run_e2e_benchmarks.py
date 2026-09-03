# -*- coding: utf-8 -*-
"""scripts/run_e2e_benchmarks.py - Command-line runner for Scientific Composite Benchmarks.

Executes:
1. Scenario A: In-frame Gibson Assembly fusion cloning with C-terminal 6xHis tag,
   feature preservation, Tier 3 bio-guardrail audit, and native SnapGene export.
2. Scenario B: CRISPR Cas9 sgRNA design, U6 cloning oligos, HDR donor template
   with automated synonymous PAM silencing, junction verification primers, and Tier 3 audit.
3. Desktop Integration: Checks native binary .dna generation and SnapGene viewer path.

Usage:
    python scripts/run_e2e_benchmarks.py [--open]
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import time

from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

# Ensure project root is in sys.path
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.guardrails import quick_biological_sanity_check, scan_crispr_recleavage_risk
from core.recipes.crispr_hdr import recipe_crispr_hdr_donor
from core.recipes.gibson import recipe_gibson_assembly
from core.recipes.protein_tagging import recipe_protein_tagging
from core.recipes.verification import recipe_cloning_verification
from core.tools.amplification import simulate_pcr
from core.tools.crispr import design_crispr_grna, prepare_grna_oligos
from core.tools.feature_ops import annotate_feature
from core.tools.inspection import inspect_dna
from core.tools.snapgene_io import SNAPGENE_EXE_PATH, export_snapgene, open_in_snapgene


def run_scenario_a(out_dir: pathlib.Path) -> dict:
    print("\n" + "=" * 70)
    print(">>> [Scenario A] Gibson Assembly Fusion Cloning E2E Benchmark")
    print("=" * 70)

    # 1. Prepare expression vector backbone: pET-like plasmid (~1,500 bp)
    print("[1/6] Building expression vector backbone (pUC ori + AmpR marker)...")
    amp_cds = "ATG" + "GCATCGTAGCTA" * 20 + "TAA"  # 246 bp model marker
    ori_seq = (
        "TTGAGATCCTTTTTTTCTGCGCGTAATCTGCTGCTTGCAAACAAAAAAACCACCGCTACCAGCGGTGGTTTGTTTGCCGGATCAAGAGCTACCAACTCTTTTTCC"
        "GAAGGTAACTGGCTTCAGCAGAGCGCAGATACCAAATACTGTCCTTCTAGTGTAGCCGTAGTTAGGCCACCACTTCAAGAACTCTGTAGCACCGCCTACATACCT"
        "CGCTCTGCTAATCCTGTTACCAGTGGCTGCTGCCAGTGGCGATAAGTCGTGTCTTACCGGGTTGGACTCAAGACGATAGTTACCGGATAAGGCGCAGCGGTCGGGC"
    )
    spacer1 = ("AGCTTGAC" + "TGCAGCTA" + "CAAGTCAG" + "GATCGATC") * 4
    spacer2 = ("GATCACGT" + "ACTGATCG" + "CGATAGCT" + "TACGATCG") * 5
    spacer3 = ("CTAGCTAG" + "AGCTAGCT" + "GATCGATC" + "CGTACGTA") * 4
    mcs = "GAATTC" + "CGATCGATC" + "AAGCTT"  # EcoRI ... HindIII

    vector_seq = ori_seq + spacer1 + amp_cds + spacer2 + mcs + spacer3
    vec_record = SeqRecord(Seq(vector_seq), id="pVector_pET", name="pVector_pET")
    vec_record.annotations["topology"] = "circular"
    vec_record.features.append(SeqFeature(FeatureLocation(0, len(ori_seq)), type="rep_origin", qualifiers={"label": ["pUC ori"]}))
    amp_start = len(ori_seq) + len(spacer1)
    vec_record.features.append(SeqFeature(FeatureLocation(amp_start, amp_start + len(amp_cds)), type="CDS", qualifiers={"label": ["AmpR"]}))

    # Linearize vector between EcoRI and HindIII
    mcs_start = amp_start + len(amp_cds) + len(spacer2)
    ecori_cut = mcs_start + 1
    hindiii_cut = mcs_start + 6 + 9 + 1
    vector_backbone_seq = vector_seq[hindiii_cut:] + vector_seq[:ecori_cut]
    print(f"      Vector linearized: backbone length = {len(vector_backbone_seq)} bp")

    # 2. Protein Tagging: C-terminal 6xHis fusion with flexible GS linker
    print("[2/6] Tagging target gene: appending flexible (G4S)2 linker + 6xHis tag (stripping stop)...")
    gfp_cds = "ATG" + "GTGAGCAAGGGCGAG" * 29 + "TAA"  # 453 bp
    tag_recipe = recipe_protein_tagging(
        target_cds_seq_or_file=gfp_cds,
        tag_name_or_seq="6xHis",
        tag_position="C-terminal",
        linker_type="flexible_G4S_x2",
        include_kozak=False,
    )
    tagged_insert_seq = tag_recipe["product_dna_sequence"]
    print(f"      Tagged CDS length = {len(tagged_insert_seq)} bp, in-frame = {tag_recipe['quality_checks']['in_frame_fusion']}")

    # 3. Gibson overlap primer design and overlap assembly simulation
    print("[3/6] Designing Gibson overlap primers (22 bp homology) & assembling construct...")
    gibson_design = recipe_gibson_assembly(
        vector_linear_seq=vector_backbone_seq,
        insert_template_seq=tagged_insert_seq,
        insert_start=0,
        insert_end=len(tagged_insert_seq),
        overlap_length=22,
        circular_product=True,
    )
    fwd_primer = gibson_design["primers"]["forward"]["full_sequence"]
    rev_primer = gibson_design["primers"]["reverse"]["full_sequence"]
    assembled_seq = gibson_design["product_sequence"]
    print(f"      Forward primer (5' overhang + binding): {fwd_primer}")
    print(f"      Reverse primer (5' overhang + binding): {rev_primer}")
    print(f"      Assembled circular construct size = {len(assembled_seq)} bp")

    # 4. Feature migration and annotation
    print("[4/6] Migrating backbone features and annotating recombinant 6xHis tag...")
    construct_rec = SeqRecord(Seq(assembled_seq), id="pET_eGFP_6xHis", name="pET_eGFP_6xHis")
    construct_rec.annotations["topology"] = "circular"
    construct_rec.features = list(vec_record.features)
    annotated_rec = annotate_feature(
        record=construct_rec,
        name="6xHis",
        feature_type="tag",
        start=len(vector_backbone_seq) + len(tagged_insert_seq) - 18,
        end=len(vector_backbone_seq) + len(tagged_insert_seq),
        strand=1,
        color="#fdbf6f",
    )

    # 5. Tier 3 Objective Biological Guardrail Verification
    print("[5/6] Executing Tier 3 First-Principles Biological Guardrail Audit...")
    sanity_cds = quick_biological_sanity_check(tagged_insert_seq, is_cds=True)
    sanity_plasmid = quick_biological_sanity_check(
        annotated_rec,
        cloning_enzymes=["BamHI"],
        primers=[fwd_primer, rev_primer],
        check_secondary_structure=True,
        is_cds=False,
        topology="circular",
    )
    print(f"      Insert CDS guardrail audit: {'PASS (Clean)' if sanity_cds['all_clean'] else 'FAILED'}")
    print(f"      Plasmid replicon (ori): {sanity_plasmid['maintenance_elements']['has_origin']}")
    print(f"      Selectable marker:      {sanity_plasmid['maintenance_elements']['has_marker']}")
    print(f"      Full construct audit:   {'PASS (Clean)' if sanity_plasmid['all_clean'] else 'ISSUES FOUND'}")

    # 6. SnapGene Export
    print("[6/6] Exporting native SnapGene .dna and GenBank .gb...")
    out_files = export_snapgene(
        record_or_seq=annotated_rec,
        out_dir=out_dir,
        filename_base="scenario_a_gibson_egfp_6xhis",
        topology="circular",
    )
    print(f"      SnapGene DNA file: {out_files['dna_file']}")
    print(f"      GenBank GB file:   {out_files['gb_file']}")

    # Verification re-read
    inspection = inspect_dna(out_files["dna_file"])
    print(f"      Re-read verification: length = {inspection['sequence_length']} bp, topology = {inspection['topology']}, features = {inspection['feature_count']}")

    return {
        "scenario": "A_Gibson_Fusion_Cloning",
        "status": "SUCCESS",
        "construct_length": len(assembled_seq),
        "files": out_files,
        "guardrail_clean": sanity_cds["all_clean"] and sanity_plasmid["all_clean"],
    }


def run_scenario_b(out_dir: pathlib.Path) -> dict:
    print("\n" + "=" * 70)
    print(">>> [Scenario B] CRISPR HDR Precision Knock-In E2E Benchmark")
    print("=" * 70)

    # 1. Target genomic locus (human EMX1 exon 3 target site)
    print("[1/5] Loading target genomic locus (EMX1 model locus)...")
    spacer = "GAGTCCGAGCAGAAGAAGAA"
    pam = "GGG"
    target_genomic_locus = "T" * 80 + "CTAGCAGCTAGCA" + spacer + pam + "GCTAGCTAGCTA" + "A" * 80
    print(f"      Target locus size = {len(target_genomic_locus)} bp, SpCas9 spacer = {spacer} ({pam})")

    # 2. CRISPR sgRNA scan & U6 golden gate oligos
    print("[2/5] Designing candidate sgRNAs & preparing U6 cloning oligos (BbsI)...")
    guides = design_crispr_grna(target_seq_or_file=target_genomic_locus, nuclease="SpCas9")
    oligos = prepare_grna_oligos(spacer_seq=spacer, vector_type="BbsI")
    print(f"      Selected Guide: {guides[0]['spacer']} (Quality Score: {guides[0]['quality_score']})")
    print(f"      Top oligo (5' CACC overhang): {oligos['forward_oligo']['sequence']}")
    print(f"      Bottom oligo (5' AAAC overhang): {oligos['reverse_oligo']['sequence']}")

    # 3. HDR donor template design with automated synonymous PAM silencing
    print("[3/5] Designing CRISPR HDR donor repair template with PAM mutation...")
    cut_pos = 80 + 13 + 17  # 3 bp upstream of PAM
    ha_payload = "TATCCATATGATGTTCCAGATTATGCT"  # 27 bp HA tag
    hdr_recipe = recipe_crispr_hdr_donor(
        target_seq_or_file=target_genomic_locus,
        cut_position_0based=cut_pos,
        edit_dna=ha_payload,
        donor_type="ssODN",
        grna_seq=spacer,
        custom_arm_length=50,
    )
    donor_seq = hdr_recipe["donor_sequence"]
    print(f"      HDR ssODN donor size = {len(donor_seq)} nt")
    print(f"      PAM silenced: {hdr_recipe['pam_silenced']} ({hdr_recipe['pam_silencing_details']})")

    # 4. Tier 3 First-Principles Guardrail: Cas9 re-cleavage audit
    print("[4/5] Auditing in vivo Cas9 re-cleavage risk...")
    recleavage_audit = scan_crispr_recleavage_risk(donor_seq=donor_seq, grna_seq=spacer)
    sanity = quick_biological_sanity_check(
        record_or_seq=donor_seq,
        crispr_grna_seq=spacer,
        topology="linear",
        is_cds=False,
    )
    print(f"      Cas9 re-cleavage risk: {recleavage_audit['recleavage_risk']} (intact seed/PAM found: {recleavage_audit['intact_seed_pam_found']})")
    print(f"      Guardrail clean:       {'PASS (Clean)' if sanity['all_clean'] else 'ISSUES FOUND'}")

    # 5. Junction Verification Primers & Export
    print("[5/5] Designing junction verification primers & exporting construct...")
    verification_plan = recipe_cloning_verification(
        recombinant_plasmid_seq_or_file=donor_seq,
        insert_start_0based=50,
        insert_end_0based=50 + len(ha_payload),
    )
    donor_rec = SeqRecord(Seq(donor_seq), id="EMX1_HA_Donor", name="EMX1_HA_Donor")
    donor_rec.annotations["topology"] = "linear"
    donor_rec.features.append(SeqFeature(FeatureLocation(50, 50 + len(ha_payload)), type="tag", qualifiers={"label": ["HA Tag"]}))

    out_files = export_snapgene(
        record_or_seq=donor_rec,
        out_dir=out_dir,
        filename_base="scenario_b_crispr_hdr_ha_tag",
        topology="linear",
    )
    colony_info = verification_plan["colony_pcr_primers"]
    print(f"      Colony PCR Fwd (vector): {colony_info['forward_primer_in_vector']} (Tm: {colony_info['forward_tm']}°C)")
    print(f"      Colony PCR Rev (insert): {colony_info['reverse_primer_in_insert']} (Tm: {colony_info['reverse_tm']}°C)")
    print(f"      Sanger sequencing:       {verification_plan['sanger_sequencing_primer']['sequence']}")
    print(f"      SnapGene DNA file:       {out_files['dna_file']}")

    return {
        "scenario": "B_CRISPR_HDR_Knockin",
        "status": "SUCCESS",
        "donor_length": len(donor_seq),
        "files": out_files,
        "pam_silenced": hdr_recipe["pam_silenced"],
        "recleavage_risk": recleavage_audit["recleavage_risk"],
        "guardrail_clean": sanity["all_clean"],
    }


def main():
    parser = argparse.ArgumentParser(description="Run SnapGene DNA Design Scientific Composite Benchmarks")
    parser.add_argument("--open", action="store_true", help="Launch desktop SnapGene viewer on generated construct")
    args = parser.parse_args()

    out_dir = PROJECT_ROOT / "output" / "e2e_benchmarks"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "#" * 70)
    print("#  SNAPGENE DNA DESIGN - PHASE 6 SCIENTIFIC COMPOSITE BENCHMARK SUITE")
    print(f"#  SnapGene Executable: {SNAPGENE_EXE_PATH} (Exists: {pathlib.Path(SNAPGENE_EXE_PATH).exists()})")
    print("#" * 70)

    start_t = time.time()
    res_a = run_scenario_a(out_dir)
    res_b = run_scenario_b(out_dir)
    elapsed = round(time.time() - start_t, 3)

    print("\n" + "=" * 70)
    print(">>> BENCHMARK SUMMARY REPORT")
    print("=" * 70)
    print(f"  [Scenario A: Gibson Fusion]:     {res_a['status']} | Guardrails: {'CLEAN' if res_a['guardrail_clean'] else 'FAIL'}")
    print(f"  [Scenario B: CRISPR HDR Donor]:  {res_b['status']} | Guardrails: {'CLEAN' if res_b['guardrail_clean'] else 'FAIL'}")
    print(f"  Total Execution Time:             {elapsed} seconds")
    print(f"  Artifact Directory:               {out_dir}")
    print("=" * 70)

    if args.open:
        dna_path = res_a["files"]["dna_file"]
        print(f"\nLaunching desktop SnapGene on: {dna_path}...")
        open_res = open_in_snapgene(dna_path)
        print(f"Launcher result: {open_res}")


if __name__ == "__main__":
    main()
