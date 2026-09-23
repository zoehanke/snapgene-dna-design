# SnapGene DNA Design: software page draft

**Draft for Tianjin 2026. Not published.** Replace team-owned project context and external evidence only with verified material. Target page: https://2026.igem.wiki/tianjin/software. Official software repository: pending team confirmation.

## Problem and contribution

AI-assisted DNA design combines natural-language choices with precise sequence operations. A plausible explanation is insufficient if primers, boundaries, annotations or output files are wrong. Motivated by the team's yeast-genome project, this tool separates host-authored intent from executable sequence computation and records the evidence available for review.

The contribution is an agent-accessible local toolkit with standard construction recipes, composable operations, annotated artifacts, explicit validation and an accompanying Evidence Trace. It is not a model service or an autonomous biosafety authority.

## Design and architecture

The host supplies structured parameters. Recipes handle preparation workflows; ConstructionTask handlers build declared sequence/annotation models; explicit Pipelines compose actual tools. The runtime checks saved artifacts, recomputation and requested components before authoritative delivery. Specialized sequence models do not by themselves establish a physical preparation route.

Evidence Trace observes tool inputs, results, failures and file versions. The host/researcher organizes scientific choices and sources. Deterministic code checks references and generates offline HTML/Markdown without a fresh model call. Source verification, evidence applicability and scientific correctness remain separate.

[Architecture and control-flow figure](../../results/engineering-audit-20260922/architecture.svg), corresponding to the documented module boundaries. The reproducible demo supplies the concrete preparation and file lineage; it must be shown with its actual parameters.

## User workflow and interoperability

Users begin with their available materials and desired result. Existing suitable material may be reused. New work uses a supported Recipe or explicit Pipeline, retains actual intermediates and complete primers, and distinguishes components, candidates, QC designs and authoritative files.

The toolkit exchanges GenBank, FASTA and native SnapGene files through documented Python/CLI interfaces. It preserves structured feature locations and strand conventions. SBOL support is not implemented. Primer3 is a real external computation backend; local model scoring and Cas-OFFinder have separate availability and interpretation limits. See docs/integration.md and the standards table.

## Engineering and validation

The audit found failures despite a green test suite: lost annotations, exceptional validation left marked successful, ignored component requirements, misleading capture and output behavior. Repairs preserve the original failing evidence and add independent valid/invalid cases. Final quantitative results are in docs/validation.md and results/engineering-audit-20260922; they must be displayed with their skips and scope.

The 90 scenario suite contains 40 executed cases, 11 partial analyses and 39 intended blocks. This is evidence of execution contracts, not 90 successful biological constructs. Local runtime measurements use three repetitions and synthetic inputs; their purpose is reproducibility and observed cost, not claims of user efficiency or biological success.

[FIGURE: results/engineering-audit-20260922/runtime-comparison.svg]
[Actual synthetic output map](../../results/engineering-audit-20260922/demo-construct-map.svg). This is generated from the delivered DNA, not a desktop SnapGene screenshot.
[Actual Evidence Trace screenshot](../../results/engineering-audit-20260922/trace-desktop.png), with [narrow-window view](../../results/engineering-audit-20260922/trace-narrow.png). Interaction checks are recorded separately; these images do not establish user comprehension.

## Evidence Trace and responsible use

The module helps readers distinguish requests, choices, sources, conditions, actual checks and remaining gaps. Unknown dependency is not no impact. A record of a reason does not authenticate the model's internal motivation. A successful local sequence check does not establish expression, genome-wide specificity or ecological safety.

The module supports review and communication; institutional review, applicable iGEM safety processes and experimental decisions remain separate. No safety score or safe/unsafe verdict is produced.

## Reproducibility, results and limitations

Use docs/installation.md and docs/quick-start.md, then run the predesigned engineering demo. Source, parameters and actual files are retained together. The demo's requests/routes are explicitly preselected; only program results are measured.

Independent user-task completion, expert review and wet-lab outcomes remain missing. Source annotation errors and limited reaction/host observation models constrain claims. A recent automated SnapGene roundtrip retained sequence/topology/features but introduced qualifier defaults, so it was not strictly identical.

[DATA REQUIRED: independent users, expert feedback and relevant laboratory outcomes]

## Availability and attribution

Original project code uses MIT; third-party models and external executables retain their licenses. External regression DNA and supplied reference images need separate redistribution review. See docs/attribution.md. GitHub is the development source; the official dedicated iGEM GitLab URL and submission receipt require team action. Record student, external and AI contributions in the official Attributions process.

Future work should respond to measured use and actual evidence gaps. It must not expand the record system into unsupported biological or ecological certification. Official criteria and references are linked in docs/igem/official-requirements.md; scientific methods are sourced in references/recipes.md.
