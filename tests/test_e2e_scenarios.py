# -*- coding: utf-8 -*-
"""Realistic end-to-end research scenarios.

Scenario A: lab-mate backbone + GOI donor -> Gibson plan -> construct files.
Scenario B: Gateway entry clone -> LR expression vector -> validate.
Scenario C: 4-fragment Golden Gate simulation -> validate.
Scenario D: high-GC template PCR strategy + primer design.
"""
import json
import os
import pathlib
import random
import subprocess
import sys
import tempfile
import unittest

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPTS))

import simulate_advanced  # noqa: E402
from simulate_advanced import ATTL1, ATTL2, ATTR1, ATTR2  # noqa: E402


def rnd(n, seed):
    random.seed(seed)
    return "".join(random.choice("ACGT") for _ in range(n))


def orf(n_codons, seed):
    random.seed(seed)
    codons = [a + b + c for a in "ACGT" for b in "ACGT"
              for c in "ACGT" if a + b + c not in ("TAA", "TAG", "TGA")]
    return "".join(random.choice(codons) for _ in range(n_codons))


def record(seq, name, circular=True, features=()):
    rec = SeqRecord(Seq(seq), id=name, name=name)
    rec.annotations = {"molecule_type": "DNA",
                       "topology": "circular" if circular else "linear"}
    for feature in features:
        rec.features.append(feature)
    return rec


def orf_with_start_stop(n_codons, seed):
    """Generate a complete CDS fixture instead of an unvalidated random ORF."""
    return "ATG" + orf(max(0, n_codons - 2), seed) + "TAA"


def write_gb(rec, directory, name):
    path = pathlib.Path(directory) / name
    with open(path, "w", encoding="utf-8") as handle:
        SeqIO.write(rec, handle, "genbank")
    return str(path)


def run_cli(name, *args, expect_fail=False):
    completed = subprocess.run(
        [sys.executable, "-X", "utf8", "-B", str(SCRIPTS / name)] + list(args),
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if expect_fail:
        if completed.returncode == 0:
            raise AssertionError("%s unexpectedly succeeded" % name)
    else:
        if completed.returncode != 0:
            raise AssertionError("%s failed: %s" % (
                name, (completed.stderr + completed.stdout)[-1200:]))
    return completed


class ScenarioA_GibsonPlan(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("SNAPGENE_RUN_PRIMER3") == "1",
                         "set SNAPGENE_RUN_PRIMER3=1 for real Primer3 plan")
    def test_backbone_plus_goi_full_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            backbone = write_gb(record(rnd(2200, 11), "pLAB"), tmp, "backbone.gb")
            cds = orf_with_start_stop(216, 12)  # 648 bp, complete CDS
            goi_seq = rnd(60, 12) + cds + rnd(42, 112)
            donor = record(goi_seq, "pGOI", features=(
                SeqFeature(FeatureLocation(60, 708, strand=1), type="CDS",
                           qualifiers={"gene": ["GOI"], "label": ["GOI"]}),))
            donor_path = write_gb(donor, tmp, "donor.gb")
            intent = tmp / "intent.json"
            intent.write_text(json.dumps({
                "goal": "师兄骨架 + GOI", "method": "gibson",
                "backbone": {"source": 0},
                "fragments": [{"source": 1, "feature": "GOI"}],
                "topology": "circular", "name": "pLAB-GOI"}), encoding="utf-8")
            plan_json = tmp / "plan.json"
            plan_md = tmp / "plan.md"
            run_cli("plan_assembly.py", backbone, donor_path,
                    "--intent-json", str(intent),
                    "--out-json", str(plan_json),
                    "--out-markdown", str(plan_md),
                    "--out-construct", str(tmp / "construct"),
                    "--consent", "auto")
            plan = json.loads(plan_json.read_text(encoding="utf-8"))
            self.assertEqual(plan["assembly_strategy"]["method"], "gibson")
            self.assertIn(plan["status"], ("complete", "blocked"))
            self.assertEqual(len(plan["fragment_assignments"]), 2)
            self.assertTrue(plan["primers"][0]["forward"]["sequence"])
            construct = SeqIO.read(str(tmp / "construct.gb"), "genbank")
            self.assertEqual(len(construct.seq), 2200 + 648)
            self.assertEqual(str(construct.seq), rnd(2200, 11) + cds)
            self.assertTrue(all(p['complete_oligo_structure']['passed'] for p in plan['primers']))
            # The full backbone contributes its promoter and existing feature;
            # the selected donor CDS is migrated as a third feature.
            self.assertEqual(len(construct.features), 3)
            # validate final construct
            run_cli("validate_construct.py", str(tmp / "construct.gb"),
                    "--json")


class ScenarioB_GatewayLR(unittest.TestCase):
    def test_entry_to_destination_lr(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            goi = orf_with_start_stop(200, 13)
            entry = record(ATTL1 + goi + str(Seq(ATTL2).reverse_complement()),
                            "pENTR-GOI")
            entry.features = [
                SeqFeature(FeatureLocation(0, len(ATTL1)), type="protein_bind",
                           qualifiers={"label": ["attL1"]}),
                SeqFeature(FeatureLocation(len(ATTL1), len(ATTL1) + len(goi)),
                           type="CDS", qualifiers={"gene": ["GOI"]}),
                SeqFeature(FeatureLocation(len(ATTL1) + len(goi), len(entry)),
                           type="protein_bind", qualifiers={"label": ["attL2"]}),
            ]
            dest = record(ATTR1 + rnd(1200, 14)
                           + str(Seq(ATTR2).reverse_complement()), "pDEST")
            entry_path = write_gb(entry, tmp, "entry.gb")
            dest_path = write_gb(dest, tmp, "dest.gb")
            out = tmp / "lr_product.gb"
            completed = run_cli("simulate_advanced.py", "--method",
                                "gateway-lr", "--entry", entry_path,
                                "--destination", dest_path,
                                "--out", str(out), "--json")
            payload = json.loads(completed.stdout)
            self.assertTrue(payload.get("ok"))
            product = SeqIO.read(out, "genbank")
            self.assertIn(goi, str(product.seq))
            self.assertIn(simulate_advanced.ATTB1, str(product.seq))
            run_cli("validate_construct.py", str(out), "--json")


class ScenarioC_GoldenGate(unittest.TestCase):
    def test_four_fragment_golden_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            overhangs = [("AAAA", "TTTT"), ("TTTT", "CCCC"),
                         ("CCCC", "GGGG"), ("GGGG", "AAAA")]
            parts = []
            for i, (left, right) in enumerate(overhangs):
                seq = ("GGTCTC" + "A" + left + rnd(60, 20 + i) + right
                       + "A" + "GAGACC")
                circular = i == 0
                parts.append(write_gb(
                    record(seq, "part%d" % (i + 1), circular=circular),
                    tmp, "part%d.gb" % (i + 1)))
            out = tmp / "gg_product.gb"
            completed = run_cli("golden_gate.py", "--parts", *parts,
                                "--enzyme", "BsaI", "--out", str(out),
                                "--json")
            payload = json.loads(completed.stdout)
            self.assertTrue(payload.get("ok"))
            product = SeqIO.read(out, "genbank")
            self.assertGreater(len(product.seq), 200)
            run_cli("validate_construct.py", str(out), "--json")


class ScenarioD_HighGcPcr(unittest.TestCase):
    def test_high_gc_strategy_and_primers(self):
        import pcr_strategy
        import primer_design_engine
        from operation_consent import ConsentBroker
        template = ("G" * 40 + "CGCGCGCGCGCGATATATCGCGCGCG" * 20 + "C" * 40)
        profile = {"length": len(template), "gc_percent": 78.0,
                   "purpose": "cloning"}
        strategy = pcr_strategy.recommend_pcr_strategy(profile)
        self.assertIn("GC", strategy["recommended_enzyme"])
        self.assertTrue(strategy["protocol"]["url"].startswith("https://"))
        result = primer_design_engine.design_region_primers(
            template, 0, min_len=15, max_len=25, top_n=1,
            consent=ConsentBroker(policy="auto"))
        self.assertIn(result["backend"], ("primer3-core", "heuristic"))
        self.assertTrue(result["validation"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
