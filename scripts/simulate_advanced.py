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

from assembly_model import (
    AssemblyError, AssemblyFragment, check_gibson_overlaps,
    check_sticky_junctions, gibson_fragment, join_by_homology,
    overhang_end, validate_unique_contributions,
)
from construct_model import ConstructModel
from sg_common import jfail, jprint, load_seq, topology
from simulate_cloning import _shift_features

# Gateway recombination-site sequences (standard Invitrogen/Thermo attB1/attB2
# set). attP/attL/attR sequences correspond to pDONR-family and pDEST-family
# vectors (verified against SnapGene's Gateway vector collection).
ATTB1 = "ACAAGTTTGTACAAAAAAGCAGGCT"
ATTB2 = "ACCCAGCTTTCTTGTACAAAGTGGT"

ATTL1 = ("CAAATAATGATTTTATTTTGACTGATAGTGACCTGTTCGTTGCAACAAATTGATGAGCAATGCTTTTTTATAATGCC"
         "AACTTTGTACAAAAAAGCAGGCT")
ATTL2 = ("CAAATAATGATTTTATTTTGACTGATAGTGACCTGTTCGTTGCAACAAATTGATAAGCAATGCTTTCTTATAATGCC"
         "AACTTTGTACAAGAAAGCTGGGT")

ATTR1 = ("ACAAGTTTGTACAAAAAAGCTGAACGAGAAACGTAAAATGATATAAATATCAATATATTAAATTAGATTTTGCATAAAA"
         "AACAGACTACATAATACTGTAAAACACAACATATCCAGTCACTATG")
ATTR2 = ("ACCACTTTGTACAAGAAAGCTGAACGAGAAACGTAAAATGATATAAATATCAATATATTAAATTAGATTTTGCATAAAA"
         "AACAGACTACATAATACTGTAAAACACAACATATCCAGTCACTATG")

ATTP1 = ("AAATAATGATTTTATTTTGACTGATAGTGACCTGTTCGTTGCAACAAATTGATGAGCAATGCTTTTTTATAATGCC"
         "AAGTTTGTACAAAAAAGCAGAACGAGAAACGTAAAATGATATAAATATCAATATATTAAATTAGATTTTGCATAAAA"
         "AACAGACTACATAATACTGTAAAACACAACATATCCAGTCACTATGAATCAACTACTTAGATGGTATTAGTGACCTGTA")
ATTP2 = ("AAATAATGATTTTATTTTGACTGATAGTGACCTGTTCGTTGCAACAAATTGATAAGCAATGCTTTCTTATAATGCC"
         "CACTTTGTACAAGAAAGCTGAACGAGAAACGTAAAATGATATAAATATCAATATATTAAATTAGATTTTGCATAAAA"
         "AACAGACTACATAATACTGTAAAACACAACATATCCAGTCACTATGAATCAACTACTTAGATGGTATTAGTGACCTGTA")


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


def _occurrences(seq, query):
    positions = []
    start = 0
    while True:
        pos = seq.find(query, start)
        if pos == -1:
            return positions
        positions.append(pos)
        start = pos + 1


def _require_explicit_circular(record, role):
    topo = record.annotations.get("topology")
    if topo is None:
        raise AssemblyError(
            "MISSING_TOPOLOGY",
            "%s record %r has no topology annotation; Gateway vectors must "
            "declare circular or linear explicitly" % (role, record.id or record.name),
        )
    if topo != "circular":
        raise AssemblyError(
            "INVALID_TOPOLOGY",
            "%s record %r is %s; Gateway %s must be circular" % (role, record.id or record.name, topo, role),
        )


def _strict_att_pair(seq, left_site, right_site, left_label, right_label,
                     right_site_reverse=True):
    """Enumerate every occurrence of both att sites in both orientations.

    Exactly one occurrence of each site in the expected orientation is
    accepted; any duplicate or wrong-orientation occurrence aborts.
    """
    left_rc = str(Seq(left_site).reverse_complement())
    right_expected = str(Seq(right_site).reverse_complement()) if right_site_reverse else right_site
    right_other = right_site if right_site_reverse else str(Seq(right_site).reverse_complement())

    left_good = _occurrences(seq, left_site)
    left_bad = _occurrences(seq, left_rc)
    right_good = _occurrences(seq, right_expected)
    right_bad = _occurrences(seq, right_other)

    if not left_good or not right_good:
        raise AssemblyError(
            "ATT_SITE_MISSING",
            "expected exactly one %s (forward) and one %s (%s) site; found %d and %d"
            % (left_label, right_label,
               "reverse" if right_site_reverse else "forward",
               len(left_good), len(right_good)),
            details={
                left_label: {"forward": left_good, "reverse": left_bad},
                right_label: {"expected": right_good, "wrong_orientation": right_bad},
            },
        )
    if len(left_good) != 1 or len(right_good) != 1:
        raise AssemblyError(
            "ATT_SITE_NOT_UNIQUE",
            "%s/%s sites must be unique; found %d / %d expected-orientation copies"
            % (left_label, right_label, len(left_good), len(right_good)),
            details={
                left_label: left_good, right_label: right_good,
                left_label + "_wrong_orientation": left_bad,
                right_label + "_wrong_orientation": right_bad,
            },
        )
    if left_bad or right_bad:
        raise AssemblyError(
            "ATT_SITE_ORIENTATION",
            "%s/%s found in wrong orientation as well (%d / %d extra copies)"
            % (left_label, right_label, len(left_bad), len(right_bad)),
            details={
                left_label + "_wrong_orientation": left_bad,
                right_label + "_wrong_orientation": right_bad,
            },
        )
    left_start, left_end = left_good[0], left_good[0] + len(left_site)
    right_start, right_end = right_good[0], right_good[0] + len(right_expected)
    if left_end > right_start:
        raise AssemblyError(
            "ATT_SITE_ORDER",
            "%s (ends %d) lies after %s (starts %d); expected left-to-right order"
            % (left_label, left_end, right_label, right_start),
            details={"left_end": left_end, "right_start": right_start},
        )
    return left_start, left_end, right_start, right_end


def _extract_body(seq, left_end, right_start):
    body = seq[left_end:right_start]
    if not body:
        raise AssemblyError("ATT_SITE_EMPTY", "no insert sequence between att sites")
    return body


def _shift_feature(feature, delta):
    updated = copy.deepcopy(feature)
    parts = getattr(feature.location, "parts", [feature.location])
    migrated = []
    for part in parts:
        migrated.append(FeatureLocation(
            int(part.start) + delta, int(part.end) + delta, strand=part.strand))
    if len(migrated) == 1:
        updated.location = migrated[0]
    else:
        from Bio.SeqFeature import CompoundLocation
        updated.location = CompoundLocation(
            migrated, operator=getattr(feature.location, "operator", "join"))
    return updated


def _features_between(record, start0, end0, delta):
    out = []
    for feature in record.features:
        parts = getattr(feature.location, "parts", [feature.location])
        starts = [int(p.start) for p in parts]
        ends = [int(p.end) for p in parts]
        if min(starts) >= start0 and max(ends) <= end0:
            out.append(_shift_feature(feature, delta))
    return out


def _replace_with_features(record, start0, end0, replacement, new_features):
    model = ConstructModel(record)
    if start0 > end0:
        raise AssemblyError(
            "ATT_SITE_ORDER",
            "wrapped Gateway site intervals are not supported by the feature-migrating editor",
        )
    model.replace(start0, end0, replacement)
    model.set_topology("circular")
    product = model.to_record()
    product.features.extend(new_features)
    return product


def gateway_bp(donor, insert):
    """BP reaction with strict, unique attP/attB site validation."""
    _require_explicit_circular(donor, "donor")
    d = str(donor.seq).upper()
    ins = str(insert.seq).upper()
    b1_start, b1_end, b2_start, b2_end = _strict_att_pair(
        ins, ATTB1, ATTB2, "attB1", "attB2", right_site_reverse=False)
    body = _extract_body(ins, b1_end, b2_start)
    p1_start, p1_end, p2_start, p2_end = _strict_att_pair(
        d, ATTP1, ATTP2, "attP1", "attP2", right_site_reverse=True)

    replacement = ATTL1 + body + str(Seq(ATTL2).reverse_complement())
    attl1_start = p1_start
    attl2_start = p1_start + len(ATTL1) + len(body)
    attl1_feature = SeqFeature(
        FeatureLocation(attl1_start, attl1_start + len(ATTL1), strand=1),
        type="protein_bind", qualifiers={"label": ["attL1"]})
    attl2_feature = SeqFeature(
        FeatureLocation(attl2_start, attl2_start + len(ATTL2), strand=-1),
        type="protein_bind", qualifiers={"label": ["attL2"]})
    insert_features = _features_between(
        insert, b1_end, b2_start, p1_start + len(ATTL1) - b1_end)
    if not insert_features:
        insert_features = [SeqFeature(
            FeatureLocation(p1_start + len(ATTL1), attl2_start, strand=1),
            type="misc_feature", qualifiers={"label": ["insert"]})]
    product = _replace_with_features(
        donor, p1_start, p2_end, replacement,
        [attl1_feature, attl2_feature] + insert_features)
    product.id = "product"
    product.name = "product"
    product.description = "gateway BP product"
    notes = [
        "BP: %d bp insert between attB1/attB2 recombined into attP1/attP2 "
        "donor and converted to attL1/attL2" % len(body),
    ]
    return product, body, notes


def gateway_lr(entry, destination):
    """LR reaction with strict, unique attL/attR site validation."""
    _require_explicit_circular(entry, "entry")
    _require_explicit_circular(destination, "destination")
    e = str(entry.seq).upper()
    d = str(destination.seq).upper()
    l1_start, l1_end, l2_start, l2_end = _strict_att_pair(
        e, ATTL1, ATTL2, "attL1", "attL2", right_site_reverse=True)
    body = _extract_body(e, l1_end, l2_start)
    r1_start, r1_end, r2_start, r2_end = _strict_att_pair(
        d, ATTR1, ATTR2, "attR1", "attR2", right_site_reverse=True)

    replacement = ATTB1 + body + str(Seq(ATTB2).reverse_complement())
    attb1_start = r1_start
    attb2_start = r1_start + len(ATTB1) + len(body)
    attb1_feature = SeqFeature(
        FeatureLocation(attb1_start, attb1_start + len(ATTB1), strand=1),
        type="protein_bind", qualifiers={"label": ["attB1"]})
    attb2_feature = SeqFeature(
        FeatureLocation(attb2_start, attb2_start + len(ATTB2), strand=-1),
        type="protein_bind", qualifiers={"label": ["attB2"]})
    insert_features = _features_between(
        entry, l1_end, l2_start, r1_start + len(ATTB1) - l1_end)
    if not insert_features:
        insert_features = [SeqFeature(
            FeatureLocation(r1_start + len(ATTB1), attb2_start, strand=1),
            type="misc_feature", qualifiers={"label": ["insert"]})]
    product = _replace_with_features(
        destination, r1_start, r2_end, replacement,
        [attb1_feature, attb2_feature] + insert_features)
    product.id = "product"
    product.name = "product"
    product.description = "gateway LR product"
    notes = [
        "LR: %d bp insert between attL1/attL2 recombined between attR1/attR2 "
        "and converted to attB1/attB2" % len(body),
    ]
    return product, body, notes


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
