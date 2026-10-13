# -*- coding: utf-8 -*-
"""golden_gate.py - Experimental Golden Gate / Type IIS assembly simulation.

Type IIS enzymes (BsaI, BbsI, BsmBI, BtgZI, SapI, AarI) cut OUTSIDE their
recognition site, producing defined overhangs. This simulator:

  1. Locates recognition sites on both strands (forward and reverse
     orientation) and derives the exact double-strand cut boundaries from
     Bio.Restriction via ``sg_common.restriction_hits``.
  2. Extracts the fragment between the two cuts that is free of intact
     recognition sites (the excised insert / vector backbone) and reports its
     two overhang sequences.
  3. Assembles vector backbone + insert fragments in order, checking that
     every junction overhang (including the closing vector junction) matches.
  4. Reports junction sequences and the final product sequence.

Failure policy: Golden Gate is an all-or-nothing assembly. If ANY requested
part cannot be excised cleanly, if overhang lengths differ, or if any
junction (including the closing vector junction) mismatches, the command
exits non-zero and writes no product. It never silently drops an insert.

The destination vector must be circular. A linear part is never allowed to
produce a wrap-around fragment joining its sequence end to its sequence
start; use ``--vector-topology circular`` only when the vector record itself
lacks topology annotation (for example a plain FASTA file of a circular
plasmid).

The cut-boundary model follows Bio.Restriction semantics. For example,
BsaI GGTCTC(N1/N5) on a linear sequence yields top cut boundary 7 and
bottom cut boundary 11 relative to the recognition-site start (0-based);
the overhang is ``seq[7:11]`` on the top strand. The reverse orientation
GAGACC is searched too, with the reflected cut geometry.

This remains an experimental sequence-level approximation: ligation
fidelity, methylation, and reaction constraints are not
modeled. Do not use the output as a wet-lab-ready design.
"""
import argparse

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from assembly_model import (
    AssemblyFragment, check_sticky_junctions, overhang_end,
)
from sg_common import get_enzyme, jfail, jprint, load_seq, restriction_hits, topology

# Keep the legacy CLI as a thin adapter over the core cut geometry.  Passing
# the locally imported ``restriction_hits`` result into the shared helper also
# preserves the CLI's historical test seam and makes both entry points reject
# the same internal-site and orientation errors.
from core.tools.assembly import (
    _reverse_feature_dicts,
    migrate_features_after_assembly,
    type_iis_fragment as _core_type_iis_fragment,
)

# Supported Type IIS enzymes (resolved through Bio.Restriction so that the
# official recognition site and cut offsets are used, not hard-coded guesses).
TYPE_IIS = ["BsaI", "BbsI", "BsmBI", "BtgZI", "SapI", "AarI"]


def load_part(path):
    rec, _fmt = load_seq(path)
    return rec


def _arc(seq, start0, end0):
    """Clockwise (wrap-aware) slice of a sequence between two 0-based
    boundary coordinates."""
    n = len(seq)
    if n == 0:
        return ""
    raw_span = int(end0) - int(start0)
    start0 %= n
    end0 %= n
    length = n if raw_span and raw_span % n == 0 else (end0 - start0) % n
    if length == 0:
        return ""
    doubled = seq + seq
    return doubled[start0:start0 + length]


def _contains_recognition(fragment, enzyme):
    """True when the fragment still contains an intact recognition site on
    either strand."""
    site = str(enzyme.site).upper()
    rc_site = str(Seq(site).reverse_complement()).upper()
    frag = fragment.upper()
    return site in frag or rc_site in frag


def part_fragment(record, enzyme, topology_override=None):
    """Excise the Type IIS fragment that is free of intact recognition sites.

    Returns a dict with the fragment sequence, its left/right overhangs and
    diagnostic fields, or a dict with ``ok=False`` and a human-readable
    ``reason`` when the part cannot be excised cleanly. The returned fragment
    is always the top strand between the two top-strand cut boundaries of the
    chosen cut pair.

    For linear records, wrap-around candidates (``seq[end:] + seq[:start]``)
    are physically invalid and are rejected; only an internal, non-wrapping
    fragment is accepted.
    """
    part_topology = topology_override or topology(record)
    circular = part_topology == "circular"
    # Supply the locally computed hits so tests and callers that monkey-patch
    # the legacy module still exercise exactly the shared geometry.
    hits = [h for h in restriction_hits(str(record.seq), enzyme, circular=circular)
            if h.get("cuts_within_sequence", True)]
    return _core_type_iis_fragment(
        record,
        enzyme,
        topology_override=part_topology,
        hits=hits,
    )


def assemble(records, names, enzyme, vector_idx=0, reverse=(), vector_topology="circular"):
    """Assemble vector backbone + inserts in order.

    Returns (final_sequence, junctions, part_reports, notes). ``reverse`` is
    a set of original part indices whose excised insert should be
    reverse-complemented before assembly.

    All requested parts are mandatory. Raises SystemExit (non-zero) when any
    part fails extraction, overhang lengths differ, or any junction (including
    the closing vector junction) mismatches.
    """
    kept = []       # (original_index, fragment_info, name)
    fragments = []  # AssemblyFragment objects in final order
    overhang_len = None

    for i, (rec, nm) in enumerate(zip(records, names)):
        forced = vector_topology if i == vector_idx else None
        info = part_fragment(rec, enzyme, topology_override=forced)
        if not info["ok"]:
            jfail(
                "PART_EXCISION_FAILED",
                "Golden Gate assembly aborted: %s (%s) has no cleanly "
                "excisable Type IIS fragment: %s" % (i, nm, info["reason"]),
                details={"part_index": i, "part": nm, "reason": info["reason"]},
            )
        if overhang_len is None:
            overhang_len = info["overhang_length"]
        elif info["overhang_length"] != overhang_len:
            jfail(
                "OVERHANG_LENGTH_MISMATCH",
                "Golden Gate assembly aborted: %s overhang length %d bp does "
                "not match other parts (%d bp)"
                % (nm, info["overhang_length"], overhang_len),
            )

        fragment = info["fragment"]
        left_ov, right_ov = info["left_overhang"], info["right_overhang"]
        reversed_flag = False
        if i in reverse:
            if i == vector_idx:
                jfail("INVALID_REVERSE_INDEX",
                      "--reverse must not include the vector index %d" % i)
            fragment = str(Seq(fragment).reverse_complement())
            left_ov, right_ov = (
                str(Seq(right_ov).reverse_complement()),
                str(Seq(left_ov).reverse_complement()),
            )
            reversed_flag = True
        info = dict(info)
        info.update({
            "fragment": fragment,
            "left_overhang": left_ov,
            "right_overhang": right_ov,
            "features": (
                _reverse_feature_dicts(info.get("features", []), len(fragment))
                if reversed_flag else info.get("features", [])
            ),
            "reversed": reversed_flag,
        })
        kept.append((i, info, nm))

    ordered = [next(item for item in kept if item[0] == vector_idx)]
    ordered += [item for item in kept if item[0] != vector_idx]

    parts = []
    notes = []
    for orig_idx, info, nm in ordered:
        parts.append({
            "part_index": orig_idx,
            "name": nm,
            "role": "vector" if orig_idx == vector_idx else "insert",
            "fragment_length": len(info["fragment"]),
            "left_overhang": info["left_overhang"],
            "right_overhang": info["right_overhang"],
            "overhang_length": info["overhang_length"],
            "top_cut_start0": info["top_cut_start0"],
            "top_cut_end0": info["top_cut_end0"],
            "wraps_origin": info.get("wraps_origin", False),
            "topology": info["topology"],
            "recognition_sites": info["recognition_sites"],
            "features": info.get("features", []),
            "reversed": info["reversed"],
        })
        fragment_model = AssemblyFragment(
            nm, info["fragment"], topology="linear",
            left_end=overhang_end("5'-overhang", info["left_overhang"], 0),
            right_end=overhang_end(
                "5'-overhang",
                str(Seq(info["right_overhang"]).reverse_complement()),
                len(info["fragment"])),
        )
        fragments.append(fragment_model)
        notes.append(
            "%s: %s fragment %d bp; left overhang %s / right overhang %s%s"
            % (nm, parts[-1]["role"], parts[-1]["fragment_length"],
               info["left_overhang"], info["right_overhang"],
               " (reversed)" if info["reversed"] else "")
        )

    # Check every junction, including the closing vector junction, with the
    # shared end model.
    junctions = check_sticky_junctions(fragments, circular=True)
    for junction in junctions:
        junction["junction"] = "%s/%s" % (
            junction["left"]["overhang_sequence"],
            junction["right"]["overhang_sequence"])
    mismatches = [j for j in junctions if j["compatibility"] == "MISMATCH"]
    if mismatches:
        jfail(
            "OVERHANG_MISMATCH",
            "Golden Gate assembly aborted: %d overhang mismatch(es). "
            "No product was written." % len(mismatches),
            details=mismatches,
        )

    final = ordered[0][1]["fragment"]
    feature_fragments = [{
        "offset_in_product": 0,
        "length": len(ordered[0][1]["fragment"]),
        "features": ordered[0][1].get("features", []),
    }]
    for _, info, _ in ordered[1:]:
        left_len = len(info.get("left_overhang", ""))
        offset = len(final) - left_len
        feature_fragments.append({
            "offset_in_product": offset,
            "length": len(info["fragment"]),
            "features": info.get("features", []),
        })
        final += info["fragment"][left_len:]
    if ordered[-1][1].get("right_overhang"):
        final = final[:-len(ordered[-1][1]["right_overhang"])]
    for part, feature_fragment in zip(parts, feature_fragments):
        part["product_offset_0based"] = feature_fragment["offset_in_product"]
    return final, junctions, parts, notes, fragments


def main():
    p = argparse.ArgumentParser(description="Golden Gate (Type IIS) assembly simulation")
    p.add_argument("--parts", nargs="+", required=True,
                   help="part files (first = destination vector by default)")
    p.add_argument("--enzyme", required=True, choices=TYPE_IIS,
                   help="Type IIS enzyme")
    p.add_argument("--vector", type=int, default=0,
                   help="index (0-based) of the vector among --parts")
    p.add_argument("--reverse", type=int, nargs="+", default=[],
                   help="indices of inserts to reverse-complement")
    p.add_argument("--vector-topology", choices=["circular", "linear"], default=None,
                   help="override vector topology when its record lacks annotation "
                        "(FASTA vectors of circular plasmids need --vector-topology circular)")
    p.add_argument("--out", help="write product GenBank")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    if not (0 <= args.vector < len(args.parts)):
        jfail("INVALID_VECTOR_INDEX", "--vector index %d out of range" % args.vector)
    bad_reverse = [idx for idx in args.reverse if not (0 <= idx < len(args.parts))]
    if bad_reverse:
        jfail("INVALID_REVERSE_INDEX",
              "--reverse index out of range: %s" % ", ".join(map(str, bad_reverse)))

    try:
        enzyme = get_enzyme(args.enzyme)
        records = [load_part(x) for x in args.parts]
    except (OSError, ValueError) as error:
        jfail("INVALID_INPUT", str(error))

    vector_record = records[args.vector]
    vector_topology = args.vector_topology or topology(vector_record)
    if vector_topology != "circular":
        jfail(
            "INVALID_TOPOLOGY",
            "Golden Gate requires a circular destination vector, but %r is "
            "annotated/treated as linear. Golden Gate assembly circularizes "
            "the final construct; annotate the vector record as circular or "
            "pass --vector-topology circular." % args.parts[args.vector],
        )

    final, junctions, parts, notes, fragments = assemble(
        records, args.parts, enzyme,
        vector_idx=args.vector, reverse=set(args.reverse),
        vector_topology="circular",
    )
    notes.insert(
        0,
        "EXPERIMENTAL: Type IIS cut geometry is derived from Bio.Restriction "
        "double-strand boundaries, but ligation fidelity, feature migration, "
        "and reaction constraints are not modeled; do not use as a wet-lab-ready design",
    )
    product_features = migrate_features_after_assembly([
        {
            "offset_in_product": part.get("product_offset_0based", 0),
            "length": part.get("fragment_length", 0),
            "features": part.get("features", []),
        }
        for part in parts
    ], len(final), circular=True).analysis['features']

    result = {
        "experimental": True,
        "enzyme": args.enzyme,
        "enzyme_site": str(enzyme.site),
        "parts": parts,
        "fragments": [fragment.to_dict() for fragment in fragments],
        "product_length": len(final),
        "topology": "circular",
        "junctions": junctions,
        "notes": notes,
        "product_sequence": final,
        "features": product_features,
    }

    if args.out:
        prod = SeqRecord(Seq(final), id="gg_product", name="gg_product",
                         description="Golden Gate assembly product")
        prod.annotations["molecule_type"] = "DNA"
        prod.annotations["topology"] = "circular"
        from core.io.input_resolution import resolve_sequence_record
        prod.features = resolve_sequence_record({
            "sequence": final,
            "topology": "circular",
            "features": product_features,
        }).features
        with open(args.out, "w", encoding="utf-8") as fh:
            SeqIO.write(prod, fh, "genbank")
        result["out_file"] = args.out

    if args.json:
        jprint(result)
    else:
        print("Golden Gate (%s): %d bp (circular)" % (args.enzyme, len(final)))
        for j in junctions:
            print("  junction %s: %s [%s]" % (j["between"], j["junction"], j["compatibility"]))
        for n in notes:
            print("  note: %s" % n)
        print("product sequence:")
        print(final)
        if args.out:
            print("written to", args.out)


if __name__ == "__main__":
    main()
