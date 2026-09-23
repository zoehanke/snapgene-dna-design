"""File-decoding and optional installer contracts at actual public seams.

Installer subprocesses are replaced to exercise offline/failure outcomes;
these tests never install software or claim real-engine validation.
"""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import primer3_core_backend as primer3
import sg_common


class SequenceFileBoundaryTests(unittest.TestCase):
    def test_multi_reader_utf8_bom_and_legacy_description(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bom = root / "带BOM.fa"
            legacy = root / "legacy.fa"
            bom.write_text(">来源\nACGT\n", encoding="utf-8-sig")
            legacy.write_bytes(">café source\nTGCA\n".encode("latin-1"))
            records = sg_common.load_sequence_records([bom, legacy])
            self.assertEqual([(r.id, str(r.seq)) for r in records],
                             [("来源", "ACGT"), ("café", "TGCA")])
            # Both parser attempts must close their files, even on Windows.
            legacy.unlink()
            bom.unlink()

    def test_unknown_extension_uses_format_detection_but_bad_fasta_is_not_reinterpreted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            record = SeqRecord(Seq("ATGCGTAC"), id="example", name="example")
            record.annotations["molecule_type"] = "DNA"
            unknown, mislabeled = root / "sequence.txt", root / "sequence.fa"
            with unknown.open("w", encoding="utf-8") as handle:
                SeqIO.write(record, handle, "genbank")
            mislabeled.write_bytes(unknown.read_bytes())
            loaded = sg_common.load_sequence_records([unknown])
            self.assertEqual([(r.id, str(r.seq)) for r in loaded], [("example", "ATGCGTAC")])
            with self.assertRaises(ValueError):
                sg_common.load_sequence_records([mislabeled])
            for path, expected_success in ((unknown, True), (mislabeled, False)):
                completed = subprocess.run(
                    [sys.executable, "-X", "utf8", "-B", str(ROOT / "scripts" / "msa.py"), str(path), "--json"],
                    capture_output=True, encoding="utf-8", errors="replace")
                self.assertEqual(completed.returncode == 0, expected_success, completed.stdout + completed.stderr)
                if expected_success:
                    self.assertEqual(json.loads(completed.stdout)["data"]["sequences"],
                                     [{"id": "example", "aligned": "ATGCGTAC"}])

    def test_embl_and_empty_source_boundaries(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "source.embl"
            record = SeqRecord(Seq("AGCTTGCA"), id="TEST.1")
            record.annotations["molecule_type"] = "DNA"
            with path.open("w", encoding="utf-8") as handle:
                SeqIO.write(record, handle, "embl")
            loaded = sg_common.load_sequence_records([path])
            self.assertEqual(str(loaded[0].seq), "AGCTTGCA")
        for source in ("", " \n\t"):
            with self.assertRaisesRegex(ValueError, "Empty source"):
                sg_common.load_seq(source)
        with self.assertRaisesRegex(ValueError, "No sequence records"):
            sg_common.load_sequence_records([])

    def test_failure_envelope_keeps_unicode_reason_and_normalizes_warning(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as raised:
            sg_common.jfail("INVALID_INPUT", "来源文件无效", details={"path": "中文.fa"}, warnings="未生成产物")
        self.assertEqual(raised.exception.code, 1)
        result = json.loads(output.getvalue())
        self.assertFalse(result["ok"])
        self.assertIsNone(result["data"])
        self.assertEqual(result["error"]["message"], "来源文件无效")
        self.assertEqual(result["error"]["details"]["path"], "中文.fa")
        self.assertEqual(result["warnings"], ["未生成产物"])


class Primer3BootstrapBoundaryTests(unittest.TestCase):
    def test_missing_core_does_not_install_without_opt_in(self):
        with mock.patch.dict(os.environ, {"PRIMER3_AUTO_INSTALL": ""}), \
                mock.patch.object(primer3, "discover_primer3_core", return_value=None), \
                mock.patch.object(primer3.subprocess, "run") as run:
            self.assertIsNone(primer3.ensure_primer3_core())
            run.assert_not_called()

    def test_install_success_requires_rediscovered_binary(self):
        for verbose in (False, True):
            with self.subTest(verbose=verbose), \
                    mock.patch.object(primer3, "discover_primer3_core", side_effect=[None, "/installed/primer3_core"]), \
                    mock.patch.object(primer3, "clear_core_cache") as clear, \
                    mock.patch.object(primer3.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "ok", "")) as run, \
                    contextlib.redirect_stderr(io.StringIO()) as stderr:
                result = primer3.ensure_primer3_core(auto_install=True, verbose=verbose)
                self.assertEqual(result, "/installed/primer3_core")
                clear.assert_called_once()
                self.assertEqual(run.call_args.args[0][1:4], ["-m", "pip", "install"])
                self.assertNotIn("shell", run.call_args.kwargs)
                self.assertEqual(bool(stderr.getvalue()), verbose)

    def test_zero_exit_install_without_binary_remains_unavailable(self):
        for verbose in (False, True):
            with self.subTest(verbose=verbose), \
                    mock.patch.object(primer3, "discover_primer3_core", return_value=None), \
                    mock.patch.object(primer3.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "installed", "")), \
                    contextlib.redirect_stderr(io.StringIO()) as stderr:
                self.assertIsNone(primer3.ensure_primer3_core(auto_install=True, verbose=verbose))
                if verbose:
                    self.assertIn("executable was not found", stderr.getvalue())
                else:
                    self.assertEqual(stderr.getvalue(), "")

    def test_install_failure_and_timeout_never_claim_availability(self):
        for failure in (subprocess.CompletedProcess([], 2, "", "安装失败：无可用 wheel"),
                        subprocess.TimeoutExpired("pip", 180), OSError("cannot start pip")):
            for verbose in (False, True):
                with self.subTest(failure=type(failure).__name__, verbose=verbose), \
                        mock.patch.object(primer3, "discover_primer3_core", return_value=None), \
                        mock.patch.object(primer3.subprocess, "run") as run, \
                        contextlib.redirect_stderr(io.StringIO()) as stderr:
                    if isinstance(failure, Exception):
                        run.side_effect = failure
                    else:
                        run.return_value = failure
                    self.assertIsNone(primer3.ensure_primer3_core(auto_install=True, verbose=verbose))
                    self.assertEqual(bool(stderr.getvalue()), verbose)
                    if not isinstance(failure, Exception) and verbose:
                        self.assertIn("安装失败：无可用 wheel", stderr.getvalue())
                    self.assertEqual(run.call_args.kwargs["encoding"], "utf-8")
                    self.assertEqual(run.call_args.kwargs["errors"], "replace")

    def test_environment_opt_in_uses_same_explicit_installer_contract(self):
        with mock.patch.dict(os.environ, {"PRIMER3_AUTO_INSTALL": "true"}), \
                mock.patch.object(primer3, "discover_primer3_core", return_value=None), \
                mock.patch.object(primer3.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, "", "offline")) as run:
            self.assertIsNone(primer3.ensure_primer3_core(verbose=False))
            run.assert_called_once()

    def test_deleted_cached_binary_is_not_reported_available(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            executable = root / "primer3_core"
            executable.write_text("not executed by this discovery test", encoding="utf-8")
            with mock.patch.dict(primer3._DISCOVERED_CORE_CACHE, {}, clear=True):
                self.assertEqual(primer3.discover_primer3_core(executable), str(executable.resolve()))
                executable.unlink()
                self.assertIsNone(primer3.discover_primer3_core(executable))

    def test_env_path_precedes_path_but_missing_candidates_are_not_available(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            preferred, path_candidate = root / "preferred", root / "path-candidate"
            for path in (preferred, path_candidate):
                path.write_text("discovery only", encoding="utf-8")
                path.chmod(0o755)
            with mock.patch.dict(primer3._DISCOVERED_CORE_CACHE, {}, clear=True), \
                    mock.patch.dict(os.environ, {"PRIMER3_CORE": str(preferred)}), \
                    mock.patch.object(primer3.shutil, "which", return_value=str(path_candidate)), \
                    mock.patch("glob.glob", return_value=[]):
                self.assertEqual(primer3.discover_primer3_core(), str(preferred.resolve()))
                preferred.unlink()
                self.assertEqual(primer3.discover_primer3_core(), str(path_candidate.resolve()))
                path_candidate.unlink()
                with mock.patch.object(sys, "path", [""]):
                    self.assertIsNone(primer3.discover_primer3_core())

    def test_complete_oligo_qc_requires_real_engine_instead_of_heuristic_pass(self):
        with mock.patch.object(primer3, "discover_primer3_core", return_value=None), \
                mock.patch.object(primer3, "run_boulder") as run:
            with self.assertRaisesRegex(primer3.Primer3CoreError, "requires primer3_core"):
                primer3.check_complete_oligo_pair("ACGT" * 5, "TGCA" * 5)
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
