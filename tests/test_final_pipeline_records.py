# -*- coding: utf-8 -*-
"""Regression tests for final pipeline record delivery and failure state."""

from __future__ import annotations

from repository_paths import PROJECT_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

from core.errors import PlanningError
from core.handlers.composite_pipeline import CompositePipelineHandler, run_pipeline_steps


ROOT = SKILL_ROOT


class FinalPipelineRecordTests(unittest.TestCase):
    def test_raw_path_cannot_be_reverse_complemented_as_dna(self):
        from core.tools.translation import reverse_complement, translate_dna
        with self.assertRaisesRegex(ValueError, "could not be resolved"):
            reverse_complement("C:/data/source.gb")
        with self.assertRaisesRegex(ValueError, "frame must"):
            translate_dna("ATGAAATAA", frame=0)

    def test_source_reference_loads_complete_record_and_reverse_complements_features(self):
        source = SeqRecord(
            Seq("ATGGCTAAATAA"),
            id="complete_source",
            name="complete_source",
            annotations={"molecule_type": "DNA", "topology": "linear"},
        )
        source.features = [
            SeqFeature(
                FeatureLocation(0, 12, strand=1),
                type="CDS",
                qualifiers={"label": ["full_cds"]},
            )
        ]

        with tempfile.TemporaryDirectory(prefix="pipeline-source-") as temp:
            source_path = Path(temp) / "source.gb"
            with source_path.open("w", encoding="utf-8") as handle:
                SeqIO.write(source, handle, "genbank")

            product, records, env = run_pipeline_steps(
                [
                    {
                        "step_id": "reverse_source",
                        "tool": "reverse_complement",
                        "params": {"seq": "$src"},
                    }
                ],
                {"src": str(source_path)},
            )

        self.assertEqual(str(product.seq), "TTATTTAGCCAT")
        self.assertEqual(records[0]["output_length"], 12)
        result = env["reverse_source"].only_product()
        self.assertIsInstance(result, SeqRecord)
        self.assertEqual(result.annotations["topology"], "linear")
        self.assertEqual(len(result.features), 1)
        feature = result.features[0]
        self.assertEqual(feature.type, "CDS")
        self.assertEqual((int(feature.location.start), int(feature.location.end)), (0, 12))
        self.assertEqual(feature.location.strand, -1)
        self.assertEqual(str(feature.extract(result.seq)), "ATGGCTAAATAA")

    def test_translation_result_is_analysis_and_cannot_be_selected_as_product(self):
        steps = [
            {
                "step_id": "dna",
                "tool": "reverse_complement",
                "params": {"seq": "ATGAAA"},
            },
            {
                "step_id": "protein",
                "tool": "translate_dna",
                "params": {"seq": "$dna"},
            },
        ]

        product, records, env = run_pipeline_steps(steps, {}, output_step="dna")
        self.assertEqual(str(product.seq), "TTTCAT")
        self.assertEqual(env["protein"].analysis['translation'], "FH")
        self.assertIsNone(records[1]["output_length"])
        self.assertEqual(records[1]["details"]['analysis']['translation'], {'data_type':'protein_sequence','value':'FH'})

        field_steps = [
            {
                "step_id": "dna",
                "tool": "reverse_complement",
                "params": {"seq": "ATGAAA"},
            },
            {
                "step_id": "tm",
                "tool": "calc_primer_tm",
                "params": {"primer_seq": "$dna"},
            },
            {
                "step_id": "rc_field",
                "tool": "reverse_complement",
                "params": {"seq": "$tm.analysis.sequence"},
            },
        ]
        selected, _, field_env = run_pipeline_steps(field_steps, {}, output_step="dna")
        self.assertEqual(str(selected.seq), "TTTCAT")
        self.assertEqual(field_env["tm"].analysis["sequence"], "TTTCAT")
        self.assertEqual(str(field_env["rc_field"].only_product().seq), "ATGAAA")

        with self.assertRaises(PlanningError) as caught:
            CompositePipelineHandler().plan(
                {
                    "pipeline": {"steps": steps, "output_step": "protein"},
                    "product": {"topology": "linear"},
                }
            )
        self.assertEqual(caught.exception.error_code, "ANALYSIS_OUTPUT_REFERENCE")

        with self.assertRaises(PlanningError) as caught:
            run_pipeline_steps(
                steps
                + [
                    {
                        "step_id": "reuse_protein",
                        "tool": "reverse_complement",
                        "params": {"seq": "$protein"},
                    }
                ],
                {},
            )
        self.assertEqual(caught.exception.error_code, "ANALYSIS_OUTPUT_REFERENCE")

    def test_construction_task_invalid_input_replaces_old_result_without_deleting_history(self):
        with tempfile.TemporaryDirectory(prefix="construction-failure-") as temp:
            out = Path(temp)
            authoritative = out / "authoritative"
            authoritative.mkdir()
            marker = authoritative / "historical.marker"
            marker.write_text("keep", encoding="utf-8")
            (out / "result.json").write_text(
                json.dumps({"status": "delivered", "delivery": {"status": "delivered"}}),
                encoding="utf-8",
            )
            invalid_task = out / "invalid-task.json"
            invalid_task.write_text("{\"schema_version\":", encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    "-X",
                    "utf8",
                    "-B",
                    str(ROOT / "scripts" / "run_construction_task.py"),
                    "--task-json",
                    str(invalid_task),
                    "--out-dir",
                    str(out),
                    "--json",
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

            self.assertEqual(completed.returncode, 2, completed.stdout + completed.stderr)
            result = json.loads((out / "result.json").read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "blocked")
            self.assertIsNone(result["delivery"])
            self.assertFalse(result["write_authoritative_artifact"])
            self.assertTrue(result["historical_artifacts_preserved"])
            self.assertEqual(result["error"]["error_code"], "TASK_JSON_INVALID")
            self.assertTrue(marker.exists())


if __name__ == "__main__":
    unittest.main()
