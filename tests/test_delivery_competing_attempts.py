"""Competing real exports must preserve the winner and reject the loser."""
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

from core.guardrails.checklist import quick_biological_sanity_check
from core.runtime_gate import GateRejected, finalize_candidate_construct
from core.tools.snapgene_io import read_native_dna_record


class CompetingDeliveryTests(unittest.TestCase):
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
