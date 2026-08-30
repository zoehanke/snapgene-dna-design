# -*- coding: utf-8 -*-
"""annotate.py - Automatic sequence annotation.

Finds ORFs (ATG..stop) across frames, optionally restriction sites,
and writes a feature table (JSON) or an annotated GenBank file.
"""
import argparse
import copy

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import CompoundLocation, FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

from sg_common import get_enzyme, jprint, load_seq, restriction_hits, topology

STOP = {"TAA", "TAG", "TGA"}


def find_orfs(seq, min_len=300, both_strands=False):
    """Find ORFs starting with ATG ending at in-frame stop. Returns (start0, end0, strand)."""
    orfs = []
    s = str(seq).upper()
    frames_to_scan = range(0, 3)
    if both_strands:
        frames_to_scan = range(0, 6)
    for frame in frames_to_scan:
        if frame < 3:
            strand = 1
            t = s
        else:
            strand = -1
            t = str(Seq(s).reverse_complement())
        f = frame % 3
        i = f
        n = len(t)
        while i + 2 < n:
            if t[i:i + 3] == "ATG":
                j = i + 3
                found_stop = False
                while j + 2 < n:
                    codon = t[j:j + 3]
                    if codon in STOP:
                        found_stop = True
                        break
                    j += 3
                if found_stop:
                    aa_len = (j - i) // 3
                    if aa_len * 3 >= min_len:
                        start0, end0 = i, j + 3
                        if strand == -1:
                            start0, end0 = n - end0, n - start0
                        orfs.append((start0, end0, strand))
                        i = j + 3
                        continue
                else:
                    break
            i += 3
    seen = set()
    out = []
    for o in orfs:
        if o not in seen:
            seen.add(o)
            out.append(o)
    out.sort()
    return out


def main():
    p = argparse.ArgumentParser(description="Annotate a sequence with ORFs and restriction sites")
    p.add_argument("source")
    p.add_argument("--min-orf", type=int, default=300, help="min ORF length in bp (default 300)")
    p.add_argument("--both-strands", action="store_true", help="scan all 6 frames")
    p.add_argument("--enzyme", default="", help="comma-separated enzymes to annotate (optional)")
    p.add_argument("--out-gb", help="write annotated GenBank to this path")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    record, _fmt = load_seq(args.source)
    seq = str(record.seq)

    orfs = find_orfs(seq, args.min_orf, args.both_strands)
    features = []
    for start0, end0, strand in orfs:
        coding = Seq(seq[start0:end0])
        if strand == -1:
            coding = coding.reverse_complement()
        features.append({
            "type": "CDS", "name": "ORF_%d_%d" % (start0 + 1, end0),
            "start": start0 + 1, "end": end0, "strand": strand,
            "translation": str(coding.translate()),
        })

    enzyme_hits = []
    if args.enzyme:
        for name in [e.strip() for e in args.enzyme.split(",") if e.strip()]:
            try:
                enz = get_enzyme(name)
            except ValueError as e:
                enzyme_hits.append({"enzyme": name, "error": str(e)})
                continue
            for hit in restriction_hits(
                    seq, enz, circular=(topology(record) == "circular")):
                enzyme_hits.append({"enzyme": name, **hit})

    result = {
        "length": len(seq),
        "orf_count": len(features),
        "min_orf_bp": args.min_orf,
        "features": features,
        "enzyme_hits": enzyme_hits,
    }

    if args.out_gb:
        annotated = copy.deepcopy(record)
        annotated.id = record.id or "annotated"
        annotated.name = record.name or "annotated"
        annotated.annotations["molecule_type"] = "DNA"
        annotated.annotations["topology"] = topology(record)
        for f in features:
            strand = f["strand"]
            annotated.features.append(SeqFeature(
                FeatureLocation(f["start"] - 1, f["end"], strand=strand),
                type=f["type"],
                qualifiers={
                    "label": [f["name"]],
                    "translation": [f["translation"].rstrip("*")],
                }))
        for hit in enzyme_hits:
            if "error" in hit:
                continue
            if hit["wraps_origin"]:
                location = CompoundLocation([
                    FeatureLocation(hit["start"] - 1, len(seq), strand=hit["strand"]),
                    FeatureLocation(0, hit["end"], strand=hit["strand"]),
                ], operator="join")
            else:
                location = FeatureLocation(
                    hit["start"] - 1, hit["end"], strand=hit["strand"])
            annotated.features.append(SeqFeature(
                location,
                type="misc_feature",
                qualifiers={
                    "label": [hit["enzyme"]],
                    "note": ["restriction enzyme recognition site"],
                },
            ))
        with open(args.out_gb, "w", encoding="utf-8") as fh:
            SeqIO.write(annotated, fh, "genbank")
        result["out_file"] = args.out_gb

    if args.json:
        jprint(result)
    else:
        print("ORFs found: %d" % len(features))
        for f in features:
            print("  CDS %s %d..%d strand=%d" % (f["name"], f["start"], f["end"], f["strand"]))
        for e in enzyme_hits:
            if "error" in e:
                print("  %s: %s" % (e["enzyme"], e["error"]))
            else:
                print("  %s @ %d" % (e["enzyme"], e["start"]))


if __name__ == "__main__":
    main()
