# -*- coding: utf-8 -*-
"""v0.8.0-dev2 tests: schemas, Cas-OFFinder parser, scoring gate, protocol evidence."""

from repository_paths import PROJECT_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS
import json
import pathlib
import sys
import tempfile
import unittest

from jsonschema import Draft202012Validator, validate as schema_validate
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

HERE = pathlib.Path(__file__).resolve().parent
ROOT = SKILL_ROOT
SCRIPTS = ROOT / "scripts"
SCHEMAS = ROOT / "schemas"
sys.path.insert(0, str(SCRIPTS))

import cas_offinder_adapter  # noqa: E402
import guide_scoring  # noqa: E402
import protocol_evidence  # noqa: E402
import recommend_protocol  # noqa: E402


def load_schema(name):
    with open(SCHEMAS / name, encoding="utf-8") as handle:
        return json.load(handle)


class SchemaPositiveTests(unittest.TestCase):
    def test_all_v08_schemas_validate_examples(self):
        provenance_schema = load_schema("provenance-v0.8.json")
        guide_schema = load_schema("guide-design-result-v0.8.json")
        off_schema = load_schema("offtarget-result-v0.8.json")
        reaction_schema = load_schema("reaction-profile-v0.8.json")
        protocol_schema = load_schema("protocol-recommendation-v0.8.json")
        report_schema = load_schema("crispr-design-report-v0.8.json")

        src = {"source_type": "software", "name": "Test", "role": "x",
               "status": "verified"}
        schema_validate(src, provenance_schema)

        guide = {"schema_version": "0.8.0", "nuclease": "spcas9-wt",
                 "candidate_count": 0, "candidates": [],
                 "provenance": [src]}
        schema_validate(guide, guide_schema)

        off = {"schema_version": "0.8.0", "status": "unavailable",
               "reference_genome": {"status": "ready", "fasta_sha256": "A" * 64},
               "provenance": [src]}
        schema_validate(off, off_schema)

        profile = {"schema_version": "0.8.0", "fragment_id": "f",
                   "length": 10, "gc_percent": 50.0,
                   "provenance": [src]}
        schema_validate(profile, reaction_schema)

        proto = {"schema_version": "0.8.0", "status": "unavailable",
                 "recommendations": [], "provenance": [src]}
        schema_validate(proto, protocol_schema)

        report = {"schema_version": "0.8.0", "status": "complete",
                  "task_summary": "t",
                  "inputs": [], "nuclease": "spcas9-wt",
                  "guide_candidates": [], "on_target": {},
                  "off_target": {}, "reaction_profiles": [],
                  "protocol_recommendation": {},
                  "sequence_upload": {}, "unfinished_analysis": [],
                  "limitations": [], "human_review_required": [],
                  "provenance": [src]}
        schema_validate(report, report_schema)


class SchemaNegativeTests(unittest.TestCase):
    def test_five_negative_cases_each(self):
        provenance_schema = load_schema("provenance-v0.8.json")
        off_schema = load_schema("offtarget-result-v0.8.json")
        protocol_schema = load_schema("protocol-recommendation-v0.8.json")
        validator = Draft202012Validator(provenance_schema)
        base = {"source_type": "software", "name": "Test", "role": "x",
                "status": "verified"}
        bad_cases = [
            dict(base, source_type="AI"),
            dict(base, status="latest"),
            dict(base, name=""),
            {k: v for k, v in base.items() if k != "role"},
            dict(base, extra=1),
        ]
        for bad in bad_cases:
            self.assertTrue(list(validator.iter_errors(bad)))

        off_validator = Draft202012Validator(off_schema)
        off = {"schema_version": "0.8.0", "status": "complete",
               "reference_genome": {"status": "ready", "fasta_sha256": "A" * 64},
               "provenance": [base]}
        for bad in [
            {**off, "status": "complete", "reference_genome": {}},
            {**off, "status": "complete", "reference_genome": None},
            {**off, "status": "maybe"},
            {k: v for k, v in off.items() if k != "provenance"},
            dict(off, extra=1),
        ]:
            self.assertTrue(list(off_validator.iter_errors(bad)))

        proto_validator = Draft202012Validator(protocol_schema)
        proto = {"schema_version": "0.8.0", "status": "unavailable",
                 "recommendations": [], "provenance": [base]}
        for bad in [
            {**proto, "status": "guaranteed"},
            {**proto, "recommendations": "no"},
            {**proto, "schema_version": "0.7.0"},
            {k: v for k, v in proto.items() if k != "provenance"},
            dict(proto, extra=1),
        ]:
            self.assertTrue(list(proto_validator.iter_errors(bad)))


class CasOffinderParserTests(unittest.TestCase):
    def test_parse_v24_6col_and_v30_9col(self):
        v24 = "GCATCGATCGATCGATCGTAAGG\tchrI\t11\tGCATCGATCGATCGATCGTgAGG\t+\t1\n"
        hits, error = cas_offinder_adapter.parse_output(v24)
        self.assertIsNone(error)
        self.assertEqual(hits[0]["start"], 11)
        self.assertEqual(hits[0]["end"], 34)
        self.assertEqual(hits[0]["mismatches"], 1)
        self.assertEqual(hits[0]["mismatch_positions"], [19])
        v24_label = v24.strip() + "\tq1\n"
        hits, error = cas_offinder_adapter.parse_output(v24_label)
        self.assertIsNone(error)
        self.assertEqual(len(hits), 1)
        v30 = ("##Generated by Cas-OFFinder 3.0.0\n"
               "#Id\tBulge Type\tcrRNA\tDNA\tChromosome\tLocation\t"
               "Direction\tMismatches\tBulge Size\n"
               "q1\tDNA\tGCATCGATCGATCGATCGTAANN\t"
               "GCATCGATCGAAATCGATCGTAAGG\tchrI\t11\t+\t0\t2\n")
        hits, error = cas_offinder_adapter.parse_output(v30)
        self.assertIsNone(error)
        self.assertEqual(hits[0]["start"], 11)
        self.assertEqual(hits[0]["bulge_type"], "DNA")
        self.assertEqual(hits[0]["bulge_size"], 2)

    def test_bad_output_reports_structured_error(self):
        hits, error = cas_offinder_adapter.parse_output("bad line\n")
        self.assertIsNone(hits)
        self.assertIn("EXTERNAL_OUTPUT_PARSE_ERROR", error)

    def test_genome_record_binds_sha_and_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            fasta = pathlib.Path(tmp) / "ref.fa"
            fasta.write_text(">chr1\nACGTACGT\n>chr2\nACGT\n")
            record = cas_offinder_adapter.genome_record(str(fasta))
            self.assertEqual(record["sequence_count"], 2)
            self.assertEqual(record["total_length"], 12)
            self.assertEqual(len(record["fasta_sha256"]), 64)


class ScoringGateTests(unittest.TestCase):
    def test_lbcas12a_has_no_model(self):
        results = guide_scoring.score_guides([{"id": "g1"}], "lbcas12a-wt")
        self.assertEqual(results[0]["on_target_scores"][0]["status"], "unavailable")
        self.assertEqual(
            results[0]["on_target_scores"][0]["reason"],
            "no-reviewed-model-selected-for-lbcas12a")

    def test_ascas12a_does_not_use_cas9_model(self):
        results = guide_scoring.score_guides([{"id": "g1"}], "ascas12a-wt")
        self.assertNotIn("Doench-2016",
                         [score["model"] for score in results[0]["on_target_scores"]])

    def test_spcas9_allows_only_cas9_models(self):
        results = guide_scoring.score_guides([{"id": "g1"}], "spcas9-wt")
        models = {score["model"] for score in results[0]["on_target_scores"]}
        self.assertEqual(models, {"Doench-2016"})


class ProtocolEvidenceTests(unittest.TestCase):
    def test_packaged_evidence_has_required_fields(self):
        sources = protocol_evidence.load_sources()
        self.assertGreaterEqual(len(sources), 2)
        for item in sources:
            self.assertTrue(item["url"])
            self.assertTrue(item["title"])
            self.assertTrue(item["provider"])
            self.assertTrue(item["retrieved_at"])

    def test_recommendation_uses_loaded_source(self):
        sources = protocol_evidence.load_sources()
        result = recommend_protocol.recommend(
            [{"fragment_id": "f1", "template_type": "pcr-template",
              "length": 800}], sources)
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["recommendations"][0]["status"],
                         "compatible_candidate")
        self.assertTrue(result["recommendations"][0]["source"]["url"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
