# -*- coding: utf-8 -*-
"""methylation.py - Experimental methylation-motif overlap hints.

Scans a sequence for common prokaryotic methylation motifs and reports which
restriction enzyme cut sites would be blocked (or affected) by methylation.

Motifs:
  dam  GATC        (E. coli Dam methylase)
  dcm  CCWGG       (E. coli Dcm methylase, W = A/T)
  EcoKI AACN6GTGC  (EcoKI methylase)

This script does not contain a curated enzyme-by-methylase sensitivity
database. It reports candidate motif overlaps only and never labels a site as
blocked. Confirm sensitivity with the enzyme manufacturer's current data.
"""
import argparse
import re

from sg_common import get_enzyme, jprint, load_seq, restriction_hits, topology

# (name, motif as regex on the FORWARD strand; complement handled by scanning both)
METHYLATION = [
    ("dam", "GATC"),
    ("dcm", "CC[AT]GG"),
    ("ecoki", "AAC[ACGT]{6}GTGC"),
]


def find_motif(seq, pattern):
    """1-based start positions of a motif (forward strand, regex)."""
    hits = []
    for m in re.finditer(pattern, str(seq).upper()):
        hits.append(m.start() + 1)
    return hits


def site_overlaps_motif(site_start, site_len, motif_start, motif_len):
    """Whether a restriction site [site_start, +site_len) overlaps a motif."""
    return not (site_start + site_len <= motif_start or
                motif_start + motif_len <= site_start)


def biopython_methylable(enzyme):
    """Return Biopython's coarse methylatable flag when available."""
    try:
        return bool(enzyme.is_methylable())
    except Exception:
        return None


def main():
    p = argparse.ArgumentParser(description="Methylation sensitivity analysis")
    p.add_argument("source")
    p.add_argument("--enzyme", default="EcoRI,BamHI,HindIII,XbaI,NotI,ClaI,PvuII",
                   help="comma-separated enzymes (default: common set)")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    record, _fmt = load_seq(args.source)
    seq = str(record.seq).upper()

    # scan methylation motifs
    motifs = []
    for name, pattern in METHYLATION:
        hits = find_motif(seq, pattern)
        if hits:
            motifs.append({"methylation": name, "motif": pattern,
                           "count": len(hits), "sites_1based": hits[:100]})

    # per enzyme: blocked sites
    results = []
    for enz_name in [e.strip() for e in args.enzyme.split(",") if e.strip()]:
        try:
            enz = get_enzyme(enz_name)
        except ValueError as e:
            results.append({"enzyme": enz_name, "error": str(e)})
            continue
        site_len = len(enz.site)
        hits = restriction_hits(
            seq, enz, circular=(topology(record) == "circular"))
        overlaps = []
        for hit in hits:
            if hit["wraps_origin"]:
                continue  # deferred until circular interval support is complete
            s = hit["start"]
            for name, pattern in METHYLATION:
                for match in re.finditer(pattern, seq):
                    mpos = match.start() + 1
                    if site_overlaps_motif(s, site_len, mpos, len(match.group(0))):
                        overlaps.append({
                            "site_start": s,
                            "methylation_motif": name,
                            "motif_start": mpos,
                            "status": "candidate_overlap_only",
                        })
                        break
        results.append({
            "enzyme": enz_name,
            "recognition_site": enz.site,
            "sensitivity": {"dam": None, "dcm": None, "ecoki": None},
            "biopython_methylable": biopython_methylable(enz),
            "site_count": len(hits),
            "sites_1based": [h["start"] for h in hits[:50]],
            "potential_motif_overlaps": overlaps,
            "blocked_sites": [],
        })

    out = {
        "experimental": True,
        "warning": (
            "Candidate motif overlaps only; methylase-specific enzyme sensitivity "
            "is unknown and blocked sites are not inferred"
        ),
        "length": len(seq),
        "topology": topology(record),
        "methylation_motifs": motifs,
        "enzymes": results,
    }

    if args.json:
        jprint(out)
    else:
        print("methylation motifs found:")
        for m in motifs:
            print("  %s (%s): %d site(s) %s" % (
                m["methylation"], m["motif"], m["count"],
                m["sites_1based"][:10]))
        print("enzymes:")
        for r in results:
            if "error" in r:
                print("  %s: %s" % (r["enzyme"], r["error"]))
                continue
            print("  %s (%s): %d sites, methylation sensitivity=unknown" % (
                r["enzyme"], r["recognition_site"], r["site_count"]))
            if r["potential_motif_overlaps"]:
                print("    candidate overlaps:", r["potential_motif_overlaps"])


if __name__ == "__main__":
    main()
