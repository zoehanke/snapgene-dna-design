# -*- coding: utf-8 -*-
"""Smoke / regression tests for the snapgene-dna-design skill.

Run with:  python tests/test_smoke.py
Portable: locates the scripts directory relative to this file.
"""

from project_paths import PROJECT_ROOT as REPOSITORY_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS, TESTS_ROOT
import json
import os
import shutil
import subprocess
import sys
import tempfile
import atexit

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = str(RUNTIME_SCRIPTS)
PY = sys.executable
sys.path.insert(0, SCRIPTS)

import simulate_advanced as simadv  # noqa: E402

PASS = []
FAIL = []


def check(name, cond, detail=""):
    if cond:
        PASS.append(name)
        print("PASS  %s" % name)
    else:
        FAIL.append(name)
        print("FAIL  %s  %s" % (name, detail))


def run(*args):
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run([PY] + list(args), cwd=SCRIPTS,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=env)


def run_ok(*args):
    r = run(*args)
    check("exit=0: %s %s" % (os.path.basename(args[0]), args[1] if len(args) > 1 else ""),
          r.returncode == 0, r.stderr[-300:])
    return r


def script(name):
    return os.path.join(SCRIPTS, name)


def main():
    # P0: distinguish recognition start (2) from first base after top cut (3)
    r = run_ok(script("find_sites.py"), "GGAATTCC", "--enzyme", "EcoRI", "--json")
    _env = json.loads(r.stdout)
    d = _env.get("data", _env)
    check("find_sites EcoRI recognition start == 2", d["results"][0]["sites_1based"] == [2],
          str(d["results"][0]))
    check("find_sites EcoRI top cut before base 3",
          d["results"][0]["top_cut_first_bases_1based"] == [3],
          str(d["results"][0]))

    # P0: circular restriction site crossing the origin is found
    r = run_ok(script("find_sites.py"), "AATTCAAAAG", "--enzyme", "EcoRI",
               "--topology", "circular", "--json")
    _env = json.loads(r.stdout)
    cross = _env["data"]["results"][0]
    check("circular EcoRI site starts at 10 and wraps origin",
          cross["sites_1based"] == [10] and cross["hits"][0]["wraps_origin"],
          str(cross))

    # P0: topology defaults linear
    check("topology defaults linear", d["topology"] == "linear", d["topology"])

    # P1: missing path reported
    r = run(script("parse_dna.py"), "missing.gb")
    check("missing path reported", r.returncode != 0 and "not found" in (r.stderr + r.stdout),
          (r.stderr + r.stdout)[-200:])

    # P1: translation frame mapping (--frame 1 -> +1, --frame 6 -> -3)
    r = run_ok(script("analyze_seq.py"), "ATGGGATAAATGGGATAA", "translate", "--frame", "1", "--json")
    _env = json.loads(r.stdout)
    d = _env.get("data", _env)
    check("translate envelope present", _env["schema_version"] == "0.5.0" and "translations" in d, str(d))
    check("frame 1 == +1", d["translations"][0]["frame"] == "+1", str(d))
    r = run_ok(script("analyze_seq.py"), "ATGGGATAAATGGGATAA", "translate", "--frame", "6", "--json")
    _env = json.loads(r.stdout)
    d = _env.get("data", _env)
    check("frame 6 == -3", d["translations"][0]["frame"] == "-3", str(d))

    # P1: separate forward/reverse restriction-site tails
    r = run_ok(script("design_primers.py"),
               "ATGCATGCATGCATGCATGCATGCATGCATGCATGCATGCATGC",
               "--start", "1", "--end", "42",
               "--fwd-site", "EcoRI", "--rev-site", "BamHI", "--consent", "auto", "--json")
    _env = json.loads(r.stdout)
    d = _env.get("data", _env)
    fwd_seq = d["forward"]["sequence"]
    rev_seq = d["reverse"]["sequence"]
    check("forward has EcoRI not BamHI", "GAATTC" in fwd_seq and "GGATCC" not in fwd_seq, fwd_seq)
    check("reverse has BamHI not EcoRI", "GGATCC" in rev_seq and "GAATTC" not in rev_seq, rev_seq)
    check("primer binding remains anchored to requested region",
          d["forward"]["bind_start"] == 1 and d["reverse"]["bind_end"] == 42
          and d["product_size"] == 42, str(d))
    r = run(script("design_primers.py"),
            "ATGCATGCATGCATGCATGCATGCATGCATGCATGCATGCATGC",
            "--start", "1", "--end", "42", "--consent", "auto")
    check("design_primers text mode does not crash", r.returncode == 0, r.stderr[-200:])

    # P0: gibson overlap mismatch raises instead of silently joining
    r = run(script("simulate_cloning.py"), "--method", "gibson",
            "--parts", "AAAAAA", "TTTTTT", "--overlap", "4")
    err = json.loads(r.stdout)
    check("gibson overlap mismatch raises",
          r.returncode != 0 and err.get("ok") is False
          and err["error"]["code"] == "OVERLAP_MISMATCH", str(err))

    # P0: write_dna snapgene-gb round-trips cleanly (no phantom features)
    tmp = tempfile.mkdtemp()
    atexit.register(shutil.rmtree, tmp, ignore_errors=True)
    gb = os.path.join(tmp, "out.gb")
    run_ok(script("write_dna.py"), "ATGCATGCATGC", "--out", gb,
           "--format", "snapgene-gb", "--name", "pTest")
    from Bio import SeqIO
    from Bio.Seq import Seq
    from Bio.SeqFeature import CompoundLocation, FeatureLocation, SeqFeature
    from Bio.SeqRecord import SeqRecord
    rec = next(SeqIO.parse(gb, "genbank"))
    check("snapgene-gb re-reads with 0 features", len(rec.features) == 0, str(len(rec.features)))
    check("snapgene-gb LOCUS name Exported", rec.name == "Exported", rec.name)

    # P0: native .dna write + re-read round-trip
    dna = os.path.join(tmp, "out.dna")
    run_ok(script("write_dna.py"), "ATGCATGCATGC", "--out", dna,
           "--format", "dna", "--name", "pNative")
    import sg_common
    rec2, _fmt = sg_common.load_seq(dna)
    check("native .dna re-reads sequence", str(rec2.seq) == "ATGCATGCATGC", str(rec2.seq))

    # P0: annotate --out-gb + enzyme no longer fails
    agb = os.path.join(tmp, "ann.gb")
    r = run_ok(script("annotate.py"), "ATGCATGCATGCATGCATGCGAATTC",
               "--min-orf", "12", "--enzyme", "EcoRI", "--out-gb", agb, "--json")
    _env = json.loads(r.stdout)
    d = _env.get("data", _env)
    check("annotate EcoRI found",
          any("error" not in h and h.get("enzyme") == "EcoRI" for h in d["enzyme_hits"]),
          str(d["enzyme_hits"]))
    rec3 = next(SeqIO.parse(agb, "genbank"))
    check("annotate gb re-reads", len(rec3.seq) > 0)
    check("annotate writes enzyme site into GenBank features",
          any("EcoRI" in str(f.qualifiers.get("label", [])) for f in rec3.features),
          str([f.qualifiers.get("label") for f in rec3.features]))

    # P0: reverse-strand ORF translation uses reverse complement
    r = run_ok(script("annotate.py"), "TTATTTCAT", "--min-orf", "3",
               "--both-strands", "--json")
    _env = json.loads(r.stdout)
    d = _env.get("data", _env)
    reverse_orfs = [f for f in d["features"] if f["strand"] == -1]
    check("reverse ORF translates to MK*",
          reverse_orfs and reverse_orfs[0]["translation"] == "MK*",
          str(reverse_orfs))

    # --- round 3: primer QC + golden gate ---
    # design_primers reports quality block in JSON
    r = run_ok(script("design_primers.py"),
               "ATGCATGCATGCATGCATGCATGCATGCATGCATGCATGCATGC",
               "--start", "1", "--end", "42", "--json", "--consent", "auto")
    _env = json.loads(r.stdout)
    d = _env.get("data", _env)
    check("design_primers includes quality report", "quality" in d, str(list(d.keys())))
    check("quality has risk_flags list",
          "risk_flags" in d.get("quality", {}), str(d.get("quality")))

    # golden_gate: synthetic BsaI parts with correct GGTCTC(1/5) cut geometry.
    # Each insert is GGTCTC + tail + left-overhang + body + right-overhang + tail + GAGACC;
    # the vector is a reverse-first destination backbone so both recognition sites
    # leave with the discarded stuffer fragment.
    ga = os.path.join(tmp, "gg_a.fa")
    gb = os.path.join(tmp, "gg_b.fa")
    gv = os.path.join(tmp, "gg_vec.fa")
    ins_a_seq = "GGTCTC" + "A" + "GGGG" + "AAAA" + "CCCC" + "T" + "GAGACC" + "TTTT"
    ins_b_seq = "GGTCTC" + "A" + "CCCC" + "GGGG" + "TTTT" + "T" + "GAGACC" + "TTTT"
    vec_seq = "GGGG" + "A" + "GAGACC" + "CCCCCCCC" + "GGTCTC" + "A" + "TTTT" + "ACGTACGT"
    with open(ga, "w") as fh:
        fh.write(">ggA\n%s\n" % ins_a_seq)
    with open(gb, "w") as fh:
        fh.write(">ggB\n%s\n" % ins_b_seq)
    with open(gv, "w") as fh:
        fh.write(">ggVec\n%s\n" % vec_seq)
    r = run_ok(script("golden_gate.py"), "--parts", gv, ga, gb, "--enzyme", "BsaI",
               "--vector-topology", "circular", "--json")
    _env = json.loads(r.stdout)
    d = _env.get("data", _env)
    check("golden_gate junctions reported", len(d["junctions"]) == 3, str(d["junctions"]))
    check("golden_gate all junctions compatible (including closing junction)",
          all(j["compatibility"] == "ok" for j in d["junctions"]), str(d["junctions"]))
    check("golden_gate uses 0-based cut boundaries 7/11",
          d["parts"][0]["recognition_sites"][0]["top_cut_boundary_0based"] in (0, 26)
          and d["parts"][1]["recognition_sites"][0]["top_cut_boundary_0based"] == 7
          and d["parts"][1]["recognition_sites"][0]["bottom_cut_boundary_0based"] == 11,
          str(d["parts"]))
    check("golden_gate product sequence is recognition-site free and assembled",
          d["product_sequence"] == "TTTTACGTACGT" + "GGGGAAAA" + "CCCCGGGG"
          and "GGTCTC" not in d["product_sequence"]
          and "GAGACC" not in d["product_sequence"],
          d["product_sequence"])
    check("golden_gate product topology is circular",
          d["topology"] == "circular", str(d))
    check("golden_gate reports excised fragment overhangs",
          d["parts"][1]["left_overhang"] == "GGGG"
          and d["parts"][1]["right_overhang"] == "CCCC"
          and d["parts"][0]["left_overhang"] == "TTTT"
          and d["parts"][0]["right_overhang"] == "GGGG",
          str(d["parts"]))
    check("golden_gate is explicitly experimental",
          d["experimental"] is True and any("EXPERIMENTAL" in n for n in d["notes"]),
          str(d))

    # Release blocker: an unannotated FASTA vector is linear, so wrap-around
    # backbone extraction must be rejected, not silently joined end+start.
    r = run(script("golden_gate.py"), "--parts", gv, ga, gb, "--enzyme", "BsaI", "--json")
    check("golden_gate rejects wrap-around backbone for a linear vector",
          r.returncode != 0 and "circular destination vector" in (r.stderr + r.stdout),
          (r.stderr + r.stdout)[-300:])

    # Release blocker: an invalid insert aborts with non-zero and writes no product.
    gc = os.path.join(tmp, "gg_c.fa")
    with open(gc, "w") as fh:
        fh.write(">ggC\nGGTCTCAAAAATGATGGTCTC\n")
    gg_bad_out = os.path.join(tmp, "gg_bad_product.gb")
    r = run(script("golden_gate.py"), "--parts", gv, gc, "--enzyme", "BsaI",
            "--vector-topology", "circular", "--out", gg_bad_out, "--json")
    check("golden_gate aborts on insert whose cuts leave the sequence",
          r.returncode != 0 and "assembly aborted" in (r.stderr + r.stdout),
          (r.stderr + r.stdout)[-400:])
    check("golden_gate does not write a product when aborted",
          not os.path.exists(gg_bad_out), gg_bad_out)

    # Release blocker: an overhang mismatch aborts with non-zero and writes nothing.
    gm = os.path.join(tmp, "gg_mismatch.fa")
    with open(gm, "w") as fh:
        fh.write(">ggM\n%s\n" % ("GGTCTC" + "A" + "TTTT" + "AAAA" + "CCCC" + "T" + "GAGACC" + "TTTT"))
    gg_mm_out = os.path.join(tmp, "gg_mismatch_product.gb")
    r = run(script("golden_gate.py"), "--parts", gv, gm, "--enzyme", "BsaI",
            "--vector-topology", "circular", "--out", gg_mm_out, "--json")
    check("golden_gate aborts on overhang mismatch",
          r.returncode != 0 and "overhang mismatch" in (r.stderr + r.stdout),
          (r.stderr + r.stdout)[-400:])
    check("golden_gate does not write a product on overhang mismatch",
          not os.path.exists(gg_mm_out), gg_mm_out)

    inf_a = os.path.join(tmp, "inf_a.fa")
    inf_b = os.path.join(tmp, "inf_b.fa")
    with open(inf_a, "w") as fh:
        fh.write(">infA\nAAAACCCC\n")
    with open(inf_b, "w") as fh:
        fh.write(">infB\nCCCCGGGG\n")
    r = run_ok(script("simulate_advanced.py"), "--method", "infusion",
               "--parts", inf_a, inf_b, "--overlap", "4", "--json")
    _env = json.loads(r.stdout)
    d = _env.get("data", _env)
    check("advanced cloning is explicitly experimental",
          d["experimental"] is True and any("EXPERIMENTAL" in n for n in d["notes"]),
          str(d))

    # In-Fusion/Gibson: mismatched overlap must fail, never warn-and-concatenate.
    bad_gib_a = os.path.join(tmp, "gib_bad_a.fa")
    bad_gib_b = os.path.join(tmp, "gib_bad_b.fa")
    with open(bad_gib_a, "w") as fh:
        fh.write(">ga\nAAAAAACCCC\n")
    with open(bad_gib_b, "w") as fh:
        fh.write(">gb\nGGGGTTTTTT\n")
    bad_gib_out = os.path.join(tmp, "gib_bad.gb")
    r = run(script("simulate_cloning.py"), "--method", "gibson",
            "--parts", bad_gib_a, bad_gib_b, "--overlap", "4",
            "--out", bad_gib_out, "--json")
    err = json.loads(r.stdout)
    check("gibson mismatch returns ok:false JSON with OVERLAP_MISMATCH",
          r.returncode != 0 and err.get("ok") is False
          and err["error"]["code"] == "OVERLAP_MISMATCH", str(err))
    check("gibson mismatch writes no product", not os.path.exists(bad_gib_out), bad_gib_out)
    r = run(script("simulate_advanced.py"), "--method", "infusion",
            "--parts", bad_gib_a, bad_gib_b, "--overlap", "4", "--json")
    err = json.loads(r.stdout)
    check("infusion mismatch fails with OVERLAP_MISMATCH",
          r.returncode != 0 and err.get("ok") is False
          and err["error"]["code"] == "OVERLAP_MISMATCH", str(err))

    # ta/topo use explicit premises: vector cut, vector 3'-T, insert 3'-A.
    ta_vec = os.path.join(tmp, "ta_vec.fa")
    ta_ins = os.path.join(tmp, "ta_ins.fa")
    ta_bad_ins = os.path.join(tmp, "ta_bad_ins.fa")
    with open(ta_vec, "w") as fh:
        fh.write(">taVec\nCCCCGGGG\n")
    with open(ta_ins, "w") as fh:
        fh.write(">taIns\nATGA\n")
    with open(ta_bad_ins, "w") as fh:
        fh.write(">taBadIns\nATGC\n")
    r = run(script("simulate_advanced.py"), "--method", "ta",
            "--vector", ta_vec, "--insert", ta_ins,
            "--vector-end", "t-tailed", "--insert-end", "a-tailed", "--json")
    err = json.loads(r.stdout)
    check("ta without --vector-cut fails with MISSING_VECTOR_CUT",
          r.returncode != 0 and err.get("ok") is False
          and err["error"]["code"] == "MISSING_VECTOR_CUT", str(err))
    r = run(script("simulate_advanced.py"), "--method", "ta",
            "--vector", ta_vec, "--insert", ta_ins, "--vector-cut", "4", "--json")
    err = json.loads(r.stdout)
    check("ta without explicit end premises fails with END_TYPE_MISMATCH",
          r.returncode != 0 and err["error"]["code"] == "END_TYPE_MISMATCH", str(err))
    r = run_ok(script("simulate_advanced.py"), "--method", "ta",
               "--vector", ta_vec, "--insert", ta_bad_ins, "--vector-cut", "4",
               "--vector-end", "t-tailed", "--insert-end", "a-tailed", "--json")
    _env = json.loads(r.stdout)
    d = _env.get("data", _env)
    check("ta accepts declared 3'-A premise without endswith inference",
          d["product_sequence"] == "CCCCATGCGGGG" and d["topology"] == "circular",
          str(d))
    r = run_ok(script("simulate_advanced.py"), "--method", "topo",
               "--vector", ta_vec, "--insert", ta_bad_ins, "--vector-cut", "4",
               "--vector-end", "t-tailed", "--insert-end", "a-tailed", "--json")
    _env = json.loads(r.stdout)
    d = _env.get("data", _env)
    check("topo uses the same explicit premise model", d["product_sequence"] == "CCCCATGCGGGG",
          str(d))

    # Gateway LR: attL entry x attR destination -> attB expression clone.
    attl_entry = os.path.join(tmp, "attl_entry.gb")
    attr_dest = os.path.join(tmp, "attr_dest.gb")
    _entry_rec = SeqRecord(
        Seq(simadv.ATTL1 + "GGGAAA" + str(Seq(simadv.ATTL2).reverse_complement())),
        id="attL-entry", name="attL-entry",
        annotations={"molecule_type": "DNA", "topology": "circular"})
    _dest_rec = SeqRecord(
        Seq("CCCC" + simadv.ATTR1 + "TTTT" + str(Seq(simadv.ATTR2).reverse_complement()) + "GGGG"),
        id="attR-dest", name="attR-dest",
        annotations={"molecule_type": "DNA", "topology": "circular"})
    with open(attl_entry, "w") as fh:
        SeqIO.write(_entry_rec, fh, "genbank")
    with open(attr_dest, "w") as fh:
        SeqIO.write(_dest_rec, fh, "genbank")
    r = run_ok(script("simulate_advanced.py"), "--method", "gateway-lr",
               "--entry", attl_entry, "--destination", attr_dest, "--json")
    _env = json.loads(r.stdout)
    d = _env.get("data", _env)
    check("gateway-lr replaces attR cassette with attB1/attB2",
          d["product_sequence"] == (
              "CCCC" + simadv.ATTB1 + "GGGAAA"
              + str(Seq(simadv.ATTB2).reverse_complement()) + "GGGG"),
          d["product_sequence"])
    bad_entry = os.path.join(tmp, "bad_entry.gb")
    _bad_entry_rec = SeqRecord(Seq("AAAACCCCGGGG"), id="badEntry", name="badEntry",
                               annotations={"molecule_type": "DNA", "topology": "circular"})
    with open(bad_entry, "w") as fh:
        SeqIO.write(_bad_entry_rec, fh, "genbank")
    r = run(script("simulate_advanced.py"), "--method", "gateway-lr",
            "--entry", bad_entry, "--destination", attr_dest, "--json")
    err = json.loads(r.stdout)
    check("gateway-lr missing attL sites fails with ATT_SITE_MISSING",
          r.returncode != 0 and err.get("ok") is False
          and err["error"]["code"] == "ATT_SITE_MISSING", str(err))

    r = run_ok(script("methylation.py"), "ATCGAT", "--enzyme", "ClaI", "--json")
    _env = json.loads(r.stdout)
    d = _env.get("data", _env)
    check("methylation does not invent dam/dcm sensitivity",
          d["experimental"] is True
          and d["enzymes"][0]["sensitivity"]["dam"] is None
          and d["enzymes"][0]["blocked_sites"] == [],
          str(d))

    # --- round 4: alignment, PCR, gel, mutagenesis, codon, protein, convert, map ---
    # align_seq
    r = run_ok(script("align_seq.py"), "ATGCATGCATGC", "ATGCTTGCATGC", "--json")
    _env = json.loads(r.stdout)
    d = _env.get("data", _env)
    check("align_seq detects 1 mismatch", d["mismatches"] == 1, str(d))

    r = run_ok(script("align_seq.py"), "CATGC", "AAAACATGCGGGG", "--mode", "local", "--json")
    _env = json.loads(r.stdout)
    d = _env.get("data", _env)
    check("align_seq local finds subread", d["matches"] >= 5, str(d))

    r = run_ok(script("align_seq.py"), "GGGACGT", "TTTACGT", "--mode", "local", "--json")
    _env = json.loads(r.stdout)
    d = _env.get("data", _env)
    check("local alignment stops at zero without crashing",
          d["alignment"]["query"] == "ACGT" and d["local_start_query"] == 4,
          str(d))

    # align_sanger
    ref_fa = os.path.join(tmp, "ref.fa")
    with open(ref_fa, "w") as fh:
        fh.write(">ref\nATGCATGCATGCATGCATGCATGCATGCATGC\n")
    read_fa = os.path.join(tmp, "read.fa")
    with open(read_fa, "w") as fh:
        fh.write(">read1\nATGCATGCATGCATGCATGC\n")
    r = run_ok(script("align_sanger.py"), ref_fa, "--reads", read_fa, "--json")
    _env = json.loads(r.stdout)
    d = _env.get("data", _env)
    check("align_sanger confirms read", d["reads"][0]["identity"] >= 90, str(d))

    # Keep the repeated-template failure; its multiple products are not a success.
    r = run(script("simulate_pcr.py"), ref_fa,
            "--fwd", "ATGCATGCAT", "--rev", "GCATGCATGC", "--json")
    d = json.loads(r.stdout)["data"]
    check("simulate_pcr rejects ambiguous products",
          r.returncode != 0 and d["length"] == 0 and any("ambiguity" in n for n in d["notes"]), str(d))

    unique = "ACGTCAGGCTTACCGTAGCTCGATGCCATGTTCAGGACTACCGTATGACCTGA"
    from Bio.Seq import Seq
    r = run_ok(script("simulate_pcr.py"), unique,
               "--fwd", unique[:18], "--rev", str(Seq(unique[-18:]).reverse_complement()), "--json")
    d = json.loads(r.stdout)["data"]
    check("simulate_pcr reproduces the independently specified unique product", d["amplicon"] == unique, str(d))

    r = run(script("simulate_pcr.py"), "AAAACCCCGGGGTTTT",
            "--fwd", "GGGG", "--rev", "GGGG", "--json")
    envelope = json.loads(r.stdout)
    d = envelope["data"]
    check("simulate_pcr rejects outward/upstream primer pair",
          r.returncode != 0 and not envelope["ok"] and d["length"] == 0, str(d))

    # simulate_gel
    r = run_ok(script("simulate_gel.py"), "--fragments", "1000,500,200", "--json")
    _env = json.loads(r.stdout)
    d = _env.get("data", _env)
    check("simulate_gel smaller migrates further",
          d["fragments"][0]["migration"] < d["fragments"][2]["migration"], str(d))

    # mutagenesis
    r = run_ok(script("mutagenesis.py"), ref_fa, "--op", "point",
               "--mutation", "1:T", "--json")
    _env = json.loads(r.stdout)
    d = _env.get("data", _env)
    check("mutagenesis point mutation", d["sequence"][0] == "T", str(d))

    r = run_ok(script("mutagenesis.py"), "ATGCCC", "--op", "insert-codon",
               "--pos", "4", "--codon", "AAA", "--json")
    _env = json.loads(r.stdout)
    d = _env.get("data", _env)
    check("mutagenesis insert-codon validates and inserts",
          d["sequence"] == "ATGAAACCC" and d["length_after"] == 9, str(d))

    r = run(script("mutagenesis.py"), "ATGCCC", "--op", "delete-codon",
            "--start", "1", "--end", "2", "--json")
    check("mutagenesis delete-codon rejects non-codon span",
          r.returncode != 0 and "multiple of 3" in (r.stderr + r.stdout),
          (r.stderr + r.stdout)[-200:])

    r = run(script("mutagenesis.py"), "ATGCCC", "--op", "delete-codon",
            "--start", "2", "--end", "4", "--json")
    check("mutagenesis delete-codon rejects off-frame start",
          r.returncode != 0 and "not on a codon boundary" in (r.stderr + r.stdout),
          (r.stderr + r.stdout)[-200:])

    r = run(script("mutagenesis.py"), "ATGCCC", "--op", "overlap-pcr",
            "--fwd-outer", "ATG", "--rev-outer", "GGG",
            "--fwd-inner", "CCC", "--rev-inner", "CAT", "--json")
    check("mutagenesis overlap-pcr fails loudly instead of returning template",
          r.returncode != 0 and "not implemented" in (r.stderr + r.stdout),
          (r.stderr + r.stdout)[-200:])

    # codon_optimize
    r = run_ok(script("codon_optimize.py"), "MALTW", "--host", "ecoli", "--json")
    _env = json.loads(r.stdout)
    d = _env.get("data", _env)
    check("codon_optimize back-translate", d["optimized_dna"] == "ATGGCGCTGACCTGG",
          d["optimized_dna"])

    r = run_ok(script("codon_optimize.py"), "ATGGGATAA", "--host", "ecoli", "--json")
    _env = json.loads(r.stdout)
    d = _env.get("data", _env)
    check("codon_optimize auto-detects DNA input",
          d["mode"] == "dna" and d["optimized_dna"] == "ATGGGCTAA", str(d))
    check("codon_optimize preserves terminal stop codon",
          d["optimized_protein"] == "MG*" and d["optimized_dna"].endswith("TAA"),
          str(d))

    missing_protein = os.path.join(tmp, "missing-protein.fa")
    r = run(script("codon_optimize.py"), missing_protein, "--mode", "protein", "--json")
    check("codon_optimize missing protein file is an error, not a protein string",
          r.returncode != 0 and "not found" in (r.stderr + r.stdout),
          (r.stderr + r.stdout)[-200:])

    multi_fa = os.path.join(tmp, "multi-protein.fa")
    with open(multi_fa, "w") as fh:
        fh.write(">p1\nMALTW\n>p2\nMALTW\n")
    r = run(script("codon_optimize.py"), multi_fa, "--mode", "protein", "--json")
    check("codon_optimize multi-record FASTA is rejected",
          r.returncode != 0 and "exactly one record" in (r.stderr + r.stdout),
          (r.stderr + r.stdout)[-200:])

    # protein_tools
    r = run_ok(script("protein_tools.py"), "reverse-translate", "MALTW", "--json")
    _env = json.loads(r.stdout)
    d = _env.get("data", _env)
    check("protein_tools reverse-translate", "ATG" in d["degenerate_dna"], str(d))
    r = run_ok(script("protein_tools.py"), "reverse-translate", "LR*", "--json")
    _env = json.loads(r.stdout)
    d = _env.get("data", _env)
    check("degenerate codons do not include off-target amino acids",
          d["degenerate_dna"] == "CTNCGNTAR", d["degenerate_dna"])
    r = run_ok(script("protein_tools.py"), "anneal", "GCATGCATGCATGC",
               "--bottom", "GCATGCATGCATGC", "--json")
    _env = json.loads(r.stdout)
    d = _env.get("data", _env)
    check("protein_tools anneal", d["length"] >= 4, str(d))

    print("\n===== %d passed, %d failed =====" % (len(PASS), len(FAIL)))
    return 1 if FAIL else 0



if __name__ == "__main__":
    sys.exit(main())
