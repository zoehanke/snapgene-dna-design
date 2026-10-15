# -*- coding: utf-8 -*-
"""Destructive/edge input tests for v0.8/v0.9 surfaces."""

from repository_paths import PROJECT_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

HERE = pathlib.Path(__file__).resolve().parent
ROOT = SKILL_ROOT
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPTS))

import cas_offinder_adapter  # noqa: E402
import design_guides  # noqa: E402
import pcr_strategy  # noqa: E402
import primer_design_engine  # noqa: E402
import sequence_upload_consent  # noqa: E402
from planning.intent import normalize_intent, parse_intent_text  # noqa: E402
from planning.planner import plan_assembly  # noqa: E402
from rules.engine import evaluate_plan  # noqa: E402


def record(seq, circular=True):
    rec = SeqRecord(Seq(seq), id="rec", name="rec")
    rec.annotations = {"molecule_type": "DNA",
                       "topology": "circular" if circular else "linear"}
    return rec


class DesignGuidesDestructiveTests(unittest.TestCase):
    def test_empty_sequence(self):
        self.assertEqual(design_guides.scan_guides(
            record("", circular=False), "spcas9-wt"), [])

    def test_all_n_and_repeat_boundary(self):
        self.assertEqual(design_guides.scan_guides(
            record("N" * 30), "spcas9-wt"), [])
        candidates = design_guides.scan_guides(
            record("AGG" + "C" * 20, circular=True), "spcas9-wt")
        self.assertTrue(candidates)
        for candidate in candidates:
            for key in ("protospacer_start", "protospacer_end",
                        "pam_start", "pam_end"):
                self.assertLessEqual(candidate["coordinates"][key], 23)

    def test_region_zero_length_and_boundaries(self):
        self.assertEqual(design_guides.scan_guides(
            record("ACGT" * 10), "spcas9-wt", region=(5, 5)), [])
        with self.assertRaises(ValueError):
            design_guides.scan_guides(record("ACGT" * 10), "spcas9-wt",
                                      region=(0, 100))


class CasOffinderDestructiveTests(unittest.TestCase):
    def test_invalid_parameters_and_query(self):
        with tempfile.TemporaryDirectory() as tmp:
            fasta = pathlib.Path(tmp) / "ref.fa"
            fasta.write_text(">chr1\nACGTACGTACGT\n")
            with self.assertRaises(ValueError):
                cas_offinder_adapter.search_offtargets(
                    "ACGT", fasta, "not-dict")
            result = cas_offinder_adapter.search_offtargets(
                "ACGTACGTACGTACGTACGTN", fasta, {"mismatches": 3},
                nuclease_id="spcas9-wt")
            self.assertEqual(result["status"], "failed")
            self.assertIn("QUERY", result["reason"])

    def test_missing_fasta_is_structured(self):
        result = cas_offinder_adapter.search_offtargets(
            "ACGTACGTACGTACGTACGT", "Z:\\nope\\missing.fa",
            {"mismatches": 3})
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["reason"], "REFERENCE_FASTA_NOT_FOUND")

    def test_parse_output_empty_and_bad_columns(self):
        hits, error = cas_offinder_adapter.parse_output("")
        self.assertEqual(hits, [])
        self.assertIn("EMPTY", error)
        for bad in ["\t".join(["a"] * 5) + "\n",
                    "q\tchr\t0\tACGT\t+\tnotint\n",
                    "q\tchr\t-1\tACGT\t+\t1\n"]:
            self.assertIsNone(cas_offinder_adapter.parse_output(bad)[0])


class PrimerEngineDestructiveTests(unittest.TestCase):
    def test_short_and_empty_regions(self):
        with self.assertRaises(ValueError):
            primer_design_engine.design_region_primers("A" * 10, 0)
        with self.assertRaises(ValueError):
            primer_design_engine.design_region_primers(
                "A" * 50, 45, min_len=18)
        with self.assertRaises(ValueError):
            primer_design_engine.design_region_primers(
                "A" * 50, -1, min_len=18)

    def test_unknown_enzyme_and_long_tail(self):
        with self.assertRaises(ValueError):
            primer_design_engine.restriction_tail(["BADENZYME"])
        tail = primer_design_engine.restriction_tail(["EcoRI", "BamHI"])
        self.assertIn("GAATTC", tail)
        self.assertIn("GGATCC", tail)

    def test_homopolymer_fallback_is_structured(self):
        from operation_consent import ConsentBroker
        result = primer_design_engine.design_region_primers(
            "A" * 100, 10, min_len=10, max_len=15, top_n=1,
            consent=ConsentBroker(policy="auto"))
        self.assertEqual(result["backend"], "heuristic")
        self.assertIn("validation", result)
        self.assertTrue(any(
            entry.get("category") == "degradation"
            for entry in result["operation_log"]))


class ConsentDestructiveTests(unittest.TestCase):
    def test_none_and_empty_uploads_are_denied(self):
        consent = sequence_upload_consent.SequenceUploadConsent()
        consent.request("https://x", "p", sequence="")
        consent.approve()
        self.assertFalse(consent.allowed("https://x", "p", ""))
        self.assertFalse(consent.allowed("https://x", "p", None))
        self.assertFalse(consent.allowed(None, "p", "ACGT"))
        self.assertFalse(consent.allowed("https://x", None, "ACGT"))


class RulesDestructiveTests(unittest.TestCase):
    def test_eval_is_sandboxed(self):
        result = evaluate_plan({"fragment_count": 2, "method": "gibson",
                                "internal_site_count": 0,
                                "min_overlap_length": 20,
                                "max_overlap_length": 20,
                                "min_overlap_gc": 50,
                                "max_overlap_gc": 50,
                                "max_fragment_length": 1000,
                                "total_length": 2000,
                                "any_primer_tm_outside_52_72": False,
                                "any_primer_strong_structure": False})
        self.assertIn(result["grade"], ("high", "medium", "low"))
        with tempfile.TemporaryDirectory() as tmp:
            rules_dir = pathlib.Path(tmp)
            (rules_dir / "evil.json").write_text(json.dumps({
                "rules": [{"id": "evil", "constraint": "x",
                           "check": "__import__('os').system('echo bad')",
                           "severity": "error", "suggestion": "",
                           "source": "test"}]}), encoding="utf-8")
            result = evaluate_plan({}, rules_dir)
            self.assertFalse(any(h["rule_id"] == "evil"
                                 for h in result["errors"]))


class PcrStrategyDestructiveTests(unittest.TestCase):
    def test_non_finite_and_negative_length(self):
        result = pcr_strategy.recommend_pcr_strategy(
            {"length": -5, "gc_percent": float("nan")})
        self.assertEqual(result["status"], "invalid-input")
        self.assertEqual(result["extension_time_seconds"], 0)
        self.assertIsNone(result["protocol"])
        self.assertEqual(pcr_strategy.extension_time_seconds(-1), 0)


class PlannerFuzzTests(unittest.TestCase):
    def test_random_intents_never_crash_with_bare_exceptions(self):
        from unittest import mock as umock
        for seed in range(25):
            with tempfile.TemporaryDirectory() as tmp:
                tmp = pathlib.Path(tmp)
                source = tmp / "s.gb"
                rec = record("".join(
                    ("ACGT"[hash((seed, i)) % 4] for i in range(200))),
                    "s%d" % seed)
                import Bio.SeqIO as SeqIO
                with open(source, "w", encoding="utf-8") as handle:
                    SeqIO.write(rec, handle, "genbank")
                intent = {
                    "method": ["auto", "overlap", "gibson", "golden_gate",
                               "digest-ligate"][seed % 5],
                    "backbone": {"source": 0,
                                 "interval": [0, 50 + seed]},
                    "fragments": [
                        {"source": 0, "interval": [60 + seed, 120 + seed]}]}
                with umock.patch(
                        "planning.planner.design_region_primers",
                        side_effect=lambda seq, start, **kwargs: {
                            "schema_version": "0.9.0",
                            "backend": "fake", "backend_status": "available",
                            "primer3_version": "fake", "primer3_failure": None,
                            "region": {"start": 0, "end": len(seq),
                                       "length": len(seq)},
                            "fwd_tail": "", "rev_tail": "",
                            "forward_candidates": [],
                            "reverse_candidates": [], "pairs": [],
                            "validation": {"forward": [], "reverse": []},
                            "provenance": []}):
                    try:
                        plan = plan_assembly([str(source)], intent)
                    except Exception as error:  # noqa: BLE001
                        self.assertIn(
                            type(error).__name__,
                            ("PlannerError", "ValueError", "OSError",
                             "KeyError"))
                    else:
                        self.assertIn("schema_version", plan)


class PlannerDestructiveTests(unittest.TestCase):
    def test_missing_source_file(self):
        with self.assertRaises(Exception):
            plan_assembly(["Z:/missing.gb"], normalize_intent({
                "backbone": {"source": 0}, "fragments": []}))

    def test_empty_fasta_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "empty.fa"
            path.write_text("")
            with self.assertRaises(Exception):
                plan_assembly([str(path)], normalize_intent({
                    "backbone": {"source": 0}, "fragments": []}))

    def test_bad_intent_text(self):
        for text in ["", "backbone=0", "method=alien;backbone=0;fragments=0"]:
            with self.assertRaises(Exception):
                parse_intent_text(text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
