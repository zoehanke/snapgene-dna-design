# -*- coding: utf-8 -*-
"""Red-to-green tests for shared complete-CDS validation and extraction."""
from __future__ import annotations

from repository_paths import PROJECT_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS

import pathlib
import sys
import tempfile
import unittest
from unittest import mock

from Bio import SeqIO
from Bio.Data.CodonTable import TranslationError
from Bio.Seq import Seq
from Bio.SeqFeature import CompoundLocation, FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord


ROOT = SKILL_ROOT
SCRIPTS = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import validate_construct
from core.guardrails.checklist import quick_biological_sanity_check
from core.runtime_validate import _validate_artifact
from core.recipes.protein_tagging import recipe_protein_tagging
from core.tools.sequence_ops import (
    extract_subsequence,
    slice_record_interval,
    validate_cds_feature,
)


def _record(sequence, qualifiers=None, location=None, topology="linear"):
    record = SeqRecord(Seq(sequence), id="cds-case", name="cds-case")
    record.annotations["molecule_type"] = "DNA"
    record.annotations["topology"] = topology
    if qualifiers is not None:
        feature = SeqFeature(
            location or FeatureLocation(0, len(sequence), strand=1),
            type="CDS",
            qualifiers=qualifiers,
        )
        record.features = [feature]
    return record


class CDSRegionSemanticsTests(unittest.TestCase):
    def test_direct_sequence_offset_is_a_region_start_not_codon_start_qualifier(self):
        from core.tools.sequence_ops import check_reading_frame
        result = check_reading_frame('GCCACCATGGCTTAA', start_offset=6)
        self.assertTrue(result['valid'])
        self.assertEqual(result['translation'], 'MA*')
        self.assertEqual(result['length_bp'],9)

    def test_middle_cds_slice_does_not_claim_the_original_full_translation(self):
        original = _record('ATGGCTAAACTTGGGTTTTAA', {'label':['gene'], 'translation':['MAKLGF']})
        fragment = slice_record_interval(original,3,9)
        self.assertTrue(validate_cds_feature(fragment.features[0],fragment.seq)['valid'])
        self.assertNotIn('translation',fragment.features[0].qualifiers)
        self.assertEqual(original.features[0].qualifiers['translation'],['MAKLGF'])


def _runtime_artifact(record, directory):
    gb = directory / "product.gb"
    fasta = directory / "product.fasta"
    with gb.open("w", encoding="utf-8") as handle:
        SeqIO.write(record, handle, "genbank")
    with fasta.open("w", encoding="utf-8") as handle:
        SeqIO.write(record, handle, "fasta")
    return _validate_artifact(
        {"product_gb": str(gb), "product_fasta": str(fasta)},
        {"product_topology": record.annotations["topology"]},
    )


class FinalCdsValidationTests(unittest.TestCase):
    def test_invalid_complete_cds_fails_all_three_validation_entries(self):
        cases = {
            "invalid_start": (
                "AAAGCTTAA",
                {"label": ["GOI"], "codon_start": ["1"], "transl_table": ["1"]},
            ),
            "unknown_codon": (
                "ATGNNNTAA",
                {"label": ["GOI"], "codon_start": ["1"], "transl_table": ["1"]},
            ),
            "invalid_table": (
                "ATGGCTTAA",
                {"label": ["GOI"], "codon_start": ["1"], "transl_table": ["999"]},
            ),
            "invalid_codon_start": (
                "ATGGCTTAA",
                {"label": ["GOI"], "codon_start": ["0"], "transl_table": ["1"]},
            ),
        }
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = pathlib.Path(tmp_name)
            for case, (sequence, qualifiers) in cases.items():
                record = _record(sequence, qualifiers)
                audit = validate_cds_feature(record.features[0], record.seq)
                self.assertFalse(audit["valid"], case)

                sanity = quick_biological_sanity_check(record, topology="linear")
                self.assertFalse(sanity["all_applicable_pass"], case)

                standalone = validate_construct.validate(record)
                self.assertFalse(standalone["summary"]["pass"], case)

                artifact_valid, _parsed, errors = _runtime_artifact(record, tmp)
                self.assertFalse(artifact_valid, case)
                self.assertTrue(errors, case)

    def test_explicit_table_11_gtg_start_and_source_translation_are_supported(self):
        record = _record(
            "GTGGCTTAA",
            {
                "label": ["GOI"],
                "codon_start": ["1"],
                "transl_table": ["11"],
                # Some source records use generic translation, where GTG is V.
                "translation": ["VA*"],
            },
        )
        audit = validate_cds_feature(record.features[0], record.seq)
        self.assertTrue(audit["valid"], audit)
        self.assertEqual(audit["translation"], "MA*")
        self.assertTrue(audit["translation_qualifier_compatible"], audit)
        self.assertTrue(audit["compatibility_note"])

        leucine_initiator = _record(
            "TTGGCTTAA",
            {
                "label": ["GOI"],
                "codon_start": ["1"],
                "transl_table": ["11"],
                "translation": ["LA*"],
            },
        )
        self.assertFalse(
            validate_cds_feature(
                leucine_initiator.features[0], leucine_initiator.seq
            )["valid"]
        )
        atg_with_generic_val = _record(
            "ATGGCTTAA",
            {
                "label": ["GOI"],
                "codon_start": ["1"],
                "transl_table": ["11"],
                "translation": ["VA*"],
            },
        )
        self.assertFalse(
            validate_cds_feature(
                atg_with_generic_val.features[0], atg_with_generic_val.seq
            )["valid"]
        )

        sanity = quick_biological_sanity_check(record, topology="linear")
        self.assertTrue(sanity["all_applicable_pass"], sanity)
        self.assertEqual(sanity["annotated_cds_audits"][0]["translation"], "MA*")

    def test_valid_codon_start_two_is_applied_and_partial_is_explicit(self):
        record = _record(
            "AATGGCTTAA",
            {"label": ["GOI"], "codon_start": ["2"], "transl_table": ["1"]},
        )
        audit = validate_cds_feature(record.features[0], record.seq)
        self.assertTrue(audit["valid"], audit)
        self.assertEqual(audit["translation"], "MA*")
        self.assertEqual(audit["codon_start"], 2)

        partial = _record(
            "AAAGCTTAA",
            {
                "label": ["fragment"],
                "partial": ["true"],
                "codon_start": ["1"],
                "transl_table": ["1"],
            },
        )
        partial_audit = validate_cds_feature(partial.features[0], partial.seq)
        self.assertTrue(partial_audit["valid"], partial_audit)
        self.assertTrue(partial_audit["partial"], partial_audit)

        partial_empty = _record(
            "AT",
            {"label": ["empty_fragment"], "partial": ["true"]},
        )
        empty_audit = validate_cds_feature(
            partial_empty.features[0], partial_empty.seq
        )
        self.assertFalse(empty_audit["valid"], empty_audit)
        self.assertIn(
            "CDS_NO_COMPLETE_CODON",
            {error["code"] for error in empty_audit["errors"]},
        )

    def test_table_27_uses_biopython_dual_codon_semantics(self):
        record = _record(
            "ATGTGATGA",
            {"label": ["dual_table"], "transl_table": ["27"]},
        )
        audit = validate_cds_feature(record.features[0], record.seq)
        self.assertTrue(audit["valid"], audit)
        self.assertEqual(audit["translation"], "MW*")
        self.assertFalse(audit["has_premature_stop"], audit)

    def test_complete_translation_failure_does_not_fall_back_to_valid(self):
        record = _record(
            "ATGGCTTAA",
            {"label": ["translation_failure"], "transl_table": ["1"]},
        )
        original_translate = Seq.translate

        def fail_complete_translation(sequence, *args, **kwargs):
            if kwargs.get("cds"):
                raise TranslationError("synthetic complete-CDS failure")
            return original_translate(sequence, *args, **kwargs)

        with mock.patch.object(Seq, "translate", fail_complete_translation):
            audit = validate_cds_feature(record.features[0], record.seq)
        self.assertFalse(audit["valid"], audit)
        self.assertIn(
            "CDS_TRANSLATION_FAILED",
            {error["code"] for error in audit["errors"]},
        )

    def test_present_empty_cds_qualifiers_are_invalid(self):
        record = _record(
            "ATGGCTTAA",
            {
                "label": ["empty_qualifier"],
                "codon_start": [],
                "transl_table": [""],
            },
        )
        audit = validate_cds_feature(record.features[0], record.seq)
        codes = {error["code"] for error in audit["errors"]}
        self.assertFalse(audit["valid"], audit)
        self.assertIn("INVALID_CODON_START", codes)
        self.assertIn("INVALID_TRANSL_TABLE", codes)

    def test_runtime_rejects_non_iupac_product_sequence(self):
        record = _record("C:\\temp\\source.gb", qualifiers=None)
        with tempfile.TemporaryDirectory() as tmp_name:
            artifact_valid, _parsed, errors = _runtime_artifact(record, pathlib.Path(tmp_name))
        self.assertFalse(artifact_valid)
        self.assertTrue(any("DNA" in error or "IUPAC" in error for error in errors), errors)

    def test_protein_tagging_cds_excludes_kozak_prefix(self):
        result = recipe_protein_tagging(
            "ATGGCTTAA",
            tag_name_or_seq="6xHis",
            include_kozak=True,
        )
        feature = result.features[0]
        kozak_length = len("GCCACC")
        self.assertEqual(feature["interval_0based"][0], kozak_length)
        self.assertEqual(feature["start"], kozak_length + 1)
        self.assertEqual(feature["interval_0based"][1], len(result.product_sequence))

    def test_cross_origin_negative_compound_feature_is_clipped_and_marked_partial(self):
        record = _record("ACGT" * 25, qualifiers=None, topology="circular")
        record.features = [
            SeqFeature(
                CompoundLocation(
                    [
                        FeatureLocation(90, 100, strand=-1),
                        FeatureLocation(0, 15, strand=-1),
                    ]
                ),
                type="CDS",
                qualifiers={"label": ["origin_spanning_cds"], "codon_start": ["1"]},
            )
        ]
        result = extract_subsequence(
            record,
            90,
            10,
            topology="circular",
            strand=1,
        )
        self.assertEqual(result["length"], 20)
        self.assertEqual(len(result["features"]), 1)
        feature = result["features"][0]
        self.assertEqual(feature["type"], "CDS")
        self.assertEqual(
            [
                (part["start0"], part["end0"], part["strand"])
                for part in feature["location"]["parts"]
            ],
            [(0, 10, -1), (10, 20, -1)],
        )
        self.assertEqual(feature["qualifiers"]["partial"], ["true"])
        self.assertEqual(feature["qualifiers"]["codon_start"], ["1"])

        positive = _record("ACGT" * 25, qualifiers=None, topology="circular")
        positive.features = [
            SeqFeature(
                CompoundLocation(
                    [
                        FeatureLocation(90, 100, strand=1),
                        FeatureLocation(0, 15, strand=1),
                    ]
                ),
                type="CDS",
                qualifiers={"label": ["positive_cds"], "codon_start": ["1"]},
            )
        ]
        positive_result = extract_subsequence(
            positive, 95, 10, topology="circular", strand=1
        )
        self.assertEqual(
            positive_result["features"][0]["qualifiers"]["codon_start"],
            ["2"],
        )

    def test_linear_slice_retains_clipped_feature_and_phase(self):
        record = _record("ACGT" * 10, qualifiers=None, topology="linear")
        record.features = [
            SeqFeature(
                FeatureLocation(5, 20, strand=1),
                type="CDS",
                qualifiers={"label": ["linear_cds"], "codon_start": ["1"]},
            )
        ]
        fragment = slice_record_interval(record, 10, 5, circular=False)
        self.assertEqual(str(fragment.seq), str(record.seq[10:15]))
        self.assertEqual(len(fragment.features), 1)
        clipped = fragment.features[0]
        self.assertEqual((int(clipped.location.start), int(clipped.location.end)), (0, 5))
        self.assertEqual(clipped.qualifiers["partial"], ["true"])
        self.assertEqual(clipped.qualifiers["codon_start"], ["2"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
