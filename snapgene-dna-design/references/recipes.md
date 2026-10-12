# Recipe parameter reference

This file mirrors `core/recipes/` signatures; query `scripts/describe_tools.py` for the executable definition. CLI inputs accept DNA/file strings or complete molecule wire values. Python also accepts SeqRecord/Molecule. RecipeResult carries complete `products`, `analysis`, scoped `checks`, primers, warnings, protocol/citations and details. Sequence/topology/features in legacy reports are computed projections, not independent DNA outputs. Preparation rows carry actual template/product Molecules; serialize only at the report/file boundary.

## Goal continuity

Python `run_step(..., requirements=context)` and step JSON use the same context as `validate_candidate`/`deliver_result`. Later steps inherit it through `previous`/`history_file`; finalization can omit repeated requirements. Explicit additions merge with earlier constraints. A conflicting original request or scalar goal is rejected; changed routes and intermediate materials are allowed.

Recipe CLI params may contain `requirements: {...}` or legacy `original_request`, `expected_components`, `forbidden_components`, `sources`, `goal_items`; direct Recipe scientific signatures stay unchanged. Pipeline JSON/Python accepts `requirements` and `original_request`; Task uses `requirements` plus existing `raw_request`/product constraints.

```json
{
  "original_request": "Keep the supplied marker in a linear DNA fragment.",
  "topology": "linear",
  "expected_components": [{"name": "marker", "source_id": "original"}],
  "goal_items": [{"id": "keep_marker", "text": "Keep the supplied marker",
    "source_quote": "Keep the supplied marker",
    "constraint_refs": ["/expected_components/0"]}]
}
```

References name existing constraints (`/topology`, `/expected_sequence`, `/is_cds`, or an indexed component/required file). `source_quote` is checked against original text, not scientifically interpreted. MISSED means no mapped check; UNCHECKED means the check has not established a result. PASSED applies to the actual checked material/version. `task_completion.original_task_verified` is not promoted by local PASS; declared-goal success and free-text interpretation remain separate. Single analyses need no full goal.

## Common preparation rule

Recipes also run through `core.workflow.run_step` or `scripts/run_step.py`. `describe_tools.py <name>` shares signature-derived parameter validation with execution. Adaptation retains products, subject, roles/completeness, checks, primers, preparation, protocol, citations and actual internal operations. QC subject remains the checked source. Failed attempts remain recorded but supply no completed material. Resume against changed original input or implementation/backend conditions fails. Recipe finalization uses common candidate/bundle checks rather than sanity alone.

Executable common goals are defined by `describe_tools.py workflow_requirements`. Unknown goal/component fields and conflicting literal/source selectors are rejected. Preserve original text separately; returned goal coverage certifies declared computations, not all free-text meaning. Final links use `present_files` from the actual delivery, with optional `verify_delivery.py` before presentation.

Preparation quality is checked independently from reaction replay and written as `preparation_quality.json`. Full-oligo measurements reuse [Primer3](https://primer3.org/manual.html) conditions; the default 47°C structural policy is not a universal experimental cutoff. [QuikChange's intended complementary pair](https://www.agilent.com/cs/library/usermanuals/Public/200518.pdf) is measured as two individual complete oligos; its source-window/reaction checks still apply. Backend limits or absent measurements retain INCOMPLETE, not a pass.

`compare_sequences` is analysis-only. It reuses [Biopython pairwise alignment](https://biopython.org/docs/latest/Tutorial/chapter_pairwise.html) and the shared CDS validation contract. Local/global mode, query coverage, strand, actual selected boundaries and an explicit computation limit are reported. Coding changes are translated using the annotated frame/table; protein equality does not certify expression, selection or other phenotype.

Treat a source template, a prepared fragment, and a designed component as different things.

```text
complete source -> PCR and/or restriction digest -> actual intermediate -> assembly or ligation
```

Every backbone must either have a preparation row with its actual PCR or digest route, or be declared as supplied prepared material. A theoretical tag, fusion, guide component, or donor design does not become a physical PCR template. When a PCR is required, return to the complete original template and verify both primers against it.

The standard entry point is:

```text
python scripts/run_recipe.py --recipe <recipe_name> --params-json params.json --out-dir build
```

When `details.preparation` is present, the CLI also writes actual products to `build/intermediates/`, primer-annotated source copies to `build/annotated_sources/`, and `build/primer_order_table.tsv`. The order table carries the complete oligo, binding sequence, interval, strand, and Tm fields. Long 5-prime additions are split by `core.tools.amplification.prepare_pcr_fragment` into successive PCR rows; each row records the actual prior template, product and `annealing_temperature_hint_C`. `--finalize --confirmed` is only meaningful for a complete construct and requires the user's existing authorization.

Recipe CLI parameter JSON may also include `sources`, `expected_components` and `forbidden_components`. These common fields do not belong to the direct Recipe function signature. A source supplies `source_id` and `path`; a component supplies `name` plus either an explicit `expected_sequence`/`sequence`, or a `source_id` whose original feature matches that name. `interval_0based` selects a non-wrapping source interval instead of a feature. Optional `strand` is `1` or `-1`. The existing goal validator checks the saved GenBank candidate against those original sources. Failed requirements reject promotion. Keep downstream interfaces separate from sites consumed by this reaction.

For example, a common goal block can retain an original annotated connector without copying its DNA:

```json
{
  "sources": [{"source_id": "original", "path": "source.gb"}],
  "expected_components": [{"name": "connector", "source_id": "original"}]
}
```

Preparation export re-simulates declared PCRs from actual templates and ordered oligos before writing files. `coordinate_reference` in the order table names the annotated template copy, relative to the run directory; its intervals are 0-based half-open. A negative-strand cassette retains its declared primer orientation. Source copies remain distinct from final-product primer maps.

Use `python scripts/describe_tools.py <name>` for current callable parameters and tool schemas. For directly supplied primers, `python scripts/simulate_pcr.py template.gb --fwd SEQUENCE --rev SEQUENCE --out fragment.gb --json` uses the Core's exact tailed-PCR model and writes annotated GenBank/native files. No binding or ambiguous binding reports failure; the explicit mismatch mode is a separate approximate full-primer calculation.

## 1. `recipe_gibson_assembly`

**Callable:** `core.recipes.gibson.recipe_gibson_assembly`
**Returns:** `construct`, `complete_construct`
**Use for:** overlap assembly from real source-derived fragments.

### Signature parameters

| Parameter | Type | Default | Meaning |
|---|---|---:|---|
| `vector_linear_seq` | `Any` | `None` | Legacy pre-linearized vector input. Use only when the vector is already supplied in the required linear form. |
| `insert_template_seq` | `Any` | `None` | Legacy insert source template. |
| `insert_start` | `int \| None` | `None` | Legacy half-open start on the insert template. |
| `insert_end` | `int \| None` | `None` | Legacy half-open end on the insert template. |
| `overlap_length` | `int` | `22` | Requested homology length. The implementation bounds it to 15–35 bp. |
| `circular_product` | `bool` | `True` | Close the final junction when `True`. |
| `fragments` | `list[dict[str, Any]] \| None` | `None` | Recommended mode. Ordered full-template fragment specifications. |

### Recommended `fragments` mode

Use complete source templates for every fragment, including the backbone:

```json
{
  "fragments": [
    {"id": "backbone", "template": "backbone.gb", "start": 100, "end": 4500},
    {"id": "insert", "template": "insert.gb", "start": 20, "end": 820}
  ],
  "overlap_length": 22,
  "circular_product": true
}
```

Each item requires `template` (or the implementation's `source` alias), `start` (or `start_0based`), and `end` (or `end_0based`). Coordinates are half-open; a circular source may use a wrapping interval. The function chooses, for each junction, whether forward or reverse primer carries the homology arm, prepares every fragment from its complete source, and assembles the returned PCR products. Long additions become real successive PCR rows whose next template is the preceding product. `details.preparation` records the selected layout, complete primers, actual products and annealing hints. Do not pass an already-designed theoretical fusion as `template`.

The legacy four-input mode accepts a pre-linearized vector and prepares only the insert. Its result records that vector preparation was provided externally and warns that the all-fragment chain is incomplete. Prefer explicit `fragments` when the vector must be amplified or when provenance of every assembly fragment matters.

**Checks to inspect:** actual PCR products, overlap junctions, accepted core Tm in the 52–72°C window, complete-oligo structure QC, primer dimer warning, product topology, and `all_fragments_pcr_prepared` / `preparation_complete`. A 60°C core target is a ranking preference, not a universal promise.

**Reading:** Gibson et al., *Nature Methods* (2009), DOI `10.1038/nmeth.1318`; NEB NEBuilder HiFi protocol.

## 2. `recipe_restriction_cloning`

**Callable:** `core.recipes.restriction_cloning.recipe_restriction_cloning`
**Returns:** `construct`, `complete_construct`
**Use for:** PCR insert preparation, restriction digest, and T4 ligation.

### Signature parameters

| Parameter | Type | Default | Meaning |
|---|---|---:|---|
| `vector_source` | `str \| pathlib.Path` | required | Vector file or sequence input. |
| `insert_template` | `str \| pathlib.Path` | required | Complete insert source template. |
| `insert_start` | `int` | required | Half-open start on the insert template. |
| `insert_end` | `int` | required | Half-open end on the insert template. |
| `enzyme5` | `str` | `EcoRI` | 5-prime cloning enzyme. |
| `enzyme3` | `str` | `BamHI` | 3-prime cloning enzyme. |
| `insert_enzyme5` | `str | None` | `None` | Optional insert-side 5-prime enzyme for compatible cohesive ends such as BspHI with an NcoI vector; defaults to `enzyme5`. |
| `insert_enzyme3` | `str | None` | `None` | Optional insert-side 3-prime enzyme; defaults to `enzyme3`. |
| `insert_prefix` | `str` | `""` | Product-side sequence placed before the selected insert in the forward primer tail and expression-boundary check. |
| `insert_suffix` | `str` | `""` | Product-side sequence placed after the selected insert; the reverse-primer tail uses its reverse complement. |
| `coding_sequence` | `bool \| None` | `None` | Whether to apply coding-boundary checks. `None` infers coding intent from a target beginning with `ATG`. |
| `expression_start` | `bool \| None` | `None` | Records whether the caller asserts the expression start. `False` records a warning when the enzyme supplies an initiation boundary. |
| `orientation` | `str` | `auto` | Orientation passed to digest-ligation simulation. |

The function prepares the insert from the complete source with `prepare_pcr_fragment`, then simulates vector and insert digestion followed by ligation. Long primer additions are split into real successive PCR steps and each step exports its actual template, complete primers, product and annealing hint. The supplied vector is the digest substrate; if it must first be PCR-linearized, prepare it as an earlier pipeline step and pass that actual intermediate.

### NcoI/NdeI expression boundary

When `enzyme5` is `NcoI` or `NdeI` and the target is coding, the implementation checks the real enzyme-derived start boundary together with `insert_prefix`, the selected target interval, and `insert_suffix`. It checks the resulting sequence for an `ATG` start, frame remainder, internal stops, and terminal stop state. Inspect `quality_checks.expression_boundary` and the actual vector junction. Do not replace the selected interval with another downstream CDS to make translation pass. An incompatible expression boundary is a design failure that must be resolved against the original vector record.

**Checks to inspect:** internal enzyme cuts, directional end compatibility, methylation warnings, actual PCR product, `expression_boundary_compatible`, and ligation product sequence.

**Reading:** Green and Sambrook, *Molecular Cloning*, 4th ed.; NEB restriction-enzyme guidance.

## 3. `recipe_golden_gate`

**Callable:** `core.recipes.golden_gate.recipe_golden_gate`
**Returns:** `construct`, `complete_construct`
**Use for:** Type IIS digest and one-pot ligation of already specified fragments.

### Signature parameters

| Parameter | Type | Default | Meaning |
|---|---|---:|---|
| `fragments` | `list[str \| dict[str, Any]]` | required | At least two sequence/file/record or serialized fragment inputs carrying the Type IIS sites and overhangs. |
| `enzyme` | `str` | `BsaI` | Type IIS enzyme used by the simulator. |
| `circular` | `bool` | `True` | Circular product when `True`. |
| `enzyme_name` | `str \| None` | `None` | Compatibility alias. When supplied, overrides `enzyme`. |
| `circular_product` | `bool \| None` | `None` | Compatibility alias. When supplied, overrides `circular`. |

This recipe performs the digest and assembly simulation. It does not invent a PCR preparation for fragments. If a source fragment or backbone needs amplification, run a preceding PCR tool or pipeline step and pass that returned product. Every backbone must be an actual digest input or be explicitly supplied as a prepared fragment.

**Checks to inspect:** actual cut products, junction compatibility, palindromic overhang warnings, and recognition sites remaining in the product.

**Reading:** Engler et al., *PLoS ONE* (2008), DOI `10.1371/journal.pone.0003647`; Potapov et al., *ACS Synthetic Biology* (2018), DOI `10.1021/acssynbio.8b00333`.

## 4. `recipe_crispr_hdr_donor`

`require_pam_disruption` defaults to `false` for compatibility. Set it to `true` when the user's task requires the selected PAM to be changed; a retained NGG PAM raises `PAM_DISRUPTION_REQUIRED`. The tool still preserves coding identity for its additional silent edit. Review another guide or valid coding context if this one cannot meet the constraint; warnings or seed mismatches are not an actual PAM change.

**Callable:** `core.recipes.crispr_hdr.recipe_crispr_hdr_donor`
**Returns:** `component`, `component_only`
**Use for:** ssODN, short annealed dsDNA, or larger donor design around a Cas9 cut.

### Signature parameters

| Parameter | Type | Default | Meaning |
|---|---|---:|---|
| `target_seq_or_file` | `str \| pathlib.Path \| SeqRecord` | required | Original target locus record or sequence. |
| `cut_position_0based` | `int` | required | Cas cleavage boundary. |
| `edit_dna` | `str` | required | Inserted or replacement payload. |
| `donor_type` | `str` | `ssODN` | `ssODN`, `dsDNA` (including `double-stranded DNA` / `double-stranded donor`), or `plasmid` / `double-stranded plasmid donor`. |
| `grna_seq` | `str` | `""` | Optional spacer used to match the original target and assess PAM re-cleavage. |
| `grna_strand` | `int` | `1` | Guide strand, `1` or `-1`. |
| `custom_arm_length` | `int \| None` | `None` | Override left and right homology-arm length. |
| `target_is_cds` | `bool` | `False` | Apply CDS-aware PAM-silencing checks. |
| `cds_frame_offset` | `int` | `0` | Frame offset used for CDS-aware synonymous changes. |
| `edit_start_0based` | `int \| None` | `None` | Start of an explicit edit interval. |
| `edit_end_0based` | `int \| None` | `None` | End of an explicit edit interval. Must be supplied with `edit_start_0based`. |

If both edit boundaries are omitted, `edit_dna` is an insertion at `cut_position_0based` for compatibility with the original API. Supplying both boundaries uses a half-open interval `[edit_start_0based, edit_end_0based)`: equal boundaries are an insertion and unequal boundaries are a replacement. Do not use an empty `edit_dna` to stand in for a replacement.

Default arm lengths are 50 bp for `ssODN` and short `dsDNA`, and 600 bp for a plasmid donor. A short `dsDNA` result at or below 200 bp includes complete top and bottom oligos and an annealing description. A plasmid donor is a component design; its vector backbone must be supplied or built in a separate preparation route.

**Checks to inspect:** `edit_mode`, replacement interval and length, donor type, arm lengths, guide match, PAM-silencing state, and the complete donor sequence. This recipe does not create a guide expression plasmid.

**Reading:** Ran et al., *Nature Protocols* (2013), DOI `10.1038/nprot.2013.143`; Paquet et al., *Nature* (2016), DOI `10.1038/nature17664`.

## Core tool: `prepare_pcr_fragment`

**Callable:** `core.tools.amplification.prepare_pcr_fragment`

| Parameter | Type | Default | Meaning |
|---|---|---:|---|
| `template` | sequence input | required | Complete source `SeqRecord`, sequence or file. |
| `start` / `end` | `int` | required | 0-based half-open source interval; circular sources may wrap. |
| `fwd_tail` / `rev_tail` | `str` | `""` | 5-prime additions in forward-primer orientation. |
| `name` | `str` | `fragment` | Preparation row identifier. |
| `target_tm` | `float` | `60.0` | Ranking target; accepted complete cores are checked within 52–72°C. |

The result contains the actual sequence, `pcr`, `design`, complete primers and ordered `preparation` rows. If a tail would exceed the complete-oligo length limit, each successive PCR uses the preceding real product as its template and records the product and `annealing_temperature_hint_C`. A design failure remains a failure.

## Existing guide cassettes

**Callables:** `core.tools.grna.replace_grna_spacer`, `core.tools.grna.check_grna`. Both are registered atomic tools, discoverable with `describe_tools.py` and executable through `run_step`/Pipeline.

```python
replace_grna_spacer(vector_record_or_seq, spacer_seq,
    promoter_name=None, promoter_end_0based=None, transcription_strand=None,
    scaffold_seq="GTTTTAGAGCTAGAAATAGCAAGTTAAAATAAGGC")
check_grna(vector_record_or_seq, target_seq_or_file,
    promoter_name=None, promoter_end_0based=None, transcription_strand=None,
    scaffold_seq="GTTTTAGAGCTAGAAATAGCAAGTTAAAATAAGGC", pam_pattern="NGG")
```

Vector/target accept complete Molecules, records or files including `.dna`. `spacer_seq` is exactly 20 A/C/G/T bases in transcription orientation. Automatic location requires a directed promoter followed by exactly 20 bases and an actual scaffold anchor. Default anchor is the SpCas9 prefix shared with the published [pML104 method](https://pmc.ncbi.nlm.nih.gov/articles/PMC5868978/); scaffold suffix and vector name are not fixed. `scaffold_seq` accepts another anchor of at least 20 nt. Anchor matching does not certify full scaffold or promoter function.

`promoter_name` selects an exact annotation label/gene/product; multiple cassettes require a selector. For an unannotated source, `promoter_end_0based` is the promoter's 3-prime reference boundary: exclusive end on `+1`, start on `-1`. Supply `transcription_strand` with that boundary. Fuzzy/remote promoter positions are not accepted. Circular origin crossings retain ordered `spacer_parts_0based` and `scaffold_parts_0based`. Guide annotations do not determine transcription direction.

Replacement returns one same-length Molecule. `analysis.replacement` records before/after, strand and parts; `annotation_changes` retains every retired overlapping annotation with original coordinates/qualifiers. Nonoverlapping features and broad source metadata remain. Per-base values at replaced positions become unknown (`None`); other positions remain unchanged. New `misc_RNA` guide annotation records both spacer sequences. This is a sequence-model edit; physical preparation needs an actual supported PCR/assembly route.

Check returns analysis and a scoped check on original vector (`analysis.subject`), without a new product. `target_matches` retains every exact hit for transcribed spacer and its reverse complement, including invalid/incomplete PAMs. `strand` is reference strand **identical** to spacer; RNA binds `rna_binding_strand`, its opposite. PAM is read 5-prime to 3-prime on identical strand, immediately after 20 nt. `pam_pattern` is a 3-prime IUPAC motif; default `NGG` is for [wild-type SpCas9](https://www.addgene.org/guides/crispr/).

| `direction_status` | Meaning |
|---|---|
| `CORRECT` | Transcribed spacer has an exact PAM-compatible target |
| `REVERSED` | Only its reverse complement has a PAM-compatible target |
| `INVALID_PAM` | Exact hit exists, neither orientation has a compatible complete PAM |
| `NO_TARGET_MATCH` | Neither orientation has an exact hit; direction remains unknown |

Multiple valid loci and targets in both orientations remain explicit warnings; intended locus and uniqueness are not inferred. Guide annotation strand conflict says "Annotation may be incorrect (注释可能有误)" and does not reverse a sequence-supported conclusion. Results establish exact-match/PAM evidence only, not cutting efficiency or genome-wide/mismatch specificity.

Use `validate_construct.py product.gb --template original.dna --json` for QC origin. Inherited findings require identical extracted feature DNA, annotation metadata, location shape and diagnosis; pure coordinate shift is allowed. Same names alone do not establish inheritance. New/changed issues are `INTRODUCED_OR_CHANGED`; no template gives `UNDETERMINED`. Inherited ERR remains ERR with exit code 1 and `summary.pass=false`.

## Core tool: `prepare_pml104_guide`

**Callable:** `core.tools.crispr.prepare_pml104_guide`

| Parameter | Type | Default | Meaning |
|---|---|---:|---|
| `vector_record_or_seq` | `str \| pathlib.Path \| SeqRecord` | required | Complete circular pML104 template. |
| `spacer_seq` | `str` | required | Exactly 20 `A/C/G/T` bases in the guide orientation. |

The tool performs the pML104 inverse-PCR and KLD preparation route, restores the missing 5-prime guide-cassette sequence, and returns the circular product, complete preparation primers, and `scaffold_complete`. It does not prepend a generic U6 transcription G. Check the spacer and the full scaffold in the product before delivery. Primary method reference: [Hu et al. (2018)](https://pmc.ncbi.nlm.nih.gov/articles/PMC5868978/).

## 5. `recipe_site_directed_mutagenesis`  (alias: `recipe_point_mutagenesis`)

**Callable:** `core.recipes.mutagenesis.recipe_site_directed_mutagenesis`
**Returns:** `construct`, `complete_construct`
**Use for:** QuikChange mutagenic oligos or inverse-PCR mutagenesis.

### Signature parameters

| Parameter | Type | Default | Meaning |
|---|---|---:|---|
| `template_seq_or_file` | `str \| pathlib.Path \| SeqRecord` | required | Complete parental plasmid record or sequence. |
| `start_0based` | `int` | required | Half-open mutation start. |
| `end_0based` | `int` | required | Half-open mutation end. Equal boundaries insert. |
| `alt_seq` | `str` | required | Replacement or inserted DNA. |
| `target_flank_bp` | `int` | `15` | QuikChange flank length, bounded to 10–25 bp; inverse PCR minimum core length, bounded to 15–30 bp, with longer cores selected by shared Primer3 design. |
| `method` | `str` | `quikchange` | `quikchange` or `inverse_pcr`. Hyphens are normalized to underscores. |

`method="quikchange"` designs complete complementary mutagenic oligos and counts actual sequence differences against the original template. `method="inverse_pcr"` designs a full-plasmid PCR intermediate from the original circular template, then models circularization and verifies the resulting product. A QuikChange complementary pair is expected by that method; do not apply an unrelated generic dimer rejection rule as if the intended complementarity were a failed product.

Inverse PCR uses the shared anchored-primer search, complete-oligo structure checks and exact template simulation. It reports actual selected core lengths and Tm under the shared 50 nM oligo, 1.5 mM Mg and 0.6 mM dNTP calculation conditions. An unchanged-boundary search can have no solution; preserve the edit while choosing another supported preparation route. Fixed short flanks are not a verified primer design.

QuikChange source annotations now identify each oligo's exact 3-prime wild-type anchoring segment; the complete mutagenic oligo, mismatch count and whole-oligo QuikChange Tm remain separate. Preparation export replays the original reference window and actual complementary oligos, including circular-origin changes and indels, rather than treating the method as an unchecked exception. Automatic preparation replay supports PCR, inverse PCR and QuikChange; unknown method labels are rejected, not silently exported as verified products.

The source map shows the exact 3-prime anchor, not every mismatched annealing base. The remaining 5-prime sequence includes the other wild-type flank and the intended mutation; it is not solely an unpaired PCR overhang. Markdown uses the reported method Tm; missing temperatures are shown as not provided, never invented zero values. This sequence model does not establish amplification efficiency.

Inspect `details.preparation`, `details.pcr_evidence`, method-specific primer rows, the DpnI reminder, and the feature-preserving product. The source template must be the complete parental record, including when the edit crosses the circular origin.

**Reading:** Zheng et al., *Nucleic Acids Research* (2004), DOI `10.1093/nar/gnh110`; Green and Sambrook, Ch. 13; Agilent QuikChange instructions.

## 6. `recipe_protein_tagging`

**Callable:** `core.recipes.protein_tagging.recipe_protein_tagging`
**Returns:** `component`, `component_only`
**Use for:** in-frame tag, linker, and optional protease-site design.

### Signature parameters

| Parameter | Type | Default | Meaning |
|---|---|---:|---|
| `target_cds_seq_or_file` | `str \| pathlib.Path \| SeqRecord` | required | Complete target CDS record or sequence. |
| `tag_name_or_seq` | `str` | `6xHis` | Standard tag name or custom DNA sequence. |
| `tag_position` | `str` | `C-terminal` | `C-terminal` or `N-terminal`. |
| `linker_type` | `str` | `flexible_G4S_x2` | Standard linker key or custom DNA sequence. |
| `protease_cleavage` | `str \| None` | `None` | `TEV`, `PreScission`, or `Thrombin`. |
| `include_kozak` | `bool` | `False` | Prepend `GCCACC` when requested. |
| `terminal_stop_codon` | `str` | `TAA` | Stop codon appended when needed. |
| `protease_site` | `str \| None` | `None` | Compatibility alias used only when `protease_cleavage` is not supplied. |

The result is a design component, not a vector or a physical PCR product. Use it to define the desired fusion, then design PCR from the complete original CDS/vector source. Inspect the actual target start, stop handling, linker frame, and internal stops.

**Reading:** Terpe, *Applied Microbiology and Biotechnology* (2003); Kozak, *Cell* (1986); Waugh, *Protein Expression and Purification* (2011).

## 7. `recipe_cloning_verification`

**Callable:** `core.recipes.verification.recipe_cloning_verification`
**Returns:** `verification`, `qc_only`
**Use for:** junction PCR, Sanger primer placement, and optional diagnostic digest prediction.

QC候选必须唯一结合、核心Tm在52–72°C，并通过真实Primer3的单引物发夹/自二聚体检查。最终PCR对另做完整寡核苷酸配对检查；无可接受候选时不交不合格引物。默认结构阈值47°C沿用共享后端，不代表任何酶体系的实验保证。返回`complete_oligo_structure`和`sanger_oligo_structure`记录真实测量；亲本区分仍须另查。

### Signature parameters

| Parameter | Type | Default | Meaning |
|---|---|---:|---|
| `recombinant_plasmid_seq_or_file` | `str \| pathlib.Path \| SeqRecord` | required | Complete recombinant record or sequence. |
| `insert_start_0based` | `int` | required | Insert start in the recombinant record. |
| `insert_end_0based` | `int` | required | Insert end in the recombinant record. |
| `diagnostic_enzymes` | `list[str] \| None` | `None` | Optional enzymes for simulated diagnostic digest. |
| `max_pair_checks` | `int \| None` | `None` | Optional search budget; exhaustion is incomplete search, not no solution. |
| `background_templates` | `dict \| None` | `None` | Named actual parent templates; report exact PCR bands per template. |
| `sequencing_primers` | `list[dict] \| None` | `None` | Supplementary complete oligos as `{name, sequence}`; binding and structure are checked. |
| `read_length_bp` | `int \| None` | `None` | Assumed readable distance from primer 3prime end; no read data implied. |
| `read_trim_bp` | `int` | `30` | Initial bases excluded from coverage; caller must choose conditions appropriate to its service. |

Optional checks are in `RecipeResult.details`, or `ToolResult.analysis.details` after `run_step` adaptation. Background-positive PCR is a control finding, not failure of the construct. Ambiguous predictions remain UNKNOWN. Supplementary oligos failing default structure screening remain recorded; common final delivery rejects failed/incomplete QC quality. This screen does not establish experimental sequencing failure. Actual Sanger data and mismatch-tolerant/genomic off-target checks remain separate.

This recipe returns a QC design plus an annotated copy of the source, including `.dna` with the designed primers. It retains source topology and existing features. PCR length comes from full-template exact-match simulation; primers are restricted to the actual backbone and insert. It refuses ambiguous binding. If an upstream Sanger primer is unavailable, it tries a reverse primer facing the junction. The reported distance is measured from the real 3′ end. Short inserts can require a matched lower-Tm pair within 52–72°C. Parent discrimination is unchecked without supplied backgrounds; mismatch-tolerant off-target binding and actual experimental specificity remain unverified.

**Reading:** Green and Sambrook, Ch. 1 and Ch. 8; Sanger et al., *PNAS* (1977).
