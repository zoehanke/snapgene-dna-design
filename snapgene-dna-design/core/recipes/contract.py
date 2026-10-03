# -*- coding: utf-8 -*-
"""core/recipes/contract.py - Standard Recipe Result Contract.

Provides a unified, type-safe data structure for all 7 standard laboratory
recipes, clearly distinguishing between complete plasmid constructs,
functional components/fragments, PCR primers, and QC verification designs.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

ResultKind = Literal["construct", "component", "primers", "verification", "protocol"]
CompletenessKind = Literal["complete_construct", "component_only", "qc_only"]


@dataclass
class RecipeResult:
    recipe_name: str
    result_kind: ResultKind
    completeness: CompletenessKind
    product_sequence: str = ""
    product_topology: Literal["circular", "linear"] = "circular"
    features: list[dict[str, Any]] = field(default_factory=list)
    primers: list[dict[str, Any]] = field(default_factory=list)
    quality_checks: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    protocol_steps: list[dict[str, Any]] = field(default_factory=list)
    citations: list[dict[str, Any]] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def quality_checks_table(self) -> list[dict[str, Any]]:
        """Return quality checks as a list of name/value records for tabular display."""
        return [{"name": k, "value": v} for k, v in self.quality_checks.items()]

    def is_plasmid_construct(self) -> bool:
        """Check if this recipe generated a full plasmid construct ready for .dna export."""
        return self.result_kind == "construct" and self.completeness == "complete_construct"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary, merging top-level fields and recipe-specific details."""
        d = asdict(self)
        # Recipe-specific detail must never change a contract field's type.
        # Retain the nested detail and expose non-contract extras for older callers.
        det = d["details"]
        return {**det, **d}

    def __getitem__(self, key: str) -> Any:
        if hasattr(self, key):
            return getattr(self, key)
        if key in self.details:
            return self.details[key]
        raise KeyError(key)

    def __setitem__(self, key: str, value: Any) -> None:
        if hasattr(self, key):
            setattr(self, key, value)
        else:
            self.details[key] = value

    def __contains__(self, key: str) -> bool:
        return (key in self.details) or hasattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        if hasattr(self, key):
            return getattr(self, key)
        if key in self.details:
            return self.details[key]
        return default
