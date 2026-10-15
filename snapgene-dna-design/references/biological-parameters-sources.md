# 默认生物学参数单一来源文件（人读版）

- 目的：本文件是 `SnapGene DNA Design v0.9.0-dev1` 所有**默认生物学参数**的单一来源索引。
  任何默认值都必须能指向本文件中的一条记录；没有来源的参数不得作为默认值输出。
- 使用规则：AI 需要 PCR 体系、酶选择、Tm 计算等参数时，依据本文件去对应文献/数据库/官方文档提取或拟合，**禁止凭记忆**。
- 配套机读文件：`references/biological-parameters-sources.json`。
- 检索日期：全部条目以 `2026-08-19` 为检索日期（代码内 `provenance` 保留各自开发日期）。

## 参数总表

| ID | 参数族 | 参数名 | 默认值 | 来源 | URL | 代码引用 |
|---|---|---|---|---|---|---|
| P01 | Tm | Wallace 公式 | 2×(A+T)+4×(G+C) | Wallace et al. 1979, Nucleic Acids Res 6:3543-3558 | https://doi.org/10.1093/nar/6.11.3543 | `scripts/validation_crosscheck.py` |
| P02 | Tm | SantaLucia 1998 最近邻模型（Biopython `Tm_NN`） | salt-corrected NN 参数 | SantaLucia 1998, PNAS 95:1460-1465 | https://doi.org/10.1073/pnas.95.4.1460 | `scripts/validation_crosscheck.py`、`scripts/design_primers.py` |
| P03 | Tm | Primer3 盐参数 | Na+ 50 mM、Mg2+ 1.5 mM | Primer3 官方文档（primer3-py argdefaults） | https://primer3.org/manual.html | `scripts/primer3_core_backend.py`、`validation_crosscheck.py` |
| P04 | primer-quality | Primer3 GC 范围 | 20–80% | Primer3 官方默认参数 | https://primer3.org/manual.html | `primer3_core_backend.py`（slide-retry 不放松 GC） |
| P05 | primer-quality | 引物长度范围 | 18–27 bp（CLI 默认 18–30） | Primer3 官方默认参数 | https://primer3.org/manual.html | `primer_design_engine.py`、`design_primers.py` |
| P06 | primer-quality | Tm 目标窗口 | 目标 ±5 °C；retry 50–72 °C | Primer3 官方默认参数 | https://primer3.org/manual.html | `primer_design_engine.py` |
| P07 | primer-quality | 3' GC clamp | 结合区 3' 端为 G/C | Primer3 官方文档 | https://primer3.org/manual.html | `primer_design_engine.py::_validate_primer` |
| P08 | primer-quality | 发夹/二聚体阈值 | hairpin TH 47 °C；self-any TH 45 °C | Primer3 官方默认参数 | https://primer3.org/manual.html | `primer_design_engine.py::_validate_primer` |
| P09 | primer-quality | slide-retry 滑动预算与产物窗口 | 5' 端向内 ≤ min(25, n//4) nt；产物 n−100..n+100 bp | 发布迭代需求清单 §3（AI B 实证 B8/B9） | `references/release-iteration-requirements.md` | `primer3_core_backend.py::design_anchored_pairs` |
| P10 | PCR | 退火温度策略 | Q5：按 NEB Tm Calculator，通常较低 Tm +3 °C，若计算值 ≥72 °C 可两步法 72 °C；Taq/OneTaq：按产品体系取较低 Tm 减值，并用梯度 PCR 优化 | NEB Q5 PCR 优化说明；NEB Tm Calculator；Taq/OneTaq 产品 protocol | https://www.neb.com/en-us/protocols/pcr-optimization-e0555 | `pcr_strategy.py` |
| P11 | PCR | 延伸时间 | 20–30 s/kb；实现取保守 30 s/kb | NEB Q5 protocol | https://www.neb.com/en/protocols/pcr-using-q5-high-fidelity-dna-polymerase-m0491 | `pcr_strategy.py::extension_time_seconds` |
| P12 | PCR | 高 GC 模板判定 | GC > 70% 使用 Q5 + High GC Enhancer（或 3% DMSO） | NEB GC-rich FAQ | https://www.neb.com/en/faqs/pcr-amplification-of-gc-rich-templates | `pcr_strategy.py` |
| P13 | PCR | AT-rich 模板判定 | GC < 30% 使用高保真酶并降低退火温度 | NEB Q5 / PCR optimization guidance | https://www.neb.com/en/protocols/pcr-using-q5-high-fidelity-dna-polymerase-m0491 | `pcr_strategy.py` |
| P14 | PCR | 长片段判定 | >10 kb 推荐 PrimeSTAR GXL 或 Q5 长片段方案 | Takara PrimeSTAR GXL 官方产品页 | https://www.takarabio.com/products/pcr/all-enzymes-and-accessories/primestar-series/primestar-gxl-dna-polymerase | `pcr_strategy.py`、`rules/feasibility_rules.json` |
| P15 | assembly | Overlap 长度 | 15–40 bp | IDT primer design guidance; Gibson 2009 | https://beta.idtdna.com/page/support-and-education/decoded-plus/how-to-design-primers-and-probes-for-pcr-and-qpcr/ | `planning/planner.py`、`rules/feasibility_rules.json` |
| P16 | assembly | Overlap GC | 30–70% | IDT primer design guidance | 同上 | `planning/planner.py`、`rules/feasibility_rules.json` |
| P17 | assembly | Gibson 片段数 | 推荐 ≤4–5 段 | Gibson et al. 2009, Nat Methods 6:343-345 | https://doi.org/10.1038/nmeth.1318 | `rules/feasibility_rules.json` |
| P18 | assembly | Golden Gate 片段数 | ≤8 段 | Engler et al. 2008, PLoS One 3:e3647 | https://doi.org/10.1371/journal.pone.0003647 | `rules/feasibility_rules.json` |
| P19 | assembly | Golden Gate 内部 Type IIS 位点 | 禁止（自动换 BsaI/BsmBI/Esp3I/BbsI） | Engler 2008 + NEB Golden Gate | https://international.neb.com/applications/cloning-and-synthetic-biology/golden-gate-assembly | `planning/planner.py` |
| P20 | restriction | 保护碱基 | NEB 常见酶 5' 保护碱基表 | NEB Cleavage Close to the End of DNA Fragments | https://www.neb.com/en/faqs/cleavage-close-to-the-end-of-dna-fragments | `design_primers.py::PROTECTIVE_BASES` |
| P21 | restriction | 酶切位点分析 | Bio.Restriction + 直接 motif 扫描（正链与反向互补）双重验证 | Bio.Restriction; NEBcutter | https://nc3.neb.com/NEBcutter/ | `sg_common.py`、`validation_crosscheck.py` |
| P22 | off-target | SpCas9 on-target 评分 | Azimuth 模型（Doench 2016） | Doench et al. 2016, Nat Biotechnol 34:184-191 | https://doi.org/10.1038/nbt.3437 | `scripts/azimuth_backend.py` |
| P23 | off-target | AsCas12a on-target 评分 | DeepCpf1 模型（Kim 2018） | Kim et al. 2018, Nat Biotechnol 36:239-241 | https://doi.org/10.1038/nbt.4061 | `scripts/deepcpf1_model.py` |
| P24 | off-target | 全基因组脱靶搜索 | Cas-OFFinder v2.4.1 / v3.0.0b3（bulge 语义） | Bae et al. 2014, Bioinformatics 30:1473-1475; Cas-OFFinder GitHub | https://github.com/snugel/cas-offinder | `cas_offinder_adapter.py` |
| P25 | off-target | 物种适用性警告 | Azimuth/DeepCpf1 未验证酵母；LbCas12a 拒绝 on-target 模型 | Doench 2016 / Kim 2018 | 同上 P22/P23 | `guide_scoring.py` |
| P26 | feasibility | M2 规则阈值（片段数/长度/Tm/结构/GC） | 全部条目见 `rules/feasibility_rules.json`（10 条） | Gibson 2009 / Engler 2008 / IDT / NEB / Primer3 | 见各规则 `source` 字段 | `rules/feasibility_rules.json` |
| P27 | feasibility | 构建体大小 >20 kb 提示电转化 | 实验室共识（Molecular Cloning 指南） | Sambrook & Russell, Molecular Cloning | https://www.cshlpress.com/default.tpl?cart=1615984732196908370&fromlink=T&linkaction=full&linksortby=oop_title&--eqSKUdatarq=918 | `rules/feasibility_rules.json` |
| P28 | primer-quality | 尾巴/overhang 参与 Primer3 评分语义 | `SEQUENCE_OVERHANG_LEFT/RIGHT`；失败时 binding-only 重试 | Primer3 官方文档 | https://primer3.org/manual.html | `primer3_core_backend.py`、`primer_design_engine.py` |
| P29 | assembly | 融合蛋白读框检查 | junction 后读框偏移 mod 3 == 0 | M1 设计契约（人工读框检查） | https://doi.org/10.1038/nmeth.1318（Gibson 载体构建实践） | `planning/planner.py::_check_fusion_frame` |
| P30 | PCR | 常规克隆/验证酶选择 | 克隆 Q5；验证/菌落 PCR OneTaq | NEB 聚合酶选择表 | https://www.neb.com/en/tools-and-resources/selection-charts/dna-polymerase-selection-chart | `pcr_strategy.py` |

## 说明

- 表中 P09 是发布迭代新增的**第 4 层 slide-retry 契约**：只释放边界与产物窗口，
  GC 仍保持 Primer3 默认 20–80%；若需要放宽 GC，必须走 `operation_consent.py`
  的询问机制（类别 `relaxation`），并记录决策到 operation log。
- 所有“实验室共识”类阈值（P27）只作为 `warn` 级提示，不作为 `error` 级阻断。
- 参数代码引用会随 `references/biological-parameters-sources.json` 的
  `code_references` 字段由 `tests/test_release_iteration.py` 做存在性检查；
  下轮审查可逐条核对“参数 ↔ 来源 ↔ 代码引用”三向一致。
