# -*- coding: utf-8 -*-
"""coverage_gate.py - Release gate for core-module coverage.

Enforces the formal-release coverage gate:

    * v0.5/v0.7 core modules: line >= 90%, branch >= 85%
    * v0.8 CRISPR modules (joined in dev3): line >= 85%, branch >= 75%

Measurement strategy (canonical coverage.py parallel workflow)
--------------------------------------------------------------
* the gate writes a temporary ``sitecustomize.py`` that calls
  ``coverage.process_startup()``. Together with ``COVERAGE_PROCESS_START`` +
  ``COVERAGE_FILE`` (parallel mode), this makes coverage collection independent
  of a machine-specific ``coverage.pth`` installation and includes every CLI
  child process spawned by tests and smoke.
* ``coverage combine`` merges the parallel files into one data file.
* ``coverage json`` emits per-file line/branch numbers; the gate is enforced
  on the configured core module set.

Usage::

    python -X utf8 scripts/coverage_gate.py                 # run + enforce
    python -X utf8 scripts/coverage_gate.py --json          # JSON report on stdout
    python -X utf8 scripts/coverage_gate.py --no-enforce    # report only, exit 0
    python -X utf8 scripts/coverage_gate.py --core a,b,c    # override core set

Exit code is 0 only when the suites pass and every core module meets both
thresholds (or when ``--no-enforce`` is given). Reports are written to
``reports/coverage/``.
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
TESTS = ROOT / "tests"
SCRIPTS = HERE

# Modules the formal gate measures. These are the correctness-critical core:
# shared helpers, the unified fragment model, the construct model, the four
# assembly engines (Gibson / digest-ligate / In-Fusion / Golden Gate),
# export, round-trip validation, construct QC and the editing engine.
CORE_MODULES = [
    "sg_common",
    "assembly_model",
    "construct_model",
    "simulate_cloning",
    "simulate_advanced",
    "golden_gate",
    "write_dna",
    "validate_roundtrip",
    "validate_construct",
    "edit_plasmid",
    "snapgene_compatibility",
    "export_delivery_bundle",
    "primer3_core_backend",
    "design_primers",
    "operation_consent",
]

# v0.8 CRISPR design surface.  These are part of the same formal gate: the
# P0 coordinate fixes, Cas-OFFinder contract, on-target model adapters,
# consent/provenance/recommendation gates and the unified report.
V09_CORE_MODULES = [
    "plan_assembly",
    "design.spec",
    "agent.clarification",
    "agent.session",
    "agent.nl_parser",
    "agent.orchestrator",
    "agent.delivery",
    "planning.method_selector",
    "validate_design_spec",
    "primer_design_engine",
    "pcr_strategy",
    "parts_library",
    "online_sources",
    "validation_crosscheck",
    "planning.intent",
    "planning.planner",
    "planning.manual_render",
    "rules.engine",
]

V08_CORE_MODULES = [
    "design_guides",
    "cas_offinder_adapter",
    "guide_scoring",
    "recommend_protocol",
    "characterize_reaction",
    "sequence_upload_consent",
    "annotate_offtargets",
    "generate_crispr_design_report",
    "crispor_adapter",
    "protocol_evidence",
    "provenance",
    "azimuth_backend",
    "deepcpf1_model",
]
CORE_MODULES = CORE_MODULES + V08_CORE_MODULES + V09_CORE_MODULES

LINE_THRESHOLD = 90.0
BRANCH_THRESHOLD = 85.0

# Optional-real-backend modules are only enforceable when the release-real
# environment switches are present; default mode still reports their raw
# coverage but does not gate on it.
REAL_BACKEND_ONLY_MODULES = {
    "azimuth_backend",
    "deepcpf1_model",
}

RELEASE_REAL_ENV = {
    "SNAPGENE_RUN_REAL_MODELS": "1",
    "CAS_OFFINDER_EXE": None,
    "CAS_OFFINDER_EXE_V3": None,
    "PRIMER3_CORE": None,
}
# v0.8 CRISPR modules joined the gate in dev3.  They start from a lower
# (still meaningful) bar until their surface matures; the v0.5/v0.7 core
# keeps the original 90/85 release bar.
V08_LINE_THRESHOLD = 85.0
V08_BRANCH_THRESHOLD = 75.0
# v0.9 planning surface: meaningful lower bar until it matures.
V09_LINE_THRESHOLD = 75.0
V09_BRANCH_THRESHOLD = 60.0

REPORT_ROOT = ROOT / "reports" / "coverage"


def _coveragerc(target_dir):
    """Write the coverage config used by every process (parent + children)."""
    cfg = target_dir / "coveragerc"
    cfg.write_text(
        "[run]\n"
        "branch = True\n"
        "parallel = True\n"
        "source =\n"
        "    %s\n"
        "    %s\n"
        "    %s\n"
        "    %s\n"
        "    %s\n" % (
            SCRIPTS, ROOT / "planning", ROOT / "rules",
            ROOT / "design", ROOT / "agent"),
        encoding="utf-8",
    )
    return cfg


def _coverage_bootstrap(target_dir):
    """Create a temporary Python startup hook inherited by all subprocesses."""
    path = target_dir / "sitecustomize.py"
    path.write_text(
        "import coverage\ncoverage.process_startup()\n",
        encoding="utf-8",
    )
    return path


def _run(cmd, cwd, env, timeout=None):
    return subprocess.run(
        cmd, cwd=str(cwd), capture_output=True, text=True,
        encoding="utf-8", errors="replace", env=env, timeout=timeout,
    )


def _branch_percent(info):
    covered = info["summary"].get("covered_branches", 0)
    missing = info["summary"].get("missing_branches", 0)
    total = covered + missing
    if total == 0:
        return 100.0 if covered == 0 else 0.0
    return covered / total * 100.0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true",
                        help="print the JSON report to stdout")
    parser.add_argument("--no-enforce", action="store_true",
                        help="report only; never exit non-zero for low coverage")
    parser.add_argument("--core", default=",".join(CORE_MODULES),
                        help="comma-separated core module names (default: all)")
    parser.add_argument("--out-dir", default=str(REPORT_ROOT),
                        help="directory for coverage reports")
    parser.add_argument("--mode", choices=("default", "release-real"),
                        default="default",
                        help="default: gates correctness modules without "
                             "optional real backends; release-real: "
                             "requires all real backend env vars first")
    args = parser.parse_args(argv)

    if args.mode == "release-real":
        missing = []
        for key, expected in RELEASE_REAL_ENV.items():
            value = os.environ.get(key)
            if expected is None:
                if not value or not os.path.exists(value):
                    missing.append("%s (file missing)" % key)
            elif value != expected:
                missing.append("%s=%s" % (key, expected))
        if missing:
            print("REAL_BACKEND_REQUIRED: " + "; ".join(missing))
            return 2

    core_modules = [name.strip() for name in args.core.split(",") if name.strip()]
    if args.mode == "default":
        core_modules = [name for name in core_modules
                        if name not in REAL_BACKEND_ONLY_MODULES]
    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="covgate-") as td:
        target_dir = pathlib.Path(td)
        cfg = _coveragerc(target_dir)
        _coverage_bootstrap(target_dir)
        data_file = target_dir / "coverage"
        env = dict(os.environ)
        env["COVERAGE_PROCESS_START"] = str(cfg)
        env["COVERAGE_FILE"] = str(data_file)
        env["PYTHONPATH"] = (str(target_dir) + os.pathsep + str(SCRIPTS)
                             + os.pathsep
                             + env.get("PYTHONPATH", ""))
        # Ensure every coverage child and every CLI spawned by the tests reads
        # committed UTF-8 fixtures consistently on non-English Windows.
        env["PYTHONUTF8"] = "1"

        python = sys.executable

        unittest_cmd = [python, str(SCRIPTS / "run_test_suite.py")]
        if args.mode == "default":
            unittest_cmd.append("--allow-primer3-skip")
        steps = [
            ("unittest", unittest_cmd, ROOT),
            ("smoke_core", [python, str(SCRIPTS / "smoke_core.py")], ROOT),
            ("property_quick", [python, str(SCRIPTS / "property_tests.py"),
                                "--quick"], ROOT),
            ("rich_fixtures", [python,
                               str(SCRIPTS / "validate_rich_fixtures.py")], ROOT),
        ]
        if args.mode == "release-real":
            # Literature scenario suite is part of the release-real CI gate;
            # it uses the real primer3_core from the preflighted environment.
            steps.append((
                "scenario_suite",
                [python, str(SCRIPTS / "run_scenario_suite.py"),
                 "--out-dir", str(target_dir / "scenario-out")],
                ROOT))
        step_results = {}
        for name, cmd, cwd in steps:
            step_env = dict(env)
            if name == "scenario_suite":
                # The 90-scenario suite is an execution gate, not a coverage
                # target; running it with coverage.process_startup doubles
                # every child startup and can exceed the step timeout.
                step_env.pop("COVERAGE_PROCESS_START", None)
                step_env.pop("COVERAGE_FILE", None)
            print(f"[coverage_gate] Starting step: {name}...", flush=True)
            completed = _run(cmd, cwd=cwd, env=step_env, timeout=1800)
            print(f"[coverage_gate] Step {name} finished (rc={completed.returncode})", flush=True)
            step_results[name] = {
                "returncode": completed.returncode,
                "stdout_tail": (completed.stdout or "")[-400:],
                "stderr_tail": (completed.stderr or "")[-400:],
            }
        unittest_ok = step_results["unittest"]["returncode"] == 0
        smoke_rc = step_results["smoke_core"]["returncode"]
        suites_ok = all(item["returncode"] == 0 for item in step_results.values())

        combine = _run(
            [python, "-m", "coverage", "combine", "--rcfile", str(cfg),
             "--data-file", str(data_file)],
            cwd=ROOT, env=env)
        if combine.returncode != 0:
            raise RuntimeError(
                "coverage combine failed: %s"
                % (combine.stderr or combine.stdout))

        json_path = out_dir / "coverage.json"
        json_run = _run(
            [python, "-m", "coverage", "json", "--rcfile", str(cfg),
             "--data-file", str(data_file), "-o", str(json_path),
             "--include", str(SCRIPTS) + "/*," + str(ROOT / "planning") + "/*," + str(ROOT / "rules") + "/*," + str(ROOT / "design") + "/*," + str(ROOT / "agent") + "/*"],
            cwd=ROOT, env=env)
        if json_run.returncode != 0:
            raise RuntimeError(
                "coverage json failed: %s" % (json_run.stderr or json_run.stdout))
        report_json = json.loads(json_path.read_text(encoding="utf-8"))

        modules = []
        gate_ok = True
        for name in core_modules:
            info = None
            target = (name.replace(".", "/") + ".py"
                      if "." in name else name + ".py")
            for path, candidate in report_json.get("files", {}).items():
                normalized = path.replace("\\", "/")
                if (normalized == target
                        or normalized.endswith("/" + target)
                        or normalized.endswith("\\" + target)):
                    info = candidate
                    break
            if info is None:
                modules.append({
                    "module": name,
                    "line_percent": 0.0,
                    "branch_percent": 0.0,
                    "lines_covered": 0, "lines_total": 0,
                    "branches_covered": 0, "branches_total": 0,
                    "line_ok": False, "branch_ok": False,
                    "reason": "module not found in coverage report",
                })
                gate_ok = False
                continue
            summary = info["summary"]
            line_percent = float(summary["percent_covered"])
            branch_percent = _branch_percent(info)
            is_v09 = name in V09_CORE_MODULES
            is_v08 = name in V08_CORE_MODULES or is_v09
            line_threshold = (V09_LINE_THRESHOLD if is_v09
                              else V08_LINE_THRESHOLD if is_v08
                              else LINE_THRESHOLD)
            branch_threshold = (V09_BRANCH_THRESHOLD if is_v09
                                else V08_BRANCH_THRESHOLD if is_v08
                                else BRANCH_THRESHOLD)
            line_ok = line_percent >= line_threshold
            branch_ok = branch_percent >= branch_threshold
            gate_ok = gate_ok and line_ok and branch_ok
            modules.append({
                "module": name,
                "line_percent": round(line_percent, 2),
                "branch_percent": round(branch_percent, 2),
                "lines_covered": int(summary["covered_lines"]),
                "lines_total": int(summary["num_statements"]),
                "branches_covered": int(summary.get("covered_branches", 0)),
                "branches_total": int(summary.get("covered_branches", 0))
                + int(summary.get("missing_branches", 0)),
                "line_ok": line_ok,
                "branch_ok": branch_ok,
                "reason": None,
            })

        overall = {
            "gate": "core-module-coverage",
            "mode": args.mode,
            "line_threshold": LINE_THRESHOLD,
            "branch_threshold": BRANCH_THRESHOLD,
            "v08_line_threshold": V08_LINE_THRESHOLD,
            "v08_branch_threshold": V08_BRANCH_THRESHOLD,
            "v09_line_threshold": V09_LINE_THRESHOLD,
            "v09_branch_threshold": V09_BRANCH_THRESHOLD,
            "core_modules": modules,
            "gate_ok": gate_ok,
            "unittest_ok": bool(unittest_ok),
            "smoke_core_rc": int(smoke_rc),
            "suites_ok": bool(suites_ok),
            "steps": step_results,
        }
        (out_dir / "coverage-full.json").write_text(
            json.dumps(report_json, indent=2, sort_keys=True), encoding="utf-8")
        (out_dir / "coverage-gate.json").write_text(
            json.dumps(overall, indent=2, sort_keys=True), encoding="utf-8")

    if args.json:
        print(json.dumps(overall, indent=2, sort_keys=True, ensure_ascii=False))

    for module in modules:
        status = "PASS" if (module["line_ok"] and module["branch_ok"]) else "FAIL"
        print("%s %-22s line %6.2f%% (%d/%d)  branch %6.2f%% (%d/%d)%s"
              % (status, module["module"],
                 module["line_percent"], module["lines_covered"],
                 module["lines_total"],
                 module["branch_percent"], module["branches_covered"],
                 module["branches_total"],
                 "  " + module["reason"] if module["reason"] else ""))
    print("suites: %s" % " | ".join(
        "%s=%s" % (name, info["returncode"])
        for name, info in overall["steps"].items()))
    print("gate: %s" % ("PASS" if gate_ok else "FAIL"))
    if args.no_enforce:
        return 0
    if not gate_ok or not suites_ok:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
