# Safety module

## Purpose and document ownership

**Evidence Trace 是事实与证据记录系统；Design Decision Trace 是其默认的人类可读组织方式。** It is an inspectable record of biological design by users, AI and deterministic programs. Researcher Projection is the code that organizes those facts, not a second system or fact store.

Improve researchers' ability to understand and review designs while preserving a future iGEM safety contribution. Genome Resurrection motivates distinguishing DNA presence, functional restoration and autonomy; none is established merely by a successful construct file. No safety score, safe/unsafe verdict, hidden-thought viewer or ecological prediction is provided.

This spec owns lasting Trace contracts. [Core spec](core-skill.md) owns DNA behavior; [design.md](../docs/development-plans/design.md) is the sole reader/UI guideline; [development index](../docs/development-plans/README.md) and [current plan](../docs/development-plans/safety-phase-3-readability-v0.3.1.md) own implementation status, checks and predecessor handoff. Carry unresolved items forward explicitly. Avoid duplicating UI rules across these files.

## Current implementation and selected scope

- `evidence_trace/` and entry-point wrappers capture Recipe, Pipeline and ConstructionTask facts; events, source statements, conditional links, revisions, existing hashes and artifact manifests are reusable.
- Global collection levels, decision provenance and separately appended assistance are implemented. Phase 2 applicability and Phase 3 Change Impact remain available.
- HTML still uses v0.3 Decision-centered chapters. Unified process projection, conditional sections, revised review semantics and process Mind Map are planned, not implemented. See [v0.3 handoff](../docs/development-plans/safety-phase-3-change-impact-v0.3.md).
- The GFP comparison Reader Demo has case approval, not human comprehension acceptance. GFP +3 bp remains an engineering regression. Phase 4 is paused.

## Locked design boundary

Trace observes `LLM → ConstructionTask → plan → execute → validate → finalize` and each route's actual equivalents. It changes no DNA, parameters, planner, Handler, validation rule or authoritative artifact. Keep instrumentation in wrappers rather than distributed through Handlers. No new safety core or automatic reaction reruns.

Core results alone generate Validation and Artifact facts. Preserve preparation, confirmations and delivery behavior, partial/failed runs and original errors. Normal Trace failures continue DNA work with `TRACE_INCOMPLETE`; explicit strict policy may stop at an execution boundary, without rolling back existing files. Missing Trace data is not a Core validation failure.

## Collection and attribution

| Level | Contract |
|---|---|
| Off | No new Trace; existing records remain readable. |
| Observed | Capture available inputs, choices, program results and supplied user requirements/reasons. No extra model explanation request. |
| Full | Observed plus brief public rationale for consequential choices, usually 1–2 sentences in the original design response. No separate Trace model call. |

One global setting applies to subsequent captures; each running capture keeps its initial level. New events carry `mode_at_capture`; old events without it remain unknown. Development defaults to full; release default is undecided. No conversation/session registry, per-conversation override or duplicate skill package. Configuration and compatibility details belong in [usage](../references/evidence-trace.md).

Record consequential discretionary choices, not every parameter, ordinary tool call or compliance with an explicit user constraint. A single choice may cover several parameters. Reuse user reasons rather than paraphrasing them again. Observed and Full share runtime facts; neither guarantees capture of every host action.

`actor` identifies the submitter. Reuse `decision_actor`, `decision_source` and `explanation_origin` to identify the declared chooser and explanation source. Missing attribution remains unknown; a source reference is a supplied assertion, not authenticated authorship. `decision_kind` stays extensible and never limits AI choices.

Distinguish user explanation, concurrent AI explanation, no original explanation and post-hoc assistance. Assistance is explicitly supplied, appended separately and bound to exact old revisions. It cannot replace original rationale, fill original-explanation coverage or become Validation. No automatic observer service or hidden chain-of-thought capture.

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

Sections are conditional on actual content and the user's goal. A simple delivered construction can end at its artifact. Preserve relevant failures, unresolved requirements and consequential uncertainty; do not invent review items, experiments, user intervention or explanations to fill a template. Separate capture faults, explanation coverage gaps and actionable design review items. Do not use old `explained` alone as their common signal.

The shipped renderer is deterministic. Narrative grouping cannot invent biology or causal relations; readable summaries retain exact source references. Old logs remain readable without being relabeled as fully explained. Reader wording, branch behavior, layout and examples live only in design.md.

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
