# -*- coding: utf-8 -*-
"""core/recipes/contract.py - Standard Recipe Result Contract.

Provides a unified, type-safe data structure for all 7 standard laboratory
recipes, clearly distinguishing between complete plasmid constructs,
functional components/fragments, PCR primers, and QC verification designs.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields
from core.models.molecule import Molecule
from core.models.construct_model import feature_to_dict
from typing import Any, Literal

ResultKind = Literal["construct", "component", "primers", "verification", "protocol"]
CompletenessKind = Literal["complete_construct", "component_only", "qc_only"]


@dataclass
class RecipeResult:
    recipe_name: str
    result_kind: ResultKind
    completeness: CompletenessKind
    products: list[Molecule] = field(default_factory=list)
    analysis: dict[str, Any] = field(default_factory=dict)
    checks: list[dict[str, Any]] = field(default_factory=list)
    subject: Molecule | None = None
    primers: list[dict[str, Any]] = field(default_factory=list)
    quality_checks: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    protocol_steps: list[dict[str, Any]] = field(default_factory=list)
    citations: list[dict[str, Any]] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def product_record(self):
        if self.result_kind == 'verification':
            return self.subject
        if len(self.products) > 1:
            raise ValueError('Recipe has multiple products; select one explicitly')
        return self.products[0] if self.products else None

    @property
    def product_sequence(self):
        record = self.product_record
        return str(record.seq) if record is not None else ''

    @property
    def product_topology(self):
        record = self.product_record
        return record.topology if record is not None else None

    @property
    def features(self):
        record = self.product_record
        return [feature_to_dict(f,len(record)) for f in record.features] if record is not None else []

    @property
    def quality_checks_table(self) -> list[dict[str, Any]]:
        """Return quality checks as a list of name/value records for tabular display."""
        return [{"name": k, "value": v} for k, v in self.quality_checks.items()]

    def is_plasmid_construct(self) -> bool:
        """Check if this recipe generated a full plasmid construct ready for .dna export."""
        return self.result_kind == "construct" and self.completeness == "complete_construct"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary, merging top-level fields and recipe-specific details."""
        from core.tools.result import to_wire
        d = {definition.name: to_wire(getattr(self,definition.name)) for definition in fields(self)}
        # Retained external Recipe report fields are projections of the one material,
        # never independent stored DNA or a second computation contract.
        d.update(product_sequence=self.product_sequence, product_topology=self.product_topology,
                 features=self.features)
        return {**d['details'], **d}

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
