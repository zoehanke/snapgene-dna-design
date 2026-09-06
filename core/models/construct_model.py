# -*- coding: utf-8 -*-
"""Canonical construct model for loss-minimizing DNA edits.

All coordinates in this module are 0-based, half-open boundaries.  CLI
adapters are responsible for translating user-facing 1-based coordinates.
"""
import copy

from Bio.Seq import Seq
from Bio.SeqFeature import CompoundLocation, FeatureLocation


MODEL_VERSION = "0.3.0"
COORDINATE_SYSTEM = "0-based-half-open"


def _parts(location):
    return list(getattr(location, "parts", [location]))


def _part(start0, end0, original):
    """Recreate a location part while preserving strand and remote refs."""
    kwargs = {"strand": original.strand}
    if getattr(original, "ref", None) is not None:
        kwargs["ref"] = original.ref
    if getattr(original, "ref_db", None) is not None:
        kwargs["ref_db"] = original.ref_db
    return FeatureLocation(start0, end0, **kwargs)


def _location(parts, operator="join"):
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    return CompoundLocation(parts, operator=operator or "join")


def feature_to_dict(feature, sequence_length=None):
    """Serialize a feature without flattening CompoundLocation information."""
    loc = feature.location
    loc_parts = _parts(loc)
    strand = 0 if loc.strand is None else int(loc.strand)
    qualifiers = {}
    for key, value in feature.qualifiers.items():
        values = value if isinstance(value, list) else [value]
        qualifiers[key] = [str(item) for item in values]
    name_values = feature.qualifiers.get(
        "label", feature.qualifiers.get("gene", [feature.id or "feature"])
    )
    name = name_values[0] if isinstance(name_values, list) else name_values
    part_dicts = []
    for part in loc_parts:
        pstrand = 0 if part.strand is None else int(part.strand)
        part_dicts.append({
            "start0": int(part.start),
            "end0": int(part.end),
            "start": int(part.start) + 1,
            "end": int(part.end),
            "strand": pstrand,
        })
    wraps = False
    if len(part_dicts) > 1:
        wraps = any(
            part_dicts[i]["start0"] < part_dicts[i - 1]["start0"]
            for i in range(1, len(part_dicts))
        )
        if sequence_length:
            wraps = wraps or (
                part_dicts[0]["end0"] == sequence_length
                and part_dicts[-1]["start0"] == 0
            )
    result = {
        "name": str(name),
        "type": feature.type,
        "strand": strand,
        "start": int(loc.start) + 1,
        "end": int(loc.end),
        "qualifiers": qualifiers,
        "location": {
            "coordinate_system": COORDINATE_SYSTEM,
            "operator": getattr(loc, "operator", None),
            "parts": part_dicts,
            "wraps_origin": wraps,
        },
    }
    if feature.id and feature.id != "<unknown id>":
        result["id"] = feature.id
    if len(part_dicts) > 1:
        # Backward-compatible 1-based closed representation.
        result["segments"] = [
            {"start": part["start"], "end": part["end"]}
            for part in part_dicts
        ]
    return result


class ConstructModel:
    """A SeqRecord wrapper that preserves structured locations during edits."""

    def __init__(self, record):
        self.record = copy.deepcopy(record)
        self.record.annotations.setdefault("molecule_type", "DNA")
        self.warnings = []

    @property
    def length(self):
        return len(self.record.seq)

    def _replace_parts(self, transform, feature_callback=None):
        migrated = []
        for feature in self.record.features:
            new_parts = []
            for part in _parts(feature.location):
                new_parts.extend(transform(part))
            if not new_parts:
                continue
            updated = copy.deepcopy(feature)
            updated.location = _location(
                new_parts, getattr(feature.location, "operator", "join")
            )
            if feature_callback is not None:
                feature_callback(feature, updated)
            migrated.append(updated)
        self.record.features = migrated

    @staticmethod
    def _mark_cds_disrupted(original, updated, operation):
        """Annotate a CDS whose interval was cut by an indel.

        An insertion/deletion inside a CDS changes its biological meaning: it
        is no longer safe to describe the resulting annotation as a complete
        ORF.  Keep the feature (so users can see what was interrupted), mark
        it partial, and record the operation instead of weakening the
        downstream start/stop validation.
        """
        if original.type != "CDS":
            return
        qualifiers = copy.deepcopy(updated.qualifiers or {})
        qualifiers["partial"] = ["true"]
        note_values = qualifiers.get("note", [])
        if not isinstance(note_values, list):
            note_values = [note_values]
        note = "CDS interrupted by %s; complete protein function is not asserted" % operation
        if note not in [str(value) for value in note_values]:
            note_values.append(note)
        qualifiers["note"] = note_values
        updated.qualifiers = qualifiers

    def _clear_letter_annotations(self, reason):
        if self.record.letter_annotations:
            self.record.letter_annotations = {}
            self.warnings.append(
                "per-letter annotations removed after %s because inserted/deleted "
                "bases have no defined annotation values" % reason
            )

    def insert(self, pos0, sequence):
        if not (0 <= pos0 <= self.length):
            raise ValueError("insert boundary out of range: %d" % pos0)
        text = str(sequence)
        if not text:
            raise ValueError("insert sequence is empty")
        delta = len(text)

        def transform(part):
            start0, end0 = int(part.start), int(part.end)
            new_start = start0 + (delta if start0 >= pos0 else 0)
            new_end = end0 + (delta if end0 > pos0 else 0)
            return [_part(new_start, new_end, part)]

        def annotate(original, updated):
            parts = _parts(original.location)
            if any(int(part.start) < pos0 < int(part.end)
                   for part in parts):
                self._mark_cds_disrupted(original, updated, "insertion")

        self._replace_parts(transform, annotate)
        self._clear_letter_annotations("insertion")
        old = str(self.record.seq)
        self.record.seq = Seq(old[:pos0] + text + old[pos0:])
        return self

    def delete(self, start0, end0):
        if not (0 <= start0 < end0 <= self.length):
            raise ValueError("invalid delete interval: [%d, %d)" % (start0, end0))
        delta = end0 - start0

        def map_boundary(value):
            if value <= start0:
                return value
            if value >= end0:
                return value - delta
            return start0

        def transform(part):
            new_start = map_boundary(int(part.start))
            new_end = map_boundary(int(part.end))
            return [] if new_end <= new_start else [_part(new_start, new_end, part)]

        def annotate(original, updated):
            parts = _parts(original.location)
            if any(max(int(part.start), start0) <
                   min(int(part.end), end0) for part in parts):
                self._mark_cds_disrupted(original, updated, "deletion")

        self._replace_parts(transform, annotate)
        self._clear_letter_annotations("deletion")
        old = str(self.record.seq)
        self.record.seq = Seq(old[:start0] + old[end0:])
        return self

    def replace(self, start0, end0, sequence):
        self.delete(start0, end0)
        self.insert(start0, sequence)
        return self

    def mutate(self, mutations):
        bases = list(str(self.record.seq))
        for pos0, base in mutations:
            if not (0 <= pos0 < len(bases)):
                raise ValueError("mutation position out of range: %d" % pos0)
            bases[pos0] = str(base)
        self.record.seq = Seq("".join(bases))
        return self

    def rotate(self, origin0, topology=None):
        """Move origin0 to coordinate zero and retain every location part."""
        n = self.length
        if not n or not (0 <= origin0 < n):
            raise ValueError("rotation origin out of range: %d" % origin0)
        if origin0 == 0:
            if topology:
                self.record.annotations["topology"] = topology
            return self

        def transform(part):
            start0, end0 = int(part.start), int(part.end)
            length = end0 - start0
            new_start = (start0 - origin0) % n
            unwrapped_end = new_start + length
            if unwrapped_end <= n:
                return [_part(new_start, unwrapped_end, part)]
            split = [
                _part(new_start, n, part),
                _part(0, unwrapped_end - n, part),
            ]
            return list(reversed(split)) if part.strand == -1 else split

        self._replace_parts(transform)
        old = str(self.record.seq)
        self.record.seq = Seq(old[origin0:] + old[:origin0])
        for key, values in list(self.record.letter_annotations.items()):
            self.record.letter_annotations[key] = values[origin0:] + values[:origin0]
        if topology:
            self.record.annotations["topology"] = topology
        return self

    def set_topology(self, value):
        if value not in ("linear", "circular"):
            raise ValueError("topology must be linear or circular")
        self.record.annotations["topology"] = value
        return self

    def to_record(self):
        return copy.deepcopy(self.record)

    def to_dict(self):
        return {
            "model_version": MODEL_VERSION,
            "coordinate_system": COORDINATE_SYSTEM,
            "length": self.length,
            "topology": self.record.annotations.get("topology", "linear"),
            "features": [
                feature_to_dict(feature, self.length)
                for feature in self.record.features
            ],
            "warnings": list(self.warnings),
        }
