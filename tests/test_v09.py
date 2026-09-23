# -*- coding: utf-8 -*-
"""v0.9.0 module tests: M1 planner, M2 rules, M3 primers, M4/M5/M6."""
import json
import os
import pathlib
import random
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPTS))

from planning.intent import normalize_intent, parse_intent_text  # noqa: E402
from planning.planner import plan_assembly as planner_plan_assembly, choose_overlap  # noqa: E402
from operation_consent import ConsentBroker  # noqa: E402
from rules.engine import evaluate_plan, load_rules  # noqa: E402
import pcr_strategy  # noqa: E402
import parts_library  # noqa: E402
import online_sources  # noqa: E402
from planning import manual_render  # noqa: E402
import plan_assembly as plan_cli  # noqa: E402


def record(seq, name="rec", circular=True, feature=None):
    rec = SeqRecord(Seq(seq), id=name, name=name)
    rec.annotations["molecule_type"] = "DNA"
    rec.annotations["topology"] = "circular" if circular else "linear"
    if feature:
        rec.features.append(feature)
    return rec


def random_seq(length, seed):
    random.seed(seed)
    return "".join(random.choice("ACGT") for _ in range(length))


def auto_consent():
    return ConsentBroker(policy="auto")


def write_gb(rec, directory, name):
    path = pathlib.Path(directory) / name
    with open(path, "w", encoding="utf-8") as handle:
        SeqIO.write(rec, handle, "genbank")
    return str(path)


def fake_primer_result(fragment, fwd_tail="", rev_tail=""):
    fragment = str(fragment).upper()
    fwd_binding = fragment[:18]
    rev_binding = str(Seq(fragment[-18:]).reverse_complement())
    return {
        "schema_version": "0.9.0", "backend": "primer3-core",
        "backend_status": "available", "primer3_version": "2.6.1",
        "primer3_failure": None,
        "region": {"start": 0, "end": len(fragment), "length": len(fragment)},
        "fwd_tail": fwd_tail, "rev_tail": rev_tail,
        "forward_candidates": [{
            "side": "forward", "binding": fwd_binding,
            "tail": fwd_tail, "sequence": fwd_tail + fwd_binding,
            "tm": 60.0, "gc": 50.0, "length": len(fwd_tail) + 18, "binding_length": 18,
            "bind_start": 0, "bind_end": 17,
            "hairpin": {"tm": 0.0}, "self_dimer": {"tm_any": 0.0},
            "heterodimer": {"tm_any": 0.0}, "recommended": "high",
            "_backend": "primer3-core"}],
        "reverse_candidates": [{
            "side": "reverse", "binding": rev_binding,
            "tail": rev_tail, "sequence": rev_tail + rev_binding,
            "tm": 60.0, "gc": 50.0, "length": len(rev_tail) + 18, "binding_length": 18,
            "bind_start": len(fragment) - 18, "bind_end": len(fragment) - 1,
            "hairpin": {"tm": 0.0}, "self_dimer": {"tm_any": 0.0},
            "heterodimer": {"tm_any": 0.0}, "recommended": "high",
            "_backend": "primer3-core"}],
        "pairs": [{"forward_index": 0, "reverse_index": 0,
                   "product_size": len(fragment),
                   "heterodimer": {"tm_any": 0.0}}],
        "validation": {"forward": [{"passed": True, "problems": [],
                                    "backend": "primer3-core"}],
                       "reverse": [{"passed": True, "problems": [],
                                    "backend": "primer3-core"}]},
        "provenance": [],
    }


class M2RuleTests(unittest.TestCase):
    def test_builtin_rules_load_with_sources(self):
        data = load_rules()
        self.assertGreaterEqual(len(data["rules"]), 8)
        for rule in data["rules"]:
            self.assertTrue(rule["source"])
            self.assertIn(rule["action"]["type"], ("block", "warn", "warn_and_confirm"))
            self.assertNotIn("check", rule)

    def test_overlap_4_fragments_is_error(self):
        context = {"method": "overlap", "fragment_count": 4,
                   "internal_site_count": 0, "min_overlap_length": 20,
                   "max_overlap_length": 20, "min_overlap_gc": 50,
                   "max_overlap_gc": 50, "max_fragment_length": 1000,
                   "total_length": 4000,
                   "any_primer_tm_outside_52_72": False,
                   "any_primer_strong_structure": False}
        result = evaluate_plan(context)
        self.assertTrue(any(item["rule_id"] == "overlap-fragment-count"
                            for item in result["errors"]))
        self.assertEqual(result["grade"], "low")

    def test_user_rules_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            rules_dir = pathlib.Path(tmp)
            (rules_dir / "custom.json").write_text(json.dumps({"rules": [{
                "schema_version": "1.0.0",
                "id": "custom-no-pcr", "name": "custom",
                "version": 1, "status": "active",
                "scope": {"type": "global"},
                "trigger": "assembly_feasibility",
                "when": {"field": "fragment_count", "operator": "gt",
                         "value": 1},
                "action": {"type": "warn", "message": "custom suggestion"},
                "source": {"type": "user-experience"}}]}), encoding="utf-8")
            result = evaluate_plan({"fragment_count": 2,
                                    "method": "gibson"}, rules_dir)
            self.assertTrue(any(item["rule_id"] == "custom-no-pcr"
                                for item in result["warnings"]))


class M1PlannerTests(unittest.TestCase):
    def _sources(self, tmp):
        backbone = record(random_seq(800, 2), "pBACKBONE")
        donor = record(random_seq(600, 4), "pDONOR",
                        feature=SeqFeature(
                            FeatureLocation(50, 550, strand=1), type="CDS",
                            qualifiers={"label": ["EGFP"], "gene": ["EGFP"]}))
        return (write_gb(backbone, tmp, "backbone.gb"),
                write_gb(donor, tmp, "donor.gb"))

    def test_mocked_core_metrics_cannot_certify_bad_complete_oligos(self):
        with tempfile.TemporaryDirectory() as tmp:
            sources = self._sources(pathlib.Path(tmp))
            intent = normalize_intent({
                "goal": "assemble EGFP", "method": "overlap",
                "backbone": {"source": 0},
                "fragments": [{"source": 1, "feature": "EGFP"}]})
            with mock.patch(
                    "planning.planner.design_region_primers",
                    side_effect=lambda seq, start, **kwargs:
                        fake_primer_result(seq, kwargs.get("fwd_tail", ""),
                                           kwargs.get("rev_tail", ""))):
                plan = planner_plan_assembly(sources, intent)
            # Mocked core-only zeroes must not certify the supplied bad pairs.
            # A separately checked anchored search may legitimately find a
            # different pair without changing the requested DNA.
            self.assertEqual(plan["status"], "complete")
            self.assertEqual(plan["assembly_strategy"]["method"], "overlap")
            rescued = [p for p in plan["primers"] if p.get("anchored_search")]
            self.assertTrue(rescued)
            for primer in rescued:
                self.assertTrue(primer["rejected_short_candidates"])
                self.assertTrue(all(not check["passed"] for check in primer["rejected_short_candidates"]))
                self.assertTrue(primer["complete_oligo_structure"]["passed"])
                self.assertTrue(primer["pcr_product"]["amplicon"])
                fragment = next(f for f in plan["fragment_assignments"] if f["name"] == primer["fragment"])
                f_tail = primer["forward"].get("tail") or ""
                r_tail = primer["reverse"].get("tail") or ""
                original_bad_pair = (f_tail + fragment["sequence"][:18],
                    r_tail + str(Seq(fragment["sequence"][-18:]).reverse_complement()))
                self.assertNotEqual((primer["forward"]["sequence"], primer["reverse"]["sequence"]),original_bad_pair)
                self.assertEqual(primer["pcr_product"]["amplicon"],
                    f_tail + fragment["sequence"] + str(Seq(r_tail).reverse_complement()))
            self.assertEqual(plan["final_construct"]["sequence"],
                             "".join(f["sequence"] for f in plan["fragment_assignments"]))
            self.assertEqual(len(plan["fragment_assignments"]), 2)
            self.assertTrue(plan["assembly_strategy"]["overlap_junctions"][0]
                            ["length"] >= 15)

    def test_four_fragment_overlap_auto_switch_gibson(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            source = write_gb(record(random_seq(2000, 5), "pMULTI"), tmp,
                              "multi.gb")
            intent = normalize_intent({
                "method": "overlap", "backbone": {"source": 0},
                "fragments": [{"source": 0, "interval": [10, 300]},
                              {"source": 0, "interval": [320, 700]},
                              {"source": 0, "interval": [720, 1200]}]})
            with mock.patch(
                    "planning.planner.design_region_primers",
                    side_effect=lambda seq, start, **kwargs:
                        fake_primer_result(seq, kwargs.get("fwd_tail", ""),
                                           kwargs.get("rev_tail", ""))):
                plan = planner_plan_assembly([source], intent)
            self.assertEqual(plan["assembly_strategy"]["method"], "gibson")
            self.assertTrue(any(alt["reason"].find("overlap") >= 0
                                for alt in plan["assembly_strategy"]
                                ["alternatives"]))

    def test_golden_gate_internal_bsai_switches_enzyme(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            # BsaI is present internally, while both parts have exactly two
            # BsmBI flanking sites. The planner must choose BsmBI and the
            # method-specific executor must complete the actual assembly.
            body_v = "GGTCTC" + ("ATGC" * 30)
            body_i = "ATGC" * 30
            vector = ("CGTCTC" + "A" + "AAAA" + body_v + "TTTT"
                      + "A" + "GAGACG")
            insert = ("CGTCTC" + "A" + "TTTT" + body_i + "AAAA"
                      + "A" + "GAGACG")
            vector_path = write_gb(record(vector, "pGG", circular=True),
                                   tmp, "gg-vector.gb")
            insert_path = write_gb(record(insert, "pINS", circular=False),
                                   tmp, "gg-insert.gb")
            intent = normalize_intent({
                "method": "golden_gate", "backbone": {"source": 0},
                "fragments": [{"source": 1}]})
            with mock.patch(
                    "planning.planner.design_region_primers",
                    side_effect=lambda seq, start, **kwargs:
                        fake_primer_result(seq, kwargs.get("fwd_tail", ""),
                                           kwargs.get("rev_tail", ""))):
                plan = planner_plan_assembly([vector_path, insert_path], intent)
            self.assertEqual(plan["assembly_strategy"]["method"],
                             "golden_gate")
            self.assertNotEqual(plan["assembly_strategy"]["enzymes"],
                                ["BsaI"])
            self.assertEqual(plan["status"], "complete")
            self.assertEqual(plan["execution"]["status"], "validated")

    def test_reverse_strand_feature_extraction_is_biological(self):
        from Bio.Seq import Seq as BioSeq
        seq = random_seq(300, 8)
        rec = record(seq, "pREV", feature=SeqFeature(
            FeatureLocation(50, 250, strand=-1), type="CDS",
            qualifiers={"label": ["REV"], "gene": ["REV"]}))
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            source = write_gb(rec, tmp, "rev.gb")
            intent = normalize_intent({
                "backbone": {"source": 0, "interval": [0, 50]},
                "fragments": [{"source": 0, "feature": "REV"}]})
            with mock.patch(
                    "planning.planner.design_region_primers",
                    side_effect=lambda seq, start, **kwargs:
                        fake_primer_result(seq, kwargs.get("fwd_tail", ""),
                                           kwargs.get("rev_tail", ""))):
                plan = planner_plan_assembly([source], intent)
            extracted = plan["fragment_assignments"][1]["sequence"]
            self.assertEqual(extracted,
                             str(BioSeq(seq[50:250]).reverse_complement()))

    def test_intent_text_parser(self):
        intent = parse_intent_text(
            "backbone=0;fragments=1:EGFP;method=gibson;name=pX")
        self.assertEqual(intent["method"], "gibson")
        self.assertEqual(intent["fragments"][0]["feature"], "EGFP")
        with self.assertRaises(ValueError):
            parse_intent_text("nothing useful")


class M3PrimerEngineTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("SNAPGENE_RUN_PRIMER3") == "1",
                         "set SNAPGENE_RUN_PRIMER3=1")
    def test_real_primer3_reproducible_and_in_range(self):
        import primer_design_engine
        seq = random_seq(800, 5)
        result = primer_design_engine.design_region_primers(
            seq, 100, top_n=1, consent=auto_consent())
        self.assertEqual(result["backend"], "primer3-core")
        pair = primer_design_engine.best_pair(result)
        self.assertTrue(pair)
        for side in ("forward", "reverse"):
            self.assertGreaterEqual(pair[side]["tm"], 52.0)
            self.assertLessEqual(pair[side]["tm"], 72.0)
        second = primer_design_engine.design_region_primers(
            seq, 100, top_n=1, consent=auto_consent())
        self.assertEqual(result["forward_candidates"][0]["sequence"],
                         second["forward_candidates"][0]["sequence"])

    def test_restriction_tail(self):
        import primer_design_engine
        tail = primer_design_engine.restriction_tail(["EcoRI"])
        self.assertIn("GAATTC", tail)
        with self.assertRaises(ValueError):
            primer_design_engine.restriction_tail(["NOPE"])


class Primer3TailRetryTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("SNAPGENE_RUN_PRIMER3") == "1",
                         "set SNAPGENE_RUN_PRIMER3=1")
    def test_tailed_design_retries_binding_only(self):
        import primer_design_engine
        seq = ("AGAACGATTGCCCGCAACGC"
               + "ACGATCGTAGCT" * 100
               + "TCGACGCAACCTTTCGTGCG")
        tail = str(Seq("TCGACGCAACCTTTCGTGCG").reverse_complement())
        result = primer_design_engine.design_region_primers(
            seq, 0, rev_tail=tail, top_n=1, consent=auto_consent())
        self.assertEqual(result["backend"], "primer3-core")
        self.assertIn("binding-only", result["primer3_retry_note"])
        self.assertEqual(
            result["reverse_candidates"][0]["sequence"][:len(tail)], tail)


class Primer3FailureModeTests(unittest.TestCase):
    def test_unavailable_primer3_is_explicit_fallback(self):
        import primer_design_engine
        with mock.patch.object(
                primer_design_engine, "probe_primer3_core",
                return_value={"status": "unavailable",
                              "backend": "primer3-core",
                              "path": None, "version": None,
                              "detail": "no primer3_core"}):
            result = primer_design_engine.design_region_primers(
                "A" * 20 + "CGTACGTACGTACGTACGTACGT" + "G" * 20,
                5, top_n=1, consent=auto_consent())
        self.assertEqual(result["backend"], "heuristic")
        self.assertEqual(result["backend_status"], "fallback")
        self.assertIn("no primer3_core", result["primer3_failure"])
        self.assertIn("NOT Primer3",
                      result["forward_candidates"][0]["_backend_source"])

    def test_require_primer3_fails_when_unavailable(self):
        import primer_design_engine
        with mock.patch.object(
                primer_design_engine, "probe_primer3_core",
                return_value={"status": "unavailable",
                              "backend": "primer3-core",
                              "path": None, "version": None,
                              "detail": "no primer3_core"}):
            with self.assertRaises(
                    primer_design_engine.Primer3CoreError):
                primer_design_engine.design_region_primers(
                    "A" * 20 + "CGTACGTACGTACGTACGTACGT" + "G" * 20,
                    5, top_n=1, require_primer3=True,
                    consent=auto_consent())


class M4StrategyTests(unittest.TestCase):
    def test_high_gc_and_at_and_long(self):
        high = pcr_strategy.recommend_pcr_strategy(
            {"length": 1000, "gc_percent": 78.0, "purpose": "cloning"})
        self.assertIn("GC", high["recommended_enzyme"])
        self.assertIn("High GC", high["recommended_enzyme"])
        self.assertIn("+ 3 C", high["annealing_strategy"])
        at = pcr_strategy.recommend_pcr_strategy(
            {"length": 1000, "gc_percent": 25.0, "purpose": "cloning"})
        self.assertIn("AT-rich", at["reason"])
        long_pcr = pcr_strategy.recommend_pcr_strategy(
            {"length": 12000, "gc_percent": 50.0, "purpose": "cloning"})
        self.assertIn("GXL", long_pcr["recommended_enzyme"])
        self.assertEqual(long_pcr["extension_time_seconds"], 360)
        for result in (high, at, long_pcr):
            self.assertTrue(result["protocol"]["url"].startswith("https://"))


class M5PartsTests(unittest.TestCase):
    def test_lookup(self):
        parts = parts_library.find_parts(name="T7")
        self.assertEqual(parts[0]["type"], "promoter")
        self.assertTrue(parts[0]["accession"])
        backbones = parts_library.find_parts(part_type="backbone")
        self.assertGreaterEqual(len(backbones), 3)


class AdditionalV09CoverageTests(unittest.TestCase):
    def test_intent_parser_branches(self):
        self.assertEqual(normalize_intent({"backbone": {"source": 0},
                                           "fragments": [
                                               {"source": 0,
                                                "interval": "10-20"}]})
                         ["fragments"][0]["interval"], [10, 20])
        with self.assertRaises(ValueError):
            normalize_intent({"method": "nope", "backbone": {},
                              "fragments": []})
        with self.assertRaises(ValueError):
            normalize_intent("not-dict")
        with self.assertRaises(ValueError):
            parse_intent_text("")
        with self.assertRaises(ValueError):
            parse_intent_text("fragments=0")

    def test_planner_error_branches(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            source = write_gb(record(random_seq(200, 1), "p1"), tmp, "p.gb")
            with self.assertRaises(Exception):
                plan_assembly([source], {"backbone": {"source": 1},
                                         "fragments": []})
            with self.assertRaises(Exception):
                plan_assembly([source], {"backbone": {"source": 0},
                                         "fragments": [
                                             {"source": 1}]})
            with self.assertRaises(Exception):
                plan_assembly([source], {"backbone": {"source": 0},
                                         "fragments": [{"source": 0,
                                                        "feature": "MISSING"}]})
            with self.assertRaises(Exception):
                plan_assembly([source], {"backbone": {"source": 0},
                                         "fragments": [
                                             {"source": 0,
                                              "interval": [500, 600]}]})

    def test_choose_overlap_short_and_bad_gc(self):
        seq, length, gc, tm, problems = choose_overlap("ACGT", "TTTT")
        self.assertEqual(length, 4)
        self.assertIn("overlap_shorter_than_15", problems)
        upstream = "A" * 40
        seq, length, gc, tm, problems = choose_overlap(upstream, "C" * 40)
        self.assertEqual(length, 15)
        self.assertTrue(problems)

    def test_html_render_matches_plan_data(self):
        plan = {"construct_name": "pX", "goal": "g", "status": "complete",
                "topology": "circular", "sources": [],
                "fragment_assignments": [{
                    "name": "f", "role": "backbone", "source_index": 0,
                    "source_path": "x.gb", "source_interval_0based": [0, 10],
                    "source_interval_1based": [1, 10], "length": 10,
                    "sequence": "ACGT"}],
                "assembly_strategy": {"method": "gibson",
                                      "requested_method": "auto",
                                      "reason": "r", "enzymes": None,
                                      "overlap_junctions": [],
                                      "alternatives": []},
                "primers": [{"fragment": "f", "backend": "primer3-core",
                             "forward": {"name": "f-F", "sequence": "ACGT",
                                         "tm": 60, "gc": 50},
                             "reverse": {"name": "f-R", "sequence": "TGCA",
                                         "tm": 60, "gc": 50}}],
                "feasibility": {"grade": "high", "errors": [],
                                "warnings": []},
                "steps": ["Step one"], "fusion_frame_check": {}}
        html_text = manual_render.render_html(plan)
        self.assertIn("pX", html_text)
        self.assertIn("f-F", html_text)
        self.assertIn("ACGT", html_text)
        self.assertIn("Step one", html_text)

    def test_manual_render(self):
        plan = {"construct_name": "pX", "goal": "g", "status": "complete",
                "topology": "circular", "sources": [],
                "fragment_assignments": [{
                    "name": "f", "role": "backbone", "source_index": 0,
                    "source_path": "x.gb", "source_interval_0based": [0, 10],
                    "source_interval_1based": [1, 10], "length": 10,
                    "sequence": "ACGT"}],
                "assembly_strategy": {"method": "gibson",
                                      "requested_method": "auto",
                                      "reason": "r", "enzymes": None,
                                      "overlap_junctions": [],
                                      "alternatives": []},
                "primers": [], "feasibility": {"grade": "high",
                                                "errors": [],
                                                "warnings": []},
                "fusion_frame_check": {}}
        text = manual_render.render_markdown(plan)
        self.assertIn("构建手册", text)
        self.assertIn("Step 1", text)

    def test_planner_digest_ligate_falls_back_when_sites_nonunique(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            seq = "GAATTC" + random_seq(200, 1) + "GGATCC"
            source = write_gb(record(seq, "pD"), tmp, "p.gb")
            intent = {"method": "digest-ligate",
                      "backbone": {"source": 0},
                      "fragments": [{"source": 0, "interval": [0, 200]}]}
            with mock.patch(
                    "planning.planner.design_region_primers",
                    side_effect=lambda seq, start, **kwargs:
                        fake_primer_result(seq, kwargs.get("fwd_tail", ""),
                                           kwargs.get("rev_tail", ""))):
                plan = planner_plan_assembly([source], intent)
            self.assertEqual(plan["assembly_strategy"]["method"], "gibson")

    def test_manual_render_rich_plan(self):
        plan = {"construct_name": "pX", "goal": "g", "status": "blocked",
                "topology": "circular",
                "sources": [{"index": 0, "path": "x", "id": "x",
                             "length": 10, "topology": "circular",
                             "features": []}],
                "fragment_assignments": [{
                    "name": "f", "role": "backbone", "source_index": 0,
                    "source_path": "x.gb", "source_interval_0based": [0, 10],
                    "source_interval_1based": [1, 10], "length": 10,
                    "sequence": "ACGT"}],
                "assembly_strategy": {"method": "gibson",
                                      "requested_method": "overlap",
                                      "reason": "r", "enzymes": ["BsaI"],
                                      "overlap_junctions": [{
                                          "between": ["a", "b"],
                                          "length": 20, "gc_percent": 50,
                                          "tm": 55, "problems": []}],
                                      "alternatives": [{"method": "gibson",
                                                        "reason": "x"}]},
                "primers": [{"fragment": "f", "backend": "primer3-core",
                             "forward": {"name": "f-F",
                                         "sequence": "ACGT", "tm": 60,
                                         "gc": 50, "tail": None,
                                         "use": "x"},
                             "reverse": {"name": "f-R",
                                         "sequence": "TGCA", "tm": 60,
                                         "gc": 50, "tail": None,
                                         "use": "x"}}],
                "feasibility": {"grade": "medium",
                                "errors": [{"rule_id": "r1",
                                            "severity": "error",
                                            "suggestion": "s",
                                            "source": "src"}],
                                "warnings": [{"rule_id": "r2",
                                              "severity": "warn",
                                              "suggestion": "s",
                                              "source": "src"}]},
                "fusion_frame_check": {"checked": True,
                                       "in_frame": False,
                                       "frame_offset_mod3": 1}}
        text = manual_render.render_markdown(plan)
        self.assertIn("alternatives", text)
        self.assertIn("OUT OF FRAME", text)
        self.assertIn("r1", text)

    def test_plan_assembly_main_direct(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            source = write_gb(record(random_seq(800, 2), "p1"), tmp, "p.gb")
            intent = tmp / "intent.json"
            intent.write_text(json.dumps({
                "backbone": {"source": 0},
                "fragments": [{"source": 0, "interval": [10, 300]}]}),
                encoding="utf-8")
            import io, contextlib
            with mock.patch.object(sys, "argv", [
                    "plan_assembly.py", source, "--intent-json",
                    str(intent), "--out-json", str(tmp / "plan.json"),
                    "--out-markdown", str(tmp / "plan.md"),
                    "--consent", "auto"]):
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    self.assertEqual(plan_cli.main(), 0)
            self.assertTrue((tmp / "plan.json").exists())
            with mock.patch.object(sys, "argv", [
                    "plan_assembly.py", source, "--intent-text",
                    "backbone=0;fragments=0:10-300;method=gibson",
                    "--out-json", str(tmp / "plan2.json"),
                    "--consent", "auto"]):
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    self.assertEqual(plan_cli.main(), 0)
            self.assertFalse((tmp / "construct.gb").exists())
            with mock.patch.object(sys, "argv", [
                    "plan_assembly.py", source, "--intent-text",
                    "backbone=0;fragments=0:10-300;method=gibson",
                    "--out-construct", str(tmp / "construct"),
                    "--consent", "auto"]):
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    self.assertEqual(plan_cli.main(), 0)
            self.assertTrue((tmp / "construct.gb").exists())
            self.assertTrue((tmp / "construct.fa").exists())
            self.assertTrue((tmp / "construct.dna").exists())
            provenance_path = tmp / "construct.provenance.json"
            self.assertTrue(provenance_path.exists())
            provenance = json.loads(provenance_path.read_text(
                encoding="utf-8"))
            self.assertEqual(provenance["schema_version"], "0.9.0")
            self.assertEqual(provenance["validation_status"], "validated")
            self.assertEqual(provenance["execution_status"], "validated")
            self.assertTrue(provenance["assembly_method"])
            self.assertTrue(provenance["input_files"])

    def test_plan_schema_validation(self):
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest("jsonschema is an install-time core dependency")
        schema = json.loads((ROOT / "schemas" /
                             "assembly-plan-v0.9.json").read_text(
                                 encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            donor = record(random_seq(600, 4), "pDONOR",
                           feature=SeqFeature(
                               FeatureLocation(50, 550, strand=1),
                               type="CDS", qualifiers={"label": ["EGFP"]}))
            sources = (write_gb(record(random_seq(800, 2), "pBACKBONE"),
                                tmp, "b.gb"),
                       write_gb(donor, tmp, "d.gb"))
            intent = normalize_intent({
                "backbone": {"source": 0},
                "fragments": [{"source": 1, "feature": "EGFP"}]})
            with mock.patch(
                    "planning.planner.design_region_primers",
                    side_effect=lambda seq, start, **kwargs:
                        fake_primer_result(seq, kwargs.get("fwd_tail", ""),
                                           kwargs.get("rev_tail", ""))):
                plan = planner_plan_assembly(sources, intent)
            self.assertEqual(
                list(Draft202012Validator(schema).iter_errors(plan)), [])

    def test_digest_ligate_rejects_two_sites_in_one_fragment(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            # backbone fragment has two EcoRI sites; insert has none.
            seq = "GAATTC" + random_seq(100, 1) + "GAATTC" + random_seq(200, 2)
            source = write_gb(record(seq, "pDUP"), tmp, "p.gb")
            intent = {"method": "digest-ligate",
                      "backbone": {"source": 0, "interval": [0, 306]},
                      "fragments": [{"source": 0, "interval": [306, 312]}]}
            with mock.patch(
                    "planning.planner.design_region_primers",
                    side_effect=lambda seq, start, **kwargs:
                        fake_primer_result(seq, kwargs.get("fwd_tail", ""),
                                           kwargs.get("rev_tail", ""))):
                plan = planner_plan_assembly([source], intent)
            self.assertEqual(plan["assembly_strategy"]["method"], "gibson")

    def test_plan_assembly_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            source = write_gb(record(random_seq(800, 2), "p1"), tmp, "p.gb")
            intent = tmp / "intent.json"
            intent.write_text(json.dumps({
                "backbone": {"source": 0},
                "fragments": [{"source": 0, "interval": [10, 300]}]}),
                encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, "-X", "utf8", "-B",
                 str(SCRIPTS / "plan_assembly.py"), source,
                 "--intent-json", str(intent),
                 "--out-json", str(tmp / "plan.json"),
                 "--out-markdown", str(tmp / "plan.md"),
                 "--consent", "auto"],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace")
            self.assertEqual(completed.returncode, 0,
                             (completed.stdout + completed.stderr)[-800:])
            self.assertTrue((tmp / "plan.json").exists())
            self.assertTrue((tmp / "plan.md").exists())

    def test_primer_engine_error_branches(self):
        import primer_design_engine
        with self.assertRaises(ValueError):
            primer_design_engine.design_region_primers(
                "A" * 20, 10, min_len=18)
        self.assertIsNone(primer_design_engine.best_pair(
            {"pairs": []}))
        result = primer_design_engine.design_region_primers(
            "A" * 20 + "CGTACGTACGTACGTACGTACGT" + "G" * 20,
            5, top_n=1, consent=auto_consent())
        self.assertEqual(result["backend"], "heuristic")

    def test_pcr_strategy_cli_and_branches(self):
        check = pcr_strategy.recommend_pcr_strategy(
            {"length": 500, "gc_percent": 50, "purpose": "colony-pcr"})
        self.assertIn("OneTaq", check["recommended_enzyme"])
        self.assertEqual(pcr_strategy.extension_time_seconds(0), 0)
        self.assertEqual(pcr_strategy.extension_time_seconds(2500), 75)
        with mock.patch.object(sys, "argv", [
                "pcr_strategy.py", "--length", "2000", "--gc", "75"]):
            import io, contextlib
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                self.assertEqual(pcr_strategy.main(), 0)
            self.assertIn("GC", buffer.getvalue())

    def test_parts_cli(self):
        with mock.patch.object(sys, "argv", ["parts_library.py", "--type",
                                             "tag"]):
            import io, contextlib
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                self.assertEqual(parts_library.main(), 0)
            self.assertIn("6xHis", buffer.getvalue())

    def test_online_sources_success_paths(self):
        fake_search = json.dumps({
            "esearchresult": {"idlist": ["123"]}})
        fake_summary = json.dumps({"result": {"123": {
            "caption": "NM_001", "title": "EGFP",
            "organism": "Aequorea victoria", "accessionversion": "NM_001.1"}}})
        with mock.patch.object(
                online_sources, "_get",
                side_effect=[fake_search, fake_summary]):
            result = online_sources.ncbi_search("EGFP")
        self.assertEqual(result["status"], "verified-online")
        self.assertEqual(result["records"][0]["accession"], "NM_001")
        # An HTTP response must contain a parsed record, not just a LOCUS prefix.
        record = SeqRecord(Seq("ACGT"), id="X", name="X")
        record.annotations["molecule_type"] = "DNA"
        import io
        buffer = io.StringIO()
        SeqIO.write(record, buffer, "genbank")
        with mock.patch.object(online_sources, "_get",
                               return_value=buffer.getvalue()):
            result = online_sources.fetch_genbank("X")
        self.assertEqual(result["status"], "verified-online")
        with mock.patch.object(online_sources, "_get",
                               side_effect=OSError("x")):
            result = online_sources.fetch_genbank("X")
        self.assertEqual(result["status"], "offline-unverified")


class M6OnlineSourceTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("SNAPGENE_RUN_ONLINE") == "1",
                         "set SNAPGENE_RUN_ONLINE=1 for live NCBI queries")
    def test_live_ncbi_search(self):
        result = online_sources.ncbi_search("EGFP", retmax=2, timeout=30)
        self.assertEqual(result["status"], "verified-online")
        self.assertTrue(result["records"])

    def test_offline_degrade_is_explicit(self):
        with mock.patch.object(online_sources, "_get",
                               side_effect=OSError("offline")):
            result = online_sources.ncbi_search("EGFP")
        self.assertEqual(result["status"], "offline-unverified")
        self.assertIn("offline", result["reason"])
        addgene = online_sources.addgene_lookup(42230)
        self.assertEqual(addgene["status"], "offline-unverified")
        blast = online_sources.ncbi_blast_hint("ACGT")
        self.assertEqual(blast["status"], "offline-unverified")
        self.assertIn("blast.ncbi.nlm.nih.gov", blast["url"])
        self.assertNotIn("ACGT", json.dumps(blast, sort_keys=True))
        consent = online_sources.request_crispor_query(
            "ACGT", "human", "guide-search", "target-40bp")
        consent.approve()
        self.assertTrue(consent.allowed(
            "https://crispor.org", "guide-search", "ACGT", "target-40bp"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
