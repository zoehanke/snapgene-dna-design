import pathlib
import random
import tempfile
import unittest

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import CompoundLocation, FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

from core.errors import GateRejected, PlanningError
from core.handlers.composite_pipeline import run_pipeline_steps
from core.recipes.contract import RecipeResult
from core.tools.crispr import prepare_pml104_guide
from core.guardrails.checklist import quick_biological_sanity_check
from scripts.run_recipe import write_preparation_artifacts


class WorkflowDeliveryTests(unittest.TestCase):
    def test_direct_native_export_keeps_fuzzy_cds_partial_meaning(self):
        from Bio.SeqFeature import BeforePosition
        from core.tools.snapgene_io import write_native_dna, read_native_dna_record
        record = SeqRecord(Seq("GCTGCTTAA"), annotations={"molecule_type": "DNA"})
        record.features = [SeqFeature(FeatureLocation(BeforePosition(0), 9, strand=1), type="CDS",
                                      qualifiers={"translation": ["MMAA"]})]
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "partial.dna"
            write_native_dna(record, path)
            observed = read_native_dna_record(path)
            self.assertEqual(observed.features[0].qualifiers["partial"], ["true"])
            self.assertNotIn("partial", record.features[0].qualifiers)

    def test_reverse_compatible_digest_uses_bottom_strand_boundaries(self):
        from Bio.Restriction import BspHI, NcoI, XhoI
        from core.tools.assembly import simulate_digest_ligation
        sequence = "A" * 70 + "CTCGAG" + "A" * 60 + "CCATGG" + "A" * 250
        vector = SeqRecord(Seq(sequence), id="reverse_mcs",
                           annotations={"molecule_type": "DNA", "topology": "circular"})
        vector.features = [SeqFeature(FeatureLocation(190, 260), type="rep_origin", qualifiers={"label": ["ori"]})]
        insert = "CGCTCATGA" + "TG" + "CAT" * 5 + "CACGAAAACCTGTATTTTCAGGGC" + "ATGGCTGCTTAA" + "CTCGAGCGC"
        result = simulate_digest_ligation(vector, insert, ["NcoI", "XhoI"], ["BspHI", "XhoI"])
        left = XhoI.search(vector.seq, linear=False)[0] - 1
        right = NcoI.search(vector.seq, linear=False)[0] - 1
        # These are physical bottom-strand cleavage coordinates on the
        # original PCR insert, not a reverse complement of its top interval.
        insert_left = insert.index("TCATGA") + len(BspHI.site) + BspHI.fst3
        insert_right = insert.index("CTCGAG") + len(XhoI.site) + XhoI.fst3
        expected = sequence[:left] + str(Seq(insert[insert_left:insert_right]).reverse_complement()) + sequence[right:]
        self.assertEqual(result["insert_orientation"], "reverse")
        self.assertEqual(result["product_sequence"], expected)
        self.assertEqual(BspHI.search(Seq(expected), linear=False), [])
        self.assertEqual(NcoI.search(Seq(expected), linear=False), [])
        nonpal_vector = SeqRecord(Seq(sequence.replace("CCATGG", "GAATC")),
                                  annotations={"molecule_type": "DNA", "topology": "circular"})
        nonpal_insert = "CGCGATTCATGGCTGCTTAACTCGAGCGC"
        matched = simulate_digest_ligation(nonpal_vector, nonpal_insert, ["HinfI", "XhoI"], orientation="reverse")
        self.assertEqual(matched["insert_orientation"], "reverse")
        with self.assertRaisesRegex(ValueError, "Sticky ends"):
            simulate_digest_ligation(nonpal_vector, nonpal_insert.replace("GATTC", "GAATC"),
                                      ["HinfI", "XhoI"], orientation="reverse")

    def test_primer_ending_at_origin_is_readable_in_native_format(self):
        from core.tools.snapgene_io import annotate_record_primers, export_plasmid, read_native_dna_record
        record = SeqRecord(Seq("AACCGGTATA"), id="circular_source",
                           annotations={"molecule_type": "DNA", "topology": "circular"})
        annotated = annotate_record_primers(record, [{"name": "at_origin", "sequence": "GGCTATA",
                                                     "binding_sequence": "TATA", "strand": -1,
                                                     "binding_interval_0based": [6, 0]}])
        with tempfile.TemporaryDirectory() as tmp:
            files = export_plasmid(annotated, tmp)
            observed = read_native_dna_record(files["dna_file"])
            primer = next(f for f in observed.features if f.type == "primer_bind")
            self.assertEqual(str(primer.extract(observed.seq)), "TATA")
            self.assertEqual(primer.qualifiers["primer_sequence"], ["GGCTATA"])
            self.assertEqual(int(primer.location.end), 10)

    def test_recipe_required_component_is_checked_on_candidate(self):
        from scripts.run_recipe import run_recipe_cli
        with tempfile.TemporaryDirectory() as tmp:
            params = {"target_cds_seq_or_file": "ATGAAACCCGGGTTTTAA", "tag_name_or_seq": "6xHis",
                      "expected_components": [{"name": "retained_site", "expected_sequence": "GGTCTC"}]}
            with self.assertRaises(GateRejected) as caught:
                run_recipe_cli("protein_tagging", params, pathlib.Path(tmp) / "missing")
            self.assertEqual(caught.exception.error_code, "GATE_GOAL_FAILED")
            self.assertTrue((pathlib.Path(tmp) / "missing/candidate/recipe_protein_tagging.gb").exists())
            params["expected_components"] = [{"name": "source_core", "sequence": "AAACCCGGGTTT"}]
            passed = run_recipe_cli("protein_tagging", params, pathlib.Path(tmp) / "present")
            self.assertEqual(passed["goal_check"]["status"], "passed")

    def test_adjacent_reverse_join_is_equivalent_but_order_is_not(self):
        from core.tools.feature_ops import canonical_location_parts
        parts = [FeatureLocation(10, 20, strand=-1), FeatureLocation(0, 10, strand=-1)]
        single = FeatureLocation(0, 20, strand=-1)
        self.assertEqual(canonical_location_parts(CompoundLocation(parts, operator="join")),
                         canonical_location_parts(single))
        self.assertNotEqual(canonical_location_parts(CompoundLocation(parts, operator="order")),
                            canonical_location_parts(single))

    def test_serialized_source_keeps_identity_and_circular_topology(self):
        from core.io.input_resolution import resolve_sequence_record
        record = resolve_sequence_record({"id": "original_source", "name": "source_name",
                                          "sequence": "ACGTACGT",
                                          "annotations": {"topology": "circular", "molecule_type": "DNA"}})
        self.assertEqual(record.id, "original_source")
        self.assertEqual(record.name, "source_name")
        self.assertEqual(record.annotations["topology"], "circular")
        override = resolve_sequence_record({"sequence": "ACGT", "topology": "linear",
                                            "annotations": {"topology": "circular"}})
        self.assertEqual(override.annotations["topology"], "linear")

    def test_native_order_loss_cannot_be_promoted(self):
        from core.runtime_gate import _promote_verified_candidate
        record = SeqRecord(Seq("AAAACCCC"), id="order_source",
                           annotations={"molecule_type": "DNA", "topology": "linear"})
        record.features = [SeqFeature(CompoundLocation([
            FeatureLocation(4, 8, strand=1), FeatureLocation(0, 4, strand=1)], operator="order"),
            type="misc_feature", qualifiers={"label": ["ordered_feature"]})]
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp)
            with (out / "input.gb").open("w", encoding="utf-8") as handle:
                SeqIO.write(record, handle, "genbank")
            (out / "input.fasta").write_text(">order_source\nAAAACCCC\n", encoding="utf-8")
            with self.assertRaises(GateRejected) as caught:
                _promote_verified_candidate(out / "input.gb", out / "input.fasta", out / "build", {}, "order-test")
            self.assertEqual(caught.exception.error_code, "GATE_DNA_FEATURE_MISMATCH")
            self.assertFalse((out / "build/authoritative").exists())

    def test_complete_annotated_component_still_requires_stop(self):
        record = SeqRecord(Seq("ATGGCTGCT"), annotations={"molecule_type": "DNA", "topology": "linear"})
        record.features = [SeqFeature(FeatureLocation(0, 9, strand=1), type="CDS")]
        result = quick_biological_sanity_check(record, is_cds=True)
        self.assertEqual(result["guardrail_status_table"]["BIO-02-STOP"]["status"], "FAIL")

    def test_annotated_cds_phase_and_translation_table(self):
        record = SeqRecord(Seq("AATGTGATAG"), annotations={"molecule_type": "DNA", "topology": "linear"})
        record.features = [SeqFeature(FeatureLocation(0, 10, strand=1), type="CDS",
                                      qualifiers={"codon_start": ["2"], "transl_table": ["4"]})]
        result = quick_biological_sanity_check(record)
        self.assertTrue(result["all_applicable_pass"])
        self.assertFalse(result["has_premature_stop"])

    def test_terminal_stop_is_required_for_explicit_complete_cds(self):
        result = quick_biological_sanity_check("ATGGCTGCT", is_cds=True, topology="linear")
        self.assertEqual(result["guardrail_status_table"]["BIO-02-STOP"]["status"], "FAIL")
        self.assertFalse(result["all_applicable_pass"])

    def test_plasmid_domain_annotation_does_not_claim_an_independent_orf(self):
        record = SeqRecord(Seq("ATGGCTGCT"), annotations={"molecule_type": "DNA", "topology": "linear"})
        record.features = [SeqFeature(FeatureLocation(0, 9, strand=1), type="CDS", qualifiers={"label": ["fusion domain"], "partial": ["true"]})]
        result = quick_biological_sanity_check(record, is_cds=False)
        self.assertFalse(result["guardrail_status_table"]["BIO-02-STOP"]["applicable"])
        self.assertEqual(result["guardrail_status_table"]["BIO-02-STOP"]["status"], "N/A")
    def test_contract_details_cannot_replace_primer_list(self):
        primers = [{"name": "F", "seq": "ACGT"}]
        result = RecipeResult("example", "primers", "qc_only", primers=primers,
                              details={"primers": {"legacy": "detail"}})
        self.assertEqual(result["primers"], primers)
        self.assertEqual(result.get("primers"), primers)
        self.assertEqual(result.to_dict()["primers"], primers)
        self.assertEqual(result.to_dict()["details"]["primers"], {"legacy": "detail"})

    def test_pipeline_keeps_fields_and_selected_sequence_output(self):
        rng = random.Random(104)
        sequence = "".join(rng.choices("ACGT", k=240))
        forward = sequence[30:54]
        reverse = str(Seq(sequence[166:190]).reverse_complement())
        steps = [
            {"step_id": "PCR", "tool": "simulate_pcr", "params": {
                "template": sequence, "f_primer": forward, "r_primer": reverse}},
            {"step_id": "tm", "tool": "calc_primer_tm", "params": {
                "primer_seq": "$PCR.primers.0.sequence"}},
        ]
        product, records, _ = run_pipeline_steps(steps, {}, output_step="PCR")
        self.assertEqual(product, sequence[30:190])
        self.assertEqual(records[1]["details"]["length"], len(forward))
        self.assertEqual(records[0]["details"]["template"]["sequence"], sequence)

    def test_pipeline_rejects_side_effect_before_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            steps = [{"step_id": "export", "tool": "export_snapgene", "params": {
                "record_or_seq": "ACGT", "out_dir": tmp}}]
            with self.assertRaises(PlanningError) as caught:
                run_pipeline_steps(steps, {})
            self.assertEqual(caught.exception.error_code, "PIPELINE_SIDE_EFFECT")
            self.assertEqual(list(pathlib.Path(tmp).iterdir()), [])

    @staticmethod
    def pml_template():
        scaffold = "GTTTTAGAGCTAGAAATAGCAAGTTAAAATAAGGCTAGTCCGTTATCAACTTGAAAAAGTGGCACCGAGTCGGTGGTGC"
        upstream = str(Seq("GATCATTTATCTTTCACTGC").reverse_complement())
        expression = upstream + "AGAATCGATGCATTT" + scaffold[13:] + "TTTTTTT"
        expression += "".join(random.Random(79).choices("ACGT", k=240))
        record = SeqRecord(Seq(expression).reverse_complement(), id="pml_test", name="pml_test")
        record.annotations = {"molecule_type": "DNA", "topology": "circular"}
        record.features = [SeqFeature(FeatureLocation(30, 60, strand=-1), type="misc_feature",
                                     qualifiers={"label": ["backbone segment"]})]
        return record, scaffold

    def test_pml104_restores_full_scaffold_for_arbitrary_guide(self):
        source, scaffold = self.pml_template()
        guide = "ACGTCAGTCAGTCTAGTCGA"
        result = prepare_pml104_guide(source, guide)
        self.assertEqual(len(result["product_sequence"]), len(source) + 18)
        self.assertTrue(result["product_sequence"].startswith(scaffold + "TTTTTT"))
        self.assertTrue(result["product_sequence"].endswith(guide))
        self.assertEqual(result["preparation"][0]["product"]["topology"], "linear")
        self.assertEqual(result["topology"], "circular")

    def test_pml104_rejects_changed_scaffold_not_only_missing_prefix(self):
        source, _ = self.pml_template()
        expressed = str(source.seq.reverse_complement())
        site = expressed.index("TATCAACTTGA")
        changed = expressed[:site] + "C" + expressed[site + 1:]
        source.seq = Seq(changed).reverse_complement()
        with self.assertRaisesRegex(ValueError, "cassette layout"):
            prepare_pml104_guide(source, "ACGTCAGTCAGTCTAGTCGA")

    def test_preparation_export_preserves_full_oligos_and_source_dna(self):
        from sgffp import SgffReader
        source, _ = self.pml_template()
        result = prepare_pml104_guide(source, "ACGTCAGTCAGTCTAGTCGA")
        with tempfile.TemporaryDirectory() as tmp:
            files = write_preparation_artifacts(result["preparation"], tmp)
            item = files["steps"][0]
            raw = SgffReader.from_file(item["annotated_source"]["dna_file"])
            self.assertEqual([p.sequence for p in raw.primers], [p["sequence"] for p in result["primers"]])
            saved = SeqIO.read(item["annotated_source"]["gb_file"], "genbank")
            self.assertEqual(saved.seq, source.seq)
            self.assertEqual(saved.annotations["topology"], "circular")
            native = SeqIO.read(item["annotated_source"]["dna_file"], "snapgene")
            self.assertEqual(native.annotations["topology"], "circular")
            amplicon = SeqIO.read(item["product"]["gb_file"], "genbank")
            self.assertEqual(amplicon.annotations["topology"], "linear")
            self.assertTrue(pathlib.Path(files["primer_order_table"]).exists())


if __name__ == "__main__":
    unittest.main()
