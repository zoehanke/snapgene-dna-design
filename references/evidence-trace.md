# Evidence Trace v0.3

Optional local sidecar for scientific decisions, evidence and actual program results. It does not change DNA design, decide safety, or capture hidden model reasoning. Phase 2 adds structured input-choice coverage and context comparison, not general biological interpretation. Runtime has no new package dependencies.

## Collection levels (v0.3.1 capture; reading UI still v0.3)

Evidence Trace is the fact/evidence system; Design Decision Trace is its default human-readable organization. Capture remediation is available; renderer reconstruction awaits human approval of the [static reading draft](../docs/development-plans/safety-phase-3-reading-draft.md).

One global setting applies to subsequent captures in the public Recipe, Pipeline and ConstructionTask wrappers. Development default is `full`; no settings file is created merely by reading the default. `normal/strict` remains the independent failure policy.

```text
python scripts/trace_design.py config
python scripts/trace_design.py config --set-level observed
```

Use `off`, `observed` or `full`. Settings live at `~/.snapgene-dna-design/trace.json`. `SNAPGENE_TRACE_CONFIG` can locate that single file for an isolated installation/test; it is not a conversation/session override. This task does not modify the user's installed skill or global setting.

- Off creates no new trace. Legacy `--trace`, `trace=True/False`, `--trace-dir`, `--trace-input` and strict failure policy do not override this collection setting. The boolean trace flag is accepted for old callers but no longer selects collection; use the global config command. Read/inspect/render existing logs remains available while off.
- Observed automatically records available runtime facts and preserves supplied user reasons or explanations already in the design response. It never asks the model for an extra rationale. Program context remains separate from claimed motives.
- Full includes Observed and asks the host to submit 1–2 sentences of public rationale with the original design response. No separate Trace model call. Missing explanation remains missing.
- New events record `mode_at_capture`; each running capture keeps its initial level. Global changes affect subsequent captures only. Legacy events with no recorded level/authorship remain unknown.
- Malformed/unreadable settings emit `TRACE_INCOMPLETE` and preserve DNA work in normal mode; strict stops at the entry boundary. Neither path silently claims complete capture.

For an attributed Decision add `decision_actor` (`user` or `ai`), `decision_source: {"reference": "supplied-message-or-response-reference", "excerpt": "optional relevant original text"}` and `explanation_origin` (`user_statement` or `ai_concurrent`) alongside its genuine `rationale`. `actor` still identifies the record submitter. Use `unknown` or omit attribution when unavailable. A reference is a supplied provenance assertion, not an authenticated identity or hidden reasoning transcript.

Explicitly supplied post-hoc assistance uses a separate bundle array:

```json
{"actor":"host-assistant","explanations":[{"decision_ref":"D1@1","basis_refs":["D1@1"],"text":"Only this boundary choice was recorded; its original motivation is unavailable."}]}
```

Append with the existing `record` command. Exact stored revisions are required; the supplement is always labeled `事后辅助解释`. It never changes the Decision, original rationale, original-explanation coverage or Validation. `inspect` exposes supplements and decision provenance; graph.json retains them. Their new human UI awaits the trial gate.

Coverage now separately exposes `target_match`, `matched_decision_refs`, `explanation_provenance` and `original_explanation_recorded`. Historical `status=explained` only denotes target matching plus submitted text for the old UI, not authenticated original rationale. No-rationale Observed capture is distinct from lost supplied explanation.

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

These are alternative execution routes, not a prescribed three-step biological workflow. Preserve actual task authorization. `--trace` alone uses `<out-dir>/evidence-trace`; `--trace-input choices.json` appends a bundle when starting a run. Use a new output directory per run. A trace directory represents one design task and its revisions; run association uses its current recorded decisions.

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

Document / Mind Map / Split share one state owner: selected run, Decision, node and expansion state. Document reads each Decision as Why → Evidence → Applicability → Validation → Change Impact → Output. Mind Map is a primary, full-page SVG reading mode; Split connects the map and chapter. Fixed shipped renderer code controls layout. Changes and Review are contextual reading aids, not dashboards or safety scores.

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
