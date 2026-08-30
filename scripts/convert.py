# -*- coding: utf-8 -*-
"""convert.py - Batch format conversion.

Convert sequence files between supported formats:
  snapgene (.dna), genbank (.gb), fasta (.fa), embl (.embl)

Single file or a directory (--dir) of files.
"""
import argparse
import os

from Bio import SeqIO

from sg_common import jprint, load_seq

FORMAT_EXT = {
    "genbank": ".gb",
    "fasta": ".fa",
    "embl": ".embl",
    "snapgene": ".dna",
}

WRITERS = {
    "genbank": lambda rec, fh: SeqIO.write(rec, fh, "genbank"),
    "fasta": lambda rec, fh: SeqIO.write(rec, fh, "fasta"),
    "embl": lambda rec, fh: SeqIO.write(rec, fh, "embl"),
}


def convert_file(src, dst, out_format):
    rec, _fmt = load_seq(src)
    if out_format == "snapgene":
        # native .dna via sgffp
        from write_dna import write_native_dna
        write_native_dna(rec, dst)
    else:
        if "molecule_type" not in rec.annotations:
            rec.annotations["molecule_type"] = "DNA"
        with open(dst, "w", encoding="utf-8") as fh:
            WRITERS[out_format](rec, fh)
    return dst


def main():
    p = argparse.ArgumentParser(description="Convert sequence files")
    p.add_argument("source", help="input file, or directory with --dir")
    p.add_argument("--out", help="output path (file or directory)")
    p.add_argument("--format", required=True, choices=list(FORMAT_EXT.keys()),
                   help="target format")
    p.add_argument("--dir", action="store_true", help="batch-convert a directory")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    ext = FORMAT_EXT[args.format]
    results = []

    if args.dir:
        if not os.path.isdir(args.source):
            raise SystemExit("--dir requires a directory source")
        outdir = args.out or args.source
        os.makedirs(outdir, exist_ok=True)
        files = [f for f in os.listdir(args.source)
                 if os.path.splitext(f)[1].lower() in
                 (".dna", ".gb", ".genbank", ".fa", ".fasta", ".embl", ".emb")]
        for f in sorted(files):
            src = os.path.join(args.source, f)
            dst = os.path.join(outdir, os.path.splitext(f)[0] + ext)
            try:
                convert_file(src, dst, args.format)
                results.append({"in": src, "out": dst, "status": "ok"})
            except Exception as e:
                results.append({"in": src, "status": "error", "error": str(e)})
    else:
        dst = args.out or (os.path.splitext(args.source)[0] + ext)
        try:
            convert_file(args.source, dst, args.format)
            results.append({"in": args.source, "out": dst, "status": "ok"})
        except Exception as e:
            results.append({"in": args.source, "status": "error", "error": str(e)})

    if args.json:
        jprint({"format": args.format, "results": results})
    else:
        for r in results:
            if r["status"] == "ok":
                print("%s -> %s" % (r["in"], r["out"]))
            else:
                print("ERROR %s: %s" % (r["in"], r["error"]))


if __name__ == "__main__":
    main()
