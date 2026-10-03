# SnapGene DNA Design

**v1.0.4 · 通用制备重放与评测资格修复。** [本轮审查](docs/development-plans/general-capability-audit-v1.0.4.md) · [前版说明](docs/RELEASE-v1.0.3.md) · [真实任务评分](docs/question-bank/scoring-v0.1.md)。当前证据为开发回归和非隔离试用，没有通用任务成功率提高结论。Historical v1.0.0 scope: [release notes](docs/RELEASE-v1.0.0.md).

New contributors: read [project history](docs/history.md) for the decisions and feedback behind this design, [current specs](specs/core-skill.md) for the product contract, and [development plans](docs/development-plans/README.md) for implementation status.

Current development provides **Evidence Trace v0.3.2** beside the DNA runtime: capture real calls/files, explicitly submit a host-authored design process and report plan, then generate offline HTML/Markdown from those saved records. The seven entry points cover design, inspection, primer annotation, conversion and preview export. Missing/stale organization is visible; normal Trace faults preserve DNA execution. See [usage and limits](references/evidence-trace.md) and the [current plan](docs/development-plans/workflow-phase-3-usability-repair-v0.3.2.md). Development defaults to full; semantic fidelity and independent human readability remain distinct from program/reference checks. This does not replace the historical v1.0.0 release or certify safety.

A skill runtime for plasmid design, PCR, cloning, mutagenesis and local CRISPR/HDR designs. The host assistant chooses a route; the runtime computes reactions and exports annotated GenBank and SnapGene files.

Use complete source records and follow the actual preparation chain. Every assembled fragment must come from a supplied prepared fragment, a simulated PCR using the delivered primers, or an explicit digest. A theoretical fusion or edited sequence is a design component, not a stock PCR template. See [Recipe parameters](references/recipes.md).

## Key Architecture & Philosophy

- **Host LLM as the Intelligent Brain**: The chat assistant understands user intent in natural language, explores biological strategies, and aligns with the researcher.
- **Skill Runtime as Hands & Feet**:
  1. **Plasmid Map Inspection (`scripts/inspect_plasmid.py`)**: Fast, token-efficient extraction of plasmid topology, origins, markers, CDS reading frames, and unique cloning cutters.
  2. **7 Recipe modules (`scripts/run_recipe.py`)**: Gibson, restriction cloning, Golden Gate, CRISPR HDR, mutagenesis, protein tagging and cloning verification, with method references and explicit preparation outputs.
  3. **41 registered tools & composite pipelines (`scripts/run_pipeline.py`)**: Compose supported sequence, PCR and digestion operations while retaining annotated records.
  4. **Biological checks (`BIO-01 ~ BIO-10`)**: `PASS`, `FAIL`, `N/A`, or `UNKNOWN`. Complete CDS stop checks apply on circular and linear records; exemptions require explicit partial-feature evidence.
  5. **Delivery checks (`finalize`)**: Promote candidates with explicit passing evidence into `authoritative/` (`.dna`, `.gb`, `.fasta`, `DELIVERY-MANIFEST.json`). Hashes track file integrity; biological correctness also depends on the preparation chain and functional context.

---

### Quick Start

先安装 `python -m pip install -r requirements.txt`，在仓库根目录运行：

```text
python -X utf8 -B scripts/check_env.py --json
python -X utf8 -B scripts/run_recipe.py --recipe recipe_protein_tagging --params-json fixtures/synthetic/tagging_params.json --out-dir output/quick-start --json
```

产出是合成教学 CDS 的带标签 **component**，不是已验证的完整表达质粒。详见[快速开始](docs/quick-start.md)、[用户指南](docs/user-guide.md)、[安装](docs/installation.md)及[排障](docs/troubleshooting.md)。

开发者先读[架构](docs/architecture.md)、[数据流](docs/data-flow.md)、[开发指南](docs/developer-guide.md)。本周期的[工程审计](docs/audit-report.md)、[修复计划](docs/remediation-plan.md)、[最终报告](docs/final-remediation-report.md)区分已实现、已验证和外部缺口。iGEM Tianjin 2026 材料见[提交清单](docs/igem/submission-checklist.md)，不代表已经提交。

---

## Table of contents

1. [Feature overview](#1-feature-overview)
2. [Installation and dependencies](#2-installation-and-dependencies)
3. [CLI command reference](#3-cli-command-reference)
4. [Usage examples](#4-usage-examples)
5. [v0.9 assembly planning and CRISPR workflow](#5-v09-assembly-planning-and-crispr-workflow)
6. [Data formats and schemas](#6-data-formats-and-schemas)
7. [Validation, tests and release gates](#7-validation-tests-and-release-gates)
8. [90-scenario literature validation](#8-90-scenario-literature-validation)
9. [Known limitations](#9-known-limitations)
10. [Roadmap](#10-roadmap)
11. [License and third-party notices](#11-license-and-third-party-notices)

---

## 1. Feature overview

| Area | Scripts / modules | Capability |
|---|---|---|
| Read & analyze | `parse_dna.py`, `analyze_seq.py`, `align_seq.py`, `align_sanger.py`, `msa.py`, `assemble_contig.py` | Parse SnapGene/GenBank/FASTA/EMBL; stats, reverse complement, translation; global/local alignment; Sanger consensus; MSA; contig assembly |
| Restriction enzymes | `find_sites.py` | Recognition sites and simulated digests; explicit double-strand cut boundaries |
| PCR / primers | `design_primers.py`, `primer_design_engine.py`, `primer3_core_backend.py`, `primer_qc.py`, `simulate_pcr.py`, `pcr_strategy.py`, `core.tools.amplification.prepare_pcr_fragment` | Exact-boundary primer design; complete oligo structure QC; core Tm accepted in the 52–72°C window with 60°C as a ranking target; long additions split into real successive PCR steps with actual templates, intermediates and `annealing_temperature_hint_C`; tails / restriction sites / protective bases; PCR simulation; GC/AT/long-template strategies |
| Consent & transparency | `operation_consent.py` | Structured confirmation for parameters, relaxations, degradations, no-solution and external writes; `--consent ask/auto`, `--yes`; unconfirmed = not executed; append-only operation log (backend, parameters, input SHA, retry path, output files) |
| Recipes and tools | `core/recipes/*`, `core/tools/*`, `core/guardrails/*`, `core/task.py` | 7 recipes, 41 registered tools, and method-specific biological checks |
| Cloning simulation | `simulate_cloning.py`, `simulate_advanced.py`, `golden_gate.py` | Gibson / digest-ligate; In-Fusion, TA, TOPO, Gateway BP/LR; Type IIS Golden Gate |
| Plasmid editing | `edit_plasmid.py`, `mutagenesis.py`, `annotate.py`, `draw_map.py`, `convert.py`, `write_dna.py` | Insert/delete/replace/rotate/linearize; site-directed mutagenesis and codon edits; ORF annotation; SVG maps; format conversion; GenBank / SnapGene-GB / native `.dna` / FASTA export |
| Validation | `validate_construct.py`, `validate_roundtrip.py`, `validation_crosscheck.py` | One-shot QC (topology/length/CDS stops/unique cutters); internal and official SnapGene round-trip; independent Tm / restriction / GC cross-checks |
| CRISPR design | `design_guides.py`, `guide_scoring.py`, `cas_offinder_adapter.py`, `annotate_offtargets.py`, `generate_crispr_design_report.py` | PAM-rule scanning in reference coordinates; Azimuth V3 (Doench 2016) and DeepCpf1 (Kim 2018) real scoring; Cas-OFFinder v2/v3 real off-target search; feature-overlap annotation; unified JSON/Markdown report |
| v0.9 planning | `plan_assembly.py`, `planning/`, `rules/`, `primer_design_engine.py` | Multi-source fragment assignment → assembly method decision → primer list → feasibility filter → build manual |
| Data & provenance | `provenance.py`, `protocol_evidence.py`, `parts_library.py`, `online_sources.py`, `sequence_upload_consent.py` | Versioned provenance sources; manufacturer protocol evidence; parts registry; NCBI eUtils live query; Addgene official-page link helper (no record lookup); explicit offline degradation; bound one-time upload consent |
| Packaging & gates | `build_release.py`, `check_redistributable.py`, `coverage_gate.py`, `mutation_tests.py`, `property_tests.py`, `run_test_suite.py`, `run_scenario_suite.py` | Reproducible academic/redistributable ZIPs; restricted-content hash checks; coverage/mutation/property release gates; 90-scenario literature suite with human-readable report |

Coordinates: user-facing CLI positions are **1-based closed** for legacy tools
(primers/edits); the v0.8/v0.9 CRISPR and planning layers use **0-based
half-open** coordinates on the input reference axis and explicitly label the
coordinate system in every result.

---

## 2. Installation and dependencies

### 2.1 Core requirements

Python 3.10+ on Windows/macOS/Linux.

```bash
pip install -r requirements.txt
```

Core dependencies:

- `biopython==1.88`
- `snapgene_reader==0.1.23`
- `sgffp==0.21.0`
- `jsonschema>=4.17,<5`
- `primer3-py>=2.3.0` for the bundled `primer3_core` discovery path

### 2.2 Optional dependencies

```bash
pip install -r requirements-optional.txt
```

| Dependency | Used for |
|---|---|
| `numpy`, `pandas`, `matplotlib`, `scikit-learn` | Azimuth V3 feature calculation and model inference |
| `torch`, `h5py` | DeepCpf1 inference |
| Cas-OFFinder binary | Real genome off-target search. BSD-3-Clause; download from `https://github.com/snugel/cas-offinder/releases` and pass `--cas-offinder` / `CAS_OFFINDER_EXE`. |

### 2.3 External programs

| Program | How it is used | Fallback |
|---|---|---|
| `primer3_core` (required for main primer design) | `PRIMER3_CORE` env var, `--primer3-core`, PATH, or primer3-py wheel discovery | `design_primers.py` / `primer_design_engine.py` explicitly label heuristic results as **NOT Primer3** |
| `cas-offinder` | `--cas-offinder` / `CAS_OFFINDER_EXE` | structured `unavailable` result |
| `SnapGene.exe` (Windows, e.g. `D:\SnapGene\SnapGene.exe`) | `validate_roundtrip.py --snapgene-exe` official conversion | internal round-trip only |
| Internet access | `online_sources.py` NCBI eUtils / Addgene | explicit `offline-unverified` |

Environment check:

```bash
python scripts/check_env.py
```

---

## 3. CLI command reference

All commands are run from the repository root. Most commands support `--json`
for machine-readable output. Failure envelopes use
`{"schema_version","ok","command","data","warnings","error"}` (legacy) or the
native v0.8/v0.9 schema for the newer CRISPR/planning commands.

### 3.1 Read, analyze, annotate

```text
python scripts/parse_dna.py <file> [--seq-limit N] [--json]
python scripts/analyze_seq.py <file> {stats|revcomp|translate} [--frame 1..6] [--json]
python scripts/align_seq.py <query> <reference> [--mode global|local] [--json]
python scripts/align_sanger.py <reference.gb> --reads <read1.fa> [<read2.fa> ...] [--json]
python scripts/msa.py <seq1.fa> <seq2.fa> ... [--out-fasta aln.fa] [--json]
python scripts/assemble_contig.py --reads <reads.fa> [--min-overlap 20] [--json]
python scripts/annotate.py <seq.fa> [--both-strands] [--out-gb annotated.gb] [--json]
python scripts/draw_map.py <plasmid> --out map.svg [--theme light|dark] [--json]
```

### 3.2 Restriction sites and digests

```text
python scripts/find_sites.py <file> --enzyme EcoRI,BamHI [--digest] [--topology linear|circular] [--json]
```

Results include recognition start/end, strand, and explicit top/bottom cut
boundaries (`top_cut_boundary_0based` / `bottom_cut_boundary_0based`).

### 3.3 Primers and PCR

```text
python scripts/design_primers.py <template> \
  --start 100 --end 900 --target-tm 60 --min-len 18 --max-len 27 \
  [--engine auto|primer3-core|heuristic] [--require-primer3] [--json]

python scripts/design_primers.py <template> --gibson \
  --fwd-overlap <upstream_homology> --rev-overlap <downstream_homology> \
  [--fwd-site EcoRI] [--rev-site BamHI] [--json]

python scripts/simulate_pcr.py <template> --fwd <seq> --rev <seq> [--json]
python scripts/pcr_strategy.py --length 2000 --gc 75 --purpose cloning [--json]
python scripts/primer3_probe.py
```

`primer3_core_backend.py` is also importable when `scripts/` is on
`PYTHONPATH`:

```python
import sys; sys.path.insert(0, "scripts")
from primer3_core_backend import probe_primer3_core, design_anchored_pairs
```

`primer_design_engine.py` (v0.9 M3) adds tails, validation and
`tm_crosscheck` (Primer3 vs Biopython `Tm_NN` vs Wallace).  When Primer3
rejects a tailed exact-boundary pair it retries in order:

1. `tailed` (overhangs scored by Primer3);
2. `binding-only-retry` (tails reattached after ranking);
3. `relaxed-tm-retry` (Tm window 50–72 °C);
4. `slide-retry` (forced starts released within `min(25, n//4)` nt, product
   window `n-100..n+100` bp, GC still 20–80%; reports
   `boundary_offset_5p/3p`).

Each reason is returned in `primer3_retry_note`; if all layers fail the result
carries actionable `alternatives` (e.g. extend the 5' flank 20–40 bp or use an
internal pair) and `require_primer3` fails closed with those alternatives.
Abnormal relaxations/degradations require explicit consent via
`operation_consent.py` (`--consent ask` is interactive default; unconfirmed =
not executed). Current reproducible findings and validation are recorded in [the engineering audit](docs/audit-report.md) and [testing guide](docs/testing.md). Historical unavailable local reports are not current evidence.

### 3.4 Cloning simulation

```text
python scripts/simulate_cloning.py --method gibson --parts a.gb b.gb --overlap 20 --out out.gb [--topology circular] [--json]
python scripts/simulate_cloning.py --method digest-ligate --vector v.gb --insert i.gb --enzyme EcoRI --out out.gb [--json]

python scripts/simulate_advanced.py --method infusion --parts a.gb b.gb --overlap 15 --out out.gb [--json]
python scripts/simulate_advanced.py --method ta|topo --vector v.gb --insert i.gb --vector-cut 0 --vector-end t-tailed --insert-end a-tailed --out out.gb [--json]
python scripts/simulate_advanced.py --method gateway-lr --entry entry.gb --destination dest.gb --out out.gb [--json]
python scripts/simulate_advanced.py --method gateway-bp --vector donor.gb --insert attb.gb --out out.gb [--json]

python scripts/golden_gate.py --parts vector.gb part1.gb part2.gb --enzyme BsaI --out out.gb [--reverse 1] [--json]
```

Advanced and Golden Gate simulations are labelled experimental where they do
not model complete reaction chemistry (see §9).

### 3.5 Plasmid editing and export

```text
python scripts/edit_plasmid.py <file> --op insert --pos 100 --seq AAAA --out out.gb [--json]
python scripts/edit_plasmid.py <file> --op delete --start 100 --end 200 --out out.gb [--json]
python scripts/edit_plasmid.py <file> --op mutate --mutation 100:A --out out.gb [--json]
python scripts/mutagenesis.py <file> --op point --mutation 100:A --out mutant.fa [--json]
python scripts/mutagenesis.py <file> --op insert-codon --pos 100 --codon GGA --out mutant.fa [--json]
python scripts/mutagenesis.py <file> --op delete-codon --start 100 --end 117 --out mutant.fa [--json]
python scripts/write_dna.py <seq-or-file> --out out.gb --format snapgene-gb [--features-json feats.json] [--json]
python scripts/write_dna.py <seq-or-file> --out out.dna --format dna [--json]
python scripts/convert.py <file> --out out.fa --format fasta [--json]
```

### 3.6 Validate

```text
python scripts/validate_construct.py <file> [--json]
python scripts/validate_roundtrip.py <file> --format snapgene-gb [--strict] [--json]
python scripts/validate_roundtrip.py <file> --format dna --snapgene-exe "D:\SnapGene\SnapGene.exe" [--strict] [--json]
```

### 3.7 CRISPR design

```text
python scripts/design_guides.py <target> --nuclease spcas9-wt [--region 0 1000] [--json]
python scripts/generate_crispr_design_report.py <target> --nuclease spcas9-wt \
  [--fragments f1.gb f2.gb] [--protocol-evidence evidence.json] \
  [--reference-fasta genome.fa --annotation genome.gb --target-gene MYGENE] \
  [--cas-offinder C:\tools\cas-offinder.exe --offinder-device C0 --mismatches 3] \
  [--out-json report.json --out-markdown report.md --out-dir design-out]
```

The report writes GenBank + FASTA + SnapGene `.dna` when `--out-dir` is set.

### 3.8 v0.9 assembly planner

```text
python scripts/plan_assembly.py backbone.gb donor1.gb donor2.gb \
  --intent-json intent.json \
  --primer3-core C:\tools\primer3_core.exe \
  --out-json plan.json --out-markdown plan.md \
  --out-construct construct [--json]
```

`--intent-json` shape:

```json
{
  "goal": "clone GOI into lab backbone",
  "method": "auto",
  "topology": "circular",
  "name": "pBackbone-GOI",
  "backbone": {"source": 0},
  "fragments": [
    {"source": 1, "feature": "GOI"},
    {"source": 2, "interval": [10, 400]}
  ],
  "fusion": {"junction_after": 0, "expected_frame": 0}
}
```

`--intent-text` accepts a deterministic subset, e.g.
`backbone=0;fragments=1:GOI;method=gibson;name=pX`.

### 3.9 Feasibility rules, parts, online sources

```text
python scripts/recommend_protocol.py --profile reaction-profiles.json [--protocol-evidence evidence.json] [--json]
python scripts/parts_library.py --type promoter [--name T7] [--json]
python scripts/online_sources.py  # NCBI live query; offline is explicit
```

Python APIs:

```python
from rules.engine import evaluate_plan
from planning.planner import plan_assembly
from validation_crosscheck import primer_tm_crosscheck, restriction_site_crosscheck
```

---

## 4. Usage examples

### 4.1 Parse a SnapGene plasmid

```bash
python scripts/parse_dna.py fixtures/pDONR201.dna --json | python -m json.tool
```

### 4.2 Design Gibson primers

```bash
python scripts/design_primers.py donor.gb --gibson \
  --fwd-overlap ATGCTAGCTAGCATCGATGCTAG --rev-overlap GCTAGCTAGCATCGATCGATGCTA \
  --engine auto --json
```

### 4.3 Simulate a Golden Gate assembly

```bash
python scripts/golden_gate.py \
  --parts vector.gb part1.gb part2.gb part3.gb --enzyme BsaI \
  --out product.gb --json
```

### 4.4 Plan a two-plasmid assembly

```bash
cat > intent.json <<'JSON'
{"goal":"表达载体构建","method":"auto","backbone":{"source":0},
 "fragments":[{"source":1,"feature":"EGFP"}],"name":"pBACKBONE-EGFP"}
JSON

python scripts/plan_assembly.py backbone.gb donor.gb \
  --intent-json intent.json \
  --primer3-core "$PRIMER3_CORE" \
  --out-json plan.json --out-markdown plan.md --out-construct construct
```

### 4.5 Full-genome CRISPR off-target run

```bash
python scripts/generate_crispr_design_report.py target.gb \
  --nuclease spcas9-wt \
  --reference-fasta genome.fa --annotation genome.gb \
  --cas-offinder C:\tools\cas-offinder.exe \
  --out-json report.json --out-markdown report.md --out-dir design
```

### 4.6 High-GC PCR strategy

```bash
python scripts/pcr_strategy.py --length 2000 --gc 78 --purpose cloning --json
```

---

## 5. v0.9 assembly planning and CRISPR workflow

### 5.1 Planner pipeline

1. Parse all source records with `sg_common.load_seq`.
2. Resolve fragment intervals from structured intent (interval or feature name).
3. Select assembly method (`auto`, `overlap`, `gibson`, `golden_gate`,
   `digest-ligate`) with literature rules.
4. Golden Gate: check BsaI/BsmBI/Esp3I/BbsI inside every fragment with two
   independent site finders; on conflict switch enzyme or fall back to Gibson.
5. Overlap/Gibson: search 15–40 bp windows for GC 30–70% and `Tm_NN`;
   attach independent GC/Tm cross-checks.
6. Design primers via `primer_design_engine` (Primer3 preferred; heuristic
   fallback is clearly labelled) with overlap/enzyme tails and NEB protective
   bases.
7. Run safe declarative M2 rules (`rules/feasibility_rules.json`, confirmed
   user rules in `user_rules/rules.json`). `block` rules prevent execution;
   `warn` rules lower feasibility grade. Raw Python `check` expressions are
   rejected.
8. Emit fragment assignments, primers, strategy + reasons, feasibility,
   fusion-frame check, steps, and optional final `.gb/.fa/.dna`.

### 5.2 CRISPR pipeline

`generate_crispr_design_report.py` produces a unified report containing:
guide candidates (reference-axis coordinates), on-target scores
(Azimuth/DeepCpf1 when their backends are available), off-target hits from a
real Cas-OFFinder run annotated against GenBank features, reaction profiles,
and protocol recommendations. Off-target search remains `unavailable` when no
reference or no binary is provided — it never fabricates a complete result.

---

## 6. Data formats and schemas

### 6.1 Inputs

- SnapGene `.dna` (Biopython snapgene parser; `snapgene_reader` fallback)
- GenBank `.gb` / `.genbank`
- FASTA `.fa` / `.fasta` / `.fna` / `.fsa`
- EMBL `.embl` / `.emb`
- Raw sequence strings and single-record inline FASTA

### 6.2 Outputs

- Human-readable text (default)
- JSON with `--json`
- GenBank, SnapGene-flavoured GenBank, native `.dna` (sgffp), FASTA
- Markdown build manuals and CRISPR reports

### 6.3 v0.8/v0.9 JSON schemas

`schemas/`:

| Schema | Purpose |
|---|---|
| `guide-design-result-v0.8.json` | gRNA candidates, reference-axis coordinates, context sequences |
| `offtarget-result-v0.8.json` | off-target search results, binding metadata |
| `provenance-v0.8.json` | source objects; conditional required fields per source type |
| `reaction-profile-v0.8.json` | fragment reaction profiles |
| `protocol-recommendation-v0.8.json` | source-gated protocol recommendations |
| `crispr-design-report-v0.8.json` | unified CRISPR design report |
| `assembly-plan-v0.9.json` | v0.9 assembly plan |

Provenance rules: `manufacturer-protocol` requires `url`, `retrieved_at`,
`version`; `prediction-model` requires `version`; `public-protocol` requires
`url`, `retrieved_at`. Version strings come from `VERSION` (single source).

### 6.4 Coordinate conventions

- Legacy CLI positions (primers, edits, feature JSON): **1-based closed**.
- v0.8/v0.9 planning and CRISPR outputs: **0-based half-open** on the input
  reference axis. Reverse-strand guide candidates are mapped back to that
  axis; circular wrap is represented with explicit segments plus
  `wraps_origin`.

---

### Agent entry (v0.9.0-dev1)

```text
python scripts/run_design_agent.py --text "<自然语言目标>" \
  --files backbone.gb donor.gb --mode exploration|formal \
  --answers-json answers.json --deliver --json
```

`run_design_agent.py` only schedules existing tools; direct expert CLIs remain
unchanged.

## 7. Validation, tests and release gates

### 7.1 Quick checks

```bash
python scripts/check_env.py
python -X utf8 -B -m unittest discover -s tests
```

Run current targeted and release checks after every code change. Test counts,
failures and optional skips must come from the current command output; older
reports are not evidence for this checkout.

### 7.2 Real-backend gates

```bash
export SNAPGENE_RUN_REAL_MODELS=1      # Azimuth + DeepCpf1 reference values
export SNAPGENE_RUN_PRIMER3=1          # real primer3_core reproducibility
export SNAPGENE_RUN_ONLINE=1           # live NCBI eUtils query
export CAS_OFFINDER_EXE='D:\...\cas-offinder.exe'        # v2.x
export CAS_OFFINDER_EXE_V3='D:\...\cas-offinder.exe'     # v3.x
export CAS_OFFINDER_TMP='D:\ascii\tmp'
export PRIMER3_CORE='...\primer3_core.exe'
```

```bash
python -X utf8 -B -m unittest tests.test_v08_dev3.RealModelTests \
  tests.test_v08_dev3.RealCasOffinderIntegrationTests \
  tests.test_v09.M3PrimerEngineTests.test_real_primer3_reproducible_and_in_range
```

### 7.3 Release gates

```bash
# default mode: gates core modules without requiring optional real backends
python -X utf8 -B scripts/coverage_gate.py --mode default --json
# release-real mode: preflights SNAPGENE_RUN_REAL_MODELS/CAS_OFFINDER_EXE/CAS_OFFINDER_EXE_V3/PRIMER3_CORE and fails fast if missing
python -X utf8 -B scripts/coverage_gate.py --mode release-real --json
python -X utf8 -B scripts/mutation_tests.py --json
python -X utf8 -B scripts/property_tests.py --json
python -X utf8 -B scripts/build_release.py <repo-root> <output-dir> --version 1.0.0
python -X utf8 -B scripts/check_redistributable.py output/<redist-zip>
python -X utf8 -B scripts/check_redistributable.py output/<academic-zip> --academic
python -X utf8 -B scripts/collect_release_evidence.py
```

Thresholds in `coverage_gate.py`:

- v0.5/v0.7 core modules: line ≥ 90%, branch ≥ 85%
- v0.8 CRISPR modules: line ≥ 85%, branch ≥ 75%
- v0.9 planning modules: line ≥ 75%, branch ≥ 60%

Mutation gate: ≥ 90% kill rate across 12 specified mutations (current 12/12).
Property gate: Gibson/In-Fusion/Golden Gate/digest-ligate 1000 success + 300
failure; Gateway/TA 500 + 200.

### 7.4 SnapGene round-trip

```bash
python -X utf8 -B scripts/validate_roundtrip.py \
  fixtures/rich/rich_cross_origin.gb --format snapgene-gb \
  --snapgene-exe "D:\SnapGene\SnapGene.exe" --strict --json
```

The official SnapGene conversion is optional; without it the internal
read-back is still performed.

### 7.5 Single source of default biological parameters

`references/biological-parameters-sources.md` (+ machine-readable `.json`) is
the single source for every default biological parameter (Tm models, primer
quality windows, PCR/assembly/restriction/off-target thresholds). Each entry
has `参数名 | 默认值 | 来源 | URL | 检索日期 | 代码引用`; unlisted parameters
must not be emitted as defaults. `tests/test_release_iteration.py` checks the
required families and code-reference fields.

### 7.6 Informed consent and transparency

- `design_primers.py` and `plan_assembly.py` accept
  `--consent ask|auto` and `--yes`. Interactive `ask` is the default when a
  TTY is present: parameter confirmation, slide-retry relaxation, degradation
  to heuristic, no-solution alternatives and pending construct writes all
  stop until confirmed. With no confirmation **nothing is executed**.
- `operation_consent.py` provides the programmable API
  (`ConsentBroker(policy="ask", confirm_callback=...)`) and the
  `TransparencyLog`. Every result carries `operation_log` (backend/version,
  parameters, input sequence SHA-256 prefix, retry path, consent decisions,
  written files) and `consent.pending`.

---

## 8. 90-scenario literature validation

```bash
PRIMER3_CORE=<primer3_core.exe> python scripts/run_scenario_suite.py \
  --out-dir reports/scenarios
```

The bundled suite runs **90 literature/protocol sourced scenarios** and meets
the release-iteration minimum coverage: Gibson multi-fragment ≥3, Golden Gate
≥3, SOEing/overlap fusion ≥3, high-GC/AT-rich ≥5, long PCR (>5 kb) ≥3,
primer failure/retry chains ≥10 (A/B/C slide-retry groups included),
digest-ligation ≥3, and real-vector workflows ≥5 using shipped
pDONR201/Gateway/pGEM-T fixtures with catalog citations. Every scenario cites
a paper DOI or official protocol URL and records the paper/expected value as
ground truth where the source provides one.

Results are written as:

- `scenario-validation-human-report.md` — human-readable report with
  execution summary, overview table, and per-scenario 出处/描述/操作/产物;
- `90-scenario-execution-and-limitation-report.md` — compact machine-derived
  execution/limitation table;
- `scenario-results.json` — machine-readable ground truth and detail.

Scenario results are run-specific evidence. Rows classify completed,
partial and blocked-as-designed execution separately; a blocked row is not a
construct success and does not establish release readiness.

---

## 9. Known limitations

- **Simulation ≠ wet-lab protocol.** All cloning/assembly outputs are
  computational predictions. Method-specific biochemistry that is not modelled
  (e.g. SLIC exonuclease treatment, CPEC polymerase extension, USER uracil
  excision) is explicitly labelled as an approximation.
- **Primer search modes are explicit.** Core search can use Biopython `Tm_NN`
  under the same buffer conditions and then run complete-oligo Primer3
  structure QC. It is reported separately from Primer3 candidate search.
- **On-target models are context-limited.** Azimuth V3 and DeepCpf1 warnings
  (“not specifically validated for yeast”) are always attached.
- **Cas-OFFinder 3.x is an experimental beta backend.** v2.x is the production default; v3 results are flagged `experimental_backend=true`, `production_ready=false` and must be cross-checked with v2.x or an independent tool before any low-off-target claim.
- **Cas-OFFinder path handling.** v2.x is called with relative paths and the
  FASTA directory as `cwd` to survive non-ASCII Windows paths; a read-only
  reference directory is required to be writable for temporary IO files.
- **CRISPR off-target completeness** depends on an external Cas-OFFinder
  binary and OpenCL runtime. Empty output is reported as `incomplete`, not a
  silent zero-hit claim.
- **Online lookups are consent-gated.** Authorized BLAST URLs currently carry only the first 100 nt; longer sequences need a credentialed BLAST client (not implemented).
- **Online lookups are consent-gated.** `ncbi_search` refuses raw sequence terms; `ncbi_blast_hint` never embeds sequence; actual BLAST submission requires `ncbi_blast_consent_request` + `authorized_blast_url` (one-time, destination/purpose/SHA-bound). Addgene is a page-link helper only.
- **Online lookups degrade explicitly.** Without network or credentials,
  `online_sources.py` returns `offline-unverified`; it never fabricates a
  sequence.
- **Native `.dna` qualifier fidelity.** `sgffp` preserves sequence, topology,
  features and key qualifiers, but complex qualifier/history details may be
  simplified; always use `validate_roundtrip.py` before delivery.
- **v0.9 modules are a dev preview.** M1/M2/M3 APIs may evolve before RC.

## 10. Roadmap

- **RC blockers**: rerun real model / Cas-OFFinder / SnapGene round-trip gates
  in a clean RC environment; archive hashes and logs.
- **M1 natural language**: expand the deterministic intent parser to a wider
  Chinese/English subset; keep structured JSON as the canonical interface.
- **M3 specificity**: optional BLAST-backed primer uniqueness check.
- **M6 online**: authenticated Addgene API, asynchronous NCBI BLAST RID
  polling, CRISPOR online query behind the hardened consent boundary.
- **Rules**: more literature-sourced rules (recombineering, large-insert
  cloning, mammalian assembly), user-rule validation UI.
- **Packaging**: publish release ZIPs to GitHub Releases with a generated
  `RELEASE-MANIFEST.json`.

## 11. License and third-party notices

- Project code: MIT (`LICENSE`).
- `third_party/azimuth/`: Azimuth 2.0 (BSD-3-Clause), Doench et al. 2016.
- `third_party/deepcpf1/`: DeepCpf1 weights distributed by Bioconductor
  CRISPRseek (Artistic-2.0), Kim et al. 2018.
- External, never bundled: Cas-OFFinder (BSD-3-Clause), Primer3 (GPL),
  CRISPOR.
- Academic package fixtures: SnapGene/GSL terms; see
  `THIRD_PARTY_NOTICE.md`.
- `redistributable` package excludes all restricted SnapGene-derived fixtures
  and contains its own package-specific notice.
