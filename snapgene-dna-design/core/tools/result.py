"""One result surface for molecular products, analysis and scoped checks."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from core.models.molecule import Molecule


def to_wire(value):
    """Serialize only at explicit report/file/CLI boundaries."""
    from core.models.molecule import ProteinSequence
    if isinstance(value,ProteinSequence):
        return {'data_type':'protein_sequence','value':str(value)}
    if isinstance(value, (Molecule, ToolResult)):
        return value.to_dict()
    from Bio.SeqFeature import SeqFeature
    if isinstance(value,SeqFeature):
        from core.models.molecule import feature_data
        return feature_data(value)
    if isinstance(value, dict):
        return {key: to_wire(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_wire(item) for item in value]
    return value


@dataclass
class ToolResult:
    products: list[Molecule] = field(default_factory=list)
    analysis: dict[str, Any] = field(default_factory=dict)
    checks: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        if not all(isinstance(product, Molecule) for product in self.products):
            raise TypeError('ToolResult products must be complete Molecules')

    def to_dict(self):
        return {'products': [product.to_dict() for product in self.products],
                'analysis': to_wire(self.analysis), 'checks': to_wire(self.checks)}

    def only_product(self):
        if len(self.products) != 1:
            raise ValueError(f'An explicit product selection is required for {len(self.products)} products')
        return self.products[0]


def check_result(name, *, subject: Molecule, status, scope, conditions=None, details=None):
    if status not in ('PASSED', 'FAILED', 'INCOMPLETE', 'NOT_APPLICABLE'):
        raise ValueError('Unknown program check status')
    version=subject.record_version
    return {'name': name, 'subject_version': version,
            'subject_id': f'{subject.id}:{version}', 'status': status,
            'scope': scope, 'conditions': conditions or {}, 'details': details or {}}


def reaction_checks(products, name, conditions=None):
    """Called only after an actual reaction simulation's constraints succeed."""
    return [check_result(name,subject=p,status='PASSED',scope='preparation_model',
        conditions=conditions, details={'inputs':list(p.source_refs), 'wet_lab':'NOT_CHECKED'}) for p in products]
