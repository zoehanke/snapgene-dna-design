# -*- coding: utf-8 -*-
"""core/recipes/gibson.py - Standard SOP Recipe for Gibson & In-Fusion Assembly.

LITERATURE SOURCES & PROTOCOL REFERENCES:
1. Gibson, D.G., Young, L., Chuang, R.Y., Venter, J.C., Hutchison, C.A. and Smith, H.O. (2009).
   Enzymatic assembly of DNA molecules up to several hundred kilobases.
   Nature Methods, 6(5), pp.343-345. doi:10.1038/nmeth.1318.
2. New England Biolabs. (2023).
   NEBuilder® HiFi DNA Assembly Master Mix Protocol (NEB #E2621). Ipswich, MA.
3. Takara Bio / Clontech. (2022).
   In-Fusion® HD Cloning Plus User Manual.
"""
from __future__ import annotations

import pathlib
import copy
import hashlib
from typing import Any

from Bio.Seq import Seq
from Bio.SeqFeature import CompoundLocation, FeatureLocation
from Bio.SeqRecord import SeqRecord

from core.recipes.contract import RecipeResult
from core.tools.amplification import calc_primer_tm, check_primer_dimers, design_overhang_primers, simulate_pcr, prepare_pcr_fragment
from core.tools.assembly import (
    _arc,
    _feature_dicts_for_arc,
    simulate_overlap_assembly,
)
from core.models.molecule import Molecule, derived_molecule
from core.tools.result import ToolResult
from core.io.input_resolution import resolve_sequence_input, resolve_sequence_record
from core.tools.feature_ops import migrate_features_after_assembly


def _prepare_gibson_fragments(specs, records, targets, overlap, circular):
    """Choose which primer carries each added homology, minimizing PCR steps.

    A junction has two choices. Each fragment depends only on its incoming and
    outgoing junction, so two states per boundary suffice instead of enumerating
    every whole-construct layout. Candidates are actual validated PCR routes.
    """
    count = len(specs)
    cache = {}
    failures = []

    def candidate(index, incoming, outgoing):
        previous = targets[index-1] if index or circular else ""
        following = targets[(index+1) % count] if index+1 < count or circular else ""
        target = targets[index]
        left = previous[-overlap:] if previous and incoming == 0 and previous[-overlap:] != target[:overlap] else ""
        right = str(Seq(following[:overlap]).reverse_complement()) if following and outgoing == 1 and target[-overlap:] != following[:overlap] else ""
        key = (index, left, right)
        if key not in cache:
            spec = specs[index]
            try:
                cache[key] = prepare_pcr_fragment(records[index], spec["start"], spec["end"], left, right, name=spec["id"])
            except ValueError as exc:
                if not str(exc).startswith(("NO_VALID_PRIMER_PAIR", "OLIGO_LENGTH_LIMIT", "No unique complete primer")):
                    raise
                cache[key] = None
                failures.append(f"{spec['id']}: {exc}")
        return cache[key]

    default = [candidate(index, 0, 0) for index in range(count)]
    if all(route is not None and len(route.analysis["preparation"]) == 1 for route in default):
        return default, [0] * count
    best = None
    for initial in ((0, 1) if circular else (0,)):
        states = {initial: ((0, 0), [], [])}
        for index in range(count):
            following_states = {}
            for incoming, (cost, routes, layout) in states.items():
                for outgoing in (0, 1):
                    route = candidate(index, incoming, outgoing)
                    if route is None:
                        continue
                    next_cost = (cost[0]+len(route.analysis["preparation"]), cost[1]+sum(len(p["sequence"]) for p in route.analysis["primers"]))
                    current = following_states.get(outgoing)
                    if current is None or next_cost < current[0]:
                        following_states[outgoing] = (next_cost, routes+[route], layout+[outgoing])
            states = following_states
        options = [states[initial]] if circular and initial in states else ([] if circular else list(states.values()))
        for option in options:
            if best is None or option[0] < best[0]:
                best = option
    if best is None:
        raise ValueError("NO_VALID_GIBSON_PRIMERS: no compatible homology placement; " + "; ".join(failures[:3]))
    return best[1], best[2]

AUTHORITATIVE_SOURCES = [
    {
        "citation": "Gibson et al. (2009). Enzymatic assembly of DNA molecules up to several hundred kilobases. Nature Methods 6:343-345.",
        "institution": "J. Craig Venter Institute (JCVI)",
        "doi": "10.1038/nmeth.1318",
        "rules_enforced": [
            "Homologous overlap length recommended at 20-25 bp for 2-3 fragment assembly (minimum 15 bp, maximum 40 bp).",
            "Overlap region GC content optimal between 40% and 60% with Tm >= 48°C to ensure stable single-strand annealing.",
            "Short fragments (< 200 bp) risk complete degradation by T5 5'->3' exonuclease; require increased molar ratio or shortened incubation.",
        ],
    },
    {
        "citation": "New England Biolabs (2023). NEBuilder® HiFi DNA Assembly Master Mix Protocol (NEB #E2621).",
        "institution": "New England Biolabs (NEB)",
        "url": "https://www.neb.com/en-us/protocols/2014/11/26/nebuilder-hifi-dna-assembly-reaction-protocol",
        "rules_enforced": [
            "Primer binding cores are evaluated with Biopython nearest-neighbor Tm under the same buffer conditions; accepted cores remain within 52–72°C, with 60°C as a ranking target.",
            "Every complete oligo is checked for hairpin, self-dimer and pair structure with Primer3 check_primers; cores above 36 nt use the extended Biopython search before this check.",
            "Forward and reverse core Tm difference is reported for the selected pair; it is not represented as a universal 60±2°C guarantee.",
        ],
    },
]


def _preparation_template(source: Any, record: SeqRecord) -> Any:
    """Keep original input identity while making in-memory records serializable."""
    if isinstance(source, (str, pathlib.Path)):
        return str(source)
    from core.models.molecule import as_molecule
    return as_molecule(record)


def _primer_delivery(name: str, primer: dict[str, Any], strand: int) -> dict[str, Any]:
    binding = primer.get("binding") or {}
    return {
        "name": name,
        "sequence": primer.get("full_sequence", ""),
        "seq": primer.get("full_sequence", ""),
        "binding_sequence": primer.get("binding_core", ""),
        "binding_core": primer.get("binding_core", ""),
        "location": [
            binding.get("template_start_0based"),
            binding.get("template_end_0based"),
        ],
        "binding_interval_0based": [
            binding.get("template_start_0based"),
            binding.get("template_end_0based"),
        ],
        "strand": strand,
        "tm": primer.get("binding_core_tm"),
        "binding_core_tm": primer.get("binding_core_tm"),
        "overhang_5prime": primer.get("overhang_5prime", ""),
        "binding": binding,
    }


def _pcr_product_record(pcr):
    """The actual annotated PCR product, not a reconstruction from report fields."""
    return pcr.only_product()


def _restore_unique_source_features(
    product_sequence: str,
    existing_features: list[dict[str, Any]],
    source_records: list[SeqRecord],
    circular: bool,
) -> list[dict[str, Any]]:
    """Restore complete source features whose bases cross PCR boundaries.

    PCR slicing can legitimately omit a feature annotation at a primer
    boundary even when the overlap restores the complete feature in the final
    molecule.  A feature is restored only when its exact extracted sequence
    occurs once in the product, with strand inferred from the matching
    orientation.  Ambiguous or partial matches remain unannotated.
    """
    from core.models.construct_model import feature_to_dict

    product = str(product_sequence).upper()
    restored = list(existing_features)
    existing_keys = {
        (
            feature.get("name"), feature.get("type"), feature.get("start"),
            feature.get("end"), feature.get("strand"),
        )
        for feature in restored
    }
    existing_spans = {
        (feature.get("name"), feature.get("type"), feature.get("start"), feature.get("end"))
        for feature in restored
    }
    source_complete_candidates: list[dict[str, Any]] = []

    def all_positions(needle: str) -> list[int]:
        if not needle or (circular and len(needle) > len(product)):
            return []
        search_product = product
        if circular:
            search_product += product[: len(needle) - 1]
        positions = []
        cursor = 0
        while True:
            found = search_product.find(needle, cursor)
            if found < 0:
                return positions
            if circular and found >= len(product):
                return positions
            positions.append(found)
            cursor = found + 1

    def matched_location(position: int, length: int, strand: int):
        end = position + length
        if not circular or end <= len(product):
            return FeatureLocation(position, end, strand=strand)
        if strand == -1:
            parts = [
                FeatureLocation(0, end - len(product), strand=strand),
                FeatureLocation(position, len(product), strand=strand),
            ]
        else:
            parts = [
                FeatureLocation(position, len(product), strand=strand),
                FeatureLocation(0, end - len(product), strand=strand),
            ]
        return CompoundLocation(
            parts,
            operator="join",
        )

    for record in source_records:
        for source_feature in getattr(record, "features", []):
            if source_feature.type == "source" or source_feature.location is None:
                continue
            source_sequence = str(source_feature.extract(record.seq)).upper()
            if len(source_sequence) < 20:
                continue
            reverse_sequence = str(Seq(source_sequence).reverse_complement())
            candidates = [(position, 1) for position in all_positions(source_sequence)]
            if reverse_sequence != source_sequence:
                candidates.extend((position, -1) for position in all_positions(reverse_sequence))
            if len(candidates) != 1:
                continue
            position, product_strand = candidates[0]
            copied = copy.deepcopy(source_feature)
            copied.location = matched_location(position, len(source_sequence), product_strand)
            feature_dict = feature_to_dict(copied, len(product))
            if circular and position + len(source_sequence) > len(product):
                feature_dict["location"]["wraps_origin"] = True
            source_complete_candidates.append(feature_dict)
            key = (
                feature_dict.get("name"), feature_dict.get("type"),
                feature_dict.get("start"), feature_dict.get("end"),
                feature_dict.get("strand"),
            )
            span_key = (
                feature_dict.get("name"), feature_dict.get("type"),
                feature_dict.get("start"), feature_dict.get("end"),
            )
            if key not in existing_keys and span_key not in existing_spans:
                restored.append(feature_dict)
                existing_keys.add(key)
                existing_spans.add(span_key)

    clipped_marker = "feature clipped at extraction boundary"

    def actual_parts(feature: dict[str, Any]) -> list[tuple[int, int]]:
        location = feature.get("location") or {}
        raw_parts = location.get("parts") if isinstance(location, dict) else None
        if raw_parts:
            parts = []
            for part in raw_parts:
                if not isinstance(part, dict):
                    continue
                start = part.get("start0")
                end = part.get("end0")
                if start is None and part.get("start") is not None:
                    start = int(part["start"]) - 1
                if end is None:
                    end = part.get("end")
                if start is not None and end is not None:
                    parts.append((int(start), int(end)))
            if parts:
                return parts
        start = feature.get("start")
        end = feature.get("end")
        if start is None or end is None:
            return []
        return [(int(start) - 1, int(end))]

    def has_machine_clip_marker(feature: dict[str, Any]) -> bool:
        qualifiers = feature.get("qualifiers") or {}
        notes = qualifiers.get("note", []) if isinstance(qualifiers, dict) else []
        if isinstance(notes, (str, bytes)):
            notes = [notes]
        return any(clipped_marker in str(note) for note in notes)

    def same_identity(left: dict[str, Any], right: dict[str, Any]) -> bool:
        return all(left.get(key) == right.get(key) for key in ("name", "type", "strand"))

    def parts_are_contained(container: dict[str, Any], fragment: dict[str, Any]) -> bool:
        container_parts = actual_parts(container)
        fragment_parts = actual_parts(fragment)
        return bool(container_parts and fragment_parts) and all(
            any(
                container_start <= fragment_start
                and fragment_end <= container_end
                for container_start, container_end in container_parts
            )
            for fragment_start, fragment_end in fragment_parts
        )

    complete_source_features = [
        candidate
        for candidate in source_complete_candidates
        if not has_machine_clip_marker(candidate)
        and any(
            same_identity(existing, candidate)
            and actual_parts(existing) == actual_parts(candidate)
            for existing in restored
        )
    ]
    cleaned = []
    for feature in restored:
        redundant = has_machine_clip_marker(feature) and any(
            same_identity(candidate, feature)
            and parts_are_contained(candidate, feature)
            for candidate in complete_source_features
        )
        if not redundant:
            cleaned.append(feature)
    return cleaned


def recipe_gibson_assembly(
    vector_linear_seq: Any = None,
    insert_template_seq: Any = None,
    insert_start: int | None = None,
    insert_end: int | None = None,
    overlap_length: int = 22,  # Standard 20-25 bp starting point
    circular_product: bool = True,
    fragments: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Execute a literature-grounded Gibson / In-Fusion overlapping assembly route.

    Follows Gibson et al. (2009 Nature Methods) and NEB NEBuilder HiFi Guidelines:
    - Selects which forward or reverse primer carries each junction homology.
    - Prepares each fragment from its complete source, using successive PCR
      steps when a complete oligo would exceed the length limit.
    - Checks complete oligo structure and reports core Tm values in the
      accepted 52–72°C range.
    - Simulates PCR and overlap assembly and emits literature citations.
    """
    # New explicit mode: every ordered fragment is defined by a complete
    # source template and target interval.  All fragments, including the
    # backbone, are PCR products before assembly.
    if fragments is not None:
        if len(fragments) < 2:
            raise ValueError("Gibson fragments mode requires at least 2 fragment specifications")
        ol = max(15, min(35, int(overlap_length)))
        source_records: list[SeqRecord] = []
        target_sequences: list[str] = []
        normalized_specs: list[dict[str, Any]] = []
        for index, spec in enumerate(fragments):
            if not isinstance(spec, dict):
                raise TypeError("Each Gibson fragment must be a mapping with template, start, and end")
            template = spec.get("template", spec.get("source"))
            start = spec.get("start", spec.get("start_0based"))
            end = spec.get("end", spec.get("end_0based"))
            if template is None or start is None or end is None:
                raise ValueError(f"Gibson fragment {index + 1} requires template, start, and end")
            record, sequence = resolve_sequence_input(template)
            start, end = int(start), int(end)
            topology = record.annotations.get("topology", "linear")
            if start < 0 or end < 0 or start >= len(sequence) or end > len(sequence):
                raise ValueError(f"Gibson fragment {index + 1} interval [{start}, {end}) is outside template")
            if end <= start and not (topology == "circular" and end < start):
                raise ValueError(f"Gibson fragment {index + 1} interval must be non-empty")
            target = _arc(sequence, start, end)
            if len(target) < 2 * 18:
                raise ValueError(f"Gibson fragment {index + 1} target is too short for two primer binding cores")
            source_records.append(record)
            target_sequences.append(target)
            normalized_specs.append({
                "id": spec.get("id", f"fragment_{index + 1}"),
                "template": _preparation_template(template, record),
                "start": start,
                "end": end,
                "topology": topology,
                "target_length": len(target),
            })

        pcr_records: list[SeqRecord] = []
        preparation: list[dict[str, Any]] = []
        primer_pairs: list[dict[str, Any]] = []
        warnings: list[str] = []
        dimer_reports: list[dict[str, Any]] = []
        prepared_fragments, homology_layout = _prepare_gibson_fragments(
            normalized_specs, source_records, target_sequences, ol, circular_product)
        for prepared in prepared_fragments:
            pcr_records.append(prepared.only_product())
            for row in prepared.analysis["preparation"]:
                designed = row["primer_design"]
                forward, reverse = row["primers"]
                forward.update(_primer_delivery(row["id"]+"_forward", designed["forward_primer"], 1))
                reverse.update(_primer_delivery(row["id"]+"_reverse", designed["reverse_primer"], -1))
                dimer_reports.append(check_primer_dimers(forward["sequence"], reverse["sequence"]).analysis)
                primer_pairs.append({"id": row["id"], "forward": forward, "reverse": reverse,
                                     "binding_core_delta_tm": designed["binding_core_delta_tm"]})
                preparation.append(row)

        assembly_res = simulate_overlap_assembly(
            fragments=pcr_records,
            min_overlap=max(12, ol - 5),
            circular=circular_product,
        )
        if circular_product:
            # Preserve the established display origin independently of which
            # oligo carries homology. Rotate the actual molecule and features.
            from core.models.construct_model import ConstructModel, feature_to_dict
            product = str(assembly_res.only_product().seq)
            target = target_sequences[0]
            starts = [i for i in range(len(product)) if (product+product).startswith(target, i)]
            if len(starts) == 1:
                default_tail = 0 if target_sequences[-1][-ol:] == target[:ol] else ol
                rotation = (starts[0]-default_tail) % len(product)
                if rotation:
                    parent = assembly_res.only_product()
                    from core.tools import rotate_sequence
                    assembly_res.products = rotate_sequence(parent,rotation).products
                assembly_res.analysis["origin_rotation_bp"] = rotation
        restored_features = _restore_unique_source_features(
            str(assembly_res.only_product().seq),
            [feature_to_dict(f, len(assembly_res.only_product())) for f in assembly_res.only_product().features],
            source_records,
            circular=circular_product,
        )
        parent = assembly_res.only_product()
        annotated = copy.deepcopy(parent)
        annotated.features = resolve_sequence_record({'sequence': str(parent.seq), 'features': restored_features}).features
        assembly_res.products = [derived_molecule(annotated, [parent], operation='restore_unique_source_features', strandedness=parent.strandedness)]
        all_primer_deltas = [pair["binding_core_delta_tm"] for pair in primer_pairs]
        quality_checks = {
            "standard_overlap_length_bp": ol,
            "all_fragments_pcr_prepared": len(pcr_records) == len(fragments) and all(row["method"] == "PCR" for row in preparation),
            "preparation_complete": len(pcr_records) == len(fragments),
            "binding_core_delta_tm_max": max(all_primer_deltas) if all_primer_deltas else 0.0,
            "delta_tm_within_standard_2C": all(delta <= 2.0 for delta in all_primer_deltas),
            "primer_dimer_safe": not any(d["high_dimer_risk"] for d in dimer_reports),
            "assembled_successfully": bool(str(assembly_res.only_product().seq)),
        }
        flat_primers = [primer for pair in primer_pairs for primer in (pair["forward"], pair["reverse"])]
        protocol_steps = [
            {"step": 1, "action": "PCR prepare each fragment in the listed step order, using actual intermediate templates for successive extensions."},
            {"step": 2, "action": "Verify actual PCR products and their annotated source features."},
            {"step": 3, "action": "Assemble the actual PCR products with Gibson / NEBuilder HiFi."},
            {"step": 4, "action": "Transform the assembly product into competent cells."},
        ]
        return RecipeResult(
            recipe_name="recipe_gibson_assembly",
            result_kind="construct",
            completeness="complete_construct",

        products=assembly_res.products,

            primers=flat_primers,
            quality_checks=quality_checks,
            warnings=warnings,
            protocol_steps=protocol_steps,
            citations=AUTHORITATIVE_SOURCES,
            details={
                "recipe": "recipe_gibson_assembly",
                "product_length": assembly_res.analysis['product_length'],
                "primers": primer_pairs,
                "preparation": preparation,
                "homology_tail_placement": ["reverse" if side else "forward" for side in homology_layout],
                "fragments": normalized_specs,
                "junctions": assembly_res.analysis.get("junctions", []),
                "quality_checks": quality_checks,
                "authoritative_sources": AUTHORITATIVE_SOURCES,
            },
        )

    # Backward-compatible API: the caller supplies a pre-linearized vector.
    # The insert still comes from a real PCR, and the preparation record makes
    # the missing vector-preparation step explicit instead of hiding it.
    if vector_linear_seq is None or insert_template_seq is None or insert_start is None or insert_end is None:
        raise ValueError("Provide fragments=[...] or the legacy vector/insert template parameters")
    vector_record, v_seq = resolve_sequence_input(vector_linear_seq)
    insert_record, _ = resolve_sequence_input(insert_template_seq)
    ol = max(15, min(35, int(overlap_length)))
    fwd_tail = v_seq[-ol:]
    rev_tail = str(Seq(v_seq[:ol]).reverse_complement())
    try:
        designed = design_overhang_primers(
            template_record_or_seq=insert_record,
            start=int(insert_start),
            end=int(insert_end),
            target_tm=60.0,
            fwd_5prime_overhang=fwd_tail,
            rev_5prime_overhang=rev_tail,
        )
    except ValueError as exc:
        if "too short" in str(exc).lower() or "cross each other" in str(exc).lower():
            raise ValueError(
                "Legacy Gibson insert target is too short for standard primer binding cores; "
                "short-target Gibson is unsupported. Provide a longer target interval or use an explicit PCR design."
            ) from exc
        raise
    fwd = designed.analysis['forward_primer']["full_sequence"]
    rev = designed.analysis['reverse_primer']["full_sequence"]
    dimer_check = check_primer_dimers(fwd, rev).analysis
    pcr_res = simulate_pcr(
        template_path_or_seq=insert_record,
        f_primer=fwd,
        r_primer=rev,
        topology=insert_record.annotations.get("topology", "linear"),
        forward_binding_core_length=designed.analysis['forward_primer'].get("binding_core_length"),
        reverse_binding_core_length=designed.analysis['reverse_primer'].get("binding_core_length"),
        forward_binding_start_0based=designed.analysis['forward_primer'].get("binding", {}).get("template_start_0based"),
        reverse_binding_start_0based=designed.analysis['reverse_primer'].get("binding", {}).get("template_start_0based"),
    )
    pcr_record = pcr_res.only_product()
    assembly_res = simulate_overlap_assembly(
        fragments=[vector_record, pcr_record],
        min_overlap=max(12, ol - 5),
        circular=circular_product,
    )
    warnings = [
        "Legacy API supplied a pre-linearized vector; its preparation is not represented as PCR. "
        "Use fragments=[{template,start,end}, ...] for a complete all-fragment preparation chain."
    ]
    if len(str(pcr_res.only_product().seq)) < 200:
        warnings.append(f"Insert amplicon is short ({len(str(pcr_res.only_product().seq))} bp < 200 bp)")
    if dimer_check["high_dimer_risk"]:
        warnings.append(f"Primer 3' complementarity risk ({dimer_check['max_3prime_complementarity']} bp)")
    pair = {
        "id": "insert",
        "forward": _primer_delivery("forward_primer", designed.analysis['forward_primer'], 1),
        "reverse": _primer_delivery("reverse_primer", designed.analysis['reverse_primer'], -1),
        "binding_core_delta_tm": designed.analysis['binding_core_delta_tm'],
        "dimer_analysis": dimer_check,
    }
    quality_checks = {
        "standard_overlap_length_bp": ol,
        "binding_core_delta_tm": designed.analysis['binding_core_delta_tm'],
        "delta_tm_within_standard_2C": designed.analysis['binding_core_delta_tm'] <= 2.0,
        "primer_dimer_safe": not dimer_check["high_dimer_risk"],
        "assembled_successfully": bool(str(assembly_res.only_product().seq)),
        "all_fragments_pcr_prepared": False,
        "preparation_complete": False,
    }
    # The legacy vector is an explicit pre-linearized input, so it is tracked
    # as a provided component rather than fabricated into a PCR row.  Every
    # preparation row below therefore has an actual primer pair and product.
    preparation = [{
        "id": "insert",
        "method": "PCR",
        "template": _preparation_template(insert_template_seq, insert_record),
        "primers": [pair["forward"], pair["reverse"]],
        "product": _pcr_product_record(pcr_res),
    }]
    return RecipeResult(
        recipe_name="recipe_gibson_assembly",
        result_kind="construct",
        completeness="complete_construct",

        products=assembly_res.products,

        primers=[pair["forward"], pair["reverse"]],
        quality_checks=quality_checks,
        warnings=warnings,
        protocol_steps=[
            {"step": 1, "action": "Amplify insert from its complete source template with designed overhang primers."},
            {"step": 2, "action": "Use the supplied pre-linearized vector."},
            {"step": 3, "action": "Assemble vector and actual PCR product with NEBuilder HiFi / Gibson master mix."},
            {"step": 4, "action": "Transform the assembly product into competent cells."},
        ],
        citations=AUTHORITATIVE_SOURCES,
        details={
            "recipe": "recipe_gibson_assembly",
            "product_length": assembly_res.analysis['product_length'],
            "primers": {
                "forward": designed.analysis['forward_primer'],
                "reverse": designed.analysis['reverse_primer'],
                "dimer_analysis": dimer_check,
            },
            "preparation": preparation,
            "provided_components": [{
                "id": "vector",
                "method": "provided",
                "template": _preparation_template(vector_linear_seq, vector_record),
                "sequence": str(vector_record.seq).upper(),
                "topology": vector_record.annotations.get("topology", "linear"),
                "features": [
                    {
                        "name": feature.qualifiers.get("label", [feature.type])[0],
                        "type": feature.type,
                    }
                    for feature in vector_record.features
                ],
            }],
            "insert_amplicon_length": len(str(pcr_res.only_product().seq)),
            "junctions": assembly_res.analysis.get("junctions", []),
            "quality_checks": quality_checks,
            "authoritative_sources": AUTHORITATIVE_SOURCES,
        },
    )
