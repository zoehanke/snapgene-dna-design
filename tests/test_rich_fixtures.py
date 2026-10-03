# -*- coding: utf-8 -*-
"""Rich-feature strict round-trip tests (synthetic fixtures, both packages).

Covers the v0.5 formal gate checklist: forward/reverse CDS, CompoundLocation
(join/order), cross-origin features, Unicode and multi-value qualifiers.
Fixtures are fully synthetic (``fixtures/rich/``), so they are safe for both
the academic-full and the redistributable packages.
"""

from repository_paths import PROJECT_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS
import pathlib
import sys
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
ROOT = SKILL_ROOT
SCRIPTS = ROOT / "scripts"
FIXTURES = ROOT / "fixtures" / "rich"
sys.path.insert(0, str(SCRIPTS))

import validate_roundtrip  # noqa: E402

RICH_FIXTURES = (
    "rich_fwd_cds", "rich_rev_cds", "rich_join", "rich_order",
    "rich_cross_origin", "rich_unicode", "rich_multivalue",
    "rich_kitchen_sink",
)


class RichFixtureRoundTripTests(unittest.TestCase):
    def setUp(self):
        if not FIXTURES.is_dir():
            self.skipTest("fixtures/rich not present in this package")

    def test_snapgene_gb_strict_roundtrip_preserves_everything(self):
        failures = []
        for name in RICH_FIXTURES:
            fixture = FIXTURES / (name + ".gb")
            if not fixture.exists():
                failures.append("%s: fixture missing" % name)
                continue
            with mock.patch("validate_roundtrip.find_snapgene_executable", return_value=None):
                result = validate_roundtrip.validate(
                    str(fixture), "snapgene-gb", strict=True)
            if not result["core_passed"]:
                failures.append("%s: core failed" % name)
            if not result["strict_passed"]:
                failures.append(
                    "%s: strict failed (grade=%s)"
                    % (name, result["delivery_grade"]))
        self.assertEqual(failures, [], "; ".join(failures))

    def test_official_order_operator_boundary_is_explicit(self):
        fixture = FIXTURES / "rich_order.gb"
        executable = validate_roundtrip.find_snapgene_executable()
        if executable is None:
            self.skipTest("SnapGene executable not installed")
        result = validate_roundtrip.validate(
            str(fixture), "snapgene-gb", snapgene_exe=str(executable), strict=True
        )
        self.assertTrue(result["internal_roundtrip"]["passed"], result)
        self.assertFalse(result["official_snapgene_roundtrip"]["features_equal"], result)
        self.assertFalse(result["core_passed"], result)

    def test_native_dna_roundtrip_matches_declared_compatibility(self):
        failures = []
        for name in RICH_FIXTURES:
            fixture = FIXTURES / (name + ".gb")
            if not fixture.exists():
                continue
            result = validate_roundtrip.validate(
                str(fixture), "dna", strict=True)
            from snapgene_compatibility import analyze
            policy = analyze(str(fixture))["formats"]["dna"]
            if not result["core_passed"] and policy["core_safe"]:
                failures.append("%s: unclassified dna core failure" % name)
        self.assertEqual(failures, [], "; ".join(failures))

    def test_known_risky_fixtures_are_not_called_lossless(self):
        from snapgene_compatibility import analyze
        for name in ("rich_join", "rich_order", "rich_unicode"):
            result = analyze(str(FIXTURES / (name + ".gb")))
            self.assertFalse(result["formats"]["dna"]["core_safe"], name)

    def test_cross_origin_cds_extract_matches_source(self):
        from Bio import SeqIO
        from Bio.Seq import Seq
        from Bio.SeqFeature import CompoundLocation
        fixture = FIXTURES / "rich_cross_origin.gb"
        record = SeqIO.read(str(fixture), "genbank")
        feature = next(f for f in record.features
                       if f.type == "CDS")
        self.assertIsInstance(feature.location, CompoundLocation)
        extract = str(feature.extract(record.seq))
        self.assertEqual(len(extract), 9)
        self.assertEqual(feature.qualifiers["translation"],
                         [str(Seq(extract).translate())])

    def test_unicode_and_multivalue_qualifiers_survive_export(self):
        from Bio import SeqIO
        fixture = FIXTURES / "rich_unicode.gb"
        with open(fixture, "r", encoding="utf-8") as fh:
            record = SeqIO.read(fh, "genbank")
        feature = next(f for f in record.features)
        self.assertIn("引物设计", feature.qualifiers["note"][0])

        multi = FIXTURES / "rich_multivalue.gb"
        with open(multi, "r", encoding="utf-8") as fh:
            record = SeqIO.read(fh, "genbank")
        feature = next(f for f in record.features)
        self.assertEqual(len(feature.qualifiers["note"]), 4)
        self.assertEqual(len(feature.qualifiers["db_xref"]), 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
