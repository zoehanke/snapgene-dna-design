# Safety module

## Purpose and document ownership

**Evidence Trace 是事实与证据记录系统；Design Decision Trace 是其默认的人类可读组织方式。** It is an inspectable record of biological design by users, AI and deterministic programs. The selected redesign produces a complete structured design process plus a separate report plan; the report presents that result rather than first inventing its research logic.

Improve researchers' ability to understand and review designs while preserving a future iGEM safety contribution. Genome Resurrection motivates distinguishing DNA presence, functional restoration and autonomy; none is established merely by a successful construct file. No safety score, safe/unsafe verdict, hidden-thought viewer or ecological prediction is provided.

This spec owns lasting Trace contracts. [Core spec](core-skill.md) owns DNA behavior; [design.md](../docs/development-plans/design.md) owns reader/UI rules; the [standard framework](../docs/development-plans/evidence-trace-reader-template.md) is the required pre-implementation structural reference for optional reading blocks, not a compulsory form; [development index](../docs/development-plans/README.md) and [current plan](../docs/development-plans/safety-phase-3-readability-v0.3.1.md) own implementation status, checks and predecessor handoff. Carry unresolved items forward explicitly. Avoid duplicating UI rules across these files.

## Current implementation and selected scope

- `evidence_trace/` and entry-point wrappers capture Recipe, Pipeline and ConstructionTask facts; events, source statements, conditional links, revisions, existing hashes and artifact manifests are reusable.
- Global collection levels, decision provenance and separately appended assistance are implemented. Phase 2 applicability and Phase 3 Change Impact remain available.
- Source/phase links, explicit per-run context, separate diagnostics and the unified reader projection are implemented. Reader steps, conditional branches, run selection and grouped review share one dataset; [mapping](../references/evidence-trace-reader-mapping.md) defines the interface. HTML still uses v0.3 Decision-centered chapters; the new Document/Map/Split renderer is not implemented. See [v0.3 handoff](../docs/development-plans/safety-phase-3-change-impact-v0.3.md).
- The GFP comparison static Reader Demo was accepted by the project owner at step 2 on 2026-09-13. No two-reader answers or timing measurements were supplied; final HTML comprehension remains unverified. GFP +3 bp remains an engineering regression. Phase 4 is paused.

## Selected three-layer redesign (not implemented)

The [r3 development design](../docs/development-plans/safety-phase-3-three-layer-design-v0.3.1.md) and [human review version](../docs/development-plans/safety-phase-3-three-layer-review-v0.3.1.md) supersede the r1 assumption that program-only projection can organize the full design logic. Current code status above remains unchanged.

- Collection preserves actual program facts, submitted statements and available source material. Missing host activity stays outside observed scope.
- The data layer combines deterministic fact/index processing with explicit host-AI or human semantic organization. Its result includes goals, stages, steps, branches, complete explanations, typed relationships, evidence references and unassigned records. Python checks references, versions, coverage and observable consistency; it does not certify scientific meaning.
- The report layer includes authored choices about emphasis, summaries and grouping. Save these as `report_plan`, optionally in the same host response as `design_process`, and bind them to the exact process version. Rendering, export and interactive viewing use fixed code without another model call.
- AI organization is real additional work with token/time cost. No independent model service is required. Full includes organization at meaningful stage/handoff boundaries; Observed does not request extra organization by default, but explicitly requested organization of existing material remains possible and is labeled as later work. Off adds no records. Existing capture settings are unchanged until implementation.
- Preserve raw design records and append organization/report-plan revisions to the same journal. `graph.json` becomes the complete machine result; hidden report detail is not deleted. New facts make old organization stale. Missing or stale organization yields an explicitly limited fact view, not a claim of complete design reasoning.
- Distinguish original statements, organized summaries and later interpretations. AI cannot author runtime Validation or file-generation facts. Structure/reference checks are not semantic proof. Complete record disposition is not proof of complete host observation.

## Core observation boundary

Trace observes `LLM → ConstructionTask → plan → execute → validate → finalize` and each route's actual equivalents. It changes no DNA, parameters, planner, Handler, validation rule or authoritative artifact. Keep instrumentation in wrappers rather than distributed through Handlers. No new safety core or automatic reaction reruns.

Core results alone generate Validation and Artifact facts. Preserve preparation, confirmations and delivery behavior, partial/failed runs and original errors. Normal Trace failures continue DNA work with `TRACE_INCOMPLETE`; explicit strict policy may stop at an execution boundary, without rolling back existing files. Missing Trace data is not a Core validation failure.

## Collection and attribution

The following table describes the implemented collection behavior. The selected redesign above adds explicit process/report organization; it is not implemented by the current capture setting alone.

| Level | Contract |
|---|---|
| Off | No new Trace; existing records remain readable. |
| Observed | Capture available inputs, choices, program results and supplied user requirements/reasons. No extra model explanation request. |
| Full | Observed plus brief public rationale for consequential choices, usually 1–2 sentences in the original design response. No separate Trace model call. |

One global setting applies to subsequent captures; each running capture keeps its initial level. New events carry `mode_at_capture`; old events without it remain unknown. Development defaults to full; release default is undecided. No conversation/session registry, per-conversation override or duplicate skill package. Configuration and compatibility details belong in [usage](../references/evidence-trace.md).

Record consequential discretionary choices, not every parameter, ordinary tool call or compliance with an explicit user constraint. A single choice may cover several parameters. Reuse user reasons rather than paraphrasing them again. Observed and Full share runtime facts; neither guarantees capture of every host action.

`actor` identifies the submitter. Reuse `decision_actor`, `decision_source` and `explanation_origin` to identify the declared chooser and explanation source. Missing attribution remains unknown; a source reference is a supplied assertion, not authenticated authorship. `decision_kind` stays extensible and never limits AI choices.

Distinguish user explanation, concurrent AI explanation, no original explanation and post-hoc assistance. Assistance is explicitly supplied, appended separately and bound to exact old revisions. It cannot replace original rationale, fill original-explanation coverage or become Validation. No automatic observer service or hidden chain-of-thought capture.

Requirements retain optional `requirement_source` with original/summary form and supplied context. User change/confirm/reject requires a source and exact affected `basis_refs`; submitter identity alone does not establish user intent. Decisions and supplements may reference exact recorded revisions or tool event IDs as declared basis, without inventing causal proof. No new conversation registry is required.

Explicit `context_refs` in the existing Trace input selects run records and retains their recorded dependencies; only selected Decisions are active. Omission keeps legacy latest-record selection, labeled as such. Stage references pair inputs, returns and failures; accepted-input observations retain their after-call phase. Runtime results bind to their returned-value event, while broad same-run associations remain distinct from a Claim-specific validation. Old logs retain unknown anchors rather than reconstructed history.

## Facts and evidence

- `events.jsonl` is the append-only, single-writer fact source. Graph, applicability/impact projections, manifests and human views are derived. Preserve old events; rebuilding never invents missing history.
- Keep Requirement, Source, Evidence Statement, Claim, Decision, Validation and Artifact distinct. `Source → Statement → Claim → Decision` separates what a source reports, what is inferred here and what is chosen. A user requirement can support a choice without a compulsory paper/Claim chain.
- Evidence links retain support/oppose/constrain/contextualize, aspect, strength, applicability, conditions and limitations. One source can support one aspect and limit another. Evidence about candidate identity does not automatically support a preparation sequence or performance claim.
- Source `verified` records verification method, scope, verifier, time and locator only. It does not verify the extracted statement, applicability or Decision. Unverified references remain unverified; model inference is labeled.
- Applicability keeps declared and computed assessments separate. Existing comparisons cover organism, strain, host/chassis, construct context, temperature, medium, assay and intended use. Retain each dimension's comparison, reasons and declared relevance scope. `direct / partial / extrapolated / unknown` are contextual assessments, not proof of transferability. Existing normalization limits remain; no general taxonomy or paper-understanding service.
- Reuse recorded task/plan/execution/artifact anchors. They identify versions, not intent or tamper-proof authorship. Same-run links are coarse associations, not proof that each check establishes every Claim or applies to every region.
- Actual execution, material and revision references determine order/dependency where known. Append time alone is not event occurrence time or causality; inputs observed after a call returns must not be presented as a later scientific decision. Retrospective explanation stays retrospective.

## Change Impact

Change remains an append-only object with ID, from_revision, to_revision, changed_field, old_value, new_value, recorded_at and scope/origin. Automatic comparison requires the same Task ID/kind or Recipe name; other baselines are explicit. Missing observation coverage stays UNKNOWN, not an invented addition/deletion.

| Judgment | Meaning |
|---|---|
| AFFECTED | Explicit dependency |
| NEEDS REVIEW | Possible dependency |
| UNAFFECTED | Explicit complete comparable scope establishes irrelevance, with no contradictory path |
| UNKNOWN | Insufficient information; missing edges are not proof of irrelevance |

Actions remain separate: REASSESS for Claim/Decision, RECHECK for evidence/applicability, RERUN recommends a program check, STALE identifies a truthful old-context record, NEEDS REVIEW signals uncertain impact. They are not safety levels. Preserve original Claims, source verification, Validation and artifacts. A newer revision is not automatically cleared by reviewing an older one.

## Reader product contract and acceptance

Human understanding outranks default display completeness while preserving underlying facts. Present sourced task context, consequential process steps and actual results. Document, Mind Map and Split share one projection and selection state. Inputs, choices, program results and artifacts remain distinguishable; ordinary logs stay in detailed records.

The selected report contract defaults to `research-report-v1`: fixed purpose/requirements, process, outcome, conditional actions and details, as defined in design.md. AI authors source-bound content and stage grouping within that format; fixed code owns top-level structure, labels and actual status. Missing data yields explicit gaps, not invented filler. This is a report constraint, not a restriction on scientific choices. The profile is not yet implemented.

Sections are conditional on actual content and the user's goal. A simple delivered construction can end at its artifact. Preserve relevant failures, unresolved requirements and consequential uncertainty; do not invent review items, experiments, user intervention or explanations to fill a template. Separate capture faults, explanation coverage gaps and actionable design review items. Do not use old `explained` alone as their common signal.

Record integrity concerns recorded events, not completeness of reasoning or user context. Missing submitted requirements/Decisions are coverage gaps; missing Full explanations are explanation gaps; a not-requested check is not failure. A user requirement can be sufficient recorded basis without a compulsory Claim. The reading layer must keep these distinctions rather than hiding a fault or manufacturing a task problem.

The shipped renderer is deterministic. Narrative grouping cannot invent biology or causal relations; readable summaries retain exact source references. Old logs remain readable without being relabeled as fully explained. Reader wording, branch behavior, layout and examples live only in design.md.

The current reader projects unique requirement/choice/program/artifact steps from existing records. These deterministic operations remain useful in the redesign; they do not alone establish complete research logic. Unmatched inputs remain program observations. Checks group by actual return; same-name generations stay distinct, candidates stay non-authoritative, ambiguous origins remain unresolved. Ordering anchors are not occurrence timestamps or causal proof.

Run selection filters steps, evidence, later assistance, change knowledge and individual review items together. General partial/unknown applicability remains evidence context rather than an automatic task failure. Explicit opposition, missing judgment basis, actual failures and change follow-up remain reviewable. Raw records and log faults stay accessible; any model interpretation belongs to an explicitly attributed organization submission, never an unrecorded renderer inference.

Before renderer/HTML reconstruction, a static case must pass human comprehension review under predeclared criteria. Case approval is distinct from reading approval; absent feedback, model self-review and browser tests cannot pass the gate. Simulated dialogue is labeled once; replayed results and new execution are distinguishable. A final executable Reader Demo must capture real program results for its run.

Engineering acceptance includes three-level A/B equivalence of DNA, topology, features, primers, preparation, validation meaning and authoritative files; normal/strict fault behavior; legacy/revision reading; simple, branched, changed and failed cases; offline/keyboard/narrow-screen interactions. Human acceptance requires understanding purpose, participant choices, evidence scope and actual checks without opening advanced records. Timing is recorded separately; no efficiency or safety benefit is claimed from test counts.

## Limits and later direction

Entry-point and known-field coverage, supplied provenance/verification receipts, single-writer logs and original-location artifact links remain limits. Preserve existing [sequence consent](../references/privacy-and-consent.md), provenance and licensing requirements. Avoid logging full conversations, credentials or raw DNA by default; host data handling remains separate.

Open questions: release default, real Full token overhead, broader source/field coverage, user effort and reliable artifact portability. Current architecture is revisable when demonstrated needs justify changes.

| Later phase | Direction, not current work |
|---|---|
| 4 | Assurance Case around existing claims, including assumptions, defeaters and mitigations |
| 5 | Conclusion Boundary: what evidence can actually establish |
| 6 | Applicable macro/laboratory framework providers |

Original engineering evidence and unresolved limits stay in the [Phase 1](../docs/development-plans/safety-phase-1-trace-v0.1.md), [Phase 2](../docs/development-plans/safety-phase-2-applicability-v0.2.md) and current plans. Historical counts do not establish present correctness or human readability.
