---
name: "snapgene-dna-design"
description: "Design, inspect, and verify plasmids and DNA constructs with the repository's recipes and atomic tools. Invoke for cloning, assembly, mutagenesis, tagging, HDR donors, guide vectors, or verification designs."
---

# SnapGene DNA Design

Use this skill to turn a molecular-biology request into an inspectable sequence design and an explicit preparation chain. Keep design output, physical source material, and verification evidence separate.

## Short workflow

1. **Inspect sources.** Identify every source record, topology, feature interval, strand, and coordinate system. Start with:

   ```text
   python scripts/inspect_plasmid.py <source> [<second-source>]
   ```

   Sequence inputs may be raw DNA, FASTA text, a sequence file, or a `SeqRecord` in direct Python calls. CLI JSON normally uses strings or file paths. Resolve the complete original record before designing PCR.

2. **State intent and material status.** Record what is a complete provided fragment, what must be prepared from a source template, and what is only a design component. A backbone must have an actual PCR or digest preparation row, or be explicitly marked as supplied prepared material. Translate required and forbidden DNA components into the existing `expected_components` / `forbidden_components` fields before delivery. Recipe parameter JSON accepts these fields with explicit component sequences; Pipeline can also resolve source features. User authorization persists; do not ask for the same confirmation again.

3. **Choose a standard recipe first.** Use the exact signatures and branch notes in [references/recipes.md](references/recipes.md). Use the composite pipeline only for a multi-step or non-standard route. Keep the physical order visible:

   ```text
   complete source -> PCR and/or digest -> actual intermediate -> assembly or ligation -> product checks
   ```

   A theoretical tag, fusion, or other component result can guide design. It is not a PCR template. PCR must bind the complete original template and its returned product must feed the next digest or assembly step.

   In Gibson fragments mode, the runtime evaluates which forward or reverse primer carries each junction homology arm and keeps the selected layout in the preparation records.

4. **Check biological context.** Verify source boundaries, orientation, cut geometry, junction sequence, topology, reading frame, and primer/template consistency. Distinguish sites consumed by the current reaction from sites required for the product's next use. A recipient or dropout cassette can need its flanking recognition sites even when its coding sequence is intact. Inspect all downstream interfaces before choosing PCR boundaries, then check their retained sequences and actual cut counts in the final file. For expression cloning, inspect the vector's real start point and the complete enzyme-to-insert boundary. Do not select a different downstream CDS to make a translation look valid. For HDR, distinguish insertion from replacement. For a guide vector, verify the full guide structure, including scaffold.

   Treat an annotated CDS as complete unless its metadata explicitly identifies a partial protein, bounded tag, start-codon marker, or fuzzy boundary. For a fusion, record the complete ORF and its contained protein domains before delivery. Absence of a stop codon is a failed check, not evidence of a partial CDS.

5. **Run and inspect artifacts.** Standard entry points are:

   ```text
   python scripts/run_recipe.py --recipe <recipe> --params-json params.json --out-dir build
   python scripts/run_pipeline.py --pipeline pipeline.json --out-dir build
   ```

   Normal execution writes the product candidate and result JSON. When a result contains preparation rows, it also writes actual intermediates under `intermediates/`, source-record primer copies under `annotated_sources/`, and `primer_order_table.tsv`. Inspect the complete oligo sequence, binding core, strand, and interval separately. Long 5-prime additions use `core.tools.amplification.prepare_pcr_fragment`; every successive row names the actual preceding template, complete primers, product, and `annealing_temperature_hint_C`.

   Recipe component requirements use `name`, `expected_sequence` (or `sequence`), and optional `strand` (`1` or `-1`). They are checked against the saved GenBank candidate through the existing goal validator. Failed requirements retain candidate evidence and stop delivery. An absent requirement is not a verified user goal.

   Verification designs use complete-template PCR simulation and actual primer coordinates. Read the returned Tm, junction coverage and Sanger distance; repeated sequence or insufficient flanks can prevent a usable assay. Parental-template discrimination needs an explicit parent control. QC `.dna` files retain source topology, features and the designed primers. For primer search, 60°C is a ranking target; accepted cores may fall within 52–72°C. Complete oligos are checked, and cores beyond 36 nt use Biopython nearest-neighbor calculations with same-condition Primer3 structure checks.

6. **Promote only after confirmation.** `--finalize --confirmed` requests authoritative promotion for a complete construct. A component or QC result remains a component or QC result. Report warnings and unknowns; sequence computation does not establish wet-lab efficiency, expression, or genome-wide specificity.

Use the Recipe or ConstructionTask routes for biological edits. The legacy keyword agent cannot execute promoter/resistance replacement, fusion tagging or HDR from keyword classification and refuses those requests. Its simple sequence-edit previews do not provide a physical preparation protocol.

## Evidence Trace (v0.3.1 sidecar)

Before design work, read the global level with `python scripts/trace_design.py config`; read [references/evidence-trace.md](references/evidence-trace.md) for capture and organization contracts. Off creates no new Trace. Observed preserves facts and supplied reasons without extra explanation or organization by default. Full adds brief public reasons during actual choices, then requires the host to organize the recorded process at a meaningful stage boundary and before handoff. This consumes real model work; Python does not invoke another model service.

Use one `--trace-dir` for the task, including inspect, primer annotation, conversion and preview-bundle commands. Those file tools join Trace only when this directory is explicitly supplied. Record user constraints as requirements, not invented AI choices. Observe available original text with `trace_design.py observe`, retain exact returned references, and keep later interpretations separate from original explanations.

At handoff: submit the explicit final file list with `handoff`; read `inspect --data`; author an organization JSON from those actual records; submit it with `organize`. Include stage purposes, actual steps/branches, source references, unknowns and an optional `report_plan`. The full packet contract and commands are in the reference above. It is not enough to record scattered Decisions or generate attractive HTML. Check the returned snapshot is current, the intended files are linked, and the generated report reflects actual checks and failures. New tool results require refreshed organization; never rewrite old events. Use `report-plan` only to change the reading arrangement of an exact process version. `render` deterministically exports HTML/Markdown without model calls. Do not hand-code a replacement report.

Keep record submitter (`actor`) separate from `decision_actor` and its supplied source reference. Preserve user requirements with `requirement_source` and supplied background in context; label summaries rather than quoting them as original words. For user change/confirm/reject, include the source and exact affected `basis_refs`. Decisions can reference existing program events as basis without treating input submission as success. User reasons remain user reasons; missing authorship stays unknown. Later assistance is a separate `explanations` entry tied to an exact old revision. `reader` returns the complete machine result; `--run-id` adds a focused factual view while retaining supporting history. `--through-sequence` selects historical facts. See the [data-to-reader mapping](references/evidence-trace-reader-mapping.md).

When a trace contains alternatives or old revisions, use `context_refs` in the existing trace-input bundle to select the exact records for this run; see the reference above. Check result_event_ref and stage_ref for actual program results. Recording time is not the time a scientific choice occurred. Treat capture faults, coverage/explanation gaps and design review items separately; do not invent Claims or rationale to clear gaps. These are sidecar records, not permission to alter Core behavior.

Before execution, use `python scripts/trace_design.py coverage --trace-dir <trace-dir> --design-json <task-or-pipeline-or-recipe-params.json>` to review known input choices against recorded Decision.targets. Provide exact fields/values and step scope where available. A missing/weak association is a gap, not a reason to invent rationale; preserve the time and nature of any later clarification. This preflight does not execute or gate DNA design.

For applicability, record structured contexts separately on Evidence Statements and Claims. Do not fill missing organism, strain, host, construct context, temperature, medium, assay or intended use with guessed defaults. The program compares declared contexts; it neither verifies papers nor proves the Claim. Source-verification receipts remain separate.

Trace observes program results and files; it does not choose parameters or change Core rules. Normal mode preserves DNA execution on Trace failure and reports `TRACE_INCOMPLETE`; strict mode is explicit. The fixed offline Living Evidence Document provides Document / Mind Map / Split projections sharing selection and expansion state. Record genuine context/target revisions as they occur; Change Impact links differences to old records and recommends checks without changing conclusions or executing RERUN. Automatic comparisons require matching task identity or Recipe; use the documented compare command for another baseline. The host must not generate HTML from design.md or mark uncertain dependencies unaffected. Record completeness is not a safety verdict. When tracing was not enabled, do not claim the task's decisions were recorded.

## Composite pipeline references

Pipeline parameters resolve recursively. Use `$source_id` for a named source, `$step_id` for the prior step output, `$step_id.field` for a result field, and `$step_id.field.0` or another numeric segment for a list index. A whole `$step_id` passes the sequence record when the step produced one, preserving sequence, topology, and features; use field references for scalar or list values. Set `output_step` in the pipeline or pass `--output-step` when later steps are analysis-only and a prior sequence-producing step is the deliverable.

The resolver accepts references inside nested dictionaries and lists. A reference must point to a source or an earlier step. The selected output step must produce a sequence.

## pML104 guide preparation

The dedicated atomic tool is:

```text
prepare_pml104_guide(vector_record_or_seq, spacer_seq)
```

It requires the complete circular pML104 template and an explicit 20 nt `A/C/G/T` spacer. It follows the pML104 inverse-PCR and KLD route, restores the missing 5-prime part of the guide cassette, and returns preparation primers, the circular product, and `scaffold_complete`. It does not apply the generic BbsI/U6 oligo rule or prepend an extra transcription G. The delivered guide must contain the spacer and the complete scaffold. See the primary pML104 method description [Hu et al. (2018)](https://pmc.ncbi.nlm.nih.gov/articles/PMC5868978/).

## Pointers

- Read [references/recipes.md](references/recipes.md) for all seven Recipe signatures, defaults, aliases, and method-specific checks.
- Read [references/guardrails.md](references/guardrails.md) when a biological check or warning needs its rule and applicability.
- Read [references/source-policy.md](references/source-policy.md) when provenance or source evidence is unclear.
