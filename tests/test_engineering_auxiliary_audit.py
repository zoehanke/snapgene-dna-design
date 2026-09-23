"""Independent input-preservation, read-mapping and failure-contract regressions."""
import copy
import hashlib
import io
import json
import os
import pathlib
import random
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
import align_sanger
import assemble_contig
import convert
import msa
import online_sources
from design import spec
from rules.engine import evaluate_plan
from sg_common import load_sequence_records


def cli(script, *args, env=None):
    return subprocess.run([sys.executable, "-X", "utf8", "-B",
                           str(ROOT / "scripts" / script), *map(str, args)],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)


def genbank(sequence, record_id="TEST001.1"):
    record = SeqRecord(Seq(sequence), id=record_id, name=record_id.split(".")[0])
    record.annotations["molecule_type"] = "DNA"
    output = io.StringIO()
    SeqIO.write(record, output, "genbank")
    return output.getvalue()


class AlignmentContracts(unittest.TestCase):
    def test_msa_keeps_each_original_sequence_and_equal_widths(self):
        rng = random.Random(932)
        examples = [[("a", "CGGTGTCGGTTA"), ("b", "GCATCGACTTTT"), ("c", "ACCAGAT")]]
        for _ in range(50):
            examples.append([(str(i), "".join(rng.choice("ACGT") for _ in range(rng.randint(5,30))))
                             for i in range(5)])
        for inputs in examples:
            aligned, consensus = msa.msa(inputs)
            self.assertEqual(dict(inputs), {name: seq.replace("-", "") for name, seq in aligned})
            self.assertEqual({len(consensus)}, {len(seq) for _, seq in aligned})

    def test_msa_public_cli_preserves_insertions_in_earlier_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / "三条.fa"
            sequences = {"a": "CGGTGTCGGTTA", "b": "GCATCGACTTTT", "c": "ACCAGAT"}
            path.write_text("".join(">%s\n%s\n" % item for item in sequences.items()), encoding="utf-8")
            result = cli("msa.py", path, "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(sequences, {item["id"]: item["aligned"].replace("-", "")
                                        for item in json.loads(result.stdout)["data"]["sequences"]})

    def test_multi_reader_closes_handles_rejects_empty_and_invalid_dna(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / "序列.fa"
            for content in ("", ">empty\n", ">invalid\nAC!T\n"):
                path.write_text(content, encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_sequence_records([path])
                path.unlink()  # Windows detects leaked parser handles here.
            path.write_text(">a\nACTG\n>b\nGCCA\n", encoding="utf-8")
            self.assertEqual([str(r.seq) for r in load_sequence_records([path])], ["ACTG", "GCCA"])
            gb = pathlib.Path(folder) / "source.gb"
            gb.write_text(genbank("ACGTA"), encoding="utf-8")
            self.assertEqual(msa.load_sequences([str(gb)]), [("TEST001.1", "ACGTA")])

    def test_empty_read_clis_fail_instead_of_zero_record_success(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / "empty.fa"
            path.write_text("", encoding="utf-8")
            for script, args in (("msa.py", [path]), ("assemble_contig.py", ["--reads", path]),
                                 ("align_sanger.py", ["ACGT", "--reads", path])):
                result = cli(script, *args, "--json")
                self.assertNotEqual(result.returncode, 0, script)

    def test_exact_contig_assembly_and_invalid_overlap(self):
        self.assertEqual(assemble_contig.assemble([("a", "AAACCC"), ("b", "CCCGGG")], 3),
                         [("a+b", "AAACCCGGG")])
        with self.assertRaises(ValueError):
            assemble_contig.assemble([("a", "AAACCC")], 0)

    def test_sanger_reverse_read_reports_reference_coordinates(self):
        reference = "ATTCGAGTACCGTATCGACCTAGGCTAACG"
        result = align_sanger.align_read_to_ref(str(Seq(reference[5:26]).reverse_complement()), reference)
        self.assertEqual(result["strand"], "-")
        self.assertEqual(result["covered_positions"], list(range(6,27)))
        self.assertEqual(result["matched_positions"], list(range(6,27)))
        self.assertEqual(result["aligned_read_percent"], 100)

    def test_sanger_cli_one_based_gaps_and_rejected_reads(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / "reads.fa"
            path.write_text(">valid\nCCCCCC\n", encoding="utf-8")
            result = cli("align_sanger.py", "AAAACCCCCCGGGG", "--reads", path, "--json")
            data = json.loads(result.stdout)["data"]
            self.assertEqual(data["uncovered_spans"], [{"start":1,"end":4},{"start":11,"end":14}])
            path.write_text(">tiny_hit\nGGGGAGGGGG\n", encoding="utf-8")
            result = cli("align_sanger.py", "AAAAAAAAAAAA", "--reads", path, "--json")
            data = json.loads(result.stdout)["data"]
            self.assertFalse(data["reads"][0]["confirmed"])
            self.assertEqual(data["coverage_percent"], 0)
            self.assertEqual(data["uncovered_spans"], [{"start":1,"end":12}])

    def test_sanger_deletion_and_ambiguous_bases_are_not_covered(self):
        rng = random.Random(311)
        reference = "".join(rng.choice("ACGT") for _ in range(90))
        read = reference[:40] + reference[46:]
        result = align_sanger.align_read_to_ref(read, reference)
        self.assertEqual(result["deletion_positions"], list(range(41,47)))
        self.assertFalse(set(range(41,47)) & set(result["covered_positions"]))
        ambiguous = align_sanger.align_read_to_ref("N"*15, "N"*15)
        self.assertEqual(ambiguous["matched_positions"], [])
        self.assertEqual(ambiguous["covered_positions"], [])


class StateAndExternalContracts(unittest.TestCase):
    def test_rejected_spec_edits_leave_every_field_unchanged(self):
        for state in ("user-confirmed", "evidence-resolved", "planned", "executed", "verified", "delivered"):
            original = spec.new_spec("synthetic request")
            original["status"] = state
            before = copy.deepcopy(original)
            with self.assertRaises(spec.DesignSpecError):
                spec.set_field(original, ["objective", "method"], "new method")
            self.assertEqual(original, before)
            with self.assertRaises(spec.DesignSpecError):
                spec.add_source(original, {"source_id":"changed"})
            self.assertEqual(original, before)
            with self.assertRaises(spec.DesignSpecError):
                spec.record_answer(original, "clarify-host", "new host")
            self.assertEqual(original, before)
        draft = spec.new_spec("draft")
        before = copy.deepcopy(draft)
        with self.assertRaises(spec.DesignSpecError):
            spec.set_field(draft, ["objective", "method"], "new method", evidence_layer="invented")
        self.assertEqual(draft, before)
        spec.set_field(draft, ["objective", "method"], "valid")
        self.assertEqual(draft["objective"]["method"], "valid")

    def test_explicitly_denied_primer_order_is_not_approval(self):
        value = spec.new_spec("x", mode="formal")
        value["approvals"]["primers-ready-to-order"] = {"value": False}
        self.assertIn("PRIMERS_NOT_APPROVED_FOR_ORDER", spec.formal_blockers(value))
        value["approvals"]["primers-ready-to-order"]["value"] = True
        self.assertNotIn("PRIMERS_NOT_APPROVED_FOR_ORDER", spec.formal_blockers(value))

    def test_ncbi_download_checks_content_and_accession(self):
        for text in ("<html>busy</html>", "LOCUS       X", genbank("ACGT", "OTHER.1")):
            with mock.patch.object(online_sources, "_get", return_value=text):
                self.assertEqual(online_sources.fetch_genbank("TEST001.1")["status"], "offline-unverified")
        with mock.patch.object(online_sources, "_get", return_value=genbank("ACGT")):
            result = online_sources.fetch_genbank("TEST001.1")
        self.assertEqual(result["status"], "verified-online")
        self.assertEqual(result["sequence_length"], 4)
        self.assertEqual(result["resolved_accession"], "TEST001.1")

    def test_ncbi_missing_summary_is_not_verified_record(self):
        for responses in (("[]",), ('{"esearchresult":{"idlist":["42"]}}', '{"result":{}}')):
            with mock.patch.object(online_sources, "_get", side_effect=responses):
                self.assertEqual(online_sources.ncbi_search("EGFP")["status"], "offline-unverified")

    def test_blast_never_silently_truncates_authorized_sequence(self):
        sequence = "ACGT" * 40
        consent = online_sources.ncbi_blast_consent_request(sequence, "test", "full")["consent"]
        consent.approve()
        result = online_sources.authorized_blast_url(consent, sequence, "test", "full")
        self.assertEqual(result["status"], "unsupported")
        self.assertIsNone(result["url"])
        self.assertFalse(result["contains_sequence"])

    def test_invalid_rule_has_diagnostic_not_high_feasibility(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / "rules.json"
            path.write_text('{"rules":[null]}', encoding="utf-8")
            result = evaluate_plan({}, user_rules_dir=folder)
            self.assertEqual(result["grade"], "unknown")
            self.assertTrue(result["diagnostics"])
            path.write_text(json.dumps({"rules": [{"trigger":"assembly_feasibility", "version":"bad"}]}), encoding="utf-8")
            result = evaluate_plan({}, user_rules_dir=folder)
            self.assertEqual(result["grade"], "unknown")


class FileFailureContracts(unittest.TestCase):
    def test_authorized_overwrite_replaces_atomically_and_trace_keeps_versions(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            source, destination, trace = root/"source.fa", root/"existing.gb", root/"trace"
            source.write_text(">new\nACGTACGT\n", encoding="utf-8")
            destination.write_text(genbank("GGGGCCCC"), encoding="utf-8")
            before = hashlib.sha256(destination.read_bytes()).hexdigest()
            config = root/"settings.json"
            config.write_text('{"trace_level":"observed"}', encoding="utf-8")
            env = {**os.environ, "SNAPGENE_TRACE_CONFIG": str(config)}
            result = cli("convert.py", source, "--out", destination, "--format", "genbank",
                         "--allow-overwrite", "--trace-dir", trace, "--json", env=env)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(json.loads(result.stdout)["ok"])
            self.assertEqual(str(SeqIO.read(destination, "genbank").seq), "ACGTACGT")
            after = hashlib.sha256(destination.read_bytes()).hexdigest()
            self.assertNotEqual(before, after)
            events = [json.loads(line) for line in (trace/"events.jsonl").read_text(encoding="utf-8").splitlines()]
            completed = next(e["payload"] for e in events if e["event_type"] == "file_operation_completed")
            target = str(destination.resolve())
            self.assertEqual(next(item["sha256"] for item in completed["before"] if item["path"] == target).lower(), before)
            self.assertEqual(next(item["sha256"] for item in completed["after"] if item["path"] == target).lower(), after)

    def test_authorized_overwrite_preserves_old_file_on_writer_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            source, destination = root/"source.fa", root/"existing.gb"
            source.write_text(">new\nACGT\n", encoding="utf-8")
            original = genbank("GCGCTA").encode("utf-8")
            destination.write_bytes(original)
            def failed_writer(_record, handle):
                handle.write("partial conversion")
                raise ValueError("injected conversion writer failure")
            with mock.patch.dict(convert.WRITERS, {"genbank": failed_writer}):
                with self.assertRaisesRegex(ValueError, "writer failure"):
                    convert.convert_file(source, destination, "genbank", allow_overwrite=True)
            self.assertEqual(destination.read_bytes(), original)
            source.write_text("", encoding="utf-8")
            result = cli("convert.py", source, "--out", destination, "--format", "genbank", "--allow-overwrite", "--json")
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(json.loads(result.stdout)["ok"])
            self.assertEqual(destination.read_bytes(), original)

    def test_convert_failure_and_mixed_batch_have_nonzero_exit(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            result = cli("convert.py", root/"missing.gb", "--format", "fasta", "--json")
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(json.loads(result.stdout)["ok"])
            (root/"bad.fa").write_text("", encoding="utf-8")
            (root/"good.fa").write_text(">good\nACGT\n", encoding="utf-8")
            result = cli("batch.py", root, "--op", "parse", "--json")
            self.assertNotEqual(result.returncode, 0)
            data = json.loads(result.stdout)
            self.assertFalse(data["ok"])
            self.assertEqual(len(data["data"]["results"]), 2)
            self.assertEqual(data["data"]["results"][1]["length"], 4)

    def test_conversion_collisions_keep_originals_and_independent_success(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            (root/"same.fa").write_text(">a\nACGT\n", encoding="utf-8")
            (root/"same.gb").write_text(genbank("GCTA"), encoding="utf-8")
            (root/"unique.fa").write_text(">b\nCCCGGG\n", encoding="utf-8")
            original = {p: p.read_bytes() for p in root.iterdir()}
            output = root/"out"
            result = cli("convert.py", root, "--dir", "--out", output, "--format", "embl", "--json")
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((output/"same.embl").exists())
            self.assertEqual(str(SeqIO.read(output/"unique.embl", "embl").seq), "CCCGGG")
            self.assertEqual(original, {p:p.read_bytes() for p in original})
            existing = root/"same.gb"
            result = cli("convert.py", root/"same.fa", "--out", existing, "--format", "genbank", "--json")
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(existing.read_bytes(), original[existing])
            # Permission to replace a known output cannot resolve ambiguous
            # ownership when two batch sources target the same file.
            result = cli("convert.py", root, "--dir", "--out", output, "--format", "embl",
                         "--allow-overwrite", "--json")
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((output/"same.embl").exists())
            self.assertEqual(original, {p:p.read_bytes() for p in original})


if __name__ == "__main__":
    unittest.main()
