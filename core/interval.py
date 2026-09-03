# -*- coding: utf-8 -*-
"""Topology-aware Interval Model (v0.9.1-dev2).

Establishes unified interval semantics across all task kinds.
Replaces legacy ad-hoc slicing and modulo fallbacks with strict, topology-aware
coordinate validation.

Rules:
Linear records:
  - 0 <= start0 < end0 <= length
  - start0 == end0 -> ZERO_WIDTH_INTERVAL_REJECTED
  - start0 > end0 -> REVERSE_INTERVAL_REJECTED
  - start0 < 0 or end0 > length -> INTERVAL_OUT_OF_RANGE
  - No implicit modulo or wrap.
  - [0, length) requires explicit whole_record approval for component operations.

Circular records:
  - start0 < end0: standard interval.
  - start0 > end0: cross-origin circular interval.
  - start0 == end0: rejected unless explicit whole_record operation is approved.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from Bio.Seq import Seq

from core.errors import PlanningError, TaskValidationError

if TYPE_CHECKING:
    from Bio.SeqRecord import SeqRecord


def validate_interval(
    start0: int,
    end0: int,
    record_len: int,
    topology: str = "linear",
    wraps_origin: bool = True,
    whole_record_approved: bool = False,
    task_kind: str = "generic",
) -> tuple[int, int, bool]:
    """Validate 0-based half-open interval [start0, end0) against sequence length and topology.

    Returns (normalized_start0, normalized_end0, is_cross_origin).
    Raises PlanningError or TaskValidationError on violation.
    """
    if record_len <= 0:
        raise PlanningError("INVALID_RECORD_LENGTH", "record length must be positive, got %d" % record_len)

    if isinstance(start0, float) or isinstance(end0, float):
        raise PlanningError(
            "INVALID_INTERVAL_COORDINATE",
            "interval coordinates must be integers, got float: start=%r, end=%r" % (start0, end0),
        )

    try:
        s0 = int(start0)
        e0 = int(end0)
    except (TypeError, ValueError):
        raise PlanningError(
            "COMPONENT_BOUNDARY_REQUIRED",
            "interval coordinates must be integers, got start=%r, end=%r" % (start0, end0),
        )

    # 1. Out of range checks
    if s0 < 0 or e0 < 0 or s0 > record_len or e0 > record_len:
        raise PlanningError(
            "INTERVAL_OUT_OF_RANGE",
            "interval [%d, %d) outside record length %d" % (s0, e0, record_len),
            missing_fields=["target.selection.interval_0based"],
        )

    is_circular = (topology == "circular")

    if not is_circular:
        # Linear record
        if s0 == e0:
            raise PlanningError(
                "ZERO_WIDTH_INTERVAL_REJECTED",
                "zero-width interval [%d, %d) is rejected on linear record" % (s0, e0),
                missing_fields=["target.selection.interval_0based"],
            )
        if s0 > e0:
            raise PlanningError(
                "REVERSE_INTERVAL_REJECTED",
                "reverse interval [%d, %d) is invalid on linear record without wrap" % (s0, e0),
                missing_fields=["target.selection.interval_0based"],
            )
        if s0 == 0 and e0 == record_len:
            if not whole_record_approved:
                raise PlanningError(
                    "WHOLE_TEMPLATE_SELECTED_FOR_COMPONENT",
                    "interval [0, %d) covers the entire template; whole-record operation requires explicit approval" % record_len,
                    missing_fields=["target.selection.interval_0based"],
                )
        return (s0, e0, False)

    # Circular record
    if s0 == e0:
        if not whole_record_approved:
            raise PlanningError(
                "ZERO_WIDTH_INTERVAL_REJECTED",
                "zero-width interval [%d, %d) is rejected on circular record unless whole-record operation is explicitly approved" % (s0, e0),
                missing_fields=["target.selection.interval_0based"],
            )
        return (0, record_len, False)

    if s0 < e0:
        if s0 == 0 and e0 == record_len:
            if not whole_record_approved:
                raise PlanningError(
                    "WHOLE_TEMPLATE_SELECTED_FOR_COMPONENT",
                    "interval [0, %d) covers the entire circular template; requires explicit approval" % record_len,
                    missing_fields=["target.selection.interval_0based"],
                )
        return (s0, e0, False)

    # s0 > e0: Cross-origin circular interval
    if not wraps_origin:
        raise PlanningError(
            "CROSS_ORIGIN_WRAP_UNSUPPORTED",
            "cross-origin interval [%d, %d) is invalid when wraps_origin=False" % (s0, e0),
            missing_fields=["target.selection.interval_0based"],
        )
    selected_len = (record_len - s0) + e0
    if selected_len >= record_len:
        if not whole_record_approved:
            raise PlanningError(
                "WHOLE_TEMPLATE_SELECTED_FOR_COMPONENT",
                "cross-origin interval covers the entire circular record; requires explicit approval",
                missing_fields=["target.selection.interval_0based"],
            )
    return (s0, e0, True)


def extract_interval(
    record: SeqRecord,
    start0: int,
    end0: int,
    topology: str = "linear",
    wraps_origin: bool = True,
    strand: int = 1,
    whole_record_approved: bool = False,
) -> str:
    """Validate interval and extract the exact nucleotide sequence from a SeqRecord."""
    seq_str = str(record.seq).upper()
    n = len(seq_str)
    s0, e0, is_wrap = validate_interval(
        start0, end0, n, topology=topology, wraps_origin=wraps_origin, whole_record_approved=whole_record_approved
    )

    if s0 == e0 and whole_record_approved:
        sub = seq_str
    elif not is_wrap:
        sub = seq_str[s0:e0]
    else:
        sub = seq_str[s0:] + seq_str[:e0]

    if strand == -1:
        sub = str(Seq(sub).reverse_complement())

    return sub


def interval_length(start0: int, end0: int, record_len: int, wraps_origin: bool = True) -> int:
    """Return nucleotide length of interval [start0, end0)."""
    if start0 <= end0:
        return end0 - start0
    if wraps_origin:
        return (record_len - start0) + end0
    return 0


def interval_overlaps(
    a_start0: int,
    a_end0: int,
    b_start0: int,
    b_end0: int,
    record_len: int,
    a_wraps: bool = False,
    b_wraps: bool = False,
) -> bool:
    """Check if interval A overlaps interval B in a sequence of length record_len."""
    def _segments(s0: int, e0: int, wraps: bool) -> list[tuple[int, int]]:
        if not wraps:
            return [(s0, e0)] if s0 < e0 else []
        return [(s0, record_len), (0, e0)]

    segs_a = _segments(a_start0, a_end0, a_wraps)
    segs_b = _segments(b_start0, b_end0, b_wraps)

    for sa, ea in segs_a:
        for sb, eb in segs_b:
            if max(sa, sb) < min(ea, eb):
                return True
    return False
