# -*- coding: utf-8 -*-
"""Validate semantic round trips for GenBank and native SnapGene exports."""
import argparse
import copy
import os
import subprocess
import tempfile
import warnings as py_warnings

from Bio import SeqIO

from sg_common import jprint, load_seq, topology
from write_dna import _ensure_annotations, _snapgene_annotated, write_native_dna


def _label(feature):
    value = feature.qualifiers.get(
        "label", feature.qualifiers.get("gene", [feature.id or "feature"])
    )
    return str(value[0] if isinstance(value, list) else value)


def _feature_core(feature):
    parts = getattr(feature.location, "parts", [feature.location])
    return (
        feature.type,
        _label(feature),
        getattr(feature.location, "operator", None),
        tuple(
            (
                int(part.start), int(part.end),
                0 if part.strand is None else int(part.strand),
            )
            for part in parts
        ),
    )


def _feature_qualifiers(feature):
    normalized = []
    for key, value in feature.qualifiers.items():
        values = value if isinstance(value, list) else [value]
        normalized.append((str(key), tuple(str(item) for item in values)))
    return (_feature_core(feature), tuple(sorted(normalized)))


def _feature_set(record, with_qualifiers=False):
    signature = _feature_qualifiers if with_qualifiers else _feature_core
    return sorted(
        signature(feature)
        for feature in record.features
        if feature.type != "source"
    )


IMPORTANT_QUALIFIER_KEYS = {
    "translation", "codon_start", "gene", "label", "product",
    "directionality", "transl_table",
}


def _qualifier_differences(expected, observed):
    """Return key-level qualifier differences with an importance flag."""
    expected_by_core = {
        _feature_core(f): _feature_qualifiers(f)[1]
        for f in expected.features if f.type != "source"
    }
    observed_by_core = {
        _feature_core(f): _feature_qualifiers(f)[1]
        for f in observed.features if f.type != "source"
    }
    differences = []
    for core, qualifiers in expected_by_core.items():
        label = core[1]
        if core not in observed_by_core:
            differences.append({
                "feature": label,
                "missing_feature": True,
                "important": True,
            })
            continue
        observed_qualifiers = observed_by_core[core]
        if observed_qualifiers == qualifiers:
            continue
        expected_dict = dict(qualifiers)
        observed_dict = dict(observed_qualifiers)
        expected_keys = set(expected_dict)
        observed_keys = set(observed_dict)
        missing_keys = sorted(expected_keys - observed_keys)
        unexpected_keys = sorted(observed_keys - expected_keys)
        changed = {
            key: {"expected": list(expected_dict[key]),
                  "observed": list(observed_dict[key])}
            for key in sorted(expected_keys & observed_keys)
            if expected_dict[key] != observed_dict[key]
        }
        important = any(
            key in IMPORTANT_QUALIFIER_KEYS
            for key in missing_keys + unexpected_keys + list(changed)
        )
        differences.append({
            "feature": label,
        "location_operator": core[2],
        "location": str(core[3]),
            "missing_keys": missing_keys,
            "unexpected_keys": unexpected_keys,
            "changed": changed,
            "important": important,
        })
    for core in observed_by_core:
        if core not in expected_by_core:
            differences.append({
                "feature": core[1],
                "unexpected_feature": True,
                "important": True,
            })
    return differences


def _qualifier_risk(differences):
    if not differences:
        return "none"
    return "important" if any(d.get("important") for d in differences) else "safe"


def compare_records(expected, observed):
    """Compare sequence, topology and feature semantics independently."""
    sequence_equal = str(expected.seq).upper() == str(observed.seq).upper()
    topology_equal = topology(expected) == topology(observed)
    features_equal = _feature_set(expected) == _feature_set(observed)
    qualifiers_equal = (
        _feature_set(expected, with_qualifiers=True)
        == _feature_set(observed, with_qualifiers=True)
    )
    qualifier_differences = _qualifier_differences(expected, observed)
    return {
        "passed": sequence_equal and topology_equal and features_equal,
        "sequence_equal": sequence_equal,
        "topology_equal": topology_equal,
        "features_equal": features_equal,
        "qualifiers_equal": qualifiers_equal,
        "qualifier_differences": qualifier_differences,
        "qualifier_risk": _qualifier_risk(qualifier_differences),
        "expected_feature_count": len(_feature_set(expected)),
        "observed_feature_count": len(_feature_set(observed)),
    }


def _write(record, fmt, path):
    record = copy.deepcopy(record)
    if fmt == "dna":
        write_native_dna(record, path)
    else:
        if fmt == "snapgene-gb":
            record = _snapgene_annotated(record)
        else:
            record = _ensure_annotations(record)
        with open(path, "w", encoding="utf-8") as handle:
            SeqIO.write(record, handle, "genbank")


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


def _official_convert(executable, input_path, output_path, target_format):
    startupinfo = None
    creationflags = 0
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    completed = subprocess.run(
        [
            executable, "--convert", target_format,
            "--input", input_path, "--output", output_path,
        ],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=90, startupinfo=startupinfo, creationflags=creationflags,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "SnapGene conversion failed (%d): %s"
            % (completed.returncode, (completed.stderr or completed.stdout).strip())
        )
    if not os.path.isfile(output_path):
        raise RuntimeError("SnapGene did not create expected output: %s" % output_path)


def _add_qualifier_warnings(comparison, prefix, warnings):
    if not comparison.get("qualifiers_equal"):
        differences = comparison.get("qualifier_differences", [])
        labels = [item.get("feature", "?") for item in differences]
        warnings.append(
            "%s qualifiers differ (%d difference(s), risk=%s): %s"
            % (prefix, len(differences),
               comparison.get("qualifier_risk", "unknown"),
               ", ".join(labels))
        )


def validate(source, fmt, snapgene_exe=None, require_snapgene=False, strict=False):
    expected, source_format = load_seq(source)
    warnings = []
    with tempfile.TemporaryDirectory(prefix="snapgene-v03-roundtrip-") as temp_dir:
        suffix = ".dna" if fmt == "dna" else ".gb"
        exported = os.path.join(temp_dir, "skill-export" + suffix)
        _write(expected, fmt, exported)
        with py_warnings.catch_warnings(record=True) as caught:
            py_warnings.simplefilter("always")
            observed, _ = load_seq(exported)
        internal = compare_records(expected, observed)
        internal["parser_warnings"] = [str(item.message) for item in caught]
        warnings.extend(
            "internal read-back: %s" % message
            for message in internal["parser_warnings"]
        )
        _add_qualifier_warnings(internal, "internal read-back", warnings)

        executable = _find_snapgene(snapgene_exe)
        official = {"status": "skipped", "passed": None}
        if executable:
            if fmt == "dna":
                official_path = os.path.join(temp_dir, "snapgene-export.gb")
                target_format = "GenBank - Standard"
            else:
                official_path = os.path.join(temp_dir, "snapgene-export.dna")
                target_format = "SnapGene DNA"
            _official_convert(executable, exported, official_path, target_format)
            with py_warnings.catch_warnings(record=True) as caught:
                py_warnings.simplefilter("always")
                official_record, _ = load_seq(official_path)
            official = compare_records(expected, official_record)
            official.update({
                "status": "completed",
                "executable": executable,
                "target_format": target_format,
                "parser_warnings": [str(item.message) for item in caught],
            })
            warnings.extend(
                "official SnapGene read-back: %s" % message
                for message in official["parser_warnings"]
            )
            _add_qualifier_warnings(official, "official SnapGene read-back", warnings)
        else:
            message = "SnapGene executable not found; official round trip skipped"
            warnings.append(message)
            if require_snapgene:
                official = {"status": "required_but_missing", "passed": False}

    core_passed = internal["passed"] and official.get("passed") is not False
    strict_passed = (
        core_passed
        and internal.get("qualifiers_equal", True)
        and (official.get("status") == "skipped"
             or official.get("qualifiers_equal", True))
    )
    passed = strict_passed if strict else core_passed
    lossless = bool(strict_passed and not warnings)
    if not core_passed:
        delivery_grade = "failed"
    elif lossless:
        delivery_grade = "lossless"
    else:
        risks = []
        for comparison in (internal, official):
            if comparison.get("status") == "completed" or comparison is internal:
                if comparison.get("qualifier_risk") == "important":
                    risks.append("important")
                elif comparison.get("qualifier_risk") == "safe":
                    risks.append("safe")
        if "important" in risks:
            delivery_grade = "core-compatible-with-important-differences"
        elif risks:
            delivery_grade = "core-compatible-with-safe-differences"
        else:
            delivery_grade = "core-compatible"
    return {
        "passed": passed,
        "core_passed": core_passed,
        "strict_passed": strict_passed,
        "strict": strict,
        "lossless": lossless,
        "delivery_grade": delivery_grade,
        "source_format": source_format,
        "export_format": fmt,
        "internal_roundtrip": internal,
        "official_snapgene_roundtrip": official,
        "warnings": warnings,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Validate semantic export/read-back and optional SnapGene round trip"
    )
    parser.add_argument("source")
    parser.add_argument(
        "--format", choices=["genbank", "snapgene-gb", "dna"],
        default="snapgene-gb",
    )
    parser.add_argument("--snapgene-exe", help="path to SnapGene.exe")
    parser.add_argument(
        "--strict", action="store_true",
        help="require full qualifier equality, not only sequence/topology/feature cores",
    )
    parser.add_argument(
        "--require-snapgene", action="store_true",
        help="fail when the official SnapGene executable is unavailable",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = validate(
            args.source, args.format, args.snapgene_exe, args.require_snapgene,
            strict=args.strict,
        )
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        raise SystemExit(str(error))
    if args.json:
        jprint(result)
    else:
        print(
            "round trip: %s (core=%s, strict=%s, internal=%s, official=%s)"
            % (
                "PASS" if result["passed"] else "FAIL",
                result["core_passed"], result["strict_passed"],
                result["internal_roundtrip"]["passed"],
                result["official_snapgene_roundtrip"].get("passed"),
            )
        )
        for warning in result["warnings"]:
            print("warning:", warning)
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
