# -*- coding: utf-8 -*-
"""validate_release_manifest.py - Verify RELEASE-MANIFEST.json against a ZIP."""
import argparse
import hashlib
import json
import pathlib
import sys
import zipfile


def _sha256(data):
    return hashlib.sha256(data).hexdigest().upper()


def _read_manifest(archive, prefix):
    candidates = [name for name in archive.namelist()
                  if name == prefix + "RELEASE-MANIFEST.json"]
    if not candidates:
        return None, "RELEASE-MANIFEST.json not found"
    return json.loads(archive.read(candidates[0])), None


def validate(zip_path, package_kind=None, version=None):
    errors = []
    prefix = "snapgene-dna-design/"
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
        normalized = [n.replace("\\", "/") for n in names]
        if any(".." in n or n.startswith("/") for n in normalized):
            errors.append("unsafe archive path")
        manifest, error = _read_manifest(archive, prefix)
        if error:
            errors.append(error)
            return errors

        manifest_prefix = prefix
        entry_paths = set()
        for entry in manifest.get("entries", []):
            rel = entry["path"]
            archive_name = manifest_prefix + rel
            entry_paths.add(archive_name)
            if archive_name not in names:
                errors.append("manifest path missing from archive: %s" % rel)
                continue
            data = archive.read(archive_name)
            if entry.get("size") != len(data):
                errors.append("size mismatch: %s" % rel)
            if entry.get("sha256") != _sha256(data):
                errors.append("sha mismatch: %s" % rel)
            if entry.get("redistributable") and entry.get("exclusion_reason") is not None:
                errors.append("redistributable file has exclusion_reason: %s" % rel)
            if package_kind == "redistributable" and not entry.get("redistributable"):
                errors.append("non-redistributable file present: %s" % rel)

        manifest_entry_paths = entry_paths | {prefix + "RELEASE-MANIFEST.json"}
        unregistered = [
            name for name in names
            if not name.endswith("/") and name not in manifest_entry_paths
        ]
        if unregistered:
            errors.append("unregistered archive files: %s" % ", ".join(unregistered))

        if version and manifest.get("build_version") != version:
            errors.append("build_version mismatch: %s" % manifest.get("build_version"))
        if manifest.get("build_version") not in zip_path:
            errors.append("version not reflected in file name")
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("archive")
    parser.add_argument("--package", choices=["academic-full", "redistributable"])
    parser.add_argument("--version")
    args = parser.parse_args()
    errors = validate(args.archive, args.package, args.version)
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, indent=2))
        return 1
    print(json.dumps({"ok": True, "archive": args.archive}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
