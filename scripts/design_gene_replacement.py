# -*- coding: utf-8 -*-
"""design_gene_replacement.py - Gene replacement construct design (v0.6).

Designs a replacement cassette for swapping a target gene in a template with
a new CDS (e.g. marker swap, allele replacement):

1. locate the target feature (by label/gene) or an explicit 1-based region;
2. extract upstream/downstream homology arms (``--flank-len`` bp each);
3. build the replacement cassette = upstream arm + replacement CDS +
   downstream arm;
4. design the two Gibson primers with *separated* overlap tails and binding
   regions:

       forward = [upstream arm]      + [replacement 5' binding region]
       reverse = [rc(downstream arm)] + [rc(replacement 3' binding region)]

   (the reverse primer tail is the reverse complement of the downstream arm
   because the reverse primer is synthesized from the bottom strand);
5. QC the replacement CDS (start/stop codons, frame, GC) and the primers
   (Tm balance via design_primers.best_primer);
6. write the edited product (template with the target region replaced) as
   GenBank and a design JSON.

The design is a calculation aid: wet-lab verification (homology length,
recombination fidelity, host background) is always required.

Usage::

    python -X utf8 scripts/design_gene_replacement.py \\
        --template plasmid.gb --target-gene cdc15 \\
        --replacement new_cds.fa --flank-len 40 \\
        --out product.gb --design-json design.json --json
"""
import argparse
import json
import pathlib
import sys

from Bio.Seq import Seq
from Bio.SeqUtils import MeltingTemp as mt

from design_primers import best_primer
from edit_plasmid import op_replace
from sg_common import gc_percent, jprint, load_seq, normalize_dna

DEFAULT_FLANK = 40


def _biology_gate(host_species=None, strain=None, ploidy=None,
                  essentiality_status=None, complemented=None, locus=None,
                  essentiality_evidence=None, complementation_strategy=None):
    """Validate biological context before a replacement becomes deliverable.

    Sequence arithmetic cannot infer host background, ploidy or gene
    essentiality.  Missing context therefore blocks a final product instead
    of being silently replaced by an assumption.
    """
    errors = []
    species = str(host_species or "").strip()
    strain_value = str(strain or "").strip()
    locus_value = str(locus or "").strip()
    evidence_value = str(essentiality_evidence or "").strip()
    strategy_value = str(complementation_strategy or "").strip()
    ploidy_value = str(ploidy or "").strip().lower()
    essentiality = str(essentiality_status or "").strip().lower()
    if not species:
        errors.append("host_species is required")
    if not strain_value:
        errors.append("strain is required")
    if not locus_value:
        errors.append("locus is required")
    if ploidy_value not in ("haploid", "diploid", "polyploid"):
        errors.append("ploidy must be haploid, diploid, or polyploid")
    if essentiality not in ("essential", "nonessential"):
        errors.append("essentiality_status must be essential or nonessential")
    if not evidence_value:
        errors.append("essentiality_evidence is required")
    if complemented is None:
        errors.append("complemented must be explicitly true or false")
    elif essentiality == "essential" and complemented is not True:
        errors.append("essential target requires complemented=true")
    if not strategy_value:
        errors.append("complementation_strategy is required")
    return {
        "status": "ready" if not errors else "blocked",
        "host_species": species or None,
        "strain": strain_value or None,
        "locus": locus_value or None,
        "ploidy": ploidy_value or None,
        "essentiality_status": essentiality or None,
        "essentiality_evidence": evidence_value or None,
        "complemented": complemented,
        "complementation_strategy": strategy_value or None,
        "errors": errors,
        "source": "user-supplied biological context; no essentiality inference",
    }


def find_target_details(record, gene=None, region=None):
    """Locate the target feature or region.

    Returns (start_1based, end_1based, label). ``gene`` matches the feature's
    label or gene qualifier (case-insensitive substring). Compound features
    use their min..max span with a warning flag.
    """
    if region is not None:
        start, end = region
        return {
            "start": start, "end": end,
            "label": "region %d..%d" % (start, end),
            "compound": False, "strand": 1,
        }
    if not gene:
        raise ValueError("--target-gene or --target-region is required")
    hits = []
    for feature in record.features:
        label = feature.qualifiers.get(
            "label", feature.qualifiers.get("gene", [feature.id or ""]))
        if isinstance(label, (list, tuple)):
            label = label[0] if label else (feature.id or feature.type or "")
        if gene.lower() in str(label).lower():
            parts = getattr(feature.location, "parts", [feature.location])
            start0 = min(int(p.start) for p in parts)
            end0 = max(int(p.end) for p in parts)
            hits.append((start0, end0, str(label), len(parts) > 1,
                         feature.location.strand or 1))
    if not hits:
        raise ValueError(
            "no feature matching %r found (labels: %s)"
            % (gene, ", ".join(
                str((f.qualifiers.get("label", f.qualifiers.get("gene", ["?"]))[0]
                     if isinstance(f.qualifiers.get("label",
                                                      f.qualifiers.get("gene", ["?"])),
                                   (list, tuple)) else
                     f.qualifiers.get("label", f.qualifiers.get("gene", "?"))))
                for f in record.features) or "none"))
    if len(hits) > 1:
        raise ValueError(
            "multiple features match %r; use --target-region explicitly: %s"
            % (gene, hits))
    start0, end0, label, compound, strand = hits[0]
    return {
        "start": start0 + 1, "end": end0, "label": label,
        "compound": compound, "strand": int(strand),
    }


def find_target(record, gene=None, region=None):
    """Backward-compatible tuple target lookup without losing new metadata."""
    details = find_target_details(record, gene=gene, region=region)
    return (details["start"], details["end"], details["label"],
            details["compound"])


def design_replacement(record, replacement_dna, flank=DEFAULT_FLANK,
                       gene=None, region=None, target_tm=60.0,
                       min_len=18, max_len=30,
                       replacement_orientation="preserve-target",
                       biology=None):
    """Core design: returns a dict with arms, primers, cassette and QC."""
    target_details = find_target_details(record, gene, region)
    start = target_details["start"]
    end = target_details["end"]
    label = target_details["label"]
    compound = target_details["compound"]
    target_strand = int(target_details["strand"])
    if compound:
        raise ValueError(
            "COMPOUND_TARGET_REQUIRES_ORIGIN_AWARE_REPLACEMENT: target %s "
            "has a multi-part location; use an explicit contiguous interval "
            "after reviewing the origin mapping" % label)
    if start > end:
        raise ValueError(
            "TARGET_REGION_CROSS_ORIGIN_UNSUPPORTED: replacement target must "
            "be a contiguous non-wrapping interval")
    try:
        flank = int(flank)
    except (TypeError, ValueError):
        raise ValueError("FLANK_LENGTH_MUST_BE_INTEGER")
    if flank <= 0:
        raise ValueError("FLANK_LENGTH_MUST_BE_POSITIVE")
    biology = dict(biology or {})
    biology_gate = _biology_gate(
        biology.get("host_species"), biology.get("strain"),
        biology.get("ploidy"), biology.get("essentiality_status"),
        biology.get("complemented"), biology.get("locus"),
        biology.get("essentiality_evidence"),
        biology.get("complementation_strategy"))
    if replacement_orientation not in (
            "preserve-target", "as-provided", "reverse-complement"):
        raise ValueError(
            "replacement orientation must be preserve-target, as-provided, "
            "or reverse-complement")
    seq = str(record.seq)
    n = len(seq)
    if not (1 <= start <= end <= n):
        raise ValueError("target region %d..%d out of bounds (len %d)"
                         % (start, end, n))
    record_topology = str(
        (getattr(record, "annotations", {}) or {}).get("topology", "")
    ).lower()
    if record_topology == "circular" and (
            start - flank < 1 or end + flank > n):
        raise ValueError(
            "TARGET_FLANK_CROSS_ORIGIN_UNSUPPORTED: circular target %d..%d "
            "would require wrapping homology arms; provide an explicit "
            "origin-aware donor/interval design" % (start, end))
    upstream = seq[max(0, start - 1 - flank): start - 1]
    downstream = seq[end: min(n, end + flank)]
    if len(upstream) < flank or len(downstream) < flank:
        raise ValueError(
            "template does not provide %d bp of flanking sequence around "
            "%d..%d (upstream %d, downstream %d)"
            % (flank, start, end, len(upstream), len(downstream)))

    replacement_input = normalize_dna(replacement_dna, "replacement CDS")
    if replacement_orientation == "reverse-complement":
        replacement = str(Seq(replacement_input).reverse_complement())
    elif replacement_orientation == "preserve-target" and target_strand == -1:
        replacement = str(Seq(replacement_input).reverse_complement())
    else:
        replacement = replacement_input
    cassette = upstream + replacement + downstream

    # Gibson primers: binding regions are picked inside the replacement CDS
    # ends, tails are the homology arms.
    fwd_binding = best_primer(replacement, target_tm, min_len, max_len)
    rev_template = str(Seq(replacement).reverse_complement())
    rev_binding = best_primer(rev_template, target_tm, min_len, max_len)

    # QC the replacement CDS.
    # QC is reported in the replacement's biological input orientation.  The
    # inserted genomic sequence may be reverse-complemented for a reverse-
    # strand target, but the protein coding checks must not flip with it.
    cds_upper = replacement_input.upper()
    starts_with_atg = cds_upper.startswith("ATG")
    ends_with_stop = cds_upper[-3:] in ("TAA", "TAG", "TGA")
    frame_ok = len(cds_upper) % 3 == 0
    gc = gc_percent(cds_upper)
    qc = {
        "starts_with_atg": starts_with_atg,
        "ends_with_stop": ends_with_stop,
        "frame_multiple_of_3": frame_ok,
        "length": len(cds_upper),
        "gc_percent": round(gc, 1),
        "risks": [],
    }
    if not starts_with_atg:
        qc["risks"].append("replacement does not start with ATG (no start codon)")
    if not ends_with_stop:
        qc["risks"].append("replacement lacks a terminal stop codon")
    if not frame_ok:
        qc["risks"].append("replacement length is not a multiple of 3 (frame shift)")
    if gc < 30 or gc > 70:
        qc["risks"].append("unusual GC content (%.1f%%)" % gc)
    qc["blocking_risks"] = [risk for risk in qc["risks"]
                             if ("no start codon" in risk or
                                 "terminal stop codon" in risk or
                                 "frame shift" in risk)]
    if fwd_binding is None or rev_binding is None:
        qc["blocking_risks"].append(
            "Primer3/heuristic binding region could not produce both primers")

    primers = {"forward": None, "reverse": None}
    if fwd_binding:
        binding = fwd_binding[1]
        primers["forward"] = {
            "sequence": upstream + binding,
            "overlap": upstream,
            "overlap_length": len(upstream),
            "binding": binding,
            "tm": fwd_binding[2], "gc": fwd_binding[3],
            "length": len(upstream) + len(binding),
        }
    if rev_binding:
        binding = rev_binding[1]
        tail = str(Seq(downstream).reverse_complement())
        primers["reverse"] = {
            "sequence": tail + binding,
            "overlap": downstream,
            "overlap_tail": tail,
            "overlap_length": len(downstream),
            "binding": binding,
            "tm": rev_binding[2], "gc": rev_binding[3],
            "length": len(downstream) + len(binding),
        }

    return {
        "template": record.name or record.id,
        "target": {"gene": label, "start": start, "end": end,
                   "length": end - start + 1, "compound": compound,
                   "strand": target_strand},
        "flank_length": flank,
        "homology_arms": {
            "upstream": upstream, "upstream_length": len(upstream),
            "downstream": downstream, "downstream_length": len(downstream),
        },
        "replacement": {
            "input_sequence": replacement_input,
            "sequence": replacement, "length": len(replacement),
            "gc_percent": round(gc, 1),
            "orientation": replacement_orientation,
            "inserted_genomic_strand": (
                target_strand if replacement_orientation == "preserve-target"
                else (-1 if replacement_orientation == "reverse-complement"
                      else 1)),
        },
        "cassette": {
            "sequence": cassette, "length": len(cassette),
            "assembly_note": "upstream arm + replacement CDS + downstream arm",
        },
        "primers": primers,
        "qc": qc,
        "biology": biology_gate,
        "notes": [
            "Gibson primers: 5' tails are the homology arms; binding regions "
            "anneal inside the replacement CDS",
            "The reverse primer carries rc(downstream arm) because it is "
            "synthesized from the bottom strand",
            "Replacement orientation is explicit; preserve-target reverse-strand "
            "targets use reverse-complement(input) in genomic sequence",
            "Wet-lab verification of homology length, recombination fidelity "
            "and host background is required before execution",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", required=True)
    parser.add_argument("--target-gene", default=None,
                        help="feature label/gene to replace")
    parser.add_argument("--target-region", default=None,
                        help="explicit 1-based interval 'start-end'")
    parser.add_argument("--replacement", required=True,
                        help="replacement CDS file (FASTA/GenBank) or raw sequence")
    parser.add_argument("--flank-len", type=int, default=DEFAULT_FLANK)
    parser.add_argument("--target-tm", type=float, default=60.0)
    parser.add_argument("--min-len", type=int, default=18)
    parser.add_argument("--max-len", type=int, default=30)
    parser.add_argument(
        "--replacement-orientation",
        choices=("preserve-target", "as-provided", "reverse-complement"),
        default="preserve-target",
        help=("genomic insertion orientation; preserve-target is the safe "
              "default for a feature-targeted replacement"),
    )
    parser.add_argument("--host-species", default=None,
                        help="required for a final product, e.g. Saccharomyces cerevisiae")
    parser.add_argument("--strain", default=None,
                        help="required for a final product, e.g. S288C")
    parser.add_argument("--locus", default=None,
                        help="explicit target locus/gene identifier")
    parser.add_argument("--ploidy", choices=("haploid", "diploid", "polyploid"),
                        default=None, help="required biological context")
    parser.add_argument("--essentiality-status",
                        choices=("essential", "nonessential"), default=None,
                        help="must be supplied; no database inference is performed")
    parser.add_argument("--essentiality-evidence", default=None,
                        help="source/accession or user evidence for essentiality status")
    complement_group = parser.add_mutually_exclusive_group()
    complement_group.add_argument("--complemented", dest="complemented",
                                  action="store_true", default=None)
    complement_group.add_argument("--not-complemented", dest="complemented",
                                  action="store_false")
    parser.add_argument("--complementation-strategy", default=None,
                        help="explicit complementation/conditional strategy, or why not needed")
    parser.add_argument("--out", default=None, help="product GenBank path")
    parser.add_argument("--design-json", default=None,
                        help="write the design JSON to this path")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        record, _fmt = load_seq(args.template)
        replacement_rec, _rfmt = load_seq(args.replacement)
        replacement_dna = str(replacement_rec.seq)
        region = None
        if args.target_region:
            parts = args.target_region.split("-")
            if len(parts) != 2:
                raise ValueError("--target-region must be 'start-end'")
            region = (int(parts[0]), int(parts[1]))
        design = design_replacement(
            record, replacement_dna, flank=args.flank_len,
            gene=args.target_gene, region=region,
            target_tm=args.target_tm, min_len=args.min_len,
            max_len=args.max_len,
            replacement_orientation=args.replacement_orientation,
            biology={
                "host_species": args.host_species,
                "strain": args.strain,
                "locus": args.locus,
                "ploidy": args.ploidy,
                "essentiality_status": args.essentiality_status,
                "essentiality_evidence": args.essentiality_evidence,
                "complemented": args.complemented,
                "complementation_strategy": args.complementation_strategy,
            })
    except (OSError, ValueError) as error:
        raise SystemExit(str(error))

    if design["qc"]["risks"]:
        design["warnings"] = design["qc"]["risks"]

    if args.out:
        if design["biology"]["status"] != "ready":
            raise SystemExit(
                "BIOLOGY_CONTEXT_REQUIRED: %s" %
                "; ".join(design["biology"]["errors"]))
        if design["qc"].get("blocking_risks"):
            raise SystemExit(
                "REPLACEMENT_QC_FAILED: %s" %
                "; ".join(design["qc"]["blocking_risks"]))
        product = op_replace(record, design["target"]["start"],
                             design["target"]["end"], design["replacement"]["sequence"])
        from Bio.SeqFeature import FeatureLocation, SeqFeature
        inserted_start = design["target"]["start"] - 1
        inserted_end = inserted_start + design["replacement"]["length"]
        product.features.append(SeqFeature(
            FeatureLocation(
                inserted_start, inserted_end,
                strand=design["target"].get("strand", 1)),
            type="misc_feature",
            qualifiers={
                "label": ["replacement:%s" % design["target"]["gene"]],
                "note": ["orientation=%s" % design["replacement"]["orientation"]],
            },
        ))
        product.id = "replacement_product"
        product.name = "replacement_product"
        product.description = "gene replacement of %s with %s bp CDS" % (
            design["target"]["gene"], design["replacement"]["length"])
        with open(args.out, "w", encoding="utf-8") as handle:
            from Bio import SeqIO
            SeqIO.write(product, handle, "genbank")
        design["product_file"] = args.out
        design["product_length"] = len(product.seq)
        design["product_feature_count"] = len(product.features)

    if args.design_json:
        pathlib.Path(args.design_json).write_text(
            json.dumps(design, indent=2, ensure_ascii=False), encoding="utf-8")
        design["design_json"] = args.design_json

    if args.json:
        jprint(design)
    else:
        print("target: %s %d..%d (%s)  flank=%d" % (
            design["target"]["gene"], design["target"]["start"],
            design["target"]["end"], design["template"], args.flank_len))
        print("replacement: %d bp, GC %.1f%%, ATG=%s stop=%s frame=%s" % (
            design["replacement"]["length"], design["replacement"]["gc_percent"],
            design["qc"]["starts_with_atg"], design["qc"]["ends_with_stop"],
            design["qc"]["frame_multiple_of_3"]))
        for side in ("forward", "reverse"):
            primer = design["primers"][side]
            if primer:
                print("%s: 5'-[%d bp overlap] + [%d bp binding Tm=%s]  %s..." % (
                    side, primer["overlap_length"], len(primer["binding"]),
                    primer["tm"], primer["sequence"][:40]))
        for risk in design["qc"]["risks"]:
            print("RISK: %s" % risk)
        if args.out:
            print("product written to %s (%d bp)" % (
                args.out, design["product_length"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
