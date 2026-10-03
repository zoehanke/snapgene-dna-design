"""Reaction annotations must describe the material actually retained by cuts."""

from repository_paths import PROJECT_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS
import pathlib
import tempfile
import unittest

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import CompoundLocation, FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

from core.io.input_resolution import resolve_sequence_record
from core.tools.assembly import _feature_dicts_for_arc, simulate_digest_ligation
from core.tools.sequence_ops import validate_cds_feature


class RestrictionAnnotationBoundaryTests(unittest.TestCase):
    def test_explicit_peptide_annotations_are_not_complete_proteins(self):
        for product in ("epitope tag from a capsid protein", "affinity tag", "TEV protease cleavage site",
                        "thrombin recognition and cleavage site"):
            with self.subTest(product=product):
                feature = SeqFeature(FeatureLocation(0, 9), type="CDS",
                    qualifiers={"product": [product], "translation": ["MAA"]})
                audit = validate_cds_feature(feature, Seq("ATGGCTGCT"))
                self.assertTrue(audit["partial"], audit)
                self.assertTrue(audit["valid"], audit)

    def test_peptide_metadata_does_not_hide_wrong_translation_or_broken_cds(self):
        for product, translation in (("epitope tag", "MKK"),
                                     ("protein containing an epitope tag", "MAA")):
            feature = SeqFeature(FeatureLocation(0, 9), type="CDS",
                qualifiers={"product": [product], "translation": [translation]})
            self.assertFalse(validate_cds_feature(feature, Seq("ATGGCTGCT"))["valid"])

    def test_actual_digest_marks_cut_cds_partial_and_updates_frame(self):
        vector = SeqRecord(Seq("CCCCGAATTCAAAAGCTTGGGG"), id="vector",
                           annotations={"molecule_type": "DNA", "topology": "circular"})
        sequence = "ATG" + "GAATTC" + "GCTGCT" + "AAGCTT" + "TAA"
        source = SeqRecord(Seq(sequence), id="insert",
                           annotations={"molecule_type": "DNA", "topology": "linear"})
        source.features = [SeqFeature(FeatureLocation(0, len(source), strand=1),
            type="CDS", qualifiers={"label": ["source coding region"],
                                     "codon_start": ["1"], "translation": ["MEFAAKL"]})]
        self.assertTrue(validate_cds_feature(source.features[0], source.seq)["valid"])
        with tempfile.TemporaryDirectory() as directory:
            paths = [pathlib.Path(directory)/name for name in ("vector.gb", "insert.gb")]
            for record, path in zip((vector, source), paths):
                with path.open("w", encoding="utf-8") as stream:
                    SeqIO.write(record, stream, "genbank")
            result = simulate_digest_ligation(paths[0], paths[1], ["EcoRI", "HindIII"])
        record = resolve_sequence_record({"sequence": result["product_sequence"],
            "features": result["features"], "topology": "circular"})
        feature = next(f for f in record.features if f.qualifiers.get("label") == ["source coding region"])
        start = sequence.index("GAATTC") + 1
        end = sequence.index("AAGCTT") + 1
        self.assertEqual(str(feature.extract(record.seq)), sequence[start:end])
        self.assertEqual(feature.qualifiers.get("partial"), ["true"])
        self.assertEqual(feature.qualifiers.get("codon_start"), [str((-start) % 3 + 1)])
        self.assertNotIn("translation", feature.qualifiers)
        self.assertEqual(source.features[0].qualifiers["translation"], ["MEFAAKL"])

    def test_negative_origin_crossing_feature_keeps_biological_order(self):
        source = SeqRecord(Seq("ACGT" * 10), annotations={"topology": "circular"})
        original = SeqFeature(CompoundLocation([FeatureLocation(0, 6, strand=-1),
            FeatureLocation(35, 40, strand=-1)]), type="misc_feature", qualifiers={"label": ["reverse junction"]})
        source.features = [original]
        fragment = resolve_sequence_record({"sequence": str(source.seq[35:]+source.seq[:10]),
            "features": _feature_dicts_for_arc(source, 35, 10)})
        self.assertEqual(str(fragment.features[0].extract(fragment.seq)), str(original.extract(source.seq)))

    def test_explicit_wrapping_reaction_arc_keeps_unannotated_vector_features(self):
        # A FASTA destination's explicitly requested topology must reach its
        # annotation extraction as well as the reaction's sequence geometry.
        source = SeqRecord(Seq("ACGT" * 10), annotations={"topology": "linear"})
        source.features = [SeqFeature(FeatureLocation(0, 6), type="misc_feature",
                                      qualifiers={"label": ["retained region"]})]
        features = _feature_dicts_for_arc(source, 35, 10, circular=True)
        fragment = resolve_sequence_record({"sequence": str(source.seq[35:]+source.seq[:10]), "features": features})
        self.assertEqual(str(fragment.features[0].extract(fragment.seq)), "ACGTAC")

    def test_cut_primer_does_not_claim_intact_binding_site(self):
        source = SeqRecord(Seq("ACGT" * 10), annotations={"topology": "linear"})
        source.features = [SeqFeature(FeatureLocation(5, 25, strand=-1), type="primer_bind",
            qualifiers={"label": ["primer"], "primer_sequence": ["ACGT" * 5]})]
        fragment = resolve_sequence_record({"sequence": str(source.seq[10:30]),
            "features": _feature_dicts_for_arc(source, 10, 30)})
        feature = fragment.features[0]
        self.assertEqual(feature.type, "misc_feature")
        self.assertEqual(feature.qualifiers.get("partial"), ["true"])
        self.assertEqual(feature.qualifiers["primer_sequence"], ["ACGT" * 5])


if __name__ == "__main__":
    unittest.main()
