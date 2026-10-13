# -*- coding: utf-8 -*-
"""Academic-only real-fixture license checker tests."""

from repository_paths import PROJECT_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
import zipfile

HERE = pathlib.Path(__file__).resolve().parent
ROOT = SKILL_ROOT
SCRIPTS = ROOT / "scripts"


@unittest.skipUnless(
    (ROOT / "fixtures" / "pDONR201.dna").exists(),
    "academic SnapGene fixtures are not present")
class RealLicenseHashCheckerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="v06-license-real-")
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

    def test_real_restricted_file_is_detected_even_when_renamed(self):
        target = self.tmp_path / "pkg"
        target.mkdir()
        source = ROOT / "fixtures" / "pDONR201.dna"
        (target / "renamed.dna").write_bytes(source.read_bytes())
        archive = self._zip_dir(target, "real.zip")
        rc, report = self._run_checker(archive)
        self.assertEqual(rc, 1)
        self.assertFalse(report["ok"])


if __name__ == "__main__":
    unittest.main()
