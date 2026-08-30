# -*- coding: utf-8 -*-
"""recommend_protocol.py - Feature-driven, source-gated protocol recommendation.

A recommendation is only made when a reaction profile matches the evidence
source's ``applicable_to`` tags.  Every match reason names the actual profile
field and observed value that produced the match.  Profiles without any
matching evidence receive ``insufficient_evidence`` and never a product name.
"""
import argparse
import json
import pathlib
import sys

from sg_common import jprint
from provenance import source
from protocol_evidence import load_sources, source_object, usable_source


def _as_bool(value):
    return value is True or str(value).strip().lower() in {
        "true", "yes", "required", "high", "1"}


def _category_for(profile):
    """Map objective reaction-profile fields to evidence categories."""
    profile = profile or {}
    if "reaction_type" in profile:
        reaction_type = str(profile.get("reaction_type")).strip().lower()
        if reaction_type in ("assembly", "gibson-like-assembly", "gibson",
                             "nebuilder", "nebuilder-hifi"):
            return "assembly"
        if reaction_type in ("pcr", "high-fidelity-cloning-pcr", "high-gc-pcr"):
            return "pcr"
    assembly = str(profile.get("assembly_method", "")).strip().lower()
    if assembly in ("gibson", "gibson-like-assembly", "nebuilder",
                    "nebuilder-hifi", "gibson-assembly"):
        return "assembly"
    template_type = str(profile.get("template_type", "")).strip().lower()
    if template_type in ("pcr-template", "linear-pcr-template", "genomic-dna",
                         "plasmid-pcr-template"):
        return "pcr"
    if _as_bool(profile.get("high_fidelity_required")):
        return "pcr"
    if "five_prime_tail" in profile and profile.get("five_prime_tail") not in (
            None, "", "unknown"):
        return "pcr"
    if profile.get("specificity_checked") is True:
        return "pcr"
    return None


def _source_matches(category, profile, item):
    applicable = set(item.get("applicable_to") or [])
    if category == "pcr":
        try:
            length = float(profile.get("length"))
        except (TypeError, ValueError):
            length = None
        if length is None or length <= 0:
            return False, ["required profile field length is missing or invalid"]
        gc_value = profile.get("gc_percent")
        if gc_value is not None:
            try:
                gc_value = float(gc_value)
            except (TypeError, ValueError):
                return False, ["gc_percent is not numeric"]
            if not 0 <= gc_value <= 100:
                return False, ["gc_percent is outside 0..100"]
        if "high-fidelity-cloning-pcr" in applicable:
            return True, [
                "category=high-fidelity-cloning-pcr matched applicable_to",
                "observed length=%.0f bp" % length,
                "source=%s (%s)" % (item.get("provider"), item.get("title")),
            ]
        if "high-gc-pcr" in applicable:
            try:
                gc = float(profile.get("gc_percent"))
            except (TypeError, ValueError):
                gc = None
            if gc is not None and gc >= 60.0:
                return True, [
                    "category=high-gc-pcr matched applicable_to",
                    "observed gc_percent=%.1f%% >= 60%%" % gc,
                ]
    if category == "assembly":
        try:
            fragment_count = int(profile.get("fragment_count"))
        except (TypeError, ValueError):
            fragment_count = 0
        if fragment_count < 2:
            return False, ["required profile field fragment_count >= 2 is missing"]
        overlap_values = profile.get("overlap_lengths")
        if overlap_values is None and profile.get("overlap_length") is not None:
            overlap_values = [profile.get("overlap_length")]
        if not overlap_values:
            return False, ["required profile field overlap_length(s) is missing"]
        try:
            overlap_values = [float(value) for value in overlap_values]
        except (TypeError, ValueError):
            return False, ["overlap_length(s) must be numeric"]
        if any(value < 12 or value > 40 for value in overlap_values):
            return False, ["overlap length must be within validated 12..40 bp"]
        if "gibson-like-assembly" in applicable or "nebuilder-hifi" in applicable:
            return True, [
                "category=gibson-like-assembly matched applicable_to",
                "observed fragment_count=%d" % fragment_count,
                "observed overlap_lengths=%s" % overlap_values,
                "source=%s (%s)" % (item.get("provider"), item.get("title")),
            ]
    return False, []


def _pick_source(category, profile, sources):
    best = None
    best_reasons = []
    for index, item in enumerate(sources):
        matched, reasons = _source_matches(category, profile, item)
        if matched:
            best = (index, item, reasons)
            break
    return best


def recommend(profiles, protocol_sources=None):
    sources = protocol_sources or []
    usable_sources = [item for item in sources if usable_source(item)]
    profiles = list(profiles or [])
    if not profiles:
        return {
            "schema_version": "0.8.0",
            "status": "unavailable",
            "reason": "NO_REACTION_PROFILES_PROVIDED",
            "recommendations": [],
            "provenance": ([source_object(item) for item in sources]
                           if sources else [source(
                               "software", "No verified protocol source",
                               "protocol-recommendation",
                               status="unavailable")]),
        }
    if not sources:
        return {
            "schema_version": "0.8.0",
            "status": "unavailable",
            "reason": "PROTOCOL_SOURCE_NOT_FOUND",
            "recommendations": [],
            "provenance": [source(
                "software", "No verified protocol source",
                "protocol-recommendation", status="unavailable")],
        }
    recommendations = []
    matched_count = 0
    for index, profile in enumerate(profiles):
        category = _category_for(profile)
        choice = _pick_source(category, profile, usable_sources)
        if choice is None:
            recommendations.append({
                "recommendation_id": "pcr-%03d" % (index + 1),
                "reaction_id": profile.get("fragment_id", "unknown"),
                "category": category or "unmatched-profile",
                "recommended_system": None,
                "status": "insufficient_evidence",
                "match_reasons": [
                    "no evidence source matches observed profile features",
                    "observed profile: %s" % json.dumps(
                        {key: profile.get(key) for key in (
                            "length", "gc_percent", "template_type",
                            "assembly_method", "high_fidelity_required",
                            "specificity_checked") if key in profile},
                        sort_keys=True, ensure_ascii=False),
                ],
                "limitations": ["no matching verified protocol source"],
                "source": None,
                "evidence_level": "none",
                "human_review_required": True,
            })
            continue
        source_index, item, reasons = choice
        matched_count += 1
        recommendations.append({
            "recommendation_id": "pcr-%03d" % (index + 1),
            "reaction_id": profile.get("fragment_id", "unknown"),
            "category": category or "unmatched-profile",
            "recommended_system": (
                "Q5 High-Fidelity DNA Polymerase"
                if "high-fidelity-cloning-pcr" in (item.get("applicable_to") or [])
                else "NEBuilder HiFi DNA Assembly"),
            "status": "compatible_candidate",
            "match_reasons": reasons,
            "limitations": ["no wet-lab validation", "conditions need human review"],
            "source": source_object(item),
            "evidence_level": "manufacturer-official-source; design-specific-fit-unverified",
            "match_scope": "category-level compatibility only",
            "required_manual_checks": [
                "exact product/catalog and current revision",
                "template length/GC and primer Tm",
                "fragment count, molar ratios, DNA amount and reaction volume",
                "host strain and laboratory inventory",
            ],
            "human_review_required": True,
        })
    return {
        "schema_version": "0.8.0",
        "status": "partial" if matched_count and matched_count < len(profiles) else (
            "available" if matched_count == len(profiles) else "unavailable"),
        "reason": None if matched_count else "NO_PROFILE_MATCHED_EVIDENCE",
        "recommendations": recommendations,
        "provenance": [source_object(item) for item in sources],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile")
    parser.add_argument("--protocol-evidence",
                        help="JSON evidence file; default packaged evidence")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.profile:
        with open(args.profile, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        profiles = data.get("reaction_profiles", [])
    else:
        profiles = [{"fragment_id": "no-profile"}]
    sources = load_sources(args.protocol_evidence)
    result = recommend(profiles, sources)
    if args.json:
        jprint(result)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    main()
