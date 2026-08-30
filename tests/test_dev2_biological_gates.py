# -*- coding: utf-8 -*-
"""v0.9.0-dev2 regression tests for biological fail-closed gates."""
import argparse
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPTS))

from Bio.Seq import Seq  # noqa: E402
from Bio.SeqFeature import FeatureLocation, SeqFeature  # noqa: E402
from Bio.SeqRecord import SeqRecord  # noqa: E402

import codon_optimize  # noqa: E402
import design_gene_replacement  # noqa: E402
import generate_crispr_design_report  # noqa: E402
import pcr_strategy  # noqa: E402
import recommend_protocol  # noqa: E402
import validate_construct  # noqa: E402
from planning.executor import execute_assembly  # noqa: E402
from planning.planner import _extract_region  # noqa: E402
from assembly_model import (  # noqa: E402
    AssemblyError, check_gibson_overlaps, gibson_fragment,
)


def rec(sequence, name="r", circular=False, features=()):
    item = SeqRecord(Seq(sequence), id=name, name=name)
    item.annotations["molecule_type"] = "DNA"
    item.annotations["topology"] = "circular" if circular else "linear"
    item.features = list(features)
    return item


class ReplacementGateTests(unittest.TestCase):
    def test_reverse_target_orientation_and_biology_context(self):
        target = SeqFeature(
            FeatureLocation(30, 45, strand=-1), type="CDS",
            qualifiers={"label": ["target"]})
        template = rec("A" * 80, features=[target])
        replacement = "ATG" + "GCT" * 3 + "TAA"
        result = design_gene_replacement.design_replacement(
            template, replacement, flank=20, gene="target", biology={
                "host_species": "Saccharomyces cerevisiae",
                "strain": "S288C", "ploidy": "haploid",
                "locus": "target", "essentiality_status": "nonessential",
                "essentiality_evidence": "user-provided nonessentiality record",
                "complemented": False,
                "complementation_strategy": "not-required-nonessential",
            })
        self.assertEqual(result["biology"]["status"], "ready")
        self.assertEqual(result["replacement"]["sequence"],
                         str(Seq(replacement).reverse_complement()))
        self.assertEqual(result["replacement"]["inserted_genomic_strand"], -1)

    def test_final_replacement_requires_context(self):
        target = SeqFeature(FeatureLocation(30, 45, strand=1), type="CDS",
                            qualifiers={"label": ["target"]})
        template = rec("A" * 80, features=[target])
        result = design_gene_replacement.design_replacement(
            template, "ATGGCTGCTTAA", flank=20, gene="target")
        self.assertEqual(result["biology"]["status"], "blocked")
        self.assertTrue(result["biology"]["errors"])

    def test_circular_flank_cross_origin_is_explicitly_blocked(self):
        target = SeqFeature(FeatureLocation(2, 12, strand=1), type="CDS",
                            qualifiers={"label": ["target"]})
        template = rec("A" * 40, circular=True, features=[target])
        with self.assertRaisesRegex(
                ValueError, "TARGET_FLANK_CROSS_ORIGIN_UNSUPPORTED"):
            design_gene_replacement.design_replacement(
                template, "ATGGCTGCTTAA", flank=5, gene="target",
                biology={"host_species": "Saccharomyces cerevisiae",
                         "strain": "S288C", "locus": "target",
                         "ploidy": "haploid",
                         "essentiality_status": "nonessential",
                         "essentiality_evidence": "user-provided record",
                         "complemented": False,
                         "complementation_strategy": "not-required-nonessential"})


class AssemblyExecutorTests(unittest.TestCase):
    def test_gibson_product_is_unique_contribution_product(self):
        overlap = "ACGT" * 5
        a = rec("AAAA" + overlap, "a")
        # The overlap is a PCR tail, not a duplicated source segment.  The
        # executor adds it to the downstream synthetic PCR product and removes
        # it once during assembly.
        b = rec("GGGG", "b")
        fragments = [
            {"name": "a", "sequence": str(a.seq), "length": len(a.seq),
             "role": "backbone", "source_path": "a.gb",
             "source_interval": [0, len(a.seq)], "_source_record": a},
            {"name": "b", "sequence": str(b.seq), "length": len(b.seq),
             "role": "insert", "source_path": "b.gb",
             "source_interval": [0, len(b.seq)], "_source_record": b},
        ]
        result = execute_assembly(
            fragments, "gibson", "linear",
            junctions=[{"sequence": overlap, "length": len(overlap)}])
        self.assertEqual(result["status"], "validated")
        self.assertEqual(result["sequence"], "AAAA" + overlap + "GGGG")
        self.assertEqual(result["executor"], "scripts.simulate_cloning.gibson")

    def test_short_overlap_is_blocked_before_execution(self):
        with self.assertRaises(Exception) as ctx:
            execute_assembly(
                [{"name": "a", "sequence": "AAAACCCC", "length": 8},
                 {"name": "b", "sequence": "CCCCGGGG", "length": 8}],
                "gibson", "linear",
                junctions=[{"sequence": "CCCC", "length": 4}])
        self.assertEqual(ctx.exception.code, "OVERLAP_TOO_SHORT_FOR_EXECUTION")

    def test_overlap_alias_has_same_hard_floor_as_gibson(self):
        fragments = [gibson_fragment("a", "AAAAA"),
                     gibson_fragment("b", "AAAAA")]
        with self.assertRaises(AssemblyError) as ctx:
            check_gibson_overlaps(fragments, 1, method="overlap")
        self.assertEqual(ctx.exception.code, "OVERLAP_TOO_SHORT_FOR_EXECUTION")


class BoundaryAndReportTests(unittest.TestCase):
    def test_circular_interval_crosses_origin_deterministically(self):
        template = rec("ACGTACGTAC", circular=True)
        sequence, start, end = _extract_region(
            template, {"interval": [8, 2]}, 0)
        self.assertEqual(sequence, "ACAC")
        self.assertEqual((start, end), (8, 2))

    def test_crispr_coverage_reports_truncation(self):
        candidates = [{"id": "g%03d" % i,
                       "protospacer_sequence": "A" * 20}
                      for i in range(60)]
        args = argparse.Namespace(
            reference_fasta="reference.fa", cas_offinder="cas-offinder",
            offinder_device="C0", mismatches=3, dna_bulge=0, rna_bulge=0,
            max_offtarget_candidates=50, rebuild_stale_index=True,
            annotation=None, target_gene=None, nuclease="spcas9-wt")
        with mock.patch.object(
                generate_crispr_design_report, "offinder_detect",
                return_value={"installed": True, "provenance": []}), \
             mock.patch.object(
                 generate_crispr_design_report, "search_offtargets",
                 return_value={"status": "complete", "hits": [],
                               "reference_genome": {"sha256": "X"}}):
            result = generate_crispr_design_report._offtarget_analysis(
                rec("A" * 100), candidates, args)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["coverage"]["candidate_total"], 60)
        self.assertEqual(result["coverage"]["candidate_searched"], 50)
        self.assertTrue(result["coverage"]["truncated"])
        self.assertEqual(result["reason"], "OFFTARGET_CANDIDATES_TRUNCATED")

    def test_complete_cds_requires_start_and_stop_but_partial_is_waived(self):
        complete = rec("AAAACCCCGGGG", features=[
            SeqFeature(FeatureLocation(0, 9), type="CDS",
                       qualifiers={"label": ["bad"]})])
        result = validate_construct.validate(complete)
        errors = {item["check"] for item in result["checks"]
                  if item["status"] == "error"}
        self.assertIn("cds_start_codon", errors)
        self.assertIn("cds_stop_codon", errors)
        partial = rec("AAAACCCCGGGG", features=[
            SeqFeature(FeatureLocation(0, 9), type="CDS",
                       qualifiers={"label": ["partial"], "partial": ["true"]})])
        self.assertTrue(validate_construct.validate(partial)["summary"]["pass"])

    def test_cds_translation_qualifier_mismatch_is_error(self):
        feature = SeqFeature(
            FeatureLocation(0, 12, strand=1), type="CDS",
            qualifiers={"label": ["bad_translation"],
                        "translation": ["MKK"],
                        "transl_table": ["11"]})
        result = validate_construct.validate(
            rec("ATGGCTAAATAA", features=[feature]))
        self.assertTrue(any(
            item["check"] == "cds_translation_mismatch" and
            item["status"] == "error" for item in result["checks"]))

    def test_explicit_fragment_annotation_waives_complete_orf_gate(self):
        feature = SeqFeature(
            FeatureLocation(0, 9, strand=1), type="CDS",
            qualifiers={"label": ["lacZalpha"],
                        "product": ["lacZ alpha fragment"]})
        result = validate_construct.validate(
            rec("AAAACCCCG", features=[feature]))
        errors = {item["check"] for item in result["checks"]
                  if item["status"] == "error"}
        self.assertNotIn("cds_start_codon", errors)
        self.assertNotIn("cds_stop_codon", errors)


class RecommendationAndCodonTests(unittest.TestCase):
    def test_protocol_without_length_or_fragment_count_does_not_match(self):
        sources = [{"provider": "X", "title": "Q5", "applicable_to":
                    ["high-fidelity-cloning-pcr"]}]
        result = recommend_protocol.recommend(
            [{"fragment_id": "x", "template_type": "pcr-template"}], sources)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["recommendations"][0]["status"],
                         "insufficient_evidence")

    def test_invalid_pcr_profile_is_structured_failure(self):
        result = pcr_strategy.recommend_pcr_strategy(
            {"length": 0, "gc_percent": 101})
        self.assertEqual(result["status"], "invalid-input")
        self.assertIsNone(result["protocol"])

    def test_codon_table_uses_source_backed_preferred_codons(self):
        optimized, _unknown = codon_optimize.optimize_aa("KR", codon_optimize.CODON_TABLES["ecoli"])
        self.assertEqual(optimized, "AAACGC")
        self.assertEqual(codon_optimize.CODON_TABLE_METADATA["yeast"]["status"],
                         "source-backed-preferred-codon-only")


if __name__ == "__main__":
    unittest.main(verbosity=2)
