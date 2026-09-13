# Core skill

## Development plan relationship

This spec owns lasting product decisions, constraints and open questions; stage plans own implementation steps and completion evidence. Before creating, continuing or replacing a plan, read the [development index](../docs/development-plans/README.md), the relevant plan and its predecessor's handoff. Carry each unresolved item forward explicitly, defer it with a reason, or record an accepted cancellation. A new plan does not silently reset this spec or earlier decisions.

Current integration plan: [Phase 3.1 remediation](../docs/development-plans/safety-phase-3-readability-v0.3.1.md). Capture levels, provenance and unified reading projection are implemented; replacement HTML is not. Static step 2 has project-owner approval; final-page comprehension still requires its own acceptance.

Context updated: 2026-09-13. This spec defines the DNA product and its boundaries, not a fixed architecture or a universal correctness claim. [safety-module.md](safety-module.md) owns Trace contracts; [design.md](../docs/development-plans/design.md) owns reader behavior; read the [standard framework](../docs/development-plans/evidence-trace-reader-template.md) before implementing reading structures. Static step 2 has project-owner acceptance; final HTML acceptance remains pending.

## Goal

Help molecular and synthetic biology researchers turn a design request and real source material into a correct, inspectable DNA construct and usable preparation instructions. Reduce manual design work while preserving biological intent. The product serves research and laboratory R&D beyond the team's own iGEM project.

## Current functionality and structure

The repository identifies itself as v1.0.0. The following describes implemented surfaces, not universal validation:

| Area | Current role |
|---|---|
| `SKILL.md`, `agents/openai.yaml` | Host-assistant workflow and tool guidance; the host handles natural-language reasoning. |
| `core/recipes/`, `scripts/run_recipe.py` | Seven standard routes: Gibson, restriction cloning, Golden Gate, mutagenesis, tagging, HDR donors and cloning verification. |
| `core/tools/`, `core/handlers/composite_pipeline.py`, `scripts/run_pipeline.py` | Registered inspection, sequence, feature, PCR, digestion and assembly operations; composition of multi-step designs. |
| `core/task.py`, `core/handlers/`, `core/runtime_*.py`, `scripts/run_construction_task.py` | Structured ConstructionTask planning, execution, validation and delivery. |
| `scripts/`, `planning/`, `design/`, `agent/` | Additional analysis, primer/guide design, assembly planning, orchestration and older interfaces. The keyword agent's formal construction path is deprecated. |
| `rules/`, `parts/`, `schemas/`, `references/` | Feasibility/experience rules, a parts library, data contracts and method/source guidance. |
| `tests/`, `fixtures/`, `.github/`, release scripts | Regression and workflow checks, fixtures, CI and packaging. Optional models and their licenses live in `third_party/`. |

Inputs include sequence records/files and raw DNA. Outputs include annotated GenBank and native SnapGene `.dna`, FASTA, result JSON, and task-dependent primers, source primer annotations, intermediates and preparation tables.

Recipe and ConstructionTask routes have different contracts and maturity handling. In the current task registry, `restriction_ligation` and `crispr_editing` are experimental. Their status must not be generalized to every similarly named Recipe or standalone tool.

## Evidence Trace integration

Evidence Trace records facts and evidence beside the actual design route. Design Decision Trace is its human-readable organization. It must not change DNA, execution parameters, planners, Handlers, Core validation or authoritative files. Observe each route's real results; Recipe runs must not invent a ConstructionTask history. Correct design delivery remains the primary product purpose.

One global off/observed/full collection setting applies to subsequent captures. Full adds brief public rationale in the original design response; Observed preserves supplied facts/reasons without requiring extra AI explanation. Default development level is full; release default remains open. Normal Trace failures preserve DNA execution and report incomplete capture; explicit strict policy can stop at an execution boundary without rewriting completed files. Capture level and failure policy are independent.

The reading layer must distinguish user constraints, real AI choices, program results and delivered artifacts. Captured parameters do not establish AI authorship; shared-run association does not prove a Claim. Sequence checks do not establish fluorescence, expression or biosafety. A complete record does not establish a correct or safe design. Detailed source, applicability, change and reader contracts belong in the safety spec rather than being duplicated here.

Trace input may select exact recorded context and cite actual stage results without changing the DNA task. Runtime returns retain event references; source assertions and post-hoc explanations remain separate. Log integrity, context/explanation coverage and actual design review are distinct, so an Observed record lacking extra AI rationale is not a Core failure.

## User workflow

1. Provide the biological objective and sources. Inspect full records, topology, features and available physical materials; resolve ambiguity that affects the result.
2. Express required/forbidden components and relevant constraints. Choose a standard Recipe or compose a multi-step route; structured tasks are another existing entry point.
3. Compute preparation and reactions from actual inputs. Feed each real intermediate into its next step.
4. Check the saved product against the request and reaction chain, including sequence, junctions, topology, features and complete primers where applicable.
5. Deliver usable files and concise preparation/verification information. Distinguish candidates, components, QC designs and final constructs. Current promotion interfaces require confirmation; existing user authorization need not be requested again.

## Locked decisions

These are confirmed product priorities, revisable through an explicit product decision:

- Practical design completion and correct artifacts take priority over feature counts, test counts or elaborate review systems.
- Host AI reasons about intent and strategy; sequence computation uses executable tools. The present module layout and orchestration are not locked.
- Assembly inputs must be supplied prepared material or products of an explicit preparation step. A desired sequence is not evidence of PCR amplification from the supplied template and delivered primers.
- Preserve relevant source, backbone, inserted-feature and primer annotations through transformations and export. Source annotation corrections must remain distinguishable from DNA changes.
- A component, missing check, failed run or historical success must not be presented as a newly verified complete construct.
- Broad researcher utility remains the main product goal. Safety extends that goal; it does not replace it.

## Important constraints

- Coordinate conventions differ across existing APIs. Follow each actual contract; retain strand, compound-location and circular-origin semantics.
- Biological defaults need sources and applicability. Heuristics, unavailable backends and incomplete reference searches remain explicit.
- Sequence/file validation does not establish wet-lab success, expression, whole-genome specificity or biological safety. Hash agreement establishes integrity, not biological correctness.
- Existing external-service consent and distribution/license restrictions apply. Local computation alone does not imply that the host assistant never transmits sequence data.
- Mandatory regressions must run from a clean Git checkout using tracked or generated test inputs. Private/ignored DNA fixtures require an explicit optional invocation, not an implicit local dependency; synthetic tests do not establish wet-lab function.

## Open questions

- Which real researcher workflows remain poorly served despite existing tests? What design effort does the skill actually save?
- Which duplicated planning, validation or delivery paths should be consolidated? Retain or replace them based on evidence, not architectural labels.
- How much interpretation can the host handle reliably, and where does a structured clarification materially improve results?
- Which optional backend and file-compatibility claims can be reproduced in the intended release environment?

## Acceptance criteria

- A representative real task runs through a documented public entry point and produces the requested result. Its reaction chain and saved files can be checked against independent source/target evidence.
- Relevant topology, feature locations, strands, junctions and full primers survive export/read-back. SnapGene compatibility claims use actual SnapGene evidence where claimed.
- Failure and incomplete cases report the current state accurately. Rejecting a task is not counted as successful design completion.
- A change addresses a demonstrated workflow need or reproducible defect, passes relevant regressions and preserves normal design usability. Release checks include running the packaged skill outside the checkout.
- Trace on/off A/B regression must preserve DNA sequence, topology, annotations, primers, preparation, validation semantics and authoritative artifacts for the same fixed design inputs. Injected Trace failures in normal mode must not prevent an otherwise successful DNA run. Trace status must not be reported as a biological validation or safety conclusion.

## Evidence pointers

[SKILL.md](../SKILL.md) and [Recipe reference](../references/recipes.md) describe current usage. [v1.0.0 release notes](../docs/RELEASE-v1.0.0.md) and [final audit](../docs/FINAL-RELEASE-AUDIT-20260907.md) record historical validation, including untested scope. Older README/architecture sections contain version drift; verify claims against code and fresh evidence. This context review did not rerun the biological test suite.

## Historical trace evidence

The [Phase 1 record](../docs/development-plans/safety-phase-1-trace-v0.1.md) preserves its original test counts, packaged-run evidence and limits. The current remediation plan records later capture tests and pending human reading acceptance. Historical engineering results do not establish present user comprehension.
