# Kit architecture: verified Wiki paragraph

Scope: block K phase 2, independent development candidate. This is reusable architecture text, not a second installation guide or a completed Wiki publication.

## Text for Wiki

Genome Revival Toolkit is one installable Skill containing four manifest-owned sub-Skills: Construct, Genome Identity, Revival Evidence and CRISPR. Each Kit provides its own SKILL.md, kit.json, workflow code, sourced guidance and synthetic examples. The DNA Core supplies the local Kit runtime and the existing molecular tools; Evidence Trace records observed execution, checks, files and explicitly submitted explanations. Kits still depend on both components. The package copies the selected Core runtime from its single upstream source at build time, rather than maintaining a second DNA implementation.

Kit contributions reuse four existing interfaces: atomic tools, linear Pipeline execution, required Kit validation gates and the experience-rule grammar. CRISPR declares direction, PAM and supplied-vector self-target checks as required gates and loads its selection mappings from individually sourced rules. The four established workflows retain their conditional Kit code and currently do not use a contributed Pipeline template. That interface was demonstrated with a temporary external test Kit, which is excluded from the distribution.

Required Kit gates add checks within the selected Kit execution boundary. They do not replace original Core validation or authorize a host to bypass file receipts. An input-template diagnosis, including an inherited annotation error, may still block formal delivery; original findings and input/product provenance are retained. Explicit acceptance was demonstrated only for a test Kit's own sourced scope, with raw failure and an acceptance notice preserved. CRISPR enables no exemption. Acceptance of original Core inherited diagnoses has not been implemented.

Engineering evidence includes file-by-file migration comparison, retained rejected inputs, independent construction-defined synthetic sequences/PCR lengths/count arithmetic, public command-line execution, complete local regression with skips reported separately, and an empty-directory installation that runs all four Kits and checks saved files and English Trace reports. These are engineering and sequence-simulation results, not autonomous host-routing success or wet-lab validation. Official GitLab CI was not executed. GitHub CI, local tests and local candidate hash checks are identified separately.

## Evidence and publication boundary

The developer evidence owner is [phase 2 checkpoint](../kit-runtime-phase2-checkpoint-2026-10-14.md), with source contracts in [Core spec](../../specs/core-skill.md) and [Toolkit spec](../../specs/genome-revival-toolkit.md). Actual package/candidate hashes and the exact tested GitHub commit are recorded in the external delivery index; do not transfer historical results to a new source version.

Natural-language routing materials have been written but not executed by the developers. Handler/Recipe/schema contribution adapters, broader compatibility, original Core diagnostic acceptance and scientific experiments are future work and have not been performed. Enabling original Core acceptance first requires a user decision and independent verification across source/product versions, unrelated findings and public delivery routes. This branch has not been merged into main or any existing frozen candidate. This paragraph does not publish the Wiki or complete attribution, rights or AI-disclosure review.
