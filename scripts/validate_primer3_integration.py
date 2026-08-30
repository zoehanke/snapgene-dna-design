# -*- coding: utf-8 -*-
"""Fail-closed release gate for the real external Primer3 design path."""
import argparse
import json
import pathlib
import sys

from primer3_core_backend import design_anchored_pairs, probe_primer3_core


REAL_SEQUENCE = (
    "GCTAAAGACAATTACATAACATACACGTCAGCACGAAACTTGTTGGCCCAGTGTGAATCGCTTA"
    "AGGGTTAAGTAAGTGTGATGCATACGCCTTTACTTGCTGTGTCCACCCCATCGGACTGGCATTT"
    "TTATTACACTCAGAAACAGAACTCGGGTAATTTTGACAGGTCACGCAGAGGCGCGCCCTCCTGA"
    "AGTGCGTGGACACTCGCTATGAATCTCTGATTTACCCACTCTGCCAAACTCCAGCGCGGTCAGT"
    "TCCATCACCCTAAGTAACCGAATAATGCGTTCGCTCTATTGACT"
)


def main():
    parser = argparse.ArgumentParser(
        description="Require and exercise a real primer3_core executable")
    parser.add_argument("--primer3-core", default=None)
    parser.add_argument("--report", default=None)
    args = parser.parse_args()

    info = probe_primer3_core(args.primer3_core)
    report = {"ok": False, "engine": info, "checks": {}}
    if info["status"] != "available":
        report["error"] = "real primer3_core is unavailable"
    else:
        plain = design_anchored_pairs(
            info["path"], REAL_SEQUENCE, 1, 60.0, 18, 30, 5)
        gibson = design_anchored_pairs(
            info["path"], REAL_SEQUENCE, 1, 60.0, 18, 30, 1,
            fwd_tail="ACGTACGT", rev_tail="TGCATGCA")
        report["checks"] = {
            "plain_pairs": plain["returned_pairs"],
            "plain_first_penalty": plain["pairs"][0]["primer3_penalty"]
            if plain["pairs"] else None,
            "gibson_pairs": gibson["returned_pairs"],
            "gibson_binding_product_size": gibson["pairs"][0]["product_size"]
            if gibson["pairs"] else None,
            "gibson_full_product_size":
                gibson["pairs"][0]["primer3_product_size_with_overhangs"]
                if gibson["pairs"] else None,
            "metric_source": (plain["forward_candidates"][0]["hairpin"]["source"]
                              if plain["forward_candidates"] else None),
        }
        report["ok"] = (
            report["checks"]["plain_pairs"] == 5 and
            report["checks"]["gibson_pairs"] == 1 and
            report["checks"]["gibson_binding_product_size"] == 300 and
            report["checks"]["gibson_full_product_size"] == 316 and
            report["checks"]["metric_source"] == "primer3-core")
        if not report["ok"]:
            report["error"] = "one or more real-engine assertions failed"

    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.report:
        pathlib.Path(args.report).write_text(text + "\n", encoding="utf-8")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
