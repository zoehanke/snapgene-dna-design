---
name: "snapgene-dna-design"
description: "SnapGene-compatible DNA plasmid design toolkit. Parses .dna/.gb files, analyzes sequences, finds restriction sites, designs primers, runs validated basic simulations plus clearly labeled experimental cloning approximations, annotates features, and exports SnapGene-readable files. Invoke when user asks to design or analyze a plasmid, work with SnapGene .dna files, design primers, simulate cloning, find restriction sites, or generate construct files (质粒设计、引物设计、酶切分析、克隆模拟、SnapGene 文件处理)."
---

# SnapGene DNA Design

面向分子克隆与基因编辑的质粒与 DNA 智能设计工具链。当前版本：**v0.9.1-dev2（3+1 分层架构开发版）**。

## 核心设计哲学：手脚原子化，流程标准化，底线客观化

本工具库的核心目标是**为 AI Agent 配备一套完备的生物学“手和脚”**：
- **AI 负责决策与调度**：拥有足够的科研智商去理解生物学意图、判断实验可行性；
- **Tier 1 原子工具库（Hands & Feet）**：28 个纯物理/数学操作原语（如酶切、退火、引物二聚体初筛、读码框审计等），不代替 AI 做主观判断；
- **Tier 2 黄金实验 SOP 配方库（Standard Recipes）**：针对 7 大常规高频湿实验，固化国际权威经典手册与顶刊文献标准，防止 AI“突发奇想”或“丢三落四”；遇到复杂非标准任务时，AI 可自由下潜到 Tier 1 灵活编排；
- **Tier 3 客观生物学底线清单（Guardrails）**：基于事实对移码、PAM 复切、转录终止等做客观自检，绝不主观死锁。

---

## 7 大全景黄金实验 SOP 配方库 (`core/recipes/`)

常规实验任务中，AI 应优先调用标准配方以保证设计符合权威实验室标准。所有配方在输出中均携带 `"authoritative_sources"` 学术出处：

| 配方函数 | 核心适用场景 | 权威国际手册出处 | 核心固化规范 |
| :--- | :--- | :--- | :--- |
| **`recipe_restriction_cloning`** | 限制性双酶切克隆 | CSHL《分子克隆》第 4 版 & NEB | 5' 挂载 2~6 bp 保护碱基；单切/平端去磷酸化；DpnI 模板消化；摩尔比 1:3~1:5 |
| **`recipe_gibson_assembly`** | 同源重叠无缝组装 | Gibson 2009 (*Nat Methods*) & NEB | 20~25 bp 重叠臂；Tm $60\pm 2^\circ\text{C}$，$\Delta Tm \le 2^\circ\text{C}$；短片段防嚼毁预警 |
| **`recipe_golden_gate`** | Type IIS 模块化一锅法 | Engler 2008 (*PLoS ONE*) & Potapov 2018 | 4-bp 粘端严格正交无回文；识别位点朝内并在组装后 100% 剥离 |
| **`recipe_crispr_hdr_donor`** | CRISPR 靶点与 HDR 供体 | Ran 2013 (*Nat Protoc*) & Paquet 2016 | ssODN 40~60 nt 同源臂；PAM 同义静默突变防体内复切；U6 启动子 5' G 校验 |
| **`recipe_site_directed_mutagenesis`** | 定点突变与密码子工程 | Zheng 2004 (*NAR*) & QuikChange 手册 | 突变位点居中，两侧对称 10~15 bp 完全匹配翼；$Tm \ge 78^\circ\text{C}$；强制 DpnI 消化母本 |
| **`recipe_protein_tagging`** | 表达标签与融合蛋白工程 | Terpe 2003 & Kozak 1986 (*Cell*) | C 端融合强制剥离原 CDS 终止；Linker 长度整除 3；真核 Kozak (`GCCACC`) 前置；TEV/3C 蛋白酶切位点 |
| **`recipe_cloning_verification`** | 分子质检与测序引物布局 | CSHL《分子克隆》第 4 版 & Sanger 1977 | **菌落 PCR 跨接缝**（一端骨架一端插入，防假阳性）；**Sanger 避坑窗**（引物锚定在接缝上游 50~100 bp） |

---

## 28 个 Tier 1 原子生物学工具分类索引 (`core/tools/`)

当面对非标准、探索性或复杂实验时，AI 可直接调用下列原子工具自由组合：
- **序列检视**：`inspect_dna`, `find_open_reading_frames`
- **内切酶与末端化学**：`find_restriction_sites`, `digest_sequence`, `digest_type_iis`, `fill_or_chew_overhang`, `check_overhang_compatibility`
- **引物与热力学**：`calc_primer_tm`, `check_primer_dimers`, `anneal_oligos`, `design_overhang_primers`, `simulate_pcr`
- **同源与组装模拟**：`simulate_overlap_assembly`, `simulate_golden_gate`, `simulate_digest_ligation`
- **序列手术与重构**：`mutate_sequence`, `strip_terminal_codons`, `translate_dna`, `check_reading_frame`, `get_codon_synonyms`, `fuse_in_frame`, `get_standard_element`
- **CRISPR 核心运算**：`design_crispr_grna`, `prepare_grna_oligos`, `extract_homology_arms`
- **图谱与文件交互**：`read_plasmid_file`, `export_plasmid_file`, `open_in_snapgene`

---

## 核心原则：LLM 负责理解与决策，程序负责精确计算与底线拦截

**LLM 必须做：**

1. 理解自然语言与生物学实验意图（如启动子替换、点突变、荧光标记融合等）；
2. 识别任务类型并选择优先走标准 SOP 还是调用原子工具下潜探索；
3. 核查输出报告中的 quality checks 与警告，向用户清晰解释设计原理与实验提示；
4. 结合实验场景明确指出所依据的国际权威文献来源。

**LLM 禁止做：**

1. 凭空捏造长链 DNA 序列或随意猜测坐标；
2. 破坏读码框或在融合蛋白中遗漏终止密码子剥离；
3. 在标准流程中丢弃必要的负控、DpnI 消化提醒或 PAM 静默突变；
4. 绕过生物学客观自检闸门。

公共 seam 只有这五个函数。`finalize` 只接受 `mode=formal`、用户确认、`verified` 且 `method_maturity=validated` 的构建；失败时不创建 `authoritative/`。

## task kind 路由表

| task_kind | 状态 | 必填关键字段 | 产物拓扑 |
|---|---|---|---|
| `component_amplification` | 已迁移 | template + 明确 feature/interval；环状全长与近全长默认拒绝 | linear |
| `plasmid_replace` | 已迁移 | backbone + replace interval + replacement interval | circular |
| `plasmid_insert` | 已迁移 | backbone + 唯一插入边界 + insert interval | circular |
| `point_mutation` | 已迁移 | `mutations[{position_1based, ref, alt}]` | 同模板 |
| `overlap_assembly` | 已迁移 | 全部片段显式 interval + order + overlap_length；overlap 不匹配即拒绝 | circular/linear |
| `protein_fusion` | 已迁移 | partner5/partner3 显式区间 + stop_policy + 可选 linker；读框与翻译强制校验 | linear |
| `integration_donor` | 已迁移 | template 组件边界 + homology_arms + locus；臂与座位强制匹配 | linear |
| `gateway_recombination` | 已迁移 | reaction bp/lr + entry/destination source + stop_policy；唯一 att 对强制校验 | circular |
| `restriction_ligation` | 已迁移（experimental） | vector/insert + enzymes + orientation；位点唯一、黏端兼容、闭环强制校验 | circular |
| `hierarchical_assembly` | 已迁移 | stages 图 + 每级 fragments/overlap/topology；逐级独立验证 | circular/linear |
| `crispr_editing` | 已迁移（experimental） | nuclease + reference + target interval + guide/donor 策略 | 同 reference |

`method_maturity=experimental` 的 kind（restriction_ligation、crispr_editing）产物只能为 `experimental-preview`，闸门拒绝其进入 authoritative。未注册 kind 返回 `TASK_KIND_NOT_REGISTERED`，不退回通用组装器。

## 三层验证

- `artifact-valid`：文件可读、序列非空、拓扑正确、feature 坐标/strand 合法、CDS 一致、格式往返符合声明等级。
- `computation-valid`：从记录的输入与 transformation 独立重建序列，与产物一致。
- `goal-valid`：required/forbidden 组件、操作类型、区间、方向、拓扑满足用户目标；供体做骨架污染检查。

```text
verified = artifact-valid AND computation-valid AND goal-valid
```

## 唯一正式产物闸门

只有 `core.finalize()` 可生成：

```text
authoritative/construct.gb
authoritative/construct.fasta
authoritative/construct.dna
authoritative/DELIVERY-MANIFEST.json
```

其他脚本只能写 `preview/`、`intermediate/`、`experimental-preview/`。`.gb/.dna` 扩展名不构成权威性；权威性只由 `DELIVERY-MANIFEST.json` 中的 `artifact_class=authoritative` 与闸门签发决定。

## 隐私、来源与实验性结果硬规则

- 任何序列上传默认拒绝；在线服务（BLAST/CRISPOR 等）需用户明确同意。
- 每个来源必须携带 `source_evidence_class`（`user-provided` / `public-record` / `internal-fixture` / `synthetic-fixture` / `heuristic`）与 SHA-256；派生产物等级不得高于最弱关键来源。
- `method_maturity=experimental` 的产物只能是 `experimental-preview`，不得进入 authoritative，也不得声称可下单或用于湿实验。
- 所有计算结果均为序列级预测；湿实验结论必须由实验获得。

## 低层工具与旧路径

大多数脚本支持 `--json`，可直接作为**预览级**工具使用（设计引物、找酶切位点、模拟 PCR 等），但直接脚本产物不是权威交付。v0.9.0 的关键词 Agent 正式路径已弃用（`run_design_agent.py --mode formal` 返回 `LEGACY_AGENT_FORMAL_DEPRECATED`）。

## 参考资料

- `references/architecture-decision-record-v091.md`：本次架构恢复的决策与迁移状态。
- `references/construction-task-v1.md`：ConstructionTask 字段与语义。
- `references/SKILL-v090-legacy.md`：v0.9.0 完整历史说明（只读存档）。
- `references/upgrade-log.md`：版本变化与兼容性。
- `references/biological-parameters-sources.md`：默认参数与来源。
- `references/source-policy.md` 与 `references/privacy-and-consent.md`：来源与隐私政策。
