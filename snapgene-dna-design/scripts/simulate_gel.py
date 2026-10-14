# -*- coding: utf-8 -*-
"""simulate_gel.py - Agarose gel electrophoresis simulation.

Given fragment sizes (bp), estimate migration distance using an empirical
log-linear model and print an ASCII band diagram. Useful for previewing a
digest or PCR product before running the actual gel.

Migration model: distance = L * (1 - (log(size) - log(min)) /
(log(max) - log(min)))  — smaller fragments migrate further.
"""
import argparse
import math

from sg_common import jprint

# Common ladder markers (bp), NEB 1 kb / 100 bp style.
MARKERS = {
    "1kb": [10000, 8000, 6000, 5000, 4000, 3000, 2000, 1500, 1000, 500],
    "100bp": [1500, 1000, 900, 800, 700, 600, 500, 400, 300, 200, 100],
    "1kb-plus": [10000, 8000, 6000, 5000, 4000, 3000, 2000, 1500, 1000, 700, 500, 400, 300, 200, 100],
}


def migration(size, lane_length=100, min_size=50, max_size=10000):
    """Migration distance (0..lane_length); smaller fragments migrate further."""
    lo, hi = math.log(min_size), math.log(max_size)
    x = math.log(max(size, 1))
    frac = (x - lo) / (hi - lo)  # 0 for small, 1 for large
    return lane_length * (1 - frac)


def band_row(lane_length, dist, symbol="#", width=1):
    row = [" "] * lane_length
    d = int(round(dist))
    for w in range(width):
        pos = min(lane_length - 1, d + w)
        if 0 <= pos < lane_length:
            row[pos] = symbol
    return "".join(row)


def main():
    p = argparse.ArgumentParser(description="Simulate agarose gel migration")
    p.add_argument("--fragments", required=True,
                   help="comma-separated fragment sizes (bp)")
    p.add_argument("--marker", choices=list(MARKERS.keys()), default="1kb",
                   help="ladder to display")
    p.add_argument("--lane-length", type=int, default=80)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    sizes = [int(x) for x in args.fragments.split(",") if x.strip()]
    ladder = MARKERS[args.marker]

    sample_dists = [migration(s, args.lane_length) for s in sizes]
    ladder_dists = [migration(s, args.lane_length) for s in ladder]

    if args.json:
        jprint({
            "fragments": [{"size": s, "migration": round(d, 1)} for s, d in zip(sizes, sample_dists)],
            "marker": args.marker,
            "ladder": [{"size": s, "migration": round(d, 1)} for s, d in zip(ladder, ladder_dists)],
        })
        return

    # ASCII lanes
    lane_sample = band_row(args.lane_length, max(sample_dists) if sample_dists else 0)
    # ladder: draw each band
    lane_ladder = [" "] * args.lane_length
    for d in ladder_dists:
        pos = int(round(d))
        if 0 <= pos < args.lane_length:
            lane_ladder[pos] = "#"
    lane_ladder = "".join(lane_ladder)

    print("Marker %-8s | Sample" % args.marker)
    print("%s | %s" % (lane_ladder, lane_sample))
    print("well %s → migration direction" % (" " * (args.lane_length - 12)))
    print("\nSample fragments:")
    for s, d in zip(sizes, sample_dists):
        print("  %5d bp  →  position %.0f" % (s, d))
    print("\nLadder (%s):" % args.marker)
    for s, d in zip(ladder, ladder_dists):
        print("  %5d bp" % s)


if __name__ == "__main__":
    main()
