# -*- coding: utf-8 -*-
"""tests/test_defect_governance.py - Verification suite for full-system biological truth and structural defect remediation.

Verifies:
1. Biological Truth: N-terminal tag assembly order (Kozak -> Tag -> Linker -> Cleavage -> CDS).
2. Biological Truth: CRISPR HDR donor strictly rejects non-synonymous PAM mutations in CDS.
3. Biological Truth: Multi-site restriction removal in translation.py dynamically tracking current hits.
4. Biological Truth: Restriction cloning directional verification via physical overhang compatibility.
5. Biological Truth: Dynamic stop codon determination using NCBI CodonTable.
6. Topology & Interval: Insertion zero-width interval semantics on circular and linear records.
7. Guardrails: Structured CRITICAL vs WARNING severity categorization.
8. Architectural Decoupling: Zero core/ -> scripts/ layer inversion imports.
"""
from __future__ import annotations

from repository_paths import PROJECT_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS

import pathlib
import unittest

from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from core.guardrails.checklist import quick_biological_sanity_check
from core.interval import PlanningError, validate_interval
from core.recipes.crispr_hdr import recipe_crispr_hdr_donor
from core.recipes.protein_tagging import recipe_protein_tagging
from core.recipes.restriction_cloning import (
    are_restriction_ends_compatible,
    recipe_restriction_cloning,
)
from core.tools.restriction import get_enzyme
from core.tools.sequence_ops import check_reading_frame
from core.tools.translation import silent_mutation_remove_site, translate_dna


class TestDefectGovernance(unittest.TestCase):
    """Test cases verifying remediation of deep structural and biological defects."""

    def test_n_terminal_tag_assembly_order(self):
        """Verify N-terminal tag order is [Kozak] + Tag + [Linker] + [Cleavage] + Target_CDS.

        Protease cleavage must occur immediately adjacent to the CDS so no permanent
        linker scar remains attached to the purified protein.
        """
        target_cds = "ATGGTGAGCAAGGGCGAGGAGCTGTTCACCGGGGTGGTGCCCATCCTGGTCGAGCTGGACGGCGACGTAAACGGCCACAAGTTCAGCGTGTCCGGCGAGTAG"
        res = recipe_protein_tagging(
            target_cds_seq_or_file=target_cds,
            tag_name_or_seq="6xHis",
            tag_position="N-terminal",
            linker_type="flexible_G4S_x2",
            protease_cleavage="TEV",
            include_kozak=True,
            terminal_stop_codon="TAA",
        )

        product = res["product_sequence"]
        self.assertTrue(product.startswith("GCCACCATGCATCATCATCATCATCAT"), "Must begin with Kozak + initiator ATG + 6xHis tag")
        # TEV recognition sequence is ENLYFQG (GAAAACCTGTATTTTCAGGGC)
        tev_dna = "GAAAACCTGTATTTTCAGGGC"
        self.assertIn(tev_dna, product, "TEV recognition site must be present")
        # Target CDS (without initial start codon or fused in frame) must follow TEV cleavage site
        idx_tev = product.find(tev_dna)
        idx_cds = product.find(target_cds[3:])  # CDS after start codon
        self.assertEqual(idx_tev + len(tev_dna), idx_cds, "Cleavage site must be immediately adjacent to Target CDS")

    def test_crispr_synonymous_pam_mutation(self):
        """Verify CRISPR HDR donor uses synonymous PAM mutations in CDS and rejects missense mutations."""
        # A mock genomic locus where PAM is at right_arm[3:6] (NGG)
        # Cut is at index 50.
        # right_arm[0:3] = "TTT", right_arm[3:6] = "CGG" (Arg: CGG)
        # In CDS frame offset 0: CGG translates to Arg.
        # Synonyms for CGG (Arg): CGA, CGC, CGT, AGA, AGG.
        # Mutating G to A/C/T at pos 4/5 destroys NGG PAM while keeping Arg!
        ref_seq = "A" * 50 + "TTTCGG" + "C" * 50
        cut_pos = 50
        res = recipe_crispr_hdr_donor(
            target_seq_or_file=ref_seq,
            cut_position_0based=cut_pos,
            edit_dna="A",
            donor_type="ssODN",
            grna_seq="A" * 17 + "TTT",
            target_is_cds=True,
            cds_frame_offset=0,
        )
        self.assertTrue(res["pam_silenced"], "PAM should be silenced")
        self.assertTrue(str(res.products[0].seq))
        # Verify synonymous mutation was applied to disable PAM without altering amino acid
        self.assertTrue(res["quality_checks"]["missense_mutation_avoided"], "Missense mutations must be avoided")
        self.assertGreater(len(res["mutations_applied"]), 0, "Mutations should be applied")
        for mut in res["mutations_applied"]:
            self.assertTrue(mut.get("synonymous"), "Mutations in CDS must be synonymous")

    def test_silent_mutation_multi_site(self):
        """Verify silent_mutation_remove_site cleanly silences multiple internal restriction sites."""
        # Create a CDS with 2 EcoRI sites (GAATTC)
        # Codon 1-3: ATG (Met)
        # Codons with EcoRI: GAA TTC -> Glu Phe
        # GAA TTC can be mutated to GAG TTC (Glu Phe) - synonymous!
        # Let's construct a valid reading frame with two EcoRI sites:
        # ATG (Met) + GAA TTC (Glu Phe) + GCT GCT (Ala Ala) + GAA TTC (Glu Phe) + TAA (Stop)
        cds = "ATGGAATTCGCTGCTGAATTCTAA"
        # Both GAA TTC (Glu Phe) are in frame:
        # Codons: [ATG] [GAA] [TTC] [GCT] [GCT] [GAA] [TTC] [TAA]
        orig_aa = translate_dna(cds, frame=1).analysis['translation']

        enz = get_enzyme("EcoRI")
        hits_before = len(enz.search(Seq(cds)))
        self.assertEqual(hits_before, 2, "Test sequence must start with 2 EcoRI cuts")

        res = silent_mutation_remove_site(cds, "EcoRI", frame_offset=0, table=1)
        self.assertTrue(res.analysis['site_removed'], "All EcoRI sites must be removed")
        self.assertEqual(res.analysis['remaining_cut_count'], 0, "Remaining cut count must be 0")
        self.assertTrue(res.analysis['identical_translation'], "Translation must remain strictly identical")
        self.assertEqual(translate_dna(str(res.only_product().seq), frame=1).analysis['translation'], orig_aa)
        self.assertGreaterEqual(len(res.analysis['mutations_applied']), 2, "Must have applied mutations for both sites")

    def test_directional_cloning_compatibility(self):
        """Verify directional cloning validation detects compatible ends as non-directional."""
        bamhi = get_enzyme("BamHI")  # 5' GATC
        bglii = get_enzyme("BglII")  # 5' GATC
        ecorv = get_enzyme("EcoRV")  # blunt
        smai = get_enzyme("SmaI")    # blunt
        ecori = get_enzyme("EcoRI")  # 5' AATT
        psti = get_enzyme("PstI")    # 3' TGCA

        # 1. BamHI and BglII have identical 5' GATC overhangs -> compatible!
        self.assertTrue(are_restriction_ends_compatible(bamhi, bglii))

        # 2. EcoRV and SmaI are both blunt -> compatible!
        self.assertTrue(are_restriction_ends_compatible(ecorv, smai))

        # 3. EcoRI (AATT) and BamHI (GATC) -> incompatible!
        self.assertFalse(are_restriction_ends_compatible(ecori, bamhi))

        # 4. EcoRI (5' overhang) and EcoRV (blunt) -> incompatible!
        self.assertFalse(are_restriction_ends_compatible(ecori, ecorv))

        # 5. BamHI (5' overhang) and PstI (3' overhang) -> incompatible!
        self.assertFalse(are_restriction_ends_compatible(bamhi, psti))

    def test_non_standard_codon_table_stops(self):
        """Verify check_reading_frame dynamically queries CodonTable stop codons."""
        # In Table 1 (standard): TAA, TAG, TGA are stop codons.
        # In Table 2 (vertebrate mitochondrial):
        # Stop codons: TAA, TAG, AGA, AGG.
        # TGA is NOT a stop codon; it codes for Trp (W).

        # Sequence with TGA inside CDS and AGA at end:
        # [ATG] [TGA] [AGA]
        seq_mito = "ATGTGAAGA"

        # Under table 1: TGA is a premature stop codon
        res_t1 = check_reading_frame(seq_mito, start_offset=0, transl_table=1).analysis
        self.assertTrue(res_t1["has_premature_stop"], "Table 1 must treat TGA as premature stop")
        self.assertIn(3, res_t1["premature_stop_positions"])

        # Under table 2: TGA translates to Trp, AGA is the terminal stop codon!
        res_t2 = check_reading_frame(seq_mito, start_offset=0, transl_table=2).analysis
        self.assertFalse(res_t2["has_premature_stop"], "Table 2 must NOT treat TGA as stop codon")
        self.assertTrue(res_t2["terminal_stop"], "Table 2 must recognize AGA as canonical terminal stop")
        self.assertEqual(res_t2["translation"], "MW*")

    def test_interval_insertion_semantics(self):
        """Verify zero-width intervals are correctly handled for insertions."""
        record_len = 3000

        # Insertion on circular plasmid at coordinate 150:
        s0, e0, wraps = validate_interval(
            150, 150, record_len, topology="circular", task_kind="insertion"
        )
        self.assertEqual((s0, e0, wraps), (150, 150, False))

        # Insertion on linear fragment at coordinate 200:
        s0, e0, wraps = validate_interval(
            200, 200, record_len, topology="linear", task_kind="plasmid_insert"
        )
        self.assertEqual((s0, e0, wraps), (200, 200, False))

        # Generic task rejecting zero-width on circular plasmid without whole-record approval:
        with self.assertRaises(PlanningError):
            validate_interval(
                150, 150, record_len, topology="circular", task_kind="generic"
            )

    def test_guardrail_severity_classification(self):
        """Verify quick_biological_sanity_check separates CRITICAL blockers from WARNINGS."""
        # Sequence with frameshift (not multiple of 3)
        frameshift_seq = "ATGAAACC"  # 8 bp
        res = quick_biological_sanity_check(frameshift_seq, is_cds=True)
        self.assertTrue(res["has_critical_error"])
        self.assertTrue(any(c["code"] == "BIO-01-FRAMESHIFT" for c in res["critical_issues"]))

        # Plasmid missing replicon & marker
        rec = SeqRecord(Seq("ATGC" * 100), id="empty_plasmid", annotations={"topology": "circular"})
        res_plasmid = quick_biological_sanity_check(rec, is_cds=False)
        self.assertTrue(res_plasmid["has_critical_error"])
        self.assertTrue(any(c["code"] == "BIO-08-REPLICON_MISSING" for c in res_plasmid["critical_issues"]))

        # Sequence with U6 poly-T terminator (warning, not fatal CDS blocker)
        u6_seq = "ATGC" * 10 + "TTTTT" + "ATGC" * 10
        res_u6 = quick_biological_sanity_check(u6_seq, check_u6_termination=True, is_cds=False)
        self.assertFalse(res_u6["has_critical_error"])
        self.assertTrue(any(w["code"] == "BIO-06-POL3_TERMINATOR" for w in res_u6["warnings"]))

    def test_architectural_decoupling_no_core_to_scripts_inversion(self):
        """Verify that no file in core/ imports from scripts/."""
        core_dir = SKILL_ROOT / "core"
        py_files = list(core_dir.rglob("*.py"))
        self.assertGreater(len(py_files), 10, "Should find all core python files")

        violations = []
        for f in py_files:
            content = f.read_text(encoding="utf-8", errors="ignore")
            for line_no, line in enumerate(content.splitlines(), start=1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if "import scripts" in stripped or "from scripts" in stripped:
                    violations.append(f"{f.name}:{line_no}: {stripped}")

        self.assertEqual(
            violations,
            [],
            f"Found forbidden layer-inversion imports from scripts in core:\n" + "\n".join(violations),
        )


    def test_fill_or_chew_overhang_fidelity(self):
        """Verify enzymatic end repair blunting for both 5' fill-in and 3' chew-back."""
        from core.tools.restriction import fill_or_chew_overhang

        # 1. 5' fill-in: 5' AATT overhang filled in
        with self.assertRaises(ValueError):
            fill_or_chew_overhang("CCCC", left_overhang="AATT", right_overhang="GGCC", overhang_type="5prime", action="fill_in")
        res_fill = fill_or_chew_overhang("AATTCCCC", left_overhang="AATT", right_overhang="GGCC", overhang_type="5prime", action="fill_in")
        self.assertEqual(res_fill.analysis['end_type'], "blunt")
        self.assertEqual(str(res_fill.only_product().seq), "AATTCCCCGGCC")

        # 2. 5' fill-in does not duplicate overhang if already present
        # Complete top-strand sequence includes its left 5' extension. The
        # right 5' extension belongs to the bottom strand and is synthesized.
        res_no_dup = fill_or_chew_overhang("AATTCCCCGGCC", left_overhang="AATT", right_overhang="GGCC", overhang_type="5prime", action="fill_in")
        self.assertEqual(str(res_no_dup.only_product().seq), "AATTCCCCGGCCGGCC")

        # 3. 3' chew-back: removes 3' single-stranded tails
        res_chew = fill_or_chew_overhang("AATTCCCCGGCC", left_overhang="AATT", right_overhang="GGCC", overhang_type="3prime", action="chew_back")
        self.assertEqual(str(res_chew.only_product().seq), "AATTCCCC")

        # 4. Incompatible action (e.g. 5' chew-back with T4 pol) does not corrupt sequence
        with self.assertRaises(ValueError):
            fill_or_chew_overhang("CCCC", left_overhang="AATT", overhang_type="5prime", action="chew_back")

    def test_golden_gate_and_overhang_compatibility(self):
        """Verify check_overhang_compatibility handles both Golden Gate top-strand motif and opposite strand annealing."""
        from core.tools.restriction import check_overhang_compatibility

        # 1. Golden Gate Type IIS top-strand convention: matching 4-bp junctions (e.g. BsaI AATG and AATG)
        res_gg = check_overhang_compatibility("AATG", "AATG", type1="5prime", type2="5prime")
        self.assertTrue(res_gg.analysis["compatible"], "Identical Golden Gate junction motifs must be compatible")

        # 2. Opposite strand physical extension convention: AATG and CATT (reverse complement)
        res_opp = check_overhang_compatibility("AATG", "CATT", type1="5prime", type2="5prime")
        self.assertTrue(res_opp.analysis["compatible"], "Reverse complement single-stranded overhangs must be compatible")

        # 3. Mismatched overhangs
        res_mismatch = check_overhang_compatibility("AATG", "GGCC", type1="5prime", type2="5prime")
        self.assertFalse(res_mismatch.analysis["compatible"])

    def test_extract_homology_arms_circular_wrap(self):
        """Verify extract_homology_arms wraps around origin on circular plasmids instead of truncating."""
        from core.tools.crispr import extract_homology_arms

        # Circular plasmid of length 1000 bp, cut site at bp 10 (near origin)
        plasmid_seq = "A" * 990 + "GGGGGGGGGG"  # last 10 bp are G
        # Cut at bp 5: left arm of length 30 must wrap around origin to take bases from end
        res = extract_homology_arms(plasmid_seq, cut_position_0based=5, left_arm_length=30, right_arm_length=30, circular=True)
        self.assertEqual(res.analysis["left_arm_length"], 30, "Left arm must not be truncated on circular plasmid")
        self.assertEqual(res.analysis["right_arm_length"], 30, "Right arm must not be truncated")
        # Left arm spans bp 975..1000 + 0..5 (25 bp of end + 5 bp of start = 30 bp)
        self.assertEqual(len(res.analysis["left_homology_arm"]), 30)

    def test_c_terminal_tag_cleavage_order(self):
        """Verify C-terminal tag with protease cleavage places cleavage site adjacent to CDS.

        Order must be CDS + Cleavage + [Linker] + Tag so protease digestion leaves no permanent linker scar on CDS.
        """
        target_cds = "ATGGTGAGCAAGGGCGAGTAA"
        res = recipe_protein_tagging(
            target_cds_seq_or_file=target_cds,
            tag_name_or_seq="6xHis",
            tag_position="C-terminal",
            linker_type="flexible_G4S_x1",
            protease_cleavage="TEV",
            include_kozak=False,
            terminal_stop_codon="TAA",
        )
        product = res["product_sequence"]
        # TEV DNA: GAAAACCTGTATTTTCAGGGC
        tev_dna = "GAAAACCTGTATTTTCAGGGC"
        cds_core = target_cds[:-3]  # stripped stop
        self.assertTrue(product.startswith(cds_core), "Product must start with Target CDS")
        idx_cds_end = len(cds_core)
        self.assertEqual(product.find(tev_dna), idx_cds_end, "TEV cleavage site must immediately follow Target CDS to avoid linker scar")


if __name__ == "__main__":
    unittest.main()
