---
name: "snapgene-dna-design"
description: "SnapGene-compatible DNA plasmid design and molecular biology engineering skill. Inspects plasmids, designs PCR primers, runs isothermal Gibson assembly, restriction cloning, Golden Gate, CRISPR HDR donors, site-directed mutagenesis, in-frame protein tag fusions, and colony verification QC. Exports verified native SnapGene (.dna), GenBank (.gb), and FASTA files. Invoke whenever the user asks to design, inspect, clone, mutate, tag, or verify plasmids and DNA sequences."
---

# SnapGene DNA Design Skill

A rigorous, production-grade molecular biology and plasmid design skill runtime for AI coding assistants (Codex, Claude Code, Antigravity, Cursor, ChatGPT).

## Architectural Principles

1. **Host LLM is the Sole Brain**: You (the LLM in the user's chat window) converse naturally with researchers, understand experimental goals, inspect plasmid features, and select design strategies.
2. **Skill Runtime Provides Hands & Quality Gates**:
   - **Atomic Tools (`core/tools/`)**: 38 pure, deterministic biological operations registered in `TOOL_REGISTRY`.
   - **Standard SOP Recipes (`core/recipes/`)**: 7 gold-standard laboratory SOPs backed by authoritative literature.
   - **Biological Guardrails (`core/guardrails/`)**: Applicability-aware factual audits (`BIO-01 ~ BIO-10`) reporting `PASS`, `FAIL`, `N/A`, or `UNKNOWN`.
   - **Authoritative Gate (`core.runtime_gate`)**: Cryptographic SHA-256 hash chains separating draft candidates (`candidate/`) from officially signed deliverables (`authoritative/`).

---

## The 5-Step Operational Loop

Always follow this 5-step loop when assisting researchers with plasmid design tasks:

```text
┌─────────────┐     ┌────────────────┐     ┌──────────────┐     ┌────────────┐     ┌──────────────┐
│  1. INSPECT │ ──► │  2. ALIGN INTENT│ ──► │ 3. ROUTE/RUN │ ──► │  4. AUDIT  │ ──► │ 5. DELIVER   │
│ plasmid maps│     │ with user      │     │ Recipe/Pipe  │     │ Guardrails │     │ Sign Off     │
└─────────────┘     └────────────────┘     └──────────────┘     └────────────┘     └──────────────┘
```

### Step 1: Inspect Plasmid Maps & Sequences
Never guess coordinates, features, or sequence lengths. Immediately run `scripts/inspect_plasmid.py`:

```bash
python scripts/inspect_plasmid.py <vector_file> [<insert_file>]
```
- Inspects length, topology (`circular` / `linear`), and GC%.
- Identifies replication origins (`ori`) and selectable antibiotic markers.
- Audits CDS reading frames (verifying `length % 3 == 0` and absence of premature stops).
- Identifies unique single-cut restriction enzyme sites (candidate MCS insertion sites).

### Step 2: Clarify & Align Intent
Discuss requirements conversationally with the researcher before running irreversible calculations:
- For **Protein Tagging**: Confirm N-terminal vs C-terminal fusion, linker type (`G4S`, `EAAAK`), and protease site (`TEV`, `PreScission`, `Thrombin`).
- For **Restriction Cloning**: Confirm candidate unique enzyme pairs and ensure no internal cuts exist in the insert.
- For **Gibson Assembly**: Confirm target linearized insertion junction and overlap length (default 22 bp).
- For **CRISPR HDR**: Confirm cut site coordinate, donor payload, and synonymous PAM silencing strategy.

### Step 3: Route & Execute
Select the appropriate execution route:

#### Route A: Standard Laboratory Recipes (Recommended)
For standard molecular biology workflows, run `scripts/run_recipe.py`:

```bash
# Example: Gibson Assembly
python scripts/run_recipe.py --recipe recipe_gibson_assembly --params-json params.json --out-dir ./build

# Example: Protein Tagging
python scripts/run_recipe.py --recipe recipe_protein_tagging --params '{"target_cds_seq_or_file": "ATG...", "tag_name_or_seq": "6xHis", "tag_position": "C-terminal"}' --out-dir ./build
```

**The 7 Standard SOP Recipes:**
| Recipe Name | Result Kind | Completeness | Key Literature Citation |
| :--- | :--- | :--- | :--- |
| `recipe_gibson_assembly` | `construct` | `complete_construct` | Gibson et al. (2009) *Nat Methods* |
| `recipe_restriction_cloning` | `construct` | `complete_construct` | Sambrook & Green (2012) *Mol Cloning* |
| `recipe_golden_gate` | `construct` | `complete_construct` | Engler et al. (2008) *PLoS ONE* |
| `recipe_crispr_hdr_donor` | `component` | `component_only` | Paquet et al. (2016) *Nature* |
| `recipe_site_directed_mutagenesis` | `construct` | `complete_construct` | Zheng et al. (2004) *NAR* (alias: `recipe_point_mutagenesis`) |
| `recipe_protein_tagging` | `component` | `component_only` | Terpe (2003) & Kozak (1986) *Cell* |
| `recipe_cloning_verification` | `verification` | `qc_only` | Sanger et al. (1977) *PNAS* |

*For complete parameter definitions, see [references/recipes.md](references/recipes.md).*

#### Route B: Custom Composite Pipeline
For non-standard, multi-step, or exploratory pipelines, formulate a JSON pipeline and run `scripts/run_pipeline.py`:

```bash
python scripts/run_pipeline.py --pipeline pipeline.json --out-dir ./build
```
Any of the 38 atomic tools registered in `TOOL_REGISTRY` (e.g. `digest_sequence`, `simulate_pcr`, `simulate_overlap_assembly`, `extract_subsequence`, `mutate_sequence`) can be dynamically chained.

### Step 4: Audit Biological Guardrails
Every execution automatically evaluates the 10 biological guardrails (`BIO-01` to `BIO-10`):
- `BIO-01-FRAME`: Reading frame continuity (multiple of 3, zero premature stops).
- `BIO-02-STOP`: Canonical terminal stop codon present (`TAA`/`TAG`/`TGA`).
- `BIO-03-ENZYME`: Zero internal restriction cuts by selected cloning enzymes.
- `BIO-04-STRAND`: Self-consistent coordinate boundaries and strands.
- `BIO-05-RECLEAVAGE`: Synonymous mutation to disable Cas9 PAM re-cleavage.
- `BIO-06-POL3_TERMINATION`: No consecutive `TTTT` motifs in U6 Pol III cassettes.
- `BIO-07-PRIMER_DIMER`: PCR primer pairs free from severe 3'-terminal dimers.
- `BIO-08-REPLICON_MARKER`: Circular plasmids contain functional ori and antibiotic marker.
- `BIO-09-METHYLATION`: Flags Dam/Dcm methylation blockade on sensitive enzymes.
- `BIO-10-HAIRPIN_REPEAT`: Flags extreme inverted repeats ($\ge 30$ bp) and high-GC clusters.

*For detailed evaluation criteria, see [references/guardrails.md](references/guardrails.md).*

### Step 5: Deliver Verified Constructs
1. **Present Results**: Output the designed primer table (sequences, Tm, lengths), quality checks, and step-by-step laboratory protocol to the researcher.
2. **Authoritative Promotion**: When the researcher explicitly confirms the design, promote candidate artifacts into `authoritative/` by passing `--finalize --confirmed`:

```bash
python scripts/run_recipe.py --recipe <name> --params-json <params.json> --out-dir ./build --finalize --confirmed
```
This generates:
- `authoritative/construct.dna`: Native binary SnapGene plasmid file (with features, colors, primers).
- `authoritative/construct.gb`: Fully annotated GenBank file.
- `authoritative/construct.fasta`: High-fidelity FASTA nucleotide sequence.
- `authoritative/DELIVERY-MANIFEST.json`: Cryptographically hashed manifest recording full provenance and guardrail audits.

### CLI Conventions
- 大多数脚本支持 `--json` 输出结构化数据，供自动化解析与大模型集成。

