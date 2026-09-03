# SnapGene DNA Design 架构重构与推进清单 (RECONSTRUCTION-CHECKLIST)

> **核心定位**：给大模型装上好用的“手和脚”，彻底破除过度工程化与代码膨胀；通过“原子工具 + 基础自检清单 + 实验室经验库”辅助大模型，最终精准操纵 SnapGene。

---

## 阶段零：拆除老架构四大桎梏 (Dismantle Shackles)
- [x] **0.1 废黜 11 个单任务孤岛计划器** (`core/handlers/*.plan` & `core/runtime_plan.py`)：打破必须套进单一单步模板的死锁，引入通用的多步复合流水线 (`composite_pipeline`)，规划权彻底交还给大模型。
- [x] **0.2 废弃关键词与正则暴力提取器** (`agent/nl_parser.py`)：彻底剥离假智能的子串猜测，将意图理解与规划提示词 (`build_agent_planning_prompt`) 交付给大模型。
- [x] **0.3 解绑单任务硬编码路由器** (`core/registry.py`)：`core/registry.py` 注册通用的 `composite_pipeline` 处理器，打破 11 种任务类型的狭隘分类限制。
- [x] **0.4 替换形式主义会话编排器** (`agent/orchestrator.py` 旧逻辑)：引入现代化极简 ReAct 工具闭环 (`agent/pipeline_agent.py`)，由大模型自主编排、原子工具执行、三层验证直至 SnapGene 权威交付。

---

## 阶段一：底层原子生物学工具箱 (Hands & Feet)
- [x] **1.1 质粒检视** (`inspect_dna`): 解析全长、拓扑、GC%、Feature 坐标与方向。
  - [x] *已完善*：提取 SnapGene 原生 Feature 颜色 (Color hex) 与展示样式；新增 `summarize_backbone` 提取复制子、启动子与抗性标签。
- [x] **1.2 元件提取与标注** (`get_feature` / `annotate_feature`): 按名称或类型查元件。
  - [x] *已完善*：支持单质粒多同名元件全量返回 (`return_all=True`) 与别名模糊匹配（如 amp/bla、kan/neo、ori）；支持赋色与箭头。
- [x] **1.3 限制性内切酶分析** (`find_restriction_sites`): 常见酶、Type IIS 酶单切/双切/悬垂判定。
  - [x] *已完善*：增加大肠杆菌 Dam/Dcm/EcoKI 甲基化重叠抑制预警；新增 `check_overhang_compatibility` 校验末端几何与序列互补。
- [x] **1.4 拓扑安全切取与点突变** (`extract_subsequence` / `mutate_sequence`): 跨原点回绕、反向互补与序列突变。
- [x] **1.5 同义突变内部酶切位点沉默** (`silent_mutation_remove_site`): 破坏 CDS 内部酶切位点且 100% 保持氨基酸不变。
- [x] **1.6 引物设计与 PCR 模拟** (`simulate_pcr`): 支持带 5' 接头/同源臂/标签的引物扩增模拟。
  - [x] *已完善*：增加引物退火温度与 3' GC clamp 测算 (`calc_primer_tm`)；新增区间带悬垂引物自动设计 (`design_overhang_primers`) 并核验 $\Delta Tm$。
- [x] **1.7 读码框蛋白与标签融合** (`fuse_in_frame`): 自动剥离前置 Stop，严格核验 Linker 整除 3。
  - [x] *已完善*：新增标准生物元件库 (`get_standard_element`)，一键提供 6xHis/FLAG/HA/Myc/Strep、(G4S)n/EAAAK、TEV/PreScission 等核苷酸序列与官方配色。
- [x] **1.8 组装模拟与特征迁移** (`simulate_overlap_assembly` / `simulate_digest_ligation`): Gibson 与酶切连接拼接。
  - [x] *已完善*：新增组装产物特征全自动坐标迁移 (`migrate_features_after_assembly`)；新增 Type IIS Golden Gate 一锅法多片段组装模拟器 (`simulate_golden_gate`)。
- [x] **1.9 翻译与读码框核验** (`check_reading_frame` / `translate_dna`): 6 框翻译、移码与提前终止检测。
- [x] **1.10 SnapGene 原生交互** (`export_snapgene` / `open_in_snapgene`): 导出原生 `.dna` / `.gb`，直接调起桌面 `SnapGene.exe`。
  - [x] *已完善*：按元件类型自动赋予 SnapGene 官方推荐颜色（CDS: #ff8080, promoter: #80ff80, etc.）。

---

## 阶段二：基础生物规则自检与元件库 (Guardrails)
- [x] **2.1 基础五大普适自检要点 (BIO-01 ~ BIO-05)**: 读码框/提前终止、终止密码子策略、内部酶切位点冲突、正负链方向、调控盒闭环。
- [x] **2.2 客观物理诊断器** (`quick_biological_sanity_check`): 只报客观物理数据，不搞主观死锁。
- [ ] **2.3 常用标准生物元件轻量词典** (`core/guardrails/bio_constants.py`): 内置常见 Tags (6xHis, FLAG, HA, Myc)、Linkers ((G4S)n, (EAAAK)n)、TEV 切点与 Kozak/SD 序列。

---

## 阶段三：实验室经验规则库轻量调用 (Experience Integration)
- [ ] **3.1 激活 1,721 行现有经验库** (`rules/preloaded_experience_rules.json`)。
- [ ] **3.2 编写轻量经验检索提取器** (`core/tools/experience_helper.py`): 提供 `query_lab_experience(topic)` 供 Agent 按需检索引物确认、同源臂长、菌落 PCR 等科研经验。

---

## 阶段四：全新 Agent 交互入口重构 (ReAct Tool-Use Engine)
- [ ] **4.1 构建极简 Agent Tool-Calling 执行闭环**:
  `用户需求 -> 调工具看质粒 -> 查经验库规划 -> 调工具切拼 -> 自检清单核对纠偏 -> 导出并在桌面 SnapGene 打开`。

---

## 阶段五：去过度工程化的 Skill 说明书重写 (SKILL.md)
- [ ] **5.1 重构 `SKILL.md`**: 删去官僚门禁陈述，还原为一份现代 Agent 的“分子生物学手脚与工具箱使用手册”。

---

## 阶段六：真实科研复合案例端到端实操验证 (E2E Benchmark)
- [ ] **6.1 复合案例 A**：载体双酶切 + PCR 引入 C 端 6xHis 标签与同源臂 + Gibson 组装。
- [ ] **6.2 复合案例 B**：目的基因内部酶切位点同义突变沉默 + 启动子替换。
- [ ] **6.3 桌面真机验收**：导出文件并在 Windows 桌面调起 `SnapGene.exe` 验收质粒图谱。
