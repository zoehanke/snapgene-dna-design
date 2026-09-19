# Evidence Trace v0.3.1

Optional local sidecar for scientific decisions, evidence and actual program results. It does not change DNA design, decide safety, or capture hidden model reasoning. Phase 2 adds structured input-choice coverage and context comparison, not general biological interpretation. Runtime has no new package dependencies.

## Collection levels

Evidence Trace records facts and evidence; Design Decision Trace is their human-readable organization. The host submits a structured process; code validates references and versions and renders the saved result. Without current organization, HTML explicitly shows a limited factual view. The renderer never invents a research story or calls a model.

One global setting applies to subsequent captures in the public Recipe, Pipeline and ConstructionTask wrappers. Development default is `full`; no settings file is created merely by reading the default. `normal/strict` remains the independent failure policy.

```text
python scripts/trace_design.py config
python scripts/trace_design.py config --set-level observed
```

Use `off`, `observed` or `full`. Settings live at `~/.snapgene-dna-design/trace.json`. `SNAPGENE_TRACE_CONFIG` can locate that single file for an isolated installation/test; it is not a conversation/session override. This task does not modify the user's installed skill or global setting.

- Off creates no new trace. Legacy `--trace`, `trace=True/False`, `--trace-dir`, `--trace-input` and strict failure policy do not override this collection setting. The boolean trace flag is accepted for old callers but no longer selects collection; use the global config command. Read/inspect/render existing logs remains available while off.
- Observed automatically records available runtime facts and preserves supplied user reasons or explanations already in the design response. It never asks the model for an extra rationale. Program context remains separate from claimed motives.
- Full includes Observed and asks the host to submit brief public rationale with the original design response. At stage/handoff boundaries the host also submits process organization and optional report arrangement; these may share one response but still cost tokens/time. Missing original explanation remains missing.
- New events record `mode_at_capture`; each running capture keeps its initial level. Global changes affect subsequent captures only. Legacy events with no recorded level/authorship remain unknown.
- Malformed/unreadable settings emit `TRACE_INCOMPLETE` and preserve DNA work in normal mode; strict stops at the entry boundary. Neither path silently claims complete capture.

For an attributed Decision add `decision_actor` (`user` or `ai`), `decision_source: {"reference": "supplied-message-or-response-reference", "excerpt": "optional relevant original text"}` and `explanation_origin` (`user_statement` or `ai_concurrent`) alongside its genuine `rationale`. `actor` still identifies the record submitter. Use `unknown` or omit attribution when unavailable. A reference is a supplied provenance assertion, not an authenticated identity or hidden reasoning transcript.

Explicitly supplied post-hoc assistance uses a separate bundle array:

```json
{"actor":"host-assistant","explanations":[{"decision_ref":"D1@1","basis_refs":["D1@1"],"text":"Only this boundary choice was recorded; its original motivation is unavailable."}]}
```

Append with the existing `record` command. The target Decision must name an exact revision; basis_refs can name exact existing node revisions or event IDs. The supplement is always labeled `事后辅助解释`. It never changes the Decision, original rationale, original-explanation coverage or Validation. `inspect` exposes supplements and provenance; graph.json retains them. They appear only beside the corresponding recorded choice and remain labeled as later assistance.

Coverage now separately exposes `target_match`, `matched_decision_refs`, `explanation_provenance` and `original_explanation_recorded`. Historical `status=explained` only denotes target matching plus submitted text for the old UI, not authenticated original rationale. No-rationale Observed capture is distinct from lost supplied explanation.

## Source, phase and run scope (Phase 3.1 step 3)

Requirements can retain a real user source and context without changing ConstructionTask or Recipe inputs:

```json
{"actor":"host-assistant","nodes":[{
  "id":"R1","kind":"requirement","text":"保留原骨架",
  "requirement_source":{"reference":"user-message-1","form":"verbatim","excerpt":"保留原骨架"},
  "context":{"research_question":"比较候选","task_goal":"生成所需构建"}
}]}
```

`requirement_source.form` is verbatim, summary or unknown; a supplied verbatim excerpt must equal the recorded text. Source references are declarations, not authenticated user identity. No source means unknown even if `actor` says user. Context retains only supplied background; programs do not invent it.

`request_action` is an extensible label, default request. For change/confirm/reject, provide `requirement_source` and nonempty `basis_refs` identifying the affected exact node revisions or existing event IDs. New requests may use new IDs; revisions of one requirement retain old text. Confirmation/rejection describes a recorded user act, not permission for Trace to control Core execution.

Decisions may also provide `basis_refs` to the exact records or tool events used as their basis. These become `basis_links`, separate from biological evidence relations. They declare association, not proof of scientific causality. A reference to submitted input is not evidence of successful execution. Unknown/future references and logical IDs without revisions are rejected by the recording interface; existing reference fields retain their original semantics.

When multiple alternatives or old versions share a trace, pass an explicit run context using the existing `--trace-input scope.json`:

```json
{"context_refs":["D1@1"]}
```

The named records must already exist (or be recorded by the same input bundle). Their existing requirement/evidence dependencies are retained; only explicitly selected Decisions become active run decision_refs. An empty list intentionally selects none. Omitting context_refs preserves latest-record selection for existing callers; run_started identifies explicit versus latest_records selection. Selection is only Trace metadata and does not rewrite execution parameters. Normal-mode scope errors preserve DNA work with incomplete Trace; strict retains its original stopping behavior.

New stage_started events identify a call. stage_completed, stage_failed and accepted input observations carry its `stage_ref`; projected stages retain event ID, append sequence and recording time. `observation_phase=accepted_inputs_after_call` means parameters were observed after return, not chosen at that time. Standalone value observations and old records may lack a call reference; this stays unknown rather than being guessed.

Runtime Validation and Artifact nodes carry `result_event_ref` to the actual returned-value event in their run. Their Decision/validation associations are explicitly same_run, not per-Claim or per-region proof. Exact Core result data and existing anchors remain unchanged. Rendering a later run does not relabel earlier checks.

The graph and `inspect` separate:

- `issues` / integrity: damaged or unresolved recorded data, Trace faults, unfinished runs.
- `coverage_gaps`: absent submitted requirements/decisions or missing recorded basis; not a log failure.
- `explanation_gaps`: missing original explanations when expected; assistance does not fill them.
- `association_gaps` in chain views: ambiguous/unmatched target links; separate from missing rationale.
- `review_queue`: actual check failures/unknown results and recorded evidence questions. Not-requested checks and lack of a compulsory Claim are not automatic failures.

An intact event log can therefore be complete while coverage is limited. A Decision grounded in a user requirement does not need a fabricated paper/Claim chain. `target_matched` and `original_explanation_recorded` counts remain distinct from review status. The current v0.3 UI still has legacy layouts. The reader projection now consumes these fields; see the [mapping and reader CLI](evidence-trace-reader-mapping.md). Its Review groups differ from legacy review_queue: ordinary applicability limits remain branches, while concrete failures, opposition, missing judgment basis and change follow-up remain review items.

## Normal use

1. Check the global level, then submit available user requirements, source statements, task claims and consequential choices. Preserve existing reasons in Observed; include brief concurrent public rationale in Full. Later assistance must use the separate supplement contract above.
2. Append through `trace_design.py record`. Reusing a logical record ID creates a revision; old records and run references remain intact. References must exist when recorded, so create sources/requirements before their dependents.
3. Run the normal Recipe, Pipeline or ConstructionTask command with the same `--trace-dir`. Program validation and files are recorded automatically. Open `index.html` printed to stderr.

```text
python scripts/trace_design.py record --trace-dir work/evidence-trace --input choices.json
python scripts/run_recipe.py --recipe <recipe> --params-json params.json --out-dir work/run-1 --finalize --confirmed --trace-dir work/evidence-trace
python scripts/run_pipeline.py --pipeline pipeline.json --out-dir work/run-2 --confirmed --trace-dir work/evidence-trace
python scripts/run_construction_task.py --task-json task.json --out-dir work/run-3 --trace-dir work/evidence-trace
```

These are alternative execution routes, not a prescribed three-step biological workflow. Preserve actual task authorization. `--trace` alone uses `<out-dir>/evidence-trace`; `--trace-input choices.json` appends a bundle and can select its recorded context. Use a new output directory per run. A trace directory represents one design task and its revisions; run association uses explicit context when supplied, otherwise current recorded decisions.

## Small bundle

```json
{
  "actor": "host-assistant",
  "nodes": [
    {"id": "R1", "kind": "requirement", "text": "Preserve the backbone while preparing the requested insert."},
    {"id": "S1", "kind": "source", "source_type": "user-material", "title": "Provided source annotation", "verification_status": "unverified"},
    {"id": "E1", "kind": "statement", "source_id": "S1", "text": "The supplied annotation identifies the insert boundaries.", "locator": "Feature label in the source record"},
    {"id": "C1", "kind": "claim", "text": "These boundaries are the proposed target for this task."},
    {"id": "D1", "kind": "decision", "text": "Use the identified insert boundaries", "rationale": "Preserve the remaining backbone and calculate preparation from the complete source.", "decision_kind": "boundary_selection", "responds_to": ["R1"], "claim_ids": ["C1"], "targets": {"parameter": "insert_start/insert_end"}}
  ],
  "links": [
    {"statement_id": "E1", "claim_id": "C1", "relation": "support", "aspect": "boundary choice", "strength": "provisional", "applicability": "partial", "conditions": ["source annotation is correct"], "limitations": ["annotation has not been independently checked"]}
  ]
}
```

Replace the example with actual observations. `decision_kind` accepts custom labels. Links allow multiple relations/aspects and conditional strengths; gaps remain unknown rather than forced into a score. Claim records are statements to trace, not Assurance Cases.

Sources can include `doi`, `pmid`, `url`, context and limitations. `verified` requires a `verification` object with `verifier`, `method`, `checked_at`, `locator`, `scope`. This records a supplied external/manual check; Trace does not fetch papers or independently authenticate the receipt. Verifying source identity does not verify its statement, applicability or the decision. Keep model inferences explicitly typed `model-inference`.

The recording interface rejects user-supplied `validation` and `artifact` nodes. Those are reserved for observed program outputs; this is an application contract, not isolation against arbitrary local code.

## Views and failures

- Timeline shows requirements, decisions, checks and representative final files. Detail links reveal source statements, claims, conditions, limitations, revisions and affected artifacts. Artifact/Validation associations are run-level, not a claim that every check applies to every file or sequence region.
- Review Queue lists recorded limitations, missing evidence and failed/unknown checks. Phase 2 adds conservative structured-context comparisons, while keeping their scope and uncertainty visible; it makes no safety judgment.
- Run selection freezes the recorded decision versions and evidence relationships available for that run. “全部历史与修订” shows the complete recorded history.
- Default `normal` mode continues DNA work on Trace-only failures and emits `TRACE_INCOMPLETE` to stderr. `--trace-mode strict` explicitly enables stopping at observation boundaries. Existing Core failures keep their own behavior; completed files are never rolled back by Trace.
- `Trace integrity: complete` means record completeness within declared coverage. It does not mean every decision was captured, evidence is sufficient, the design is safe or wet-lab success is established.

Python callers can pass `trace=True`, `trace_dir=...`, `trace_input=...`, `trace_mode="normal"` to `run_recipe_cli` and `execute_agent_pipeline`. Their original result dictionaries are unchanged; the sidecar and stderr carry trace information. Core and standalone atomic calls outside these entry points are not automatically traced.

## Rebuild and portability

```text
python scripts/trace_design.py inspect --trace-dir work/evidence-trace
python scripts/trace_design.py render --trace-dir work/evidence-trace
```

`events.jsonl` is append-only and single-writer. `graph.json`, `TRACE-MANIFEST.json` and HTML are derived. A damaged log is reported as incomplete and cannot be silently appended. Concurrent writers to one trace directory are unsupported. Artifact paths include their original absolute and run-relative locations; after moving files, original links may need locating manually. Hashes still identify recorded contents, not authorship or tamper-proof storage.

No sequence uploads occur in Trace. Runtime summaries omit long raw DNA strings and secret fields, while recording source-file hashes and existing result references. User-authored text may contain sensitive information; review it before sharing the directory. The host assistant's own data handling is separate.

## Real demonstration

```text
python scripts/demo_evidence_trace.py --template <complete-pBP-eGFP.gb> --out-dir <new-demo-directory>
```

Uses the existing Q3-derived full-template mutagenesis task: Y66H, a recorded design revision adding Y145F, and a separate actual PCR Pipeline. Generates authoritative artifacts, source primer annotations, a timeline and on/off byte comparisons. Supply the unchanged 2808 bp template described in `tests/data/README.md`; source material is not bundled into the runtime package. Source-verification receipts are historical checks from 2026-09-10, not fresh network verification by the demo. No fluorescence performance or safety benefit is claimed.

## Phase 2: capture coverage and applicability

Before execution, check the current task/pipeline/recipe parameter file without changing it:

```text
python scripts/trace_design.py coverage --trace-dir work/evidence-trace --design-json params.json
```

Use the same working directory as the execution command. Preflight sees explicit JSON fields; runtime observations also include resolved Recipe defaults. Known source, boundary, orientation, method, mutation, component/order, topology and selected parameter fields are observed. Ordinary analysis helpers are excluded. Unrecognized fields and internal heuristic choices are outside this coverage; zero observations means unknown coverage.

For precise association use targets such as `{"start_0based":198,"end_0based":201,"alt_seq":"CAT","method":"inverse_pcr"}` or `{"step_id":"pcr","parameter":"start","value":6}`. Field-only or ambiguous scope is not an exact target match. Missing original explanation is reported separately from a match. Matching does not validate the quality or truth of rationale. No record is generated to patch missing model reasoning.

Contexts belong separately to the source Statement and task Claim. Supported keys are `organism`, `strain`, `host` (or `chassis`), `construct_context`, `temperature`, `medium`, `assay`, `intended_use`. Temperature accepts Celsius numbers, strings such as `30 C`/`86 F`, or explicit `{min,max,unit}` ranges. Categorical lists mean declared sets; partial overlap stays partial. Missing context is unknown, not a guessed default. Only E. coli, S. cerevisiae and S. eubayanus have explicit abbreviation normalization; this is not a taxonomy resolver.

Computed assessments keep raw contexts, every dimension's result/reason, the required dimensions and `structured-context-v0.2.0`. Default scope is all eight dimensions; a link's explicit `required_dimensions` narrows the comparison, not the biological claim. Source verification, declared applicability and computed assessment are displayed separately. A different host/strain/use yields an extrapolation warning, not an unsafe verdict.

The default renderer shows the five-stage reading spine and folds Evidence/Applicability into relation groups with two-item previews. Focus Mode narrows the selected Decision/Claim/Evidence branch. Review groups issues by Decision; observations with no Decision are grouped separately by actual input subject. Advanced Graph retains the scoped original relations. Empty or not-requested program checks are not presented as failures.

## Phase 3: Living Evidence Document and Change Impact

Document / Mind Map / Split share the selected process step and expansion state. Steps come from the saved organization and may be requirements, choices, program results or artifacts; no fixed count or compulsory AI-choice summary is inserted. The fixed renderer shows context, process, actual files/checks, conditional review and detailed sources. Changes and Review remain contextual aids, not safety scores.

Changes are append-only records carrying ID, from_revision, to_revision, changed_field, old_value, new_value, presence flags and recorded_at. Record context/targets/scientific-statement revisions are captured when submitted. Accepted inputs and recorded product sequence/topology anchors are compared automatically only for the same Task ID/kind or the same Recipe name. No new sequence computation is introduced. Comparisons are recorded differences, not proof that an earlier scientific conclusion was wrong.

For another baseline pair, explicitly compare existing runs:

```text
python scripts/trace_design.py compare --trace-dir work/evidence-trace --from-run <earlier-run-id> --to-run <later-run-id>
```

Repeating the same pair does not duplicate Changes. Earlier logs are not backfilled on render. A missing observation differs from an absent field: incomplete observation coverage produces UNKNOWN, not an invented addition/deletion. All original records and program results remain intact.

Impacts expose separate judgment and actions. AFFECTED requires an explicit dependency; broad run-level edges produce NEEDS REVIEW. Missing relations yield UNKNOWN. UNAFFECTED requires a declared complete, comparable dependency range with no contradictory path. Optional `depends_on_fields` names fields/categories; `dependency_scope_complete` asserts completeness within the recorded baseline, not universal scientific independence. Program-produced validation records have limited known dependency fields and do not assert completeness.

REASSESS asks to reconsider a Claim/Decision, RECHECK asks to inspect Evidence/Applicability, RERUN recommends repeating a program check, STALE identifies an old-context record, and NEEDS REVIEW signals uncertain impact. Recommendations do not run tools, change PASS to FAIL, gate DNA design or mark a newer revision automatically resolved.

To replay the full-template PCR/context revision demonstration:

```text
python scripts/demo_evidence_trace_phase3.py --template <complete-pBP-eGFP.gb> --out-dir <new-directory>
```

The demo compares Trace on/off native files and primer tables for both PCR boundaries. Its context and purpose are explicitly authored demonstration inputs; it makes no expression or safety claim. Independent 5/15/30-second user timing remains a UX target, not a result inferred from browser tests.

## Complete process and report submission

One append-only `events.jsonl` stores observations, declarations, organization revisions and report plans. `graph.json` is a rebuildable `design-process-v1` result containing complete source records, typed fact relationships, an authored `design_process`, its `report_plan`, coverage and findings. A single nonblocking writer lock protects each active run; normal contention continues the DNA work with incomplete capture, strict contention stops before the call.

### Capture material and final files

`observe --input observation.json` accepts one object or a list. `local_text` uses `path`, optional inclusive 1-based `start_line`/`end_line`, and optional `source_uri`; `submitted_text` uses `text`. Optional `declared_role` and `declared_occurred_at` remain assertions. The returned event ID can be cited in `basis_refs` or a supplied source reference. Exact quoted requirements with `form: verbatim` are checked against a referenced material observation; this proves text occurrence, not authorship or scientific support. Existing sequence/secret omission policy still applies.

`handoff --input files.json` accepts `{"files":[{"path":"<final file>","purpose":"<intended use>"}]}`. Results are `linked`, `untraced`, `missing`, `changed` or `ambiguous`. Linking requires a recorded successful generation/modification of the same content. Merely finding an unchanged file does not fabricate its history. The check does not promote DNA files.

The four file CLIs support `--trace-dir`, `--trace-input`, `--trace-mode` alongside their original arguments. Inspection does not start a new trace unless a directory is supplied. Annotation preserves add/remove/replace/clear semantics; conversion preserves per-file errors; bundle export remains preview. Original paths, content versions and failed-call residuals remain distinguishable. Recipe candidates are captured before a later delivery gate can reject promotion.

### Host workflow

```text
python scripts/trace_design.py observe --trace-dir work/trace --input observations.json
python scripts/trace_design.py handoff --trace-dir work/trace --input final-files.json
python scripts/trace_design.py inspect --trace-dir work/trace --data
python scripts/trace_design.py organize --trace-dir work/trace --input organization.json
python scripts/trace_design.py render --trace-dir work/trace --format both
```

Use the exact `trace_id` and `through_sequence` returned by inspect. Read relevant originals before authoring. Minimal organization packet, with snapshot values and record keys replaced by real ones:

```json
{
  "schema_version": "trace-organization-v1",
  "id": "main",
  "basis": {"trace_id": "<returned trace_id>", "through_sequence": 1},
  "design_process": {
    "stages": [{"id": "purpose", "title": "任务要求", "purpose": "明确本次目标", "step_ids": ["request"], "source_refs": ["R1@1"]}],
    "steps": {"request": {"kind": "requirement", "title": "本次目标", "content": "<faithful account of R1>", "source_refs": ["R1@1"]}},
    "relations": [], "paths": [], "unresolved": [], "detail_refs": []
  },
  "report_plan": {"profile": "research-report-v1", "title": "<task title>", "sections": []}
}
```

`steps` is an ID mapping; the other process collections are lists. Every stage needs a purpose and referenced steps. Add steps according to the actual task, not a fixed six-step template. `kind` is requirement/choice/program_result/artifact. Program steps and artifacts must cite actual returned events/records; no submitted status or Validation is accepted. Plain requirements cannot be relabeled as choices. Optional step fields: `title`, `input_refs`, `outcome_refs`, `reason`, `limitations`. A reason uses `text`, `source_refs`, and `origin`: `original_statement` (exact recorded text), `organized_summary`, `later_interpretation`, or `unknown`. Limitations use `text` and `source_refs`.

Optional stage `branches` contain `id`, `label`, `step_ids` and `source_refs`. `relations` use `id`, `from`, `to`, `kind`, `meaning`, `source_refs`; allowed semantic kinds are responds_to, declared_reason_for_change, supports, opposes, constrains, contextualizes, grouped_with, part_of, revises_plan. `fact_relation_ids` may cite existing program relationships but cannot create new ones. `paths` contain `id`, `label`, `step_ids`, `source_refs`, `order_kind` (logical_process/planned/recorded_order). Recorded order requires comparable journal anchors and does not prove scientific causality. `unresolved` items contain `id`, `text`, `step_refs`, `source_refs`. Preserve remaining relevant records in `detail_refs`; unassigned records remain accessible and visible as coverage gaps.

The report profile is fixed. `context` may supply `text` and `source_refs`. `sections` group process steps with `id`, `title`, `step_refs`, `source_refs` and optional `summary`/`unresolved_refs`; they cannot replace the report's top-level chapters. `diagram` may provide `reading_order`, `relation_refs`, `short_labels`. `default_expanded_refs` and `detail_refs` influence disclosure, never erase important failures. Titles/summaries are authored statements, not program-certified science. HTML text is escaped.

`report-plan --process-ref main@1 --input plan.json` revises only the arrangement of that exact process. The returned version is appended. New factual events make earlier organization `stale`; organization/report-only events do not. A later submission about an older snapshot cannot displace a newer basis. Off rejects new capture/organization by returning `recorded:false`, but existing traces remain readable. Observed can be organized on explicit request without relabeling the new writing as contemporaneous reasoning.

`reader` returns the full machine result. `--run-id` adds a scoped `focused_reader` without removing the full supporting history; `--handoff-id` focuses an exact file-list observation. They are mutually exclusive. `--through-sequence` selects an event prefix; `--process-ref` selects an organization version whose basis fits that prefix. Historical facts may be described by a later-authored organization of exactly those facts, whose author/time remain in `organization_history`. The renderer does not rewrite a summary to fit a filter.

`render --format html|markdown|both` defaults to both and always rebuilds graph/manifest from the journal. HTML and Markdown share the saved process, actual checks, limitations and review. Exact raw facts remain in graph/journal; absent/stale organization yields an explicitly limited factual report. The journal alone cannot capture inaccessible host searches or prove the faithfulness of a scientific interpretation.
