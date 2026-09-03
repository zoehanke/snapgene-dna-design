# -*- coding: utf-8 -*-
"""Task Handlers for SnapGene DNA Design (v0.9.1-dev2)."""
from __future__ import annotations

from core.handlers.base import TaskHandler
from core.handlers.component_amplification import ComponentAmplificationHandler
from core.handlers.composite_pipeline import CompositePipelineHandler
from core.handlers.crispr_editing import CrisprEditingHandler
from core.handlers.gateway_recombination import GatewayRecombinationHandler
from core.handlers.hierarchical_assembly import HierarchicalAssemblyHandler
from core.handlers.integration_donor import IntegrationDonorHandler
from core.handlers.overlap_assembly import OverlapAssemblyHandler
from core.handlers.plasmid_insert import PlasmidInsertHandler
from core.handlers.plasmid_replace import PlasmidReplaceHandler
from core.handlers.point_mutation import PointMutationHandler
from core.handlers.protein_fusion import ProteinFusionHandler
from core.handlers.restriction_ligation import RestrictionLigationHandler

HANDLERS: dict[str, TaskHandler] = {
    "component_amplification": ComponentAmplificationHandler(),
    "plasmid_replace": PlasmidReplaceHandler(),
    "plasmid_insert": PlasmidInsertHandler(),
    "point_mutation": PointMutationHandler(),
    "overlap_assembly": OverlapAssemblyHandler(),
    "protein_fusion": ProteinFusionHandler(),
    "integration_donor": IntegrationDonorHandler(),
    "gateway_recombination": GatewayRecombinationHandler(),
    "restriction_ligation": RestrictionLigationHandler(),
    "hierarchical_assembly": HierarchicalAssemblyHandler(),
    "crispr_editing": CrisprEditingHandler(),
    "composite_pipeline": CompositePipelineHandler(),
    "pipeline": CompositePipelineHandler(),
}

__all__ = [
    "TaskHandler",
    "HANDLERS",
    "ComponentAmplificationHandler",
    "PlasmidReplaceHandler",
    "PlasmidInsertHandler",
    "PointMutationHandler",
    "OverlapAssemblyHandler",
    "ProteinFusionHandler",
    "IntegrationDonorHandler",
    "GatewayRecombinationHandler",
    "RestrictionLigationHandler",
    "HierarchicalAssemblyHandler",
    "CrisprEditingHandler",
    "CompositePipelineHandler",
]
