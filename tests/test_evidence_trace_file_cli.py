"""Real file CLI A/B: source inspection, conversion, primer edits and preview export."""
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import SeqFeature, SimpleLocation
from Bio.SeqRecord import SeqRecord

ROOT = Path(__file__).resolve().parents[1]


class FileCLITests(unittest.TestCase):
    def test_all_file_entry_points_preserve_dna_and_annotations_in_three_levels(self):
        with tempfile.TemporaryDirectory(prefix="trace-file-中文-") as tmp:
            root = Path(tmp)
            rng = random.Random(441)
            seq = "ATG" + "".join(rng.choice(["GCT", "GAA", "TTC", "GGT"]) for _ in range(170)) + "TAA"
            seq += "".join(rng.choice("ACGT") for _ in range(600))
            record = SeqRecord(Seq(seq), id="source", name="source", description="Synthetic circular annotated source")
            record.annotations.update(molecule_type="DNA", topology="circular")
            record.features = [SeqFeature(SimpleLocation(0, 516), type="CDS", qualifiers={"label": ["synthetic CDS"]})]
            source = root / "源.gb"
            with source.open("w", encoding="utf-8") as fh:
                SeqIO.write(record, fh, "genbank")
            products = {}
            for level in ("off", "observed", "full"):
                out = root / level
                out.mkdir()
                config = out / "settings.json"
                config.write_text(json.dumps({"trace_level": level}), encoding="utf-8")
                env = {**os.environ, "SNAPGENE_TRACE_CONFIG": str(config)}
                trace = out / "trace"
                def cli(script, *args, expected=0):
                    result = subprocess.run([sys.executable, "-X", "utf8", "-B", str(ROOT / "scripts" / script),
                                             *map(str, args), "--trace-dir", str(trace)], cwd=ROOT,
                                            env=env, capture_output=True, encoding="utf-8", errors="replace")
                    self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
                    self.assertNotIn("TRACE_INCOMPLETE", result.stderr)
                    payload = json.loads(result.stdout)
                    return payload.get("data", payload) if isinstance(payload, dict) else payload
                inspected = cli("inspect_plasmid.py", source, "--json")
                self.assertTrue(inspected)
                dna = out / "source.dna"
                cli("convert.py", source, "--out", dna, "--format", "snapgene", "--json")
                for original, suffix in ((source, "gb"), (dna, "dna")):
                    target = out / ("引物." + suffix)
                    result = cli("annotate_primers.py", original, "--out", target, "--op", "add",
                                 "--name", "check", "--seq", seq[550:574], "--bind-pos", 550, "--strand", "+", "--json")
                    self.assertEqual(result["primers_count"], 1)
                    self.assertEqual(str(SeqIO.read(str(target), "genbank" if suffix == "gb" else "snapgene").seq), seq)
                bundle = cli("export_delivery_bundle.py", out / "引物.gb", "--out-dir", out / "bundle", "--json")
                self.assertEqual(bundle["artifact_class"], "preview")
                products[level] = [(out / name).read_bytes() for name in ("source.dna", "引物.gb", "引物.dna")]
                if level == "off":
                    self.assertFalse(trace.exists())
                else:
                    graph = json.loads((trace / "graph.json").read_text(encoding="utf-8"))
                    artifacts = [n for n in graph["nodes"] if n["kind"] == "artifact"]
                    for suffix in ("gb", "dna"):
                        found = [n for n in artifacts if n["path"] == str(out / ("引物." + suffix))]
                        self.assertEqual(len(found), 1)
                        self.assertEqual(found[0]["generation_observation"], "created")
                    self.assertTrue(any(n["role"] == "preview" for n in artifacts))
                    self.assertFalse(any(n["role"] == "authoritative" for n in artifacts))
            self.assertEqual(products["off"], products["observed"])
            self.assertEqual(products["off"], products["full"])


if __name__ == "__main__":
    unittest.main()
