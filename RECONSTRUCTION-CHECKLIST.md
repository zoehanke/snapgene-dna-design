# SnapGene DNA Design 架构重构与推进清单 (RECONSTRUCTION-CHECKLIST)

> **核心定位**：给大模型装上好用的“手和脚”，破除过度工程化桎梏；通过“**Tier 1 原子工具 + Tier 2 标准实验 SOP 配方 + Tier 3 生物底线自检 + Tier 4 实验室经验库**”，既保证常规实验流程标准化严谨、不让 AI 突发奇想丢三落四，又赋予大模型处理复杂非标场景的极高自由度，最终精准操纵 SnapGene 权威交付。

---

## 架构核心层次设计 (The 3+1 Tier Architecture)

```
┌─────────────────────────────────────────────────────────────┐
│ Tier 3: 生物学客观底线自检清单 (Bio-Guardrail Checklist)     │
│ 无论 AI 怎么发挥，客观生物学死线绝不能破 (PAM未沉默/移码/发夹拦截) │
└──────────────────────────────┬──────────────────────────────┘
                               │ 校验
┌──────────────────────────────┴──────────────────────────────┐
│ Tier 2: 黄金实验 SOP 配方库 (Standard Laboratory Recipes)    │
│ 针对常规高频流程给出标准配方 (如标准 HDR 供体设计、Gibson 引物) │
│ • 常规任务：AI 优先走 SOP，步步遵循湿实验金标准，杜绝“脑洞”     │
│ • 复杂任务：AI 可以随时“跳出 SOP”，深入底层自由调度           │
└──────────────────────────────┬──────────────────────────────┘
                               │ 驱动
┌──────────────────────────────┴──────────────────────────────┐
│ Tier 1: 纯物理原子工具箱 (Atomic Hands & Feet)              │
│ 28 个无状态、无副作用的底层生物学计算与物理动作               │
└─────────────────────────────────────────────────────────────┘
```

---

## 阶段零：拆除老架构四大桎梏 (Dismantle Shackles) [已完成]
- [x] ~~**0.1 废黜 11 个单任务孤岛计划器** (`core/handlers/*.plan` & `core/runtime_plan.py`)：打破必须套进单一单步模板的死锁，引入通用的多步复合流水线 (`composite_pipeline`)，规划权彻底交还给大模型。~~
- [x] ~~**0.2 废弃关键词与正则暴力提取器** (`agent/nl_parser.py`)：彻底剥离假智能的子串猜测，将意图理解交付给大模型上下文。~~
- [x] ~~**0.3 解绑单任务硬编码路由器** (`core/registry.py`)：注册通用 `composite_pipeline`，打破 11 种任务类型的分类锁。~~
- [x] ~~**0.4 替换形式主义会话编排器** (`agent/orchestrator.py` 旧逻辑)：引入现代化极简 ReAct 工具闭环 (`agent/pipeline_agent.py`)，由大模型自主编排、原子工具执行、校验直至 SnapGene 权威交付。~~

---

## 阶段一：底层纯物理原子生物学工具箱 (Tier 1: Hands & Feet) [已完成]
> ~~包含 28 个无状态、无副作用的原子工具，31 个单元测试全绿 (0.083s)。~~

- [x] ~~**1.1 质粒与序列检视**：~~
  - [x] ~~`inspect_dna`: 拓扑、全长、GC%、Feature 坐标与 SnapGene 原生十六进制颜色。~~
  - [x] ~~`summarize_backbone`: 快速锁定复制子 (pUC/ColE1)、抗性标记 (AmpR/KanR) 与启动子。~~
  - [x] ~~`find_open_reading_frames`: 6 框扫描全长或局部的 ATG 起始 ORF 及终止密码子。~~
- [x] ~~**1.2 元件提取与标注**：~~
  - [x] ~~`get_feature`: 按名称/类型或别名检索，支持 `return_all=True` 返回全部同名元件。~~
  - [x] ~~`annotate_feature`: 向质粒追加标注，支持指定官方色值与正反向箭头。~~
- [x] ~~**1.3 拓扑安全切取与点突变**：~~
  - [x] ~~`extract_subsequence`: 跨原点回绕、反向互补与安全物理切片。~~
  - [x] ~~`mutate_sequence`: 精准单点/多点突变、插入与缺失。~~
  - [x] ~~`strip_terminal_codons`: 精准剥离起始 ATG 或末尾终止密码子 (TAA/TAG/TGA)。~~
- [x] ~~**1.4 酶切、末端化学与甲基化**：~~
  - [x] ~~`find_restriction_sites`: 扫描单切/双切点及 Dam/Dcm/EcoKI 甲基化重叠抑制预警。~~
  - [x] ~~`digest_sequence`: 模拟单酶物理切割，产出带左右 Overhang 与几何极性的片段集合。~~
  - [x] ~~`digest_type_iis`: 单片段 Type IIS 酶切，脱去识别位点，裸露核心与 4-bp 粘端。~~
  - [x] ~~`check_overhang_compatibility`: 核验任意两个末端的几何对称与序列反向互补。~~
  - [x] ~~`fill_or_chew_overhang`: 模拟 Klenow/T4 聚合酶 5' 补平或 3' 切平。~~
- [x] ~~**1.5 引物热力学与退火反应**：~~
  - [x] ~~`calc_primer_tm`: 最近邻热力学公式测算 Tm、GC%、3' 端 GC clamp。~~
  - [x] ~~`check_primer_dimers`: 物理扫描正反引物 3' 端二聚体互补与自互补发夹。~~
  - [x] ~~`design_overhang_primers`: 依据目标 Tm 截取结合核心并拼接 5' 悬垂。~~
  - [x] ~~`anneal_oligos`: 模拟双单链寡核苷酸水浴退火为双链，计算左右外露粘端。~~
  - [x] ~~`simulate_pcr`: 模拟 PCR 扩增带尾巴双链产物。~~
- [x] ~~**1.6 读码框与密码子**：~~
  - [x] ~~`translate_dna` / `check_reading_frame`: 6 框翻译、移码核验、终止密码子扫描。~~
  - [x] ~~`get_codon_synonyms`: 查寻同义密码子，供大模型自主挑选最佳同义密码子。~~
  - [x] ~~`silent_mutation_remove_site`: 破坏内部位点且保持翻译一致。~~
- [x] ~~**1.7 组装装配与特征迁移**：~~
  - [x] ~~`simulate_overlap_assembly`: Gibson / In-Fusion 同源重叠臂拼接。~~
  - [x] ~~`simulate_golden_gate`: Type IIS 一锅法多片段有序组装。~~
  - [x] ~~`simulate_digest_ligation`: 双酶切定向 T4 连接。~~
  - [x] ~~`migrate_features_after_assembly`: 组装后特征坐标绝对物理位移重映射。~~
- [x] ~~**1.8 基因编辑基础原子**：~~
  - [x] ~~`design_crispr_grna`: 扫描 spacer、PAM、切割点、GC%、Poly-T。~~
  - [x] ~~`prepare_grna_oligos`: 生成 U6 表达引物对（含起始 G 与 BbsI/BsmBI 悬垂）。~~
  - [x] ~~`extract_homology_arms`: 围绕切点物理截取左右同源臂。~~
- [x] ~~**1.9 标准元件与 SnapGene 交付**：~~
  - [x] ~~`get_standard_element`: 调取 6xHis/FLAG/HA/Linker/TEV 等标准元件碱基。~~
  - [x] ~~`export_snapgene`: 写入二进制 `.dna` 与官方配色 `.gb`。~~
  - [x] ~~`open_in_snapgene`: 调起桌面 `SnapGene.exe` 查看质粒图谱。~~

---

## 阶段二：黄金实验 SOP 配方库 (Tier 2: Standard Recipes) [已完成]
> ~~**目标**：为常规高频流程提供开箱即用的标准实验 SOP 配方。常规任务走 SOP 规避 AI“突发奇想/丢三落四”，复杂任务可下潜到 Tier 1 灵活拆解。每条配方均在代码与输出中带有严格的权威文献来源与经典手册出处。~~

- [x] ~~**2.1 CRISPR HDR 供体标准配方 (`recipe_crispr_hdr_donor`)**:~~
  - ~~封装规范：标准同源臂长度（ssODN 40~60 bp，质粒 500~800 bp）；自动寻找切点残留 PAM 并调用 `get_codon_synonyms` 施加高频同义突变阻断二次切割；支持非编码区/Seed区突变降级策略；明确标注 Ran et al. 2013 Nature Protocols 与 Paquet et al. 2016 Nature 来源。~~
- [x] ~~**2.2 Gibson / In-Fusion 组装引物与片段标准配方 (`recipe_gibson_assembly`)**:~~
  - ~~封装规范：标准 20~25 bp 重叠臂挂载；结合核心 Tm 稳定在 60±2°C；正反引物 $\Delta Tm \le 2^\circ\text{C}$；自动跑引物二聚体初筛；短片段 (<200 bp) 防 T5 嚼毁预警；明确标注 Gibson et al. 2009 Nature Methods 与 NEB #E2621 来源。~~
- [x] ~~**2.3 Type IIS Golden Gate 多片段一锅法标准配方 (`recipe_golden_gate`)**:~~
  - ~~封装规范：BsaI/BsmBI 4-bp 正交粘端自动校验；无缝环状组装产物验证与识别位点清除核验；明确标注 Engler et al. 2008 PLoS ONE 与 Potapov et al. 2018 ACS Synth Biol 来源。~~
- [x] ~~**2.4 传统双酶切定向克隆标准配方 (`recipe_restriction_cloning`)**:~~
  - ~~封装规范：载体双切、插入片段双切、粘端配对、去磷酸化提醒与方向性连接；严格挂载 NEB 5' 保护碱基与 DpnI 质粒模板消除提醒；明确标注 Sambrook 《分子克隆实验指南》第 4 版与 NEB 技术手册来源。~~
- [x] ~~**2.5 定点突变与密码子工程标准配方 (`recipe_site_directed_mutagenesis`)**:~~
  - ~~封装规范：突变位点居中、两侧 10~15 bp 野生型对称臂；QuikChange 专用 $Tm \ge 78^\circ\text{C}$ 公式核验；3' GC clamp 校验；强制 DpnI 消化甲基化母本质粒提醒；明确标注 Zheng et al. 2004 Nucleic Acids Res 与 Sambrook 4th ed 来源。~~
- [x] ~~**2.6 表达标签与融合蛋白工程标准配方 (`recipe_protein_tagging`)**:~~
  - ~~封装规范：C 端融合强制剥离原 CDS 终止密码子；柔性/刚性 Linker 核酸长度严格整除 3；真核 Kozak 共有序列 (`GCCACC`) 前置；特异性内切蛋白酶位点 (TEV/3C) 嵌入；全长在读码框无内部早熟终止；明确标注 Terpe 2003 与 Kozak 1986 来源。~~
- [x] ~~**2.7 分子质检与测序引物布局标准配方 (`recipe_cloning_verification`)**:~~
  - ~~封装规范：菌落 PCR 引物必须“一端在骨架、一端在插入片段”（跨接缝，产物 300~800 bp，杜绝假阳性）；Sanger 测序引物强制锚定在接缝上游 50~100 bp（彻底避开前 30~50 bp 荧光盲区）；诊断性限制酶切双带分子量相对差 $\ge 15\%$ 预判；明确标注 Sambrook 4th ed 与 Sanger 1977 来源。~~
- [x] ~~**2.8 权威来源文档与检索接口**:~~
  - ~~创建 `references/authoritative_sop_sources.md`，提供统一的文献、经典手册与规则映射；暴露 `get_recipe_sources` 与 `GET_RECIPE_DEFINITIONS` 接口。~~

---

## 阶段三：生物学客观底线自检清单 (Tier 3: Guardrails) [已完成]
> ~~**目标**：无论 AI 走 SOP 还是自主编排，客观生物学死线绝对不能破。只报客观事实，绝不搞主观死锁。~~

- [x] ~~**3.1 核心客观底线扫描 (`quick_biological_sanity_check`) 扩展**:~~
  - [x] ~~`BIO-01`: 读码框核验（CDS 是否 3 的倍数、内部提前终止密码子扫描）。~~
  - [x] ~~`BIO-02`: 终止密码子完整性（C 端标签融合是否剥离前置 Stop，最终是否以 Stop 结尾）。~~
  - [x] ~~`BIO-03`: 内部酶切位点冲突排查。~~
  - [x] ~~`BIO-04`: 特征方向与链极性（Promoter/CDS 方向是否一致）。~~
  - [x] ~~`BIO-05`: **CRISPR 供体防二次切割自检**（扫描供体模板中是否存在未破坏的完整 PAM/Seed，阻断体内再切割）。~~
  - [x] ~~`BIO-06`: **RNA Pol III (U6) 转录终止自检**（扫描 sgRNA 是否存在连续 $\ge 4$ 个 T）。~~
  - [x] ~~`BIO-07`: **PCR 引物 3' 端严重二聚体自检**（扫描正反引物 3' 端连续互补 $\ge 4$ bp 风险）。~~

---

## 阶段四：实验室经验规则库轻量调用 (Tier 4: Experience) [待办]
- [ ] **4.1 激活 1,721 行现有经验库** (`rules/preloaded_experience_rules.json`)。
- [ ] **4.2 编写轻量经验检索提取器** (`core/tools/experience_helper.py`):
  - 提供 `query_lab_experience(topic)` 接口供 Agent 按需调取引物设计、同源臂长、感受态细胞、菌落 PCR 等湿实验经验。

---

## 阶段五：去过度工程化的 Skill 说明书重写 (SKILL.md) [已完成]
- [x] ~~**5.1 重写 `SKILL.md`**:~~
  - ~~删去陈旧的死锁计划器文档，全面阐明 3+1 分层架构（Tier 1 原子工具、Tier 2 标准 7 大 SOP 配方、Tier 3 生物自检清单），指导大模型何时调用 SOP、何时使用底层原子工具。~~

---

## 阶段六：真实科研复合案例端到端实操验证 (E2E Benchmark) [待办]
- [ ] **6.1 复合案例 A (Gibson)**：载体双酶切 + PCR 引入 C 端 6xHis 标签与同源臂 + Gibson 组装 + 特征迁移。
- [ ] **6.2 复合案例 B (CRISPR HDR)**：基因组靶点扫描 + sgRNA 退火引物 + HDR 供体设计 (含 PAM 同义沉默)。
- [ ] **6.3 桌面真机验收**：导出原生 `.dna` 并在 Windows 桌面调起 `SnapGene.exe` 验收质粒图谱。
