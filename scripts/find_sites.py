# -*- coding: utf-8 -*-
"""find_sites.py - Restriction enzyme analysis.

- List recognition-site starts and top-strand cut coordinates (1-based).
- Optionally simulate a digest (fragment lengths).
"""
import argparse

from sg_common import (
    enzyme_sites, get_enzyme, jprint, load_seq, restriction_hits, topology,
)

COMMON_ENZYMES = [
    "EcoRI", "BamHI", "HindIII", "XbaI", "SalI", "PstI", "NdeI", "NcoI",
    "KpnI", "SacI", "SmaI", "XhoI", "SpeI", "NotI", "AgeI", "BglII",
    "PvuII", "SphI", "EcoRV", "SacII", "MfeI", "AvrII", "BsaI", "BbsI",
    "BsmBI", "BtgZI", "AarI", "SapI", "HpaI", "ClaI",
]


def enzyme_info(enzyme):
    """Recognition site and overhang metadata for an enzyme."""
    try:
        return {
            "recognition_site": enzyme.site,
            "overhang": enzyme.ovhg,
            "forward_cut_5p": enzyme.fst5,
            "forward_cut_3p": enzyme.fst3,
        }
    except Exception:
        return {
            "recognition_site": "", "overhang": "",
            "forward_cut_5p": "", "forward_cut_3p": "",
        }


def digest_report(seq, topo, enzyme_names):
    """Digest at Bio.Restriction top-strand cut boundaries."""
    cuts = []
    for name in enzyme_names:
        try:
            enz = get_enzyme(name)
        except ValueError:
            continue
        for pos in enzyme_sites(seq, enz, circular=(topo == "circular")):
            cuts.append(pos - 1)  # first base after cut -> 0-based boundary
    if not cuts:
        return {"fragments": [len(seq)], "note": "no sites found", "cut_count": 0}
    cuts = sorted(set(cuts))
    n = len(seq)
    if topo == "circular":
        bounds = cuts + [cuts[0] + n]
        frags = [bounds[i + 1] - bounds[i] for i in range(len(cuts))]
    else:
        bounds = [0] + cuts + [n]
        frags = [bounds[i + 1] - bounds[i] for i in range(len(bounds) - 1)]
    frags = [f for f in frags if f > 0]
    return {"fragments": sorted(frags, reverse=True), "cut_count": len(cuts)}


def main():
    p = argparse.ArgumentParser(description="Restriction enzyme site analysis")
    p.add_argument("source")
    p.add_argument("--enzyme", default=",".join(COMMON_ENZYMES),
                   help="comma-separated enzyme names (default: common set)")
    p.add_argument("--digest", action="store_true",
                   help="simulate digest and report fragment lengths")
    p.add_argument("--topology", choices=["linear", "circular"], default=None,
                   help="override topology metadata (raw/FASTA defaults linear)")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    record, _fmt = load_seq(args.source)
    seq = str(record.seq)
    topo = args.topology or topology(record)

    names = [e.strip() for e in args.enzyme.split(",") if e.strip()]
    results = []
    for name in names:
        try:
            enz = get_enzyme(name)
        except ValueError as e:
            results.append({"enzyme": name, "error": str(e)})
            continue
        hits = restriction_hits(seq, enz, circular=(topo == "circular"))
        cuts = enzyme_sites(seq, enz, circular=(topo == "circular"))
        info = enzyme_info(enz)
        results.append({
            "enzyme": name,
            "recognition_site": info["recognition_site"],
            "overhang": info["overhang"],
            "cut_geometry": {
                "forward_top_offset": info["forward_cut_5p"],
                "forward_bottom_offset_from_site_end": info["forward_cut_3p"],
                "coordinate_system": "0-based-boundaries",
            },
            "site_count": len(hits),
            "sites_1based": [h["start"] for h in hits[:200]],
            "hits": hits[:200],
            "top_cut_first_bases_1based": cuts[:200],
        })

    if args.json:
        out = {"topology": topo, "length": len(seq), "results": results}
        if args.digest:
            out["digest"] = digest_report(seq, topo, names)
        jprint(out)
        return

    for r in results:
        if "error" in r:
            print("%s: %s" % (r["enzyme"], r["error"]))
            continue
        print("%s (%s, %s): %d sites" % (
            r["enzyme"], r["recognition_site"], r["overhang"], r["site_count"]))
        if r["sites_1based"]:
            print("   recognition starts:", ", ".join(str(x) for x in r["sites_1based"][:40]))
            print("   top cuts before bases:", ", ".join(
                str(x) for x in r["top_cut_first_bases_1based"][:40]))
    if args.digest:
        print("--- digest simulation ---")
        d = digest_report(seq, topo, names)
        print("fragments (%d cuts):" % d["cut_count"], d["fragments"])


if __name__ == "__main__":
    main()
