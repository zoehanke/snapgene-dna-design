# -*- coding: utf-8 -*-
"""simulate_advanced.py - Experimental advanced cloning approximations.

Methods:
  infusion      In-Fusion / NEBuilder HiFi (strict 15-bp homology checks)
  ta / topo     TA/TOPO cloning with explicit vector cut and user-declared
                3' T / 3' A overhang premises
  gateway-lr    Gateway LR reaction (attL entry x attR destination -> attB)
  gateway-bp    Gateway BP reaction (attB x attP donor -> attL entry)

v0.4 failure policy:

  * infusion mismatches stop the assembly with
    ``{"ok": false, "error": {"code": "OVERLAP_MISMATCH", ...}}``; no
    warning-then-concatenate fallback exists.
  * gateway records must carry an explicit topology annotation, and the
    att-site search enumerates every occurrence in both orientations. The
    pair must be unique and correctly oriented; missing, duplicated, or
    mis-oriented sites abort with structured errors.
  * ta / topo never infer overhangs from terminal bases. The user must pass
    ``--vector-cut``, ``--vector-end t-tailed``, and
    ``--insert-end a-tailed`` as experimental premises.

All assembly methods share ``assembly_model.AssemblyFragment``.
"""
import argparse
import copy

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord
import pathlib
import sys

_ROOT = str(pathlib.Path(__file__).resolve().parents[1])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.models.assembly_model import (
    AssemblyError, AssemblyFragment, check_gibson_overlaps,
    check_sticky_junctions, gibson_fragment, join_by_homology,
    overhang_end, validate_unique_contributions,
)
from core.models.construct_model import ConstructModel
from sg_common import jfail, jprint, load_seq, topology
from simulate_cloning import _shift_features

from core.tools.recombination import (
    ATTB1,
    ATTB2,
    ATTL1,
    ATTL2,
    ATTR1,
    ATTR2,
    ATTP1,
    ATTP2,
    _extract_body,
    _features_between,
    _occurrences,
    _replace_with_features,
    _require_explicit_circular,
    _shift_feature,
    _strict_att_pair,
    gateway_bp,
    gateway_lr,
)


def infusion(parts, overlap=15, circular=False):
    """Strict In-Fusion/HiFi assembly: mismatched homology aborts."""
    fragments = [
        gibson_fragment(rec.name or "fragment%d" % i, str(rec.seq))
        for i, rec in enumerate(parts)
    ]
    check_gibson_overlaps(fragments, overlap, method="infusion", circular=circular)
    contributions = validate_unique_contributions(fragments, overlap, circular)
    final = join_by_homology(fragments, overlap, circular=circular)

    product = copy.deepcopy(parts[0])
    product.seq = Seq(final)
    product.id = "product"
    product.name = "product"
    product.description = "infusion product"
    product.features = []
    warnings = []
    offset = 0
    for i, rec in enumerate(parts):
        trim = overlap if (i > 0 or circular) else 0
        features, feature_warnings = _shift_features(
            rec, offset, trim_start=trim, clip_end=len(rec.seq),
            circular=circular, is_first=(i == 0),
            product_length=len(final), product_seq=final)
        product.features.extend(features)
        warnings.extend(feature_warnings)
        offset += contributions[i]
    return product, fragments, warnings


def _ta_topo_fragments(vector_rec, insert_rec, vector_cut):
    """Build shared-end fragments from explicit user premises."""
    if vector_cut is None:
        raise AssemblyError(
            "MISSING_VECTOR_CUT",
            "ta/topo require --vector-cut (0-based cut boundary on the vector)",
        )
    v = str(vector_rec.seq).upper()
    ins = str(insert_rec.seq).upper()
    if not (0 <= vector_cut <= len(v)):
        raise AssemblyError(
            "INVALID_VECTOR_CUT",
            "vector cut boundary %d is outside 0..%d" % (vector_cut, len(v)),
        )
    vector_frag = AssemblyFragment(
        vector_rec.name or "vector", v, topology="linear",
        left_end=overhang_end("3'-overhang", "T", 0,
                              source_cut_boundary=vector_cut),
        right_end=overhang_end("3'-overhang", "T", len(v),
                               source_cut_boundary=vector_cut),
        source=vector_rec.id,
    )
    insert_frag = AssemblyFragment(
        insert_rec.name or "insert", ins, topology="linear",
        left_end=overhang_end("3'-overhang", "A", 0,
                              source_cut_boundary=0),
        right_end=overhang_end("3'-overhang", "A", len(ins),
                               source_cut_boundary=len(ins)),
        source=insert_rec.id,
    )
    return vector_frag, insert_frag


def ta_topo_clone(vector_rec, insert_rec, vector_cut, method="ta"):
    """TA/TOPO assembly from explicitly declared T/A overhang premises."""
    vector_frag, insert_frag = _ta_topo_fragments(vector_rec, insert_rec, vector_cut)
    junctions = check_sticky_junctions([vector_frag, insert_frag], circular=True)
    if any(j["compatibility"] == "MISMATCH" for j in junctions):
        raise AssemblyError(
            "STICKY_END_MISMATCH",
            "%s overhang premises are incompatible: vector 3'-T vs insert 3'-A required"
            % method,
            details=junctions,
        )
    model = ConstructModel(vector_rec).insert(vector_cut, insert_frag.sequence)
    model.set_topology("circular")
    product = model.to_record()
    product.id = "product"
    product.name = "product"
    product.description = "%s product" % method
    product.features.append(SeqFeature(
        FeatureLocation(vector_cut, vector_cut + len(insert_frag.sequence), strand=1),
        type="misc_feature", qualifiers={"label": ["insert"]},
    ))
    return product, [vector_frag, insert_frag], junctions




def main():
    p = argparse.ArgumentParser(description="Advanced cloning simulations")
    p.add_argument("--method", required=True,
                   choices=["infusion", "ta", "topo", "gateway-lr", "gateway-bp"])
    p.add_argument("--parts", nargs="+", help="fragment files (infusion)")
    p.add_argument("--overlap", type=int, default=15,
                   help="homology length (infusion, default 15)")
    p.add_argument("--vector", help="vector file (ta/topo/gateway-bp donor)")
    p.add_argument("--insert", help="insert file (ta/topo/gateway-bp)")
    p.add_argument("--vector-cut", type=int,
                   help="0-based vector cut boundary for ta/topo")
    p.add_argument("--vector-end", choices=["t-tailed", "blunt"],
                   help="declared vector sticky end (ta/topo)")
    p.add_argument("--insert-end", choices=["a-tailed", "blunt"],
                   help="declared insert sticky end (ta/topo)")
    p.add_argument("--entry", help="entry clone file (gateway-lr)")
    p.add_argument("--destination", help="destination vector file (gateway-lr)")
    p.add_argument("--out", help="write product GenBank")
    p.add_argument(
        "--allow-experimental-output", action="store_true",
        help="explicitly allow TA/TOPO approximation export; it is not a final construct",
    )
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    notes = []
    warnings = []
    try:
        if args.method == "infusion":
            if not args.parts or len(args.parts) < 2:
                raise AssemblyError("INVALID_INPUT", "infusion requires --parts with >=2 files")
            parts = [load_part(x) for x in args.parts]
            circular = topology(parts[0]) == "circular"
            product, fragments, warnings = infusion(parts, args.overlap, circular=circular)
            if not (15 <= args.overlap <= 40):
                warnings.append(
                    "overlap %d bp is outside the documented In-Fusion "
                    "working range (15-40 bp); this simulation is "
                    "sequence-level only" % args.overlap)
            topo = topology(parts[0])
        elif args.method in ("ta", "topo"):
            if not (args.vector and args.insert):
                raise AssemblyError(
                    "INVALID_INPUT", "%s requires --vector and --insert" % args.method)
            if args.vector_cut is None:
                raise AssemblyError(
                    "MISSING_VECTOR_CUT",
                    "%s requires --vector-cut (0-based cut boundary)" % args.method)
            if args.vector_end != "t-tailed" or args.insert_end != "a-tailed":
                raise AssemblyError(
                    "END_TYPE_MISMATCH",
                    "%s requires --vector-end t-tailed and --insert-end a-tailed "
                    "as explicit experimental premises (got vector=%s, insert=%s)"
                    % (args.method, args.vector_end, args.insert_end))
            vector_rec = load_part(args.vector)
            insert_rec = load_part(args.insert)
            product, fragments, junctions = ta_topo_clone(
                vector_rec, insert_rec, args.vector_cut, method=args.method)
            topo = "circular"
            notes.append(
                "%s: 3'-T vector ends and 3'-A insert ends are user-declared "
                "premises, not inferred from sequence" % args.method)
            notes.append(
                "%s: product_sequence reports the blunt insertion model and "
                "does not add the declared 3' T/A overhang bases at the two "
                "junctions; treat the sequence as an approximation, not the "
                "ligated molecule" % args.method)
        elif args.method == "gateway-lr":
            if not (args.entry and args.destination):
                raise AssemblyError(
                    "INVALID_INPUT", "gateway-lr requires --entry and --destination")
            entry_rec = load_part(args.entry)
            destination_rec = load_part(args.destination)
            product, body, notes = gateway_lr(entry_rec, destination_rec)
            fragments = [
                AssemblyFragment("entry", body, topology="linear"),
                AssemblyFragment("destination", str(destination_rec.seq), topology="circular"),
            ]
            junctions = []
            topo = "circular"
        else:  # gateway-bp
            if not (args.vector and args.insert):
                raise AssemblyError(
                    "INVALID_INPUT", "gateway-bp requires --vector and --insert")
            donor_rec = load_part(args.vector)
            insert_rec = load_part(args.insert)
            product, body, notes = gateway_bp(donor_rec, insert_rec)
            fragments = [
                AssemblyFragment("donor", str(donor_rec.seq), topology="circular"),
                AssemblyFragment("insert", body, topology="linear"),
            ]
            junctions = []
            topo = "circular"
    except AssemblyError as error:
        jfail(error.code, error.message, error.details)
    except (OSError, ValueError) as error:
        jfail("INVALID_INPUT", str(error))

    notes.insert(
        0,
        "EXPERIMENTAL: this method is a sequence-level approximation; reaction "
        "chemistry and fidelity are not validated",
    )
    result = {
        "experimental": True,
        "product_sequence_status": (
            "junction-model-only" if args.method in ("ta", "topo")
            else "sequence-level-approximation"),
        "final_deliverable": False,
        "method": args.method,
        "product_length": len(product.seq),
        "topology": topo,
        "fragments": [fragment.to_dict() for fragment in fragments],
        "junctions": junctions if args.method in ("ta", "topo") else [],
        "warnings": warnings,
        "notes": notes,
        "feature_count": len(product.features),
        "product_sequence": str(product.seq),
    }
    if args.out:
        if args.method in ("ta", "topo") and not args.allow_experimental_output:
            jfail(
                "EXPERIMENTAL_OUTPUT_REQUIRES_EXPLICIT_FLAG",
                "TA/TOPO sequence is a junction-model approximation; pass "
                "--allow-experimental-output to write it explicitly",
                {"method": args.method, "final_deliverable": False},
            )
        with open(args.out, "w", encoding="utf-8") as fh:
            SeqIO.write(product, fh, "genbank")
        result["out_file"] = args.out

    if args.json:
        jprint(result)
    else:
        print("%s: product %d bp (%s)" % (args.method, len(product.seq), topo))
        for n in notes:
            print("  note: %s" % n)
        print(str(product.seq))


def load_part(path):
    rec, _fmt = load_seq(path)
    return rec


if __name__ == "__main__":
    main()
