
from repository_paths import PROJECT_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS
import json
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from core.errors import PlanningError
from core.handlers.composite_pipeline import CompositePipelineHandler


ROOT = SKILL_ROOT


def _pcr_step(template, forward, reverse):
    return {
        "step_id": "pcr",
        "tool": "simulate_pcr",
        "params": {
            "template_path_or_seq": template,
            "f_primer": forward,
            "r_primer": reverse,
        },
    }


class FinalPipelineTopologyTests(unittest.TestCase):
    @staticmethod
    def _template():
        rng = random.Random(20260908)
        sequence = "".join(rng.choice("ACGT") for _ in range(180))
        forward = sequence[20:40]
        reverse = str(Seq(sequence[100:120]).reverse_complement())
        return sequence, forward, reverse

    def test_handler_rejects_explicit_topology_mismatch_after_real_pcr(self):
        sequence, forward, reverse = self._template()
        task = {
            "pipeline": {
                "steps": [_pcr_step(sequence, forward, reverse)],
                "output_step": "pcr",
            },
            "product": {"topology": "circular"},
        }

        with self.assertRaises(PlanningError) as caught:
            CompositePipelineHandler().plan(task)

        self.assertEqual(caught.exception.error_code, "PRODUCT_TOPOLOGY_MISMATCH")
        self.assertEqual(caught.exception.details["requested_topology"], "circular")
        self.assertEqual(caught.exception.details["actual_topology"], "linear")

    def test_handler_infers_linear_output_when_topology_is_absent(self):
        sequence, forward, reverse = self._template()
        plan = CompositePipelineHandler().plan({
            "pipeline": {
                "steps": [_pcr_step(sequence, forward, reverse)],
                "output_step": "pcr",
            },
            "product": {},
        })

        self.assertEqual(plan["product_topology"], "linear")
        self.assertEqual(plan["actual_topology"], "linear")
        self.assertIsNone(plan["requested_topology"])

    def test_handler_preserves_linear_topology_through_source_reverse_complement(self):
        sequence, _, _ = self._template()
        with tempfile.TemporaryDirectory(prefix="pipeline-source-topology-") as temp:
            source_path = Path(temp) / "linear-source.gb"
            source = SeqRecord(
                Seq(sequence),
                id="linear_source",
                annotations={"molecule_type": "DNA", "topology": "linear"},
            )
            with source_path.open("w", encoding="utf-8") as handle:
                SeqIO.write(source, handle, "genbank")

            plan = CompositePipelineHandler().plan({
                "pipeline": {
                    "steps": [{
                        "step_id": "reverse_source",
                        "tool": "reverse_complement",
                        "params": {"seq": "$src"},
                    }],
                    "output_step": "reverse_source",
                },
                "sources": [{"source_id": "src", "path": str(source_path)}],
                "product": {},
            })

        self.assertEqual(plan["product_topology"], "linear")
        self.assertEqual(plan["actual_topology"], "linear")
        self.assertIsNone(plan["requested_topology"])

    def test_cli_infers_linear_topology_for_source_record_pcr(self):
        sequence, forward, reverse = self._template()
        with tempfile.TemporaryDirectory(prefix="pipeline-topology-") as temp:
            temp_path = Path(temp)
            source_path = temp_path / "linear-source.gb"
            pipeline_path = temp_path / "pcr.json"
            out_dir = temp_path / "out"
            source = SeqRecord(
                Seq(sequence),
                id="linear_source",
                annotations={"molecule_type": "DNA", "topology": "linear"},
            )
            with source_path.open("w", encoding="utf-8") as handle:
                SeqIO.write(source, handle, "genbank")
            pipeline_path.write_text(json.dumps({
                "task_id": "linear-pcr",
                "sources": [{"source_id": "src", "path": str(source_path)}],
                "steps": [_pcr_step("$src", forward, reverse)],
            }), encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    "-X",
                    "utf8",
                    "-B",
                    str(ROOT / "scripts" / "run_pipeline.py"),
                    "--pipeline",
                    str(pipeline_path),
                    "--out-dir",
                    str(out_dir),
                    "--json",
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )

            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            result = json.loads(completed.stdout)
            self.assertEqual(result["requested_topology"], None)
            self.assertEqual(result["actual_topology"], "linear")
            self.assertEqual(result["product_topology"], "linear")
            plan = json.loads((out_dir / "plan.json").read_text(encoding="utf-8"))
            self.assertEqual(plan["actual_topology"], "linear")
            self.assertEqual(plan["product_topology"], "linear")


if __name__ == "__main__":
    unittest.main()
