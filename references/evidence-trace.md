# Evidence Trace v0.1

Optional local sidecar for scientific decisions, evidence and actual program results. It does not change DNA design, decide safety, or capture hidden model reasoning. Runtime has no new package dependencies.

The skill's host workflow enables tracing for new design tasks unless the user opts out. Direct CLI/Python use remains opt-in for compatibility and on/off comparisons. Failure policy is normal by default in both cases.

## Normal use

1. Write a small JSON bundle when making consequential choices. Record user requirements, the source's reported statement, the task-specific claim and the decision's brief rationale. Do not reconstruct unrecorded reasoning after execution.
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
- Review Queue lists recorded limitations, missing evidence and failed/unknown checks. It does not make automatic applicability or safety judgments.
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
