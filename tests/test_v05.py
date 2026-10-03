# -*- coding: utf-8 -*-
"""v0.4.3 regression tests: feature migration order/operator and origins."""

from repository_paths import PROJECT_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import CompoundLocation, FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

HERE = pathlib.Path(__file__).resolve().parent
ROOT = SKILL_ROOT
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import simulate_advanced  # noqa: E402
import simulate_cloning  # noqa: E402
from assembly_model import AssemblyError  # noqa: E402


def run_script(name, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPTS / name)] + list(args),
        cwd=str(SCRIPTS), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )



class EnvelopeData(dict):
    def __init__(self, data, envelope):
        super().__init__(data)
        self.envelope = envelope

    def __getitem__(self, key):
        if key in self:
            return dict.__getitem__(self, key)
        return self.envelope[key]


def parsed(completed):
    payload = json.loads(completed.stdout)
    if payload.get("data") is None:
        return payload
    return EnvelopeData(payload["data"], payload)

class FeatureMigrationOrderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="v05-")
        self.addCleanup(self.tmp.cleanup)
        self.tmp_path = pathlib.Path(self.tmp.name)

    def _record(self, name, sequence, feature_location, strand=1,
                feature_type="misc_feature", qualifiers=None, circular=True):
        record = SeqRecord(
            Seq(sequence), id=name, name=name,
            annotations={"molecule_type": "DNA",
                         "topology": "circular" if circular else "linear"})
        if feature_location is not None:
            if isinstance(feature_location, CompoundLocation):
                location = feature_location
            else:
                location = FeatureLocation(
                    feature_location[0], feature_location[1], strand=strand)
            record.features.append(SeqFeature(
                location, type=feature_type,
                qualifiers=qualifiers or {"label": [name + "_feat"]}))
        path = self.tmp_path / (name + ".gb")
        with open(path, "w", encoding="utf-8") as handle:
            SeqIO.write(record, handle, "genbank")
        return SeqIO.read(str(path), "genbank")

    def _featured_fragment(self, name, sequence, location, **kwargs):
        record = self._record(name, sequence, location, **kwargs)
        path = self.tmp_path / (name + "_file.gb")
        with open(path, "w", encoding="utf-8") as handle:
            SeqIO.write(record, handle, "genbank")
        return path

    def _gibson_parts(self, parts, overlap=12, circular=True):
        records = [SeqIO.read(str(p), "genbank") for p in parts]
        return simulate_cloning.gibson(records, overlap=overlap, circular=circular)

    def _feature_by_label(self, record, label):
        for feature in record.features:
            values = feature.qualifiers.get("label", [])
            if label in values:
                return feature
        raise AssertionError("missing feature %s" % label)

    def test_positive_strand_partial_wrap_preserves_order_and_extract(self):
        overlap = "ACGTACGTACGT"
        closing = "TGCATGCATGCA"
        a = self._featured_fragment(
            "wrapA", closing + "AAAAAA" + overlap, (0, 18))
        b = self._featured_fragment(
            "wrapB", overlap + "CCCCCC" + closing, None)
        # b has no feature: create plain record manually
        b_plain = self._record(
            "wrapB_plain", overlap + "CCCCCC" + closing, None)
        b_path = self.tmp_path / "wrapB_plain_file.gb"
        with open(b_path, "w", encoding="utf-8") as handle:
            SeqIO.write(b_plain, handle, "genbank")
        product, _fragments, _contrib, warnings = self._gibson_parts([a, b_path])
        feature = self._feature_by_label(product, "wrapA_feat")
        parts = [(int(p.start), int(p.end), int(p.strand)) for p in feature.location.parts]
        self.assertEqual(parts, [(24, 36, 1), (0, 6, 1)])
        self.assertEqual(feature.location.operator, "join")
        source_a = SeqIO.read(str(a), "genbank")
        source_feature = self._feature_by_label(source_a, "wrapA_feat")
        self.assertEqual(str(feature.extract(product.seq)),
                         str(source_feature.extract(source_a.seq)))

    def test_negative_strand_partial_wrap_preserves_order_and_extract(self):
        overlap = "ACGTACGTACGT"
        closing = "TGCATGCATGCA"
        a = self._featured_fragment(
            "wrapN", closing + "AAAAAA" + overlap, (0, 18), strand=-1)
        b = self._record("wrapNB", overlap + "CCCCCC" + closing, None)
        b_path = self.tmp_path / "wrapNB_file.gb"
        with open(b_path, "w", encoding="utf-8") as handle:
            SeqIO.write(b, handle, "genbank")
        product, _fragments, _contrib, _warnings = self._gibson_parts([a, b_path])
        feature = self._feature_by_label(product, "wrapN_feat")
        parts = [(int(p.start), int(p.end), int(p.strand)) for p in feature.location.parts]
        self.assertEqual(parts, [(0, 6, -1), (24, 36, -1)])
        self.assertEqual(feature.location.operator, "join")
        source_a = SeqIO.read(str(a), "genbank")
        source_extract = str(self._feature_by_label(source_a, "wrapN_feat").extract(source_a.seq))
        self.assertEqual(str(feature.extract(product.seq)), source_extract)

    def test_compound_join_and_order_operators_are_preserved(self):
        overlap = "ACGTACGTACGT"
        for operator in ("join", "order"):
            location = CompoundLocation([
                FeatureLocation(16, 18, strand=1),
                FeatureLocation(12, 14, strand=1),
            ], operator=operator)
            a = self._featured_fragment(
                "comp_" + operator, overlap + "AAAACCCC" + overlap, location)
            b = self._record("comp_B_" + operator,
                             overlap + "CCCCAAAA" + overlap, None)
            b_path = self.tmp_path / ("comp_B_%s_file.gb" % operator)
            with open(b_path, "w", encoding="utf-8") as handle:
                SeqIO.write(b, handle, "genbank")
            product, _f, _c, _w = self._gibson_parts([a, b_path])
            feature = self._feature_by_label(product, "comp_%s_feat" % operator)
            self.assertEqual(feature.location.operator, operator)
            self.assertEqual(
                [(int(p.start), int(p.end)) for p in feature.location.parts],
                [(4, 6), (0, 2)])
            source_rec = SeqIO.read(str(a), "genbank")
            source_feature = self._feature_by_label(source_rec, "comp_%s_feat" % operator)
            self.assertEqual(
                str(feature.extract(product.seq)),
                str(source_feature.extract(source_rec.seq)))

    def test_cross_origin_cds_keeps_extract_translation_and_qualifiers(self):
        overlap = "ACGTACGTACGT"
        source_seq = overlap + "AAAACC" + overlap
        translation = str(Seq("AAAACC").translate())
        qualifiers = {
            "label": ["test_CDS"],
            "codon_start": ["1"],
            "translation": [translation],
        }
        a = self._featured_fragment(
            "cdsA", source_seq, (12, 18), strand=1,
            feature_type="CDS", qualifiers=qualifiers)
        b = self._record("cdsB", overlap + "CCCCCC" + overlap, None)
        b_path = self.tmp_path / "cdsB_file.gb"
        with open(b_path, "w", encoding="utf-8") as handle:
            SeqIO.write(b, handle, "genbank")
        product, _f, _c, _w = self._gibson_parts([a, b_path])
        feature = self._feature_by_label(product, "test_CDS")
        self.assertEqual(str(feature.extract(product.seq)), "AAAACC")
        self.assertEqual(str(feature.extract(product.seq).translate()), translation)
        self.assertEqual(feature.location.parts[0].strand, 1)
        self.assertEqual(feature.qualifiers["codon_start"], ["1"])
        self.assertEqual(feature.qualifiers["translation"], [translation])
        gb = self.tmp_path / "cds_product.gb"
        with open(gb, "w", encoding="utf-8") as handle:
            SeqIO.write(product, handle, "genbank")
        reread = SeqIO.read(str(gb), "genbank")
        reread_feature = self._feature_by_label(reread, "test_CDS")
        self.assertEqual(str(reread_feature.extract(reread.seq)), "AAAACC")
        self.assertEqual(reread_feature.qualifiers["translation"], [translation])

    def test_three_fragment_circular_gibson_and_middle_feature(self):
        overlap = "ACGTACGTACGT"
        a = self._featured_fragment(
            "threeA", overlap + "AAAA" + overlap, (12, 16))
        b = self._featured_fragment(
            "threeB", overlap + "CCCC" + overlap, (12, 16),
            feature_type="misc_feature")
        c = self._record("threeC", overlap + "GGGG" + overlap, None)
        c_path = self.tmp_path / "threeC_file.gb"
        with open(c_path, "w", encoding="utf-8") as handle:
            SeqIO.write(c, handle, "genbank")
        product, _f, contributions, _w = self._gibson_parts([a, b, c_path])
        self.assertEqual(str(product.seq),
                         "AAAA" + overlap + "CCCC" + overlap +
                         "GGGG" + overlap)
        self.assertEqual(sum(contributions), len(product.seq))
        middle = self._feature_by_label(product, "threeB_feat")
        self.assertEqual(str(middle.extract(product.seq)), "CCCC")

    def test_three_fragment_circular_infusion(self):
        overlap = "ACGTACGTACGT"
        a_path = self._featured_fragment(
            "infA", overlap + "AAAA" + overlap, (12, 16))
        b_path = self._featured_fragment(
            "infB", overlap + "CCCC" + overlap, (12, 16))
        c = self._record("infC", overlap + "GGGG" + overlap, None)
        c_path = self.tmp_path / "infC_file.gb"
        with open(c_path, "w", encoding="utf-8") as handle:
            SeqIO.write(c, handle, "genbank")
        records = [SeqIO.read(str(p), "genbank") for p in (a_path, b_path, c_path)]
        product, fragments, warnings = simulate_advanced.infusion(
            records, overlap=12, circular=True)
        self.assertEqual(str(product.seq),
                         "AAAA" + overlap + "CCCC" + overlap +
                         "GGGG" + overlap)
        self.assertEqual(len(product.features), 2)


class OriginsReconstructionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="v05-origins-")
        self.addCleanup(self.tmp.cleanup)
        self.tmp_path = pathlib.Path(self.tmp.name)

    def _fragment(self, name, sequence):
        path = self.tmp_path / (name + ".fa")
        path.write_text(">%s\n%s\n" % (name, sequence), encoding="utf-8")
        return path

    def _reconstruct(self, mappings, source_length):
        bases = [None] * source_length
        for mapping in mappings:
            if mapping.get("dropped"):
                continue
            source_span = mapping["source_end"] - mapping["source_start"] + 1
            product_span = mapping["product_end"] - mapping["product_start"] + 1
            self.assertEqual(source_span, product_span)
            for idx in range(source_span):
                bases[mapping["source_start"] - 1 + idx] = \
                    self.product_seq[mapping["product_start"] - 1 + idx]
        return "".join(bases)

    def test_circular_origins_reconstruct_full_sources(self):
        overlap = "ACGTACGTACGT"
        seqs = [overlap + "AAAA" + overlap,
                overlap + "CCCC" + overlap,
                overlap + "GGGG" + overlap]
        paths = [self._fragment("o%d" % i, seqs[i]) for i in range(3)]
        completed = run_script(
            "simulate_cloning.py", "--method", "gibson",
            "--parts", *(str(p) for p in paths),
            "--overlap", "12", "--topology", "circular", "--json")
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        payload = parsed(completed)
        self.product_seq = payload["product_sequence"]
        self.assertEqual(
            sum(o["length"] for o in payload["origins"]),
            payload["product_length"])
        for idx, (origin, sequence) in enumerate(zip(payload["origins"], seqs)):
            reconstructed = self._reconstruct(
                origin["source_mappings"], len(sequence))
            self.assertEqual(reconstructed, sequence)
            # contribution segments cover each source base at most once and
            # never overlap in product space.
            spans = [
                (s["product_start"], s["product_end"])
                for s in origin["contribution_segments"]]
            self.assertEqual(
                sum(end - start + 1 for start, end in spans),
                origin["length"])
            if idx == 0:
                self.assertTrue(origin["source_mappings"][0]["wraps_origin"])
                self.assertTrue("dropped" not in origin["source_mappings"][0])


class FeatureMigrationFailureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="v05-fail-")
        self.addCleanup(self.tmp.cleanup)
        self.tmp_path = pathlib.Path(self.tmp.name)

    def test_feature_migration_mismatch_is_structured_failure_without_product(self):
        a = self.tmp_path / "a.gb"
        b = self.tmp_path / "b.gb"
        out = self.tmp_path / "out.gb"
        overlap = "ACGTACGTACGT"
        for path, sequence, name in ((a, overlap + "AAAA" + overlap, "a"),
                                     (b, overlap + "CCCC" + overlap, "b")):
            record = SeqRecord(
                Seq(sequence), id=name, name=name,
                annotations={"molecule_type": "DNA", "topology": "linear"})
            record.features.append(SeqFeature(
                FeatureLocation(0, len(sequence), strand=1),
                type="misc_feature", qualifiers={"label": [name + "_feat"]}))
            with open(path, "w", encoding="utf-8") as handle:
                SeqIO.write(record, handle, "genbank")
        wrapper = self.tmp_path / "force_mismatch.py"
        wrapper.write_text(
            "import sys\n"
            "sys.path.insert(0, r'%s')\n"
            "from unittest.mock import patch\n"
            "from Bio.SeqFeature import FeatureLocation\n"
            "import simulate_cloning\n"
            "def bad(part, trim_start, clip_end, offset, circular, is_first, product_length):\n"
            "    return [FeatureLocation(0, 1, strand=part.strand)], False\n"
            "with patch('simulate_cloning._mapped_part_segments', bad):\n"
            "    simulate_cloning.main()\n" % str(SCRIPTS),
            encoding="utf-8")
        completed = subprocess.run(
            [sys.executable, str(wrapper), "--method", "gibson",
             "--parts", str(a), str(b), "--overlap", "12",
             "--topology", "circular", "--out", str(out), "--json"],
            cwd=str(SCRIPTS), capture_output=True, text=True,
            encoding="utf-8", errors="replace")
        self.assertNotEqual(completed.returncode, 0)
        payload = parsed(completed)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "FEATURE_MIGRATION_MISMATCH")
        self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
