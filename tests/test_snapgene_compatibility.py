# -*- coding: utf-8 -*-
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
SCRIPTS = ROOT / "scripts"
FIXTURES = ROOT / "fixtures" / "rich"
sys.path.insert(0, str(SCRIPTS))

import export_delivery_bundle  # noqa: E402
import snapgene_compatibility  # noqa: E402
import validate_roundtrip  # noqa: E402
import generate_design_report  # noqa: E402


class SnapGeneCompatibilityTests(unittest.TestCase):
    def assessment(self, name):
        return snapgene_compatibility.analyze(str(FIXTURES / (name + ".gb")))

    def run_script(self, name, *args):
        return subprocess.run(
            [sys.executable, "-X", "utf8", str(SCRIPTS / name)] + list(args),
            cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=60)

    def test_simple_construct_allows_native_convenience_file(self):
        result = self.assessment("rich_rev_cds")
        self.assertTrue(result["formats"]["snapgene-gb"]["core_safe"])
        self.assertTrue(result["formats"]["dna"]["core_safe"])

    def test_empty_and_unlabelled_features_have_safe_fallbacks(self):
        empty = SeqRecord(Seq("ATGC"), id="raw")
        result = snapgene_compatibility.analyze_record(empty, "raw")
        self.assertEqual(result["formats"]["snapgene-gb"]["delivery_grade"],
                         "safe")
        feature = SeqFeature(FeatureLocation(0, 2), type="misc_feature")
        empty.features.append(feature)
        result = snapgene_compatibility.analyze_record(empty, "raw")
        self.assertEqual(result["feature_count"], 1)

    def test_order_is_core_risk_in_both_snapgene_paths(self):
        result = self.assessment("rich_order")
        for fmt in ("snapgene-gb", "dna"):
            self.assertFalse(result["formats"][fmt]["core_safe"])
            codes = {item["code"] for item in result["formats"][fmt]["findings"]}
            self.assertIn("ORDER_LOCATION_NOT_PRESERVED", codes)
        self.assertTrue(result["recommendation"]["manual_review_required"])

    def test_join_and_unicode_block_native_dna(self):
        join = self.assessment("rich_join")
        unicode_result = self.assessment("rich_unicode")
        self.assertFalse(join["formats"]["dna"]["core_safe"])
        self.assertFalse(unicode_result["formats"]["dna"]["core_safe"])

    def test_snapgene_normalizations_are_strict_not_core_risks(self):
        result = self.assessment("rich_multivalue")
        gb = result["formats"]["snapgene-gb"]
        self.assertTrue(gb["core_safe"])
        self.assertFalse(gb["strict_safe"])
        self.assertEqual(gb["delivery_grade"], "core-compatible")

    def test_operator_participates_in_core_comparison(self):
        expected = SeqIO.read(str(FIXTURES / "rich_order.gb"), "genbank")
        observed = SeqIO.read(str(FIXTURES / "rich_order.gb"), "genbank")
        observed.features[0].location.operator = "join"
        comparison = validate_roundtrip.compare_records(expected, observed)
        self.assertFalse(comparison["features_equal"])
        self.assertFalse(comparison["passed"])

    def test_bundle_omits_risky_native_file_and_is_preview_class(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = export_delivery_bundle.build_bundle(
                str(FIXTURES / "rich_unicode.gb"), temp_dir)
            root = pathlib.Path(temp_dir)
            self.assertFalse(result["native_dna_written"])
            self.assertTrue(list(root.glob("*.preview.gb")))
            self.assertFalse(list(root.glob("*.dna")))
            manifest = json.loads((root / "DELIVERY-MANIFEST.json").read_text(
                encoding="utf-8"))
            self.assertFalse(manifest["native_dna_written"])
            self.assertEqual(manifest["artifact_class"], "preview")
            self.assertTrue(manifest["not_authoritative"])

    def test_bundle_can_explicitly_opt_in_to_core_risk(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = export_delivery_bundle.build_bundle(
                str(FIXTURES / "rich_join.gb"), temp_dir,
                allow_core_risk=True)
            self.assertTrue(result["native_dna_written"])
            manifest = json.loads((pathlib.Path(temp_dir) /
                                   "DELIVERY-MANIFEST.json").read_text(
                                       encoding="utf-8"))
            self.assertTrue(manifest["native_dna_core_risk_accepted"])

    def test_require_dna_fails_before_claiming_success(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(ValueError, "blocked by core"):
                export_delivery_bundle.build_bundle(
                    str(FIXTURES / "rich_order.gb"), temp_dir,
                    require_dna=True)

    def test_design_report_includes_compatibility_findings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            compatibility_path = pathlib.Path(temp_dir) / "compat.json"
            compatibility_path.write_text(json.dumps(
                self.assessment("rich_order"), ensure_ascii=False),
                encoding="utf-8")
            report = generate_design_report.build_report(
                "compatibility", [], [], [], [compatibility_path])
            self.assertEqual(report["summary"]["compatibility_reports"], 1)
            self.assertGreater(report["summary"]["risks"], 0)
            self.assertIn("SnapGene compatibility",
                          generate_design_report.render_html(report))

    def test_preflight_cli_json_text_and_error_paths(self):
        order = str(FIXTURES / "rich_order.gb")
        completed = self.run_script(
            "snapgene_compatibility.py", order, "--json")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertFalse(json.loads(completed.stdout)["data"]["formats"]
                         ["dna"]["core_safe"])
        completed = self.run_script(
            "snapgene_compatibility.py", str(FIXTURES / "rich_rev_cds.gb"))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("SnapGene delivery preflight", completed.stdout)
        completed = self.run_script(
            "snapgene_compatibility.py", "missing.gb", "--json")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("not found", completed.stderr)

    def test_delivery_cli_json_text_and_blocking_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            completed = self.run_script(
                "export_delivery_bundle.py",
                str(FIXTURES / "rich_rev_cds.gb"),
                "--out-dir", str(pathlib.Path(temp_dir) / "json"), "--json")
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue(json.loads(completed.stdout)["data"]
                            ["native_dna_written"])
            completed = self.run_script(
                "export_delivery_bundle.py",
                str(FIXTURES / "rich_unicode.gb"),
                "--out-dir", str(pathlib.Path(temp_dir) / "text"))
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("native .dna: omitted", completed.stdout)
            completed = self.run_script(
                "export_delivery_bundle.py",
                str(FIXTURES / "rich_order.gb"),
                "--out-dir", str(pathlib.Path(temp_dir) / "blocked"),
                "--require-dna")
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("blocked by core", completed.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
