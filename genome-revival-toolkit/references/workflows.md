# Workflow inputs

All intervals are 0-based half-open on `context.material(reference_id)`, including a selected region. Context material paths resolve relative to its JSON file. Explicit `record_id` selects a multi-record file; a single native record's ID is checked, not parsed as FASTA. Actual hashes and declared strain/source/version stay separate.

## Shared Context and request

Context uses `schema_version: genome-revival-context-v1`, `project`, `strains`, `references`, optional source-labelled `facts` and `routes`. Each reference has `path`; optional fields are `record_id`, `topology`, `strain_id`, `declared_version`, `source`, `sha256` and `region: {start0, end0, strand}`. Fasta chromosome topology should be explicit. The packaged template has no research material.

Each request has nonempty `original_request`. Optional `title` affects the report. Optional `decisions` contain explicitly submitted `text`, `rationale`, `actor: user/ai/unknown`, `origin: user_statement/ai_concurrent/unknown`, optional `kind`, `basis_references` and `limitations`. Submit contemporaneous public notes with the design request; source attribution is declared, not authenticated. Missing reasoning stays missing.

## Construct

Required: `method: integration_donor`, `target_reference`, `cargo_reference`, `target_interval`, `cargo_interval`, positive integer `arm_length`. Empty target interval means insertion; cargo must be explicitly nonempty. Both arms must exist in the selected linear target reference. Genomic intervals are not guessed from a gene or strain name.

`preparation_method: pcr` additionally needs `donor_template_reference` and `donor_interval`: amplify a real existing donor template, then check against the independent reference/cargo model. `gibson` prepares and assembles real left/cargo/right fragments with the existing Recipe; `assembly_overlap_bp` defaults to its 22 bp overlap, supported 15–35 bp. Failure does not silently select another route. Both donor boundaries get actual QC and unedited-reference predictions. This is donor verification, not evidence of genomic integration.

`requirements` may add the Core's supported executable goals. They cannot remove the workflow's structural and preparation requirements. Missing source data, annotations incompatible with the actual product, or failed full-oligo quality remain incomplete/failed.

## Genome Identity

`references` lists selected Context IDs, defaulting to all. `compare_regions` defaults true; `alignment_mode` is global/local using the existing bounded Core comparator. Large genomes need explicit regions for pairwise alignment. Best local alignment does not certify unique placement.

`assays` contains `id`, full `forward`/`reverse` A/C/G/T oligos, optional explicit `forward_binding_core_length`/`reverse_binding_core_length` for declared tails, `annealing_temperature_C`, `size_resolution_bp`, and `expected` mapping reference IDs to `AMPLICON`/`NO_EXACT_PRODUCT`. Without a supplied tail, the full oligo must bind exactly. Missing binding, ambiguity and other calculation failures are distinguished. Full-oligo QC remains required and backend failure remains incomplete.

Alternatively `design_assays` contains `id`, `target_reference`, `interval`, optional `target_tm` (Core default 60°C), `annealing_temperature_C`, `size_resolution_bp` and `expected`. The program designs at those explicit interval ends, checks complete oligos, and predicts each reference. An unsuitable candidate may need different valid boundaries; failure of one interval is not proof that no assay exists. Size discrimination needs declared resolution; experimental band separation remains unverified.

## Revival Evidence

`observations` rows have unique `id`, `group`, `colonies` and optional `plated_cells`, `role`, `source` and experimental conditions. Missing counts stay missing. `observations_file` accepts UTF-8 CSV with these columns, resolved relative to request JSON. Totals and normalised yields are descriptive counts, not revival rates. The explicit role `inactivated_donor_control` permits checking whether reported outgrowth contradicts absence of donor-control growth.

Optional `comparisons` specify existing `experiment_group` and `control_group`. `genotype_results` specify `sample_id`, supplied `reference_id`, `result: positive/negative/indeterminate/not_tested`, and reported `control_status: passed/failed/unknown`, plus source/assay details. A supported selected-marker observation does not establish whole-genome absence. Contradictory submitted results remain visible.

No primary data means no fabricated measurements. The workflow reports supplied observations, their scope and `SUPPORTED / INSUFFICIENT / CONTRADICTED / NOT_TESTED` conclusions where applicable; zero colonies mean no reported outgrowth, not proven death. Revival and entire-genome elimination require evidence beyond the supported local record analysis.
