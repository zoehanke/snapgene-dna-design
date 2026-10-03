# -*- coding: utf-8 -*-
"""v0.3 regression tests for structured locations and JSON contracts."""

from repository_paths import PROJECT_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS
import json
import os
import subprocess
import sys
import unittest

from Bio.Restriction import BsaI, EcoRI
from Bio.Seq import Seq
from Bio.SeqFeature import CompoundLocation, FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = str(SKILL_ROOT)
SCRIPTS = os.path.join(ROOT, "scripts")
sys.path.insert(0, SCRIPTS)

from construct_model import ConstructModel, feature_to_dict  # noqa: E402
from edit_plasmid import op_linearize  # noqa: E402
from sg_common import restriction_hits  # noqa: E402
from validate_roundtrip import validate  # noqa: E402


def record_with_compound():
    record = SeqRecord(Seq("AACCGGTTAACC"), id="compound", name="compound")
    record.annotations = {"molecule_type": "DNA", "topology": "circular", "note": "keep"}
    location = CompoundLocation([
        FeatureLocation(8, 12, strand=1),
        FeatureLocation(0, 3, strand=1),
    ], operator="join")
    record.features = [SeqFeature(
        location, type="CDS", id="feat-1",
        qualifiers={"label": ["wrapped"], "note": ["preserve me"]},
    )]
    return record


class ConstructModelTests(unittest.TestCase):
    def test_insert_preserves_compound_parts_and_metadata(self):
        result = ConstructModel(record_with_compound()).insert(2, "TT").to_record()
        feature = result.features[0]
        self.assertIsInstance(feature.location, CompoundLocation)
        self.assertEqual(
            [(int(p.start), int(p.end)) for p in feature.location.parts],
            [(10, 14), (0, 5)],
        )
        self.assertEqual(feature.id, "feat-1")
        self.assertIn("preserve me", feature.qualifiers["note"])
        self.assertEqual(feature.qualifiers["partial"], ["true"])
        self.assertTrue(any("CDS interrupted by insertion" in note
                            for note in feature.qualifiers["note"]))
        self.assertEqual(result.annotations["note"], "keep")

    def test_delete_migrates_each_compound_part(self):
        result = ConstructModel(record_with_compound()).delete(1, 10).to_record()
        feature = result.features[0]
        self.assertEqual(
            [(int(p.start), int(p.end)) for p in feature.location.parts],
            [(1, 3), (0, 1)],
        )

    def test_rotate_splits_crossing_feature_without_sequence_loss(self):
        record = SeqRecord(Seq("AACCGGTTAA"), id="rotate")
        record.annotations = {"molecule_type": "DNA", "topology": "circular"}
        record.features = [SeqFeature(
            FeatureLocation(3, 8, strand=1), type="misc_feature",
            qualifiers={"label": ["cross-cut"]},
        )]
        expected_extract = str(record.features[0].extract(record.seq))
        result = ConstructModel(record).rotate(5, topology="circular").to_record()
        self.assertIsInstance(result.features[0].location, CompoundLocation)
        self.assertEqual(
            [(int(p.start), int(p.end)) for p in result.features[0].location.parts],
            [(8, 10), (0, 3)],
        )
        self.assertEqual(str(result.features[0].extract(result.seq)), expected_extract)
        exported = feature_to_dict(result.features[0], len(result.seq))
        self.assertTrue(exported["location"]["wraps_origin"])
        self.assertEqual(exported["location"]["coordinate_system"], "0-based-half-open")

    def test_linearize_accepts_compound_feature(self):
        result = op_linearize(record_with_compound(), 6)
        self.assertEqual(result.annotations["topology"], "linear")
        self.assertEqual(len(result.features), 1)
        self.assertEqual(result.features[0].qualifiers["label"], ["wrapped"])


class RestrictionModelTests(unittest.TestCase):
    def test_ecori_double_strand_boundaries(self):
        hit = restriction_hits("GGAATTCC", EcoRI)[0]
        self.assertEqual(hit["recognition_start0"], 1)
        self.assertEqual(hit["top_cut_boundary_0based"], 2)
        self.assertEqual(hit["bottom_cut_boundary_0based"], 6)

    def test_type_iis_forward_and_reverse_boundaries(self):
        forward = restriction_hits("GGTCTCAAAAAAA", BsaI)[0]
        self.assertEqual(
            (forward["top_cut_boundary_0based"], forward["bottom_cut_boundary_0based"]),
            (7, 11),
        )
        reverse = restriction_hits("AAAAAAGAGACCAAAAA", BsaI)[0]
        self.assertEqual(reverse["strand"], -1)
        self.assertEqual(
            (reverse["top_cut_boundary_0based"], reverse["bottom_cut_boundary_0based"]),
            (1, 5),
        )


class ContractAndRoundTripTests(unittest.TestCase):
    def test_json_envelope_strict_v05_shape(self):
        script = os.path.join(SCRIPTS, "find_sites.py")
        completed = subprocess.run(
            [sys.executable, script, "GGAATTCC", "--enzyme", "EcoRI", "--json"],
            cwd=SCRIPTS, capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["schema_version"], "0.5.0")
        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["length"], 8)
        self.assertNotIn("length", result)
        self.assertEqual(set(result), {"schema_version","ok","command","data","warnings"})

    def test_internal_snapgene_genbank_roundtrip(self):
        fixture = os.path.join(ROOT, "fixtures", "pDONR201.dna")
        if not os.path.exists(fixture):
            self.skipTest("fixtures/pDONR201.dna not present (academic-only)")
        result = validate(fixture, "snapgene-gb")
        self.assertTrue(result["internal_roundtrip"]["passed"], result)
        self.assertTrue(result["passed"], result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
