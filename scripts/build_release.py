# -*- coding: utf-8 -*-
"""build_release.py - Reproducible academic-full / redistributable packaging.

Builds two ZIPs from the same source tree, refreshes
DEVELOPMENT-MANIFEST.json from the current tree, and writes a fresh
RELEASE-MANIFEST.json using the stable release-manifest schema contract
(`schema_version = "0.8.0"`) into each archive.  The two packages receive package-appropriate
DEVELOPMENT-NOTICE.md / THIRD_PARTY_NOTICE.md content instead of sharing
one contradictory notice.
"""
import argparse
import hashlib
import json
import pathlib
import sys
import zipfile

from check_redistributable import RESTRICTED_HASHES
from provenance import read_version

EXCLUDE_ALL = (
    "RELEASE-MANIFEST.json",
    ".coverage",
)
EXCLUDE_PREFIXES = (
    "reports/",
    "build/",
    "output/",
    "dist/",
    "docs/REAL-WORLD-SKILL-",
    "docs/REAL-WORKFLOW-REPAIR-",
    ".venv/",
    ".codex/",
    "__pycache__/",
    "tmp_",
    ".git/",
    ".pytest_cache/",
)

ACADEMIC_ONLY_PATHS = (
    "fixtures/pDONR201.dna",
    "fixtures/golden/",
    "tests/test_smoke_academic.py",
    "tests/test_v03.py",
    "tests/test_v04.py",
    "tests/test_license_real.py",
    "scripts/smoke_suite.py",
    "scripts/smoke_academic.py",
)

THIRD_PARTY_LICENSES = {
    "third_party/azimuth/": "BSD-3-Clause (Azimuth/Doench-2016)",
    "third_party/deepcpf1/": "Artistic-2.0 (CRISPRseek DeepCpf1 weights)",
}

ZIP_PREFIX = "snapgene-dna-design/"


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _third_party_license(rel):
    for prefix, license_value in THIRD_PARTY_LICENSES.items():
        if rel.startswith(prefix):
            return license_value
    return None


def _classify(path, digest):
    if digest in RESTRICTED_HASHES:
        return "snapgene-fixture" if path.endswith(".dna") else "derived-fixture"
    third_party = _third_party_license(path)
    if third_party:
        if path.endswith(".h5") or path.endswith(".pickle"):
            return "third-party-model"
        if path.endswith(".py"):
            return "third-party-code"
        return "third-party-license"
    if path.startswith("fixtures/"):
        return "synthetic-fixture"
    if path in ("THIRD_PARTY_NOTICE.md", "LICENSE",
                "DEVELOPMENT-NOTICE.md"):
        return "license-notice"
    if path.endswith(".md") or (path.endswith(".json")
                                and path.startswith("references/")):
        return "documentation"
    return "project-code"


def _exclusion_reason(path, digest):
    if digest in RESTRICTED_HASHES:
        return "snapgene-restricted-or-derived"
    for prefix in ACADEMIC_ONLY_PATHS:
        if path == prefix or path.startswith(prefix):
            return "depends-on-restricted-fixtures"
    return None


def _collect(root, exclude_extra=()):
    entries = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if (rel in EXCLUDE_ALL or rel in exclude_extra
                or "__pycache__" in rel or rel.endswith(".pyc")):
            continue
        if any(rel.startswith(prefix) for prefix in EXCLUDE_PREFIXES):
            continue
        digest = _sha256(path)
        category = _classify(rel, digest)
        exclusion_reason = _exclusion_reason(rel, digest)
        license_value = _third_party_license(rel)
        if license_value is None:
            license_value = ("GraphPad/SnapGene-terms"
                             if digest in RESTRICTED_HASHES else "MIT")
        entries.append({
            "path": rel,
            "sha256": digest,
            "size": path.stat().st_size,
            "license": license_value,
            "source_category": category,
            "redistributable": exclusion_reason is None,
            "exclusion_reason": exclusion_reason,
        })
    return entries


def _development_manifest(root, version):
    entries = _collect(root, exclude_extra=("DEVELOPMENT-MANIFEST.json",))
    manifest = {
        "manifest_kind": "development-manifest",
        "version": version,
        "generator": "scripts/build_release.py",
        "entries": entries,
    }
    (root / "DEVELOPMENT-MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8")


def _development_notice(version, redistributable):
    package_kind = ("redistributable" if redistributable else "academic-full")
    prerelease = "dev" in version.lower() or "-rc" in version.lower()
    return (
        "# Package status\n\n"
        "Version: SnapGene DNA Design v%s (%s package).\n\n"
        "%s Python dependencies and optional external programs must be "
        "installed separately; follow README.md.\n\n"
        "Backend honesty: Cas-OFFinder, CRISPOR and primer3_core are optional "
        "external runtimes. None of them is bundled. Real-backend gates must "
        "run the real executable/model in this environment and are never "
        "satisfied by a placeholder or a skipped test.\n\n"
        "License warning: %s\n\n"
        "The reports/ directory is rebuilt by the coverage/mutation/property "
        "gates. Re-run every gate after code changes; do not treat older "
        "reports as evidence for this version.\n"
        % (version, package_kind,
           ("This is a prerelease candidate for validation." if prerelease else
            "This is a versioned release package. See CHANGELOG.md for the validated scope and known limits."),
           ("this archive contains academic-only SnapGene fixtures and "
            "derived fixtures. Do not publish or redistribute it. See "
            "THIRD_PARTY_NOTICE.md."
            if not redistributable else
            "this package contains only MIT project code plus the third-party "
            "model artifacts listed in THIRD_PARTY_NOTICE.md; no academic-only "
            "fixtures are present."))
    )


def _third_party_notice(redistributable):
    lines = [
        "# Third-Party Notice",
        "",
        "The software source code in this repository (including `scripts/`, "
        "`tests/`, `SKILL.md`, `agents/openai.yaml`, and `references/`) is "
        "provided under the MIT License in `LICENSE`.",
    ]
    if not redistributable:
        lines += [
            "",
            "## SnapGene fixtures (academic-only)",
            "",
            "`fixtures/pDONR201.dna` and the `fixtures/golden/` directory were "
            "copied or derived from the SnapGene 6.x plasmid collection "
            "(GraphPad Software / SnapGene). SnapGene states that maps, notes "
            "and annotations from its plasmid collection are copyrighted: "
            "academic, non-profit and government users may use them with "
            "attribution at www.snapgene.com/resources; commercial users must "
            "contact GraphPad for a separate license. Do not redistribute "
            "this package commercially without written authorization from "
            "GraphPad/SnapGene.",
        ]
    lines += [
        "",
        "## Bundled third-party model artifacts",
        "",
        "- `third_party/azimuth/` - Azimuth 2.0 (Microsoft Research), "
        "Doench et al. 2016, DOI 10.1038/nbt.3437. BSD license. The V3 model "
        "pickles and converted featurization code are bundled.",
        "- `third_party/deepcpf1/` - DeepCpf1 model weights as distributed by "
        "the Bioconductor CRISPRseek package (Kim et al. 2018, DOI "
        "10.1038/nbt.4061). Artistic License 2.0. See "
        "`third_party/deepcpf1/README.license`.",
        "",
        "## External runtimes (not bundled)",
        "",
        "- Cas-OFFinder: BSD-3-Clause, https://github.com/snugel/cas-offinder",
        "- CRISPOR: https://crispor.org, license must be reviewed before use",
        "- primer3_core / Primer3: GPL-2.0-or-later, "
        "https://github.com/primer3-org/primer3",
        "",
        "Upstream licenses remain with their respective copyright holders.",
    ]
    return "\n".join(lines) + "\n"


def _entry(rel, text, license_value="MIT", category="license-notice"):
    return {
        "path": rel,
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest().upper(),
        "size": len(text.encode("utf-8")),
        "license": license_value,
        "source_category": category,
        "redistributable": True,
        "exclusion_reason": None,
    }


def _write_zip(zip_path, entries, root, version, notice_texts):
    prefix = ZIP_PREFIX
    with zipfile.ZipFile(
            zip_path, "w", compression=zipfile.ZIP_DEFLATED,
            compresslevel=9) as archive:
        for index, entry in enumerate(entries):
            rel = entry["path"]
            if rel == "THIRD_PARTY_NOTICE.md":
                text = notice_texts["third_party"]
                entry = _entry(rel, text,
                               license_value=entry.get("license", "MIT"),
                               category=entry.get("source_category"))
                entries[index] = entry
            elif rel == "DEVELOPMENT-NOTICE.md":
                text = notice_texts["development"]
                entry = _entry(rel, text,
                               license_value=entry.get("license", "MIT"),
                               category=entry.get("source_category"))
                entries[index] = entry
            else:
                text = None
            archive_path = prefix + rel
            info = zipfile.ZipInfo(archive_path, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            if text is None:
                with open(root / rel, "rb") as handle:
                    archive.writestr(info, handle.read())
            else:
                archive.writestr(info, text.encode("utf-8"))
        manifest = {
            "manifest_kind": "release-manifest",
            "build_version": version,
            "package": zip_path.name,
            "schema_version": "0.8.0",
            "entries": entries,
        }
        info = zipfile.ZipInfo(prefix + "RELEASE-MANIFEST.json",
                               date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o644 << 16
        archive.writestr(info, json.dumps(manifest, indent=2, sort_keys=True))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root")
    parser.add_argument("output")
    parser.add_argument("--version", default=None)
    parser.add_argument("--refresh-dev-manifest", action="store_true",
                        default=True)
    args = parser.parse_args()
    root = pathlib.Path(args.root).resolve()
    output = pathlib.Path(args.output).resolve()
    version_file = root / "VERSION"
    if not version_file.is_file():
        parser.error("package root has no VERSION file")
    declared_version = version_file.read_text(encoding="utf-8").strip()
    version = args.version or declared_version
    if version != declared_version:
        parser.error("--version %s does not match VERSION %s"
                     % (version, declared_version))
    output.mkdir(parents=True, exist_ok=True)

    if args.refresh_dev_manifest:
        _development_manifest(root, version)

    entries = _collect(root)
    if not any(entry["path"] == "DEVELOPMENT-NOTICE.md" for entry in entries):
        entries.append(_entry("DEVELOPMENT-NOTICE.md", _development_notice(version, True)))
    academic_entries = entries
    # Source notices are replaced by package-specific generated content.
    redist_entries = [entry for entry in entries if entry["redistributable"]]

    academic = output / ("snapgene-dna-design-v%s-academic-full.zip" % version)
    redist = output / ("snapgene-dna-design-v%s-redistributable.zip" % version)
    _write_zip(academic, academic_entries, root, version, {
        "third_party": _third_party_notice(redistributable=False),
        "development": _development_notice(version, redistributable=False),
    })
    _write_zip(redist, redist_entries, root, version, {
        "third_party": _third_party_notice(redistributable=True),
        "development": _development_notice(version, redistributable=True),
    })
    print(json.dumps({
        "academic": str(academic),
        "redistributable": str(redist),
        "academic_entries": len(academic_entries),
        "redistributable_entries": len(redist_entries),
        "version": version,
    }, indent=2))


if __name__ == "__main__":
    sys.exit(main())
