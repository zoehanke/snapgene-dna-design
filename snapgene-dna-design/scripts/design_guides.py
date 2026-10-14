# -*- coding: utf-8 -*-
"""design_guides.py - Deterministic guide-RNA candidate scanner.

PAM rules come exclusively from ``references/nuclease-registry.json``.
All output coordinates are on the **input reference axis** (0-based
half-open).  Reverse-strand candidates are scanned on the reverse-complement
sequence internally, then mapped back to the reference axis with the
transformation ``reference = [n - scan_end, n - scan_start)``.

Linear sequences never wrap: both PAM and protospacer must fit completely
inside ``[0, n)``.  Circular sequences may wrap and every wrapped interval is
expressed as explicit reference-axis segments in ``coordinates``.
"""
import argparse
import json
import pathlib
import sys

from Bio.Seq import Seq

from sg_common import jprint, load_seq, topology
from provenance import source, source_id, now_iso, read_version

REGISTRY_PATH = pathlib.Path(__file__).resolve().parents[1] / "references" / "nuclease-registry.json"


def load_registry(path=None):
    path = pathlib.Path(path or REGISTRY_PATH)
    data = json.loads(path.read_text(encoding="utf-8"))
    return {entry["id"]: entry for entry in data["nucleases"]}


def _iupac_compatible(pattern_base, sequence_base):
    pattern_base = pattern_base.upper()
    sequence_base = sequence_base.upper()
    if pattern_base == "N":
        return True
    if pattern_base == "V":
        return sequence_base in "ACG"
    if pattern_base == "B":
        return sequence_base in "CGT"
    if pattern_base == "D":
        return sequence_base in "AGT"
    if pattern_base == "H":
        return sequence_base in "ACT"
    if pattern_base == "W":
        return sequence_base in "AT"
    if pattern_base == "S":
        return sequence_base in "CG"
    if pattern_base == "M":
        return sequence_base in "AC"
    if pattern_base == "K":
        return sequence_base in "GT"
    if pattern_base == "R":
        return sequence_base in "AG"
    if pattern_base == "Y":
        return sequence_base in "CT"
    return pattern_base == sequence_base


def pam_matches(seq, pattern):
    if len(seq) != len(pattern):
        return False
    return all(_iupac_compatible(p, s) for p, s in zip(pattern, seq))


def _arc(dna, start, length):
    """Circular slice. ``start`` is an unwrapped (possibly >= n) offset."""
    if length <= 0:
        return ""
    n = len(dna)
    if not n:
        return ""
    start %= n
    return (dna + dna)[start:start + length]


def _circular_segments(start, length, n):
    """Explicit 0-based half-open segments for a circular interval.

    ``start`` is an unwrapped offset.  Returns non-wrapping contiguous
    segments (for example ``[[36, 38], [0, 18]]``).
    """
    if length <= 0 or n <= 0:
        return []
    origin_start = start % n
    origin_end = (start + length) % n
    if not (start != origin_start or (start + length) != origin_end) and \
            origin_start + length <= n:
        return [[origin_start, origin_start + length]]
    first = [origin_start, n]
    second = [0, origin_end]
    if second[1] > second[0]:
        return [first, second]
    return [first]


def _scan_interval_to_reference(start, length, n, strand, circular):
    """Map a scan-axis interval to reference-axis fields.

    ``strand`` is 1 (forward) or -1 (reverse).  Returns
    ``(reference_start, reference_end, wraps_origin, segments)`` where
    reference_start/end are normalized 0-based half-open coordinates and
    ``wraps_origin`` means the interval crosses the origin.
    """
    if n <= 0:
        return 0, 0, False, []
    start %= n
    if strand == 1:
        ref_start = start
    else:
        # rc[k] corresponds to dna[n-1-k].  The reverse-complement image of
        # rc[start:start+length) is dna[n-(start+length):n-start) on a
        # circular molecule.
        ref_start = (n - ((start + length) % n)) % n

    if not circular:
        # Linear molecules never wrap.  Keep n as an explicit boundary:
        # an interval ending exactly at n is written as [s, n), never as
        # [s, 0) with an empty second segment.
        if length > n:
            ref_start, ref_end, wraps_origin = 0, 0, False
        else:
            ref_end = ref_start + length
            wraps_origin = False
        segments = _linear_segments(ref_start, ref_end, n)
        return ref_start, ref_end, wraps_origin, segments

    if length == n:
        segments = [[0, n]]
        return 0, n, False, segments
    if length > n:
        segments = [[0, n]]
        return 0, 0, True, segments

    unwrapped_end = ref_start + length
    wraps_origin = unwrapped_end > n
    # An interval ending exactly at n does not wrap: preserve the n
    # boundary so the scalar fields and explicit segments agree.
    ref_end = unwrapped_end % n if wraps_origin else unwrapped_end
    segments = _circular_segments(ref_start, length, n)
    return ref_start, ref_end, wraps_origin, segments


def _linear_segments(start, end, n):
    if start < 0 or end > n or start > end:
        return []
    return [[start, end]]


def _slice_circular(dna, start, length, n):
    if length <= 0 or n == 0:
        return ""
    start %= n
    return _arc(dna, start, length)


def _user_1based(segments):
    return [[segment[0] + 1, segment[1]] for segment in segments]


def _candidate_coordinates(n, strand, scan_pam_start, pam_length,
                           scan_protospacer_start, spacer_length, circular):
    pam_ref_start, pam_ref_end, pam_wraps, pam_segments = \
        _scan_interval_to_reference(scan_pam_start, pam_length, n, strand, circular)
    protospacer_ref_start, protospacer_ref_end, protospacer_wraps, protospacer_segments = \
        _scan_interval_to_reference(scan_protospacer_start, spacer_length,
                                    n, strand, circular)
    return {
        "coordinate_system": "0-based-half-open-reference-axis",
        "axis": "reference",
        "strand": "forward" if strand == 1 else "reverse",
        "protospacer_start": protospacer_ref_start,
        "protospacer_end": protospacer_ref_end,
        "pam_start": pam_ref_start,
        "pam_end": pam_ref_end,
        "wraps_origin": bool(protospacer_wraps or pam_wraps),
        "protospacer_segments": protospacer_segments,
        "pam_segments": pam_segments,
        "user_coordinates_1based_inclusive": {
            "protospacer_segments": _user_1based(protospacer_segments),
            "pam_segments": _user_1based(pam_segments),
        },
    }


def _region_overlaps(segments, region):
    """True when any reference-axis segment overlaps ``[start, end)``."""
    start, end = region
    if start >= end:
        return False
    for seg_start, seg_end in segments:
        if seg_start < end and start < seg_end:
            return True
    return False



def _context_sequences(seq, n, circular, nuc, scan_pam_start, pam_length,
                       scan_protospacer_start, spacer_length):
    """Model contexts on the same strand axis used for scanning.

    Returned values are None when a linear sequence does not contain the
    required flanking bases.
    """
    def _take(start, length):
        if circular:
            return _arc(seq, start, length)
        if start < 0 or start + length > n:
            return None
        return seq[start:start + length]

    contexts = {}
    family = (nuc.get("family") or "").lower()
    if family == "cas9" and nuc.get("pam_side") == "3prime":
        # Azimuth: 4 upstream + 20 protospacer + 3 PAM + 3 downstream.
        contexts["azimuth_30mer"] = _take(
            scan_protospacer_start - 4, 4 + spacer_length + pam_length + 3)
    if family == "cas12a" and nuc.get("pam_side") == "5prime":
        # DeepCpf1 (CRISPRseek semantics): 4 upstream + 4 PAM + 20 gRNA
        # + 6 downstream; the model consumes the 20 PAM-proximal bases of
        # the longer AsCas12a spacer.
        contexts["deepcpf1_34mer"] = _take(
            scan_pam_start - 4, 4 + pam_length + min(20, spacer_length) + 6)
    return contexts


def scan_guides(record, nuclease_id, region=None, registry=None,
                max_candidates=1000):
    """Scan linear/circular DNA for guide candidates.

    ``region`` is an optional 0-based half-open interval [start, end) on the
    input reference axis.  A candidate is kept when its PAM or protospacer
    reference segments overlap the region.

    Returns a list of candidate dictionaries with provenance.  All candidate
    coordinates are on the input reference axis.
    """
    registry = registry or load_registry()
    if nuclease_id not in registry:
        raise ValueError("UNKNOWN_NUCLEASE: %s" % nuclease_id)
    nuc = registry[nuclease_id]
    if not nuc["pam_patterns"] or not nuc["spacer_lengths"]:
        raise ValueError("INVALID_PAM_DEFINITION: %s" % nuclease_id)

    dna = str(record.seq).upper()
    circular = topology(record) == "circular"
    n = len(dna)
    if region is None:
        start, end = 0, n
    else:
        start, end = int(region[0]), int(region[1])
    if not (0 <= start <= end <= n):
        raise ValueError("TARGET_REGION_OUT_OF_RANGE")

    if n == 0:
        return []

    candidates = []
    pam_length = len(nuc["pam_patterns"][0])
    spacer_lengths = set(nuc["spacer_lengths"])
    pam_side = nuc["pam_side"]
    version = read_version()

    for strand, seq, strand_name in ((1, dna, "forward"),
                                     (-1, str(Seq(dna).reverse_complement()), "reverse")):
        # Scan PAM anchors.  For linear molecules the PAM must lie fully
        # inside the sequence; for circular molecules every anchor is valid.
        pam_positions = range(n) if circular else range(0, n - pam_length + 1)
        for pattern in nuc["pam_patterns"]:
            for i in pam_positions:
                pam = _arc(seq, i, pam_length)
                if not pam_matches(pam, pattern):
                    continue
                for spacer_len in spacer_lengths:
                    if pam_side == "3prime":
                        scan_protospacer_start = i - spacer_len
                        scan_pam_start = i
                    else:
                        scan_protospacer_start = i + pam_length
                        scan_pam_start = i
                    scan_protospacer_end = scan_protospacer_start + spacer_len
                    # Linear topology: neither PAM nor protospacer may wrap.
                    if not circular and (
                            scan_protospacer_start < 0
                            or scan_protospacer_end > n
                            or scan_pam_start < 0
                            or scan_pam_start + pam_length > n):
                        continue
                    protospacer = _arc(seq, scan_protospacer_start, spacer_len)
                    coordinates = _candidate_coordinates(
                        n, strand, scan_pam_start, pam_length,
                        scan_protospacer_start, spacer_len, circular)
                    if not _region_overlaps(
                            coordinates["protospacer_segments"], (start, end)) and \
                            not _region_overlaps(
                                coordinates["pam_segments"], (start, end)):
                        continue
                    if any(base not in "ACGT" for base in protospacer):
                        warning = "AMBIGUOUS_TARGET_SEQUENCE: protospacer contains non-ACGT base"
                    else:
                        warning = None
                    reference_sequence = _slice_circular(
                        dna, coordinates["protospacer_start"],
                        spacer_len, n)
                    context_sequences = _context_sequences(
                        seq, n, circular, nuc, scan_pam_start,
                        pam_length, scan_protospacer_start, spacer_len)
                    candidates.append({
                        "id": None,
                        "nuclease": nuclease_id,
                        "strand": strand_name,
                        "protospacer_sequence": protospacer,
                        "protospacer_reference_sequence": reference_sequence,
                        "pam_sequence": pam,
                        "pam_pattern": pattern,
                        "pam_side": pam_side,
                        "coordinates": coordinates,
                        "context_sequences": context_sequences,
                        "warning": warning,
                        "provenance": [source(
                            "software", "SnapGene DNA Design PAM Scanner",
                            "guide-candidate-search", version=version,
                            status="verified",
                            verification={"method": "unit-tests", "status": "verified"})],
                    })
                    if len(candidates) >= max_candidates:
                        return _assign_ids(candidates)
    return _assign_ids(candidates)


def _assign_ids(candidates):
    for idx, candidate in enumerate(candidates):
        candidate["id"] = "gRNA-%03d" % (idx + 1)
        candidate["provenance"][0]["source_id"] = source_id(candidate["provenance"][0])
    return candidates


def _format_user_interval(segments):
    return ";".join("%d-%d" % (seg[0] + 1, seg[1]) for seg in segments)


def main():
    parser = argparse.ArgumentParser(description="Scan gRNA candidates from registry PAM rules")
    parser.add_argument("source")
    parser.add_argument("--nuclease", required=True,
                        help="registry nuclease id, e.g. spcas9-wt")
    parser.add_argument("--region", nargs=2, type=int,
                        help="optional 0-based half-open start end")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        record, _ = load_seq(args.source)
        candidates = scan_guides(record, args.nuclease, region=args.region)
    except (ValueError, OSError) as error:
        print(json.dumps({"ok": False, "error": {"code": str(error).split(":")[0],
                                                 "message": str(error)}},
                         ensure_ascii=False, indent=2))
        return 1
    result = {
        "schema_version": "0.8.0",
        "nuclease": args.nuclease,
        "source": args.source,
        "topology": topology(record),
        "candidate_count": len(candidates),
        "candidates": candidates,
        "generated_at": now_iso(),
        "provenance": [source(
            "software", "SnapGene DNA Design PAM Scanner",
            "guide-candidate-search", version=read_version(),
            status="verified",
            verification={"method": "unit-tests", "status": "verified"})],
    }
    if args.json:
        jprint(result)
    else:
        print("%s: %d candidate(s)" % (args.nuclease, len(candidates)))
        for candidate in candidates:
            coords = candidate["coordinates"]
            print("%s %s %s PAM=%s protospacer(ref)=%s..%s[0bho) pam(ref)=%s..%s[0bho) %s" % (
                candidate["id"], candidate["strand"],
                candidate["protospacer_sequence"], candidate["pam_sequence"],
                coords["protospacer_start"], coords["protospacer_end"],
                coords["pam_start"], coords["pam_end"],
                candidate.get("warning") or ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
