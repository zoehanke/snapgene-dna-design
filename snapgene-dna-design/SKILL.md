---
name: "snapgene-dna-design"
description: "Design, inspect, and verify plasmids and DNA constructs with the repository's recipes and atomic tools. Invoke for cloning, assembly, mutagenesis, tagging, HDR donors, guide vectors, or verification designs."
---

# SnapGene DNA Design

Use this skill to turn a molecular-biology request into an inspectable sequence design and an explicit preparation chain. Keep design output, physical source material, and verification evidence separate.

First decide whether supplied material can be reused, needs physical preparation, or needs a new design. A verification-only task can finish with a supported reuse conclusion; do not add PCR, assembly or redesign merely to exercise the workflow. Lead the response with that conclusion and the shortest next action, then state conditions where they change the action. Inspect actual records without inventing a conflicting strain background or assuming undocumented biological properties.

## Short workflow

Read `INSTALL-SOURCE.json` only in this Skill root when present and use its verified `python_executable`. If absent, choose an interpreter and run `scripts/check_env.py --json` once. Do not search parent/test directories for installation records. Setup instructions are in [docs/installation.md](docs/installation.md).

1. **Inspect sources.** Identify every source record, topology, feature interval, strand, and coordinate system. Start with:

   ```text
   python scripts/inspect_plasmid.py <source> [<second-source>]
   ```

   Sequence inputs may be raw DNA, FASTA text, a sequence file, or a `SeqRecord` in direct Python calls. CLI JSON normally uses strings or file paths. Resolve the complete original record before designing PCR.

2. **State intent and material status.** Preserve the user's required components, interfaces, mutations and exclusions before choosing a route. Check that original list at handoff; a route that cannot satisfy it needs revision or an explicit incomplete result. Record what is provided prepared DNA, what must be prepared from a complete template, and what is only a design component. Express required/forbidden DNA in `expected_components` / `forbidden_components`; Recipe and Pipeline can resolve features from named `sources`, avoiding manual copying of long sequences. A backbone needs an actual preparation row or an explicit supplied-prepared status. User authorization persists.

   Query `python scripts/describe_tools.py workflow_requirements` for the executable goal fields. Retain the user's exact text in `original_request` and add computable constraints as needed. Read `goal_coverage` at handoff: it lists what was checked and preserves free-text gaps. A string `requirements` list is descriptive text, not an executable component declaration; the goal boundary rejects it. Choose either an explicit component sequence or an original source selector; if both are supplied, they must agree.

3. **Choose a route for the remaining work.** If new construction is needed, prefer a standard Recipe with the exact signatures and branch notes in [references/recipes.md](references/recipes.md). Use the composite pipeline for a multi-step or non-standard route. Already suitable material does not require a new construction run. When preparation is needed, keep its physical order visible:

   Query current parameters with `python scripts/describe_tools.py <recipe_or_tool>`; omit the name to list available entries. Use existing PCR/digest/assembly operations for sequence calculations. If custom code is needed, verify its final ordered oligos and actual returned products before delivering, including any later edits.

   For one step at a time, use `python scripts/run_step.py --input step.json --out-dir build/step`. Inputs name `method`, `params`, `step_id` and original `sources`; continue with the previous `steps.json` as `history_file`. Tools and Recipes share the same entry. `$step.products.0` explicitly selects a real product; QC's `analysis.subject` is the checked source, not a new construct. Default output is concise; the returned record path holds full facts.

   Finish construction with `scripts/finalize_workflow.py --input close.json --out-dir build/final --deliver --confirmed`. Inputs name the actual record, original requirements/sources, selected candidate and final oligos. Use existing user authorization for the flag; do not ask again. [Runnable example and exact input fields](examples/execution_workflow.py). The common gate replays actual work and builds one current bundle. Custom results without replayable transformation evidence retain INCOMPLETE scopes. A supplied already suitable donor still needs no redesign.

   Present the returned `present_files` paths from that delivery. Use `python scripts/verify_delivery.py --directory <returned-directory> --presented-json <selected-path-list.json> --manifest-sha256 <returned-hash>` to check the actual final selection. Edited/renamed candidate copies need renewed domain/file validation. This command verifies file membership and integrity, not new biological claims or arbitrary host activity.

   Actual preparation pairs have separate complete-oligo quality results in `preparation_quality.json`; replay success is not a quality pass. Use the returned method/conditions and revise the route when quality fails or is incomplete. Known QuikChange complementary pairs are individually measured; ordinary PCR rules remain unchanged. Keep synthesis and QC uses separate.

   ```text
   complete source -> PCR and/or digest -> actual intermediate -> assembly or ligation -> product checks
   ```

   A theoretical tag, fusion, or other component result can guide design. It is not a PCR template. PCR must bind the complete original template and its returned product must feed the next digest or assembly step.

   For source/reference similarity or coding-difference claims, query `describe_tools.py compare_sequences` and use its actual feature boundaries, coverage, orientation, frame and genetic code. Local mode handles a short region inside a longer reference. Inspect protein/codon results before saying changes are synonymous. Use selected-record coordinates; genomic offsets and phenotype require their own evidence.

   For a continuing task, reference the previous delivered file as the next actual template. Its retained sequence alone does not establish inheritance if preparation still uses the original parent. The PCR CLI supports 5-prime tails and annotated `.gb/.dna` output; its source copy and order tables use template coordinates, not final-product coordinates.

   In Gibson fragments mode, the runtime evaluates which forward or reverse primer carries each junction homology arm and keeps the selected layout in the preparation records.

4. **Check biological context.** Verify source boundaries, orientation, cut geometry, junction sequence, topology, reading frame, and primer/template consistency. Distinguish sites consumed by the current reaction from sites required for the product's next use. A recipient or dropout cassette can need its flanking recognition sites even when its coding sequence is intact. Inspect all downstream interfaces before choosing PCR boundaries, then check their retained sequences and actual cut counts in the final file. For expression cloning, inspect the vector's real start point and the complete enzyme-to-insert boundary. Do not select a different downstream CDS to make a translation look valid. For HDR, distinguish insertion from replacement. For a guide vector, verify the full guide structure, including scaffold.

   Treat an annotated CDS as complete unless its metadata explicitly identifies a partial protein, bounded tag, start-codon marker, or fuzzy boundary. For a fusion, record the complete ORF and its contained protein domains before delivery. Absence of a stop codon is a failed check, not evidence of a partial CDS.

   If the user requires an actual PAM change, set `require_pam_disruption=true` in the HDR tool/Recipe. It rejects a retained NGG PAM rather than substituting a warning. A guide that cannot meet the condition is a route-selection problem; preserve the requirement while choosing another guide.

5. **Run and inspect artifacts.** Standard entry points are:

   ```text
   python scripts/run_recipe.py --recipe <recipe> --params-json params.json --out-dir build
   python scripts/run_pipeline.py --pipeline pipeline.json --out-dir build
   ```

   Normal execution writes the product candidate and result JSON. When a result contains preparation rows, it also writes actual intermediates under `intermediates/`, source-record primer copies under `annotated_sources/`, and `primer_order_table.tsv`. Inspect the complete oligo sequence, binding core, strand, and interval separately. Long 5-prime additions use `core.tools.amplification.prepare_pcr_fragment`; every successive row names the actual preceding template, complete primers, product, and `annealing_temperature_hint_C`.

   Recipe component requirements use `name`, `expected_sequence` (or `sequence`), and optional `strand` (`1` or `-1`). They are checked against the saved GenBank candidate through the existing goal validator. Failed requirements retain candidate evidence and stop delivery. An absent requirement is not a verified user goal.

   Verification designs use complete-template PCR simulation and actual primer coordinates. Read the returned Tm, junction coverage and Sanger distance; repeated sequence or insufficient flanks can prevent a usable assay. QC primer search also rejects measured hairpin/self-dimer candidates and checks the actual PCR pair through Primer3. Parental-template discrimination needs an explicit parent control. QC `.dna` files retain source topology, features and the designed primers. For primer search, 60°C is a ranking target; accepted cores may fall within 52–72°C. Complete oligos are checked, and cores beyond 36 nt use Biopython nearest-neighbor calculations with same-condition Primer3 structure checks.

6. **Deliver the actual result.** `--finalize --confirmed` requests authoritative promotion for a complete construct. A component or QC result remains a component or QC result. Keep an assumption in the delivery gate only when resolving it changes this artifact or the requested action. General biological caveats belong with the affected downstream step, not as invented unresolved task assumptions. Report concrete warnings and unknowns; sequence computation does not establish wet-lab efficiency, expression, or genome-wide specificity.

The first handoff must include the main result, actual requested artifacts and any generated Trace HTML/Markdown links, using the host's supported link format. A short reuse conclusion may be sufficient for a simple inspection; add a scheme or diagram when it explains the actual task. Do not present a nonexistent report or a plain-text placeholder as an actionable link.

Use the Recipe or ConstructionTask routes for biological edits. The legacy keyword agent cannot execute promoter/resistance replacement, fusion tagging or HDR from keyword classification and refuses those requests. Its simple sequence-edit previews do not provide a physical preparation protocol.

## Evidence Trace: capture during work, organize at handoff

Read the current level once with `python scripts/trace_design.py config`. Keep the user's setting. Use one explicit `--trace-dir` for actual tool calls, including inspection and file operations. Off records nothing; Observed records facts without extra explanations; Full also retains a brief public explanation alongside each consequential choice. Record the user's stated reasons as theirs. Normal capture failures preserve DNA work.

During design, concentrate on the requested result. For a genuine choice, retain what you selected, the short reason, relevant source and any consequential limit in the same public response. Follow requirements without inventing a choice. Capture missing explanations honestly. Read [capture instructions](references/trace-capture.md) only when submitting notes or running a custom script.

Once the relevant design result is established, read [Trace organization and handoff](references/evidence-trace.md). In Full, organize actual captured records and prepare the report at that boundary; include it with the first handoff. Observed needs no extra organization unless requested. The report explains the work; recording gaps do not change biological parameters or become experimental prerequisites.

## Composite pipeline references

Atomic tools return `ToolResult`: `products` contains complete Molecules, `analysis` contains calculations, `checks` contains scoped program results. Python callers use `.only_product()` only for one product, `.products[index]` for an explicit choice, and `.analysis` for analysis. Keep the complete material, never `str(record)` or a reconstructed sequence-only surrogate.

Pipeline references are `$source_id`, `$step_id` for exactly one product, `$step_id.products.0` for an explicit product, and `$step_id.analysis.field` or `$step_id.analysis.field.0` for analysis. Multiple products and analysis-only outputs cannot be selected implicitly. Set `output_step` when later steps only inspect the deliverable. Use `ligate_fragments` for already digested/annealed duplexes and `rotate_sequence` for a circular display-origin change.

If preparation is required, submit `validation_requirements: ["sequence_model", "preparation_model", "file", "user_goal"]`. Otherwise inspect the reported preparation scope and state what was checked; sequence editing alone does not establish a preparation chain. A saved `.gb`/`.dna` can be the next actual material input. Edited files with stale molecular metadata require explicit re-import/rebinding, not reuse of an old result.

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
