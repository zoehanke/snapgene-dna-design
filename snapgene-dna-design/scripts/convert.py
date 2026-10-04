# -*- coding: utf-8 -*-
"""convert.py - Batch format conversion.

Convert sequence files between supported formats:
  snapgene (.dna), genbank (.gb), fasta (.fa), embl (.embl)

Single file or a directory (--dir) of files.
"""
import argparse
import os
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from evidence_trace.runtime import add_trace_arguments, trace_options, trace_file_call

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


def convert_file(src, dst, out_format, allow_overwrite=False):
    if out_format not in FORMAT_EXT:
        raise ValueError("Unsupported output format: %s" % out_format)
    destination = pathlib.Path(dst)
    if destination.exists() and not allow_overwrite:
        raise FileExistsError("Refusing to overwrite existing file: %s" % dst)
    rec, _fmt = load_seq(os.fspath(src))
    # A failed writer must not leave a truncated destination or destroy input.
    with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
        candidate = pathlib.Path(temporary) / destination.name
        if out_format == "snapgene":
            from write_dna import write_native_dna
            write_native_dna(rec, candidate)
        else:
            if "molecule_type" not in rec.annotations:
                rec.annotations["molecule_type"] = "DNA"
            import copy
            from core.io.molecule_codec import genbank_record
            if out_format=='genbank':
                rec=genbank_record(rec)
            else:
                rec=copy.deepcopy(rec)
                if rec.annotations.get('topology') is None:rec.annotations.pop('topology',None)
            with candidate.open("w", encoding="utf-8") as fh:
                WRITERS[out_format](rec, fh)
        if allow_overwrite:
            # Candidate is on the same filesystem; only a completely written
            # conversion replaces the explicitly selected destination.
            os.replace(candidate, destination)
        else:
            with candidate.open("rb") as source, destination.open("xb") as target:
                import shutil
                shutil.copyfileobj(source, target)
    return dst


def conversion_conflicts(paths, outdir, out_format, allow_overwrite=False):
    """Return source paths whose destinations collide with inputs or each other."""
    destinations = {}
    conflicts = {}
    for source in paths:
        target = pathlib.Path(outdir) / (pathlib.Path(source).stem + FORMAT_EXT[out_format])
        key = os.path.normcase(str(target.resolve()))
        destinations.setdefault(key, []).append(source)
        if target.exists() and not allow_overwrite:
            conflicts[source] = "Refusing to overwrite existing file: %s" % target
    for sources in destinations.values():
        if len(sources) > 1:
            for source in sources:
                conflicts[source] = "Multiple input files map to the same output filename"
    return conflicts


def main():
    p = argparse.ArgumentParser(description="Convert sequence files")
    p.add_argument("source", help="input file, or directory with --dir")
    p.add_argument("--out", help="output path (file or directory)")
    p.add_argument("--format", required=True, choices=list(FORMAT_EXT.keys()),
                   help="target format")
    p.add_argument("--dir", action="store_true", help="batch-convert a directory")
    p.add_argument("--allow-overwrite", action="store_true",
                   help="atomically replace an existing output; ambiguous batch targets still fail")
    p.add_argument("--json", action="store_true")
    add_trace_arguments(p)
    args = p.parse_args()

    ext = FORMAT_EXT[args.format]
    results = []

    if args.dir:
        if not os.path.isdir(args.source):
            raise SystemExit("--dir requires a directory source")
        outdir = args.out or args.source
        os.makedirs(outdir, exist_ok=True)
        files = [f for f in os.listdir(args.source)
                 if os.path.isfile(os.path.join(args.source, f))
                 and os.path.splitext(f)[1].lower() in
                 (".dna", ".gb", ".genbank", ".fa", ".fasta", ".fna", ".fsa", ".embl", ".emb")]
        if not files:
            results.append({"in": args.source, "status": "error", "error": "No sequence files found"})
        conflicts = conversion_conflicts(
            [os.path.join(args.source, f) for f in files], outdir, args.format,
            allow_overwrite=args.allow_overwrite)
        for f in sorted(files):
            src = os.path.join(args.source, f)
            dst = os.path.join(outdir, os.path.splitext(f)[0] + ext)
            if src in conflicts:
                results.append({"in": src, "status": "error", "error": conflicts[src]})
                continue
            try:
                trace_file_call("convert", convert_file, args=(src, dst, args.format),
                                kwargs={"allow_overwrite": args.allow_overwrite},
                                input_paths=[src], expected_paths=[dst], output_paths=lambda value: [value],
                                artifact_role="converted", **trace_options(args))
                results.append({"in": src, "out": dst, "status": "ok"})
            except Exception as e:
                results.append({"in": src, "status": "error", "error": str(e)})
    else:
        dst = args.out or (os.path.splitext(args.source)[0] + ext)
        try:
            trace_file_call("convert", convert_file, args=(args.source, dst, args.format),
                            kwargs={"allow_overwrite": args.allow_overwrite},
                            input_paths=[args.source], expected_paths=[dst], output_paths=lambda value: [value],
                            artifact_role="converted", **trace_options(args))
            results.append({"in": args.source, "out": dst, "status": "ok"})
        except Exception as e:
            results.append({"in": args.source, "status": "error", "error": str(e)})

    success = bool(results) and all(item["status"] == "ok" for item in results)
    if args.json:
        jprint({"format": args.format, "results": results}, ok=success)
    else:
        for r in results:
            if r["status"] == "ok":
                print("%s -> %s" % (r["in"], r["out"]))
            else:
                print("ERROR %s: %s" % (r["in"], r["error"]))
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
