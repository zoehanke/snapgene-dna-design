# -*- coding: utf-8 -*-
"""batch.py - Batch operation pipeline over a directory of sequence files.

Applies one operation to every file in a directory and emits a summary.
Operations reuse the other scripts' core functions.

Usage:
  batch.py DIR --op parse|validate|sites|annotate|convert [--format gb]
"""
import argparse
import json
import os
import sys

from Bio import SeqIO

import sg_common

SEQ_EXTS = (".dna", ".gb", ".genbank", ".fa", ".fasta", ".fna", ".fsa", ".embl", ".emb")


def list_files(directory):
    return [os.path.join(directory, f) for f in sorted(os.listdir(directory))
            if os.path.splitext(f)[1].lower() in SEQ_EXTS
            and os.path.isfile(os.path.join(directory, f))]


def op_parse(path):
    rec, fmt = sg_common.load_seq(path)
    return {"file": path, "format": fmt, "length": len(rec.seq),
            "topology": sg_common.topology(rec),
            "feature_count": len(rec.features)}


def op_validate(path):
    import validate_construct
    rec, _fmt = sg_common.load_seq(path)
    r = validate_construct.validate(rec)
    return {"file": path, **r["summary"]}


def op_sites(path):
    import find_sites
    rec, _fmt = sg_common.load_seq(path)
    seq = str(rec.seq)
    topo = sg_common.topology(rec)
    d = find_sites.digest_report(seq, topo, find_sites.COMMON_ENZYMES[:6])
    return {"file": path, "cut_count": d["cut_count"], "fragments": d["fragments"][:8]}


def op_convert(path, out_format):
    import convert
    ext = convert.FORMAT_EXT[out_format]
    dst = os.path.splitext(path)[0] + ext
    try:
        convert.convert_file(path, dst, out_format)
        return {"file": path, "status": "ok", "out": dst}
    except Exception as e:
        return {"file": path, "status": "error", "error": str(e)}


def main():
    p = argparse.ArgumentParser(description="Batch operation over sequence files")
    p.add_argument("directory")
    p.add_argument("--op", required=True,
                   choices=["parse", "validate", "sites", "convert"])
    p.add_argument("--format", default="genbank",
                   choices=["genbank", "fasta", "embl", "snapgene"],
                   help="target format (for --op convert)")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    if not os.path.isdir(args.directory):
        raise SystemExit("not a directory: %s" % args.directory)
    files = list_files(args.directory)
    if not files:
        raise SystemExit("no sequence files found in %s" % args.directory)

    results = []
    conflicts = {}
    if args.op == "convert":
        from convert import conversion_conflicts
        conflicts = conversion_conflicts(files, args.directory, args.format)
    for f in files:
        try:
            if f in conflicts:
                raise ValueError(conflicts[f])
            if args.op == "parse":
                results.append(op_parse(f))
            elif args.op == "validate":
                results.append(op_validate(f))
            elif args.op == "sites":
                results.append(op_sites(f))
            else:
                results.append(op_convert(f, args.format))
        except Exception as e:
            results.append({"file": f, "status": "error", "error": str(e)})

    report = {"op": args.op, "total": len(files), "results": results}
    success = all(item.get("status") != "error" and not item.get("errors", 0)
                  for item in results)
    if args.json:
        sg_common.jprint(report, ok=success)
    else:
        print("batch %s: %d files" % (args.op, len(files)))
        for r in results:
            if "status" in r and r["status"] == "error":
                print("  ERROR %s: %s" % (r["file"], r.get("error")))
            elif args.op == "parse":
                print("  %s: %s %d bp %s, %d features" % (
                    r["file"], r["format"], r["length"], r["topology"], r["feature_count"]))
            elif args.op == "validate":
                print("  %s: errors=%d warnings=%d" % (
                    r["file"], r["errors"], r["warnings"]))
            else:
                print("  %s: %s" % (r["file"], json.dumps(r, ensure_ascii=False)[:120]))
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
