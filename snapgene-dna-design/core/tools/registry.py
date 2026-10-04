# -*- coding: utf-8 -*-
"""core/tools/registry.py - Unified Atomic Tool Registry for DNA Design Skill.

Defines ToolSpec, categorizes tools by purity/side-effects, and provides
dynamic dispatch for both LLM schema generation (GET_TOOL_DEFINITIONS)
and CompositePipelineHandler execution.
"""
from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Literal
from Bio.SeqRecord import SeqRecord


MOLECULE_INPUT_SCHEMA = {
    'anyOf': [{'type': 'string'}, {'type': 'object', 'required': ['sequence'],
        'properties': {'sequence': {'type': 'string'},
                       'topology': {'enum': ['linear', 'circular', None]}}}],
}


def _schema_value(value):
    from core.models.molecule import ProteinSequence
    if isinstance(value,ProteinSequence):
        raise ValueError('Protein analysis cannot be used as DNA input')
    from Bio.Seq import Seq
    if isinstance(value, Seq):
        return str(value)
    if isinstance(value, SeqRecord):
        return {'sequence': str(value.seq), 'topology': value.annotations.get('topology')}
    if isinstance(value, dict):
        return {key: _schema_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_schema_value(item) for item in value]
    from pathlib import Path
    return str(value) if isinstance(value, Path) else value


def _parameter_schema(annotation):
    import types
    from typing import get_args, get_origin
    from Bio.Seq import Seq
    from pathlib import Path
    origin, args = get_origin(annotation), get_args(annotation)
    if annotation in (SeqRecord, Seq) or any(a in (SeqRecord, Seq) for a in args):
        return MOLECULE_INPUT_SCHEMA.copy()
    if origin in (list, tuple):
        return {'type': 'array', 'items': _parameter_schema(args[0]) if args else {}}
    if origin in (dict,) or annotation is dict:
        return {'type': 'object'}
    if origin in (types.UnionType, __import__('typing').Union):
        alternatives = [_parameter_schema(a) for a in args]
        return {'anyOf': alternatives} if all(a for a in alternatives) else {}
    return {str: {'type': 'string'}, int: {'type': 'integer'}, float: {'type': 'number'},
            bool: {'type': 'boolean'}, type(None): {'type': 'null'}, Path: {'type': 'string'}}.get(annotation, {})


ToolCategory = Literal['compute', 'inspect', 'write', 'external', 'network']


@dataclass
class ToolSpec:
    name: str
    callable: Callable[..., Any]
    category: ToolCategory
    description: str
    parameters_schema: dict[str, Any]
    param_aliases: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        import copy
        import jsonschema
        from typing import get_type_hints
        self._signature = inspect.signature(self.callable)
        self._function = self.callable
        hints = get_type_hints(self.callable)
        schema = copy.deepcopy(self.parameters_schema)
        declarations = schema.get('properties', {})
        unknown = set(declarations) - set(self._signature.parameters)
        if unknown:
            raise ValueError(f'{self.name}: schema declares nonexistent parameters: {sorted(unknown)}')
        properties, required = {}, []
        for name, parameter in self._signature.parameters.items():
            if parameter.kind in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD):
                continue
            derived = _parameter_schema(hints.get(name))
            declared = declarations.get(name, {})
            merged = {**derived, **declared}
            # Complete molecule inputs and arrays use their actual Python type,
            # rather than an obsolete string-only declaration.
            if 'anyOf' in derived or derived.get('type') == 'array':
                for key in ('type', 'items', 'anyOf'):
                    merged.pop(key, None)
                merged.update(derived)
            merged.pop('default', None)
            if parameter.default is parameter.empty:
                required.append(name)
            else:
                merged['default'] = parameter.default
                if parameter.default is None and 'enum' in merged and None not in merged['enum']:
                    merged['enum'] = [*merged['enum'],None]
            properties[name] = merged
        schema.update(type='object', properties=properties, required=required, additionalProperties=False)
        self.parameters_schema = schema
        jsonschema.Draft7Validator.check_schema(schema)
        self._validator = jsonschema.Draft7Validator(schema)

    def to_definition(self):
        return {'name': self.name, 'description': f'[{self.category.upper()}] {self.description}',
                'category': self.category, 'parameters': self.parameters_schema,
                'result': {'products': 'Molecule[]', 'analysis': 'object', 'checks': 'ScopedCheck[]'}}

    def adapt_params(self, params):
        adapted = {}
        for key, value in params.items():
            canonical = self.param_aliases.get(key, key)
            if canonical in adapted:
                raise ValueError(f'Duplicate canonical argument: {canonical}')
            adapted[canonical] = value
        return adapted

    def execute(self, **kwargs):
        from core.errors import CoreError, ToolExecutionError
        from core.tools.result import ToolResult
        try:
            adapted = self.adapt_params(kwargs)
            self._validator.validate(_schema_value(adapted))
            bound = self._signature.bind(**adapted)
            bound.apply_defaults()
            result = self._function(*bound.args, **bound.kwargs)
            if not isinstance(result, ToolResult):
                raise TypeError(f'{self.name} returned a non-contract result')
            return result
        except CoreError:
            raise
        except Exception as exc:
            message = str(exc)
            prefix = message.split(':', 1)[0]
            code = getattr(exc,'error_code',None) or (prefix if prefix.startswith('QC_') else 'TOOL_EXECUTION_FAILED')
            raise ToolExecutionError(code, message, details={'tool': self.name, 'exception': type(exc).__name__}) from exc


# Global Registry Map
TOOL_REGISTRY: dict[str, ToolSpec] = {}


class DuplicateToolRegistration(Exception):
    """Raised when attempting to register a duplicate tool name."""
    pass


def register_tool(spec: ToolSpec) -> None:
    """Register a ToolSpec into the global registry. Raises DuplicateToolRegistration on duplicate."""
    if spec.name in TOOL_REGISTRY:
        raise DuplicateToolRegistration(f"Tool '{spec.name}' is already registered in TOOL_REGISTRY.")
    TOOL_REGISTRY[spec.name] = spec
    # Direct Python and registered calls use this same cached declaration.
    # This validates/errors only; it never transforms or reconstructs DNA.
    import functools
    import sys
    original = spec._function
    @functools.wraps(original)
    def public(*args, **kwargs):
        try:
            bound = spec._signature.bind(*args, **spec.adapt_params(kwargs))
        except TypeError as exc:
            from core.errors import ToolExecutionError
            raise ToolExecutionError('TOOL_ARGUMENT_INVALID', str(exc), details={'tool': spec.name}) from exc
        return spec.execute(**bound.arguments)
    spec.callable = public
    module = sys.modules.get(original.__module__)
    if module is not None and getattr(module, original.__name__, None) is original:
        for alias,value in list(vars(module).items()):
            if value is original:setattr(module,alias,public)
    package = sys.modules.get('core.tools')
    if package is not None and getattr(package, original.__name__, None) is original:
        setattr(package, original.__name__, public)


def get_tool(name: str) -> ToolSpec | None:
    """Look up a tool by name."""
    return TOOL_REGISTRY.get(name)


def list_tool_definitions() -> list[dict[str, Any]]:
    """Return JSON Schema tool declarations for all registered tools."""
    return [spec.to_definition() for spec in TOOL_REGISTRY.values()]


def init_default_registry() -> None:
    """Initialize standard atomic tools into TOOL_REGISTRY."""
    if TOOL_REGISTRY:
        return

    from core.tools.amplification import (
        anneal_oligos,
        calc_primer_tm,
        check_primer_dimers,
        design_overhang_primers,
        prepare_pcr_fragment,
        simulate_pcr,
    )
    from core.tools.assembly import (
        ligate_fragments,
        simulate_digest_ligation,
        simulate_golden_gate,
        simulate_overlap_assembly,
    )
    from core.tools.crispr import (
        design_crispr_grna,
        design_hdr_donor,
        extract_homology_arms,
        prepare_grna_oligos,
        prepare_pml104_guide,
    )
    from core.tools.experience_helper import (
        get_experience_categories,
        get_experience_rule_by_id,
        list_all_experience_rules,
        query_lab_experience,
    )
    from core.tools.feature_ops import (
        annotate_feature,
        get_feature,
        migrate_features_after_assembly,
    )
    from core.tools.fusion import fuse_in_frame, get_standard_element
    from core.tools.inspection import (
        find_open_reading_frames,
        inspect_dna,
        summarize_backbone,
    )
    from core.tools.restriction import (
        check_overhang_compatibility,
        digest_sequence,
        digest_type_iis,
        fill_or_chew_overhang,
        find_restriction_sites,
    )
    from core.tools.sequence_ops import (
        rotate_sequence,
        check_reading_frame,
        extract_subsequence,
        mutate_sequence,
        strip_terminal_codons,
    )
    from core.tools.snapgene_io import export_snapgene, open_in_snapgene
    from core.tools.translation import (
        get_codon_synonyms,
        reverse_complement,
        silent_mutation_remove_site,
        translate_dna,
    )

    tools = [
        ToolSpec('rotate_sequence',rotate_sequence,'compute',
                 'Rotate the origin of a circular Molecule, retaining sequence, annotations and input version.',
                 {'properties':{'origin_0based':{'minimum':0}}}),
        ToolSpec('ligate_fragments',ligate_fragments,'compute',
                 'Join prepared linear double-stranded Molecules with explicit compatible physical ends; no re-digestion.',
                 {'properties':{}}),
        ToolSpec(
            name="inspect_dna",
            callable=inspect_dna,
            category="inspect",
            description="Parse and inspect a DNA sequence file (GenBank, FASTA, SnapGene .dna) to retrieve topology, length, GC%, and all annotated features with exact coordinates.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "file_path_or_record": {"type": "string", "description": "Path to the GenBank, FASTA, or SnapGene .dna file, or SeqRecord."},
                },
                "required": ["file_path_or_record"],
            },
            param_aliases={"file_path": "file_path_or_record", "file": "file_path_or_record", "record": "file_path_or_record"},

        ),
        ToolSpec(
            name="summarize_backbone",
            callable=summarize_backbone,
            category="inspect",
            description="Identify plasmid backbone components: replication origins, antibiotic markers, and promoters.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "file_path_or_record": {"type": "string", "description": "Path to plasmid file or SeqRecord."},
                },
                "required": ["file_path_or_record"],
            },

        ),
        ToolSpec(
            name="get_feature",
            callable=get_feature,
            category="inspect",
            description="Find and extract a specific feature from a plasmid by name or type, returning sequence and coordinates.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "file_path_or_record": {"type": "string", "description": "Path to sequence file."},
                    "name_or_type": {"type": "string", "description": "Name or type of feature."},
                    "return_all": {"type": "boolean", "default": False},
                },
                "required": ["file_path_or_record", "name_or_type"],
            },
            param_aliases={
                "record_or_path": "file_path_or_record",
                "source": "file_path_or_record",
                "file": "file_path_or_record",
                "name": "name_or_type",
                "feature_name": "name_or_type",
            },

        ),
        ToolSpec(
            name="find_open_reading_frames",
            callable=find_open_reading_frames,
            category="compute",
            description="Find open reading frames (ORFs) in a DNA sequence or sequence file.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "file_path_or_seq": {"type": "string", "description": "DNA sequence or path to sequence file."},
                    "min_length_aa": {"type": "integer", "default": 30},
                    "transl_table": {"type": "integer", "default": 1},
                },
                "required": ["file_path_or_seq"],
            },
            param_aliases={"seq": "file_path_or_seq", "dna_seq": "file_path_or_seq", "min_len_aa": "min_length_aa"},

        ),
        ToolSpec(
            name="find_restriction_sites",
            callable=find_restriction_sites,
            category="compute",
            description="Analyze restriction enzyme recognition and cut sites in a DNA sequence or file.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "file_path_or_seq": {"type": "string", "description": "File path or DNA sequence."},
                    "enzymes": {"type": "array", "items": {"type": "string"}, "description": "Enzyme names."},
                    "topology": {"type": "string", "enum": ["circular", "linear"], "default": "linear"},
                },
                "required": ["file_path_or_seq"],
            },

        ),
        ToolSpec(
            name="digest_sequence",
            callable=digest_sequence,
            category="compute",
            description="Digest sequence with a restriction endonuclease, returning cleaved fragments and overhangs.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "seq": {"type": "string", "description": "DNA sequence."},
                    "enzyme": {"type": "string", "description": "Enzyme name."},
                    "circular": {"type": "boolean", "default": False},
                },
                "required": ["seq", "enzyme"],
            },

        ),
        ToolSpec(
            name="digest_type_iis",
            callable=digest_type_iis,
            category="compute",
            description="Digest fragment flanked by Type IIS restriction sites (BsaI, BsmBI), stripping recognition sites.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "fragment_seq": {"type": "string", "description": "Fragment flanked by Type IIS sites."},
                    "enzyme": {"type": "string", "default": "BsaI"},
                },
                "required": ["fragment_seq"],
            },

        ),
        ToolSpec(
            name="fill_or_chew_overhang",
            callable=fill_or_chew_overhang,
            category="compute",
            description="Enzymatic end-repair blunting of sticky ends via 5' fill-in or 3' chew-back.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "seq": {"type": "string", "description": "Double-stranded sequence core."},
                    "left_overhang": {"type": "string", "default": ""},
                    "right_overhang": {"type": "string", "default": ""},
                    "overhang_type": {"type": "string", "default": "5prime"},
                    "action": {"type": "string", "enum": ["fill_in", "chew_back"], "default": "fill_in"},
                },
                "required": ["seq"],
            },

        ),
        ToolSpec(
            name="check_overhang_compatibility",
            callable=check_overhang_compatibility,
            category="compute",
            description="Check if two overhangs can ligate based on geometry and sequence complementarity.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "overhang1": {"type": "string"},
                    "overhang2": {"type": "string"},
                    "type1": {"type": "string", "enum": ["5prime", "3prime", "blunt"], "default": "5prime"},
                    "type2": {"type": "string", "enum": ["5prime", "3prime", "blunt"], "default": "5prime"},
                },
                "required": ["overhang1", "overhang2"],
            },

        ),
        ToolSpec(
            name="extract_subsequence",
            callable=extract_subsequence,
            category="compute",
            description="Topology-aware sequence extraction supporting origin-crossing circular intervals.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "file_path_or_record": {"type": "string", "description": "File path or sequence record."},
                    "start": {"type": "integer", "description": "0-based start coordinate."},
                    "end": {"type": "integer", "description": "0-based end coordinate."},
                    "strand": {"type": "integer", "enum": [1, -1], "default": 1},
                    "topology": {"type": "string", "enum": ["circular", "linear"], "default": "linear"},
                    "wraps_origin": {"type": "boolean", "default": False},
                },
                "required": ["file_path_or_record", "start", "end"],
            },

            param_aliases={"source": "file_path_or_record"},

        ),
        ToolSpec(
            name="check_reading_frame",
            callable=check_reading_frame,
            category="compute",
            description="Check reading frame integrity, length multiple of 3, and internal stop codons.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "dna_seq": {"type": "string", "description": "DNA sequence or record."},
                    "start_offset": {"type": "integer", "default": 0},
                    "transl_table": {"type": "integer", "default": 1},
                },
                "required": ["dna_seq"],
            },
            param_aliases={"seq": "dna_seq", "seq_or_record": "dna_seq", "table_id": "transl_table"},

        ),
        ToolSpec(
            name="mutate_sequence",
            callable=mutate_sequence,
            category="compute",
            description="Apply precise point mutations, insertions, or deletions to a DNA sequence.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "dna_seq": {"type": "string", "description": "Base DNA sequence."},
                    "mutations": {"type": "array", "items": {"type": "object"}, "description": "Mutations list."},
                },
                "required": ["dna_seq", "mutations"],
            },

            param_aliases={"seq": "dna_seq"},

        ),
        ToolSpec(
            name="strip_terminal_codons",
            callable=strip_terminal_codons,
            category="compute",
            description="Strip start codon (ATG) or stop codons (TAA/TAG/TGA) from a CDS.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "cds_seq": {"type": "string", "description": "CDS nucleotide sequence."},
                    "strip_start": {"type": "boolean", "default": False},
                    "strip_stop": {"type": "boolean", "default": False},
                },
                "required": ["cds_seq"],
            },

            param_aliases={"seq": "cds_seq", "dna_seq": "cds_seq"},

        ),
        ToolSpec(
            name="calc_primer_tm",
            callable=calc_primer_tm,
            category="compute",
            description="Calculate exact melting temperature (Tm) with nearest-neighbor thermodynamics.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "primer_seq": {"type": "string", "description": "Primer sequence."},
                    "salt_conc_mM": {"type": "number", "default": 50.0},
                    "primer_conc_nM": {"type": "number", "default": 200.0},
                },
                "required": ["primer_seq"],
            },

        ),
        ToolSpec(
            name="check_primer_dimers",
            callable=check_primer_dimers,
            category="compute",
            description="Check for primer heterodimer or homodimer cross-hybridization.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "primer1": {"type": "string", "description": "Forward primer sequence."},
                    "primer2": {"type": "string", "description": "Reverse primer sequence (optional)."},
                },
                "required": ["primer1"],
            },

        ),
        ToolSpec(
            name="design_overhang_primers",
            callable=design_overhang_primers,
            category="compute",
            description="Design optimal forward and reverse primer pair with optional 5' overhang tails.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "template_record_or_seq": {"type": "string"},
                    "start": {"type": "integer"},
                    "end": {"type": "integer"},
                    "fwd_5prime_overhang": {"type": "string", "default": ""},
                    "rev_5prime_overhang": {"type": "string", "default": ""},
                    "target_tm": {"type": "number", "default": 60.0},
                    "min_core_len": {"type": "integer"},
                    "max_core_len": {"type": "integer"},
                    "prefer_primer3": {"type": "boolean"},
                    "circular": {"type": "boolean"},
                    "topology": {"type": "string", "enum": ["circular", "linear"]},
                },
                "required": ["template_record_or_seq", "start", "end"],
            },
            param_aliases={"template": "template_record_or_seq"},

        ),
        ToolSpec(
            name="anneal_oligos",
            callable=anneal_oligos,
            category="compute",
            description="Simulate in-vitro annealing of two single-stranded oligos.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "top_oligo": {"type": "string"},
                    "bottom_oligo": {"type": "string"},
                },
                "required": ["top_oligo", "bottom_oligo"],
            },

        ),
        ToolSpec(
            name="prepare_pcr_fragment",
            callable=prepare_pcr_fragment,
            category="compute",
            description="Prepare an exact template interval with added tails using validated complete primers. Long additions use successive real PCR intermediates; returns all preparation steps and primers.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "template": {"type": "string"},
                    "start": {"type": "integer", "minimum": 0},
                    "end": {"type": "integer", "minimum": 0},
                    "fwd_tail": {"type": "string", "default": ""},
                    "rev_tail": {"type": "string", "default": ""},
                    "name": {"type": "string", "default": "fragment"},
                    "target_tm": {"type": "number", "default": 60.0},
                },
                "required": ["template", "start", "end"],
            },


        ),
        ToolSpec(
            name="simulate_pcr",
            callable=simulate_pcr,
            category="compute",
            description="Simulate PCR amplification with forward and reverse primers on template.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "template_path_or_seq": {"type": "string"},
                    "f_primer": {"type": "string"},
                    "r_primer": {"type": "string"},
                    "topology": {"type": ["string", "null"], "enum": ["circular", "linear", None]},
                    "forward_binding_core_length": {"type": "integer", "minimum": 1},
                    "reverse_binding_core_length": {"type": "integer", "minimum": 1},
                    "forward_binding_start_0based": {"type": "integer", "minimum": 0},
                    "reverse_binding_start_0based": {"type": "integer", "minimum": 0},
                    "min_binding_len": {"type": "integer", "minimum": 1},
                },
                "required": ["template_path_or_seq", "f_primer", "r_primer"],
            },

            param_aliases={"template": "template_path_or_seq"},

        ),
        ToolSpec(
            name="simulate_overlap_assembly",
            callable=simulate_overlap_assembly,
            category="compute",
            description="Simulate homologous overlap assembly (Gibson Assembly / In-Fusion) of overlapping fragments.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "fragments": {"type": "array", "items": {"type": "string"}},
                    "min_overlap": {"type": "integer", "default": 15},
                    "circular": {"type": "boolean", "default": True},
                },
                "required": ["fragments"],
            },

        ),
        ToolSpec(
            name="simulate_golden_gate",
            callable=simulate_golden_gate,
            category="compute",
            description="Simulate Type IIS Golden Gate one-pot assembly.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "fragments": {"type": "array", "items": {"type": "string"}},
                    "enzyme": {"type": "string", "default": "BsaI"},
                    "circular": {"type": "boolean", "default": True},
                },
                "required": ["fragments"],
            },

        ),
        ToolSpec(
            name="simulate_digest_ligation",
            callable=simulate_digest_ligation,
            category="compute",
            description="Simulate restriction enzyme digestion of vector and insert followed by T4 DNA ligation.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "vector_source": {"type": "string"},
                    "insert_source": {"type": "string"},
                    "vector_enzymes": {"type": "array", "items": {"type": "string"}},
                    "insert_enzymes": {"type": "array", "items": {"type": "string"}},
                    "orientation": {"type": "string", "enum": ["auto", "forward", "reverse"], "default": "auto"},
                },
                "required": ["vector_source", "insert_source", "vector_enzymes"],
            },

            param_aliases={"vector": "vector_source", "insert": "insert_source"},

        ),
        ToolSpec(
            name="fuse_in_frame",
            callable=fuse_in_frame,
            category="compute",
            description="Fuse two protein coding sequences in-frame with optional linker and stop codon policy.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "partner5_seq": {"type": "string"},
                    "partner3_seq": {"type": "string"},
                    "linker_seq": {"type": "string", "default": ""},
                    "strip_p5_stop": {"type": "boolean", "default": True},
                    "add_terminal_stop": {"type": "boolean", "default": True},
                },
                "required": ["partner5_seq", "partner3_seq"],
            },

            param_aliases={"partner5": "partner5_seq", "partner3": "partner3_seq", "linker": "linker_seq"},

        ),
        ToolSpec(
            name="get_standard_element",
            callable=get_standard_element,
            category="compute",
            description="Retrieve nucleotide sequence and translation of standard biological tags and linkers.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Element name ('6xHis', 'FLAG', 'HA', 'TEV', '(G4S)3')."},
                },
                "required": ["name"],
            },

        ),
        ToolSpec(
            name="design_crispr_grna",
            callable=design_crispr_grna,
            category="compute",
            description="Scan target gene or locus for candidate CRISPR sgRNA target sites.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "target_seq_or_file": {"type": "string"},
                    "nuclease": {"type": "string", "enum": ["SpCas9", "AsCas12a"], "default": "SpCas9"},
                    "start": {"type": "integer"},
                    "end": {"type": "integer"},
                },
                "required": ["target_seq_or_file"],
            },
            param_aliases={"target": "target_seq_or_file"},

        ),
        ToolSpec(
            name="prepare_grna_oligos",
            callable=prepare_grna_oligos,
            category="compute",
            description="Generate top and bottom forward/reverse cloning oligos for sgRNA expression vectors.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "spacer_seq": {"type": "string"},
                    "vector_type": {"type": "string", "default": "BbsI"},
                },
                "required": ["spacer_seq"],
            },

        ),
        ToolSpec(
            name="prepare_pml104_guide",
            callable=prepare_pml104_guide,
            category="compute",
            description="Build a pML104 guide vector from its full circular template by actual inverse PCR and KLD; restores the required sgRNA scaffold.",
            parameters_schema={
                "type": "object",
                "properties": {"vector_record_or_seq": {"type": "string"},
                               "spacer_seq": {"type": "string"}},
                "required": ["vector_record_or_seq", "spacer_seq"],
            },

        ),
        ToolSpec(
            name="design_hdr_donor",
            callable=design_hdr_donor,
            category="compute",
            description="Design an HDR donor repair template with synonymous PAM mutation.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "target_seq_or_file": {"type": "string"},
                    "cut_position_0based": {"type": "integer"},
                    "edit_dna": {"type": "string"},
                    "left_arm_length": {"type": "integer", "default": 50},
                    "right_arm_length": {"type": "integer", "default": 50},
                    "grna_seq": {"type": "string", "default": ""},
                    "grna_strand": {"type": "integer", "enum": [1, -1]},
                    "edit_start_0based": {"type": "integer", "minimum": 0},
                    "edit_end_0based": {"type": "integer", "minimum": 0},
                    "donor_type": {"type": "string"},
                    "target_is_cds": {"type": "boolean"},
                    "cds_frame_offset": {"type": "integer"},
                    "require_pam_disruption": {"type": "boolean", "default": False},
                },
                "required": ["target_seq_or_file", "cut_position_0based", "edit_dna"],
            },

            param_aliases={"target": "target_seq_or_file", "cut_position": "cut_position_0based"},

        ),
        ToolSpec(
            name="extract_homology_arms",
            callable=extract_homology_arms,
            category="compute",
            description="Extract left and right homology arms centered at a genomic cut site.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "target_seq_or_file": {"type": "string"},
                    "cut_position_0based": {"type": "integer"},
                    "left_arm_length": {"type": "integer", "default": 50},
                    "right_arm_length": {"type": "integer", "default": 50},
                    "edit_dna": {"type": "string"},
                    "edit_start_0based": {"type": "integer", "minimum": 0},
                    "edit_end_0based": {"type": "integer", "minimum": 0},
                },
                "required": ["target_seq_or_file", "cut_position_0based"],
            },
            param_aliases={"target": "target_seq_or_file", "cut_position": "cut_position_0based"},

        ),
        ToolSpec(
            name="annotate_feature",
            callable=annotate_feature,
            category="compute",
            description="Append a new feature annotation; existing features are preserved, not replaced.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "record": {"type": "string", "description": "Sequence record, file path, or DNA sequence."},
                    "name": {"type": "string", "description": "Feature label/name."},
                    "feature_type": {"type": "string", "default": "misc_feature"},
                    "start": {"type": "integer", "default": 0},
                    "end": {"type": "integer", "default": 0},
                    "strand": {"type": "integer", "default": 1},
                    "color": {"type": "string", "default": ""},
                },
                "required": ["record", "name"],
            },
            param_aliases={
                "record_or_path": "record",
                "source": "record",
                "file": "record",
                "start_0based": "start",
                "end_0based": "end",
            },

        ),
        ToolSpec(
            name="migrate_features_after_assembly",
            callable=migrate_features_after_assembly,
            category="compute",
            description="Remap feature annotations from source fragments to assembled product construct.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "fragments": {"type": "array", "items": {"type": "object"}, "description": "Fragments with offset_in_product, length, features, strand."},
                    "total_length": {"type": "integer", "description": "Total length of assembled product."},
                    "circular": {"type": "boolean", "default": True},
                },
                "required": ["fragments", "total_length"],
            },
            param_aliases={"fragments_features": "fragments", "product_length": "total_length"},

        ),
        ToolSpec(
            name="reverse_complement",
            callable=reverse_complement,
            category="compute",
            description="Generate reverse complement of a DNA sequence string.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "seq": {"type": "string", "description": "DNA sequence."},
                },
                "required": ["seq"],
            },

        ),
        ToolSpec(
            name="translate_dna",
            callable=translate_dna,
            category="compute",
            description="Translate DNA sequence to amino acids.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "seq": {"type": "string", "description": "DNA sequence."},
                    "frame": {"type": "integer", "default": 1},
                    "table": {"type": "integer", "default": 1},
                },
                "required": ["seq"],
            },
            param_aliases={"seq_or_record": "seq", "dna_seq": "seq", "table_id": "table"},

        ),
        ToolSpec(
            name="get_codon_synonyms",
            callable=get_codon_synonyms,
            category="compute",
            description="Retrieve synonymous codons translating to same amino acid.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "codon": {"type": "string"},
                    "table": {"type": "integer", "default": 1},
                },
                "required": ["codon"],
            },

        ),
        ToolSpec(
            name="silent_mutation_remove_site",
            callable=silent_mutation_remove_site,
            category="compute",
            description="Introduce synonymous mutations into CDS to silence restriction site without altering translation.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "cds_seq": {"type": "string"},
                    "enzyme_name": {"type": "string"},
                    "frame_offset": {"type": "integer", "default": 0},
                },
                "required": ["cds_seq", "enzyme_name"],
            },

            param_aliases={"enzyme": "enzyme_name"},

        ),
        ToolSpec(
            name="export_snapgene",
            callable=export_snapgene,
            category="write",
            description="Export designed construct into native SnapGene .dna and standard GenBank (.gb) files.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "record_or_seq": {"type": "string"},
                    "out_dir": {"type": "string"},
                    "filename_base": {"type": "string", "default": "construct"},
                    "topology": {"type": "string", "enum": ["circular", "linear"], "default": "circular"},
                },
                "required": ["record_or_seq", "out_dir"],
            },

        ),
        ToolSpec(
            name="open_in_snapgene",
            callable=open_in_snapgene,
            category="external",
            description="Launch local desktop SnapGene application to view construct map directly.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                },
                "required": ["file_path"],
            },

        ),
        ToolSpec(
            name="query_lab_experience",
            callable=query_lab_experience,
            category="compute",
            description="Retrieve wet-lab experience rules and practical tips.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "default": ""},
                    "category": {"type": "string", "default": ""},
                    "max_results": {"type": "integer", "default": 5},
                },
            },

        ),
        ToolSpec(
            name="get_experience_categories",
            callable=get_experience_categories,
            category="compute",
            description="List categories in experience rules store.",
            parameters_schema={"type": "object", "properties": {}},

        ),
        ToolSpec(
            name="get_experience_rule_by_id",
            callable=get_experience_rule_by_id,
            category="compute",
            description="Retrieve specific experience rule by its rule_id.",
            parameters_schema={
                "type": "object",
                "properties": {"rule_id": {"type": "string"}},
                "required": ["rule_id"],
            },

        ),
        ToolSpec(
            name="list_all_experience_rules",
            callable=list_all_experience_rules,
            category="compute",
            description="List all available wet-lab experience rules.",
            parameters_schema={"type": "object", "properties": {}},

        ),
    ]

    for tool in tools:
        register_tool(tool)


# Initialize default tools upon module load
init_default_registry()
