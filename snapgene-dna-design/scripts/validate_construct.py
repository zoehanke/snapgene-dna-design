# -*- coding: utf-8 -*-
"""validate_construct.py - One-shot construct QC.

Checks a sequence file and reports problems with severity levels:
  error   - coordinate out of bounds, invalid CDS metadata/frame/start/stop,
            unknown base, translation mismatch, premature stop
  warning - non-unique cutter, missing primers, unusual length
  ok      - check passed

Output: JSON (--json) or a readable report. Exit code 1 if any error.
"""
import argparse
import json
from collections import defaultdict

from Bio.Seq import Seq

from sg_common import enzyme_sites, features_to_dict, get_enzyme, jprint, load_seq, topology

# Enzymes commonly used as single-cutters (for unique-cutter check).
QC_ENZYMES = ["EcoRI", "BamHI", "HindIII", "XbaI", "NotI", "XhoI", "SalI", "PstI", "KpnI", "SacI"]


from core.tools.sequence_ops import validate_cds_feature


def _cds_translation(seq, start0, end0, strand):
    frag = seq[start0:end0]
    if strand == -1:
        frag = str(Seq(frag).reverse_complement())
    return str(Seq(frag).translate())


def _feature_identity(record, index):
    """Compare actual feature content/metadata, allowing an unchanged coordinate shift."""
    from core.models.molecule import feature_data, json_metadata
    feature = record.features[index]
    data = feature_data(feature)
    location = data.pop('location')
    data['location_shape'] = {'operator': location['operator'], 'parts': [
        {'length': len(part), 'strand': part.strand, 'start_kind': type(part.start).__name__,
         'end_kind': type(part.end).__name__, 'ref': part.ref, 'ref_db': part.ref_db}
        for part in feature.location.parts]}
    try:
        data['extracted_sequence'] = str(feature.extract(record.seq)).upper()
    except (AttributeError, TypeError, ValueError):
        # Invalid coordinates cannot be certified unchanged by an extraction.
        data['unextractable_location'] = location
    return json.dumps(json_metadata(data), sort_keys=True, ensure_ascii=False)


def _classify_origins(record, checks, template):
    previous = defaultdict(list)
    if template is not None:
        for check in validate(template)['checks']:
            if check['status'] not in ('error', 'warning'):
                continue
            index = check.get('feature_index')
            identity = _feature_identity(template, index) if index is not None else None
            previous[(identity, check['status'], check['check'], check['detail'])].append(index)
    for check in checks:
        if check['status'] not in ('error', 'warning'):
            continue
        check['origin'] = 'UNDETERMINED'
        if template is None:
            continue
        index = check.get('feature_index')
        identity = _feature_identity(record, index) if index is not None else None
        key = (identity, check['status'], check['check'], check['detail'])
        if previous[key]:
            check['origin'] = 'INHERITED_FROM_TEMPLATE'
            check['template_feature_index'] = previous[key].pop(0)
        else:
            check['origin'] = 'INTRODUCED_OR_CHANGED'


def validate(record, template=None):
    seq = str(record.seq)
    n = len(seq)
    checks = []

    # topology + length
    topo = topology(record)
    checks.append({"check": "topology", "status": "ok",
                   "detail": "circular" if topo == "circular" else "linear"})
    if n == 0:
        checks.append({"check": "length", "status": "error", "detail": "empty sequence"})
    else:
        checks.append({"check": "length", "status": "ok", "detail": "%d bp" % n})

    features = features_to_dict(record)
    checks.append({"check": "feature_count", "status": "ok",
                   "detail": "%d features" % len(features)})

    for index, (feature, f) in enumerate(zip(record.features, features)):
        check_start = len(checks)
        start, end = f.get("start"), f.get("end")
        name = f.get("name", "feature")

        # coordinate bounds (including compound segments)
        segs = f.get("segments", [{"start": start, "end": end}])
        for s in segs:
            if s["start"] < 1 or s["end"] > n or s["start"] > s["end"]:
                checks.append({
                    "check": "feature_coordinates", "status": "error",
                    "feature": name, "detail": "%s %d..%d out of bounds (len %d)"
                    % (f["type"], s["start"], s["end"], n)})
                break

        # CDS frame, metadata, translation and start/stop checks
        if f["type"] == "CDS" and start and end:
            audit = validate_cds_feature(feature, record.seq)
            error_checks = {
                "CDS_FRAME_INVALID": "cds_frame",
                "CDS_PREMATURE_STOP": "cds_premature_stop",
                "CDS_START_CODON_INVALID": "cds_start_codon",
                "CDS_TERMINAL_STOP_MISSING": "cds_stop_codon",
                "CDS_TRANSLATION_MISMATCH": "cds_translation_mismatch",
                "CDS_UNKNOWN_BASES": "cds_unknown_bases",
                "INVALID_CODON_START": "cds_codon_start",
                "INVALID_TRANSL_TABLE": "cds_transl_table",
                "CDS_EXTRACTION_FAILED": "cds_extraction",
            }
            for error in audit["errors"]:
                checks.append({
                    "check": error_checks.get(error["code"], "cds_validation"),
                    "status": "error",
                    "feature": name,
                    "detail": error["message"],
                })
            if audit["valid"] and audit["terminal_stop"]:
                checks.append({
                    "check": "cds_frame", "status": "ok", "feature": name,
                    "detail": "in-frame, terminal stop",
                })
            elif audit["valid"] and audit["partial"]:
                checks.append({
                    "check": "cds_frame", "status": "warning", "feature": name,
                    "detail": "partial CDS validated with explicit evidence",
                })
            for warning in audit["warnings"]:
                checks.append({
                    "check": "cds_translation_compatibility" if warning["code"] == "CDS_TRANSLATION_COMPATIBILITY" else "cds_partial_codon",
                    "status": "warning",
                    "feature": name,
                    "detail": warning["message"],
                })
            if audit["partial"] and not audit["start_codon_valid"]:
                checks.append({
                    "check": "cds_start_codon", "status": "ok", "feature": name,
                    "detail": "start-codon requirement waived by evidence: %s"
                    % "; ".join(audit["partial_evidence"]),
                })
        for check in checks[check_start:]:
            check['feature_index'] = index

    # unique cutter check
    for enz_name in QC_ENZYMES:
        try:
            enz = get_enzyme(enz_name)
        except ValueError:
            continue
        sites = enzyme_sites(seq, enz, circular=(topo == "circular"))
        if len(sites) == 1:
            checks.append({"check": "unique_cutter", "status": "ok",
                           "detail": "%s unique at %d" % (enz_name, sites[0])})
        elif len(sites) > 1:
            checks.append({"check": "unique_cutter", "status": "warning",
                           "detail": "%s cuts %d times (%s)"
                           % (enz_name, len(sites), ",".join(map(str, sites[:5])))})

    # primers
    n_primers = sum(1 for f in features if "primer" in f["type"].lower())
    checks.append({"check": "primers", "status": ("ok" if n_primers > 0 else "warning"),
                   "detail": "%d primer(s)" % n_primers})

    # junction (compound) features
    n_compound = sum(1 for f in features if f.get("segments") and len(f["segments"]) > 1)
    checks.append({"check": "junction", "status": "ok",
                   "detail": "%d multi-segment feature(s)" % n_compound})

    _classify_origins(record, checks, template)
    errors = [c for c in checks if c["status"] == "error"]
    warnings = [c for c in checks if c["status"] == "warning"]
    return {
        "id": record.id,
        "length": n,
        "topology": topo,
        "summary": {"errors": len(errors), "warnings": len(warnings),
                    "inherited_errors": sum(c['origin'] == 'INHERITED_FROM_TEMPLATE' for c in errors),
                    "introduced_or_changed_errors": sum(c['origin'] == 'INTRODUCED_OR_CHANGED' for c in errors),
                    "undetermined_errors": sum(c['origin'] == 'UNDETERMINED' for c in errors),
                    "pass": len(errors) == 0},
        "template_comparison": {'provided': template is not None,
            'template_id': template.id if template is not None else None,
            'method': 'Actual extracted feature DNA, annotation metadata, location shape and diagnostic equality; severity unchanged.'},
        "checks": checks,
    }


def main():
    p = argparse.ArgumentParser(description="Validate a construct (one-shot QC)")
    p.add_argument("source")
    p.add_argument("--json", action="store_true")
    p.add_argument("--template", help="Original template for inherited versus introduced/changed diagnostics; errors remain errors")
    args = p.parse_args()

    record, _fmt = load_seq(args.source)
    template = load_seq(args.template)[0] if args.template else None
    result = validate(record, template=template)

    if args.json:
        # A structurally parseable QC report is not a successful validation.
        # Bind the envelope's ``ok`` flag to the biological summary so callers
        # (including the agent orchestrator) cannot mistake CDS errors for a
        # verified construct merely because JSON was emitted.
        jprint(result, ok=bool(result["summary"]["pass"]))
    else:
        print("== %s: %d bp, %s ==" % (result["id"], result["length"], result["topology"]))
        print("errors=%d warnings=%d" % (result["summary"]["errors"],
                                         result["summary"]["warnings"]))
        for c in result["checks"]:
            tag = {"ok": "OK  ", "warning": "WARN", "error": "ERR "}[c["status"]]
            feat = (" [%s]" % c["feature"]) if "feature" in c else ""
            origin = (" [%s]" % c['origin']) if 'origin' in c else ''
            print("  %s %s%s%s: %s" % (tag, c["check"], feat, origin, c["detail"]))

    raise SystemExit(0 if result["summary"]["pass"] else 1)


if __name__ == "__main__":
    main()
