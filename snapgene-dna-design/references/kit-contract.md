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
| outputs | `contract: json-object`, plus declared relative file roles/names. This declaration does not itself validate DNA or authorize delivery. |
| contributions | Rows with `target`, local `name`, `content`, `source` and `description`. Sources explain where the rule/capability comes from; they are not automatic verification. |
| metadata | Opaque application-owned declaration. Core does not interpret project-specific fields or register project names. |

For `target: tools`, content contains an entrypoint, a side-effect category and parameters_schema. The effective name is `kit.<Kit-name>.<tool-name>`. Existing ToolSpec checks signature, aliases, parameters and ToolResult; the existing run_step gate rejects write/network/external categories. Imported Python is not sandboxed, and an inaccurate category cannot make unsafe code safe.

v2 adds three typed adapters into existing seams:

| target | content and execution boundary |
|---|---|
| pipeline | `steps` is the existing linear `step_id/tool/params` list; `inputs_schema` validates host-supplied inputs; optional `output_step` uses the existing product selector. Effective ToolSpec name is `kit.<name>.pipeline.<local-name>`. Existing composite Pipeline executes it, including the original side-effect gate. Conditions remain Kit Python. |
| gates | `entrypoint` returns current-version scoped check rows. `required_scopes` supplies scope/error_code/message. Missing execution, missing scopes or failed checks block a successful Kit result. Active Kit requirements are added to candidate validation; original Core judgments are retained. |
| rules | `path` names UTF-8 JSON in the existing experience-rule grammar; `fields` explicitly declares extra local context fields. Every row needs a nonblank source type and description or URL. Evaluation uses the original rule engine and restores local fields afterwards. |

Optional gate `acceptances` require an explicit Kit-owned scope, nonblank source and reason. A failed row must bind the actual input identifier/version before receiving effective status ACCEPTED_BY_KIT_RULE. Output and Trace retain its raw FAILED status, source, reason and notice “按 Kit 规则豁免”. This cannot accept original Core inherited diagnoses or clear Core errors. An input-template annotation error can therefore still prevent formal delivery. This phase demonstrates acceptance with a toy only; the project CRISPR Kit enables none.

Handler, Recipe, data-contract and reference adapters remain **NOT_IMPLEMENTED**. All four current project Kits keep their established conditional workflows; none uses a contributed Pipeline template. A temporary external toy proves that adapter.

## Shortest addition workflow

1. Create the Kit folder with SKILL.md and kit.json. Keep the entrypoint and contributed tool files inside it. A tool callable returns the existing `core.tools.result.ToolResult`.
2. Describe the task trigger, scientific boundaries, required checks and actual files in SKILL.md. Keep machine fields in the manifest and cite domain rules in their owning resources.
3. Use `scripts/run_kit.py list --kit-dir <parent-or-Kit>` and `describe <name> --kit-dir ...` to validate/discover metadata without importing Kit code.
4. Invoke `scripts/run_kit.py run <name> --kit-dir ... --input inputs.json --out-dir output` to run its entrypoint. Explicit external loading warns before Python import and records name/version/manifest hash/source in the active Trace. Notice is once per catalog/process; no hidden persistent trust store is created.
5. For contributed atomic tools, use existing `describe_tools.py` and `run_step.py` with `--kit-dir`. Tool loading reuses the registry/step boundary; inspect actual outputs and retained errors.
6. Test valid input, invalid input, incompatible Core, missing entrypoint and a malformed neighbor Kit. Test namespacing/collisions and category enforcement. Keep test-only toys outside the distributed tree.

The caller controls explicit directories. Discovery reads package-local kits/ and explicit directories only, never downloads code, and does not search user home or neighboring repositories. Metadata discovery does not execute Python. Missing required fields, incompatible versions and missing entrypoints have separate diagnostics; a malformed neighbor does not hide valid Kits.

Unloading removes the catalog's contributed registry entries and restores its module wrappers, so reloading records one operation per actual call. It does not undo arbitrary import side effects or unload Python modules. Loading failures, including an entry module's SystemExit and a manifest disappearing after discovery, remain diagnostics without blocking a valid neighbor.

The complete Kit CLI closes its loading recorder under kit-loading/ before calling a Kit-owned application/receipt boundary. Its domain Trace can then retain its established files and scopes. Atomic tool loading inside run_step is observed in that step's existing Trace. These are actual loading facts, not new scientific relationships. A local file URI can name a non-DNA configuration input; ordinary existing-file strings in the current step material collector denote DNA.

## SKILL.md template

```markdown
---
name: example-assessment
description: Assess the supplied example records when the user needs a bounded comparison, including ambiguous or unsupported inputs.
---

# Example assessment

Use this Kit for <supported user intent>. Its evidence covers <scope>.
Read kit.json for input fields and examples. Run the declared entrypoint through the Core Kit runtime.
Inspect <required checks> and the actual <output files>. Retain failed attempts and unknown results.
<Scientific inference outside the supported inputs> remains unverified.
For domain decisions, read <sourced reference>.
```

The description triggers host selection; the identifier is not a fixed routing answer. Human/host routing quality is a separate later evaluation. Do not claim a plugin ecosystem, automatic compatibility with arbitrary Kits or wet-lab success.

## Legacy compatibility

The first pilot retains its old Toolkit CLI/import interface and existing business capture. Generic runtime loading has its own explicit load metadata. Comparing the legacy output may normalize only enumerated volatile invocation/time/path values, and hashes must be checked against the actual corresponding files; scientific content and checks stay exact. No old test expectation changes merely because files moved.
