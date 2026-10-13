# -*- coding: utf-8 -*-
"""build_rich_fixtures.py - Generate rich-feature round-trip fixtures.

These fixtures are fully synthetic (no SnapGene-derived content) so they are
safe for both release packages. They cover the v0.5 gate checklist for rich
feature semantics:

    * forward and reverse CDS (with translation / codon_start qualifiers)
    * CompoundLocation with operator=join and operator=order
    * cross-origin (wraps_origin) features on circular records
    * multi-value qualifiers (note, db_xref, EC_number, synonym)
    * Unicode qualifier values and notes (UTF-8)

Run from the package root:

    python -X utf8 tools/build_rich_fixtures.py            # write fixtures/rich/
    python -X utf8 tools/build_rich_fixtures.py --out DIR  # custom target

The fixtures are then validated by ``tools/validate_rich_fixtures.py`` and
by ``tests/test_rich_fixtures.py``.
"""

from project_paths import PROJECT_ROOT as REPOSITORY_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS, TESTS_ROOT
import argparse
import pathlib

from Bio.Seq import Seq
from Bio.SeqFeature import CompoundLocation, FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

HERE = pathlib.Path(__file__).resolve().parent
ROOT = SKILL_ROOT
DEFAULT_OUT = ROOT / "fixtures" / "rich"

UNICODE_NOTE = "引物设计验证 fixture · café Σ DNA π 质粒"
UNICODE_LABEL = "基因_α"


def _record(name, sequence, circular, features):
    record = SeqRecord(Seq(sequence), id=name, name=name,
                       description="rich fixture %s" % name)
    record.annotations = {"molecule_type": "DNA",
                          "topology": "circular" if circular else "linear"}
    record.features.extend(features)
    return record


def _cds(start, end, label, strand=1, translation=None, extra=None):
    qualifiers = {"label": [label], "gene": [label.lower()],
                  "codon_start": ["1"], "transl_table": ["11"]}
    if translation:
        qualifiers["translation"] = [translation]
    if extra:
        qualifiers.update(extra)
    return SeqFeature(FeatureLocation(start, end, strand=strand),
                      type="CDS", qualifiers=qualifiers)


def build_fixtures(out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []

    # 1) forward CDS with translation + multi-value qualifiers.
    seq1 = "ATGGCTAAATAA"
    cds1 = _cds(0, 9, "cds_fwd", strand=1,
                translation="MAK",
                extra={"note": ["forward CDS", "orf 1"],
                       "db_xref": ["UniProtKB:P00001", "GeneID:12345"],
                       "EC_number": ["2.7.1.1"]})
    rec = _record("rich_fwd_cds", seq1, False, [cds1])
    path = out_dir / "rich_fwd_cds.gb"
    with open(path, "w", encoding="utf-8") as handle:
        from Bio import SeqIO
        SeqIO.write(rec, handle, "genbank")
    written.append(path)

    # 2) reverse-strand CDS (translation computed from the actual extracted
    #    sequence so it matches both Biopython and SnapGene re-translation).
    seq2 = "TTATTTAGCCAT"
    cds2 = _cds(0, 9, "cds_rev", strand=-1,
                translation=str(Seq(seq2[0:9]).reverse_complement().translate()))
    rec = _record("rich_rev_cds", seq2, False, [cds2])
    path = out_dir / "rich_rev_cds.gb"
    with open(path, "w", encoding="utf-8") as handle:
        from Bio import SeqIO
        SeqIO.write(rec, handle, "genbank")
    written.append(path)

    # 3) CompoundLocation operator=join (parts on the same strand).
    seq3 = "AAAA" + "CCCCCC" + "GGGGGG" + "TTTT"
    join_loc = CompoundLocation([
        FeatureLocation(0, 4, strand=1),
        FeatureLocation(4, 10, strand=1),
        FeatureLocation(10, 16, strand=1),
    ], operator="join")
    feature = SeqFeature(join_loc, type="misc_feature",
                         qualifiers={"label": ["join_feat"],
                                     "note": ["compound join", "three parts"]})
    rec = _record("rich_join", seq3, False, [feature])
    path = out_dir / "rich_join.gb"
    with open(path, "w", encoding="utf-8") as handle:
        from Bio import SeqIO
        SeqIO.write(rec, handle, "genbank")
    written.append(path)

    # 4) CompoundLocation operator=order (parts in non-contiguous order).
    order_loc = CompoundLocation([
        FeatureLocation(4, 8, strand=1),
        FeatureLocation(0, 4, strand=1),
    ], operator="order")
    feature = SeqFeature(order_loc, type="misc_feature",
                         qualifiers={"label": ["order_feat"]})
    rec = _record("rich_order", "AAAACCCC", False, [feature])
    path = out_dir / "rich_order.gb"
    with open(path, "w", encoding="utf-8") as handle:
        from Bio import SeqIO
        SeqIO.write(rec, handle, "genbank")
    written.append(path)

    # 5) Cross-origin feature on a circular record.
    seq5 = "AAAACCCCGGGGTTTT"
    cross_loc = CompoundLocation([
        FeatureLocation(12, 16, strand=1),
        FeatureLocation(0, 5, strand=1),
    ], operator="join")
    feature = SeqFeature(cross_loc, type="CDS",
                         qualifiers={"label": ["cross_origin_cds"],
                                     "codon_start": ["1"],
                                     "transl_table": ["11"],
                                     "translation": [str(Seq("TTTTAAAAC").translate())]})
    rec = _record("rich_cross_origin", seq5, True, [feature])
    path = out_dir / "rich_cross_origin.gb"
    with open(path, "w", encoding="utf-8") as handle:
        from Bio import SeqIO
        SeqIO.write(rec, handle, "genbank")
    written.append(path)

    # 6) Unicode qualifier values and notes.
    unicode_feature = SeqFeature(
        FeatureLocation(0, 12, strand=1), type="gene",
        qualifiers={"label": [UNICODE_LABEL],
                    "gene": [UNICODE_LABEL],
                    "note": [UNICODE_NOTE, "second note line"]})
    rec = _record("rich_unicode", "ATGGCTAAATAA", False, [unicode_feature])
    path = out_dir / "rich_unicode.gb"
    with open(path, "w", encoding="utf-8") as handle:
        from Bio import SeqIO
        SeqIO.write(rec, handle, "genbank")
    written.append(path)

    # 7) Multi-value qualifier stress: many values per key.
    multi_feature = SeqFeature(
        FeatureLocation(0, 9, strand=1), type="CDS",
        qualifiers={"label": ["multi_cds"],
                    "gene": ["multi", "multigene"],
                    "note": ["value one", "value two", "value three", "value four"],
                    "db_xref": ["a:1", "b:2", "c:3"],
                    "synonym": ["syn1", "syn2"]})
    rec = _record("rich_multivalue", "ATGGCTAAATAA", False, [multi_feature])
    path = out_dir / "rich_multivalue.gb"
    with open(path, "w", encoding="utf-8") as handle:
        from Bio import SeqIO
        SeqIO.write(rec, handle, "genbank")
    written.append(path)

    # 8) Kitchen-sink circular plasmid: cross-origin CDS + reverse promoter +
    #    multi-value misc features + Unicode.
    seq8 = ("ATGGCTAAATAA" + "TTTT" + "CCCGGG" + "AAAA" + "TATAAT" + "GGGG"
            + "AAACCCGGGTTT")
    cds8 = _cds(0, 12, "sink_cds", strand=1,
                translation=str(Seq(seq8[0:12]).translate()))
    promoter = SeqFeature(
        FeatureLocation(19, 25, strand=-1), type="promoter",
        qualifiers={"label": ["sink_promoter"], "note": ["reverse", "σ70"]})
    sink_cross = CompoundLocation([
        FeatureLocation(len(seq8) - 4, len(seq8), strand=1),
        FeatureLocation(0, 3, strand=1),
    ], operator="join")
    cross_feature = SeqFeature(
        sink_cross, type="misc_feature",
        qualifiers={"label": ["sink_cross_origin"],
                    "note": [UNICODE_NOTE, "multi", "values"]})
    rec = _record("rich_kitchen_sink", seq8, True,
                  [cds8, promoter, cross_feature])
    path = out_dir / "rich_kitchen_sink.gb"
    with open(path, "w", encoding="utf-8") as handle:
        from Bio import SeqIO
        SeqIO.write(rec, handle, "genbank")
    written.append(path)

    return written


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args(argv)
    written = build_fixtures(pathlib.Path(args.out))
    for path in written:
        print("wrote %s" % path)
    print("%d rich fixtures written" % len(written))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
