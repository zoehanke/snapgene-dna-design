# DEVELOPER MANUAL — SnapGene DNA Design v0.9.0

- 版本：0.9.0（技术门禁通过；等待真人独立生物学验收）
- 仓库：`D:\codex_project\snapgene-dna-design-v0.9.0-work`
- 读者：需要理解、核查、修改本项目任一技术细节的开发者。
- 使用约定：本手册所有文件路径均相对仓库根；行号引用为编写时快照，若代码移动以实际文件为准。文中不省略技术细节：每个脚本/模块都说明技术原理、生物原理与引用、实现路径、科学边界与测试。

## v0.9.1-dev2 3+1 分层架构与 7 大黄金实验 SOP 配方库 (当前开发基线)

针对早期由于提示词过度工程化导致的“测试门禁过度堆砌、工具暗藏黑盒决策、AI 丧失灵活度与缺少权威实验标准”的痛点，v0.9.1-dev2 全面实施了 **3+1 分层架构重构**：

### 1. 架构设计哲学
* **给 AI 配备纯粹的手脚**：工具库（Tier 1）必须彻底原子化，只做客观物理/数学变换（如切断、退火、计算 Tm、翻译、移码核验），绝不替 AI 擅自决定生物学方案。
* **为高频实验固化 SOP 轨道**：高频常规湿实验走标准配方（Tier 2），通过国际权威经典实验圣经（CSHL《分子克隆》、Nature Protocols、Nature Methods、ACS Synth Biol、NEB）将定量标准（同源臂 40~60 nt、重叠臂 20~25 bp、PAM 同义静默突变、U6 转录 5' G 校验、5' 保护碱基、DpnI 去背景等）固化下来，从根源上杜绝 AI“突发奇想”或“丢三落四”。
* **保留高级任务自由下潜**：当遇到非编码区突变、复杂多重重叠、罕见宿主等复杂非标情况时，AI 可完全脱离 SOP，自由调度 Tier 1 原子工具进行多步定制编排。
* **客观底线守门，绝不主观死锁**：底线清单（Tier 3）只针对破坏读码框、未破坏 PAM 导致体内复切、U6 连续 T 转录终止等客观生物学死线进行自检并提示风险。

### 2. 7 大全景黄金实验 SOP 配方库 (`core/recipes/`)
所有 SOP 均在模块内与输出中嵌入不可磨灭的学术文献出处（`authoritative_sources`）：
1. **`recipe_restriction_cloning`**：限制性双酶切与定向连接（来源：CSHL《分子克隆实验指南》第 4 版 & NEB 技术手册）。
2. **`recipe_gibson_assembly`**：同源重叠无缝组装（来源：Gibson et al. 2009 *Nature Methods* & NEB #E2621）。
3. **`recipe_golden_gate`**：Type IIS 模块化一锅法组装（来源：Engler et al. 2008 *PLoS ONE* & Potapov et al. 2018 *ACS Synth Biol*）。
4. **`recipe_crispr_hdr_donor`**：CRISPR sgRNA 与 HDR 供体设计（来源：Ran et al. 2013 *Nature Protocols* & Paquet et al. 2016 *Nature*）。
5. **`recipe_site_directed_mutagenesis`**：定点突变与密码子工程（来源：Zheng et al. 2004 *Nucleic Acids Res* & QuikChange 手册）。
6. **`recipe_protein_tagging`**：重组蛋白表达与标签工程（来源：Terpe 2003 *Appl Microbiol Biotechnol* & Kozak 1986 *Cell*）。
7. **`recipe_cloning_verification`**：分子质检、菌落 PCR 与 Sanger 测序引物布局（来源：CSHL《分子克隆》Ch. 1 & 8、Sanger et al. 1977 *PNAS*）。

### 3. 28 个 Tier 1 原子工具矩阵 (`core/tools/`)
* **检查类**：`inspect_dna`, `find_open_reading_frames`
* **酶切与末端类**：`find_restriction_sites`, `digest_sequence`, `digest_type_iis`, `fill_or_chew_overhang`, `check_overhang_compatibility`
* **PCR 与退火类**：`calc_primer_tm`, `check_primer_dimers`, `anneal_oligos`, `design_overhang_primers`, `simulate_pcr`
* **重组模拟类**：`simulate_overlap_assembly`, `simulate_golden_gate`, `simulate_digest_ligation`
* **序列手术类**：`mutate_sequence`, `strip_terminal_codons`, `translate_dna`, `check_reading_frame`, `get_codon_synonyms`, `fuse_in_frame`, `get_standard_element`
* **CRISPR 原语**：`design_crispr_grna`, `prepare_grna_oligos`, `extract_homology_arms`
* **SnapGene 接口**：`read_plasmid_file`, `export_plasmid_file`, `open_in_snapgene`

---

## v0.9.0-rc1 经验规则与发布闭环（历史章节；随 v0.9.0 发布）

本版本把个人经验规则纳入可审计的运行链：自然语言只产生候选，
候选必须经过固定预览、明确确认、声明式 Schema 校验后才会持久化。
规则条件只能使用受控 JSON 语法，顶层或嵌套出现 `check`、`eval` 都必须
失败；规则动作 `block` 是硬阻断，不能用 `--acknowledge-experience-warning`
绕过或写出产物。预存规则可以编辑、停用、删除、恢复和回滚，但每次变化
都要保留历史。验证引物设计仍需用户明确请求，不能用自动确认替代授权。

这份手册下面的 v0.9.0-dev2 章节是生物学审计基线；若与本节冲突，以
当前源码、`VERSION`、测试和最终发布包的 manifest 为准。

## v0.9.0-dev2 生物学审计闭环（历史基线）

本版本的最终构建物交付必须经过 `planning/executor.py` 的方法级执行和
验证；规划阶段的片段顺序、实验性近似或未执行状态不得写成最终质粒。
Golden Gate、digest-ligate、Gibson/overlap 分别使用对应执行路径，环状
组装覆盖闭环 junction，feature 迁移携带方向、复合位置、qualifier 和
来源坐标。CRISPR 报告必须如实列出候选总数与已搜索数；基因替换、完整
CDS、overlap、PCR、密码子和协议证据均为 fail-closed。输出构建物除
`.gb/.fa/.dna` 外还必须有同名 `.provenance.json`，其中包含方法、executor、
输入文件哈希、junction 和验证状态。所有边界（空值、n 边界、反向链、
跨原点、坏来源和不完整后端）都必须通过回归测试或结构化失败证据闭环。

## 目录

### 第 1 章：包结构、核心数据模型、格式读写与编辑导出
- 1. 概述与阅读约定
- 2. 包结构与资源布局
- 3. 坐标约定与拓扑规则
- 4. `scripts/sg_common.py`：公共基础设施
- 5. `scripts/construct_model.py`：核心数据模型
- 6. `scripts/parse_dna.py`：结构化读取
- 7. `scripts/write_dna.py`：格式写出
- 8. `scripts/edit_plasmid.py`：质粒编辑与 feature 迁移
- 9. `scripts/convert.py`：格式转换
- 10. `scripts/batch.py`：批量操作流水线
- 11. `scripts/validate_construct.py`：构建体一键 QC
- 12. `scripts/validate_roundtrip.py`：语义往返验证
- 13. `scripts/snapgene_compatibility.py`：导出前兼容性预检
- 14. `scripts/export_delivery_bundle.py`：安全交付包
- 15. `scripts/draw_map.py`：SVG 质粒图谱
- 16. `scripts/simulate_gel.py`：琼脂糖凝胶电泳模拟
- …（该章共 24 个小节）
### 第 2 章：引物设计、Primer3 外部引擎、Tm/QC 与 PCR 策略
- primer3_core_backend.py：Boulder-IO 外部引擎
- primer3_probe.py：旧 binding 诊断与崩溃隔离
- design_primers.py：CLI 引物设计与候选排名
- primer_design_engine.py：M3 引擎与 consent 接线
- primer_qc.py：纯 Python 引物结构 QC
- validation_crosscheck.py：独立数值交叉验证
- validate_primer3_integration.py：真实引擎发布门禁
- pcr_strategy.py：M4 模板感知 PCR 策略
- simulate_pcr.py：PCR 产物模拟
- 引用来源与仓库内位置
- 常见失败模式与排查
- 本章覆盖脚本清单
- 关键测试清单
### 第 3 章：组装模拟、克隆方法与基础序列分析工具
- assembly_model.py：统一末端/片段模型
- simulate_cloning.py：Gibson 组装与 digest-ligate 克隆
- simulate_advanced.py：In-Fusion、TA/TOPO 与 Gateway 近似
- golden_gate.py：Golden Gate / Type IIS 组装模拟
- mutagenesis.py：定点突变与密码子编辑模拟
- codon_optimize.py：密码子优化与编码区重编码
- protein_tools.py：蛋白反向翻译与寡核苷酸退火
- design_gene_replacement.py：基因替换盒设计
- find_sites.py：限制酶位点分析与模拟酶切
- analyze_seq.py：基础序列统计、反向互补与翻译
- align_seq.py：全局与局部双序列比对
- align_sanger.py：Sanger read 比对与覆盖度确认
- msa.py：渐进式多序列比对
- assemble_contig.py：贪心 overlap contig 组装
- methylation.py：甲基化 motif 重叠提示（实验性）
- annotate.py：ORF 自动注释与酶切位点 feature 写出
- …（该章共 20 个小节）
### 第 3 章补遗：generate_design_report.py
- generate_design_report.py：统一设计报告（JSON + 自包含 HTML）
### 第 4 章：v0.9 组装规划、可行性规则、元件库、在线来源与知情权
- scripts/plan_assembly.py：M1 组装规划 CLI 入口
- planning/intent.py：结构化组装意图
- planning/planner.py：多来源组装规划器
- planning/manual_render.py：构建手册渲染
- rules/engine.py：M2 可行性规则引擎
- rules/feasibility_rules.json：内置可行性规则
- user_rules/README.md：用户规则
- schemas/assembly-plan-v0.9.json：组装计划 JSON Schema
- scripts/parts_library.py：M5 元件库查询
- scripts/online_sources.py：M6 在线来源适配器
- scripts/sequence_upload_consent.py：序列上传同意状态机
- scripts/operation_consent.py：操作同意与透明日志
- scripts/provenance.py：来源追踪
- scripts/protocol_evidence.py：协议证据加载
- scripts/recommend_protocol.py：特征驱动的协议推荐
- scripts/characterize_reaction.py：反应特征刻画
- …（该章共 24 个小节）
### 第 5 章：CRISPR gRNA 设计、on/off-target 模型与 Cas-OFFinder 集成
- references/nuclease-registry.json
- references/crispr-model-applicability.md
- scripts/design_guides.py
- scripts/guide_scoring.py
- scripts/azimuth_backend.py
- scripts/deepcpf1_model.py
- scripts/cas_offinder_adapter.py
- scripts/annotate_offtargets.py
- scripts/generate_crispr_design_report.py
- scripts/crispor_adapter.py
- scripts/recommend_protocol.py
- scripts/characterize_reaction.py
- v2/v3 输入输出列格式与 bulge 语义
- 关键数据结构示例
- 错误码与结构化失败总表
- 测试运行与验证方法
- …（该章共 23 个小节）
### 第 6 章：打包发布、测试体系、场景套件与文档/参数溯源
- 1. 本章总览与发布物结构
- 2. `scripts/build_release.py`
- 3. `scripts/check_redistributable.py`
- 4. `scripts/validate_release_manifest.py`
- 5. `scripts/collect_release_evidence.py`
- 6. `scripts/check_env.py`
- 7. `scripts/run_test_suite.py`
- 8. `scripts/coverage_gate.py`
- 9. `scripts/mutation_tests.py`
- 10. `scripts/property_tests.py`
- 11. `scripts/smoke_core.py`
- 12. `scripts/smoke_academic.py`
- 13. `scripts/build_rich_fixtures.py`
- 14. `scripts/validate_rich_fixtures.py`
- 15. `scripts/run_scenario_suite.py`
- 16. `references/biological-parameters-sources`
- …（该章共 19 个小节）

---

# 第 0 章：项目全景与阅读地图

## 0.1 项目定位

本项目是面向合成生物学的质粒设计与分析工具链，功能分为四层：

1. **基础序列层**：`.dna/.gb/.fa/.embl` 读写、拓扑识别、1-based 闭区间 ↔ 0-based 半开区间转换、反向互补、IUPAC 校验。
2. **分析层**：限制酶位点与双链切口、翻译、双序列/多序列比对、Sanger 覆盖、凝胶模拟、甲基化提示、质粒图谱。
3. **设计层**：引物设计（真实 Primer3 外部进程 + 四层重试）、PCR/Gibson 引物、CRISPR gRNA 设计与 on/off-target 评分、v0.9 多片段组装规划。
4. **交付层**：GenBank/FASTA/原生 .dna 写出、往返验证、兼容性预检、交付 bundle、统一设计报告、场景验证套件与发布门禁。

## 0.2 四件事写作契约

本手册每一部分都遵守同一契约，读者可在任一小节按固定顺序检索：

- **技术原理**：数据结构、算法、边界条件、关键代码路径（函数名+行号）。
- **生物原理**：分子生物学依据与权威来源（不编造 DOI/URL；仓库内已有来源优先）。
- **实现路径**：输入 → 处理 → 输出的完整调用链。
- **科学性说明与功能**：适用边界、实验性标注、已知限制、对应验证测试。

## 0.3 关键全局约定（速查）

- 坐标：CLI 兼容字段/feature 识别坐标 1-based 闭区间；内部 `ConstructModel` 与 v0.8/v0.9 规划结果 0-based 半开区间；限制酶输出区分 recognition start 与 top/bottom cut boundary。
- 拓扑：只有显式 `circular` 才环化；裸序列/FASTA 默认 `linear`。
- 引擎：引物优先 `primer3_core` 子进程，失败/降级必须显式 `NOT Primer3` 或 consent 门。
- 隐私：在线提交必须 `SequenceUploadConsent` 一次性绑定；异常操作必须 `ConsentBroker` 确认。
- 实验性：所有克隆/组装模拟未建模的生化步骤均带 `experimental` 或 `approximation` 标注。

## 0.4 脚本 → 章节映射

| 章节 | 覆盖内容 |
|---|---|
| 第 1 章 | `sg_common`、`construct_model`、`parse_dna`、`write_dna`、`edit_plasmid`、`convert`、`batch`、`validate_construct`、`validate_roundtrip`、`snapgene_compatibility`、`export_delivery_bundle`、`draw_map`、`simulate_gel` |
| 第 2 章 | `primer3_core_backend`、`primer_design_engine`、`design_primers`、`primer_qc`、`primer3_probe`、`validate_primer3_integration`、`validation_crosscheck`、`pcr_strategy`、`simulate_pcr` |
| 第 3 章 | `assembly_model`、`simulate_cloning`、`simulate_advanced`、`golden_gate`、`mutagenesis`、`codon_optimize`、`protein_tools`、`design_gene_replacement`、`find_sites`、`analyze_seq`、`align_seq`、`align_sanger`、`msa`、`assemble_contig`、`methylation`、`annotate`、`generate_design_report` |
| 第 4 章 | `plan_assembly`、`planning/*`、`rules/*`、`user_rules`、`parts_library`、`online_sources`、`sequence_upload_consent`、`operation_consent`、`provenance`、`protocol_evidence`、`recommend_protocol`、`characterize_reaction` |
| 第 5 章 | `design_guides`、`guide_scoring`、`azimuth_backend`、`deepcpf1_model`、`cas_offinder_adapter`、`annotate_offtargets`、`generate_crispr_design_report`、`crispor_adapter`、nuclease registry、适用性文档 |
| 第 6 章 | `build_release`、`check_redistributable`、`validate_release_manifest`、`coverage_gate`、`mutation_tests`、`property_tests`、`run_test_suite`、`smoke_core`、`smoke_academic`、`build_rich_fixtures`、`validate_rich_fixtures`、`check_env`、`collect_release_evidence`、`run_scenario_suite` |

---
## 0.5 开发环境搭建（可复现）

本项目验证环境使用的解释器是 **Python 3.12.4**，完整路径：

```text
C:\Users\祝浩淇\AppData\Local\Programs\Python\Python312\python.exe
```

该解释器安装了 `requirements.txt` 与 `requirements-optional.txt` 的全部依赖。若当前 shell 的 `python` 不是上述解释器（例如指向 Anaconda），必须先切换，否则会出现 `No module named Bio` 等错误。逐条确认：

```powershell
# 1. 确认解释器路径
where python
C:\Users\祝浩淇\AppData\Local\Programs\Python\Python312\python.exe --version
C:\Users\祝浩淇\AppData\Local\Programs\Python\Python312\python.exe -c "import Bio; print(Bio.__version__)"

# 2. 推荐：创建专用虚拟环境
C:\Users\祝浩淇\AppData\Local\Programs\Python\Python312\python.exe -m venv .venv
.venv\Scripts\activate

# 3. 安装依赖
python -m pip install -r requirements.txt
python -m pip install -r requirements-optional.txt

# 4. 外部后端（可选但 release-real 必需）
# primer3_core（通过 primer3-py wheel 发现或 PRIMER3_CORE 显式指定）
$env:PRIMER3_CORE="C:\Users\祝浩淇\AppData\Local\Programs\Python\Python312\Lib\site-packages\primer3\src\libprimer3\primer3_core.exe"
$env:CAS_OFFINDER_EXE="D:\codex_project\output\dev3-backends\cas-offinder.exe"
$env:CAS_OFFINDER_EXE_V3="D:\codex_project\output\dev3-backends\cas-offinder-3.0.0b3\build\cas-offinder.exe"
$env:CAS_OFFINDER_TMP="D:\codex_project\output\dev3-backends\tmp"
$env:SNAPGENE_RUN_REAL_MODELS="1"
$env:SNAPGENE_RUN_PRIMER3="1"
$env:SNAPGENE_RUN_ONLINE="1"
# SnapGene.exe 位于 D:\SnapGene\SnapGene.exe（仅 roundtrip 官方核验需要）

# 5. 环境自检
python -X utf8 -B scripts/check_env.py --json
```

**本手册第 7 章验证记录** 使用上述完整解释器路径执行，不使用裸 `python`。日志内记录的解释器版本为 3.12.4；如果你在另一环境复跑，必须先把 `python` 换成同一解释器或在每个命令中显式写完整路径。

---


# 第 1 章：包结构、核心数据模型、格式读写与编辑导出

> 适用范围：`snapgene-dna-design` v0.8.0-dev3（开发预览，不是 RC，不是正式版）。
> 本章只描述计算端行为：解析、建模、编辑、写出、验证、交付与可视化。所有模拟结果都是计算预测，交付前需要向用户说明可由湿实验验证；标有 `experimental` 的功能只能作为概念预演，不得作为可直接执行的湿实验方案。

## 1. 概述与阅读约定

本章覆盖 13 个必须出现的脚本/模块：

`scripts/sg_common.py`、`scripts/construct_model.py`、`scripts/parse_dna.py`、`scripts/write_dna.py`、`scripts/edit_plasmid.py`、`scripts/convert.py`、`scripts/batch.py`、`scripts/validate_construct.py`、`scripts/validate_roundtrip.py`、`scripts/snapgene_compatibility.py`、`scripts/export_delivery_bundle.py`、`scripts/draw_map.py`、`scripts/simulate_gel.py`。

除这 13 个脚本外，本章还会覆盖 `SKILL.md` 中的对应命令、`references/schemas/` 下的 JSON Schema、`fixtures/` 目录结构、坐标约定，以及 BioPython `SeqIO`、`sgffp`、`snapgene_reader` 的读写路径与容错行为。

文中所有行号引用均以仓库根目录 `D:/codex_project/snapgene-dna-design-v0.9.0-work` 为基准，格式为 `文件路径:起始行`。函数签名与行号以 v0.9.0 实际代码为准；如果后续版本代码移动，应以仓库内 `SKILL.md` 与 `references/upgrade-log.md` 的版本说明为准。

## 2. 包结构与资源布局

### 2.1 顶层结构

| 路径 | 作用 |
|---|---|
| `SKILL.md` | 技能入口文档：脚本清单、坐标约定、标准工作流、注意事项 |
| `scripts/` | 全部 Python 3.10+ 脚本，核心逻辑都放在这一层 |
| `references/` | 生物学参数单一来源、schema、版本升级日志、协议证据 |
| `references/schemas/` | JSON 输出契约 Schema（v0.4 兼容参考 + v0.5 现行） |
| `fixtures/golden/` | 学术版测试载体（Gateway/TA/TOPO 真实载体快照） |
| `fixtures/rich/` | 合成 rich feature 夹具（复合位置、Unicode、多值 qualifier 等） |
| `tests/` | 回归测试与集成测试 |
| `reports/` | 覆盖率、变异、property、rich fixture 等门禁报告 |
| `rules/`、`user_rules/`、`planning/`、`parts/` | v0.9.0-dev 组装规划相关（不属于本章核心，但包结构上位于顶层） |

### 2.2 `SKILL.md` 命令索引（本章相关）

本章脚本在 `SKILL.md` 的“脚本清单”和“常见任务速查”中的位置如下：

| 脚本 | `SKILL.md` 主要条目 | 关键行号 |
|---|---|---|
| `parse_dna.py` | 读取与分析表 | `SKILL.md:122` |
| `validate_construct.py` | 编辑与产出表 | `SKILL.md:149` |
| `simulate_gel.py` | 编辑与产出表 | `SKILL.md:150` |
| `draw_map.py` | 编辑与产出表 | `SKILL.md:151` |
| `convert.py` | 编辑与产出表 | `SKILL.md:152` |
| `batch.py` | 编辑与产出表 | `SKILL.md:153` |
| `write_dna.py` | 编辑与产出表 | `SKILL.md:154` |
| `snapgene_compatibility.py` | 编辑与产出表 | `SKILL.md:155` |
| `export_delivery_bundle.py` | 编辑与产出表 | `SKILL.md:156` |
| `validate_roundtrip.py` | 编辑与产出表 | `SKILL.md:158` |
| `edit_plasmid.py` | 编辑与产出表 | `SKILL.md:147` |
| 坐标约定 | 1-based/0-based、切口边界、拓扑 | `SKILL.md:160-165` |
| 标准工作流 | 读取 → 理解 → 执行 → 编辑产出 → 验证 | `SKILL.md:167-173` |
| 常见任务速查 | 格式转换、导出、验证入口 | `SKILL.md:175-193` |
| 注意事项 | `.dna` TLV、sgffp、SnapGene 官方核验发现 | `SKILL.md:195-209` |

### 2.3 `references/schemas/`

| 文件 | 状态 | 内容 |
|---|---|---|
| `references/schemas/common-envelope-v0.4.json` | v0.4 兼容参考 | 成功/失败信封：`schema_version`、`ok`、`command`、`data`、`warnings`、`error` |
| `references/schemas/common-envelope-v0.5.json` | 现行 | 将 `schema_version` 固定为 `"0.5.0"`，`warning` 定义为字符串，`error` 使用结构化对象 |
| `references/schemas/roundtrip-result-v0.4.json` | v0.4 兼容参考 | 往返验证结果字段 |
| `references/schemas/roundtrip-result-v0.5.json` | 现行 | `passed`、`core_passed`、`strict_passed`、`strict`、`lossless`、`delivery_grade`、`internal_roundtrip`、`official_snapgene_roundtrip`、`warnings` |
| `references/schemas/assembly-result-v0.4.json` | v0.4 兼容参考 | 组装结果字段 |
| `references/schemas/assembly-result-v0.5.json` | 现行 | 组装结果、`$defs` 中的 `coordinate`、`source_mapping` 等 |

`scripts/sg_common.py:22` 的 `JSON_SCHEMA_VERSION = "0.5.0"` 与 `references/schemas/common-envelope-v0.5.json` 对应。`tests/test_v06.py` 的 `SchemaContractTests.test_schemas_validate_real_outputs` 会读取这些 schema 验证真实脚本输出；`tests/test_v08_dev2.py` 的 `SchemaPositiveTests`/`SchemaNegativeTests` 对 v0.8 schema 做正反例校验。

### 2.4 `fixtures/` 结构

#### 2.4.1 `fixtures/golden/`（学术版，academic-only）

`fixtures/golden/README.md` 声明这些文件是本地测试快照，来自公开载体系统，只用于内部验证，不作为权威分发副本。文件包括：

| 文件 | 来源/用途 |
|---|---|
| `pDONR201.dna` | Invitrogen Gateway 供体载体；Hartley et al. 2000, Genome Res 10:1788-1795, DOI 10.1101/gr.143000 |
| `pDEST40.dna` | Invitrogen Gateway 目的载体 |
| `pENTR-D-TOPO.dna` | Invitrogen 入门载体 |
| `pcDNA3.2-V5-GW-D-TOPO.dna` | Invitrogen 表达系统 |
| `pGEM-T-linearized.dna` | Promega pGEM-T Easy 线性化载体 |
| `ta-insert.fa` | 合成 A-tailed PCR 插入片段；Marchuk et al. 1991, Nucleic Acids Res 19:1154, DOI 10.1093/nar/19.5.1154 |
| `attB-EmGFP.gb`、`pENTR-EmGFP.gb` | 本地 Gateway attB/attL + EmGFP 预期构建体 |
| `pDEST-EmGFP.gb` | 本地 Gateway LR 预期产物 |
| `pGEM-T-insert.gb` | 本地 TA 预期产物 |

这些文件主要用于 `tests/test_v04.py`、`tests/test_v06.py`、`scripts/smoke_academic.py` 的 Gateway/TA/TOPO 工作流回归。

#### 2.4.2 `fixtures/rich/`（合成，双包可发布）

`fixtures/rich/` 下 8 个合成 GenBank 文件用于严格往返测试，均由 `scripts/build_rich_fixtures.py` 生成：

| 文件 | 覆盖点 |
|---|---|
| `rich_fwd_cds.gb` | 正链 CDS，含 `db_xref`、`EC_number` |
| `rich_rev_cds.gb` | 反链 CDS（`complement(1..9)`） |
| `rich_join.gb` | `join(1..4,5..10,11..16)` 三段复合位置 |
| `rich_order.gb` | `order(5..8,1..4)` 顺序复合位置 |
| `rich_cross_origin.gb` | 环状跨原点 CDS `join(13..16,1..5)`，`translation="F*N"` |
| `rich_unicode.gb` | 非 ASCII feature 名与 note（`基因_α`、`引物设计验证 fixture · café Σ DNA π 质粒`） |
| `rich_multivalue.gb` | 多值 `note`、`db_xref`、`synonym`、`gene` |
| `rich_kitchen_sink.gb` | 环状 + 正/反 feature + 跨原点 + Unicode + 多值混合 |

对应测试为 `tests/test_rich_fixtures.py` 的 `RichFixtureRoundTripTests`，以及 `scripts/validate_rich_fixtures.py` 门禁脚本。

## 3. 坐标约定与拓扑规则

### 3.1 两套坐标系统

`SKILL.md:160-165` 规定：

1. CLI 参数及兼容字段中的 feature/识别序列坐标使用 **1-based 闭区间**，与 SnapGene 一致。
2. 内部 `ConstructModel` 只使用 **0-based 半开区间**。
3. 限制酶结果区分“识别序列起点”和“正/负链切口边界”。
4. feature JSON 的 `location` 保留 `operator`、`parts`、各段 strand 与 `wraps_origin`；旧 `segments`、`start`、`end` 同时保留。
5. 拓扑只有显式标注 `circular` 才按环状处理，默认 `linear`。

### 3.2 转换规则

- 用户坐标 `[start, end]`（1-based closed）转换为内部坐标 `[start-1, end)`。
- 内部坐标 `[start0, end0)` 转回用户坐标 `[start0+1, end0]`。
- 例如 BioPython `FeatureLocation(0, 3)` 表示 0-based 半开 `[0, 3)`，导出为 `start=1, end=3`，即 `1..3`。
- 插入位置 `--pos 100` 表示“插在第 100 位碱基之前”，转换为 `pos0 = 99`。
- 限制酶切口 `top_cut_boundary_0based` 是边界坐标不是碱基索引：线性序列中 `0` 表示第 1 位碱基之前，`n` 表示最后一个碱基之后；环状序列归一化到 `0..n-1`。

一个完整的转换示例：用户输入“删除 100..200（1-based 闭区间）”，CLI 将 `start=100, end=200` 转为 `ConstructModel.delete(start0=99, end0=200)`。删除后，原来 `FeatureLocation(250, 300)` 的 feature 位于删除区间之后，按 `map_boundary` 左移 `delta=101`，变为 `[149, 199)`（0-based），导出为 1-based `150..199`。这就是“CLI 说 1-based，模型算 0-based，输出再回到 1-based”的完整闭环。

### 3.3 拓扑规则

`scripts/sg_common.py:198-206` 的 `topology(record)` 只读取 `record.annotations["topology"]`，且仅接受 `"circular"` 或 `"linear"`，否则返回 `"linear"`。裸序列和普通 FASTA 一律视为线性。这样做的生物学理由是：环状 DNA 的坐标计算、限制酶片段数、PCR 产物边界、跨原点 feature 的语义都不同；在缺少人工确认时默认线性更保守，避免把裸序列误判为质粒。

## 4. `scripts/sg_common.py`：公共基础设施

### 4.1 技术原理

`sg_common.py` 是全部脚本共享的 I/O 与序列工具层，核心函数如下：

| 函数 | 签名/关键行 | 作用 |
|---|---|---|
| `jprint` | `jprint(obj, ok=None)` `sg_common.py:25` | 输出 v0.5 成功信封，兼容 v0.2.1 旧顶层字段 |
| `jfail` | `jfail(code, message, details=None, warnings=None)` `sg_common.py:63` | 输出失败信封并 `sys.exit(1)` |
| `looks_like_path` | `looks_like_path(s)` `sg_common.py:93` | 启发式判断输入是路径还是裸序列 |
| `normalize_dna` | `normalize_dna(text, label="sequence")` `sg_common.py:98` | 去空白、转大写、拒绝非 IUPAC 符号 |
| `_read_one` | `_read_one(path, fmt)` `sg_common.py:112` | 按格式读取且确保关闭文件句柄 |
| `load_seq` | `load_seq(source)` `sg_common.py:126` | 统一入口：文件/裸序列/行内 FASTA → `SeqRecord` |
| `features_to_dict` | `features_to_dict(record)` `sg_common.py:191` | 调 `construct_model.feature_to_dict` 序列化 features |
| `topology` | `topology(record)` `sg_common.py:198` | 返回 `circular`/`linear`，默认 `linear` |
| `gc_percent` | `gc_percent(seq)` `sg_common.py:209` | 兼容 BioPython `<1.80` 的 `GC` 与 `>=1.80` 的 `gc_fraction` |
| `get_enzyme` | `get_enzyme(enzyme_name)` `sg_common.py:221` | 大小写不敏感解析 `Bio.Restriction` 酶类 |
| `enzyme_sites` | `enzyme_sites(seq, enzyme, circular=False)` `sg_common.py:242` | 返回 1-based 切口后第一位位置（旧口径） |
| `restriction_hits` | `restriction_hits(seq, enzyme, circular=False)` `sg_common.py:258` | 返回识别位点 + 双链切口边界的结构化 hit |

#### 4.1.1 JSON 信封

`jprint` 对普通 dict 包装为：

```json
{"schema_version": "0.5.0", "ok": true, "command": "<脚本名>",
 "data": <原 payload>, "warnings": [...]}
```

`ok` 默认取 `payload["passed"]`（如果存在），否则为 `True`（`sg_common.py:34-51`）。如果 payload 自身带有 `schema_version` 且以 `0.8` 开头，则直接输出原 v0.8 schema，不再包装 v0.5 信封（`sg_common.py:40-44`）。`jfail` 输出 `ok: false`、`data: null`、`error: {code, message, details?}` 后退出非零（`sg_common.py:82-90`）。

#### 4.1.2 `load_seq` 的读写路径与容错

`load_seq(source)` 的决策流程：

1. 空输入/非字符串：`ValueError("Empty source")`（`sg_common.py:134-138`）。
2. 路径形态但文件不存在：`FileNotFoundError`（`sg_common.py:140-141`）。
3. 文件存在时按扩展名路由：
   - `.dna`：先 `SeqIO.read(handle, "snapgene")`（BioPython 内置 SnapGene 二进制解析），任何异常回退 `snapgene_reader.snapgene_file_to_seqrecord`；两个都失败才 `ValueError`（`sg_common.py:147-160`）。
   - `.gb`/`.genbank`：`SeqIO.read(..., "genbank")`（`sg_common.py:161-162`）。
   - `.fa`/`.fasta`/`.fna`/`.fsa`：`SeqIO.read(..., "fasta")`（`sg_common.py:163-164`）。
   - `.embl`/`.emb`：`SeqIO.read(..., "embl")`（`sg_common.py:165-166`）。
   - 未知扩展名：依次尝试 `genbank`、`fasta`、`embl`、`snapgene`（`sg_common.py:168-172`）。
4. 非文件文本：
   - 以 `>` 开头：按 FASTA 解析，要求恰好 1 条记录，并对序列执行 `normalize_dna`（`sg_common.py:177-185`）。
   - 其他：视为裸序列，`normalize_dna` 后构造 `SeqRecord(Seq(seq), id="seq", name="seq")`（`sg_common.py:186-188`）。

`_read_one` 的容错点：

- SnapGene 二进制用 `open(path, "rb")`（`sg_common.py:114-116`）。
- 文本格式先尝试 `utf-8-sig`（可处理 BOM），捕获 `UnicodeDecodeError` 后用 `latin-1` 重读，兼容旧的单字节编码 INSDC 文件（`sg_common.py:117-123`）。
- 始终使用 `with` 确保句柄关闭。

#### 4.1.3 `normalize_dna`

`normalize_dna` 将输入去空白、转大写，然后检查每个字符是否属于 `DNA_IUPAC = frozenset("ACGTRYSWKMBDHVN")`（`sg_common.py:21`）。非法字符按排序后去重列表报错。`U`（RNA 尿嘧啶）不在允许集合中，因此 RNA 序列会在此处被拒绝；这符合 DNA 设计工具的边界。

#### 4.1.4 限制酶位点与双链切口

`get_enzyme` 的查找顺序：先精确属性名，再首字母大写形式，最后对 `dir(Bio.Restriction)` 做大小写不敏感全扫描（`sg_common.py:228-239`）。

`enzyme_sites` 直接调用 `enzyme.search`，返回“正链切口后第一位碱基”的 1-based 坐标，线性用 `linear=not circular`，环状时对 `n` 取模并排序去重（`sg_common.py:249-253`）。函数说明明确指出这是切口坐标，不是识别位点起点；向用户报告识别位点应使用 `restriction_hits`。

`restriction_hits` 是本模块算法最复杂的部分：

- 用 IUPAC 展开表扫描序列窗口（`sg_common.py:271-281`）。
- 对非回文酶同时搜索正向与反向互补方向（`sg_common.py:285-301`）。
- 用 `enzyme.fst5`、`enzyme.fst3` 计算正链与负链切口边界；负链方向将正向切口几何镜像（`sg_common.py:306-314`）。
- 环状序列将切口边界归一化到 `0..n-1`，并报告 `wraps_origin`（`sg_common.py:316-318`）。
- 输出字段同时包含识别序列 `start/end`（1-based）、`recognition_start0/end0`、`top_cut_boundary_0based`、`bottom_cut_boundary_0based`、`top_cut_after_base_1based` 和 `cuts_within_sequence`（`sg_common.py:319-337`）。

例如 EcoRI（G^AATTC，`fst5=1`、`fst3=5`）在 `GGAATTCC` 中：识别起点为 `start=2`（1-based），`top_cut_boundary_0based=2`，`bottom_cut_boundary_0based=6`；即正链在第 2 位之后（边界坐标 2，对应 1-based 第 3 位前）切口，负链在第 6 位之后切口，产生 5' AATT 黏性末端。`tests/test_v03.py` 的 `RestrictionModelTests` 覆盖了 EcoRI 和 BsaI 的正反向切口边界。

具体字段对应关系：

| 字段 | 含义 | EcoRI `GGAATTCC` | BsaI `GGTCTCAAAAAAA`（正向） | BsaI 反向 |
|---|---|---|---|---|
| `start` | 识别序列起点，1-based 闭区间 | 2 | 1 | 7 |
| `end` | 识别序列终点，1-based 闭区间 | 7 | 6 | 12 |
| `recognition_start0` | 识别序列起点，0-based | 1 | 0 | 6 |
| `strand` | 命中方向（1=正向，-1=反向互补） | 1 | 1 | -1 |
| `top_cut_boundary_0based` | 正链切口边界 | 2 | 7 | 1 |
| `bottom_cut_boundary_0based` | 负链切口边界 | 6 | 11 | 5 |
| `wraps_origin` | 识别序列是否跨环状原点 | false | false | false |

BsaI 正向位点 `GGTCTC(7/11)` 表示正链在识别起点后第 7 个边界处切割，负链在第 11 个边界处切割，产生 4 bp 的 5' 黏性末端；反向位点通过将正向几何镜像得到 `top_cut_boundary_0based=1`、`bottom_cut_boundary_0based=5`。这就是 Golden Gate 组装中“识别位点被切除、切口末端可编程”的序列基础（Engler 2008，见 §17）。

### 4.2 生物原理

限制性内切酶在识别序列内部或附近的固定位置切割磷酸二酯键。Type II 酶（如 EcoRI、BamHI）在识别位点内切割，产生 5' 或 3' 黏性末端；Type IIS 酶（如 BsaI、BsmBI）在识别位点一侧的固定距离处切割，因此识别位点可以与切割产生的末端分离。`Bio.Restriction` 的 `fst5`/`fst3` 来自 REBASE 酶数据，用于描述“正链切割距识别序列 5' 端的距离”和“负链切割距识别序列 3' 端的距离”。该切口的双链边界是 `find_sites.py` 计算片段长度的基础。仓库在 `references/biological-parameters-sources.md` P21 中声明酶切位点分析采用 Bio.Restriction 加直接 motif 扫描双重验证，参考 NEBcutter（URL：`https://nc3.neb.com/NEBcutter/`）。

### 4.3 实现路径

```
CLI main -> load_seq(source) -> SeqRecord
         -> features_to_dict(record) -> construct_model.feature_to_dict
         -> restriction_hits / enzyme_sites -> JSON
```

### 4.4 科学性说明

- `load_seq` 对 `.dna` 的双解析器回退属于容错，但两个解析器对同一文件可能给出不同 feature 细节；后续 `validate_roundtrip` 会把读回差异显式化。
- `enzyme_sites` 中 `except Exception: return []` 会吞掉酶解析/搜索异常，适合“查询多个酶时不要因一个失败全盘崩溃”的批处理场景，但调用方不应把空列表解释为“确认无位点”。需要严格报告时应使用 `restriction_hits`。
- `restriction_hits` 的负链切口几何依赖 `Bio.Restriction` 的 `fst5/fst3` 语义，对环状跨原点位点做了归一化；它不模拟甲基化、碱基修饰或酶切缓冲液对活性的影响。

## 5. `scripts/construct_model.py`：核心数据模型

### 5.1 技术原理

`construct_model.py` 定义统一构建体模型，模块级常量：

- `MODEL_VERSION = "0.3.0"`（`construct_model.py:13`）
- `COORDINATE_SYSTEM = "0-based-half-open"`（`construct_model.py:14`）

模型只使用 0-based 半开边界，CLI 适配器负责把用户 1-based 坐标翻译成 0-based。

#### 5.1.1 `feature_to_dict`（`construct_model.py:39`）

输入一个 `SeqFeature` 和可选序列长度，输出无展平的 feature 字典：

- 顶层兼容字段：`name`、`type`、`strand`、`start`、`end`、`qualifiers`、`location`。
- `location.parts` 逐段输出为 `start0/end0` 与 1-based `start/end`，并保留每段 strand（`construct_model.py:52-61`）。
- `wraps_origin` 的判定：多段之间出现后一段 `start0` 小于前一段 `start0`，或首段末尾在序列长度处且末段起点在 0（`construct_model.py:62-72`）。
- 多段时附加旧版 `segments`（1-based 闭区间）兼容字段（`construct_model.py:89-94`）。

#### 5.1.2 `ConstructModel` 类（`construct_model.py:98`）

构造时深拷贝 `SeqRecord`，设置默认 `molecule_type="DNA"`，初始化 `warnings`（`construct_model.py:101-104`）。`length` 为序列长度（`construct_model.py:106-108`）。

`_replace_parts(self, transform)` 是 feature 迁移核心（`construct_model.py:110-123`）：对每个 feature 的每个 part 应用 `transform`，返回新 parts 列表；空的 parts 丢弃该 feature；否则复制 feature 并用 `_location` 重建位置。`_location` 在 0 个 part 时返回 `None`，1 个 part 时返回单个 `FeatureLocation`，多个时返回 `CompoundLocation`（`construct_model.py:31-36`）。`_part` 重建 part 时保留 strand 与远程 ref/ref_db（`construct_model.py:21-28`）。

主要编辑操作：

| 方法 | 签名 | 行号 | 边界条件 |
|---|---|---|---|
| `insert` | `insert(self, pos0, sequence)` | `construct_model.py:133` | `0 <= pos0 <= length`；空序列报错 |
| `delete` | `delete(self, start0, end0)` | `construct_model.py:153` | `0 <= start0 < end0 <= length` |
| `replace` | `replace(self, start0, end0, sequence)` | `construct_model.py:176` | 先 delete 再 insert |
| `mutate` | `mutate(self, mutations)` | `construct_model.py:181` | 每个 `(pos0, base)` 必须 `0 <= pos0 < len` |
| `rotate` | `rotate(self, origin0, topology=None)` | `construct_model.py:190` | `0 <= origin0 < n` |
| `set_topology` | `set_topology(self, value)` | `construct_model.py:221` | 只接受 `linear`/`circular` |
| `to_record` | `to_record(self)` | `construct_model.py:227` | 返回深拷贝 |
| `to_dict` | `to_dict(self)` | `construct_model.py:230` | 输出模型版本、坐标系统、长度、拓扑、features、warnings |

#### 5.1.3 插入迁移算法

`insert` 对每个 part：

- 新 start = `start0 + (delta if start0 >= pos0 else 0)`
- 新 end = `end0 + (delta if end0 > pos0 else 0)`（`construct_model.py:141-145`）

含义：插入发生在 `pos0` 边界处。起点在插入点之后（含等于）的 part 右移；终点在插入点之后（严格大于）的 part 右移。若 feature 正好从 `pos0` 开始，其 `end0` 右移而 `start0` 也右移，feature 被整体后移；若 feature 覆盖插入点（`start0 < pos0 < end0`），start 不动、end 右移，feature 变长，符合生物学“在基因内部插入一段”的坐标语义。随后 `_clear_letter_annotations` 清除 per-letter 注释并记录 warning（`construct_model.py:125-131`、`147-150`）。

#### 5.1.4 删除迁移算法

`delete` 的 `map_boundary` 是一个三区间映射（`construct_model.py:158-163`）：

- `value <= start0`：坐标不动。
- `value >= end0`：坐标左移 `delta`。
- `start0 < value < end0`：坐标吸附到 `start0`。

然后丢弃 `new_end <= new_start` 的 part（`construct_model.py:165-168`）。这保证完全落在删除区间内的 part 消失，横跨删除边界的 part 被裁剪，完全在删除区间之后的 part 整体平移。该算法对 `CompoundLocation` 逐段独立应用，不展平。

#### 5.1.5 旋转算法

`rotate(origin0)` 将新的原点切到 `origin0`：

- 每个 part 的 `new_start = (start0 - origin0) % n`，`unwrapped_end = new_start + length`。
- 若 `unwrapped_end <= n`，直接返回单段；否则拆成 `[new_start, n)` 和 `[0, unwrapped_end - n)` 两段（`construct_model.py:200-210`）。
- 序列旋转 `old[origin0:] + old[:origin0]`，per-letter 注释同步旋转（`construct_model.py:212-216`）。

跨切割点的 feature 被拆成跨原点复合位置，且 `extract` 序列不变；`tests/test_v03.py` 的 `test_rotate_splits_crossing_feature_without_sequence_loss` 验证了这一点。

#### 5.1.6 迁移示例

设环状序列长度 12，一个 `join(9..12,1..3)` 的跨原点 feature（0-based parts 为 `[8,12)` 与 `[0,3)`，1-based 闭区间 `9..12` 与 `1..3`）。在 `pos0=2` 处插入 `TT`（delta=2）后：

| part | 原坐标（0-based） | 新 start0 计算 | 新 end0 计算 | 结果（0-based） | 结果（1-based） |
|---|---|---|---|---|---|
| 1 | `[8,12)` | `8 >= 2` → `10` | `12 > 2` → `14` | `[10,14)` | `11..14` |
| 2 | `[0,3)` | `0 >= 2` 不成立 → `0` | `3 > 2` → `5` | `[0,5)` | `1..5` |

得到 `join(11..14,1..5)`。在同样序列上删除 `[1,10)`（delta=9）：

| part | 原坐标（0-based） | `map_boundary(start0)` | `map_boundary(end0)` | 结果（0-based） | 结果（1-based） |
|---|---|---|---|---|---|
| 1 | `[8,12)` | `8` 在删除区间内 → `1` | `12 >= 10` → `12-9=3` | `[1,3)` | `2..3` |
| 2 | `[0,3)` | `0 <= 1` → `0` | `3` 在删除区间内 → `1` | `[0,1)` | `1..1` |

最终 feature 保留为 `join(2..3,1)` 的两段复合位置，读框和提取序列语义不变。`tests/test_v03.py` 的 `ConstructModelTests` 即用类似的 `record_with_compound()` 构造验证这些数字。

#### 5.1.7 `to_dict`

`to_dict` 输出 `model_version`、`coordinate_system`、`length`、`topology`（默认 `"linear"`）、`features`（经 `feature_to_dict`）与 `warnings`（`construct_model.py:230-241`）。

### 5.2 生物原理

质粒编辑的坐标迁移对应分子克隆中的“在指定碱基位置插入/删除/替换 DNA 片段”。在环状质粒上，坐标原点是人为设定的；SnapGene 允许旋转原点而不改变分子。因此 `rotate` 必须在序列旋转的同时重算所有 feature 坐标，并保持 feature 的生物学含义（转录方向、读框、氨基酸产物）不变。模型在插入/删除后删除 per-letter 注释，是因为插入或删除会改变碱基编号，原 per-letter 注释值无法确定地映射到新序列（`construct_model.py:125-131`）。

跨原点 feature 是环状质粒常见现象（例如复制起点 ori 或横跨人工原点的 CDS）。GenBank `join(13..16,1..5)` 表示 feature 从 13 位到 16 位后接 1 到 5 位，生物上连续。`feature_to_dict` 的 `wraps_origin` 正是为了无展平保留这一语义。

### 5.3 实现路径

```
edit_plasmid.py main -> load_seq -> op_insert/op_delete/op_replace/op_mutate/
                        op_linearize/op_circularize/op_rotate
                     -> ConstructModel(record).insert/delete/replace/mutate/rotate/set_topology
                     -> to_record() -> SeqIO.write(genbank)
```

其他脚本（如 `write_dna.py` 的 feature 序列化）通过 `sg_common.features_to_dict` 间接调用 `feature_to_dict`。

### 5.4 科学性说明

- 适用边界：编辑操作只处理序列与 feature 坐标，不自动设计引物、不验证阅读框；读框 QC 由 `validate_construct.py` 承担。
- 已知限制：`mutate` 直接替换碱基，不校验密码子、剪接或调控元件；`rotate` 仅在 `origin0 != 0` 时重写拓扑，`origin0 == 0` 且传了 `topology` 时只改拓扑不旋转。
- 对应测试：`tests/test_v03.py` 的 `ConstructModelTests`（4 个测试）、`tests/test_v05.py` 的 `FeatureMigrationOrderTests`（正/负链部分跨原点、`join`/`order` 保持、跨原点 CDS 提取翻译与 qualifier 保持）。

## 6. `scripts/parse_dna.py`：结构化读取

### 6.1 技术原理

`parse_dna.py` 是“读取”工作流的第一入口。核心函数：

| 函数 | 签名/行号 | 作用 |
|---|---|---|
| `parse_primers` | `parse_primers(record)` `parse_dna.py:13` | 提取 `primer_bind` 或类型含 `primer` 的 feature |
| `main` | `main()` `parse_dna.py:31` | 解析 CLI 参数，加载序列，输出 JSON/文本 |

`parse_primers` 对每个 primer 输出：`name`、`type`、1-based 闭区间 `start/end`、`strand`（0 表示无链）、`sequence`（`f.extract(record.seq)`）、`qualifiers`（`parse_dna.py:19-27`）。

`main` 输出字段（`parse_dna.py:41-53`）：

```text
source, format, id, name, description(截断500字符), length,
topology, dna(是否全部为ACGTN), features, primers, feature_count
```

`--seq-limit N` 额外输出 `sequence_preview`（前 N bp，`parse_dna.py:54-55`）。`--json` 走 `jprint` 信封；文本模式打印标题、长度、拓扑、描述、features 与 primers（`parse_dna.py:57-72`）。

#### 6.1.1 输出示例

对一条 3,500 bp 环状质粒运行 `python scripts/parse_dna.py plasmid.dna --seq-limit 20 --json`，得到的成功信封形如：

```json
{
  "schema_version": "0.5.0",
  "ok": true,
  "command": "parse_dna.py",
  "data": {
    "source": "plasmid.dna",
    "format": "snapgene",
    "id": "pDONR201",
    "name": "pDONR201",
    "description": "...",
    "length": 3500,
    "topology": "circular",
    "dna": true,
    "features": [
      {
        "name": "attP1",
        "type": "misc_feature",
        "strand": 1,
        "start": 100,
        "end": 150,
        "qualifiers": {},
        "location": {
          "coordinate_system": "0-based-half-open",
          "operator": null,
          "parts": [{"start0": 99, "end0": 150, "start": 100, "end": 150, "strand": 1}],
          "wraps_origin": false
        }
      }
    ],
    "primers": [],
    "feature_count": 12,
    "sequence_preview": "ACGTACGTACGTACGTACGT"
  },
  "warnings": []
}
```

要点：`data.features` 中每个 feature 同时有 1-based 顶层 `start/end` 和 `location.parts` 中的 0-based/1-based 双坐标；`topology` 直接决定后续 `draw_map.py` 选择环形还是线性图谱。`sequence_preview` 仅用于人工核对，不代表完整序列。

### 6.2 生物原理

GenBank feature 表中的 `primer_bind` 表示引物结合位点，通常带有 `label` 或 `gene` qualifier。SnapGene 导出时常把引物作为独立对象，读回后可能落在 `primer_bind` feature 中。`parse_primers` 用 `f.extract(record.seq)` 取回引物实际序列，避免手工拼接。CDS、gene、promoter 等 feature 则通过 `features_to_dict` 保持位置结构。

### 6.3 实现路径

```
CLI main -> load_seq(source) -> str(record.seq)
         -> features_to_dict(record) / parse_primers(record)
         -> result dict -> jprint (JSON) 或文本报告
```

### 6.4 科学性说明

- 适用边界：`parse_dna.py` 不修改文件，不验证 feature 坐标是否合法；它只做结构化读取。坐标合法性由 `validate_construct.py` 检查。
- 容错：`.dna` 解析失败会自动回退 `snapgene_reader`（`sg_common.py:151-160`）；文本编码先 `utf-8-sig` 再 `latin-1`。
- 已知限制：`dna` 字段只判断是否全为 `ACGTN`，IUPAC 简并碱基（如 R/Y）会使 `dna=false`；`description` 截断到 500 字符。
- 对应测试：`tests/test_smoke.py` 通过 `scripts/smoke_core.py` 检查缺失路径报错（`smoke_core.py` P1 “missing path reported”）。

## 7. `scripts/write_dna.py`：格式写出

### 7.1 技术原理

`write_dna.py` 支持 4 种输出格式：`genbank`、`snapgene-gb`、`dna`、`fasta`。关键函数：

| 函数 | 签名/行号 | 作用 |
|---|---|---|
| `attach_features` | `attach_features(record, feat_path)` `write_dna.py:24` | 从 JSON 文件附加 feature（1-based 闭区间） |
| `_ensure_annotations` | `_ensure_annotations(record)` `write_dna.py:37` | 确保 `molecule_type` 与 `topology` 存在 |
| `_snapgene_annotated` | `_snapgene_annotated(record)` `write_dna.py:44` | 加入 SnapGene 能识别的 GenBank 标记 |
| `_strand_char` | `_strand_char(strand)` `write_dna.py:62` | 将 `-1` 映射为 `"-"`，其他映射为 `"+"` |
| `write_native_dna` | `write_native_dna(record, out_path)` `write_dna.py:66` | 用 `sgffp` 写出原生 SnapGene `.dna` |
| `main` | `main()` `write_dna.py:103` | CLI 入口 |

#### 7.1.1 `snapgene-gb` 的构造

`_snapgene_annotated` 在 `_ensure_annotations` 后把 `record.name` 改为 `"Exported"`，并追加一个 `Reference`：

```python
ref.title = "Direct Submission"
ref.journal = "Exported from snapgene-dna-design (SnapGene)"
ref.authors = "."
```

（`write_dna.py:50-58`）。这样写出的 GenBank 带 SnapGene 能识别的“Direct Submission + SnapGene journal”标记，SnapGene 打开时能解码颜色/方向，不产生 phantom feature。函数使用真实 `Reference` 对象而非字符串后处理，保证 LOCUS 与 reference 格式合法（`write_dna.py:44-49`）。

#### 7.1.2 原生 `.dna` 写出

`write_native_dna` 使用 `sgffp`：

- `SgffObject.new(str(record.seq), topology=topology(record))` 创建对象（`write_dna.py:72-73`）。
- primer 类型 feature 用 `sg.add_primer(name, seq, bind_position, bind_strand)` 写出，`bind_position` 取 `f.location.start`（0-based），strand 经 `_strand_char` 转换（`write_dna.py:75-84`）。
- 其他 feature 读取 `label`/`gene`/`id` 作为名字，把 `CompoundLocation` 的每个 part 转为 `SgffSegment(start, end)`，整体作为 `SgffFeature` 写出（`write_dna.py:85-98`）。
- `SgffWriter.to_file(sg, out_path)` 写文件（`write_dna.py:99`）。

#### 7.1.3 CLI 主流程

`main`：`load_seq` → 可选 `--name` 改 id/name → 可选 `--features-json` 附加 feature → 按格式写文件（`write_dna.py:114-135`）。`dna` 格式且存在 feature 时追加 warning：原生 `.dna` 保留序列、拓扑、feature 段和 strand，但不保证所有 qualifier/notes/history（`write_dna.py:137-143`）。

### 7.2 生物原理

GenBank 平面文件格式（LOCUS/DEFINITION/ACCESSION/FEATURES/ORIGIN）是 INSDC 标准序列交换格式。SnapGene 能读取带特定 reference 标记的 GenBank 并还原颜色和方向信息。原生 `.dna` 是 SnapGene 的二进制 TLV 格式，`sgffp` 是 MIT 许可的 Python 写出器。两条路径的差异本质上是“信息保真度”与“可直接打开”的权衡：`snapgene-gb` 是信息更全的权威交付格式，`.dna` 是方便打开的原生副本。

### 7.3 实现路径

```
write_dna.py main -> load_seq(source) -> [attach_features]
                   -> genbank: SeqIO.write(record, "genbank")
                   -> fasta:   SeqIO.write(record, "fasta")
                   -> snapgene-gb: _snapgene_annotated -> SeqIO.write(record, "genbank")
                   -> dna: write_native_dna(record, out) -> sgffp
                   -> result dict -> jprint/文本
```

### 7.4 科学性说明

- 适用边界：`write_dna.py` 可以接受裸序列字符串作为 `source`；当来源是 FASTA 时拓扑默认线性。
- 已知限制：`--features-json` 只支持简单 `FeatureLocation`，不创建复合位置；原生 `.dna` 写出的 qualifiers 层级与 SnapGene 官方存在差异，需用 `validate_roundtrip.py` 核对。
- 对应测试：`scripts/smoke_core.py` 中“P0: write_dna snapgene-gb round-trips cleanly”与“P0: native .dna write + re-read round-trip”；`tests/test_v03.py` 的 `ContractAndRoundTripTests.test_internal_snapgene_genbank_roundtrip`。

## 8. `scripts/edit_plasmid.py`：质粒编辑与 feature 迁移

### 8.1 技术原理

`edit_plasmid.py` 是用户侧编辑入口，所有操作用 1-based 闭区间，内部转 0-based 调 `ConstructModel`。操作函数：

| 函数 | 签名/行号 | 边界检查 |
|---|---|---|
| `op_insert` | `op_insert(record, pos, seq)` `edit_plasmid.py:24` | `1 <= pos <= len+1`；序列 `normalize_dna` |
| `op_delete` | `op_delete(record, start, end)` `edit_plasmid.py:34` | `1 <= start <= end <= len` |
| `op_replace` | `op_replace(record, start, end, seq)` `edit_plasmid.py:43` | 先规范化序列，再检查区间 |
| `op_mutate` | `op_mutate(record, mutations)` `edit_plasmid.py:53` | 每个 `pos:base` 的 `1 <= pos <= len` 且 base 为 IUPAC 单字符 |
| `op_linearize` | `op_linearize(record, pos)` `edit_plasmid.py:72` | 输入必须 `circular`，`1 <= pos <= n` |
| `op_circularize` | `op_circularize(record)` `edit_plasmid.py:82` | 无额外检查 |
| `op_rotate` | `op_rotate(record, pos)` `edit_plasmid.py:86` | 输入必须 `circular`，`1 <= pos <= n` |

关键实现：

- `op_insert`：`ConstructModel(record).insert(pos - 1, seq).to_record()`（`edit_plasmid.py:31`）。
- `op_delete`：`ConstructModel(record).delete(start - 1, end).to_record()`（`edit_plasmid.py:40`）。
- `op_replace`：`ConstructModel(record).replace(start - 1, end, seq).to_record()`（`edit_plasmid.py:50`）。
- `op_mutate`：解析 `pos:base` 为 `(pos-1, base)` 列表后调 `mutate`（`edit_plasmid.py:53-69`）。
- `op_linearize`：`ConstructModel(record).rotate(pos - 1, topology="linear").to_record()`，新序列为 `[pos..end] + [1..pos-1]`（`edit_plasmid.py:72-79`）。
- `op_rotate`：`ConstructModel(record).rotate(pos - 1, topology="circular").to_record()`（`edit_plasmid.py:86-91`）。

`main` 根据 `--op` 分派，缺参时报 `SystemExit`（`edit_plasmid.py:94-155`）。输出固定为 GenBank（`SeqIO.write(result, fh, "genbank")`，`edit_plasmid.py:157-158`）。JSON 摘要包含 `op`、`out_file`、`length_before`、`length_after`、`topology`、`feature_count`（`edit_plasmid.py:160-167`）。

### 8.2 生物原理

- **插入**：在环状质粒的特定位点插入片段是克隆构建的基本操作。1-based `pos` 表示“插在第 pos 位碱基之前”，因此 `pos = len+1` 合法，表示追加到线性序列末尾。
- **线性化**：把环状质粒在某一碱基处切开并重写原点，分子本身不变，只是坐标原点和拓扑标记改变。实现上用 `rotate(pos-1, topology="linear")`，生物学上等价于限制酶单切线性化。
- **环化**：把线性 DNA 两端连接，只改变拓扑标记，不改变序列；磷酸二酯键成环的化学过程不在计算模型中。
- **feature 迁移**：插入/删除会改变后续所有坐标；不迁移 feature 会导致注释整体漂移，因此该模块逐段迁移 `CompoundLocation`。

### 8.3 实现路径

```
CLI main -> load_seq(source) -> 按 --op 调用 op_* -> ConstructModel
         -> to_record() -> SeqIO.write(genbank) -> JSON 摘要
```

### 8.4 科学性说明

- 适用边界：`edit_plasmid.py` 输出 GenBank，不输出 `.dna`；需要 `.dna` 交付时接 `write_dna.py` 或 `export_delivery_bundle.py`。
- 已知限制：`op_mutate` 支持多突变但都是单碱基替换，不支持删除插入复合；`op_circularize` 不校验线性序列两端是否可连接（不检查 5' 磷酸/3' 羟基，那是化学步骤）。
- 对应测试：`tests/test_v03.py` 的 `ConstructModelTests.test_linearize_accepts_compound_feature`；`tests/test_v05.py` 的 `FeatureMigrationOrderTests` 覆盖跨原点与 `join`/`order` 保持。

## 9. `scripts/convert.py`：格式转换

### 9.1 技术原理

`convert.py` 在 `genbank`、`fasta`、`embl`、`snapgene` 四种目标格式之间转换。

- `FORMAT_EXT` 定义目标扩展名：`genbank -> .gb`、`fasta -> .fa`、`embl -> .embl`、`snapgene -> .dna`（`convert.py:16-21`）。
- `WRITERS` 把 `genbank`/`fasta`/`embl` 映射为 `SeqIO.write` lambda（`convert.py:23-27`）。
- `convert_file(src, dst, out_format)`：`load_seq` 读取后，若目标是 `snapgene` 则导入 `write_dna.write_native_dna` 写出；否则补 `molecule_type="DNA"` 后调对应 writer（`convert.py:30-41`）。
- `main` 支持单文件或 `--dir` 目录模式；目录模式遍历常见序列扩展名，对每个文件 try/except 记录 `ok`/`error`（`convert.py:57-79`）。

### 9.2 生物原理

格式转换不改变序列本身，但不同格式对 feature、qualifier、拓扑、参考文献的支持不同：

- GenBank/EMBL 保留 feature 与注释，EMBL 与 GenBank 在 qualifier 细节上存在差异。
- FASTA 只有序列与标题，拓扑与 feature 丢失。
- 原生 `.dna` 是 SnapGene 二进制，保留序列、拓扑、feature 段和 strand，qualifiers 可能简化。

因此 `convert.py` 不应被理解为“无损转换”。需要无损交付时，权威格式是 GenBank（`SKILL.md` 注意事项明确“权威交付文件为标准 GenBank；原生 `.dna` 是方便打开的副本，不是信息真值源”）。

### 9.3 实现路径

```
convert.py main -> 单文件: convert_file(src, dst, format)
                -> load_seq -> [snapgene?] write_native_dna
                            -> [其他] SeqIO.write
                -> 目录: 逐个 try/except -> results -> jprint/文本
```

### 9.4 科学性说明

- 适用边界：目标 `snapgene` 实际调用 `write_native_dna`，等价于 `write_dna.py --format dna`。
- 容错：目录模式不会因为单个文件失败而中止，错误记入 `results`（`convert.py:71-72`）。
- 已知限制：不支持 `snapgene-gb` 这个 write_dna 专有方言；不做 feature 兼容性预检。
- 对应测试：`scripts/smoke_core.py` 与 `tests/test_smoke.py` 覆盖常见转换命令；`tests/test_readme_commands.py` 检查 README/SKILL 中代表性命令可运行。

## 10. `scripts/batch.py`：批量操作流水线

### 10.1 技术原理

`batch.py` 对一个目录中的全部序列文件应用同一种操作。支持 4 种操作：`parse`、`validate`、`sites`、`convert`。

- `SEQ_EXTS` 定义支持扩展名（`batch.py:18`）。
- `list_files(directory)` 返回按文件名排序的序列文件列表（`batch.py:21-23`）。
- `op_parse(path)`：`load_seq` 后返回 `file/format/length/topology/feature_count`（`batch.py:26-30`）。
- `op_validate(path)`：`load_seq` 后调 `validate_construct.validate(rec)`，返回 `file` 加 `r["summary"]`（`batch.py:33-37`）。
- `op_sites(path)`：调 `find_sites.digest_report` 对 `find_sites.COMMON_ENZYMES[:6]` 做酶切摘要，返回 `file/cut_count/fragments[:8]`（`batch.py:40-46`）。
- `op_convert(path, out_format)`：调 `convert.convert_file` 输出到同目录同 stem 不同扩展名（`batch.py:49-57`）。
- `main` 逐文件 try/except，错误记入 `results`（`batch.py:77-89`）；输出 JSON 报告或文本摘要（`batch.py:91-104`）。

### 10.2 生物原理

批量 parse/validate 对应质粒库筛选流程：对一组候选克隆做拓扑、feature 数量、QC 检查。批量 sites 对前 6 个常用酶做快速酶切概览，帮助判断哪些载体可能是单切点骨架。批量 convert 用于统一交付格式。生物学上，限制酶切片段数量与拓扑有关：环状序列单切点产生 1 条线性片段，线性序列单切点产生 2 条片段；`find_sites.digest_report` 负责这一计算，`batch.py` 只是批处理适配层。

### 10.3 实现路径

```
batch.py main -> list_files(dir) -> 按 --op 分派
             -> op_parse / op_validate / op_sites / op_convert
             -> results -> sg_common.jprint / 文本
```

### 10.4 科学性说明

- 适用边界：`batch.py` 是薄封装，实际解析与验证语义由 `sg_common`、`validate_construct`、`find_sites`、`convert` 提供。
- 已知限制：只支持 4 种操作；`sites` 只查 6 个酶；`convert` 输出到源目录同 stem，可能覆盖既有文件。
- 对应测试：`scripts/smoke_core.py` 的批处理相关检查；`tests/test_smoke.py` 执行 smoke 全流程。

## 11. `scripts/validate_construct.py`：构建体一键 QC

### 11.1 技术原理

`validate_construct.py` 对构建体做一次只读检查，错误级别分 `error`、`warning`、`ok` 三档。

- `QC_ENZYMES`：10 个常用单切点酶（`validate_construct.py:18`）。
- `_cds_translation(seq, start0, end0, strand)`：截取片段，负链先反向互补，再翻译（`validate_construct.py:21-25`）。函数目前主要用于 CDS 提取逻辑的参照，实际 validate 使用 `feature.extract`。
- `validate(record)` 是核心函数（`validate_construct.py:28-126`）：

| 检查项 | 逻辑 | 行号 |
|---|---|---|
| topology | 显式 `circular`/`linear` | `validate_construct.py:34-36` |
| length | 空序列为 `error` | `validate_construct.py:37-40` |
| feature_count | 仅报告数量 | `validate_construct.py:42-44` |
| feature_coordinates | 对每个 feature 的每个 segment 检查 `1 <= start <= end <= n` | `validate_construct.py:46-58` |
| cds_frame | CDS 提取长度是否 3 的倍数；`codon_start` 后截断 | `validate_construct.py:60-73` |
| cds_premature_stop | 内部终止密码子为 `error`，末端终止为 `ok`，无终止为 `warning` | `validate_construct.py:74-90` |
| unique_cutter | 10 个酶中单切点 `ok`，多切点 `warning` | `validate_construct.py:92-105` |
| primers | 无 primer 为 `warning` | `validate_construct.py:107-110` |
| junction | 多段 feature 数量 | `validate_construct.py:112-115` |

`validate` 返回 `{id, length, topology, summary:{errors, warnings, pass}, checks}`（`validate_construct.py:117-126`）。`main` 在 JSON 模式走 `jprint`；文本模式打印逐项报告；最后 `SystemExit(0 if pass else 1)`（`validate_construct.py:129-149`）。

#### 11.1.1 输出示例

对一个 2,900 bp 环状构建体运行 `python scripts/validate_construct.py construct.gb --json`，核心结构为：

```json
{
  "schema_version": "0.5.0",
  "ok": true,
  "command": "validate_construct.py",
  "data": {
    "id": "construct",
    "length": 2900,
    "topology": "circular",
    "summary": {"errors": 0, "warnings": 1, "pass": true},
    "checks": [
      {"check": "topology", "status": "ok", "detail": "circular"},
      {"check": "length", "status": "ok", "detail": "2900 bp"},
      {"check": "feature_count", "status": "ok", "detail": "8 features"},
      {"check": "cds_frame", "status": "ok", "feature": "GOI", "detail": "in-frame, terminal stop"},
      {"check": "unique_cutter", "status": "ok", "detail": "EcoRI unique at 123"},
      {"check": "primers", "status": "warning", "detail": "0 primer(s)"},
      {"check": "junction", "status": "ok", "detail": "1 multi-segment feature(s)"}
    ]
  },
  "warnings": []
}
```

当存在 `error` 级检查时，`ok` 为 `false`，`main` 退出码 1。`batch.py --op validate` 只取 `data.summary` 做批量摘要，因此单文件与批量 QC 的判定阈值完全一致。

### 11.2 生物原理

- **CDS 读框**：蛋白质编码序列长度必须是 3 的倍数，且内部终止密码子意味着提前终止，通常是注释错误或序列移码。`codon_start` 是 GenBank qualifier，表示从 CDS 第几位开始读码（1/2/3）；`transl_table` 指定遗传密码表，默认 1（标准密码表）。BioPython `Seq.translate(table=...)` 完成翻译。
- **唯一酶切位点**：单切点酶是质粒线性化与克隆策略的基础。`validate_construct` 只检查 10 个常用酶，不替代 `find_sites.py` 的完整酶切分析。
- **引物与 junction**：引物存在性和多段 feature 数量用于提示交付前的人工复核。

### 11.3 实现路径

```
validate_construct.py main -> load_seq -> validate(record)
                           -> checks -> summary -> jprint / 文本
                           -> exit 0 或 1
```

`batch.py --op validate` 调用同一 `validate` 函数，保证单文件与批量结果口径一致（`batch.py:33-37`）。

### 11.4 科学性说明

- 适用边界：只做静态序列与注释检查，不做结构模拟、不做引物特异性/发夹/二聚体计算、不做序列比对。
- 已知限制：`cds_premature_stop` 对无终止密码子的 CDS 只给 `warning`，因为部分 CDS 可能天然是 partial；`unique_cutter` 使用 `enzyme_sites`，其底层 `Bio.Restriction.search` 的例外会返回空列表。
- 对应测试：`tests/test_v03.py` 的 JSON 契约测试间接覆盖；`scripts/smoke_core.py` 中 validate 相关检查。

## 12. `scripts/validate_roundtrip.py`：语义往返验证

### 12.1 技术原理

`validate_roundtrip.py` 回答“导出后读回是否还是同一个构建体”。核心函数：

| 函数 | 签名/行号 | 作用 |
|---|---|---|
| `_label` | `_label(feature)` `validate_roundtrip.py:16` | 取 `label`/`gene`/`id` 作为 feature 名 |
| `_feature_core` | `_feature_core(feature)` `validate_roundtrip.py:23` | feature 核心签名：type、name、operator、parts 的 `(start, end, strand)` 元组 |
| `_feature_qualifiers` | `_feature_qualifiers(feature)` `validate_roundtrip.py:39` | 核心签名 + 排序后的 qualifier 键值 |
| `_feature_set` | `_feature_set(record, with_qualifiers=False)` `validate_roundtrip.py:47` | 过滤 `source` 后排序的 feature 集合 |
| `IMPORTANT_QUALIFIER_KEYS` | 常量 `validate_roundtrip.py:56` | `translation/codon_start/gene/label/product/directionality/transl_table` |
| `_qualifier_differences` | `_qualifier_differences(expected, observed)` `validate_roundtrip.py:62` | 逐 feature 比较 qualifier 缺失/新增/变化 |
| `_qualifier_risk` | `_qualifier_risk(differences)` `validate_roundtrip.py:120` | `none`/`safe`/`important` |
| `compare_records` | `compare_records(expected, observed)` `validate_roundtrip.py:126` | 独立比较序列、拓扑、feature 核心、qualifier |
| `_write` | `_write(record, fmt, path)` `validate_roundtrip.py:149` | 按格式写到临时文件 |
| `_find_snapgene` | `_find_snapgene(explicit=None)` `validate_roundtrip.py:162` | 显式参数 → `SNAPGENE_EXE` → Program Files 自动发现 |
| `_official_convert` | `_official_convert(...)` `validate_roundtrip.py:175` | 调用 SnapGene `--convert`，90 秒超时 |
| `_add_qualifier_warnings` | `_add_qualifier_warnings(...)` `validate_roundtrip.py:200` | 把 qualifier 差异写进 warnings |
| `validate` | `validate(source, fmt, snapgene_exe=None, require_snapgene=False, strict=False)` `validate_roundtrip.py:212` | 主流程 |

#### 12.1.1 比较语义

`compare_records` 的 `passed` 定义为核心语义通过：序列大小写不敏感相等、拓扑相等、feature 核心集合相等（`validate_roundtrip.py:126-146`）。`qualifiers_equal` 单独计算，不参与 `passed`，而是通过 `strict_passed` 控制。`_feature_core` 把 `location.operator`（`join`/`order`）纳入核心签名（`validate_roundtrip.py:23-36`），因此 `order` 被改写成 `join` 会直接导致 `features_equal=false`；`tests/test_snapgene_compatibility.py` 的 `test_operator_participates_in_core_comparison` 验证了这一点。

#### 12.1.2 主流程 `validate`

1. `load_seq(source)` 得到期望记录（`validate_roundtrip.py:213`）。
2. 在 `tempfile.TemporaryDirectory` 中按 `fmt` 写出（`validate_roundtrip.py:215-218`）。
3. 读回导出文件，期间用 `warnings.catch_warnings(record=True)` 捕获 BioPython 解析警告（`validate_roundtrip.py:219-227`）。
4. 内部比较 `internal_roundtrip`。
5. 若找到 SnapGene 可执行文件，调用官方转换：`dna` 导出转 `GenBank - Standard`，`snapgene-gb`/`genbank` 导出转 `SnapGene DNA`（`validate_roundtrip.py:230-239`）。
6. 读回官方产物并比较，收集 parser warnings（`validate_roundtrip.py:240-254`）。
7. 计算 `core_passed`、`strict_passed`、`passed`、`lossless` 与 `delivery_grade`（`validate_roundtrip.py:261-287`）。

`delivery_grade` 取值：`failed`、`core-compatible`、`core-compatible-with-safe-differences`、`core-compatible-with-important-differences`、`lossless`（`validate_roundtrip.py:269-287`）。`lossless` 要求 `strict_passed` 且无 warnings。

#### 12.1.3 官方 SnapGene 调用

`_official_convert` 使用 `subprocess.run([exe, "--convert", target_format, "--input", ..., "--output", ...])`，90 秒超时，Windows 下隐藏窗口（`validate_roundtrip.py:175-197`）。转换失败或未生成输出时抛 `RuntimeError`。SnapGene 6.0.2 官方导出的 `GenBank - Standard` 可能触发 BioPython 非标准 LOCUS 列警告，`validate` 将其收集到 `warnings`，不影响序列/拓扑/feature 判断（`SKILL.md` 注意事项）。

### 12.2 生物原理

往返验证的生物意义：分子克隆构建体交付后，接收方打开文件看到的序列、拓扑和 feature 必须与设计一致。序列决定产物，拓扑决定复制/酶切行为，feature 决定注释（CDS、启动子、复制起点）。`validate_roundtrip` 把“看到的一致”拆成序列、拓扑、feature 核心、qualifier 四个可独立判定的层次，避免把 qualifier 丢失（如 `translation`）和序列丢失混为一谈。

### 12.3 实现路径

```
validate_roundtrip.py main -> validate(source, fmt, ...)
    -> load_seq(source)
    -> tempdir 写出 -> load_seq(exported) -> compare_records
    -> [SnapGene 存在] _official_convert -> load_seq -> compare_records
    -> 汇总 delivery_grade -> jprint / 文本 -> exit
```

### 12.4 科学性说明

- 适用边界：验证的是文件语义，不是实验正确性；`passed` 不代表克隆能成功。
- 已知限制：官方核验需要本机 SnapGene 许可证；`--strict` 才把 qualifier 差异作为失败，默认只警告；内部解析器的警告会进入 `warnings` 但通常不影响核心判定。
- 对应测试：`tests/test_v03.py` 的 `ContractAndRoundTripTests`；`tests/test_v04.py` 的 `test_roundtrip_reports_and_can_require_qualifier_equality`；`tests/test_rich_fixtures.py` 的 `RichFixtureRoundTripTests`；`scripts/validate_rich_fixtures.py` 门禁。

## 13. `scripts/snapgene_compatibility.py`：导出前兼容性预检

### 13.1 技术原理

`snapgene_compatibility.py` 在导出前按格式报告已知的 SnapGene 往返风险。

- `_values`/`_name`/`_finding` 是 feature qualifier 读取与 finding 构造辅助（`snapgene_compatibility.py:13-32`）。
- `_format_result(findings)` 把 finding 分 `core`/`strict` 两级，映射为 `safe`、`core-compatible`、`manual-review-required`（`snapgene_compatibility.py:35-50`）。
- `analyze_record(record, source_format=None)` 是核心（`snapgene_compatibility.py:53-135`）：

| 风险 | 格式 | 级别 | 代码 | 行号 |
|---|---|---|---|---|
| `order` 复合位置不保 | gb + dna | core | `ORDER_LOCATION_NOT_PRESERVED` | `snapgene_compatibility.py:62-68` |
| 多段位置在 `.dna` 中可能被合并/重塑 | dna | core | `DNA_COMPOUND_LOCATION_RISK` | `snapgene_compatibility.py:69-72` |
| 非 ASCII feature 名在 `.dna` 中可能乱码 | dna | core | `DNA_UNICODE_FEATURE_NAME_RISK` | `snapgene_compatibility.py:74-78` |
| `.dna` 写出不保留 `label` 以外 qualifier | dna | strict | `DNA_QUALIFIER_LOSS` | `snapgene_compatibility.py:80-86` |
| 多值 `note` 可能被 SnapGene 截断 | gb | strict | `SNAPGENE_MULTIVALUE_NOTE_NORMALIZATION` | `snapgene_compatibility.py:88-91` |
| `db_xref` 前缀可能被移除 | gb | strict | `SNAPGENE_DB_XREF_NORMALIZATION` | `snapgene_compatibility.py:92-95` |
| `synonym` 可能丢失 | gb | strict | `SNAPGENE_SYNONYM_LOSS` | `snapgene_compatibility.py:96-99` |
| `translation` 可能被 SnapGene 重算 | gb | strict | `SNAPGENE_TRANSLATION_RECOMPUTED` | `snapgene_compatibility.py:100-103` |

- 推荐策略：`snapgene-gb` core-safe 时首选 `snapgene-gb`；否则 `genbank-authoritative-manual-review`（`snapgene_compatibility.py:105-135`）。
- `analyze(source)` 加载序列后调 `analyze_record`（`snapgene_compatibility.py:138-140`）。
- CLI `main` 支持 `--json`，失败路径 `OSError/ValueError` 转 `SystemExit`（`snapgene_compatibility.py:143-160`）。

### 13.2 生物原理

预检的生物意义在于把“文件兼容性”与“实验可行性”分开。`SnapGene` 官方对 GenBank qualifier 的规范化（重算 translation、剥除 db_xref 前缀、截断多值 note）不改变序列，但会改变注释信息；对 `order` 位置的不保留会改变 feature 坐标语义。`analyze_record` 末尾固定写入 warning：兼容性只描述文件语义，不描述引物质量、生物活性、特异性或实验成功（`snapgene_compatibility.py:131-134`）。

### 13.3 实现路径

```
snapgene_compatibility.py main -> analyze(source)
    -> load_seq -> analyze_record
    -> 逐 feature 检查 -> gb_findings/dna_findings
    -> _format_result -> recommendation -> jprint/文本
```

### 13.4 科学性说明

- 适用边界：预检只覆盖已知的 SnapGene 往返限制，未知的 core 损失仍由 `validate_roundtrip.py` 和 `validate_rich_fixtures.py` 门禁捕获。
- 已知限制：`DNA_QUALIFIER_LOSS` 对只带 `label` 的 feature 不报，因为原生 `.dna` 写出器保留 `label`；不带 qualifier 的 feature 也安全。
- 对应测试：`tests/test_snapgene_compatibility.py` 的 `SnapGeneCompatibilityTests`（11 个测试）。

## 14. `scripts/export_delivery_bundle.py`：安全交付包

### 14.1 技术原理

`export_delivery_bundle.py` 生成一个带审计清单的交付目录。

- `_sha256(path)`：大写十六进制 SHA-256（`export_delivery_bundle.py:16-17`）。
- `_entry(path, role, fmt)`：生成文件条目 `{path, role, format, size, sha256}`（`export_delivery_bundle.py:20-27`）。
- `build_bundle(source, out_dir, name=None, allow_core_risk=False, require_dna=False)` 主流程（`export_delivery_bundle.py:30-90`）：

1. `load_seq` 读取源文件。
2. `analyze_record` 做兼容性预检。
3. 创建输出目录，文件名 stem 做安全化（只保留字母数字、`-`、`_`）。
4. 始终写出 `*.authoritative.gb`（权威 GenBank，`SeqIO.write(..., "genbank")`，`export_delivery_bundle.py:40-43`）。
5. 若 `.dna` 预检 `core_safe` 或用户显式 `allow_core_risk=True`，则写 `*.dna`，角色为 `convenience` 或 `core-risk-opt-in`（`export_delivery_bundle.py:46-53`）。
6. `require_dna=True` 且 `.dna` 未写出时 `ValueError`（`export_delivery_bundle.py:54-57`）。
7. 写 `compatibility-report.json`（`export_delivery_bundle.py:59-63`）。
8. 写 `DELIVERY-MANIFEST.json`，包含 `schema_version`、`source`、`source_format`、`delivery_policy`、`native_dna_written`、`native_dna_core_risk_accepted`、`manual_review_required`、`files`（`export_delivery_bundle.py:65-80`）。
9. 返回 `bundle_dir`、`manifest`、`native_dna_written`、`manual_review_required`、`files`、`warnings`（`export_delivery_bundle.py:81-90`）。

- CLI `main` 支持 `--out-dir`、`--name`、`--allow-core-risk`、`--require-dna`、`--json`（`export_delivery_bundle.py:93-120`）。

### 14.2 生物原理

交付策略“权威 GenBank + 安全的便利副本”对应实验记录规范：权威文件保存完整注释，便利副本用于快速查看。SHA-256 清单保证接收方能核对文件未被篡改。`--allow-core-risk` 是显式人工确认，不是静默降级；`--require-dna` 在风险未接受时直接失败，避免为了满足扩展名要求而静默丢语义（`SKILL.md` 注意事项）。

### 14.3 实现路径

```
export_delivery_bundle.py main -> build_bundle
    -> load_seq -> analyze_record -> [authoritative.gb]
    -> [core_safe or allow_core_risk] write_native_dna
    -> compatibility-report.json -> DELIVERY-MANIFEST.json
    -> result -> jprint/文本
```

### 14.4 科学性说明

- 适用边界：交付包是文件层审计，不验证实验设计。
- 已知限制：`build_bundle` 不重算 feature，只按预检结果决定是否附带 `.dna`。
- 对应测试：`tests/test_snapgene_compatibility.py` 中 `test_bundle_omits_risky_native_file_and_keeps_authoritative_gb`、`test_bundle_can_explicitly_opt_in_to_core_risk`、`test_require_dna_fails_before_claiming_success`、`test_delivery_cli_json_text_and_blocking_paths`。

## 15. `scripts/draw_map.py`：SVG 质粒图谱

### 15.1 技术原理

`draw_map.py` 生成 SVG 质粒图谱，支持环形与线性两种拓扑、`light`/`dark` 双主题。

- 类型调色板：`TYPE_COLORS_LIGHT`（`draw_map.py:17-22`）与 `TYPE_COLORS_DARK`（`draw_map.py:23-28`），默认灰（`draw_map.py:29-30`）。类型匹配大小写不敏感。
- `THEME` 聚合背景、文字、骨架、调色板（`draw_map.py:32-41`）。
- `_pt(cx, cy, r, t)`：按分数 `t` 从 12 点方向顺时针计算圆上点（`draw_map.py:48-51`）。
- `_arc(cx, cy, t1, t2, r)`：用 SVG 弧线路径画弧，`large` 标志在弧长超过半圆时置 1（`draw_map.py:54-58`）。
- `_esc(s)`：XML 转义（`draw_map.py:61-63`）。
- `draw_circular(record, theme_name="light", size=820)`：画背板、骨架圆、feature 弧、引线标签（去重叠）、中心标题、图例（`draw_map.py:66-151`）。
- `draw_linear(record, theme_name="light", size=900, height=260)`：画直线骨架、每 500 bp 刻度、feature 矩形、交替行标签、标题（`draw_map.py:154-202`）。
- `main`：`load_seq` 后按拓扑选择 `draw_circular`/`draw_linear`，写 SVG 文件，输出 JSON 或文本摘要（`draw_map.py:205-235`）。

环形图的关键算法：

- feature 段 `[start, end]` 1-based 闭区间映射为 `t1=(start-1)/n`、`t2=end/n`（`draw_map.py:87-88`）。
- 相邻 feature 之间留 0.0006 分数的小视觉间隙（`draw_map.py:90-93`）。
- 标签去重叠：对宽度不小于 `max(40, n*0.008)` 的段计算中点角度，按角度排序后用 `MIN_GAP=17` 度最小间隔贪心选择，并处理 360 度回绕碰撞（`draw_map.py:97-116`）。
- 引线从 `r+11` 连到 `r_label-6`，标签文字根据左右半圆选择 `start/end/middle` 锚点（`draw_map.py:117-127`）。

### 15.2 生物原理

质粒图谱是分子克隆的通用交流形式。环状图谱按 12 点方向顺时针展开，符合 SnapGene 等工具的阅读习惯。feature 用颜色区分类型、用引线标注名字；跨原点 feature 通过 `segments` 画出多个弧段。图谱只反映 feature 的拓扑位置，不表示表达水平或生物学强度。

### 15.3 实现路径

```
draw_map.py main -> load_seq -> topology
    -> circular? draw_circular(record, theme) : draw_linear(record, theme)
    -> 写 SVG -> JSON/文本
```

### 15.4 科学性说明

- 适用边界：SVG 输出是可视化，不改变数据；线性图谱刻度固定 500 bp。
- 已知限制：标签去重叠用最小角度差，标签很多时会被丢弃；feature 名截断到 22/18 字符；不画酶切位点、不画 GC 含量、不画箭头表示方向。
- 对应测试：`scripts/smoke_core.py` 与 `tests/test_readme_commands.py` 覆盖 `draw_map.py` 可运行性。

## 16. `scripts/simulate_gel.py`：琼脂糖凝胶电泳模拟

### 16.1 技术原理

`simulate_gel.py` 用经验对数-线性模型估算片段迁移距离。

- `MARKERS`：`1kb`、`100bp`、`1kb-plus` 三套 ladder（`simulate_gel.py:17-21`）。
- `migration(size, lane_length=100, min_size=50, max_size=10000)`：

```python
lo, hi = math.log(min_size), math.log(max_size)
x = math.log(max(size, 1))
frac = (x - lo) / (hi - lo)
return lane_length * (1 - frac)
```

（`simulate_gel.py:24-29`）。`size` 钳制到至少 1 bp；片段越小 `frac` 越小、迁移距离越大。

- `band_row(lane_length, dist, symbol="#", width=1)`：生成一行条带（`simulate_gel.py:32-39`）。
- `main`：解析 `--fragments`、`--marker`、`--lane-length`，JSON 模式输出 `fragments` 与 `ladder` 的 `{size, migration}`；文本模式打印 marker/sample 泳道、迁移方向、片段位置表（`simulate_gel.py:42-85`）。

### 16.2 生物原理

琼脂糖凝胶电泳中，DNA 片段在电场中向正极迁移。迁移距离与片段分子量的对数近似成反比，这是经典核酸电泳分析的经验关系（Sambrook & Russell, Molecular Cloning: A Laboratory Manual）。`migration` 用 log(size) 的线性插值实现该关系；模型不包含琼脂糖浓度、电压、缓冲液、DNA 构象（超螺旋/线性/开环）和染料影响。`references/biological-parameters-sources.md` P27 把“大于 20 kb 提示电转化”等实验室共识类阈值追溯到 Sambrook & Russell。

### 16.3 实现路径

```
simulate_gel.py main -> 解析片段大小
    -> migration(s) / ladder migration
    -> JSON: jprint; 文本: band_row -> ASCII 泳道
```

### 16.4 科学性说明

- 适用边界：仅用于预览 PCR/酶切产物条带数量与相对位置，不能用于确定真实胶图。
- 已知限制：文本模式 sample 泳道只画最长迁移（最大 `migration`）的条带位置，实际每个片段都应在对应位置有条带；模型是经验近似，未标记为 `experimental` 但属于教学/预览级模拟，不应作为实验结论。
- 对应测试：`scripts/smoke_core.py` 中 `simulate_gel.py` 可运行性检查。

## 16A. 端到端数据流示例：从读取到交付

以下示例使用仓库 `fixtures/pDONR201.dna`，演示本章 13 个脚本中最关键的 7 步数据流。

**第 1 步：读取结构化信息。** `parse_dna.py` 通过 `load_seq` 先走 BioPython `SeqIO.read(handle, "snapgene")`，成功则返回 `("snapgene", SeqRecord)`；输出 JSON 中 `format` 为 `"snapgene"`，`topology` 从 `record.annotations["topology"]` 读取，feature 坐标全部为 1-based 闭区间。

**第 2 步：QC。** `validate_construct.py` 读回同一文件，检查 feature 坐标是否越界、CDS 是否读框内、是否有内部终止密码子、10 个常用酶是否单切点、是否缺少引物。若存在 `error`，退出码为 1，JSON 信封 `ok=false`。

**第 3 步：兼容性预检。** `snapgene_compatibility.py` 对 `pDONR201.dna` 逐 feature 扫描。若存在 `order` 复合位置，`snapgene-gb` 与 `dna` 都会标记 `ORDER_LOCATION_NOT_PRESERVED`（core 级），`manual_review_required=true`；若没有，推荐 `snapgene-gb`。

**第 4 步：编辑。** `edit_plasmid.py --op insert --pos 100 --seq AAAA --out edited.gb` 会把 1-based `pos=100` 转换为 `pos0=99`，调用 `ConstructModel.insert`，所有在插入点之后的 feature part 右移 4 bp，输出 GenBank。

**第 5 步：导出。** `write_dna.py edited.gb --out edited.dna --format dna` 调用 `write_native_dna`，用 `sgffp` 写出原生 `.dna`；primer feature 走 `add_primer`，复合位置 feature 拆成多个 `SgffSegment`。若需要 SnapGene 颜色/方向解码，则用 `--format snapgene-gb`。

**第 6 步：往返验证。** `validate_roundtrip.py edited.gb --format snapgene-gb --strict --json` 在临时目录写出 `skill-export.gb`，读回后比较序列、拓扑、feature 核心（含 operator）与 qualifier；本机有 SnapGene 时再调用官方转换核对。

**第 7 步：交付打包。** `export_delivery_bundle.py edited.gb --out-dir delivery --json` 生成 `*.authoritative.gb`、条件性 `*.dna`、`compatibility-report.json`、`DELIVERY-MANIFEST.json`，每个文件带 SHA-256。

这 7 步串起来就是 `SKILL.md:167-173` 标准工作流的工程实现：读取 → 理解 → 执行 → 编辑产出 → 验证。任何一步出现结构化错误（`jfail`）都应先解决该错误再继续，不把中间产物当作交付物。

## 17. 分子生物学依据与引用

本章及仓库代码引用的权威来源集中登记在 `references/biological-parameters-sources.md` 与 `references/biological-parameters-sources.json`。以下为本章涉及的主要依据；所有 DOI/URL 均来自仓库该文件，未额外编造。

| 主题 | 来源 | DOI/URL | 仓库引用位置 |
|---|---|---|---|
| 通用分子克隆实验（凝胶、酶切、转化等） | Sambrook J & Russell DW, Molecular Cloning: A Laboratory Manual | CSHL Press（仓库 P27 引用） | `references/biological-parameters-sources.md` P27 |
| Gibson 组装：overlap 长度 15–40 bp、推荐 ≤4–5 段 | Gibson et al. 2009, Nat Methods 6:343-345 | `https://doi.org/10.1038/nmeth.1318` | `references/biological-parameters-sources.md` P15/P17/P29；`rules/feasibility_rules.json` |
| Golden Gate：Type IIS 组装、≤8 段、内部位点禁止 | Engler et al. 2008, PLoS One 3:e3647 | `https://doi.org/10.1371/journal.pone.0003647` | `references/biological-parameters-sources.md` P18/P19 |
| NEB PCR/酶切/保护碱基官方协议 | NEB 官方指南与 FAQ | `https://www.neb.com/en/faqs/cleavage-close-to-the-end-of-dna-fragments`；`https://international.neb.com/applications/cloning-and-synthetic-biology/golden-gate-assembly` | `references/biological-parameters-sources.md` P10-P13/P19/P20/P21 |
| IDT 引物与 overlap 设计指南 | IDT 官方支持文档 | `https://beta.idtdna.com/page/support-and-education/decoded-plus/how-to-design-primers-and-probes-for-pcr-and-qpcr/` | `references/biological-parameters-sources.md` P15/P16 |
| Primer3 默认参数（Tm/GC/长度/发夹/二聚体） | Primer3 官方手册 | `https://primer3.org/manual.html` | `references/biological-parameters-sources.md` P03-P08/P28 |
| SpCas9 on-target 评分 | Doench et al. 2016, Nat Biotechnol 34:184-191 | `https://doi.org/10.1038/nbt.3437` | `references/biological-parameters-sources.md` P22 |
| AsCas12a on-target 评分 | Kim et al. 2018, Nat Biotechnol 36:239-241 | `https://doi.org/10.1038/nbt.4061` | `references/biological-parameters-sources.md` P23 |
| Cas-OFFinder 全基因组脱靶搜索 | Bae et al. 2014, Bioinformatics 30:1473-1475；Cas-OFFinder GitHub | `https://github.com/snugel/cas-offinder` | `references/biological-parameters-sources.md` P24 |
| 限制酶位点分析 | Bio.Restriction；NEBcutter | `https://nc3.neb.com/NEBcutter/` | `references/biological-parameters-sources.md` P21；`scripts/sg_common.py` |
| BioPython/SeqIO/SnapGene 解析 | BioPython 官方文档（仓库依赖声明） | 无额外 URL，以 `requirements.txt` 为准 | `SKILL.md:96`、`scripts/sg_common.py:14-16` |

本章覆盖的脚本中，直接依赖上述依据的是：`sg_common.py`（Bio.Restriction 酶切）、`validate_construct.py`（CDS 翻译与唯一酶切位点）、`simulate_gel.py`（凝胶迁移经验模型）、`snapgene_compatibility.py`/`validate_roundtrip.py`/`write_dna.py`（SnapGene 往返与 GenBank 语义）。Primer3、Doench 2016、Kim 2018、Cas-OFFinder 属于 v0.8.0-dev3 的 CRISPR/引物链，不在本章核心读写路径上，但仓库已在 `references/biological-parameters-sources.md` 中登记，供后续章节引用。

分子克隆实验操作层面的依据（Sambrook & Russell）在本章主要支撑三件事：限制性内切酶消化产物的凝胶电泳分析、线性化/环化操作中磷酸二酯键连接的实验背景，以及“大于 20 kb 构建体建议电转化”这类实验室共识阈值。本章所有脚本都不替代湿实验手册；当输出与官方协议冲突时，以官方协议为准，脚本输出标记为计算预测。

## 18. BioPython/SeqIO/sgffp/snapgene_reader 读写路径与容错总结

| 组件 | 读取路径 | 写出路径 | 容错行为 |
|---|---|---|---|
| BioPython `SeqIO` | `sg_common._read_one`：`SeqIO.read` 读 genbank/fasta/embl/snapgene | `write_dna.py`：`SeqIO.write` 写 genbank/fasta；`convert.py` 写 genbank/fasta/embl | 文本先 `utf-8-sig`，`UnicodeDecodeError` 回退 `latin-1` |
| BioPython SnapGene 解析 | `.dna` 首选 `SeqIO.read(handle, "snapgene")` | 无（BioPython 不写 `.dna`） | 任何异常回退 `snapgene_reader` |
| `snapgene_reader` | `snapgene_file_to_seqrecord(path)` 作为 `.dna` 回退 | 无 | 回退失败才报 `ValueError` |
| `sgffp` | 无（仓库不通过它读） | `write_dna.write_native_dna`：`SgffObject.new` + `SgffFeature`/`SgffSegment` + `SgffWriter.to_file` | 写出后由 `validate_roundtrip` 回读核对 |
| `validate_roundtrip` 警告捕获 | `py_warnings.catch_warnings(record=True)` 捕获 BioPython 解析警告 | `_write` 写临时文件 | SnapGene 官方导出可能产生非标准 LOCUS 警告，收集进 `warnings` |
| 裸序列/行内 FASTA | `load_seq` 文本分支 | 不适用 | 行内 FASTA 必须恰好 1 条记录；裸序列过 `normalize_dna` |

关键原则：**读入永远通过 `sg_common.load_seq`，写出通过 `write_dna`/`convert`/`edit_plasmid` 等薄封装**。这样 `.dna` 的双解析器回退、编码回退、未知格式探测只维护一份。

## 19. 边界条件与错误处理一览

| 场景 | 处理 | 位置 |
|---|---|---|
| 空输入 | `ValueError("Empty source")` | `sg_common.py:134-138` |
| 路径不存在 | `FileNotFoundError` | `sg_common.py:140-141` |
| `.dna` 两个解析器都失败 | `ValueError("Cannot parse SnapGene file ...")` | `sg_common.py:157-160` |
| 非 IUPAC 序列 | `ValueError` 列出非法字符 | `sg_common.py:103-108` |
| 插入边界越界 | `ValueError("insert boundary out of range")` | `construct_model.py:134-135` |
| 删除区间非法 | `ValueError("invalid delete interval")` | `construct_model.py:154-155` |
| 点突变位置越界 | `ValueError` | `construct_model.py:184-185` |
| 旋转原点越界 | `ValueError` | `construct_model.py:193-194` |
| `linearize`/`rotate` 输入非环状 | `ValueError` | `edit_plasmid.py:75-76`、`edit_plasmid.py:87-88` |
| 批量转换单文件失败 | 目录模式记录 `status=error` 继续 | `convert.py:71-72` |
| 批量操作单文件失败 | 记录 `status=error` 继续 | `batch.py:88-89` |
| QC 存在 error | 退出码 1 | `validate_construct.py:149` |
| 往返核心语义失败 | `passed=false`，`main` 退出 1 | `validate_roundtrip.py:344-345` |
| SnapGene 官方转换失败/超时 | `RuntimeError` 或 `TimeoutExpired` 转 `SystemExit` | `validate_roundtrip.py:191-197`、`validate_roundtrip.py:328-329` |
| `.dna` 有 core 风险且 `--require-dna` | `ValueError` | `export_delivery_bundle.py:54-57` |

## 19A. 常见错误与处理建议

| 现象 | 原因 | 处理 |
|---|---|---|
| `parse_dna.py missing.gb` 报 `sequence file not found` | `looks_like_path` 判定为路径但文件不存在 | 检查路径；不要把文件名当裸序列 |
| `.dna` 解析报 `Cannot parse SnapGene file` | BioPython 与 `snapgene_reader` 都失败 | 文件可能损坏或版本过新；尝试 SnapGene 官方导出 GenBank 再解析 |
| `write_dna.py` 输出 GenBank 带 warning | 原生 `.dna` 保留 qualifier 有限 | 改用 `snapgene-gb`；交付前跑 `validate_roundtrip.py --strict` |
| `edit_plasmid.py` 报 `insert position out of range` | 1-based 位置超出 `1..len+1` | 插入允许 `len+1`（追加末尾）；删除/替换区间必须完全落在序列内 |
| `linearize requires a circular input record` | 输入拓扑不是 `circular` | FASTA/裸序列默认线性；先 `--op circularize` 或确认来源文件拓扑 |
| `validate_construct.py` 退出码 1 | 存在 `error` 级检查（坐标越界、CDS 读框、提前终止） | 看 JSON `checks` 中 `status=error` 项；修复 feature 或序列 |
| `validate_roundtrip.py --strict` 失败 | qualifier 差异被升级为失败 | 查看 `qualifier_differences`；可交付 `core-compatible` 但必须告知用户差异 |
| `export_delivery_bundle.py --require-dna` 失败 | 预检存在 core 风险且未 `--allow-core-risk` | 人工审查 `compatibility-report.json`，再决定是否显式接受风险 |
| 转换后 feature 丢失 | FASTA 本身不含 feature | 这是格式语义限制，不是 bug；权威格式用 GenBank |
| 环状序列酶切片段数异常 | 拓扑被默认成 `linear` | 只有显式 `circular` 才按环状处理；用 `--topology circular` 或修改注释 |

这些处理建议对应本章 §19 的边界条件，实际报错文本以各脚本 `ValueError`/`jfail` 输出为准。

## 20. 本章覆盖脚本清单

| 脚本 | 本章节 | SKILL.md 行号 | 核心函数 |
|---|---|---|---|
| `scripts/sg_common.py` | §4 | `SKILL.md:96-99` 依赖与 JSON 约定 | `load_seq`、`restriction_hits`、`jprint`、`jfail` |
| `scripts/construct_model.py` | §5 | `SKILL.md:160-165` 坐标约定 | `ConstructModel`、`feature_to_dict` |
| `scripts/parse_dna.py` | §6 | `SKILL.md:122` | `parse_primers`、`main` |
| `scripts/write_dna.py` | §7 | `SKILL.md:154` | `write_native_dna`、`_snapgene_annotated`、`main` |
| `scripts/edit_plasmid.py` | §8 | `SKILL.md:147` | `op_insert`、`op_delete`、`op_replace`、`op_mutate`、`op_linearize`、`op_circularize`、`op_rotate` |
| `scripts/convert.py` | §9 | `SKILL.md:152` | `convert_file`、`main` |
| `scripts/batch.py` | §10 | `SKILL.md:153` | `list_files`、`op_parse`、`op_validate`、`op_sites`、`op_convert`、`main` |
| `scripts/validate_construct.py` | §11 | `SKILL.md:149` | `validate`、`_cds_translation`、`main` |
| `scripts/validate_roundtrip.py` | §12 | `SKILL.md:158` | `compare_records`、`validate`、`_official_convert` |
| `scripts/snapgene_compatibility.py` | §13 | `SKILL.md:155` | `analyze_record`、`analyze`、`main` |
| `scripts/export_delivery_bundle.py` | §14 | `SKILL.md:156` | `build_bundle`、`_sha256`、`main` |
| `scripts/draw_map.py` | §15 | `SKILL.md:151` | `draw_circular`、`draw_linear`、`main` |
| `scripts/simulate_gel.py` | §16 | `SKILL.md:150` | `migration`、`band_row`、`main` |

## 21. 关键测试清单

| 测试文件 | 测试类/测试名 | 覆盖点 |
|---|---|---|
| `tests/test_v03.py` | `ConstructModelTests.test_insert_preserves_compound_parts_and_metadata` | 插入迁移复合 feature，保留 metadata |
| `tests/test_v03.py` | `ConstructModelTests.test_delete_migrates_each_compound_part` | 删除逐段迁移 |
| `tests/test_v03.py` | `ConstructModelTests.test_rotate_splits_crossing_feature_without_sequence_loss` | 旋转拆分跨切割点 feature |
| `tests/test_v03.py` | `ConstructModelTests.test_linearize_accepts_compound_feature` | 线性化接受复合 feature |
| `tests/test_v03.py` | `RestrictionModelTests.test_ecori_double_strand_boundaries` | EcoRI 双链切口边界 |
| `tests/test_v03.py` | `RestrictionModelTests.test_type_iis_forward_and_reverse_boundaries` | BsaI 正/反向切口几何 |
| `tests/test_v03.py` | `ContractAndRoundTripTests.test_json_envelope_strict_v05_shape` | v0.5 JSON 信封 |
| `tests/test_v03.py` | `ContractAndRoundTripTests.test_internal_snapgene_genbank_roundtrip` | 内部 GenBank 往返 |
| `tests/test_v04.py` | `test_roundtrip_reports_and_can_require_qualifier_equality` | 往返警告与 `--strict` 失败 |
| `tests/test_v05.py` | `FeatureMigrationOrderTests`（正/负链部分跨原点、`join`/`order` 保持、跨原点 CDS） | feature 迁移 order/operator |
| `tests/test_rich_fixtures.py` | `RichFixtureRoundTripTests.test_snapgene_gb_strict_roundtrip_preserves_everything` | 8 个 rich fixture 严格 GenBank 往返 |
| `tests/test_rich_fixtures.py` | `RichFixtureRoundTripTests.test_native_dna_roundtrip_matches_declared_compatibility` | 原生 `.dna` 与预检一致性 |
| `tests/test_rich_fixtures.py` | `RichFixtureRoundTripTests.test_known_risky_fixtures_are_not_called_lossless` | join/order/unicode 不得称 lossless |
| `tests/test_rich_fixtures.py` | `RichFixtureRoundTripTests.test_cross_origin_cds_extract_matches_source` | 跨原点 CDS 提取 |
| `tests/test_rich_fixtures.py` | `RichFixtureRoundTripTests.test_unicode_and_multivalue_qualifiers_survive_export` | Unicode 与多值 qualifier |
| `tests/test_snapgene_compatibility.py` | `SnapGeneCompatibilityTests`（11 个测试） | 预检、交付包、operator 参与核心比较 |
| `scripts/smoke_core.py` | P0/P1 smoke 检查 | `write_dna`、`.dna` 回读、缺失路径、酶切识别起点 |
| `scripts/smoke_academic.py` | Gateway/TA/TOPO smoke | `fixtures/golden` 学术夹具工作流 |
| `scripts/validate_rich_fixtures.py` | rich fixture 门禁 | 内部 strict + 官方 SnapGene 差异按预检分类接受 |
| `tests/test_smoke.py` | `SmokeCoreTests.test_smoke_core_passes` | smoke 全通过 |
| `tests/test_smoke_academic.py` | `SmokeAcademicTests.test_smoke_academic_passes` | 学术 smoke 全通过 |
| `tests/test_readme_commands.py` | `ReadmeCommandTests` | README/SKILL 代表性命令可运行 |
| `tests/test_v06.py` | `SchemaContractTests.test_schemas_validate_real_outputs` | schema 验证真实输出 |

## 22. 交付前最小检查链

结合本章脚本，一个构建体在交付前应执行的最小链为：

```bash
python scripts/parse_dna.py construct.gb --json
python scripts/validate_construct.py construct.gb --json
python scripts/snapgene_compatibility.py construct.gb --json
python scripts/export_delivery_bundle.py construct.gb --out-dir delivery --json
python scripts/validate_roundtrip.py construct.gb --format snapgene-gb --strict --json
python scripts/validate_roundtrip.py construct.gb --format dna --strict --json
```

其中 `validate_roundtrip.py --strict` 失败时，可以交付 `core-compatible` 版本，但必须把 qualifier 差异明确告诉用户（`SKILL.md` 注意事项）。官方 SnapGene 核验仅在提供 `--snapgene-exe`、设置 `SNAPGENE_EXE` 或可自动发现时执行；未发现时报告 skipped，不伪装成通过。

---

*本章结束。后续章节应接续覆盖 `design_primers.py`、`simulate_pcr.py`、`simulate_cloning.py`、`golden_gate.py`、`mutagenesis.py` 等设计链脚本，以及 v0.8.0-dev3 的 CRISPR 设计链与 v0.9.0-dev 的组装规划链。*

# 第 2 章：引物设计、Primer3 外部引擎、Tm/QC 与 PCR 策略

本章覆盖 9 个脚本/模块，按职责分为四层：

| 层 | 脚本 | 职责 |
|---|---|---|
| 外部引擎层 | `scripts/primer3_core_backend.py` | 以 Boulder-IO 子进程方式调用官方 `primer3_core`，解析并映射引物候选 |
| 外部引擎层 | `scripts/primer3_probe.py` | 探测旧 `primer3-py` 绑定是否可用，崩溃隔离诊断 |
| 设计层 | `scripts/design_primers.py` | 面向用户的 CLI：引物设计、尾巴/酶切位点/Gibson overlap、四层重试、候选输出 |
| 设计层 | `scripts/primer_design_engine.py` | v0.9 M3 引物引擎：`design_region_primers` 可编程 API、consent 接线、交叉验证、`best_pair` |
| QC 层 | `scripts/primer_qc.py` | 纯 Python 发夹/自二聚体/引物二聚体启发式评分 |
| QC 层 | `scripts/validation_crosscheck.py` | Tm/GC/酶切位点独立交叉验证（Wallace、Biopython `Tm_NN`、Bio.Restriction、直接 motif 扫描） |
| 集成验证层 | `scripts/validate_primer3_integration.py` | 真实 `primer3_core` 发布门禁，失败关闭 |
| PCR 层 | `scripts/pcr_strategy.py` | 按模板长度/GC/用途推荐聚合酶、添加剂、退火与延伸策略 |
| PCR 层 | `scripts/simulate_pcr.py` | 引物定位与 PCR 产物预测（线性/环状、错配容忍） |

本章所有路径均相对仓库根 `D:/codex_project/snapgene-dna-design-v0.9.0-work`。坐标说明：CLI 输入输出沿用 1-based 闭区间；`primer3_core_backend.py` 与 `primer_design_engine.py` 内部使用 0-based 半开区间和 0-based `bind_start/bind_end`；`design_primers.py` 在输出前把候选坐标映射回 1-based 闭区间（`scripts/design_primers.py:636-646`）。本章的“模板”指待扩增区域序列，`n` 指待扩增区域长度。

**阅读顺序建议**：先读 `primer3_core_backend.py`（引擎与坐标语义），再读 `primer_design_engine.py`（四层重试与 consent 接线），然后读 `design_primers.py`（CLI 把前两者装配成产品形态）；QC 层从 `primer_qc.py`（启发式结构评分）到 `validation_crosscheck.py`（独立交叉验证）；`validate_primer3_integration.py` 是发布门禁；`pcr_strategy.py` 与 `simulate_pcr.py` 是设计下游的 PCR 策略与产物模拟。

**数据流主线**：输入模板文件或裸序列 → `sg_common.load_seq` 归一化为 `SeqRecord` → 截取 1-based 目标区域并转为内部 0-based 区域 → Primer3 外部引擎或启发式引擎生成候选 → 候选级 QC（Tm 交叉验证、结构指标、3' 稳定性）→ 成对排序与 `boundary_offset` 报告 → JSON/文本输出。所有异常放宽与降级都由 `operation_consent.ConsentBroker` 在“执行前”确认，并将决策写入 `operation_log`；无确认即 `ConsentRequiredError`，任何设计都不得执行。

**输出契约要点**：每个候选包含 `binding`（3' 结合区）、`tail`（5' 尾巴，可为空）、`sequence`（完整引物 = tail + binding）、`tm`/`gc`（只按 binding 计算）、`hairpin`/`self_dimer`/`heterodimer`（完整引物结构评分）、`end_stability_3p`、`product_size`、`penalties`、`recommended`。Primer3 路径额外有 `primer3_penalty` 与 `_backend_source`；启发式路径额外有 `_backend_source = "heuristic scanner; NOT Primer3"`。对候选的结构指标，Primer3 路径以 `HAIRPIN_TH`、`SELF_ANY_TH`、`SELF_END_TH`、`COMPL_ANY_TH`、`COMPL_END_TH`、`END_STABILITY` 为权威值；启发式路径只使用 `primer_qc` 的无单位评分，二者不得混用。

**与相邻章节的关系**：第 1 章讲述序列/feature/坐标与文件读写；本章依赖其中的 `sg_common.load_seq`、`normalize_dna`、`topology` 与坐标约定。第 3 章组装克隆会调用本章的 `primer_design_engine.design_region_primers` 为每个片段设计引物，并把 `best_pair` 结果写入 assembly plan；因此本章的 `boundary_offset` 语义、`validation` 状态与 consent 记录会被下游规则引擎消费。阅读本章时不需要先读 CRISPR 章，但 `validation_crosscheck` 的“双路径验证”思想与 `azimuth_backend.py`/`deepcpf1_model.py` 的模型交叉验证一脉相承。

## primer3_core_backend.py：Boulder-IO 外部引擎

### 技术原理

`scripts/primer3_core_backend.py` 是真实 Primer3 的进程隔离后端。模块不导入 `primer3-py` 原生扩展；它发现并执行 `primer3_core` 命令行程序，以 Boulder-IO 文本协议交换数据。这样做的生物信息学理由不是计算速度，而是崩溃隔离：`primer3-py` 原生扩展在部分 Windows CPython 3.10–3.12 环境会触发访问冲突（0xC0000005），子进程崩溃只影响单次设计调用，不会拖垮整个质粒设计工具（`reports/primer3-environment.md`）。

关键数据结构是一个 `dict`：Boulder-IO 输入为标签键值对，如 `SEQUENCE_TEMPLATE`、`PRIMER_MIN_TM`；输出为 `PRIMER_LEFT_0_TM`、`PRIMER_RIGHT_0_SEQUENCE` 等扁平键。Boulder-IO 的键是扁平的、无嵌套的字符串表，这一特性决定了本模块的解析器可以非常保守：逐行切分、遇 `=` 停止、其余交给上层校验。下面是一条精确边界模式的输入示例（省略长度相关标签）：

```text
SEQUENCE_ID=snapgene-dna-design
SEQUENCE_TEMPLATE=ACGT...（n bp，已大写）
SEQUENCE_FORCE_LEFT_START=0
SEQUENCE_FORCE_RIGHT_START=<n-1>
PRIMER_TASK=generic
PRIMER_PICK_LEFT_PRIMER=1
PRIMER_PICK_RIGHT_PRIMER=1
PRIMER_NUM_RETURN=5
PRIMER_MIN_SIZE=18
PRIMER_OPT_SIZE=20
PRIMER_MAX_SIZE=27
PRIMER_MIN_TM=55.0
PRIMER_OPT_TM=60.0
PRIMER_MAX_TM=65.0
PRIMER_PRODUCT_SIZE_RANGE=<n>-<n>
PRIMER_EXPLAIN_FLAG=1
=
```

输出示例（节选）：

```text
PRIMER_PAIR_NUM_RETURNED=5
PRIMER_LEFT_0=0,24
PRIMER_LEFT_0_SEQUENCE=GCTAAAGACAATTACATAACATACACG
PRIMER_LEFT_0_TM=57.367
PRIMER_LEFT_0_GC_PERCENT=33.333
PRIMER_LEFT_0_SELF_ANY_TH=0.00
PRIMER_LEFT_0_SELF_END_TH=0.00
PRIMER_LEFT_0_HAIRPIN_TH=0.00
PRIMER_LEFT_0_END_STABILITY=4.4900
PRIMER_RIGHT_0=299,20
PRIMER_RIGHT_0_SEQUENCE=AGTCAATAGAGCGAACGCAT
PRIMER_PAIR_0_PRODUCT_SIZE=300
PRIMER_PAIR_0_PENALTY=12.219227
PRIMER_LEFT_EXPLAIN=considered 10, low tm 8, ok 2
=
```

函数职责如下：

| 函数/类 | 行号 | 职责 |
|---|---|---|
| `Primer3CoreError` | 20 | 引擎错误统一异常 |
| `discover_primer3_core(explicit=None)` | 28 | 确定性查找 `primer3_core` 可执行文件 |
| `probe_primer3_core(explicit=None, timeout=10)` | 73 | 运行 `--about` 并解析版本 |
| `encode_boulder(tags)` | 115 | 严格编码一条 Boulder-IO 记录 |
| `parse_boulder(text)` | 130 | 解析第一条 Boulder-IO 记录 |
| `run_boulder(core_path, tags, timeout=30)` | 144 | 单次执行 `primer3_core --strict_tags` |
| `_candidate(tags, prefix, index, tail, region_start, product_size, side, slide, slide_budget)` | 200 | 把一个 Primer3 输出候选映射为内部候选字典 |
| `design_anchored_pairs(core_path, sequence, region_start, target_tm, min_len, max_len, top_n, fwd_tail="", rev_tail="", timeout=30, tm_range=None, slide=False, slide_budget=None, product_pad=100)` | 257 | 精确边界或 slide 松弛的成对引物设计 |

`discover_primer3_core` 的搜索顺序固定：显式参数 `explicit`、环境变量 `PRIMER3_CORE`、`PATH`（`primer3_core.exe` / `primer3_core`）、`sys.path` 下 `primer3/src/libprimer3/`（primer3-py wheel 内的可执行文件）。它只做文件探测，不导入 wheel 的 Python 扩展（`scripts/primer3_core_backend.py:24-70`）。`probe_primer3_core` 执行 `primer3_core --about`，用正则 `(?:release\s+)?(\d+\.\d+(?:\.\d+)?)` 解析版本，返回 `status` 为 `available`、`unavailable` 或 `probe-error`（行 73-112）。

`encode_boulder` 实现严格 Boulder-IO 输出：标签必须匹配 `^[A-Z][A-Z0-9_]*$`，值不允许换行，每条记录以单个 `=` 行结束（行 115-127）。`parse_boulder` 只解析第一条记录，遇 `=` 行停止，容忍空行和无 `=` 的行（行 130-141）。`run_boulder` 向子进程写 payload，执行 `[core_path, "--strict_tags"]`，超时抛 `Primer3CoreError`；当返回码非零或输出中出现 `PRIMER_ERROR` 时抛错并携带 Primer3 的原始错误信息（行 144-171）。

`_candidate` 的解析和坐标映射是本章坐标语义的核心。对每个候选键 `PRIMER_LEFT_<i>` / `PRIMER_RIGHT_<i>`：

1. `_location` 解析 `"start,length"` 为 `(int, int)`；非法值抛 `Primer3CoreError`（行 192-197）。
2. 校验输出序列 `key + "_SEQUENCE"` 以请求的 5' overhang `tail` 开头；若不满足抛错（行 205-207）。
3. 从完整序列中切掉尾巴得到 `binding`；校验 `len(binding) == binding_length`（行 208-212）。
4. 正链引物：`bind_start = region_start + location_start`，`bind_end = bind_start + binding_length - 1`；`boundary_offset = location_start if slide else 0`（行 214-219）。这里的 `location_start` 是 Primer3 报告的候选起始相对传入区域起点的偏移，因此在 slide 模式下它天然等于 5' 端向内滑动的碱基数。
5. 负链引物：Primer3 的 `location_start` 是右引物在传入序列上的 5' 端位置（0-based），所以 `bind_end = region_start + location_start`，`bind_start = bind_end - binding_length + 1`；slide 模式下 `boundary_offset = product_size - 1 - location_start`（行 220-223）。该公式表示右引物 5' 端从扩增子最后一个碱基向内移动的距离。
6. 热力学指标映射：`_TM`→`tm`、`_GC_PERCENT`→`gc`、`_SELF_ANY_TH`/`_SELF_END_TH`→`self_dimer`、`_HAIRPIN_TH`→`hairpin`、`_END_STABILITY`→`end_stability_3p`，来源均标注 `primer3-core`（行 225-254）。

`design_anchored_pairs` 有两种模式：

**精确边界模式（`slide=False`）**：设置 `SEQUENCE_FORCE_LEFT_START=0`、`SEQUENCE_FORCE_RIGHT_START=product_size - 1`、`PRIMER_PRODUCT_SIZE_RANGE=<n>-<n>`；若传入了尾巴，设置 `SEQUENCE_OVERHANG_LEFT/RIGHT`（行 310-333）。这是 v0.6/v0.7 语义：左引物必须从区域第 1 个碱基开始，右引物必须覆盖最后一个碱基。

**slide-retry 模式（`slide=True`）**：不设 `FORCE_*_START`，`PRIMER_NUM_RETURN` 取 `max(top_n, 50)`，产物窗口放宽为 `max(min_len*2, n-100) .. n+100`，Tm 窗口按调用方传入值（通常 50–72 °C），`PRIMER_EXPLAIN_FLAG=1`、`PRIMER_SECONDARY_STRUCTURE_ALIGNMENT=1`；不传 `SEQUENCE_OVERHANG_*`，因为 slide 模式只对结合区评分，尾巴由引擎层后接（行 282-309）。请求 50 个候选是为了让排在 top-N 之外但仍满足滑动预算的候选有机会被后置过滤器选中。slide 后置过滤器在行 382-408：只保留 `0 <= boundary_offset_5p <= budget` 且 `0 <= boundary_offset_3p <= budget` 的对，然后重新编号 rank，并把候选 `recommended` 改为 `high`（首对）或 `medium`。GC 约束保持在 Primer3 默认 20–80%，不放宽；放宽 GC 是用户 consent 层的决定，不由本层执行（行 273-275 注释）。

**坐标算例**：设传入 `sequence` 是模板上第 101–400 个碱基（1-based 闭区间），长度 `n=300`，`region_start=100`（0-based，对应模板第 101 碱基）。Primer3 返回 `PRIMER_LEFT_0=0,24`，表示左引物从区域起点 0 开始、结合区长 24 nt。`_candidate` 映射：`bind_start = 100 + 0 = 100`，`bind_end = 100 + 24 - 1 = 123`（0-based，对应模板第 101–124 碱基），精确模式 `boundary_offset = 0`。若 slide 模式返回 `PRIMER_LEFT_0=2,22`，则 `bind_start=102`、`bind_end=123`，`boundary_offset=2`，表示左引物 5' 端从扩增子边界向内滑动 2 nt。右引物同理：精确模式 `PRIMER_RIGHT_0=299,20` 表示 `bind_end = 100 + 299 = 399`（0-based，对应模板第 400 碱基，即扩增子最后一个碱基）、`bind_start = 399 - 20 + 1 = 380`（0-based，对应模板第 381 碱基）。slide 模式右引物 `location_start` 变小即 5' 端向内滑动，`boundary_offset = product_size - 1 - location_start` 把该滑动量换算为相对 3' 边界的偏移。

**边界条件与防御**：`run_boulder` 对超时、OSError、非零返回码、`PRIMER_ERROR`、空输出五类失败都有不同错误信息；`_float`/`_int` 对缺失或非数值标签返回默认值而不抛错（行 174-189），但 `_location` 对非法 `"start,length"` 抛 `Primer3CoreError`，因为坐标是下游一切计算的基础，不能被默认值掩盖。`_candidate` 对尾巴不匹配和 `len(binding) != binding_length` 同样抛错，防止“输出序列与坐标不一致”的候选进入结果。

**失败信息保留**：`run_boulder` 在返回码非零时优先取 `PRIMER_ERROR`，否则取 stderr/stdout 最后 500 字符（行 161-166）；`probe_primer3_core` 在 `--about` 失败时同样截取最后 300 字符（行 109-110）。这保证上层拿到的 `Primer3CoreError` 或 probe `detail` 不是泛化的“引擎失败”，而是 Primer3 自己的解释文本。`design_anchored_pairs` 返回字典里保留 `raw_error`（行 421）与 `explain` 三个计数，因此即使上层继续执行，原始证据仍然可审计。

### 生物原理：Boulder-IO 与 SEQUENCE_OVERHANG 语义

Boulder-IO 是 Primer3 的经典机器可读输入/输出格式，官方手册见 `https://primer3.org/manual.html`（仓库 `references/biological-parameters-sources.md` P03、P04、P28 均指向该手册）。`primer3_core` 支持 `--strict_tags` 严格标签模式，本模块固定开启。

`SEQUENCE_OVERHANG_LEFT/RIGHT` 是 Primer3 的 5' overhang 语义：overhang 追加在引物 5' 端，不出现在模板中，但出现在输出序列 `PRIMER_*_SEQUENCE` 里。本仓库审计结论（`reports/biological-correctness-and-sourcing-audit.md` §3）为：Primer3 对结合区计算退火 Tm 与 GC，对完整 tailed oligo 计算二级结构（hairpin/self-dimer）；`PRIMER_PAIR_*_PRODUCT_SIZE` 包含 overhang 长度。实测 `primer3_core 2.6.1` 中，对同一模板加 `SEQUENCE_OVERHANG_LEFT=GGGGGGGGGG` 后，`PRIMER_LEFT_0_TM` 与 `PRIMER_LEFT_0_GC_PERCENT` 保持不变，`PRIMER_PAIR_0_PRODUCT_SIZE` 增加尾巴长度。设计层依赖这一语义：tails 只影响全长寡核苷酸结构风险，不改变退火参数选择。若 tails 参与评分导致 Primer3 无解，设计层会以 binding-only 重试（见 `primer_design_engine.py` 一节）。

### 实现路径

`design_primers.py` 或 `primer_design_engine.py` 的调用链：

```text
main/design_region_primers
  -> probe_primer3_core          # 探测可用性
  -> design_anchored_pairs       # 组装 Boulder 标签
       -> run_boulder            # 子进程执行 primer3_core --strict_tags
            -> encode_boulder    # 输入 dict -> "KEY=value\n...\n=\n"
            -> parse_boulder     # 输出文本 -> dict
       -> _candidate             # 逐候选映射坐标与热力学指标
       -> slide 后过滤           # 仅 slide 模式，执行 boundary_offset 约束
  -> 返回 forward_candidates / reverse_candidates / pairs / explain
```

输出契约：`forward_candidates`、`reverse_candidates` 为候选列表；`pairs` 为成对结果，每对含 `rank`、`product_size`、`primer3_product_size_with_overhangs`、`boundary_offset_5p/3p`、`primer3_penalty`、`recommended` 等字段（行 410-424）。`explain` 保留 Primer3 的 `PRIMER_LEFT_EXPLAIN`、`PRIMER_RIGHT_EXPLAIN`、`PRIMER_PAIR_EXPLAIN` 原始计数，供失败分析使用。

### 科学性说明与测试

- 适用边界：`design_anchored_pairs` 要求 `sequence` 非空且 `region_start` 合法；空序列抛 `Primer3CoreError("cannot design primers for an empty region")`（行 277-279）。它不检查序列是否为纯 IUPAC DNA，因为调用方已完成 `normalize_dna`。
- 已知限制：`PRIMER_PRODUCT_SIZE_RANGE` 在 slide 模式下被放宽到 `n±100`，但覆盖扩增子的保证由 `boundary_offset <= budget` 后置过滤实现，不依赖 `SEQUENCE_INCLUDED_REGION`（该标签的语义是“在子区域内选引物”，不能保证产物覆盖，见审计报告 §2.1）。
- 对应测试：`tests/test_primer3_core_backend.py::BoulderContractTests`（`test_encode_and_parse`、`test_rejects_newline_in_value`、`test_rejects_invalid_tag`、`test_invalid_explicit_path_does_not_fall_through`、`test_probe_timeout_start_error_and_bad_output`、`test_run_boulder_failure_contracts`、`test_mapping_rejects_invalid_engine_output`、`test_empty_sequence_fails`）；`RealPrimer3IntegrationTests`（`test_real_core_selects_ranked_pairs`、`test_real_core_separates_gibson_tail_and_binding`、`test_cli_require_primer3_reports_real_engine`）必须真实引擎不 skip。

## primer3_probe.py：旧 binding 诊断与崩溃隔离

### 技术原理

`scripts/primer3_probe.py` 是早期 `primer3-py` Python binding 的诊断工具。它不参与 v0.8/v0.9 的生产设计路径，因为生产路径直接使用 `primer3_core` 可执行文件；该脚本保留用于判断 `primer3-py` 是否安装、能否导入、`calc_tm` 是否可用。

`_PROBE_CODE`（行 26-40）是一段独立的 Python 探针代码，在子进程中执行：

```python
import primer3
primer3.calc_tm('ACGTACGTACGTACGT')
print('P3_OK')
```

`probe_primer3(python=None, timeout=30)` 用当前解释器（或指定 `python`）运行 `python -c _PROBE_CODE`，根据返回码和 stdout 区分状态（行 45-82）：

| 状态 | 判定 | 含义 |
|---|---|---|
| `available` | 返回码 0 且 stdout 含 `P3_OK` | binding 可用 |
| `not-installed` | stdout 含 `P3_IMPORT_ERROR` | 未安装 |
| `probe-error` | 含 `P3_CALC_ERROR`、超时或启动失败 | 计算/启动失败 |
| `import-crash` | 其他（含 Windows 0xC0000005 类负返回码） | 原生扩展崩溃 |

结果缓存在 `_CACHE`（行 42），进程生命周期内只探测一次。`primer3_status()` 与 `is_available()` 是便捷封装（行 85-91）。运行 `python scripts/primer3_probe.py` 输出 `primer3_status` 与可选 `primer3_detail`；该脚本不使用 `--json`，因为它固定输出诊断格式（`SKILL.md` 已注明）。该脚本体积很小，但它是“来源诚实”原则在依赖探测上的第一个落点。

### 生物原理

本脚本不产生生物学结论。其存在依据是工程事实：`primer3-py` 的 C 扩展在部分环境 import 即崩溃（`reports/primer3-environment.md`），因此“能不能用 Primer3”本身是一个必须在子进程中回答的实验问题，不能由主进程直接 import 来回答。这符合本仓库“诚实标注来源”的原则：`unavailable` 意味着输出中不得出现任何 Primer3 验证声明。

### 实现路径

```text
primer3_probe.py __main__
  -> probe_primer3()
       -> subprocess.run([interpreter, "-c", _PROBE_CODE], ...)
       -> 解析 stdout/returncode -> (status, detail)
  -> 打印 primer3_status / primer3_detail
```

### 科学性说明与测试

- 已知限制：`probe_primer3` 只证明 `import primer3` 与 `calc_tm` 可用，不证明 `primer3_core` 存在。生产路径不依赖本脚本。
- 对应测试：`tests/test_v07_primer3.py::Primer3StatusTests`（`test_probe_reports_not_installed`、`test_probe_reports_import_crash`、`test_probe_reports_available`、`test_cli_reports_unavailable_and_warns`、`test_fallback_engine_cannot_claim_primer3`）。

## design_primers.py：CLI 引物设计与候选排名

### 技术原理

`scripts/design_primers.py` 是面向用户的 CLI。它把 `primer3_core_backend.py` 的真实引擎和本文件内的启发式扫描统一在同一输出契约下。

**静态数据表**：`PROTECTIVE_BASES`（行 54-62）与 `SITE_SEQS`（行 65-76）维护常用限制酶的保护碱基与识别序列。这是“最小常用 5' flank”表，NEB 的 “Cleavage Close to the End of DNA Fragments” 指南要求 PCR 引物再增加 ≥4 个碱基；代码注释明确该表不是完整的 NEB 表，使用前应查现表（行 50-53）。`with_sites` 的拼接规则是 `extra = PROTECTIVE_BASES[site] + SITE_SEQS[site]`（行 450-460），因此 `--fwd-site EcoRI` 生成 5' 尾 `G + GAATTC`，`--fwd-site BamHI` 生成 `GG + GGATCC`。`--add-site` 是两侧同加同一种酶的快捷方式，内部实现为把该酶同时追加到 `fwd_sites` 与 `rev_sites`（行 447-448）。

**CLI 示例**：

```text
# 真实引擎正式设计（失败关闭）
python scripts/design_primers.py template.gb --start 100 --end 900 \
  --require-primer3 --primer3-core "C:\tools\primer3_core.exe" \
  --json --consent auto

# Gibson 引物：正向 overlap 按原序列接 5'，反向 overlap 自动取反向互补
python scripts/design_primers.py donor.gb --gibson \
  --fwd-overlap ACGTACGTACGT --rev-overlap TGCATGCATGCA \
  --json --consent auto
```

**输出 JSON 的关键字段**：`design_engine.selected` 为 `primer3-core` 或 `heuristic`；`design_engine.verification` 为 `real-external-engine` 或 `unverified-heuristic`；`primer3_note` 明确写出“Primer3 Core <version> selected and ranked the primer pairs in an isolated process”或“Primer3 Core was not used; ... No Primer3 design or verification is claimed”；`warnings` 在启发式路径首条为“Primer3 design was NOT used”。这些字段把“来源是否真实引擎”变成机器可判读的字段，而不是靠人工阅读文本。

**`ThermoEngine`（行 113-147）**：启发式回退引擎。`tm` 用 Biopython `MeltingTemp.Tm_NN` 默认参数（`scripts/design_primers.py:124-125`）；`hairpin`/`self_dimer`/`heterodimer` 调用 `primer_qc` 的评分函数；`end_stability_3p` 取结合区最后 5 bp 的 GC 数作为 3' GC anchor 启发式。其 `available` 属性恒为 `False`，从结构上保证启发式结果不会被标成 Primer3。

**`scan_side(sequence, target_tm, min_len, max_len, engine, side, tail="", product_size=None)`（行 229-283）**：锚定扫描。对正向侧，窗口从区域起点开始，遍历 `length in [min_len, max_len]`，取 `sequence[:length]` 为 binding，`full = tail + binding`。Tm/GC 只按 binding 计算；hairpin/self-dimer 按 full 计算。惩罚项由 `_binding_penalties`（行 154-173）与 `_structure_penalties`（行 176-191）给出，`_recommendation`（行 206-226）把惩罚映射为 `high/medium/low`。候选按简单权重排序。

**`build_pairs(fwd_candidates, rev_candidates, engine, product_size, top_n)`（行 286-315）**：全组合配对，`engine.heterodimer` 计算交叉二聚体，`_heterodimer_penalties`（行 194-203）计罚，按合并权重排序并截取前 `top_n`。

**`main()`（行 322-805）** 的关键流程：

1. 解析参数（行 323-368）。重要默认：`--target-tm 60.0`、`--min-len 18`、`--max-len 30`、`--top-n 5`、`--engine auto`、`--primer3-timeout 30`。`--consent` 默认在 TTY 下为 `ask`，非 TTY 下为 `auto`（行 360-362）。
2. 校验：`top_n >= 1`、`min_len >= 1`、`max_len >= min_len`、`primer3_timeout >= 1`（行 370-377）。
3. 构造 `ConsentBroker`（行 391-398）：`auto` 策略显式自动确认；`--yes` 用恒真回调；否则用交互回调 `_interactive_confirm`。`_consent` 包装 `broker.request`，未确认时 `jfail("CONSENT_REQUIRED", ...)`（行 401-409）。
4. 探测 `primer3_core`（行 411-424）：`--engine heuristic` 时强制 `status="disabled"`；`--engine primer3-core` 不可用时升级为 `require_primer3`；`require_primer3` 不可用时 `jfail("PRIMER3_REQUIRED", ...)`。
5. 载入模板并截取区域：`load_seq(args.source)` → `seq = str(record.seq)`；`args.start` 为 1-based，`end` 默认序列全长；检查 `1 <= start <= end <= len(seq)`（行 430-434）。`region = seq[args.start - 1: end]`（行 462）。
6. 构造 tails：Gibson 模式要求 `--fwd-overlap` 与 `--rev-overlap` 都给出，反向引物尾巴是 `rev_overlap` 的反向互补（行 436-445）；酶切位点模式 `with_sites` 为每个酶附加 `PROTECTIVE_BASES[site] + SITE_SEQS[site]`（行 450-460）。`product_size = end - args.start + 1`（行 465）。
7. 参数 consent（行 477-485）与后端策略（行 495-623）。四层重试在行 496-509 构造：有尾巴时 `tailed -> binding-only-retry -> relaxed-tm-retry -> slide-retry`；无尾巴时 `tailed(无尾巴) -> relaxed-tm-retry -> slide-retry`。slide-retry 前必须 consent（行 513-522）。
8. Primer3 成功后：binding-only 或 slide 模式下把尾巴重新接回候选 `sequence`（行 550-558），写 `primer3_retry_note`（行 559-572）。
9. 若 Primer3 全部失败且 `require_primer3`，结构化失败 `PRIMER3_NO_CANDIDATES`；否则 consent 后降级启发式（行 587-611）。若 Primer3 一开始不可用且未 require，consent 后降级（行 612-622）。
10. 启发式回退：`scan_side` 扫描 `region` 与 `rev_region`，`build_pairs` 配对（行 624-632）。
11. 坐标映射：把 0-based `bind_start/bind_end` 与 `boundary_offset` 映射回 1-based 模板坐标。正向 `bind_start = args.start + offset`；反向 5' 端 1-based = `args.start + len(region) - 1 - offset`，`bind_start = five_prime_1based - binding_len + 1`（行 636-646）。
12. 兼容字段与质量字段：`overlap`/`overlap_tail`/`overlap_length`（行 648-655）；`quality` 由 `analyze_primers` + `flag_risks` 生成，并标注 `source: legacy-heuristic`（行 767-775）。
13. 输出：`--json` 走 `jprint`，人类可读文本打印候选表（行 777-801）。

**坐标映射细节**：`scan_side` 与 `design_anchored_pairs` 返回的 `bind_start/bind_end` 是 0-based；CLI 输出前统一转成 1-based 模板坐标（行 636-646）。正向候选 `bind_start = args.start + offset`；反向候选的 5' 端 1-based = `args.start + len(region) - 1 - offset`。以 `--start 100 --end 399`（1-based，区域长 300）为例，精确边界左引物结合区 1-based 为 100..117（长度 18），右引物 5' 端 1-based = 399，结合区 1-based 为 382..399（长度 18）。若 slide-retry 返回 `boundary_offset=2`，左引物结合区变为 102..119，右引物结合区变为 380..397（5' 端 397，长度 18），两引物 5' 端均向内滑动 2 nt；按结合区外沿计算，扩增产物会比原目标区间缩短 4 bp。`product_size` 字段仍报告请求区域长度（本例 300），而 `primer3_product_size_with_overhangs` 是 Primer3 报告的含尾巴/引物全长贡献的产物长度；`actual_product_size` 与前者一致（`primer3_core_backend.py:362-370`）。

**惩罚与推荐逻辑**：启发式路径的推荐等级不是随机标签。`_recommendation` 把“Tm 偏离”“GC 越界”“缺 3' GC clamp”“弱 3' GC anchor”各计 1.0 分，其他计 0.5 分；`structural_strong` 直接降为 `low`；`weight <= 1.0` 为 `high`、`<= 3.0` 为 `medium`、其余 `low`（行 206-226）。配对层 `build_pairs` 把 `strong` 类或 `dG=` 类罚项计 5 分、`moderate` 计 2 分、普通计 1 分；`strong` 配对直接 `low`，`weight <= 2` 为 `high`、`<= 5` 为 `medium`（行 302-313）。这些权重是项目内部的可解释启发式，用于排序和提示，不作为湿实验成功概率预测。

**无候选与候选不足**：当 `fwd_candidates` 或 `rev_candidates` 为空，CLI 不输出空列表伪装成功，而是 `jfail("NO_PRIMER_CANDIDATES", ...)`，details 含 `primer3_status`、`design_engine`、`warnings`、空 `pairs` 与失败原因（行 689-712）。当候选数少于 `top_n`，结果正常输出但 `warnings` 写入“only N forward candidate(s) found (requested M)”（行 680-687）。这两条路径使“部分成功”与“彻底失败”都能被程序区分。

### 生物原理

- **Tm 计算**：Primer3 路径使用 `primer3_core` 内置 SantaLucia 最近邻模型与 Primer3 盐参数（Na+ 50 mM、Mg2+ 1.5 mM、dNTP 0.6 mM）；启发式路径使用 Biopython `MeltingTemp.Tm_NN`（`references/biological-parameters-sources.md` P02、P03）。两种路径都在输出中标注来源。
- **GC 窗口**：设计窗口使用 Primer3 默认 20–80%；独立 QC 窗口更严，为 30–70%（`primer_design_engine._validate_primer`，见下节）。这与 IDT 对 PCR 引物的推荐一致。
- **3' GC clamp**：`_binding_penalties` 检查 `binding[-1] in "GC"`（行 163-164），依据 Primer3 官方建议（P07）。
- **酶切位点尾巴与保护碱基**：限制酶在 DNA 片段末端切割需要侧翼碱基，NEB 官方 FAQ “Cleavage Close to the End of DNA Fragments” 提供常见酶的 5' 保护碱基表；本文件实现的是最小常用 flank，并提示 PCR 引物再加 ≥4 碱基（P20）。
- **Gibson 引物**：5' overlap 尾巴提供相邻片段同源臂。依据 Gibson 2009 Nat Methods（DOI `10.1038/nmeth.1318`）；overlap 长度 15–40 bp、GC 30–70% 的规则见 `references/biological-parameters-sources.md` P15/P16 与 `planning/planner.py`。

### 实现路径

```text
design_primers.py main
  -> argparse
  -> load_seq(source)                     # sg_common.py:126
  -> normalize_dna(overlap)               # Gibson 尾巴校验
  -> probe_primer3_core                   # primer3_core_backend.py:73
  -> ConsentBroker.request(primer-design-parameters)
  -> [Primer3 路径]
       design_anchored_pairs              # 四层重试
       或
       ThermoEngine + scan_side + build_pairs
  -> 坐标映射到 1-based
  -> analyze_primers(best_fwd, best_rev)  # primer_qc.py:115
  -> flag_risks                           # primer_qc.py:136
  -> jprint / 文本输出
```

### 科学性说明与测试

- 适用边界：`--engine heuristic` 明确要求用户显式选择探索性模式；`auto` 在 Primer3 不可用时会 consent 后降级，且候选结构分数来源均为 `heuristic`，`warnings` 明确写入“Primer3 design was NOT used”（行 658-667）。
- 已知限制：本脚本不检查基因组特异性；`warnings` 中说明推荐标签只是 Primer3 排名，不预测湿实验成功（行 669-672）。`quality` 字段是向后兼容的 legacy-heuristic 摘要，Primer3 路径应使用候选级 Primer3 指标（行 769-774）。
- 对应测试：`tests/test_v07_primer3.py`（`Primer3StatusTests`、`CandidateOutputTests`、`PenaltyTests`、`GibsonSeparationTests`、`FailureAlarmTests`）；`tests/test_primer3_core_backend.py::RealPrimer3IntegrationTests::test_cli_require_primer3_reports_real_engine`；`tests/test_release_iteration.py::CliConsentGateTests`（`test_design_primers_ask_without_input_does_not_execute`、`test_design_primers_auto_consent_executes`）。

## primer_design_engine.py：M3 引擎与 consent 接线

### 技术原理

`scripts/primer_design_engine.py` 是可编程 API 形态的 M3 引物引擎，`planning/planner.py` 在片段级设计时调用它（`planning/planner.py:368`）。核心函数：

```python
def design_region_primers(sequence, region_start=0, fwd_tail="", rev_tail="",
                          target_tm=60.0, min_len=18, max_len=27, top_n=3,
                          primer3_core=None, timeout=30, require_primer3=False,
                          consent=None, consent_policy="ask",
                          confirm_callback=None, operation_log=None,
                          allow_slide=True)
```

（行 158-163）

**consent 接线**：`_resolve_consent_broker`（行 107-118）接受 `None`（按 `consent_policy` 新建）、`ConsentBroker` 实例或 dict。`design_region_primers` 在探测 Primer3 之前先写 `operation_log` 并 `broker.request(primer-design-parameters)`（行 200-210）；只有确认参数窗口后才执行探测。slide-retry、Primer3 不可用降级、Primer3 全部失败降级三类异常操作都必须在执行前 consent（行 224-233、253-264、358-365）。未确认即抛 `ConsentRequiredError`，调用方不得执行任何设计。`operation_log` 是 `TransparencyLog`，所有探测、尝试、错误、降级均追加（`scripts/operation_consent.py`）。

**四层重试/slide-retry**：`attempts` 列表在行 237-249 构造。顺序固定：

1. `tailed`：有尾巴时把 `fwd_tail/rev_tail` 以 `SEQUENCE_OVERHANG_*` 传给 Primer3，Tm 窗口 `target±5`；
2. `binding-only-retry`（仅当有尾巴）：空尾巴传给 Primer3，成功后重新接尾巴并记录 `retry_note`；
3. `relaxed-tm-retry`：空尾巴、Tm 窗口 50–72 °C；
4. `slide-retry`（`allow_slide=True` 时）：释放强制起点，滑动预算 `min(25, n//4)`，产物窗口 `n-100..n+100`，Tm 50–72 °C，GC 仍 20–80%。

每一层调用 `design_anchored_pairs(probe["path"], region, region_start, target_tm, min_len, max_len, top_n, fwd_tail=..., rev_tail=..., timeout=..., tm_range=..., slide=...)`（行 275-279）。成功即 break，并给所有候选标 `_backend="primer3-core"`、`_backend_source="Primer3 Core <version>"`（行 329-332）。

**四层重试的参数差异**（与 `design_primers.py` 同一策略）：

| 层 | 尾巴传给 Primer3 | Tm 窗口 | slide | 产物窗口 | 说明 |
|---|---|---|---|---|---|
| `tailed` | 是（`SEQUENCE_OVERHANG_*`） | target±5 | 否 | n–n | 尾巴参与完整引物结构评分 |
| `binding-only-retry` | 否（成功后重接） | target±5 | 否 | n–n | 只有 binding 参与排名 |
| `relaxed-tm-retry` | 否 | 50–72 | 否 | n–n | 只放宽 Tm，不放宽 GC/结构 |
| `slide-retry` | 否（成功后重接） | 50–72 | 是 | n−100..n+100 | 释放 `FORCE_*_START`，后过滤 boundary_offset |

`primer3_retry_note` 逐层说明原因（行 303-328）。`reports/primer3-failure-analysis.md` 用真实 `primer3_core 2.6.1` 的 explain 计数记录了失败机理：tailed 层曾出现 `right explain: considered 10, high tm 6, high hairpin stability 4, ok 0`；binding-only 层同模板得到 `ok 2`。这说明“尾巴参与结构评分导致无解”不是推测，而是可复现的实测结论。

**consent 时序**：`design_region_primers` 先写 `primer-design-start` 日志并请求 `primer-design-parameters`；确认后才 `probe_primer3_core` 并进入设计。`slide-retry` 请求只在第 4 层执行前发出，携带 `slide_budget`、`product_size_range`、`tm_range`、`gc_range` 与风险说明（行 253-264）。`test_default_ask_blocks_before_any_design` 验证了 probe 不会在 consent 前运行；`test_slide_relaxation_denied_means_no_slide_execution` 验证了拒绝 slide 后 `design_anchored_pairs` 的 `slide` 参数从未为真。三类降级（Primer3 不可用、全部重试无解、显式 heuristic）都各自走一次 `broker.request`，不存在“静默降级”。

`_validate_primer(primer, side, tail="", target_tm=60.0)`（行 50-98）是独立 QC 门：Tm 必须在 52–72 °C、与目标偏差 ≤5 °C、GC 30–70%、3' 端为 G/C、Primer3 hairpin/self-any/hetero-any 阈值 ≥47 °C 即报 `primer_strong_secondary_structure`；随后调用 `primer_tm_crosscheck` 做双路径 Tm 校验。注意 `validation_windows` 显式声明该 QC 窗口严于 consented 的 Primer3 设计窗口（GC 20–80、Tm 50–72），见行 92-97。这意味着一个候选可以“Primer3 设计通过但独立 QC 不过”，此时候选不会被删除，而是带着 `validation.problems` 出现在结果中，由调用方决定是否采用；这正是“设计”与“验收”分离的工程语义。

`_explain_alternatives(explain)`（行 121-155）把 Primer3 的 `PRIMER_*_EXPLAIN` 文本映射为可执行建议：高发夹/高 Tm/高 GC/高互补分别给出 `EXTEND_FLANK_OUTSIDE_AMPLICON`、`ADJUST_TM_WINDOW_OR_PRIMER_LENGTH`、`GC_WINDOW_NEEDS_USER_CONSENT`、`REDESIGN_OR_EXTEND_REGION`，并始终附 `USE_INTERNAL_PRIMER_PAIR`。这些 alternatives 在失败关闭时随异常返回。

`restriction_tail(enzyme_names)`（行 38-47）复用 `design_primers.SITE_SEQS` 与 `PROTECTIVE_BASES`，未知酶抛 `ValueError("UNKNOWN_RESTRICTION_ENZYME: ...")`。`RESTRICTION_TAIL_SOURCE`（行 31-35）固定指向 NEB 官方 FAQ。

`best_pair(primer_result)`（行 440-446）取 `pairs[0]` 并按 `forward_index/reverse_index` 回查候选，返回 `{"forward": ..., "reverse": ..., "pair": ...}`。

### 生物原理

本模块的生物学决策遵循“先确认窗口、再执行；异常放宽必须可见”：

- 参数窗口确认的生物学依据是 Primer3 官方默认：Tm 57/60/63 °C 附近、GC 20–80%、长度 18–27 bp（P03-P06）。设计窗口与 QC 窗口分离：设计允许 Primer3 默认 20–80% GC，但 QC 用更严格的 30–70% 标记风险，不静默修改候选。
- slide-retry 的依据是发布迭代需求（`references/release-iteration-requirements.md` §3，P09）：端部极端 GC 或结构使精确边界无解时，允许引物 5' 端向内滑动 `min(25, n//4)` nt，产物窗口 `n±100` bp。这符合分子克隆实践：扩增子端部不适合做引物结合位点时，应向内移动引物或外扩侧翼（Sambrook & Russell, Molecular Cloning）。
- 失败 alternatives 的“外扩 20–40 bp / 内部引物对”是湿实验可执行方案：在目标区间外扩增 20–40 bp 侧翼可避开端部低复杂度序列；内部引物对会缩短产物但可保留目标区间主体。

### 实现路径

```text
design_region_primers(sequence, region_start, ...)
  -> 输入校验 / operation_log 记录
  -> broker.request(primer-design-parameters)
  -> probe_primer3_core
  -> [可用] 四层 attempts:
       tailed -> binding-only-retry -> relaxed-tm-retry -> slide-retry
       (slide-retry 前 broker.request(slide-retry))
       每层 design_anchored_pairs
       成功 -> 标 _backend -> 跳出
       失败 -> 记录 -> 继续
  -> [全部失败] _explain_alternatives -> 需要时抛 Primer3CoreError，
       否则 consent 降级后走启发式
  -> [不可用] consent 降级后 ThermoEngine + scan_side + build_pairs
  -> 逐候选 primer_tm_crosscheck
  -> 组装 schema_version 0.9.0 结果
  -> best_pair(primer_result) 供调用方取首对
```

**返回结构**（`design_region_primers` 行 400-437）：`schema_version`、`backend`、`backend_status`、`primer3_version`、`primer3_failure`、`primer3_retry_note`、`alternatives`、`boundary_offsets`、`region`（`start/end/length`）、`fwd_tail`、`rev_tail`、`tail_sources`、`forward_candidates`、`reverse_candidates`、`pairs`、`validation`（正反向逐候选 QC 与 `tm_crosscheck`）、`provenance`、`consent`（`broker_policy`、`requests`、`pending`）、`operation_log`、`input_sequence.sha256_prefix`。`best_pair` 是便捷解包，供 `planning/planner.py` 直接把首对写入片段级引物列表。

**适用边界**：`design_region_primers` 对输入做两类防御：坐标非法抛 `ValueError`（行 179-186）；Primer3 执行失败在 `require_primer3=True` 时抛 `Primer3CoreError`（行 344-345），错误对象可携带 `alternatives`（行 354-357）。`ConsentBroker` 的 `policy` 只接受 `ask` 或 `auto`；`ask` 无回调/无 TTY 即抛 `ConsentRequiredError`（`operation_consent.py:99-106`）。`_validate_primer` 的 `primer_tm_crosscheck` 在 Primer3 路径用 `mg=1.5`、启发式路径用 `mg=0.0`，确保两条 Tm 主路径使用各自盐模型，交叉验证才公平。

### 科学性说明与测试

- 适用边界：`region_start` 必须满足 `0 <= region_start < len(sequence)`，区域长度至少 `min_len * 2`（行 179-186）。`require_primer3=True` 时任何不可用或执行失败都抛 `Primer3CoreError`，不降级。
- 实验性标注：启发式回退候选的 `_backend_source` 为 `"heuristic scanner; NOT Primer3"`（行 89-90、378-379），`provenance.status` 为 `partial`（行 424-428）。
- 已知限制：slide-retry 成功时 `boundary_offsets` 只报告首对（行 325-328、408）；binding-only 与 slide 模式下尾巴不参与 Primer3 排名，完整引物结构风险由 `validation` 与 `tm_crosscheck` 报告，这是设计语义而非隐藏风险。
- 对应测试：`tests/test_release_iteration.py::PrimerEngineConsentGateTests`（`test_default_ask_blocks_before_any_design`、`test_slide_relaxation_denied_means_no_slide_execution`、`test_slide_relaxation_approved_executes_and_is_visible`）、`TransparencyGateTests`（`test_result_carries_backend_parameters_sha_and_retry_path`、`test_degradation_is_recorded_not_silent`）、`SlideRetryRealEngineTests`（`test_group_a_tail_case_binding_only`、`test_group_b_high_gc_terminal_slide_retry`、`test_group_c_poly_g_gives_actionable_alternatives`）；`tests/test_v09.py::M3PrimerEngineTests`、`Primer3TailRetryTests`、`Primer3FailureModeTests`、`test_primer_engine_error_branches`；`tests/test_destructive_inputs.py::PrimerEngineDestructiveTests`。

## primer_qc.py：纯 Python 引物结构 QC

### 技术原理

`scripts/primer_qc.py` 用标准库实现 Primer3 风格的三种结构检查，无 Bio 依赖。阈值常量为 `MIN_STEM = 3`、`ANCHOR = 4`（行 16-19）。

**`score_hairpin(seq)`（行 31-55）**：枚举序列内两个位置 `i < j`，从 `j` 向前、`i` 向后逐碱基互补延伸，得到茎长 `stem`；要求 `stem >= 3` 且 `loop >= 1`。评分 `score = stem*10 + (5 if stem>=4 else 0) + min(loop,5)`，返回 `(score, stem, loop, stem_start, stem_end)`。该评分只近似热力学发夹稳定性，不等同于 Primer3 的 `HAIRPIN_TH`。

**`score_self_dimer(seq)`（行 58-83）**：将序列与其自身反向互补 `rc = complement(seq[::-1])` 做局部比对。`rc[j+length] == seq[i+length]` 的连续匹配段长度即二聚体配对长度。若配对区触及 3' 端最后 4 bp（`i+length >= n-ANCHOR` 或 `j+length >= n-ANCHOR`），加 8 分锚定惩罚。评分 `length*10 + (8 if anchor else 0)`。该实现已修复旧版“rc 未使用导致自互补寡核苷酸 0 分”的问题（`reports/biological-correctness-and-sourcing-audit.md` §2.1）。

**`score_pair_dimer(fwd, rev)`（行 86-112）**：将反向引物读为 3'→5'（`r = complement(rev[::-1])`），与正向引物做局部比对；同样对 3' 锚定加罚。这模拟引物二聚体形成方向：两引物 3' 端互补延伸是 PCR 中二聚体扩增的来源。

**`analyze_primers(fwd, rev)`（行 115-133）** 汇总正/反向 hairpin、self-dimer 与 pair-dimer；**`flag_risks(report)`（行 136-150）** 以阈值 40 分标记 `strong hairpin`、`self-dimer`、`pair dimer` 风险。

**算法复杂度与边界**：三个评分函数都是 O(n²·m) 量级的朴素局部比对，其中 n 为引物长度（≤30），m 为匹配段长度（通常很短），因此对设计任务足够快。`score_hairpin` 要求 `stem >= 3` 且 `loop >= 1`，避免把相邻的零散互补当作发夹；`score_self_dimer` 与 `score_pair_dimer` 要求连续匹配 `length >= 3` 才计分。`ANCHOR=4` 表示配对段触及最后 4 bp 即视为 3' 锚定，加 8 分；这一加权使得“5' 端轻微互补”和“3' 端危险互补”在分数上可区分。得分阈值 40 由 `design_primers.py` 的 `HAIRPIN_STRONG/DIMER_STRONG` 复用（`scripts/design_primers.py:79-80`），`flag_risks` 同样以 40 为界。示例：`score_self_dimer("AATT")` 会得到非零分，因为 `AATT` 的反向互补仍为 `AATT`，`rc` 序列与自身完全匹配；而随机序列通常为 0 分（`tests/test_bio_audit_regressions.py::test_self_dimer_detects_reverse_complement`）。

### 生物原理

引物二级结构与二聚体的生物学依据：

- 发夹（hairpin）：引物分子内 3' 端回折形成茎环会竞争模板退火，严重时降低有效引物浓度并导致无产物或短产物；Primer3 默认 `PRIMER_MAX_HAIRPIN_TH=47.0`（P08）。
- 自二聚体（self-dimer）：引物自身反向互补配对，3' 端配对可被聚合酶延伸形成引物二聚体；Primer3 默认 `PRIMER_MAX_SELF_ANY_TH=47.0`。
- 引物二聚体（pair dimer/cross-dimer）：正反向引物 3' 端互补，PCR 中扩增出短二聚体条带，消耗引物与 dNTP。这些检查属于设计阶段的计算机预筛，不能替代实验（Sambrook & Russell, Molecular Cloning；IDT primer design guide）。

`primer_qc.py` 的分数是启发式互补评分，`SKILL.md` 明确“只做启发式互补评分，不等同于 Primer3 的热力学 hairpin/dimer 计算”。

### 实现路径

```text
design_primers.main
  -> analyze_primers(best_fwd["sequence"], best_rev["sequence"])
       -> score_hairpin / score_self_dimer / score_pair_dimer
  -> flag_risks(qc)

ThermoEngine.hairpin/self_dimer/heterodimer
  -> score_hairpin / score_self_dimer / score_pair_dimer
```

### 科学性说明与测试

- 适用边界：仅用于启发式路径与兼容性 `quality` 摘要；Primer3 路径的权威结构指标来自 `PRIMER_*_SELF_ANY_TH`、`SELF_END_TH`、`HAIRPIN_TH`、`COMPL_ANY_TH`、`COMPL_END_TH`。
- 已知限制：分数不具热力学单位（不是 dG 或 °C），不能与 Primer3 阈值直接比较。
- 对应测试：`tests/test_bio_audit_regressions.py::AuditRegressionTests::test_self_dimer_detects_reverse_complement`；`tests/test_v07_primer3.py::PenaltyTests`（`test_hairpin_and_self_dimer_penalties`、`test_cross_dimer_penalty`、`test_recommendation_levels`）。

## validation_crosscheck.py：独立数值交叉验证

### 技术原理

`scripts/validation_crosscheck.py` 实现“单一库错误不得静默产出错误 Tm/GC/酶切位点”的工程原则。每个有生物学意义的数值至少由两条独立路径计算，冲突以结构化 `conflicts` 返回。

常量（行 25-27）：`PRIMER_TM_AGREE_C = 2.0`、`PRIMER_TM_WARN_C = 3.5`、`PRIMER_TM_RANGE = (52.0, 72.0)`。

**Wallace Tm**：`wallace_tm(seq)`（行 30-44）返回 `Tm = 2*(A+T) + 4*(G+C)`，来源标注 Wallace et al. 1979, Nucleic Acids Res 6:3543（P01）。注释明确该公式是短寡核苷酸（≤14 nt）近似，长序列仍报告但标 `approximation_validity: short-only`。

**Biopython Tm_NN**：`bio_tm_nn(seq, na=50.0, mg=1.5, dntp=0.6)`（行 47-64）调用 `mt.Tm_NN`，默认盐参数对齐 Primer3 默认（Na 50 mM、Mg 1.5 mM、dNTP 0.6 mM）。`mg=0` 可复现 overlap 窗口搜索使用的简单 Na-only 约定。异常时返回 `{"tm": None, "error": ...}` 而不是抛错。

**`primer_tm_crosscheck(binding, primary_tm, primary_label="primer3-core", na=50.0, mg=1.5)`**（行 90-146）：比较主 Tm（Primer3 或启发式 `Tm_NN`）与 Biopython `Tm_NN`、Wallace 三条路径。生成两类冲突：

- `tm_method_disagreement`：主 Tm 与 Biopython 差 >3.5 °C 时，`severity` 为 `warn`（≤5 °C）或 `error`（>5 °C）；
- `tm_outside_52_72`：主 Tm 或 Biopython Tm 越出项目内部 52–72 °C 窗口，`severity` 视两者是否同时越界而定。

返回 `status`：`conflict-error` / `conflict-warn` / `consistent`。

**`restriction_site_crosscheck(sequence, enzyme_name, circular=False)`**（行 149-205）：一条路径是 `sg_common.restriction_hits`（Bio.Restriction，返回 `recognition_start0` 与 `top_cut_boundary_0based`）；另一条路径是直接 motif 扫描：取酶识别位点与其反向互补，按 IUPAC 符号表（行 160-165）在序列上滑窗匹配；环状模板允许窗口跨原点回绕（行 172-180）。计数一致则 `consistent_count=True`。该实现修复了环状跨原点漏检（`reports/biological-correctness-and-sourcing-audit.md` §2.2）。

**`overlap_crosscheck(overlap)`**（行 208-231）：对设计出的 overlap 窗口，比较直接碱基计数 GC（`manual_gc_percent`，行 67-79）与 `Bio.SeqUtils.gc_fraction`（`biopython_gc_percent`，行 82-87），并报告 `Tm_NN(mg=0)` 与 Wallace Tm。

**状态机与调用方处置**：三个主函数都以 `status` 结尾。`primer_tm_crosscheck` 的 `status` 由 `conflicts` 中是否出现 `severity=="error"` 决定（行 141-145）；`overlap_crosscheck` 只在 GC 双路径差 >0.01% 时报 `conflict-error`；`restriction_site_crosscheck` 用计数一致而非位置一致作为 `consistent_count`，因为 Bio.Restriction 报告切点边界、直接扫描报告 motif 起点，二者位置维度不同但计数必须相同（行 195-204）。调用方 `_validate_primer` 把 `conflict-error` 映射为 `primer_tm_crosscheck_failed`、`conflict-warn` 映射为 `primer_tm_crosscheck_warn`（`scripts/primer_design_engine.py:80-83`），使交叉验证结果进入候选级 QC。

**IUPAC 直接扫描细节**：`restriction_site_crosscheck` 的 `iupac` 表（行 160-165）覆盖全部标准简并符号（R/Y/S/W/K/M/B/D/H/V/N）。`matches(window, pattern)` 要求窗口与模式等长，并且窗口每个碱基都属于模式符号允许的集合；例如模式 `RGATCY` 能匹配 `AGATCC` 也能匹配 `GGATCT`。直接扫描同时检查识别序列正链与反向互补（`matches(window, site) or matches(window, rc_site)`），这保证非回文酶（如 BsaI `GGTCTC`，其反向互补 `GAGACC`）的两种链向都被计数。环状模板的窗口在 `i` 越界时用 `probe[:len(site)-len(window)]` 补齐（行 176-178），因此跨 origin 的位点不会漏检；测试 `test_non_palindromic_site_both_orientations` 与 `test_circular_restriction_crosscheck_handles_wrap` 分别锁定这两个性质。

### 生物原理

- Tm 计算不能依赖单一实现：Primer3 与 Biopython 使用不同最近邻参数集（P02、P03）。Wallace 公式（P01）提供第三个独立量级估计。三条路径交叉可在不联网、不做实验的情况下发现“参数用错、标签错位、公式移植错误”等问题。
- 限制酶位点不能只依赖 Bio.Restriction：直接 motif 扫描同时搜索识别序列正反向互补，并与 Bio.Restriction 计数核对。这对应分子克隆中的基本事实——回文酶识别同一双链序列，非回文酶的正反向互补都是合法位点（Bio.Restriction 文档；NEBcutter）。
- 环状模板的位点可能跨 origin，直接扫描必须回绕，否则会漏掉跨越 `n-1|0` 边界的位点（`tests/test_bio_audit_regressions.py::test_circular_restriction_crosscheck_handles_wrap`）。

### 实现路径

```text
primer_design_engine._validate_primer
  -> primer_tm_crosscheck(binding, tm, backend, mg=1.5 或 0.0)
       -> bio_tm_nn + wallace_tm
       -> 生成 conflicts/status

planning/planner.py overlap 窗口
  -> overlap_crosscheck
       -> manual_gc_percent + biopython_gc_percent + bio_tm_nn + wallace_tm

限制酶交叉验证
  -> restriction_site_crosscheck
       -> sg_common.get_enzyme -> Bio.Restriction
       -> sg_common.restriction_hits
       -> 直接 IUPAC motif 扫描
```

### 科学性说明与测试

- 适用边界：`primer_tm_crosscheck` 的 `mg` 参数必须与主后端的盐模型一致：Primer3 路径 `mg=1.5`，启发式 `Tm_NN` 路径 `mg=0.0`（`primer_design_engine.py:395-398` 与 `_validate_primer` 行 77-79）。
- 已知限制：Wallace 公式对 >14 nt 寡核苷酸只是量级参考；`tm_method_disagreement` 的 3.5/5.0 °C 阈值是项目内部判据。
- 对应测试：`tests/test_validation_crosscheck.py`（`TmCrosscheckTests`、`GcCrosscheckTests`、`RestrictionCrosscheckTests`）；`tests/test_bio_audit_regressions.py::test_circular_restriction_crosscheck_handles_wrap`、`test_degenerate_restriction_site_matches_iupac`。

## validate_primer3_integration.py：真实引擎发布门禁

### 技术原理

`scripts/validate_primer3_integration.py` 是发布前失败关闭门禁：没有真实 `primer3_core` 或断言不通过，进程返回 1 且 `ok=false`。

`main()`（行 20-63）流程：

1. `probe_primer3_core(args.primer3_core)`；不可用则 `report = {"ok": False, "engine": info, ...}` 并返回 1。
2. 可用时对固定 `REAL_SEQUENCE`（行 11-17，300 bp 的确定序列）调用 `design_anchored_pairs(..., 1, 60.0, 18, 30, 5)`（plain）与 `design_anchored_pairs(..., fwd_tail="ACGTACGT", rev_tail="TGCATGCA")`（gibson）。
3. 断言（行 50-55）：plain 返回 5 对；gibson 返回 1 对；`gibson_binding_product_size == 300`；`gibson_full_product_size == 316`；首候选 hairpin `metric_source == "primer3-core"`。其中 316 = 300 + 8 + 8，对应两个 8 nt 尾巴，验证了 `SEQUENCE_OVERHANG_*` 的产物长度语义。
4. 可选 `--report` 把 JSON 报告写入文件（行 61-62）。

运行方式：

```text
python -X utf8 scripts/validate_primer3_integration.py \
  --primer3-core "<primer3_core 路径>" --report reports/primer3-integration.json
```

`--report` 写出的 JSON 结构为 `{"ok": bool, "engine": {...}, "checks": {...}, "error": ...}`；`ok=true` 是发布晋升的必要条件。若引擎缺失，`engine.status` 为 `unavailable` 且 `error` 写明原因，进程返回 1。

### 生物原理

门禁序列是 300 bp 自然序列，plain 5 对与 gibson 1 对是真实引擎确定性行为的回归断言。它不是引物质量好坏的生物学判断，而是“真实引擎路径没有被假模块替代”的可执行证据。门禁坚持 `real-external-engine` 的验证状态；任何 mock/skip 都不计为通过（`SKILL.md` v0.7.0-dev2）。

### 实现路径

```text
validate_primer3_integration.py main
  -> probe_primer3_core
  -> design_anchored_pairs(plain)
  -> design_anchored_pairs(gibson, tails)
  -> 断言 pair 数量 / product_size / metric_source
  -> 打印 JSON，返回 0/1
```

### 科学性说明与测试

- 已知限制：门禁只覆盖固定序列与固定 tail，不覆盖全部 Primer3 功能；它是发布流程的一部分，不是常规 QC。
- 对应测试：该脚本本身由发布流程调用，其契约由 `tests/test_primer3_core_backend.py::RealPrimer3IntegrationTests` 与 `tests/test_release_iteration.py::ParameterSourcesGateTests` 间接约束；`reports/primer3-integration-dev2.json` 等报告文件记录实际运行结果。

## pcr_strategy.py：M4 模板感知 PCR 策略

### 技术原理

`scripts/pcr_strategy.py` 是纯规则系统，不调用 Primer3。`SOURCES`（行 17-24）集中维护所有推荐来源 URL：NEB Q5 protocol、NEB GC-rich FAQ、Takara PrimeSTAR GXL 产品页、NEB 聚合酶选择表、NEB OneTaq 产品页、Thermo Phusion 产品页。每个推荐必须带来源 URL，不允许“无出处温度”。

`extension_time_seconds(length_bp, rate_seconds_per_kb=30.0)`（行 27-31）：`max(1, ceil(length/1000 * 30))`；长度 ≤0 返回 0。依据 NEB Q5 20–30 s/kb，取保守 30 s/kb（P11）。

`recommend_pcr_strategy(profile)`（行 34-94）决策树按 `length > 10000 → gc > 70 → gc < 30 → purpose ∈ {verification, colony-pcr, check} → 默认克隆` 的顺序命中即返回：

| 条件 | 推荐 | 依据 |
|---|---|---|
| `length > 10000` | PrimeSTAR GXL（或 Q5 长片段方案） | Takara PrimeSTAR GXL（P14） |
| `gc > 70.0` | Q5 + Q5 High GC Enhancer（或 3% DMSO） | NEB GC-rich FAQ（P12） |
| `gc < 30.0` | Q5 或 Phusion，降低退火温度 | NEB Q5/PCR optimization（P13） |
| `purpose in (verification, colony-pcr, check)` | OneTaq | NEB 聚合酶选择表（P30） |
| 其他克隆用途 | Q5 High-Fidelity | NEB Q5 protocol（P11） |

`annealing_strategy` 按酶种分流（行 79-84）：Q5 体系“退火温度约引物 Tm 低值 +3 °C，若计算值 ≥72 °C 可用两步法 72 °C”；Taq/OneTaq 体系“约引物 Tm 低值 −5 °C”；AT-rich 模板再降 2–3 °C 并复核制造商方案。Tm 来自 M3 Primer3 算法，不由本脚本发明。这是审计修正后的表述（`reports/biological-correctness-and-sourcing-audit.md` §2.1）。

`main()`（行 97-118）支持 `--profile` JSON 文件或 `--length/--gc/--purpose` 命令行参数。

**输出示例**（`recommend_pcr_strategy` 返回结构，行 71-94）：

```json
{
  "schema_version": "0.9.0",
  "profile": {"length": 12000, "gc_percent": 50.0, "purpose": "cloning"},
  "recommended_enzyme": "PrimeSTAR GXL DNA Polymerase（或 Q5 长片段方案）",
  "reason": "片段长度 12000 bp > 10 kb，建议长片段高保真聚合酶",
  "additives": ["按 Takara 方案使用 GXL buffer"],
  "extension_time_seconds": 360,
  "extension_formula": "length_bp/1000*30s (NEB Q5 20-30 s/kb, conservative 30 s/kb)",
  "annealing_strategy": "退火温度 ~ 引物 Tm 低值 - 5 C（Taq 类酶）；Tm 由 M3 Primer3 算法计算；AT-rich 模板再降 2-3 C",
  "protocol": {"name": "official manufacturer protocol", "url": "https://www.takarabio.com/products/pcr/all-enzymes-and-accessories/primestar-series/primestar-gxl-dna-polymerase"},
  "provenance": [{"type": "manufacturer-protocol", "source_name": "PCR strategy recommendation", "source_id": "pcr-strategy", "url": "...", "status": "verified", "verification": {"method": "structured-rule", "status": "verified"}, "retrieved_at": "2026-08-17"}]
}
```

`annealing_strategy` 的酶种分支很重要：Q5 与 Taq 的退火温度规则方向相反，代码通过 `"Q5" in enzyme` 分流，避免对所有酶套用同一条公式。该分支是审计修正项（`reports/biological-correctness-and-sourcing-audit.md` §2.1）。

**防御与来源**：`recommend_pcr_strategy` 对 `profile` 先 `dict(profile or {})` 拷贝，`length` 用 `int(... or 0)` 兜底，`gc` 在 `float()` 失败时置 `None`（行 35-41）。负长度或 `NaN` GC 不会导致崩溃：`extension_time_seconds` 对 `length_bp <= 0` 返回 0（行 29-30），决策树对 `gc is not None and gc > 70` 的写法天然跳过 `NaN`（`NaN > 70` 为 False）。每个结果带 `provenance`，`type` 为 `manufacturer-protocol`、`status` 为 `verified`、`verification.method` 为 `structured-rule`；`retrieved_at` 固定为仓库来源登记日期。这些字段与 `references/biological-parameters-sources.json` 的 `source_url`/`retrieved_at` 形成对应关系。

### 生物原理

- 高保真聚合酶选择：克隆用途默认 Q5（NEB）；>10 kb 长片段用 Takara PrimeSTAR GXL（Takara 官方产品页）。验证/菌落 PCR 用 OneTaq 即可（P30）。
- 高 GC 模板：GC >70% 时双链难解链，NEB 建议 Q5 High GC Enhancer 或 3% DMSO（P12）。
- AT-rich 模板：GC <30% 时退火温度降低，可考虑甜菜碱；仓库代码将甜菜碱标为“按实验室经验/NEB 建议复核”，未伪装成官方配方（行 58）。
- 退火策略：NEB Q5 与 Taq 的退火温度规则不同，代码按酶分流；该修正有测试锁定（`tests/test_v09.py::M4StrategyTests`）。

### 实现路径

```text
pcr_strategy.py main
  -> 读取 --profile 或 --length/--gc/--purpose
  -> recommend_pcr_strategy(profile)
       -> 决策树（length/gc/purpose）
       -> extension_time_seconds
       -> provenance + source URL
  -> jprint / 文本输出
```

### 科学性说明与测试

- 适用边界：这是策略建议，不是反应条件优化结果。输出只有延伸时间是数值化的，退火策略是温度方向性建议，最终必须以制造商当前 protocol 为准。
- 已知限制：`recommend_pcr_strategy` 对非数值 GC 或负长度做防御性处理（`gc=None` 走默认 Q5，`extension_time_seconds` 返回 0）；`purpose` 未匹配时默认克隆 Q5。
- 对应测试：`tests/test_v09.py::M4StrategyTests::test_high_gc_and_at_and_long`、`AdditionalV09CoverageTests::test_pcr_strategy_cli_and_branches`；`tests/test_destructive_inputs.py::PcrStrategyDestructiveTests::test_non_finite_and_negative_length`；`tests/test_e2e_scenarios.py::ScenarioD_HighGcPcr::test_high_gc_strategy_and_primers`。

## simulate_pcr.py：PCR 产物模拟

### 技术原理

`scripts/simulate_pcr.py` 输入模板（文件或裸序列）与正/反向引物，输出预测扩增子与结合位点。

`find_binding(template, primer, allow_mismatch=0, circular=False)`（行 15-44）：把模板与引物大写，计算引物反向互补 `rc`。环状模板构造 `searchable = t + t[:len(p)-1]`，起始位置遍历 `range(len(t))`，允许跨 origin；线性模板只在 `0 .. len(t)-len(p)` 内搜索。每个位置分别比较子串与 `p`（top 链命中，`strand=+1`）以及与 `rc`（bottom 链命中，`strand=-1`），错配数 ≤ `allow_mismatch` 即记录 `(pos, strand, mismatches)`。

`simulate(template, fwd, rev, allow_mismatch=0, circular=False)`（行 47-117）：

1. 取正向引物的 `+1` 命中（`fwd_top`）与反向引物的 `-1` 命中（`rev_bot`）；缺失时返回 `None` 与 notes。
2. 对每个 `(f_hit, r_hit)` 组合：
   - 环状：`distance = (rev_start - start) % n`；要求 `distance >= len(fwd)` 且 `product_len = distance + len(rev) <= n`；产物从 `(t+t)[start:start+product_len]` 截取，`wraps = start + product_len > n`（行 69-77）。
   - 线性：要求 `rev_start >= start + len(fwd)`；`product_len = rev_start + len(rev) - start`；`amplicon = t[start:start+product_len]`（行 79-83）。
3. 候选按 `(product_len, start, rev_start)` 排序，报告最短产物；多产物时记 note（行 91-97）。
4. 结合位点坐标：`forward_bind`/`reverse_bind` 以 1-based 输出，环状时用 `end_coord` 取模（行 99-116）。

`main()`（行 120-178）：`load_seq` → `normalize_dna` 校验引物 → 按 `topology(rec)` 选择环状/线性 → `simulate` → 可选 `--out` 写 FASTA → JSON 或文本输出。`--allow-mismatch` 必须 ≥0。

### 生物原理

PCR 模拟的分子生物学基础是引物方向性：正向引物与模板 top 链相同（结合 bottom 链，向右侧延伸），反向引物是 bottom 链序列的 5'→3'（其 3' 端朝左，与 top 链互补）。因此程序要求正向引物命中 top 链、反向引物命中 bottom 链，且两引物 3' 端相向；若两引物同向或背向，无产物（“primer sites exist but do not face inward in a valid order”）。这对应标准 PCR 几何：产物长度 = 反向引物 5' 端位置 + 反向引物长度 − 正向引物 5' 端位置（线性模板）；环状模板产物可能跨越复制起点并回绕（Sambrook & Russell, Molecular Cloning 的 PCR 扩增几何）。

`find_binding` 允许错配（默认 0）对应引物退火的简并性：低错配数结合位点可能导致非特异产物；本程序只报告最短产物，并在 notes 中说明多产物情况，不做熔解曲线或特异性判断。

**坐标算例**：设线性模板为 `ACGTACGTACGTACGTACGTACGTACGTACGT`（32 bp），正向引物 `ACGTACGTAC`，反向引物 `ACGTACGTAC`。`find_binding` 会为正向引物返回多个 top 链命中（`strand=+1`）、为反向引物返回多个 bottom 链命中（`strand=-1`，因为该重复引物的反向互补与自身序列等价）。`simulate` 对所有 `(f_hit, r_hit)` 组合应用 `rev_start >= start + len(fwd)` 校验后，按 `(product_len, start, rev_start)` 排序，报告最短合法产物，并在 notes 中写入“N valid products found; reporting the shortest”。`forward_bind.start = start+1`、`reverse_bind.end = end_coord(rev_start, len(rev))` 输出 1-based 闭区间；环状模板中同一对引物若跨 origin，`wraps_origin=true`，`end_coord` 用 `(start0 + width - 1) % n + 1` 回绕。

**环状与线性的差异**：环状模板 `find_binding` 在 `t + t[:len(p)-1]` 上搜索并允许 `pos` 取 `0..n-1`，保证跨 `n-1|0` 边界的位点不丢失；`simulate` 用 `(rev_start - start) % n` 计算方向距离，再排除产物长度超过模板周长或两引物重叠的非法组合。线性模板则简单地拒绝 `rev_start < start + len(fwd)`。环状产物长度以实际模板周长 `n` 为上限，这是“质粒扩增后产物不能超过质粒自身长度”的序列几何约束。

**错误与 note 语义**：`simulate` 返回 `(None, notes)` 的情况有两种——引物没有正确链向的结合位点（“forward primer has no top-strand binding site” / “reverse primer has no bottom-strand binding site”），或有位点但方向顺序不合法（“primer sites exist but do not face inward in a valid order”）。前者常见于引物序列写反，后者常见于两引物同向或背向。`main` 在 `result` 为 `None` 时输出 `amplicon: null`、`length: 0` 和 `notes`，不会写 FASTA。

**CLI 流程**：`main` 先 `load_seq` 读取模板（文件或裸序列），再对两条引物做 `normalize_dna`（去空白、大写、非 IUPAC 符号拒绝），随后检查 `--allow-mismatch >= 0`。`circular` 参数来自 `sg_common.topology(record)`，只有 GenBank/SnapGene 文件显式标注 `circular` 时才按环状处理，裸序列默认线性（`sg_common.py:198-207`）。`--out` 只在 `result` 非空时写 FASTA，id 固定为 `amplicon`，description 为 `PCR product N bp`。输出 JSON 始终包含 `template`、`template_length`、`forward_primer`、`reverse_primer`、`notes`，以及 `result` 中的 `amplicon`、`length`、`candidate_count`、`wraps_origin`、`forward_bind`、`reverse_bind`。

### 实现路径

```text
simulate_pcr.py main
  -> load_seq(template)
  -> normalize_dna(fwd/rev)
  -> topology(record) 决定 circular
  -> simulate(template, fwd, rev, allow_mismatch, circular)
       -> find_binding(template, fwd, ...)
       -> find_binding(template, rev, ...)
       -> 筛选 strand 方向
       -> 枚举产物候选并排序
  -> 可选 SeqIO.write FASTA
  -> jprint / 文本
```

### 科学性说明与测试

- 适用边界：这是序列级预测，不模拟聚合酶效率、退火竞争、错配延伸、引物二聚体竞争等湿实验因素。
- 已知限制：环状模板多产物时只报告最短产物；`allow_mismatch` 不区分错配位置，3' 端错配与 5' 端错配同等对待（真实 PCR 中 3' 端错配影响更大）。线性模板中 `rev_start < start + len(fwd)` 的组合被拒绝，即两引物重叠区不允许。
- 对应测试：`scripts/smoke_core.py` 与 `scripts/smoke_academic.py` 的 `simulate_pcr` 冒烟检查（产物生成、外向/上游引物对拒绝并给出 `valid order` note）。

## 引用来源与仓库内位置

本章引用的权威来源按仓库统一登记在 `references/biological-parameters-sources.md` 与 `.json`（表号 P01-P30）。本节列出本章直接使用或与本章边界相关的来源：

| 来源 | DOI/URL | 仓库内使用位置 |
|---|---|---|
| Sambrook & Russell, Molecular Cloning | CSHL Press（P27） | `rules/feasibility_rules.json` 的 20 kb 电转化 warn；本章引物/延伸实践背景 |
| Gibson et al. 2009, Nat Methods 6:343-345 | `https://doi.org/10.1038/nmeth.1318` | Gibson overlap 引物、`simulate_cloning.py`、`planning/planner.py`、`rules/feasibility_rules.json` |
| Engler et al. 2008, PLoS One 3:e3647 | `https://doi.org/10.1371/journal.pone.0003647` | Golden Gate 位点规则、`golden_gate.py`、`planning/planner.py` |
| NEB 官方协议（Q5、GC-rich、OneTaq、聚合酶选择、Cleavage Close to the End） | `https://www.neb.com/...` | `pcr_strategy.py::SOURCES`、`design_primers.py::PROTECTIVE_BASES`、`primer_design_engine.py::RESTRICTION_TAIL_SOURCE` |
| Takara PrimeSTAR GXL 产品页 | `https://www.takarabio.com/products/pcr/all-enzymes-and-accessories/primestar-series/primestar-gxl-dna-polymerase` | `pcr_strategy.py::SOURCES` |
| IDT primer design guidance | `https://beta.idtdna.com/...` | overlap 长度/GC 规则（P15/P16） |
| Primer3 官方手册 | `https://primer3.org/manual.html` | `primer3_core_backend.py`、`validation_crosscheck.py`、`primer_design_engine.py` |
| Wallace et al. 1979, Nucleic Acids Res 6:3543 | `https://doi.org/10.1093/nar/6.11.3543` | `validation_crosscheck.py::wallace_tm` |
| SantaLucia 1998, PNAS 95:1460-1465 | `https://doi.org/10.1073/pnas.95.4.1460` | Biopython `MeltingTemp.Tm_NN`（P02） |
| Doench et al. 2016, Nat Biotechnol 34:184-191 | `https://doi.org/10.1038/nbt.3437` | `scripts/azimuth_backend.py`（CRISPR 章，不在本章脚本） |
| Kim et al. 2018, Nat Biotechnol 36:239-241 | `https://doi.org/10.1038/nbt.4061` | `scripts/deepcpf1_model.py`（CRISPR 章，不在本章脚本） |
| Cas-OFFinder GitHub（Bae et al. 2014） | `https://github.com/snugel/cas-offinder` | `scripts/cas_offinder_adapter.py`（CRISPR 章，不在本章脚本） |
| BioPython / Bio.Restriction 文档 | Biopython 官方文档 | `sg_common.py`、`validation_crosscheck.py`、`simulate_pcr.py` |

Doench 2016、Kim 2018 与 Cas-OFFinder 属于 CRISPR 靶点预测与脱靶搜索模块，不参与引物 Tm/QC；本仓库为每个参数保存 `source_url` 与 `retrieved_at`（`tests/test_release_iteration.py::ParameterSourcesGateTests` 强制字段齐全），因此本章不再为这些来源编造与引物的关联。

**引用纪律**：本章 DOI 均来自仓库既有文件——`references/biological-parameters-sources.md`（P01-P30）与 `reports/biological-correctness-and-sourcing-audit.md`。审计报告声明对 DOI/URL 做过实时解析（doi.org / Crossref / HTTP 探测），并修复了 11 个坏 DOI、Takara/IDT 死链与 pDONR201 catalog 错误。任何文档写作都不得在仓库登记之外新造 DOI 或 URL；需要新来源时先修改 `references/biological-parameters-sources.json` 并补 `source_url` 与 `retrieved_at`，再引用。

## 常见失败模式与排查

| 错误码/异常 | 触发条件 | 排查路径 |
|---|---|---|
| `PRIMER3_REQUIRED` | `--engine primer3-core` 或 `--require-primer3` 时 `probe_primer3_core` 不可用 | 运行 `python scripts/primer3_probe.py` 与 `python scripts/check_env.py --json`；设置 `PRIMER3_CORE` 或 `--primer3-core` 指向真实可执行文件 |
| `PRIMER3_EXECUTION_FAILED` | `require_primer3=True` 且 `design_anchored_pairs` 抛 `Primer3CoreError` | 检查 `--primer3-timeout` 是否过短；直接运行 `primer3_core --about`；查看 `details.primer3_error` 中 Primer3 的原始输出 |
| `PRIMER3_NO_CANDIDATES` | Primer3 四层重试后仍 0 对，且 `require_primer3=True` | 查看 `details.primer3_explain` 与 `alternatives`；按建议外扩侧翼 20–40 bp、改用内部引物对，或人工检查端部序列 |
| `CONSENT_REQUIRED` | `--consent ask` 下参数确认/降级/放宽未获用户确认 | 交互确认、传 `--yes`，或程序化场景传 `--consent auto`（auto 是显式自动确认并记录） |
| `NO_PRIMER_CANDIDATES`（jfail） | 启发式路径正/反向候选任一为空 | 区域过短（<2×min_len）或端部序列不可用；扩大 `--start/--end` 范围或降低 `--min-len` |
| `UNKNOWN_RESTRICTION_ENZYME` | `--fwd-site/--rev-site/--add-site` 给未知酶名 | 检查拼写；可用 `scripts/find_sites.py` 或 Bio.Restriction 枚举酶名 |
| `invalid region` / `ValueError: invalid primer region` | CLI 区域越界，或 API `region_start` 越界/区域过短 | 检查 1-based 与 0-based 坐标差异；API 要求 `0 <= region_start < len(sequence)` 且区域长 ≥ 2×min_len |
| simulate_pcr 的 `valid order` note | 引物有位点但方向不对（同向/背向/重叠非法） | 检查反向引物是否应输入 bottom 链的 5'→3' 序列；用 `--allow-mismatch 0` 先确认完全匹配位点 |
| 环状 PCR 产物长度为 0 | 环状模板上合法产物超过周长，或被 `distance < len(fwd)` 拒绝 | 检查引物方向与环状坐标；环状产物长度上限为模板周长 |

## 本章覆盖脚本清单

| 脚本 | 本章小节 | 核心函数/类 |
|---|---|---|
| `scripts/primer3_core_backend.py` | Boulder-IO 外部引擎 | `design_anchored_pairs`、`run_boulder`、`_candidate` |
| `scripts/primer_design_engine.py` | M3 引擎与 consent 接线 | `design_region_primers`、`_validate_primer`、`best_pair` |
| `scripts/design_primers.py` | CLI 引物设计 | `main`、`scan_side`、`build_pairs`、`ThermoEngine` |
| `scripts/primer_qc.py` | 引物结构 QC | `score_hairpin`、`score_self_dimer`、`score_pair_dimer` |
| `scripts/primer3_probe.py` | 旧 binding 诊断 | `probe_primer3`、`primer3_status` |
| `scripts/validate_primer3_integration.py` | 真实引擎发布门禁 | `main`（plain/gibson 断言） |
| `scripts/validation_crosscheck.py` | 独立交叉验证 | `primer_tm_crosscheck`、`restriction_site_crosscheck`、`overlap_crosscheck` |
| `scripts/pcr_strategy.py` | PCR 策略 | `recommend_pcr_strategy`、`extension_time_seconds` |
| `scripts/simulate_pcr.py` | PCR 产物模拟 | `find_binding`、`simulate` |

## 关键测试清单

下列测试按“先契约后集成、先单元后场景”的顺序组织。契约测试不依赖真实 `primer3_core`，在任何环境都必须通过；真实引擎测试在缺少 `primer3_core` 时按仓库策略 skip，但发布晋升时必须在 `SNAPGENE_RUN_PRIMER3=1` 与真实 `PRIMER3_CORE` 下全数执行。读者若要验证本章结论，建议按表逐项运行，并优先关注带 `Real` 或 `RealEngine` 字样的集成测试与 `ConsentGate` 系列测试，因为它们覆盖了最容易被 mock 掩盖的失败模式。

| 测试文件 | 关键测试名 |
|---|---|
| `tests/test_primer3_core_backend.py` | `BoulderContractTests::test_encode_and_parse`、`test_rejects_newline_in_value`、`test_rejects_invalid_tag`、`test_invalid_explicit_path_does_not_fall_through`、`test_probe_timeout_start_error_and_bad_output`、`test_run_boulder_failure_contracts`、`test_mapping_rejects_invalid_engine_output`、`test_empty_sequence_fails`；`RealPrimer3IntegrationTests::test_real_core_selects_ranked_pairs`、`test_real_core_separates_gibson_tail_and_binding`、`test_cli_require_primer3_reports_real_engine` |
| `tests/test_v07_primer3.py` | `Primer3StatusTests::test_probe_reports_not_installed`、`test_probe_reports_import_crash`、`test_probe_reports_available`、`test_cli_reports_unavailable_and_warns`、`test_fallback_engine_cannot_claim_primer3`、`test_require_primer3_fails_when_unavailable`、`test_require_primer3_fails_on_execution_error`、`test_require_primer3_fails_when_engine_returns_no_pair`；`CandidateOutputTests::test_default_top5_candidates_with_all_fields`、`test_top_n_configurable`、`test_candidate_shortage_warns`、`test_zero_candidates_is_structured_failure`；`PenaltyTests::test_tm_mismatch_penalty`、`test_hairpin_and_self_dimer_penalties`、`test_cross_dimer_penalty`、`test_recommendation_levels`；`GibsonSeparationTests::test_binding_and_tail_separated`、`test_annealing_parameters_from_binding_not_tail`、`test_structural_checks_use_full_primer`、`test_gibson_without_overlaps_fails`；`FailureAlarmTests` 全部 |
| `tests/test_release_iteration.py` | `ConsentBrokerTests` 全部；`PrimerEngineConsentGateTests::test_default_ask_blocks_before_any_design`、`test_slide_relaxation_denied_means_no_slide_execution`、`test_slide_relaxation_approved_executes_and_is_visible`；`TransparencyGateTests` 全部；`SlideRetryRealEngineTests::test_group_a_tail_case_binding_only`、`test_group_b_high_gc_terminal_slide_retry`、`test_group_c_poly_g_gives_actionable_alternatives`；`CliConsentGateTests::test_design_primers_ask_without_input_does_not_execute`、`test_design_primers_auto_consent_executes`；`ScenarioCoverageGateTests`、`ParameterSourcesGateTests` |
| `tests/test_validation_crosscheck.py` | `TmCrosscheckTests::test_primer3_bio_nn_agree_within_tolerance`、`test_wrong_primary_tm_flags_conflict`、`test_wallace_formula_is_short_oligo_approximation`、`test_empty_and_non_iupac`；`GcCrosscheckTests` 全部；`RestrictionCrosscheckTests::test_ecoRI_counts_agree`、`test_non_palindromic_site_both_orientations`、`test_unknown_enzyme_fails_structured` |
| `tests/test_v09.py` | `M3PrimerEngineTests::test_real_primer3_reproducible_and_in_range`、`test_restriction_tail`；`Primer3TailRetryTests::test_tailed_design_retries_binding_only`；`Primer3FailureModeTests::test_unavailable_primer3_is_explicit_fallback`、`test_require_primer3_fails_when_unavailable`；`M4StrategyTests::test_high_gc_and_at_and_long`；`AdditionalV09CoverageTests::test_primer_engine_error_branches`、`test_pcr_strategy_cli_and_branches` |
| `tests/test_destructive_inputs.py` | `PrimerEngineDestructiveTests::test_short_and_empty_regions`、`test_unknown_enzyme_and_long_tail`、`test_homopolymer_fallback_is_structured`；`PcrStrategyDestructiveTests::test_non_finite_and_negative_length` |
| `tests/test_bio_audit_regressions.py` | `test_self_dimer_detects_reverse_complement`、`test_circular_restriction_crosscheck_handles_wrap`、`test_degenerate_restriction_site_matches_iupac` |
| `scripts/smoke_core.py` / `scripts/smoke_academic.py` | `simulate_pcr` 冒烟检查（产物生成；外向/上游引物对拒绝） |

# 第 3 章：组装模拟、克隆方法与基础序列分析工具

本章覆盖 16 个脚本/模块，按职责分为四组：

| 组 | 脚本 | 职责 |
|---|---|---|
| 组装公共模型 | `scripts/assembly_model.py` | 统一片段/末端模型，同源组装与粘性末端校验，origin 坐标不变量 |
| 克隆模拟 | `scripts/simulate_cloning.py` | Gibson 组装与 digest-ligate 克隆模拟 |
| 克隆模拟 | `scripts/simulate_advanced.py` | In-Fusion、TA/TOPO、Gateway BP/LR 序列近似 |
| 克隆模拟 | `scripts/golden_gate.py` | Golden Gate / Type IIS 组装模拟 |
| 编辑与设计 | `scripts/mutagenesis.py` | 定点突变、密码子插入/删除、overlap-extension PCR 占位 |
| 编辑与设计 | `scripts/codon_optimize.py` | 按宿主密码子表反向翻译与编码区重编码 |
| 编辑与设计 | `scripts/protein_tools.py` | 蛋白反向翻译（简并 DNA）与双链寡核苷酸退火 |
| 编辑与设计 | `scripts/design_gene_replacement.py` | 基因替换盒设计（同源臂 + Gibson 引物 + QC） |
| 序列分析 | `scripts/find_sites.py` | 限制酶位点分析与模拟酶切 |
| 序列分析 | `scripts/analyze_seq.py` | 长度/GC/碱基组成/反向互补/六读框翻译 |
| 序列分析 | `scripts/align_seq.py` | 双序列全局（Needleman-Wunsch）与局部（Smith-Waterman）比对 |
| 序列分析 | `scripts/align_sanger.py` | Sanger read 比对参考与覆盖度确认 |
| 序列分析 | `scripts/msa.py` | 渐进式多序列比对与 consensus |
| 序列分析 | `scripts/assemble_contig.py` | 贪心 overlap contig 组装（CAP3 简化） |
| 序列分析 | `scripts/methylation.py` | dam/dcm/EcoKI 甲基化 motif 重叠提示（实验性） |
| 序列分析 | `scripts/annotate.py` | ORF 自动注释与酶切位点 feature 写出 |

所有路径均相对仓库根 `D:/codex_project/snapgene-dna-design-v0.9.0-work`。坐标约定与全仓库一致：CLI 参数和兼容字段中的 feature/识别序列坐标使用 1-based 闭区间；`assembly_model.py`、`construct_model.py` 内部只使用 0-based 半开区间；`sg_common.restriction_hits` 同时输出识别序列 1-based 起点和双链切口 0-based 边界。拓扑默认线性，只有显式标注 `circular` 才按环状处理（`scripts/sg_common.py:198-206`）。

本章的“实验性”标注与仓库 README 第 9 节一致：所有组装模拟输出均为计算预测，不等同于湿实验方案；`experimental: true` 的 JSON 输出只能作为概念预演。各脚本的适用边界、已知限制与对应测试在每小节“科学性说明”给出。

**数据流主线**：输入 `.dna`/`.gb`/`.fa`/裸序列 → `sg_common.load_seq`（`scripts/sg_common.py:126-188`）归一化为 `SeqRecord` → 组装类脚本把序列转换为 `AssemblyFragment` 列表 → 末端/overlap 校验 → `ConstructModel` 执行编辑或直接拼接 → `to_record`/`SeqRecord` 写出 GenBank/FASTA → JSON 成功或失败信封。所有组装失败统一经 `sg_common.jfail` 输出 `{"ok": false, "error": {"code": ..., "message": ...}}` 并退出非零；失败时不写任何产物文件（`scripts/sg_common.py:63-90`）。

**引用来源**：本章引用的权威来源包括 Sambrook & Russell《Molecular Cloning: A Laboratory Manual》（CSHL Press）；Gibson et al. 2009 *Nat Methods* 6:343-345（DOI 10.1038/nmeth.1318）；Engler et al. 2008 *PLoS One* 3:e3647（DOI 10.1371/journal.pone.0003647）；NEB/Takara/IDT 官方协议与 FAQ；Primer3 官方手册（https://primer3.org/manual.html）；Doench et al. 2016 *Nat Biotechnol* 34:184-191（DOI 10.1038/nbt.3437）；Kim et al. 2018 *Nat Biotechnol* 36:239-241（DOI 10.1038/nbt.4061）；Cas-OFFinder GitHub（https://github.com/snugel/cas-offinder）；BioPython/Bio.Restriction 文档。这些引用已在 `references/biological-parameters-sources.md` 与 `references/biological-parameters-sources.json` 中登记（例如 P15-P21、P22-P25、P27），本章沿用，不新增 DOI/URL。

## assembly_model.py：统一末端/片段模型

### 技术原理

`scripts/assembly_model.py` 是全部克隆模拟共享的数据结构层。它定义了两类对象与一组纯函数。所有坐标在此模块内均为 0-based 半开边界；overhang 序列按实际单链延伸的 5'→3' 方向存储。

| 符号/类/函数 | 行号 | 说明 |
|---|---|---|
| `END_KINDS` | 26 | `("blunt", "5'-overhang", "3'-overhang")` |
| `VALID_TOPOLOGIES` | 27 | `("linear", "circular")` |
| `class AssemblyError` | 30-36 | 携带稳定 `error.code` 的组装异常，`code/message/details` 三字段 |
| `class FragmentEnd` | 39-65 | 末端对象：`kind`、`overhang_sequence`、`cut_boundary`、`homology_sequence`、`homology_length`、`source_cut_boundary` |
| `class AssemblyFragment` | 68-99 | 片段对象：`name`、`sequence`、`topology`、`left_end`、`right_end`、`source`；`_validate` 检查 `cut_boundary` 范围 |
| `blunt_end(...)` | 102-108 | 构造平末端，可携带 Gibson 同源臂 |
| `overhang_end(kind, overhang_sequence, cut_boundary, source_cut_boundary)` | 111-114 | 构造粘性末端 |
| `gibson_fragment(name, sequence, left_overlap="", right_overlap="", topology="linear")` | 117-124 | 构造带同源臂的平末端片段 |
| `_check_one_overlap(prev, cur, ov, method, prev_idx, cur_idx)` | 127-146 | 校验相邻片段 `prev[-ov:] == cur[:ov]`，并把同源臂记录到两侧末端 |
| `validate_unique_contributions(fragments, overlap_length, circular=False)` | 149-188 | 计算每个片段去除 overlap 后的净贡献，拒绝零贡献片段与比 overlap 还短的环状产物 |
| `check_gibson_overlaps(fragments, overlap_length, method="gibson", circular=False)` | 191-214 | 对 Gibson/In-Fusion 的逐对同源臂校验，`circular=True` 额外校验末→首闭环 |
| `validate_origins(origins, product_length)` | 217-254 | 校验组装 origin 元数据的长度和、坐标范围、`contribution_segments` 与 `source_mappings` 不变量 |
| `join_by_homology(fragments, overlap_length, circular=False)` | 277-290 | 去除重复 overlap 后拼接；环状组装线性化在第一个片段左同源臂之后 |
| `_complement(seq)` | 293-295 | Bio.Seq 反向互补 |
| `compatible_sticky(left, right)` | 297-310 | 平端对平端恒真；粘端必须同 kind、等长、互补 |
| `check_sticky_junctions(fragments, circular=False)` | 313-333 | 返回相邻（及闭合）junction 兼容性列表 |

`FragmentEnd.__init__` 有两个关键边界校验：`blunt` 末端不得携带 overhang；`5'-overhang`/`3'-overhang` 必须携带非空 overhang（`scripts/assembly_model.py:52-55`）。`AssemblyFragment._validate` 要求 `cut_boundary` 落在 `[0, len(sequence)]`（`scripts/assembly_model.py:82-89`）。这些校验保证了后续所有组装方法不会在无意义末端上继续运行。

同源组装的算法是严格逐对校验：`check_gibson_overlaps` 先拒绝 `overlap<=0` 或片段数 <2，然后对 `i=1..n-1` 调用 `_check_one_overlap`；环状组装再把 `fragments[-1]` 与 `fragments[0]` 校验一次（`scripts/assembly_model.py:199-213`）。`join_by_homology` 的线性产物保留第一片段全长，后续片段从 `overlap_length` 之后拼接；环状产物把所有片段统一截掉 `overlap_length` 再拼接，使第一个片段左同源臂恰好落到产物末端、末→首 junction 跨 origin（`scripts/assembly_model.py:277-290`）。

粘性末端兼容性基于“存储实际 5'→3' 延伸序列”的约定。`compatible_sticky` 对两个 5'-overhang 或两个 3'-overhang 要求长度相等且 `_complement(left.overhang_sequence) == right.overhang_sequence`（`scripts/assembly_model.py:297-310`）。注意：该函数名中的 left/right 分别指“左片段的右端”与“右片段的左端”，调用方负责传入正确顺序。

`validate_origins` 是 v0.4 之后为组装产物溯源而设的硬坐标不变量，错误码包括 `ORIGIN_LENGTH_MISMATCH`、`ORIGIN_COORDINATE_INVALID`、`SOURCE_MAPPING_INVALID`（`scripts/assembly_model.py:217-254`）。它校验三件事：各 origin 长度之和等于产物长度；每个 origin 的 1-based 区间在产物范围内；每个 `contribution_segments` 的 source 区间不颠倒、product 区间在产物范围内；每个 `source_mappings` 的 `dropped` 映射不得携带 product 坐标、非 dropped 映射区间合法。

### 生物原理

Gibson 等温组装与 In-Fusion/NEBuilder HiFi 的共同原理是相邻片段共享 15-40 bp 末端同源序列，外切酶产生单链末端后互补退火，再由聚合酶与连接酶封闭缺口（Gibson 2009 DOI 10.1038/nmeth.1318；IDT 引物设计指南亦给出 15-40 bp overlap 建议，见 `references/biological-parameters-sources.md` P15-P17）。因此模型把这两种方法统一为“平末端 + 同源臂”的抽象，并把同源序列当作在拼接时去除的重复片段，这是对酶学过程的序列级近似，而非切口几何模拟。

粘性末端连接（digest-ligate、Golden Gate）依赖互补单链突出末端的氢键退火与 DNA 连接酶封口（Sambrook & Russell《Molecular Cloning》关于限制酶消化与连接的章节）。模型把突出末端建模为带方向与序列的 `FragmentEnd`，互补性用反向互补判定。对于回文位点产生的末端，该模型仍能工作，因为 left/right 末端由 `_hit_end_sequences` 从双链切口边界导出，不依赖回文假设。

### 实现路径

调用链示例（Gibson）：`simulate_cloning.main -> load_part -> gibson_fragment -> check_gibson_overlaps -> validate_unique_contributions -> join_by_homology -> _shift_features -> validate_origins -> jprint`。粘性末端路径：`simulate_cloning.digest_ligate -> _vector_fragment/_restriction_insert_fragment -> overhang_end -> check_sticky_junctions -> ConstructModel.insert -> to_record`。`golden_gate.assemble` 走同一组 `overhang_end`/`check_sticky_junctions` 公共函数。

### 科学性说明

`assembly_model.py` 本身不输出实验性标注，但被 `simulate_cloning.py`（digest-ligate）、`simulate_advanced.py`（全部方法）、`golden_gate.py` 标记为 `experimental: true`。模型不包含连接效率、末端磷酸化/去磷酸化、温度退火热力学、错配容忍与核酸外切酶动力学；`compatible_sticky` 只做严格互补匹配，不预测错配末端在低严格度下是否会被连接酶接受。已知限制：`join_by_homology` 假设所有 overlap 等长且只去除一次；不等长 overlap 或复杂多片段网络不在模型内表达。对应测试：`tests/test_coverage_gap.py::EndValidationErrors`、`ProductShorterThanOverlap`、`CheckGibsonOverlapsErrors`、`ValidateOriginsAllBranches`、`CompatibleStickyBranches`、`CheckStickyJunctionsEmpty`（类名省略 `Test` 前缀，下同）；`tests/test_v06.py::test_circular_zero_contribution_fails_with_stable_error`、`test_linear_zero_contribution_fails`。


## simulate_cloning.py：Gibson 组装与 digest-ligate 克隆

### 技术原理

`scripts/simulate_cloning.py` 实现两种组装：`gibson`（严格 overlap 校验）与 `digest-ligate`（限制酶双链切口边界驱动的粘性末端连接）。失败策略统一为结构化失败：`AssemblyError` 经 `jfail` 输出，退出非零，不写产物文件（`scripts/simulate_cloning.py:9-11`）。

关键函数签名与行号：

| 函数/类 | 行号 | 职责 |
|---|---|---|
| `load_part(path)` | 30-32 | `sg_common.load_seq` 的薄包装 |
| `_merge_parts_in_biological_order(parts, operator)` | 35-65 | 按生物学顺序合并相邻同链 location part；`order` 保持原顺序与 operator，`join` 只合并输入顺序相邻的同链 part |
| `_mapped_part_segments(part, trim_start, clip_end, offset, circular, is_first, product_length)` | 68-107 | 把一个 `FeatureLocation` part 映射到产物坐标；返回 `(segments, dropped_overlap)` |
| `_shift_features(record, offset, trim_start=0, clip_end=None, circular=False, is_first=False, product_length=None, product_seq=None)` | 110-178 | feature 迁移主函数：逐 part 迁移，保留 operator/part 顺序，迁移后用 `extract(Seq(product_seq))` 复核，不一致抛 `FEATURE_MIGRATION_MISMATCH` |
| `gibson(parts, overlap=0, circular=False)` | 181-214 | Gibson 组装主函数 |
| `_arc(seq, start0, end0)` | 217-227 | 环状序列顺时针切段（0-based 边界，可跨 origin） |
| `_hit_end_sequences(seq, hit)` | 230-249 | 由 `raw_top_cut_boundary_0based` 与 `raw_bottom_cut_boundary_0based` 的有符号关系推导 `kind` 与左右末端 overhang 序列 |
| `_vector_fragment(vector_rec, enzyme)` | 252-283 | 环状载体在唯一酶切位点线性化 |
| `_restriction_insert_fragment(insert_rec, enzyme)` | 285-335 | 从两酶切位点之间切出不含完整识别位点的插入片段 |
| `digest_ligate(vector_rec, insert_rec, enzyme_name)` | 337-371 | 粘性末端连接并环化，经 `ConstructModel.insert` 迁移 feature 后补 `misc_feature` insert 标签 |

Gibson 路径的产物序列在 `gibson` 中构建：先构造 `gibson_fragment` 列表，随后 `check_gibson_overlaps`、`validate_unique_contributions`、`join_by_homology`，产物序列写入 `copy.deepcopy(parts[0])` 并把 `product.features` 清空后由 `_shift_features` 逐片段重新迁移（`scripts/simulate_cloning.py:188-213`）。每个片段在产物中的 offset 用 `contributions` 累加；`trim_start` 对第 0 个片段且线性时为 0，其余为 overlap，环状组装第 0 个片段也截掉 overlap。

`_shift_features` 是 feature 迁移的合规层。它先提取源 feature 序列 `source_extract`，再获取 `location.parts` 与 `operator`（无 parts 视为单 part `join`），对每个 part 调 `_mapped_part_segments`；若线性组装中 feature 位于被去除的 overlap 内，`dropped_any=True`，显式警告并丢弃；最后用 `_merge_parts_in_biological_order` 重建 location，并用 `updated.extract(Seq(product_seq))` 与 `source_extract` 比对，不一致立即抛 `AssemblyError("FEATURE_MIGRATION_MISMATCH", ...)`（`scripts/simulate_cloning.py:161-176`）。这一复核能捕获坐标映射错误导致 feature 序列改变的情况。

`_mapped_part_segments` 处理三类几何：保留段（`retained_start=max(start, trim_start)`，`retained_end=min(end, clip_end)`）、overlap 段（`[start, min(end, trim_start))`）。环状组装时 overlap 段迁移到产物末端或前一片段末端的对应位置；线性组装时 overlap 段被移除并标记 dropped。负链 part 的段顺序是“保留段在前、overlap 段在后”，正链相反（`scripts/simulate_cloning.py:101-106`），保证 `extract` 得到的序列顺序与源一致。

digest-ligate 的切口几何由 `sg_common.restriction_hits` 提供。`_hit_end_sequences` 用原始（未模）边界 `raw_t`/`raw_b` 判断：相等为 blunt；`raw_t < raw_b` 时区域 `seq[t:b]` 为下游片段的 5'-overhang，其反向互补为上游片段末端；`raw_t > raw_b` 时为 3'-overhang，上游片段末端为 `seq[b:t]`（`scripts/simulate_cloning.py:230-249`）。注意此处与 `assembly_model` 约定一致：left 末端存下游片段实际延伸序列，right 末端存互补延伸序列。

`_vector_fragment` 要求载体为环状且目标酶有且仅有一个 `cuts_within_sequence` 的 hit，否则 `INVALID_TOPOLOGY`/`SITE_COUNT`（`scripts/simulate_cloning.py:259-271`）。`_restriction_insert_fragment` 要求插入片段记录中恰好两个有效 hit，并对两个候选弧段 `_arc(seq, t1, t2)` 与 `_arc(seq, t2, t1)` 选择不含完整识别位点（正链 site 或反向互补 rc_site）的片段；都含则 `INSERT_EXCISION_FAILED`（`scripts/simulate_cloning.py:313-335`）。`digest_ligate` 用 `check_sticky_junctions([vector_frag, insert_frag], circular=True)` 校验两个 junction（载体左端→插入右端、插入左端→载体右端）互补；随后 `ConstructModel(vector_rec).insert(vector_cut0, ins_seq).set_topology("circular").to_record()` 生成环状产物并自动迁移 vector 上的 feature，再额外追加 insert 的 `misc_feature`（`scripts/simulate_cloning.py:337-371`）。

CLI 主函数 `main` 在 `scripts/simulate_cloning.py:373-522`。Gibson 分支解析 `--parts`、`--overlap`、`--topology`，产物拓扑默认取第一个 part 的拓扑；overlap 超出 15-40 bp 或片段数 >5 时写 warning，引用 Gibson 2009 工作范围（`scripts/simulate_cloning.py:121-130`）。origin 元数据在每个片段内按 1-based 区间构造，`validate_origins` 做最终校验。digest-ligate 分支要求 `--vector --insert --enzyme`，其 `origins` 只报告 vector-backbone 与 insert-fragment 的长度（`scripts/simulate_cloning.py:200-205`）。

### 生物原理

Gibson 组装要求在相邻片段末端设计 15-40 bp 的完全同源序列（Gibson 2009 DOI 10.1038/nmeth.1318）。本脚本因此对 overlap 做严格字符串比较，而非像某些组装工具那样允许错配后拼接。载体与插入片段的限制酶消化连接是经典克隆方法：II 型限制酶在识别位点内或旁侧产生平端/5'-突出/3'-突出，连接酶重新封口（Sambrook & Russell《Molecular Cloning》）。`_hit_end_sequences` 把 Bio.Restriction 的 `fst5`/`fst3` 切口几何映射为真实突出末端，是相对多数“只按识别序列切”的模拟更接近实际的一步。但连接效率、载体自连、插入片段方向（本脚本只模拟单方向插入，且选择唯一的不含完整识别位点的弧段）、末端磷酸化状态均未建模。

### 实现路径

Gibson 输入→处理→输出：`main -> load_part(多个) -> gibson -> [check_gibson_overlaps -> validate_unique_contributions -> join_by_homology] -> _shift_features(逐片段) -> validate_origins -> SeqIO.write(out.gb) / jprint`。digest-ligate：`main -> load_part(vector/insert) -> digest_ligate -> _vector_fragment -> _restriction_insert_fragment -> check_sticky_junctions -> ConstructModel.insert -> to_record -> SeqIO.write / jprint`。

### 科学性说明

`experimental` 标志：digest-ligate 为 `true`，gibson 不设 `experimental`（但 JSON 仍含 warnings 与 product_sequence）。Gibson 序列级模拟是仓库中被测试得最充分的组装路径，但不模拟 T5 外切酶/Phusion/DNA 连接酶的酶学过程；digest-ligate 明确标注实验性，未建模自连、去磷酸化、连接温度与载体/插入比例。已知限制：`_shift_features` 对线性组装中被 overlap 部分移除的 feature 直接丢弃并 warning，而不是生成部分 feature；`_merge_parts_in_biological_order` 对 `order` operator 不做合并。对应测试：`tests/test_v04.py::FailureContractTests`、`DigestLigateEndModelTests`（含 `test_ecori_psti_smai_end_kinds_and_linear_vector_fragment`）；`tests/test_v05.py::FeatureMigrationOrderTests`（含 `test_positive_strand_partial_wrap_preserves_order_and_extract` 等）；`tests/test_v05.py::OriginsReconstructionTests`、`FeatureMigrationFailureTests`；`tests/test_v06.py::ZeroContributionTests`、`ClipEndTests`；`tests/test_gate_targets.py::CloningCliTests`（`test_gibson_cli_success_writes_product`、`test_gibson_cli_failures`、`test_circular_gibson_cli_origins`、`test_digest_ligate_cli`）；`tests/test_coverage_gap.py::CloningGapTests`（`test_shift_features_defaults_and_simple_location`、`test_arc_edge_cases`、`test_digest_ligate_psti_three_prime_overhang`、`test_insert_excision_failed_guard`、`test_sticky_end_mismatch_guard`、`test_cli_human_output_and_invalid_input`）。


## simulate_advanced.py：In-Fusion、TA/TOPO 与 Gateway 近似

### 技术原理

`scripts/simulate_advanced.py` 实现四种实验性克隆方法的序列级近似：`infusion`、`ta`/`topo`、`gateway-lr`、`gateway-bp`。模块复用 `assembly_model.AssemblyFragment` 与 `simulate_cloning._shift_features`，并内置 Invitrogen/Thermo 标准 attB/attL/attR/attP 序列（`scripts/simulate_advanced.py:46-64`）。

关键函数签名与行号：

| 函数/常量 | 行号 | 职责 |
|---|---|---|
| `ATTB1`/`ATTB2` | 46-47 | attB1（25 bp）与 attB2（25 bp）标准位点 |
| `ATTL1`/`ATTL2` | 49-52 | attL1/attL2（约 100 bp，pDONR 家族） |
| `ATTR1`/`ATTR2` | 54-57 | attR1/attR2（约 125 bp，pDEST 家族） |
| `ATTP1`/`ATTP2` | 59-64 | attP1/attP2（约 232 bp） |
| `infusion(parts, overlap=15, circular=False)` | 67-94 | 严格 In-Fusion/HiFi 组装，错配即失败 |
| `_ta_topo_fragments(vector_rec, insert_rec, vector_cut)` | 97-127 | 用用户声明的 3'-T 载体末端与 3'-A 插入末端构造片段 |
| `ta_topo_clone(vector_rec, insert_rec, vector_cut, method="ta")` | 130-151 | TA/TOPO 共享的环化插入模型 |
| `_occurrences(seq, query)` | 154-162 | 线性枚举子串所有出现位置 |
| `_require_explicit_circular(record, role)` | 165-177 | Gateway 载体必须显式 `topology=circular` |
| `_strict_att_pair(...)` | 180-238 | 严格 att 位点搜索：双向枚举、唯一性、方向、左右顺序 |
| `_extract_body(seq, left_end, right_start)` | 241-245 | 提取 att 位点之间 body |
| `_shift_feature(feature, delta)` | 248-261 | 平移 feature 的各个 part |
| `_features_between(record, start0, end0, delta)` | 264-272 | 迁移完全落在 body 内的 feature |
| `_replace_with_features(record, start0, end0, replacement, new_features)` | 275-286 | `ConstructModel.replace` 后追加新 feature |
| `gateway_bp(donor, insert)` | 289-326 | BP 反应：attB×attP → attL，产物环状 |
| `gateway_lr(entry, destination)` | 328-366 | LR 反应：attL×attR → attB，产物环状 |

In-Fusion 路径与 Gibson 共用同一套 `check_gibson_overlaps`/`join_by_homology`/`_shift_features`，默认 overlap 15 bp（`scripts/simulate_advanced.py:67-94`）。与 v0.4 之前“警告后拼接”的行为不同，当前版本 mismatch 直接 `AssemblyError("OVERLAP_MISMATCH")`，没有 warning-then-concatenate 回退（`scripts/simulate_advanced.py:11-19`）。

TA/TOPO 路径坚持“不推断末端”。`_ta_topo_fragments` 要求 `--vector-cut` 为 0-based 边界并校验 `0 <= vector_cut <= len(v)`；随后构造载体片段（两个末端均为 `3'-overhang "T"`）和插入片段（两个末端均为 `3'-overhang "A"`），并用 `check_sticky_junctions([vector_frag, insert_frag], circular=True)` 校验两个 junction（`scripts/simulate_advanced.py:97-151`）。产物用 `ConstructModel(vector_rec).insert(vector_cut, insert_frag.sequence).set_topology("circular")` 生成。CLI 在 `main` 中强制 `--vector-end t-tailed` 且 `--insert-end a-tailed`，否则 `END_TYPE_MISMATCH`；同时输出两条 note 说明：3'-T/3'-A 是用户声明前提，且 `product_sequence` 是平端插入模型、不额外加入两个 junction 处声明的 T/A 突出碱基（`scripts/simulate_advanced.py:143-160`）。这就是该方法“近似边界”的准确含义：模拟的是插入序列本身，而不是带突出碱基的最终连接分子。

Gateway 路径的严格性体现在 `_strict_att_pair`。该函数对每个 att 位点同时枚举正链序列与反向互补序列的出现位置；要求正方向恰好 1 个、反方向 0 个；否则分别抛 `ATT_SITE_MISSING`、`ATT_SITE_NOT_UNIQUE`、`ATT_SITE_ORIENTATION`；最后要求 `left_end <= right_start`，否则 `ATT_SITE_ORDER`（`scripts/simulate_advanced.py:180-238`）。BP 反应中 attB1/attB2 的预期方向为 forward/forward（`right_site_reverse=False`），attP1/attP2 为 forward/reverse；LR 反应中 attL1/attL2 与 attR1/attR2 均为 forward/reverse（`scripts/simulate_advanced.py:289-366`）。

Gateway 的序列替换逻辑是：BP 把 donor 的 `attP1..attP2` 区间替换为 `ATTL1 + body + rc(ATTL2)`；LR 把 destination 的 `attR1..attR2` 区间替换为 `ATTB1 + body + rc(ATTB2)`（`scripts/simulate_advanced.py:289-366`）。注意 Gateway 重组后 attL2/attB2 在产物上位于负链，因此代码构造 `SeqFeature(..., strand=-1)` 并在 replacement 中使用 `str(Seq(ATTL2/ATTB2).reverse_complement())`。插入 body 上的 feature 通过 `_features_between` 只迁移完全位于 att 位点之间的部分，平移量由 `r1_start + len(ATTB1) - l1_end` 等公式给出；没有可迁移 feature 时补一个 `misc_feature` insert。

CLI 的 `--vector` 在 `gateway-bp` 中扮演 donor、在 `ta/topo` 中扮演载体；`gateway-lr` 使用 `--entry` 与 `--destination`。所有方法的结果都插入固定 note `EXPERIMENTAL: this method is a sequence-level approximation; reaction chemistry and fidelity are not validated`（`scripts/simulate_advanced.py:193-197`），JSON 中 `experimental: true`。

### 生物原理

In-Fusion/NEBuilder HiFi 依赖 15 bp 同源臂与重组酶混合物（Takara In-Fusion 克隆协议）；因此脚本把 overlap 默认设为 15 bp 且允许 15-40 bp 工作范围。TA 克隆依赖 Taq 聚合酶在 PCR 产物 3' 端加 A，与线性化 T 载体（如 pGEM-T）的 3'-T 突出互补连接（Sambrook & Russell《Molecular Cloning》；Promega pGEM-T 载体系统手册）。TOPO 克隆依赖拓扑异构酶共价结合载体末端，本脚本只模拟其 T/A 互补末端前提，不模拟拓扑异构酶共价中间体。Gateway BP/LR 是 Invitrogen/Thermo 的 λ 噬菌体位点特异性重组系统：attB×attP 经 BP Clonase 生成 attL 与 attR，attL×attR 经 LR Clonase 生成 attB 与 attP；attB1/attB2 的标准序列由 Thermo 提供，attP/attL/attR 序列与 SnapGene Gateway 载体集核对（`scripts/simulate_advanced.py:43-45`）。脚本不模拟重组酶浓度、超螺旋底物、ccdB 筛选等反应约束。

### 实现路径

In-Fusion：`main -> load_part(多片段) -> infusion -> [check_gibson_overlaps -> validate_unique_contributions -> join_by_homology] -> _shift_features -> SeqIO.write/jprint`。TA/TOPO：`main -> load_part(vector/insert) -> 校验 --vector-cut/--vector-end/--insert-end -> ta_topo_clone -> _ta_topo_fragments -> check_sticky_junctions -> ConstructModel.insert -> to_record`。Gateway LR：`main -> load_part(entry/destination) -> gateway_lr -> _require_explicit_circular -> _strict_att_pair(attL)/_strict_att_pair(attR) -> _extract_body -> _replace_with_features(ConstructModel.replace) -> to_record`。Gateway BP 同理，只是位点对为 attB/attP、replacement 为 attL 盒。

### 科学性说明

全部方法 `experimental: true`。In-Fusion 序列级近似只保证 overlap 严格匹配与产物序列拼接，不模拟重组酶/外切酶效率和 frame 保留以外的生化约束。TA/TOPO 明确不推断末端、不把声明的 3'-T/3'-A 突出碱基加入产物序列，因此其 `product_sequence` 不能直接当作最终连接分子的完整序列（脚本已在 note 中说明）。Gateway 方法要求输入记录显式标注拓扑；未标注则 `MISSING_TOPOLOGY`，这是刻意的失败关闭。Gateway 替换不接受跨 origin 的 att 区间（`_replace_with_features` 中 `start0 > end0` 抛 `ATT_SITE_ORDER`，`scripts/simulate_advanced.py:275-286`），因此跨 origin 的 Gateway 载体需先 `edit_plasmid.py --op rotate` 旋转后再模拟。对应测试：`tests/test_v04.py::GoldenGatewayTests`（`test_bp_matches_committed_pENTR_EmGFP_fixture`、`test_lr_matches_committed_pDEST_EmGFP_fixture`、`test_gateway_requires_explicit_topology`、`test_gateway_rejects_misordered_att_pair_instead_of_find_first`、`test_gateway_duplicate_att_site_is_rejected`）；`tests/test_v04.py::GoldenTATests`（`test_ta_matches_committed_pGEM_T_fixture_with_explicit_premises`、`test_ta_requires_explicit_end_premises`、`test_ta_requires_vector_cut`）；`tests/test_v05.py::FeatureMigrationOrderTests::test_three_fragment_circular_infusion`；`tests/test_gate_targets.py::AdvancedCliTests`（`test_infusion_cli`、`test_ta_cli`、`test_gateway_cli`）；`tests/test_coverage_gap.py::AdvancedGapTests`（`test_ta_sticky_mismatch_guard`、`test_gateway_feature_migration_compound`、`test_replace_with_features_wrapped_rejected`、`test_cli_missing_args_and_human_output`）；`tests/test_e2e_scenarios.py::test_entry_to_destination_lr`。

## golden_gate.py：Golden Gate / Type IIS 组装模拟

### 技术原理

`scripts/golden_gate.py` 模拟 Type IIS 限制酶介导的 Golden Gate 组装。支持的酶为 `BsaI`、`BbsI`、`BsmBI`、`BtgZI`、`SapI`、`AarI`（`scripts/golden_gate.py:51`），均通过 Bio.Restriction 解析，使用官方识别序列与切点偏移，不硬编码猜测。算法分四步：识别位点定位与双链切口边界推导、切出无完整识别位点的片段、按载体+插入顺序组装、逐 junction（含闭合 junction）校验。

关键函数签名与行号：

| 函数 | 行号 | 职责 |
|---|---|---|
| `load_part(path)` | 54-56 | 读取 part 文件 |
| `_arc(seq, start0, end0)` | 59-71 | 环状序列顺时针切段（0-based 边界，可跨 origin） |
| `_contains_recognition(fragment, enzyme)` | 74-80 | 片段是否仍含完整识别位点（正链 site 或反向互补 rc_site） |
| `part_fragment(record, enzyme, topology_override=None)` | 83-198 | 核心：枚举两两 hit 对，寻找唯一无识别位点的可切出片段并返回 overhang 与诊断 |
| `assemble(records, names, enzyme, vector_idx=0, reverse=(), vector_topology="circular")` | 201-303 | 组装主函数：强制所有 part 可切出、overhang 等长、junction 全匹配 |
| `main` | 315-405 | CLI：参数校验、拓扑要求、JSON/文本输出 |

`part_fragment` 先取 `restriction_hits` 并过滤 `cuts_within_sequence`；hit 数 <2 返回 `ok=False` 与原因。随后对每对 hit `(i,j)` 计算两个 top 切点之间的弧段 `frag_a = _arc(seq, t1, t2)` 与 `frag_b = _arc(seq, t2, t1)`，左右 overhang 分别为 `_arc(seq, t1, b1)` 与 `_arc(seq, t2, b2)`；要求 overhang 非空且等长、片段不含完整识别位点。线性 part 上 `start0 >= end0` 的环绕片段被拒绝并计为 `wrap_candidates`（`scripts/golden_gate.py:110-146`）。候选唯一性由 `unique_pairs` 判定：两 hit 的合法设计只应产生一个干净片段；多于一个意味着内部位点歧义，直接拒绝而不是猜测（`scripts/golden_gate.py:148-172`）。片段长度必须大于 overhang 长度，否则返回 `ok=False`（`scripts/golden_gate.py:174-180`）。

`assemble` 对所有 part 调用 `part_fragment`，任何 part 失败即 `jfail("PART_EXCISION_FAILED")`；所有 part 的 overhang 长度必须一致，否则 `jfail("OVERHANG_LENGTH_MISMATCH")`（`scripts/golden_gate.py:226-235`）。`--reverse` 指定的插入先反向互补并交换左右 overhang，再构造 `AssemblyFragment`；载体不允许 reverse。片段模型中，右末端存储的是 `rc(info["right_overhang"])`，因为 `assembly_model` 约定“right 末端存互补延伸序列”（`scripts/golden_gate.py:270-281`）。最后 `check_sticky_junctions(fragments, circular=True)` 校验包括闭合 junction 在内的所有 junction；任一 mismatch 即 `jfail("OVERHANG_MISMATCH")`，不写产物（`scripts/golden_gate.py:294-301`）。最终序列是所有有序片段的直接拼接，产物标记为环状。

切口边界示例（`scripts/golden_gate.py:28-32`）：BsaI 识别位点 `GGTCTC(N1/N5)`，在识别位点起点（0-based 起点）后 7 与 11 处产生 top/bottom 切口，overhang 为 `seq[7:11]`；反向识别位点 `GAGACC` 也由 `sg_common.restriction_hits` 的负链反射几何搜索。`scripts/smoke_core.py:201-205` 固定断言 BsaI top=7、bottom=11。

### 生物原理

Golden Gate 组装由 Engler 等提出：Type IIS 酶在识别位点之外切割，产生用户可编程的 4 bp（或其它长度）突出末端；识别位点落在丢弃片段中，使最终产物不再含识别位点，消化与连接可在同一管中循环进行（Engler 2008 PLoS One DOI 10.1371/journal.pone.0003647；NEB Golden Gate Assembly 协议）。脚本支持 BsaI/BbsI/BsmBI/BtgZI/SapI/AarI 六种常见 Type IIS 酶，overhang 长度由 Bio.Restriction 的切点偏移推导。文献与 NEB 指南建议 Golden Gate 片段数 ≤8（`references/biological-parameters-sources.md` P18），本脚本不硬性拒绝多于 8 段，但产物序列级模拟不预测复杂多片段反应的效率。与 `simulate_cloning.digest-ligate` 相同，脚本不建模连接酶保真度、DTT/ATP 循环、温度循环、甲基化敏感性与 carrier DNA。

### 实现路径

`main -> get_enzyme -> load_part(全部 parts) -> 校验 vector 索引与 vector_topology -> assemble -> part_fragment(每个 part) -> 反向互补处理(可选) -> overhang 长度统一校验 -> 构造 AssemblyFragment -> check_sticky_junctions(circular=True) -> 拼接 -> SeqRecord 写出 / jprint`。任何失败经 `jfail` 退出非零且不写 `--out` 文件。

### 科学性说明

`experimental: true`，note 明确“Type IIS cut geometry is derived from Bio.Restriction double-strand boundaries, but ligation fidelity, feature migration, and reaction constraints are not modeled”。与 `simulate_cloning.py` 不同，Golden Gate 产物不迁移 feature；`--out` 写出的 GenBank 只有裸序列与拓扑注释，没有从 parts 继承 feature。该限制必须在交付时说明。已知限制：线性 part 的环绕片段被拒绝（这是物理正确行为，FASTA 环状载体必须用 `--vector-topology circular`）；载体必须环状；多于两 hit 且无法唯一确定干净片段时失败关闭。对应测试：`tests/test_coverage_gap.py::GoldenGateGapTests`（`test_arc_and_contains_recognition`、`test_part_fragment_wrap_rejection`、`test_part_fragment_fragment_shorter_than_overhang`、`test_overhang_length_mismatch_guard`、`test_reverse_insert_cli_success`、`test_cli_invalid_input_and_human_output`）；`tests/test_gate_targets.py::GoldenGateCliTests`（`test_cli_success_with_reverse_insert`、`test_cli_failures`）；`tests/test_e2e_scenarios.py::test_four_fragment_golden_gate`；`scripts/smoke_core.py` 中 `golden_gate junctions reported`、`golden_gate all junctions compatible`、`golden_gate uses 0-based cut boundaries 7/11`、`golden_gate aborts on overhang mismatch` 等检查；`tests/test_v03.py::ContractAndRoundTripTests::test_json_envelope_strict_v05_shape` 覆盖 JSON 信封。


## mutagenesis.py：定点突变与密码子编辑模拟

### 技术原理

`scripts/mutagenesis.py` 实现四类操作：`point`、`insert-codon`、`delete-codon`、`overlap-pcr`。前三个是确定性序列编辑，第四个是刻意失败关闭的占位实现。

| 函数 | 行号 | 职责 |
|---|---|---|
| `mutate_point(seq, mutations)` | 26-49 | 解析 `pos:base`（1-based 闭区间）并替换碱基 |
| `insert_codon(seq, pos, codon)` | 52-64 | 在 1-based `pos` 前插入 3 bp 密码子 |
| `delete_codon(seq, start, end)` | 67-86 | 删除 1-based 闭区间，要求起点在阅读框边界且长度为 3 的倍数 |
| `overlap_pcr(seq, fwd_outer, rev_outer, fwd_inner, rev_inner)` | 89-101 | 故意未实现，抛 `ValueError` |
| `main` | 104-176 | CLI，加载序列并分派操作，输出 FASTA/JSON |

`mutate_point` 的校验边界：每条 mutation 必须恰好一个冒号；`pos` 必须 `1 <= pos <= len(seq)`；碱基必须为单个 DNA/IUPAC 符号（`DNA_IUPAC` 来自 `sg_common`，包含 `ACGTRYSWKMBDHVN`）。应用方式是先把序列转为列表再逐条替换，保证重复 mutation 按命令行出现顺序覆盖（`scripts/mutagenesis.py:26-49`）。

`insert_codon` 的 `pos` 允许 `1..len(seq)+1`，与 `edit_plasmid.op_insert` 语义一致（`pos=1` 前插，`pos=len+1` 追加）；密码子必须恰好 3 个 DNA/IUPAC 碱基（`scripts/mutagenesis.py:52-64`）。`delete_codon` 假定阅读框从序列位置 1 开始，要求 `(start - 1) % 3 == 0` 且 `(end - start + 1) % 3 == 0`，否则拒绝（`scripts/mutagenesis.py:67-86`）。这一约束不读取任何 feature 注释，因此对“序列 5' 端不是起始密码子”或非编码区序列会过于严格，调用者需自行确认阅读框。

`overlap_pcr` 在 v0.3 中曾返回未修改模板，v0.4 起改为抛错，错误消息直接建议改用 `edit_plasmid.py --op mutate`（`scripts/mutagenesis.py:89-101`）。这样避免把“未模拟”伪装成“成功”。

### 生物原理

定点突变（site-directed mutagenesis）的分子生物学方法包括重叠延伸 PCR（overlap-extension PCR）、全质粒扩增（如 NEB Q5 Site-Directed Mutagenesis Kit）等。点突变改变单个碱基即可改变密码子（如 `100:A`）；密码子插入/删除改变编码序列但不改变移码，前提是插入或删除的序列是完整密码子且落在读框内。本脚本的 `point` 与 `insert-codon`/`delete-codon` 直接编辑序列，属于全质粒合成/编辑的序列级抽象，不模拟引物错配、PCR 扩增与 DpnI 消化模板等步骤。`overlap-pcr` 需要放置四条引物、把 inner 引物尾部携带的突变重建到两个扩增子中，再通过互补 overlap 拼接，当前版本明确不模拟。

### 实现路径

`main -> sg_common.load_seq -> str(record.seq).upper() -> [mutate_point | insert_codon | delete_codon | overlap_pcr] -> SeqRecord(id="mutant") -> SeqIO.write(fasta) / jprint`。失败路径为 `raise SystemExit(str(e))`，文本输出不进入 JSON 信封；这与组装类脚本的 `jfail` 信封不同，调用者应同时检查退出码与 stderr。

### 科学性说明

输出为纯序列编辑，不产生 feature 迁移。`point`/`insert-codon`/`delete-codon` 可用作序列层面的快速计算，但不等同于 QuickChange/overlap PCR 方案。已知限制：`delete_codon` 的读框假定从位置 1 开始，未读取 CDS feature；`overlap-pcr` 未实现。对应测试：`scripts/smoke_core.py` 中 `mutagenesis point mutation`、`mutagenesis insert-codon validates and inserts`、`mutagenesis delete-codon rejects non-codon span`、`mutagenesis delete-codon rejects off-frame start`、`mutagenesis overlap-pcr fails loudly instead of returning template`；`tests/test_v03.py` 不覆盖本脚本，但 `tests/test_scenario_suite_metadata.py` 确认 scenario 元数据包含 `mutagenesis` kind。

## codon_optimize.py：密码子优化与编码区重编码

### 技术原理

`scripts/codon_optimize.py` 使用宿主高频密码子表把蛋白序列反向翻译为 DNA，或把编码 DNA 按同一表格重编码。内置三种宿主：`ecoli`、`yeast`、`human`（`scripts/codon_optimize.py:22-44`）。每个氨基酸取该宿主最常用密码子；未知符号输出 `NNN`。

| 函数 | 行号 | 职责 |
|---|---|---|
| `CODON_TABLES` | 22-44 | 三种宿主的氨基酸→最频繁密码子表 |
| `_first_fasta_sequence(text)` | 49-57 | 解析单记录 FASTA 文本；多记录拒绝 |
| `_read_source_text(source)` | 60-76 | 路径类参数按文件读，否则视为裸蛋白序列；FASTA 文本转单记录 |
| `detect_mode(raw, explicit_mode=None)` | 79-101 | 启发式输入类型检测：全 DNA/IUPAC 判为 DNA，出现非 DNA 符号判为蛋白 |
| `optimize_aa(aa_seq, table)` | 104-107 | 蛋白反向翻译，未知 AA 用 `NNN` |
| `recode_dna(dna_seq, table)` | 110-125 | DNA 编码区重编码：翻译后按最优密码子重建，保留终止密码子 |
| `main` | 128-202 | CLI：自动检测/强制模式、警告、JSON/文本输出 |

`detect_mode` 的规则很直接：`clean = "".join(str(raw).split()).upper()`；若 `set(clean) - DNA_IUPAC` 非空则判定为 protein，否则判为 dna，并给出可读 warning；`--mode protein|dna` 可强制覆盖（`scripts/codon_optimize.py:79-101`）。这一规则修复了 v0.3 把纯 A/C/G/T 氨基酸序列（如 MALTW 之外的 `D`/`E` 无，但 `ATG` 会被误读为 DNA）当成蛋白翻译的历史问题——现在纯 DNA/IUPAC 输入默认为 DNA，用户要强制蛋白可显式 `--mode protein`。

`recode_dna` 先检查长度是 3 的倍数，然后 `str(Seq(dna).translate())` 得到蛋白，再用 `optimize_aa` 重建，保证“翻译产物（包括末端终止密码子）完全不变”（`scripts/codon_optimize.py:110-125`）。`optimize_aa` 对未知氨基酸符号返回 `NNN`，并在 `main` 中生成 warning（`scripts/codon_optimize.py:104-107, 147, 155-156, 172-175`）。蛋白模式输入允许 `AA_SYMBOLS`（含 `X U O J B Z -`）之外的符号，但也会转成 `NNN` 并 warning。

### 生物原理

密码子使用偏好影响翻译效率与蛋白产量；将异源基因重编码为宿主高频密码子（如大肠杆菌 `CTG`/`GCG` 等）是基因合成常用策略（Sambrook & Russell《Molecular Cloning》；IDT/NEB 密码子优化指南）。但最频繁密码子策略不是最优策略：它未考虑 mRNA 二级结构、核糖体 pausing、稀有密码子簇、5' 端低结构窗口、限制酶位点消除与重复序列。脚本注释与输出均不声称“优化表达”，只报告序列级重编码。DNA 模式保留末端终止密码子（`scripts/codon_optimize.py:110`），是合成编码区时必须保持的生物学边界。

### 实现路径

蛋白模式：`main -> _read_source_text -> detect_mode -> optimize_aa -> jprint/print`。DNA 模式：`main -> load_seq -> recode_dna -> Seq.translate -> optimize_aa -> jprint`。若 `--mode dna`，不经过 `_read_source_text`，直接走 `load_seq`，因此路径类参数总是被当作文件。

### 科学性说明

该脚本是启发式重编码，不保证表达量、可溶性或 mRNA 结构。终止密码子只保留“最优终止密码子”（E. coli/yeast 用 `TAA`，human 用 `TGA`），并提示 `optimized_protein` 与 `original_protein` 一致。对应测试：`scripts/smoke_core.py` 中 `codon_optimize back-translate`（断言 E. coli MALTW → `ATGGCGCTGACCTGG`）、`codon_optimize auto-detects DNA input`（`ATGGGATAA` → `ATGGGCTAA`，蛋白 `MG*` 不变）、`codon_optimize preserves terminal stop codon`、`codon_optimize missing protein file is an error, not a protein string`、`codon_optimize multi-record FASTA is rejected`；`tests/test_coverage_gap.py::ValidateConstructGapTests::test_codon_start_and_transl_table_fallbacks` 覆盖翻译表回退。

## protein_tools.py：蛋白反向翻译与寡核苷酸退火

### 技术原理

`scripts/protein_tools.py` 有两个子命令：`reverse-translate` 与 `anneal`。模块很小，核心是两张字典与一个重叠查找循环。

| 函数 | 行号 | 职责 |
|---|---|---|
| `AA_CODONS` | 17-23 | 简并反向翻译密码子表（IUPAC） |
| `reverse_translate(protein)` | 26-28 | 蛋白→简并 DNA，未知 AA 用 `NNN` |
| `anneal(top, bottom)` | 31-52 | 两条寡核苷酸退火为双链，识别 5' 突出 |
| `main` | 55-80 | CLI 分派 |

`AA_CODONS` 采用“保守简并”策略：为每个氨基酸选择一个 IUPAC 简并密码子，优先保证反向翻译出的任何密码子都编码目标氨基酸，而不是穷尽所有同义密码子。例如 Leu 使用 `CTN`（覆盖 CTA/CTC/CTG/CTT 四个 Leu 密码子）而不是 `YTN`——后者会引入 `TTN` 中的 TTT/TTC（Phe），造成错误氨基酸；Leu 的另两个密码子 `TTA/TTG` 与 Arg 的 `AGA/AGG` 被有意排除。六密码子 Ser 使用 `TCN`，覆盖 TCT/TCC/TCA/TCG 四个 Ser 密码子，不覆盖 AGT/AGC；代码注释（`scripts/protein_tools.py:14-16`）明确说明这是“exact four-codon family rather than a broader pattern that introduces a different amino acid”。因此该表是保守简并，不等同于完全覆盖所有同义密码子。

`anneal` 的算法：bottom 以 5'→3' 给出；计算 `rc_bottom = reverse_complement(bottom)`，然后从 `shift=0..len(top)-1` 寻找 `top[shift:shift+overlap] == rc_bottom[:overlap]` 且 `overlap >= 4` 的第一个匹配；找到后返回 `top` 全长、`bottom = rc(top)`、退火长度与 5' 突出信息（`scripts/protein_tools.py:31-52`）。若找不到互补 overlap ≥4 bp，抛 `ValueError`。该实现允许 bottom 是 top 反向互补的子集（模拟 5' 突出），但不处理 3' 突出（bottom 更长且 top 只覆盖底部中间）——因为搜索方向是 top 的 5' 端与 rc_bottom 的 5' 端对齐。若需要 3' 突出或双突出模型，应使用其它工具或手工构建。

### 生物原理

蛋白反向翻译用于设计简并引物或基因合成文库。IUPAC 简并密码子表是分子克隆常规工具（Sambrook & Russell《Molecular Cloning》；IDT 简并密码子表）。`anneal` 模拟两条互补寡核苷酸退火形成双链 DNA：互补区退火，未配对 5' 端成为突出末端。4 bp 最小互补长度是脚本人为阈值，不是文献硬性规定；更短互补在低盐/低温下也可能退火，但脚本拒绝以避免假阳性。

### 实现路径

`reverse-translate`：`main -> reverse_translate -> jprint`。`anneal`：`main -> anneal -> jprint`。两个命令都无文件写出。

### 科学性说明

`reverse_translate` 是简并反向翻译，不是最优密码子选择；它会为未知符号输出 `NNN`。`anneal` 只支持 bottom 为 top 反向互补子集（产生 5' 突出或平端）的情况，不支持 3' 突出。对应测试：`scripts/smoke_core.py` 中 `protein_tools reverse-translate`（`ATG` 在简并 DNA 中）、`degenerate codons do not include off-target amino acids`（`LR*` → `CTNCGNTAR`）、`protein_tools anneal`（长度 ≥4）。

## design_gene_replacement.py：基因替换盒设计

### 技术原理

`scripts/design_gene_replacement.py` 为“在模板中把目标基因替换为新 CDS”的场景设计完整计算方案：定位靶标 → 提取同源臂 → 构建替换盒 → 设计带同源臂尾巴的 Gibson 引物 → QC → 写出编辑产物。模块依赖 `design_primers.best_primer` 选择替换 CDS 两端的结合区，依赖 `edit_plasmid.op_replace` 生成最终产物。

| 函数 | 行号 | 职责 |
|---|---|---|
| `DEFAULT_FLANK` | 46 | 默认同源臂长度 40 bp |
| `find_target(record, gene=None, region=None)` | 49-82 | 按 label/gene 子串匹配或显式 `start-end` 定位靶标；返回 1-based 闭区间与 compound 标志 |
| `design_replacement(record, replacement_dna, flank=DEFAULT_FLANK, gene=None, region=None, target_tm=60.0, min_len=18, max_len=30)` | 85-186 | 核心设计函数 |
| `main(argv=None)` | 189-273 | CLI |

`find_target` 的匹配是 case-insensitive substring：对每个 feature 取 `label` 或 `gene` qualifier，`gene.lower() in str(label).lower()`；命中多个报错并要求显式 `--target-region`；命中 0 个报错并列出全部 label（`scripts/design_gene_replacement.py:49-82`）。CompoundLocation feature 用 `min(part.start)` 与 `max(part.end)` 作为 0-based 半开区间，返回 1-based `start0+1, end0` 与 `compound=True`。

`design_replacement` 的流程：提取上游臂 `seq[start-1-flank : start-1]` 与下游臂 `seq[end : end+flank]`（注意 1-based `start/end` 转 0-based 半开边界；`end` 本身就是 0-based 半开终点，故下游臂从 `end` 开始）。任何一侧不足 `flank` 即报错（`scripts/design_gene_replacement.py:95-101`）。替换盒 = 上游臂 + 替换 CDS + 下游臂（`scripts/design_gene_replacement.py:104`）。正/反向 Gibson 引物分别由 `best_primer(replacement)` 与 `best_primer(rc(replacement))` 选择结合区；正向引物 = 上游臂 + 结合区，反向引物 = rc(下游臂) + 反向结合区（`scripts/design_gene_replacement.py:106-157`）。反向引物尾巴取下游臂反向互补，因为反向引物从底链合成，这一注释在 `scripts/design_gene_replacement.py:180-182` 明确写出。

QC 检查四项：替换 CDS 是否以 `ATG` 开头、是否以 `TAA/TAG/TGA` 结尾、长度是否为 3 的倍数、GC 是否在 30-70%。风险写入 `design["qc"]["risks"]`（`scripts/design_gene_replacement.py:112-133`）。`main` 若 `--out` 则调 `edit_plasmid.op_replace` 生成产物 GenBank；若 `--design-json` 则写出设计 JSON（`scripts/design_gene_replacement.py:229-246`）。

### 生物原理

基因替换（gene replacement/allele swap）常通过同源重组或 Gibson 组装完成：两侧同源臂与受体模板同源，中间为新 CDS；若用 Gibson 引物扩增替换盒，引物 5' 尾巴就是同源臂，3' 结合区在替换 CDS 内（Gibson 2009 DOI 10.1038/nmeth.1318）。默认 40 bp 同源臂高于 Gibson 建议的 15-40 bp 下限，对酵母/真菌基因替换常用 40-60 bp 同源臂；脚本提示“湿实验验证 homology length, recombination fidelity and host background 始终必需”（`scripts/design_gene_replacement.py:24-25`）。`best_primer` 是 `design_primers.py` 的向后兼容启发式选择器（`scripts/design_primers.py:92-106`），其 Tm 计算基于 Biopython `Tm_NN`（盐校正，Na+ 50 mM）；如果替换 CDS 很短或 GC 极端，`best_primer` 可能返回 `None`，此时对应引物为 `None`，设计 JSON 应被人工复核。

### 实现路径

`main -> load_seq(template)/load_seq(replacement) -> design_replacement -> find_target -> 同源臂提取 -> best_primer(fwd/rev) -> QC -> op_replace(record, start, end, replacement) -> SeqIO.write(product.gb) -> jprint/print`。

### 科学性说明

输出是“计算辅助设计”，不是可执行实验方案。`design["qc"]["risks"]` 会提示无起始密码子、无终止密码子、读框非 3 倍数、GC 异常。已知限制：`find_target` 对复合 feature 只取 min..max 跨度，替换后不会按原 compound 结构迁移；`best_primer` 是启发式选择器，不调用 Primer3，也不做 hairpin/dimer QC。对应测试：`tests/test_gate_targets.py::V06FeatureTests` 中 `test_design_gene_replacement_core`、`test_design_gene_replacement_qc_risks_and_region`、`test_design_gene_replacement_cli`；`tests/test_gate_targets.py::test_generate_design_report` 间接覆盖设计 JSON 被下游报告消费。


## find_sites.py：限制酶位点分析与模拟酶切

### 技术原理

`scripts/find_sites.py` 包装 `sg_common` 的酶解析、位点搜索与双链切口边界，并额外提供 `--digest` 片段长度模拟。默认酶列表 `COMMON_ENZYMES` 包含 30 种常用酶（含 BsaI/BbsI/BsmBI/BtgZI/SapI/AarI 六个 Type IIS 酶）（`scripts/find_sites.py:13-18`）。

| 函数 | 行号 | 职责 |
|---|---|---|
| `COMMON_ENZYMES` | 13-18 | 默认 30 种酶 |
| `enzyme_info(enzyme)` | 21-34 | 读取 Bio.Restriction 的 `site`、`ovhg`、`fst5`、`fst3` |
| `digest_report(seq, topo, enzyme_names)` | 37-58 | 按 top 切点边界模拟消化并输出片段长度 |
| `main` | 61-127 | CLI |

`main` 对每个酶调 `sg_common.get_enzyme`（大小写不敏感解析）、`sg_common.restriction_hits`（识别位点 + 双链切口）与 `sg_common.enzyme_sites`（Bio.Restriction.search 的切点位置，用于兼容字段 `top_cut_first_bases_1based`）。JSON 输出中 `sites_1based` 是识别序列 1-based 起点，`top_cut_first_bases_1based` 是“切点后第一个碱基”的 1-based 位置；二者对 EcoRI 在 `GGAATTCC` 上分别为 2 与 3，这是仓库 P0 级别的坐标区分（`scripts/smoke_core.py:56-63` 固定断言）。`restriction_hits` 的每个 hit 还给出 `top_cut_boundary_0based`、`bottom_cut_boundary_0based`、`raw_*` 与 `cuts_within_sequence` 字段，优先用于精确切口边界（`scripts/sg_common.py:258-338`）。

`digest_report` 只按 `enzyme_sites` 的 top 切点模拟：收集 `pos - 1` 作为 0-based 边界，排序去重；环状序列的片段长度为相邻切点弧长，线性序列从 0 与 n 两端夹逼；最后过滤长度为 0 的片段并按降序排列（`scripts/find_sites.py:37-58`）。该函数是单酶/多酶混合消化的简化近似，多酶混合时只合并切点，不判断星号活性、缓冲液兼容性、甲基化敏感性与双酶切所需条件。

### 生物原理

II 型限制性内切酶识别特定回文或非回文序列并切割（Sambrook & Russell《Molecular Cloning》；NEBcutter/Bio.Restriction 文档）。`sg_common.restriction_hits` 同时扫描正链识别序列与反向互补识别序列，正链切点偏移为 `fst5` 与 `start + width + fst3`，负链切点按 `start - fst3` 与 `start + width - fst5` 反射（`scripts/sg_common.py:306-314`）。环状序列通过复制 `(width-1)//n + 2` 倍搜索窗口实现跨 origin 识别（`scripts/sg_common.py:286-289`），并能标记 `wraps_origin`。

### 实现路径

`main -> load_seq -> topology(record) -> 对每个酶: get_enzyme -> restriction_hits/enzyme_sites/enzyme_info -> 汇总 results -> 可选 digest_report -> jprint/print`。

### 科学性说明

位点搜索本身基于 Bio.Restriction 官方数据，结果可靠；但 `digest_report` 只按 top 切点近似，对产生 5'/3' 突出的酶，片段长度通常仍正确（切点边界对应磷酸二酯键），但双酶切顺序、星号活性、缓冲液与甲基化影响未建模。输出上限：`sites_1based` 与 `top_cut_first_bases_1based` 只保留前 200 个，`hits` 也只保留前 200 个。对应测试：`scripts/smoke_core.py` 中 `find_sites EcoRI recognition start == 2`、`find_sites EcoRI top cut before base 3`、`circular EcoRI site starts at 10 and wraps origin`、`topology defaults linear`；`tests/test_v03.py::ContractAndRoundTripTests::test_json_envelope_strict_v05_shape`；`tests/test_v03.py` 中 Type IIS 正/反向切口边界测试（`test_type_iis_forward_and_reverse_boundaries`）覆盖 BsaI `(7,11)` 与反向 `(1,5)`。

## analyze_seq.py：基础序列统计、反向互补与翻译

### 技术原理

`scripts/analyze_seq.py` 提供 `stats`、`revcomp`、`translate` 三个子命令。代码全部基于 Biopython `Seq` 与 `sg_common.gc_percent`。

| 函数 | 行号 | 职责 |
|---|---|---|
| `tm_estimate(seq)` | 20-23 | `Bio.SeqUtils.MeltingTemp.Tm_NN` 最近邻 Tm（盐校正 50 mM Na+），保留 1 位小数 |
| `cmd_stats(record, as_json)` | 26-45 | 长度、GC%、碱基计数、非 ACGT 计数与比例、Tm 估计 |
| `cmd_revcomp(record, as_json)` | 48-53 | 反向互补 |
| `cmd_translate(record, as_json, frame=None)` | 56-90 | 指定读框或全部 6 读框翻译 |
| `main` | 93-111 | CLI 分派 |

`cmd_stats` 的 GC 用 `sg_common.gc_percent`，兼容 Biopython <1.80 的 `GC` 与 >=1.80 的 `gc_fraction`（`scripts/sg_common.py:209-218`）。`ambiguous_count` 统计 `not in "ACGT"` 的碱基，因此 `N`、IUPAC 混合碱基与 `-` 都计入。`tm_estimate` 对长度 <10 bp 返回 `None`，避免最近邻方法在过短序列上的不可靠估计（`scripts/analyze_seq.py:38`）。

`cmd_translate` 的读框映射是 1-based CLI 语义：`frame 1..3` 为正义链偏移 `0..2`，`frame 4..6` 为反向互补链偏移 `0..2`，标签分别为 `+1/+2/+3` 与 `-1/-2/-3`（`scripts/analyze_seq.py:66-77`）。翻译使用 `Seq.translate()` 标准遗传密码表，未处理细菌/酵母/哺乳动物线粒体等替代密码表；部分密码子会触发 `Partial codon` 警告，脚本在导入时过滤该警告（`scripts/analyze_seq.py:17`）。

### 生物原理

GC% 与最近邻 Tm 是引物设计、克隆模拟与序列 QC 的基础参数（Primer3 官方手册 https://primer3.org/manual.html 对 GC/Tm 有默认窗口；Biopython `MeltingTemp.Tm_NN` 实现 SantaLucia 最近邻参数与盐校正）。六读框翻译是 ORF 注释和表达框校验的基础：原核/真核基因组的正向与反向六种读框均应检查（Sambrook & Russell《Molecular Cloning》）。

### 实现路径

`main -> load_seq -> cmd_stats/cmd_revcomp/cmd_translate -> jprint/print`。

### 科学性说明

`translate` 是直接翻译，不寻找 ORF（ORF 注释见 `annotate.py`），也不报告读框选择依据。`tm_estimate` 对 <10 bp 返回空，避免误导。对应测试：`scripts/smoke_core.py` 中 `translate envelope present`、`frame 1 == +1`、`frame 6 == -3`；`tests/test_v03.py` 的 JSON 信封测试覆盖 `find_sites.py` 但 `analyze_seq.py` 的信封形状由 `tests/test_v04.py::FailureContractTests::test_failure_envelope_matches_success_shape` 与 smoke 覆盖。

## align_seq.py：全局与局部双序列比对

### 技术原理

`scripts/align_seq.py` 实现不带空位罚分扩展的 Needleman-Wunsch 全局比对与 Smith-Waterman 局部比对。评分常量为 `MATCH=2, MISMATCH=-1, GAP=-2`（`scripts/align_seq.py:14`）。

| 函数 | 行号 | 职责 |
|---|---|---|
| `_traceback(score, trace, a, b, i, j, stop_at_zero=False)` | 17-31 | 从 `(i,j)` 回溯，局部模式在 score 为 0 时停止 |
| `global_align(a, b)` | 34-56 | Needleman-Wunsch 全局比对 |
| `local_align(a, b)` | 59-83 | Smith-Waterman 局部比对，返回 best score、比对串与起止坐标 |
| `_stats(al_a, al_b)` | 86-96 | identity/matches/mismatches/gaps 统计 |
| `_format_pair(al_a, al_b, width=60)` | 99-106 | 文本比对块 |
| `main` | 109-155 | CLI |

`global_align` 初始化第一行/列为 `i*GAP`/`j*GAP`，递推取 `diag/up/left` 最大值；平局优先级固定为 diag > up > left（`scripts/align_seq.py:38-54`）。`local_align` 递推时与 0 取最大值，并记录 `best_i/best_j/best_score`；回溯从 best 单元格开始，遇 score 0 停止（`scripts/align_seq.py:59-83`）。局部比对的 1-based 起点计算为 `si+1 if ei>si else 0`（`scripts/align_seq.py:127-130`），避免零长度比对报告 1..0 的怪异区间。

`_stats` 的 identity 定义是 `matches / alignment_length * 100`，其中 alignment_length 包含空位列；这不是 BLAST 的 identity 定义（BLAST 通常 identity = matches / (matches + mismatches)，不含 gap）。调用者解读时必须注意这一差异（`scripts/align_seq.py:86-96`）。

### 生物原理

Needleman-Wunsch 与 Smith-Waterman 是序列比对的经典动态规划算法（Sambrook & Russell《Molecular Cloning》序列分析章节；BioPython PairwiseAligner 文档）。全局比对适用于完整构建体 vs 参考序列的端到端核对；局部比对适用于在长参考序列中定位短 read、引物或 motif。本脚本是教学级 O(nm) 时间/O(nm) 空间实现，未做 Hirschberg 空间优化，也不支持 affine gap、错配罚分矩阵与替代矩阵。

### 实现路径

`main -> load_seq(query/reference) -> global_align/local_align -> _stats -> 可选 _format_pair -> jprint/print`。

### 科学性说明

序列长度受 O(nm) 内存限制；对 >10 kb 的完整质粒比对，建议改用 Biopython `PairwiseAligner` 或 minimap2/MAFFT 等专用工具。identity 统计含 gap 列，与 BLAST/CLUSTAL 的 pairwise identity 可能不同。对应测试：`scripts/smoke_core.py` 中 `align_seq detects 1 mismatch`、`align_seq local finds subread`、`local alignment stops at zero without crashing`（断言 query `GGGACGT` 对 reference `TTTACGT` 的局部比对为 `ACGT`，起点 4）；`scripts/smoke_academic.py` 有同名检查。

## align_sanger.py：Sanger read 比对与覆盖度确认

### 技术原理

`scripts/align_sanger.py` 把一条或多条 Sanger read 局部比对到参考序列，并用 0/1 覆盖轨道汇总覆盖区间与确认状态。模块复用 `align_seq.local_align` 与 `_stats`。

| 函数 | 行号 | 职责 |
|---|---|---|
| `load_reads(paths)` | 21-39 | 读取多记录 FASTA 或多个文件，UTF-8-sig 失败回退 latin-1，再失败回退 `load_seq` |
| `align_read_to_ref(read, ref)` | 42-54 | 局部比对，返回覆盖区间与统计 |
| `main` | 57-118 | CLI：逐 read 比对、覆盖轨道、确认状态、覆盖/未覆盖区间 |
| `_complement_spans(spans, n)` | 121-131 | 由 1-based 覆盖区间求 0-based 未覆盖区间 |

`align_read_to_ref` 调用 `local_align(read, ref)`，取 `ref_start0/ref_end` 作为 0-based 半开覆盖区间；`ref_start = ref_start0 + 1 if ref_end > ref_start0 else 0`（`scripts/align_sanger.py:42-54`）。`main` 中 `covered = [0] * n` 记录每个参考位点被多少 read 覆盖；`confirmed = identity >= --min-identity`（默认 80.0）。覆盖度百分比为 `covered_bp / n * 100`；覆盖 spans 与未覆盖 spans 分别按 1-based 闭区间输出（`scripts/align_sanger.py:57-118`）。`_complement_spans` 使用 `cursor` 在 1-based 空间推进，返回 0-based 半开未覆盖区间，再在外层转 1-based。

### 生物原理

Sanger 测序验证是质粒构建的标准 QC：测序 read 应覆盖克隆 junction、ORF 与关键突变位点；通常要求双向覆盖或至少单 read 高 identity 覆盖关键区域（Sambrook & Russell《Molecular Cloning》）。脚本不生成 consensus 序列，而是按位点报告覆盖/未覆盖，并逐 read 报告 mismatch 与 indel 计数。`min-identity` 默认 80% 是宽松阈值，Sanger read 首末端 50-100 bp 常含低质量序列，实际分析应人工检查峰图（本脚本不读 .ab1）。

### 实现路径

`main -> load_seq(reference) -> load_reads -> 对每条 read: align_read_to_ref -> 更新 covered 轨道 -> 汇总 spans -> jprint/print`。

### 科学性说明

脚本只做局部比对，不 trim 低质量末端、不识别杂合/双峰、不处理 .ab1 质量值；`coverage_percent` 仅代表至少一条 read 覆盖的位点比例，不等同于 consensus 准确性。对应测试：`scripts/smoke_core.py` 中 `align_sanger confirms read`；`scripts/smoke_academic.py` 同名检查；`tests/test_readme_commands.py` 只检查 README 命令代表性，不覆盖本脚本。


## msa.py：渐进式多序列比对

### 技术原理

`scripts/msa.py` 实现 star/progressive 多序列比对：选最长序列为初始 profile，随后把每条新序列与 profile 的 anchor 做全局比对，并按新 anchor 的空位模式重排已有行。

| 函数 | 行号 | 职责 |
|---|---|---|
| `load_sequences(paths)` | 19-28 | 读取多个 FASTA/序列文件 |
| `_align_profile(profile, seq)` | 31-44 | 用 `global_align(anchor, seq)` 对齐新序列，并把已有行 rebase 到新 anchor |
| `_rebase(row, old_anchor, new_anchor)` | 47-66 | 按旧 anchor→新 anchor 的空位映射重排行 |
| `msa(seqs)` | 69-86 | 主流程：排序、逐条比对、生成 consensus |
| `_format_block(aligned, consensus, width=60)` | 89-96 | 文本块输出 |
| `main` | 99-126 | CLI，可选 `--out-fasta` 写对齐 FASTA |

`msa` 先按长度降序排序；`profile` 初始为 `[seqs[0][1]]`；随后对每条剩余序列调 `_align_profile`，其中 anchor 始终是 `profile[0]`（最长序列）且 `global_align` 返回的新 anchor 与 aligned seq 具有相同空位列。`_rebase` 遍历 `new_anchor`，遇 gap 输出 gap，遇非 gap 则跳过旧 anchor 中的 gap 后把对应行字符复制到输出（`scripts/msa.py:47-66`）。该逻辑成立的前提是“旧 anchor 与新 anchor 是同一序列、只是空位模式不同”，`_align_profile` 保证这一点。

Consensus 生成：逐列收集非 gap 字符，取最高频字符；全 gap 列输出 `-`（`scripts/msa.py:77-85`）。如果输入只有一条序列，直接返回该序列与自身作 consensus（`scripts/msa.py:71-72`）。

### 生物原理

多序列比对是进化分析、保守区识别与测序 read 比对的常规方法。渐进式比对（progressive alignment）是 CLUSTAL W/Omega 与 MAFFT 等工具的基础策略；本脚本选择最长序列作为初始模板，属于 star 近似，不是 guide tree 驱动的真实 progressive。全局比对使用 `align_seq.global_align`，因此 gap 罚分与替代矩阵同样简单。

### 实现路径

`main -> load_sequences -> msa -> [_align_profile/_rebase/consensus] -> 可选写 FASTA -> jprint/print`。

### 科学性说明

该实现是教学级 star 比对：锚点固定在最长序列，顺序影响结果；不计算 guide tree、不重估计权重、不支持 profile-profile 比对。对序列长度或条数较大时，重复 `global_align` 的 O(nm) 开销会迅速增长。对应测试：仓库当前没有以 `msa` 命名的专用 unittest；该脚本由 `tests/test_readme_commands.py::test_skill_does_not_claim_every_script_has_json` 与 README 命令一致性间接约束（README 示例 `python scripts/msa.py <seq1.fa> <seq2.fa> ... [--out-fasta aln.fa] [--json]` 必须可执行）。如需发布门禁，应补充专用测试。

## assemble_contig.py：贪心 overlap contig 组装

### 技术原理

`scripts/assemble_contig.py` 是 CAP3 风格的简化版：反复寻找 read 之间的 suffix-prefix overlap，贪心合并最高 overlap 的 read 对，直到无可合并对。

| 函数 | 行号 | 职责 |
|---|---|---|
| `load_reads(paths)` | 19-28 | 读取 FASTA reads |
| `best_overlap(a, b, min_overlap)` | 31-42 | 返回 `a` 后缀等于 `b` 前缀（`ab`）或 `b` 后缀等于 `a` 前缀（`ba`）的最大长度 |
| `assemble(reads, min_overlap=20)` | 45-91 | 贪心合并主循环 |
| `main` | 94-127 | CLI，写 contig FASTA |

`best_overlap` 从 `min(len(a), len(b))` 到 `min_overlap` 递减搜索，找到即返回，因此是最大 overlap 优先。`assemble` 每轮对当前所有片段对找全局最大 overlap，合并 `id_a+"+"+id_b`（或反向顺序），替换两个片段为一个；直到最大 overlap ≤0 或只剩 1 条。合并 id 以 `+` 连接，读成员关系可从 contig id 反推（`scripts/assemble_contig.py:45-91`）。脚本注释明确说明不追踪每条 read 在 contig 中的坐标；这与 CAP3 的布局输出不同。

### 生物原理

Sanger/短读组装通常先找 read 间的 overlap，再逐步延伸 contig（CAP3 使用碱基质量与比对分值；现代短读组装使用 de Bruijn 图）。本脚本是最简化的贪心策略：只接受完全匹配的 suffix-prefix overlap，不考虑测序错误、杂合位点、重复序列、read 方向与质量值。

### 实现路径

`main -> load_reads -> assemble -> 写出 contig_1..contig_k FASTA -> jprint/print`。

### 科学性说明

贪心 + 精确匹配意味着任何测序错误都会阻断合并，且重复序列可能导致错误连接或提前终止。`min_overlap` 默认 20 bp，无统计依据。不追踪 placement 坐标。对应测试：仓库当前没有以 `assemble_contig` 命名的专用 unittest；README 示例 `python scripts/assemble_contig.py --reads <reads.fa> [--min-overlap 20] [--json]` 被 `tests/test_readme_commands.py` 的“README 命令不得虚构”约束。正式分析应使用 CAP3、phrap、SPAdes 等工具。

## methylation.py：甲基化 motif 重叠提示（实验性）

### 技术原理

`scripts/methylation.py` 扫描 dam/dcm/EcoKI 三种原核甲基化 motif，并报告与限制酶识别位点的重叠。脚本不包含“酶×甲基化酶敏感性”数据库，不推断 blocked 位点。

| 常量/函数 | 行号 | 职责 |
|---|---|---|
| `METHYLATION` | 22-26 | `("dam", "GATC")`、`("dcm", "CC[AT]GG")`、`("ecoki", "AAC[ACGT]{6}GTGC")` |
| `find_motif(seq, pattern)` | 29-34 | 正链 regex 扫描，返回 1-based 起点 |
| `site_overlaps_motif(site_start, site_len, motif_start, motif_len)` | 37-40 | 1-based 区间重叠判定 |
| `biopython_methylable(enzyme)` | 43-48 | 读取 Bio.Restriction 的粗粒度 `is_methylable()` |
| `main` | 51-137 | CLI |

`main` 先扫描三种 motif 并输出前 100 个位点；随后对每个酶用 `restriction_hits` 定位识别位点，对每个非跨 origin hit 检查是否与任一 motif 区间重叠，输出 `status: "candidate_overlap_only"`（`scripts/methylation.py:82-96`）。跨 origin 的 hit 直接跳过，注释说明“deferred until circular interval support is complete”（`scripts/methylation.py:83-84`）。结果中每个酶的 `sensitivity.dam/dcm/ecoki` 恒为 `None`，`blocked_sites` 恒为空数组，并附总 warning（`scripts/methylation.py:100-113`）。

### 生物原理

大肠杆菌 Dam 甲基化（GATC 中 A 甲基化）与 Dcm 甲基化（CCWGG 中第二个 C 甲基化）会阻断或抑制某些限制酶切割（如 ClaI 识别 ATCGAT 对 Dam 敏感）；EcoKI 识别 AACN6GTGC 并甲基化腺嘌呤。但这些“某酶是否敏感”的规则是酶特异性的，需要制造商数据（NEB、Thermo 的甲基化敏感性表）。Bio.Restriction 的 `is_methylable` 只表示酶数据库中存在甲基化注释的粗标志，不等于对 dam/dcm/EcoKI 敏感。脚本因此只做重叠提示。

### 实现路径

`main -> load_seq -> find_motif(dam/dcm/ecoki) -> 对每个酶: get_enzyme -> restriction_hits -> 与 motif 重叠判定 -> jprint/print`。

### 科学性说明

`experimental: true`。输出不能用于判定某个酶切位点是否被甲基化阻断；必须查制造商当前数据。对应测试：`scripts/smoke_core.py` 中 `methylation does not invent dam/dcm sensitivity`（断言 `sensitivity.dam is None` 且 `blocked_sites == []`）；`scripts/smoke_academic.py` 同名检查。

## annotate.py：ORF 自动注释与酶切位点 feature 写出

### 技术原理

`scripts/annotate.py` 在序列中查找 ORF（默认仅正链 3 帧），可选附加限制酶位点，并写出 GenBank 或 JSON。

| 常量/函数 | 行号 | 职责 |
|---|---|---|
| `STOP` | 17 | `{"TAA","TAG","TGA"}` |
| `find_orfs(seq, min_len=300, both_strands=False)` | 20-66 | ORF 扫描：`ATG..in-frame stop`，默认 `min_len` 300 bp |
| `main` | 69-166 | CLI，可选 `--out-gb` |

`find_orfs` 对正链 3 帧（`both_strands=True` 时 6 帧）逐密码子扫描。帧内从 `ATG` 开始，沿 3 bp 步进寻找终止密码子；找到后若 `aa_len * 3 >= min_len` 则记录 `(start0, end0, strand)`，并跳到终止密码子后继续；找不到终止密码子则 `break`（`scripts/annotate.py:37-57`）。负链先对 `reverse_complement()` 扫描，再把坐标映射回原序列（`start0, end0 = n - end0, n - start0`，`strand=-1`）。结果按元组排序并去重。

`main` 把每个 ORF 翻译为蛋白（负链先取反向互补再翻译），feature 名为 `ORF_<start1>_<end0>`。若 `--enzyme`，对每个酶取 `restriction_hits` 并作为 `misc_feature` 加入；跨 origin 的识别位点用 `CompoundLocation` 两段 join 表示（`scripts/annotate.py:132-146`）。`--out-gb` 写出时保留输入记录的 id/name/annotations，追加新 feature。

### 生物原理

原核基因预测常用 ORF 扫描（起始密码子 ATG 到同框终止密码子），但真核基因含内含子，不能直接 ORF 扫描。默认 `min_len=300 bp` 是任意阈值，只用于过滤短 ORF 噪音；NCBI 原核基因预测用更长阈值与统计模型（Sambrook & Russell《Molecular Cloning》）。限制酶位点 feature 用于质粒图谱标注，SnapGene 亦将识别位点显示为酶切位点 feature。

### 实现路径

`main -> load_seq -> find_orfs -> 翻译 ORF -> 可选酶位点 -> 可选 SeqIO.write(genbank) -> jprint/print`。

### 科学性说明

ORF 扫描会遗漏非 ATG 起始、TGA 编码硒代半胱氨酸、重叠读框、内含子基因与短 ORF；`--both-strands` 可补扫负链。写出 GenBank 时 ORF 的 `translation` qualifier 会去掉终止密码子（`rstrip("*")`）。对应测试：`scripts/smoke_core.py` 中 `annotate EcoRI found`、`annotate gb re-reads`、`annotate writes enzyme site into GenBank features`、`reverse ORF translates to MK*`；`scripts/smoke_academic.py` 同名检查。

## 跨模块主题：限制酶双链切口边界

本章多个脚本（`find_sites.py`、`simulate_cloning.py`、`golden_gate.py`、`methylation.py`、`annotate.py`）依赖 `sg_common.restriction_hits` 的统一双链切口模型，此处集中说明。

`restriction_hits(seq, enzyme, circular=False)`（`scripts/sg_common.py:258-338`）返回识别序列与双链切口的完整几何：对正链 hit，`top_cut = start0 + fst5`，`bottom_cut = start0 + width + fst3`；对负链 hit，`top_cut = start0 - fst3`，`bottom_cut = start0 + width - fst5`。`raw_*` 字段保留线性序列上的未模坐标，`top_cut_boundary_0based/bottom_cut_boundary_0based` 在环状时模 `n` 到 `0..n-1`。`cuts_within_sequence` 在线性序列上要求 `0 <= raw_top_cut <= n` 且 `0 <= raw_bottom_cut <= n`，环状恒为真（`scripts/sg_common.py:319-337`）。这一模型对 Type IIS（如 BsaI GGTCTC 1/5）给出 top=7、bottom=11（相对识别起点），对经典 II 型酶（EcoRI GAATTC 1/5）给出 top=1、bottom=5（相对识别起点），与 Bio.Restriction 官方 `fst5/fst3` 一致。

`enzyme_sites(seq, enzyme, circular=False)`（`scripts/sg_common.py:242-255`）是兼容层，返回 Bio.Restriction.search 的“切点后第一个碱基”1-based 位置，只应作为显示字段；任何依赖精确切口的逻辑都应使用 `restriction_hits` 的边界字段。`find_sites.py` 同时输出两者，并显式区分 `sites_1based`（识别起点）与 `top_cut_first_bases_1based`（切点后首碱基），这是 P0 回归固定项。

## 科学边界汇总

本章 16 个脚本中，`simulate_cloning.py --method digest-ligate`、`simulate_advanced.py` 全部方法、`golden_gate.py`、`methylation.py` 输出 `experimental: true`；`simulate_cloning.py --method gibson` 与序列编辑/分析脚本不输出 `experimental`，但所有序列产物仍应视为计算预测。共性限制如下：

| 限制 | 影响脚本 | 说明 |
|---|---|---|
| 不模拟酶学/反应动力学 | 全部克隆模拟 | 外切酶/连接酶/重组酶/拓扑异构酶效率、温度循环、缓冲液、末端磷酸化均不建模 |
| feature 迁移策略不同 | `simulate_cloning.py`、`simulate_advanced.py`、`design_gene_replacement.py`、`mutagenesis.py`、`golden_gate.py` | Gibson/In-Fusion/Gateway/digest-ligate 走 feature 迁移；Golden Gate 与 mutagenesis 不迁移 feature |
| 拓扑保守 | `sg_common.topology` | 只有显式 `topology=circular` 才环状；裸序列/FASTA 默认线性 |
| 环状跨 origin | `restriction_hits` | 识别位点可跨 origin；但 `methylation.py` 跳过跨 origin hit，Gateway 不接受跨 origin att 区间 |
| 序列长度上限 | `align_seq.py`、`msa.py` | O(nm) 动态规划，长序列内存随乘积增长 |
| 读框假定 | `mutagenesis.delete_codon` | 假定阅读框从位置 1 开始，不读取 CDS feature |
| 密码子表 | `codon_optimize.py`、`analyze_seq.py` | 标准遗传密码表；不处理线粒体/替代密码表 |
| ORF 阈值 | `annotate.py` | 默认 `min-orf 300`，不预测内含子基因 |

## 本章覆盖脚本清单

| # | 脚本 | 主要函数/类 | 本章小节 |
|---|---|---|---|
| 1 | `scripts/assembly_model.py` | `FragmentEnd`、`AssemblyFragment`、`check_gibson_overlaps`、`join_by_homology`、`compatible_sticky`、`check_sticky_junctions`、`validate_origins` | assembly_model |
| 2 | `scripts/simulate_cloning.py` | `gibson`、`_shift_features`、`_hit_end_sequences`、`_vector_fragment`、`_restriction_insert_fragment`、`digest_ligate` | simulate_cloning |
| 3 | `scripts/simulate_advanced.py` | `infusion`、`_ta_topo_fragments`、`ta_topo_clone`、`_strict_att_pair`、`gateway_bp`、`gateway_lr` | simulate_advanced |
| 4 | `scripts/golden_gate.py` | `part_fragment`、`assemble` | golden_gate |
| 5 | `scripts/mutagenesis.py` | `mutate_point`、`insert_codon`、`delete_codon`、`overlap_pcr` | mutagenesis |
| 6 | `scripts/codon_optimize.py` | `detect_mode`、`optimize_aa`、`recode_dna` | codon_optimize |
| 7 | `scripts/protein_tools.py` | `reverse_translate`、`anneal` | protein_tools |
| 8 | `scripts/design_gene_replacement.py` | `find_target`、`design_replacement` | design_gene_replacement |
| 9 | `scripts/find_sites.py` | `enzyme_info`、`digest_report` | find_sites |
| 10 | `scripts/analyze_seq.py` | `tm_estimate`、`cmd_stats`、`cmd_revcomp`、`cmd_translate` | analyze_seq |
| 11 | `scripts/align_seq.py` | `global_align`、`local_align`、`_stats` | align_seq |
| 12 | `scripts/align_sanger.py` | `load_reads`、`align_read_to_ref`、`_complement_spans` | align_sanger |
| 13 | `scripts/msa.py` | `_align_profile`、`_rebase`、`msa` | msa |
| 14 | `scripts/assemble_contig.py` | `best_overlap`、`assemble` | assemble_contig |
| 15 | `scripts/methylation.py` | `find_motif`、`site_overlaps_motif` | methylation |
| 16 | `scripts/annotate.py` | `find_orfs` | annotate |

## 关键测试清单

| 测试文件 | 关键测试/检查 | 覆盖脚本 |
|---|---|---|
| `scripts/smoke_core.py` | `find_sites EcoRI recognition start == 2`、`top cut before base 3`、`circular EcoRI site starts at 10 and wraps origin`、`gibson overlap mismatch raises`、`annotate EcoRI found`、`reverse ORF translates to MK*`、`golden_gate junctions reported`、`golden_gate uses 0-based cut boundaries 7/11`、`golden_gate aborts on overhang mismatch`、`methylation does not invent dam/dcm sensitivity`、`align_seq detects 1 mismatch`、`align_sanger confirms read`、`mutagenesis point mutation`、`codon_optimize back-translate`、`protein_tools reverse-translate` 等 | find_sites, analyze_seq, simulate_cloning, simulate_advanced, golden_gate, methylation, align_seq, align_sanger, mutagenesis, codon_optimize, protein_tools, annotate |
| `scripts/smoke_academic.py` | 同上（学术 fixture 版） | 同上 |
| `tests/test_smoke.py` | `test_smoke_core_passes` | 运行 smoke_core 的 unittest 包装 |
| `tests/test_smoke_academic.py` | 运行 smoke_academic | 学术 fixture 包装 |
| `tests/test_v03.py` | `test_type_iis_forward_and_reverse_boundaries`、`test_json_envelope_strict_v05_shape` | sg_common, find_sites |
| `tests/test_v04.py` | `test_gibson_mismatch_is_structured_failure_and_writes_nothing`、`test_infusion_mismatch_is_structured_failure`、`test_linear_gibson_origins_and_feature_coordinates`、`test_circular_gibson_feature_maps_across_closing_overlap`、`test_bp_matches_committed_pENTR_EmGFP_fixture`、`test_lr_matches_committed_pDEST_EmGFP_fixture`、`test_gateway_requires_explicit_topology`、`test_ta_matches_committed_pGEM_T_fixture_with_explicit_premises`、`test_ecori_psti_smai_end_kinds_and_linear_vector_fragment` | simulate_cloning, simulate_advanced, assembly_model |
| `tests/test_v05.py` | `test_positive_strand_partial_wrap_preserves_order_and_extract`、`test_negative_strand_partial_wrap_preserves_order_and_extract`、`test_compound_join_and_order_operators_are_preserved`、`test_cross_origin_cds_keeps_extract_translation_and_qualifiers`、`test_three_fragment_circular_gibson_and_middle_feature`、`test_circular_origins_reconstruct_full_sources`、`test_feature_migration_mismatch_is_structured_failure_without_product` | simulate_cloning, simulate_advanced, assembly_model |
| `tests/test_v06.py` | `test_circular_zero_contribution_fails_with_stable_error`、`test_linear_zero_contribution_fails`、`test_feature_beyond_clip_end_is_not_migrated`、`test_feature_crossing_clip_end_fails_or_is_dropped_explicitly`、`test_100_seeded_successful_assemblies_preserve_invariants`、`test_seeded_zero_contribution_failures_are_stable` | assembly_model, simulate_cloning |
| `tests/test_gate_targets.py` | `CloningCliTests`（`test_gibson_cli_success_writes_product`、`test_digest_ligate_cli`）、`AdvancedCliTests`（`test_infusion_cli`、`test_ta_cli`、`test_gateway_cli`）、`GoldenGateCliTests`（`test_cli_success_with_reverse_insert`、`test_cli_failures`）、`V06FeatureTests`（`test_design_gene_replacement_core`、`test_design_gene_replacement_qc_risks_and_region`、`test_design_gene_replacement_cli`） | simulate_cloning, simulate_advanced, golden_gate, design_gene_replacement |
| `tests/test_coverage_gap.py` | `AssemblyModelGapTests::test_end_validation_errors`、`::test_product_shorter_than_overlap`、`::test_check_gibson_overlaps_errors`、`::test_validate_origins_all_branches`、`::test_compatible_sticky_branches`、`::test_check_sticky_junctions_empty`；`CloningGapTests::test_merge_parts_empty_and_single`、`::test_shift_features_defaults_and_simple_location`、`::test_digest_ligate_psti_three_prime_overhang`、`::test_sticky_end_mismatch_guard`；`AdvancedGapTests::test_ta_sticky_mismatch_guard`、`::test_gateway_feature_migration_compound`、`::test_cli_missing_args_and_human_output`；`GoldenGateGapTests::test_arc_and_contains_recognition`、`::test_part_fragment_wrap_rejection`、`::test_overhang_length_mismatch_guard`、`::test_reverse_insert_cli_success`；`ValidateConstructGapTests::test_codon_start_and_transl_table_fallbacks` | assembly_model, simulate_cloning, simulate_advanced, golden_gate, validate_construct, codon_optimize 相关 |
| `tests/test_e2e_scenarios.py` | `test_backbone_plus_goi_full_chain`、`test_entry_to_destination_lr`、`test_four_fragment_golden_gate` | 端到端场景 |


## generate_design_report.py：统一设计报告（JSON + 自包含 HTML）

**技术原理**

`generate_design_report.py` 是 v0.6 引入的“设计交付物聚合器”，它不产生任何生物学计算，只把流水线已经生成的 JSON、GenBank/FASTA/DNA 产物与 SnapGene 兼容性报告聚合为一个可读交付物。

- 输入四类文件：`--design-json`（`design_gene_replacement.py` 或任意 dict 风格设计 JSON）、`--assembly-json`（`simulate_cloning.py` / `simulate_advanced.py` / `golden_gate.py` 的 `--json` 输出）、`--product`（GenBank/FASTA/.dna 产物）、`--compatibility-json`（`snapgene_compatibility.py` 或 delivery bundle 的兼容性报告）。
- 输出：`--out` 自包含 HTML（inline CSS、无外部资产）；`--report-json` 机器可读聚合 JSON。

核心函数：

| 函数 | 行号 | 作用 |
|---|---|---|
| `_read_json(path)` | 44-50 | 读取 JSON；若为 v0.5 信封 `{"data": {...}}` 则取 `data`，否则原样返回 |
| `_product_section(path)` | 53-62 | 用 `sg_common.load_seq` 读产物，输出 name/length/topology/sequence/features |
| `build_report(...)` | 65-166 | 聚合设计 JSON 的 primers/risks/notes，组装 JSON 的 method/experimental/junctions/warnings，产物 CDS 信息，兼容性 findings |
| `render_html(report)` | 169-290 | 渲染 Summary/Primers/Assemblies/Products/QC/Risks/SnapGene compatibility/Notes |
| `main(argv=None)` | 293-333 | CLI：至少一类输入，否则退出；写出 HTML 与 JSON；`--json` 时用 `jprint` 输出结果信封 |

**生物原理与来源**

报告本身不是湿实验证据；它把各步骤的输出原样保留并标注来源文件，使开发者/审阅者能追溯“某个引物序列来自哪个设计 JSON、某个 assembly warning 来自哪个模拟器”。这与实验记录规范一致：交付物必须可追溯，不能只给最终序列（Sambrook & Russell《Molecular Cloning》）。

**实现路径**

```
main
  -> build_report(title, design_jsons, assembly_jsons, products, compatibility_jsons)
       -> _read_json / _product_section
       -> 收集 primers/assemblies/qc/risks/notes/compatibility/sections
  -> render_html(report) -> --out HTML
  -> json.dump(report)   -> --report-json
  -> jprint(html_report, report_json, summary) 当 --json
```

**科学性说明、边界与验证**

- 边界：只聚合，不校验输入文件的相互一致性；不会重算 Tm、不会重做组装。若上游 JSON 被篡改或字段缺省，报告原样呈现（`data.get(..., "")` 容错），因此 HTML 中字段缺失不等于上游失败。
- HTML 是自包含的，不依赖网络；序列字段以等宽字体完整显示，适合本地审阅。
- 验证：`tests/test_v08_dev3.py::ReportAndOutputFormatTests::test_output_formats_sequence_identical` 只覆盖关联的产物格式一致性；`generate_design_report` 的直接聚合路径由 `tests/test_v08_gate_coverage.py::ReportGapTests::test_make_report_direct` 与 `test_main_direct_success_and_failure` 覆盖。

# 第 4 章：v0.9 组装规划、可行性规则、元件库、在线来源与知情权

本章覆盖 v0.9 发布迭代中的组装规划链（M1）、可行性规则引擎（M2）、结构化元件库（M5）、在线权威来源适配器（M6），以及贯穿这些模块的知情同意与来源追踪基础设施。必须覆盖的文件为：

| 分组 | 文件 | 职责 |
|---|---|---|
| CLI 入口 | `scripts/plan_assembly.py` | M1 多来源组装规划命令行入口，产出计划 JSON/Markdown/HTML 与最终构建体文件 |
| 规划核心 | `planning/intent.py` | 结构化组装意图（JSON 契约 + 确定性 key=value/中文子集解析） |
| 规划核心 | `planning/planner.py` | 多来源组装规划器：片段提取、overlap 选择、方法自动切换、引物与可行性集成 |
| 规划渲染 | `planning/manual_render.py` | 将计划 JSON 渲染为人类可读 Markdown/HTML 构建手册 |
| 可行性规则 | `rules/engine.py` | M2 结构化规则求值引擎，支持 `user_rules/` 覆盖 |
| 可行性规则 | `rules/feasibility_rules.json` | 内置 10 条可行性规则（阈值 + 来源 + 建议） |
| 用户规则 | `user_rules/README.md` | 用户自定义规则的放置与覆盖约定说明 |
| 契约 Schema | `schemas/assembly-plan-v0.9.json` | 组装计划 JSON Schema（Draft 2020-12） |
| 元件库 | `scripts/parts_library.py` | M5 结构化元件库查询（`parts/parts_library.json`） |
| 在线来源 | `scripts/online_sources.py` | M6 NCBI/Addgene/BLAST/CRISPOR 适配器，离线显式降级 |
| 序列上传同意 | `scripts/sequence_upload_consent.py` | 每次上传一票一授权的绑定状态机 |
| 操作同意 | `scripts/operation_consent.py` | 操作级同意代理与透明日志（Iron rule 4） |
| 来源追踪 | `scripts/provenance.py` | 结构化 source 对象、校验、版本单一来源 |
| 协议证据 | `scripts/protocol_evidence.py` | 从 `references/protocol-evidence-dev2.json` 加载协议证据 |
| 协议推荐 | `scripts/recommend_protocol.py` | 特征驱动、来源门控的协议推荐 |
| 反应刻画 | `scripts/characterize_reaction.py` | PCR 片段客观反应特征表，不推荐试剂 |
| 参数来源 | `references/biological-parameters-sources.json`、`references/biological-parameters-sources.md` | 默认生物学参数单一来源索引（P01-P30） |
| 政策文件 | `references/source-policy.md`、`references/privacy-and-consent.md`、`references/protocol-recommendation.md`、`references/protocol-evidence-dev2.json` | 来源优先级、隐私与同意、协议推荐规则、已加载协议证据 |

所有路径相对仓库根 `D:/codex_project/snapgene-dna-design-v0.9.0-work`。坐标约定与全仓库一致：CLI 参数与兼容字段使用 1-based 闭区间；`planning/planner.py` 内部 `fragment_assignments` 同时给出 `source_interval_0based`（0-based 半开）与 `source_interval_1based`（1-based 闭区间）；`sg_common.restriction_hits` 输出识别序列起点与双链切口 0-based 边界（`scripts/sg_common.py:258-300`）。拓扑默认线性，只有显式标注 `circular` 才按环状处理（`scripts/sg_common.py:198-206`）。

**引用来源**：本章引用 Sambrook & Russell《Molecular Cloning: A Laboratory Manual》（CSHL Press）；Gibson et al. 2009 *Nat Methods* 6:343-345（DOI 10.1038/nmeth.1318）；Engler et al. 2008 *PLoS One* 3:e3647（DOI 10.1371/journal.pone.0003647）；NEB/Takara/IDT 官方协议与 FAQ；Primer3 官方手册（https://primer3.org/manual.html）；Doench et al. 2016 *Nat Biotechnol* 34:184-191（DOI 10.1038/nbt.3437）；Kim et al. 2018 *Nat Biotechnol* 36:239-241（DOI 10.1038/nbt.4061）；Cas-OFFinder GitHub（https://github.com/snugel/cas-offinder）；BioPython/Bio.Restriction 文档。以上引用均已在 `references/biological-parameters-sources.md`、`references/biological-parameters-sources.json` 或 `rules/feasibility_rules.json` 中登记，本章沿用仓库既有 DOI/URL，不新增 DOI/URL。

**数据流主线**：`plan_assembly.main` → `planning.intent.normalize_intent`（或 `parse_intent_text`）→ `planning.planner.plan_assembly`（内部：`sg_common.load_seq` → `_extract_region` → `choose_overlap` → `primer_design_engine.design_region_primers` → `rules.engine.evaluate_plan` → `validation_crosscheck.overlap_crosscheck`/`restriction_site_crosscheck`）→ `planning.manual_render.render_markdown/render_html` → `_write_construct_files`。所有输出 JSON 携带 `provenance` 与 `consent`/`operation_log` 字段；在线来源在离线或未授权时返回 `offline-unverified`、`refused-consent-required` 或 `denied`，绝不静默伪造序列或跳过同意。

---

## scripts/plan_assembly.py：M1 组装规划 CLI 入口

### 技术原理

`scripts/plan_assembly.py` 是 M1 组装规划的用户可执行入口，代码总量 160 行。模块顶部把仓库根加入 `sys.path`（`scripts/plan_assembly.py:8-9`），随后从 `sg_common`、`planning.intent`、`planning.planner`、`planning.manual_render` 与 `operation_consent` 导入公共函数（`scripts/plan_assembly.py:11-15`）。

CLI 参数结构（`main()`，`scripts/plan_assembly.py:30-48`）：

| 参数 | 行号 | 说明 |
|---|---|---|
| `sources`（位置参数，nargs="+"） | 32 | 一个或多个 `.gb`/`.dna`/`.fa`/裸序列来源 |
| `--intent-json` | 33 | 结构化组装意图 JSON 文件路径 |
| `--intent-text` | 34 | 确定性 `key=value;...` 文本意图 |
| `--primer3-core` | 35 | 显式传入 primer3_core 可执行文件路径 |
| `--out-json` / `--out-markdown` / `--out-html` | 36-38 | 计划输出路径 |
| `--out-construct` | 39 | 写出最终构建体（`.gb`/`.fa`/`.dna` 路径 stem） |
| `--json` | 40 | 成功时把计划打印为 JSON 信封 |
| `--consent {ask,auto}` | 41-44 | 默认 `ask`：无确认不执行 |
| `--yes` | 45-47 | 等价于 `--consent ask` + 全 yes 回调 |

意图来源必须二选一，否则抛 `ValueError("INTENT_REQUIRED: ...")`（`scripts/plan_assembly.py:50-57`）。同意策略有三种形态：`--consent auto` 构造 `ConsentBroker(policy="auto")`（自动确认并记录）；`--yes` 构造 `policy="ask"` 且 `confirm_callback=lambda request: True`；默认构造 `policy="ask"` 且回调为 `_interactive_confirm`（`scripts/plan_assembly.py:58-65`）。`_interactive_confirm(request)`（`scripts/plan_assembly.py:18-27`）打印操作、类别、说明与替代方案后读取 `[y/N]`；EOF 直接抛 `ConsentRequiredError`，确保管道自动化中不会误放行。

`plan_assembly.main` 的核心调用是：

```python
plan = plan_assembly(args.sources, intent, args.primer3_core,
                     consent_broker=broker)
```

（`scripts/plan_assembly.py:66-67`）。`plan_assembly` 返回 dict 后，`main` 调用 `_steps_list` 把 `steps` 挂到计划上（`scripts/plan_assembly.py:82`，`_steps_list` 见 154-156），读取 `plan["consent"]["pending"]`（`scripts/plan_assembly.py:83`），并用 `render_markdown` 生成构建手册（`scripts/plan_assembly.py:84`）。

写出阶段有显式知情同意门：每次写文件前先经 `_record_write(path)` 向 `operation_log` 追加 `write-file`/`external-write` 条目，标记 `approved: true` 与 `source: "explicit CLI output path"`（`scripts/plan_assembly.py:86-93`）。只有用户显式给出的输出路径才会被写；计划中的异常操作（`pending`）在 `--consent ask` 且非 `--yes` 时阻断最终构建体写出，返回码 1，防止把未确认的组装策略沉淀为可执行文件（`scripts/plan_assembly.py:106-111`）。

异常路径输出结构化失败信封：`{"schema_version":"0.9.0","status":"failed","reason":<错误码>,"detail":<完整消息>}`，错误码取 `str(error).split(":")[0]`（`scripts/plan_assembly.py:68-80`）。`reason` 因此是稳定机器可读的错误前缀，例如 `INTENT_REQUIRED`、`BACKBONE_SOURCE_OUT_OF_RANGE`。

`_write_construct_files(plan, stem)`（`scripts/plan_assembly.py:122-151`）负责最终构建体写出。它从 `plan["final_construct"]["sequence"]` 取序列，构造 `SeqRecord`（id/name 为 `construct_name`，`molecule_type="DNA"`，`topology=plan.get("topology","circular")`，见 131-134）；随后按 `fragment_assignments` 逐片段添加 `misc_feature`，qualifier 中包含 `label`、`note="role=... source=..."`（135-144）。写出前调用 `write_dna._ensure_annotations` 补注释（145），然后依次写出 `.gb`（GenBank）、`.fa`（FASTA）与原生 `.dna`（`write_dna.write_native_dna`，147-151）。

### 生物原理

组装规划 CLI 本身不直接处理分子生物学；它把用户给出的“哪个来源作骨架、哪些片段插入、用哪种组装方法”转成机器可执行的计划，并在计划通过可行性规则和同意门之后写出构建体。其生物学正确性依赖 `planning.planner.choose_overlap`（15-40 bp 同源臂窗口，IDT 指南与 Gibson 2009）与 `rules/engine.evaluate_plan`（片段数、长度、GC、Tm、二级结构阈值）保证。写出的 GenBank 注释用 `misc_feature` 记录片段来源与角色，便于下游追溯嵌合位点。

### 实现路径

调用链：`main` → `normalize_intent`/`parse_intent_text` → `ConsentBroker` → `plan_assembly` → `_steps_list`/`render_markdown`/`render_html` → `_write_construct_files`。失败路径不写任何产物，只写 `--out-json`（若指定）并打印失败信封。

### 科学性说明

适用边界：该脚本只做规划与文件写出，不执行湿实验，也不替代 `simulate_cloning.digest_ligate`/`golden_gate.assemble` 的产物序列计算。`plan["final_construct"]["sequence"]` 对 digest-ligate/Golden Gate 仅表示片段顺序拼接（`planning/planner.py` 中 `sequence_note` 明确说明，见 `planning/planner.py:472-478`），最终酶切连接产物必须用相应模拟脚本计算。已知限制：`--out-construct` 的 `.gb` 片段 feature 是简化标签，非完整的 feature 迁移。对应测试：`tests/test_v09.py::AdditionalV09CoverageTests::test_plan_assembly_main_direct`、`test_plan_assembly_cli`、`test_plan_schema_validation`；`tests/test_release_iteration.py::CliConsentGateTests::test_plan_assembly_ask_blocks_construct_write_until_confirmed`。

---

## planning/intent.py：结构化组装意图

### 技术原理

`planning/intent.py` 定义 AI 调用契约：`plan_assembly(..., intent=...)` 接受 JSON 对象；CLI 使用 `parse_intent_text` 解析确定性的 `key=value;...` 子集与少量中文回退。模块不发明无法解析的字段（`planning/intent.py:1-7`）。

`_coerce_interval(value)`（`planning/intent.py:11-23`）把区间统一为 `[start, end]` 双元素列表：列表/元组直接转 `int`；字符串支持 `"123-456"` 与 `"123:456"` 两种写法；解析失败返回 `None`。

`normalize_intent(intent)`（`planning/intent.py:26-48`）只接受 dict，否则抛 `ASSEMBLY_INTENT_MUST_BE_DICT`。归一化字段：

| 字段 | 默认值 | 约束 |
|---|---|---|
| `goal` | `"assembly-plan"` | 任意字符串 |
| `method` | `"auto"` | 必须是 `auto`、`overlap`、`gibson`、`golden_gate`、`digest-ligate` 之一，否则 `UNSUPPORTED_ASSEMBLY_METHOD` |
| `topology` | `"circular"` | 透传，最终由 planner 使用 |
| `backbone` | `{}` | 可含 `interval`、`name` |
| `fragments` | `[]` | 每个元素 dict 化，可含 `interval` |
| `fusion` | `None` | 融合读框检查规格 |
| `tag` | `None` | 标签意图 |
| `name` | `"assembled-construct"` | 构建体名 |

backbone 与每个 fragment 的 `interval` 都经过 `_coerce_interval` 规范化（39-44）。

`parse_intent_text(text)`（`planning/intent.py:51-107`）解析分号分隔的键值对；`；` 先替换为 `;`（56）。支持的键：`backbone`（source 编号）、`fragments`（逗号分隔 token，支持 `source:feature`、`source:start-end`、`source:start:end` 与纯 `source`）、`method`、`topology`、`name`、`goal`。中文回退分支识别“骨架/骨架质粒 + N 号”、“Gibson/gibson”、“Golden Gate/golden gate”、“overlap”（91-102）。缺少 `backbone` 抛 `INTENT_MISSING_BACKBONE_SOURCE`，缺少 `fragments` 抛 `INTENT_MISSING_FRAGMENTS`（103-106）。

### 生物原理

片段来源编号语义：`backbone=0` 表示第一个 `sources` 文件作骨架，`fragments=1:EGFP` 表示第二个文件中名为 EGFP 的 feature 作插入片段。该契约把“从 GenBank feature 或区间提取生物学片段”与后续组装策略分离，使得反向链 feature 提取、跨原点 feature 提取等问题集中在 planner 的 `_extract_region` 中处理，而意图层保持纯粹。

### 实现路径

`plan_assembly.main` 在有 `--intent-json` 时读文件并 `json.loads` 后直接 `normalize_intent`；在有 `--intent-text` 时走 `parse_intent_text`，后者内部最终仍调用 `normalize_intent`（`planning/intent.py:107`）。

### 科学性说明

适用边界：`parse_intent_text` 是确定性 CLI 解析器，不是自然语言理解器；中文回退只识别有限模式，不能替代结构化意图。未知键被忽略，不报错；这可能导致拼写错误静默变为默认值，因此生产调用建议直接传 JSON 意图。对应测试：`tests/test_v09.py::M1PlannerTests::test_intent_text_parser`、`AdditionalV09CoverageTests::test_intent_parser_branches`；`tests/test_destructive_inputs.py::PlannerDestructiveTests::test_bad_intent_text`。

---

## planning/planner.py：多来源组装规划器

### 技术原理

`planning/planner.py` 是 M1 的核心，547 行。顶部导入 `Bio.Seq`、`Bio.SeqUtils.MeltingTemp`（`planning/planner.py:12-13`）、`sg_common`（`load_seq`、`restriction_hits`、`get_enzyme`、`gc_percent`、`topology`，18-19）、`rules.engine.evaluate_plan`、`primer_design_engine.design_region_primers/restriction_tail`、`operation_consent` 与 `validation_crosscheck`（20-28）。

主要数据结构与函数：

| 符号 | 行号 | 说明 |
|---|---|---|
| `TYPE_IIS_CANDIDATES` | 32 | `("BsaI", "BsmBI", "Esp3I", "BbsI")` 候选 Type IIS 酶 |
| `PlannerError` | 35-36 | 规划器业务异常 |
| `_record_summary(record, path, index)` | 39-54 | 来源文件摘要（id、长度、拓扑、feature 列表） |
| `_feature_sequence(record, feature)` | 57-58 | 用 `feature.extract` 提取 feature 序列 |
| `_find_feature(record, spec)` | 61-80 | 按 `label/gene/locus_tag/product/note` 或 `feature_type` 唯一匹配；多匹配时优先精确 label |
| `_extract_region(record, spec, source_index)` | 86-105 | 区间提取（0-based 边界检查）或 feature 提取（`feature.extract` 自动处理反向链与复合位置） |
| `_enzyme_site(enzyme_name)` | 108-110 | `get_enzyme` 后取 `enzyme.site` |
| `_find_type_iis_enzyme(fragments)` | 113-121 | 选第一个内部无位点的 Type IIS 酶 |
| `choose_overlap(upstream, downstream, target_gc=50.0)` | 123-150 | 在 15-40 bp 窗口内选择 GC 最接近 50% 的 overlap |
| `_check_fusion_frame(fragments, fusion_spec)` | 152-174 | 融合蛋白读框检查（mod 3） |
| `_decide_method(requested, fragments)` | 177-184 | `auto` 时按片段大小/数量选 overlap 或 gibson |
| `_golden_gate_site_counts(fragments, enzyme_name)` | 188-193 | 统计识别序列及其反向互补的出现次数 |
| `_primer_tails(method, fragments, index, junctions, enzymes)` | 195-213 | 按组装方法决定正/反向引物 5' 尾巴 |
| `plan_assembly(source_paths, intent, primer3_core=None, user_rules_dir=None, consent_broker=None, operation_log=None)` | 213-512 | 主规划函数 |
| `_method_reason(...)` | 515-527 | 生成方法选择理由 |
| `_feasibility_context(...)` | 530-546 | 把规划中间结果压平为规则引擎上下文 |

`_extract_region` 的边界条件：区间模式要求 `0 <= start < end <= len(seq)`，否则抛 `FRAGMENT_INTERVAL_OUT_OF_RANGE`（`planning/planner.py:91-94`）；feature 模式找不到且指定了 feature/name 时抛 `FEATURE_NOT_FOUND`（96-99）；未指定时返回整条序列。反向链 feature 使用 `feature.extract`，得到生物学的 5'→3' 片段（100-105），其正确性由 `test_reverse_strand_feature_extraction_is_biological` 锁定。

`choose_overlap` 的算法：对 `length=15..min(40,len(upstream))` 逐一取 `upstream[-length:]`，计算 GC 与 `mt.Tm_NN`；若存在 GC 30-70% 的候选，取 GC 距 50% 最近者；否则返回距 50% 最近候选并附 `overlap_gc_outside_30_70` 警告（`planning/planner.py:123-150`）。长度 <15 直接返回上游全序列并附 `overlap_shorter_than_15`。

`plan_assembly` 的执行顺序：

1. 归一化意图并准备同意代理与日志（213-222）。
2. `sg_common.load_seq` 加载所有来源，生成 `summaries`（223-229）。
3. 提取骨架：`backbone_spec["source"]` 越界抛 `BACKBONE_SOURCE_OUT_OF_RANGE`；`_extract_region` 提取骨架序列，角色固定 `backbone`（230-243）。
4. 逐个提取插入片段：`source` 越界抛 `FRAGMENT_SOURCE_OUT_OF_RANGE`；角色默认 `insert`（245-264）。
5. 方法决策与替代方案（265-330）：`golden_gate` 先 `_find_type_iis_enzyme` 选内部无位点的酶；每个片段过 `restriction_site_crosscheck` 平行验证，计数不一致或冲突则记录替代方案并回退 `gibson`。`digest-ligate` 默认 `["EcoRI","BamHI"]`（或 `intent["enzymes"]`），要求每种酶在每个片段中恰好出现一次，否则回退 `gibson`。
6. overlap junction 设计：`overlap`/`gibson` 且片段数 >1 时逐对调用 `choose_overlap`，再过 `overlap_crosscheck`（331-348）。
7. 规则初筛：构造 `_feasibility_context` 后 `evaluate_plan`；若用户指定 `overlap` 且命中 `overlap-fragment-count` 错误，自动切 `gibson` 并重算可行性（349-363）。
8. 引物设计：每个片段用 `_primer_tails` 计算尾巴，调用 `primer_design_engine.design_region_primers`（364-405）。异常被记录为 `{"fragment":..., "error":..., "error_type":...}`，不中止整个规划。
9. 引物 QC 汇总：统计 `primer_tm_outside_52_72` 与 `primer_strong_secondary_structure` 问题，回填 context 并再次 `evaluate_plan`（406-421）。
10. 融合读框检查：`_check_fusion_frame`；不在框则追加 `fusion-frame` 错误并降级 `low`（422-428）。
11. 产物序列与手工计划组装（429-509）：`final_sequence` 为片段顺序拼接；输出 `sources`、`fragment_assignments`、`assembly_strategy`、`primers`、`fusion_frame_check`、`feasibility`、`final_construct`、`numeric_evidence`、`provenance`、`consent`、`operation_log`。

`fragment_assignments` 同时输出 `source_interval_0based` 与 `source_interval_1based`（`planning/planner.py:441-447`）。`final_construct.sequence_note` 对 digest-ligate/Golden Gate 明确写“fragment-order concatenation only; cut/ligation product is computed by simulate_cloning.digest_ligate or golden_gate.assemble, not by the planner”（`planning/planner.py:472-478`）。

`numeric_evidence` 把数值依据与规则阈值显式写入计划（`planning/planner.py:466-489`）：overlap 窗口 15-40 bp、GC 30-70%，来源 IDT 与 Gibson 2009；primer Tm 52-72 °C 交叉验证，来源 Primer3 官方文档；限制酶位点交叉验证，来源 Bio.Restriction 与 `sg_common.restriction_hits`。

### 生物原理

**Overlap 选择**：Gibson 组装要求相邻片段共享 15-40 bp 末端同源区；过短则退火特异性不足，过长增加合成成本与二级结构风险（Gibson et al. 2009 DOI 10.1038/nmeth.1318；IDT 引物设计指南；仓库登记于 `references/biological-parameters-sources.json` P15-P16）。`choose_overlap` 用 `mt.Tm_NN` 计算最近邻热力学 Tm，并在 GC 超窗时返回警告而非硬失败，因为 overlap 长度窗口内不一定存在 30-70% GC 的候选。

**Golden Gate 与 Type IIS**：Type IIS 酶（如 BsaI）在识别序列外切割，产生的粘性末端不携带识别位点，因此识别序列必须不出现于任何片段内部，否则产物会内部切断或组装错误（Engler et al. 2008 DOI 10.1371/journal.pone.0003647；NEB Golden Gate 文档）。planner 的候选酶顺序 `BsaI/BsmBI/Esp3I/BbsI` 与规则 `golden-gate-internal-site` 一致。

**Digest-ligate**：经典限制酶切连接要求每种酶在每个片段中恰好切割一次，使末端互补且可连接（Sambrook & Russell《Molecular Cloning》）。planner 只验证位点数量；粘性末端兼容性与最终连接产物由 `simulate_cloning.digest_ligate` 负责（`planning/planner.py:457-464` 的 `digest_ligate_note`）。

**融合读框**：`_check_fusion_frame` 用调用方提供的 CDS 偏移计算 `(upstream_end + downstream_start) % 3` 与期望读框比较（`planning/planner.py:152-174`）。这是人工读框检查，注释明确提示最终决策前必须在最终构建体中翻译/验证 junction。

**引物尾巴**：overlap/Gibson 的正向引物尾巴是前一 junction 序列，反向引物尾巴是下一 junction 序列的反向互补（`planning/planner.py:195-207`）；Golden Gate 与 digest-ligate 使用 `primer_design_engine.restriction_tail` 生成 NEB 保护碱基 + 识别序列（`primer_design_engine.py:38-47`）。

### 实现路径

主调用链：`plan_assembly.main -> planning.planner.plan_assembly -> load_seq -> _extract_region -> choose_overlap -> validation_crosscheck.overlap_crosscheck -> rules.engine.evaluate_plan -> primer_design_engine.design_region_primers -> _check_fusion_frame -> 返回 dict`。其中 `evaluate_plan` 可因用户规则目录改变行为（`rules/engine.py:19-30`）。

### 科学性说明

适用边界：planner 输出的是“计划”，不是反应产物；对 Golden Gate/digest-ligate 的序列不做切割连接模拟。自动方法选择 `_decide_method` 是启发式（最大片段 ≤5000 bp 且 ≤3 段选 overlap，否则 gibson），不是实验证明的最优解。引物设计失败只记录错误不阻断计划，计划仍可被可行性规则标记为阻断或降级。已知限制：`choose_overlap` 只在固定窗口内选择，不预测末端二级结构与退火动力学；`_find_type_iis_enzyme` 只做字符串 motif 扫描，不做切口几何与 fidelity 模拟。对应测试：`tests/test_v09.py::M1PlannerTests::test_two_fragment_overlap_plan`、`test_four_fragment_overlap_auto_switch_gibson`、`test_golden_gate_internal_bsai_switches_enzyme`、`test_reverse_strand_feature_extraction_is_biological`、`AdditionalV09CoverageTests::test_planner_digest_ligate_falls_back_when_sites_nonunique`、`test_digest_ligate_rejects_two_sites_in_one_fragment`；`tests/test_bio_audit_regressions.py::AuditRegressionTests::test_fusion_frame_uses_addition_not_subtraction`、`test_circular_restriction_crosscheck_handles_wrap`。

---

## planning/manual_render.py：构建手册渲染

### 技术原理

`planning/manual_render.py` 把同一个计划 dict 结构性地渲染为 Markdown 或 HTML，保证内容一致性。`render_html(plan)`（`planning/manual_render.py:7-83`）与 `render_markdown(plan)`（86-169）都从 `plan` 的 `fragment_assignments`、`primers`、`feasibility`、`consent.pending`、`steps` 与 `assembly_strategy` 字段生成内容，不维护第二份文本。

`render_html` 是无依赖 HTML：`html.escape` 转义所有字段（14），片段表与引物表手工拼接（15-46），可行性条目与待确认项渲染为 `<ul>`（47-61），最终套用内联 CSS（63-83）。

`render_markdown` 的结构：标题 `# <construct_name> 构建手册`，随后 goal/status/topology；组装策略（method/requested/reason/enzymes）、overlap junctions、alternatives（91-110）；片段分配表用 0-based 与 1-based 两种区间表达（112-120）；引物清单含 Tm/GC/tail/backend（122-134）；可行性 grade 与 error/warning 条目（136-144）；待确认项（146-155）；逐步操作（157-161）；融合读框检查（163-168）。

`_default_steps(plan)`（172-191）在计划未提供 `steps` 时生成：解析来源 → 逐片段 PCR 扩增 → 按方法做 overlap/Gibson/Golden Gate/digest-ligate → 转化 → 挑克隆验证 junction。这是最小可用实验步骤模板，不包含具体温度与时间。

### 生物原理

构建手册把算法输出翻译为实验员可读步骤。步骤模板是工作流级别的，不发明试剂条件；具体温度/时间/缓冲液必须来自 `recommend_protocol.py` 匹配到的官方协议证据，而不是手册本身。

### 实现路径

`plan_assembly.main` 调用 `render_markdown(plan)` 与 `render_html(plan)`；`--out-markdown`/`--out-html` 写文件，未指定输出时默认打印 Markdown（`scripts/plan_assembly.py:99-105`、115-118）。

### 科学性说明

已知限制：`_default_steps` 是文字模板，不是可执行协议；不包含转化热激/电转条件、抗生素浓度、菌株等。对应测试：`tests/test_v09.py::AdditionalV09CoverageTests::test_html_render_matches_plan_data`、`test_manual_render`、`test_manual_render_rich_plan`。

---

## rules/engine.py：M2 可行性规则引擎

### 技术原理

`rules/engine.py` 是 M2 实验可行性规则引擎，88 行。`RULES_PATH` 指向 `rules/feasibility_rules.json`，`USER_RULES_DIR` 默认 `user_rules/`（`rules/engine.py:15-16`）。

`load_rules(user_rules_dir=None)`（`rules/engine.py:19-30`）先读内置规则；若用户规则目录存在，按文件名排序逐个读入 `*.json`，以 `rule["id"]` 为键覆盖或追加内置规则。输入 JSON 可以是 `{"rules":[...]}` 或直接 dict（25）。

`_check_rule(rule, context)`（`rules/engine.py:39-46`）以受限 `eval` 求值规则 `check` 表达式：`_ALLOWED_NAMES` 只含 `__builtins__`（空 dict）、`True/False/None`（33-36）；表达式包含 `any(` 或 `__` 直接返回 False；异常也返回 False。该沙箱策略由 `tests/test_destructive_inputs.py::RulesDestructiveTests::test_eval_is_sandboxed` 锁定。

`evaluate_plan(plan_context, user_rules_dir=None)`（`rules/engine.py:49-88`）遍历规则，命中的规则生成 `{rule_id, constraint, severity, suggestion, source, source_id}`（60-67）；`error` 聚合为 errors，`warn` 聚合为 warnings；grade 规则：有 error 为 `low`，只有 warn 为 `medium`，无命中为 `high`（68-75）。返回结构还包含 `schema_version`、`rules_evaluated` 与 `provenance`（76-87）。

规则上下文是 planner 生成的扁平 dict，键包括 `method`、`fragment_count`、`internal_site_count`、`min_overlap_length`、`max_overlap_length`、`min_overlap_gc`、`max_overlap_gc`、`max_fragment_length`、`total_length`、`any_primer_tm_outside_52_72`、`any_primer_strong_structure`（`planning/planner.py:530-546`）。

### 生物原理

规则引擎本身不做生物学判断，生物学阈值在 `rules/feasibility_rules.json` 中逐条登记来源。规则覆盖：overlap 片段数 >3（Gibson 2009 建议 4-5 段以上用 Gibson）；Gibson 片段数 >5 警告（Gibson 2009）；Golden Gate 片段数 >8 警告（Engler 2008）；Golden Gate 内部 Type IIS 位点阻断（Engler 2008 + NEB Golden Gate）；overlap 长度 15-40 bp（IDT + Gibson 2009）；overlap GC 30-70%（IDT）；PCR 片段 >10 kb（NEB Q5 / Takara PrimeSTAR GXL）；总构建体 >20 kb 提示电转化（Sambrook & Russell《Molecular Cloning》）；引物 Tm 52-72 °C 与强二级结构（Primer3 官方文档）。

### 实现路径

`planning.planner.plan_assembly` 在引物设计前后两次调用 `evaluate_plan`；先做方法/长度/GC 规则，再补充引物 Tm/结构规则。用户规则目录由 `plan_assembly(..., user_rules_dir=...)` 透传；CLI 未暴露该参数。

### 科学性说明

已知限制：`eval` 沙箱仅限制名字空间与表达式特征，仍应在受信规则文件下运行；`_check_rule` 异常静默返回 False，意味着规则表达式写错会“不命中”而非报错，调试时应检查 `rules_evaluated`。规则命中只输出结构化提示，不直接修改计划；自动切换方法由 planner 读取 errors 后执行。对应测试：`tests/test_v09.py::M2RuleTests::test_builtin_rules_load_with_sources`、`test_overlap_4_fragments_is_error`、`test_user_rules_override`；`tests/test_destructive_inputs.py::RulesDestructiveTests::test_eval_is_sandboxed`。

---

## rules/feasibility_rules.json：内置可行性规则

### 技术原理

`rules/feasibility_rules.json` 共 10 条规则，每条含 `id`、`constraint`、`check`、`severity`、`suggestion`、`source`。规则求值表达式只能引用 `rules/engine.py` 约定的扁平上下文键。

| rule_id | severity | check（行号） | 来源 |
|---|---|---|---|
| `overlap-fragment-count` | error | `method == 'overlap' and fragment_count > 3`（7） | Gibson 2009; IDT |
| `gibson-fragment-count` | warn | `method == 'gibson' and fragment_count > 5`（15） | Gibson 2009; Engler 2008 |
| `golden-gate-fragment-count` | warn | `method == 'golden_gate' and fragment_count > 8`（23） | Engler 2008 |
| `golden-gate-internal-site` | error | `method == 'golden_gate' and internal_site_count > 0`（31） | Engler 2008; NEB Golden Gate |
| `overlap-length` | warn | `method in ('overlap','gibson') and (min_overlap_length < 15 or max_overlap_length > 40)`（39） | IDT; Gibson 2009 |
| `overlap-gc` | warn | `method in ('overlap','gibson') and (min_overlap_gc < 30 or max_overlap_gc > 70)`（47） | IDT |
| `pcr-length` | warn | `max_fragment_length > 10000`（55） | NEB Q5; Takara PrimeSTAR GXL |
| `construct-size` | warn | `total_length > 20000`（63） | Sambrook, Molecular Cloning; 实验室共识 |
| `primer-tm` | error | `any_primer_tm_outside_52_72`（71） | SnapGene DNA Design 内部窗口 52-72 °C |
| `primer-structure` | error | `any_primer_strong_structure`（79） | Primer3 官方文档; IDT OligoAnalyzer |

### 生物原理

规则阈值全部来自登记来源：`overlap-fragment-count` 阻断 4 段以上的 overlap 组装，因为多片段 overlap 退火复杂、错误配对概率上升，Gibson 2009 方法更适合 4-5 段（DOI 10.1038/nmeth.1318）；`golden-gate-fragment-count` 警告 >8 段，因为 Engler 2008 展示的模块化 Golden Gate 在 ≤8 段效率较好（DOI 10.1371/journal.pone.0003647）；`golden-gate-internal-site` 是序列级硬约束（内部 Type IIS 位点会切断产物）；`primer-tm` 与 `primer-structure` 是引物可用性硬阻断，分别对应 Primer3 手册的 Tm 默认参数与发夹/二聚体阈值（https://primer3.org/manual.html）。

### 实现路径

`rules/engine.load_rules` 读入本文件；用户规则目录中同 `id` 条目覆盖内置条目。

### 科学性说明

适用边界：`construct-size` 与 `pcr-length` 是 warn 级提示，不阻断；`overlap-gc` 只约束 overlap 窗口 GC，不约束模板 GC（见规则建议“高 GC 区使用 M4 高 GC 策略”）。规则文件由 `tests/test_release_iteration.py::ParameterSourcesGateTests::test_parameter_source_file_covers_required_families` 间接核对参数来源覆盖，并由 `tests/test_v09.py::M2RuleTests` 逐条检查 source 非空与 severity 合法。

---

## user_rules/README.md：用户规则

### 技术原理

`user_rules/README.md` 是 11 行的用户规则使用说明。核心约定：在 `user_rules/` 目录放置 JSON 文件，schema 与 `rules/feasibility_rules.json` 相同；`rules/engine.load_rules` 在加载内置规则后按文件名排序读入，并以 `id` 覆盖内置规则（`rules/engine.py:19-30`）。用户可新增内置没有的 `id`，也可覆盖内置 `id` 改变 check/severity/suggestion。

### 生物原理

用户规则用于机构或实验室沉淀本地可行性约束（例如只允许 Golden Gate 的酶列表、更严格的片段长度上限）。规则带来源字段，因此本地规则也应写清依据，保持来源可追溯。

### 实现路径

`plan_assembly(..., user_rules_dir=...)` 把目录传给 `evaluate_plan`；CLI 默认使用 `user_rules/`。

### 科学性说明

已知限制：README 只描述约定，不包含示例 JSON；规则表达式失败静默不命中（见 `rules/engine.py` 科学性说明）。对应测试：`tests/test_v09.py::M2RuleTests::test_user_rules_override`。

---

## schemas/assembly-plan-v0.9.json：组装计划 JSON Schema

### 技术原理

`schema/assembly-plan-v0.9.json` 是 Draft 2020-12 JSON Schema（`$schema` 行 2），`$id` 为 `urn:snapgene-dna-design:schema:assembly-plan-v0.9`（行 3）。`additionalProperties: true`（行 6），只约束必需字段和关键类型。必需字段：`schema_version`（const `0.9.0`）、`goal`、`construct_name`、`status`（enum `complete`/`blocked`）、`sources`、`fragment_assignments`、`assembly_strategy`、`primers`、`feasibility`、`final_construct`、`provenance`（行 7-9）。

关键子约束：

| 字段 | 约束 | 行号 |
|---|---|---|
| `fragment_assignments` | 数组 `minItems:1`，元素必须含 `name/role/source_index/source_interval_0based/length/sequence` | 16-19 |
| `assembly_strategy` | 必须含 `method/reason/alternatives` | 20-21 |
| `feasibility` | 必须含 `grade/errors/warnings` | 23-24 |
| `final_construct` | 必须含 `length/sequence/gc_percent` | 25-26 |
| `provenance` | 数组 `minItems:1` | 27 |

### 生物原理

Schema 把“计划完成/阻断”的机器可判定状态固定为 `status: complete|blocked`，并把来源、片段分配、可行性、最终序列与 provenance 设为必需，确保下游消费者不会拿到缺少溯源或缺少序列的计划。

### 实现路径

`planning.planner.plan_assembly` 返回的 dict 即符合该 schema；测试用 `jsonschema.Draft202012Validator` 做全量验证（`tests/test_v09.py::AdditionalV09CoverageTests::test_plan_schema_validation`）。

### 科学性说明

`additionalProperties: true` 允许计划携带 `consent`、`operation_log`、`numeric_evidence` 等附加字段，但也不拒绝未来新增字段；消费者不应假设未声明字段一定存在。对应测试：`tests/test_v09.py::AdditionalV09CoverageTests::test_plan_schema_validation`。

---

## scripts/parts_library.py：M5 元件库查询

### 技术原理

`scripts/parts_library.py` 是 M5 结构化元件库查询，50 行。`PARTS_PATH = ROOT / "parts" / "parts_library.json"`（`scripts/parts_library.py:9`）。`load_parts(path=None)`（12-15）读 JSON 并返回 `data["parts"]` 列表。`find_parts(name=None, part_type=None, path=None)`（18-27）做大小写不敏感的子串匹配：`name` 匹配 `part["name"]`，`part_type` 匹配 `part["type"]`；两者可组合（AND）。`main`（30-46）解析 `--name`/`--type`/`--json`，输出 `{"schema_version":"0.9.0","parts":[...],"count":N}` 或人类可读行。

`parts/parts_library.json` 当前包含 15 条记录：`pET-28a(+)`、`pUC19`、`pDONR201`、`pX330`（backbone）；`T7 promoter`、`CMV promoter`、`U6 promoter`（promoter）；`6xHis`、`HA`、`FLAG`（tag）；`AmpR`、`KanR`（resistance）；`pMB1 ori`、`pBR322 ori`（origin）。每条记录含 `name/type/source/accession/sequence/features/notes`；`sequence` 为 `null` 时表示“仅来源索引”，注释明确要求下载权威序列后再使用（例如 pET-28a(+) 的 `notes`）。

### 生物原理

元件库不是序列库。生物安全与正确性的关键设计是：只有短共识元件（T7 启动子、6xHis、HA、FLAG）内嵌序列，质粒骨架与抗生素抗性基因只有来源索引（GenBank accession、Addgene ID、Novagen 货号）。这避免在未核对权威序列的情况下把可能错误的骨架序列用于组装。

### 实现路径

`find_parts -> load_parts -> parts_library.json`；CLI `parts_library.py --type tag` 打印匹配元件。

### 科学性说明

已知限制：`find_parts` 是简单子串匹配，无模糊搜索，无序列分发；`sequence: null` 的元件不能直接用于 `plan_assembly`，必须先取得权威文件。对应测试：`tests/test_v09.py::M5PartsTests::test_lookup`、`AdditionalV09CoverageTests::test_parts_cli`。

---

## scripts/online_sources.py：M6 在线来源适配器

### 技术原理

`scripts/online_sources.py` 是 M6 在线权威来源适配器，213 行。常量：`NCBI_EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"`、`ADDGENE_BASE = "https://www.addgene.org"`、`CRISPOR_URL = "https://crispor.org"`（17-19）。`_get(url, timeout=20)`（22-26）用 `urllib.request` 发 GET，UA 为 `snapgene-dna-design/0.9`。

**序列判定与哈希**：`_normalize_sequence(text)`（29-30）去除空白并大写；`_looks_like_sequence(term)`（33-44）是保守启发式：长度 ≥4 且 IUPAC 核苷酸字符（`ACGTRYSWKMBDHVNU`）占比 ≥0.75 判定为原始序列；`_sequence_sha256(sequence)`（47-49）返回规范化后序列的大写 SHA-256。注意 `ncbi_blast_hint` 可以输出 SHA-256 前 16 位作审计，但 `_looks_like_sequence` 只用于拒绝裸序列查询。

**NCBI eUtils**：`ncbi_search(term, database="nucleotide", retmax=5, timeout=20)`（52-95）先拒绝 `_looks_like_sequence(term)` 的输入，返回 `refused-consent-required` 且只含 `term_sha256`（58-65）；通过 `esearch.fcgi` 取 idlist，再用 `esummary.fcgi` 取 summary，映射为 `{id, accession, title, organism, url}`（66-91）；任何 `URLError/TimeoutError/OSError/ValueError` 返回 `offline-unverified`（93-95）。`fetch_genbank(accession, timeout=30)`（98-110）用 `efetch.fcgi` 拉 `gbwithparts` 文本，失败返回 `offline-unverified`，绝不伪造 GenBank 文本。

**Addgene**：`addgene_lookup(addgene_id)`（113-127）只返回官方页面链接 `https://www.addgene.org/<id>/`，并显式标注 `adapter_kind="official-page-link-helper"`、`status="offline-unverified"`，说明未实现记录查询与序列验证。

**BLAST 隐私安全**：`ncbi_blast_hint(sequence=None)`（133-149）返回裸官方 BLAST URL（`https://blast.ncbi.nlm.nih.gov/Blast.cgi?PROGRAM=blastn&PAGE_TYPE=BlastSearch`），`contains_sequence_in_url=False`；可附 SHA-256 前 16 位但绝不含原始序列。`ncbi_blast_consent_request(sequence, purpose, scope, retention_notice=True)`（154-166）构造 `SequenceUploadConsent(scope)` 并 `request(BLAST_URL, purpose, sequence=..., retention_notice=...)`，返回 consent 对象与请求摘要（destination/purpose/scope/SHA-256/前 16 位/`contains_sequence:False`）。`authorized_blast_url(consent, sequence, purpose, scope)`（173-193）只有在 `consent.allowed(...)` 对完整四元组返回 True 时才把序列放入 URL，且当前只放前 100 nt（NCBI URL 实际限制），更长序列需 credentialed BLAST client 或文件上传，当前未实现。

**CRISPOR**：`request_crispor_query(target_sequence, organism, purpose, scope, retention_notice=True)`（199-202）只构造同意请求，不触网；真正的上传由调用方在获得授权后执行。

### 生物原理

NCBI GenBank 是序列验证的权威一级来源；Addgene 是质粒实物与序列的权威分发方；CRISPOR 是 gRNA 设计在线工具。把裸序列提交给 NCBI BLAST 或 CRISPOR 意味着序列离开本地，因此代码将“查询关键词/accession”与“上传序列”分成不同通道：关键词查询可匿名进行，序列提交必须绑定同意。该设计落实 `references/privacy-and-consent.md` 的“默认不上传”与“每次上传显式同意”。

### 实现路径

`ncbi_search`：`_looks_like_sequence` 守卫 → `esearch.fcgi` → `esummary.fcgi` → records。`authorized_blast_url`：`SequenceUploadConsent.allowed` 逐项比较 destination/purpose/sequence SHA-256/scope，通过才拼 URL。

### 科学性说明

适用边界：`ncbi_search` 返回的 `verified-online` 只说明“此时在线查询成功”，不保证记录内容正确；`addgene_lookup` 不验证序列；`authorized_blast_url` 有 100 nt URL 限制。已知限制：未实现 credentialed BLAST client、未实现 Addgene API 查询、未实现 CRISPOR 上传执行。对应测试：`tests/test_online_privacy.py::BlastPrivacyTests::test_unauthorized_hint_never_contains_sequence`、`test_consent_request_contains_hash_not_sequence`、`test_authorized_url_is_one_time_and_bound`、`test_unauthorized_url_is_never_built`、`test_ncbi_search_refuses_sequence_like_terms_without_network`、`test_short_keyword_still_allowed`；`tests/test_v09.py::AdditionalV09CoverageTests::test_online_sources_success_paths`、`M6OnlineSourceTests::test_offline_degrade_is_explicit`。

---

## scripts/sequence_upload_consent.py：序列上传同意状态机

### 技术原理

`scripts/sequence_upload_consent.py` 实现每次上传一票一授权的绑定状态机，147 行。默认状态 `consent=False`，即不上传（`sequence_upload_consent.py:2-9`、24-36）。`_normalize_sequence(value)`（16-18）与 `online_sources._normalize_sequence` 相同，保证哈希对象是“适配器实际提交的规范化字符串”。

`SequenceUploadConsent.__init__(self, sequence_scope="unknown")`（22-37）创建单一 `sequence_upload` 状态块，字段包括 `requested/consent/scope/sequence_sha256/destination/purpose/requested_at/approved_at/retention_notice_shown/receipt`。

`request(destination, purpose, sequence=None, retention_notice=True)`（39-57）绑定新上传请求：记录 destination/purpose/retention_notice，计算 `sequence_sha256`（`provenance.sha256_of_text(normalized)`），置 `requested=True`、`requested_at`，清空旧 consent/approved_at/receipt。新请求总是取代旧收据（42-44），旧批准不能复用于不同参数。

`approve()`（59-77）只在已有请求且 destination/purpose/sequence_sha256 齐全时签发收据：`receipt={destination, purpose, sequence_sha256, scope, approved_at, consumed:False}`。

`deny()`（79-84）清空同意与收据。

`peek_allowed()`（86-90）是非消耗检查：存在未消耗收据且 `consent=True` 才返回 True。

`allowed(destination=None, purpose=None, sequence=None, scope=None, consume=True)`（92-126）是绑定的、一次性的授权检查。任何参数缺失都是拒绝，不是“旧式授权 peek”（97-99）。实现细节：未 consent/无 receipt/已 consumed 均 False（102-106）；destination/purpose/sequence 为 None 或空白 False（107-109）；重算当前序列 SHA-256 后逐项比较 `destination/purpose/sequence_sha256/scope`（110-117）；任何不匹配调用 `deny()` 并返回 False（118-122）；匹配且 `consume=True` 时置 `receipt["consumed"]=True`、`consent=False`（123-126），保证一次授权只能使用一次。

`_default_retention_policy(destination)`（21-31）按目的地返回 `unverified` 声明：NCBI/BLAST 提示“查看 NCBI 现行隐私/安全政策”；CRISPOR 提示“官方手册仅说明过去两年未删除结果并试图保留至少一年，未确认固定期限”；其他服务提示查看当前留存政策。`request()` 可显式覆盖 `retention_policy`（59-70）。`consent_message(sequence_length=None, local_alternative="")`（155-165）生成中文提示，包含 destination、scope、长度、目的、`留存政策` 字段、本地替代方案与是否允许；不再把 CRISPOR 的未经确认期限写死，也不会把 CRISPOR 文案用于 NCBI BLAST。`to_json()`（168-171）序列化状态并移除可能存在的 `sequence` 键，确保序列不落盘。

### 生物原理

分子生物学数据（尤其临床相关序列、未发表质粒序列）上传至公共 BLAST/CRISPOR 可能带来隐私与知识产权风险。`references/privacy-and-consent.md` 规定：默认不上传；任何发送 DNA/RNA/gRNA/PCR/质粒序列到外部服务都需逐次显式同意；提示必须包含 destination、scope、purpose、留存政策与本地替代；完整序列与凭据不写日志。该状态机用“SHA-256 绑定收据 + 一次性消耗”把政策变成代码。

### 实现路径

`online_sources.ncbi_blast_consent_request` 与 `request_crispor_query` 创建 consent 并 `request`；调用方展示 `consent_message` 并 `approve`；上传前用 `allowed(...)` 做消费式授权。

### 科学性说明

已知限制：状态机不持久化，进程重启后收据丢失；`scope` 在 request 时绑定但 `allowed` 可显式传 scope，缺省用实例 scope；哈希绑定的是规范化大写无空白序列，调用方必须用同一规范化函数，否则误拒绝。对应测试：`tests/test_v08_dev3.py::ConsentBindingTests::test_ten_interception_scenarios`；`tests/test_v08_gate_coverage.py::ConsentGapTests::test_deny_and_message`、`test_approve_without_request`、`AdditionalCoverageTests::test_consent_consumed_branch`；`tests/test_online_privacy.py::BlastPrivacyTests::test_authorized_url_is_one_time_and_bound`。

---

## scripts/operation_consent.py：操作同意与透明日志

### 技术原理

`scripts/operation_consent.py` 把 Iron rule 4（用户知情权与操作透明）实现为代码行为，158 行。`ConsentRequiredError(RuntimeError)`（25-33）携带完整 request dict 并生成可读消息。`sha256_prefix(data, length=16)`（36-40）用于日志中的输入序列/参数摘要。`make_request(operation, category, description, parameters=None, alternatives=None, risk=None, source=None)`（43-56）构造带 `id="op-"+uuid4().hex[:12]`、时间戳的结构化请求。

`ConsentBroker`（59-129）是唯一结构化交互点。`__init__(policy="ask", confirm_callback=None, pre_approved=(), log=None)`（71-79）校验 policy ∈ {ask, auto}。`request(request)`（81-106）决策顺序：

1. `operation` 或 `category` 命中 `pre_approved` → 批准并记 `source="pre-approved"`；
2. 有 `confirm_callback` → 调回调，批准记录 `programmable-callback`，拒绝则 `_record` 后抛 `ConsentRequiredError`；
3. `policy=="auto"` → 批准并记 `auto-confirm`；
4. 否则抛 `ConsentRequiredError`（即 ask 无回调/TTY 不执行）。

`_record(request, decision)`（108-120）把 decision 与 request 快照合并追加到 `TransparencyLog`。`pending()`（122-129）返回 `requests` 中尚无批准决策的请求列表。`TransparencyLog`（132-145）是追加日志，`snapshot()` 返回浅拷贝。`operation_summary(log_entries)`（148-158）输出每行 `时间 操作: 描述 (decision=..., source=...)`。

### 生物原理

该模块不直接处理序列，而是确保危险/降级操作（例如 Primer3 不可用降级为启发式、slide-retry 放松精确边界、写外部文件）在无人批准时不会执行。政策依据是 `references/privacy-and-consent.md` 与 `references/protocol-recommendation.md` 中“不得静默”的要求；`ConsentBroker(policy="auto")` 要求自动化显式选择并记录，防止默认放行。

### 实现路径

`planning.planner.plan_assembly` 默认 `ConsentBroker(policy="ask")`，并把 broker 传给 `primer_design_engine.design_region_primers`；`plan_assembly.py` 的 `--consent auto/--yes` 决定 broker 形态。`recommend_protocol.py` 不直接使用该模块，但同属知情权基础设施。

### 科学性说明

已知限制：`pending()` 按 request id 匹配 decisions，若同一请求有多次决策只看最后一条；`pre_approved` 是精确名称匹配，不支持通配符。对应测试：`tests/test_release_iteration.py::ConsentBrokerTests::test_ask_without_callback_or_tty_does_not_execute`、`test_deny_callback_blocks_execution`、`test_approve_callback_executes`、`test_auto_policy_is_explicit_and_recorded`、`test_invalid_policy_and_bytes_sha_and_pre_approved`；`tests/test_release_iteration.py::TransparencyGateTests::test_result_carries_backend_parameters_sha_and_retry_path`、`test_degradation_is_recorded_not_silent`。

---

## scripts/provenance.py：来源追踪

### 技术原理

`scripts/provenance.py` 是结构化来源追踪基础设施，188 行。`read_version()`（20-28）从 `ROOT/VERSION` 读版本，文件缺失返回 `unknown`；所有 provenance 对象必须使用该值，禁止硬编码版本。`ALLOWED_SOURCE_TYPES`（31-40）含 `software`、`prediction-model`、`reference-database`、`manufacturer-protocol`、`public-protocol`、`published-paper`、`heuristic`、`user-input`。`ALLOWED_STATUSES`（41-43）含 `verified/partial/unavailable/unknown/conflicting/stale`。

`source(source_type, name, role, url=None, version=None, license_value=None, status="unknown", verification=None, retrieved_at=None, additional=None)`（69-100）创建 source 对象，强制：source_type 与 status 合法；name 非空且不得为 `AI`/`internet`/`latest`（大小写不敏感，81-82）；role 非空；version 不得为 `latest`（85-86）。输出过滤 None 值（100）。

`validate(source_obj)`（116-137）复验必填键与枚举，并按 `CONDITIONAL_REQUIRED`（109-113）检查条件必填：`manufacturer-protocol` 必须含 `url/retrieved_at/version`；`prediction-model` 必须含 `name/version`；`public-protocol` 必须含 `url/retrieved_at`。`source_id(source_obj)`（103-106）对排序 JSON 做 SHA-256，返回 `"src-"+前 12 位`。

`probe_executable(executable, version_args=None)`（140-168）用 `shutil.which` 探测可执行文件，`subprocess.run([exe]+version_args or ["--version"])` 超时 20 s 获取版本；任何失败返回 `(exe, None, {"method":"subprocess-version-probe","status":"unavailable",...})`，不向调用方抛异常。`ensure_provenance(result, label="result")`（171-177）要求 result dict 含非空 `provenance` 且逐条 `validate`。

### 生物原理

来源追踪是科学可复现性的基础。`references/source-policy.md` 规定优先级：制造商官方协议 > protocols.io > Addgene 通用方案 > 同行评议论文及补充材料 > 博客/论坛/搜索摘要；禁止 `AI`、`internet`、`latest` 与未限定的 `verified`。`provenance.source` 把这些政策转成构造期校验，`validate` 在结果交付前复验，使“无来源不输出”成为可测试的硬约束。

### 实现路径

所有计划、反应刻画、协议推荐与规则评估结果都调用 `provenance.source` 生成 provenance；`provenance.validate` 由 `ensure_provenance` 与各测试调用。

### 科学性说明

已知限制：`source` 不验证 URL 可访问性，只验证结构；`verified` 状态必须由调用方给出可解释的 `verification` 方法，否则只是字符串。对应测试：`tests/test_v08_dev3.py::ProvenanceVersionTests::test_conditional_required_fields`、`test_schema_rejects_manufacturer_missing_required_fields`、`test_all_provenance_versions_come_from_version_file`；`tests/test_v08_gate_coverage.py::ProvenanceGapTests::test_source_rejections`、`test_validate_rejections`、`test_read_version_missing_file`、`test_probe_executable_paths`；`tests/test_v08_guides.py::ProvenanceTests::test_valid_source`、`test_forbidden_sources_rejected`、`test_missing_provenance_fails`。

---

## scripts/protocol_evidence.py：协议证据加载

### 技术原理

`scripts/protocol_evidence.py` 加载带 provenance 的协议证据，30 行。`EVIDENCE_PATH` 指向 `references/protocol-evidence-dev2.json`（12）。`load_sources(path=None)`（15-19）文件缺失返回 `[]`，存在则读 `data["sources"]`。`source_object(item)`（22-29）把证据条目转换为 `provenance.source` 对象：source_type 原样传入，name 为 `"<provider> protocol"`，role 固定 `protocol-recommendation`，url/version 来自条目，状态在 `verification_status == "current-page-read"` 时为 `verified` 否则 `unknown`，verification 方法记为 `web-page-read`，additional 保存 provider/title/catalog_number。

`references/protocol-evidence-dev2.json` 当前含两条证据：NEB Q5 高保真 DNA 聚合酶（M0491，`applicable_to: ["high-fidelity-cloning-pcr","high-gc-pcr"]`）与 NEB NEBuilder HiFi DNA Assembly（E2621/E5520/E2623，`applicable_to: ["gibson-like-assembly","nebuilder-hifi"]`）。检索日期 2026-08-17，document_revision 未知，verification_status 为 `current-page-read`。

### 生物原理

协议推荐不得凭记忆发明温度/时间/缓冲液/酶系统/反应体积（`references/protocol-recommendation.md`）。证据文件由真实制造商网页读取生成，搜索摘要不作为精确实验条件的证据。`source_object` 把证据条目的“当前页已读”状态转为 `verified` provenance，使下游推荐可追溯到具体官方页面。

### 实现路径

`recommend_protocol.recommend` 调 `protocol_evidence.load_sources`，并 `source_object` 逐条生成 provenance。CLI 由 `recommend_protocol.py --protocol-evidence` 覆盖证据路径。

### 科学性说明

已知限制：证据只有两条且 `document_revision` 未知；离线时 `load_sources` 返回 `[]`，推荐会显式降级为 `PROTOCOL_SOURCE_NOT_FOUND`。对应测试：`tests/test_v08_dev2.py::ProtocolEvidenceTests::test_packaged_evidence_has_required_fields`、`test_recommendation_uses_loaded_source`；`tests/test_v08_gate_coverage.py::ProtocolEvidenceGapTests::test_load_missing_and_source_object`。

---

## scripts/recommend_protocol.py：特征驱动的协议推荐

### 技术原理

`scripts/recommend_protocol.py` 做来源门控的协议推荐，192 行。`_as_bool(value)`（19-21）把 `true/yes/required/high/1` 视作 True。`_category_for(profile)`（24-49）把反应特征映射为证据类别：`reaction_type` 为 assembly/gibson/nebuilder 系列或 `assembly_method` 为 gibson/nebuilder 系列 → `assembly`；`reaction_type` 为 pcr 系列、`template_type` 为 PCR 模板、`high_fidelity_required` 为真、存在 5' 尾巴或 `specificity_checked is True` → `pcr`；否则 None。

`_source_matches(category, profile, item)`（52-76）逐条判断证据适用性：`pcr` 类别下 `high-fidelity-cloning-pcr` 直接匹配，`high-gc-pcr` 需 `gc_percent >= 60.0` 才匹配；`assembly` 类别下 `gibson-like-assembly` 或 `nebuilder-hifi` 匹配。匹配理由必须写出实际 profile 字段与观测值。

`_pick_source(category, profile, sources)`（79-87）返回第一个匹配的 `(index, item, reasons)`。

`recommend(profiles, protocol_sources=None)`（90-158）核心逻辑：

1. `profiles` 为空返回 `NO_REACTION_PROFILES_PROVIDED`（93-104）；
2. `sources` 为空返回 `PROTOCOL_SOURCE_NOT_FOUND`（105-114）；
3. 每个 profile 经 `_category_for` + `_pick_source`；未匹配返回 `insufficient_evidence`，`recommended_system=None`、`evidence_level="none"`、`human_review_required=True`（120-137）；
4. 匹配成功返回 `compatible_candidate`，推荐系统为 Q5（`high-fidelity-cloning-pcr` 适用）或 NEBuilder HiFi（`gibson-like-assembly` 适用），`evidence_level="manufacturer-official"`、`human_review_required=True`（140-158）。

顶层状态：`matched_count==0` → `unavailable`；部分匹配 → `partial`；全匹配 → `available`（159-166）。

### 生物原理

酶系统选择必须有来源。Q5 高保真聚合酶适合高保真克隆 PCR 与高 GC 模板（NEB M0491 官方协议；`references/biological-parameters-sources.json` P11-P12）；NEBuilder HiFi DNA Assembly 是 Gibson 类组装的主流商品化体系（NEB E2621 官方协议）。推荐函数只做“证据标签与反应特征匹配”，不发明具体实验条件；条件字段留在证据文件中（`conditions`），标注为 `manufacturer-provided`。

### 实现路径

`recommend_protocol.main` 读 `--profile` JSON 的 `reaction_profiles`，加载 `--protocol-evidence`（默认打包证据），调用 `recommend` 后 `jprint`。调用链：`main -> load_sources -> recommend -> _category_for -> _pick_source -> _source_matches -> source_object`。

### 科学性说明

已知限制：推荐是候选级别（`compatible_candidate`），不等于最优选择，且始终要求人工复核；当前证据仅 Q5 与 NEBuilder 两条，其他反应类别会得到 `insufficient_evidence`。对应测试：`tests/test_v08_dev3.py::ProtocolRecommendationFeatureTests::test_pcr_profile_selects_q5`、`test_assembly_profile_selects_nebuilder`、`test_empty_profile_list_is_unavailable`、`test_unmatched_profile_is_unavailable_with_insufficient_evidence`；`tests/test_v08_gate_coverage.py::RecommendGapTests::test_mixed_profiles_partial`、`test_high_gc_pcr_match`。

---

## scripts/characterize_reaction.py：反应特征刻画

### 技术原理

`scripts/characterize_reaction.py` 产出客观反应特征表，不推荐试剂，93 行。`_windows(seq, width=40, step=10)`（19-20）滑动窗口；`characterize_fragment(record, fragment_id)`（23-47）输出：

| 字段 | 含义 |
|---|---|
| `length` | 片段长度 |
| `topology` | `sg_common.topology(record)`，默认 linear |
| `gc_percent` | 全长 GC%（`gc_fraction`） |
| `gc_5prime_40` / `gc_3prime_40` | 5' 与 3' 端 40 bp GC% |
| `max_local_gc_window_40` | 40 bp 滑窗最大 GC% |
| `homopolymer_runs` | 长度 ≥6 的同聚物串列表 |
| `predicted_difficulty` | 固定 `"not_scored"` |
| `high_fidelity_required` / `five_prime_tail` / `assembly_method` | 固定 `"unknown"` |
| `specificity_checked` | 固定 `False` |
| `provenance` | 软件来源，角色 `reaction-profile`，版本来自 `read_version()` |

`_homopolymer_runs(seq, threshold=6)`（50-66）线性扫描，记录 `base` 与 `length`。`main`（69-89）对每个输入文件 `load_seq` 后 `characterize_fragment`，汇总为 `{"reaction_profiles":[...], "generated_at":..., "note":"reaction profile only; no reagent or protocol recommendation included"}`。

### 生物原理

PCR 扩增难度与片段 GC 含量、端部 GC、局部高 GC 与同聚物串相关：端部 GC 影响引物结合，局部高 GC 影响变性，长同聚物串可能导致聚合酶滑移（NEB GC-rich FAQ；Primer3 官方文档关于模板质量与 mispriming 的说明）。该脚本只计算这些可观测特征，不把 `predicted_difficulty` 设为数值分数，避免在无验证模型时给实验员错误的确定性。

### 实现路径

`characterize_reaction.main -> sg_common.load_seq -> characterize_fragment -> _windows/_homopolymer_runs -> jprint`。产物可作 `recommend_protocol.py --profile` 的输入（需包一层 `{"reaction_profiles":[...]}`）。

### 科学性说明

已知限制：`template_type`、`high_fidelity_required`、`five_prime_tail`、`assembly_method` 当前固定为 unknown，需要调用方补充或后续从实验上下文推断；`predicted_difficulty` 固定 `not_scored`，不是预测模型。对应测试：`tests/test_v08_gate_coverage.py::CharacterizeGapTests::test_windows_and_runs`、`test_circular_profile`、`AdditionalCoverageTests::test_characterize_cli`；`tests/test_v08_guides.py::ReactionProfileTests::test_profile_contains_required_fields`。

---

## references 参数来源文件：默认生物学参数的单一来源

### 技术原理

`references/biological-parameters-sources.json`（414 行）是机读单一来源，含 `schema_version: "0.9.0"`、`retrieved_at: "2026-08-19"` 与 `parameters` 数组（P01-P30）。每个条目含 `id/family/name/default/source/source_url/retrieved_at/code_references/notes`。`references/biological-parameters-sources.md`（52 行）是人读索引，总表列 ID、参数族、参数名、默认值、来源、URL、代码引用；使用规则要求“没有来源的参数不得作为默认值输出”，AI 提取或拟合参数必须依据本文件，禁止凭记忆（`references/biological-parameters-sources.md:1-7`）。

与本章直接相关的条目：

| ID | 参数 | 默认值 | 来源 | 代码引用 |
|---|---|---|---|---|
| P15 | overlap 长度 | 15-40 bp | IDT; Gibson 2009 | `planning/planner.py`、`rules/feasibility_rules.json` |
| P16 | overlap GC | 30-70% | IDT | 同上 |
| P17 | Gibson 片段数 | 推荐 4-5，>5 警告 | Gibson 2009 | `rules/feasibility_rules.json` |
| P18 | Golden Gate 片段数 | ≤8 | Engler 2008 | `rules/feasibility_rules.json` |
| P19 | Golden Gate 内部位点 | 自动换酶/回退 Gibson | Engler 2008; NEB | `planning/planner.py`、`rules/feasibility_rules.json` |
| P26 | M2 规则阈值 | 10 条 | 各规则 source | `rules/feasibility_rules.json`、`rules/engine.py` |
| P27 | 构建体大小 | >20 kb 电转化提示（warn） | Sambrook & Russell | `rules/feasibility_rules.json` |
| P29 | 融合读框 | junction offset mod 3 == 0 | M1 设计契约; Gibson 实践 | `planning/planner.py` |

引物相关条目 P03-P09、P28 与 PCR 相关条目 P10-P14、P30 也由本章 planner 的引物设计路径间接使用，具体见第 2 章引物与 PCR 部分；本章只做交叉引用。P22-P25 登记了 Doench 2016（DOI 10.1038/nbt.3437）、Kim 2018（DOI 10.1038/nbt.4061）与 Cas-OFFinder GitHub（https://github.com/snugel/cas-offinder），供第 5 章 gRNA 设计使用。

`references/source-policy.md`（15 行）规定来源优先级（制造商官方协议 > protocols.io > Addgene 通用方案 > 同行评议论文 > 博客/论坛/搜索摘要）与禁止值（`AI`、`internet`、`latest`、未限定 `verified`）。`references/privacy-and-consent.md`（10 行）规定默认不上传、逐次同意、提示内容、同意只记录元数据、完整序列不入日志。`references/protocol-recommendation.md`（11 行）规定不得凭记忆发明条件、具体产品必须来自该产品当前官方协议、不得混用不同聚合酶/试剂盒条件、无网络时标记 `unavailable` 但仍输出客观反应特征。

### 生物原理

参数来源文件把“科学数字必须有出处”固化为数据契约。P27 是实验室共识类阈值，只作 warn，不作 error（`references/biological-parameters-sources.md:49-50`）。P09 的 slide-retry 契约只释放边界与产物窗口，GC 仍保持 Primer3 默认 20-80%；若要放宽 GC，必须走 `operation_consent.py` 的 `relaxation` 询问并记录操作日志（`references/biological-parameters-sources.md:46-48`）。

### 实现路径

`tests/test_release_iteration.py::ParameterSourcesGateTests::test_parameter_source_file_covers_required_families` 校验参数文件覆盖必需家族；`tests/test_release_iteration.py` 还逐条检查 `code_references` 的存在性（`references/biological-parameters-sources.md:50-52` 所述）。

### 科学性说明

已知限制：检索日期为 2026-08-19，页面无 revision 的以 `document_revision: unknown` 处理；来源文件本身不自动更新，需人工维护。对应测试：`tests/test_release_iteration.py::ParameterSourcesGateTests::test_parameter_source_file_covers_required_families`。

---

## 与上下游模块的接口契约

本节用输入/输出契约的视角把本章模块串起来，便于后续开发与集成测试。

**`plan_assembly` 的输入契约**（`planning/planner.py:213-222`）：

| 参数 | 类型 | 契约 |
|---|---|---|
| `source_paths` | `list[str]` | 至少一个来源；每个元素先经 `sg_common.load_seq` 归一化为 `SeqRecord`，格式可为 `.dna`/`.gb`/`.fa`/`.embl`/裸序列/内联 FASTA |
| `intent` | `dict` | 必须经 `normalize_intent` 归一化；缺省 method 为 auto，拓扑缺省 circular |
| `primer3_core` | `str|None` | 传给 `primer_design_engine.design_region_primers`，None 时走自动探测 |
| `user_rules_dir` | `str|Path|None` | 传给 `rules.engine.evaluate_plan`，None 时使用内置 `user_rules/` |
| `consent_broker` | `ConsentBroker|None` | None 时默认 `ConsentBroker(policy="ask")`，即无确认不执行 |
| `operation_log` | `TransparencyLog|None` | None 时新建；最终快照写入计划的 `operation_log` 字段 |

**`plan_assembly` 的输出契约**：顶层 dict 必须满足 `schemas/assembly-plan-v0.9.json` 的必填字段，并额外携带 `consent`（含 `broker_policy`、`requests`、`pending`）与 `operation_log`。`fragment_assignments` 是唯一同时包含序列、来源文件路径、0-based/1-based 区间与角色（backbone/insert）的权威片段表；`assembly_strategy` 记录方法切换原因与替代方案；`numeric_evidence` 把本章使用的数值窗口与出处显式写进计划，便于审计。

**规则引擎的上下文契约**：`evaluate_plan` 只接受扁平 dict，键集合由 `_feasibility_context` 定义（`planning/planner.py:530-546`）。新增规则时必须在 `_feasibility_context` 中补充键，否则内置规则求值因异常静默返回 False。用户规则 JSON 采用同一 schema，`id` 覆盖内置规则。

**协议推荐与反应刻画的契约**：`characterize_reaction.main` 输出 `{"reaction_profiles":[...]}`；`recommend_protocol.main --profile` 读取同一结构的 `reaction_profiles`。推荐器不修改 profile，未匹配时返回 `insufficient_evidence` 而非猜测产品。两者之间的数据语义边界是：`characterize_reaction` 只陈述客观序列特征，`recommend_protocol` 只做“特征 → 证据标签”匹配。

**在线来源与同意的契约**：`online_sources` 不直接执行任何序列上传；它返回 `offline-unverified`、`refused-consent-required`、`denied` 或 `authorized` 四种机器状态之一。真正允许序列离开本地前，必须由 `SequenceUploadConsent.allowed` 对 `(destination, purpose, sequence, scope)` 四元组做一次性消费检查。新增在线适配器时必须复用该状态机，不得绕过。

这些契约的共同点是：输入非法早失败、授权缺失早阻断、证据缺失显式降级、来源缺失拒绝输出。

## 边界条件与稳定错误码

本章各模块的失败必须是结构化、可机器解析的。统一约定：CLI 顶层失败信封为 `{"schema_version":"0.9.0","status":"failed","reason":<前缀>,"detail":<完整消息>}`（`scripts/plan_assembly.py:68-80`）；库函数抛出的异常名/错误码前缀稳定，调用方不应依赖完整消息文本。

| 错误码/异常 | 抛出位置 | 触发条件 |
|---|---|---|
| `INTENT_REQUIRED` | `scripts/plan_assembly.py:57` | 未提供 `--intent-json` 或 `--intent-text` |
| `EMPTY_ASSEMBLY_INTENT_TEXT` | `planning/intent.py:54` | 空意图文本 |
| `ASSEMBLY_INTENT_MUST_BE_DICT` | `planning/intent.py:28` | `normalize_intent` 收到非 dict |
| `UNSUPPORTED_ASSEMBLY_METHOD` | `planning/intent.py:47` | method 不在五种允许值内 |
| `INTENT_MISSING_BACKBONE_SOURCE` | `planning/intent.py:104` | 文本意图缺少 backbone |
| `INTENT_MISSING_FRAGMENTS` | `planning/intent.py:106` | 文本意图缺少 fragments |
| `BACKBONE_SOURCE_OUT_OF_RANGE` | `planning/planner.py:237-239` | backbone source 编号越界 |
| `FRAGMENT_SOURCE_OUT_OF_RANGE` | `planning/planner.py:255-257` | fragment source 编号越界 |
| `FRAGMENT_INTERVAL_OUT_OF_RANGE` | `planning/planner.py:91-94` | 区间不满足 `0 <= start < end <= len(seq)` |
| `FEATURE_NOT_FOUND` | `planning/planner.py:97-99` | 指定 feature/name 但无法唯一解析 |
| `FUSION_JUNCTION_OUT_OF_RANGE` | `planning/planner.py:156-157` | fusion junction 不在 `0..n-2` |
| `UNKNOWN_RESTRICTION_ENZYME` | `scripts/primer_design_engine.py:43` | `restriction_tail` 收到未知酶名 |
| `invalid consent policy` | `scripts/operation_consent.py:74` | `ConsentBroker` policy 不是 ask/auto |
| `ConsentRequiredError` | `scripts/operation_consent.py:106` | ask 策略无回调/TTY 或回调拒绝 |
| `ProvenanceError` | `scripts/provenance.py:46-47` | source/validate 校验失败（禁止 `AI`/`internet`/`latest` 等） |
| `BLAST_CONSENT_REQUIRED` | `scripts/online_sources.py:186-188` | `authorized_blast_url` 未获一次性绑定同意 |
| `refused-consent-required` | `scripts/online_sources.py:59-65` | `ncbi_search` 收到裸序列样输入 |
| `offline-unverified` | `scripts/online_sources.py:93-95, 108-110` 等 | 网络失败/无结果/未实现适配器，绝不伪造 |

关键边界条件汇总：

1. **坐标边界**：`planning/planner.py:_extract_region` 的区间是 0-based 半开；`plan` 输出的 `source_interval_1based` 是 `[start+1, end]`（`planning/planner.py:446-448`）。环形来源的片段区间可能跨 origin，但 `_extract_region` 的区间模式仍要求 `start < end`，跨 origin 的环形区间必须使用 feature 路径或先线性化。
2. **空序列**：`sg_common.load_seq` 接受裸序列字符串，但空字符串抛 `ValueError("Empty source")`（`scripts/sg_common.py:126-137`）。空 FASTA 记录会进入 planner，随后区间提取可能因 `start < end` 失败；`tests/test_destructive_inputs.py::PlannerDestructiveTests::test_empty_fasta_source` 锁定该行为。
3. **反向链 feature**：`feature.extract` 返回生物学 5'→3' 方向片段，同时区间坐标仍是参考轴上的 `[start,end)`；这意味着下游 `fragment_assignments[].source_interval_0based` 是参考轴坐标，`sequence` 是提取后的方向序列，两者语义不同（`planning/planner.py:100-105`）。
4. **环形限制位点**：`sg_common.restriction_hits` 与 `validation_crosscheck.restriction_site_crosscheck` 在 `circular=True` 时允许 hit 跨 origin；planner 只对 `role=="backbone"` 且意图拓扑为 `circular` 的片段启用环形扫描（`planning/planner.py:292-296`、312-316）。
5. **在线来源不可用**：`online_sources.ncbi_search` 在 NCBI 返回空 idlist 时也返回 `offline-unverified`，不会把“无结果”伪装成“已验证在线”（`scripts/online_sources.py:74-76`）。
6. **同意消耗**：`SequenceUploadConsent.allowed` 默认 `consume=True`，一次授权只能使用一次；任何参数不匹配先 `deny()` 再返回 False（`scripts/sequence_upload_consent.py:118-126`）。
7. **规则表达式**：`rules/engine.py:_check_rule` 拒绝含 `any(` 或 `__` 的表达式，异常返回 False；规则文件写错不会导致崩溃，但会静默不命中（`rules/engine.py:39-46`）。

这些边界条件共同保证：规划器对非法输入早失败，对未授权操作早阻断，对离线/无证据场景显式降级，不产生静默错误或伪造数据。

## 全流程调用链与模块关系

### 规划主链

```
scripts/plan_assembly.py:main
  ├─ planning/intent.py:normalize_intent | parse_intent_text
  ├─ scripts/operation_consent.py:ConsentBroker
  └─ planning/planner.py:plan_assembly
       ├─ scripts/sg_common.py:load_seq
       ├─ planning/planner.py:_extract_region
       ├─ planning/planner.py:choose_overlap
       │    └─ scripts/validation_crosscheck.py:overlap_crosscheck
       ├─ planning/planner.py:_find_type_iis_enzyme / restriction_hits
       │    └─ scripts/validation_crosscheck.py:restriction_site_crosscheck
       ├─ rules/engine.py:evaluate_plan
       │    ├─ rules/feasibility_rules.json
       │    └─ user_rules/*.json
       ├─ scripts/primer_design_engine.py:design_region_primers
       │    └─ scripts/operation_consent.py:ConsentBroker.request
       ├─ planning/planner.py:_check_fusion_frame
       └─ scripts/provenance.py:source
  ├─ planning/manual_render.py:render_markdown | render_html
  └─ scripts/plan_assembly.py:_write_construct_files
       └─ scripts/write_dna.py:_ensure_annotations, write_native_dna
```

### 协议推荐链

```
scripts/recommend_protocol.py:main
  └─ scripts/recommend_protocol.py:recommend
       ├─ scripts/protocol_evidence.py:load_sources
       ├─ scripts/recommend_protocol.py:_category_for
       ├─ scripts/recommend_protocol.py:_pick_source
       │    └─ scripts/recommend_protocol.py:_source_matches
       └─ scripts/protocol_evidence.py:source_object -> scripts/provenance.py:source
```

### 在线来源与同意链

```
scripts/online_sources.py:ncbi_search
  ├─ _looks_like_sequence（拒绝裸序列）
  ├─ _get -> esearch.fcgi -> esummary.fcgi
  └─ 失败 -> offline-unverified

scripts/online_sources.py:ncbi_blast_consent_request
  └─ scripts/sequence_upload_consent.py:SequenceUploadConsent.request
       └─ scripts/provenance.py:sha256_of_text
scripts/online_sources.py:authorized_blast_url
  └─ SequenceUploadConsent.allowed（一次一票，消费式）
```

### 反应刻画 → 推荐

```
scripts/characterize_reaction.py:main
  └─ characterize_fragment -> reaction_profiles
       └─ scripts/recommend_protocol.py:recommend（profile JSON 作为输入）
```

---

## 下游消费与人工复核要点

计划 JSON 与构建手册是给人看、也给程序读的双格式产物。程序消费时应优先读取 `status`、`assembly_strategy.method`、`feasibility.grade`、`feasibility.errors` 与 `consent.pending`；只有在 `status == "complete"`、`grade == "high"` 且 `pending` 为空时，才可认为规划无阻断项。人工复核时应重点查看三处：一是 `assembly_strategy.alternatives`，任何自动方法切换都必须被操作者知晓；二是 `primers[].validation` 与 `primer3_retry_note`，确认引物后端与重试层；三是 `operation_log`，确认所有降级、放宽与外部写文件决策均已被记录。对于 digest-ligate 与 Golden Gate，人工复核还必须回到 `simulate_cloning.digest_ligate` 或 `golden_gate.assemble` 计算真实酶切连接产物，不能以 planner 的顺序拼接序列作为最终序列。

## 科学性与适用边界总述

本章所有输出均为计算预测或来源索引，不构成可直接执行的湿实验方案。具体边界如下：

1. **组装计划**：`plan_assembly` 的 `final_construct.sequence` 对 digest-ligate/Golden Gate 只是片段顺序拼接，不是酶切连接产物；最终产物序列由 `simulate_cloning.digest_ligate` 或 `golden_gate.assemble` 计算。`status: complete` 只表示通过 M2 规则与同意门，不表示实验一定成功。
2. **实验性标注**：M2 规则是经验阈值（如 >20 kb 电转化提示），按 warn/error 分级；`recommend_protocol` 的输出是 `compatible_candidate`，`human_review_required` 始终为 True。
3. **在线来源**：离线/失败显式为 `offline-unverified`；Addgene 适配器只是官方链接助手；BLAST/CRISPOR 序列上传必须经过一次性绑定同意。
4. **已知限制**：`choose_overlap` 不做末端二级结构与退火动力学预测；`rules.engine._check_rule` 表达式异常静默不命中；`parts_library` 多数元件 `sequence: null`，只作来源索引；`characterize_reaction` 的 `predicted_difficulty` 固定为 `not_scored`。
5. **引用纪律**：本章 DOI/URL 均来自仓库内 `references/biological-parameters-sources.json`、`references/biological-parameters-sources.md`、`rules/feasibility_rules.json`、`references/protocol-evidence-dev2.json` 与 `references/*.md`，未新增任何 DOI/URL。

---

## 本章覆盖脚本清单

| # | 文件 | 关键入口/类 | 行号 |
|---|---|---|---|
| 1 | `scripts/plan_assembly.py` | `main()`、`_interactive_confirm()`、`_write_construct_files()` | 30、18、122 |
| 2 | `planning/intent.py` | `normalize_intent()`、`parse_intent_text()`、`_coerce_interval()` | 26、51、11 |
| 3 | `planning/planner.py` | `plan_assembly()`、`choose_overlap()`、`_extract_region()`、`_check_fusion_frame()`、`_decide_method()`、`_primer_tails()`、`_feasibility_context()` | 213、123、86、152、177、195、530 |
| 4 | `planning/manual_render.py` | `render_html()`、`render_markdown()`、`_default_steps()` | 7、86、172 |
| 5 | `rules/engine.py` | `load_rules()`、`_check_rule()`、`evaluate_plan()` | 19、39、49 |
| 6 | `rules/feasibility_rules.json` | 10 条规则 | 3-84 |
| 7 | `user_rules/README.md` | 用户规则约定 | 1-11 |
| 8 | `schemas/assembly-plan-v0.9.json` | Draft 2020-12 Schema | 1-29 |
| 9 | `scripts/parts_library.py` | `load_parts()`、`find_parts()`、`main()` | 12、18、30 |
| 10 | `scripts/online_sources.py` | `ncbi_search()`、`fetch_genbank()`、`addgene_lookup()`、`ncbi_blast_hint()`、`ncbi_blast_consent_request()`、`authorized_blast_url()`、`request_crispor_query()` | 52、98、113、133、154、173、199 |
| 11 | `scripts/sequence_upload_consent.py` | `SequenceUploadConsent`、`request()`、`approve()`、`allowed()`、`consent_message()` | 21、39、59、92、128 |
| 12 | `scripts/operation_consent.py` | `ConsentBroker`、`make_request()`、`TransparencyLog`、`operation_summary()` | 59、43、132、148 |
| 13 | `scripts/provenance.py` | `source()`、`validate()`、`source_id()`、`probe_executable()`、`ensure_provenance()`、`read_version()` | 69、116、103、140、171、20 |
| 14 | `scripts/protocol_evidence.py` | `load_sources()`、`source_object()` | 15、22 |
| 15 | `scripts/recommend_protocol.py` | `recommend()`、`_category_for()`、`_source_matches()`、`_pick_source()` | 90、24、52、79 |
| 16 | `scripts/characterize_reaction.py` | `characterize_fragment()`、`_windows()`、`_homopolymer_runs()` | 23、19、50 |
| 17 | `references/biological-parameters-sources.json` | P01-P30 参数来源 | 1-414 |
| 18 | `references/biological-parameters-sources.md` | 人读参数总表 | 1-52 |
| 19 | `references/source-policy.md` | 来源优先级 | 1-15 |
| 20 | `references/privacy-and-consent.md` | 隐私与上传同意 | 1-10 |
| 21 | `references/protocol-recommendation.md` | 协议推荐规则 | 1-11 |
| 22 | `references/protocol-evidence-dev2.json` | NEB Q5 / NEBuilder 证据 | 1-38 |

## 关键测试清单

| 测试文件 | 测试类/测试名 | 覆盖点 |
|---|---|---|
| `tests/test_v09.py` | `M1PlannerTests::test_two_fragment_overlap_plan` | 两片段 overlap 计划完整、overlap ≥15 bp、grade high |
| `tests/test_v09.py` | `M1PlannerTests::test_four_fragment_overlap_auto_switch_gibson` | M2 规则触发自动切换 Gibson |
| `tests/test_v09.py` | `M1PlannerTests::test_golden_gate_internal_bsai_switches_enzyme` | Type IIS 内部位点自动换酶 |
| `tests/test_v09.py` | `M1PlannerTests::test_reverse_strand_feature_extraction_is_biological` | 反向链 feature 提取 5'→3' |
| `tests/test_v09.py` | `M1PlannerTests::test_intent_text_parser` | key=value 意图解析 |
| `tests/test_v09.py` | `M2RuleTests::test_builtin_rules_load_with_sources` | 内置规则来源非空、severity 合法 |
| `tests/test_v09.py` | `M2RuleTests::test_overlap_4_fragments_is_error` | overlap >3 片段为 error、grade low |
| `tests/test_v09.py` | `M2RuleTests::test_user_rules_override` | 用户规则覆盖内置规则 |
| `tests/test_v09.py` | `M5PartsTests::test_lookup` | 元件库查询 |
| `tests/test_v09.py` | `AdditionalV09CoverageTests::test_plan_assembly_main_direct` | CLI main 直接调用与 construct 写出 |
| `tests/test_v09.py` | `AdditionalV09CoverageTests::test_plan_schema_validation` | 计划通过 assembly-plan-v0.9 schema |
| `tests/test_v09.py` | `AdditionalV09CoverageTests::test_plan_assembly_cli` | CLI 端到端 |
| `tests/test_v09.py` | `AdditionalV09CoverageTests::test_digest_ligate_rejects_two_sites_in_one_fragment` | digest-ligate 位点唯一性 |
| `tests/test_v09.py` | `AdditionalV09CoverageTests::test_html_render_matches_plan_data` / `test_manual_render` | Markdown/HTML 渲染 |
| `tests/test_v09.py` | `M6OnlineSourceTests::test_offline_degrade_is_explicit` | 离线显式降级 |
| `tests/test_online_privacy.py` | `BlastPrivacyTests`（全部 6 项） | BLAST URL 不含序列、同意绑定、一次一票 |
| `tests/test_bio_audit_regressions.py` | `AuditRegressionTests::test_fusion_frame_uses_addition_not_subtraction` | 融合读框计算 |
| `tests/test_bio_audit_regressions.py` | `AuditRegressionTests::test_consent_hash_matches_normalized_transmitted_sequence` | 同意哈希与传输序列一致 |
| `tests/test_bio_audit_regressions.py` | `AuditRegressionTests::test_short_raw_oligo_is_refused_before_network` | 短裸序列在联网前拒绝 |
| `tests/test_destructive_inputs.py` | `RulesDestructiveTests::test_eval_is_sandboxed` | 规则 eval 沙箱 |
| `tests/test_destructive_inputs.py` | `PlannerFuzzTests::test_random_intents_never_crash_with_bare_exceptions` | 随机意图不裸崩 |
| `tests/test_destructive_inputs.py` | `PlannerDestructiveTests::test_missing_source_file` / `test_empty_fasta_source` / `test_bad_intent_text` | 规划器破坏性输入 |
| `tests/test_release_iteration.py` | `ConsentBrokerTests`（全部 5 项） | ask/deny/approve/auto/pre_approved 与非法 policy |
| `tests/test_release_iteration.py` | `TransparencyGateTests::test_result_carries_backend_parameters_sha_and_retry_path` | 透明日志字段 |
| `tests/test_release_iteration.py` | `TransparencyGateTests::test_degradation_is_recorded_not_silent` | 降级显式记录 |
| `tests/test_release_iteration.py` | `CliConsentGateTests::test_plan_assembly_ask_blocks_construct_write_until_confirmed` | 未确认不写构建体 |
| `tests/test_release_iteration.py` | `ParameterSourcesGateTests::test_parameter_source_file_covers_required_families` | 参数来源覆盖 |
| `tests/test_v08_dev2.py` | `ProtocolEvidenceTests::test_packaged_evidence_has_required_fields` | 证据字段完整 |
| `tests/test_v08_dev2.py` | `ProtocolEvidenceTests::test_recommendation_uses_loaded_source` | 推荐使用已加载来源 |
| `tests/test_v08_dev3.py` | `ConsentBindingTests::test_ten_interception_scenarios` | 上传同意 10 种拦截场景 |
| `tests/test_v08_dev3.py` | `ProvenanceVersionTests`（全部 3 项） | 来源条件必填、schema 拒绝、版本单一来源 |
| `tests/test_v08_dev3.py` | `ProtocolRecommendationFeatureTests`（全部 4 项） | Q5/NEBuilder/空列表/未匹配 |
| `tests/test_v08_gate_coverage.py` | `RecommendGapTests::test_high_gc_pcr_match` / `test_mixed_profiles_partial` | 高 GC PCR 匹配与部分可用状态 |
| `tests/test_v08_gate_coverage.py` | `CharacterizeGapTests::test_windows_and_runs` / `test_circular_profile` | 滑窗、同聚物串、环状 profile |
| `tests/test_v08_gate_coverage.py` | `ProtocolEvidenceGapTests::test_load_missing_and_source_object` | 证据缺失与 source 对象 |
| `tests/test_v08_gate_coverage.py` | `ProvenanceGapTests`（全部 5 项） | source/validate 拒绝、版本文件缺失、probe_executable |
| `tests/test_v08_guides.py` | `UploadConsentTests::test_default_is_denied` / `test_approve_changes_state_once` | 上传默认拒绝与单次批准 |
| `tests/test_v08_guides.py` | `ReactionProfileTests::test_profile_contains_required_fields` | 反应特征字段 |
| `tests/test_v08_guides.py` | `ProtocolRecommendationTests::test_without_sources_is_unavailable` | 无来源显式不可用 |

# 第 5 章：CRISPR gRNA 设计、on/off-target 模型与 Cas-OFFinder 集成

本章覆盖 v0.9.0 中 CRISPR 引导 RNA（gRNA）候选扫描、on-target 评分模型、off-target 搜索与注释、CRISPR 设计报告生成，以及与 Cas-OFFinder / CRISPOR 的外部工具适配。全章涉及的脚本、参考数据与 Schema 均相对仓库根 `D:/codex_project/snapgene-dna-design-v0.9.0-work`。

必须覆盖的文件为：

| 分组 | 文件 | 职责 |
|---|---|---|
| 候选扫描 | `scripts/design_guides.py` | 基于 `references/nuclease-registry.json` 的确定性 gRNA 候选扫描器 |
| on-target 评分门 | `scripts/guide_scoring.py` | 按核酸酶选择 on-target 模型，模型不可用时显式返回 unavailable |
| SpCas9 模型后端 | `scripts/azimuth_backend.py` | 真实 Azimuth V3 / Doench-2016 梯度提升树推理 |
| AsCas12a 模型后端 | `scripts/deepcpf1_model.py` | 真实 DeepCpf1 / Kim-2018 Keras 权重的 PyTorch 前向推理 |
| off-target 搜索 | `scripts/cas_offinder_adapter.py` | Cas-OFFinder 探测、输入构造、执行、v2/v3 输出解析 |
| off-target 注释 | `scripts/annotate_offtargets.py` | 将脱靶 hit 与 GenBank feature 按区间重叠注释 |
| 统一报告 | `scripts/generate_crispr_design_report.py` | 汇总候选、评分、脱靶、反应特征、协议推荐，写 JSON/Markdown/序列文件 |
| CRISPOR 适配 | `scripts/crispor_adapter.py` | CRISPOR 本地探测与“先同意、后上传”的请求构造 |
| 协议推荐 | `scripts/recommend_protocol.py` | 特征驱动、来源门控的 PCR/组装协议推荐 |
| 反应刻画 | `scripts/characterize_reaction.py` | PCR 片段客观反应特征表，不推荐试剂 |
| 注册表 | `references/nuclease-registry.json` | 核酸酶 PAM、spacer、模型与参考文献注册表 |
| 模型适用性 | `references/crispr-model-applicability.md` | on/off-target 模型适用边界与禁用规则 |
| Schema | `schemas/guide-design-result-v0.8.json`、`schemas/offtarget-result-v0.8.json`、`schemas/crispr-design-report-v0.8.json`、`schemas/protocol-recommendation-v0.8.json`、`schemas/reaction-profile-v0.8.json`、`schemas/provenance-v0.8.json` | 输出 JSON 契约 |

**引用来源**：本章引用 Sambrook & Russell《Molecular Cloning: A Laboratory Manual》（CSHL Press）；Gibson et al. 2009 *Nat Methods* 6:343-345（DOI 10.1038/nmeth.1318）；Engler et al. 2008 *PLoS One* 3:e3647（DOI 10.1371/journal.pone.0003647）；NEB/Takara/IDT 官方协议；Primer3 官方手册（https://primer3.org/manual.html）；Doench et al. 2016 *Nat Biotechnol* 34:184-191（DOI 10.1038/nbt.3437）；Kim et al. 2018 *Nat Biotechnol* 36:239-241（DOI 10.1038/nbt.4061）；Cas-OFFinder GitHub（https://github.com/snugel/cas-offinder）；BioPython/Bio.Restriction 文档。以上来源中，Doench-2016 与 Kim-2018 已登记于 `references/nuclease-registry.json:40-46` 与 `references/nuclease-registry.json:86-92`，Cas-OFFinder URL 与 BSD-3-Clause 许可证写在 `scripts/cas_offinder_adapter.py:52-53`，NEB 协议 URL 登记于 `references/protocol-evidence-dev2.json`。Primer3 官方手册是引物 Tm/hairpin/dimer 计算的权威来源，在本章仅用于说明边界：本章 gRNA 评分不使用 Primer3 热力学，gRNA 的 `heuristic_qc` 也不是引物二聚体计算。

**数据流主线**：`generate_crispr_design_report.main`（`scripts/generate_crispr_design_report.py:351-401`）→ `make_report`（`scripts/generate_crispr_design_report.py:143-220`）→ 内部依次调用 `sg_common.load_seq`（`scripts/sg_common.py:126`）→ `design_guides.scan_guides`（`scripts/design_guides.py:228-329`）→ `guide_scoring.score_guides`（`scripts/guide_scoring.py:114-154`）→ `characterize_reaction.characterize_fragment`（`scripts/characterize_reaction.py:23-47`）→ `protocol_evidence.load_sources`（`scripts/protocol_evidence.py:15-19`）→ `recommend_protocol.recommend`（`scripts/recommend_protocol.py:90-166`）→ `_offtarget_analysis`（`scripts/generate_crispr_design_report.py:58-140`）→ `cas_offinder_adapter.detect` / `search_offtargets`（`scripts/cas_offinder_adapter.py:91-141` / `440-591`）→ `annotate_offtargets.annotate_hits`（`scripts/annotate_offtargets.py:105-155`）→ `_write_design_files`（`scripts/generate_crispr_design_report.py:334-348`）→ `_markdown`（`scripts/generate_crispr_design_report.py:254-331`）。任何上游失败都会落入 `_failed_report`（`scripts/generate_crispr_design_report.py:223-251`）生成结构化 failed 报告并返回非零退出码，绝不裸抛 traceback。

**坐标约定**：`design_guides.py` 的全部候选坐标位于**输入参考轴**（input reference axis），使用 **0-based 半开区间**；反链候选在反向互补序列内部扫描，再通过 `reference = [n - scan_end, n - scan_start)` 映射回参考轴。`user_coordinates_1based_inclusive` 字段给出 1-based 闭区间展示值。Cas-OFFinder v2/v3 输出的 `start` 本身就是 0-based 起点，适配器统一转换为 `[start, start+reference_span)` 的 0-based 半开坐标。拓扑只有显式标注 `circular` 才按环状处理，默认 `linear`（`scripts/sg_common.py:198-206`）。

**阅读提示**：本章先给出注册表与模型适用性政策（数据与规则），再按数据流顺序展开每个脚本；随后专节说明 v2/v3 输入输出列格式、bulge 语义、坐标映射与反链公式；最后给出 Schema、CLI 示例、错误码总表、脚本清单与测试清单。开发者在调试单个脚本时可直接跳到对应 `##` 小节，不必顺序阅读。

---

## references/nuclease-registry.json

### 技术原理

`scripts/design_guides.py:24` 定义 `REGISTRY_PATH = <repo>/references/nuclease-registry.json`；`load_registry(path=None)`（`scripts/design_guides.py:27-30`）读取 JSON 后返回 `{entry["id"]: entry}` 字典。注册表顶层为 `schema_version: 0.8.0` 与 `nucleases` 数组（`references/nuclease-registry.json:1-6`）。每个核酸酶条目包含：

| 字段 | 行号（示例 spCas9） | 含义 |
|---|---|---|
| `id` | 5 | 内部唯一标识，CLI 的 `--nuclease` 值 |
| `display_name` / `family` / `variant` | 6-8 | 显示名、家族（Cas9/Cas12a）、变体 |
| `spacer_lengths` | 9-11 | 允许的 protospacer 长度集合 |
| `pam_patterns` | 12-14 | 允许的 PAM IUPAC 模式列表 |
| `pam_side` | 15 | PAM 位于 protospacer 的 `3prime` 或 `5prime` |
| `target_molecule` | 16 | 靶分子，当前为 DNA |
| `cut_geometry` | 17-20 | 切割几何的定性描述，明确“不做精确偏移推断” |
| `on_target_models` | 21-33 | 允许的 on-target 模型、验证上下文与警告 |
| `off_target_models` | 34-39 | 允许/禁止的 off-target 模型（如 CFD） |
| `references` | 40-46 | 已登记的权威参考文献 DOI/URL |

三个已注册核酸酶为：

| id | family | PAM | spacer | on-target 模型 | off-target CFD |
|---|---|---|---|---|---|
| `spcas9-wt` | Cas9 | `NGG`，3' 侧 | 20 | Doench-2016 / Azimuth V3，允许 | 允许（Cas9 来源模型） |
| `ascas12a-wt` | Cas12a | `TTTV`，5' 侧 | 23 | DeepCpf1 / Kim-2018，允许 | 禁止（Cas9 来源模型，`reason` 见注册表 82-84） |
| `lbcas12a-wt` | Cas12a | `TTTV`，5' 侧 | 23 | 无 | 禁止（Cas9 来源模型） |

### 生物原理

SpCas9 识别 `NGG` PAM，PAM 位于 protospacer 的 3' 侧；AsCas12a/LbCas12a 识别 `TTTV` PAM，PAM 位于 protospacer 的 5' 侧。这些方向性规则是候选扫描中 `pam_side` 分支的分子生物学依据。注册表刻意不给出 SpCas9 的固定切割位点（`references/nuclease-registry.json:17-20` 只写“PAM 上游 3 bp，候选输出必须显式给出边界”），避免把定性知识伪装成定量预测；Cas12a 的交错切割也要求候选级显式坐标。Doench 2016（DOI 10.1038/nbt.3437）与 Kim 2018（DOI 10.1038/nbt.4061）是 on-target 模型来源，注册表同时记录其训练上下文与警告。

### 实现路径

`design_guides.load_registry()` → `scan_guides()` 校验 `nuclease_id`、`pam_patterns`、`spacer_lengths` 后读取规则；`guide_scoring.MODEL_APPLICABILITY`（`scripts/guide_scoring.py:29-39`）与注册表的 `on_target_models` 一致；`cas_offinder_adapter.NUCLEASE_SEARCH_RULES`（`scripts/cas_offinder_adapter.py:58-77`）独立维护 Cas-OFFinder 搜索所需的 PAM/长度约束，三者由测试共同锁定（`tests/test_v08_guides.py:23-39`）。

### 科学性与边界

注册表不是模型本身，也不是实验协议。它只声明“允许使用什么模型、模型有什么警告”。若 `pam_patterns` 或 `spacer_lengths` 为空，`scan_guides` 抛 `INVALID_PAM_DEFINITION`（`scripts/design_guides.py:243-244`）。未知核酸酶抛 `UNKNOWN_NUCLEASE`（`scripts/design_guides.py:240-241`）。

---

## references/crispr-model-applicability.md

### 技术原理

`references/crispr-model-applicability.md` 是模型适用性的政策文件，共 14 行，其规则直接编码在 `scripts/guide_scoring.py:17-39` 的 `APPLICABILITY_WARNINGS` 与 `MODEL_APPLICABILITY` 中：

- 软件与模型分离：always record software, model, training context, applicability warnings separately（`crispr-model-applicability.md:3-5`）。
- SpCas9 可用 Doench 2016 / Azimuth V3，但必须带“未针对酵母验证”警告；`Rule Set 3` 因无独立权威引用不得作为单独模型（`crispr-model-applicability.md:6-9`）。
- AsCas12a 可用 DeepCpf1，但不得自动套用到 LbCas12a（`crispr-model-applicability.md:10-11`）。
- LbCas12a 无已审查模型时返回 `status=unavailable`、`reason=no-validated-model-selected-for-lbcas12a`（`crispr-model-applicability.md:12-13`）。
- 禁止把 Cas9 来源的 off-target 模型（如 CFD）未经审查套用到 Cas12a（`crispr-model-applicability.md:14`）。

### 生物原理与实现路径

模型适用性由训练数据的物种与核酸酶决定：Azimuth/Doench-2016 训练于哺乳动物细胞上下文，因此输出必须带宿主适用性警告；DeepCpf1/Kim-2018 训练于 AsCas12a，不能外推到 LbCas12a。`score_guides()` 对每个候选按 `MODEL_APPLICABILITY` 选择后端；对 `lbcas12a-wt` 且无 scores 的候选补一条 `model=None`、`status=unavailable`、`reason=no-reviewed-model-selected-for-lbcas12a`（`scripts/guide_scoring.py:136-142`）。该行为与 `crispr-model-applicability.md:12-13` 完全一致。

---

## scripts/design_guides.py

### 技术原理

模块文档（`scripts/design_guides.py:2-13`）明确了三条不变式：PAM 规则只来自 `references/nuclease-registry.json`；所有输出坐标为 0-based 半开参考轴；反链候选在反向互补序列内部扫描后映射回参考轴。线性序列绝不环绕，环状序列可环绕且以显式 `coordinates.segments` 表达。

**IUPAC 兼容判断**：`_iupac_compatible(pattern_base, sequence_base)`（`scripts/design_guides.py:33-58`）实现完整 IUPAC 歧义碱基匹配：`N` 匹配任意碱基，`V` 匹配 `A/C/G`，`B` 匹配 `C/G/T`，`D` 匹配 `A/G/T`，`H` 匹配 `A/C/T`，`W` 匹配 `A/T`，`S` 匹配 `C/G`，`M` 匹配 `A/C`，`K` 匹配 `G/T`，`R` 匹配 `A/G`，`Y` 匹配 `C/T`。`pam_matches(seq, pattern)`（`scripts/design_guides.py:61-64`）要求等长并逐位调用 `_iupac_compatible`。

**环状切片**：`_arc(dna, start, length)`（`scripts/design_guides.py:67-75`）对 unwrapped 偏移做 `start %= n` 后用 `(dna + dna)[start:start+length]` 取片；`_slice_circular`（`scripts/design_guides.py:151-155`）是其包装。`_circular_segments(start, length, n)`（`scripts/design_guides.py:78-95`）把 unwrapped 环状区间展开为不环绕的连续段，例如 `[[36, 38], [0, 18]]`。

**区间到参考轴映射**：`_scan_interval_to_reference(start, length, n, strand, circular)`（`scripts/design_guides.py:98-142`）是坐标系统核心：

- 正链：`ref_start = start % n`（`scripts/design_guides.py:109-110`）。
- 反链：反向互补序列的第 k 个碱基对应参考序列第 `n-1-k` 个碱基，因此 `rc[start:start+length)` 在参考轴上的像是 `dna[n-(start+length):n-start)`，即 `ref_start = (n - ((start + length) % n)) % n`（`scripts/design_guides.py:112-115`）。
- 线性分子绝不环绕：`ref_end = ref_start + length`，`wraps_origin=False`；若 `length > n` 返回 `(0,0,False)` 且无 segments（`scripts/design_guides.py:117-127`）。
- 环状分子：`length == n` 返回整环 `[[0,n]]`；`length > n` 返回整环但 `wraps_origin=True`；一般情况 `unwrapped_end = ref_start + length`，`wraps_origin = unwrapped_end > n`，`ref_end = unwrapped_end % n if wraps_origin else unwrapped_end`（`scripts/design_guides.py:129-142`）。**区间恰好在 n 结束不算环绕**，例如 `[20, 23)` 的 PAM 在线性序列末端保留 n 边界，与 SnapGene 语义一致。

**候选坐标对象**：`_candidate_coordinates(...)`（`scripts/design_guides.py:162-184`）返回 `coordinate_system`、`axis=reference`、`strand`、`protospacer_start/end`、`pam_start/end`、`wraps_origin`、`protospacer_segments`、`pam_segments` 与 `user_coordinates_1based_inclusive`。`_user_1based(segments)`（`scripts/design_guides.py:158-159`）把每个 0-based 半开段 `[a,b)` 转为 1-based 闭区间 `[a+1, b]`。

**上下文序列**：`_context_sequences(...)`（`scripts/design_guides.py:199-225`）按模型语义截取评分上下文。对 SpCas9（`family == cas9` 且 `pam_side == 3prime`），`azimuth_30mer` 取 `scan_protospacer_start - 4` 起的 `4 + spacer_length + pam_length + 3` 个碱基，即 4 上游 + 20 protospacer + NGG + 3 下游（`scripts/design_guides.py:215-218`）。对 Cas12a（`family == cas12a` 且 `pam_side == 5prime`），`deepcpf1_34mer` 取 `scan_pam_start - 4` 起的 `4 + pam_length + min(20, spacer_length) + 6` 个碱基，即 4 上游 + TTTV + 20 PAM 近端 gRNA + 6 下游（`scripts/design_guides.py:219-224`）。线性序列两侧侧翼不足时返回 `None`（`scripts/design_guides.py:206-211`）。

**扫描主函数**：`scan_guides(record, nuclease_id, region=None, registry=None, max_candidates=1000)`（`scripts/design_guides.py:228-329`）：

1. 校验核酸酶与 PAM 定义（`scripts/design_guides.py:239-244`）。
2. `dna = str(record.seq).upper()`，`circular = topology(record) == "circular"`，`n = len(dna)`；`region` 为可选 0-based 半开区间，越界抛 `TARGET_REGION_OUT_OF_RANGE`（`scripts/design_guides.py:246-254`）。
3. 对正链 `(1, dna)` 与反链 `(-1, str(Seq(dna).reverse_complement()))` 分别扫描（`scripts/design_guides.py:265-266`）。PAM 锚点：环状 `range(n)`，线性 `range(0, n - pam_length + 1)`（`scripts/design_guides.py:269`），因此线性分子中 PAM 必须完整落在 `[0,n)`。
4. 对每个 PAM 模式、每个锚点 i、每个 spacer 长度，按 `pam_side` 计算 `scan_protospacer_start`：3' PAM 时 `i - spacer_len`，5' PAM 时 `i + pam_length`（`scripts/design_guides.py:276-281`）。
5. 线性拓扑下 protospacer 与 PAM 都不得越界，否则跳过（`scripts/design_guides.py:283-289`）。
6. 区域过滤：仅当 `coordinates["protospacer_segments"]` 或 `pam_segments` 与 `[start,end)` 重叠才保留（`scripts/design_guides.py:294-298`），重叠判据 `_region_overlaps`（`scripts/design_guides.py:187-195`）为严格半开区间相交。
7. protospacer 含非 ACGT 碱基时打 `AMBIGUOUS_TARGET_SEQUENCE` 警告，候选仍保留但不假装适合模型评分（`scripts/design_guides.py:299-301`）。
8. `protospacer_sequence` 是扫描轴上的 5'→3' 序列（反链候选即参考序列的 reverse-complement），`protospacer_reference_sequence` 是参考轴上的同区间序列（`scripts/design_guides.py:290-305`），二者必须区分。
9. 超过 `max_candidates` 时立即截断并 `_assign_ids`（`scripts/design_guides.py:327-328`）。

`_assign_ids(candidates)`（`scripts/design_guides.py:332-336`）按顺序编号 `gRNA-001` 起，并回填 provenance 的 `source_id`。

**CLI**：`main()`（`scripts/design_guides.py:343-390`）接受 `source`、`--nuclease`、可选 `--region start end` 与 `--json`。错误路径打印 `{"ok": false, "error": {"code", "message"}}` 并返回 1（`scripts/design_guides.py:355-359`）。成功时 JSON 含 `schema_version=0.8.0`、`nuclease`、`source`、`topology`、`candidate_count`、`candidates`、`generated_at`、`provenance`（`scripts/design_guides.py:360-373`）。文本模式打印每个候选的 ID、链、序列、PAM、参考轴坐标与警告（`scripts/design_guides.py:377-385`）。

### 生物原理

CRISPR 核酸酶通过 PAM 识别靶位点。SpCas9 的 `NGG` 位于 protospacer 3' 端，Cas12a 的 `TTTV` 位于 5' 端；因此扫描器把 PAM 作为锚点，protospacer 位置由 PAM 侧向推导。gRNA 的 spacer 序列必须与靶 DNA 的反向互补链配对，因此在反链扫描时，扫描序列是参考序列的反向互补，候选序列 5'→3' 显示为 RNA 方向，而坐标仍映射回参考 DNA 轴。环状质粒可跨越 origin 形成 PAM/protospacer 环绕，`wraps_origin` 与显式 segments 正是为了与 SnapGene 的跨原点 feature 表达一致。

从实验设计角度看，扫描器只做 PAM 锚定，不内置 GC 含量、U6/T7 启动子兼容性、poly-T 终止等过滤规则；这些属于下游评分与人工复核。Sambrook & Russell《Molecular Cloning》对核酸酶反应与核酸操作的一般原则（反应条件须以酶学参数为准）在此体现为“候选扫描只依赖注册表 PAM，不发明切割条件”；IDT 官方 gRNA 实验方案同样强调 gRNA 序列必须经实验验证活性，计算扫描不能替代。仓库把 `heuristic_qc`（GC 与同聚物串）放在 `guide_scoring` 而非 `design_guides`，正是为了把“客观扫描”与“启发式质量提示”分层。

### 实现路径

CLI `main` → `sg_common.load_seq` → `scan_guides` → `load_registry` → 正/反链扫描 → `_arc`/`pam_matches`/`_scan_interval_to_reference` → `_candidate_coordinates` → `_context_sequences` → `_assign_ids` → `jprint` 或文本输出。

### 科学性与边界

- 该脚本是**候选扫描器**，不是评分器，也不保证候选有切割活性。
- 非 ACGT protospacer 仅警告不丢弃；下游 `guide_scoring` 会因上下文不合法而返回 unavailable。
- 线性末端 PAM 不环绕、候选 `[s,n)` 保留 n 边界，这些边界由 `tests/test_v08_dev3.py:53-106` 的 P0 坐标测试锁定。
- 环状分子允许跨原点候选，`wraps_origin` 与 segments 的一致性由 `tests/test_v08_dev3.py:58-60,87-106` 验证。

---

## scripts/guide_scoring.py

### 技术原理

模块文档（`scripts/guide_scoring.py:2-11`）明确：SpCas9 使用 Doench-2016 / Azimuth V3（真实 pickle 模型 + 真实特征）；AsCas12a 使用 DeepCpf1 / Kim 2018（真实 Keras 权重由 PyTorch 求值，34 bp 上下文语义）；LbCas12a 没有已审查模型，总是 unavailable。任何后端缺失或上下文不可用都不产生预测，而是返回 unavailable。

`APPLICABILITY_WARNINGS`（`scripts/guide_scoring.py:17-27`）记录每个核酸酶的人类可读警告：SpCas9 模型训练于哺乳动物上下文、未针对酵母验证；AsCas12a 的 DeepCpf1 只适用 AsCas12a、且只对 23 nt 候选的 PAM 近端 20 nt 评分；LbCas12a 无模型。

`MODEL_APPLICABILITY`（`scripts/guide_scoring.py:29-39`）将核酸酶映射到模型规格：

```python
"spcas9-wt": {"Doench-2016": {"backend": "azimuth",
                              "context_key": "azimuth_30mer",
                              "context_length": 30}}
"ascas12a-wt": {"DeepCpf1": {"backend": "deepcpf1",
                             "context_key": "deepcpf1_34mer",
                             "context_length": 34}}
"lbcas12a-wt": {}
```

`_run_azimuth(contexts)`（`scripts/guide_scoring.py:50-67`）在上下文为空时返回 `AZIMUTH_CONTEXT_UNAVAILABLE`；否则延迟导入 `azimuth_backend.score_30mers`，对单个 30mer 调用并包装为 `{score, score_range:[0,1], model:"Doench-2016", model_version:"Azimuth-V3", context_sequence, context_length:30, context_semantics, warnings}`。任何异常（模型文件缺失、特征代码缺失、数值失败）都降级为 `AZIMUTH_BACKEND_UNAVAILABLE: ...`（`scripts/guide_scoring.py:66-67`）。

`_run_deepcpf1(contexts, strand)`（`scripts/guide_scoring.py:70-88`）在上下文为空时返回 `DEEPCPF1_CONTEXT_UNAVAILABLE`；否则导入 `deepcpf1_model.predict_sequence_only`，包装为 `{model:"DeepCpf1", model_version:"DeepCpf1-Kim-2018", context_length:34, context_semantics:"4-upstream+TTTV-PAM+20-gRNA+6-downstream", strand_direction, warnings}`。异常同样降级为 `DEEPCPF1_BACKEND_UNAVAILABLE`。

`_heuristic_qc(sequence)`（`scripts/guide_scoring.py:91-111`）是纯序列 QC：GC 百分含量（精确到两位小数）与最长同聚物串长度；`homopolymer_risk` 判定为 `high`（≥4）、`medium`（==3）、`low`（否则）。这不是任何已发表模型，字段放在 `heuristic_qc` 中与模型评分隔离。

`score_guides(candidates, nuclease_id)`（`scripts/guide_scoring.py:114-154`）对每个候选遍历 `MODEL_APPLICABILITY`，按 backend 调用 `_run_azimuth` 或 `_run_deepcpf1`；error 非空时追加 `_unavailable(model_name, reason)`，成功时把 payload 的 `status` 设为 `available`。LbCas12a 无模型且 scores 为空时，追加 `model=None, status=unavailable, reason=no-reviewed-model-selected-for-lbcas12a`（`scripts/guide_scoring.py:136-142`）。每个结果含 `guide_id`、`on_target_scores`、`applicability_warnings`、`heuristic_qc`、`provenance`。

### 生物原理

on-target 评分回答“这条 gRNA 有多大可能产生切割活性”。Doench 2016 / Azimuth V3 是 SpCas9 活性预测的权威模型；DeepCpf1 / Kim 2018 是 AsCas12a 活性预测模型。模型不能跨核酸酶迁移：Cas9 的 PAM 与切割几何与 Cas12a 不同，因此注册表禁止把 Cas9 来源 CFD 用于 Cas12a（`references/nuclease-registry.json:79-84`）。LbCas12a 与 AsCas12a 虽然同属 Cas12a，但蛋白序列与活性决定因素不同，因此 DeepCpf1 不得自动套用到 LbCas12a（`references/crispr-model-applicability.md:10-11`）。

`_heuristic_qc` 的 GC 与同聚物串提示对应 gRNA 设计中的两条经验规则：过高 GC 影响 gRNA 合成与靶点可及性，≥4 nt 的同聚物串（尤其是 T 串）可能影响转录与 Cas 结合。这些规则在 IDT 的 gRNA 设计与合成技术说明中反复出现，但仓库将其标记为 `heuristic_qc` 而非模型分数，避免与 Doench/Kim 的定量预测混淆。该分层也是 `references/crispr-model-applicability.md` 中“软件、模型、训练上下文、适用性警告分别记录”原则的体现。

### 实现路径

`score_guides(candidates, nuclease_id)` → `_run_azimuth` / `_run_deepcpf1` → `azimuth_backend.score_30mers` / `deepcpf1_model.predict_sequence_only` → 逐候选组装 scores → 输出列表。CLI `main()`（`scripts/guide_scoring.py:157-160`）为无参自检，打印 LbCas12a 的无模型 JSON。

### 科学性与边界

- 模型预测是计算值，不等同于湿实验切割活性；报告层在 `limitations` 中固定写入“计算候选不等同于实验验证”（`scripts/generate_crispr_design_report.py:206-209`）。
- DeepCpf1 只对 23 nt 候选的 PAM 近端 20 nt 评分，完整 23 nt 候选的远端 3 nt 未进入模型；该警告随模型结果返回。
- 后端失败静默降级为 unavailable，绝不编造分数；测试 `tests/test_v08_gate_coverage.py:272-281` 以 import 异常覆盖该分支。

---

## scripts/azimuth_backend.py

### 技术原理

官方 Azimuth 2.0 是 Python 2 代码，其 scikit-learn pickle 早于现代 scikit-learn，因此本后端（`scripts/azimuth_backend.py:2-13`）采用三件套：导入 `third_party/azimuth` 的 featurization（BSD 许可）、用兼容 unpickler 加载 `saved_models/V3_model_nopos.pickle` 并捕获 GradientBoostingRegressor 树状态、用 numpy 做精确推理。分数是模型原始预测值，落在 `[0,1]`。

**路径常量**：`THIRD_PARTY = <repo>/third_party/azimuth`，`MODEL_PICKLE = THIRD_PARTY/saved_models/V3_model_nopos.pickle`（`scripts/azimuth_backend.py:21-22`）。

**兼容 unpickler**：`_CaptureTree`、`_CaptureDecisionTree`、`_CaptureGBR`、`_CaptureMean`（`scripts/azimuth_backend.py:29-68`）是仅捕获 `__setstate__` 的占位类，避免实例化已移除的 sklearn 类。`_CompatibilityUnpickler.find_class`（`scripts/azimuth_backend.py:70-81`）把 `sklearn.tree._tree.Tree`、`sklearn.tree.tree.DecisionTreeRegressor`、`sklearn.ensemble.gradient_boosting.GradientBoostingRegressor`、`MeanEstimator` 替换为捕获类，其余类交给标准 pickle。`encoding="latin1"` 兼容 Python 2 pickle 字节（`scripts/azimuth_backend.py:107-108`）。

**AzimuthPredictor 初始化**：`AzimuthPredictor.__init__(model_path=None, featurization_root=None)`（`scripts/azimuth_backend.py:87-109`）先检查模型文件存在，否则抛 `BackendUnavailable("AZIMUTH_MODEL_NOT_FOUND: ...")`；把 `third_party` 父目录加入 `sys.path` 后导入 `azimuth.features.featurization` 与 `azimuth.util`，失败抛 `AZIMUTH_FEATURIZATION_UNAVAILABLE`；随后用兼容 unpickler 加载模型并把 `self._state = self._model.state` 固定为捕获后的树状态。

**predict 特征流程**：`predict(sequences)`（`scripts/azimuth_backend.py:115-144`）要求每个序列长度 30 且只含 ACGT（错误码 `AZIMUTH_CONTEXT_LENGTH` / `AZIMUTH_CONTEXT_BASE`，`scripts/azimuth_backend.py:121-132`）。它构造 `pandas.DataFrame(columns=["30mer","Strand"])`，`Strand` 全部为 `"NA"`，并传入空的 `gene_position` 与 `pam_audit=True, length_audit=False` 调用 `featurize_data`，再经 `concatenate_feature_sets` 得到输入矩阵（`scripts/azimuth_backend.py:133-143`）。这是 Azimuth V3 的 627 特征路径（`AzimuthPredictor` docstring，`scripts/azimuth_backend.py:85`）。

**梯度提升推理**：`_gbr_predict(inputs)`（`scripts/azimuth_backend.py:146-155`）从 `state["init_"].state["mean"]` 取初始值，按 `learning_rate` 逐步累加 `estimators_` 中每棵树的预测。`_tree_predict(tree_state, inputs)`（`scripts/azimuth_backend.py:157-176`）直接操作 sklearn 树状态：`left_child`/`right_child`/`feature`/`threshold`/`values`，对每棵树走 4 层（注释说明该模型 `max_depth == 3`），向量化比较后把样本落入叶节点，返回 `values[indices,0,0]`。

`score_30mers(sequences)`（`scripts/azimuth_backend.py:182-187`）是模块级单例入口：`_PREDICTOR` 懒加载并复用。

### 生物原理

Doench 2016（DOI 10.1038/nbt.3437）在哺乳动物细胞中系统测量 SpCas9 gRNA 活性并训练 Azimuth 模型。30mer 语义为“4 bp 上游 + 20 bp protospacer + NGG PAM + 3 bp 下游”，对应注册表中 Doench-2016 的实现条目（`references/nuclease-registry.json:21-33`）。该模型是**on-target 活性**模型，不直接预测脱靶数量。梯度提升回归树在这里的生物学意义是：活性不是单个碱基的线性函数，而是位置依赖的序列特征组合；Azimuth 的 627 个特征正是从 30mer 上下文派生的位置与碱基统计量。模型输出 `[0,1]` 的活性预测，但训练物种限制使其在酵母等非哺乳动物宿主中只能作为参考排序，不能直接解释为绝对活性。

### 实现路径

`guide_scoring._run_azimuth` → `azimuth_backend.score_30mers` → `AzimuthPredictor.predict` → `featurize_data` → `concatenate_feature_sets` → `_gbr_predict` → `_tree_predict` → `numpy` 返回分数列表。

### 科学性与边界

- 模型与训练上下文见 `references/nuclease-registry.json:40-46` 与 `references/crispr-model-applicability.md:6-9`；必须带“未针对酵母验证”警告。
- 后端不重新训练模型，也不做特征工程外的加工；`third_party/azimuth/README.license` 记录 BSD 许可与 30 bp 输入语义。
- 真实模型测试受环境变量 `SNAPGENE_RUN_REAL_MODELS=1` 门控，期望分数 `0.31682680735151075`（`tests/test_v08_dev3.py:366-373`）。

---

## scripts/deepcpf1_model.py

### 技术原理

模块文档（`scripts/deepcpf1_model.py:2-15`）说明：加载 Bioconductor CRISPRseek（Artistic License 2.0）发布的 DeepCpf1 Keras 权重，用 PyTorch 求值完全相同的网络架构。输入语义为 34 bp = 4 bp 上游 + 4 bp PAM（TTTV）+ 20 bp gRNA + 6 bp 下游。sequence-only 模型输出除以 100 得 `[0,1]` 分数（匹配 CRISPRseek 的 `deepCpf1`）；chromatin-accessibility 变体输出乘以 3 再除以 100。

**路径常量**：`SEQ_WEIGHTS = third_party/deepcpf1/Seq_deepCpf1_weights.h5`，`CA_WEIGHTS = third_party/deepcpf1/DeepCpf1_weights.h5`（`scripts/deepcpf1_model.py:20-22`）。`_torch()` 与 `_h5py()`（`scripts/deepcpf1_model.py:29-42`）把依赖缺失包装为 `BackendUnavailable`。

**one-hot 编码**：`_onehot(sequences)`（`scripts/deepcpf1_model.py:45-58`）生成 `(n, 34, 4)` 矩阵，A/C/G/T 映射到 0/1/2/3 通道；长度不为 34 抛 `DEEPCPF1_CONTEXT_LENGTH`，非 ACGT 抛 `DEEPCPF1_CONTEXT_BASE`。

**sequence-only 网络**：`_SeqOnlyNet`（`scripts/deepcpf1_model.py:61-105`）架构为 `Conv1d(4,80,5)` → ReLU → `avg_pool1d(kernel=2)` → permute+flatten（1200 维）→ `Linear(1200,80)` → ReLU → `Linear(80,40)` → ReLU → `Linear(40,40)` → ReLU → `Linear(40,1)`。`_load_h5`（`scripts/deepcpf1_model.py:74-92`）读取 Keras HDF5 权重；Keras `Conv1D` 核形状 `(kernel_size, in_channels, filters)` 转置为 PyTorch `(filters, in_channels, kernel_size)`（`scripts/deepcpf1_model.py:83-87`）；全连接层权重转置为 PyTorch 行主序（`scripts/deepcpf1_model.py:88-92`）。`forward`（`scripts/deepcpf1_model.py:94-105`）注意 Keras Flatten 是 position-major，因此 permute 为 `(0,2,1)` 再 flatten（`scripts/deepcpf1_model.py:99-101`）。

**chromatin-accessibility 网络**：`_SeqCANet`（`scripts/deepcpf1_model.py:108-156`）在 sequence 分支外增加 `Linear(1,40)` 的 chromatin 分支，最终输出 `dense_out(seq_branch * ca_branch)`（`scripts/deepcpf1_model.py:146-156`）。其权重装载把 dense_1..dense_3 视为序列分支、dense_4 为 chromatin 分支、dense_5 为输出层（`scripts/deepcpf1_model.py:136-144`）。

**推理入口**：`predict_sequence_only(sequences)`（`scripts/deepcpf1_model.py:181-190`）one-hot 后 `torch.no_grad()` 前向，`raw / 100.0` 返回。`predict_with_chromatin(sequences, chromatin_accessible)`（`scripts/deepcpf1_model.py:193-206`）把 chromatin 输入扩为 `(n,1)` 并乘 100，输出 `raw * 3.0 / 100.0`；chromatin 数量不匹配抛 `DEEPCPF1_CA_LENGTH_MISMATCH`。

### 生物原理

Kim 2018（DOI 10.1038/nbt.4061）用深度学习预测 CRISPR-Cpf1（Cas12a）gRNA 活性。DeepCpf1 的 sequence-only 模型只吃 34 bp 上下文；chromatin-accessibility 变体额外吃 0/1 染色质可及性。CRISPRseek 的权重和缩放约定（/100 与 *3/100）被逐位复刻，`tests/test_v08_dev3.py:375-385` 以两个已知序列的 Bioconductor 参考分数核对：sequence-only `0.5346983`、`0.5569931`，chromatin 分支 `0.07932924`、`0.46077484`、`0.44095499`、`0.08181222`。

DeepCpf1 的 34 bp 输入语义直接来自 CRISPRseek 的 `deepCpf1` 函数：4 bp 上游 + TTTV PAM + 20 bp PAM 近端 gRNA + 6 bp 下游。Cas12a 的 23 nt spacer 中只有 PAM 近端 20 nt 进入模型，远端 3 nt 的贡献未被模型编码；因此 `guide_scoring` 对 23 nt AsCas12a 候选返回的分数应理解为“PAM 近端 20 nt 的活性预测”，这是模型的已知边界而非实现缺陷。

### 实现路径

`guide_scoring._run_deepcpf1` → `deepcpf1_model.predict_sequence_only` → `_onehot` → `_load_seq_net` → `_SeqOnlyNet.forward` → `raw/100.0`。chromatin 路径单独由 `predict_with_chromatin` 提供，当前 `guide_scoring` 不调用它，避免在没有表观数据的报告里引入不可验证假设。

### 科学性与边界

- 该模型只对 AsCas12a 适用，绝不自动套用到 LbCas12a（`references/crispr-model-applicability.md:10-11`）。
- 模型只对 23 nt 候选的 PAM 近端 20 nt 评分；`guide_scoring` 在 warnings 中明示（`scripts/guide_scoring.py:22-24`）。
- 权重文件缺失时抛 `DEEPCPF1_WEIGHTS_NOT_FOUND`；torch/h5py 缺失时抛 `DEEPCPF1_TORCH_UNAVAILABLE` / `DEEPCPF1_H5PY_UNAVAILABLE`，所有错误都由 `guide_scoring` 转成 unavailable（`tests/test_v08_gate_coverage.py:575-589`）。

---

## scripts/cas_offinder_adapter.py

### 技术原理

模块文档（`scripts/cas_offinder_adapter.py:2-20`）定义了真实 CLI 契约：

```
cas-offinder {input_filename|-} {C|G|A}[device_id(s)] {output_filename|-}
```

输入文件布局（一次运行一个 query，可选 label）：

```
<reference FASTA file or chromosome directory>
<full-length IUPAC pattern including PAM> [dna_bulge] [rna_bulge]   # 3.x
<query sequence of the same length> <max_mismatches> [label]
```

v2.4 输出列：`query  chromosome  start(0-based)  sequence  strand  mismatches`。v3.0 输出列（`##Generated` 头之后）：`id  bulge_type  crRNA  DNA  chromosome  location  direction  mismatches  bulge_size`。

**索引注册表位置**：`default_index_registry_path()`（`scripts/cas_offinder_adapter.py:34-49`）返回用户可写位置（Windows `%LOCALAPPDATA%\SnapGeneDNADesign\cas-offinder-index-registry.json`，其他平台 `$XDG_STATE_HOME` 或 `~/.local/state`），绝不在源码树内写索引。可用环境变量 `CAS_OFFINDER_REGISTRY` 覆盖。

**搜索规则**：`NUCLEASE_SEARCH_RULES`（`scripts/cas_offinder_adapter.py:58-77`）固定三个核酸酶的 PAM/长度。`search_rules(nuclease_id, parameters=None)`（`scripts/cas_offinder_adapter.py:272-283`）允许参数覆盖 `pam_side`/`pam_pattern`/`pam_length`/`spacer_length`，未知核酸酶抛 `CAS_OFFINDER_UNSUPPORTED_NUCLEASE`。

**输入文本构造**：`build_input_text(query_sequence, nuclease_id, parameters)`（`scripts/cas_offinder_adapter.py:286-317`）校验 query 长度等于 spacer 长度（`QUERY_LENGTH_MISMATCH`）、只含 IUPAC 碱基（`QUERY_CONTAINS_UNSUPPORTED_BASES`）；3' PAM 时 `pattern = "N"*spacer_length + pam_pattern`，query 补 `"N"*pam_length` 在 3' 端；5' PAM 时 `pattern = pam_pattern + "N"*spacer_length`，query 补 PAM 在 5' 端（`scripts/cas_offinder_adapter.py:297-309`）。这样 PAM 列由 pattern 强制，query 的 PAM 位置为 `N`，错配计数只落在 protospacer 内。`dna_bulge`/`rna_bulge` 非零时追加到 pattern 行（`scripts/cas_offinder_adapter.py:310-316`）。

**检测**：`detect(executable=None)`（`scripts/cas_offinder_adapter.py:91-141`）先用 `shutil.which` 查找 `cas-offinder`/`cas-offinder.exe`；Cas-OFFinder 没有 `--version` 开关，所以用无参调用捕获 banner，经 `_normalise_version`（`scripts/cas_offinder_adapter.py:80-88`）提取 `2.4.1` 之类版本号；banner 含 `Available device list` 且 `Type: GPU|CPU` 时标记 `opencl_detected`。未找到返回结构化 `installed=False`。

**参考基因组绑定**：`genome_record(fasta_path, annotation_path=None, ...)`（`scripts/cas_offinder_adapter.py:155-208`）对 FASTA 缺失返回 `REFERENCE_FASTA_NOT_FOUND`，注释缺失返回 `REFERENCE_ANNOTATION_NOT_FOUND`；正常时用 `_read_fasta_stats`（`scripts/cas_offinder_adapter.py:144-152`，Bio.SeqIO 解析）记录 `sequence_count`、`total_length` 与 `fasta_sha256`。`load_index_registry`/`save_index_registry`（`scripts/cas_offinder_adapter.py:211-225`）管理注册表。`check_reference_binding`（`scripts/cas_offinder_adapter.py:228-250`）按 FASTA SHA-256 比较，缺失为 `unbound`，哈希不符为 `stale`；`record_reference_binding`（`scripts/cas_offinder_adapter.py:253-269`）搜索成功后写入绑定。

**输出解析**：`parse_output(text, query_sequence=None, pattern=None)`（`scripts/cas_offinder_adapter.py:320-386`）：

- 丢弃空行与 `#` 开头行（含 v3 的 `##Generated` 与列头 `#Id...`）。
- 6 列视为 v2.4 无 label；7 列且首列非数字视为 v2.4 带 label；≥9 列视为 v3.0（`scripts/cas_offinder_adapter.py:333-347`）。
- 任何坐标非整数、负坐标、未知 strand、空 hit 序列、非整数 bulge_size 都返回 `EXTERNAL_OUTPUT_PARSE_ERROR`（`scripts/cas_offinder_adapter.py:348-365`）。
- `reference_span = len(dna.replace("-",""))`，即 bulge 对齐中 `-` gap 不占参考跨度；`end = start + reference_span`（`scripts/cas_offinder_adapter.py:369-375`）。
- `bulge_type` 在非 `X` 时保留（`X` 表示无 bulge，规范化为 `None`），`bulge_size` 从 v3 第 9 列读取（`scripts/cas_offinder_adapter.py:347-350,366`）。
- `_mismatch_positions`（`scripts/cas_offinder_adapter.py:389-412`）优先读输出序列中的小写碱基（Cas-OFFinder 用小写标错配），bulge 对齐含 gap 列时只使用小写标记，不做逐列比较；否则与 query 逐列比较佐证。
- `_infer_pam_side`（`scripts/cas_offinder_adapter.py:415-428`）从 pattern 判断 PAM 侧，缺省 3prime（历史布局）。
- `_extract_pam`（`scripts/cas_offinder_adapter.py:431-437`）从去 gap 序列按 PAM 侧提取 5' 端 4 bp 或 3' 端 3 bp PAM。

**搜索主函数**：`search_offtargets(query_sequence, reference_fasta, parameters, executable=None, timeout=120, device="C0", nuclease_id="spcas9-wt", annotation_path=None, registry_path=None, rebuild_stale=True)`（`scripts/cas_offinder_adapter.py:440-591`）：

1. 构造 `genome_record`；参考未就绪返回 failed（`scripts/cas_offinder_adapter.py:449-464`）。
2. `check_reference_binding` 为 `stale` 且 `rebuild_stale=False` 时返回 failed/stale（`scripts/cas_offinder_adapter.py:465-479`）。
3. 构造输入文本与 pattern；错误转 `_failed_payload`（`scripts/cas_offinder_adapter.py:480-488`）。
4. `detect` 未安装返回 unavailable（`scripts/cas_offinder_adapter.py:489-499`）。
5. 请求 bulge 但检测到 2.x 返回 `CAS_OFFINDER_BULGE_UNSUPPORTED`（`scripts/cas_offinder_adapter.py:500-505`）。
6. `_run_cas_offinder_cli`（`scripts/cas_offinder_adapter.py:594-632`）执行真实 CLI；返回码非 0 返回 `CAS_OFFINDER_EXECUTION_FAILED`；stderr 含 `non-acceptable` 或 `Skipping non-acceptable file` 返回 `CAS_OFFINDER_REFERENCE_EXTENSION_UNSUPPORTED`（`scripts/cas_offinder_adapter.py:506-527`）。
7. 输出文件为空或不存在返回 incomplete（`CAS_OFFINDER_EMPTY_OUTPUT`），并注明“可能是真零 hit，也可能是后端静默失败，必须人工复核”（`scripts/cas_offinder_adapter.py:528-541`）。
8. `parse_output` 成功后 `record_reference_binding`，组装 complete 结果；检测到 3.x 时 `experimental_backend=True`、`production_ready=False` 并带交叉验证警告（`scripts/cas_offinder_adapter.py:542-575`）。
9. `finally` 删除输出临时文件（`scripts/cas_offinder_adapter.py:584-590`）。

**非 ASCII 路径安全**：`_run_cas_offinder_cli`（`scripts/cas_offinder_adapter.py:594-632`）注释说明 Cas-OFFinder 2.x 用 ANSI 代码页解析文件参数，而 Python 以 UTF-8 写输入文件，含中文的绝对路径会失败。稳健形式是保持所有参数为相对路径：工作目录设为 FASTA 所在目录，输入文件第一行只写 FASTA 文件名（`scripts/cas_offinder_adapter.py:605-611`）。若 FASTA 文件名含非 ASCII，则在参考目录复制为 ASCII 临时名并在 `finally` 删除（`scripts/cas_offinder_adapter.py:612-631`）。`_invoke_cli`（`scripts/cas_offinder_adapter.py:636-652`）以 `subprocess.run([exe, input_name, device, output_name], cwd=..., ...)` 调用，并在 finally 删除输入文件。这一契约由 `tests/test_v08_dev3.py:300-358` 的 fake binary 测试和 `tests/test_v08_dev3.py:433-455` 的真实二进制非 ASCII 路径测试验证。

### 生物原理

Cas-OFFinder 是 OpenCL 加速的 CRISPR/Cas off-target 搜索工具（Cas-OFFinder GitHub，https://github.com/snugel/cas-offinder）。它把 gRNA 全长模式（含 PAM）与参考基因组比对，支持错配与 bulge。bulge 语义按 Cas-OFFinder 输入输出定义：`dna_bulge` 表示目标 DNA 相对 gRNA 多碱基（DNA 凸起），`rna_bulge` 表示 gRNA 相对目标 DNA 多碱基（RNA 凸起，等价于目标 DNA 缺失）。v3 输出的 `bulge_type` 为 `DNA`/`RNA`（无 bulge 记 `X`），`bulge_size` 为凸起碱基数。适配器只做透传与规范化，不改变 Cas-OFFinder 的生物学定义。

### 实现路径

`search_offtargets` → `genome_record` → `check_reference_binding` → `search_rules` → `build_input_text` → `detect` → `_run_cas_offinder_cli` → `_invoke_cli` → `parse_output` → `_mismatch_positions`/`_infer_pam_side`/`_extract_pam` → `record_reference_binding` → complete/failed/unavailable payload。

### 科学性与边界

- v3.0.0 beta 为实验后端：结果 `production_ready=False`，必须与 v2.x 或独立脱靶工具交叉核对（`scripts/cas_offinder_adapter.py:560-568`）。
- 空输出不自动判零 hit，标记 `incomplete` 供人工复核（`scripts/cas_offinder_adapter.py:528-541`）。
- 2.x 不支持 bulge；3.x 支持但实验性。两种限制都以结构化 reason 返回，不静默降级。
- 输出 `start` 是 0-based 起点，适配器统一转 `[start, start+reference_span)`；bulge 对齐的 gap 不占参考跨度。

---

## scripts/annotate_offtargets.py

### 技术原理

模块文档（`scripts/annotate_offtargets.py:2-8`）明确：hit 与 feature 的注释关系是**区间重叠**（`hit_start < feature_end and feature_start < hit_end`），不是“hit 起点落在 feature 内”。

`feature_type_for(feature)`（`scripts/annotate_offtargets.py:20-36`）把 GenBank feature type 归并为 `CDS`、`gene`、`promoter`、`regulatory`、`tRNA`、`rRNA`、`ncRNA`（`ncRNA`/`misc_RNA`）、`unknown`。

`_location_segments(location, sequence_length)`（`scripts/annotate_offtargets.py:47-63`）把 Biopython location（含 CompoundLocation）展开为 0-based 半开 segments；`end < start` 判定环绕，拆为 `[[start, sequence_length], [0, end]]`，对 `start==sequence_length, end==0` 的边缘零长段返回空。`_hit_segments(hit, sequence_length)`（`scripts/annotate_offtargets.py:66-78`）对 hit 做同样展开。`_overlaps(segments_a, segments_b)`（`scripts/annotate_offtargets.py:81-84`）是严格半开区间相交，`[0,1]` 与 `[1,2]` 不相交。

`annotate_hits(hits, annotation_path, target_gene=None)`（`scripts/annotate_offtargets.py:105-155`）：

1. 读入 GenBank 记录列表。
2. 按 hit 的 `chromosome` 匹配 `record.id` 或 `record.name`（`scripts/annotate_offtargets.py:110-114`）。
3. 对命中的染色体，计算 hit segments，遍历 features 计算 feature segments 并判重叠；保留全部 `overlapping_features`，每条含 `feature_type`、`feature_name`、`feature_strand`、`feature_start/end`、`wraps_origin`、`orientation_to_hit`（`scripts/annotate_offtargets.py:116-132`）。
4. 无重叠时写入 `intergenic`，并计算 `is_additional_perfect_match`（`scripts/annotate_offtargets.py:134-141`）。
5. 有重叠时按 `_PRIORITY`（`gene:0, CDS:1, promoter:2, regulatory:3, ncRNA:4, tRNA:5, rRNA:6, unknown:7`，`scripts/annotate_offtargets.py:101-102`）排序取主 feature；`is_target_gene` 为 `target_gene` 与任一 overlapping feature 名匹配；`is_additional_perfect_match` 要求 `mismatches==0`、`not bulge_size`、`bulge_type in (None, "X")`（`scripts/annotate_offtargets.py:143-154`）。

`_feature_name`（`scripts/annotate_offtargets.py:87-92`）按 `label`、`gene`、`locus_tag`、`product` 优先级取名。`_orientation`（`scripts/annotate_offtargets.py:95-98`）比较 hit strand（`+/-`）与 feature strand（`1/-1`），返回 `same`/`opposite`/`unknown`。

CLI `main()`（`scripts/annotate_offtargets.py:158-194`）读取 hits JSON、调用 `annotate_hits`，输出含 `schema_version`、`status`、`reference_genome`、`hits`、`provenance`（原 payload provenance 加 annotate 条目）。

### 生物原理

脱靶位点的生物学意义取决于它与基因组 feature 的相对位置：落在 CDS 内的脱靶可能改变蛋白编码，落在启动子/调控区的脱靶可能影响表达。重叠而非包含的判据（`hit_start < feature_end and feature_start < hit_end`）保证跨越 CDS 边界或跨基因间区的 hit 不会被漏判。环状基因组（如细菌染色体、线粒体、质粒）的跨原点 feature 需要拆段判断，因此 `_location_segments` 与 `_hit_segments` 都把环绕区间展开为 `[[start, n], [0, end]]`。

`orientation_to_hit` 为 `same` 表示脱靶切割与该 feature 在同一条链上，`opposite` 表示相反链；对启动子/调控区而言，同向/反向的生物学后果不同，但本脚本只做客观标注，不推断后果等级。`is_additional_perfect_match` 仅对错配 0、无 bulge 的额外位点标 `true`，这类位点在实验上几乎等价于目标位点本身，是脱靶复核的最高优先级对象。BioPython `SeqFeature.location` 的 `CompoundLocation` 与跨原点语义是这里的解析基础；`sg_common.topology` 的保守默认线性也影响参考序列长度参数，但 `annotate_hits` 直接使用 `len(record.seq)` 作为环状展开边界（`scripts/annotate_offtargets.py:114`）。

### 实现路径

CLI `main` → `annotate_hits` → Bio.SeqIO 读 GenBank → `_hit_segments` / `_location_segments` / `_overlaps` / `feature_type_for` / `_feature_name` / `_orientation` → 按优先级排序 → 写回 `hit["annotation"]`。

### 科学性与边界

- 注释质量完全取决于参考 GenBank 的 feature 质量；不匹配染色体的 hit 记为 `intergenic`，但实际可能是“参考记录缺失”，因此报告仍要求人工复核。
- `is_additional_perfect_match` 严格排除任何 bulge 命中（`bulge_size=0` 且 `bulge_type in (None,"X")`），避免把 bulge 命中误标为完美匹配（`tests/test_v08_dev3.py:219-246` 覆盖重叠语义）。

---

## scripts/generate_crispr_design_report.py

### 技术原理

模块文档（`scripts/generate_crispr_design_report.py:2-7`）说明：JSON 与 Markdown 携带相同核心内容；中间失败生成结构化 failed 报告（当请求输出路径时写盘）并返回非零退出码。

`_input_records(paths)`（`scripts/generate_crispr_design_report.py:26-37`）对每个输入文件记录 `path`、`sha256`（`provenance.sha256_of_file`）、`size`；不存在时 `sha256=None`。`_merge_hits(search_results)`（`scripts/generate_crispr_design_report.py:40-55`）把多个 gRNA 的搜索结果按 `(chromosome, start, end, strand, sequence)` 去重，并用 `query_guide_ids` 记录哪些候选命中同一脱靶位点。

`_offtarget_analysis(record, candidates, args)`（`scripts/generate_crispr_design_report.py:58-140`）：

- 无 `--reference-fasta` 时返回 unavailable，reason `no-complete-reference-genome-provided`（`scripts/generate_crispr_design_report.py:59-66`）。
- 先 `offinder_detect` 检查二进制，未安装返回 unavailable（`scripts/generate_crispr_design_report.py:67-76`）。
- 对前 `max_offtarget_candidates` 个候选（默认 50）构造 query；query 为空或含非 ACGT 碱基则跳过（`scripts/generate_crispr_design_report.py:84-87`）。
- 逐候选调用 `search_offtargets`，捕获 `ValueError/OSError` 转 failed（`scripts/generate_crispr_design_report.py:88-103`）。
- `_merge_hits` 去重后，若给 `--annotation` 则调用 `annotate_hits`（`scripts/generate_crispr_design_report.py:104-118`）。
- 状态聚合：任一 failed → failed/`CAS_OFFINDER_PARTIAL_FAILURE`；无状态 → incomplete/`NO_SCORABLE_GUIDE_QUERIES`；全部 complete → complete；其他 → incomplete/`OFFTARGET_SEARCH_NOT_COMPLETE`（`scripts/generate_crispr_design_report.py:119-131`）。

`make_report(target_path, nuclease, fragment_paths=None, protocol_source_path=None, off_target_options=None)`（`scripts/generate_crispr_design_report.py:143-220`）是核心编排：

1. `load_seq(target_path)` → `scan_guides(record, nuclease)` → `score_guides(candidates, nuclease)`（`scripts/generate_crispr_design_report.py:146-148`）。
2. 对每个 fragment 路径 `load_seq` 后 `characterize_fragment`（`scripts/generate_crispr_design_report.py:149-152`）。
3. `protocol_evidence.load_sources` → `recommend_protocol.recommend(fragments, sources)`（`scripts/generate_crispr_design_report.py:153-154`）。
4. 把 `off_target_options` 转成 `argparse.Namespace` 并补 `nuclease`，调用 `_offtarget_analysis`（`scripts/generate_crispr_design_report.py:156-162`）。
5. 收集 `available_scores` 与 `partial_reasons`：on-target 无可用模型、off-target 非 complete、协议 unavailable、无反应 profile 均写入 partial_reasons（`scripts/generate_crispr_design_report.py:164-175`）。
6. `unfinished_analysis` 固定包含 `primer-specificity` 与 `wet-lab-validation`；on-target 无分或 off-target 未完成时再追加对应项（`scripts/generate_crispr_design_report.py:177-182`）。
7. 状态：on-target 可用分 + off-target complete + 有 fragment 时为 `complete`，否则 `partial`（`scripts/generate_crispr_design_report.py:184-189`）。
8. 报告体含 `schema_version`、`status`、`task_summary`、`partial_reasons`、`inputs`、`nuclease`、`guide_candidates`、`on_target.candidates`、`off_target`、`reaction_profiles`、`protocol_recommendation`、`sequence_upload`（默认全部 denied）、`unfinished_analysis`、`limitations`、`human_review_required`、`provenance`（`scripts/generate_crispr_design_report.py:191-219`）。

`_failed_report(error, target_path=None, nuclease=None, args=None)`（`scripts/generate_crispr_design_report.py:223-251`）生成失败报告：`status=failed`，`partial_reasons=[str(error)]`，空候选与空分析块，provenance 为 `unavailable`/`failed`。

`_markdown(report)`（`scripts/generate_crispr_design_report.py:254-331`）把报告渲染为 Markdown：标题、状态、候选列表（含 on-target 分数或 unavailable reason）、off_target 前 20 条、反应 profile、协议推荐、序列上传状态、未完成分析、限制与人工复核项。

`_write_design_files(record, out_dir, stem)`（`scripts/generate_crispr_design_report.py:334-348`）从 `write_dna` 导入 `_ensure_annotations`、`_snapgene_annotated`、`write_native_dna`，写出 `.gb`（SnapGene 兼容 GenBank）、`.fa`、`.dna`（sgffp 原生 SnapGene），返回三种格式路径。

CLI `main()`（`scripts/generate_crispr_design_report.py:351-401`）参数为：`target`、`--nuclease`（必填）、`--fragments`、`--protocol-evidence`、`--out-json`、`--out-markdown`、`--out-dir`、`--reference-fasta`、`--annotation`、`--target-gene`、`--cas-offinder`、`--offinder-device`（默认 `C0`）、`--mismatches`（默认 3）、`--dna-bulge`/`--rna-bulge`（默认 0）、`--max-offtarget-candidates`（默认 50）、`--rebuild-stale-index`（默认 True）。`make_report` 成功则 `failed=False`；任何异常进入 `_failed_report` 并置 `failed=True`。`--out-dir` 生成序列文件，失败只追加 `partial_reasons` 不影响主报告状态。最后写 JSON/Markdown，打印报告，失败时返回 1。

### 生物原理

CRISPR 设计交付物必须同时回答三问：候选在哪里（guide_candidates）、活性如何（on_target）、脱靶风险如何（off_target）。统一报告还附带反应 profile 与协议推荐，用于后续 gRNA 合成与供体修复模板扩增。报告把 `wet-lab-validation` 永远列入 `unfinished_analysis`，因为计算工具无法替代实验验证；`human_review_required` 永远包含 gRNA 排序、脱靶位点生物学意义与协议复核。这与 Sambrook & Russell 对分子克隆实验中“预测必须经实验确认”的一般原则一致，也与 NEB/IDT 官方协议中“反应条件须以最终实验为准”的免责口径一致。

### 实现路径

`main` → `make_report`（`load_seq` → `scan_guides` → `score_guides` → `characterize_fragment` → `load_sources` → `recommend` → `_offtarget_analysis`）→ `_markdown` / `_write_design_files` → 写盘打印。异常路径 `main` → `_failed_report` → 写盘返回 1。

### 科学性与边界

- 报告输出不通过 Schema 实时校验，但结构与 `schemas/crispr-design-report-v0.8.json` 一致（`additionalProperties:false`，必填字段见下）。
- 对未知核酸酶的 CLI 失败报告测试：`tests/test_v08_dev3.py:391-405`。
- 三种输出格式（`.gb`/`.fa`/`.dna`）的序列一致性测试：`tests/test_v08_dev3.py:407-431`。

---

## scripts/crispor_adapter.py

### 技术原理

`crispor_adapter.py` 是 CRISPOR 外部适配骨架（`scripts/crispor_adapter.py:2-8`）：不捆绑 CRISPOR 源码、二进制、模型或第三方凭据；只检测本地安装，捕获版本与许可提示；只有经 `sequence_upload_consent` 的显式逐次上传同意后才可能提交查询。

`detect(executable=None)`（`scripts/crispor_adapter.py:22-47`）用 `shutil.which` 探测 `crispor`/`crispor.py`，本版本不实现本地 CRISPOR 执行；探测结果含 `installed`、`executable`、`version`、`license_notice.url`（`https://github.com/maximilianh/crisporWebsite/blob/master/LICENSE.txt`，`scripts/crispor_adapter.py:17-19`）、provenance。

`online_query_request(target_sequence, organism, purpose)`（`scripts/crispor_adapter.py:50-55`）只构造 `SequenceUploadConsent("target-region").request(CRISPOR_URL, purpose, sequence=target_sequence, retention_notice=True)` 并返回 consent 对象，**不执行任何上传**。

### 生物原理

CRISPOR 是外部 gRNA 设计与脱靶分析工具（https://crispor.org）。外部查询涉及把目标序列上传到第三方服务器，因此必须遵守知情同意与最小披露：`sequence_upload_consent` 默认拒绝上传，批准后只存 `sequence_sha256` 不存全长序列（`scripts/sequence_upload_consent.py:2-9`）。授权是一次一票的绑定收据，destination/purpose/sequence/scope 任一不匹配即拒绝（`scripts/sequence_upload_consent.py:92-126`）。

### 实现路径

`online_query_request` → `SequenceUploadConsent.request`（绑定请求）→ 调用方 `approve()` → `allowed(destination, purpose, sequence, scope)` 逐项比对 → 一次消费。当前报告生成器不使用 CRISPOR，只保留适配层与测试（`tests/test_v08_gate_coverage.py:841` 起）。

### 科学性与边界

- 本地未安装 CRISPOR 时 `installed=False`，显式 unavailable，不伪造在线结果。
- `license_notice.status` 为 `user-must-review`，许可合规留给用户。
- 默认不上传；`sequence_upload_consent` 的拒绝与单次消费逻辑由 `tests/test_v08_guides.py:89-103` 与 `tests/test_v08_dev3.py:107-149` 锁定。

---

## scripts/recommend_protocol.py

### 技术原理

模块文档（`scripts/recommend_protocol.py:2-8`）：推荐只有在 reaction profile 命中证据源的 `applicable_to` 标签时才给出；每条匹配理由都写明实际命中的 profile 字段与观测值；无匹配的 profile 返回 `insufficient_evidence`，绝不给出产品名。

`_category_for(profile)`（`scripts/recommend_protocol.py:24-49`）把客观反应特征映射到证据类别：`reaction_type` 为 `assembly`/`gibson`/`nebuilder` 等 → `assembly`；`reaction_type` 为 `pcr` 等 → `pcr`；`assembly_method` 为 gibson/nebuilder 类 → `assembly`；`template_type` 为 PCR 模板类 → `pcr`；`high_fidelity_required` 为真 → `pcr`；存在 5' 尾 → `pcr`；`specificity_checked is True` → `pcr`。

`_source_matches(category, profile, item)`（`scripts/recommend_protocol.py:52-76`）：PCR 类先匹配 `high-fidelity-cloning-pcr`；再匹配 `high-gc-pcr`，此时要求 `gc_percent >= 60.0` 且把观测值写进理由。assembly 类匹配 `gibson-like-assembly` 或 `nebuilder-hifi`。

`_pick_source(category, profile, sources)`（`scripts/recommend_protocol.py:79-87`）按 sources 顺序取第一个匹配源。`recommend(profiles, protocol_sources=None)`（`scripts/recommend_protocol.py:90-166`）：

- 无 profiles → unavailable/`NO_REACTION_PROFILES_PROVIDED`（`scripts/recommend_protocol.py:93-104`）。
- 无 sources → unavailable/`PROTOCOL_SOURCE_NOT_FOUND`（`scripts/recommend_protocol.py:105-114`）。
- 逐 profile 推荐：无匹配 → `status=insufficient_evidence`、`recommended_system=None`、`evidence_level=none`、`human_review_required=True`；有匹配 → `status=compatible_candidate`，`recommended_system` 为 `Q5 High-Fidelity DNA Polymerase`（当证据含 `high-fidelity-cloning-pcr`）或 `NEBuilder HiFi DNA Assembly`（`scripts/recommend_protocol.py:148-152`）。
- 整体状态：全部匹配 `available`，部分匹配 `partial`，无匹配 `unavailable`/`NO_PROFILE_MATCHED_EVIDENCE`（`scripts/recommend_protocol.py:159-166`）。

### 生物原理

证据文件 `references/protocol-evidence-dev2.json` 只包含两条从厂商页面读取的协议：NEB Q5 High-Fidelity DNA Polymerase（`M0491`，适用 `high-fidelity-cloning-pcr` 与 `high-gc-pcr`）与 NEB NEBuilder HiFi DNA Assembly（`E2621`，适用 `gibson-like-assembly`/`nebuilder-hifi`）。NEBuilder 是 Gibson 组装的商业化形式，其原理来自 Gibson 2009（DOI 10.1038/nmeth.1318）；Type IIS/Golden Gate 组装原理见 Engler 2008（DOI 10.1371/journal.pone.0003647），本章的 assembly profile 仅标记 `assembly_method=gibson` 时匹配 NEBuilder，不自动推断 Golden Gate。推荐不发明温度、时间、缓冲液与体积；所有条件必须来自当前官方协议（`references/protocol-recommendation.md`）。

在 CRISPR 供体修复模板场景中，`recommend_protocol` 的作用是把 `characterize_reaction` 的客观特征（GC、高保真要求、组装方法）映射到官方试剂。高 GC 模板的扩增常需高保真聚合酶与 GC 增强剂，这正是 `_source_matches` 对 `high-gc-pcr` 分支检查 `gc_percent >= 60.0` 的生物学理由（`scripts/recommend_protocol.py:60-69`）。Gibson 组装对末端同源臂的依赖（Gibson 2009）决定 NEBuilder 只在 profile 明示 `gibson-like-assembly`/`nebuilder-hifi` 特征时被推荐；PCR 扩增供体片段则匹配 Q5。Takara 与 IDT 的官方方案在仓库中未作为证据加载，因此不会出现在推荐结果里；这是来源门控的直接后果：只推荐已登记、已读页、可追溯的厂商协议。

### 实现路径

`recommend_protocol.main`（`scripts/recommend_protocol.py:169-188`）读取 `--profile` JSON 的 `reaction_profiles`，或默认 `[{"fragment_id":"no-profile"}]`，`protocol_evidence.load_sources` 加载证据后调用 `recommend`。

### 科学性与边界

- `recommended_system` 是“兼容候选”（`compatible_candidate`），不是首选保证；`human_review_required=True` 永远保留。
- 高 GC PCR 只有在 `gc_percent >= 60.0` 时匹配；低 GC 只匹配 Q5 高保真 PCR 类。测试：`tests/test_v08_dev3.py:185-216`、`tests/test_v08_gate_coverage.py:304-327`。

---

## scripts/characterize_reaction.py

### 技术原理

模块文档（`scripts/characterize_reaction.py:2-7`）：该脚本只生成客观反应特征表，不推荐试剂，不发明实验条件。

`_windows(seq, width=40, step=10)`（`scripts/characterize_reaction.py:19-20`）生成长度 40、步长 10 的滑窗；序列不足 40 时返回整序列单窗。`characterize_fragment(record, fragment_id)`（`scripts/characterize_reaction.py:23-47`）返回：

| 字段 | 含义 | 实现 |
|---|---|---|
| `fragment_id` | 片段名，默认路径 stem | 参数 |
| `source` | 记录 id/name | `record.id or record.name` |
| `template_type` | 固定 `"unknown"`，不猜测模板类型 | 27 |
| `length` | 序列长度 | 31 |
| `topology` | `linear`/`circular`，来自 `sg_common.topology` | 32 |
| `gc_percent` | 全序列 GC% | `gc_fraction`，33 |
| `gc_5prime_40` / `gc_3prime_40` | 前/后 40 bp GC% | 34-35 |
| `max_local_gc_window_40` | 40 bp 滑窗最大 GC% | 36 |
| `homopolymer_runs` | ≥6 bp 同聚物串列表 | `_homopolymer_runs`，37 |
| `predicted_difficulty` | 固定 `"not_scored"` | 38 |
| `high_fidelity_required` / `five_prime_tail` / `assembly_method` | 固定 `"unknown"` | 39-41 |
| `specificity_checked` | 固定 `False` | 42 |
| `provenance` | 结构化来源 | 43-46 |

`_homopolymer_runs(seq, threshold=6)`（`scripts/characterize_reaction.py:50-66`）返回 `[{base, length}]`，只记录 ≥6 bp 的连续同聚物串。

### 生物原理

PCR 扩增的难度与模板 GC 含量、两端 GC 平衡、同聚物串长度有关。高 GC 模板需要专门缓冲液或增强剂（如 NEB Q5 High-GC Enhancer，证据见 `references/protocol-evidence-dev2.json`）；5' 与 3' 末端 GC 失衡影响引物结合，因此分别记录 `gc_5prime_40` 与 `gc_3prime_40`。这些特征被 `recommend_protocol._source_matches` 用于高 GC PCR 判定。脚本故意不计算 Tm、不发夹/二聚体评分：引物热力学应依据 Primer3 官方手册（https://primer3.org/manual.html），在本仓库中由第 2 章的引物模块负责；本章只描述模板片段，不做引物级计算。

### 实现路径

`characterize_reaction.main`（`scripts/characterize_reaction.py:69-89`）接受多个片段路径，逐文件 `load_seq` 后 `characterize_fragment`，输出 `reaction_profiles` 与 `generated_at`。

### 科学性与边界

- `template_type`/`high_fidelity_required`/`assembly_method` 等字段保持 `unknown`，等待下游或用户提供，绝不臆测。
- 同聚物串阈值 6 bp 是仓库约定，不是文献切割阈值；输出不解释其风险等级。
- 环状片段 profile 的 `topology` 正确透传（`tests/test_v08_gate_coverage.py:338-342`）。

---

## v2/v3 输入输出列格式与 bulge 语义

### Cas-OFFinder 输入文件格式

适配器 `build_input_text` 生成的输入体为：

```text
<FASTA 文件名>
<全长 IUPAC pattern> [dna_bulge rna_bulge]
<query 序列> <mismatches> <label>
```

示例（SpCas9，20 nt protospacer，mismatches≤3）：

```text
ref.fa
NNNNNNNNNNNNNNNNNNNNNGG
GCATCGATCGATCGATCGTA 3 query1
```

Cas12a（TTTV + 23 nt，5' PAM）时 pattern 行为 `TTTV` 后接 23 个 `N`，query 行为 4 个 `N` 后接 23 nt protospacer（即 `"N"*pam_length + query`）。具体由 `build_input_text` 生成：5' PAM 时 pattern 为 `pam_pattern + "N"*spacer_length`，query 为 `"N"*pam_length + query`（`scripts/cas_offinder_adapter.py:297-309`）。查询行的 PAM 位置为 `N`，保证错配只统计在 protospacer。

### v2.4 输出列

Cas-OFFinder 2.4.1 输出为无表头 TSV：

```text
<query>  <chromosome>  <start(0-based)>  <sequence>  <strand>  <mismatches>
```

若输入文件含 label，则 label 追加为第 7 列。`parse_output` 对 6 列按无 label 处理，7 列且首列非数字按有 label 处理（`scripts/cas_offinder_adapter.py:333-342`）。序列中小写碱基为 Cas-OFFinder 的错配标记，适配器据此计算 `mismatch_positions`。

### v3.0 输出列

Cas-OFFinder 3.0.0 beta 先输出 `##Generated by Cas-OFFinder 3.0.0`，再输出 `#Id  Bulge Type  crRNA  DNA  Chromosome  Location  Direction  Mismatches  Bulge Size` 表头与数据行：

```text
##Generated by Cas-OFFinder 3.0.0
#Id	Bulge Type	crRNA	DNA	Chromosome	Location	Direction	Mismatches	Bulge Size
q1	DNA	GCATCGATCGATCGATCGTAANN	GCATCGATCGAAATCGATCGTAAGG	chrI	11	+	0	2
```

`parse_output` 跳过所有 `#` 行，取前 8 列，第 9 列解析为 `bulge_size`（`scripts/cas_offinder_adapter.py:343-350`）。

解析后的统一 hit 字段与两种输出列的对应关系：

| 解析后字段 | v2.4 来源列 | v3.0 来源列 | 说明 |
|---|---|---|---|
| `chromosome` | 第 2 列 `chromosome` | 第 5 列 `Chromosome` | 取 split 后首段，容忍带空格的染色体名 |
| `start` | 第 3 列（0-based） | 第 6 列 `Location`（0-based） | 保持 0-based，不转 1-based |
| `end` | `start + len(sequence)` | `start + len(DNA 去 gap)` | bulge gap 不占参考跨度 |
| `strand` | 第 5 列 `+/-` | 第 7 列 `Direction` | 只接受 `+`/`-` |
| `sequence` | 第 4 列 | 第 4 列 `DNA` | 大写保存，小写用于错配标记 |
| `mismatches` | 第 6 列 | 第 8 列 `Mismatches` | 整数 |
| `mismatch_positions` | 小写碱基位置 + query 列比对 | 小写碱基位置（bulge 时仅此） | 0-based，位于 hit 序列内 |
| `pam` | `_extract_pam` 按 PAM 侧取 3' 3 bp 或 5' 4 bp | 同左 | 从去 gap 序列提取 |
| `bulge_type` | `None` | 第 2 列 `Bulge Type`，`X` 规范为 `None` | `DNA`/`RNA` |
| `bulge_size` | `0` | 第 9 列 `Bulge Size` | 非整数报解析错误 |
| `query_guide_ids` | 报告层 `_merge_hits` 合并时追加 | 同左 | 记录哪些候选命中该位点 |

### bulge 语义

- `dna_bulge` / `rna_bulge` 参数只对 Cas-OFFinder 3.x 有意义；对 2.x 返回 `CAS_OFFINDER_BULGE_UNSUPPORTED`（`scripts/cas_offinder_adapter.py:500-505`）。
- 按 Cas-OFFinder 约定：`dna_bulge` 表示目标 DNA 链相对 gRNA 有额外碱基（DNA bulge），`rna_bulge` 表示 gRNA 相对目标 DNA 有额外碱基（RNA bulge，等价于目标 DNA 缺失）。
- v3 输出 `bulge_type` 取值 `DNA`/`RNA`，无 bulge 记 `X`；适配器把 `X` 规范化为 `None`（`scripts/cas_offinder_adapter.py:366`）。
- bulge 对齐中的 gap 列（`-`）不占参考跨度：`reference_span = len(dna.replace("-",""))`（`scripts/cas_offinder_adapter.py:371`）。
- `annotate_offtargets` 的完美匹配判定排除一切 bulge 命中：`mismatches==0 and not bulge_size and bulge_type in (None,"X")`（`scripts/annotate_offtargets.py:139,152`）。

解析契约测试：`tests/test_v08_dev2.py:115-148`（v2.4 6/7 列与 v3.0 9 列）与 `tests/test_v08_dev3.py:457-479`（真实 3.x bulge 端到端）。

---

## 关键数据结构示例

以下示例均取自真实代码路径的字段集合，便于开发者在阅读各脚本小节前建立全局形状。

`design_guides.scan_guides` 返回的候选对象（省略 provenance 细节）：

```json
{
  "id": "gRNA-001",
  "nuclease": "spcas9-wt",
  "strand": "forward",
  "protospacer_sequence": "GCATCGATCGATCGATCGTA",
  "protospacer_reference_sequence": "GCATCGATCGATCGATCGTA",
  "pam_sequence": "AGG",
  "pam_pattern": "NGG",
  "pam_side": "3prime",
  "coordinates": {
    "coordinate_system": "0-based-half-open-reference-axis",
    "axis": "reference",
    "strand": "forward",
    "protospacer_start": 5,
    "protospacer_end": 25,
    "pam_start": 25,
    "pam_end": 28,
    "wraps_origin": false,
    "protospacer_segments": [[5, 25]],
    "pam_segments": [[25, 28]],
    "user_coordinates_1based_inclusive": {
      "protospacer_segments": [[6, 25]],
      "pam_segments": [[26, 28]]
    }
  },
  "context_sequences": {
    "azimuth_30mer": "ACGTGCATCGATCGATCGATCGTAAGGAAA",
    "deepcpf1_34mer": null
  },
  "warning": null,
  "provenance": [{"source_type": "software", "name": "SnapGene DNA Design PAM Scanner", "role": "guide-candidate-search", "status": "verified"}]
}
```

注意 `protospacer_sequence` 与 `protospacer_reference_sequence` 在反链候选上不同：前者是 5'→3' 的 gRNA spacer（参考序列的反向互补），后者是参考轴上同坐标区间的原序列。`user_coordinates_1based_inclusive` 把 0-based 半开 `[a,b)` 显示为 1-based 闭区间 `[a+1,b]`。

`guide_scoring.score_guides` 返回的评分对象：

```json
{
  "guide_id": "gRNA-001",
  "on_target_scores": [
    {
      "score": 0.3168,
      "score_range": [0.0, 1.0],
      "model": "Doench-2016",
      "model_version": "Azimuth-V3",
      "context_sequence": "ACGTGCATCGATCGATCGATCGTAAGGAAA",
      "context_length": 30,
      "context_semantics": "4-upstream+20-protospacer+NGG+3-downstream",
      "warnings": ["Azimuth/Doench-2016 was trained and validated in mammalian contexts; it is not specifically validated for yeast or other species."],
      "status": "available"
    }
  ],
  "applicability_warnings": ["Azimuth/Doench-2016 was trained and validated in mammalian contexts; it is not specifically validated for yeast or other species."],
  "heuristic_qc": {"gc_percent": 50.0, "homopolymer_risk": "low"},
  "provenance": [{"source_type": "software", "name": "SnapGene DNA Design guide_scoring", "role": "on-target-scoring-gate", "status": "verified"}]
}
```

`cas_offinder_adapter.parse_output` 解析后、`annotate_offtargets.annotate_hits` 注释后的 hit 对象：

```json
{
  "chromosome": "chrI",
  "start": 11,
  "end": 34,
  "reference_span": 23,
  "strand": "+",
  "sequence": "GCATCGATCGATCGATCGTgAGG",
  "mismatches": 1,
  "mismatch_positions": [19],
  "pam": "AGG",
  "bulge_type": null,
  "bulge_size": 0,
  "annotation": {
    "feature_type": "CDS",
    "feature_name": "geneA",
    "is_target_gene": false,
    "is_additional_perfect_match": false,
    "overlapping_features": [
      {
        "feature_type": "CDS",
        "feature_name": "geneA",
        "feature_strand": "+",
        "feature_start": 10,
        "feature_end": 30,
        "wraps_origin": false,
        "orientation_to_hit": "same"
      }
    ]
  }
}
```

`characterize_reaction.characterize_fragment` 生成的 reaction profile：

```json
{
  "fragment_id": "donor-1",
  "source": "donor-1",
  "template_type": "unknown",
  "length": 600,
  "topology": "linear",
  "gc_percent": 55.2,
  "gc_5prime_40": 52.5,
  "gc_3prime_40": 47.5,
  "max_local_gc_window_40": 72.5,
  "homopolymer_runs": [{"base": "A", "length": 6}],
  "predicted_difficulty": "not_scored",
  "high_fidelity_required": "unknown",
  "five_prime_tail": "unknown",
  "assembly_method": "unknown",
  "specificity_checked": false,
  "provenance": [{"source_type": "software", "name": "SnapGene DNA Design characterize_reaction", "role": "reaction-profile", "status": "verified"}]
}
```

## 错误码与结构化失败总表

本章所有脚本都遵循“可预期失败结构化返回，不裸抛 traceback”。`generate_crispr_design_report` 在最外层兜底，任何未捕获异常也会变成 `status=failed` 报告（`scripts/generate_crispr_design_report.py:380-382`）。下表汇总关键错误码与产生位置：

| 错误码 | 位置 | 含义 |
|---|---|---|
| `UNKNOWN_NUCLEASE` | `design_guides.scan_guides`（`scripts/design_guides.py:241`） | 注册表中无该核酸酶 id |
| `INVALID_PAM_DEFINITION` | `design_guides.scan_guides`（`scripts/design_guides.py:244`） | PAM 模式或 spacer 长度为空 |
| `TARGET_REGION_OUT_OF_RANGE` | `design_guides.scan_guides`（`scripts/design_guides.py:254`） | region 不是 `[0,n)` 内的合法半开区间 |
| `AZIMUTH_CONTEXT_UNAVAILABLE` | `guide_scoring._run_azimuth`（`scripts/guide_scoring.py:52`） | 候选没有 30mer 上下文 |
| `AZIMUTH_BACKEND_UNAVAILABLE` | `guide_scoring._run_azimuth`（`scripts/guide_scoring.py:67`） | Azimuth 导入/推理失败 |
| `AZIMUTH_CONTEXT_LENGTH` / `AZIMUTH_CONTEXT_BASE` | `azimuth_backend.predict`（`scripts/azimuth_backend.py:126-132`） | 30mer 长度或碱基非法 |
| `DEEPCPF1_CONTEXT_UNAVAILABLE` | `guide_scoring._run_deepcpf1`（`scripts/guide_scoring.py:72`） | 候选没有 34mer 上下文 |
| `DEEPCPF1_BACKEND_UNAVAILABLE` | `guide_scoring._run_deepcpf1`（`scripts/guide_scoring.py:88`） | DeepCpf1 导入/推理失败 |
| `DEEPCPF1_CONTEXT_LENGTH` / `DEEPCPF1_CONTEXT_BASE` | `deepcpf1_model._onehot`（`scripts/deepcpf1_model.py:50-56`） | 34mer 长度或碱基非法 |
| `DEEPCPF1_CA_LENGTH_MISMATCH` | `deepcpf1_model.predict_with_chromatin`（`scripts/deepcpf1_model.py:200`） | chromatin 数组与序列数不一致 |
| `DEEPCPF1_TORCH_UNAVAILABLE` / `DEEPCPF1_H5PY_UNAVAILABLE` / `DEEPCPF1_WEIGHTS_NOT_FOUND` | `deepcpf1_model`（`scripts/deepcpf1_model.py:34,42,167`） | torch/h5py 缺失或权重文件缺失 |
| `CAS_OFFINDER_UNSUPPORTED_NUCLEASE` | `cas_offinder_adapter.search_rules`（`scripts/cas_offinder_adapter.py:276`） | 未配置 Cas-OFFinder 搜索规则 |
| `QUERY_LENGTH_MISMATCH` | `cas_offinder_adapter.build_input_text`（`scripts/cas_offinder_adapter.py:292`） | protospacer 长度与规则不符 |
| `QUERY_CONTAINS_UNSUPPORTED_BASES` | `cas_offinder_adapter.build_input_text`（`scripts/cas_offinder_adapter.py:295`） | query 含 IUPAC 外字符 |
| `CAS_OFFINDER_PAM_LENGTH_MISMATCH` / `CAS_OFFINDER_PATTERN_QUERY_LENGTH_MISMATCH` | `cas_offinder_adapter.build_input_text`（`scripts/cas_offinder_adapter.py:302,308`） | PAM 长度或 pattern/query 长度不一致 |
| `REFERENCE_FASTA_NOT_FOUND` / `REFERENCE_ANNOTATION_NOT_FOUND` | `cas_offinder_adapter.genome_record`（`scripts/cas_offinder_adapter.py:164,181`） | 参考 FASTA/注释不存在 |
| `REFERENCE_INDEX_NOT_RECORDED` / `REFERENCE_FASTA_CHANGED_STALE_INDEX` | `cas_offinder_adapter.check_reference_binding`（`scripts/cas_offinder_adapter.py:241,246`） | 索引未绑定或 FASTA 已变化 |
| `CAS_OFFINDER_NOT_INSTALLED` | `cas_offinder_adapter.search_offtargets`（`scripts/cas_offinder_adapter.py:494`） | 未检测到二进制 |
| `CAS_OFFINDER_BULGE_UNSUPPORTED` | `cas_offinder_adapter.search_offtargets`（`scripts/cas_offinder_adapter.py:502`） | 2.x 不支持 bulge 搜索 |
| `CAS_OFFINDER_EXECUTION_FAILED` | `cas_offinder_adapter.search_offtargets`（`scripts/cas_offinder_adapter.py:514,583`） | 进程返回非 0 或 OSError |
| `CAS_OFFINDER_REFERENCE_EXTENSION_UNSUPPORTED` | `cas_offinder_adapter.search_offtargets`（`scripts/cas_offinder_adapter.py:522`） | 参考扩展名被后端跳过 |
| `CAS_OFFINDER_TIMEOUT` | `cas_offinder_adapter.search_offtargets`（`scripts/cas_offinder_adapter.py:578`） | 搜索超时 |
| `CAS_OFFINDER_EMPTY_OUTPUT` | `cas_offinder_adapter.parse_output` / `search_offtargets`（`scripts/cas_offinder_adapter.py:330,532`） | 输出为空（真零 hit 或静默失败，需人工复核） |
| `EXTERNAL_OUTPUT_PARSE_ERROR` | `cas_offinder_adapter.parse_output`（`scripts/cas_offinder_adapter.py:353-365`） | 外部 TSV 列数/类型非法 |
| `NO_REACTION_PROFILES_PROVIDED` / `PROTOCOL_SOURCE_NOT_FOUND` / `NO_PROFILE_MATCHED_EVIDENCE` | `recommend_protocol.recommend`（`scripts/recommend_protocol.py:96,109,163`） | 推荐前提缺失 |

## 测试运行与验证方法

本章相关测试全部基于 `unittest`，位于 `tests/` 目录。常规测试不依赖外部模型或二进制，可直接按测试文件运行（例如 `python -m unittest tests.test_v08_guides -v`，具体模块路径取决于测试目录是否作为包被导入；仓库已有 CI 或测试套件约定时按其约定执行）。三类门控测试需要环境变量：

| 环境变量 | 测试 | 验证内容 |
|---|---|---|
| `SNAPGENE_RUN_REAL_MODELS=1` | `tests/test_v08_dev3.py::RealModelTests` | Azimuth 与 DeepCpf1 真实模型输出与已知参考分数一致 |
| `CAS_OFFINDER_EXE=<path>` | `tests/test_v08_dev3.py::RealCasOffinderIntegrationTests::test_real_binary_end_to_end` 与 `test_real_binary_end_to_end_non_ascii_path` | 真实 2.x 二进制端到端搜索 |
| `CAS_OFFINDER_EXE_V3=<path>` | `tests/test_v08_dev3.py::RealCasOffinderIntegrationTests::test_real_binary_v3_bulge` | 真实 3.x bulge 搜索与实验性标注 |

`CAS_OFFINDER_TMP` 可指定真实二进制测试的临时目录基路径（`tests/test_v08_dev3.py:434-436`），用于把 Cas-OFFinder 的 OpenCL 临时文件放在合适位置。真实二进制测试会检查辅助文件 `.cas-offinder-*` 不泄漏在参考目录（`tests/test_v08_dev3.py:452-455`）。

## 坐标映射与反链公式

`design_guides.py` 的坐标系统是全章节最关键的实现细节。所有候选的 `coordinates` 对象同时给出标量 `start/end`（0-based 半开，参考轴）与显式 `segments`。反链映射公式为：

```text
rc[start:start+length) 在参考轴上的像
= dna[n-(start+length) : n-start)
= [n - scan_end, n - scan_start)
```

其中 `start` 是反向互补扫描轴上的区间起点。代码实现见 `_scan_interval_to_reference` 的反链分支：

```python
ref_start = (n - ((start + length) % n)) % n   # scripts/design_guides.py:115
```

示例（`tests/test_v08_dev3.py:40-51`）：参考序列 `A*10 + CCG + 20nt + A*6`。反链候选的 `protospacer_start/end == (13,33)`，`pam_start/end == (10,13)`，且 `reverse[0]["protospacer_sequence"] == str(Seq(seq[13:33]).reverse_complement())`、`reverse[0]["protospacer_reference_sequence"] == seq[13:33]`。这验证了“显示序列取反向互补，参考坐标落回原轴”的约定。

另一示例：参考序列 `AGG + C*20`（`n=23`，环状）。正链 3' PAM 的 PAM 锚点 `i=0`，protospacer 扫描区间为 `[-20,0)`；线性拓扑下该候选因 `scan_protospacer_start < 0` 被丢弃（`scripts/design_guides.py:284-285`），因此 `tests/test_v08_dev3.py:53-56` 断言线性 `AGG + C*20` 无候选。环状拓扑下同一锚点合法，`_scan_interval_to_reference(-20, 20, 23, 1, circular=True)` 先 `start %= n` 得 `3`，`ref_start=3`，`unwrapped_end=23`，恰在 n 结束不环绕，segments 为 `[[3,23]]`；这与 `tests/test_v08_dev3.py:87-106` 的“环状标量与 segments 在 n 处一致”相呼应。若环状序列 `AAGG + G*20`（`n=24`），PAM `AGG` 在 `[1,4)`，protospacer 在 `[5,24)` 等环绕候选会显式拆成 `[[s,24],[0,e]]` 两段（`tests/test_v08_dev3.py:58-60`）。

线性分子边界条件（`_scan_interval_to_reference` 线性分支，`scripts/design_guides.py:117-127`）：

- 区间结束于 n 时保留 `[s, n)`，不写成 `[s,0)` 加空段。
- `length > n` 无有效区间。
- PAM 与 protospacer 都必须完整落在 `[0,n)`（`scan_guides` 线性过滤，`scripts/design_guides.py:283-289`）。

环状分子边界条件（`_scan_interval_to_reference` 环状分支，`scripts/design_guides.py:129-142`）：

- `length == n` → `[[0,n]]`，`wraps_origin=False`。
- `length > n` → `[[0,n]]`，`wraps_origin=True`。
- 一般情况 `wraps_origin = (ref_start + length > n)`；结束恰在 n 不环绕。
- 环绕时 `segments = [[origin_start, n], [0, origin_end]]`，`origin_end > 0` 才保留第二段（`_circular_segments`，`scripts/design_guides.py:84-95`）。

1-based 用户坐标转换：每个 0-based 半开段 `[a,b)` 转为 1-based 闭区间 `[a+1, b]`（`_user_1based`，`scripts/design_guides.py:158-159`）。例如 `[[4,27]]` 转为 `[[5,27]]`，与 SnapGene 的 1-based 闭区间显示一致。

Cas-OFFinder 坐标：v2/v3 输出 `start` 本身为 0-based 起点，适配器保持 0-based 半开 `[start, start+reference_span)`（`scripts/cas_offinder_adapter.py:369-375`）。`annotate_offtargets` 也以 0-based 半开做重叠判断（`scripts/annotate_offtargets.py:81-84`）。

---

## Schema 与输出契约

### schemas/guide-design-result-v0.8.json

必填：`schema_version`、`nuclease`、`candidate_count`、`candidates`、`provenance`（`schemas/guide-design-result-v0.8.json:7-13`）。候选必填 `id`、`nuclease`、`strand`、`protospacer_sequence`、`pam_sequence`、`pam_pattern`、`pam_side`、`coordinates`、`provenance`（`schemas/guide-design-result-v0.8.json:59-72`）。`coordinates` 必填 `coordinate_system`、`protospacer_start`、`protospacer_end`、`pam_start`、`pam_end`、`wraps_origin`（`schemas/guide-design-result-v0.8.json:106-116`），可选 `axis`、`strand`、`protospacer_segments`、`pam_segments`、`user_coordinates_1based_inclusive`。`context_sequences` 仅允许 `azimuth_30mer` 与 `deepcpf1_34mer` 两个键（`schemas/guide-design-result-v0.8.json:183-200`）。

### schemas/offtarget-result-v0.8.json

必填：`schema_version`、`status`、`reference_genome`、`provenance`（`schemas/offtarget-result-v0.8.json:7-12`）。`status` 枚举 `complete/incomplete/unavailable/failed/stale`（`schemas/offtarget-result-v0.8.json:17-25`）。`reference_genome` 必填 `fasta_sha256` 与 `status`（`schemas/offtarget-result-v0.8.json:29-32`）。hit 必填 `chromosome`、`start`、`end`、`strand`、`sequence`、`mismatches`、`pam`、`annotation`（`schemas/offtarget-result-v0.8.json:174-186`）；`annotation` 必填 `feature_type`、`feature_name`、`is_target_gene`、`is_additional_perfect_match`（`schemas/offtarget-result-v0.8.json:251-259`）。

### schemas/crispr-design-report-v0.8.json

必填：`schema_version`、`status`、`task_summary`、`inputs`、`nuclease`、`guide_candidates`、`on_target`、`off_target`、`reaction_profiles`、`protocol_recommendation`、`sequence_upload`、`unfinished_analysis`、`limitations`、`human_review_required`、`provenance`（`schemas/crispr-design-report-v0.8.json:7-23`）。`status` 枚举 `complete/partial/failed/unavailable`（`schemas/crispr-design-report-v0.8.json:83-89`）。Schema 使用 `additionalProperties:false`，防止报告层静默夹带未契约字段。

### schemas/protocol-recommendation-v0.8.json

必填 `schema_version`、`status`、`recommendations`、`provenance`（`schemas/protocol-recommendation-v0.8.json:7-12`）。`status` 枚举 `available/partial/unavailable/conflicting`；推荐条目必填 `recommendation_id`、`reaction_id`、`category`、`status`、`source`、`evidence_level`、`human_review_required`（`schemas/protocol-recommendation-v0.8.json:53-60`）。`status` 枚举 `preferred_candidate/compatible_candidate/not_recommended/insufficient_evidence/conflicting_sources`（`schemas/protocol-recommendation-v0.8.json:64-70`）。

### schemas/reaction-profile-v0.8.json

必填 `schema_version`、`fragment_id`、`length`、`gc_percent`、`provenance`（`schemas/reaction-profile-v0.8.json:7-12`）。`topology` 枚举 `linear/circular`，`specificity_checked` 为 boolean。

### schemas/provenance-v0.8.json

必填 `source_type`、`name`、`role`、`status`（`schemas/provenance-v0.8.json:7-12`）。`source_type` 枚举 `software/prediction-model/reference-database/manufacturer-protocol/public-protocol/published-paper/heuristic/user-input`。`allOf` 条件必填：`manufacturer-protocol` 必填 `url`、`retrieved_at`、`version`；`prediction-model` 必填 `version`；`public-protocol` 必填 `url`、`retrieved_at`（字段定义见 `schemas/provenance-v0.8.json` 的 `allOf`/`then` 分支）。`provenance.validate`（`scripts/provenance.py` 中 `CONDITIONAL_REQUIRED`，`scripts/provenance.py:109-113`）在运行时执行同样检查；`version` 永远来自 `VERSION` 文件（`scripts/provenance.py:20-28`），禁止 `"latest"`。

---

## CLI 调用示例

本章各脚本的典型命令行形态（坐标参数均按各自约定：`design_guides` 的 `--region` 为 0-based 半开；`generate_crispr_design_report` 的 `--mismatches`/`--dna-bulge`/`--rna-bulge` 为 Cas-OFFinder 搜索参数）：

```bash
# 候选扫描
python scripts/design_guides.py target.fa --nuclease spcas9-wt --json
python scripts/design_guides.py target.fa --nuclease ascas12a-wt --region 0 500 --json

# 反应特征（供协议推荐，不推荐试剂）
python scripts/characterize_reaction.py donor1.fa donor2.fa --json

# 协议推荐（默认读取 references/protocol-evidence-dev2.json）
python scripts/recommend_protocol.py --profile reaction_profiles.json --json

# 脱靶注释（hits_json 通常来自 Cas-OFFinder 搜索结果）
python scripts/annotate_offtargets.py hits.json --annotation reference.gb --target-gene YFG1 --json

# 统一报告（可叠加 --reference-fasta/--annotation/--out-dir 等）
python scripts/generate_crispr_design_report.py target.fa \
  --nuclease spcas9-wt \
  --fragments donor1.fa donor2.fa \
  --reference-fasta genome.fa \
  --annotation genome.gb \
  --target-gene YFG1 \
  --out-json crispr-report.json \
  --out-markdown crispr-report.md \
  --out-dir crispr-output
```

`design_guides.py` 与 `annotate_offtargets.py` 的 JSON 输出直接对应 `schemas/guide-design-result-v0.8.json` 与 `schemas/offtarget-result-v0.8.json` 的字段；`recommend_protocol.py` 对应 `schemas/protocol-recommendation-v0.8.json`；`characterize_reaction.py` 的 `reaction_profiles` 元素对应 `schemas/reaction-profile-v0.8.json`；`generate_crispr_design_report.py` 的顶层报告对应 `schemas/crispr-design-report-v0.8.json`。这些脚本在失败路径上的共同约定是：错误码前缀可被程序解析，`schema_version` 保留为 `0.8.0`，provenance 不缺失。

## 实现路径汇总

完整调用链（成功路径）：

```text
generate_crispr_design_report.main
  ├─ sg_common.load_seq(target)
  ├─ design_guides.scan_guides(record, nuclease)
  │    ├─ design_guides.load_registry()
  │    ├─ 正/反链 PAM 扫描 (pam_matches / _arc)
  │    ├─ _scan_interval_to_reference -> _candidate_coordinates
  │    └─ _context_sequences -> _assign_ids
  ├─ guide_scoring.score_guides(candidates, nuclease)
  │    ├─ _run_azimuth -> azimuth_backend.score_30mers -> AzimuthPredictor.predict
  │    └─ _run_deepcpf1 -> deepcpf1_model.predict_sequence_only
  ├─ characterize_reaction.characterize_fragment(每个 fragment)
  ├─ protocol_evidence.load_sources
  ├─ recommend_protocol.recommend(fragments, sources)
  ├─ _offtarget_analysis(record, candidates, args)
  │    ├─ cas_offinder_adapter.detect
  │    ├─ 逐候选 cas_offinder_adapter.search_offtargets
  │    │    ├─ genome_record -> check_reference_binding
  │    │    ├─ search_rules -> build_input_text
  │    │    ├─ _run_cas_offinder_cli -> _invoke_cli
  │    │    ├─ parse_output
  │    │    └─ record_reference_binding
  │    ├─ _merge_hits
  │    └─ annotate_offtargets.annotate_hits
  ├─ _markdown(report)
  └─ _write_design_files -> write_dna._ensure_annotations / _snapgene_annotated / write_native_dna
```

失败路径：

```text
main
  ├─ 异常 -> _failed_report -> 写 JSON/Markdown -> return 1
  └─ 局部失败 -> partial_reasons 累积，报告 status=partial/failed
```

---

## 科学适用边界与实验性标注

1. **on-target 模型适用边界**：Azimuth/Doench-2016 训练于哺乳动物上下文，未针对酵母验证；DeepCpf1 只适用 AsCas12a，不适用 LbCas12a；LbCas12a 无已审查模型，总是 unavailable。警告随结果返回（`scripts/guide_scoring.py:17-27`），并在注册表与 `crispr-model-applicability.md` 中双重登记。
2. **off-target 后端分级**：Cas-OFFinder 2.4.1 为生产可用（`production_ready=True`）；Cas-OFFinder 3.0.0 beta 为实验后端（`experimental_backend=True`、`production_ready=False`），结果必须与 v2.x 或独立工具交叉核对（`scripts/cas_offinder_adapter.py:560-568`）。
3. **CRISPOR 不默认联网**：本地未安装则 unavailable；在线查询需要逐次上传同意，默认拒绝且不存全长序列。
4. **协议推荐不是实验方案**：`recommend_protocol` 只给 `compatible_candidate`，证据级别为 `manufacturer-official`，条件必须人工复核；`characterize_reaction` 不推荐试剂，不发明温度/时间/缓冲液。
5. **计算不等同于湿实验**：报告固定写 `limitations`（`scripts/generate_crispr_design_report.py:206-209`）与 `unfinished_analysis`（含 `wet-lab-validation`、`primer-specificity`）。`human_review_required` 固定包含 gRNA 排序、脱靶位点生物学意义、协议条件复核。
6. **已知限制**：非 ACGT protospacer 不进入 on-target 模型；Cas-OFFinder 空输出判为 incomplete 而非零 hit；bulge 命中不判完美匹配；环状基因组 feature 注释依赖 GenBank 记录与染色体名匹配。

实验性标注的落点汇总：

| 标注对象 | 落点 | 内容 |
|---|---|---|
| 模型适用性警告 | `guide_scoring.APPLICABILITY_WARNINGS`（`scripts/guide_scoring.py:17-27`） | 哺乳动物训练、未验证酵母、DeepCpf1 只适用 AsCas12a |
| LbCas12a 无模型 | `guide_scoring.score_guides`（`scripts/guide_scoring.py:136-142`） | `status=unavailable`、`reason=no-reviewed-model-selected-for-lbcas12a` |
| Cas-OFFinder 3.x 实验后端 | `cas_offinder_adapter.search_offtargets`（`scripts/cas_offinder_adapter.py:559-568`） | `experimental_backend=True`、`production_ready=False`、交叉核对警告 |
| 空输出不可判零 | `cas_offinder_adapter.search_offtargets`（`scripts/cas_offinder_adapter.py:528-541`） | `status=incomplete`、`reason=CAS_OFFINDER_EMPTY_OUTPUT` |
| CRISPOR 许可未审 | `crispor_adapter.detect`（`scripts/crispor_adapter.py:38-41`） | `license_notice.status=user-must-review` |
| 协议推荐非实验方案 | `recommend_protocol.recommend`（`scripts/recommend_protocol.py:154-157`） | `status=compatible_candidate`、`human_review_required=True` |
| 反应难度不评分 | `characterize_reaction.characterize_fragment`（`scripts/characterize_reaction.py:38`） | `predicted_difficulty=not_scored` |
| 计算不等同湿实验 | `generate_crispr_design_report.make_report`（`scripts/generate_crispr_design_report.py:206-209`） | `limitations` 固定条目 |
| 未完成分析 | `generate_crispr_design_report.make_report`（`scripts/generate_crispr_design_report.py:177-182`） | `unfinished_analysis` 含 `wet-lab-validation` 与 `primer-specificity` |

---

## 本章覆盖脚本清单

| 脚本 | 关键函数/类（行号） | 本章小节 |
|---|---|---|
| `scripts/design_guides.py` | `load_registry`(27)、`_iupac_compatible`(33)、`pam_matches`(61)、`_arc`(67)、`_circular_segments`(78)、`_scan_interval_to_reference`(98)、`_candidate_coordinates`(162)、`_context_sequences`(199)、`scan_guides`(228)、`_assign_ids`(332)、`main`(343) | `## scripts/design_guides.py` |
| `scripts/guide_scoring.py` | `APPLICABILITY_WARNINGS`(17)、`MODEL_APPLICABILITY`(29)、`_run_azimuth`(50)、`_run_deepcpf1`(70)、`_heuristic_qc`(91)、`score_guides`(114)、`main`(157) | `## scripts/guide_scoring.py` |
| `scripts/azimuth_backend.py` | `_CaptureTree`(29)、`_CompatibilityUnpickler`(70)、`AzimuthPredictor.__init__`(87)、`predict`(115)、`_gbr_predict`(146)、`_tree_predict`(157)、`score_30mers`(182) | `## scripts/azimuth_backend.py` |
| `scripts/deepcpf1_model.py` | `_onehot`(45)、`_SeqOnlyNet`(61)、`_SeqOnlyNet.forward`(94)、`_SeqCANet`(108)、`_load_seq_net`(163)、`predict_sequence_only`(181)、`predict_with_chromatin`(193) | `## scripts/deepcpf1_model.py` |
| `scripts/cas_offinder_adapter.py` | `default_index_registry_path`(34)、`NUCLEASE_SEARCH_RULES`(58)、`detect`(91)、`genome_record`(155)、`check_reference_binding`(228)、`search_rules`(272)、`build_input_text`(286)、`parse_output`(320)、`_mismatch_positions`(389)、`search_offtargets`(440)、`_run_cas_offinder_cli`(594)、`_invoke_cli`(636) | `## scripts/cas_offinder_adapter.py` |
| `scripts/annotate_offtargets.py` | `feature_type_for`(20)、`_location_segments`(47)、`_hit_segments`(66)、`_overlaps`(81)、`annotate_hits`(105)、`main`(158) | `## scripts/annotate_offtargets.py` |
| `scripts/generate_crispr_design_report.py` | `_input_records`(26)、`_merge_hits`(40)、`_offtarget_analysis`(58)、`make_report`(143)、`_failed_report`(223)、`_markdown`(254)、`_write_design_files`(334)、`main`(351) | `## scripts/generate_crispr_design_report.py` |
| `scripts/crispor_adapter.py` | `detect`(22)、`online_query_request`(50) | `## scripts/crispor_adapter.py` |
| `scripts/recommend_protocol.py` | `_category_for`(24)、`_source_matches`(52)、`_pick_source`(79)、`recommend`(90)、`main`(169) | `## scripts/recommend_protocol.py` |
| `scripts/characterize_reaction.py` | `_windows`(19)、`characterize_fragment`(23)、`_homopolymer_runs`(50)、`main`(69) | `## scripts/characterize_reaction.py` |

---

## 关键测试清单

| 测试文件 | 测试名 | 验证点 |
|---|---|---|
| `tests/test_v08_guides.py` | `NucleaseRegistryTests::test_spcas9_has_ngg_3prime` | SpCas9 PAM 注册正确 |
| `tests/test_v08_guides.py` | `NucleaseRegistryTests::test_ascas12a_and_lbcas12a_are_separate` | 两种 Cas12a 分开注册 |
| `tests/test_v08_guides.py` | `NucleaseRegistryTests::test_lbcas12a_has_no_on_target_models` | LbCas12a 无 on-target 模型 |
| `tests/test_v08_guides.py` | `GuideScannerTests::test_spcas9_forward_and_reverse` | 正反链扫描 |
| `tests/test_v08_guides.py` | `GuideScannerTests::test_circular_wrap_is_preserved` | 环状环绕候选 |
| `tests/test_v08_guides.py` | `GuideScannerTests::test_ambiguous_protospacer_warns` | 非 ACGT 警告 |
| `tests/test_v08_guides.py` | `GuideScannerTests::test_unknown_nuclease_fails` | 未知核酸酶报错 |
| `tests/test_v08_dev2.py` | `CasOffinderParserTests::test_parse_v24_6col_and_v30_9col` | v2.4 6/7 列与 v3 9 列解析 |
| `tests/test_v08_dev2.py` | `CasOffinderParserTests::test_bad_output_reports_structured_error` | 坏输出结构化错误 |
| `tests/test_v08_dev2.py` | `ScoringGateTests::test_lbcas12a_has_no_model` | LbCas12a unavailable |
| `tests/test_v08_dev2.py` | `ScoringGateTests::test_ascas12a_does_not_use_cas9_model` | Cas12a 不用 Cas9 模型 |
| `tests/test_v08_dev2.py` | `ScoringGateTests::test_spcas9_allows_only_cas9_models` | SpCas9 仅 Cas9 模型 |
| `tests/test_v08_dev2.py` | `ProtocolEvidenceTests::test_packaged_evidence_has_required_fields` | 协议证据字段 |
| `tests/test_v08_dev3.py` | `P0CoordinateTests::test_reverse_strand_maps_to_reference_axis` | 反链坐标映射公式 |
| `tests/test_v08_dev3.py` | `P0CoordinateTests::test_linear_end_pam_never_wraps` | 线性末端 PAM 不环绕 |
| `tests/test_v08_dev3.py` | `P0CoordinateTests::test_circular_wrap_has_explicit_segments` | 环状显式 segments |
| `tests/test_v08_dev3.py` | `P0CoordinateTests::test_linear_cas12a_never_reports_wrap` | 线性 Cas12a 不误报环绕 |
| `tests/test_v08_dev3.py` | `P0CoordinateTests::test_linear_interval_ending_at_n_keeps_n_boundary` | 区间终止于 n 保留边界 |
| `tests/test_v08_dev3.py` | `P0CoordinateTests::test_circular_scalar_and_segments_agree_at_n` | 环状标量与 segments 一致 |
| `tests/test_v08_dev3.py` | `ConsentBindingTests::test_ten_interception_scenarios` | 上传同意 10 种拦截 |
| `tests/test_v08_dev3.py` | `OfftargetAnnotationTests::test_overlap_not_start_containment` | 脱靶重叠而非包含注释 |
| `tests/test_v08_dev3.py` | `CasOffinderAdapterTests::test_build_input_contract` | 输入文件契约 |
| `tests/test_v08_dev3.py` | `CasOffinderAdapterTests::test_stale_index_blocks_without_rebuild` | stale 索引阻断 |
| `tests/test_v08_dev3.py` | `CasOffinderAdapterTests::test_real_cli_contract_and_failure_paths_with_fake_binary` | CLI 参数契约与失败路径 |
| `tests/test_v08_dev3.py` | `RealModelTests::test_azimuth_real_prediction`（需 `SNAPGENE_RUN_REAL_MODELS=1`） | Azimuth 真实分数 |
| `tests/test_v08_dev3.py` | `RealModelTests::test_deepcpf1_matches_bioconductor_reference`（需 `SNAPGENE_RUN_REAL_MODELS=1`） | DeepCpf1 与 Bioconductor 参考一致 |
| `tests/test_v08_dev3.py` | `ReportAndOutputFormatTests::test_unknown_nuclease_is_structured_failed_report` | 未知核酸酶 failed 报告 |
| `tests/test_v08_dev3.py` | `ReportAndOutputFormatTests::test_output_formats_sequence_identical` | `.gb`/`.fa`/`.dna` 序列一致 |
| `tests/test_v08_dev3.py` | `RealCasOffinderIntegrationTests::test_real_binary_end_to_end_non_ascii_path`（需 `CAS_OFFINDER_EXE`） | 非 ASCII 路径端到端 |
| `tests/test_v08_dev3.py` | `RealCasOffinderIntegrationTests::test_real_binary_v3_bulge`（需 `CAS_OFFINDER_EXE_V3`） | 3.x bulge 端到端 |
| `tests/test_v08_dev3.py` | `RealCasOffinderIntegrationTests::test_real_binary_end_to_end`（需 `CAS_OFFINDER_EXE`） | 真实二进制端到端 |
| `tests/test_v08_gate_coverage.py` | `DesignGuidesGapTests::test_iupac_all_bases` | IUPAC 全码匹配 |
| `tests/test_v08_gate_coverage.py` | `DesignGuidesGapTests::test_scan_errors_and_limits` | 扫描错误与限制 |
| `tests/test_v08_gate_coverage.py` | `DesignGuidesGapTests::test_context_helpers_and_circular` | 上下文截取与环状 |
| `tests/test_v08_gate_coverage.py` | `CasOffinderGapTests::test_parse_errors` | 解析错误路径 |
| `tests/test_v08_gate_coverage.py` | `CasOffinderGapTests::test_timeout_and_unsupported_bulge` | 超时与 2.x bulge 拒绝 |
| `tests/test_v08_gate_coverage.py` | `ScoringGapTests::test_backend_failures_are_unavailable` | 后端失败降级 unavailable |
| `tests/test_v08_gate_coverage.py` | `RecommendGapTests::test_high_gc_pcr_match` | 高 GC PCR 匹配 |
| `tests/test_v08_gate_coverage.py` | `CharacterizeGapTests::test_windows_and_runs` | 滑窗与同聚物串 |
| `tests/test_v08_gate_coverage.py` | `AnnotateGapTests::test_compound_and_circular_locations` | 复合/环状位置拆分 |
| `tests/test_v08_gate_coverage.py` | `ReportGapTests::test_make_report_direct` | 报告直调路径 |
| `tests/test_v08_gate_coverage.py` | `ReportGapTests::test_offtarget_analysis_failure_branches` | 脱靶分析失败分支 |
| `tests/test_v08_gate_coverage.py` | `ReportGapTests::test_main_direct_success_and_failure` | CLI 成功/失败 |
| `tests/test_v08_gate_coverage.py` | `ReportGapTests::test_markdown_and_failed_report` | Markdown 与失败报告 |
| `tests/test_v08_gate_coverage.py` | `AdditionalCoverageTests::test_guide_scoring_missing_context_and_cli` | 上下文缺失 unavailable |
| `tests/test_v08_gate_coverage.py` | `AdditionalCoverageTests::test_deepcpf1_error_branches` | DeepCpf1 错误分支 |
| `tests/test_v08_gate_coverage.py` | `AdditionalCoverageTests::test_azimuth_error_branches` | Azimuth 错误分支 |

# 第 6 章：打包发布、测试体系、场景套件与文档/参数溯源

> 适用范围：`snapgene-dna-design` v0.8.0-dev3（开发预览，不是 RC，不是正式版）。
> 本章只描述计算端行为：打包、发布清单、许可证门禁、覆盖率门禁、变异测试、property 测试、烟雾测试、rich fixture、场景套件与参数溯源。所有模拟结果都是计算预测；标有 `experimental` 的克隆功能只能作为概念预演，不得作为可直接执行的湿实验方案。
> 行号引用以仓库根目录 `D:/codex_project/snapgene-dna-design-v0.9.0-work` 为基准，格式为 `文件路径:起始行`。函数签名与行号以 v0.9.0 实际代码为准。

## 1. 本章总览与发布物结构

本章覆盖 14 个必须出现的脚本/模块：

`scripts/build_release.py`、`scripts/check_redistributable.py`、`scripts/validate_release_manifest.py`、`scripts/coverage_gate.py`、`scripts/mutation_tests.py`、`scripts/property_tests.py`、`scripts/run_test_suite.py`、`scripts/smoke_core.py`、`scripts/smoke_academic.py`、`scripts/validate_rich_fixtures.py`、`scripts/build_rich_fixtures.py`、`scripts/check_env.py`、`scripts/collect_release_evidence.py`、`scripts/run_scenario_suite.py`。

同时覆盖两个包形态（`academic-full` 与 `redistributable`）、`DEVELOPMENT-MANIFEST.json` 与 `RELEASE-MANIFEST.json`、受限哈希表、coverage 并行子进程机制、12 个变异、property 规模、90 个场景分类与 `ground_truth`，以及 `references/biological-parameters-sources.md` / `.json` 的“参数—来源—代码引用”三向溯源。

### 1.1 两种发布包

`scripts/build_release.py:2-9` 的 docstring 明确：从同一源码树构建两个 ZIP，并且为两个包分别重写 `DEVELOPMENT-NOTICE.md` 与 `THIRD_PARTY_NOTICE.md`，避免把互相矛盾的声明打进同一个包。

| 包 | 文件名模式 | 内容策略 | 受限 SnapGene fixture |
|---|---|---|---|
| `academic-full` | `snapgene-dna-design-v<version>-academic-full.zip` | 源码树全量条目，包含学术专用 fixture | 允许存在，`check_redistributable.py --academic` 校验其完整 |
| `redistributable` | `snapgene-dna-design-v<version>-redistributable.zip` | 过滤 `redistributable=false` 的条目 | 禁止存在，`check_redistributable.py` 检出即失败 |

`ACADEMIC_ONLY_PATHS`（`scripts/build_release.py:35-44`）列出学术包专用路径：`fixtures/pDONR201.dna`、`fixtures/golden/`、`tests/test_smoke_academic.py`、`tests/test_v03.py`、`tests/test_v04.py`、`tests/test_license_real.py`、`scripts/smoke_suite.py`、`scripts/smoke_academic.py`。

### 1.2 两个 manifest 的分工

| 文件 | 生成者 | 位置 | 作用 |
|---|---|---|---|
| `DEVELOPMENT-MANIFEST.json` | `build_release.py:_development_manifest`（`scripts/build_release.py:125-135`） | 源码树根目录 | 开发态快照清单，`manifest_kind="development-manifest"`，含全部条目 |
| `RELEASE-MANIFEST.json` | `build_release.py:_write_zip`（`scripts/build_release.py:254-265`） | ZIP 内部 `snapgene-dna-design/RELEASE-MANIFEST.json` | 每个包内部发布清单，`manifest_kind="release-manifest"`，`build_version`、`package`、`schema_version`、`entries` |

`DEVELOPMENT-MANIFEST.json` 在 `main()` 中通过 `--refresh-dev-manifest`（默认 `True`）在构建前刷新（`scripts/build_release.py:288-289`）。`RELEASE-MANIFEST.json` 被写进 ZIP 时使用固定的 `schema_version="0.8.0"`（`scripts/build_release.py:258`），因为该清单描述的是 v0.8 行发布契约。

### 1.3 受限哈希

受限内容不按路径识别，而按 SHA-256 识别。`scripts/check_redistributable.py:20-41` 的 `RESTRICTED_HASHES` 映射了 10 个哈希：

| 哈希 | 期望路径 |
|---|---|
| `3F68...10CA` | `fixtures/pDONR201.dna` |
| `9D6F...5682` | `fixtures/golden/pDEST40.dna` |
| `8F66...DFA1` | `fixtures/golden/pENTR-D-TOPO.dna` |
| `DE8C...6278` | `fixtures/golden/pcDNA3.2-V5-GW-D-TOPO.dna` |
| `9377...0F04` | `fixtures/golden/pGEM-T-linearized.dna` |
| `525A...F7E1` | `fixtures/golden/attB-EmGFP.fa` |
| `5B82...8CA1` | `fixtures/golden/attB-EmGFP.gb` |
| `4719...EA04` | `fixtures/golden/pDEST-EmGFP.gb` |
| `1137...A231` | `fixtures/golden/pENTR-EmGFP.gb` |
| `2E07...6B33` | `fixtures/golden/pGEM-T-insert.gb` |

这些条目涵盖 SnapGene 原始文件与其衍生 golden fixture。哈希识别使重命名、大小写变化、多套目录、路径分隔符变化都无法绕过检查（`scripts/check_redistributable.py:8-10`）。

---

## 2. `scripts/build_release.py`

### 2.1 技术原理

`build_release.py` 是发布包构建器，核心数据结构是 `_collect()` 生成的条目列表。每个条目字典含 `path`、`sha256`、`size`、`license`、`source_category`、`redistributable`、`exclusion_reason`（`scripts/build_release.py:113-121`）。

关键常量：

| 常量 | 行号 | 值/作用 |
|---|---|---|
| `EXCLUDE_ALL` | `scripts/build_release.py:21-24` | 总是排除 `RELEASE-MANIFEST.json`、`.coverage` |
| `EXCLUDE_PREFIXES` | `scripts/build_release.py:30-33` | 有效值为 `("reports/", "__pycache__/")` |
| `ACADEMIC_ONLY_PATHS` | `scripts/build_release.py:35-44` | 学术包专用路径 |
| `THIRD_PARTY_LICENSES` | `scripts/build_release.py:46-49` | 第三方路径到许可证字符串的映射 |
| `ZIP_PREFIX` | `scripts/build_release.py:51` | `"snapgene-dna-design/"`，ZIP 内部统一前缀 |

注意 `scripts/build_release.py:25-29` 还有一个包含 `"tmp_"` 的 `EXCLUDE_PREFIXES` 定义，但它在 `30-33` 行被重新赋值覆盖，因此**不生效**。有效排除逻辑是：`reports/` 前缀、`__pycache__` 子串、`.pyc` 后缀、`EXCLUDE_ALL` 命中（`scripts/build_release.py:101-105`）。

`_classify(path, digest)`（`scripts/build_release.py:65-83`）按顺序分类：命中 `RESTRICTED_HASHES` 的 `.dna` 文件为 `snapgene-fixture`，其他命中哈希的文件为 `derived-fixture`；`third_party/azimuth/` 与 `third_party/deepcpf1/` 下的模型文件为 `third-party-model`，Python 文件为 `third-party-code`，其余为 `third-party-license`；`fixtures/` 下其他文件为 `synthetic-fixture`；LICENSE/NOTICE 为 `license-notice`；`.md` 与 `references/` 下的 `.json` 为 `documentation`；其余为 `project-code`。

`_exclusion_reason(path, digest)`（`scripts/build_release.py:86-92`）只产生两种不可再分发原因：哈希命中受限表的 `"snapgene-restricted-or-derived"`，以及路径命中 `ACADEMIC_ONLY_PATHS` 的 `"depends-on-restricted-fixtures"`。`_collect()` 将 `exclusion_reason is None` 记为 `redistributable`。

`_write_zip(zip_path, entries, root, version, notice_texts)`（`scripts/build_release.py:224-265`）逐条目写入 ZIP；对 `THIRD_PARTY_NOTICE.md` 与 `DEVELOPMENT-NOTICE.md` 不读磁盘，而是写入 `_third_party_notice()` / `_development_notice()` 生成的包专属文本，并重新计算哈希与大小（`scripts/build_release.py:231-242`）。所有 ZIP 条目使用固定时间戳 `(1980, 1, 1, 0, 0, 0)` 与外部位权限 `0o644 << 16`，保证可复现构建（`scripts/build_release.py:246-248`）。

### 2.2 生物学与许可原理

- **学术包**包含 `fixtures/pDONR201.dna` 与 `fixtures/golden/`，其来源为 SnapGene 6.x 质粒集合（GraphPad Software / SnapGene）。`_third_party_notice(redistributable=False)`（`scripts/build_release.py:173-187`）写明：SnapGene 声明其质粒集合的 maps、notes、annotations 受版权保护；学术、非营利与政府用户可在注明来源 `www.snapgene.com/resources` 的前提下使用；商业使用需另行联系 GraphPad。该段不编造 DOI，直接引用官方许可声明。
- **可再分发包**只含 MIT 项目代码与 `THIRD_PARTY_NOTICE.md` 列出的第三方模型工件：`third_party/azimuth/`（Azimuth 2.0，Doench et al. 2016，DOI 10.1038/nbt.3437，BSD）与 `third_party/deepcpf1/`（DeepCpf1，Kim et al. 2018，DOI 10.1038/nbt.4061，Artistic-2.0）。Cas-OFFinder、CRISPOR、primer3_core 是外部运行时，不在包内（`scripts/build_release.py:200-207`）。
- 两个包的 `_development_notice()`（`scripts/build_release.py:138-162`）都声明：这是开发快照，不是正式发布，也不是可安装依赖包；真实后端门禁必须运行真实可执行文件/模型，占位或跳过测试不得作为发布证据。

### 2.3 实现路径

```text
CLI main() [scripts/build_release.py:268]
  -> 解析 root/output/--version；校验 VERSION 文件与 --version 一致 [279-285]
  -> _development_manifest(root, version) [288-289]
       -> _collect(root, exclude_extra={"DEVELOPMENT-MANIFEST.json"}) [125-135]
  -> _collect(root) 得到全量 entries [291]
  -> redist_entries = [e for e in entries if e["redistributable"]] [294]
  -> _write_zip(academic, academic_entries, ...) [298-301]
  -> _write_zip(redist, redist_entries, ...) [302-305]
  -> stdout 输出 JSON：academic/redistributable 路径、条目数、版本 [306-312]
```

### 2.4 科学性说明与已知限制

- 限制：`build_release.py` 只做文件分类与打包，不做序列层面的生物学验证；软件行为与代码已声明不变量由 smoke、mutation、property、scenario 套件验证，不等于湿实验生物学正确性证明。
- 限制：`schema_version` 硬编码为 `"0.8.0"`（`scripts/build_release.py:258`）；若未来发布 v0.9 需要同步修改。
- 限制：`EXCLUDE_PREFIXES` 第一处赋值被覆盖，`"tmp_"` 前缀并未真正生效；当前仓库根目录无 `tmp_` 文件，无实际影响，但属于死代码。
- 限制：`_development_manifest` 收集时排除自身（`scripts/build_release.py:126`），但 `main()` 随后调用的 `_collect(root)` 不再排除它；`EXCLUDE_ALL` 只有 `RELEASE-MANIFEST.json` 与 `.coverage`（`scripts/build_release.py:21-24`）。因此刷新后的 `DEVELOPMENT-MANIFEST.json` 会作为普通文件进入两个 ZIP，可再分发包中的该清单 JSON 文本仍可见受限条目的路径与哈希值（受限 fixture 字节本身不进入可再分发包）。若要求连受限条目名称也不得在可再分发包中披露，需要调整 `EXCLUDE_ALL` 或为可再分发包重写包内开发清单。
- 测试：`tests/test_v06.py` 的 `GeneralLicenseHashCheckerTests` 与 `tests/test_license_real.py` 的 `RealLicenseHashCheckerTests` 覆盖哈希检查；包结构本身的回归在 `tests/test_release_iteration.py` 与 `tests/test_v08_dev3.py` 中体现。

---

## 3. `scripts/check_redistributable.py`

### 3.1 技术原理

`check_redistributable.py` 是内容哈希许可证门禁。核心数据是 `RESTRICTED_HASHES`（`scripts/check_redistributable.py:20-41`），SHA-256 为键，期望路径为值。

关键函数：

| 函数 | 签名 | 行号 | 作用 |
|---|---|---|---|
| `_sha256` | `_sha256(data)` | `scripts/check_redistributable.py:44-45` | 返回大写 SHA-256 十六进制 |
| `_safe_zip_entries` | `_safe_zip_entries(path)` | `scripts/check_redistributable.py:48-58` | 生成 ZIP 内正规化路径与字节；拒绝路径穿越 |
| `inspect_zip` | `inspect_zip(path, restricted_hashes=None)` | `scripts/check_redistributable.py:61-71` | ZIP 内查受限哈希 |
| `inspect_dir` | `inspect_dir(path, restricted_hashes=None)` | `scripts/check_redistributable.py:74-88` | 目录树内查受限哈希 |
| `main` | `main()` | `scripts/check_redistributable.py:91-146` | CLI 入口；academic 模式校验完整性，默认模式校验可再分发 |

`_safe_zip_entries` 将 `info.filename` 的反斜杠替换为 `/`，拒绝 `normalized.startswith("/")`、包含 `..`、`startswith("\\\\")` 的条目。第三个检查在替换后永远不可能命中（反斜杠已被替换），属于防御性死条件；前两个检查足以阻止 ZIP 解压时的路径穿越。

`main()` 的判定逻辑：
- `--academic`：`missing = expected_hashes - found_hashes`，`ok = not missing`；输出 `found` 与 `missing`，退出码 `0 if not missing else 1`（`scripts/check_redistributable.py:113-128`）。
- 默认（redistributable）：只要 `found_hashes` 非空即 `ok:false`，输出错误 `"restricted SnapGene-derived content present"`，退出码 `1`（`scripts/check_redistributable.py:129-142`）。
- `--restricted-hash HASH=LABEL` 可追加测试用哈希，用于在无真实 fixture 的包内做合成字节测试（`scripts/check_redistributable.py:94-103`）。

### 3.2 生物学与许可原理

受限哈希表覆盖 SnapGene 原始文件与由它们派生的 golden fixture。哈希检测不依赖路径，因此把 `pDONR201.dna` 重命名为 `renamed.dna` 或改变目录结构都无法绕过。`tests/test_license_real.py:40-48` 的 `test_real_restricted_file_is_detected_even_when_renamed` 验证了这一性质。

学术包与可再分发包的分界来自 SnapGene 官方许可声明：原始 fixture 只允许学术/非营利/政府用途；可再分发包必须完全移除这些字节及其衍生文件。该脚本为这一边界提供了可自动执行的证据。

### 3.3 实现路径

```text
CLI main() [scripts/check_redistributable.py:91]
  -> 合并 RESTRICTED_HASHES 与 --restricted-hash 追加项 [98-103]
  -> target 为目录 -> inspect_dir(target, effective_hashes) [105-106]
  -> target 为文件 -> inspect_zip(target, effective_hashes) [107-108]
  -> 不存在 -> 输出 {"ok": False, "error": "path not found"}，退出 1 [109-111]
  -> academic 模式：expected - found = missing，报告 missing 与 found [113-128]
  -> redistributable 模式：found 非空即失败 [129-142]
```

### 3.4 科学性说明与已知限制

- 限制：哈希门禁只证明“受限字节不存在”，不证明其他文件的版权状态。MIT 代码与第三方模型工件仍需 `THIRD_PARTY_NOTICE.md` 逐项声明。
- 限制：`--academic` 模式要求全部 10 个哈希都出现。若未来替换或新增 golden fixture，必须先更新 `RESTRICTED_HASHES` 与 `build_release.py` 的派生关系，否则学术包完整性检查会失败。
- 测试：`tests/test_v06.py` 的 `GeneralLicenseHashCheckerTests`（合成哈希）与 `tests/test_license_real.py` 的 `RealLicenseHashCheckerTests`（真实重命名检测）。

---

## 4. `scripts/validate_release_manifest.py`

### 4.1 技术原理

`validate_release_manifest.py` 校验 ZIP 内 `RELEASE-MANIFEST.json` 与实际归档内容的一致性。核心函数：

| 函数 | 签名 | 行号 | 作用 |
|---|---|---|---|
| `_sha256` | `_sha256(data)` | `scripts/validate_release_manifest.py:11-12` | 大写 SHA-256 |
| `_read_manifest` | `_read_manifest(archive, prefix)` | `scripts/validate_release_manifest.py:15-20` | 只接受 `prefix + "RELEASE-MANIFEST.json"` 这一精确路径 |
| `validate` | `validate(zip_path, package_kind=None, version=None)` | `scripts/validate_release_manifest.py:23-67` | 执行全部一致性检查 |
| `main` | `main()` | `scripts/validate_release_manifest.py:70-85` | CLI 入口 |

`validate()` 检查项：
1. ZIP 条目安全：`..` 或 `/` 开头（`scripts/validate_release_manifest.py:28-30`）。
2. `RELEASE-MANIFEST.json` 必须存在（`15-20`，`31-34`）。
3. 每个 manifest 条目对应文件必须在 ZIP 中，`size` 与 `sha256` 必须与 ZIP 实际字节一致（`38-49`）。
4. `redistributable=true` 的条目不得有 `exclusion_reason`（`50-51`）。
5. `--package redistributable` 时，manifest 中不得出现 `redistributable=false` 的条目（`52-53`）。
6. ZIP 内除目录项和 manifest 自身外，不得有未注册文件（`55-61`）。
7. `--version` 与 manifest `build_version` 一致（`63-64`）。
8. `build_version` 必须出现在 ZIP 文件名中（`65-66`）。

### 4.2 生物学与许可原理

该脚本不涉及分子生物学，只验证“清单—归档—版本—可再分发标记”四者的一致性。其生物学/许可含义在于：`redistributable` 标记与 `exclusion_reason` 的语义由 `build_release.py` 和 `check_redistributable.py` 定义；本脚本保证发布包没有“清单说安全、实际混入受限文件”或“清单漏写文件”的情况。

### 4.3 实现路径

```text
CLI main() [scripts/validate_release_manifest.py:70]
  -> validate(args.archive, args.package, args.version) [76]
       -> ZipFile -> namelist -> 路径安全 [26-30]
       -> _read_manifest [31-34]
       -> 逐 entry 检查 size/sha256/redistributable/exclusion_reason [38-53]
       -> 未注册文件检查 [55-61]
       -> version 与文件名检查 [63-66]
  -> errors 非空输出 {"ok": false, "errors": errors}，退出 1；否则 {"ok": true} [77-80]
```

### 4.4 科学性说明与已知限制

- 限制：`validate()` 只做结构性校验，不校验 `license` 字段的文本是否与 `THIRD_PARTY_NOTICE.md` 一致；许可证文本一致性由 `build_release.py` 生成时保证。
- 测试：包构建与清单校验组合验证在 `tests/test_release_iteration.py` 与 `tests/test_v08_dev3.py` 的发布迭代测试中覆盖。

---

## 5. `scripts/collect_release_evidence.py`

### 5.1 技术原理

`collect_release_evidence.py` 生成 `reports/release-dependency-evidence.json`。核心函数：

| 函数 | 签名 | 行号 | 作用 |
|---|---|---|---|
| `_version` | `_version(dist, fallback=None)` | `scripts/collect_release_evidence.py:12-16` | 通过 `importlib.metadata.version` 取发行版版本，失败回退 |
| `main` | `main()` | `scripts/collect_release_evidence.py:19-67` | 写依赖证据 JSON |

输出结构（`scripts/collect_release_evidence.py:21-58`）：
- `schema_version: "0.8.0-dev3"`、`project_version`（读 `VERSION`）、`python` 版本与 `python_executable`。
- `core_dependencies`：`biopython`、`snapgene_reader`、`sgffp`、`jsonschema`。
- `real_backend_dependencies`：`numpy`、`pandas`、`matplotlib`、`scikit-learn`、`torch`、`h5py`。
- `expected_reference_values`：`azimuth_30mer_score = 0.31682680735151075`，`deepcpf1_seq_only_scores` 与 `deepcpf1_chromatin_scores` 的固定期望向量。
- `instructions`：安装 requirements、运行 `check_env.py --json`、以 `SNAPGENE_RUN_REAL_MODELS=1` 等环境变量跑真实后端门禁、归档 `coverage_gate.py --mode release-real`。

### 5.2 生物学原理

`expected_reference_values` 是真实后端门禁的“金标准锚点”：
- `azimuth_30mer_score` 来自 Azimuth 2.0 V3 模型对固定 30-mer 的 on-target 评分；Azimuth 的生物学依据是 Doench et al. 2016（DOI 10.1038/nbt.3437）。
- `deepcpf1_seq_only_scores` / `deepcpf1_chromatin_scores` 来自 DeepCpf1 权重对固定序列的评分；依据 Kim et al. 2018（DOI 10.1038/nbt.4061）。
- 这些期望值的作用是检测“模型工件被替换、权重加载错位、随机初始化”等错误：真实模型在相同输入上必须复现这些数值。

### 5.3 实现路径

```text
python scripts/collect_release_evidence.py
  -> main() [19]
  -> 读 VERSION [23]
  -> _version() 探测 4 个核心依赖 + 6 个真实后端依赖 [26-39]
  -> 写 reports/release-dependency-evidence.json [59-61]
  -> stdout 打印完整 JSON [62]
```

### 5.4 科学性说明与已知限制

- 限制：`_version()` 捕获所有异常后返回 `None`（`scripts/collect_release_evidence.py:13-16`）。因此 JSON 中出现 `null` 版本只说明“未安装或元数据缺失”，不自动判定失败；判定由 `check_env.py` 完成。
- 限制：该脚本只记录环境证据，不运行模型；期望数值必须由 `coverage_gate.py --mode release-real` 或对应测试实际复现。
- 测试：`tests/test_check_env.py` 验证 `check_env.py` 输出；真实模型数值回归在 `tests/test_v08_gate_coverage.py` 的 `AdditionalCoverageTests` / `ScoringGapTests` 中覆盖。

---

## 6. `scripts/check_env.py`

### 6.1 技术原理

`check_env.py` 是环境自检器。核心数据结构：

| 常量 | 行号 | 内容 |
|---|---|---|
| `REQUIRED` | `scripts/check_env.py:20-25` | `Bio→biopython`、`snapgene_reader`、`sgffp`、`jsonschema` |
| `OPTIONAL` | `scripts/check_env.py:27-34` | `numpy`、`pandas`、`matplotlib`、`sklearn`、`torch`、`h5py` |
| `MODEL_ARTIFACTS` | `scripts/check_env.py:36-46` | 3 个模型工件的相对路径与期望 SHA-256 |

`probe(module, dist_name)`（`scripts/check_env.py:49-60`）执行 `__import__` 并尝试 `importlib.metadata.version`。`probe_model_artifacts()`（`63-78`）读取每个模型工件字节并计算 SHA-256，缺失为 `missing`，不一致为 `hash-mismatch`。`probe_snapgene()`（`81-91`）按 `SNAPGENE_EXE` 环境变量与默认安装路径探测 SnapGene 可执行文件。`probe_online()`（`94-103`）请求 NCBI eutils `esearch.fcgi` 探测联网。

`main()` 的判定（`scripts/check_env.py:129-137`）：
- `core_ok = not missing_required and not bad_artifacts`。
- `release_real_ok = core_ok and not optional_missing and primer3_core available and cas_v2 installed and cas_v3 installed`。
- 退出码只看 `core_ok`（`scripts/check_env.py:194`）：核心依赖或模型工件缺失退出 1，可选/真实后端缺失只报告不导致退出非零。这是有意的设计：开发环境可以在没有 Cas-OFFinder/GPU/PyTorch 时运行全部合成测试，但不能把缺失真实后端的环境标记为 `release_real_ok`。

### 6.2 生物学原理

- **Primer3**：`from primer3_core_backend import probe_primer3_core`（`scripts/check_env.py:119-120`）探测 `primer3_core` 可执行文件。Primer3 热力学模型是引物设计质量的核心依据（Primer3 官方手册 https://primer3.org/manual.html）。仓库 `references/biological-parameters-sources.md` 的 P03-P08 记录了盐参数、GC 窗口、长度窗口、Tm 窗口、3' GC clamp、发夹/二聚体阈值。
- **Cas-OFFinder**：`cas_offinder_adapter.detect` 探测 v2/v3 两个可执行文件（`scripts/check_env.py:122-124`）。全基因组脱靶搜索依据 Bae et al. 2014 与 Cas-OFFinder GitHub（https://github.com/snugel/cas-offinder）。
- **模型工件哈希**：Azimuth V3 与 DeepCpf1 两个权重文件的期望哈希（`scripts/check_env.py:36-46`）防止模型被部分下载、破坏或替换。

### 6.3 实现路径

```text
python scripts/check_env.py --json
  -> main() [106]
  -> probe() x 4 核心依赖 + x 6 可选依赖 [115-116]
  -> probe_model_artifacts() [117]
  -> probe_primer3_core() [119-120]
  -> detect(CAS_OFFINDER_EXE) / detect(CAS_OFFINDER_EXE_V3) [122-124]
  -> probe_snapgene() [126]
  -> probe_online() [127]
  -> 计算 core_ok / release_real_ok [129-137]
  -> --json 输出完整报告 [158-159]；文本模式打印分段报告 [160-192]
  -> sys.exit(0 if core_ok else 1) [194]
```

### 6.4 科学性说明与已知限制

- 限制：`probe_online()` 请求 NCBI 以探测联网，但实际 CRISPOR 与 NCBI 数据获取是否可用由 `online_sources.py` 与 `crispor_adapter.py` 在运行时决定；此处只做连通性快照。
- 限制：`release_real_ok` 不要求 SnapGene 与在线服务可用；官方 SnapGene 往返核验在 `validate_rich_fixtures.py` 中单独报告。
- 测试：`tests/test_check_env.py` 验证 JSON 可解析、`core_ok=true`、至少 3 个模型工件状态 `ok`。

---

## 7. `scripts/run_test_suite.py`

### 7.1 技术原理

`run_test_suite.py` 是 unittest 发现的平替入口。`scripts/run_test_suite.py:2-6` 说明：某些解释器上 `coverage run -m unittest` 会失败（unittest 模块位于 `python310.zip` 内），因此 coverage 门禁执行本文件而不是 `-m unittest`。

`main()`（`scripts/run_test_suite.py:21-42`）：
- `--allow-primer3-skip` 允许真实 primer3 测试跳过。
- `sys.path.insert(0, str(HERE))` 把 `scripts/` 放进导入路径。
- `unittest.TestLoader().discover(str(ROOT / "tests"))` 发现 `tests/` 下全部测试。
- `TextTestRunner(verbosity=1)` 运行。
- 遍历 `result.skipped`，若跳过项 id 或字符串包含 `primer3` 且未加 `--allow-primer3-skip`，打印 `REAL-PRIMER3-GATE: skipped primer3 tests are not release evidence` 并返回 1（`scripts/run_test_suite.py:31-41`）。
- 否则 `0 if result.wasSuccessful() else 1`。

### 7.2 生物学原理

真实 Primer3 测试被跳过意味着该环境没有 `primer3_core` 可执行文件。对发布门禁而言，跳过不等于通过，因为引物设计的热力学质量（Primer3 手册 https://primer3.org/manual.html）是正式发布证据链的一环。该脚本把跳过升级为失败，防止 CI 在无 Primer3 的机器上误发“测试通过”的报告。

### 7.3 实现路径

```text
python scripts/run_test_suite.py [--allow-primer3-skip]
  -> main() [21]
  -> loader.discover(tests) [28]
  -> runner.run(suite) [30]
  -> 收集 primer3 skips [31-36]
  -> 无 --allow-primer3-skip 且存在 primer3 skip -> 返回 1 [37-41]
  -> 返回 wasSuccessful() ? 0 : 1 [42]
```

### 7.4 科学性说明与已知限制

- 限制：该脚本本身不生成报告文件；覆盖率和通过数由 `coverage_gate.py` 采集。
- 测试：`coverage_gate.py` 的 `steps` 中第一项就是运行本脚本（`scripts/coverage_gate.py:226-229`）。

---

## 8. `scripts/coverage_gate.py`

### 8.1 技术原理

`coverage_gate.py` 是正式发布的覆盖率门禁，强制核心模块的行/分支覆盖率。核心模块集由三部分拼接而成（`scripts/coverage_gate.py:97`）：

| 组 | 行号 | 模块 |
|---|---|---|
| v0.5/v0.7 核心 | `scripts/coverage_gate.py:48-64` | `sg_common`、`assembly_model`、`construct_model`、`simulate_cloning`、`simulate_advanced`、`golden_gate`、`write_dna`、`validate_roundtrip`、`validate_construct`、`edit_plasmid`、`snapgene_compatibility`、`export_delivery_bundle`、`primer3_core_backend`、`design_primers`、`operation_consent` |
| v0.9 规划面 | `scripts/coverage_gate.py:69-80` | `plan_assembly`、`primer_design_engine`、`pcr_strategy`、`parts_library`、`online_sources`、`validation_crosscheck`、`planning.intent`、`planning.planner`、`planning.manual_render`、`rules.engine` |
| v0.8 CRISPR 面 | `scripts/coverage_gate.py:82-96` | `design_guides`、`cas_offinder_adapter`、`guide_scoring`、`recommend_protocol`、`characterize_reaction`、`sequence_upload_consent`、`annotate_offtargets`、`generate_crispr_design_report`、`crispor_adapter`、`protocol_evidence`、`provenance`、`azimuth_backend`、`deepcpf1_model` |

阈值（`scripts/coverage_gate.py:99-123`）：
- v0.5/v0.7 核心：行 ≥ 90%，分支 ≥ 85%。
- v0.8 CRISPR（dev3 并入）：行 ≥ 85%，分支 ≥ 75%。
- v0.9 planning：行 ≥ 75%，分支 ≥ 60%。
- `REAL_BACKEND_ONLY_MODULES = {"azimuth_backend", "deepcpf1_model"}` 在默认模式下从门禁列表移除（`scripts/coverage_gate.py:105-108`，`203-205`），但 `release-real` 模式重新纳入。

### 8.2 coverage 并行子进程机制

`coverage_gate.py` 实现的是 coverage.py 官方并行工作流，其关键点是不依赖机器上是否安装了 `coverage.pth`：

1. `_coveragerc(target_dir)`（`scripts/coverage_gate.py:128-143`）写 `coveragerc`：`branch=True`、`parallel=True`、`source` 为 `scripts/`、`planning/`、`rules/`，`concurrency=multiprocessing`。
2. `_coverage_bootstrap(target_dir)`（`146-153`）写临时 `sitecustomize.py`，内容只有 `import coverage; coverage.process_startup()`。
3. `main()` 在临时目录设置 `COVERAGE_PROCESS_START=<cfg>` 与 `COVERAGE_FILE=<data_file>`（`scripts/coverage_gate.py:214-216`），并把临时目录放到 `PYTHONPATH` 最前（`217-219`）。这样父进程与所有 Python 子进程（包括 `run_test_suite.py`、smoke、property 快速模式、rich fixture 校验中由测试再 spawn 的 CLI 子进程）都会执行 `sitecustomize.py`，由 `coverage.process_startup()` 启动并行数据收集。
4. `steps`（`scripts/coverage_gate.py:229-244`）依次运行：`run_test_suite.py`（默认加 `--allow-primer3-skip`）、`smoke_core.py`、`property_tests.py --quick`、`validate_rich_fixtures.py`；`release-real` 模式追加 `run_scenario_suite.py`。
5. `python -m coverage combine --rcfile <cfg> --data-file <data_file>` 合并并行文件（`scripts/coverage_gate.py:257-264`）。
6. `python -m coverage json ... --include scripts/*,planning/*,rules/*` 产出 `coverage.json`（`266-274`）。
7. 对每个核心模块，从 `coverage.json` 的 `files` 中按模块名匹配 `.py` 路径（`scripts/coverage_gate.py:279-289`），读取 `summary` 的 `percent_covered`、`covered_lines`、`num_statements`、`covered_branches`、`missing_branches`。
8. `_branch_percent(info)`（`163-169`）以 `covered / (covered + missing) * 100` 计算分支覆盖率；无分支时返回 100.0。
9. 对每个模块按 v0.5/v0.8/v0.9 三档阈值判定 `line_ok` 与 `branch_ok`（`305-314`），任何模块不达标或套件返回码非 0 均 `gate_ok=false`。
10. 输出 `reports/coverage/coverage-full.json` 与 `reports/coverage/coverage-gate.json`（`346-349`）。`--no-enforce` 时只报告不返回非零（`358-359`）。

### 8.3 生物学原理

覆盖率门禁的模块选择不是随意的。`assembly_model`、`simulate_cloning`、`simulate_advanced`、`golden_gate` 对应 Gibson 组装（Gibson et al. 2009，DOI 10.1038/nmeth.1318）、In-Fusion/Gateway/TOPO 等实验性模拟、Golden Gate（Engler et al. 2008，DOI 10.1371/journal.pone.0003647）。`primer3_core_backend` 与 `design_primers` 对应引物设计热力学（Primer3 手册 https://primer3.org/manual.html）。`design_guides`、`guide_scoring`、`azimuth_backend`、`deepcpf1_model`、`cas_offinder_adapter` 对应 CRISPR on/off-target 评分（Doench 2016，DOI 10.1038/nbt.3437；Kim 2018，DOI 10.1038/nbt.4061；Cas-OFFinder GitHub https://github.com/snugel/cas-offinder）。对这些模块要求高覆盖率，是因为它们承载了本工具最可能被误解为“湿实验结论”的数值输出。

### 8.4 实现路径

```text
python -X utf8 scripts/coverage_gate.py [--json] [--mode release-real]
  -> main() [172]
  -> release-real: 校验 RELEASE_REAL_ENV [189-200]
  -> 组装 core_modules；default 模式移除 REAL_BACKEND_ONLY_MODULES [202-205]
  -> TemporaryDirectory 内：
       _coveragerc -> coveragerc [211, 128-143]
       _coverage_bootstrap -> sitecustomize.py [212, 146-153]
       env 注入 COVERAGE_PROCESS_START/COVERAGE_FILE/PYTHONPATH/PYTHONUTF8 [214-222]
       _run(run_test_suite.py) [226-229]
       _run(smoke_core.py) [230-231]
       _run(property_tests.py --quick) [232-233]
       _run(validate_rich_fixtures.py) [234-235]
       release-real: _run(run_scenario_suite.py) [240-244]
       coverage combine [257-264]
       coverage json -> reports/coverage/coverage.json [266-274]
       per-module 阈值判定 [277-328]
       overall + 写 reports/coverage/coverage-full.json 与 coverage-gate.json [330-349]
  -> stdout 逐模块 PASS/FAIL、suites、gate [351-357]
  -> no-enforce ? 0 : (gate_ok and suites_ok ? 0 : 1) [358-362]
```

### 8.5 科学性说明与已知限制

- 限制：默认模式不门禁 `azimuth_backend` / `deepcpf1_model`，因为其运行需要模型工件与可选依赖；正式发布必须使用 `--mode release-real`。
- 限制：`RELEASE_REAL_ENV` 对 `CAS_OFFINDER_EXE`、`CAS_OFFINDER_EXE_V3`、`PRIMER3_CORE` 要求“文件存在”，但不会验证版本或 OpenCL 可用性；该部分由 `check_env.py` 与 `cas_offinder_adapter.detect` 补充。
- 限制：子进程输出只保留末尾 400 字符（`scripts/coverage_gate.py:249-251`），失败时需回到 `reports/coverage/coverage-full.json` 或对应报告文件排查。
- 测试：`tests/test_gate_targets.py` 是覆盖率目标的系统性填充测试；`tests/test_coverage_gap.py` 与 `tests/test_v08_gate_coverage.py` 专门补齐核心模块的边界分支。

---

## 9. `scripts/mutation_tests.py`

### 9.1 技术原理

`mutation_tests.py` 实现 v0.5 正式发布门禁要求的变异测试：对 `scripts/` 树中的源码做 12 个故意变异，每个变异必须被对应的行为检查“杀死”。门禁要求 kill rate ≥ 90%，即 12 个中至少杀死 11 个（`math.ceil(12 * 0.9) = 11`，`scripts/mutation_tests.py:40`，`required_kills` 在 `:492-496` 计算）。

关键函数：

| 函数 | 签名 | 行号 | 作用 |
|---|---|---|---|
| `_run_check` | `_run_check(check_name, scripts_dir, python)` | `scripts/mutation_tests.py:420-444` | 写 `_mutation_checks.py`，在新进程中跑指定行为检查，结果写入 `_result_*.json` |
| `_apply_mutation` | `_apply_mutation(source, mutation)` | `scripts/mutation_tests.py:447-453` | 检查 `old` 恰好出现 1 次后替换为 `new` |
| `main` | `main(argv=None)` | `scripts/mutation_tests.py:456-540` | 对每个变异：复制 `scripts/` → pristine 检查 → 施加变异 → mutant 检查 → 判定 killed/survived/check-broken/error |

`_run_check` 不使用 stdout 传递结果，因为行为检查内部可能打印 JSON 信封（如 `sg_common.jfail`）；结果文件路径经 `MUTATION_RESULT_FILE` 环境变量传递（`scripts/mutation_tests.py:396-399`，`434-437`）。`_apply_mutation` 要求 `old` 锚点在目标文件中唯一出现，否则报 `ValueError`（`447-453`），防止把变异打到错误位置。

### 9.2 12 个变异清单

`MUTATIONS` 定义在 `scripts/mutation_tests.py:47-144`：

| ID | 文件 | 变异内容 | 检查函数 |
|---|---|---|---|
| M01 | `assembly_model.py` | `if contribution <= 0:` → `if contribution < 0:` | `check_m01_zero_contribution` |
| M02 | `assembly_model.py` | Gibson overlap mismatch 检查改为 `and False` | `check_m02_overlap_mismatch` |
| M03 | `assembly_model.py` | 环状闭合 overlap 不再裁剪 | `check_m03_circular_trim` |
| M04 | `assembly_model.py` | 粘端兼容性恒为 `True` | `check_m04_sticky_compat` |
| M05 | `simulate_cloning.py` | `CompoundLocation` parts 全局按 start 排序 | `check_m05_compound_order` |
| M06 | `simulate_cloning.py` | feature `extract()` 一致性检查移除 | `check_m06_extract_check` |
| M07 | `assembly_model.py` | origin 坐标不变量禁用 | `check_m07_origins` |
| M08 | `golden_gate.py` | 允许片段内部含识别位点 | `check_m08_gg_recognition` |
| M09 | `golden_gate.py` | overhang mismatch 守卫禁用 | `check_m09_gg_mismatch` |
| M10 | `simulate_advanced.py` | Gateway att 位点唯一性检查移除 | `check_m10_att_unique` |
| M11 | `sg_common.py` | 失败信封 `ok` 误写为 `True` | `check_m11_failure_envelope` |
| M12 | `construct_model.py` | `ConstructModel.insert` 边界 `>=` 改 `>`（off-by-one） | `check_m12_insert_boundary` |

### 9.3 生物学原理

每个变异对应一个分子生物学意义上的严重错误：
- **M01/M02/M03** 对应 Gibson 组装（Gibson et al. 2009，DOI 10.1038/nmeth.1318）的贡献片段检查、overlap 序列一致性、环状组装末端裁剪。M01 若只把 `<=` 改为 `<`，长度恰等于 overlap 的零贡献片段会被接受；M02 若 `and False`，两端 overlap 不同的片段会被错误拼装；M03 若不再裁剪，环状组装产物会多出一段重复 overlap。
- **M04** 对应限制酶切粘端互补：`_complement(left.overhang_sequence) == right.overhang_sequence`（`assembly_model.py`，被 `check_m04_sticky_compat` 验证）是酶切连接的基础；恒为 `True` 会把错配粘端当作可连接。
- **M05/M06** 对应 feature 迁移顺序与提取一致性：M05 把跨原点 `join` 的 parts 错误地全局按 start 排序，破坏 `operator` 语义；M06 删除 `extract()` 一致性检查后，迁移出的 feature 可能丢失或错位而不被察觉。
- **M07** 对应 origin 坐标不变量：`validate_origins` 校验 origin 长度和等于产物长度；禁用后错误 origin 会被接受。
- **M08/M09** 对应 Golden Gate（Engler et al. 2008，DOI 10.1371/journal.pone.0003647）与 Type IIS 酶切（BsaI 识别 `GGTCTC`，切口在识别序列下游 1/5 位置）：内部含识别位点的片段会改变切点几何；overhang 错配应中止。
- **M10** 对应 Gateway BP/LR 重组（Hartley et al. 2000 等，场景来源见 `run_scenario_suite.py:527-529`）：att 位点不唯一会错误选择重组位点。
- **M11** 对应失败信封契约：`ok:false` 的失败输出若被改成 `ok:true`，下游无法区分成功与失败。
- **M12** 对应 `ConstructModel.insert` 在插入点处 feature 边界的开闭区间处理（0-based 半开区间）：`>=` 改 `>` 会把恰好从插入点起始的 feature 留在原地，造成坐标错误。

### 9.4 实现路径

```text
python -X utf8 scripts/mutation_tests.py
  -> main(argv) [456]
  -> 对 M01..M12 逐项：
       copytree(SCRIPTS, tmp/scripts) [466-468]
       _run_check(check, pristine copy) -> pristine_payload [471-472]
       _apply_mutation(target.read_text, mutation) -> 写回 [476-479]
       _run_check(check, mutant copy) -> mutant_payload [481-482]
       判定: error/check-broken/survived/killed [486-498]
  -> 统计 killed/survived/errors, kill_rate, required_kills=ceil(total*0.9) [503-508]
  -> 写 reports/mutation/mutation-gate.json [514-516]
  -> stdout 逐项结果与 gate [520-528]
  -> no-enforce ? 0 : (gate_ok ? 0 : 1) [529-532]
```

### 9.5 科学性说明与已知限制

- 限制：变异测试覆盖的是“指定 12 个锚点”，不是全部源码；未覆盖源码由覆盖率门禁与 property 测试补充。
- 限制：行为检查运行在新进程中，但 `_run_check` 固定把 `_mutation_checks.py` 写在 `scripts_dir.parent`，并依赖 `cwd=str(scripts_dir.parent)`；并发运行多个 `mutation_tests.py` 会互相覆盖临时检查文件，不适合并发执行。
- 限制：M11 的检查函数会写临时文件到系统 TMP（`scripts/mutation_tests.py:332-339`），失败残留极小但存在。
- 测试：`tests/test_release_iteration.py` 与 `tests/test_v08_dev3.py` 对门禁输出结构做断言。

---

## 10. `scripts/property_tests.py`

### 10.1 技术原理

`property_tests.py` 是全规模种子化 property 测试。规模定义在 `SCALE`（`scripts/property_tests.py:49-56`）：

| 方法 | 成功数 | 失败数 |
|---|---|---|
| `gibson` | 1000 | 300 |
| `infusion` | 1000 | 300 |
| `golden-gate` | 1000 | 300 |
| `digest-ligate` | 1000 | 300 |
| `gateway` | 500 | 200 |
| `ta` | 500 | 200 |

合计 5000 成功 + 1600 失败 = 6600 个用例。`--quick` 时 `factor = 0.05`（`scripts/property_tests.py:764-765`），即 coverage 门禁运行的 CI 规模是每个方法 5%（最少 1 个）。种子为 `SEED = 20260816`（`scripts/property_tests.py:46`）；每个方法的种子由 `args.seed + (zlib.crc32(method.encode("utf-8")) & 0x7FFFFFFF)` 生成（`786-787`），避免 Python `hash()` 随机化。

成功用例断言：
- 产物序列等于由构造几何独立计算出的期望序列（如 Gibson `_overlap_parts` 的 `expected`，`scripts/property_tests.py:178-180`）。
- `sum(contributions) == len(product.seq)`（`204-207`）。
- `_verify_features()`（`113-138`）：每个迁移 feature 的 `extract()` 必须与源 feature 一致；线组装中位于被删 overlap 内的 feature 允许缺失，环状组装必须全部保留。
- `_gb_roundtrip()`（`141-151`）：每 10 个成功用例做一次 GenBank 写读，序列不得改变。

失败用例断言：必须抛出带稳定 `AssemblyError.code` 的失败，并且每种失败模式都必须被覆盖（`seen` 集合检查，如 `scripts/property_tests.py:273-276`）。

### 10.2 各方法生成器

| 方法 | 成功生成器 | 失败生成器 | 失败模式 |
|---|---|---|---|
| `gibson` | `run_gibson_success`（`scripts/property_tests.py:184`） | `run_gibson_failure`（`213`） | `mismatch`、`zero-contribution`、`too-long`、`short-product` |
| `infusion` | 复用 Gibson 成功生成器，包裹 `simulate_advanced.infusion`（`188-194`） | 复用 Gibson 失败生成器 | 同上 |
| `golden-gate` | `run_golden_gate_success`（`312`） | `run_golden_gate_failure`（`373`） | `too-few-sites`、`site-in-fragment`、`overhang-mismatch` |
| `digest-ligate` | `run_digest_ligate_success`（`448`） | `run_digest_ligate_failure`（`492`） | `vector-no-site`、`vector-two-sites`、`insert-one-site`、`insert-three-sites`、`vector-linear` |
| `gateway` | `run_gateway_success`（`586`） | `run_gateway_failure`（`633`） | `missing-attb`、`duplicate-attb`、`wrong-orientation`、`att-order`、`empty-body`、`donor-linear`、`donor-no-topology` |
| `ta` | `run_ta_success`（`702`） | `run_ta_failure`（`722`） | `missing-cut`、`cut-negative`、`cut-too-large` |

Golden Gate 成功生成器 `_gg_part()`（`scripts/property_tests.py:284-305`）构造 `GGTCTC + A + left_overhang + body + right_overhang + A + GAGACC` 的 BsaI part，并验证序列中 `GGTCTC`/`GAGACC` 总数恰为 2，保证边界处不会因随机 body 与 overhang 拼接出额外识别位点。`run_golden_gate_success` 独立期望 `overhangs[-1] + vec_body + Σ(overhangs[i] + body_i)`（`333-336`），并校验 junction 的 `expected_junction` 等于 `reverse_complement(overhang_k)/overhang_k`（`358-364`）。

Digest-ligate 成功生成器用 EcoRI（粘端）与 SmaI（平端）交替，手工计算切点与期望产物（`scripts/property_tests.py:434-468`），并检查产物为环状、junction 全部 `ok`、insert feature 存在。

### 10.3 生物学原理

- **Gibson**：同源 overlap 末端连接，片段间 overlap 序列必须匹配，且片段贡献长度必须大于 0（Gibson et al. 2009，DOI 10.1038/nmeth.1318）。`zero-contribution` 与 `short-product` 模式正是这一生物学约束的边界。
- **In-Fusion**：仓库明确将 In-Fusion 建模为严格 overlap 拼接近似，不建模 In-Fusion 酶学（`scripts/property_tests.py:184-194` 注释与 `run_scenario_suite.py` S04 的 `approximation` 字段）。
- **Golden Gate**：BsaI 识别 `GGTCTC`，切点在识别序列下游，产生 4 nt 5' overhang（Engler et al. 2008，DOI 10.1371/journal.pone.0003647；NEB Golden Gate 协议）。失败模式覆盖“位点不足”“片段内残留识别位点”“overhang 错配”三类真实设计错误。
- **Digest-ligate**：EcoRI 产生 5' sticky overhang（Sambrook & Russell, Molecular Cloning；Bio.Restriction/BioPython 文档），SmaI 产生平端。失败模式覆盖载体位点数、插入片段位点数、载体拓扑错误。
- **Gateway**：attB×attP 与 attL×attR 重组需要位点唯一、方向正确、顺序正确；property 测试的失败模式直接对应这些约束。
- **TA**：TA 克隆要求载体有明确切口位置与 3'-T 尾、插入片段有 3'-A 尾；缺切口、负切口、超长切口为失败模式。

### 10.4 实现路径

```text
python -X utf8 scripts/property_tests.py [--methods gibson,ta] [--quick] [--json]
  -> main(argv) [765]
  -> 解析 methods；检查方法名合法性 [778-783]
  -> factor = 0.05 if quick else 1.0 [784]
  -> 逐方法：
       success_target, failure_target = SCALE[method] 并乘 factor [789-791]
       method_seed = SEED + crc32(method) [792-793]
       rng = random.Random(method_seed) [794]
       success_runner(rng, success_target) [798]
       failure_runner(rng, failure_target) [799]
       AssertionError -> 该方法 ok=false，detail 为失败信息 [800-803]
  -> 写 reports/property/property-tests.json [826-827]
  -> stdout 逐方法 PASS/FAIL 与总耗时 [828-833]
  -> 返回 0 if report["ok"] else 1 [834-835]
```

### 10.5 科学性说明与已知限制

- 限制：全量 6600 个用例耗时较长，coverage 门禁只跑 5% 快速模式；正式发布证据应以全量 `property_tests.py` 报告为准。
- 限制：property 测试是序列级、结构级不变量检查，不验证酶动力学、连接效率、重组效率等湿实验量。
- 测试：`tests/test_v06.py`、`tests/test_v08_dev3.py` 中对 property 报告结构有回归断言；coverage 门禁固定调用 `property_tests.py --quick`。

---

## 11. `scripts/smoke_core.py`

### 11.1 技术原理

`smoke_core.py` 是纯合成数据的核心烟雾/回归测试，不依赖学术 fixture，因此可以进入可再分发包。核心是三个辅助函数：`check(name, cond, detail)`（`scripts/smoke_core.py:26-32`）累积 `PASS`/`FAIL` 列表；`run(*args)`（`35-40`）以 `PYTHONIOENCODING=utf-8` 运行 `scripts/` 下 CLI 子进程；`run_ok(*args)`（`43-47`）断言子进程返回码为 0。

覆盖的关键回归（均在 `main()`，`scripts/smoke_core.py:54-513`）：
- P0：`find_sites.py` 对 EcoRI 识别起点（1-based 2）与 top cut 首碱基（1-based 3）的区分（`55-63`）；环状跨原点位点（`66-72`）；拓扑默认线性（`74-75`）。
- P1：缺失路径报错、翻译读框映射（frame 1 → +1，frame 6 → -3）、正反向引物分别加 EcoRI/BamHI 酶切位点尾巴（`78-110`）。
- P0：Gibson overlap mismatch 必须失败（`112-118`）；`write_dna.py` 写出 GenBank 回读 0 phantom features（`120-132`）；原生 `.dna` 写出与回读（`134-140`）。
- P0：`annotate.py --out-gb --enzyme`、反链 ORF 翻译（`142-165`）。
- round 3：`design_primers` 质量报告、Golden Gate BsaI 0-based 切口边界 7/11、环状产物、`experimental: true` 与 EXPERIMENTAL notes（`167-221`）；Golden Gate 线性载体拒绝环化骨架、无效插入不写产物、overhang 错配不写产物（`223-255`）；In-Fusion 标注 experimental（`257-269`）；Gibson/In-Fusion mismatch 失败（`271-291`）。
- TA/TOPO 显式前提模型：缺 `--vector-cut` 失败 `MISSING_VECTOR_CUT`，缺 `--vector-end/--insert-end` 失败 `END_TYPE_MISMATCH`，显式声明 3'-A 尾的插入片段按声明处理（`293-325`）。
- Gateway LR 合成 attL/attR 载体与 `ATT_SITE_MISSING` 失败（`327-359`）。
- `methylation.py` 不发明 dam/dcm 敏感性（`361-369`）。
- round 4：`align_seq`、`align_sanger`、`simulate_pcr`（含外向引物拒绝）、`simulate_gel`、`mutagenesis`（点突变、插入密码子、删除密码子非 3 倍与 off-frame 拒绝、overlap-pcr 未实现时大声失败）、`codon_optimize`（E. coli 反翻译、DNA 自动检测、终止密码子保持、多记录 FASTA 拒绝）、`protein_tools`（反向翻译、简并密码子、退火）（`371-513`）。

### 11.2 生物学原理

- EcoRI 识别 `GAATTC`，正链切口在识别序列第 1 个 G 后，即 1-based 识别起点 2、切口前碱基 3。该 P0 断言防止把识别起点与切点混淆（`scripts/smoke_core.py:55-63`）。
- Golden Gate 的 BsaI 识别 `GGTCTC`，正链切口在识别序列下游 1 nt，负链切口在互补链下游 5 nt；0-based 边界为 7/11（`scripts/smoke_core.py:201-205`），对应 Engler 2008（DOI 10.1371/journal.pone.0003647）与 NEB Golden Gate 协议。
- TA/TOPO 克隆的生物学前提是 3'-T 载体与 3'-A 插入；脚本要求显式声明端类型，拒绝用 `endswith` 猜测（`scripts/smoke_core.py:293-325`），避免把序列巧合当作酶学事实。
- `codon_optimize` 使用 E. coli 密码子表做反翻译，并保持终止密码子（`scripts/smoke_core.py:438-462`）。
- 引物 Tm 与酶切位点尾巴依据 Primer3 手册与 NEB 保护碱基指南（`references/biological-parameters-sources.md` P20、P28）。

### 11.3 实现路径

```text
python -X utf8 scripts/smoke_core.py
  -> main() [54]
  -> 全部 check() 调用按主题顺序执行
  -> 最后打印 "===== N passed, M failed =====" 并返回 1 if FAIL else 0 [511-513]
```

### 11.4 科学性说明与已知限制

- 限制：`smoke_core.py` 是回归测试而非完整验证；它只覆盖每个脚本的代表路径。
- 测试：`tests/test_smoke.py` 的 `SmokeCoreTests.test_smoke_core_passes` 断言返回码 0、stdout 无 `FAIL`、匹配 `N passed, 0 failed`（`tests/test_smoke.py:16-28`）。

---

## 12. `scripts/smoke_academic.py`

### 12.1 技术原理

`smoke_academic.py` 与 `smoke_core.py` 共享相同的 `check`/`run`/`run_ok`/`script` 辅助函数（`scripts/smoke_academic.py:26-51`），但在 `main()` 中插入了一段学术 fixture 专属回归（与 `smoke_core.py` 的 diff 显示，`smoke_academic.py:167-271` 为学术块）。该脚本只存在于学术包，因为它依赖 `fixtures/pDONR201.dna` 与 `fixtures/golden/`。

学术块覆盖：
- `FIXTURE = fixtures/pDONR201.dna`（`scripts/smoke_academic.py:168`）。
- 原生 `.dna` 导出真实质粒：写出后回读，序列长 4470、拓扑 circular、9 个 feature，并断言有保真度警告（`170-183`）。
- `check_env.py --json` 退出 0 且 `core_ok=true`（`185-190`）。
- `validate_construct.py` 对真实 fixture 通过，`cds_frame` 检查 ok（`192-198`）。
- 复合/跨原点 CDS 的读框检查使用提取片段长度而非外接跨度（`200-217`）。
- `edit_plasmid.py` 在真实质粒上插入 4 bp 后全长 4474，KanR feature 从 0-based 2868 迁移到 2871（1-based 2872）（`219-230`）；删除 73-100 后长度 4442（`232-238`）；点突变长度不变且碱基改变（`240-248`）。
- 编辑操作拒绝 0 位置与多碱基突变（`250-256`）。
- 裸序列解析拒绝非法符号（`258-260`）。
- 运行 `SKILL.md` 中的真实 fixture 示例命令（`262-270`）。
- 后续 Gateway BP 使用真实 `pDONR201.dna` 作为 attP 供体（`scripts/smoke_academic.py` 后段），验证 attP 区域被 attL 替代；Gateway LR 仍用合成 attL/attR（与 `smoke_core.py` 相同的后段）。

### 12.2 生物学原理

`pDONR201.dna` 是 Invitrogen Gateway 供体载体，携带 attP1/attP2 位点。Gateway BP 重组（Hartley et al. 2000，场景 S86 来源见 `scripts/run_scenario_suite.py`）将 attP 区域替换为 attL 位点，插入片段进入入门克隆。该脚本在真实载体快照上验证这一序列替换、`validate_construct` 的 CDS 读框检查，以及 `edit_plasmid.py` 对真实 GenBank feature 的坐标迁移。

### 12.3 实现路径

```text
python -X utf8 scripts/smoke_academic.py
  -> main() [54]
  -> 基础合成检查（同 smoke_core 的公共部分）
  -> FIXTURE = fixtures/pDONR201.dna [168]
  -> write_dna 导出真实质粒 -> load_seq 回读 -> 断言 4470/circular/9 features [170-183]
  -> check_env -> validate_construct -> 复合 CDS -> edit_plasmid 插入/删除/突变 -> 非法输入拒绝 [185-260]
  -> SKILL.md 示例命令 [262-270]
  -> 后续 golden_gate/infusion/TA/Gateway LR 等（同 smoke_core 后段）
```

### 12.4 科学性说明与已知限制

- 限制：`tests/test_smoke_academic.py` 使用 `@unittest.skipUnless(os.path.exists(FIXTURE))`（`tests/test_smoke_academic.py:13-14`）；可再分发包中该测试自动跳过。
- 限制：学术 smoke 依赖 `fixtures/golden/` 中的衍生文件，其坐标与长度是快照值；若上游 fixture 被替换，必须先更新 `RESTRICTED_HASHES` 与本脚本断言。

---

## 13. `scripts/build_rich_fixtures.py`

### 13.1 技术原理

`build_rich_fixtures.py` 生成 8 个全合成 rich-feature 夹具到 `fixtures/rich/`。夹具完全合成，不含 SnapGene 衍生内容，因此两个包都安全（`scripts/build_rich_fixtures.py:4-5`）。

关键函数：

| 函数 | 签名 | 行号 | 作用 |
|---|---|---|---|
| `_record` | `_record(name, sequence, circular, features)` | `scripts/build_rich_fixtures.py:37-43` | 构造带拓扑与 feature 的 `SeqRecord` |
| `_cds` | `_cds(start, end, label, strand=1, translation=None, extra=None)` | `scripts/build_rich_fixtures.py:46-54` | 构造 CDS feature，带 `label/gene/codon_start/transl_table/translation` |
| `build_fixtures` | `build_fixtures(out_dir)` | `scripts/build_rich_fixtures.py:57-190` | 写 8 个 `.gb` 文件 |
| `main` | `main(argv=None)` | `scripts/build_rich_fixtures.py:192-205` | CLI 入口 |

8 个夹具与 v0.5 门禁检查单的对应：

| 夹具 | 覆盖点 |
|---|---|
| `rich_fwd_cds.gb` | 正向 CDS，translation + 多值 `note/db_xref/EC_number` |
| `rich_rev_cds.gb` | 反向 CDS，translation 从实际提取序列计算 |
| `rich_join.gb` | `CompoundLocation(operator="join")` 三段同链 |
| `rich_order.gb` | `CompoundLocation(operator="order")` 非连续顺序 |
| `rich_cross_origin.gb` | 环状记录上跨原点 CDS（parts 12-16 与 0-5） |
| `rich_unicode.gb` | Unicode label/note（`引物设计验证 fixture · café Σ DNA π 质粒`） |
| `rich_multivalue.gb` | 多值 qualifier 压力（4 个 note、3 个 db_xref、2 个 synonym） |
| `rich_kitchen_sink.gb` | 环状综合：正向 CDS + 反链 promoter + 跨原点 misc_feature + Unicode + 多值 |

`UNICODE_NOTE` 与 `UNICODE_LABEL` 定义在 `scripts/build_rich_fixtures.py:33-34`。

### 13.2 生物学原理

正向/反向 CDS、`codon_start`、`transl_table=11` 是 GenBank CDS feature 的标准语义（BioPython `Bio.SeqFeature` 文档）。`operator="join"` 表示各部分按给定顺序连接，`operator="order"` 表示顺序可能未知或非连续（`tests/test_rich_fixtures.py` 验证不把 risky fixture 称为 lossless）。跨原点 CDS 是环状质粒上常见真实情况：基因跨过复制起点时用 `join` 表示。

### 13.3 实现路径

```text
python -X utf8 scripts/build_rich_fixtures.py [--out DIR]
  -> main() [192]
  -> build_fixtures(pathlib.Path(args.out)) [198]
       -> 逐夹具 SeqIO.write(rec, handle, "genbank") [69-186]
  -> stdout 打印 wrote ... 与总数 [199-201]
```

### 13.4 科学性说明与已知限制

- 限制：夹具是合成序列，只用于格式与往返语义测试，不代表任何天然基因或蛋白。
- 测试：`tests/test_rich_fixtures.py` 的 5 个测试直接验证这些夹具的严格往返、兼容性预检、CDS 提取、Unicode 与多值 qualifier 存活。

---

## 14. `scripts/validate_rich_fixtures.py`

### 14.1 技术原理

`validate_rich_fixtures.py` 是 rich-feature 门禁，执行“内部严格往返 + 可选官方 SnapGene 往返 + 声明式兼容性策略”三层校验。

`CORE_FIXTURES`（`scripts/validate_rich_fixtures.py:42-46`）与 `build_rich_fixtures.py` 的 8 个夹具一一对应。`_find_snapgene(explicit=None)`（`49-59`）按显式参数、`SNAPGENE_EXE`、`ProgramFiles` 下的 SnapGene 路径自动发现官方程序。`_run_roundtrip(fixture, fmt, snapgene_exe=None, require_snapgene=False)`（`62-107`）以子进程运行 `validate_roundtrip.py --format <fmt> --strict --json`，解析 JSON 中的 `internal_roundtrip` 与 `official_snapgene_roundtrip` 字段。

`main()`（`scripts/validate_rich_fixtures.py:110-210`）的判定：
- 对每个夹具先调用 `snapgene_compatibility.analyze()`（`133`）得到 `formats.snapgene-gb` 与 `formats.dna` 的 `core_safe`/`strict_safe` 策略。
- `gb_internal_ok`：内部 `snapgene-gb` 往返通过且 qualifiers 完全一致（`140-143`）。
- `dna_internal_ok`：内部 `.dna` 往返通过，或该格式预检 `core_safe=false`（`144-146`）。
- `gb_official_ok`：官方未运行（skipped）或官方通过，或预检 `core_safe=false` 时接受已知差异（`147-150`）。
- `gb_strict_ok`：官方无 qualifier 差异，或预检 `strict_safe=false` 时接受已知差异（`151-154`）。
- `dna_official_ok` 同理（`155-158`）。
- 门禁通过要求 `gb_ok and dna_ok`（`159-161`）。报告写入 `reports/rich/rich-roundtrip.json`。

`accepted_known_difference` 字段（`scripts/validate_rich_fixtures.py:166-172`）把“官方差异但预检已预测该 severity”的情况记录为 accepted finding，而不是宣称 lossless 成功。

### 14.2 生物学原理

GenBank qualifier 的精确保留对生物注释至关重要：CDS 的 `translation`、`codon_start`、`transl_table` 决定读框解释；`note`、`db_xref`、`EC_number` 携带功能与交叉引用。原生 SnapGene `.dna` 写出可能简化 qualifiers/notes/history（`SKILL.md` 注意事项）。本门禁确保：
- 内部 `snapgene-gb` 路径必须 strict 通过；
- 原生 `.dna` 路径只接受 `snapgene_compatibility.analyze` 已声明的差异；
- 官方 SnapGene 程序在场时，其转换差异必须与预检分类一致，未分类差异一律失败。

### 14.3 实现路径

```text
python -X utf8 scripts/validate_rich_fixtures.py [--snapgene-exe PATH] [--json] [--no-enforce]
  -> main() [110]
  -> fixtures/rich 目录不存在 -> 提示先运行 build_rich_fixtures.py，退出 1 [118-120]
  -> executable = _find_snapgene(args.snapgene_exe) [124]
  -> 逐夹具：
       compatibility = analyze(fixture) [133]
       snapgene_gb = _run_roundtrip(fixture, "snapgene-gb", executable, require_snapgene=bool(executable)) [134-135]
       dna = _run_roundtrip(fixture, "dna", executable) [136-137]
       计算 gb_internal_ok/dna_internal_ok/gb_official_ok/gb_strict_ok/dna_official_ok [140-158]
       gate_ok &= (gb_ok and dna_ok) [159-161]
  -> 写 reports/rich/rich-roundtrip.json [196-198]
  -> stdout 打印 gate 与 official_note [201-203]
  -> no-enforce ? 0 : (gate_ok ? 0 : 1) [204-206]
```

### 14.4 科学性说明与已知限制

- 限制：官方 SnapGene 核验在未检测到可执行文件时报告 `skipped`，不是通过；报告 `official_note` 明确写“internal strict round trip passed, official verification pending”。
- 测试：`tests/test_rich_fixtures.py` 与 `tests/test_snapgene_compatibility.py` 覆盖兼容性策略。

---

## 15. `scripts/run_scenario_suite.py`

### 15.1 技术原理

`run_scenario_suite.py` 是文献来源场景套件，当前实际生成 90 个场景（S01–S90）。每个场景带 `source`（DOI 或官方 catalog 页）、`title`、`description`、`kind`、`ground_truth` 等字段。

`scenarios()`（`scripts/run_scenario_suite.py:442-791`）用闭包 `add(kind, sid, source, title, desc, **kwargs)` 注册场景。90 个场景的生成方式分两类：直接 `add(...)` 与循环 `for sid, ... in mut_sources/expr/crispr/retry_cases: add(...)`。

### 15.2 90 场景分类

| 类别 `kind` | 数量 | ID 范围 | 典型 runner | 出处举例 |
|---|---|---|---|---|
| `plan` | 34 | S01–S03, S05–S11, S15–S16, S31–S45, S62–S68 | `run_plan_scenario` | Gibson 2009；NEB HiFi；SLIC；CPEC；BioBrick；表达标签系列；酶切连接系列 |
| `advanced` | 5 | S04, S17–S20 | `run_simulate_advanced` | In-Fusion；Gateway BP/LR；TOPO；TA |
| `golden_gate` | 3 | S12–S14 | `run_golden_gate` | Engler 2008；MoClo；GoldenBraid |
| `mutagenesis` | 10 | S21–S30 | `run_mutagenesis` | QuikChange；Kunkel；SOEing；反向 PCR；Q5 SDM |
| `crispr` | 11 | S46–S56 | `run_crispr` | Ran 2013；Cong 2013；Komor 2016；Doench 2016；Kim 2018 |
| `pcr` | 8 | S57–S59, S69–S73 | `run_pcr_strategy` | NEB Q5；Takara PrimeSTAR GXL；Phusion |
| `verification` | 2 | S60–S61 | `run_verification` | Sanger 1977；Addgene QC；Oxford Nanopore |
| `primer-retry` | 12 | S74–S85 | `run_primer_retry` | Primer3 manual；NEB；Dieffenbach 1993；Rychlik 1990；Kwok 1990；Stadhouders 2010 |
| `real-vector` | 5 | S86–S90 | `run_real_vector` | 真实载体 Gateway BP/LR、TA、Gibson、双酶切连接 |

`RUNNERS`（`scripts/run_scenario_suite.py:429-440`）把 kind 映射到执行函数。

### 15.3 场景执行器

| runner | 行号 | 执行内容 |
|---|---|---|
| `run_plan_scenario` | `scripts/run_scenario_suite.py:98-132` | `planning.intent.normalize_intent` → `planning.planner.plan_assembly` → `plan_assembly._write_construct_files` → `validate_construct.py` |
| `run_simulate_advanced` | `134-190` | 构造 Gateway/In-Fusion/TA/TOPO 输入 → `simulate_advanced.py` → `validate_construct.py` |
| `run_mutagenesis` | `193-211` | `mutagenesis.py` → `validate_construct.py` |
| `run_golden_gate` | `213-231` | 构造 BsaI parts → `golden_gate.py` → `validate_construct.py` |
| `run_crispr` | `233-249` | `design_guides.py` → `generate_crispr_design_report.py` |
| `run_pcr_strategy` | `251-267` | `pcr_strategy.recommend_pcr_strategy` → `primer_design_engine.design_region_primers` |
| `run_verification` | `269-282` | `validate_construct.py` → `find_sites.py` → `align_seq.py` |
| `run_primer_retry` | `312-383` | 构造困难模板 → `primer_design_engine.design_region_primers` 四层重试链 → 真值对比 |
| `run_real_vector` | `385-427` | 执行 `commands` 中的真实载体命令（fixtures 路径替换）→ `validate_construct.py` |

### 15.4 `ground_truth` 机制

`run_all()`（`scripts/run_scenario_suite.py:906-963`）为每个场景生成结果，`ground_truth` 有两种来源：
1. `primer-retry` 场景的 runner 返回 `detail["ground_truth"]`，由 `_retry_truth_match()`（`284-310`）判定。`expected_note` 可为 `binding-only`、`slide-retry`、`binding-only-or-slide`、`slide-retry-or-fallback`、`fallback-with-alternatives`、`primer3-core`、`require-fail-closed-with-alternatives`。判定基于返回的 `backend`、`primer3_retry_note`、`boundary_offsets`、`alternatives`、`expected_fail_closed` 等字段。
2. 其他场景若 runner 未提供 `ground_truth`，`run_all()` 写默认真值：`expected = "execution-contract-for-<kind>"`，`matches = status == "PASS"`，`note` 说明“执行级契约；论文给出的数值真值只在来源提供时记录”（`scripts/run_scenario_suite.py:929-934`）。这是诚实处理：不编造论文未给出的数值真值。因此 78 个默认 `matches=true` 只表示“程序按该场景设计执行并正常退出”，**不是**文献数值复现，也不是湿实验成功；12 个 primer-retry 场景才有专门预期值判断。

### 15.5 生物学原理与诚实近似

`run_scenario_suite.py` docstring（`scripts/run_scenario_suite.py:1-8`）明确：每个场景引用真实论文/协议，但当本工具实现的是相关但不同的模拟模型时（如 SLIC 以 Gibson 同源连接近似），报告显式写明该近似，不冒充原方法生化。`approximation` 字段逐条标注未建模的方法特异性步骤：
- S04 In-Fusion：酶学未建模，严格 overlap 拼接近似；
- S05/S06 SLIC/SLiCE：核酸外切酶/退火未建模，以 Gibson 模型近似；
- S07 CPEC：聚合酶延伸未建模，以 overlap 模型近似；
- S15/S16 BioBrick/3A：以标准酶切连接模型近似。

生物依据覆盖：Gibson et al. 2009（DOI 10.1038/nmeth.1318）、Engler et al. 2008（DOI 10.1371/journal.pone.0003647）、Doench 2016（DOI 10.1038/nbt.3437）、Kim 2018（DOI 10.1038/nbt.4061）、NEB Q5/GC-rich/长片段协议、Takara PrimeSTAR GXL、IDT oligo 设计指南、Primer3 手册（https://primer3.org/manual.html）、Cas-OFFinder GitHub（https://github.com/snugel/cas-offinder）。其余 DOI 以 `run_scenario_suite.py` 场景 `source` 字段为准。

### 15.6 实现路径

```text
python -X utf8 scripts/run_scenario_suite.py [--out-dir DIR]
  -> main() [1004]
  -> run_all(out_dir) [906]
       -> 对 scenarios() 的每个 scenario：
            TemporaryDirectory -> runner(scenario, tmp) [909-914]
            异常 -> status=FAIL, reason 记录异常 [915-922]
            ground_truth 取自 detail 或默认真值 [923-934]
            组装结果字典（含 skill_usage, sequence_profile） [936-952]
       -> 写 scenario-results.json [953-956]
       -> 写 90-scenario-execution-and-limitation-report.md [957-959]
       -> 写 scenario-validation-human-report.md [960-962]
       -> stdout: PASS/FAIL/total [963-964]
  -> 返回 0 [1008-1009]
```

### 15.7 科学性说明与已知限制

- 历史文件名 `62-scenario-...` 已改为 `90-scenario-execution-and-limitation-report.md`（`scripts/run_scenario_suite.py:957-959`），与实际场景数一致。
- 限制：`render_markdown` 的 `doi_count` 只统计 `source` 含 `"DOI"` 的条目（`scripts/run_scenario_suite.py:966`），官方 catalog 页面（如 NEB/Takara/Addgene）不会被计入 DOI 计数。
- 限制：`run_scenario_suite.py` 不保证每个场景都在本机通过；`release-real` 模式下被 `coverage_gate.py` 调用时，失败会导致门禁失败。
- 测试：`tests/test_scenario_suite_metadata.py` 的 `ScenarioMetadataTests.test_at_least_50_real_sourced_scenarios` 校验数量、id 唯一、kind 合法；`tests/test_release_iteration.py:353` 的 `ScenarioCoverageGateTests.test_expanded_suite_meets_release_counts` 校验分类下限（gibson≥3、golden≥3、overlap≥3、high_gc_at≥5、long≥3、retry≥10、digest≥3、real≥5）。

---

## 16. `references/biological-parameters-sources`

### 16.1 技术原理

`references/biological-parameters-sources.md` 是默认生物学参数的单一来源索引（人读版），`references/biological-parameters-sources.json` 是配套机读文件。规则（`references/biological-parameters-sources.md:3-5`）：任何默认值都必须能指向文件中一条记录；没有来源的参数不得作为默认值输出。

JSON 结构（`references/biological-parameters-sources.json`）：`schema_version="0.9.0"`、`retrieved_at="2026-08-19"`、`parameters` 数组，每项含 `id`、`family`、`name`、`default`、`source`、`source_url`、`retrieved_at`、`code_references`、`notes`。

### 16.2 参数总表（P01–P30）

| ID | 参数族 | 参数名 | 默认值 | 来源 | 代码引用 |
|---|---|---|---|---|---|
| P01 | Tm | Wallace 公式 | `2×(A+T)+4×(G+C)` | Wallace et al. 1979 | `scripts/validation_crosscheck.py` |
| P02 | Tm | SantaLucia 最近邻模型 | Biopython `Tm_NN` 盐校正参数 | SantaLucia 1998 | `scripts/validation_crosscheck.py`、`scripts/design_primers.py` |
| P03 | Tm | Primer3 盐参数 | Na+ 50 mM、Mg2+ 1.5 mM | Primer3 官方手册 https://primer3.org/manual.html | `scripts/primer3_core_backend.py`、`scripts/validation_crosscheck.py` |
| P04 | primer-quality | Primer3 GC 范围 | 20–80% | Primer3 官方默认 | `scripts/primer3_core_backend.py`、`scripts/primer_design_engine.py` |
| P05 | primer-quality | 引物长度范围 | 18–27 bp（CLI 默认 18–30） | Primer3 官方默认 | `scripts/primer_design_engine.py`、`scripts/design_primers.py` |
| P06 | primer-quality | Tm 目标窗口 | 目标 ±5 °C；retry 50–72 °C | Primer3 官方默认 | `scripts/primer_design_engine.py`、`scripts/design_primers.py` |
| P07 | primer-quality | 3' GC clamp | 结合区 3' 端 G/C | Primer3 官方文档 | `scripts/primer_design_engine.py` |
| P08 | primer-quality | 发夹/二聚体阈值 | hairpin TH 47 °C；self-any TH 45 °C | Primer3 官方默认 | `scripts/primer_design_engine.py` |
| P09 | primer-quality | slide-retry 预算与产物窗口 | 5' 端 ≤ min(25, n//4) nt；产物 n−100..n+100 bp | `references/release-iteration-requirements.md` §3 | `scripts/primer3_core_backend.py`、`scripts/primer_design_engine.py` |
| P10 | PCR | 退火温度策略 | Q5：按 NEB Tm Calculator，通常较低引物 Tm +3 °C，计算值 ≥72 °C 时可用两步法 72 °C；Taq/OneTaq：按产品体系取较低 Tm 减值，梯度 PCR 优化 | NEB Q5 PCR 优化说明（E0555）；NEB Tm Calculator；Taq/OneTaq 产品 protocol | `scripts/pcr_strategy.py` |
| P11 | PCR | 延伸时间 | 保守 30 s/kb | NEB Q5 protocol | `scripts/pcr_strategy.py` |
| P12 | PCR | 高 GC 判定 | GC > 70% 用 Q5 + High GC Enhancer（或 3% DMSO） | NEB GC-rich FAQ | `scripts/pcr_strategy.py` |
| P13 | PCR | AT-rich 判定 | GC < 30% 高保真酶并降低退火温度 | NEB Q5 / PCR optimization | `scripts/pcr_strategy.py` |
| P14 | PCR | 长片段判定 | >10 kb 推荐 PrimeSTAR GXL 或 Q5 长片段 | Takara PrimeSTAR GXL 产品页 | `scripts/pcr_strategy.py`、`rules/feasibility_rules.json` |
| P15 | assembly | Overlap 长度 | 15–40 bp | IDT 引物设计指南；Gibson 2009 | `planning/planner.py`、`rules/feasibility_rules.json` |
| P16 | assembly | Overlap GC | 30–70% | IDT 引物设计指南 | `planning/planner.py`、`rules/feasibility_rules.json` |
| P17 | assembly | Gibson 片段数 | 推荐 ≤4–5 段 | Gibson et al. 2009, DOI 10.1038/nmeth.1318 | `rules/feasibility_rules.json` |
| P18 | assembly | Golden Gate 片段数 | ≤8 段 | Engler et al. 2008, DOI 10.1371/journal.pone.0003647 | `rules/feasibility_rules.json` |
| P19 | assembly | Golden Gate 内部 Type IIS 位点 | 禁止，自动换 BsaI/BsmBI/Esp3I/BbsI | Engler 2008 + NEB Golden Gate | `planning/planner.py`、`rules/feasibility_rules.json` |
| P20 | restriction | 保护碱基 | NEB 5' 保护碱基表 | NEB Cleavage Close to the End | `scripts/design_primers.py` |
| P21 | restriction | 酶切位点分析 | Bio.Restriction + 直接 motif 扫描双重验证 | Bio.Restriction；NEBcutter | `scripts/sg_common.py`、`scripts/validation_crosscheck.py` |
| P22 | off-target | SpCas9 on-target 评分 | Azimuth 模型 | Doench et al. 2016, DOI 10.1038/nbt.3437 | `scripts/azimuth_backend.py` |
| P23 | off-target | AsCas12a on-target 评分 | DeepCpf1 模型 | Kim et al. 2018, DOI 10.1038/nbt.4061 | `scripts/deepcpf1_model.py` |
| P24 | off-target | 全基因组脱靶搜索 | Cas-OFFinder v2.4.1 / v3.0.0b3 | Bae et al. 2014；Cas-OFFinder GitHub | `scripts/cas_offinder_adapter.py` |
| P25 | off-target | 物种适用性警告 | Azimuth/DeepCpf1 未验证酵母；LbCas12a 拒绝 on-target 模型 | Doench 2016 / Kim 2018 | `scripts/guide_scoring.py` |
| P26 | feasibility | M2 规则阈值 | 10 条见 `rules/feasibility_rules.json` | Gibson 2009 / Engler 2008 / IDT / NEB / Primer3 | `rules/feasibility_rules.json` |
| P27 | feasibility | 构建体 >20 kb 提示电转化 | warn 级提示 | Sambrook & Russell, Molecular Cloning | `rules/feasibility_rules.json` |
| P28 | primer-quality | 尾巴/overhang 参与 Primer3 评分 | `SEQUENCE_OVERHANG_LEFT/RIGHT`；失败 binding-only 重试 | Primer3 官方文档 | `scripts/primer3_core_backend.py`、`scripts/primer_design_engine.py` |
| P29 | assembly | 融合蛋白读框检查 | junction 后读框偏移 mod 3 == 0 | Gibson 载体构建实践 | `planning/planner.py::_check_fusion_frame` |
| P30 | PCR | 克隆/验证酶选择 | 克隆 Q5；验证/菌落 PCR OneTaq | NEB 聚合酶选择表 | `scripts/pcr_strategy.py` |

### 16.3 实现路径与溯源检查

```text
开发/审查:
  1. 读 references/biological-parameters-sources.md 确定参数与来源
  2. 在对应 code_references 中核对实现
测试:
  tests/test_release_iteration.py:391 ParameterSourcesGateTests
    -> test_parameter_source_file_covers_required_families
        校验 7 个 family 都在 JSON/MD 中
        校验每项 name/default/source/source_url/retrieved_at/code_references 非空
```

### 16.4 科学性说明与已知限制

- 限制：P27 “>20 kb 提示电转化”来自实验室共识（Molecular Cloning），只作 `warn` 级提示，不作 `error` 阻断（`references/biological-parameters-sources.md:49-50`）。
- 限制：P09 的 slide-retry 只放宽边界与产物窗口，GC 仍保持 Primer3 默认 20–80%；放宽 GC 必须走 `operation_consent.py` 的 `relaxation` 类别并记录到 operation log（`references/biological-parameters-sources.md:46-48`）。
- 限制：检索日期统一为 2026-08-19（`references/biological-parameters-sources.md:7`），URL 可能随时间失效。

---

## 17. 门禁矩阵与发布前执行链

### 17.1 门禁矩阵

| 门禁 | 脚本 | 默认模式 | release-real 模式 | 输出 |
|---|---|---|---|---|
| 环境自检 | `check_env.py` | `core_ok` 必须 true | 额外要求 `release_real_ok=true` | stdout/JSON |
| 单测+Primer3 跳过 | `run_test_suite.py` | 脚本本体默认禁止 Primer3 skip；coverage 默认模式调用时加 `--allow-primer3-skip` | 不应有 Primer3 skip | 退出码 |
| 覆盖率 | `coverage_gate.py` | 核心模块 90/85、v0.8 85/75、v0.9 75/60 | 额外纳入 `azimuth_backend`/`deepcpf1_model`，追加场景套件 | `reports/coverage/coverage-gate.json` |
| 变异 | `mutation_tests.py` | 12 个，kill rate ≥ 90% | 同默认 | `reports/mutation/mutation-gate.json` |
| property | `property_tests.py` | 全量 6600（发布证据）；CI `--quick` 5% | 同默认 | `reports/property/property-tests.json` |
| 核心 smoke | `smoke_core.py` | 必须通过 | 同默认 | stdout |
| 学术 smoke | `smoke_academic.py` | 仅学术包 | 同默认 | stdout |
| rich fixture | `build_rich_fixtures.py` + `validate_rich_fixtures.py` | 必须通过 | 同默认 | `reports/rich/rich-roundtrip.json` |
| 场景套件 | `run_scenario_suite.py` | 独立运行 | 被 coverage release-real 调用 | `reports/scenarios/` |
| 打包 | `build_release.py` + `validate_release_manifest.py` + `check_redistributable.py` | 构建后校验 | 同默认 | ZIP + manifest |
| 证据收集 | `collect_release_evidence.py` | 按需运行 | 发布前必跑 | `reports/release-dependency-evidence.json` |

### 17.2 最小发布前命令链

```bash
python -X utf8 scripts/check_env.py --json
python -X utf8 scripts/collect_release_evidence.py
python -X utf8 scripts/coverage_gate.py --json
python -X utf8 scripts/mutation_tests.py --json
python -X utf8 scripts/property_tests.py --json
python -X utf8 scripts/validate_rich_fixtures.py --json
python -X utf8 scripts/build_release.py . dist --version 0.8.0-dev3
python scripts/check_redistributable.py dist/snapgene-dna-design-v0.8.0-dev3-redistributable.zip
python scripts/check_redistributable.py dist/snapgene-dna-design-v0.8.0-dev3-academic-full.zip --academic
python scripts/validate_release_manifest.py dist/snapgene-dna-design-v0.8.0-dev3-redistributable.zip --package redistributable --version 0.8.0-dev3
python scripts/validate_release_manifest.py dist/snapgene-dna-design-v0.8.0-dev3-academic-full.zip --package academic-full --version 0.8.0-dev3
```

`coverage_gate.py --mode release-real` 还要求预置 `SNAPGENE_RUN_REAL_MODELS=1`、`SNAPGENE_RUN_PRIMER3=1`、`SNAPGENE_RUN_ONLINE=1`、`PRIMER3_CORE`、`CAS_OFFINDER_EXE`、`CAS_OFFINDER_EXE_V3`（`scripts/coverage_gate.py:110-115`、`scripts/collect_release_evidence.py:49-57`）。

### 17.3 门禁之间的数据流与重复证据边界

门禁之间既有数据流，也有刻意保留的重复验证边界：

- `run_test_suite.py` 发现并运行 `tests/` 下全部测试；`coverage_gate.py` 又通过 `sitecustomize.py` 机制采集这些测试触发的所有子进程覆盖。两者不重复：前者只关心“测试是否通过”，后者只关心“核心模块被测试执行了多少行/多少分支”。
- `smoke_core.py` 与 `tests/test_smoke.py` 之间有刻意重复：`tests/test_smoke.py` 是 unittest 适配器，负责让 `smoke_core.py` 进入 `run_test_suite.py` 的发现范围；`coverage_gate.py` 又单独运行一次 `smoke_core.py`，原因是 smoke 的许多断言走 CLI 子进程，子进程路径也需要被覆盖采集。两次执行的输入相同、证据用途不同，因此不算重复证据。
- `mutation_tests.py` 与 `property_tests.py` 从不同角度保护同一批组装模块：property 测试验证“随机输入空间上的结构不变量”，变异测试验证“特定错误锚点被测试杀死”。两者不能互相替代。
- `validate_rich_fixtures.py` 依赖 `fixtures/rich/`，而 `fixtures/rich/` 由 `build_rich_fixtures.py` 生成。发布流程中应先执行生成器，再执行校验器；若生成器产物未提交，校验器会以“fixtures/rich not found”失败（`scripts/validate_rich_fixtures.py:118-120`）。
- `check_redistributable.py` 与 `validate_release_manifest.py` 都检查 ZIP，但前者检查“受限字节是否出现”，后者检查“清单与归档是否一致”；两者共同构成发布包的双重门禁。
- `collect_release_evidence.py` 不产生通过/失败结论，只记录依赖版本与模型期望值；它必须与 `check_env.py`、`coverage_gate.py --mode release-real` 的通过结论配套使用，不能单独作为发布证据。

### 17.4 开发态与发布态的执行边界

开发态（本仓库当前状态）允许：
- `check_env.py` 退出 0 只要求核心依赖与模型工件；
- `coverage_gate.py` 默认模式排除 `azimuth_backend`/`deepcpf1_model`；
- `run_test_suite.py` 默认不允许 Primer3 跳过，但 `coverage_gate.py` 默认步骤给它加 `--allow-primer3-skip`（`scripts/coverage_gate.py:226-229`）；
- `validate_rich_fixtures.py` 在没有 SnapGene 官方程序时报告 skipped，但内部 strict 必须通过。

发布态要求更严：
- `check_env.py` 的 `release_real_ok` 必须为 true；
- `coverage_gate.py --mode release-real` 必须通过，且场景套件进入覆盖范围；
- Primer3 跳过不得作为发布证据；
- 官方 SnapGene 程序在场时，官方差异必须与 `snapgene_compatibility.analyze` 的预检分类一致；
- `property_tests.py` 必须跑满 6600 个用例，不能用 `--quick` 替代。

这些边界在 `DEVELOPMENT-NOTICE.md` 与 `collect_release_evidence.py` 的 `instructions` 中都有对应声明：真实后端门禁运行真实可执行文件/模型，占位或跳过测试不得作为发布证据。

后续迭代若继续扩展场景套件或门禁脚本，应注意保持四类证据一致：脚本 docstring 中的门禁目标、`reports/` 下机器可读报告、`tests/test_release_iteration.py` 中的门禁断言、以及本章的文字说明。任何一边单独更新都会造成“代码说通过、报告说通过、测试说未检查、文档说通过”的错位。尤其当 `run_scenario_suite.py` 的场景总数或分类再次变化时，应同步更新 `tests/test_scenario_suite_metadata.py` 与 `tests/test_release_iteration.py:353` 的分类下限，（该历史文件名问题已修正为 `90-scenario-execution-and-limitation-report.md`）。

### 17.5 门禁脚本与领域代码的边界

本章 14 个脚本都属于“开发基础设施”，它们不直接输出质粒文件、引物序列或 CRISPR 报告，而是保证那些领域脚本的输出可信。因此本章不重复展开 `ConstructModel.insert`、`AssemblyError` 等核心模型的内部实现（见第 1–5 章），只在门禁语境下引用它们的关键锚点，例如 `mutation_tests.py` 的 M12 直接锚定 `construct_model.py` 中插入点边界的 `>=` 与 `>` 差异，`property_tests.py` 的 `_verify_features` 直接调用 `SeqFeature.extract` 比较迁移前后序列。读者在排查门禁失败时，应先把失败定位到具体领域模块，再回到对应章节阅读该模块的数据结构与算法。

---

## 18. 本章覆盖脚本清单

| 脚本 | 主要函数/常量 | 关键行号 | 输出/报告 |
|---|---|---|---|
| `scripts/build_release.py` | `_collect`、`_classify`、`_write_zip`、`main` | `54-316` | 两个 ZIP、`DEVELOPMENT-MANIFEST.json` |
| `scripts/check_redistributable.py` | `RESTRICTED_HASHES`、`inspect_zip`、`inspect_dir`、`main` | `20-146` | stdout JSON |
| `scripts/validate_release_manifest.py` | `validate`、`main` | `23-85` | stdout JSON |
| `scripts/coverage_gate.py` | `CORE_MODULES`、`_coveragerc`、`_coverage_bootstrap`、`main` | `48-375` | `reports/coverage/coverage.json`、`coverage-full.json`、`coverage-gate.json` |
| `scripts/mutation_tests.py` | `MUTATIONS`、`CHECK_CODE`、`_run_check`、`_apply_mutation`、`main` | `40-551` | `reports/mutation/mutation-gate.json` |
| `scripts/property_tests.py` | `SCALE`、`run_gibson_success`、`run_golden_gate_success`、`main` | `46-835` | `reports/property/property-tests.json` |
| `scripts/run_test_suite.py` | `main` | `21-46` | 退出码 |
| `scripts/smoke_core.py` | `check`、`run`、`main` | `26-514` | stdout |
| `scripts/smoke_academic.py` | `check`、`run`、`main` | `26-660` | stdout |
| `scripts/validate_rich_fixtures.py` | `CORE_FIXTURES`、`_run_roundtrip`、`main` | `42-210` | `reports/rich/rich-roundtrip.json` |
| `scripts/build_rich_fixtures.py` | `build_fixtures`、`main` | `57-205` | `fixtures/rich/*.gb` |
| `scripts/check_env.py` | `probe`、`probe_model_artifacts`、`main` | `49-198` | stdout JSON |
| `scripts/collect_release_evidence.py` | `_version`、`main` | `12-67` | `reports/release-dependency-evidence.json` |
| `scripts/run_scenario_suite.py` | `scenarios`、`RUNNERS`、`run_all`、`render_markdown`、`main` | `429-1013` | `reports/scenarios/scenario-results.json` 等 |

---

## 19. 关键测试清单

| 测试文件 | 测试类/方法 | 覆盖内容 |
|---|---|---|
| `tests/test_check_env.py` | `CheckEnvTests.test_core_report_json_is_parseable_and_artifacts_checked` | `check_env.py` 核心报告与模型工件哈希 |
| `tests/test_smoke.py` | `SmokeCoreTests.test_smoke_core_passes` | `smoke_core.py` 全通过 |
| `tests/test_smoke_academic.py` | `SmokeAcademicTests.test_smoke_academic_passes` | `smoke_academic.py` 全通过（学术 fixture 存在时） |
| `tests/test_rich_fixtures.py` | `RichFixtureRoundTripTests`（5 个测试） | rich fixture 内部 strict 往返、兼容性预检、跨原点 CDS、Unicode/多值 qualifier |
| `tests/test_smoke_self_test.py` | `SmokeSelfTestTests` | smoke 模块自身失败路径 |
| `tests/test_gate_targets.py` | `DefaultOutputFormatTests`、`ConstructModelTests`、`SgCommonTests` 等 | 覆盖率门禁核心模块的系统性路径 |
| `tests/test_coverage_gap.py` | `SgCommonGapTests`、`AssemblyModelGapTests`、`CloningGapTests` 等 | 核心模块边界分支补齐 |
| `tests/test_v08_gate_coverage.py` | `DesignGuidesGapTests`、`CasOffinderGapTests`、`ScoringGapTests` 等 | v0.8 CRISPR 模块覆盖率补齐 |
| `tests/test_release_iteration.py` | `ConsentBrokerTests`、`PrimerEngineConsentGateTests`、`TransparencyGateTests`、`SlideRetryRealEngineTests`、`ScenarioCoverageGateTests`、`ParameterSourcesGateTests` | 发布迭代的 consent/透明/slide-retry/场景分类/参数溯源 |
| `tests/test_scenario_suite_metadata.py` | `ScenarioMetadataTests.test_at_least_50_real_sourced_scenarios` | 场景数量、id 唯一、kind 合法 |
| `tests/test_v06.py` | `GeneralLicenseHashCheckerTests`、`SchemaContractTests` | 合成哈希检测与 schema 契约 |
| `tests/test_license_real.py` | `RealLicenseHashCheckerTests.test_real_restricted_file_is_detected_even_when_renamed` | 真实受限 fixture 重命名后仍被检出 |
| `tests/test_readme_commands.py` | `ReadmeCommandTests` | README/SKILL 示例命令可运行 |

---

*本章结束。至此，包结构/核心格式、引物与 PCR、组装与分析、规划与在线源、CRISPR、打包发布/测试/场景/溯源六部分均已覆盖。*


# 第 7 章：验证记录

- 验证日期：2026-08-21
- 验证目的：确认本说明书与当前代码一致（脚本数量、函数路径、测试名称、场景数量均以本次运行实际输出为准）。
- 解释器：`C:\Users\祝浩淇\AppData\Local\Programs\Python\Python312\python.exe`（Python 3.12.4）；不使用系统默认 `python`。环境搭建见第 0.5 节。

## 7.1 全量单元/集成测试

命令：

```text
cd D:\codex_project\snapgene-dna-design-v0.9.0-work
$env:PYTHONPATH='D:\codex_project\.tmp\dev2-deps;D:\codex_project\snapgene-dna-design-v0.9.0-work;D:\codex_project\snapgene-dna-design-v0.9.0-work\scripts'
$env:PRIMER3_CORE='D:\codex_project\.primer3-artifacts\wheel\primer3\src\libprimer3\primer3_core.exe'
$env:SNAPGENE_RUN_PRIMER3='1'
$env:CAS_OFFINDER_REGISTRY='D:\codex_project\.tmp\cas-offinder-registry-dev2.json'
D:\anaconda\python.exe -X utf8 -B -m unittest discover -s tests
```

结果：`Ran 427 tests`，`OK (skipped=7)`，失败 0。
本机解释器：Python 3.14.6；依赖使用隔离目录 `D:\codex_project\.tmp\dev2-deps`。

skipped=13 的构成与手册一致：真实后端/在线开关未打开的集成用例按仓库策略跳过（`PRIMER3_CORE`、`CAS_OFFINDER_EXE(_V3)`、`SNAPGENE_RUN_REAL_MODELS`、`SNAPGENE_RUN_ONLINE` 等），每个 skip 都输出固定原因字符串，不视为通过。

## 7.2 90 场景文献套件

命令：

```text
$env:PYTHONPATH='D:\codex_project\.tmp\dev2-deps;D:\codex_project\snapgene-dna-design-v0.9.0-work;D:\codex_project\snapgene-dna-design-v0.9.0-work\scripts'
$env:PRIMER3_CORE='D:\codex_project\.primer3-artifacts\wheel\primer3\src\libprimer3\primer3_core.exe'
D:\anaconda\python.exe -X utf8 -B scripts/run_scenario_suite.py --out-dir reports/scenarios
```

结果：`PASS 90 / FAIL 0 / total 90`。
状态分布：complete=40 / partial=11 / blocked=39。
ground_truth：90/90 场景执行契约通过；其中 12 个 primer-retry 场景有专门预期值判断，其余 78 个场景为 execution-contract（只证明程序按预期执行并退出，不构成文献数值复现或湿实验成功证据）。本轮 90 个场景均无崩溃，complete=40、partial=11、blocked=39。PASS 包含 `executed`、`partial-analysis` 与明确预期的 `blocked-as-designed`；blocked 场景不写最终构建体。
机器结果：`reports/scenarios/scenario-results.json`；紧凑执行/限制表：`reports/scenarios/90-scenario-execution-and-limitation-report.md`；人类可读报告：`reports/scenarios/scenario-validation-human-report.md`。

## 7.3 与手册的对照结论

- 脚本覆盖：手册第 1-6 章覆盖 `scripts/` 全部 70 个 `.py` 脚本；第 3 章补遗补上 `generate_design_report.py`。
- 模块覆盖：`planning/`、`rules/`、`parts/`、`references/`、`schemas/`、`fixtures/` 均在各章内出现。
- 测试名核对：各章“关键测试清单”中的类/方法名来自 `tests/` 实际文件；本次全量运行通过，未发现手册引用不存在的测试。
- 遗留提示：行号引用以 2026-08-22 dev2 快照为准；后续改动请以 `progress.md` 与 `references/upgrade-log.md` 同步修订本手册。


---

# 第 8 章：v0.9.0-dev1 Natural-language Construction Agent Core 增补

v0.9.0-dev1 在保持第 1-7 章全部 CLI/引擎能力不变的前提下新增上层 Agent：

## 8.1 新增文件与职责
- `schemas/design-spec-v1.json`：DesignSpec JSON Schema。
- `design/spec.py`：9 状态状态机、探索/正式模式、证据分层、序列来源、revision/diff。
- `scripts/validate_design_spec.py`：规格校验。
- `agent/clarification.py` + `references/clarification-rules.json`：must-ask/default-visible/derived。
- `agent/nl_parser.py`：确定性自然语言解析（仅产出草稿/问题/假设/文件角色）。
- `agent/session.py`：文件摘要、哈希绑定、revision。
- `planning/method_selector.py`：7 方法候选比较与排除证据。
- `agent/orchestrator.py`：调度现有 CLI；`agent/delivery.py`：统一交付包。
- `scripts/run_design_agent.py`、`scripts/diff_design_spec.py`。

## 8.2 状态机
`draft -> needs-clarification -> user-confirmed -> evidence-resolved -> planned -> executed -> verified -> delivered`，任一节点可入 `blocked`；非法迁移抛 `DesignSpecError`；已确认规格修改必须 revision。

## 8.3 探索/正式
exploration 永远 `ready_to_order=false, ready_for_wet_lab=false`；formal 要求用户确认、输入哈希绑定、真实 Primer3、网络序列 accession/版本/日期/哈希、上传授权、QC 与往返验证、零 blockers，否则失败关闭。

## 8.4 序列来源
每个来源记录 `source_id/source_type/source_path/accession/sha256/interval_0based/strand/transformations`；正式模式禁止大模型直接生成最终构建体碱基序列。

## 8.5 方法选择
评分只用于排序，不是成功率；输出 selected 与 excluded，每条带 advantages/risks/required_materials/hard_blockers/assumptions/source_evidence。

## 8.6 交付
`DELIVERY-MANIFEST.json` 绑定 spec_id/revision/SHA、输入输出哈希、软件/后端版本、生成时间、验证等级；`.dna` 不安全时省略并写原因。

## 8.7 测试
`tests/test_v09_agent.py`：DesignSpec 状态/来源/formal/exploration、NL 30 场景、方法选择 10 矩阵、10 端到端链、CLI/diff。

## 8.8 dev1 当时为何仍是 dev（历史记录）
dev1 的未完成项包括真实后端、官方 SnapGene `.dna` 核验和独立审计；这些项在
dev2 已完成本机证据闭环，历史报告 `reports/v09-dev1-agent-core-report.md`
仅用于追溯，不代表 dev2 当前状态。

---

# 第 9 章：v0.9.0-dev2 生物学技术审计闭环（2026-08-22）

## 9.1 本轮实际修复

- 场景套件严格区分 `executed`、`partial-analysis` 与
  `blocked-as-designed`；不可行规划和真实载体失败关闭时不写任何最终构建体。
- TOPO/TA 场景必须显式传入 `--allow-experimental-output`，并在结果中写明
  末端化学未建模。
- 真实 pDONR201/pENTR-EmGFP Gibson 区间改为完整 feature 区间，避免部分
  feature 映射被错误当成完整构建。
- indel 插入/删除打断 CDS 时自动加入 `partial=true` 与“功能不作完整断言”
  注释；带有明确 `fragment` 来源注释的 CDS 不再被误判为完整 ORF。
- 场景报告的字符串详情、空值和 outcome 汇总路径均做了类型安全处理。

## 9.2 最终验证证据

| 证据 | 实测结论 |
|---|---|
| 全量 unittest | 427 OK，7 skip，0 failure/error |
| coverage gate | `gate_ok=true`、`suites_ok=true`；所有模块达到各自 line/branch 门槛 |
| mutation | 12/12 killed，100% |
| property | Gibson/In-Fusion/Golden Gate/digest-ligate 各 1000+300；Gateway/TA 各 500+200，全部 PASS |
| 90 场景 | PASS 90 / FAIL 0；complete 40 / partial 11 / blocked 39；ground_truth 90/90 |
| 真实后端 | Cas-OFFinder v2/v3、Azimuth、DeepCpf1、Primer3 真实测试 8/8 OK |
| 在线来源 | 仅公开关键词 EGFP 的 NCBI 查询 1/1 OK；无用户序列上传 |
| 官方 SnapGene | `D:\SnapGene\SnapGene.exe` 官方往返：8 fixtures、GenBank/.dna 两路径，declared compatibility gate PASS |

## 9.3 当前交付语义

本版本仍是开发快照（dev，非 RC）。所有可写出的最终构建物必须来自已验证
executor；实验性 TA/TOPO 和其他方法近似结果只能在显式标志下输出，并保留
`final_deliverable=false`。`.gb` 是元数据权威格式；`.dna` 只在兼容性门禁允许
时提供。以上是已经实现并由测试强制的交付规则，不是待修复事项。
