# -*- coding: utf-8 -*-
"""planning/intent.py - Structured assembly intent and a small NL parser.

The AI-facing contract is ``plan_assembly(..., intent=...)`` with a JSON
object.  ``parse_intent_text`` accepts a deterministic key=value subset for
CLI use; it never invents fields it cannot parse.
"""
import re


def _coerce_interval(value):
    if value is None:
        return None
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return [int(value[0]), int(value[1])]
    text = str(value).strip()
    match = re.match(r"^(\d+)-(\d+)$", text)
    if match:
        return [int(match.group(1)), int(match.group(2))]
    match = re.match(r"^(\d+):(\d+)$", text)
    if match:
        return [int(match.group(1)), int(match.group(2))]
    return None


def normalize_intent(intent):
    if not isinstance(intent, dict):
        raise ValueError("ASSEMBLY_INTENT_MUST_BE_DICT")
    result = {
        "goal": str(intent.get("goal") or "assembly-plan"),
        "method": str(intent.get("method") or "auto").lower(),
        "topology": str(intent.get("topology") or "circular"),
        "backbone": dict(intent.get("backbone") or {}),
        "fragments": [dict(item) for item in intent.get("fragments", [])],
        "fusion": intent.get("fusion"),
        "tag": intent.get("tag"),
        "name": intent.get("name") or "assembled-construct",
        "overlap_length": (None if intent.get("overlap_length") is None
                            else int(intent.get("overlap_length"))),
        "enzymes": ([str(item) for item in intent.get("enzymes", [])]
                     if intent.get("enzymes") is not None else None),
    }
    backbone = result["backbone"]
    if "interval" in backbone:
        backbone["interval"] = _coerce_interval(backbone["interval"])
    for fragment in result["fragments"]:
        if "interval" in fragment:
            fragment["interval"] = _coerce_interval(fragment["interval"])
    if result["method"] not in ("auto", "overlap", "gibson",
                                "golden_gate", "digest-ligate"):
        raise ValueError("UNSUPPORTED_ASSEMBLY_METHOD: %s" % result["method"])
    if result["topology"] not in ("linear", "circular"):
        raise ValueError("UNSUPPORTED_TOPOLOGY: %s" % result["topology"])
    if result["overlap_length"] is not None and result["overlap_length"] <= 0:
        raise ValueError("OVERLAP_LENGTH_MUST_BE_POSITIVE")
    return result


def parse_intent_text(text):
    """Parse ``key=value;...`` pairs plus a simple Chinese fallback."""
    if not text:
        raise ValueError("EMPTY_ASSEMBLY_INTENT_TEXT")
    data = {}
    for part in str(text).replace("；", ";").split(";"):
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            key, value = part.split("=", 1)
            key = key.strip().lower()
            value = value.strip()
            if key == "backbone":
                data["backbone"] = {"source": int(value)}
            elif key == "fragments":
                fragments = []
                for token in value.split(","):
                    if not token:
                        continue
                    if ":" in token:
                        source_s, name = token.split(":", 1)
                        interval = _coerce_interval(name)
                        if interval:
                            fragments.append({"source": int(source_s),
                                              "interval": interval})
                        else:
                            fragments.append({"source": int(source_s),
                                              "feature": name})
                    else:
                        fragments.append({"source": int(token)})
                data["fragments"] = fragments
            elif key == "method":
                data["method"] = value
            elif key == "topology":
                data["topology"] = value
            elif key == "name":
                data["name"] = value
            elif key == "goal":
                data["goal"] = value
        else:
            chinese = str(part)
            if "骨架" in chinese or "骨架质粒" in chinese:
                match = re.search(r"(\d+)\s*号", chinese)
                if match:
                    data.setdefault("backbone", {"source": int(match.group(1))})
            if "Gibson" in chinese or "gibson" in chinese:
                data["method"] = "gibson"
            elif "Golden Gate" in chinese or "golden gate" in chinese:
                data["method"] = "golden_gate"
            elif "overlap" in chinese.lower():
                data["method"] = "overlap"
    if "backbone" not in data:
        raise ValueError("INTENT_MISSING_BACKBONE_SOURCE")
    if "fragments" not in data:
        raise ValueError("INTENT_MISSING_FRAGMENTS")
    return normalize_intent(data)
