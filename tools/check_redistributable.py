# -*- coding: utf-8 -*-
"""check_redistributable.py - Content-hash license checker for release packages.

Usage:
    python tools/check_redistributable.py <path-to-zip-or-directory>
    python tools/check_redistributable.py <path> --academic

Every regular file in a ZIP or directory is SHA-256 hashed. Restricted
content is detected by hash, not by path, so renames, case changes, extra
directories, or path separator variants cannot bypass the check.
"""

from project_paths import PROJECT_ROOT as REPOSITORY_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS, TESTS_ROOT
import argparse
import hashlib
import json
import pathlib
import sys
import zipfile

# All SnapGene-copied originals AND derived golden fixtures.
RESTRICTED_HASHES = {
    "3F684FE5CD0FDD68A042531C404D1EEE66437C678283666A30F0615B5E9810CA":
        "fixtures/pDONR201.dna",
    "9D6F5581AE1EFB6BB4444DE9AC367C101C3CA71EA3F87DCF6BEABF8A60CB5682":
        "fixtures/golden/pDEST40.dna",
    "8F66A4CC0DA1768DF8997F88ABEF6775650981649D942294B4ACEBF15E51DFA1":
        "fixtures/golden/pENTR-D-TOPO.dna",
    "DE8C2ADA35C3D866B0A96A7B3A1B5E1A61D064ADA517A8E0960C4F0179F06278":
        "fixtures/golden/pcDNA3.2-V5-GW-D-TOPO.dna",
    "93775CE66A4F95DFABCF42E05015AF9713F162C2BDDC72FBFC6CF1820EAE0F04":
        "fixtures/golden/pGEM-T-linearized.dna",
    "525AA602C3A3A4DCC4D98AD3AB2A22AC51DD9A3970ED8C60BDAC2AC89F01AC7E":
        "fixtures/golden/attB-EmGFP.fa",
    "5B829AE12F5C042D8906A8E10F19E8119973C9F6B7F9F9902FFC95652D008CA1":
        "fixtures/golden/attB-EmGFP.gb",
    "4719291A3F989D90EDB9EEF5F0E3512229911B0E987D13D1BF1312D29656EA04":
        "fixtures/golden/pDEST-EmGFP.gb",
    "1137275EFB7AF7DFDC6172EB264CEF2770885B4DDB05856A7FC30FF4C570A231":
        "fixtures/golden/pENTR-EmGFP.gb",
    "2E07DB4CE7052C0E5C39718CEF84F0C8202734253A22D259CC3E8EC9C96A6B33":
        "fixtures/golden/pGEM-T-insert.gb",
}


def _sha256(data):
    return hashlib.sha256(data).hexdigest().upper()


def _safe_zip_entries(path):
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            normalized = info.filename.replace("\\", "/")
            if (normalized.startswith("/") or ".." in normalized
                    or normalized.startswith("\\\\")):
                raise ValueError("unsafe archive entry: %s" % info.filename)
            if info.is_dir():
                continue
            data = archive.read(info)
            yield normalized, data


def inspect_zip(path, restricted_hashes=None):
    hashes = RESTRICTED_HASHES if restricted_hashes is None else restricted_hashes
    found = {}
    for normalized, data in _safe_zip_entries(path):
        digest = _sha256(data)
        if digest in hashes:
            found.setdefault(digest, []).append({
                "path": normalized,
                "expected_path": hashes[digest],
            })
    return found


def inspect_dir(path, restricted_hashes=None):
    hashes = RESTRICTED_HASHES if restricted_hashes is None else restricted_hashes
    found = {}
    for candidate in path.rglob("*"):
        if not candidate.is_file():
            continue
        if "__pycache__" in candidate.parts:
            continue
        digest = _sha256(candidate.read_bytes())
        if digest in hashes:
            found.setdefault(digest, []).append({
                "path": str(candidate.relative_to(path)).replace("\\", "/"),
                "expected_path": hashes[digest],
            })
    return found


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--academic", action="store_true")
    parser.add_argument("--restricted-hash", action="append", default=[],
                        help="extra restricted hash as HASH=LABEL (tests)")
    args = parser.parse_args()
    extra_hashes = {}
    for item in args.restricted_hash:
        digest, label = item.split("=", 1)
        extra_hashes[digest.upper()] = label
    effective_hashes = dict(RESTRICTED_HASHES)
    effective_hashes.update(extra_hashes)
    target = pathlib.Path(args.path)
    if target.is_dir():
        found = inspect_dir(target, effective_hashes)
    elif target.is_file():
        found = inspect_zip(target, effective_hashes)
    else:
        print(json.dumps({"ok": False, "error": "path not found"}))
        return 1

    expected_hashes = set(effective_hashes)
    found_hashes = set(found)
    if args.academic:
        missing = sorted(expected_hashes - found_hashes)
        flattened = [item for digest in sorted(found_hashes)
                     for item in found[digest]]
        report = {
            "ok": not missing,
            "package": "academic-full",
            "expected_restricted_hashes": len(expected_hashes),
            "found_restricted_hashes": len(found_hashes),
            "found": flattened,
            "missing": [effective_hashes[h] for h in missing],
        }
        print(json.dumps(report, indent=2))
        return 0 if not missing else 1
    if found_hashes:
        flattened = [item for digest in sorted(found_hashes)
                     for item in found[digest]]
        report = {
            "ok": False,
            "package": "redistributable",
            "error": "restricted SnapGene-derived content present",
            "found": flattened,
        }
        print(json.dumps(report, indent=2))
        return 1
    print(json.dumps({"ok": True, "package": "redistributable",
                      "restricted_hashes_found": 0}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
