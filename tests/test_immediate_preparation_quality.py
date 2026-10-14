"""Current preparation facts, independent positive/negative material and real backend."""
from repository_paths import SKILL_ROOT
import copy
import random
import sys
import unittest
from unittest import mock

from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

sys.path.insert(0, str(SKILL_ROOT))
from core.models.molecule import as_molecule
from core.tools.primer3_backend import Primer3CoreError, discover_primer3_core
from core.workflow import run_step


def synthetic_record(sequence, name="independent", topology="linear"):
    return as_molecule(SeqRecord(Seq(sequence), id=name, name=name,
        annotations={"molecule_type":"DNA", "topology":topology}))


def independent_pcr_row(tail=""):
    rng = random.Random(788759)
    raw = "".join(rng.choice("ACGT") for _ in range(650))
    forward, reverse = raw[100:122], str(Seq(raw[380:402]).reverse_complement())
    return {"id":"independent-pcr", "method":"PCR", "template":synthetic_record(raw),
        "product":synthetic_record(tail+raw[100:402], "prepared"),
        "primers":[{"name":"F", "sequence":tail+forward, "binding_sequence":forward,
                    "binding_interval_0based":[100,122], "strand":1},
                   {"name":"R", "sequence":reverse, "binding_sequence":reverse,
                    "binding_interval_0based":[380,402], "strand":-1}]}


@unittest.skipUnless(discover_primer3_core(), "Real primer3_core required")
class ImmediatePreparationQualityTests(unittest.TestCase):
    def test_quikchange_reaction_can_match_while_complete_oligos_fail(self):
        rng = random.Random(421992)
        stem = "GCGCGCGCGCGCGCG"
        raw = ("".join(rng.choice("ACGT") for _ in range(250)) + stem + "GGG"
               + str(Seq(stem).reverse_complement()) + "".join(rng.choice("ACGT") for _ in range(400)))
        source = synthetic_record(raw, topology="circular")
        step = run_step("recipe_site_directed_mutagenesis", {"template_seq_or_file":"$source",
            "start_0based":265,"end_0based":268,"alt_seq":"AAA","target_flank_bp":15,"method":"quikchange"},
            sources={"source":source},step_id="mutation")
        self.assertIsNone(step.error)
        self.assertEqual(str(step.result.only_product().seq), raw[:265]+"AAA"+raw[268:])
        self.assertEqual(str(source.seq), raw)
        facts = step.result.analysis["preparation_feedback"]
        self.assertEqual(facts["reaction_replay"]["status"], "PASSED")
        self.assertEqual(facts["quality"]["status"], "FAILED")
        self.assertEqual(facts["status"], "FAILED")
        self.assertFalse(facts["ready_for_preparation"])
        self.assertEqual(facts["quality"]["checks"][0]["template_version"], source.record_version)
        self.assertTrue(facts["quality"]["checks"][0]["failed_metrics"])
        self.assertEqual(step.result.analysis["quality_checks"]["complete_oligo_structure_status"], "FAILED")
        self.assertTrue(step.result.analysis["warnings"])
        self.assertEqual(step.params["method"], "quikchange")

    def test_valid_pcr_checks_actual_pair_and_template_without_mutating_input(self):
        from core.preparation import preparation_feedback
        row = independent_pcr_row()
        before = copy.deepcopy(row)
        result = preparation_feedback([row])
        self.assertEqual(result["status"], "PASSED")
        self.assertTrue(result["ready_for_preparation"])
        self.assertEqual(result["reaction_replay"]["status"], "PASSED")
        check = result["quality"]["checks"][0]
        self.assertEqual(check["template_version"], row["template"].record_version)
        self.assertEqual([p["sequence_5to3"] for p in check["oligos"]], [p["sequence"] for p in row["primers"]])
        self.assertEqual(str(row["template"].seq), str(before["template"].seq))
        self.assertEqual(row["primers"], before["primers"])
        self.assertEqual(result["wet_lab"], "NOT_CHECKED")

    def test_current_template_change_fails_replay_even_with_unchanged_structure(self):
        from core.preparation import preparation_feedback
        row = independent_pcr_row()
        raw = str(row["template"].seq)
        current = raw[:121] + next(b for b in "ACGT" if b != raw[121]) + raw[122:]
        row["template"] = synthetic_record(current, "current")
        result = preparation_feedback([row])
        self.assertEqual(result["reaction_replay"]["status"], "FAILED")
        self.assertEqual(result["status"], "FAILED")
        self.assertFalse(result["ready_for_preparation"])
        self.assertIn("binding site", result["reaction_replay"]["checks"][0]["reason"])

    def test_current_complete_tail_and_condition_are_measured(self):
        from core.preparation import preparation_feedback
        stem = "GCGCGCGCGC"
        tail = stem+"TTTT"+str(Seq(stem).reverse_complement())
        row = independent_pcr_row(tail)
        old = preparation_feedback([row])
        current = copy.deepcopy(row)
        current["annealing_temperature_hint_C"] = 60.0
        new = preparation_feedback([current])
        self.assertEqual(old["reaction_replay"]["status"], "PASSED")
        self.assertEqual(old["quality"]["status"], "FAILED")
        first, second = old["quality"]["checks"][0], new["quality"]["checks"][0]
        self.assertTrue(first["oligos"][0]["sequence_5to3"].startswith(tail))
        self.assertEqual(first["result"]["structure_limit_C"], 47.0)
        self.assertEqual(second["result"]["structure_limit_C"], 55.0)
        self.assertEqual(second["result"]["annealing_temperature_C"], 60.0)
        self.assertTrue(second["failed_metrics"])

    def test_backend_limit_preserves_true_candidate_as_incomplete(self):
        from core.preparation import preparation_feedback
        row = independent_pcr_row("ACGT"*10)
        result = preparation_feedback([row])
        self.assertEqual(result["reaction_replay"]["status"], "PASSED")
        self.assertEqual(result["quality"]["status"], "INCOMPLETE")
        self.assertFalse(result["ready_for_preparation"])
        self.assertEqual(result["quality"]["checks"][0]["error_code"], "BACKEND_LIMIT_UNSUPPORTED")
        self.assertEqual(str(row["product"].seq), "ACGT"*10+str(row["template"].seq)[100:402])

    def test_backend_unavailable_is_not_quality_failure_or_pass(self):
        from core.preparation import preparation_feedback
        with mock.patch("core.tools.primer3_backend.check_complete_oligo_pair",
             side_effect=Primer3CoreError("unavailable", "BACKEND_UNAVAILABLE")):
            result = preparation_feedback([independent_pcr_row()])
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertEqual(result["reaction_replay"]["status"], "PASSED")
        self.assertEqual(result["quality"]["checks"][0]["error_code"], "BACKEND_UNAVAILABLE")

    def test_same_edit_reports_current_readiness_for_each_requested_method(self):
        rng = random.Random(488729)
        raw = "".join(rng.choice("ACGT") for _ in range(490))
        source = synthetic_record(raw, "independent_routes", "circular")
        alternate = "ACG" if raw[223:226] != "ACG" else "ATC"
        expected = raw[:223]+alternate+raw[226:]
        for method in ("quikchange", "inverse_pcr"):
            with self.subTest(method=method):
                step = run_step("recipe_site_directed_mutagenesis", {"template_seq_or_file":"$source",
                    "start_0based":223,"end_0based":226,"alt_seq":alternate,"target_flank_bp":20,"method":method},
                    sources={"source":source},step_id=method)
                self.assertIsNone(step.error, step.error)
                self.assertEqual(str(step.result.only_product().seq), expected)
                facts = step.result.analysis["preparation_feedback"]
                # Independent raw Primer3-core confirms 54.2 C on this
                # QuikChange forward oligo, above the unchanged 47 C screen.
                # Keep this original material; inverse-PCR is a different
                # explicitly requested route with independently valid oligos.
                expected_status = "FAILED" if method == "quikchange" else "PASSED"
                self.assertEqual(facts["status"], expected_status)
                self.assertEqual(facts["ready_for_preparation"], method == "inverse_pcr")
                self.assertEqual(step.params["method"], method)
                self.assertEqual({r["method"] for r in facts["reaction_replay"]["checks"]}, {method})
                self.assertEqual(facts["quality"]["checks"][0]["template_version"], source.record_version)
        self.assertEqual(str(source.seq), raw)

    def test_retained_second_candidate_is_not_assumed_structurally_valid(self):
        from core.recipes.mutagenesis import recipe_site_directed_mutagenesis
        rng = random.Random(288511)
        left, right = "AGTCGACATCGATGAGCTGC", "GCGATACGCTAGTGACGTCA"
        raw = ("".join(rng.choice("ACGT") for _ in range(100))+left+"GGG"+right
               +"".join(rng.choice("ACGT") for _ in range(250)))
        source = synthetic_record(raw, "normal_mutation", "circular")
        result = recipe_site_directed_mutagenesis(source,120,123,"CCA",target_flank_bp=20,method="quikchange")
        self.assertEqual(str(result.product_record.seq), raw[:120]+"CCA"+raw[123:])
        self.assertEqual(result.analysis["preparation_feedback"]["status"], "FAILED")
        self.assertFalse(result.analysis["preparation_feedback"]["ready_for_preparation"])
        check = result.analysis["preparation_feedback"]["quality"]["checks"][0]
        self.assertEqual(check["template_version"], source.record_version)
        self.assertEqual(check["oligos"][0]["sequence_5to3"], left+"CCA"+right)

    def test_independent_quikchange_pair_without_self_complementarity_passes(self):
        from core.recipes.mutagenesis import recipe_site_directed_mutagenesis
        rng = random.Random(291841)
        left, right = "AGGAGAGAGGAGGGAAGGAG", "GGAAGAGGAGGAAGAAGAGG"
        raw = ("".join(rng.choice("ACGT") for _ in range(100))+left+"CCC"+right
               +"".join(rng.choice("ACGT") for _ in range(250)))
        source = synthetic_record(raw, "independent_ag_flanks", "circular")
        result = recipe_site_directed_mutagenesis(source,120,123,"GAG",target_flank_bp=20,method="quikchange")
        self.assertEqual(str(result.product_record.seq), raw[:120]+"GAG"+raw[123:])
        facts = result.analysis["preparation_feedback"]
        self.assertEqual(facts["status"], "PASSED")
        self.assertTrue(facts["ready_for_preparation"])
        forward, reverse = facts["quality"]["checks"][0]["oligos"]
        # F contains A/G only, R T/C only: neither contains complementary
        # bases within itself. The intentional F/R QuikChange duplex is separate.
        self.assertLessEqual(set(forward["sequence_5to3"]), {"A","G"})
        self.assertLessEqual(set(reverse["sequence_5to3"]), {"T","C"})

    def test_shared_feedback_applies_to_actual_gibson_preparations(self):
        from core.recipes.gibson import recipe_gibson_assembly
        rng = random.Random(349862)
        raw = "".join(rng.choice("ACGT") for _ in range(600))
        left = synthetic_record("".join(rng.choice("ACGT") for _ in range(40))+raw[:320]+"".join(rng.choice("ACGT") for _ in range(50)), "left_source")
        right = synthetic_record("".join(rng.choice("ACGT") for _ in range(45))+raw[300:]+"".join(rng.choice("ACGT") for _ in range(55)), "right_source")
        result = recipe_gibson_assembly(fragments=[{"id":"left","template":left,"start":40,"end":360},
          {"id":"right","template":right,"start":45,"end":345}],overlap_length=20,circular_product=False)
        self.assertEqual(str(result.product_record.seq), raw)
        facts = result.analysis["preparation_feedback"]
        self.assertEqual(facts["status"], "PASSED")
        self.assertEqual(len(facts["quality"]["checks"]), 2)
        self.assertEqual({r["template_version"] for r in facts["quality"]["checks"]}, {left.record_version,right.record_version})

    def test_reconstructing_result_does_not_repeat_measurements(self):
        from core.preparation import preparation_feedback
        from core.recipes.contract import RecipeResult
        row = independent_pcr_row()
        facts = preparation_feedback([row])
        with mock.patch("core.preparation.preparation_feedback") as measure:
            result = RecipeResult(recipe_name="reconstructed",result_kind="component",completeness="component_only",
                products=[row["product"]],analysis={"preparation_feedback":facts},details={"preparation":[row]})
            measure.assert_not_called()
        self.assertEqual(result.analysis["preparation_feedback"], facts)

    def test_no_preparation_rows_do_not_manufacture_pass(self):
        from core.recipes.contract import RecipeResult
        for kind, completeness in (("verification","qc_only"),("component","component_only"),("protocol","qc_only")):
            with self.subTest(kind=kind):
                result = RecipeResult(recipe_name="analysis_only",result_kind=kind,completeness=completeness)
                self.assertNotIn("preparation_feedback", result.analysis)
                self.assertEqual(result.quality_checks, {})

    def test_missing_template_retains_structure_but_cannot_pass_preparation_quality(self):
        from core.preparation import check_preparation_quality
        row = independent_pcr_row()
        del row["template"]
        result = check_preparation_quality([row])
        self.assertEqual(result["status"], "INCOMPLETE")
        check = result["checks"][0]
        self.assertEqual(check["error_code"], "PREPARATION_TEMPLATE_NOT_PROVIDED")
        self.assertTrue(check["result"]["passed"])
        self.assertIsNone(check["template_version"])
        self.assertEqual(check["binding_context_status"], "NOT_PROVIDED")

    def test_missing_template_does_not_mask_unavailable_backend(self):
        from core.preparation import check_preparation_quality
        row = independent_pcr_row()
        del row["template"]
        with mock.patch("core.tools.primer3_backend.check_complete_oligo_pair",
             side_effect=Primer3CoreError("unavailable", "BACKEND_UNAVAILABLE")):
            result = check_preparation_quality([row])
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertEqual(result["checks"][0]["error_code"], "BACKEND_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
