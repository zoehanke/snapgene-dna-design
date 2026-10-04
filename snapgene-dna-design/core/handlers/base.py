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
import hashlib
import pathlib
import copy
from typing import TYPE_CHECKING

from Bio import SeqIO
from core.models.construct_model import ConstructModel, feature_to_dict
from core.tools.sequence_ops import slice_record_interval
from core.io.input_resolution import resolve_sequence_record
from core.models.molecule import as_molecule, derived_molecule


def planned_molecule(record, task):
    """Bind a handler's actual transformed record to its actual input versions."""
    sources = [as_molecule(s.get('_resolved_path') or s.get('path') or s.get('filepath'))
               for s in task.get('sources', [])]
    record.annotations.setdefault('topology', task.get('product', {}).get('topology'))
    return derived_molecule(record, sources, operation=task['task_kind'],
                            strandedness=getattr(record, 'strandedness', None),
                            left_end=getattr(record,'left_end',None), right_end=getattr(record,'right_end',None))


def record_slice(record, start, end, strand=1):
    """Extract an explicit interval with all overlapping annotation parts."""
    circular = record.annotations.get("topology") == "circular"
    length = end-start if end >= start else len(record)-start+end
    result = slice_record_interval(record, start, length, circular=circular)
    if strand == -1:
        result = result.reverse_complement(id=True, name=True, description=True)
    elif strand != 1:
        raise ValueError("record interval strand must be 1 or -1")
    result.annotations.update(molecule_type="DNA", topology="linear")
    return result


def insert_record(record, boundary, inserted):
    result = ConstructModel(record).insert(boundary, str(inserted.seq)).to_record()
    result.features.extend(copy.deepcopy(f)._shift(boundary) for f in inserted.features)
    return result


def replace_record(record, start, end, inserted):
    if start > end:
        # Keep the declared display origin: replacement then retained backbone.
        retained = record_slice(record, end, start)
        result = inserted + retained
        result.annotations.update(molecule_type="DNA", topology=record.annotations.get("topology", "linear"))
        return result
    result = ConstructModel(record).delete(start, end).to_record()
    return insert_record(result, start, inserted)


def product_features(record, expected_sequence):
    """Serialize only the actual transformed record, never inferred annotations."""
    if str(record.seq).upper() != expected_sequence.upper():
        raise ValueError("Transformed record sequence disagrees with planned sequence")
    # A missing translation may be derived only from an independently valid
    # complete CDS. Never replace a contradictory source qualifier to pass QC.
    from core.tools.sequence_ops import validate_cds_feature
    for feature in record.features:
        if feature.type == "CDS" and "translation" not in feature.qualifiers:
            audit = validate_cds_feature(feature, record.seq)
            if audit["valid"] and not audit["partial"]:
                feature.qualifiers["translation"] = [audit["translation"]]
    return [feature_to_dict(f, len(record)) for f in record.features]


def overlap_record(records, sequence, overlap, circular):
    from core.tools.feature_ops import migrate_features_after_assembly
    offset = -overlap if circular else 0
    fragments = []
    for record in records:
        fragments.append({"offset_in_product": offset, "length": len(record),
                          "features": [feature_to_dict(f, len(record)) for f in record.features]})
        offset += len(record)-overlap
    return resolve_sequence_record({"sequence": sequence, "topology": "circular" if circular else "linear",
        "features": migrate_features_after_assembly(fragments, len(sequence), circular=circular).analysis['features']})

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

    def execute(self, task: dict, plan: dict, out_dir: pathlib.Path) -> dict:
        """Execute plan deterministically and write intermediate files into out_dir."""
        from core.errors import PlanningError
        from core.tools.snapgene_io import export_plasmid
        if "product_features" not in plan:
            raise PlanningError("PLAN_REGENERATION_REQUIRED", "Regenerate this legacy plan to bind source-derived annotations")
        out_dir.mkdir(parents=True, exist_ok=True)
        if 'product_molecule' not in plan:
            raise PlanningError('PLAN_REGENERATION_REQUIRED', 'Regenerate plan for the complete molecular contract')
        record = as_molecule(plan['product_molecule'])
        files = export_plasmid(record, out_dir, "construct", topology=plan["product_topology"]).analysis
        gb_path, fa_path = pathlib.Path(files["gb_file"]), out_dir / "construct.fasta"
        dna_path = pathlib.Path(files["dna_file"])
        with fa_path.open("w", encoding="utf-8") as handle:
            SeqIO.write(record, handle, "fasta")
        return {"artifact_class": "intermediate", "method_maturity": self.method_maturity,
            "product_gb": str(gb_path), "product_fasta": str(fa_path),
            "product_dna": str(dna_path),
            "artifact_hashes": {path.name: hashlib.sha256(path.read_bytes()).hexdigest().upper()
                                for path in (gb_path, fa_path, dna_path)},
            "product_sequence_sha256": plan["product_sequence_sha256"]}

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
