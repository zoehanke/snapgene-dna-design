# -*- coding: utf-8 -*-
"""pcr_strategy.py - M4 template-aware PCR strategy.

Every recommendation carries a source URL.  Extension time is calculated
from length (30 s/kb for high-fidelity polymerases, NEB Q5 guidance); no
temperatures are invented — annealing guidance always references the
algorithmically designed primer Tm from M3.
"""
import argparse
import json
import math
import sys

from sg_common import jprint
from provenance import read_version, source

SOURCES = {
    "neb_q5": "https://www.neb.com/en/protocols/pcr-using-q5-high-fidelity-dna-polymerase-m0491",
    "neb_gc": "https://www.neb.com/en/faqs/pcr-amplification-of-gc-rich-templates",
    "takara_gxl": "https://www.takarabio.com/products/pcr/all-enzymes-and-accessories/primestar-series/primestar-gxl-dna-polymerase",
    "neb_enzyme_guide": "https://www.neb.com/en/tools-and-resources/selection-charts/dna-polymerase-selection-chart",
    "neb_onetaq": "https://www.neb.com/en/products/m0480-onetaq-dna-polymerase",
    "thermo_phusion": "https://www.thermofisher.com/order/catalog/product/F530S",
}


def extension_time_seconds(length_bp, rate_seconds_per_kb=30.0):
    """NEB Q5 guideline: 20-30 s/kb; use the conservative 30 s/kb."""
    if length_bp <= 0:
        return 0
    return max(1, int(math.ceil(length_bp / 1000.0 * rate_seconds_per_kb)))


def recommend_pcr_strategy(profile):
    profile = dict(profile or {})
    raw_length = profile.get("length")
    try:
        length = int(raw_length)
    except (TypeError, ValueError, OverflowError):
        length = 0
    gc = profile.get("gc_percent")
    try:
        gc = float(gc)
    except (TypeError, ValueError):
        gc = None
    errors = []
    if length <= 0:
        errors.append("length must be a positive finite integer")
    if gc is not None and (not math.isfinite(gc) or not 0.0 <= gc <= 100.0):
        errors.append("gc_percent must be finite and within 0..100")
    if errors:
        return {
            "schema_version": "0.9.0",
            "status": "invalid-input",
            "reason": "INVALID_PCR_PROFILE",
            "errors": errors,
            "profile": profile,
            "recommended_enzyme": None,
            "additives": [],
            "extension_time_seconds": 0,
            "protocol": None,
            "provenance": [source(
                "software", "PCR strategy input validation",
                "pcr-strategy", status="verified",
                verification={"method": "finite-range-input-check",
                              "status": "verified"})],
        }
    purpose = str(profile.get("purpose") or "cloning")

    if length > 10000:
        enzyme = "PrimeSTAR GXL DNA Polymerase（或 Q5 长片段方案）"
        reason = "片段长度 %d bp > 10 kb，建议长片段高保真聚合酶" % length
        url = SOURCES["takara_gxl"]
        additives = ["按 Takara 方案使用 GXL buffer"]
    elif gc is not None and gc > 70.0:
        enzyme = "Q5 High-Fidelity DNA Polymerase + Q5 High GC Enhancer"
        reason = "模板 GC %.1f%% > 70%%，需要高 GC 增强体系" % gc
        url = SOURCES["neb_gc"]
        additives = ["Q5 High GC Enhancer（或 3% DMSO，按 NEB 方案）"]
    elif gc is not None and gc < 30.0:
        enzyme = "Q5 High-Fidelity DNA Polymerase（或 Phusion）"
        reason = "模板 GC %.1f%% < 30%%（AT-rich），使用高保真酶并降低退火温度" % gc
        url = SOURCES["neb_q5"]
        additives = ["AT-rich 添加剂需按确切聚合酶厂商协议选择；不自动指定浓度"]
    elif purpose in ("verification", "colony-pcr", "check"):
        enzyme = "OneTaq DNA Polymerase"
        reason = "验证/菌落 PCR 用途，常规保真度即可"
        url = SOURCES["neb_onetaq"]
        additives = []
    else:
        enzyme = "Q5 High-Fidelity DNA Polymerase"
        reason = "克隆用途默认高保真聚合酶"
        url = SOURCES["neb_q5"]
        additives = []

    extension_seconds = extension_time_seconds(length)
    result = {
        "schema_version": "0.9.0",
        "status": "compatible-candidate",
        "profile": profile,
        "recommended_enzyme": enzyme,
        "reason": reason,
        "additives": additives,
        "extension_time_seconds": extension_seconds,
        "extension_formula": "length_bp/1000*30s (NEB Q5 20-30 s/kb, conservative 30 s/kb)",
        "annealing_strategy": (
            "Q5: 退火温度 ~ 引物 Tm 低值 + 3 C（若计算值 >=72 C 可用两步法 72 C）；"
            "Taq/OneTaq: ~ Tm 低值 - 5 C；Tm 由 M3 Primer3 算法计算；"
            "AT-rich 模板再降 2-3 C 并复核制造商方案" if "Q5" in enzyme else
            "退火温度 ~ 引物 Tm 低值 - 5 C（Taq 类酶）；"
            "Tm 由 M3 Primer3 算法计算；AT-rich 模板再降 2-3 C"),
        "protocol": {"name": "official manufacturer protocol", "url": url},
        "provenance": [source(
            "manufacturer-protocol", "PCR strategy recommendation",
            "pcr-strategy", url=url, version="unknown",
            # ``candidate`` describes the recommendation fit, not a valid
            # provenance status.  ``partial`` records that the manufacturer
            # page is real while design-specific conditions remain unverified.
            status="partial",
            verification={"method": "structured-rule",
                          "status": "candidate; conditions require product-specific review"},
            retrieved_at="2026-08-17")],
    }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile")
    parser.add_argument("--length", type=int)
    parser.add_argument("--gc", type=float)
    parser.add_argument("--purpose", default="cloning")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.profile:
        profile = json.loads(open(args.profile, encoding="utf-8").read())
    else:
        profile = {"length": args.length or 1000, "gc_percent": args.gc,
                   "purpose": args.purpose}
    result = recommend_pcr_strategy(profile)
    if args.json:
        jprint(result)
    else:
        if result.get("status") == "invalid-input":
            print("INVALID_PCR_PROFILE: %s" % "; ".join(result["errors"]))
            return 1
        print("%s: %s\nadditives: %s\nextension: %ds" % (
            result["recommended_enzyme"], result["reason"],
            ", ".join(result["additives"]) or "-",
            result["extension_time_seconds"]))
    return 1 if result.get("status") == "invalid-input" else 0


if __name__ == "__main__":
    sys.exit(main())
