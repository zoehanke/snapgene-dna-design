# -*- coding: utf-8 -*-
"""Small regressions for real-template PCR and mutagenesis preparation."""
import unittest
import random

from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

from core.recipes.mutagenesis import recipe_site_directed_mutagenesis
from core.tools.amplification import simulate_pcr
from core.tools.amplification import calc_primer_tm, check_primer_dimers, design_overhang_primers
from planning.executor import ExecutionError, execute_assembly


class RealWorkflowRepairTests(unittest.TestCase):
    def test_correct_strand_is_not_hidden_by_wrong_strand_longer_match(self):
        template = "G" * 5 + "ACGTACGTACGTACGTA" + "T" * 18
        template += "CCGTAACCGGTTACCGGA" + "A" * 5
        forward = "TTTT" + template[5:22]
        reverse = "GGGG" + str(Seq(template[40:57]).reverse_complement())
        result = simulate_pcr(template, forward, reverse)
        self.assertEqual(result["forward_binding"]["strand"], 1)
        self.assertEqual(result["template_interval_0based"], [5, 57])
        self.assertEqual(result["primers"][0]["sequence"], forward)
        self.assertEqual(result["primers"][1]["strand"], -1)
        self.assertEqual(result["template"]["sequence"], template)

    def test_ambiguous_products_require_explicit_positions(self):
        template = "A" * 20 + "GATTACA" * 4 + "C" * 20
        forward = "GAATTC" + "A" * 18
        reverse = "GCGGCCGC" + "G" * 18
        with self.assertRaisesRegex(ValueError, "ambiguity"):
            simulate_pcr(template, forward, reverse)
        with self.assertRaisesRegex(ValueError, "coordinate alone"):
            simulate_pcr(
                template,
                forward,
                reverse,
                forward_binding_start_0based=0,
                reverse_binding_start_0based=48,
            )

    def test_circular_pcr_keeps_feature_and_origin_metadata(self):
        rng = random.Random(20260909)
        template = "".join(rng.choice("ACGT") for _ in range(160))
        record = SeqRecord(Seq(template), id="circ")
        record.annotations.update({"molecule_type": "DNA", "topology": "circular"})
        record.features.append(
            SeqFeature(
                FeatureLocation(2, 30, strand=1),
                type="CDS",
                qualifiers={"label": ["feature"]},
            )
        )
        result = simulate_pcr(
            record,
            template[70:90],
            str(Seq(template[10:30]).reverse_complement()),
            topology="circular",
            forward_binding_start_0based=70,
            reverse_binding_start_0based=10,
        )
        self.assertTrue(result["wraps_origin"])
        self.assertEqual(result["template_topology"], "circular")
        self.assertTrue(any(feature["name"] == "feature" for feature in result["features"]))

    def test_quikchange_counts_only_actual_substitution_mismatch(self):
        template = "A" * 30 + "TAT" + "C" * 40
        record = SeqRecord(Seq(template), id="p")
        record.annotations.update({"molecule_type": "DNA", "topology": "circular"})
        result = recipe_site_directed_mutagenesis(record, 30, 33, "CAT")
        self.assertEqual(result["quality_checks"]["mismatch_base_count"], 1)
        self.assertEqual(result["details"]["method"], "quikchange")
        self.assertEqual(len(result["details"]["preparation"]), 1)
        self.assertEqual(result["details"]["preparation"][0]["product"]["topology"], "circular")

    def test_inverse_pcr_reports_full_plasmid_pcr_and_cyclization(self):
        rng = random.Random(20260910)
        template = "".join(rng.choice("ACGT") for _ in range(200))
        record = SeqRecord(Seq(template), id="p")
        record.annotations.update({"molecule_type": "DNA", "topology": "circular"})
        result = recipe_site_directed_mutagenesis(
            record, 2, 5, "CAT", method="inverse_pcr"
        )
        evidence = result["details"]["reaction_evidence"]
        self.assertEqual(evidence["reaction_model"], "full_plasmid_pcr_then_circularization")
        self.assertEqual(result["product_sequence"][2:5], "CAT")
        self.assertEqual(result["details"]["preparation"][0]["method"], "inverse_pcr")
        preparation_product = result["details"]["preparation"][0]["product"]
        self.assertEqual(preparation_product["topology"], "linear")
        self.assertEqual(preparation_product["sequence"], evidence["linear_intermediate_sequence"])
        self.assertEqual(result["product_topology"], "circular")
        self.assertEqual(result["details"]["circular_product"]["topology"], "circular")
        reminders = result["details"]["sop_reminders"]
        protocol = result["protocol_steps"]
        self.assertTrue(any("INVERSE_PCR_AMPLIFICATION" in item for item in reminders))
        self.assertTrue(any("KLD" in item for item in reminders))
        self.assertFalse(any("QuikChange" in item or "THERMOCYCLING" in item
                             for item in reminders + [step["action"] for step in protocol]))
        primers = result["details"]["primers"]
        self.assertEqual(primers[0]["qc_tm"], calc_primer_tm(primers[0]["binding_core"])["tm"])
        self.assertEqual(primers[1]["qc_tm"], calc_primer_tm(primers[1]["binding_core"])["tm"])

    def test_declared_golden_gate_pcr_cannot_fall_back_to_native_fragment(self):
        fragments = [
            {"name": "vector", "sequence": "A", "role": "backbone",
             "source_path": "vector", "_pcr_required": True},
            {"name": "insert", "sequence": "C", "role": "insert",
             "source_path": "insert", "_pcr_required": True},
        ]
        with self.assertRaises(ExecutionError) as raised:
            execute_assembly(
                fragments,
                "golden_gate",
                "circular",
                enzymes=["BsmBI"],
            )
        self.assertEqual(raised.exception.code, "PCR_PRODUCT_REQUIRED")

    def test_primer_selection_scores_complete_oligo_quality(self):
        rng = random.Random(20260907)
        template = "".join(rng.choice("ACGT") for _ in range(260))
        result = design_overhang_primers(
            template,
            start=20,
            end=230,
            fwd_5prime_overhang="GATCGTACGATCGTAGCTAGCTAGCTAGCT",
            rev_5prime_overhang="TCAGGATCCGATACCTGACCTGAGTCA",
            prefer_primer3=False,
        )
        fwd = result["forward_primer"]["full_sequence"]
        rev = result["reverse_primer"]["full_sequence"]
        dimer = check_primer_dimers(fwd, rev)
        self.assertLess(dimer["max_3prime_complementarity"], 4)
        self.assertTrue(result["forward_primer"]["unique_binding"])
        self.assertTrue(result["reverse_primer"]["unique_binding"])
        self.assertGreaterEqual(result["forward_primer"]["binding_core_tm"], 52.0)
        self.assertGreaterEqual(result["reverse_primer"]["binding_core_tm"], 52.0)
        self.assertIn("selected_pair_quality", result["primer3_metrics"])

    def test_repeated_binding_sites_fail_closed_without_unique_pair(self):
        with self.assertRaisesRegex(ValueError, "No unique complete primer pair"):
            design_overhang_primers(
                "ACGT" * 80,
                start=20,
                end=260,
                prefer_primer3=False,
            )


if __name__ == "__main__":
    unittest.main()
