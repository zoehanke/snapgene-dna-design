import tempfile
import unittest
from pathlib import Path
import subprocess
import sys

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import CompoundLocation, FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord
from sgffp import SgffReader


from core.tools.snapgene_io import (
    annotate_record_primers,
    read_native_dna_record,
    write_native_dna,
)


class PrimerIORepairTests(unittest.TestCase):
    def _record(self, sequence, topology="linear"):
        return SeqRecord(
            Seq(sequence),
            id="primer_io_fixture",
            annotations={"molecule_type": "DNA", "topology": topology},
        )

    def test_full_oligo_and_binding_core_are_separate_on_both_strands(self):
        record = self._record("AAAACCCCGGGGTTTTAAAACCCCGGGGTTTT")
        annotated = annotate_record_primers(
            record,
            [
                {
                    "name": "forward_tail",
                    "sequence": "TTTTCCCCGGGG",
                    "binding_sequence": "CCCCGGGG",
                    "binding_interval_0based": [4, 12],
                    "strand": "+",
                },
                {
                    "name": "reverse_tail",
                    "sequence": "AAAAGGGGTTTT",
                    "binding_sequence": "GGGGTTTT",
                    "binding_interval_0based": [16, 24],
                    "strand": "-",
                },
            ],
        )
        self.assertEqual(len(record.features), 0)
        self.assertEqual(
            [str(feature.extract(annotated.seq)) for feature in annotated.features],
            ["CCCCGGGG", "GGGGTTTT"],
        )

        with tempfile.TemporaryDirectory(prefix="primer-io-") as temp:
            path = Path(temp)
            native = path / "annotated.dna"
            write_native_dna(annotated, native)
            sg = SgffReader.from_file(native)
            self.assertEqual(
                [(p.name, p.sequence) for p in sg.primers],
                [
                    ("forward_tail", "TTTTCCCCGGGG"),
                    ("reverse_tail", "AAAAGGGGTTTT"),
                ],
            )
            self.assertEqual(
                [
                    (site.start, site.end, site.bound_strand, site.annealed_bases)
                    for primer in sg.primers
                    for site in primer.binding_sites
                ],
                [
                    (4, 12, "+", "CCCCGGGG"),
                    (16, 24, "-", "GGGGTTTT"),
                ],
            )

            restored = read_native_dna_record(native)
            restored_primers = [
                feature for feature in restored.features if feature.type == "primer_bind"
            ]
            self.assertEqual(
                [feature.qualifiers["primer_sequence"][0] for feature in restored_primers],
                ["TTTTCCCCGGGG", "AAAAGGGGTTTT"],
            )

    def test_cross_origin_plus_and_reverse_round_trip(self):
        record = self._record("AACCGGTATA", topology="circular")
        annotated = annotate_record_primers(
            record,
            [
                {
                    "name": "cross_forward",
                    "sequence": "GGGTAAA",
                    "binding_sequence": "TAAA",
                    "binding_interval_0based": [8, 2],
                    "strand": "+",
                },
                {
                    "name": "cross_reverse",
                    "sequence": "GGGTTTA",
                    "binding_sequence": "TTTA",
                    "binding_interval_0based": [8, 2],
                    "strand": "-",
                },
            ],
        )
        self.assertEqual(
            [str(feature.extract(annotated.seq)) for feature in annotated.features],
            ["TAAA", "TTTA"],
        )

        with tempfile.TemporaryDirectory(prefix="primer-io-wrap-") as temp:
            native = Path(temp) / "cross.dna"
            write_native_dna(annotated, native)
            sg = SgffReader.from_file(native)
            self.assertEqual(
                [
                    (site.start, site.end, site.bound_strand, site.annealed_bases)
                    for primer in sg.primers
                    for site in primer.binding_sites
                ],
                [(8, 2, "+", "TAAA"), (8, 2, "-", "TTTA")],
            )
            restored = read_native_dna_record(native)
            self.assertEqual(
                [
                    feature.qualifiers["binding_interval"][0]
                    for feature in restored.features
                    if feature.type == "primer_bind"
                ],
                ["[8,2]", "[8,2]"],
            )

    def test_legacy_bind_position_and_full_sequence_derives_core(self):
        record = self._record("AAAACCCCGGGGTTTTAAAACCCCGGGGTTTT")
        annotated = annotate_record_primers(
            record,
            [
                {
                    "name": "legacy_forward",
                    "sequence": "TTTTCCCCGGGG",
                    "bind_position": 4,
                    "strand": "+",
                }
            ],
        )
        feature = annotated.features[0]
        self.assertEqual(str(feature.location), "[4:12](+)")
        self.assertEqual(feature.qualifiers["binding_sequence"], ["CCCCGGGG"])
        self.assertEqual(feature.qualifiers["primer_sequence"], ["TTTTCCCCGGGG"])

    def test_native_metadata_rehydrates_into_genbank_conversion(self):
        record = self._record("AACCGGTATA", topology="circular")
        annotated = annotate_record_primers(
            record,
            [
                {
                    "name": "p",
                    "sequence": "GGGTAAA",
                    "binding_sequence": "TAAA",
                    "binding_interval_0based": [8, 2],
                    "strand": "+",
                }
            ],
        )
        with tempfile.TemporaryDirectory(prefix="primer-io-gb-") as temp:
            native = Path(temp) / "input.dna"
            genbank = Path(temp) / "output.gb"
            write_native_dna(annotated, native)
            restored = read_native_dna_record(native)
            with genbank.open("w", encoding="utf-8") as handle:
                SeqIO.write(restored, handle, "genbank")
            reread = SeqIO.read(genbank, "genbank")
            primer = next(feature for feature in reread.features if feature.type == "primer_bind")
            self.assertEqual(primer.qualifiers["primer_sequence"], ["GGGTAAA"])
            self.assertEqual(primer.qualifiers["binding_sequence"], ["TAAA"])

    def test_convert_cli_preserves_full_oligo_in_both_directions(self):
        record = self._record("AACCGGTATA", topology="circular")
        annotated = annotate_record_primers(
            record,
            [
                {
                    "name": "p",
                    "sequence": "GGGTAAA",
                    "binding_sequence": "TAAA",
                    "binding_interval_0based": [8, 2],
                    "strand": "+",
                }
            ],
        )
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix="primer-io-convert-") as temp:
            path = Path(temp)
            source = path / "source.gb"
            native = path / "source.dna"
            roundtrip = path / "roundtrip.gb"
            with source.open("w", encoding="utf-8") as handle:
                SeqIO.write(annotated, handle, "genbank")
            for args in (
                [str(source), "--out", str(native), "--format", "snapgene"],
                [str(native), "--out", str(roundtrip), "--format", "genbank"],
            ):
                completed = subprocess.run(
                    [sys.executable, str(root / "scripts" / "convert.py"), *args],
                    cwd=str(root),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                )
                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            result = SeqIO.read(roundtrip, "genbank")
            primer = next(feature for feature in result.features if feature.type == "primer_bind")
            self.assertEqual(primer.qualifiers["primer_sequence"], ["GGGTAAA"])
            self.assertEqual(primer.qualifiers["binding_sequence"], ["TAAA"])

    def test_native_discontinuous_features_encode_explicit_gaps(self):
        record = self._record("A" * 80, topology="linear")
        record.features.append(
            SeqFeature(
                CompoundLocation(
                    [
                        FeatureLocation(20, 26, strand=-1),
                        FeatureLocation(15, 19, strand=-1),
                    ],
                    operator="join",
                ),
                type="protein_bind",
                qualifiers={"label": ["discontinuous"]},
            )
        )
        with tempfile.TemporaryDirectory(prefix="primer-io-gap-") as temp:
            native = Path(temp) / "gap.dna"
            write_native_dna(record, native)
            sg = SgffReader.from_file(native)
            feature = next(item for item in sg.features if item.type == "protein_bind")
            self.assertEqual(
                [(part.start, part.end, part.type) for part in feature.segments],
                [(15, 19, "standard"), (19, 20, "gap"), (20, 26, "standard")],
            )

    def test_native_adjacent_join_does_not_gain_gap(self):
        record = self._record("A" * 80, topology="linear")
        record.features.append(
            SeqFeature(
                CompoundLocation(
                    [
                        FeatureLocation(15, 19, strand=1),
                        FeatureLocation(19, 26, strand=1),
                    ],
                    operator="join",
                ),
                type="misc_feature",
                qualifiers={"label": ["adjacent"]},
            )
        )
        with tempfile.TemporaryDirectory(prefix="primer-io-adjacent-") as temp:
            native = Path(temp) / "adjacent.dna"
            write_native_dna(record, native)
            sg = SgffReader.from_file(native)
            feature = next(item for item in sg.features if item.name == "adjacent")
            self.assertEqual(
                [(part.start, part.end, part.type) for part in feature.segments],
                [(15, 19, "standard"), (19, 26, "standard")],
            )

    def test_native_cross_origin_feature_does_not_gain_gap(self):
        record = self._record("A" * 80, topology="circular")
        record.features.append(
            SeqFeature(
                CompoundLocation(
                    [
                        FeatureLocation(70, 80, strand=1),
                        FeatureLocation(0, 5, strand=1),
                    ],
                    operator="join",
                ),
                type="misc_feature",
                qualifiers={"label": ["wrap"]},
            )
        )
        with tempfile.TemporaryDirectory(prefix="primer-io-wrap-feature-") as temp:
            native = Path(temp) / "wrap.dna"
            write_native_dna(record, native)
            sg = SgffReader.from_file(native)
            feature = next(item for item in sg.features if item.name == "wrap")
            self.assertEqual(
                [(part.start, part.end, part.type) for part in feature.segments],
                [(70, 80, "standard"), (0, 5, "standard")],
            )

    def test_native_cross_origin_discontinuity_uses_wrapped_gap(self):
        record = self._record("A" * 80, topology="circular")
        record.features.append(
            SeqFeature(
                CompoundLocation(
                    [
                        FeatureLocation(70, 75, strand=1),
                        FeatureLocation(10, 15, strand=1),
                    ],
                    operator="join",
                ),
                type="misc_feature",
                qualifiers={"label": ["wrap_gap"]},
            )
        )
        with tempfile.TemporaryDirectory(prefix="primer-io-wrap-gap-") as temp:
            native = Path(temp) / "wrap-gap.dna"
            write_native_dna(record, native)
            sg = SgffReader.from_file(native)
            feature = next(item for item in sg.features if item.name == "wrap_gap")
            self.assertEqual(
                [(part.start, part.end, part.type) for part in feature.segments],
                [(70, 75, "standard"), (75, 10, "gap"), (10, 15, "standard")],
            )



if __name__ == "__main__":
    unittest.main()
