# -*- coding: utf-8 -*-
"""generate_design_report.py - Unified design report (JSON + HTML) (v0.6).

Collects design artifacts produced by the pipeline into one design report:

* ``--design-json`` files from ``design_gene_replacement.py`` (or any
  dict-style design JSON, including primer designs);
* ``--assembly-json`` files from the cloning simulators
  (``simulate_cloning.py`` / ``simulate_advanced.py`` / ``golden_gate.py``);
* ``--product`` GenBank/FASTA/DNA files (features are serialized into the
  report).
* ``--compatibility-json`` reports from ``snapgene_compatibility.py`` or a
  delivery bundle.

Outputs:

* ``--out``        standalone HTML report (default ``design-report.html``)
* ``--report-json`` machine-readable unified report JSON (default
  ``design-report.json``)

The HTML report is fully self-contained (inline CSS, no external assets) and
contains overview, sequence, features, primers, assemblies, QC and risk
sections.

Usage::

    python -X utf8 scripts/generate_design_report.py \\
        --title "CDC15 -> Hyg replacement" \\
        --design-json design.json \\
        --assembly-json assembly.json \\
        --product product.gb \\
        --out design-report.html --report-json design-report.json --json
"""
import argparse
import datetime
import html
import json
import pathlib
import sys

from sg_common import features_to_dict, jprint, load_seq, topology


def _read_json(path):
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, dict) and "data" in payload and \
            isinstance(payload.get("data"), dict):
        return payload["data"]
    return payload


def _product_section(path):
    record, _fmt = load_seq(str(path))
    return {
        "file": str(path),
        "name": record.name or record.id,
        "length": len(record.seq),
        "topology": topology(record),
        "sequence": str(record.seq),
        "features": features_to_dict(record),
    }


def build_report(title, design_jsons, assembly_jsons, products,
                 compatibility_jsons=None):
    compatibility_jsons = compatibility_jsons or []
    sections = []
    primers = []
    assemblies = []
    qc_checks = []
    risks = []
    notes = []
    compatibility = []

    for path in design_jsons:
        data = _read_json(path)
        sections.append({"source": "design", "file": str(path), "data": data})
        for side in ("forward", "reverse"):
            primer = data.get("primers", {}).get(side) if isinstance(
                data.get("primers"), dict) else data.get(side)
            if isinstance(primer, dict) and primer.get("sequence"):
                primers.append({
                    "side": side,
                    "sequence": primer["sequence"],
                    "binding": primer.get("binding", ""),
                    "overlap": primer.get("overlap", primer.get("overlap_tail", "")),
                    "tm": primer.get("tm"),
                    "gc": primer.get("gc"),
                    "length": primer.get("length", len(primer.get("sequence", ""))),
                    "source": str(path),
                })
        for risk in data.get("qc", {}).get("risks", []) if isinstance(
                data.get("qc"), dict) else data.get("risks", []):
            risks.append({"source": str(path), "risk": risk})
        for note in data.get("notes", []):
            notes.append({"source": str(path), "note": note})

    for path in assembly_jsons:
        data = _read_json(path)
        assemblies.append({
            "source": str(path),
            "method": data.get("method"),
            "experimental": data.get("experimental"),
            "product_length": data.get("product_length"),
            "topology": data.get("topology"),
            "junction_count": len(data.get("junctions", [])),
            "feature_count": data.get("feature_count"),
            "warnings": data.get("warnings", []),
        })
        for warning in data.get("warnings", []):
            qc_checks.append({"source": str(path), "level": "warning",
                              "message": str(warning)})

    product_sections = [_product_section(p) for p in products]
    for product in product_sections:
        sections.append({"source": "product", "file": product["file"],
                         "data": product})
        for feature in product["features"]:
            if feature["type"] == "CDS":
                qc_checks.append({
                    "source": product["file"], "level": "info",
                    "message": "CDS %s %d..%d strand=%d"
                               % (feature["name"], feature["start"],
                                  feature["end"], feature["strand"])})

    for path in compatibility_jsons:
        data = _read_json(path)
        compatibility.append({"source": str(path), "data": data})
        for fmt, assessment in data.get("formats", {}).items():
            for finding in assessment.get("findings", []):
                risks.append({
                    "source": str(path),
                    "risk": "%s [%s] %s: %s" % (
                        fmt, finding.get("severity", "unknown"),
                        finding.get("code", "UNCLASSIFIED"),
                        finding.get("message", "")),
                })

    return {
        "title": title,
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "schema_version": "0.5.0",
        "inputs": {
            "design_jsons": [str(p) for p in design_jsons],
            "assembly_jsons": [str(p) for p in assembly_jsons],
            "products": [str(p) for p in products],
            "compatibility_jsons": [str(p) for p in compatibility_jsons],
        },
        "summary": {
            "designs": len(sections),
            "primers": len(primers),
            "assemblies": len(assemblies),
            "product_count": len(product_sections),
            "qc_checks": len(qc_checks),
            "risks": len(risks),
            "compatibility_reports": len(compatibility),
        },
        "primers": primers,
        "assemblies": assemblies,
        "qc": qc_checks,
        "risks": risks,
        "notes": notes,
        "compatibility": compatibility,
        "sections": sections,
    }


def render_html(report):
    def esc(value):
        return html.escape(str(value))

    rows = []
    for primer in report["primers"]:
        rows.append(
            "<tr><td>%s</td><td class='mono'>%s</td><td class='mono'>%s</td>"
            "<td class='mono'>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
            % (esc(primer["side"]), esc(primer["sequence"]),
               esc(primer.get("binding", "")), esc(primer.get("overlap", "")),
               esc(primer.get("tm", "")), esc(primer.get("gc", "")),
               esc(primer.get("length", ""))))
    primers_html = ("<table><tr><th>side</th><th>full sequence</th><th>binding</th>"
                    "<th>overlap tail</th><th>Tm</th><th>GC%</th><th>len</th></tr>"
                    + "".join(rows) + "</table>") if rows else "<p>none</p>"

    assembly_rows = []
    for assembly in report["assemblies"]:
        assembly_rows.append(
            "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
            "<td>%s</td></tr>"
            % (esc(assembly["method"]), esc(assembly["experimental"]),
               esc(assembly["product_length"]), esc(assembly["topology"]),
               esc(assembly["junction_count"]), esc(assembly["feature_count"]),
               esc("; ".join(assembly["warnings"]))))
    assemblies_html = (
        "<table><tr><th>method</th><th>experimental</th><th>length</th><th>topology</th>"
        "<th>junctions</th><th>features</th><th>warnings</th></tr>"
        + "".join(assembly_rows) + "</table>") if assembly_rows else "<p>none</p>"

    qc_html = "".join(
        "<li class='%s'>[%s] %s</li>" % (esc(item.get("level", "info")),
                                         esc(item["source"]), esc(item["message"]))
        for item in report["qc"]) or "<li>no checks</li>"
    risks_html = "".join(
        "<li>%s</li>" % esc(item["risk"]) for item in report["risks"]
    ) or "<li>no risks</li>"
    compatibility_html = "".join(
        "<li><strong>%s</strong>: preferred=%s, manual review=%s</li>" % (
            esc(item["source"]),
            esc(item["data"].get("recommendation", {}).get(
                "preferred_format", "unknown")),
            esc(item["data"].get("recommendation", {}).get(
                "manual_review_required", "unknown")))
        for item in report.get("compatibility", [])
    ) or "<li>not assessed</li>"

    product_blocks = []
    for section in report["sections"]:
        if section["source"] != "product":
            continue
        data = section["data"]
        feature_rows = "".join(
            "<tr><td>%s</td><td>%s</td><td>%d..%d</td><td>%d</td><td>%s</td></tr>"
            % (esc(f["type"]), esc(f["name"]), f["start"], f["end"],
               f["strand"], esc(json.dumps(f.get("qualifiers", {}),
                                           ensure_ascii=False)[:120]))
            for f in data["features"])
        product_blocks.append(
            "<h3>%s (%d bp, %s)</h3><p class='mono'>%s</p>"
            "<table><tr><th>type</th><th>name</th><th>1-based span</th>"
            "<th>strand</th><th>qualifiers</th></tr>%s</table>"
            % (esc(data["name"]), data["length"], esc(data["topology"]),
               esc(data["sequence"]), feature_rows))

    notes_html = "".join(
        "<li>%s</li>" % esc(item["note"]) for item in report["notes"]
    ) or "<li>no notes</li>"

    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>%s</title>
<style>
body { font-family: -apple-system, "Segoe UI", Roboto, sans-serif;
       margin: 2rem auto; max-width: 1000px; padding: 0 1rem;
       color: #1a1a1a; background: #fff; }
h1 { border-bottom: 3px solid #2563eb; padding-bottom: .4rem; }
h2 { margin-top: 2rem; color: #1e3a8a; }
table { border-collapse: collapse; width: 100%%; font-size: 13px; }
th, td { border: 1px solid #d1d5db; padding: 4px 8px; text-align: left; }
th { background: #eff6ff; }
.mono { font-family: Consolas, monospace; font-size: 12px;
        word-break: break-all; }
ul { padding-left: 1.2rem; }
li.error { color: #b91c1c; }
li.warning { color: #b45309; }
</style>
</head>
<body>
<h1>%s</h1>
<p>generated %s · schema 0.5.0</p>
<h2>Summary</h2>
<ul>
<li>designs: %s</li><li>primers: %s</li><li>assemblies: %s</li>
<li>products: %s</li><li>QC checks: %s</li><li>risks: %s</li>
</ul>
<h2>Primers</h2>
%s
<h2>Assemblies</h2>
%s
<h2>Products</h2>
%s
<h2>QC</h2>
<ul>%s</ul>
<h2>Risks</h2>
<ul>%s</ul>
<h2>SnapGene compatibility</h2>
<ul>%s</ul>
<h2>Notes</h2>
<ul>%s</ul>
</body>
</html>
""" % (esc(report["title"]), esc(report["title"]),
       esc(report["generated_at"]),
       report["summary"]["designs"], report["summary"]["primers"],
       report["summary"]["assemblies"], report["summary"]["product_count"],
       report["summary"]["qc_checks"], report["summary"]["risks"],
       primers_html, assemblies_html, "".join(product_blocks),
       qc_html, risks_html, compatibility_html, notes_html)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--title", default="DNA design report")
    parser.add_argument("--design-json", action="append", default=[])
    parser.add_argument("--assembly-json", action="append", default=[])
    parser.add_argument("--product", action="append", default=[])
    parser.add_argument("--compatibility-json", action="append", default=[])
    parser.add_argument("--out", default="design-report.html")
    parser.add_argument("--report-json", default="design-report.json")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if not (args.design_json or args.assembly_json or args.product
            or args.compatibility_json):
        raise SystemExit("nothing to report: pass --design-json, "
                         "--assembly-json and/or --product")

    try:
        report = build_report(args.title, [pathlib.Path(p) for p in args.design_json],
                              [pathlib.Path(p) for p in args.assembly_json],
                              [pathlib.Path(p) for p in args.product],
                              [pathlib.Path(p) for p in args.compatibility_json])
    except (OSError, ValueError) as error:
        raise SystemExit(str(error))

    pathlib.Path(args.out).write_text(render_html(report), encoding="utf-8")
    pathlib.Path(args.report_json).write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    result = {
        "html_report": args.out,
        "report_json": args.report_json,
        "summary": report["summary"],
    }
    if args.json:
        jprint(result)
    else:
        print("design report written: %s / %s" % (args.out, args.report_json))
        for key, value in report["summary"].items():
            print("  %s: %s" % (key, value))
    return 0


if __name__ == "__main__":
    sys.exit(main())
