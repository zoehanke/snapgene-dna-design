# -*- coding: utf-8 -*-
"""Architecture-recovery acceptance tests (v0.9.1).

These tests exercise only the public seams:
validate_construction_task / plan / execute / validate / finalize.
"""

from repository_paths import PROJECT_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS
import json
import pathlib
import tempfile
import unittest

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

from core import (execute, finalize, plan, validate,
                  validate_construction_task)
from core.errors import (CoreError, GateRejected, PlanningError,
                         TaskValidationError)


def _record(seq, name="record", topology="circular", features=()):
    rec = SeqRecord(Seq(seq), id=name, name=name)
    rec.annotations["molecule_type"] = "DNA"
    rec.annotations["topology"] = topology
    for feature in features:
        rec.features.append(feature)
    return rec


def _misc(label, start, end, strand=1):
    return SeqFeature(FeatureLocation(start, end, strand=strand),
                      type="misc_feature",
                      qualifiers={"label": [label]})


class TaskFactory:
    def __init__(self, tmp):
        self.tmp = pathlib.Path(tmp)

    def write(self, name, rec):
        path = self.tmp / name
        SeqIO.write(rec, path, "genbank")
        return str(path)

    def base(self, kind, sources, **overrides):
        task = {
            "schema_version": "construction-task-v1",
            "task_id": "task-test",
            "revision": 1,
            "mode": "formal",
            "task_kind": kind,
            "sources": sources,
            "operation": {},
            "target": {"source_id": sources[0]["source_id"]},
            "product": {"topology": "circular",
                        "formats": ["gb", "fasta", "dna"]},
            "method_constraints": {},
            "approvals": {"user_confirmed_task": {"value": True}},
            "assumptions": [],
            "provenance": [],
        }
        task.update(overrides)
        return task

    def source(self, source_id, path, role, evidence="user-provided"):
        return {
            "source_id": source_id,
            "path": path,
            "role": role,
            "evidence": {"source_evidence_class": evidence},
            "annotation_status": "reviewed",
        }


class ConstructionTaskTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.f = TaskFactory(self._tmp.name)
        self.out = pathlib.Path(self._tmp.name) / "out"

    def tearDown(self):
        self._tmp.cleanup()

    def _component_task(self, template_seq="A" * 20 + "GGATCC" + "C" * 40,
                        interval=(20, 26)):
        rec = _record(template_seq, "template", "circular")
        path = self.f.write("template.gb", rec)
        return self.f.base(
            "component_amplification",
            [self.f.source("template-1", path, "template")],
            target={"source_id": "template-1",
                    "selection": {"kind": "interval",
                                  "interval_0based": list(interval),
                                  "resolution_status": "resolved",
                                  "resolution_evidence": [
                                      {"kind": "user-interval"}]}},
            product={"topology": "linear",
                     "formats": ["gb", "fasta", "dna"]},
        )

    def test_unknown_task_kind_is_not_a_fallback(self):
        rec = _record("A" * 40, "x", "circular")
        path = self.f.write("x.gb", rec)
        task = self.f.base("plasmid_cowboy",
                           [self.f.source("x-1", path, "backbone")])
        with self.assertRaises(CoreError) as cm:
            validate_construction_task(task)
        self.assertEqual(cm.exception.error_code, "TASK_KIND_NOT_REGISTERED")

    def test_component_missing_selection_refused(self):
        rec = _record("A" * 40, "template", "circular")
        path = self.f.write("template.gb", rec)
        task = self.f.base(
            "component_amplification",
            [self.f.source("template-1", path, "template")],
            target={"source_id": "template-1"},
            product={"topology": "linear", "formats": ["gb"]})
        with self.assertRaises(TaskValidationError) as cm:
            validate_construction_task(task)
        self.assertEqual(cm.exception.error_code, "COMPONENT_BOUNDARY_REQUIRED")

    def test_whole_template_selection_refused(self):
        # S06 regression: whole circular template must never become a cassette
        task = self._component_task(interval=(0, 68))
        with self.assertRaises(TaskValidationError) as cm:
            validate_construction_task(task)
        self.assertEqual(cm.exception.error_code,
                         "WHOLE_TEMPLATE_SELECTED_FOR_COMPONENT")

    def test_replace_interval_required(self):
        # S05 regression: replace without explicit interval is refused
        vec = _record("A" * 20 + "GGATCC" + "C" * 40, "backbone", "circular")
        ins = _record("T" * 20, "replacement", "linear")
        vpath = self.f.write("vec.gb", vec)
        ipath = self.f.write("ins.gb", ins)
        task = self.f.base(
            "plasmid_replace",
            [self.f.source("backbone-1", vpath, "backbone"),
             self.f.source("replacement-1", ipath, "replacement")],
            operation={"replace": {"replacement_source_id": "replacement-1"}},
            target={"source_id": "backbone-1",
                    "selection": {"kind": "interval",
                                  "resolution_status": "resolved"}})
        with self.assertRaises(TaskValidationError) as cm:
            validate_construction_task(task)
        self.assertEqual(cm.exception.error_code, "REPLACE_INTERVAL_REQUIRED")

    def test_mutation_spec_required_no_default(self):
        # S01 regression: 100:A default path no longer exists
        rec = _record("A" * 60, "template", "circular")
        path = self.f.write("template.gb", rec)
        task = self.f.base(
            "point_mutation",
            [self.f.source("template-1", path, "template")],
            operation={})
        with self.assertRaises(TaskValidationError) as cm:
            validate_construction_task(task)
        self.assertEqual(cm.exception.error_code, "MUTATION_SPEC_REQUIRED")

    def test_mutation_ref_mismatch_refused(self):
        rec = _record("A" * 60, "template", "circular")
        path = self.f.write("template.gb", rec)
        task = self.f.base(
            "point_mutation",
            [self.f.source("template-1", path, "template")],
            operation={"mutations": [
                {"position_1based": 5, "ref": "G", "alt": "T"}]})
        with self.assertRaises(PlanningError) as cm:
            plan(task)
        self.assertEqual(cm.exception.error_code, "REFERENCE_RESIDUE_MISMATCH")

    def test_source_hash_mismatch_refused(self):
        task = self._component_task()
        task["sources"][0]["sha256"] = "0" * 64
        with self.assertRaises(TaskValidationError) as cm:
            validate_construction_task(task)
        self.assertEqual(cm.exception.error_code, "SOURCE_HASH_MISMATCH")

    def test_every_registered_kind_has_dedicated_planner(self):
        # No task kind may remain a silent "not implemented" placeholder,
        # and no generic assembler may act as a fallback.
        from core.registry import TASK_KINDS
        from core.runtime_plan import _PLANNERS
        for name, kind in TASK_KINDS.items():
            self.assertNotEqual(kind.get("status"), "not_implemented", name)
            self.assertIn(kind["planner"], _PLANNERS, name)

    def test_negative_strand_interval_component_is_reverse_complemented(self):
        seq = "A" * 20 + "GGATCC" + "C" * 40
        rec = _record(seq, "template", "circular")
        path = self.f.write("template.gb", rec)
        task = self.f.base(
            "component_amplification",
            [self.f.source("template-1", path, "template")],
            target={"source_id": "template-1",
                    "selection": {"kind": "interval",
                                  "interval_0based": [20, 26],
                                  "strand": -1,
                                  "resolution_status": "resolved",
                                  "resolution_evidence": [
                                      {"kind": "user-interval"}]}},
            product={"topology": "linear", "formats": ["gb", "fasta"]})
        task, p = plan(task)
        self.assertEqual(p["product_sequence"],
                         str(Seq("GGATCC").reverse_complement()))
        ex = execute(task, p, self.out)
        report = validate(task, p, ex)
        self.assertEqual(report["overall"], "verified", report["error_codes"])

    def test_negative_strand_complete_cds_component_keeps_cds_annotation(self):
        from Bio.Seq import Seq as BSeq
        bio = "ATGAAATTTGGGTAA"
        stored = str(BSeq(bio).reverse_complement())
        rec = _record("A" * 20 + stored + "C" * 40, "template", "circular",
                      features=[SeqFeature(
                          FeatureLocation(20, 20 + len(stored), strand=-1),
                          type="CDS",
                          qualifiers={"gene": ["revCds"]})])
        path = self.f.write("template.gb", rec)
        task = self.f.base(
            "component_amplification",
            [self.f.source("template-1", path, "template")],
            target={"source_id": "template-1",
                    "selection": {"kind": "feature",
                                  "feature_name": "revCds",
                                  "resolution_status": "resolved",
                                  "resolution_evidence": [
                                      {"kind": "computed-unique-feature"}]}},
            product={"topology": "linear", "formats": ["gb"]})
        task, p = plan(task)
        self.assertEqual(p["product_sequence"], bio)
        ex = execute(task, p, self.out)
        report = validate(task, p, ex)
        self.assertEqual(report["overall"], "verified", report["error_codes"])
        product = SeqIO.read(ex["product_gb"], "genbank")
        cdss = [f for f in product.features if f.type == "CDS"]
        self.assertTrue(cdss)
        self.assertTrue(cdss[0].qualifiers.get("translation"))

    def test_broken_source_cds_is_preserved_and_rejected(self):
        # Preserve the original B04 failure. Relabeling its invalid CDS as a
        # gene used to bypass validation instead of repairing the source.
        stored = "TTACCCAAATTTCATGGG"
        rec = _record("A" * 20 + stored + "C" * 40, "template", "circular",
                      features=[SeqFeature(
                          FeatureLocation(20, 20 + len(stored), strand=-1),
                          type="CDS",
                          qualifiers={"gene": ["revBroken"]})])
        path = self.f.write("template.gb", rec)
        task = self.f.base(
            "component_amplification",
            [self.f.source("template-1", path, "template")],
            target={"source_id": "template-1",
                    "selection": {"kind": "feature",
                                  "feature_name": "revBroken",
                                  "resolution_status": "resolved",
                                  "resolution_evidence": [
                                      {"kind": "computed-unique-feature"}]}},
            product={"topology": "linear", "formats": ["gb"]})
        task, p = plan(task)
        ex = execute(task, p, self.out)
        report = validate(task, p, ex)
        self.assertEqual(report["overall"], "failed")
        self.assertFalse(report["artifact_valid"])
        product = SeqIO.read(ex["product_gb"], "genbank")
        self.assertTrue([f for f in product.features if f.type == "CDS"])
        self.assertFalse([f for f in product.features if f.type == "gene"])
        with self.assertRaises(GateRejected):
            finalize(task, p, ex, report, self.out)

    def test_circular_wrap_interval_component(self):
        seq = "GGATCC" + "C" * 56
        rec = _record(seq, "template", "circular")
        path = self.f.write("template.gb", rec)
        # wrap interval [58, 8) = last 4 bp + first 8 bp
        task = self.f.base(
            "component_amplification",
            [self.f.source("template-1", path, "template")],
            target={"source_id": "template-1",
                    "selection": {"kind": "interval",
                                  "interval_0based": [58, 8],
                                  "resolution_status": "resolved",
                                  "resolution_evidence": [
                                      {"kind": "user-interval"}]}},
            product={"topology": "linear", "formats": ["gb"]})
        task, p = plan(task)
        self.assertEqual(p["product_sequence"],
                         seq[58:] + seq[:8])
        ex = execute(task, p, self.out)
        report = validate(task, p, ex)
        self.assertEqual(report["overall"], "verified", report["error_codes"])

    def test_near_full_length_selection_refused(self):
        seq = "A" * 100
        rec = _record(seq, "template", "circular")
        path = self.f.write("template.gb", rec)
        task = self.f.base(
            "component_amplification",
            [self.f.source("template-1", path, "template")],
            target={"source_id": "template-1",
                    "selection": {"kind": "interval",
                                  "interval_0based": [0, 97],
                                  "resolution_status": "resolved",
                                  "resolution_evidence": [
                                      {"kind": "user-interval"}]}},
            product={"topology": "linear", "formats": ["gb"]})
        with self.assertRaises(TaskValidationError) as cm:
            validate_construction_task(task)
        self.assertEqual(cm.exception.error_code,
                         "NEAR_FULL_TEMPLATE_SELECTED_FOR_COMPONENT")

    def test_near_full_length_with_explicit_approval_runs(self):
        seq = "A" * 100
        rec = _record(seq, "template", "circular")
        path = self.f.write("template.gb", rec)
        task = self.f.base(
            "component_amplification",
            [self.f.source("template-1", path, "template")],
            target={"source_id": "template-1",
                    "selection": {"kind": "interval",
                                  "interval_0based": [0, 97],
                                  "resolution_status": "resolved",
                                  "resolution_evidence": [
                                      {"kind": "user-interval"}]}},
            product={"topology": "linear", "formats": ["gb"]},
            approvals={"user_confirmed_task": {"value": True},
                       "near_whole_record": {
                           "value": True,
                           "evidence_layer": "user-provided"}})
        task, p = plan(task)
        self.assertEqual(p["component_length"], 97)

    def test_required_component_missing_fails_goal_layer(self):
        # goal checks must use independent evidence: a required component
        # that is not backed by a template feature inside the selection
        # must fail the goal layer, not pass by label circularity.
        seq = "A" * 20 + "GGATCC" + "C" * 40
        rec = _record(seq, "template", "circular",
                      features=[_misc("cassette", 20, 26)])
        path = self.f.write("template.gb", rec)
        task = self.f.base(
            "component_amplification",
            [self.f.source("template-1", path, "template")],
            target={"source_id": "template-1",
                    "selection": {"kind": "interval",
                                  "interval_0based": [20, 26],
                                  "resolution_status": "resolved",
                                  "resolution_evidence": [
                                      {"kind": "user-interval"}]}},
            product={"topology": "linear", "formats": ["gb"],
                     "required_components": ["missing-cassette"]})
        task, p = plan(task)
        ex = execute(task, p, self.out)
        report = validate(task, p, ex)
        self.assertFalse(report["goal_valid"])
        self.assertIn("REQUIRED_COMPONENT_MISSING", report["error_codes"])
        self.assertEqual(report["overall"], "failed")


class PositivePipelineTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.f = TaskFactory(self._tmp.name)
        self.out = pathlib.Path(self._tmp.name) / "out"

    def tearDown(self):
        self._tmp.cleanup()

    def test_component_amplification_full_pipeline(self):
        # S06 positive: explicit cassette interval + arms -> linear donor
        rec = _record("A" * 20 + "GGATCC" + "C" * 40, "template", "circular",
                      features=[_misc("cassette", 20, 26),
                                _misc("bla", 30, 40)])
        path = self.f.write("template.gb", rec)
        task = self.f.base(
            "component_amplification",
            [self.f.source("template-1", path, "template")],
            operation={"homology_arms": {"left_arm": "TTTT",
                                         "right_arm": "CCCC"}},
            target={"source_id": "template-1",
                    "selection": {"kind": "interval",
                                  "interval_0based": [20, 26],
                                  "resolution_status": "resolved",
                                  "resolution_evidence": [
                                      {"kind": "user-interval"}]}},
            product={"topology": "linear",
                     "required_components": ["cassette"],
                     "formats": ["gb", "fasta", "dna"]},
        )
        task, p = plan(task)
        self.assertEqual(p["component_length"], 6)
        self.assertEqual(p["product"]["expected_length"], 14)
        ex = execute(task, p, self.out)
        self.assertIn("intermediate", ex["product_gb"])
        report = validate(task, p, ex)
        self.assertTrue(report["artifact_valid"], report["error_codes"])
        self.assertTrue(report["computation_valid"], report["error_codes"])
        self.assertTrue(report["goal_valid"], report["error_codes"])
        self.assertEqual(report["overall"], "verified")
        delivery = finalize(task, p, ex, report, self.out)
        self.assertTrue((self.out / "authoritative" /
                         "DELIVERY-MANIFEST.json").exists())
        manifest = json.loads((self.out / "authoritative" /
                               "DELIVERY-MANIFEST.json")
                              .read_text(encoding="utf-8"))
        self.assertEqual(manifest["artifact_class"], "authoritative")
        self.assertEqual(delivery["status"], "delivered")

    def test_plasmid_replace_full_pipeline(self):
        # S05 positive: explicit replace interval yields exact product
        vec = _record("A" * 20 + "GGATCC" + "C" * 40, "backbone", "circular")
        ins = _record("NNNNNTTTTTNNNNN", "replacement", "linear")
        vpath = self.f.write("vec.gb", vec)
        ipath = self.f.write("ins.gb", ins)
        task = self.f.base(
            "plasmid_replace",
            [self.f.source("backbone-1", vpath, "backbone"),
             self.f.source("replacement-1", ipath, "replacement")],
            operation={"replace": {
                "interval_0based": [20, 26],
                "replacement_source_id": "replacement-1",
                "replacement_interval_0based": [5, 10]}},
            target={"source_id": "backbone-1",
                    "selection": {"kind": "interval",
                                  "interval_0based": [20, 26],
                                  "resolution_status": "resolved",
                                  "resolution_evidence": [
                                      {"kind": "user-interval"}]}},
            product={"topology": "circular",
                     "formats": ["gb", "fasta", "dna"]},
        )
        task, p = plan(task)
        expected = "A" * 20 + "TTTTT" + "C" * 40
        self.assertEqual(p["product_sequence"], expected)
        ex = execute(task, p, self.out)
        report = validate(task, p, ex)
        self.assertEqual(report["overall"], "verified", report["error_codes"])
        finalize(task, p, ex, report, self.out)

    def test_replace_old_concat_product_fails_goal(self):
        # S05 regression: the old "full backbone + inserts" product must be
        # rejected by independent recomputation.
        vec = _record("A" * 20 + "GGATCC" + "C" * 40, "backbone", "circular")
        ins = _record("NNNNNTTTTTNNNNN", "replacement", "linear")
        vpath = self.f.write("vec.gb", vec)
        ipath = self.f.write("ins.gb", ins)
        task = self.f.base(
            "plasmid_replace",
            [self.f.source("backbone-1", vpath, "backbone"),
             self.f.source("replacement-1", ipath, "replacement")],
            operation={"replace": {
                "interval_0based": [20, 26],
                "replacement_source_id": "replacement-1",
                "replacement_interval_0based": [5, 10]}},
            target={"source_id": "backbone-1",
                    "selection": {"kind": "interval",
                                  "interval_0based": [20, 26],
                                  "resolution_status": "resolved",
                                  "resolution_evidence": [
                                      {"kind": "user-interval"}]}},
            product={"topology": "circular", "formats": ["gb"]},
        )
        task, p = plan(task)
        ex = execute(task, p, self.out)
        # tamper execution to the historical wrong concat product
        ex["product_sequence"] = str(vec.seq) + "TTTTT"
        wrong = _record(ex["product_sequence"], "wrong", "circular")
        SeqIO.write(wrong, ex["product_gb"], "genbank")
        report = validate(task, p, ex)
        self.assertFalse(report["computation_valid"])
        self.assertEqual(report["overall"], "failed")

    def test_point_mutation_full_pipeline(self):
        # S01 positive: explicit mutation spec with ref check
        rec = _record("A" * 10 + "CGTGGTAAA" + "T" * 20, "template",
                      "circular")
        path = self.f.write("template.gb", rec)
        task = self.f.base(
            "point_mutation",
            [self.f.source("template-1", path, "template")],
            operation={"mutations": [
                {"position_1based": 12, "ref": "G", "alt": "T"},
                {"position_1based": 18, "ref": "A", "alt": "G"}]},
            product={"topology": "circular", "formats": ["gb", "fasta"]},
        )
        task, p = plan(task)
        self.assertEqual(p["product_sequence"][11], "T")
        ex = execute(task, p, self.out)
        report = validate(task, p, ex)
        self.assertEqual(report["overall"], "verified", report["error_codes"])
        finalize(task, p, ex, report, self.out)

    def test_backbone_contamination_flagged_in_donor(self):
        # A donor containing the vector bla fragment must fail goal-valid.
        template_seq = "A" * 20 + "GGATCC" + "C" * 40
        rec = _record(template_seq, "template", "circular",
                      features=[_misc("cassette", 20, 26),
                                _misc("bla", 30, 40)])
        path = self.f.write("template.gb", rec)
        task = self.f.base(
            "component_amplification",
            [self.f.source("template-1", path, "template")],
            target={"source_id": "template-1",
                    "selection": {"kind": "interval",
                                  "interval_0based": [20, 26],
                                  "resolution_status": "resolved",
                                  "resolution_evidence": [
                                      {"kind": "user-interval"}]}},
            product={"topology": "linear", "formats": ["gb"]},
        )
        task, p = plan(task)
        ex = execute(task, p, self.out)
        contaminated = "A" * 20 + "GGATCC" + "C" * 40  # whole template
        wrong = _record(contaminated, "wrong", "linear")
        SeqIO.write(wrong, ex["product_gb"], "genbank")
        ex["product_sequence"] = contaminated
        report = validate(task, p, ex)
        codes = report["error_codes"]
        self.assertTrue(report["goal_valid"] is False or
                        "UNEXPECTED_VECTOR_BACKBONE_IN_DONOR" in codes,
                        codes)


class OverlapAssemblyTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.f = TaskFactory(self._tmp.name)
        self.out = pathlib.Path(self._tmp.name) / "out"

    def tearDown(self):
        self._tmp.cleanup()

    def _task(self, fragments, overlap=20, topology="circular"):
        sources = []
        op_fragments = []
        for idx, seq in enumerate(fragments):
            rec = _record(seq, "f%d" % idx, "linear")
            path = self.f.write("f%d.gb" % idx, rec)
            sources.append(self.f.source("frag-%d" % idx, path, "insert"))
            op_fragments.append({"source_id": "frag-%d" % idx,
                                 "order": idx,
                                 "interval_0based": [0, len(seq)]})
        return self.f.base(
            "overlap_assembly", sources,
            operation={"fragments": op_fragments,
                       "overlap_length": overlap},
            target={},
            product={"topology": topology, "formats": ["gb", "fasta"]})

    def test_explicit_overlap_assembly_positive(self):
        a = "T" * 20 + "G" * 30
        b = "G" * 20 + "C" * 30
        c = "C" * 20 + "T" * 30
        task = self._task([a, b, c])
        task, p = plan(task)
        self.assertEqual(p["product_sequence"], "G" * 30 + "C" * 30 + "T" * 30)
        ex = execute(task, p, self.out)
        report = validate(task, p, ex)
        self.assertEqual(report["overall"], "verified", report["error_codes"])
        finalize(task, p, ex, report, self.out)

    def test_overlap_mismatch_refused(self):
        a = "T" * 20 + "G" * 30
        b = "C" * 20 + "C" * 30  # does not match a suffix
        c = "C" * 20 + "T" * 30
        task = self._task([a, b, c])
        with self.assertRaises(PlanningError) as cm:
            plan(task)
        self.assertEqual(cm.exception.error_code, "OVERLAP_MISMATCH")

    def test_overlap_fragment_interval_required(self):
        a = "A" * 20 + "G" * 30
        b = "G" * 20 + "C" * 30
        task = self._task([a, b])
        task["operation"]["fragments"][0].pop("interval_0based")
        with self.assertRaises(TaskValidationError) as cm:
            validate_construction_task(task)
        self.assertEqual(cm.exception.error_code, "OVERLAP_FRAGMENTS_REQUIRED")

    def test_linear_overlap_assembly_positive(self):
        a = "A" * 20 + "G" * 30
        b = "G" * 20 + "C" * 30
        task = self._task([a, b], topology="linear")
        task, p = plan(task)
        self.assertEqual(p["product_sequence"], a + "C" * 30)
        ex = execute(task, p, self.out)
        report = validate(task, p, ex)
        self.assertEqual(report["overall"], "verified", report["error_codes"])


class AuthoritativeGateTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.f = TaskFactory(self._tmp.name)
        self.out = pathlib.Path(self._tmp.name) / "out"

    def tearDown(self):
        self._tmp.cleanup()

    def _pipeline(self):
        rec = _record("A" * 20 + "GGATCC" + "C" * 40, "template", "circular")
        path = self.f.write("template.gb", rec)
        task = self.f.base(
            "component_amplification",
            [self.f.source("template-1", path, "template")],
            target={"source_id": "template-1",
                    "selection": {"kind": "interval",
                                  "interval_0based": [20, 26],
                                  "resolution_status": "resolved",
                                  "resolution_evidence": [
                                      {"kind": "user-interval"}]}},
            product={"topology": "linear", "formats": ["gb", "fasta", "dna"]},
        )
        task, p = plan(task)
        ex = execute(task, p, self.out)
        v = validate(task, p, ex)
        return task, p, ex, v

    def test_exploration_mode_cannot_deliver(self):
        task, p, ex, v = self._pipeline()
        task["mode"] = "exploration"
        with self.assertRaises(GateRejected) as cm:
            finalize(task, p, ex, v, self.out)
        self.assertEqual(cm.exception.error_code, "GATE_REQUIRES_FORMAL_MODE")
        self.assertFalse((self.out / "authoritative").exists())

    def test_missing_approval_cannot_deliver(self):
        # Approval is absent from the original task, so the plan hash is
        # computed over a task that never carried the approval.
        rec = _record("A" * 20 + "GGATCC" + "C" * 40, "template", "circular")
        path = self.f.write("template.gb", rec)
        task = self.f.base(
            "component_amplification",
            [self.f.source("template-1", path, "template")],
            target={"source_id": "template-1",
                    "selection": {"kind": "interval",
                                  "interval_0based": [20, 26],
                                  "resolution_status": "resolved",
                                  "resolution_evidence": [
                                      {"kind": "user-interval"}]}},
            product={"topology": "linear", "formats": ["gb", "fasta",
                                                       "dna"]},
            approvals={},
        )
        task, p = plan(task)
        ex = execute(task, p, self.out)
        v = validate(task, p, ex)
        with self.assertRaises(GateRejected) as cm:
            finalize(task, p, ex, v, self.out)
        self.assertEqual(cm.exception.error_code, "GATE_APPROVAL_MISSING")
        self.assertFalse((self.out / "authoritative").exists())

    def test_failed_validation_cannot_deliver_and_leaves_no_dir(self):
        task, p, ex, v = self._pipeline()
        v["overall"] = "failed"
        v["error_codes"] = ["LENGTH_MISMATCH"]
        with self.assertRaises(GateRejected):
            finalize(task, p, ex, v, self.out)
        self.assertFalse((self.out / "authoritative").exists())

    def test_broken_hash_chain_cannot_deliver(self):
        task, p, ex, v = self._pipeline()
        ex["plan_hash"] = "0" * 64
        with self.assertRaises(GateRejected) as cm:
            finalize(task, p, ex, v, self.out)
        self.assertEqual(cm.exception.error_code, "GATE_HASH_CHAIN_BROKEN")
        self.assertFalse((self.out / "authoritative").exists())

    def test_task_tamper_after_planning_breaks_chain(self):
        task, p, ex, v = self._pipeline()
        task["approvals"] = {}
        with self.assertRaises(GateRejected) as cm:
            finalize(task, p, ex, v, self.out)
        self.assertEqual(cm.exception.error_code, "GATE_HASH_CHAIN_BROKEN")
        self.assertFalse((self.out / "authoritative").exists())

    def test_intermediate_tamper_after_validation_breaks_gate(self):
        task, p, ex, v = self._pipeline()
        gb = pathlib.Path(ex["product_gb"])
        gb.write_text("LOCUS tampered\n//\n", encoding="utf-8")
        with self.assertRaises(GateRejected) as cm:
            finalize(task, p, ex, v, self.out)
        self.assertEqual(cm.exception.error_code, "GATE_ARTIFACT_TAMPERED")
        self.assertFalse((self.out / "authoritative").exists())

    def test_unresolved_assumption_cannot_deliver(self):
        rec = _record("A" * 20 + "GGATCC" + "C" * 40, "template", "circular")
        path = self.f.write("template.gb", rec)
        task = self.f.base(
            "component_amplification",
            [self.f.source("template-1", path, "template")],
            target={"source_id": "template-1",
                    "selection": {"kind": "interval",
                                  "interval_0based": [20, 26],
                                  "resolution_status": "resolved",
                                  "resolution_evidence": [
                                      {"kind": "user-interval"}]}},
            product={"topology": "linear", "formats": ["gb", "fasta",
                                                       "dna"]},
            assumptions=[{"text": "x", "resolution_status": "open"}],
        )
        task, p = plan(task)
        ex = execute(task, p, self.out)
        v = validate(task, p, ex)
        with self.assertRaises(GateRejected) as cm:
            finalize(task, p, ex, v, self.out)
        self.assertEqual(cm.exception.error_code, "GATE_UNRESOLVED_ASSUMPTION")


if __name__ == "__main__":
    unittest.main()
