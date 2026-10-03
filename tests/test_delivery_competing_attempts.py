"""Competing real exports must preserve the winner and reject the loser."""

from repository_paths import PROJECT_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import threading
import unittest
import os
from unittest.mock import patch

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

from core.guardrails.checklist import quick_biological_sanity_check
from core.runtime_gate import GateRejected, finalize_candidate_construct
from core.tools.snapgene_io import read_native_dna_record


class CompetingDeliveryTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Requires actual Windows file-sharing semantics")
    def test_transient_windows_lock_retries_but_persistent_lock_stays_failed(self):
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
            ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record = SeqRecord(Seq("ATGGCTTAA"), id="candidate",
                annotations={"molecule_type": "DNA", "topology": "linear"},
                features=[SeqFeature(FeatureLocation(0, 9, strand=1), type="CDS")])
            gb, fasta = root/"candidate.gb", root/"candidate.fasta"
            for path, fmt in ((gb, "genbank"), (fasta, "fasta")):
                with path.open("w", encoding="utf-8") as stream:
                    SeqIO.write(record, stream, fmt)
            sanity = quick_biological_sanity_check(record, topology="linear")
            real_replace = Path.replace
            for transient in (True, False):
                with self.subTest(transient=transient):
                    attempts, handles, timers = [], [], []
                    destination = root/str(transient)

                    def locked_replace(path, target):
                        attempts.append(path)
                        if not handles:
                            # A real read handle without FILE_SHARE_DELETE.
                            handle = kernel.CreateFileW(str(path/"construct.dna"), 0x80000000,
                                                        3, None, 3, 0x80, None)
                            self.assertNotEqual(handle, ctypes.c_void_p(-1).value)
                            handles.append(handle)
                            if transient:
                                timer = threading.Timer(0.03, kernel.CloseHandle, [handle])
                                timers.append(timer)
                                timer.start()
                        return real_replace(path, target)

                    try:
                        with patch.object(Path, "replace", locked_replace):
                            if transient:
                                finalize_candidate_construct(gb, fasta, destination,
                                    {"recipe": "Windows lock test"}, sanity, user_confirmed=True)
                            else:
                                with self.assertRaises(PermissionError):
                                    finalize_candidate_construct(gb, fasta, destination,
                                        {"recipe": "Windows lock test"}, sanity, user_confirmed=True)
                    finally:
                        for timer in timers:
                            timer.join()
                        if not transient:
                            for handle in handles:
                                kernel.CloseHandle(handle)
                    self.assertGreater(len(attempts), 1)
                    self.assertEqual(len(set(attempts)), 1)
                    self.assertEqual((destination/"authoritative").exists(), transient)
                    if transient:
                        self.assertEqual(str(read_native_dna_record(destination/"authoritative/construct.dna").seq), "ATGGCTTAA")
                    self.assertTrue(gb.is_file())

    def test_same_destination_has_one_complete_winner_and_explicit_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidates = []
            for index, sequence in enumerate(("ATGGCTTAA", "ATGAAATAA")):
                record = SeqRecord(Seq(sequence), id="candidate",
                    annotations={"molecule_type": "DNA", "topology": "linear"},
                    features=[SeqFeature(FeatureLocation(0, 9), type="CDS", qualifiers={"label": ["gene"]})])
                gb, fasta = root/f"candidate{index}.gb", root/f"candidate{index}.fasta"
                for path, format_name in ((gb, "genbank"), (fasta, "fasta")):
                    with path.open("w", encoding="utf-8") as stream:
                        SeqIO.write(record, stream, format_name)
                candidates.append((gb, fasta, quick_biological_sanity_check(record, topology="linear")))

            # Both attempts pass the initial existence check. The barrier
            # coordinates real staging directories; export/readback is real.
            barrier = threading.Barrier(2)
            make_directory = tempfile.mkdtemp

            def synchronized_staging(*args, **kwargs):
                path = make_directory(*args, **kwargs)
                barrier.wait(timeout=30)
                return path

            def deliver(candidate):
                gb, fasta, sanity = candidate
                try:
                    finalize_candidate_construct(gb, fasta, root/"delivery",
                        {"recipe": "concurrent test"}, sanity, user_confirmed=True)
                    return "delivered"
                except GateRejected as error:
                    return error.error_code

            with patch("core.runtime_gate.tempfile.mkdtemp", side_effect=synchronized_staging):
                with ThreadPoolExecutor(max_workers=2) as executor:
                    results = list(executor.map(deliver, candidates))
            self.assertCountEqual(results, ["delivered", "GATE_AUTHORITATIVE_ALREADY_EXISTS"])
            delivered = root/"delivery"/"authoritative"
            actual = read_native_dna_record(delivered/"construct.dna")
            self.assertIn(str(actual.seq), ("ATGGCTTAA", "ATGAAATAA"))
            manifest = json.loads((delivered/"DELIVERY-MANIFEST.json").read_text(encoding="utf-8"))
            for name, details in manifest["files"].items():
                self.assertEqual(hashlib.sha256((delivered/name).read_bytes()).hexdigest().upper(), details["sha256"])
            self.assertFalse(list((root/"delivery").glob(".authoritative-*.tmp")))


if __name__ == "__main__":
    unittest.main()
