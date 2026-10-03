# -*- coding: utf-8 -*-
"""install_primer3.py - Zero-friction one-click installer and validator for Primer3.

Usage:
    python scripts/install_primer3.py
    python scripts/install_primer3.py --check-only
    python scripts/install_primer3.py --force
    python scripts/install_primer3.py --json

This utility ensures that official Primer3 capability is ready out of the box.
It uses pip to fetch the precompiled binary wheel for the active platform
(Windows, macOS, or Linux) with zero C++ compilation required.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys

# Ensure repository scripts directory is importable
HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from primer3_core_backend import (
    clear_core_cache,
    design_anchored_pairs,
    discover_primer3_core,
    probe_primer3_core,
)


def verify_primer3_execution(core_path: str) -> dict:
    """Run a test PCR primer design against a natural 125 bp EGFP coding segment."""
    test_seq = (
        "ATGGCTAGCAAAGGAGAAGAACTTTTCACTGGAGTTGTCCCAATTCTTGTTGAATTAGATGGTGATGTTAATGGGCACAAATTTTCTGTCCGTGGAGAGGGTGAAGGTGATGCTACAAACGGAAAACTCACCC"
    )
    res = design_anchored_pairs(
        core_path=core_path,
        sequence=test_seq,
        region_start=0,
        target_tm=60.0,
        min_len=18,
        max_len=28,
        top_n=1,
    )
    pairs = res.get("pairs") or []
    if not pairs:
        raise RuntimeError(
            "primer3_core executed but returned no acceptable pairs: %s"
            % res.get("explain")
        )
    return {
        "status": "verified",
        "returned_pairs": len(pairs),
        "product_size": pairs[0].get("product_size"),
        "primer3_penalty": pairs[0].get("primer3_penalty"),
        "heterodimer_tm": (pairs[0].get("heterodimer") or {}).get("tm_any"),
    }


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Install and verify Primer3 core engine")
    parser.add_argument("--check-only", action="store_true", help="Only check, do not install")
    parser.add_argument("--force", action="store_true", help="Force re-install even if found")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    args = parser.parse_args()

    clear_core_cache()
    current_probe = probe_primer3_core()

    already_ok = (current_probe.get("status") == "available" and not args.force)

    if already_ok:
        core_path = current_probe["path"]
        try:
            test_run = verify_primer3_execution(core_path)
            report = {
                "ok": True,
                "action": "already_installed",
                "path": core_path,
                "version": current_probe.get("version"),
                "verification": test_run,
            }
            if args.json:
                print(json.dumps(report, indent=2))
            else:
                print("================================================================")
                print(" Primer3 Core Engine: READY (Already Installed)")
                print("================================================================")
                print(" Path:    %s" % core_path)
                print(" Version: %s" % current_probe.get("version"))
                print(" Status:  100%% Operational (Boulder-IO verified)")
                print("================================================================")
            return 0
        except Exception as exc:
            if not args.json:
                print("[WARNING] Existing primer3_core failed verification: %s" % exc)

    if args.check_only:
        report = {
            "ok": False,
            "action": "check_only",
            "probe": current_probe,
            "message": "primer3_core is not available",
        }
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print("Primer3 core is NOT installed. Run 'python scripts/install_primer3.py' to install.")
        return 1

    # Perform installation
    if not args.json:
        print("================================================================")
        print(" Installing official precompiled Primer3 wheel via pip...")
        print(" Target environment: %s" % sys.executable)
        print("================================================================")

    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "primer3-py>=2.3.0"]
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=180,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        else:
            print("[ERROR] Failed to invoke pip: %s" % exc)
        return 1

    if completed.returncode != 0:
        err_msg = (completed.stderr or completed.stdout or "").strip()
        if args.json:
            print(json.dumps({"ok": False, "exit_code": completed.returncode, "error": err_msg}, indent=2))
        else:
            print("[ERROR] pip install failed with exit code %d:" % completed.returncode)
            print(err_msg)
        return completed.returncode

    clear_core_cache()
    new_probe = probe_primer3_core()
    if new_probe.get("status") != "available":
        if args.json:
            print(json.dumps({"ok": False, "error": "Executable not found after pip install", "probe": new_probe}, indent=2))
        else:
            print("[ERROR] primer3-py was installed, but primer3_core executable was not discovered.")
            print("Detail: %s" % new_probe.get("detail"))
        return 1

    core_path = new_probe["path"]
    try:
        test_run = verify_primer3_execution(core_path)
    except Exception as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": "Verification failed", "detail": str(exc)}, indent=2))
        else:
            print("[ERROR] Installed primer3_core failed operational verification: %s" % exc)
        return 1

    report = {
        "ok": True,
        "action": "installed_and_verified",
        "path": core_path,
        "version": new_probe.get("version"),
        "verification": test_run,
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("================================================================")
        print(" SUCCESS! Primer3 Core Engine is installed and ready to use.")
        print("================================================================")
        print(" Path:    %s" % core_path)
        print(" Version: %s" % new_probe.get("version"))
        print(" Mode:    Process-isolated Boulder-IO (MIT compliant)")
        print("================================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
