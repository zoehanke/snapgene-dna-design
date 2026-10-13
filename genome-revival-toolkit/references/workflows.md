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

## CRISPR plasmid preparation

`vector_reference` and `target_reference` select actual Context files. `operation` is `check` or `replace`; replacement additionally requires explicit `spacer_seq` of exactly 20 A/C/G/T bases. `promoter_name`, or explicit `promoter_end_0based`/`transcription_strand`, and `scaffold_seq` use the Core cassette selectors; no plasmid name or fixed position determines the edit. `target_tm` defaults to Core's 60°C; native single strands or incomplete circular templates cannot establish inverse-PCR preparation.

`transcription_promoter` is Core's `unspecified / human_U6 / other_pol_III / non_pol_III`, default `other_pol_III`. `max_mismatches` defaults to three for the supplied-vector NGG screen. Neither candidates nor mismatch counts are calibrated editing efficiencies or genome-wide specificity.

`strain_genotype` is an explicit object: `organism`, optional human-readable `description`, `existing_markers`, and `auxotrophies`. Empty lists are statements by the caller, not defaults inferred from a strain name. Missing genotype, relevant lists or host mappings remain UNKNOWN. E. coli and S. cerevisiae mappings cover documented marker families in `revival/selection.py`; every returned plate option carries its literature/manufacturer source. Marker names need complete actual CDS structure; function remains NOT_TESTED. Existing-marker conflicts, wrong auxotrophy and guide-sized false CDS annotations do not become successful selection advice.

Compatibility is scoped to the declared recipient. A bacterial propagation marker is NOT_APPLICABLE to a yeast recipient; its bacterial plate remains visible with UNKNOWN compatibility until that host's genotype is supplied. NatMX has the documented nourseothricin mapping. Unmapped recognized cassettes remain visible and unresolved. Generic APH labels do not identify a kanamycin determinant ([APH(6)-Id primary study](https://pmc.ncbi.nlm.nih.gov/articles/PMC3942886/)); tetR alone does not identify the resistance efflux gene ([Tn10 primary study](https://pmc.ncbi.nlm.nih.gov/articles/PMC216410/)). Neither is promoted to a supported plate by its name or an intact ORF.

Replacement records before/after, outside-window preservation, actual Core primer/condition data and independently simulated preparation. Route status PLANNED never means a completed PCR, DpnI, KLD, transformation or knockout. Formal DNA delivery uses Core's existing gate; failed/unresolved attempts retain candidate files and reports. `selection.tsv` and presented DNA files are bound to the Toolkit receipt, and `verify` detects later edits.

## Revival Evidence

`observations` rows have unique `id`, `group`, `colonies` and optional `plated_cells`, `role`, `source` and experimental conditions. Missing counts stay missing. `observations_file` accepts UTF-8 CSV with these columns, resolved relative to request JSON. Totals and normalised yields are descriptive counts, not revival rates. The explicit role `inactivated_donor_control` permits checking whether reported outgrowth contradicts absence of donor-control growth.

Optional `comparisons` specify existing `experiment_group` and `control_group`. `genotype_results` specify `sample_id`, supplied `reference_id`, `result: positive/negative/indeterminate/not_tested`, and reported `control_status: passed/failed/unknown`, plus source/assay details. A supported selected-marker observation does not establish whole-genome absence. Contradictory submitted results remain visible.

No primary data means no fabricated measurements. The workflow reports supplied observations, their scope and `SUPPORTED / INSUFFICIENT / CONTRADICTED / NOT_TESTED` conclusions where applicable; zero colonies mean no reported outgrowth, not proven death. Revival and entire-genome elimination require evidence beyond the supported local record analysis.
