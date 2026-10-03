# -*- coding: utf-8 -*-
"""Regression tests for Gibson source-feature restoration cleanup."""

from __future__ import annotations

from repository_paths import PROJECT_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS

import unittest
import random

from Bio.Seq import Seq
from Bio.SeqFeature import CompoundLocation, FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

from core.recipes.gibson import _restore_unique_source_features


def feature_dict(name, feature_type, strand, parts, *, partial=False, clipped=False):
    part_dicts = [
        {
            "start0": start,
            "end0": end,
            "start": start + 1,
            "end": end,
            "strand": strand,
        }
        for start, end in parts
    ]
    qualifiers = {"label": [name]}
    if partial:
        qualifiers["partial"] = ["true"]
    if clipped:
        qualifiers["note"] = [
            "feature clipped at extraction boundary; complete feature is not asserted"
        ]
    return {
        "name": name,
        "type": feature_type,
        "strand": strand,
        "start": parts[0][0] + 1,
        "end": parts[-1][1],
        "qualifiers": qualifiers,
        "location": {
            "coordinate_system": "0-based-half-open",
            "operator": "join" if len(parts) > 1 else None,
            "parts": part_dicts,
            "wraps_origin": False,
        },
    }


def feature_from_dict(feature):
    parts = [
        FeatureLocation(
            part["start0"],
            part["end0"],
            strand=part.get("strand"),
        )
        for part in feature["location"]["parts"]
    ]
    location = (
        parts[0]
        if len(parts) == 1
        else CompoundLocation(parts, operator=feature["location"].get("operator") or "join")
    )
    return SeqFeature(
        location=location,
        type=feature["type"],
        qualifiers=feature.get("qualifiers") or {},
    )


class FinalFeatureRestorationTests(unittest.TestCase):
    def test_restore_removes_only_clipped_ampR_fragments(self):
        amp_product = ("ACGTTGCAAGTC" * 72 + "ACG")[:861]
        product = "G" * 19 + amp_product + "C" * (7895 - 19 - len(amp_product))
        source = SeqRecord(
            Seq("T" * 19 + amp_product + "A" * 20),
            id="pVH1001",
            annotations={"molecule_type": "DNA", "topology": "circular"},
        )
        source.features = [
            SeqFeature(
                FeatureLocation(19, 880, strand=-1),
                type="CDS",
                qualifiers={"label": ["AmpR"]},
            )
        ]
        existing = [
            feature_dict(
                "AmpR",
                "CDS",
                -1,
                [(30, 880)],
                partial=True,
                clipped=True,
            ),
            feature_dict(
                "AmpR",
                "CDS",
                -1,
                [(19, 30)],
                partial=True,
                clipped=True,
            ),
            feature_dict("P2A", "CDS", 1, [(3319, 3376)], partial=True),
            feature_dict(
                "unmatched_partial",
                "CDS",
                -1,
                [(5000, 5010)],
                partial=True,
                clipped=True,
            ),
        ]

        restored = _restore_unique_source_features(
            product, existing, [source], circular=False
        )

        amp_r = [feature for feature in restored if feature["name"] == "AmpR"]
        self.assertEqual(len(amp_r), 1)
        self.assertEqual(amp_r[0]["location"]["parts"], [
            {"start0": 19, "end0": 880, "start": 20, "end": 880, "strand": -1}
        ])
        self.assertEqual(
            [feature["name"] for feature in restored if feature["name"] == "P2A"],
            ["P2A"],
        )
        self.assertEqual(
            [
                feature["name"]
                for feature in restored
                if feature["name"] == "unmatched_partial"
            ],
            ["unmatched_partial"],
        )

    def test_restore_preserves_cross_origin_positive_and_negative_features(self):
        rng = random.Random(20260908)
        product = "".join(rng.choice("ACGT") for _ in range(120))

        positive = SeqRecord(
            Seq(product),
            id="origin_positive",
            annotations={"molecule_type": "DNA", "topology": "circular"},
        )
        positive.features = [
            SeqFeature(
                CompoundLocation(
                    [
                        FeatureLocation(110, 120, strand=1),
                        FeatureLocation(0, 15, strand=1),
                    ],
                    operator="join",
                ),
                type="misc_feature",
                qualifiers={"label": ["origin_positive"]},
            )
        ]
        negative = SeqRecord(
            Seq(product),
            id="origin_negative",
            annotations={"molecule_type": "DNA", "topology": "circular"},
        )
        negative.features = [
            SeqFeature(
                CompoundLocation(
                    [
                        FeatureLocation(0, 15, strand=-1),
                        FeatureLocation(110, 120, strand=-1),
                    ],
                    operator="join",
                ),
                type="misc_feature",
                qualifiers={"label": ["origin_negative"]},
            )
        ]

        duplicate_product = list(product)
        duplicate_product[60:85] = product[20:45]
        duplicate_source = SeqRecord(
            Seq(product[20:45]),
            id="duplicate_source",
            annotations={"molecule_type": "DNA", "topology": "linear"},
        )
        duplicate_source.features = [
            SeqFeature(
                FeatureLocation(0, 25, strand=1),
                type="misc_feature",
                qualifiers={"label": ["ambiguous_feature"]},
            )
        ]

        restored = _restore_unique_source_features(
            "".join(duplicate_product),
            [],
            [positive, negative, duplicate_source],
            circular=True,
        )
        by_name = {feature["name"]: feature for feature in restored}

        self.assertNotIn("ambiguous_feature", by_name)
        for source in (positive, negative):
            name = source.features[0].qualifiers["label"][0]
            self.assertIn(name, by_name)
            restored_feature = feature_from_dict(by_name[name])
            self.assertEqual(
                str(restored_feature.extract(Seq("".join(duplicate_product)))),
                str(source.features[0].extract(source.seq)),
            )
            self.assertEqual(
                len(by_name[name]["location"]["parts"]),
                2,
            )
            self.assertTrue(by_name[name]["location"]["wraps_origin"])

        self.assertEqual(
            _restore_unique_source_features(product, [], [positive, negative], circular=False),
            [],
        )


if __name__ == "__main__":
    unittest.main()
