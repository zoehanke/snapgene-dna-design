# -*- coding: utf-8 -*-
"""mutation_tests.py - Mutation testing for the v0.5 formal-release gate.

The release gate requires a mutation-test kill rate >= 90% across the 12
specified mutations below. Each mutation is a deliberate source-level change
that must be caught by the behavior checks (a "kill"). A mutant that still
passes its behavior check is a "survivor" and lowers the kill rate; the aggregate gate uses the stated 90% threshold.

Method
------
For every mutant the scripts and their project runtime dependencies are copied to a fresh temporary
directory, the mutation is applied to the copy, and a dedicated check process
(running against the mutated copy) verifies the required behavior. The same
check must pass against a pristine copy; if it does not, the check itself is
broken and is reported as an error, never as a kill.

Usage::

    python -X utf8 tools/mutation_tests.py            # run all 12 + enforce
    python -X utf8 tools/mutation_tests.py --json     # JSON report
    python -X utf8 tools/mutation_tests.py --no-enforce

Exit code 0 only when every check is valid, the pristine checks pass, and the
kill rate >= 90% (ceil). Reports are written to ``reports/mutation/``.
"""

from project_paths import PROJECT_ROOT as REPOSITORY_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS, TESTS_ROOT
import argparse
import json
import math
import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
ROOT = SKILL_ROOT
SCRIPTS = RUNTIME_SCRIPTS
REPORT_ROOT = ROOT / "reports" / "mutation"

MIN_KILL_RATE = 90.0

# --------------------------------------------------------------------------
# The 12 specified mutations. `old` must match exactly once in the pristine
# source; `new` is the mutated replacement. `check` names the function in
# CHECK_CODE that returns True when the required behavior holds.
# --------------------------------------------------------------------------
MUTATIONS = [
    {
        "id": "M01",
        "title": "zero-contribution fragment check removed",
        "file": "core/models/assembly_model.py",
        "old": "        if contribution <= 0:",
        "new": "        if contribution < 0:",
        "check": "check_m01_zero_contribution",
    },
    {
        "id": "M02",
        "title": "Gibson overlap mismatch check removed",
        "file": "core/models/assembly_model.py",
        "old": "    if left != right:",
        "new": "    if left != right and False:",
        "check": "check_m02_overlap_mismatch",
    },
    {
        "id": "M03",
        "title": "circular closing overlap no longer trimmed",
        "file": "core/models/assembly_model.py",
        "old": "        return \"\".join(fragment.sequence[overlap_length:] for fragment in fragments)",
        "new": "        return \"\".join(fragment.sequence for fragment in fragments)",
        "check": "check_m03_circular_trim",
    },
    {
        "id": "M04",
        "title": "sticky ends always compatible",
        "file": "core/models/assembly_model.py",
        "old": "    return _complement(left.overhang_sequence) == right.overhang_sequence",
        "new": "    return True",
        "check": "check_m04_sticky_compat",
    },
    {
        "id": "M05",
        "title": "CompoundLocation parts globally sorted by start",
        "file": "scripts/simulate_cloning.py",
        "old": "    if len(parts) == 1:\n        return parts[0]\n    if operator != \"join\":",
        "new": "    if len(parts) == 1:\n        return parts[0]\n    parts = sorted(parts, key=lambda p: int(p.start))\n    if operator != \"join\":",
        "check": "check_m05_compound_order",
    },
    {
        "id": "M06",
        "title": "feature extract() consistency check removed",
        "file": "scripts/simulate_cloning.py",
        "old": "        if migrated_extract != source_extract:",
        "new": "        if migrated_extract != source_extract and False:",
        "check": "check_m06_extract_check",
    },
    {
        "id": "M07",
        "title": "origin coordinate invariants disabled",
        "file": "core/models/assembly_model.py",
        "old": "    if sum(int(origin[\"length\"]) for origin in origins) != product_length:",
        "new": "    if sum(int(origin[\"length\"]) for origin in origins) != product_length and False:",
        "check": "check_m07_origins",
    },
    {
        "id": "M08",
        "title": "Golden Gate accepts fragments containing recognition sites",
        "file": "core/tools/assembly.py",
        "old": "            if _contains_recognition_site(fragment, enzyme):",
        "new": "            if False and _contains_recognition_site(fragment, enzyme):",
        "check": "check_m08_gg_recognition",
    },
    {
        "id": "M09",
        "title": "Golden Gate overhang mismatch tolerated",
        "file": "scripts/golden_gate.py",
        "old": "    if mismatches:\n        jfail(",
        "new": "    if False and mismatches:\n        jfail(",
        "check": "check_m09_gg_mismatch",
    },
    {
        "id": "M10",
        "title": "Gateway att-site uniqueness check removed",
        "file": "core/tools/recombination.py",
        "old": "    if len(left_good) != 1 or len(right_good) != 1:",
        "new": "    if False and (len(left_good) != 1 or len(right_good) != 1):",
        "check": "check_m10_att_unique",
    },
    {
        "id": "M11",
        "title": "failure envelope reports ok:true",
        "file": "scripts/sg_common.py",
        "old": "        \"ok\": False,\n        \"command\": os.path.basename(sys.argv[0]),",
        "new": "        \"ok\": True,\n        \"command\": os.path.basename(sys.argv[0]),",
        "check": "check_m11_failure_envelope",
    },
    {
        "id": "M12",
        "title": "ConstructModel.insert boundary off-by-one",
        "file": "core/models/construct_model.py",
        "old": "            new_start = start0 + (delta if start0 >= pos0 else 0)",
        "new": "            new_start = start0 + (delta if start0 > pos0 else 0)",
        "check": "check_m12_insert_boundary",
    },
]

# --------------------------------------------------------------------------
# Behavior checks. Each returns True iff the required behavior holds.
# They run in a fresh process against a (possibly mutated) scripts/ copy.
# --------------------------------------------------------------------------
CHECK_CODE = r'''
# -*- coding: utf-8 -*-
"""Behavior checks for the 12 specified mutations (fresh-process execution)."""
import argparse
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "scripts"))

from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

import assembly_model
import construct_model
import golden_gate
import sg_common
import simulate_advanced
import simulate_cloning
from assembly_model import AssemblyError, check_sticky_junctions, overhang_end
from construct_model import ConstructModel


def _record(sequence, name, circular=False, features=()):
    rec = SeqRecord(Seq(sequence), id=name, name=name)
    rec.annotations = {"molecule_type": "DNA",
                       "topology": "circular" if circular else "linear"}
    for feature in features:
        rec.features.append(feature)
    return rec


def _label_feature(start, end, label, strand=1):
    return SeqFeature(FeatureLocation(start, end, strand=strand),
                      type="misc_feature",
                      qualifiers={"label": [label]})


def check_m01_zero_contribution():
    a = _record("AAAA", "a")
    b = _record("AAAA", "b")
    try:
        simulate_cloning.gibson([a, b], overlap=4, circular=True)
        return False
    except AssemblyError as error:
        return error.code == "ZERO_CONTRIBUTION_FRAGMENT"


def check_m02_overlap_mismatch():
    a = _record("AAAACCCC", "a")
    b = _record("GGGGAAAA", "b")
    try:
        simulate_cloning.gibson([a, b], overlap=4, circular=False)
        return False
    except AssemblyError as error:
        return error.code == "OVERLAP_MISMATCH"


def check_m03_circular_trim():
    ov1 = "ACGT" * 3
    ov2 = "TGCA" * 3
    ov3 = "GATC" * 3
    parts = [
        _record(ov3 + "AAAA" + ov1, "a", circular=True),
        _record(ov1 + "CCCC" + ov2, "b", circular=True),
        _record(ov2 + "GGGG" + ov3, "c", circular=True),
    ]
    product, _fragments, _contributions, _warnings = simulate_cloning.gibson(
        parts, overlap=12, circular=True)
    return str(product.seq) == "AAAA" + ov1 + "CCCC" + ov2 + "GGGG" + ov3


def check_m04_sticky_compat():
    vector = assembly_model.AssemblyFragment(
        "v", "AAAACCCC",
        left_end=overhang_end("5'-overhang", "AACC", 0),
        right_end=overhang_end("5'-overhang", "TTGG", 4))
    insert = assembly_model.AssemblyFragment(
        "i", "GGGGTTTT",
        left_end=overhang_end("5'-overhang", "CCCC", 0),
        right_end=overhang_end("5'-overhang", "AAAA", 4))
    junctions = check_sticky_junctions([vector, insert], circular=True)
    return all(j["compatibility"] == "MISMATCH" for j in junctions)


def check_m05_compound_order():
    ov1 = "ACGT" * 3
    ov2 = "TGCA" * 3
    ov3 = "GATC" * 3
    a = _record(ov3 + "AAAA" + ov1, "wrapA", circular=True,
                features=[_label_feature(0, 16, "wrapA_feat")])
    b = _record(ov1 + "CCCC" + ov2, "wrapB", circular=True)
    c = _record(ov2 + "GGGG" + ov3, "wrapC", circular=True)
    try:
        product, _f, _c, _w = simulate_cloning.gibson(
            [a, b, c], overlap=12, circular=True)
    except AssemblyError:
        return False
    feature = next(f for f in product.features
                   if "wrapA_feat" in f.qualifiers.get("label", []))
    parts = [(int(p.start), int(p.end), int(p.strand))
             for p in feature.location.parts]
    return parts == [(36, 48, 1), (0, 4, 1)]


def check_m06_extract_check():
    from unittest import mock
    ov = "ACGT" * 3
    a = _record(ov + "AAAA" + ov, "a", circular=True,
                features=[_label_feature(0, 16, "f")])
    b = _record(ov + "CCCC" + ov, "b", circular=True)

    def bad(part, trim_start, clip_end, offset, circular, is_first, product_length):
        return [FeatureLocation(0, 1, strand=part.strand)], False

    with mock.patch("simulate_cloning._mapped_part_segments", bad):
        try:
            simulate_cloning.gibson([a, b], overlap=12, circular=True)
            return False
        except AssemblyError as error:
            return error.code == "FEATURE_MIGRATION_MISMATCH"


def check_m07_origins():
    bad = [{"name": "x", "length": 5, "start": 1, "end": 5,
            "contribution_segments": [], "source_mappings": []}]
    try:
        assembly_model.validate_origins(bad, 8)
        return False
    except AssemblyError as error:
        return error.code == "ORIGIN_LENGTH_MISMATCH"


def check_m08_gg_recognition():
    # Two BsaI sites where the only internal fragment still contains a site:
    # the linear part must be rejected, never excised.
    seq = "GGTCTC" + "A" * 30 + "GGTCTC" + "A" * 30 + "GGTCTC"
    rec = _record(seq, "badpart", circular=False)
    enzyme = sg_common.get_enzyme("BsaI")
    info = golden_gate.part_fragment(rec, enzyme)
    return info["ok"] is False


def check_m09_gg_mismatch():
    from unittest import mock
    # Valid BsaI parts whose excised fragments would produce mismatched
    # junctions; the mismatch guard is what must abort the assembly.
    vector = _record(
        "GGTCTC" + "A" + "AAAA" + "A" * 40 + "TTTT" + "A" + "GAGACC",
        "v", circular=True)
    insert = _record(
        "GGTCTC" + "A" + "CCCC" + "A" * 40 + "GGGG" + "A" + "GAGACC",
        "i", circular=False)
    enzyme = sg_common.get_enzyme("BsaI")
    fake_junctions = [{
        "between": "v->i",
        "left": {"overhang_sequence": "TTTT"},
        "right": {"overhang_sequence": "CCCC"},
        "compatibility": "MISMATCH", "junction": "TTTT/CCCC",
    }]
    with mock.patch("golden_gate.check_sticky_junctions",
                    return_value=fake_junctions):
        try:
            golden_gate.assemble([vector, insert], ["v", "i"], enzyme,
                                 vector_idx=0, vector_topology="circular")
            return False
        except SystemExit as error:
            return error.code == 1


def check_m10_att_unique():
    donor = _record(
        simulate_advanced.ATTP1 + "A" * 20
        + str(Seq(simulate_advanced.ATTP2).reverse_complement()),
        "donor", circular=True)
    dup_insert = _record(
        "AAA" + simulate_advanced.ATTB1 + "CCCC" + simulate_advanced.ATTB1
        + "GGGG" + simulate_advanced.ATTB2 + "TTT",
        "dup", circular=False)
    try:
        simulate_advanced.gateway_bp(donor, dup_insert)
        return False
    except AssemblyError as error:
        return error.code == "ATT_SITE_NOT_UNIQUE"


def check_m11_failure_envelope():
    import os
    import subprocess
    scripts = pathlib.Path(__file__).resolve().parent / "scripts"
    tmp = pathlib.Path(os.environ.get("TMPDIR", os.environ.get("TEMP", ".")))
    work = pathlib.Path(tmp) / "m11-input"
    work.mkdir(parents=True, exist_ok=True)
    a = work / "a.fa"
    b = work / "b.fa"
    a.write_text(">a\nAAAA\n", encoding="utf-8")
    b.write_text(">b\nAAAA\n", encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(scripts / "simulate_cloning.py"),
         "--method", "gibson", "--parts", str(a), str(b),
         "--overlap", "4", "--topology", "circular", "--json"],
        cwd=str(scripts), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=180)
    if completed.returncode == 0:
        return False
    try:
        payload = json.loads(completed.stdout)
    except ValueError:
        return False
    return payload.get("ok") is False and payload.get("data") is None


def check_m12_insert_boundary():
    rec = _record("AAAACCCCGGGG", "t", circular=False,
                  features=[_label_feature(4, 6, "f")])
    out = ConstructModel(rec).insert(4, "TT").to_record()
    feature = next(f for f in out.features
                   if "f" in f.qualifiers.get("label", []))
    return (int(feature.location.start), int(feature.location.end)) == (6, 8)


CHECKS = {
    "check_m01_zero_contribution": check_m01_zero_contribution,
    "check_m02_overlap_mismatch": check_m02_overlap_mismatch,
    "check_m03_circular_trim": check_m03_circular_trim,
    "check_m04_sticky_compat": check_m04_sticky_compat,
    "check_m05_compound_order": check_m05_compound_order,
    "check_m06_extract_check": check_m06_extract_check,
    "check_m07_origins": check_m07_origins,
    "check_m08_gg_recognition": check_m08_gg_recognition,
    "check_m09_gg_mismatch": check_m09_gg_mismatch,
    "check_m10_att_unique": check_m10_att_unique,
    "check_m11_failure_envelope": check_m11_failure_envelope,
    "check_m12_insert_boundary": check_m12_insert_boundary,
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", help="run a single check by id (debug)")
    args = parser.parse_args()
    # The result is written to a file (not stdout) so that scripts which print
    # JSON envelopes during a check (e.g. jfail) cannot corrupt the parsing.
    result_file = os.environ.get("MUTATION_RESULT_FILE")
    if args.check:
        fn = CHECKS[args.check]
        error = None
        try:
            result = bool(fn())
        except SystemExit:
            result = False
        except Exception as exc:  # noqa: BLE001 - a crashing check is a failure
            result = False
            error = "%r" % (exc,)
        payload = {"check": args.check, "behavior_correct": result,
                   "error": error}
    else:
        results = {}
        for name, fn in CHECKS.items():
            try:
                results[name] = bool(fn())
            except Exception as error:  # noqa: BLE001 - report, do not crash
                results[name] = "ERROR: %r" % (error,)
        payload = results
    if result_file:
        pathlib.Path(result_file).write_text(
            json.dumps(payload, indent=2), encoding="utf-8")
    else:
        print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''


def _run_check(check_name, scripts_dir, python):
    """Run one behavior check in a fresh process against scripts_dir."""
    check_path = scripts_dir.parent / "_mutation_checks.py"
    check_path.write_text(CHECK_CODE, encoding="utf-8")
    result_path = scripts_dir.parent / ("_result_%s.json" % check_name)
    if result_path.exists():
        result_path.unlink()
    env = dict(__import__("os").environ)
    env["MUTATION_RESULT_FILE"] = str(result_path)
    env["PYTHONPATH"] = str(scripts_dir.parent)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [python, str(check_path), "--check", check_name],
        cwd=str(scripts_dir.parent), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=180, env=env,
    )
    if result_path.exists():
        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
        except Exception as error:
            payload = {"parse_error": str(error)}
        result_path.unlink()
    else:
        payload = {"missing_result": True,
                   "stdout_tail": completed.stdout[-500:],
                   "stderr_tail": completed.stderr[-500:]}
    return completed, payload


def _apply_mutation(source, mutation):
    count = source.count(mutation["old"])
    if count != 1:
        raise ValueError(
            "mutation %s: anchor %r appears %d times in %s (expected 1)"
            % (mutation["id"], mutation["old"], count, mutation["file"]))
    return source.replace(mutation["old"], mutation["new"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-enforce", action="store_true")
    parser.add_argument("--out-dir", default=str(REPORT_ROOT))
    args = parser.parse_args(argv)

    python = sys.executable
    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    pristine_ok = True
    for mutation in MUTATIONS:
        with tempfile.TemporaryDirectory(prefix="mut-%s-" % mutation["id"]) as td:
            tree = pathlib.Path(td)
            scripts_copy = tree / "scripts"
            shutil.copytree(SCRIPTS, scripts_copy, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            for directory in ('core', 'evidence_trace', 'planning', 'design', 'rules', 'agent', 'schemas', 'parts', 'references'):
                shutil.copytree(ROOT / directory, tree / directory, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            shutil.copy2(ROOT / 'VERSION', tree / 'VERSION')

            # 1) pristine check must hold (validates the check itself).
            pristine, pristine_payload = _run_check(
                mutation["check"], scripts_copy, python)
            pristine_correct = pristine_payload.get("behavior_correct")
            if not pristine_correct:
                pristine_ok = False

            # 2) apply the mutation to the copy.
            target = tree / mutation["file"]
            try:
                mutated_source = _apply_mutation(target.read_text(encoding="utf-8"), mutation)
                target.write_text(mutated_source, encoding="utf-8")
            except (OSError, ValueError) as exc:
                results.append({'id': mutation['id'], 'title': mutation['title'], 'status': 'error', 'detail': str(exc)})
                pristine_ok = False
                continue

            # 3) behavior check against the mutant: kill = behavior broke.
            mutant, mutant_payload = _run_check(
                mutation["check"], scripts_copy, python)
            mutant_correct = mutant_payload.get("behavior_correct")

            if pristine_correct is None or mutant_correct is None:
                status = "error"
            elif not pristine_correct:
                status = "check-broken"
            elif mutant_correct:
                status = "survived"
            else:
                status = "killed"
            results.append({
                "id": mutation["id"],
                "title": mutation["title"],
                "file": mutation["file"],
                "status": status,
                "pristine_behavior_correct": pristine_correct,
                "mutant_behavior_correct": mutant_correct,
                "pristine_stderr": (pristine.stderr or "")[-400:],
                "mutant_stderr": (mutant.stderr or "")[-400:],
            })

    killed = sum(1 for r in results if r["status"] == "killed")
    survived = sum(1 for r in results if r["status"] == "survived")
    errors = sum(1 for r in results if r["status"] in ("error", "check-broken"))
    total = len(results)
    kill_rate = killed / total * 100 if total else 0.0
    required_kills = math.ceil(total * MIN_KILL_RATE / 100.0)
    gate_ok = (killed >= required_kills and errors == 0 and pristine_ok)

    report = {
        "gate": "mutation-tests",
        "min_kill_rate": MIN_KILL_RATE,
        "required_kills_of_%d" % total: required_kills,
        "total": total,
        "killed": killed,
        "survived": survived,
        "errors": errors,
        "kill_rate_percent": round(kill_rate, 2),
        "gate_ok": gate_ok,
        "mutations": results,
    }
    (out_dir / "mutation-gate.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))

    for result in results:
        print("%-6s %-22s %s" % (result["status"].upper(), result["id"],
                                 result["title"]))
    print("kill rate: %d/%d = %.2f%% (required >= %.0f%%, i.e. >= %d kills)"
          % (killed, total, kill_rate, MIN_KILL_RATE, required_kills))
    print("gate: %s" % ("PASS" if gate_ok else "FAIL"))
    if args.no_enforce:
        return 0
    return 0 if gate_ok else 1


if __name__ == "__main__":
    sys.exit(main())
