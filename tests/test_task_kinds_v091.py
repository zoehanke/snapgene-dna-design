# -*- coding: utf-8 -*-
"""Task-kind tests for the six newly migrated kinds (v0.9.1).

protein_fusion / integration_donor / gateway_recombination /
restriction_ligation / hierarchical_assembly / crispr_editing.

Each kind has: a positive case through the public seams, closed-fail
negative cases, and boundary cases.  Experimental-maturity kinds must
produce ``experimental-preview`` and be refused by the authoritative gate.
"""

from repository_paths import PROJECT_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS
import json
import pathlib
import sys
import tempfile
import unittest

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

ROOT = SKILL_ROOT
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from core import (execute, finalize, plan, validate,  # noqa: E402
                  validate_construction_task)
from core.errors import (GateRejected, PlanningError,  # noqa: E402
                         TaskValidationError)
from simulate_advanced import (ATTB1, ATTB2, ATTL1, ATTL2,  # noqa: E402
                               ATTP1, ATTP2, ATTR1, ATTR2)


def _record(seq, name, topology="linear", features=()):
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


class TaskKindTestBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = pathlib.Path(self._tmp.name)
        self.out = self.tmp / "out"

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, name, rec):
        path = self.tmp / name
        SeqIO.write(rec, path, "genbank")
        return str(path)

    def source(self, source_id, path, role, evidence="user-provided",
               topology=None, annotation_status="reviewed"):
        source = {"source_id": source_id, "path": path, "role": role,
                  "evidence": {"source_evidence_class": evidence},
                  "annotation_status": annotation_status}
        if topology:
            source["topology"] = topology
        return source

    def base(self, kind, sources, **overrides):
        task = {
            "schema_version": "construction-task-v1",
            "task_id": "task-" + kind,
            "revision": 1,
            "mode": "formal",
            "task_kind": kind,
            "sources": sources,
            "operation": {},
            "target": {"source_id": sources[0]["source_id"]},
            "product": {"topology": "linear",
                        "formats": ["gb", "fasta", "dna"]},
            "method_constraints": {},
            "approvals": {"user_confirmed_task": {"value": True}},
            "assumptions": [],
            "provenance": [],
            "host": "Escherichia coli",
        }
        task.update(overrides)
        return task

    def run_pipeline(self, task):
        task = validate_construction_task(task)
        task, p = plan(task)
        ex = execute(task, p, self.out)
        v = validate(task, p, ex)
        return task, p, ex, v


class ProteinFusionTests(TaskKindTestBase):
    def _partners(self):
        p5 = _record("ATGGCTGCTGCTTAA", "p5", "linear",
                     features=[_misc("egfp-5", 0, 15)])
        p3 = _record("ATGGGTGGTGGTTAA", "p3", "linear",
                     features=[_misc("his-tag", 0, 15)])
        p5_path = self.write("p5.gb", p5)
        p3_path = self.write("p3.gb", p3)
        return p5_path, p3_path

    def _task(self, **op_overrides):
        p5_path, p3_path = self._partners()
        op = {
            "partner5": {"source_id": "p5", "interval_0based": [0, 15]},
            "partner3": {"source_id": "p3", "interval_0based": [0, 15]},
            "linker": {"dna": "GGCGGC"},
            "stop_policy": "stop",
        }
        op.update(op_overrides)
        return (self.base(
            "protein_fusion",
            [self.source("p5", p5_path, "reference"),
             self.source("p3", p3_path, "reference")],
            operation=op,
            product={"topology": "linear",
                     "formats": ["gb", "fasta", "dna"],
                     "required_components": ["egfp-5", "his-tag"],
                     "name": "egfp-his"}),
                op)

    def test_fusion_positive(self):
        task, op = self._task()
        task, p, ex, v = self.run_pipeline(task)
        self.assertEqual(p["product_sequence"],
                         "ATGGCTGCTGCT" + "GGCGGC" + "ATGGGTGGTGGTTAA")
        self.assertEqual(v["overall"], "verified", v["error_codes"])
        delivery = finalize(task, p, ex, v, self.out)
        self.assertEqual(delivery["status"], "delivered")
        manifest = json.loads((pathlib.Path(delivery["directory"]) /
                               "DELIVERY-MANIFEST.json").read_text(
                                   encoding="utf-8"))
        self.assertEqual(manifest["artifact_class"], "authoritative")

    def test_fusion_no_stop_policy_refused(self):
        task, _ = self._task()
        del task["operation"]["stop_policy"]
        with self.assertRaises(TaskValidationError) as cm:
            validate_construction_task(task)
        self.assertEqual(cm.exception.error_code,
                         "FUSION_STOP_POLICY_REQUIRED")

    def test_fusion_stop_policy_requires_partner3_stop(self):
        p5_path, _ = self._partners()
        p3 = _record("ATGGGTGGTGGT", "p3", "linear")
        p3_path = self.write("p3-nostop.gb", p3)
        op = {
            "partner5": {"source_id": "p5", "interval_0based": [0, 15]},
            "partner3": {"source_id": "p3", "interval_0based": [0, 12]},
            "stop_policy": "stop",
        }
        task = self.base(
            "protein_fusion",
            [self.source("p5", p5_path, "reference"),
             self.source("p3", p3_path, "reference")],
            operation=op,
            product={"topology": "linear", "formats": ["gb"]})
        with self.assertRaises(PlanningError) as cm:
            plan(task)
        self.assertEqual(cm.exception.error_code, "FUSION_STOP_CODON_REQUIRED")

    def test_fusion_linker_not_in_frame_refused(self):
        task, _ = self._task(linker={"dna": "GG"})
        with self.assertRaises(TaskValidationError) as cm:
            validate_construction_task(task)
        self.assertEqual(cm.exception.error_code,
                         "FUSION_LINKER_NOT_IN_FRAME")

    def test_fusion_no_stop_with_internal_stop_refused(self):
        p5 = _record("ATGGCTTAAGCTTAA", "p5", "linear")
        p3 = _record("ATGGGTGGTGGTTAA", "p3", "linear")
        p5_path = self.write("p5s.gb", p5)
        p3_path = self.write("p3s.gb", p3)
        op = {
            "partner5": {"source_id": "p5", "interval_0based": [0, 15]},
            "partner3": {"source_id": "p3", "interval_0based": [0, 15]},
            "stop_policy": "no-stop",
        }
        task = self.base(
            "protein_fusion",
            [self.source("p5", p5_path, "reference"),
             self.source("p3", p3_path, "reference")],
            operation=op,
            product={"topology": "linear", "formats": ["gb"]})
        with self.assertRaises(PlanningError) as cm:
            plan(task)
        self.assertEqual(cm.exception.error_code, "FUSION_INTERNAL_STOP")

    def test_fusion_negative_strand_partner(self):
        p5 = _record("TTAAGCAGCAGCCAT", "p5", "linear")
        p3 = _record("ATGGGTGGTGGTTAA", "p3", "linear")
        p5_path = self.write("p5rc.gb", p5)
        p3_path = self.write("p3rc.gb", p3)
        op = {
            "partner5": {"source_id": "p5", "interval_0based": [0, 15],
                         "strand": -1},
            "partner3": {"source_id": "p3", "interval_0based": [0, 15]},
            "stop_policy": "stop",
        }
        task = self.base(
            "protein_fusion",
            [self.source("p5", p5_path, "reference"),
             self.source("p3", p3_path, "reference")],
            operation=op,
            product={"topology": "linear", "formats": ["gb"]})
        task, p, ex, v = self.run_pipeline(task)
        # rc of p5 = ATGGCTGCTGCTTAA -> strip stop -> ATGGCTGCTGCT
        self.assertEqual(p["product_sequence"],
                         "ATGGCTGCTGCT" + "ATGGGTGGTGGTTAA")
        self.assertEqual(v["overall"], "verified", v["error_codes"])


class IntegrationDonorTests(TaskKindTestBase):
    def _fixture(self):
        template = _record("A" * 20 + "GGATCC" + "C" * 40, "pTemplate",
                           "circular",
                           features=[_misc("URA3-cassette", 20, 26),
                                     _misc("bla", 30, 40),
                                     _misc("ori", 5, 10)])
        locus = _record("T" * 100, "locus", "linear")
        return (self.write("template.gb", template),
                self.write("locus.gb", locus))

    def _task(self, locus_interval=(50, 60), strand=1):
        template_path, locus_path = self._fixture()
        ref = _record("T" * 100, "locus", "linear")
        left = str(ref.seq[45:50])
        right = str(ref.seq[60:65])
        return (self.base(
            "integration_donor",
            [self.source("template-1", template_path, "template",
                         topology="circular"),
             self.source("locus-1", locus_path, "reference")],
            target={"source_id": "template-1",
                    "selection": {"kind": "interval",
                                  "interval_0based": [20, 26],
                                  "resolution_status": "resolved",
                                  "resolution_evidence": [
                                      {"kind": "user-interval"}]}},
            operation={
                "homology_arms": {"left_arm": left, "right_arm": right},
                "locus": {"source_id": "locus-1",
                          "interval_0based": list(locus_interval),
                          "strand": strand},
            },
            product={"topology": "linear",
                     "formats": ["gb", "fasta", "dna"],
                     "required_components": ["URA3-cassette"],
                     "forbidden_components": ["bla"]}),
                left, right)

    def test_donor_positive(self):
        task, left, right = self._task()
        task, p, ex, v = self.run_pipeline(task)
        self.assertEqual(p["product_sequence"],
                         left + "GGATCC" + right)
        self.assertEqual(v["overall"], "verified", v["error_codes"])

    def test_donor_arm_mismatch_refused(self):
        task, left, _ = self._task()
        task["operation"]["homology_arms"]["left_arm"] = "A" * 5
        with self.assertRaises(PlanningError) as cm:
            plan(task)
        self.assertEqual(cm.exception.error_code, "INTEGRATION_ARM_MISMATCH")

    def test_donor_negative_strand_arms(self):
        template_path, locus_path = self._fixture()
        ref = _record("T" * 100, "locus", "linear")
        # strand -1: left == rc(downstream), right == rc(upstream)
        upstream = str(ref.seq[45:50])
        downstream = str(ref.seq[60:65])
        left = str(Seq(downstream).reverse_complement())
        right = str(Seq(upstream).reverse_complement())
        task = self.base(
            "integration_donor",
            [self.source("template-1", template_path, "template",
                         topology="circular"),
             self.source("locus-1", locus_path, "reference")],
            target={"source_id": "template-1",
                    "selection": {"kind": "interval",
                                  "interval_0based": [20, 26],
                                  "resolution_status": "resolved",
                                  "resolution_evidence": [
                                      {"kind": "user-interval"}]}},
            operation={
                "homology_arms": {"left_arm": left, "right_arm": right},
                "locus": {"source_id": "locus-1",
                          "interval_0based": [50, 60], "strand": -1},
            },
            product={"topology": "linear", "formats": ["gb"]})
        task, p, ex, v = self.run_pipeline(task)
        self.assertEqual(v["overall"], "verified", v["error_codes"])

    def test_donor_missing_arms_refused(self):
        task, _, _ = self._task()
        task["operation"]["homology_arms"] = {}
        with self.assertRaises(TaskValidationError) as cm:
            validate_construction_task(task)
        self.assertEqual(cm.exception.error_code, "INTEGRATION_ARMS_REQUIRED")


class GatewayRecombinationTests(TaskKindTestBase):
    def _lr_fixture(self):
        body = "AAAACCCTTTTAA"
        entry = _record(ATTL1 + body + str(Seq(ATTL2).reverse_complement()) +
                        "G" * 40, "entry", "circular")
        destination = _record(ATTR1 + "TTTTCCCC" +
                              str(Seq(ATTR2).reverse_complement()) +
                              "C" * 40, "destination", "circular")
        return (self.write("entry.gb", entry),
                self.write("destination.gb", destination), body)

    def test_lr_positive(self):
        entry_path, dest_path, body = self._lr_fixture()
        task = self.base(
            "gateway_recombination",
            [self.source("entry-1", entry_path, "entry", topology="circular"),
             self.source("destination-1", dest_path, "destination",
                         topology="circular")],
            operation={"reaction": "lr",
                       "entry_source_id": "entry-1",
                       "destination_source_id": "destination-1",
                       "stop_policy": "stop"},
            product={"topology": "circular",
                     "formats": ["gb", "fasta", "dna"],
                     "required_components": [],
                     "name": "pDEST-goi"})
        task, p, ex, v = self.run_pipeline(task)
        self.assertEqual(v["overall"], "verified", v["error_codes"])
        self.assertIn(body, p["product_sequence"])
        self.assertIn(ATTB1, p["product_sequence"])
        self.assertIn(str(Seq(ATTB2).reverse_complement()),
                      p["product_sequence"])

    def test_bp_positive(self):
        body = "GGGGAAAACCCC"
        insert = _record("AA" + ATTB1 + body + ATTB2 + "TT", "pcr",
                         "linear")
        donor = _record(ATTP1 + "TTTTTTTT" +
                        str(Seq(ATTP2).reverse_complement()) + "G" * 40,
                        "donor", "circular")
        insert_path = self.write("insert.gb", insert)
        donor_path = self.write("donor.gb", donor)
        task = self.base(
            "gateway_recombination",
            [self.source("insert-1", insert_path, "donor_component"),
             self.source("donor-1", donor_path, "entry",
                         topology="circular")],
            operation={"reaction": "bp",
                       "entry_source_id": "insert-1",
                       "donor_vector_source_id": "donor-1",
                       "stop_policy": "no-stop"},
            product={"topology": "circular", "formats": ["gb", "fasta"]})
        task, p, ex, v = self.run_pipeline(task)
        self.assertEqual(v["overall"], "verified", v["error_codes"])
        self.assertIn(ATTL1, p["product_sequence"])
        self.assertIn(str(Seq(ATTL2).reverse_complement()),
                      p["product_sequence"])

    def test_lr_duplicate_att_site_refused(self):
        entry_path, dest_path, _ = self._lr_fixture()
        entry = SeqIO.read(entry_path, "genbank")
        entry.seq = Seq(ATTL1 + "X" + ATTL1 + "C" * 40 +
                        str(Seq(ATTL2).reverse_complement()))
        entry.annotations["topology"] = "circular"
        entry_path = self.write("entry-dup.gb", entry)
        task = self.base(
            "gateway_recombination",
            [self.source("entry-1", entry_path, "entry", topology="circular"),
             self.source("destination-1", dest_path, "destination",
                         topology="circular")],
            operation={"reaction": "lr",
                       "entry_source_id": "entry-1",
                       "destination_source_id": "destination-1",
                       "stop_policy": "stop"},
            product={"topology": "circular", "formats": ["gb"]})
        with self.assertRaises(PlanningError) as cm:
            plan(task)
        self.assertEqual(cm.exception.error_code, "ATT_SITE_NOT_UNIQUE")

    def test_missing_reaction_refused(self):
        entry_path, dest_path, _ = self._lr_fixture()
        task = self.base(
            "gateway_recombination",
            [self.source("entry-1", entry_path, "entry", topology="circular"),
             self.source("destination-1", dest_path, "destination",
                         topology="circular")],
            operation={"entry_source_id": "entry-1",
                       "destination_source_id": "destination-1"},
            product={"topology": "circular", "formats": ["gb"]})
        with self.assertRaises(TaskValidationError) as cm:
            validate_construction_task(task)
        self.assertEqual(cm.exception.error_code,
                         "GATEWAY_REACTION_REQUIRED")


class RestrictionLigationTests(TaskKindTestBase):
    def _two_enzyme_fixture(self):
        vector = _record("GGGGAATTCAAAAAGCTTCCC", "vector", "circular")
        insert = _record("AAGAATTCTTTTTTAAGCTTGG", "insert", "linear")
        return (self.write("vector.gb", vector),
                self.write("insert.gb", insert))

    def _task(self, orientation="forward"):
        vector_path, insert_path = self._two_enzyme_fixture()
        return self.base(
            "restriction_ligation",
            [self.source("vector-1", vector_path, "backbone",
                         topology="circular"),
             self.source("insert-1", insert_path, "insert")],
            operation={"vector_source_id": "vector-1",
                       "insert_source_id": "insert-1",
                       "vector_enzymes": ["EcoRI", "HindIII"],
                       "orientation": orientation},
            product={"topology": "circular",
                     "formats": ["gb", "fasta", "dna"]})

    def test_two_enzyme_positive_experimental_preview(self):
        task = self._task()
        task, p, ex, v = self.run_pipeline(task)
        self.assertEqual(v["overall"], "experimental-preview",
                         v["error_codes"])
        self.assertTrue(v["artifact_valid"])
        self.assertTrue(v["computation_valid"])
        self.assertTrue(v["goal_valid"])
        with self.assertRaises(GateRejected) as cm:
            finalize(task, p, ex, v, self.out)
        self.assertEqual(cm.exception.error_code, "GATE_EXPERIMENTAL_METHOD")
        self.assertFalse((self.out / "authoritative").exists())

    def test_two_enzyme_reverse_orientation(self):
        # Insert with HindIII upstream of EcoRI: forward is incompatible,
        # reverse (rc) restores the compatible EcoRI/HindIII order.
        vector = _record("GGGGAATTCAAAAAGCTTCCC", "vector", "circular")
        insert = _record("TTAAGCTTAAAAAAGAATTCTT", "insert", "linear")
        vector_path = self.write("vector_r.gb", vector)
        insert_path = self.write("insert_r.gb", insert)
        task = self.base(
            "restriction_ligation",
            [self.source("vector-1", vector_path, "backbone",
                         topology="circular"),
             self.source("insert-1", insert_path, "insert")],
            operation={"vector_source_id": "vector-1",
                       "insert_source_id": "insert-1",
                       "vector_enzymes": ["EcoRI", "HindIII"],
                       "orientation": "reverse"},
            product={"topology": "circular", "formats": ["gb"]})
        task, p, ex, v = self.run_pipeline(task)
        self.assertEqual(v["overall"], "experimental-preview",
                         v["error_codes"])
        self.assertTrue(v["computation_valid"])
        # the same insert in forward orientation must be refused
        task2 = self.base(
            "restriction_ligation",
            [self.source("vector-1", vector_path, "backbone",
                         topology="circular"),
             self.source("insert-1", insert_path, "insert")],
            operation={"vector_source_id": "vector-1",
                       "insert_source_id": "insert-1",
                       "vector_enzymes": ["EcoRI", "HindIII"],
                       "orientation": "forward"},
            product={"topology": "circular", "formats": ["gb"]})
        with self.assertRaises(PlanningError) as cm:
            plan(task2)
        self.assertEqual(cm.exception.error_code, "STICKY_END_MISMATCH")

    def test_single_enzyme_positive(self):
        vector = _record("GGGGAATTCAAACCC", "vector", "circular")
        insert = _record("TTGAATTCCCCGAATTCTT", "insert", "linear")
        vector_path = self.write("vector1.gb", vector)
        insert_path = self.write("insert1.gb", insert)
        task = self.base(
            "restriction_ligation",
            [self.source("vector-1", vector_path, "backbone",
                         topology="circular"),
             self.source("insert-1", insert_path, "insert")],
            operation={"vector_source_id": "vector-1",
                       "insert_source_id": "insert-1",
                       "vector_enzymes": ["EcoRI"],
                       "orientation": "forward"},
            product={"topology": "circular", "formats": ["gb"]})
        task, p, ex, v = self.run_pipeline(task)
        self.assertEqual(v["overall"], "experimental-preview",
                         v["error_codes"])
        self.assertTrue(v["computation_valid"])

    def test_wrapped_vector_cuts_refused(self):
        vector = _record("AAGCTT" + "C" * 20 + "GAATTC" + "A" * 20,
                         "vector", "circular")
        insert = _record("AAGAATTCTTTTTTAAGCTTGG", "insert", "linear")
        vector_path = self.write("vectorwrap.gb", vector)
        insert_path = self.write("insertwrap.gb", insert)
        task = self.base(
            "restriction_ligation",
            [self.source("vector-1", vector_path, "backbone",
                         topology="circular"),
             self.source("insert-1", insert_path, "insert")],
            operation={"vector_source_id": "vector-1",
                       "insert_source_id": "insert-1",
                       "vector_enzymes": ["EcoRI", "HindIII"],
                       "orientation": "forward"},
            product={"topology": "circular", "formats": ["gb"]})
        with self.assertRaises(PlanningError) as cm:
            plan(task)
        self.assertEqual(cm.exception.error_code,
                         "RESTRICTION_WRAP_UNSUPPORTED")

    def test_insert_missing_site_refused(self):
        vector_path, insert_path = self._two_enzyme_fixture()
        insert = SeqIO.read(insert_path, "genbank")
        insert.seq = Seq("TTTTTTTTTTTTTTTTTTTT")
        insert_path = self.write("insert-nosite.gb", insert)
        task = self.base(
            "restriction_ligation",
            [self.source("vector-1", vector_path, "backbone",
                         topology="circular"),
             self.source("insert-1", insert_path, "insert")],
            operation={"vector_source_id": "vector-1",
                       "insert_source_id": "insert-1",
                       "vector_enzymes": ["EcoRI", "HindIII"],
                       "orientation": "forward"},
            product={"topology": "circular", "formats": ["gb"]})
        with self.assertRaises(PlanningError) as cm:
            plan(task)
        self.assertEqual(cm.exception.error_code, "RESTRICTION_SITE_COUNT")


class HierarchicalAssemblyTests(TaskKindTestBase):
    def _fixture(self):
        s1 = _record("AAAACCCCGGGG", "s1", "linear")
        s2 = _record("GGGGTTTT", "s2", "linear")
        s3 = _record("TTTTCCCCAAAA", "s3", "linear")
        return (self.write("s1.gb", s1), self.write("s2.gb", s2),
                self.write("s3.gb", s3))

    def _task(self):
        s1_path, s2_path, s3_path = self._fixture()
        return self.base(
            "hierarchical_assembly",
            [self.source("s1", s1_path, "reference"),
             self.source("s2", s2_path, "reference"),
             self.source("s3", s3_path, "reference")],
            operation={"stages": [
                {"stage_id": "m1",
                 "fragments": [
                     {"source_id": "s1", "interval_0based": [0, 12],
                      "order": 0},
                     {"source_id": "s2", "interval_0based": [0, 8],
                      "order": 1}],
                 "overlap_length": 4,
                 "product_topology": "linear"},
                {"stage_id": "m2",
                 "fragments": [
                     {"stage_id": "m1", "order": 0},
                     {"source_id": "s3", "interval_0based": [0, 12],
                      "order": 1}],
                 "overlap_length": 4,
                 "product_topology": "circular"},
            ]},
            product={"topology": "circular",
                     "formats": ["gb", "fasta", "dna"]})

    def test_hierarchical_positive(self):
        task = self._task()
        task, p, ex, v = self.run_pipeline(task)
        self.assertEqual(p["stages"][0]["product_sequence"],
                         "AAAACCCCGGGG" + "TTTT")
        self.assertEqual(p["product_sequence"],
                         "CCCCGGGGTTTT" + "CCCCAAAA")
        self.assertEqual(v["overall"], "verified", v["error_codes"])

    def test_unknown_stage_reference_refused(self):
        task = self._task()
        task["operation"]["stages"][1]["fragments"][0]["stage_id"] = "nope"
        with self.assertRaises(PlanningError) as cm:
            plan(task)
        self.assertEqual(cm.exception.error_code,
                         "HIERARCHICAL_STAGE_REFERENCE_MISSING")

    def test_stage_overlap_mismatch_refused(self):
        task = self._task()
        task["operation"]["stages"][1]["fragments"][1]["interval_0based"] = \
            [1, 12]
        with self.assertRaises(PlanningError) as cm:
            plan(task)
        self.assertEqual(cm.exception.error_code, "OVERLAP_MISMATCH")

    def test_final_topology_mismatch_refused(self):
        task = self._task()
        task["product"]["topology"] = "linear"
        with self.assertRaises(TaskValidationError) as cm:
            validate_construction_task(task)
        self.assertEqual(cm.exception.error_code,
                         "HIERARCHICAL_FINAL_TOPOLOGY_MISMATCH")


class CrisprEditingTests(TaskKindTestBase):
    def _fixture(self):
        ref_seq = ("AAAA" + "TACGTACGTACGTACGTACGTGG" +
                   "AAAAAAAAAAAAAAAAAAAAAAAAAAAA")
        reference = _record(ref_seq, "ref", "linear")
        donor = _record("GGGGGGGGGG", "donor", "linear")
        return (self.write("ref.gb", reference),
                self.write("donor.gb", donor), ref_seq)

    def _task(self, with_donor=True):
        ref_path, donor_path, ref_seq = self._fixture()
        sources = [self.source("ref-1", ref_path, "reference")]
        donor_strategy = {}
        if with_donor:
            sources.append(self.source("donor-1", donor_path,
                                       "donor_component"))
            donor_strategy = {
                "donor_source_id": "donor-1",
                "replacement_interval_0based": [0, 10],
                "homology_arms": {"left_arm": ref_seq[0:4],
                                  "right_arm": ref_seq[28:32]},
            }
        return self.base(
            "crispr_editing",
            sources,
            operation={"nuclease": "spcas9-wt",
                       "target_interval_0based": [4, 28],
                       "guide_strategy": {"pam": "NGG"},
                       "donor_strategy": donor_strategy},
            product={"topology": "linear",
                     "formats": ["gb", "fasta", "dna"],
                     "name": "edited-locus"})

    def test_hdr_positive_experimental_preview(self):
        task = self._task()
        task, p, ex, v = self.run_pipeline(task)
        self.assertEqual(v["overall"], "experimental-preview",
                         v["error_codes"])
        self.assertTrue(v["artifact_valid"])
        self.assertTrue(v["computation_valid"])
        self.assertTrue(v["goal_valid"])
        self.assertGreaterEqual(len(p["guides"]), 1)
        self.assertIn("GGGGGGGGGG", p["product_sequence"])
        with self.assertRaises(GateRejected) as cm:
            finalize(task, p, ex, v, self.out)
        self.assertEqual(cm.exception.error_code, "GATE_EXPERIMENTAL_METHOD")

    def test_no_guides_in_window_refused(self):
        task = self._task()
        task["operation"]["target_interval_0based"] = [32, 36]
        with self.assertRaises(PlanningError) as cm:
            plan(task)
        self.assertEqual(cm.exception.error_code,
                         "CRISPR_NO_GUIDES_IN_TARGET")

    def test_donor_arm_mismatch_refused(self):
        task = self._task()
        task["operation"]["donor_strategy"]["homology_arms"]["left_arm"] = \
            "TTTT"
        with self.assertRaises(PlanningError) as cm:
            plan(task)
        self.assertEqual(cm.exception.error_code, "CRISPR_ARM_MISMATCH")

    def test_missing_nuclease_refused(self):
        task = self._task()
        del task["operation"]["nuclease"]
        with self.assertRaises(TaskValidationError) as cm:
            validate_construction_task(task)
        self.assertEqual(cm.exception.error_code, "CRISPR_NUCLEASE_REQUIRED")


if __name__ == "__main__":
    unittest.main()
