# -*- coding: utf-8 -*-
"""core/tools/experience_helper.py - Tier 4 Laboratory Experience Rules Helper & Retriever.

Provides fast, lightweight keyword- and category-based retrieval of 33 curated,
human-reviewed wet-lab experience rules (rules/preloaded_experience_rules.json)
to assist LLM agents and researchers with practical benchwork tips.
"""
from __future__ import annotations

import json
import pathlib
import re
from typing import Any

_RULES_CACHE: list[dict[str, Any]] | None = None
_RULES_PATH = pathlib.Path(__file__).resolve().parent.parent.parent / "rules" / "preloaded_experience_rules.json"


def _load_all_rules() -> list[dict[str, Any]]:
    global _RULES_CACHE
    if _RULES_CACHE is not None:
        return _RULES_CACHE

    if not _RULES_PATH.is_file():
        return []

    try:
        with open(_RULES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        _RULES_CACHE = data.get("rules", [])
    except Exception:
        _RULES_CACHE = []

    return _RULES_CACHE


def get_experience_categories() -> list[str]:
    """Return all distinct wet-lab experience categories available in the repository."""
    rules = _load_all_rules()
    categories = set()
    for r in rules:
        cat = r.get("source", {}).get("category")
        if cat:
            categories.add(cat)
    return sorted(list(categories))


def get_experience_rule_by_id(rule_id: str) -> dict[str, Any] | None:
    """Retrieve a specific experience rule by its exact canonical rule ID."""
    rules = _load_all_rules()
    target = rule_id.strip().lower()
    for r in rules:
        if r.get("id", "").lower() == target:
            return _format_rule_output(r)
    return None


def list_all_experience_rules(category: str = "") -> list[dict[str, Any]]:
    """List all available active wet-lab experience rules, optionally filtered by category."""
    rules = _load_all_rules()
    cat_filter = category.strip().lower()
    results = []
    for r in rules:
        if cat_filter:
            r_cat = r.get("source", {}).get("category", "").lower()
            if cat_filter not in r_cat:
                continue
        results.append(_format_rule_output(r))
    return results


def query_lab_experience(
    query: str = "",
    category: str = "",
    max_results: int = 5,
) -> dict[str, Any]:
    """Query human-reviewed wet-lab experience rules by keyword or category.

    Args:
        query: Free-text search terms (e.g. 'Gibson', 'colony PCR', 'DpnI', 'Sanger', '二聚体').
        category: Optional category filter (e.g. '菌落PCR', 'Gibson', '引物基础QC', '质粒稳定性').
        max_results: Maximum number of ranked tips to return (default: 5).

    Returns:
        Structured dictionary containing matched experience rules and practical wet-lab advice.
    """
    rules = _load_all_rules()
    q_tokens = [tok.strip().lower() for tok in re.split(r"[\s,;]+", query.strip()) if tok.strip()]
    cat_filter = category.strip().lower()

    scored_rules: list[tuple[int, dict[str, Any]]] = []

    for r in rules:
        r_id = r.get("id", "").lower()
        r_name = r.get("name", "").lower()
        src = r.get("source", {})
        r_cat = src.get("category", "").lower()
        r_msg = r.get("action", {}).get("message", "").lower()
        r_orig = src.get("original_text", "").lower()
        r_scene = src.get("trigger_scene", "").lower()

        # Category constraint check
        if cat_filter and cat_filter not in r_cat:
            continue

        if not q_tokens:
            scored_rules.append((1, r))
            continue

        score = 0
        for tok in q_tokens:
            if tok in r_id:
                score += 50
            if tok in r_name:
                score += 40
            if tok in r_cat:
                score += 30
            if tok in r_msg:
                score += 20
            if tok in r_orig or tok in r_scene:
                score += 10

        if score > 0:
            scored_rules.append((score, r))

    # Sort descending by score
    scored_rules.sort(key=lambda item: item[0], reverse=True)
    top_matches = [
        _format_rule_output(r, score=s)
        for s, r in scored_rules[:max_results]
    ]

    return {
        "query": query,
        "category_filter": category,
        "total_matched": len(scored_rules),
        "results": top_matches,
    }


def _format_rule_output(rule: dict[str, Any], score: int | None = None) -> dict[str, Any]:
    src = rule.get("source", {})
    action = rule.get("action", {})
    out = {
        "id": rule.get("id", ""),
        "name": rule.get("name", ""),
        "category": src.get("category", "General"),
        "advice": action.get("message", ""),
        "trigger_scene": src.get("trigger_scene", ""),
        "threshold": src.get("threshold", ""),
        "scope_exceptions": src.get("scope_exceptions", ""),
        "human_reviewed": src.get("verification", {}).get("human_reviewed", True),
    }
    if score is not None:
        out["relevance_score"] = score
    return out
