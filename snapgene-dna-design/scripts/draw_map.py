# -*- coding: utf-8 -*-
"""draw_map.py - Pretty SVG plasmid map generation.

Draws a circular (or linear) plasmid map with features colored by type,
leader-line labels (de-overlapped), a center title, and a legend.
Supports light (default) and dark themes.

Usage:
  draw_map.py plasmid.dna --out map.svg [--theme light|dark]
"""
import argparse
import math

from sg_common import features_to_dict, jprint, load_seq, topology

# Feature-type color palette (light theme). Keys are matched case-insensitively.
TYPE_COLORS_LIGHT = {
    "CDS": "#3B82F6", "gene": "#3B82F6", "promoter": "#10B981",
    "terminator": "#F2745B", "rep_origin": "#8B5CF6",
    "primer_bind": "#F0A020", "protein_bind": "#14B8A6",
    "misc_feature": "#9CA3AF", "source": "#C7CBD4",
}
TYPE_COLORS_DARK = {
    "CDS": "#60A5FA", "gene": "#60A5FA", "promoter": "#34D399",
    "terminator": "#F87171", "rep_origin": "#A78BFA",
    "primer_bind": "#FBBF24", "protein_bind": "#2DD4BF",
    "misc_feature": "#9CA3AF", "source": "#4B5563",
}
DEFAULT_COLOR_LIGHT = "#9CA3AF"
DEFAULT_COLOR_DARK = "#6B7280"

THEME = {
    "light": {
        "bg": "#FFFFFF", "text": "#111827", "muted": "#6B7280",
        "backbone": "#D1D5DB", "colors": TYPE_COLORS_LIGHT, "default": DEFAULT_COLOR_LIGHT,
    },
    "dark": {
        "bg": "#171717", "text": "#E5E5E5", "muted": "#9CA3AF",
        "backbone": "#3F3F46", "colors": TYPE_COLORS_DARK, "default": DEFAULT_COLOR_DARK,
    },
}


def _color(ftype, theme):
    return theme["colors"].get(ftype, theme["default"])


def _pt(cx, cy, r, t):
    """Point at fraction t around the circle, from 12 o'clock, clockwise."""
    th = 2 * math.pi * t
    return cx + r * math.sin(th), cy - r * math.cos(th)


def _arc(cx, cy, t1, t2, r):
    x1, y1 = _pt(cx, cy, r, t1)
    x2, y2 = _pt(cx, cy, r, t2)
    large = 1 if (t2 - t1) > 0.5 else 0
    return "M %.1f %.1f A %.1f %.1f 0 %d 1 %.1f %.1f" % (x1, y1, r, r, large, x2, y2)


def _esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def draw_circular(record, theme_name="light", size=820):
    theme = THEME[theme_name]
    n = len(record.seq) or 1
    cx = cy = size / 2
    r = size * 0.29
    r_label = r + 46
    feats = features_to_dict(record)
    svg = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">'
        % (size, size, size, size),
        '<rect width="100%%" height="100%%" fill="%s"/>' % theme["bg"],
        '<circle cx="%.1f" cy="%.1f" r="%.1f" fill="none" stroke="%s" stroke-width="2"/>'
        % (cx, cy, r, theme["backbone"]),
    ]
    # feature arcs
    for f in feats:
        segs = f.get("segments", [{"start": f["start"], "end": f["end"]}])
        color = _color(f["type"], theme)
        for s in segs:
            if s["start"] >= s["end"]:
                continue
            t1 = (s["start"] - 1) / n
            t2 = s["end"] / n
            # small visual gap between adjacent features
            g1 = t1 + 0.0006
            g2 = t2 - 0.0006
            if g2 <= g1:
                continue
            svg.append('<path d="%s" stroke="%s" stroke-width="18" fill="none"/>'
                       % (_arc(cx, cy, g1, g2, r), color))
    # leader lines + labels (de-overlap by min angle gap)
    candidates = []
    for f in feats:
        if f["type"] == "source":
            continue
        segs = f.get("segments", [{"start": f["start"], "end": f["end"]}])
        for s in segs:
            if s["end"] - s["start"] >= max(40, n * 0.008):
                mid_deg = ((s["start"] + s["end"]) / 2) / n * 360
                candidates.append((mid_deg, f["name"]))
    candidates.sort()
    selected = []
    last = -360
    MIN_GAP = 17
    for deg, name in candidates:
        if deg - last >= MIN_GAP:
            selected.append((deg, name))
            last = deg
    # wrap-around collision
    if len(selected) > 1 and (selected[0][0] + 360 - selected[-1][0]) < MIN_GAP:
        selected.pop()
    for deg, name in selected:
        t = deg / 360
        x1, y1 = _pt(cx, cy, r + 11, t)
        x2, y2 = _pt(cx, cy, r_label - 6, t)
        svg.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="1"/>'
                   % (x1, y1, x2, y2, theme["muted"]))
        lx, ly = _pt(cx, cy, r_label, t)
        anchor = "start" if lx > cx + 30 else ("end" if lx < cx - 30 else "middle")
        svg.append('<text x="%.1f" y="%.1f" text-anchor="%s" fill="%s" font-size="12" '
                   'font-family="sans-serif">%s</text>'
                   % (lx, ly, anchor, theme["text"], _esc(name[:22])))
    # center title
    svg.append('<text x="%.1f" y="%.1f" text-anchor="middle" fill="%s" font-size="17" '
               'font-weight="600" font-family="sans-serif">%s</text>'
               % (cx, cy - 6, theme["text"], _esc(record.name or record.id or "plasmid")))
    svg.append('<text x="%.1f" y="%.1f" text-anchor="middle" fill="%s" font-size="13" '
               'font-family="sans-serif">%d bp · %s</text>'
               % (cx, cy + 16, theme["muted"], n, topology(record)))
    # legend (types actually used)
    used_types = []
    for f in feats:
        if f["type"] not in used_types and f["type"] != "source":
            used_types.append(f["type"])
    if used_types:
        lx_start = cx - (len(used_types) * 90) / 2
        ly = size - 30
        for i, t in enumerate(used_types):
            x = lx_start + i * 90
            svg.append('<rect x="%.1f" y="%.1f" width="12" height="12" rx="2" fill="%s"/>'
                       % (x, ly - 10, _color(t, theme)))
            svg.append('<text x="%.1f" y="%.1f" fill="%s" font-size="11" '
                       'font-family="sans-serif">%s</text>'
                       % (x + 16, ly, theme["muted"], _esc(t)))
    svg.append("</svg>")
    return "\n".join(svg)


def draw_linear(record, theme_name="light", size=900, height=260):
    theme = THEME[theme_name]
    n = len(record.seq) or 1
    feats = features_to_dict(record)
    x0, x1 = 70, size - 50
    y_mid = 120
    svg = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">'
        % (size, height, size, height),
        '<rect width="100%%" height="100%%" fill="%s"/>' % theme["bg"],
        '<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="4" '
        'stroke-linecap="round"/>' % (x0, y_mid, x1, y_mid, theme["backbone"]),
    ]
    # scale ticks every 500 bp
    step = 500
    for bp in range(0, n + 1, step):
        x = x0 + bp / n * (x1 - x0)
        svg.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="%s" stroke-width="1"/>'
                   % (x, y_mid - 6, x, y_mid + 6, theme["muted"]))
        svg.append('<text x="%.1f" y="%d" text-anchor="middle" fill="%s" font-size="10" '
                   'font-family="sans-serif">%d</text>' % (x, y_mid + 22, theme["muted"], bp))
    # features, alternating label rows
    row = 0
    for f in feats:
        if f["type"] == "source":
            continue
        segs = f.get("segments", [{"start": f["start"], "end": f["end"]}])
        color = _color(f["type"], theme)
        for s in segs:
            if s["start"] >= s["end"]:
                continue
            sx = x0 + (s["start"] - 1) / n * (x1 - x0)
            ex = x0 + s["end"] / n * (x1 - x0)
            svg.append('<rect x="%.1f" y="%d" width="%.1f" height="16" fill="%s" rx="3"/>'
                       % (sx, y_mid - 8, max(ex - sx, 2), color))
            # label only if wide enough
            if ex - sx >= 34:
                ly = y_mid - 24 if row % 2 == 0 else y_mid + 40
                svg.append('<text x="%.1f" y="%d" text-anchor="middle" fill="%s" font-size="11" '
                           'font-family="sans-serif">%s</text>'
                           % ((sx + ex) / 2, ly, theme["text"], _esc(f["name"][:18])))
                row += 1
    # title
    svg.append('<text x="%d" y="28" text-anchor="middle" fill="%s" font-size="15" '
               'font-weight="600" font-family="sans-serif">%s — %d bp, %s</text>'
               % ((x0 + x1) / 2, theme["text"], _esc(record.name or record.id or "plasmid"),
                  n, topology(record)))
    svg.append("</svg>")
    return "\n".join(svg)


def main():
    p = argparse.ArgumentParser(description="Draw a plasmid map (SVG)")
    p.add_argument("source")
    p.add_argument("--out", required=True, help="output SVG path")
    p.add_argument("--theme", choices=["light", "dark"], default="light")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    record, _fmt = load_seq(args.source)
    topo = topology(record)
    svg = draw_circular(record, args.theme) if topo == "circular" else draw_linear(record, args.theme)

    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(svg)

    result = {
        "out_file": args.out,
        "topology": topo,
        "length": len(record.seq),
        "feature_count": len(record.features),
        "theme": args.theme,
    }
    if args.json:
        jprint(result)
    else:
        print("wrote %s (%s, %d bp, %d features, %s theme)" % (
            args.out, topo, len(record.seq), len(record.features), args.theme))


if __name__ == "__main__":
    main()
