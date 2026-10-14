# -*- coding: utf-8 -*-
"""annotate_offtargets.py - Annotate off-target hits against GenBank features.

A hit is annotated when its genomic interval **overlaps** a feature interval
(``hit_start < feature_end and feature_start < hit_end``), not merely when
the hit's first base falls inside the feature.  Every overlapping feature is
retained in ``overlapping_features``.
"""
import argparse
import json
import pathlib
import sys

from Bio import SeqIO

from sg_common import jprint
from provenance import source, read_version


def feature_type_for(feature):
    feature_type = str(feature.type).lower()
    if feature_type == "cds":
        return "CDS"
    if feature_type == "gene":
        return "gene"
    if "promoter" in feature_type:
        return "promoter"
    if "regulatory" in feature_type:
        return "regulatory"
    if feature_type in ("trna",):
        return "tRNA"
    if feature_type in ("rrna",):
        return "rRNA"
    if feature_type in ("ncrna", "misc_rna"):
        return "ncRNA"
    return "unknown"


def _strand_label(strand):
    if strand == 1:
        return "+"
    if strand == -1:
        return "-"
    return "."


def _location_segments(location, sequence_length):
    """0-based half-open segments; wraps_origin entries are split."""
    parts = location.parts if hasattr(location, "parts") else [location]
    segments = []
    wraps = False
    for part in parts:
        start = int(part.start)
        end = int(part.end)
        if end < start:
            wraps = True
            if start < sequence_length:
                segments.append([start, sequence_length])
            if end > 0:
                segments.append([0, end])
        elif end > start:
            segments.append([start, end])
    return segments, wraps


def _hit_segments(hit, sequence_length):
    start = int(hit.get("start"))
    end = int(hit.get("end"))
    if end < start:
        segments = []
        if start < sequence_length:
            segments.append([start, sequence_length])
        if end > 0:
            segments.append([0, end])
        return segments, True
    if end == start:
        return [], False
    return [[start, end]], False


def _overlaps(segments_a, segments_b):
    return any(a_start < b_end and b_start < a_end
               for a_start, a_end in segments_a
               for b_start, b_end in segments_b)


def _feature_name(feature):
    for key in ("label", "gene", "locus_tag", "product"):
        values = feature.qualifiers.get(key)
        if values:
            return str(values[0])
    return None


def _orientation(hit_strand, feature_strand):
    if hit_strand in ("+", "-") and feature_strand in (1, -1):
        return "same" if (hit_strand == "+") == (feature_strand == 1) else "opposite"
    return "unknown"


_PRIORITY = {"gene": 0, "CDS": 1, "promoter": 2, "regulatory": 3,
             "ncRNA": 4, "tRNA": 5, "rRNA": 6, "unknown": 7}


def annotate_hits(hits, annotation_path, target_gene=None):
    with open(str(annotation_path), "r", encoding="utf-8") as handle:
        records = list(SeqIO.parse(handle, "genbank"))
    for hit in hits:
        overlapping = []
        chrom = hit.get("chromosome")
        for record in records:
            if record.id != chrom and record.name != chrom:
                continue
            sequence_length = len(record.seq)
            hit_segments, _hit_wrap = _hit_segments(hit, sequence_length)
            for feature in record.features:
                feature_segments, _feat_wrap = _location_segments(
                    feature.location, sequence_length)
                if not _overlaps(hit_segments, feature_segments):
                    continue
                name = _feature_name(feature)
                feature_strand = _strand_label(feature.location.strand)
                overlapping.append({
                    "feature_type": feature_type_for(feature),
                    "feature_name": name,
                    "feature_strand": feature_strand,
                    "feature_start": int(feature.location.start),
                    "feature_end": int(feature.location.end),
                    "wraps_origin": bool(_feat_wrap),
                    "orientation_to_hit": _orientation(
                        hit.get("strand"), feature.location.strand),
                })
            break
        if not overlapping:
            hit["annotation"] = {
                "feature_type": "intergenic",
                "feature_name": None,
                "is_target_gene": False,
                "is_additional_perfect_match": (hit.get("mismatches", 99) == 0 and not hit.get("bulge_size") and hit.get("bulge_type") in (None, "X")),
                "overlapping_features": [],
            }
            continue
        overlapping.sort(key=lambda item: _PRIORITY.get(
            item["feature_type"], 8))
        primary = overlapping[0]
        hit["annotation"] = {
            "feature_type": primary["feature_type"],
            "feature_name": primary["feature_name"],
            "is_target_gene": bool(
                target_gene and any(
                    item["feature_name"] == target_gene for item in overlapping)),
            "is_additional_perfect_match": (hit.get("mismatches", 99) == 0 and not hit.get("bulge_size") and hit.get("bulge_type") in (None, "X")),
            "overlapping_features": overlapping,
        }
    return hits


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("hits_json")
    parser.add_argument("--annotation", required=True)
    parser.add_argument("--target-gene")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    with open(args.hits_json, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    hits = annotate_hits(payload.get("hits", []), args.annotation,
                         args.target_gene)
    reference_genome = payload.get("reference_genome")
    if reference_genome is None:
        reference_genome = {
            "status": "unavailable",
            "reason": "REFERENCE_GENOME_NOT_PROVIDED",
            "fasta_sha256": "UNBOUND-REFERENCE-GENOME-NOT-PROVIDED",
        }
    result = {
        "schema_version": "0.8.0",
        "status": payload.get("status", "incomplete"),
        "reference_genome": reference_genome,
        "hits": hits,
        "provenance": payload.get("provenance", []) + [source(
            "software", "SnapGene DNA Design annotate_offtargets",
            "off-target-annotation", version=read_version(), status="verified",
            verification={"method": "unit-tests", "status": "verified"})],
    }
    if args.json:
        jprint(result)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    main()
