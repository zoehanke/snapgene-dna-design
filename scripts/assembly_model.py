# -*- coding: utf-8 -*-
"""assembly_model.py - Unified end/fragment model for cloning simulations.

One structure is shared by Gibson, In-Fusion, Golden Gate, digest-ligation,
and TA/TOPO:

    Fragment:
        sequence          top strand 5' -> 3'
        topology          circular | linear
        left_end          FragmentEnd
        right_end         FragmentEnd

    FragmentEnd:
        kind              blunt | 5'-overhang | 3'-overhang
        overhang_sequence 5' -> 3' sequence of the single-stranded extension
                          (empty for blunt ends)
        cut_boundary      position of the cut that created this end, in the
                          fragment's own coordinates (0-based boundary)

Gibson / In-Fusion homology overlaps are represented as blunt ends plus an
optional ``homology_sequence`` on each end; joining removes the duplicated
homology from the downstream fragment.
"""
from Bio.Seq import Seq

END_KINDS = ("blunt", "5'-overhang", "3'-overhang")
VALID_TOPOLOGIES = ("linear", "circular")


class AssemblyError(Exception):
    """Error carrying the unified ``error.code`` for CLI failure envelopes."""
    def __init__(self, code, message, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


class FragmentEnd:
    def __init__(self, kind, overhang_sequence="", cut_boundary=None,
                 homology_sequence="", homology_length=0,
                 source_cut_boundary=None):
        if kind not in END_KINDS:
            raise ValueError("invalid end kind %r" % kind)
        self.kind = kind
        self.overhang_sequence = str(overhang_sequence).upper()
        self.cut_boundary = None if cut_boundary is None else int(cut_boundary)
        self.source_cut_boundary = (
            None if source_cut_boundary is None else int(source_cut_boundary))
        self.homology_sequence = str(homology_sequence).upper()
        self.homology_length = int(homology_length or len(self.homology_sequence))
        if self.kind == "blunt" and self.overhang_sequence:
            raise ValueError("blunt end must not carry an overhang sequence")
        if self.kind != "blunt" and not self.overhang_sequence:
            raise ValueError("%s end requires an overhang sequence" % self.kind)

    def to_dict(self):
        return {
            "kind": self.kind,
            "overhang_sequence": self.overhang_sequence,
            "cut_boundary": self.cut_boundary,
            "source_cut_boundary": self.source_cut_boundary,
            "homology_sequence": self.homology_sequence,
            "homology_length": self.homology_length,
        }


class AssemblyFragment:
    def __init__(self, name, sequence, topology="linear",
                 left_end=None, right_end=None, source=None):
        if topology not in VALID_TOPOLOGIES:
            raise ValueError("invalid topology %r" % topology)
        self.name = str(name)
        self.sequence = str(sequence).upper()
        self.topology = topology
        self.left_end = left_end or FragmentEnd("blunt", cut_boundary=0)
        self.right_end = right_end or FragmentEnd(
            "blunt", cut_boundary=len(self.sequence))
        self.source = source
        self._validate()

    def _validate(self):
        for end in (self.left_end, self.right_end):
            if end.cut_boundary is not None:
                if not (0 <= end.cut_boundary <= len(self.sequence)):
                    raise ValueError(
                        "cut boundary %d out of range for %r (length %d)"
                        % (end.cut_boundary, self.name, len(self.sequence))
                    )

    def to_dict(self):
        return {
            "name": self.name,
            "sequence": self.sequence,
            "topology": self.topology,
            "left_end": self.left_end.to_dict(),
            "right_end": self.right_end.to_dict(),
            "source": self.source,
        }


def blunt_end(cut_boundary, homology_sequence="", homology_length=0,
              source_cut_boundary=None):
    return FragmentEnd(
        "blunt", cut_boundary=cut_boundary,
        homology_sequence=homology_sequence, homology_length=homology_length,
        source_cut_boundary=source_cut_boundary,
    )


def overhang_end(kind, overhang_sequence, cut_boundary, source_cut_boundary=None):
    return FragmentEnd(kind, overhang_sequence=overhang_sequence,
                       cut_boundary=cut_boundary,
                       source_cut_boundary=source_cut_boundary)


def gibson_fragment(name, sequence, left_overlap="", right_overlap="",
                    topology="linear"):
    """Build a blunt-ended fragment carrying Gibson homology arms."""
    return AssemblyFragment(
        name, sequence, topology=topology,
        left_end=blunt_end(0, homology_sequence=left_overlap),
        right_end=blunt_end(len(str(sequence)), homology_sequence=right_overlap),
    )


def _check_one_overlap(prev, cur, ov, method, prev_idx, cur_idx):
    if len(prev.sequence) < ov or len(cur.sequence) < ov:
        raise AssemblyError(
            "OVERLAP_TOO_LONG",
            "%s overlap %d bp exceeds fragment %d or %d length (%d / %d)"
            % (method, ov, prev_idx, cur_idx, len(prev.sequence), len(cur.sequence))
        )
    left = prev.sequence[-ov:]
    right = cur.sequence[:ov]
    if left != right:
        raise AssemblyError(
            "OVERLAP_MISMATCH",
            "%s overlap between fragment %d (%s) and fragment %d (%s) "
            "does not match: '%s' vs '%s'"
            % (method, prev_idx, prev.name, cur_idx, cur.name, left, right)
        )
    prev.right_end.homology_sequence = left
    prev.right_end.homology_length = ov
    cur.left_end.homology_sequence = right
    cur.left_end.homology_length = ov


def validate_unique_contributions(fragments, overlap_length, circular=False):
    """Return per-fragment unique contributions or raise.

    Rejects fragments that contribute no unique sequence after overlap
    trimming, and circular products shorter than the overlap itself.
    """
    contributions = []
    for index, fragment in enumerate(fragments):
        if not circular and index == 0:
            contribution = len(fragment.sequence)
        else:
            contribution = len(fragment.sequence) - overlap_length
        if contribution <= 0:
            raise AssemblyError(
                "ZERO_CONTRIBUTION_FRAGMENT",
                "fragment %d (%s) contributes no unique sequence after "
                "%d bp overlap trimming"
                % (index, fragment.name, overlap_length),
                details={
                    "fragment_index": index,
                    "fragment_name": fragment.name,
                    "fragment_length": len(fragment.sequence),
                    "overlap_length": overlap_length,
                    "unique_contribution": contribution,
                },
            )
        contributions.append(contribution)

    product_length = sum(contributions)
    if circular and product_length < overlap_length:
        raise AssemblyError(
            "PRODUCT_SHORTER_THAN_OVERLAP",
            "circular product length %d is shorter than overlap %d"
            % (product_length, overlap_length),
            details={
                "product_length": product_length,
                "overlap_length": overlap_length,
            },
        )
    return contributions


def check_gibson_overlaps(fragments, overlap_length, method="gibson",
                          circular=False):
    """Strictly validate pairwise homology and unique contributions.

    ``circular=True`` additionally validates the closing last->first overlap
    and records it on the fragment ends. Raises AssemblyError on the first
    mismatch. Returns per-fragment unique contribution lengths.
    """
    ov = overlap_length
    if ov <= 0:
        raise AssemblyError(
            "INVALID_OVERLAP",
            "%s requires a positive overlap length (got %d)" % (method, ov)
        )
    if len(fragments) < 2:
        raise AssemblyError(
            "INVALID_INPUT", "%s requires at least 2 fragments" % method)
    for i in range(1, len(fragments)):
        _check_one_overlap(fragments[i - 1], fragments[i], ov, method, i - 1, i)
    if circular:
        _check_one_overlap(
            fragments[-1], fragments[0], ov, method,
            len(fragments) - 1, 0)
    contributions = validate_unique_contributions(fragments, ov, circular)
    if method in ("gibson", "overlap") and ov < 12:
        raise AssemblyError(
            "OVERLAP_TOO_SHORT_FOR_EXECUTION",
            "%s overlap %d bp is below the hard execution floor of 12 bp"
            % (method, ov),
            details={"overlap_length": ov, "recommended_range": [15, 30]},
        )
    return contributions


def validate_origins(origins, product_length):
    """Hard coordinate invariants for assembly origin metadata.

    Raises AssemblyError with stable codes instead of relying on assert.
    """
    if sum(int(origin["length"]) for origin in origins) != product_length:
        raise AssemblyError(
            "ORIGIN_LENGTH_MISMATCH",
            "origin contribution lengths do not sum to product length",
            details={
                "sum": sum(int(o["length"]) for o in origins),
                "product_length": product_length,
            },
        )
    for origin in origins:
        if int(origin["length"]) <= 0:
            raise AssemblyError(
                "ORIGIN_COORDINATE_INVALID",
                "origin %r has non-positive length" % origin.get("name"),
                details=origin)
        if not (1 <= int(origin["start"]) <= int(origin["end"]) <= product_length):
            raise AssemblyError(
                "ORIGIN_COORDINATE_INVALID",
                "origin %r has invalid product interval %s..%s"
                % (origin.get("name"), origin.get("start"), origin.get("end")),
                details=origin)
        for segment in origin.get("contribution_segments", []):
            if not (segment["source_start"] <= segment["source_end"]):
                raise AssemblyError(
                    "SOURCE_MAPPING_INVALID",
                    "contribution segment has inverted source interval",
                    details=segment)
            if not (1 <= segment["product_start"] <= segment["product_end"] <= product_length):
                raise AssemblyError(
                    "ORIGIN_COORDINATE_INVALID",
                    "contribution segment product interval %s..%s out of range"
                    % (segment["product_start"], segment["product_end"]),
                    details=segment)
        for mapping in origin.get("source_mappings", []):
            if mapping.get("dropped"):
                if mapping.get("product_start") is not None or mapping.get("product_end") is not None:
                    raise AssemblyError(
                        "SOURCE_MAPPING_INVALID",
                        "dropped source mapping must not have product coordinates",
                        details=mapping)
                continue
            if not (mapping["source_start"] <= mapping["source_end"]):
                raise AssemblyError(
                    "SOURCE_MAPPING_INVALID",
                    "source mapping has inverted source interval",
                    details=mapping)
            if not (1 <= mapping["product_start"] <= product_length
                    and 1 <= mapping["product_end"] <= product_length):
                raise AssemblyError(
                    "ORIGIN_COORDINATE_INVALID",
                    "source mapping product interval %s..%s out of range"
                    % (mapping["product_start"], mapping["product_end"]),
                    details=mapping)


def join_by_homology(fragments, overlap_length, circular=False):
    """Return the Gibson/In-Fusion product sequence after removing overlaps.

    For a circular assembly the closing overlap is removed as well: the
    product is linearized immediately after the first fragment's left
    homology arm, so every fragment contributes ``sequence[overlap:]`` and
    the last->first junction closes across the origin.
    """
    if circular:
        return "".join(fragment.sequence[overlap_length:] for fragment in fragments)
    parts = [fragments[0].sequence]
    for i in range(1, len(fragments)):
        parts.append(fragments[i].sequence[overlap_length:])
    return "".join(parts)


def _complement(seq):
    return str(Seq(seq).reverse_complement())


def compatible_sticky(left, right):
    """True when a left fragment end and a right fragment end can anneal.

    ``overhang_sequence`` stores the actual 5'->3' single-stranded extension
    on each fragment, so two compatible ends must be the same kind, same
    length, and complementary.
    """
    if left.kind == "blunt" and right.kind == "blunt":
        return True
    if left.kind != right.kind:
        return False
    if len(left.overhang_sequence) != len(right.overhang_sequence):
        return False
    return _complement(left.overhang_sequence) == right.overhang_sequence


def check_sticky_junctions(fragments, circular=False):
    """Validate adjacent (and optionally closing) sticky junctions.

    Returns a list of junction dicts.
    """
    junctions = []
    n = len(fragments)
    if n == 0:
        return junctions
    pairs = list(range(n)) if circular else list(range(n - 1))
    for idx in pairs:
        left = fragments[idx]
        right = fragments[(idx + 1) % n]
        ok = compatible_sticky(left.right_end, right.left_end)
        junctions.append({
            "between": "%s->%s" % (left.name, right.name),
            "left": left.right_end.to_dict(),
            "right": right.left_end.to_dict(),
            "compatibility": "ok" if ok else "MISMATCH",
        })
    return junctions
