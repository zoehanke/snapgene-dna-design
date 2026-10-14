# -*- coding: utf-8 -*-
"""v0.4.4 tests: zero contributions, clip_end, JSON schemas, property tests."""

from repository_paths import PROJECT_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS
import json
import pathlib
import random
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

from jsonschema import Draft202012Validator, validate as schema_validate
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import CompoundLocation, FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

HERE = pathlib.Path(__file__).resolve().parent
ROOT = SKILL_ROOT
SCRIPTS = ROOT / "scripts"
SCHEMAS = ROOT / "references" / "schemas"
sys.path.insert(0, str(SCRIPTS))

import simulate_advanced  # noqa: E402
import simulate_cloning  # noqa: E402
from assembly_model import AssemblyError  # noqa: E402


def run_script(name, *args):
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(SCRIPTS / name)] + list(args),
        cwd=str(SCRIPTS), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )


def load_schema(name):
    with open(SCHEMAS / name, encoding="utf-8") as handle:
        return json.load(handle)


class ZeroContributionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="v06-zero-")
        self.addCleanup(self.tmp.cleanup)
        self.tmp_path = pathlib.Path(self.tmp.name)

    def _write(self, name, sequence):
        path = self.tmp_path / name
        path.write_text(">%s\n%s\n" % (name, sequence), encoding="utf-8")
        return path

    def test_circular_zero_contribution_fails_with_stable_error(self):
        a = self._write("a.fa", "AAAA")
        b = self._write("b.fa", "AAAA")
        out = self.tmp_path / "out.gb"
        completed = run_script(
            "simulate_cloning.py", "--method", "gibson",
            "--parts", str(a), str(b), "--overlap", "4",
            "--topology", "circular", "--out", str(out), "--json")
        self.assertNotEqual(completed.returncode, 0)
        payload = json.loads(completed.stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "ZERO_CONTRIBUTION_FRAGMENT")
        self.assertFalse(out.exists())

    def test_linear_zero_contribution_fails(self):
        a = self._write("a.fa", "AAAACCCC")
        b = self._write("b.fa", "CCCC")
        completed = run_script(
            "simulate_advanced.py", "--method", "infusion",
            "--parts", str(a), str(b), "--overlap", "4", "--json")
        self.assertNotEqual(completed.returncode, 0)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["error"]["code"], "ZERO_CONTRIBUTION_FRAGMENT")
        self.assertIn("schema_version", payload)
        self.assertEqual(payload["data"], None)


class ClipEndTests(unittest.TestCase):
    def _record(self, sequence, feature_start, feature_end, strand=1):
        record = SeqRecord(
            Seq(sequence), id="clip", name="clip",
            annotations={"molecule_type": "DNA", "topology": "linear"})
        record.features.append(SeqFeature(
            FeatureLocation(feature_start, feature_end, strand=strand),
            type="misc_feature", qualifiers={"label": ["clip_feat"]}))
        return record

    def test_feature_beyond_clip_end_is_not_migrated(self):
        record = self._record("AAAACCCCGGGG", 8, 12)
        features, warnings = simulate_cloning._shift_features(
            record, 0, trim_start=0, clip_end=8, circular=False,
            is_first=True, product_length=8, product_seq="AAAACCCC")
        self.assertEqual(features, [])
        self.assertEqual(warnings, [])

    def test_feature_crossing_clip_end_fails_or_is_dropped_explicitly(self):
        record = self._record("AAAACCCCGGGG", 4, 10)
        with self.assertRaises(AssemblyError) as context:
            simulate_cloning._shift_features(
                record, 0, trim_start=0, clip_end=8, circular=True,
                is_first=True, product_length=8, product_seq="AAAACCCC")
        self.assertEqual(context.exception.code, "FEATURE_MIGRATION_MISMATCH")


class SchemaContractTests(unittest.TestCase):
    def test_schemas_validate_real_outputs(self):
        envelope_schema = load_schema("common-envelope-v0.5.json")
        assembly_schema = load_schema("assembly-result-v0.5.json")
        roundtrip_schema = load_schema("roundtrip-result-v0.5.json")

        # success envelope + assembly payload
        tmp = tempfile.TemporaryDirectory(prefix="v06-schema-")
        self.addCleanup(tmp.cleanup)
        a = pathlib.Path(tmp.name) / "a.fa"
        b = pathlib.Path(tmp.name) / "b.fa"
        overlap = "ACGTACGTACGT"
        a.write_text(">a\nAAAA" + overlap + "\n")
        b.write_text(">b\n" + overlap + "GGGG\n")
        completed = run_script(
            "simulate_cloning.py", "--method", "gibson",
            "--parts", str(a), str(b), "--overlap", "12", "--json")
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        payload = json.loads(completed.stdout)
        schema_validate(payload, envelope_schema)
        schema_validate(payload["data"], assembly_schema)

        # failure envelope
        bad_a = pathlib.Path(tmp.name) / "bad_a.fa"
        bad_a.write_text(">a\nAAAA\n")
        completed = run_script(
            "simulate_cloning.py", "--method", "gibson",
            "--parts", str(bad_a), str(bad_a), "--overlap", "4",
            "--topology", "circular", "--json")
        self.assertNotEqual(completed.returncode, 0)
        payload = json.loads(completed.stdout)
        schema_validate(payload, envelope_schema)

        # roundtrip result (no official SnapGene required); the fixture is
        # academic-only, so in the redistributable package this part must be
        # an explicit, visible skip - never a silent pass.
        pdonr = ROOT / "fixtures" / "pDONR201.dna"
        if not pdonr.exists():
            self.skipTest("fixtures/pDONR201.dna not present (academic-only)")
        completed = run_script(
            "validate_roundtrip.py", str(pdonr),
            "--format", "snapgene-gb", "--json")
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        payload = json.loads(completed.stdout)
        schema_validate(payload["data"], roundtrip_schema)

    def test_schema_rejects_invalid_variants(self):
        envelope_schema = load_schema("common-envelope-v0.5.json")
        assembly_schema = load_schema("assembly-result-v0.5.json")
        validator = Draft202012Validator(assembly_schema)
        valid = {
            "method": "gibson", "experimental": False, "product_length": 8,
            "topology": "linear", "origins": [], "fragments": [],
            "junctions": [], "feature_count": 0, "product_sequence": "A" * 8,
        }
        schema_validate(valid, assembly_schema)

        bad_missing_field = dict(valid)
        del bad_missing_field["product_sequence"]
        self.assertTrue(list(validator.iter_errors(bad_missing_field)))

        bad_wrong_type = dict(valid)
        bad_wrong_type["product_length"] = "eight"
        self.assertTrue(list(validator.iter_errors(bad_wrong_type)))

        bad_illegal_coord = dict(valid)
        bad_illegal_coord["origins"] = [{
            "part": "a", "name": "a", "start": 0, "end": -1,
            "length": 0, "contribution_segments": [], "source_mappings": [],
        }]
        self.assertTrue(list(validator.iter_errors(bad_illegal_coord)))


        env_validator = Draft202012Validator(envelope_schema)
        env_valid = {
            "schema_version": "0.5.0", "ok": True, "command": "test",
            "data": {}, "warnings": [],
        }
        schema_validate(env_valid, envelope_schema)
        unknown = dict(env_valid); unknown["unexpected"] = True
        self.assertTrue(list(env_validator.iter_errors(unknown)))
        ok_true_error = dict(env_valid); ok_true_error["error"] = {"code": "X", "message": "Y"}
        self.assertTrue(list(env_validator.iter_errors(ok_true_error)))
        ok_false_data = dict(env_valid); ok_false_data["ok"] = False; ok_false_data["data"] = {}; ok_false_data["error"] = {"code": "X", "message": "Y"}
        self.assertTrue(list(env_validator.iter_errors(ok_false_data)))
        bad_warnings = dict(env_valid); bad_warnings["warnings"] = [1]
        self.assertTrue(list(env_validator.iter_errors(bad_warnings)))
        bad_version = dict(env_valid); bad_version["schema_version"] = "0.4.0"
        self.assertTrue(list(env_validator.iter_errors(bad_version)))
        bad_error = dict(env_valid); bad_error["ok"] = False; bad_error["error"] = {"message": "Y"}
        self.assertTrue(list(env_validator.iter_errors(bad_error)))


class GeneralLicenseHashCheckerTests(unittest.TestCase):
    """Synthetic-byte hash tests that run in BOTH packages without fixtures."""
    SYNTHETIC_HASH = "75DCF9DA0FC9CFA5AC2A2124EA2CAFEF8CBE08ED5EB25EEFFA700B1536E38C18"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="v06-license-")
        self.addCleanup(self.tmp.cleanup)
        self.tmp_path = pathlib.Path(self.tmp.name)

    def _run_checker(self, target, *extra):
        completed = subprocess.run(
            [sys.executable, "-X", "utf8",
             str(TOOLS_ROOT / 'check_redistributable.py'), str(target)] + list(extra),
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        return completed.returncode, json.loads(completed.stdout)

    def _zip_dir(self, directory, name):
        archive = self.tmp_path / name
        with zipfile.ZipFile(archive, "w") as zf:
            for path in sorted(directory.rglob("*")):
                if path.is_file():
                    zf.write(path, path.relative_to(directory).as_posix())
        return archive

    def _synthetic_restricted_bytes(self):
        import check_redistributable as checker
        digest = self.SYNTHETIC_HASH
        base = next(iter(checker.RESTRICTED_HASHES.values()))
        with mock.patch.dict(checker.RESTRICTED_HASHES,
                             {digest: base}, clear=False):
            # Return bytes whose SHA-256 equals digest. Build once via brute force
            # is not needed: patch hash function used by checker for this test.
            with mock.patch.object(
                    checker, "_sha256", return_value=digest) as sha:
                data = b"synthetic-restricted"
                self.assertEqual(sha(data), digest)
                return data

    def _run_with_injected_hash(self, directory, archive_name):
        archive = self._zip_dir(directory, archive_name)
        return self._run_checker(
            archive, "--restricted-hash",
            self.SYNTHETIC_HASH + "=fixtures/pDONR201.dna")

    def test_rename_and_subdirectory_do_not_escape_hash_detection(self):
        target = self.tmp_path / "pkg"
        target.mkdir()
        expected = []
        for path_name in ("vector.dna", "nested/renamed.dna"):
            (target / path_name).parent.mkdir(parents=True, exist_ok=True)
            (target / path_name).write_bytes(b"synthetic-restricted")
            expected.append(path_name.replace("\\", "/"))
        rc, report = self._run_with_injected_hash(target, "bad.zip")
        self.assertEqual(rc, 1)
        self.assertFalse(report["ok"])
        found_paths = {item["path"] for item in report["found"]}
        self.assertEqual(found_paths, set(expected))

    def test_modified_byte_is_not_a_false_positive(self):
        target = self.tmp_path / "pkg"
        target.mkdir()
        (target / "not-original.dna").write_bytes(b"modified-byte")
        archive = self._zip_dir(target, "modified.zip")
        rc, report = self._run_checker(archive)
        self.assertEqual(rc, 0)
        self.assertTrue(report["ok"])

    def test_same_name_different_content_is_not_false_positive(self):
        target = self.tmp_path / "pkg"
        target.mkdir()
        (target / "pDONR201.dna").write_text(">synthetic\nACGT\n")
        archive = self._zip_dir(target, "synthetic.zip")
        rc, report = self._run_checker(archive)
        self.assertEqual(rc, 0)
        self.assertTrue(report["ok"])


class SeededPropertyTests(unittest.TestCase):
    def _feature(self, record, start, end, strand, label, compound=False,
                 operator="join"):
        if compound:
            location = CompoundLocation([
                FeatureLocation(max(start, end - 2), end, strand=strand),
                FeatureLocation(start, min(end, start + 2), strand=strand),
            ], operator=operator)
        else:
            location = FeatureLocation(start, end, strand=strand)
        record.features.append(SeqFeature(
            location, type="misc_feature", qualifiers={"label": [label]}))

    def test_100_seeded_successful_assemblies_preserve_invariants(self):
        rng = random.Random(20260816)
        for case in range(100):
            n = rng.randint(2, 6)
            # v0.9 execution rejects Gibson homology shorter than 12 bp.
            ov = rng.randint(12, 20)
            circular = bool(rng.randint(0, 1))
            unique = [rng.randint(1, 12) for _ in range(n)]
            overlaps = ["".join(rng.choice("ACGT") for _ in range(ov))
                        for _ in range(n)]
            records = []
            for i, u in enumerate(unique):
                if circular:
                    seq = overlaps[i - 1] + ("A" * 0) + "".join(
                        rng.choice("ACGT") for _ in range(u)) + overlaps[i]
                else:
                    left = overlaps[i - 1] if i > 0 else ""
                    right = overlaps[i] if i < n - 1 else ""
                    body = "".join(rng.choice("ACGT") for _ in range(u))
                    seq = left + body + right
                rec = SeqRecord(
                    Seq(seq), id="f%d" % i, name="f%d" % i,
                    annotations={"molecule_type": "DNA", "topology": "linear"})
                # Add 1-3 features; circular assemblies must preserve extract.
                if circular or rng.random() < 0.5:
                    for _f in range(rng.randint(1, 3)):
                        start = rng.randint(0, len(seq))
                        end = rng.randint(start + 1, len(seq) + 1)
                        if end > len(seq):
                            end = len(seq)
                        if start >= end:
                            continue
                        strand = rng.choice([1, -1])
                        compound = rng.random() < 0.25
                        self._feature(
                            rec, start, end, strand,
                            "f%d_case%d_feat%d" % (i, case, _f),
                            compound=compound,
                            operator=rng.choice(["join", "order"]))
                records.append(rec)

            product, fragments, contributions, warnings = simulate_cloning.gibson(
                records, overlap=ov, circular=circular)
            expected_seq = "".join(
                str(rec.seq[ov:]) for rec in records) if circular else (
                    str(records[0].seq)
                    + "".join(str(rec.seq[ov:]) for rec in records[1:]))
            self.assertEqual(str(product.seq), str(expected_seq))
            self.assertEqual(len(product.seq), sum(contributions))
            self.assertEqual(str(product.seq), str(expected_seq))

            for rec in records:
                for source_feature in rec.features:
                    label = source_feature.qualifiers["label"][0]
                    migrated = next(
                        (f for f in product.features
                         if label in f.qualifiers.get("label", [])), None)
                    if migrated is None:
                        # Linear assembly may explicitly drop a feature that
                        # crosses a removed overlap; warn only, never silently.
                        if not circular:
                            continue
                    self.assertIsNotNone(migrated, label)
                    self.assertEqual(
                        str(source_feature.extract(rec.seq)).upper(),
                        str(migrated.extract(product.seq)).upper(),
                        "feature extract changed in case %d" % case)

            product.annotations.setdefault("molecule_type", "DNA")
            gb = pathlib.Path(tempfile.mkdtemp()) / "p.gb"
            with open(gb, "w", encoding="utf-8") as handle:
                SeqIO.write(product, handle, "genbank")
            reread = SeqIO.read(str(gb), "genbank")
            self.assertEqual(str(reread.seq), str(product.seq))

    def test_seeded_zero_contribution_failures_are_stable(self):
        rng = random.Random(20260817)
        for _case in range(20):
            ov = rng.randint(2, 10)
            circular = bool(rng.randint(0, 1))
            records = []
            for i in range(2):
                seq = "A" * rng.randint(1, ov)
                records.append(SeqRecord(
                    Seq(seq), id="f%d" % i, name="f%d" % i,
                    annotations={"molecule_type": "DNA", "topology": "linear"}))
            with self.assertRaises(AssemblyError) as context:
                simulate_cloning.gibson(records, overlap=ov, circular=circular)
            self.assertIn(
                context.exception.code,
                {"ZERO_CONTRIBUTION_FRAGMENT", "PRODUCT_SHORTER_THAN_OVERLAP",
                 "OVERLAP_TOO_LONG"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
