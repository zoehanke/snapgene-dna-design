# -*- coding: utf-8 -*-
"""core/tools/recombination.py - Recombination cloning simulation primitives.

Implements Gateway BP and Gateway LR site-specific recombination with strict att site
verification, feature migration, and circularization.
"""
from __future__ import annotations

import copy
from typing import Any

from Bio.Seq import Seq
from Bio.SeqFeature import CompoundLocation, FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

from core.models.assembly_model import AssemblyError
from core.models.construct_model import ConstructModel

ATTB1 = "ACAAGTTTGTACAAAAAAGCAGGCT"
ATTB2 = "ACCCAGCTTTCTTGTACAAAGTGGT"

ATTL1 = (
    "CAAATAATGATTTTATTTTGACTGATAGTGACCTGTTCGTTGCAACAAATTGATGAGCAATGCTTTTTTATAATGCC"
    "AACTTTGTACAAAAAAGCAGGCT"
)
ATTL2 = (
    "CAAATAATGATTTTATTTTGACTGATAGTGACCTGTTCGTTGCAACAAATTGATAAGCAATGCTTTCTTATAATGCC"
    "AACTTTGTACAAGAAAGCTGGGT"
)

ATTR1 = (
    "ACAAGTTTGTACAAAAAAGCTGAACGAGAAACGTAAAATGATATAAATATCAATATATTAAATTAGATTTTGCATAAAA"
    "AACAGACTACATAATACTGTAAAACACAACATATCCAGTCACTATG"
)
ATTR2 = (
    "ACCACTTTGTACAAGAAAGCTGAACGAGAAACGTAAAATGATATAAATATCAATATATTAAATTAGATTTTGCATAAAA"
    "AACAGACTACATAATACTGTAAAACACAACATATCCAGTCACTATG"
)

ATTP1 = (
    "AAATAATGATTTTATTTTGACTGATAGTGACCTGTTCGTTGCAACAAATTGATGAGCAATGCTTTTTTATAATGCC"
    "AAGTTTGTACAAAAAAGCAGAACGAGAAACGTAAAATGATATAAATATCAATATATTAAATTAGATTTTGCATAAAA"
    "AACAGACTACATAATACTGTAAAACACAACATATCCAGTCACTATGAATCAACTACTTAGATGGTATTAGTGACCTGTA"
)
ATTP2 = (
    "AAATAATGATTTTATTTTGACTGATAGTGACCTGTTCGTTGCAACAAATTGATAAGCAATGCTTTCTTATAATGCC"
    "CACTTTGTACAAGAAAGCTGAACGAGAAACGTAAAATGATATAAATATCAATATATTAAATTAGATTTTGCATAAAA"
    "AACAGACTACATAATACTGTAAAACACAACATATCCAGTCACTATGAATCAACTACTTAGATGGTATTAGTGACCTGTA"
)


def _occurrences(seq: str, query: str) -> list[int]:
    positions = []
    start = 0
    while True:
        pos = seq.find(query, start)
        if pos == -1:
            return positions
        positions.append(pos)
        start = pos + 1


def _require_explicit_circular(record: SeqRecord, role: str) -> None:
    topo = record.annotations.get("topology")
    if topo is None:
        raise AssemblyError(
            "MISSING_TOPOLOGY",
            f"{role} record {record.id or record.name!r} has no topology annotation; Gateway vectors must "
            "declare circular or linear explicitly",
        )
    if topo != "circular":
        raise AssemblyError(
            "INVALID_TOPOLOGY",
            f"{role} record {record.id or record.name!r} is {topo}; Gateway {role} must be circular",
        )


def _strict_att_pair(
    seq: str,
    left_site: str,
    right_site: str,
    left_label: str,
    right_label: str,
    right_site_reverse: bool = True,
) -> tuple[int, int, int, int]:
    left_rc = str(Seq(left_site).reverse_complement())
    right_expected = (
        str(Seq(right_site).reverse_complement()) if right_site_reverse else right_site
    )
    right_other = (
        right_site if right_site_reverse else str(Seq(right_site).reverse_complement())
    )

    left_good = _occurrences(seq, left_site)
    left_bad = _occurrences(seq, left_rc)
    right_good = _occurrences(seq, right_expected)
    right_bad = _occurrences(seq, right_other)

    if not left_good or not right_good:
        raise AssemblyError(
            "ATT_SITE_MISSING",
            "expected exactly one %s (forward) and one %s (%s) site; found %d and %d"
            % (
                left_label,
                right_label,
                "reverse" if right_site_reverse else "forward",
                len(left_good),
                len(right_good),
            ),
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
                left_label: left_good,
                right_label: right_good,
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


def _extract_body(seq: str, left_end: int, right_start: int) -> str:
    body = seq[left_end:right_start]
    if not body:
        raise AssemblyError("ATT_SITE_EMPTY", "no insert sequence between att sites")
    return body


def _shift_feature(feature: SeqFeature, delta: int) -> SeqFeature:
    updated = copy.deepcopy(feature)
    parts = getattr(feature.location, "parts", [feature.location])
    migrated = []
    for part in parts:
        migrated.append(
            FeatureLocation(
                int(part.start) + delta, int(part.end) + delta, strand=part.strand
            )
        )
    if len(migrated) == 1:
        updated.location = migrated[0]
    else:
        updated.location = CompoundLocation(
            migrated, operator=getattr(feature.location, "operator", "join")
        )
    return updated


def _features_between(
    record: SeqRecord, start0: int, end0: int, delta: int
) -> list[SeqFeature]:
    out = []
    for feature in record.features:
        parts = getattr(feature.location, "parts", [feature.location])
        starts = [int(p.start) for p in parts]
        ends = [int(p.end) for p in parts]
        if min(starts) >= start0 and max(ends) <= end0:
            out.append(_shift_feature(feature, delta))
    return out


def _replace_with_features(
    record: SeqRecord,
    start0: int,
    end0: int,
    replacement: str,
    new_features: list[SeqFeature],
) -> SeqRecord:
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


def gateway_bp(donor: SeqRecord, insert: SeqRecord) -> tuple[SeqRecord, str, list[str]]:
    """BP reaction with strict, unique attP/attB site validation."""
    _require_explicit_circular(donor, "donor")
    d = str(donor.seq).upper()
    ins = str(insert.seq).upper()
    b1_start, b1_end, b2_start, b2_end = _strict_att_pair(
        ins, ATTB1, ATTB2, "attB1", "attB2", right_site_reverse=False
    )
    body = _extract_body(ins, b1_end, b2_start)
    p1_start, p1_end, p2_start, p2_end = _strict_att_pair(
        d, ATTP1, ATTP2, "attP1", "attP2", right_site_reverse=True
    )

    replacement = ATTL1 + body + str(Seq(ATTL2).reverse_complement())
    attl1_start = p1_start
    attl2_start = p1_start + len(ATTL1) + len(body)
    attl1_feature = SeqFeature(
        FeatureLocation(attl1_start, attl1_start + len(ATTL1), strand=1),
        type="protein_bind",
        qualifiers={"label": ["attL1"]},
    )
    attl2_feature = SeqFeature(
        FeatureLocation(attl2_start, attl2_start + len(ATTL2), strand=-1),
        type="protein_bind",
        qualifiers={"label": ["attL2"]},
    )
    insert_features = _features_between(
        insert, b1_end, b2_start, p1_start + len(ATTL1) - b1_end
    )
    if not insert_features:
        insert_features = [
            SeqFeature(
                FeatureLocation(p1_start + len(ATTL1), attl2_start, strand=1),
                type="misc_feature",
                qualifiers={"label": ["insert"]},
            )
        ]
    product = _replace_with_features(
        donor,
        p1_start,
        p2_end,
        replacement,
        [attl1_feature, attl2_feature] + insert_features,
    )
    product.id = "product"
    product.name = "product"
    product.description = "gateway BP product"
    notes = [
        "BP: %d bp insert between attB1/attB2 recombined into attP1/attP2 "
        "donor and converted to attL1/attL2" % len(body),
    ]
    return product, body, notes


def gateway_lr(entry: SeqRecord, destination: SeqRecord) -> tuple[SeqRecord, str, list[str]]:
    """LR reaction with strict, unique attL/attR site validation."""
    _require_explicit_circular(entry, "entry")
    _require_explicit_circular(destination, "destination")
    e = str(entry.seq).upper()
    d = str(destination.seq).upper()
    l1_start, l1_end, l2_start, l2_end = _strict_att_pair(
        e, ATTL1, ATTL2, "attL1", "attL2", right_site_reverse=True
    )
    body = _extract_body(e, l1_end, l2_start)
    r1_start, r1_end, r2_start, r2_end = _strict_att_pair(
        d, ATTR1, ATTR2, "attR1", "attR2", right_site_reverse=True
    )

    replacement = ATTB1 + body + str(Seq(ATTB2).reverse_complement())
    attb1_start = r1_start
    attb2_start = r1_start + len(ATTB1) + len(body)
    attb1_feature = SeqFeature(
        FeatureLocation(attb1_start, attb1_start + len(ATTB1), strand=1),
        type="protein_bind",
        qualifiers={"label": ["attB1"]},
    )
    attb2_feature = SeqFeature(
        FeatureLocation(attb2_start, attb2_start + len(ATTB2), strand=-1),
        type="protein_bind",
        qualifiers={"label": ["attB2"]},
    )
    insert_features = _features_between(
        entry, l1_end, l2_start, r1_start + len(ATTB1) - l1_end
    )
    if not insert_features:
        insert_features = [
            SeqFeature(
                FeatureLocation(r1_start + len(ATTB1), attb2_start, strand=1),
                type="misc_feature",
                qualifiers={"label": ["insert"]},
            )
        ]
    product = _replace_with_features(
        destination,
        r1_start,
        r2_end,
        replacement,
        [attb1_feature, attb2_feature] + insert_features,
    )
    product.id = "product"
    product.name = "product"
    product.description = "gateway LR product"
    notes = [
        "LR: %d bp insert between attL1/attL2 recombined into attR1/attR2 "
        "destination and converted to attB1/attB2" % len(body),
    ]
    return product, body, notes
