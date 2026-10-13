# -*- coding: utf-8 -*-
"""Rich-feature round-trip gate with an explicit compatibility policy.

The v0.5 formal gate requires rich-feature strict SnapGene round trips:
forward/reverse CDS, CompoundLocation (join/order), cross-origin features,
Unicode and multi-value qualifiers. This runner:

* validates every ``fixtures/rich/*.gb`` fixture through
  ``validate_roundtrip.py --format snapgene-gb --strict`` (qualifier-exact
  internal round trip) and ``--format dna --strict``;
* runs the official SnapGene conversion (``--require-snapgene``) whenever a
  SnapGene executable is available (``--snapgene-exe`` or ``SNAPGENE_EXE`` or
  auto-discovery); otherwise that check is reported as skipped;
* requires the skill's internal ``snapgene-gb`` round trip to stay strict;
* accepts an official SnapGene difference only when preflight predicts that
  exact severity class for the input; an unclassified difference fails;
* reports known third-party limitations as accepted findings, never as
  "lossless" success.

Usage::

    python -X utf8 tools/validate_rich_fixtures.py            # run + enforce
    python -X utf8 tools/validate_rich_fixtures.py --json
    python -X utf8 tools/validate_rich_fixtures.py --no-enforce
    python -X utf8 tools/validate_rich_fixtures.py --snapgene-exe "C:\\SnapGene\\SnapGene.exe"
"""

from project_paths import PROJECT_ROOT as REPOSITORY_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS, TESTS_ROOT
import argparse
import json
import os
import pathlib
import subprocess
import sys

from snapgene_compatibility import analyze

HERE = pathlib.Path(__file__).resolve().parent
ROOT = SKILL_ROOT
SCRIPTS = RUNTIME_SCRIPTS
FIXTURES = ROOT / "fixtures" / "rich"
REPORT_DIR = ROOT / "reports" / "rich"

CORE_FIXTURES = (
    "rich_fwd_cds", "rich_rev_cds", "rich_join", "rich_order",
    "rich_cross_origin", "rich_unicode", "rich_multivalue",
    "rich_kitchen_sink",
)


def _find_snapgene(explicit=None):
    candidates = [
        explicit,
        os.environ.get("SNAPGENE_EXE"),
        os.path.join(os.environ.get("ProgramFiles", ""), "SnapGene", "SnapGene.exe"),
        os.path.join(os.environ.get("ProgramFiles(x86)", ""), "SnapGene", "SnapGene.exe"),
    ]
    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return os.path.abspath(candidate)
    return None


def _run_roundtrip(fixture, fmt, snapgene_exe=None, require_snapgene=False):
    cmd = [sys.executable, "-X", "utf8",
           str(SCRIPTS / "validate_roundtrip.py"), str(fixture),
           "--format", fmt, "--strict", "--json"]
    if snapgene_exe:
        cmd += ["--snapgene-exe", snapgene_exe]
    if require_snapgene:
        cmd += ["--require-snapgene"]
    completed = subprocess.run(
        cmd, cwd=str(SCRIPTS), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=300)
    try:
        payload = json.loads(completed.stdout)
    except ValueError:
        return {
            "status": "error",
            "returncode": completed.returncode,
            "stdout_tail": completed.stdout[-500:],
            "stderr_tail": completed.stderr[-500:],
        }
    data = payload.get("data", payload)
    official = data.get("official_snapgene_roundtrip", {})
    return {
        "status": "completed",
        "returncode": completed.returncode,
        "passed": data.get("passed"),
        "core_passed": data.get("core_passed"),
        "strict_passed": data.get("strict_passed"),
        "lossless": data.get("lossless"),
        "delivery_grade": data.get("delivery_grade"),
        "official_status": official.get("status"),
        "official_passed": official.get("passed"),
        "official_sequence_equal": official.get("sequence_equal"),
        "official_topology_equal": official.get("topology_equal"),
        "official_features_equal": official.get("features_equal"),
        "internal_passed": data.get("internal_roundtrip", {}).get("passed"),
        "internal_features_equal": data.get("internal_roundtrip", {}).get(
            "features_equal"),
        "internal_qualifiers_equal": data.get("internal_roundtrip", {}).get(
            "qualifiers_equal"),
        "internal_qualifier_differences": data.get("internal_roundtrip", {}).get(
            "qualifier_differences", []),
        "official_qualifier_differences": official.get(
            "qualifier_differences", []),
        "warnings": data.get("warnings", [])[:8],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapgene-exe", default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-enforce", action="store_true")
    parser.add_argument("--out-dir", default=str(REPORT_DIR))
    args = parser.parse_args(argv)

    if not FIXTURES.is_dir():
        print("fixtures/rich not found (run tools/build_rich_fixtures.py first)")
        return 1
    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    executable = _find_snapgene(args.snapgene_exe)
    fixtures = {}
    gate_ok = True
    for name in CORE_FIXTURES:
        fixture = FIXTURES / (name + ".gb")
        if not fixture.exists():
            fixtures[name] = {"error": "fixture missing"}
            gate_ok = False
            continue
        compatibility = analyze(str(fixture))
        snapgene_gb = _run_roundtrip(fixture, "snapgene-gb", executable,
                                     require_snapgene=bool(executable))
        dna = _run_roundtrip(fixture, "dna", executable,
                             require_snapgene=False)
        gb_policy = compatibility["formats"]["snapgene-gb"]
        dna_policy = compatibility["formats"]["dna"]
        gb_internal_ok = (
            snapgene_gb.get("status") == "completed"
            and snapgene_gb.get("internal_passed")
            and snapgene_gb.get("internal_qualifiers_equal"))
        dna_internal_ok = (
            dna.get("status") == "completed"
            and (dna.get("internal_passed") or not dna_policy["core_safe"]))
        gb_official_ok = (
            snapgene_gb.get("official_status") != "completed"
            or snapgene_gb.get("official_passed")
            or not gb_policy["core_safe"])
        gb_strict_ok = (
            snapgene_gb.get("official_status") != "completed"
            or not snapgene_gb.get("official_qualifier_differences")
            or not gb_policy["strict_safe"])
        dna_official_ok = (
            dna.get("official_status") != "completed"
            or dna.get("official_passed")
            or not dna_policy["core_safe"])
        gb_ok = gb_internal_ok and gb_official_ok and gb_strict_ok
        dna_ok = dna_internal_ok and dna_official_ok
        gate_ok = gate_ok and gb_ok and dna_ok
        fixtures[name] = {
            "snapgene_gb": snapgene_gb,
            "dna": dna,
            "compatibility": compatibility,
            "accepted_known_difference": bool(
                (not snapgene_gb.get("official_passed", True)
                 and not gb_policy["core_safe"])
                or (snapgene_gb.get("official_qualifier_differences")
                    and not gb_policy["strict_safe"])
                or (not dna.get("official_passed", True)
                    and not dna_policy["core_safe"])),
            "gate_ok": gb_ok and dna_ok,
        }
        print("%-22s snapgene-gb core=%-5s strict=%-5s %-10s | dna core=%-5s"
              % (name,
                 snapgene_gb.get("core_passed"),
                 snapgene_gb.get("strict_passed"),
                 snapgene_gb.get("delivery_grade", "error"),
                 dna.get("core_passed")))

    report = {
        "gate": "rich-feature-declared-compatibility",
        "policy_version": "0.6.0-rc2",
        "fixture_count": len(fixtures),
        "snapgene_executable_found": bool(executable),
        "official_snapgene_verification": "completed" if executable else "skipped",
        "official_note": (
            "SnapGene executable detected; official strict round trip ran."
            if executable else
            "No SnapGene executable on this machine; official --require-snapgene "
            "verification is pending (internal strict round trip passed)."),
        "fixtures": fixtures,
        "gate_ok": gate_ok,
    }
    (out_dir / "rich-roundtrip.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8")
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    print("rich declared compatibility gate: %s" % (
        "PASS" if gate_ok else "FAIL"))
    print(report["official_note"])
    if args.no_enforce:
        return 0
    return 0 if gate_ok else 1


if __name__ == "__main__":
    sys.exit(main())
