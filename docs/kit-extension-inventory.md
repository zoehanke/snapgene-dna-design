# Kit extension point inventory

Snapshot: 2026-10-14, baseline `e7b1f1629e9677ff04d9428c3fb7c2fa459cf375`.
This inventory covers block K phase 1. It does not authorize the later contribution adapters, routing evaluation, packaging or frozen-candidate integration.

## Original behavior and general requirement

The Core already exposes tools, tasks, recipes, declared Pipelines, rules and validation/delivery functions. Toolkit dispatch is a project-specific list in `revival/runner.py` and `scripts/run_toolkit.py`; no external Kit manifest is discovered or loaded. A Python caller can register a tool manually, but a manifest cannot currently contribute it through a public CLI. This does not meet the requested reusable Kit interface. Reuse these existing execution contracts; add only manifest discovery, validation, loading and the missing tool adapter in this phase.

## Core extension points

“Callable” and “loadable from an external Kit” are different states. The latter column describes the baseline, before this phase's runtime.

| Point | Current public seam and actual behavior | External Kit load now? | Missing adapter / disposition |
|---|---|---|---|
| Atomic tools | [registry](../snapgene-dna-design/core/tools/registry.py): `ToolSpec`, `register_tool`, `get_tool`, signature-derived schemas, duplicate-name rejection. Actual runtime has 47 tools; old architecture's 44 is historical. | Python can register manually; no manifest/CLI loader. | Phase 1: namespaced contribution becomes an existing ToolSpec. Reuse argument/result validation and category enforcement. |
| Pipeline | [composite handler](../snapgene-dna-design/core/handlers/composite_pipeline.py), [run_step](../snapgene-dna-design/core/workflow.py), [CLI](../snapgene-dna-design/scripts/run_pipeline.py): explicit linear steps and actual typed product references. | Callers can submit steps using already registered tools. No Kit template registry. | Pipeline template contribution remains NOT_IMPLEMENTED. Do not create another executor or DSL. |
| Validation / delivery | [validation](../snapgene-dna-design/core/workflow_validation.py), [delivery](../snapgene-dna-design/core/workflow_delivery.py): `validate_candidate`, `deliver_result`; [runtime gate](../snapgene-dna-design/core/runtime_gate.py) binds real files and versions. | Callable with supported objects/requirements. No external gate declaration adapter. | Kit gate contribution remains NOT_IMPLEMENTED; no check exemption or changed biological gate. |
| Rules | [engine](../snapgene-dna-design/rules/engine.py) accepts a caller-selected user rule directory; [experience grammar](../snapgene-dna-design/rules/experience.py) validates scoped declarative rules and records diagnostics. | User rule JSON can be loaded through the existing directory parameter, not Kit contributions. | Kit rule contribution remains NOT_IMPLEMENTED. Later adapter must preserve grammar, applicability and each rule's source. |
| Task Handler | [task registry](../snapgene-dna-design/core/registry.py), [Handler map](../snapgene-dna-design/core/handlers/__init__.py), [interface](../snapgene-dna-design/core/handlers/base.py). Task kind and Handler registrations are separate; router never guesses roles. | Source-level registrations exist; no external manifest adapter. | Deferred: coordinated Handler/kind contract registration, collision and missing-field semantics. |
| Recipe | [exports](../snapgene-dna-design/core/recipes/__init__.py), [result contract](../snapgene-dna-design/core/recipes/contract.py), `get_method` in [workflow](../snapgene-dna-design/core/workflow.py). Seven families plus the point-mutagenesis alias. | Exported Python functions adapt to common steps; no external Recipe contribution API. | Deferred. Preserve RecipeResult roles, completeness, physical preparation and domain-specific search. |
| Task / result contracts | [Task](../snapgene-dna-design/core/task.py), [schemas](../snapgene-dna-design/schemas/), [ToolResult](../snapgene-dna-design/core/tools/result.py), [requirements](../snapgene-dna-design/core/requirements.py). | Existing fixed contracts are reusable. No Kit schema extension registration. | Deferred. This phase validates Kit inputs with existing jsonschema; it does not extend Task/DNA schemas. |
| References | Skill references and `provenance.py` describe sources. | Hosts can read supplied references; no machine contribution adapter. | Keep sources in Kit metadata/resources. No claim that arbitrary references become verified scientific facts. |
| Evidence Trace | [runtime](../snapgene-dna-design/evidence_trace/runtime.py): observe calls/values/files through current capture policy. | Generic facts can be observed; no Kit load receipt yet. | Phase 1: record Kit name/version/manifest hash/source at runtime loading. No new scientific relation or causal interpretation. |

`run_step` already refuses write/network/external categories with `PIPELINE_SIDE_EFFECT`. A Kit contribution must use that same check. Category declarations are not an OS sandbox and do not prove imported code is harmless.

## Actual reuse in revival/

| Kit / shared code | Reused Core seams | What it does not reuse |
|---|---|---|
| [Construct](../genome-revival-toolkit/revival/construct.py) | Task `plan`; common `run_step`; preparation/QC Recipes; `deliver_result`; file verification; format export and Trace. | It orchestrates its own project workflow, not a contributed Pipeline template or rule directory. |
| [Identity](../genome-revival-toolkit/revival/identity.py) | Direct `compare_sequences`, `simulate_pcr`, primer design and complete-pair quality; ToolResult wire serialization and Trace. | No Task Handler, Recipe, Pipeline or gate contribution. Its analytical result is not a new DNA construct requiring delivery promotion. |
| [Evidence](../genome-revival-toolkit/revival/evidence.py) | Trace observation/file hashes; common Toolkit reporting/receipt. | Counts/comparisons are project logic; it does not perform DNA construction, Task/Pipeline/Recipe or Core delivery. |
| [CRISPR](../genome-revival-toolkit/revival/crispr.py) | Direct guide/direction/vector checks; `run_step` replacement with preparation; `deliver_result`; format export and Trace. | Selection mapping is project-specific [selection.py](../genome-revival-toolkit/revival/selection.py), not an imported Core rule set. |
| [Context](../genome-revival-toolkit/revival/context.py) | Real DNA parsing, molecule versions, region extraction and file hashes. | Declared strain identity is project data, not Core-certified identity. |
| [Runner](../genome-revival-toolkit/revival/runner.py) / [reporting](../genome-revival-toolkit/revival/reporting.py) | Existing Trace capture/render/organization, wire values and Core file verification. | Kit names, request fields and scopes are hard-coded on the project side. There is no generic manifest loader. |

No Kit presently imports `rules.engine` or registers a Task Handler/Recipe. Scientific functions existing in a module are not evidence of a Kit contribution interface.

## Phase 1 pilot and compatibility boundary

Select Identity. It is a P0 supplied-region assay workflow with independent positive/negative tests in [identity tests](../tests/test_genome_revival_identity.py) and public CLI coverage in [public tests](../tests/test_genome_revival_public.py). It has no Construct preparation/delivery chain or CRISPR selection/cassette coupling. Evidence is smaller, but Identity directly covers the established P0 assay requirement.

Preserve the legacy Identity import/CLI and shared project reporting. New generic Kit loading records are tested separately from the unchanged legacy business Trace. Compatibility comparison must explicitly list volatile invocation/time/path fields; scientific values, checks, errors, file roles, DNA and report text cannot be normalized away. Original baseline outputs and failures remain outside Git.

Only the tool contribution adapter is implemented in phase 1. Pipeline, gates and rules remain unsupported contributions, with explicit diagnostics. The test-only external toy Kit is generated in a temporary directory and is never shipped.

Pilot validation found a generic seam limit: ordinary existing-file strings in step parameters are collected as DNA. The analytical tool therefore names its non-DNA project context with a local file URI, while the complete legacy entry retains its context_file argument. No sequence calculation/material collector is changed, and remote URI schemes are rejected. A later typed non-DNA input contract may replace this adapter.

One obsolete package assertion counted every nested SKILL.md as another installed Skill. The explicit new sub-Skill requirement retains one top-level installable folder and permits only manifest-defined kits/*/SKILL.md below it. The corresponding package gate/test now check that structure; original payload/hash, private-material, vendor and real-CLI checks stay unchanged. This contract correction is recorded rather than hidden by omitting the pilot from tests.

Official GitLab CI is not executed for this phase. Development GitHub CI must be bound to its actual final commit. No main or frozen candidate is changed.
