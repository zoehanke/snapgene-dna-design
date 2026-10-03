"""Regression tests for the concrete extraction, delivery and annotation failures."""

from repository_paths import PROJECT_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS
import json
import os
import pathlib
import random
import tempfile
import unittest
from unittest.mock import patch

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import CompoundLocation, FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

from core import plan, execute, validate
from core.errors import GateRejected
from core.guardrails.checklist import quick_biological_sanity_check
from core.handlers.composite_pipeline import CompositePipelineHandler
from core.io.input_resolution import resolve_sequence_record
from core.runtime_gate import finalize_candidate_construct
from core.tools.feature_ops import get_feature
from core.tools.restriction import digest_sequence, find_restriction_sites
from core.tools.snapgene_io import export_snapgene

ROOT = SKILL_ROOT


def real_cloning_task(vector_path=None, donor_path=None):
    """Execute the original geometry; defaults retain the optional external case."""
    vector_path = vector_path or ROOT / "fixtures/pDONR201.dna"
    donor_path = donor_path or ROOT / "fixtures/golden/attB-EmGFP.gb"
    vector = resolve_sequence_record(vector_path)
    donor = resolve_sequence_record(donor_path)
    backbone = str(vector.seq[2744:] + vector.seq[:331])
    insert = str(donor.seq[25:745])
    task = {
        "schema_version": "construction-task-v1", "task_id": "pDONR201-EmGFP",
        "revision": 1, "mode": "formal", "task_kind": "composite_pipeline",
        "sources": [{"source_id": sid, "path": str(path), "role": role,
                     "evidence": {"source_evidence_class": "user-provided"}}
                    for sid, path, role in [("vector", vector_path, "backbone"), ("donor", donor_path, "template")]],
        "target": {}, "operation": {}, "method_constraints": {},
        "product": {"topology": "circular", "formats": ["gb", "fasta", "dna"],
                    "required_components": ["KanR", "ori", "EmGFP"], "forbidden_components": ["ccdB", "CmR"]},
        "expected_components": [{"name": "EmGFP", "expected_sequence": insert, "strand": 1}],
        "approvals": {"user_confirmed_task": {"value": True}}, "assumptions": [], "provenance": [],
        "pipeline": {"steps": [
            {"step_id": "backbone", "tool": "extract_subsequence", "params": {
                "source": "$vector", "start": 2744, "end": 331, "topology": "circular", "wraps_origin": True}},
            {"step_id": "insert", "tool": "simulate_pcr", "params": {
                "template_path_or_seq": "$donor", "topology": "linear",
                "f_primer": backbone[-22:] + insert[:23],
                "r_primer": str(Seq(backbone[:22]).reverse_complement()) + str(Seq(insert[-23:]).reverse_complement())}},
            {"step_id": "assembled", "tool": "simulate_overlap_assembly", "params": {
                "fragments": ["$backbone", "$insert"], "min_overlap": 22, "circular": True}},
        ]},
    }
    return task, backbone + insert


def synthetic_cloning_sources(directory):
    """Owned sequence stand-ins, retaining the original regression geometry.

    Feature labels exercise name-based checks; they do not claim real antibiotic
    resistance or fluorescence. No restricted sequence is copied or distributed.
    """
    rng = random.Random(20260910)
    bases = lambda n: "".join(rng.choice("ACGT") for _ in range(n))
    codons = [a + b + c for a in "ACGT" for b in "ACGT" for c in "ACGT"
              if a + b + c not in {"TAA", "TAG", "TGA"}]
    def cds(length):
        return "ATG" + "".join(rng.choice(codons) for _ in range(length // 3 - 2)) + "TAA"
    vector_seq = list(bases(4470))
    vector_seq[2867:3677] = cds(810)
    vector = SeqRecord(Seq("".join(vector_seq)), id="synthetic_vector",
                       annotations={"molecule_type": "DNA", "topology": "circular"})
    for start, end, kind, name in [(2867, 3677, "CDS", "KanR"), (3900, 4200, "rep_origin", "ori"),
                                  (50, 100, "terminator", "rrnB T1 terminator"),
                                  (130, 170, "terminator", "rrnB T2 terminator"),
                                  (500, 650, "misc_feature", "ccdB"), (800, 950, "misc_feature", "CmR")]:
        vector.features.append(SeqFeature(FeatureLocation(start, end, strand=1), type=kind,
            qualifiers={"label": [name], "note": ["Synthetic regression stand-in; function not asserted"]}))
    donor = SeqRecord(Seq(bases(25) + cds(720) + bases(25)), id="synthetic_donor",
                      annotations={"molecule_type": "DNA", "topology": "linear"})
    donor.features = [SeqFeature(FeatureLocation(25, 745, strand=1), type="CDS",
                      qualifiers={"label": ["EmGFP"], "note": ["Synthetic regression ORF, not GFP"]})]
    paths = []
    for record in (vector, donor):
        path = pathlib.Path(directory) / (record.id + ".gb")
        with path.open("w", encoding="utf-8") as handle:
            SeqIO.write(record, handle, "genbank")
        paths.append(path)
    return paths


class TargetedCorrectnessTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="targeted-fixtures-")
        self.addCleanup(self.directory.cleanup)
        self.external = os.environ.get("SNAPGENE_RUN_ACADEMIC_FIXTURES") == "1"
        if self.external:
            self.vector_path = ROOT / "fixtures/pDONR201.dna"
            self.donor_path = ROOT / "fixtures/golden/attB-EmGFP.gb"
        else:
            self.vector_path, self.donor_path = synthetic_cloning_sources(self.directory.name)

    def test_join_and_origin_extraction_on_both_strands(self):
        record = SeqRecord(Seq("ATGAAACCCGGGTTTTAA"))
        for parts in ([FeatureLocation(0, 6, strand=1), FeatureLocation(12, 18, strand=1)],
                      [FeatureLocation(12, 18, strand=1), FeatureLocation(0, 6, strand=1)],
                      [FeatureLocation(12, 18, strand=-1), FeatureLocation(0, 6, strand=-1)],
                      [FeatureLocation(0, 6, strand=-1), FeatureLocation(12, 18, strand=-1)]):
            with self.subTest(parts=parts):
                feature = SeqFeature(CompoundLocation(parts), type="CDS", qualifiers={"label": ["joined"]})
                record.features = [feature]
                result = get_feature(record, "joined")
                self.assertEqual(result["sequence"], str(feature.extract(record.seq)))
                self.assertEqual(result["length"], 12)

    def test_query_and_digest_share_real_end_geometry(self):
        cases = [("AAAGAATTCTTT", "EcoRI", False, "5prime", "AATT"),
                 ("AAACTGCAGTTT", "PstI", False, "3prime", "TGCA"),
                 ("AAAGATATCTTT", "EcoRV", False, "blunt", ""),
                 ("ATTCTTTAAAGA", "EcoRI", True, "5prime", "AATT"),
                 ("AAAGGTCTCAAAGCTTT", "BsaI", False, "5prime", "AAGC"),
                 ("AAATGCAAGAGACCTTT", "BsaI", False, "5prime", "TGCA")]
        for sequence, enzyme, circular, kind, motif in cases:
            with self.subTest(enzyme=enzyme, circular=circular):
                query = find_restriction_sites(sequence, [enzyme], "circular" if circular else "linear")
                cut = query["enzymes"][enzyme]["cuts"][0]
                self.assertEqual((cut["overhang_type"], cut["overhang_sequence"]), (kind, motif))
                fragments = digest_sequence(sequence, enzyme, circular)["fragments"]
                cut_end = fragments[0]
                self.assertEqual((cut_end["right_geometry"], cut_end["right_overhang"]), (kind, motif))

    def test_type_iis_site_outside_linear_fragment_is_not_a_digest_cut(self):
        sequence = "AAAGGTCTC"
        query = find_restriction_sites(sequence, ["BsaI"])["enzymes"]["BsaI"]
        hit = query["cuts"][0]
        self.assertFalse(hit["cuts_within_sequence"])
        self.assertIsNone(hit["overhang_sequence"])
        self.assertEqual(query["cut_count"], 0)
        self.assertEqual(query["recognition_count"], 1)
        self.assertEqual(digest_sequence(sequence, "BsaI")["cut_count"], 0)

    def test_candidate_gate_rejects_empty_or_incomplete_evidence(self):
        reports = [None, {}, {"all_applicable_pass": True},
                   {"all_applicable_pass": True, "guardrail_status_table": {}},
                   *({"all_applicable_pass": True, "guardrail_status_table": {"check": {"applicable": True, "status": status}}}
                     for status in ("FAIL", "UNKNOWN", "INCOMPLETE", "N/A")),
                   {"all_applicable_pass": True, "guardrail_status_table": {"check": {"applicable": False, "status": "N/A"}}}]
        with patch("core.runtime_gate._promote_verified_candidate") as promote:
            for report in reports:
                with self.subTest(report=report), self.assertRaises(GateRejected):
                    finalize_candidate_construct("missing.gb", "missing.fasta", "unused", {}, report, True)
            promote.assert_not_called()

    def test_gate_rechecks_annotated_candidate(self):
        record = SeqRecord(Seq("ATGAAATAACCCTAA"), id="broken", annotations={"molecule_type": "DNA", "topology": "linear"})
        record.features = [SeqFeature(FeatureLocation(0, len(record), strand=1), type="CDS", qualifiers={"label": ["broken"]})]
        # A structurally valid, passing report for a different sequence of the
        # same length must not authorize this broken annotated candidate.
        report = quick_biological_sanity_check("ATGAAACCCGGGTAA", is_cds=True)
        self.assertTrue(report["all_applicable_pass"])
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "candidate.gb"
            with path.open("w", encoding="utf-8") as handle:
                SeqIO.write(record, handle, "genbank")
            with patch("core.runtime_gate._promote_verified_candidate") as promote, self.assertRaises(GateRejected):
                finalize_candidate_construct(path, "missing.fasta", directory, {}, report, True)
            promote.assert_not_called()

    def test_goal_rejects_self_consistent_wrong_product(self):
        handler = CompositePipelineHandler()
        record = SeqRecord(Seq("ATGCCCGTATAC"), annotations={"topology": "linear"})
        for spec in ({"expected_components": [{"name": "wanted", "sequence": "GATTACA"}]},
                     {"forbidden_components": [{"name": "excluded", "sequence": "CCCGTA"}]},
                     {"expected_components": [{"name": "wanted", "sequence": "GTATACGGGCAT", "strand": 1}]},
                     {"expected_components": ["unknown"]}):
            with self.subTest(spec=spec):
                task = {**spec, "product": {"topology": "linear"}}
                ok, traces, errors = handler.validate_goal(task, {}, {}, record, str(record.seq))
                self.assertFalse(ok)
                self.assertTrue(errors)

    def test_goal_finds_forbidden_sequence_after_annotation_is_removed(self):
        task, _ = real_cloning_task(self.vector_path, self.donor_path)
        product = resolve_sequence_record(self.vector_path)
        product.features = []
        ok, _, errors = CompositePipelineHandler().validate_goal(task, {}, {}, product, str(product.seq))
        self.assertFalse(ok)
        self.assertTrue(any("FORBIDDEN_COMPONENT_PRESENT" in e for e in errors))

    def test_native_dna_retains_negative_join_and_qualifiers(self):
        if self.external:
            record = resolve_sequence_record(ROOT / "fixtures/golden/pDEST-EmGFP.gb")
            record.features = [f for f in record.features if f.qualifiers.get("label") == ["AmpR"]]
        else:
            record = SeqRecord(Seq("ATGAAACCCGGGTTTAAAGGGCCCTAA"), id="synthetic_join",
                               annotations={"molecule_type": "DNA", "topology": "circular"})
            record.features = [SeqFeature(CompoundLocation([FeatureLocation(18, 24, strand=-1),
                FeatureLocation(3, 9, strand=-1)]), type="CDS", qualifiers={"label": ["synthetic_reverse_join"]})]
        record.features[0].qualifiers["note"] = ["骨架注释", "second value"]
        with tempfile.TemporaryDirectory() as directory:
            paths = export_snapgene(record, directory)
            observed = resolve_sequence_record(paths["dna_file"])
        self.assertEqual(str(observed.features[0].location), str(record.features[0].location))
        self.assertEqual(str(observed.features[0].extract(observed.seq)), str(record.features[0].extract(record.seq)))
        self.assertEqual(observed.features[0].qualifiers["note"], ["骨架注释", "second value"])

    def test_multistep_cloning_sequence_and_annotations(self):
        task, expected = real_cloning_task(self.vector_path, self.donor_path)
        with tempfile.TemporaryDirectory() as directory:
            task, construction = plan(task)
            construction = json.loads(json.dumps(construction))
            result = execute(task, construction, pathlib.Path(directory))
            report = validate(task, construction, result)
            self.assertEqual(report["overall"], "verified", report["errors"])
            for key in ("product_gb", "product_dna"):
                observed = resolve_sequence_record(result[key])
                self.assertEqual(str(observed.seq).upper(), expected)
                features = {f.qualifiers["label"][0]: f for f in observed.features}
                self.assertEqual(set(features), {"KanR", "ori", "rrnB T1 terminator", "rrnB T2 terminator", "EmGFP"})
                self.assertEqual(str(features["EmGFP"].extract(observed.seq)), expected[-720:])
                self.assertEqual((int(features["KanR"].location.start), int(features["KanR"].location.end)), (123, 933))
                self.assertEqual((int(features["EmGFP"].location.start), int(features["EmGFP"].location.end)), (2057, 2777))

    def test_gibson_recipe_checks_and_delivers_annotated_record(self):
        from core.tools.sequence_ops import extract_subsequence
        from scripts.run_recipe import run_recipe_cli
        vector = resolve_sequence_record(self.vector_path)
        backbone = resolve_sequence_record(extract_subsequence(vector, 2744, 331, topology="circular"))
        with tempfile.TemporaryDirectory() as directory:
            result = run_recipe_cli("gibson_assembly", {
                "vector_linear_seq": backbone,
                "insert_template_seq": str(self.donor_path),
                "insert_start": 25, "insert_end": 745,
            }, directory, finalize_requested=True, user_confirmed=True)
            self.assertEqual(result["authoritative_delivery"]["status"], "delivered")
            self.assertEqual(len(result["sanity_check"]["annotated_cds_audits"]), 2)
            observed = resolve_sequence_record(pathlib.Path(directory) / "authoritative/construct.dna")
            self.assertEqual(str(observed.seq), real_cloning_task(self.vector_path, self.donor_path)[1])
            self.assertEqual({f.qualifiers["label"][0] for f in observed.features},
                             {"KanR", "ori", "rrnB T1 terminator", "rrnB T2 terminator", "EmGFP"})


if __name__ == "__main__":
    unittest.main()
