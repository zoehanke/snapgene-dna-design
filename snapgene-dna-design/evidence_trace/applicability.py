"""Conservative structured-context comparison, not biological claim verification."""
from __future__ import annotations

import copy
import math
import re

VERSION = "structured-context-v0.2.0"
DIMENSIONS = ("organism", "strain", "host", "construct_context", "temperature", "medium", "assay", "intended_use")
ALIASES = {"host": ("host", "chassis", "host_or_chassis", "host/chassis"),
           "construct_context": ("construct_context", "construct context"),
           "intended_use": ("intended_use", "intended use", "use")}
UNKNOWN = {"", "unknown", "unspecified", "not reported", "未提供", "未知"}
TAXON_ALIASES = {"e. coli": "escherichia coli", "s. cerevisiae": "saccharomyces cerevisiae",
                 "s. eubayanus": "saccharomyces eubayanus"}


def canonical_context(context):
    if not isinstance(context, dict):
        return {}
    output = {}
    for dimension in DIMENSIONS:
        values = [context[k] for k in ALIASES.get(dimension, (dimension,)) if k in context]
        if values:
            output[dimension] = values[0] if all(v == values[0] for v in values) else {"conflicting_aliases": values}
    return output


def temperature(value):
    unit = "C"
    if isinstance(value, dict):
        unit = str(value.get("unit", "C")).upper().replace("°", "")
        low, high = value.get("min", value.get("value")), value.get("max", value.get("value"))
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        low = high = value
    elif isinstance(value, str):
        match = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*°?\s*([CF])?\s*", value, re.I)
        if not match:
            return None
        low = high = float(match[1])
        unit = (match[2] or "C").upper()
    else:
        return None
    try:
        low, high = float(low), float(high)
    except (ValueError, TypeError):
        return None
    if unit not in {"C", "F"} or not all(math.isfinite(v) for v in (low, high)) or low > high:
        return None
    if unit == "F":
        low, high = (low - 32) * 5 / 9, (high - 32) * 5 / 9
    return round(low, 6), round(high, 6)


def categorical(value):
    values = value if isinstance(value, list) else [value]
    if not values or any(not isinstance(v, str) or v.strip().casefold() in UNKNOWN for v in values):
        return None
    return {re.sub(r"\s+", " ", v.strip()).casefold() for v in values}


def compare(dimension, source, target):
    a, b = (temperature(source), temperature(target)) if dimension == "temperature" else (categorical(source), categorical(target))
    if a is None or b is None:
        return "UNKNOWN", "缺失、未报告、别名冲突或格式不可比较；需要解释"
    if dimension in {"organism", "host"}:
        a, b = ({TAXON_ALIASES.get(v, v) for v in values} for values in (a, b))
    if a == b:
        return "MATCH", "所声明值一致" + ("（统一为摄氏度）" if dimension == "temperature" else "（规范大小写、空白及有限物种简称）")
    overlap = max(a[0], b[0]) <= min(a[1], b[1]) if dimension == "temperature" else bool(a & b)
    return ("PARTIAL", "范围或声明集合部分重合") if overlap else ("DIFFERENT", "所声明值不同；不自动推断生物学后果")


def assess(source_context, target_context, required_dimensions=None):
    source, target = canonical_context(source_context), canonical_context(target_context)
    required = list(DIMENSIONS if required_dimensions is None else required_dimensions)
    if not required or any(d not in DIMENSIONS for d in required):
        raise ValueError("required_dimensions must explicitly name supported context dimensions")
    rows = []
    for d in DIMENSIONS:
        status, reason = compare(d, source.get(d), target.get(d))
        rows.append({"dimension": d, "source": copy.deepcopy(source.get(d)), "target": copy.deepcopy(target.get(d)),
                     "result": status, "reason": reason, "required": d in required})
    selected = [r for r in rows if r["required"]]
    grounding = [r for r in selected if r["dimension"] in {"organism", "host", "construct_context", "intended_use"}]
    transfer = [r for r in selected if r["dimension"] in {"organism", "strain", "host", "construct_context", "intended_use"} and r["result"] == "DIFFERENT"]
    if not any(r["result"] != "UNKNOWN" for r in grounding):
        status, reason = "unknown", "缺少可比较的对象、宿主、构建背景或用途；局部条件相同不足以认定适用"
    elif transfer:
        status, reason = "extrapolated", "外推涉及不同的 " + ", ".join(r["dimension"] for r in transfer)
    elif all(r["result"] == "MATCH" for r in selected):
        status, reason = "direct", "指定维度的声明上下文一致；仅限这些维度，不证明 Claim"
    elif any(r["result"] != "UNKNOWN" for r in selected):
        status = "partial"
        reason = "; ".join(label + ": " + ", ".join(r["dimension"] for r in selected if r["result"] == state)
                           for state, label in (("DIFFERENT", "条件不同"), ("PARTIAL", "部分重合"), ("UNKNOWN", "未报告或不可比较"))
                           if any(r["result"] == state for r in selected))
    else:
        status, reason = "unknown", "没有足够的可比较上下文"
    return {"status": status, "reason": reason, "dimensions": rows,
            "source_context": copy.deepcopy(source_context), "target_context": copy.deepcopy(target_context),
            "required_dimensions": required, "algorithm_version": VERSION,
            "assessor": "deterministic structured-context comparison", "needs_interpretation": status != "direct",
            "scope": "No source identity, statement accuracy, claim validity or safety judgment."}
