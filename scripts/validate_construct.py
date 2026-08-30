# -*- coding: utf-8 -*-
"""validate_construct.py - One-shot construct QC.

Checks a sequence file and reports problems with severity levels:
  error   - coordinate out of bounds, CDS frame error, premature stop
  warning - non-unique cutter, missing primers, unusual length
  ok      - check passed

Output: JSON (--json) or a readable report. Exit code 1 if any error.
"""
import argparse
import re

from Bio.Seq import Seq
from Bio.Data import CodonTable

from sg_common import enzyme_sites, features_to_dict, get_enzyme, jprint, load_seq, topology

# Enzymes commonly used as single-cutters (for unique-cutter check).
QC_ENZYMES = ["EcoRI", "BamHI", "HindIII", "XbaI", "NotI", "XhoI", "SalI", "PstI", "KpnI", "SacI"]


def _cds_translation(seq, start0, end0, strand):
    frag = seq[start0:end0]
    if strand == -1:
        frag = str(Seq(frag).reverse_complement())
    return str(Seq(frag).translate())


def validate(record):
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

    for feature, f in zip(record.features, features):
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

        # CDS frame + premature stop
        if f["type"] == "CDS" and start and end:
            coding = feature.extract(record.seq)
            qualifiers = feature.qualifiers or {}
            label_text = str(f.get("name") or "").strip().lower()
            partial_value = str(qualifiers.get("partial", [""])[0]).lower()
            is_partial = partial_value in ("true", "1", "yes", "partial")
            # Short fusion tags are CDS fragments by design, not standalone
            # open reading frames.  Their source records commonly omit
            # ``partial`` even though they cannot contain an independent ATG
            # and stop.  Recognize only the explicit, bounded tag vocabulary;
            # arbitrary CDS labels remain subject to the strict start/stop
            # gate.
            is_fusion_tag = label_text in {
                "v5 tag", "6xhis", "6x his", "his-tag", "his tag",
                "ha tag", "flag tag", "myc tag",
            } and len(coding) <= 120
            # Public plasmid records often describe a deliberately truncated
            # CDS as a "fragment" in product/gene/note without adding the
            # GenBank ``partial`` qualifier (for example lacZalpha fragments
            # in TA vectors).  Treat that explicit annotation as partial; do
            # not waive checks for arbitrary short or oddly named CDSs.
            fragment_text = " ".join(
                str(value)
                for key in ("product", "gene", "note", "label")
                for value in (qualifiers.get(key, [])
                              if isinstance(qualifiers.get(key, []), list)
                              else [qualifiers.get(key, [])])
            ).lower()
            is_annotated_fragment = "fragment" in fragment_text
            is_partial = is_partial or is_fusion_tag or is_annotated_fragment
            is_pseudo = "pseudo" in qualifiers or str(
                qualifiers.get("pseudogene", [""])[0]).lower() in (
                    "true", "1", "yes")
            try:
                codon_start = int(qualifiers.get("codon_start", [1])[0])
            except (TypeError, ValueError):
                codon_start = 1
            coding = coding[max(0, codon_start - 1):]
            span = len(coding)
            if span % 3 != 0:
                checks.append({
                    "check": "cds_frame", "status": "error", "feature": name,
                    "detail": "%s extracted length %d not multiple of 3"
                    % (f["type"], span)})
            else:
                try:
                    table = int(qualifiers.get("transl_table", [1])[0])
                except (TypeError, ValueError):
                    table = 1
                aa = str(coding.translate(table=table))
                expected_translation = qualifiers.get("translation")
                if expected_translation:
                    # GenBank readers may preserve a line-wrap separator as
                    # a comma (and may split a qualifier into several values).
                    # A translated protein itself cannot contain commas, so
                    # canonicalize only whitespace/comma separators and join
                    # all values before comparing with the deterministic
                    # translation.  Other punctuation remains visible and
                    # therefore still fails closed as a mismatch.
                    if isinstance(expected_translation, (list, tuple)):
                        expected_translation = "".join(
                            str(value) for value in expected_translation)
                    else:
                        expected_translation = str(expected_translation)
                    expected_translation = re.sub(
                        r"[\\s,]+", "", expected_translation)
                    if expected_translation != aa:
                        checks.append({
                            "check": "cds_translation_mismatch",
                            "status": "error", "feature": name,
                            "detail": "qualifier translation %s != extracted translation %s"
                            % (expected_translation, aa),
                        })
                if not is_partial and not is_pseudo:
                    try:
                        start_codons = set(
                            CodonTable.unambiguous_dna_by_id[table].start_codons)
                    except (KeyError, AttributeError):
                        start_codons = {"ATG"}
                    if str(coding[:3]).upper() not in start_codons:
                        checks.append({
                            "check": "cds_start_codon", "status": "error",
                            "feature": name,
                            "detail": "complete CDS starts with %s, expected one of %s"
                            % (str(coding[:3]).upper(),
                               ",".join(sorted(start_codons))),
                        })
                elif is_partial or is_pseudo:
                    checks.append({
                        "check": "cds_start_codon", "status": "ok",
                        "feature": name,
                        "detail": "start-codon requirement waived by partial/pseudo qualifier",
                    })
                if "*" in aa[:-1]:
                    checks.append({
                        "check": "cds_premature_stop", "status": "error", "feature": name,
                        "detail": "internal stop codon at aa position %d"
                        % (aa.index("*") + 1)})
                elif aa.endswith("*"):
                    checks.append({"check": "cds_frame", "status": "ok",
                                   "feature": name, "detail": "in-frame, terminal stop"})
                elif is_partial or is_pseudo:
                    checks.append({"check": "cds_frame", "status": "warning",
                                   "feature": name, "detail": "no stop codon (may be partial)"})
                else:
                    checks.append({
                        "check": "cds_stop_codon", "status": "error",
                        "feature": name,
                        "detail": "complete CDS lacks a terminal stop codon",
                    })

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

    errors = [c for c in checks if c["status"] == "error"]
    warnings = [c for c in checks if c["status"] == "warning"]
    return {
        "id": record.id,
        "length": n,
        "topology": topo,
        "summary": {"errors": len(errors), "warnings": len(warnings),
                    "pass": len(errors) == 0},
        "checks": checks,
    }


def main():
    p = argparse.ArgumentParser(description="Validate a construct (one-shot QC)")
    p.add_argument("source")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    record, _fmt = load_seq(args.source)
    result = validate(record)

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
            print("  %s %s%s: %s" % (tag, c["check"], feat, c["detail"]))

    raise SystemExit(0 if result["summary"]["pass"] else 1)


if __name__ == "__main__":
    main()
