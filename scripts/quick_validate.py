# -*- coding: utf-8 -*-
"""quick_validate.py - Minimal deterministic release smoke gate.

This script only re-executes existing public tools on a small synthetic
sequence; it adds no new molecular-biology algorithm and does not require
real backends.
"""
import argparse
import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def run(cmd, cwd=ROOT):
    return subprocess.run([str(x) for x in cmd], cwd=str(cwd),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    results = []
    with tempfile.TemporaryDirectory(prefix="quick-validate-") as td:
        td = pathlib.Path(td)
        fasta = td / "seq.fa"
        seq = "GAATTC" + "ACGT" * 20 + "GGATCC"
        fasta.write_text(">s\n%s\n" % seq, encoding="utf-8")
        commands = [
            ("analyze_seq", ["analyze_seq.py", str(fasta), "stats", "--json"]),
            ("find_sites", ["find_sites.py", str(fasta), "--enzyme",
                            "EcoRI,BamHI", "--json"]),
            ("write_dna", ["write_dna.py", seq, "--out",
                           str(td / "seq.gb"), "--format", "snapgene-gb"]),
            ("validate_construct", ["validate_construct.py",
                                    str(td / "seq.gb"), "--json"]),
        ]
        for name, cmd in commands:
            completed = run([sys.executable, "-X", "utf8", "-B",
                             str(SCRIPTS / cmd[0]), *cmd[1:]])
            results.append({
                "name": name, "returncode": completed.returncode,
                "stdout_tail": (completed.stdout or "")[-500:],
                "stderr_tail": (completed.stderr or "")[-500:],
            })
    ok = all(item["returncode"] == 0 for item in results)
    report = {"schema_version": "0.9.0", "ok": ok, "results": results}
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for item in results:
            print("%s=%s" % (item["name"], item["returncode"]))
        print("quick_validate: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
