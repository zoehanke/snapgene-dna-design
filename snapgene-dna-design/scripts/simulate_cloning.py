# -*- coding: utf-8 -*-
"""simulate_cloning.py - Cloning simulations.

Methods:
  gibson         assemble multiple fragments in order (strict overlap checks)
  digest-ligate  linearize a circular vector and insert a fragment cut by a
                 restriction enzyme (explicit double-strand cut boundaries)

All failures use the unified error envelope
``{"ok": false, "error": {"code": ..., "message": ...}}`` and exit non-zero.
No product file is written after a failed assembly.
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
    overhang_end, validate_origins, validate_unique_contributions,
)
from construct_model import ConstructModel
from sg_common import get_enzyme, jfail, jprint, load_seq, restriction_hits, topology


def load_part(path):
    rec, _fmt = load_seq(path)
    return rec


def _merge_parts_in_biological_order(parts, operator):
    """Merge only adjacent same-strand parts, never reorder.

    ``operator=order`` locations are returned unchanged so their biological
    part order and operator are preserved. ``operator=join`` locations may be
    merged only when the parts are contiguous in the input order.
    """
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    if operator != "join":
        from Bio.SeqFeature import CompoundLocation
        return CompoundLocation(parts, operator=operator)
    merged = [parts[0]]
    for loc in parts[1:]:
        prev = merged[-1]
        if prev.strand == loc.strand:
            if (prev.strand in (1, None) and prev.end == loc.start) or \
               (prev.strand == -1 and prev.start == loc.end):
                merged[-1] = FeatureLocation(
                    min(prev.start, loc.start), max(prev.end, loc.end),
                    strand=prev.strand)
            else:
                merged.append(loc)
        else:
            merged.append(loc)
    if len(merged) == 1:
        return merged[0]
    from Bio.SeqFeature import CompoundLocation
    return CompoundLocation(merged, operator=operator)


def _mapped_part_segments(part, trim_start, clip_end, offset, circular,
                          is_first, product_length):
    """Map one FeatureLocation part into product coordinates.

    Returns (segments, dropped_overlap). ``segments`` are FeatureLocation
    objects in the order their source bases appear along the feature
    (ascending source coordinates for strand +1, descending for strand -1).
    """
    start = int(part.start)
    end = int(part.end)
    retained_start = max(start, trim_start)
    retained_end = min(end, clip_end)
    overlap_start = max(start, 0)
    overlap_end = min(end, trim_start)
    retained_segment = None
    overlap_segment = None
    dropped = False

    if retained_end > retained_start:
        retained_segment = FeatureLocation(
            offset + retained_start - trim_start,
            offset + retained_end - trim_start,
            strand=part.strand)
    if overlap_end > overlap_start:
        if circular:
            target = (product_length - trim_start if is_first
                      else offset - trim_start)
            overlap_segment = FeatureLocation(
                target + overlap_start, target + overlap_end,
                strand=part.strand)
        else:
            dropped = True

    # Source biological order: strand +1 reads overlap (lower coords) then
    # retained (higher coords); strand -1 reads retained then overlap.
    if part.strand == -1:
        segments = [seg for seg in (retained_segment, overlap_segment) if seg]
    else:
        segments = [seg for seg in (overlap_segment, retained_segment) if seg]
    return segments, dropped


def _shift_features(record, offset, trim_start=0, clip_end=None,
                    circular=False, is_first=False, product_length=None,
                    product_seq=None):
    """Copy features into product coordinates while preserving extract().

    * Original CompoundLocation part order and operator are preserved.
    * A single FeatureLocation split by a circular overlap becomes a
      ``join`` CompoundLocation whose parts are ordered so the extracted
      sequence is unchanged.
    * Every migrated feature is verified by re-extracting it from the
      product sequence; a mismatch raises
      ``AssemblyError("FEATURE_MIGRATION_MISMATCH")``.
    * Features partially removed by a *linear* overlap are dropped with an
      explicit warning.
    """
    if clip_end is None:
        clip_end = len(record.seq)
    out = []
    warnings = []
    for feature in record.features:
        source_extract = str(feature.extract(record.seq)).upper()
        original_parts = getattr(feature.location, "parts", None)
        operator = getattr(feature.location, "operator", "join")
        if original_parts is None:
            parts = [feature.location]
            operator = "join"
        else:
            parts = list(original_parts)

        migrated_parts = []
        dropped_any = False
        for part in parts:
            segments, dropped = _mapped_part_segments(
                part, trim_start, clip_end, offset, circular, is_first,
                product_length)
            migrated_parts.extend(segments)
            dropped_any = dropped_any or dropped

        if dropped_any:
            label = feature.qualifiers.get(
                "label", [feature.id or "feature"])[0]
            warnings.append(
                "feature %r was partially dropped because it lies in a "
                "removed linear overlap" % label)
            continue
        if not migrated_parts:
            continue

        updated = copy.deepcopy(feature)
        updated.location = _merge_parts_in_biological_order(
            migrated_parts, operator)
        migrated_extract = str(updated.extract(Seq(product_seq))).upper()
        if migrated_extract != source_extract:
            raise AssemblyError(
                "FEATURE_MIGRATION_MISMATCH",
                "feature %r changed sequence during assembly: source %r vs "
                "product %r"
                % (feature.qualifiers.get("label", [feature.id or "feature"])[0],
                   source_extract, migrated_extract),
                details={
                    "feature": feature.id or feature.qualifiers.get("label", ["feature"])[0],
                    "source_extract": source_extract,
                    "product_extract": migrated_extract,
                    "source_location": str(feature.location),
                    "product_location": str(updated.location),
                },
            )
        out.append(updated)
    return out, warnings


def gibson(parts, overlap=0, circular=False):
    """Assemble parts in order with strict pairwise overlap validation.

    ``circular=True`` also validates the closing last->first overlap and
    removes one additional duplicated overlap. Returns
    (product_record, fragments, contributions, warnings).
    """
    fragments = [
        gibson_fragment(rec.name or "fragment%d" % i, str(rec.seq))
        for i, rec in enumerate(parts)
    ]
    check_gibson_overlaps(fragments, overlap, method="gibson", circular=circular)
    contributions = validate_unique_contributions(fragments, overlap, circular)
    final_seq = join_by_homology(fragments, overlap, circular=circular)

    product = copy.deepcopy(parts[0])
    product.seq = Seq(final_seq)
    product.id = "product"
    product.name = "product"
    product.description = "gibson assembly product"
    product.annotations.setdefault("molecule_type", "DNA")
    product.features = []
    warnings = []
    offset = 0
    for i, rec in enumerate(parts):
        trim_start = overlap if (i > 0 or circular) else 0
        features, feature_warnings = _shift_features(
            rec, offset, trim_start=trim_start, clip_end=len(rec.seq),
            circular=circular, is_first=(i == 0),
            product_length=len(final_seq), product_seq=final_seq)
        product.features.extend(features)
        warnings.extend(feature_warnings)
        offset += contributions[i]
    return product, fragments, contributions, warnings


def _arc(seq, start0, end0):
    n = len(seq)
    if n == 0:
        return ""
    start0 %= n
    end0 %= n
    length = (end0 - start0) % n
    if length == 0:
        return ""
    doubled = seq + seq
    return doubled[start0:start0 + length]


def _hit_end_sequences(seq, hit):
    """Return (kind, left_sequence, right_sequence) for one cut pair.

    The kind follows the signed relation between the raw top and bottom cut
    boundaries (blunt / 5'-overhang / 3'-overhang). ``left_sequence`` is the
    actual 5'->3' single-stranded extension on the downstream fragment;
    ``right_sequence`` is the complementary extension on the upstream
    fragment.
    """
    raw_t = hit.get("raw_top_cut_boundary_0based", hit["top_cut_boundary_0based"])
    raw_b = hit.get("raw_bottom_cut_boundary_0based", hit["bottom_cut_boundary_0based"])
    t = hit["top_cut_boundary_0based"]
    b = hit["bottom_cut_boundary_0based"]
    if raw_t == raw_b:
        return "blunt", "", ""
    if raw_t < raw_b:
        region = _arc(seq, t, b)
        return "5'-overhang", region, str(Seq(region).reverse_complement())
    region = _arc(seq, b, t)
    return "3'-overhang", str(Seq(region).reverse_complement()), region


def _vector_fragment(vector_rec, enzyme):
    """Linearize a circular vector at its unique enzyme site.

    Returns (AssemblyFragment, cut0). The fragment itself is linear; only the
    final product is circular.
    """
    seq = str(vector_rec.seq).upper()
    hits = restriction_hits(seq, enzyme, circular=True)
    hits = [h for h in hits if h["cuts_within_sequence"]]
    if topology(vector_rec) != "circular":
        raise AssemblyError(
            "INVALID_TOPOLOGY",
            "digest-ligate requires a circular vector; got %s" % topology(vector_rec),
        )
    if len(hits) != 1:
        raise AssemblyError(
            "SITE_COUNT",
            "digest-ligate requires exactly 1 vector recognition site; found %d"
            % len(hits),
        )
    hit = hits[0]
    kind, left_ov, right_ov = _hit_end_sequences(seq, hit)
    source_cut = hit["top_cut_boundary_0based"] % len(seq)
    vector_frag = AssemblyFragment(
        vector_rec.name or "vector", seq, topology="linear",
        left_end=overhang_end(kind, left_ov, 0, source_cut_boundary=source_cut),
        right_end=overhang_end(kind, right_ov, len(seq),
                               source_cut_boundary=source_cut),
        source=vector_rec.id,
    )
    return vector_frag, source_cut


def _restriction_insert_fragment(insert_rec, enzyme):
    """Excise the internal fragment between exactly two restriction sites.

    Unlike Type IIS parts, the overhang kind is derived per cut from the
    signed top/bottom boundary relation, so blunt, 5'-overhang and
    3'-overhang enzymes all work.
    """
    seq = str(insert_rec.seq).upper()
    circular = topology(insert_rec) == "circular"
    hits = restriction_hits(seq, enzyme, circular=circular)
    hits = [h for h in hits if h["cuts_within_sequence"]]
    if len(hits) != 2:
        raise AssemblyError(
            "SITE_COUNT",
            "digest-ligate requires exactly 2 insert recognition sites with "
            "in-sequence cuts; found %d" % len(hits),
        )
    site = str(enzyme.site).upper()
    rc_site = str(Seq(site).reverse_complement()).upper()
    h1, h2 = hits
    t1 = h1["top_cut_boundary_0based"] % len(seq)
    t2 = h2["top_cut_boundary_0based"] % len(seq)
    frag_a = _arc(seq, t1, t2)
    frag_b = _arc(seq, t2, t1)
    chosen = None
    for fragment, left_hit, right_hit in ((frag_a, h1, h2), (frag_b, h2, h1)):
        up = fragment.upper()
        if fragment and site not in up and rc_site not in up:
            chosen = (fragment, left_hit, right_hit)
            break
    if chosen is None:
        raise AssemblyError(
            "INSERT_EXCISION_FAILED",
            "no internal insert fragment free of intact %s recognition sites "
            "(check site orientation or cuts outside the sequence)" % str(enzyme),
        )
    fragment, left_hit, right_hit = chosen
    left_kind, left_ov, _left_right = _hit_end_sequences(seq, left_hit)
    right_kind, _right_left, right_ov = _hit_end_sequences(seq, right_hit)
    insert_frag = AssemblyFragment(
        insert_rec.name or "insert", fragment, topology="linear",
        left_end=overhang_end(
            left_kind, left_ov, 0,
            source_cut_boundary=left_hit["top_cut_boundary_0based"] % len(seq)),
        right_end=overhang_end(
            right_kind, right_ov, len(fragment),
            source_cut_boundary=right_hit["top_cut_boundary_0based"] % len(seq)),
        source=insert_rec.id,
    )
    return insert_frag


def digest_ligate(vector_rec, insert_rec, enzyme_name):
    """Sticky-end ligation using the shared end model.

    Vector and insert ends are derived from the signed double-strand cut
    geometry (blunt / 5'-overhang / 3'-overhang), validated, and only then
    assembled into a circular product.
    """
    enzyme = get_enzyme(enzyme_name)
    vector_frag, vector_cut0 = _vector_fragment(vector_rec, enzyme)
    insert_frag = _restriction_insert_fragment(insert_rec, enzyme)

    junctions = check_sticky_junctions([vector_frag, insert_frag], circular=True)
    if any(j["compatibility"] == "MISMATCH" for j in junctions):
        raise AssemblyError(
            "STICKY_END_MISMATCH",
            "digest-ligation sticky ends are not complementary: %s"
            % "; ".join("%s: %s" % (j["between"], j["compatibility"]) for j in junctions),
            details=junctions,
        )

    ins_seq = insert_frag.sequence
    # Feature-migrating edit: open the circular vector at the top cut and
    # insert the excised fragment, then re-circularize.
    model = ConstructModel(vector_rec).insert(vector_cut0, ins_seq)
    model.set_topology("circular")
    product = model.to_record()
    product.id = "product"
    product.name = "product"
    product.description = "digest-ligation product"
    product.features.append(SeqFeature(
        FeatureLocation(vector_cut0, vector_cut0 + len(ins_seq), strand=1),
        type="misc_feature", qualifiers={"label": ["insert"]},
    ))
    return product, [vector_frag, insert_frag], junctions


def main():
    p = argparse.ArgumentParser(description="Simulate cloning assembly")
    p.add_argument("--method", choices=["gibson", "digest-ligate"], required=True)
    p.add_argument("--parts", nargs="+", help="fragment files (gibson)")
    p.add_argument("--overlap", type=int, default=0, help="shared overlap bp between adjacent parts (gibson)")
    p.add_argument("--vector", help="vector file (digest-ligate)")
    p.add_argument("--insert", help="insert file (digest-ligate)")
    p.add_argument("--enzyme", help="restriction enzyme name (digest-ligate)")
    p.add_argument("--topology", choices=["circular", "linear"], default=None,
                   help="product topology (gibson only)")
    p.add_argument("--out", help="write product GenBank to this path")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    try:
        if args.method == "gibson":
            if not args.parts or len(args.parts) < 2:
                raise AssemblyError(
                    "INVALID_INPUT", "gibson requires --parts with >=2 files")
            if args.overlap <= 0:
                raise AssemblyError(
                    "INVALID_OVERLAP", "gibson requires a positive --overlap")
            parts = [load_part(x) for x in args.parts]
            product_topology = args.topology or topology(parts[0])
            circular = product_topology == "circular"
            product, fragments, contributions, warnings = gibson(
                parts, args.overlap, circular=circular)
            if not (15 <= args.overlap <= 40):
                warnings.append(
                    "overlap %d bp is outside the published Gibson 15-40 bp "
                    "working range (Gibson 2009 DOI 10.1038/nmeth.1318); "
                    "this simulation is sequence-level only" % args.overlap)
            if len(parts) > 5:
                warnings.append(
                    "Gibson with %d fragments exceeds the recommended 4-5 "
                    "fragment range (Gibson 2009); validate assembly "
                    "efficiency empirically" % len(parts))
            product.annotations["topology"] = product_topology
            origins = []
            offset = 0
            product_len = len(product.seq)
            for i, frag in enumerate(fragments):
                source_len = len(frag.sequence)
                trim_start = args.overlap if (i > 0 or circular) else 0
                retained_len = source_len - trim_start
                contribution_segments = [{
                    "source_start": trim_start + 1,
                    "source_end": source_len,
                    "product_start": offset + 1,
                    "product_end": offset + retained_len,
                }]
                source_mappings = []
                if trim_start > 0:
                    if circular:
                        if i == 0:
                            product_ov_start = product_len - args.overlap + 1
                            product_ov_end = product_len
                        else:
                            product_ov_start = offset - args.overlap + 1
                            product_ov_end = offset
                        source_mappings.append({
                            "source_start": 1,
                            "source_end": args.overlap,
                            "product_start": product_ov_start,
                            "product_end": product_ov_end,
                            "wraps_origin": (i == 0),
                        })
                    else:
                        source_mappings.append({
                            "source_start": 1,
                            "source_end": args.overlap,
                            "product_start": None,
                            "product_end": None,
                            "dropped": True,
                            "wraps_origin": False,
                        })
                source_mappings.append({
                    "source_start": trim_start + 1,
                    "source_end": source_len,
                    "product_start": offset + 1,
                    "product_end": offset + retained_len,
                    "wraps_origin": False,
                })
                origins.append({
                    "part": args.parts[i], "name": frag.name,
                    "start": offset + 1, "end": offset + contributions[i],
                    "length": contributions[i],
                    "source_start": trim_start + 1,
                    "source_end": source_len,
                    "product_start": offset + 1,
                    "product_end": offset + contributions[i],
                    "contribution_segments": contribution_segments,
                    "source_mappings": source_mappings,
                })
                offset += contributions[i]
            validate_origins(origins, product_len)
        else:
            if not (args.vector and args.insert and args.enzyme):
                raise AssemblyError(
                    "INVALID_INPUT",
                    "digest-ligate requires --vector --insert --enzyme")
            vector_rec = load_part(args.vector)
            insert_rec = load_part(args.insert)
            product, fragments, junctions = digest_ligate(
                vector_rec, insert_rec, args.enzyme)
            product_topology = "circular"
            origins = [
                {"part": args.vector, "name": vector_rec.name, "role": "vector-backbone",
                 "length": len(vector_rec.seq)},
                {"part": args.insert, "name": insert_rec.name, "role": "insert-fragment",
                 "length": len(fragments[1].sequence)},
            ]
    except AssemblyError as error:
        jfail(error.code, error.message, error.details)
    except (OSError, ValueError) as error:
        jfail("INVALID_INPUT", str(error))

    result = {
        "method": args.method,
        "experimental": args.method == "digest-ligate",
        "product_length": len(product.seq),
        "topology": product_topology,
        "origins": origins,
        "fragments": [fragment.to_dict() for fragment in fragments],
        "junctions": junctions if args.method == "digest-ligate" else [],
        "warnings": warnings if args.method == "gibson" else [],
        "feature_count": len(product.features),
        "product_sequence": str(product.seq),
    }
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            SeqIO.write(product, fh, "genbank")
        result["out_file"] = args.out

    if args.json:
        jprint(result)
    else:
        print("%s: product %d bp  topology: %s" % (args.method, len(product.seq), product_topology))
        for o in origins:
            print("  %s: %s (%d bp)" % (o.get("role", "part"), o["name"], o["length"]))
        for j in result["junctions"]:
            print("  junction %s [%s]" % (j["between"], j["compatibility"]))
        print("product sequence:")
        print(str(product.seq))
        if args.out:
            print("written to", args.out)


if __name__ == "__main__":
    main()
