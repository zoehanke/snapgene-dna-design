# Objective Biological Guardrails Specification (`core/guardrails/`)

The guardrails subsystem (`core/guardrails/checklist.py`) performs automated, factual sanity checks across 10 essential biological quality gates (`BIO-01` through `BIO-10`).

Unlike arbitrary policy engines, these checks:
1. **Respect Applicability**: Distinguish whether an input is a coding CDS, a linear PCR amplicon, an ssODN donor, or a circular plasmid construct.
2. **Standardized Status**: Every check reports one of four explicit states:
   - `PASS`: The check was applicable and satisfied all biological criteria.
   - `FAIL`: The check was applicable and detected a biological defect.
   - `N/A`: The check is not applicable to the current biological scenario (e.g. Kozak check on bacterial plasmid, replicon check on linear PCR fragment).
   - `UNKNOWN`: Insufficient sequence or metadata to determine status.
3. **Acceptance Rule**: `all_applicable_pass = (no FAIL and no UNKNOWN)`.

---

## The 10 Biological Guardrails

### BIO-01: Reading Frame & Premature Stop Codons (`BIO-01-FRAME`)
- **Applicability:** Applicable when `is_cds=True` (or explicitly annotated CDS features on a plasmid). Non-coding backbones, promoters, and whole plasmids are evaluated as `N/A`.
- **Rule:** Length must be divisible by 3 ($\text{length} \pmod 3 == 0$), and translation must contain zero premature stop codons prior to the terminal codon.
- **Citation:** Crick, F.H. et al. (1961). *General nature of the genetic code for proteins*. Nature, 192, 1227–1232.

### BIO-02: Stop Codon Integrity (`BIO-02-STOP`)
- **Applicability:** Applicable when `is_cds=True` and expressing a stand-alone protein or C-terminal fusion.
- **Rule:** Sequence must terminate with a canonical stop codon (`TAA`, `TAG`, `TGA`). When designing C-terminal fusions, the upstream partner's stop codon must be stripped to preserve translational continuity into the downstream tag.
- **Citation:** Terpe, K. (2003). *Overview of tag protein fusion*. Appl Microbiol Biotechnol, 60(5), 523–533.

### BIO-03: Internal Restriction Cut Conflicts (`BIO-03-ENZYME`)
- **Applicability:** Applicable when restriction enzymes are specified for cloning or digestion (`cloning_enzymes` provided).
- **Rule:** The insert or vector must not contain internal recognition sites for the selected cloning enzymes that would cause unwanted fragmentation during digestion.
- **Citation:** Sambrook, J. and Russell, D.W. (2001). *Molecular Cloning* (3rd ed.). CSHL Press. Chapter 1.

### BIO-04: Strand & Orientation Consistency (`BIO-04-STRAND`)
- **Applicability:** Applicable to all sequence operations and assemblies.
- **Rule:** Coordinates ($0 \le \text{start} \le \text{end} \le N$) and strand annotations ($+1$ or $-1$) must be strictly self-consistent and valid within the template sequence length.

### BIO-05: CRISPR In Vivo Re-cleavage Prevention (`BIO-05-RECLEAVAGE`)
- **Applicability:** Applicable to CRISPR-Cas9 HDR donor template designs.
- **Rule:** The donor repair template must mutate the PAM site (`NGG` -> `NGN`) or sgRNA seed region (proximal 8–12 bp) to prevent Cas9 from re-cutting the successfully repaired genomic locus. In coding sequences, mutations MUST be synonymous (silent).
- **Citation:** Paquet, D. et al. (2016). *Efficient introduction of specific homozygous and heterozygous mutations using CRISPR/Cas9*. Nature, 533, 125–129.

### BIO-06: RNA Pol III (U6) Poly-T Termination (`BIO-06-POL3_TERMINATION`)
- **Applicability:** Applicable when designing sgRNA cassettes or shRNA constructs under human/mouse U6 or H1 Pol III promoters.
- **Rule:** Sequences must not contain 4 or more consecutive thymidines (`TTTT`), which acts as an intrinsic transcription termination signal for mammalian RNA Polymerase III.
- **Citation:** Goomer, R.S. and Kunkel, G.R. (1992). *The transcriptional start site for a human U6 small nuclear RNA gene is dictated by a TATA box inserted in an indispensable distal control region*. Nucleic Acids Res, 20(18), 4903–4912.

### BIO-07: PCR Primer 3' Dimer Risk (`BIO-07-PRIMER_DIMER`)
- **Applicability:** Applicable when primer pairs are designed or evaluated.
- **Rule:** Primer pairs must not form severe 3'-terminal complementary duplexes ($\ge 4\text{–}5\text{ bp}$ or $\Delta G \le -9.0\text{ kcal/mol}$), which cause primer-dimer amplicons and reaction failure.
- **Citation:** SantaLucia, J. (1998). *A unified view of polymer, dumbbell, and oligonucleotide DNA nearest-neighbor thermodynamics*. PNAS, 95(4), 1460–1465.

### BIO-08: Replicon & Selection Marker Presence (`BIO-08-REPLICON_MARKER`)
- **Applicability:** Applicable to circular plasmid constructs (`topology="circular"`). Linear fragments, primers, and oligos are evaluated as `N/A`.
- **Rule:** A circular plasmid destined for bacterial transformation and maintenance must possess at least one functional origin of replication (e.g. pUC, ColE1, p15A, SC101, F1) and at least one selectable marker (e.g. AmpR/bla, KanR/neo, CmR/cat, TetR, SpecR).
- **Citation:** Sambrook, J. and Russell, D.W. (2001). *Molecular Cloning* (3rd ed.). CSHL Press. Chapter 1: Plasmids and Their Useful Features.

### BIO-09: Dam/Dcm Methylation Cut Blockade (`BIO-09-METHYLATION`)
- **Applicability:** Applicable when restriction enzymes are specified.
- **Rule:** Flags methylation-sensitive enzymes (e.g. `ClaI`, `XbaI`, `BclI`, `StuI`) whose recognition sequences overlap with bacterial Dam (`GATC`) or Dcm (`CCWGG`) methylation sites, causing cleavage failure in standard *E. coli* cloning strains (`dam+/dcm+`).
- **Citation:** Marinus, M.G. and Morris, N.R. (1973). *Isolation of deoxyribonucleic acid methylase mutants of Escherichia coli K-12*. J Bacteriol, 114(3), 1143–1150.

### BIO-10: Extreme Long Inverted Repeats & Complexity (`BIO-10-HAIRPIN_REPEAT`)
- **Applicability:** Applicable to long synthetic constructs and viral packaging vectors (AAV, Lentivirus).
- **Rule:** Detects inverted repeats ($\ge 30\text{ bp}$) and extreme GC clusters ($\ge 85\%\text{ GC}$ in a 50 bp window) that stall replication forks, trigger host SbcCD-mediated deletion, or cause commercial gene synthesis vendor rejection.
- **Citation:** Leach, D.R. (1994). *Long DNA palindromes, cruciform structures, genetic instability and secondary structure formation*. BioEssays, 16(12), 893–900.
