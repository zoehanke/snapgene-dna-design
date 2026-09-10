# Safety module

## Development plan relationship

This spec owns lasting product decisions, constraints and open questions; stage plans own implementation steps and completion evidence. Before creating, continuing or replacing a plan, read the [development index](../docs/development-plans/README.md), the relevant plan and its predecessor's handoff. Carry each unresolved item forward explicitly, defer it with a reason, or record an accepted cancellation. A new plan does not silently reset this spec or earlier decisions.

Current plan: [Phase 2 Evidence Applicability & Trace Usability](../docs/development-plans/safety-phase-2-applicability-v0.2.md). Phase 1 UI/capture feedback is carried into this phase; later phases still require separate plans.


Status: Evidence Trace v0.2 implemented and engineering-validated; actual Phase 2 results and limits are recorded in its plan. Phase 1's sixteen clarifications remain the foundation. These supersede the earlier five-node model and blocking-on-initial-log-failure proposal. [Development plan](../docs/development-plans/safety-phase-1-trace-v0.1.md) records implementation details; [core-skill.md](core-skill.md) defines the main product.

## Purpose and project relationship

Extend the existing skill with useful design traceability, then evidence challenge and conclusion boundaries: **Trace → Challenge → Bound**. First improve researchers' ability to understand and review AI-assisted designs; preserve a future iGEM Safety and Security Award option through demonstrated benefit.

Genome Resurrection motivates separating sequence design, functional restoration, autonomy and ecological conclusions. Each needs different evidence. The skill remains useful beyond this project; neither its current yeast work nor a future trace establishes that genome resurrection is generally safe.

## Current implementation

- Core exposes task/plan/execution hashes, validation, component evidence and artifact manifests. Recipe paths expose different results and promotion; not every route has a ConstructionTask chain.
- Existing provenance, operation logs and preparation records are reusable foundations.
- `evidence_trace/` and `scripts/trace_design.py` implement the append-only store, conditional evidence links, revisions and offline views. Entry-point observers cover Recipe, Pipeline and ConstructionTask; Core/Handlers were not changed. Current correctness gates are not comprehensive biosafety assessment.

## Phase 2 decisions and implementation

- Default UI is a deterministic, shipped renderer: `Requirement → Decision → Claim → Validation → Artifact`, with collapsible Evidence/Applicability branches, Focus Mode and Decision-grouped Review Queue. `view.js` and `view.css` are embedded offline; `design.md` is a development reference, never a host page-generation prompt. Main-chain order is navigation, not an inferred causal proof.
- `coverage.py` extracts known consequential fields from actual accepted ConstructionTask/Pipeline inputs and resolved Recipe arguments/defaults. `design_choice_observed` is an observation event, not a Decision. Existing Phase 1 logs may derive observations from saved submitted inputs; this does not establish successful execution.
- `explained` means explicit target field/value and scope match plus a nonblank recorded rationale. Field-only or ambiguous association is `needs review`; no reliable association is `unexplained design choice`. Counts are structural coverage, not reasoning quality or a safety percentage. No post-hoc rationale is generated. Custom decision_kind remains unrestricted.
- Host workflow records genuine decisions as they occur and can run the read-only `trace_design.py coverage --design-json ...` preflight. Gaps do not gate normal DNA execution; existing data may be clarified without inventing past reasoning.
- `applicability.py` compares Statement.context with Claim.context across organism, strain, host/chassis, construct_context, temperature, medium, assay and intended_use. Each dimension retains raw values, MATCH/DIFFERENT/PARTIAL/UNKNOWN and a reason. Source verification and declared applicability are untouched; computed assessment is a separate derived object carrying contexts, scope and algorithm version.
- Default assessment considers all eight dimensions. Direct requires matching declared relevant dimensions and a comparable biological context; partial retains missing/overlapping/condition-different dimensions; organism/strain/host/construct/use differences require extrapolation; insufficient comparable biological context is unknown. A link may explicitly narrow required_dimensions, which must remain visible. This is a conservative context policy, not proof of biological transferability.
- Normalization handles case/whitespace, three explicit common species abbreviations, Celsius/Fahrenheit and declared ranges/sets. No general taxonomy, strain equivalence, paper interpretation or environmental prediction is implied. Free text/unknown formats remain Needs interpretation.
- Old events are not migrated or overwritten. Runtime/version-bound decisions and relations remain frozen per run; chain/coverage/assessments are rebuilt from facts with projection version 0.2. Normal-mode failures remain non-blocking; Core, planners, Handlers and authoritative files are unchanged.

## Locked Phase 1 decisions

- Build a read-only sidecar around `LLM → ConstructionTask → plan → execute → validate → finalize`. LLM handles understanding, creativity, comparison and decisions; Core computes and validates; Trace records and explains their provenance.
- Trace must not modify sequences, parameters, planners, Handlers, validation rules or final design files. Observe actual return values through an external wrapper such as `traced_run`; no per-Handler instrumentation, new planner or safety core.
- Record consequential choices: sources, features, promoters, boundaries, stop policy, mutations, arrangement, candidate selection and construction strategy. Ordinary file operations are outside this decision log.
- Use Requirement, Source, Evidence Statement, Claim, Decision, Validation and Artifact records. Separate `Source → Evidence Statement → Claim → Decision`: what the source reports, what is inferred for this task, and what was chosen. Task, Plan and Execution remain runtime anchors/events.
- Requirements retain their user source. Decisions carry brief external rationale, requirement links and optional extensible `decision_kind` labels, e.g. `component_selection`, `boundary_selection`, `method_selection`, `other`. Unknown labels remain usable; classification never limits decisions. Rationale is not hidden chain-of-thought.
- Evidence Statement → Claim links can express `support`, `oppose`, `constrain`, `contextualize`, with `strength`, `applicability`, `conditions`, `limitations` and the aspect addressed. Permit multiple conditional links from the same source, including different strengths and explicit coverage gaps. These are recorded assertions, not automatic verdicts.
- Validation nodes come from actual program results. Reuse existing hashes and evidence without fabricating unavailable checks.
- Append-only `events.jsonl` is the trace source of truth. Derive `graph.json`, `TRACE-MANIFEST.json` and human views from recorded events and referenced evidence.
- Default view is a Design Timeline with selectable Decision Detail and affected artifacts. Include a Review Queue and simple Evidence Graph; researchers should not need JSON.
- Default normal mode continues the DNA workflow on any Trace-only failure, including initialization, and reports `TRACE_INCOMPLETE`. Explicit strict mode may stop at an execution boundary; it cannot change results or roll back existing files.

## Trace semantics and constraints

- Source `verification_status = verified` establishes source verification only. Show verifier, method, time and scope; it does not automatically verify an extracted statement, applicability, claim or decision. Unchecked model citations remain `unverified`.
- Record applicability separately as `direct`, `partial`, `extrapolated` or `unknown`, with declarer and context. Human declarations are supported in v0.1; automatic assessment belongs to Phase 2. Label model inference explicitly.
- Phase 1 Claim is a task-specific statement to trace, not an evaluated safety claim. Phase 4 builds Assurance Cases around these existing claims, adding assumptions, defeaters, mitigations and structured argumentation.
- Link decisions to actual runs, revisions, relevant source/step/parameter and affected artifacts where available. Task-level association alone is not a proven causal link to a sequence region.
- Hashes anchor recorded versions. They do not authenticate model intent or prevent a privileged actor rewriting local files. Coverage includes submitted decisions and instrumented runs, not every host action.
- Display “Trace integrity: complete” or “记录完整性：完整” only for record completeness within declared coverage. Evidence gaps, source verification and biological validation stay separate; complete never means safe or sufficient evidence.
- Preserve preparation, validation, confirmation and delivery behavior. Record partial/failed runs honestly; do not manufacture stages or re-execute reactions for logging.
- Preserve sequence-upload consent, provenance and licensing. Avoid copying full sequences, credentials or entire conversations into events by default.

## Phase 1 acceptance criteria

- From each final construct in a traced run, find recorded requirements, key decisions, evidence, actual validation and file/version anchors. Missing decisions or unavailable stages are explicit.
- First demo includes a user requirement, at least two consequential AI decisions, at least one paper/database source, an actual program Validation, one design revision during the task and a final authoritative artifact. The revision retains both histories and is not an automatic Change Impact feature.
- Cover normal Recipe and Pipeline/ConstructionTask workflows without requiring researchers to rebuild tasks for tracing. Preserve route-specific semantics.
- Timeline selection opens rationale, evidence, declared applicability and affected outputs. Review Queue exposes explicit gaps/conflicts, not an automated safety judgment.
- Rebuilding derived views preserves recorded content and relationships. Failure/retry and decision revision retain history and correct run associations.
- Trace on/off A/B regression preserves DNA, topology, annotations, primers, validation semantics and authoritative artifacts. Trace failure injection verifies normal-mode continuation and explicit strict-mode stopping; Core failures still follow Core behavior.
- Relevant regression, file read-back, offline view and packaged-entry checks pass; users can review a decision without reading JSON. Repeated conditional evidence links retain their distinct aspects, strengths and limitations.
- Trace completion alone does not establish comprehensive reasoning capture, tamper-proof audit, ecological prediction or biosafety improvement.

## Later direction, not Phase 1 requirements

| Phase | Intended capability |
|---|---|
| 2: Evidence Applicability | Assess organism, host, context and extrapolation; distinguish direct, partial, extrapolated and unknown applicability. |
| 3: Change Impact | Identify affected decisions/evidence/checks after changes in host, components, sequence, use, environment or objective. |
| 4: Assurance Case | Build structured arguments around existing claims; add assumptions, defeaters and mitigations, evaluating relevant SynBioTrace ideas. |
| 5: Conclusion Boundary | Show supported conclusions and missing evidence, including limits on organism/environment-level claims. |
| 6: Framework Providers | Integrate applicable guidance for laboratory, autonomy, environmental or extinct-species-proxy contexts. |

Dangerous-sequence screening may later supply Evidence. Phase 1 excludes risk scoring, automatic safe/unsafe decisions, ecological prediction, ethical adjudication, complex safety cases and reports detached from actual events. Future providers are candidates, not implemented integrations.

## Open implementation choices

- Quantified user review effort and further host ergonomics after the Phase 2 changes. The skill enables Trace for new designs unless opted out; direct CLI/Python activation remains optional. Normal failure policy is default. See [usage](../references/evidence-trace.md).
- Broader source verification and semantic context extraction without mandatory network retrieval; capture coverage beyond the recognized structured fields.
- The Q3-derived GFP revision demo meets the engineering demonstration minimum. User trial feedback and later comparisons establishing safety benefit remain outstanding.

Earlier permission-control and standalone project-review proposals are not the active plan. Alternative implementations remain eligible if they preserve these outcomes and responsibility boundaries.

## Phase 1 evidence and remaining limits

Real Recipe, Pipeline and ConstructionTask on/off runs preserve native DNA/GenBank/FASTA bytes. The full suite ran 750 tests with real Primer3 enabled: 743 passed, 7 skipped; the final trace-only repair also passed 15 focused tests. Browser interactions and mobile layout were checked. Counts are not additive. Evidence locations and the final packaged-run result belong to the [phase plan](../docs/development-plans/safety-phase-1-trace-v0.1.md). Single-writer logs, supplied source-verification receipts, original-location artifact links and entry-point-only coverage remain explicit limits. No user-efficiency or biosafety improvement is claimed before user feedback and suitable evaluation.
