# Kit contract and how to add a Kit

A Kit is a local sub-Skill and a manifest-defined contribution to the DNA Core. It is not an independent DNA engine or a promise of compatibility with arbitrary third-party code. The installed runtime must support the manifest's Kit API version; a numeric Core version range alone does not make an older runtime acquire that API.

## Layout and responsibility

```text
kits/example/
  SKILL.md
  kit.json
  README.md
  scripts/run.py
  scripts/tools.py
  rules/                 # sourced domain guidance, when applicable
  examples/              # redistributable or generated inputs
  tests/                 # independent positive/negative checks
```

SKILL.md describes when the host should select the Kit and the supported scientific scope. kit.json owns machine fields. Shared domain context/reporting code belongs on the Kit side; the Core knows only this interface. Existing DNA algorithms remain in Core.

A complete Skill distribution assembles Core runtime code and Kits at build time, from the same source. Individual-Kit packaging is outside this phase.

## Manifest fields

Executable shapes are [kit-v1](../schemas/kit-v1.json) for the original tool-only contract and [kit-v2](../schemas/kit-v2.json) for tools, Pipeline templates, gates and rules. JSON text uses UTF-8. No user DNA, personal absolute path or credentials belong in a committed manifest/example.

| Field | Meaning |
|---|---|
| schema_version | `kit-v1` or `kit-v2`; unknown versions are rejected. v1 retains its original tool-only behavior. |
| name / version | Local stable identifier and numeric `major.minor.patch` Kit version. |
| core_version | `minimum` inclusive and `maximum_exclusive`; numeric stable three-part Core versions, with minimum less than maximum. No implicit wildcard/prerelease rules. |
| input_schema | Existing Draft 7 JSON Schema, describing an object. Unknown fields should have an explicit policy. |
| input_example | An object satisfying input_schema. Prefer file placeholders or construction-based synthetic data. |
| entrypoint | Kit-relative Python file and module-level function, e.g. `scripts/run.py:run`; the function accepts `(inputs, out_dir)` and returns a JSON object. Non-JSON values, non-string object keys and nonfinite numbers receive KIT_RESULT_INVALID. Paths stay inside the Kit. |
| outputs | `contract: json-object`, plus `files`, a list of declared relative file names. This declaration does not itself check their existence, validate DNA or authorize delivery; the application owns actual file roles and verification. |
| contributions | Rows with `target`, local `name`, `content`, `source` and `description`. Sources explain where the rule/capability comes from; they are not automatic verification. |
| metadata | Opaque application-owned declaration. Core does not interpret project-specific fields or register project names. |

For `target: tools`, content contains an entrypoint, a side-effect category and parameters_schema. The effective name is `kit.<Kit-name>.<tool-name>`. Existing ToolSpec checks signature, aliases, parameters and ToolResult; the existing run_step gate rejects write/network/external categories. Imported Python is not sandboxed, and an inaccurate category cannot make unsafe code safe.

v2 adds three typed adapters into existing seams:

| target | content and execution boundary |
|---|---|
| pipeline | `steps` is the existing linear `step_id/tool/params` list; `inputs_schema` validates host-supplied inputs; optional `output_step` uses the existing product selector. Effective ToolSpec name is `kit.<name>.pipeline.<local-name>`. Existing composite Pipeline executes it, including the original side-effect gate. Conditions remain Kit Python. |
| gates | `entrypoint` returns current-version scoped check rows. `required_scopes` supplies scope/error_code/message. Missing execution, missing scopes or failed checks block a successful Kit result. Active Kit requirements are added to candidate validation; original Core judgments are retained. |
| rules | `path` names UTF-8 JSON in the existing experience-rule grammar; `fields` explicitly declares extra local context fields. Every row needs a nonblank source type and description or URL. Evaluation uses the original rule engine and restores local fields afterwards. |

Optional gate `acceptances` require an explicit Kit-owned scope, nonblank source and reason. A failed row must bind the actual input identifier/version before receiving effective status ACCEPTED_BY_KIT_RULE. Output and Trace retain its raw FAILED status, source, reason and notice “按 Kit 规则豁免”. This cannot accept original Core inherited diagnoses or clear Core errors. An input-template annotation error can therefore still prevent formal delivery. This phase demonstrates acceptance with a temporary external toy only.

Handler, Recipe, data-contract and reference adapters remain **NOT_IMPLEMENTED**. Established conditional applications may keep their Kit Python workflows rather than adopting a Pipeline template.

## Extension-point inventory

The source repository's `docs/kit-extension-inventory.md` retains the pre-runtime inventory and phase-by-phase dispositions. This table is the current machine-interface boundary:

| Existing seam | External declaration supported here | Retained constraint |
|---|---|---|
| ToolSpec registry | v1/v2 tools | Original signature/schema/ToolResult and side-effect gate. |
| Composite Pipeline | v2 linear template | Existing reference resolution and executor; no branching syntax. |
| Candidate validation / delivery | v2 required Kit checks | Additive selected-Kit scope; original Core judgments stay authoritative. |
| Experience rules | v2 sourced rows and explicit context fields | Original triggers/operators/actions/scope grammar, temporary field extension. |
| Task Handler / Recipe / task-result schemas | None | Existing public contracts can be called by Kit code; no contribution adapter. |
| Evidence Trace | Actual loading/check/rule observations | Records name, version, manifest SHA-256 and source; does not infer scientific causality. |

No selected Kit means no active Kit gate or extra rule-field scope. Imported Python can still have arbitrary side effects; unloading reverses owned registrations, not arbitrary code effects.

## Smallest manifest example

This interface example declares integer input, not a molecular or laboratory method. Implement the two named functions before loading it.

```json
{
  "schema_version": "kit-v2",
  "name": "example-assessment",
  "version": "0.1.0",
  "core_version": {"minimum": "2.2.5", "maximum_exclusive": "3.0.0"},
  "input_schema": {
    "type": "object", "additionalProperties": false, "required": ["count"],
    "properties": {"count": {"type": "integer", "minimum": 0}}
  },
  "input_example": {"count": 7},
  "entrypoint": "scripts/run.py:run",
  "outputs": {"contract": "json-object", "files": ["result.json"]},
  "contributions": [{
    "target": "tools", "name": "assess",
    "description": "Inspect one supplied count.",
    "source": "Construction-defined interface example; no biological claim.",
    "content": {
      "entrypoint": "scripts/tools.py:assess", "category": "compute",
      "parameters_schema": {
        "type": "object", "additionalProperties": false, "required": ["count"],
        "properties": {"count": {"type": "integer", "minimum": 0}}
      }
    }
  }]
}
```

The complete entry accepts `(inputs, out_dir)`, writes any declared files with explicit UTF-8, and returns finite JSON. A contributed tool accepts its schema-declared parameters and returns ToolResult. These are separate boundaries; a returned JSON status alone is not a Core DNA delivery receipt.

## Shortest addition workflow

1. Create the Kit folder with SKILL.md and kit.json. Keep the entrypoint and contributed tool files inside it. A tool callable returns the existing `core.tools.result.ToolResult`.
2. Describe the task trigger, scientific boundaries, required checks and actual files in SKILL.md. Keep machine fields in the manifest and cite domain rules in their owning resources.
3. Use `scripts/run_kit.py list --kit-dir <parent-or-Kit>` and `describe <name> --kit-dir ...` to validate/discover metadata without importing Kit code.
4. Invoke `scripts/run_kit.py run <name> --kit-dir ... --input inputs.json --out-dir output` to run its entrypoint. Explicit external loading warns before Python import and records name/version/manifest hash/source in the active Trace. Notice is once per catalog/process; no hidden persistent trust store is created.
5. For contributed atomic tools, use existing `describe_tools.py` and `run_step.py` with `--kit-dir`. Tool loading reuses the registry/step boundary; inspect actual outputs and retained errors.
6. Test valid input, invalid input, incompatible Core, missing entrypoint and a malformed neighbor Kit. Test namespacing/collisions and category enforcement. Keep test-only toys outside the distributed tree.

For v2, inspect the declaration with `describe`, then execute only its needed seams:

```text
python -X utf8 -B scripts/run_kit.py pipeline NAME TEMPLATE --kit-dir KIT_DIRECTORY --input inputs.json --out-dir output
python -X utf8 -B scripts/run_kit.py gate NAME GATE --kit-dir KIT_DIRECTORY --input gate-input.json --out-dir output
python -X utf8 -B scripts/run_kit.py rules NAME RULESET --kit-dir KIT_DIRECTORY --input rule-input.json --out-dir output
```

Pipeline input is the template's inputs_schema object; hosts do not supply a replacement step list. The existing composite executor parses every inputs value as a molecule source. Use material inputs only; ordinary count/start/flag configuration cannot be mixed into that source map. Keep fixed parameters in the template or prepare a bounded conditional workflow in Kit Python.

Gate CLI input has `candidate`, optional `sources/requirements/steps/inputs`. Its synchronous callback accepts `candidate=..., sources=..., requirements=..., steps=..., inputs=...` and returns a list of check objects. Each declared scope needs exactly one row with `scope`, `status` and `subject_version` bound to the actual current candidate. Use the existing `check_result(..., subject=candidate, scope=...)` helper. Supported raw statuses are PASSED, FAILED, INCOMPLETE and NOT_APPLICABLE; a required scope must pass or receive its explicit permitted acceptance, so the latter two do not silently pass. Unknown/repeated/missing scopes or stale versions reject the result.

For the optional Kit-owned acceptance, the failed row's `details.inherited_from_source` names an actual sources key and `details.input_version` equals that actual source's record_version. The manifest's declared scope/source/reason is required; original Core findings cannot use this mechanism. Rule CLI input has `trigger` and `context`. The CLI writes steps.json, gate-result.json or rule-result.json respectively. A failed mandatory gate gives a nonzero exit and retained declared error code. The normal Kit execution scope rejects a declared gate that was never executed. Calling one standalone gate does not certify the complete application.

The caller controls explicit directories. Discovery reads package-local kits/ and explicit directories only, never downloads code, and does not search user home or neighboring repositories. Metadata discovery does not execute Python. Missing required fields, incompatible versions and missing entrypoints have separate diagnostics; a malformed neighbor does not hide valid Kits.

Unloading removes the catalog's contributed registry entries and restores its module wrappers, so reloading records one operation per actual call. It does not undo arbitrary import side effects or unload Python modules. Loading failures, including an entry module's SystemExit and a manifest disappearing after discovery, remain diagnostics without blocking a valid neighbor.

The complete Kit CLI closes its loading recorder under kit-loading/ before calling a Kit-owned application/receipt boundary. Its domain Trace can then retain its established files and scopes. Atomic tool loading inside run_step is observed in that step's existing Trace. These are actual loading facts, not new scientific relationships. A local file URI can name a non-DNA configuration input; ordinary existing-file strings in the current step material collector denote DNA.

## SKILL.md template

```markdown
---
name: example-assessment
description: Assess supplied count records when the user needs a bounded numeric comparison. Do not use for sequence construction or claims requiring unprovided experimental evidence.
---

# Example assessment

Use this Kit for <supported user intent>. Ask for <missing task-defining input> before running.
Its supported scope is <scope>; use <other relevant route> for <excluded intent>.
Read kit.json for input fields and a valid example; do not infer undeclared fields.
Run the declared entrypoint through the Core Kit runtime.
Before delivery, run <mandatory checks> on <actual current inputs/products>.
Inspect <actual output files and receipt>; retain failed attempts and unknown results.
For domain decisions, read <row-level sourced rule/reference>.
Example: <short natural-language request> with <construction-only inputs>.
<Inference beyond supported inputs> remains unverified.
```

The description triggers host selection; the identifier is not a fixed routing answer. Human/host routing quality is a separate evaluation. Installed support and engineering regression do not establish arbitrary Kit compatibility or wet-lab success.

## Legacy compatibility

Application migration retains its existing CLI/import interfaces and business capture. Generic runtime loading has explicit load metadata. A migration comparison may normalize only enumerated volatile invocation/time/path values, with hashes checked against corresponding actual files; scientific content, checks, errors, roles and scope stay exact. Deliberately added gates/rule observations require separately documented output differences. No old test expectation changes merely because files moved.

## Acceptance checklist and limits

1. Freeze the source and original positive/rejected inputs before evaluation. Retain failed and repeated runs; declare developer assistance.
2. Verify list/describe without import, actual external load notice, load identity/manifest hash and broken-neighbor isolation. Distinct missing-field, entrypoint, Core-range and naming errors must stay visible.
3. Run each contributed seam through public entries. Missing rules sources are rejected, real scope failures block, write/network/external tools remain rejected by run_step. Test unload/removal and no-Kit restoration.
4. Determine molecular/count expectations by independent construction or published calculation before calling the implementation. Read generated files and receipts; do not treat the implementation's self-report as the oracle.
5. Compare migration outputs file by file and explain every permitted difference. Do not suppress unknown differences or relax previous science/error expectations.
6. Build one complete application Skill from its exact source, install into an empty directory with pinned dependencies, verify source/payload hashes and run every application entry. Exclude development data and test toys.
7. Report known regression, independent constructed input, host evaluation and wet experiments separately. Skips are not passes. Bind CI to its tested source tree.

This interface does not add a planner, routing model, branch DSL, scientific relation type, code sandbox, new DNA algorithm or automatic file delivery authorization. Template-inherited Core diagnostic acceptance is **NOT_IMPLEMENTED**: it would change base delivery policy, has no enabled application, and needs a user decision before source/product correspondence, version binding, unrelated-finding rejection and all delivery routes are independently verified. Handler/Recipe/schema adapters and broader packaging/routing support remain future work, not a promise.
