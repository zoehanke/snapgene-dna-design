> 历史资料，保留当时描述。当前规则见项目spec和开发计划。

## v0.9.1-dev1 — 架构恢复开发版（2026-08-28）

- ConstructionTask v1 + 统一 runtime（validate_construction_task / plan / execute / validate / finalize）。
- 11 个 task kind 全部迁移到专用 planner；TASK_KIND_NOT_IMPLEMENTED 移除。
- 三层验证 goal-valid 从 false 开始；唯一 authoritative 闸门重算哈希并重读文件，篡改关闭失败。
- 旧 formal 入口弃用（LEGACY_AGENT_FORMAL_DEPRECATED）；export_delivery_bundle 降级 preview。
- restriction_ligation / crispr_editing 为 experimental，产物仅 experimental-preview。
- 新增 run_construction_task.py / generate_construction_report.py；.dna 输入直接可读。

# v0.9.0 — 正式技术发布（2026-08-26）

- RC1 冻结验收通过后解压重建 v0.9.0 工作副本；VERSION=0.9.0。
- 全部技术门禁（源码/真实后端/coverage/mutation/property/场景/SnapGene官方/固定任务/最终ZIP）在 v0.9.0 工作副本复跑。
- 发布判定：TECHNICALLY_READY_PENDING_HUMAN_BIOLOGICAL_ACCEPTANCE。

## v0.9.0-rc1 — 个人经验规则闭环（2026-08-23，dev 预览）

- 2026-08-26 将人工审核表合入预存库：保留原有 E-01/E-02，并加入
  C-01～C-31，去重后共 33 条。扩展受控条件字段和触发阶段；规则来源元数据
  明确区分“真人审核通过”与“独立来源核验”。
- 预存迁移从“一次初始化后永不检查”改为按 ID 增量引入：已有用户库可获得
  新预存规则，同时不会恢复用户已删除或修改过的旧预存规则。
- 自然语言经验只生成候选；明确确认后才持久化。
- `user_rules/rules.json` 保存最新确认版本，`pending.json` 保存候选状态，
  `history/` 追加新增、修改、停用、删除、恢复和回滚事件。
- 两条初始经验改称“预存规则”，首次初始化后进入普通规则库；用户可修改、
  停用或逻辑删除，删除后不会因再次启动而自动恢复。
- 用结构化 `when` 条件和有限操作符替换 Python `check`/`eval`。
- 支持当前项目和全局范围；本次规则留在 DesignSpec，不引入 lab/user 身份系统。
- 新增固定规则清单和 Markdown 快照导出。
- 验证引物设计前必须获得用户明确请求；菌落/煮菌 PCR 默认对 >1000 bp
  产物给出带实际长度的警告与确认请求。

## v0.9.0-dev — 数值交叉验证与发布打磨（2026-08-18，dev 预览）

- 新增 `validation_crosscheck.py`：Tm/酶切位点/overlap 平行验证。
- 新增真实科研场景端到端回归（Gibson/Gateway/Golden Gate/高GC PCR）。
- 新增破坏性输入测试与 README。
- 所有规则阈值继续以 `rules/feasibility_rules.json` 为唯一经验值来源。

## v0.9.0-dev — 多源组装规划与实验可行性（2026-08-17，dev 预览）

- 新增 M1 `planning/` + `plan_assembly.py`：多质粒片段分配、自动方法决策、
  overlap 算法选择、Golden Gate 内部位点检查、引物清单与构建手册。
- 新增 M2 `rules/` 可行性规则库（带文献/官方来源）与 `user_rules/` 扩展入口。
- 新增 M3 `primer_design_engine.py`：真实 primer3_core 优先，启发式回退
  明确标注；尾巴附加与 Tm/GC/二级结构校验。
- 新增 M4 `pcr_strategy.py`、M5 `parts/` 元件库、M6 `online_sources.py`。
- dev3 残余修复：D3-P1-01 坐标边界、D3-P1-02 非 ASCII 路径、D3-P2-01~10。

## v0.8.0-dev3 — 坐标修复 + 真实后端（2026-08-17）

- **P0 坐标修复**：负链候选坐标映射回输入参考轴（0-based 半开）；
  线性拓扑下 PAM 越界直接跳过；环状跨原点用显式 segments 表达。
- **Cas-OFFinder 真实契约**：输入文件 + 设备 + 输出文件三参数调用，
  同时解析 v2.4（6/7 列）与 v3.0（9 列，含 bulge）输出。
- **真实 on-target 模型**：SpCas9 接入 Azimuth V3（Doench-2016）；
  AsCas12a 接入 DeepCpf1 34bp 上下文模型（Bioconductor CRISPRseek
  权重，与官方 R 参考输出一致）。
- **全基因组脱靶与注释链路**：`generate_crispr_design_report.py`
  支持 `--reference-fasta/--annotation/--cas-offinder`，真实运行
  Cas-OFFinder 并做区间重叠注释。
- **门禁修复**：consent 绑定式一次性 receipt、provenance 条件必填、
  协议推荐按 profile 特征匹配、统一报告结构化失败、CLI 直出 v0.8
  schema、GenBank+FASTA+.dna 三格式输出。

## v0.8.0-dev2 — 开发预览

- 新增 v0.8 JSON Schema：provenance / guide-design / offtarget / reaction-profile / protocol-recommendation / crispr-design-report，含正例和反例测试。
- `cas_offinder_adapter.py` 增加真实输出解析（1-based inclusive → 0-based half-open）、参考基因组 SHA/统计绑定。
- 新增 `annotate_offtargets.py`：脱靶与 GenBank feature 交集注释。
- 新增 `guide_scoring.py`：模型适用性门禁；AsCas12a 不使用 Cas9 模型，LbCas12a 返回 `no-reviewed-model-selected-for-lbcas12a`。
- 新增 `protocol_evidence.py` 与 NEB Q5 / NEBuilder 官方协议证据文件。
- 新增 `generate_crispr_design_report.py`：统一 JSON/Markdown 报告。
- 工作目录测试：215 tests OK。
- **未完成**：Cas-OFFinder 本机未安装，真实后端运行未完成；CRISPOR/DeepCpf1 真实执行未完成；全基因组脱靶主流程仍为 unavailable。

## v0.8.0-dev1 — CRISPR 候选、provenance、后端适配器骨架（开发预览）

- 状态：**dev，不是 RC，不是正式版**
- 新增 `references/nuclease-registry.json`：SpCas9 / AsCas12a / LbCas12a 唯一 PAM/模型注册入口
- 新增 `scripts/design_guides.py`：注册表驱动 PAM 扫描，支持正负链、环状跨原点、模糊碱基警告
- 新增 `scripts/provenance.py`：统一来源对象、来源校验、外部程序探测
- 新增 `scripts/cas_offinder_adapter.py`：仅探测/运行本地 Cas-OFFinder，缺失时 unavailable
- 新增 `scripts/crispor_adapter.py`：仅本地检测 + 许可提示 + 在线上传同意请求，不打包 CRISPOR
- 新增 `scripts/sequence_upload_consent.py`：逐次上传同意状态机，默认拒绝
- 新增 `scripts/characterize_reaction.py`：客观 PCR 反应特征 profile，不推荐试剂
- 新增 `scripts/recommend_protocol.py`：无权威来源时 unavailable，不编造条件
- 新增 `references/privacy-and-consent.md`、`source-policy.md`、`crispr-model-applicability.md`、`protocol-recommendation.md`
- 新增 `tests/test_v08_guides.py`：14 项注册表/扫描/provenance/consent/profile/protocol 测试
- 未实现：CRISPOR 真实执行、Cas-OFFinder 输出解析、on-target 模型评分、脱靶后处理、全基因组索引管理

# SnapGene DNA Design 升级日志

本文件记录影响 Skill 使用方式、输出契约和生物学语义的版本变化。当前版本为 **v0.9.0**（技术门禁通过，等待真人独立生物学验收）。

### v0.9.0-rc1 安全热修（2026-08-24）

- 经验规则验证改为递归拒绝 `check`/`eval` 等可执行字段；Schema 使用 `urn:`
  标识并收紧未知条件键，当前规则、预存规则和待确认候选统一校验。
- `block` 规则成为不可绕过的硬阻断；`--acknowledge-experience-warning` 只能
  确认 warn/ask，不得写出被 block 拦截的 PCR 产物。
- 新增 3 项针对性回归测试（专项 17/17 通过），同步开发者提示、README、
  开发手册和复审指南的版本与发布语义。

## v0.7.0-dev2 — 真实 Primer3 设计后端（2026-08-17）

### 修正上一版的关键误区

- v0.7.0-dev 只用 primer3-py 计算 Tm/结构，候选仍由自写的 18–30 bp 枚举器选择；因此不应称为“Primer3 设计”。dev2 新增 `primer3_core_backend.py`，用官方 Boulder-IO 调用 `primer3_core` 的真正 primer-picking pipeline。
- 旧 `ThermoEngine` 在探针成功后仍会在主进程再次导入原生扩展，存在二次崩溃窗口；dev2 的生产路径不再导入 primer3-py，所有真实引擎调用均隔离在子进程。
- 单个 Primer3 计算异常后静默降级、但顶层仍可能写 `available`；dev2 用 `design_engine.verification` 记录整次设计实际来源，并提供 `--require-primer3` 失败关闭。
- Primer3 的 `_TH` 输出是结构熔解温度而不是 dG。dev2 按 `HAIRPIN_TH` / `SELF_ANY_TH` / `COMPL_ANY_TH` 原名和单位语义报告，不再套用自定义 dG 阈值。

### 新增

- `--engine auto|primer3-core|heuristic`、`--primer3-core`、`--require-primer3`、`--primer3-timeout`。
- 自动发现顺序：显式路径 → `PRIMER3_CORE` → PATH → 已安装 primer3-py wheel 内的 `primer3_core` 文件；发现过程不 import primer3-py。
- `validate_primer3_integration.py` 与 `test_primer3_core_backend.py`：真实 Primer3 2.6.1 普通 PCR、Gibson overhang、CLI 失败关闭三条路径。真实集成测试允许开发机缺引擎时显式 skip，但发布门禁脚本缺引擎直接失败。
- `quality.source: legacy-heuristic`：保留 v0.6 兼容字段，但明确它不是 Primer3 指标。

### 本机真实证据

- primer3-py 2.3.0 的 CPython 3.14 Windows wheel 可正常加载，内含 `primer3_core.exe` 2.6.1；此前“本机所有解释器均崩溃”的结论只覆盖 3.10–3.12，现已纠正。
- 真实门禁：普通 exact-boundary PCR 返回 5 pair；Gibson 返回 1 pair，binding product 300 bp、含两端 8 bp overhang 的 Primer3 product 316 bp；指标来源为 `primer3-core`。
- Primer3/primer3-py 为 GPL-2.0-or-later 外部运行时，不打入本项目 MIT ZIP。

## v0.7.0-dev — Primer3 第一阶段集成（2026-08-17）

### 新增

- `primer3_probe.py`：可选依赖 primer3-py 的**子进程探针**（status: `available` / `not-installed` / `import-crash` / `probe-error`）。原因：primer3-py 原生扩展在本机所有版本/解释器上 import 即 access violation（见 `reports/primer3-environment.md`），子进程探针防止崩溃拖垮工具进程。
- `design_primers.py` 重构：
  - 默认输出前 `--top-n`（默认 5）组候选 pair；每个候选报告 `binding`、`tail`（5' 尾/overlap）、`sequence`（完整引物）、`tm`/`gc`（binding 区退火参数）、`hairpin`、`self_dimer`、`heterodimer`、`end_stability_3p`、`product_size`、`penalties`、`recommended`。
  - 输出契约新增顶层 `primer3_status` / `primer3_detail` / `primer3_note`；unavailable 时显式警告"未进行 Primer3 热力学验证"，结构分数带 `source: heuristic`。
  - Primer3 available 时 Tm 用 `calc_tm`，结构用 `calc_hairpin`/`calc_homodimer`/`calc_heterodimer`/`calc_end_stability`（对完整引物）；unavailable 时用 primer_qc 启发式 + Biopython MeltingTemp。
  - Gibson 模式：binding 区用于 PCR 退火参数，完整引物（tail+binding）用于结构检查；`overlap`/`overlap_tail`/`overlap_length` 兼容字段保留。
  - 候选不足（< `--top-n`）→ warning；零候选 → 结构化失败 `NO_PRIMER_CANDIDATES`。
- `requirements-optional.txt`：可选依赖清单（primer3-py）。
- `tests/test_v07_primer3.py`：21 个新测试（缺依赖 / import-crash / available 注入假 primer3 / 候选不足 / 零候选 / Tm 不匹配 / hairpin / self-dimer / cross-dimer / Gibson 尾巴分离 / 失败报警 / 推荐等级）。
- `reports/primer3-environment.md`：本机 primer3-py 崩溃诊断证据。

### 兼容性

- v0.6.0-rc2 全部测试继续通过（基线 156 + 新增 21 = 177 tests OK）。
- `design_primers.py` 旧字段（`forward`/`reverse` 最佳候选、`quality`、`product_size`、`bind_start`/`bind_end`、`overlap`/`overlap_tail`）全部保留；`best_primer()` 兼容函数保留（`design_gene_replacement.py` 依赖）。
- JSON 契约仍为 `schema_version: "0.5.0"`。

### 已知限制

- 本机 primer3-py 无法加载（import-crash），Primer3 热力学路径仅以注入假模块的单测覆盖，**必须**在 primer3-py 可正常加载的机器上复验后才可声称"已用 Primer3 验证"。
- 启发式路径的 Tm 为 Biopython MeltingTemp（盐校正近似），不等同 Primer3。

## v0.6.0-rc2 — SnapGene 安全交付策略（2026-08-16）

### 新增

- `snapgene_compatibility.py`：在导出前按 `snapgene-gb` / `dna` 分别报告 core 与 strict 风险，覆盖 `order`、复合 location、Unicode feature 名称、`db_xref`、多值 note、synonym 与 translation 规范化。
- `export_delivery_bundle.py`：生成权威 GenBank、兼容性报告、SHA-256 `DELIVERY-MANIFEST.json`；原生 `.dna` 仅在 core-safe 时默认生成，风险导出必须显式 `--allow-core-risk`。
- `generate_design_report.py --compatibility-json`：将格式风险与人工复核要求并入统一 HTML/JSON 报告。

### 修复与门禁

- `validate_roundtrip.py` 的 feature core 签名新增 location operator，`join` 与 `order` 不再被误判为相等。
- 官方 SnapGene rc2 复跑确认：`rich_order` 在 `snapgene-gb` 与原生 `.dna` 两条路径均丢失 operator；旧报告中的 `.dna core 通过` 是旧比较口径造成的假阳性，现已纠正。
- `validate_rich_fixtures.py` 改为“内部 strict + 已声明官方差异”门禁：已知第三方差异可以被接受并明确标注，任何预检未分类的新核心损失仍阻断发布。
- `build_release.py` 默认从 `VERSION` 读取版本，并拒绝 `--version` 与文件不一致，避免打出错号包。
- `coverage_gate.py` 为 Windows 子进程固定 UTF-8；`property_tests.py --help` 转义 argparse 的 `%`，修复 Python 3.14 下门禁子步骤退出的问题。
- 覆盖率子进程收集不再依赖开发机预装的 `coverage.pth`；门禁在临时目录生成 `sitecustomize.py` 并显式调用 `coverage.process_startup()`，保证 CLI `main()` 覆盖可复现。
- 新增 12 项兼容性与交付包回归测试。

### 行为变化

- 原生 `.dna` 不再被当作默认权威交付格式；含复合 location、Unicode feature 名称或 `order` 时默认省略。
- `--allow-core-risk` 只表示用户已经审阅风险；manifest 会永久记录该选择，不代表风险消失。
- 版本仍保持 RC：本版要先用官方 SnapGene 复跑新门禁，确认已声明差异与实测一致，再决定正式发布。

### rc2 实测结果

- 源码/academic-full：156 tests OK；redistributable 解压：128 tests OK、1 个 academic-only fixture 显式 skip。
- smoke：core 95/95、academic 125/125。
- 覆盖率：12 个核心模块行 95.67–100%、分支 91.67–100%；两个新增安全模块均为 100% / 100%。
- mutation：12/12 killed；全规模 property 全部通过。
- 官方 SnapGene：8 fixture × 2 格式的 declared-compatibility gate PASS；`order` 在两条路径均被诚实标为 core 风险。
- 两个 RELEASE-MANIFEST 验证通过；redistributable 受限内容哈希 0，academic-full 预期 10/10。

## v0.6.0-rc1 — 发布门禁达标 + v0.6 功能线（2026-08-16）

### 发布门禁（v0.5 遗留项，本轮全部建立并达标）

- **coverage 门禁**：新增 `scripts/coverage_gate.py`，以 coverage.py 并行工作流（`coverage run` × unittest/smoke/property-quick/rich + `combine` + `json`）统计核心模块（sg_common / assembly_model / construct_model / simulate_cloning / simulate_advanced / golden_gate / write_dna / validate_roundtrip / validate_construct / edit_plasmid）。实测行覆盖 95.6%–100%、分支 89.3%–100%，门禁 ≥90%/≥85% 全过。
- **mutation tests**：新增 `scripts/mutation_tests.py`，对 12 个指定 mutation（零贡献检查、overlap 检查、闭环裁剪、黏性末端、CompoundLocation 排序、extract 一致性、origins 不变量、Golden Gate 识别位点/overhang、Gateway att 唯一性、失败 envelope、insert 边界）逐一代入临时源码副本并验证行为被测试捕获。**kill rate 12/12 = 100%**（门禁 ≥90%）。
- **property tests 全规模**：新增 `scripts/property_tests.py`，固定 seed（`--seed`，方法级确定性 seed 避免 `hash()` 随机化）：Gibson / In-Fusion / Golden Gate / digest-ligate 各 1,000 成功 + 300 失败，Gateway / TA 各 500 + 200，全部通过；失败用例按结构化错误码断言。
- **rich-feature strict 往返**：新增合成 `fixtures/rich/`（`scripts/build_rich_fixtures.py` 生成）——正/反链 CDS（translation/codon_start/transl_table）、CompoundLocation join/order、跨原点 CDS、Unicode qualifier、多值 qualifier、kitchen-sink 环状质粒；`scripts/validate_rich_fixtures.py` 对 `snapgene-gb --strict` 全部 core+strict 通过；原生 `.dna` core 通过（qualifier 差异按既有策略报告）。官方 SnapGene `--require-snapgene` 核验在无 SnapGene 的机器上记为 pending。
- **Python 版本矩阵**：本机验证 Python 3.10 / 3.11 / 3.12（3.11 为本次新装）——`unittest discover` 115 tests 全部 OK，`smoke_core.py` 95/95 通过。

### v0.6 功能

- **`design_gene_replacement.py`**：基因替换设计。`--target-gene`（按 label/gene 定位，支持复合 feature 的 min..max span）或 `--target-region`；提取 `--flank-len` 上下游同源臂；构建 cassette（上游臂 + 替换 CDS + 下游臂）；设计 Gibson 引物——正引物 = 上游臂尾 + 替换 CDS 5' binding，反引物 = rc(下游臂)尾 + 替换 CDS 3' binding（Tm 平衡）；QC：起始 ATG / 终止密码子 / 读框 / GC，风险逐条列出；输出替换产物 GenBank + design JSON。
- **`design_primers.py --gibson`**：真正 Gibson 引物设计，结果将 `overlap`（5' 尾）与 `binding`（3' 结合区）分离报告；`--fwd-overlap` 为正向引物 5' 尾（匹配上游片段末端），`--rev-overlap` 为下游同源序列、反引物携带其反向互补；QC 仅针对 binding 区。
- **`generate_design_report.py`**：统一 design-report。汇总 `--design-json` / `--assembly-json` / `--product` 产物，输出独立 HTML（内联 CSS，含 overview / primers / assemblies / products / QC / risks / notes 章节）与机器可读 report JSON（`schema_version: 0.5.0` envelope）。
- 测试：`tests/test_gate_targets.py`、`tests/test_coverage_gap.py`、`tests/test_rich_fixtures.py`；套件 115 tests（redistributable 无 fixtures 时相关用例 skip）。

### 兼容性

- JSON 契约仍为 `schema_version: "0.5.0"`；包版本号升为 `0.6.0-rc1`（v0.6 功能线进入 RC）。
- `design_primers.py` 成功输出新增 `method`（`gibson`/`pcr`）与 `binding`/`overlap` 字段；旧 `primer_only` 字段更名为 `binding`（QC 语义不变）。
- 新增 `scripts/run_test_suite.py`（coverage 门禁用，`coverage run -m unittest` 在 zip 解释器下不可用）。
- `fixtures/rich/*.gb` 为合成数据，两个发行包均包含。

### 官方 SnapGene 核验（本机 D:\SnapGene\SnapGene.exe，2026-08-16 补充）

- `scripts/validate_rich_fixtures.py --snapgene-exe` 已在本机执行（16 次官方转换），`rich strict round trip gate: FAIL`（strict 口径），结果如实记录于 `reports/rich/rich-roundtrip.json`。
- **snapgene-gb（优先交付格式）**：5/8 fixture 官方往返 lossless（`rich_rev_cds`、`rich_join`、`rich_cross_origin`、`rich_unicode`、`rich_kitchen_sink`）；`rich_fwd_cds` / `rich_multivalue` core 通过、strict 因 SnapGene 固有规范化失败（`db_xref` 前缀剥除、多值 `note` 截断、`synonym` 丢失，safe 级）；**`rich_order` core 失败——SnapGene 不保留 `order` 复合位置语义**。
- **原生 .dna**：6/8 core 通过；**`rich_join`（复合 join 位置）与 `rich_unicode`（Unicode feature 名称，官方导出为乱码 `»ùÒò_alpha`）core 失败**——含复合 join 或非 ASCII 名称的质粒不得用 .dna 交付。
- 修复：`rich_rev_cds` / `rich_kitchen_sink` 的 `translation` qualifier 原为手写错误值（与序列不符），`rich_cross_origin` 缺 `transl_table`——已改为按序列动态计算并补齐，修复后三者官方 strict 通过。
- 结论：strict 门禁未全过为 **SnapGene 第三方规范化/格式行为**（非本工具 bug），正式版审查需按此口径复核。

### 仍未完成（因此保持 RC）

- 官方 SnapGene 机器上的 `--require-snapgene` rich-feature 往返核验（本机无 SnapGene）。
- 正式版发布决策（门禁证据已齐，尚需官方核验 + 最终评审）。

## v0.5.0-rc2 — 发布工程与内容哈希许可证检查（2026-08-15）

### 已完成

- **smoke 拆分**：`smoke_core.py` 仅使用合成序列/features；`smoke_academic.py` 才使用真实 SnapGene fixtures。redistributable 包只运行 `smoke_core.py`。
- **许可证检查器改为内容哈希**：`check_redistributable.py` 对 ZIP/目录中每个普通文件计算 SHA-256，覆盖 5 个原始 `.dna` 和 5 个派生 `.gb/.fa` fixtures；重命名、改目录、大小写/路径分隔符变化均可识别；同名不同内容不误报。
- **反例测试**：改名、子目录、单字节修改、同名自建文件。
- **JSON schema 0.5.0**：`common-envelope-v0.5.json`、`assembly-result-v0.5.json`、`roundtrip-result-v0.5.json` 使用 `$defs`，核心对象 `additionalProperties:false`；新增 schema 反向测试（缺字段、类型错误、非法坐标、未知字段）。
- **可复现构建**：`scripts/build_release.py` 同时生成 academic-full 与 redistributable 两个 ZIP，写入 `RELEASE-MANIFEST.json`。
- **真实任务前向验证**：使用用户提供的 `S_eubayanus_Chr1.dna` 与 `Hyg换Se CDC15.dna` 完成解析、CDC15/Hyg 定位、同源臂映射、QC、引物风险复核，并明确 CDC15 必需基因存活风险与残余 CDS 片段风险。

### 未完成（因此保持 RC）

- 1,000 组/方法 property 与 300 组失败 property：当前为 100 成功 + 20 失败（固定 seed）。
- 核心模块行覆盖率 ≥90% 与分支覆盖：未运行 coverage 门禁。
- 9 项 mutation tests：未系统执行。
- rich-feature strict SnapGene 往返：尚未建立多值/Unicode/长 note 的 rich fixture 并通过 `--strict --require-snapgene`。
- 新增 `design_gene_replacement.py`、真正 Gibson 引物设计、design_report 输出：尚未实现。
- Python 3.11/3.12 CI 矩阵：本机仅有 Python 3.10。

### 兼容性

- `schema_version` 从 `0.4.0` 升级为 `0.5.0`；v0.4 schema 文件保留在 `references/schemas/`。
- `smoke_suite.py` / `smoke_academic.py` 继续存在，但 `tests/test_smoke.py` 现在运行 `smoke_core.py`。
- `check_redistributable.py` 输出结构变化（hash-first），调用方需更新。

## v0.4.4 — 零贡献拒绝、坐标不变量、schema 0.4 与属性测试（2026-08-15）

### 修复

- **零贡献片段拒绝**：新增共享 `validate_unique_contributions(fragments, overlap, circular)`，Gibson 与 In-Fusion 共用。贡献 `<= 0` → `ZERO_CONTRIBUTION_FRAGMENT`；圆形产物长度短于 overlap → `PRODUCT_SHORTER_THAN_OVERLAP`。失败时 `ok:false`、非零退出、不写 `--out`、不输出空序列或倒置坐标。
- **origins 硬性不变量**：新增 `validate_origins(origins, product_length)`（生产代码抛错，不依赖 assert）：
  - `ORIGIN_COORDINATE_INVALID`
  - `ORIGIN_LENGTH_MISMATCH`
  - `SOURCE_MAPPING_INVALID`
- **`clip_end` 生效**：`_mapped_part_segments` 新增 `clip_end` 参数，`retained_end = min(end, clip_end)`；完全位于 clip_end 之后的 feature 不迁移，穿过 clip_end 的 feature 明确失败/丢弃。
- **JSON 契约升级到 `schema_version=0.4.0`**：新增 `references/schemas/common-envelope-v0.4.json`、`assembly-result-v0.4.json`、`roundtrip-result-v0.4.json`；测试用 jsonschema 验证成功/失败 envelope、Gibson 与 roundtrip 输出。
- **qualifier 差异键级报告**：`qualifier_differences` 现在输出 `feature / location / missing_keys / unexpected_keys / changed / important`；`delivery_grade` 细分为 `lossless` / `core-compatible-with-safe-differences` / `core-compatible-with-important-differences` / `failed`（`translation/codon_start/gene/label` 等视为 important）。
- **Skill 包装**：删除顶层 `README.md`；SKILL.md 内不再写死本机 SnapGene 路径或用户名；SnapGene 仅通过 `--snapgene-exe` / `SNAPGENE_EXE` / 自动发现。
- 新增 `tests/test_v06.py`：零贡献圆形/线性反例、clip_end、JSON Schema、100 组固定 seed 随机成功组装性质测试、20 组失败稳定性测试。
- `requirements.txt` 增加 `jsonschema>=4.17,<5`。

### 兼容性

- `schema_version` 从 `0.3.0` 升为 `0.4.0`（v0.4.x 契约已变化，调用方必须更新）。
- v0.4.3 的 `origins` 字段在 v0.4.4 保持不变；零贡献与坐标非法从“可能输出坏数据”变为结构化失败。
- `delivery_grade` 旧值 `core-compatible` 仍会出现在无 qualifier 差异但有其他 warning 的场景。

### 发布验证

- `quick_validate.py` 通过。
- `python -m unittest discover -s tests -v`：42 tests OK（含 100 组随机性质测试）。
- `scripts/smoke_suite.py`：125 项通过。
- 官方 SnapGene 核心往返通过；qualifier 差异按键报告。
- ZIP 安全与许可检查通过。

## v0.4.3 — CompoundLocation 顺序/operator 与迁移安全校验（2026-08-15）

### 修复（P0）

- 删除 `_merge_parts` 中的全局 `sorted(parts, key=start)`，新增 `_merge_parts_in_biological_order`：只按传入顺序处理；`operator=order` 完全不合并，`operator=join` 仅当相邻且同 strand 时才合并。
- 单一 `FeatureLocation` 被圆形 overlap 拆分时生成 `join` CompoundLocation；原有 CompoundLocation 的 parts 顺序与 operator 原样保留。
- 映射片段按源序列生物学方向生成：正链为 overlap→retained，负链为 retained→overlap。跨原点正链 CDS 现在得到 `join{[4:8](+), [0:2](+)}`，`extract()` 与源序列一致，不再出现 `CCAAAA`。
- 每个保留 feature 迁移后执行安全校验：`feature.extract(source.seq) == migrated.extract(product.seq)`；不匹配立即 `AssemblyError("FEATURE_MIGRATION_MISMATCH")`，非零退出且不写 `--out`。
- 线性组装中确实被裁掉的 overlap feature 会从产物中丢弃并产生明确 warning：`feature was partially dropped because it lies in a removed linear overlap`。

### Origins

- `origins` 由单一 `segments` 拆分为 `contribution_segments`（独占贡献，用于产物组成）与 `source_mappings`（完整来源映射，允许 overlap 映射到同一产物区间，按源序列顺序排列）。
- 圆形首片段跨原点的 source mapping 标注 `"wraps_origin": true`；线性被裁 overlap 标注 `"dropped": true`。
- 代码内不变量：`sum(contribution lengths) == product_length`。
- 测试不变量：`reconstruct_source_from_mappings(origin) == source_fragment_sequence`。

### Roundtrip / 交付等级

- `validate_roundtrip.py` 新增 `lossless` 与 `delivery_grade`：
  - `lossless`
  - `core-compatible`
  - `failed`
- `SKILL.md` 明确：`snapgene-gb` 为优先交付格式；原生 `.dna` 只保证核心语义；`strict_passed=false` 不得描述为“完全无损”；正式交付前必须运行 `--strict`。

### 测试

- 新增 `tests/test_v05.py`（8 个测试方法，覆盖正/负链部分跨原点、join/order 保留、跨原点 CDS extract/translation/qualifiers、三片段圆形 Gibson/In-Fusion、中间片段跨 overlap feature、origins 重建、FEATURE_MIGRATION_MISMATCH 失败且不写产物）。
- `tests/test_v04.py` 更新为 18 项（线性 overlap 中被裁 feature 的 warning 语义）。
- `python -m unittest discover -s tests -v`：35 tests OK。
- `scripts/smoke_suite.py`：125 项通过。

### 兼容性

- 成功 JSON envelope 的 `schema_version` 仍为 `0.3.0`。
- `origins` 中的 `segments` 字段被 `contribution_segments` / `source_mappings` 取代；旧 `start/end/length/source_* / product_*` 保留。
- 线性 Gibson 中被裁 overlap 上的 feature 从“截断迁移”改为“丢弃 + warning”，属有意的正确性修复。

## v0.4.2 — 发布阻断热修（2026-08-15）

### 修复（P0）

- **线性 Gibson 坐标回归**：`gibson()` 的 contributions 恢复为“线性首片段全长、后续片段裁 overlap；圆形全部裁 overlap”。`origins` 新增 `source_start/source_end/product_start/product_end/segments`，修复第二片段 feature 错位到 `[4:8]` 的问题（现在正确迁移到 `[8:12]`）。
- **许可声明补全**：`THIRD_PARTY_NOTICE.md` 增加 `fixtures/pDONR201.dna`，attribution 改为官方要求的 `www.snapgene.com/resources`；商业安全删除建议同时删除 `fixtures/pDONR201.dna` 与 `fixtures/golden/`，并建议 `academic-full` / `redistributable` 双包策略。顶层 README 与 `fixtures/golden/README.md` 同步。

### 修复（重要项）

- **圆形 overlap feature 迁移**：圆形 Gibson/In-Fusion 不再简单裁掉首片段左侧 overlap。跨 overlap 的 feature 映射到闭环副本；跨闭环 feature 生成 `CompoundLocation`（连续时合并为单一 location）。线性组装中被裁掉 overlap 上的 feature 会产生 warning。
- **往返验证 qualifier 语义**：`validate_roundtrip.py` 输出 `core_passed` / `strict_passed` / `qualifier_differences`；qualifier 不一致默认加入 `warnings`；新增 `--strict`，启用后 qualifier 丢失即非零退出。`jprint` 的 envelope `ok` 现在跟随 payload 的 `passed` 字段。
- **标准测试发现**：smoke runner 移到 `scripts/smoke_suite.py`；`tests/test_smoke.py` 改为 unittest wrapper。`python -m unittest discover -s tests` 现可收集全部 26 个 test case。
- **Codex Skill UI 元数据**：`agents/openai.yaml` 改为 `interface` + `policy` schema（`display_name` / `short_description` / `default_prompt` / `allow_implicit_invocation`）。
- **新增回归**：线性 Gibson origins 覆盖到 `product_length`、带 feature 的第二/第三片段坐标准确、圆形 Gibson/In-Fusion 全片段 feature 映射为 `[0:8]`、`--strict` qualifier 失败路径、unittest discover。

### 兼容性

- 成功 JSON envelope 的 `schema_version` 仍为 `0.3.0`。
- `origins` 新增字段为纯增量，旧字段 `start/end/length` 保留。
- `validate_roundtrip.py` 新增 `--strict`；默认行为从“静默忽略 qualifier 差异”变为“产生 warning”。
- 未启用 `--strict` 时 `passed` 仍表示核心语义（序列/拓扑/feature 核心坐标）通过。

### 发布验证

- `scripts/smoke_suite.py`：125 项通过。
- `tests/test_v03.py`：8 项通过。
- `tests/test_v04.py`：17 项通过。
- `python -m unittest discover -s tests`：26 tests OK。
- 使用本机 SnapGene（`the local SnapGene executable`）的 `snapgene-gb` 与原生 `dna` 语义往返核心通过；qualifier 差异按新策略出现在 warnings，`--strict` 按预期失败。

## v0.4.1 — 圆形 Gibson、通用酶切末端与许可声明（2026-08-15）

### 修复

- **圆形 Gibson/In-Fusion**：`check_gibson_overlaps` 与 `join_by_homology` 新增 `circular=True`。圆形组装现在校验最后→第一片段的闭环 overlap，并在拼接时额外裁掉一次 overlap（产物线性化于第一个片段左同源臂之后）。闭环不匹配返回 `OVERLAP_MISMATCH`，不再错误成功。
- **digest-ligate 通用末端模型**：不再复用 Type IIS 专用的 `golden_gate.part_fragment()`。vector 与 insert 的末端直接由 `restriction_hits` 的 `raw_top/bottom_cut_boundary` 有符号关系生成：
  - `raw_t == raw_b` → blunt
  - `raw_t < raw_b` → 5'-overhang
  - `raw_t > raw_b` → 3'-overhang
  - 已用 EcoRI / PstI / SmaI 回归验证。
- **fragment 拓扑修正**：digest-ligate 与 TA/TOPO 中被切开的载体 `AssemblyFragment.topology` 改为 `linear`；只有最终产物标记 `circular`。
- **TA 局部坐标**：载体 fragment 的 `cut_boundary` 改为 0 与 `len(vector)`，原始切点改存 `FragmentEnd.source_cut_boundary`。
- **失败 envelope 与成功 envelope 对齐**：`jfail` 现在输出 `schema_version`、`command`、`data: null`、`warnings` 和 `error`。
- **许可风险**：新增根目录 `THIRD_PARTY_NOTICE.md`，明确 `fixtures/golden/*.dna` 及其派生 fixture 不受 MIT 覆盖，并说明 SnapGene 学术/非营利/政府使用与商业授权要求；`fixtures/golden/README.md` 同步加注。
- **Skill 元数据**：新增 `agents/openai.yaml`（保留顶层 `README.md`）。

### 兼容性

- 失败 JSON 新增 envelope 字段，`error` 结构不变。
- 圆形 Gibson 的 `origins` 贡献长度变为每个片段 `len - overlap`；线性 Gibson 行为不变。
- `FragmentEnd` 新增可选 `source_cut_boundary`，旧调用方读取 `cut_boundary` 语义不受影响。
- 成功输出 `schema_version` 仍为 `0.3.0`。

### 发布验证

- `tests/test_smoke.py`：125 项通过。
- `tests/test_v03.py`：8 项通过。
- `tests/test_v04.py`：13 项通过（新增圆形 Gibson 闭环、PstI/SmaI 末端模型、失败 envelope 形状与 TA 局部坐标）。
- 使用本机 SnapGene（`the local SnapGene executable`）的 `snapgene-gb` 与原生 `dna` 语义往返通过。

## v0.4.0 — 统一末端模型、结构化失败与 golden fixtures（2026-08-15）

### 新增

- 新增 `scripts/assembly_model.py`：统一 `AssemblyFragment` / `FragmentEnd` 结构（`sequence`、`topology`、`left_end`、`right_end`、`overhang_sequence`、`cut_boundary`），Gibson/In-Fusion、Golden Gate、digest-ligate、TA/TOPO 共用。
- 新增 `fixtures/golden/` 独立测试数据：真实 pDONR201、pDEST40、pENTR D-TOPO、pGEM-T、pcDNA3.2-V5-GW-D-TOPO 载体，以及从 SnapGene feature 坐标独立生成的 `attB-EmGFP.gb`、`pENTR-EmGFP.gb`、`pDEST-EmGFP.gb`、`pGEM-T-insert.gb` 预期产物。
- 新增 `tests/test_v04.py`（10 项）：用 committed golden fixtures 校验序列、方向、拓扑、junction 与 feature 迁移。

### 行为变更

- **Gibson / In-Fusion 失败即停止**：相邻 overlap 必须完全匹配；不匹配返回 `ok:false` + `error.code=OVERLAP_MISMATCH`，非零退出且不写 `--out`。
- **Gateway 严格校验**：
  - entry / donor / destination 必须显式标注拓扑（缺失 → `MISSING_TOPOLOGY`，非 circular → `INVALID_TOPOLOGY`）。
  - att 位点枚举全部正/反链出现，必须恰好一对且方向正确；错误码：`ATT_SITE_MISSING`、`ATT_SITE_NOT_UNIQUE`、`ATT_SITE_ORIENTATION`、`ATT_SITE_ORDER`、`ATT_SITE_EMPTY`。
  - Gateway BP/LR 通过 `ConstructModel` 迁移 feature，并迁移 att 位点与 insert feature。
- **TA/TOPO 显式末端前提**：新增 `--vector-end {t-tailed,blunt}` 与 `--insert-end {a-tailed,blunt}`；不再用 `endswith("A")` 推断。缺少 `--vector-cut` → `MISSING_VECTOR_CUT`，末端前提不满足 → `END_TYPE_MISMATCH`。
- **统一失败输出**：`simulate_cloning.py`、`simulate_advanced.py`、`golden_gate.py` 的所有失败均输出 `{"ok": false, "error": {"code": "...", "message": "..."}}` 并非零退出。
- Golden Gate 输出新增 `fragments`（共享末端模型）；junction 兼容性改为按实际单链延伸序列互补判断。

### 兼容性

- 高级克隆脚本的错误输出从纯文本改为结构化 JSON；调用方必须解析 `error.code`。
- 成功输出保持 `schema_version=0.3.0` envelope，并新增 `fragments` 字段。
- TA/TOPO 旧调用（只传 `--vector-cut`、不传末端前提）会以 `END_TYPE_MISMATCH` 失败。
- Gateway 仅支持标准正向 att 位点对（左位点正链、右位点反链；attB 插入两位点正链），镜像/跨原点布局按方向错误拒绝。

### 发布验证

- `tests/test_smoke.py`：125 项通过。
- `tests/test_v03.py`：8 项通过。
- `tests/test_v04.py`：10 项通过（golden fixtures）。
- 使用本机 SnapGene（`the local SnapGene executable`）对 `fixtures/pDONR201.dna` 的 `snapgene-gb` 与原生 `dna` 语义往返均通过。

## v0.3.3 — 高级克隆模拟修复（2026-08-15）

### 修复

- **TA / TOPO 不再直接拼接**：新增 `--vector-cut`（0-based 载体切口边界）并校验 insert 顶链末端必须为 A（3'-A overhang）。缺少切口坐标或 insert 末端不是 A 时非零退出；产物按 `vector[:cut] + insert + vector[cut:]` 成环，拓扑固定为 circular。载体 3'-T overhang 无法从序列文件读出，仍在 notes 中明确声明为假设。
- **Gateway BP / LR 不再盲目拼接**：改用标准 attB1/attB2、attP1/attP2、attL1/attL2、attR1/attR2 真实序列定位位点（attP/attL/attR 采用生物学方向：左位点正链、右位点反链；attB 插入片段两位点正链）。支持镜像方向和 circular 跨原点布局。
  - BP：`attP1..attP2` 供体区域替换为 `attL1 + insert + rc(attL2)`。
  - LR：`attR1..attR2` 目的载体区域替换为 `attB1 + insert + rc(attB2)`。
  - 位点缺失或方向不支持时非零退出，不再 fallback 为 `destination + insert`。
- `simulate_advanced.py` 所有失败路径统一以 `SystemExit` 输出清晰错误，不再把不存在的 att 位点当作“近似成功”。

### 兼容性

- TA/TOPO 旧调用（不带 `--vector-cut`）现在非零退出；带 `--vector-cut` 的成功输出字段保持兼容。
- Gateway BP/LR 成功输出的 `product_sequence` 更接近真实重组产物（右端 attL2/attB2 为反链互补序列），与 v0.3.2 的“拼接近似”不兼容，属有意的生物学修复。
- JSON 成功 envelope 的 `schema_version` 仍为 `0.3.0`（契约形状未变）。

### 发布验证

- `tests/test_smoke.py`：122 项通过。
- `tests/test_v03.py`：8 项通过。
- 新增回归：TA/TOPO 缺 `--vector-cut` 报错、TA 产物按显式切口成环、insert 无 3'-A 报错、Gateway BP 用真实 pDONR201 attP 位点得到 attL 产物、Gateway LR attL×attR 得到 attB 产物、att 位点缺失报错。
- 使用本机 SnapGene（`the local SnapGene executable`）对 `fixtures/pDONR201.dna` 的 `snapgene-gb` 与原生 `dna` 语义往返均通过。

## v0.3.2 — Golden Gate 发布阻断修复（2026-08-15）

### 修复（发布阻断）

- **Golden Gate 改为 all-or-nothing**：任何部件无法干净切出、overhang 长度不一致，或任一 junction（含最后 insert 到载体左端的成环 junction）不匹配，命令立即非零退出，**不写任何产物文件**，不再出现“只剩载体仍报告成功”的情况。
- **linear 记录禁止首尾环绕片段**：`part_fragment` 只接受 `start0 < end0` 的非环绕片段；linear 载体产生 “序列末端 + 开头” 骨架时直接报错。
- **载体必须是 circular**：Golden Gate 最终会成环，因此未标注 circular 的载体记录直接拒绝；FASTA 等无拓扑标注的载体可用新增的 `--vector-topology circular` 显式声明。产物拓扑固定为 circular。

### 修复（评审建议）

- `codon_optimize.py`：路径样式的输入若文件不存在，按 `FileNotFoundError` 报错退出，不再把 `missing-protein.fa` 当成蛋白质字符串；FASTA 输入必须恰好包含一条记录，多记录直接拒绝。
- `mutagenesis.py --op delete-codon`：除长度必须是 3 的倍数外，新增读框起点校验——按“读框从第 1 位开始”的约定，`--start` 必须是 1/4/7/... 的密码子边界；`2..4` 这类偏移区间会被拒绝。

### 兼容性

- `golden_gate.py` 的失败路径从“返回 ok:true + 空/残缺产物”改为非零退出且不产出文件，属于有意的错误语义修复。
- 成功路径的 JSON 字段保持兼容；新增 `parts[].wraps_origin` 诊断字段，`topology` 固定为 `circular`。
- 新增 CLI 参数 `--vector-topology {circular,linear}`；未提供时仍读取记录自身拓扑。
- `mutagenesis.py` 现在假定编码读框从第 1 位开始；此前接受的非边界删除区间会报错。
- JSON 成功 envelope 的 `schema_version` 仍为 `0.3.0`（契约形状未变）。

### 发布验证

- `tests/test_smoke.py`：110 项通过。
- `tests/test_v03.py`：8 项通过。
- 新增回归：linear 载体拒绝环绕骨架、无效 insert 非零退出且不写产物、overhang 不匹配非零退出且不写产物、缺失蛋白文件报错、多记录 FASTA 拒绝、非密码子边界删除拒绝。
- 使用本机 SnapGene（`the local SnapGene executable`）对 `fixtures/pDONR201.dna` 的 `snapgene-gb` 与原生 `dna` 语义往返均通过。

## v0.3.1 — Golden Gate 切位几何修复（2026-08-15）

### 修复

- **重写 `golden_gate.py` 的 Type IIS 切位计算**：不再使用错误的 `识别位点+1..+5` 内部碱基，改用 `sg_common.restriction_hits` 从 Bio.Restriction 导出的双链切口边界。BsaI 正链 0-based 边界现为 **7 / 11**，与 `test_v03.py` 的断言一致。
- 同时搜索正、反两个方向的识别序列（如 BsaI 的 `GGTCTC` 与 `GAGACC`），反向位点使用镜像切位几何。
- 片段切片改为“两条 top-strand 切口边界之间的序列”，并选择**不含完整识别序列**的那条片段（插入片段或载体骨架均适用）。
- 切口超出序列末端的位点会被拒绝或跳过，不再产生虚假的 `product_sequence`。
- junction 校验补上最后一个 insert 到载体左端的**成环 junction**，并检查所有部件 overhang 长度一致。
- `mutagenesis.py`：point / insert-codon / delete-codon 增加位置与 DNA/IUPAC 碱基校验；`overlap-pcr` 不再返回原模板冒充结果，改为明确报错“尚未实现”。
- `codon_optimize.py`：默认 `auto` 识别输入类型（DNA/IUPAC 输入按 DNA 处理），DNA 重编码保留末端终止密码子，并拒绝非 3 倍数长度的编码序列。
- `primer_qc.py` 移除未使用的 `Bio.Seq` import，与“pure-Python”说明一致；`assemble_contig.py` 文档不再声称输出 read placement。
- 更新 README/SKILL 中与实际运行结果不符的测试计数。

### 兼容性

- JSON 成功 envelope 的 `schema_version` 仍为 `0.3.0`（契约形状未变）；工具包发布版本为 v0.3.1。
- `golden_gate.py` 保留 `experimental` 标记、`junctions`、`notes` 和 `product_sequence` 顶层字段，并新增 `parts`、`enzyme_site`、`topology` 等诊断字段；旧调用方读取方式不变。
- `mutagenesis.py --op overlap-pcr` 从“返回原序列”变为非零退出，属有意的错误语义修复。

### 发布验证

- `tests/test_smoke.py`：103 项通过。
- `tests/test_v03.py`：8 项通过。
- Golden Gate 新用例覆盖：正/反向位点边界 7/11、越界切口拒绝、双向 overhang 匹配与成环 junction。
- 使用本机 SnapGene（`the local SnapGene executable`）对 `fixtures/pDONR201.dna` 重新验证 `snapgene-gb` 与原生 `dna` 两条路径：序列、拓扑、feature 语义均通过；qualifiers 差异与 Standard GenBank LOCUS 警告按既有策略单独报告。

## v0.3.0 — 语义模型与可验证输出（2026-08-15）

### 新增

- 新增统一 `ConstructModel`，内部坐标统一为 0-based、half-open，减少脚本间坐标解释不一致。
- 支持在编辑和迁移过程中保留 `CompoundLocation`、`join/order` 与跨原点 feature，不再强制展平成单一 start/end。
- 限制酶结果新增正链和负链切口边界，能够表达黏性末端、平末端和 Type IIS 方向。
- 字典型 JSON 输出新增 `schema_version`、`ok`、`command`、`data` 和 `warnings`，同时保留 v0.2.1 的原顶层字段。
- 新增 `scripts/validate_roundtrip.py`，可自动检查 GenBank、原生 `.dna`，以及可选的官方 SnapGene GUI 语义往返。
- 新增 8 个 v0.3 回归测试，覆盖复合位置、跨原点 feature、切口几何、JSON 契约和往返验证。

### 修复与改进

- feature 编辑改为按 location parts 操作，避免跨原点或复合 feature 被错误扩展成近乎全长。
- 明确区分限制酶识别位点与实际切口，不再把二者混用为同一个坐标。
- 统一成功输出结构，使调用方能够稳定判断命令、数据、警告和 schema 版本。
- 将官方 SnapGene 往返检查纳入发布验证；SnapGene 6.0.2 可打开并重新保存生成文件。

### 兼容性

- v0.2.1 的字典型顶层业务字段仍保留，旧调用通常无需立刻迁移。
- 所有字典型 JSON 输出均已纳入 `schema_version`/`ok`/`command`/`data`/`warnings` envelope（含 `analyze_seq.py translate`）。
- SnapGene 6.0.2 可能规范化部分 qualifier，Standard GenBank 导入时也可能提示非标准 LOCUS 行；验证器按生物学语义比较，不要求字节完全一致。

### 已知限制

- 错误输出尚未全部统一为版本化 JSON envelope。
- 原生 `.dna` 格式对复杂 qualifier 和 compound location 的保真度受底层库能力限制。
- `digest-ligate`、Golden Gate、In-Fusion、TA、TOPO 和 Gateway 等高级克隆仍标为实验性，不应直接作为湿实验执行依据。
- `primer_qc.py` 使用启发式互补评分，不等同于 Primer3 或其他热力学计算。
- 当前没有完整的基因组编辑工作流、全基因组脱靶检查或自动 Gibson overlap/引物联合设计。

### 发布验证

- `tests/test_smoke.py`：92 项通过。
- `tests/test_v03.py`：8 项通过。
- Skill 结构校验通过。
- GenBank、原生 `.dna` 和 SnapGene 6.0.2 语义往返通过。

## v0.2.1 — P0 热修（2026-08）

### 修复

- 取消通过字符串替换拼装 GenBank，改为使用 Biopython 语义化写出，修复错误的 REFERENCE/FEATURES/ORIGIN 结构。
- 补齐 `molecule_type=DNA`，并保留原记录的描述、拓扑、annotations 和已有 features。
- 修正 Biopython Restriction API 的坐标误读，区分识别位点与切口位置。
- FASTA 和原始短序列默认按 linear 处理；圆形序列只依据可靠元数据或显式参数判断，并支持跨原点位点搜索。
- 修正六读框编号映射，限制输入为 1–6。
- 修正负链 ORF translation，按反向互补链翻译。
- 不再把不存在的文件路径误当成 DNA；原始序列改用严格 IUPAC 校验，多记录 FASTA 不再静默拼接。
- 引物结果报告真实结合边界和扩增子长度，并将正、反引物酶切尾拆分配置。

### 可靠性

- 增加线性/环状、跨原点、正负链和读写往返回归用例。
- 建立 92 项 smoke test，覆盖 P0 缺陷与主要 CLI。
- 对近似模拟功能增加“实验性”标记和限制说明。

## 初始原型 — 功能基线

- 提供 SnapGene `.dna`/GenBank 读取、序列分析、限制酶位点、引物设计、注释与克隆模拟等基础工具。
- 初始版本建立了较完整的命令覆盖，但坐标、拓扑、复合 feature、GenBank 写出和高级克隆语义尚未达到可用于实验决策的可靠度。
- v0.2.1 和 v0.3.0 的重点是先修复语义正确性和验证能力，再扩展新的实验设计功能。

## 升级建议

- 从 v0.2.1 升级时，优先读取 v0.3 的 `data` 字段；兼容期内仍可读取旧顶层业务字段。
- 对跨原点或复合 feature，不要再假设一个 feature 只有单一 start/end；应遍历 location parts。
- 对酶切结果，分别使用识别区间、正链切口和负链切口，不要用识别位点起点代替切口。
- Golden Gate 调用方必须处理非零退出：任何部件无效或 overhang 不匹配都不会产出文件；FASTA 载体需显式传 `--vector-topology circular`。
- TA/TOPO 调用方必须提供 `--vector-cut`；Gateway BP/LR 只有在标准 att 位点全部命中时才会产出序列，调用方需处理非零退出。
- v0.4 起高级克隆失败输出统一为 `{"ok": false, "error": {"code": ..., "message": ...}}`；调用方应按 `error.code` 分支处理，而不是解析错误文本。
- 用于实验前必须复核引物特异性、末端兼容性、阅读框、宿主背景和完整构建设计；Skill 输出只作为计算辅助。

## v0.8.0-dev3 发布版迭代（2026-08-19）
- primer3 四层重试：tailed → binding-only → relaxed-Tm → slide-retry
  （budget=min(25,n//4)，产物 n±100 bp，Tm 50–72 °C，GC 20–80% 不放宽）；
  输出 `boundary_offset_5p/3p`；全失败附 alternatives。
- 知情权：`operation_consent.py`（ConsentBroker ask/auto/callback）；
  `design_primers.py`/`plan_assembly.py` 支持 `--consent ask|auto`/`--yes`；
  未确认不执行，plan 待确认不写 construct。
- 透明性：结果携带 `operation_log`（后端/版本/参数/输入 SHA-256 前缀/重试/
  决策/写出文件）与 `consent.pending`。
- 参数溯源：`references/biological-parameters-sources.md/.json`。
- 场景套件 90 个论文来源场景；人类可读
  `reports/scenarios/scenario-validation-human-report.md`。
## v0.9.0-dev2 — 生物学技术审计闭环（2026-08-22，dev 预览）

- 新增 `planning/executor.py` 统一方法执行器；最终 `.gb/.fa/.dna` 仅在 executor 返回 validated product 后写出。Golden Gate、digest-ligate、Gibson/overlap 均调用对应底层序列算法，环状构建检查 closing junction，feature 按真实产物迁移。
- Golden Gate 的 Type IIS 前置证据收紧为每个输入片段恰好两处可用位点；明确指定但不可执行时阻断，不静默换法。
- CRISPR 报告增加 candidate total/searched/skipped/invalid/truncated 覆盖统计；截断、失败或参考不匹配时禁止 complete/低风险结论。
- 基因替换加入 replacement orientation、species/strain/ploidy/locus、essentiality evidence、complementation strategy 门禁；反向、复合和跨原点边界显式处理。
- 完整 CDS 增加 start/terminal-stop/translation 约束；GenBank translation 的换行/逗号分隔按蛋白序列规则规范化后比较，真实不一致仍失败。
- overlap <12 bp 阻断；PCR 非法 length/GC 结构化失败；密码子表和协议建议均带来源、日期和适用性语义；构建物输出增加 `.provenance.json`。
- 本版修复 Gateway LR 回归并补充 provenance sidecar 测试；修复 Azimuth 第三方代码在 Python 3.14 下的字符串比较/转义警告，并以 `-W error::SyntaxWarning` 编译检查。
- 最终实测：源码/academic 427 OK+7 skip，redistributable 399 OK+9 skip；coverage、mutation、property、90 场景、Cas-OFFinder v2/v3、Azimuth、DeepCpf1、Primer3 和 SnapGene 官方核验均已归档。发布状态仍为 `0.9.0-dev2`，不是 RC。

