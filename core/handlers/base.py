# -*- coding: utf-8 -*-
"""Base TaskHandler interface for SnapGene DNA Design (v0.9.1-dev2).

Every task kind is implemented as a dedicated TaskHandler with a unified contract:
1. validate_contract(task)
2. clarify(task)
3. plan(task)
4. execute(task, plan, out_dir)
5. recompute(task, plan)
6. validate_goal(task, plan, execution, product_record, product_seq)
7. delivery_policy(task, validation)
"""
from __future__ import annotations

from abc import ABC, abstractmethod
import pathlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Bio.SeqRecord import SeqRecord


class TaskHandler(ABC):
    """Abstract base class for all DNA construction task handlers."""
    kind: str
    handler_id: str
    handler_version: str = "1.0.0"
    method_maturity: str = "validated"  # "validated" or "experimental"
    required_fields: list[str] = []
    default_topology: str = "circular"

    @abstractmethod
    def validate_contract(self, task: dict) -> None:
        """Validate task schema and task-specific domain constraints."""
        pass

    @abstractmethod
    def clarify(self, task: dict) -> list[dict]:
        """Collect clarification questions when required biological fields are missing."""
        pass

    @abstractmethod
    def plan(self, task: dict) -> dict:
        """Construct explicit, deterministic execution plan."""
        pass

    @abstractmethod
    def execute(self, task: dict, plan: dict, out_dir: pathlib.Path) -> dict:
        """Execute plan deterministically and write intermediate files into out_dir."""
        pass

    @abstractmethod
    def recompute(self, task: dict, plan: dict) -> str:
        """Independently recompute expected product sequence from inputs and transformations."""
        pass

    @abstractmethod
    def validate_goal(
        self,
        task: dict,
        plan: dict,
        execution: dict,
        product_record: SeqRecord,
        product_seq: str,
    ) -> tuple[bool, list[dict], list[str]]:
        """Validate task goal against actual assembled product."""
        pass

    def delivery_policy(self, task: dict, validation: dict) -> dict:
        """Determine deliverability based on maturity and validation."""
        if self.method_maturity == "experimental":
            return {
                "authoritative_allowed": False,
                "artifact_class": "experimental-preview",
                "reason": f"Task kind '{self.kind}' uses experimental method approximations",
            }
        is_verified = (validation.get("overall") == "verified")
        return {
            "authoritative_allowed": is_verified,
            "artifact_class": "authoritative" if is_verified else "intermediate",
            "reason": "Verified mature method" if is_verified else "Validation incomplete",
        }
