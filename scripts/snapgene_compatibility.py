# -*- coding: utf-8 -*-
"""Preflight a construct against known SnapGene round-trip limitations.

This module does not claim that a file will be experimentally correct.  It
answers a narrower delivery question: which semantics are known to survive
the supported SnapGene interchange paths, and which require a human review.
"""
import argparse

from sg_common import jprint, load_seq


def _values(feature, key):
    value = feature.qualifiers.get(key, [])
    return value if isinstance(value, list) else [value]


def _name(feature):
    for key in ("label", "gene"):
        values = _values(feature, key)
        if values:
            return str(values[0])
    return str(feature.id or feature.type or "feature")


def _finding(code, severity, feature, message):
    return {
        "code": code,
        "severity": severity,
        "feature": _name(feature),
        "message": message,
    }


def _format_result(findings):
    core_findings = [item for item in findings if item["severity"] == "core"]
    strict_findings = [item for item in findings
                       if item["severity"] in ("core", "strict")]
    if core_findings:
        grade = "manual-review-required"
    elif strict_findings:
        grade = "core-compatible"
    else:
        grade = "safe"
    return {
        "core_safe": not core_findings,
        "strict_safe": not strict_findings,
        "delivery_grade": grade,
        "findings": findings,
    }


def analyze_record(record, source_format=None):
    """Return a conservative, evidence-backed compatibility assessment."""
    gb_findings = []
    dna_findings = []
    for feature in record.features:
        location = feature.location
        parts = list(getattr(location, "parts", [location]))
        operator = getattr(location, "operator", None)

        if operator == "order":
            message = ("SnapGene official round trips do not preserve the "
                       "INSDC order operator; do not re-save without review")
            gb_findings.append(_finding(
                "ORDER_LOCATION_NOT_PRESERVED", "core", feature, message))
            dna_findings.append(_finding(
                "ORDER_LOCATION_NOT_PRESERVED", "core", feature, message))
        elif len(parts) > 1:
            dna_findings.append(_finding(
                "DNA_COMPOUND_LOCATION_RISK", "core", feature,
                "Native .dna export may merge or reshape multi-part locations"))

        name = _name(feature)
        if not name.isascii():
            dna_findings.append(_finding(
                "DNA_UNICODE_FEATURE_NAME_RISK", "core", feature,
                "SnapGene may export a native .dna Unicode feature name as mojibake"))

        qualifiers = set(feature.qualifiers)
        native_lost = sorted(qualifiers - {"label"})
        if native_lost:
            dna_findings.append(_finding(
                "DNA_QUALIFIER_LOSS", "strict", feature,
                "Native .dna writer does not preserve qualifier keys: %s"
                % ", ".join(native_lost)))

        if len(_values(feature, "note")) > 1:
            gb_findings.append(_finding(
                "SNAPGENE_MULTIVALUE_NOTE_NORMALIZATION", "strict", feature,
                "SnapGene may keep only one value from a multi-value note"))
        if _values(feature, "db_xref"):
            gb_findings.append(_finding(
                "SNAPGENE_DB_XREF_NORMALIZATION", "strict", feature,
                "SnapGene may normalize or remove db_xref prefixes"))
        if _values(feature, "synonym"):
            gb_findings.append(_finding(
                "SNAPGENE_SYNONYM_LOSS", "strict", feature,
                "SnapGene may omit synonym qualifiers"))
        if _values(feature, "translation"):
            gb_findings.append(_finding(
                "SNAPGENE_TRANSLATION_RECOMPUTED", "strict", feature,
                "SnapGene may recompute translation and add transl_table"))

    formats = {
        "snapgene-gb": _format_result(gb_findings),
        "dna": _format_result(dna_findings),
    }
    gb = formats["snapgene-gb"]
    dna = formats["dna"]
    if gb["core_safe"]:
        preferred = "snapgene-gb"
        reason = "GenBank is the authoritative delivery format for metadata fidelity"
    else:
        preferred = "genbank-authoritative-manual-review"
        reason = ("No SnapGene re-save path is core-safe for every feature; "
                  "retain the original GenBank and review affected features")
    return {
        "policy_version": "0.6.0-rc2",
        "source_format": source_format,
        "sequence_length": len(record.seq),
        "feature_count": len(record.features),
        "formats": formats,
        "recommendation": {
            "preferred_format": preferred,
            "authoritative_format": "genbank",
            "include_native_dna_by_default": bool(dna["core_safe"]),
            "manual_review_required": not gb["core_safe"],
            "reason": reason,
        },
        "warnings": [
            "Compatibility describes file semantics, not primer quality, "
            "biological viability, specificity, or experimental success."
        ],
    }


def analyze(source):
    record, source_format = load_seq(source)
    return analyze_record(record, source_format)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = analyze(args.source)
    except (OSError, ValueError) as error:
        raise SystemExit(str(error))
    if args.json:
        jprint(result)
    else:
        print("SnapGene delivery preflight")
        for name, assessment in result["formats"].items():
            print("  %s: %s (%d finding(s))" % (
                name, assessment["delivery_grade"],
                len(assessment["findings"])))
        print("  preferred:", result["recommendation"]["preferred_format"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
