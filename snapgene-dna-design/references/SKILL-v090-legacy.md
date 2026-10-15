---
name: "snapgene-dna-design"
description: "SnapGene-compatible DNA plasmid design toolkit. Parses .dna/.gb files, analyzes sequences, finds restriction sites, designs primers, runs validated basic simulations plus clearly labeled experimental cloning approximations, annotates features, and exports SnapGene-readable files. Invoke when user asks to design or analyze a plasmid, work with SnapGene .dna files, design primers, simulate cloning, find restriction sites, or generate construct files (质粒设计、引物设计、酶切分析、克隆模拟、SnapGene 文件处理)."
---

# SnapGene DNA Design

面向合成生物学的质粒设计与分析工具链。让 AI 助手能够像使用 SnapGene 一样读取、分析、设计并生成质粒文件——完全在计算端完成，不需要湿实验。

当前版本：**v0.9.0（正式发布候选已完成全部技术门禁，等待真人独立生物学验收）**。在 v0.9.0-dev2 生物学技术审计闭环之上加入可确认、可验证、可回滚的个人经验规则链。

### v0.9.0-rc1 个人经验规则闭环（历史章节；已随 v0.9.0 发布）

- 自然语言提出经验后只能形成候选规则；系统必须展示固定格式预览，用户明确确认后才写入 `user_rules/rules.json`。
- 用户规则使用受控 JSON 条件语法，禁止 Python `check` 和 `eval`；未知字段、操作符、单位或动作必须返回待澄清。
- `check`/`eval` 不仅在顶层禁止，嵌套在条件、来源或列表中的可执行字段也一律拒绝；`schemas/experience-rule-v1.json` 是当前规则、预存规则和候选的共同校验入口。
- 动作 `block` 是硬阻断：任何确认参数都不能绕过，也不能写出被阻断的产物；`--acknowledge-experience-warning` 只用于 `warn_and_confirm`/`ask`。
- 持久范围只有全局和当前项目；仅本次规则属于当前 DesignSpec。没有 `lab` 或显式 `user_id` 身份层。
- 预存库包含原有两条经验和经人工审核的 C-01～C-31，共 33 条；首次初始化后与用户规则一样保存在 `user_rules/rules.json`。它们不是不可变内置策略，用户可以修改、停用或删除。升级已有规则库时只补入从未引入过的新预存 ID，不恢复用户已经删除的旧规则。
- 每次新增、修改、停用、删除、恢复和回滚都创建新版本，并在 `user_rules/history/` 留下事件；删除是有历史的逻辑删除，不会在下次运行时自动复活。
- `manage_experience_rules.py` 支持自然语言新增、确认、查看、停用、删除、恢复、回滚、Markdown 清单导出和确定性规则评估。
- 对预置短语之外的经验，Agent 应先整理为声明式规则，再用 `manage_experience_rules.py --candidate-json <JSON或文件>` 暂存候选；不得猜测缺失的阈值、范围或动作。该入口同样必须经用户明确确认才生效。
- 设计验证引物前必须询问用户是否已有引物；`design_primers.py --primer-role validation` 只有在用户明确要求后才能加 `--user-requested-design` 执行，`--yes`/自动确认不能代替这项授权。
- 菌落/煮菌 PCR 在 `simulate_pcr.py --pcr-type colony|boiled_colony` 下会检查产物长度；默认超过 1000 bp 警告并要求确认，允许用户规则覆盖阈值。
- 33 条预存规则覆盖 PCR、菌落 PCR、引物 QC、Sanger/qPCR、Gibson/Golden Gate、验证、来源边界与质粒稳定性。其 `source.verification` 区分“人工规则审核通过”和“来源已独立核验”；除 C-31 外不得把来源线索描述为已完成独立文献核验。

### v0.9.0-dev2 生物学技术审计闭环（本版重点）

- `planning/executor.py` 是唯一最终构建物执行入口：Gibson/overlap、Golden Gate、digest-ligate 走对应序列算法；未返回 `final_construct.status == "validated"` 时禁止写最终 `.gb/.fa/.dna`。
- 环状组装显式验证末段→首段 junction；feature 按最终产物迁移，保留 strand、复合 location、qualifier 和源坐标；不支持的裁剪/跨原点情形明确失败。
- Golden Gate 只有每个输入片段恰好两处可用 Type IIS 位点才会被判定可执行；用户明确指定但证据不足时阻断，不静默换方法。
- `generate_crispr_design_report.py` 输出 `candidate_total/searched/skipped/invalid/truncated`；未覆盖全部候选不得标记 `complete` 或低脱靶推荐。
- 基因替换要求 species/strain/ploidy/locus、essentiality evidence、complementation strategy 和 replacement orientation；反向目标按显式策略处理，缺证据阻断最终输出。
- 完整 CDS 必须通过 start/stop/frame/translation 校验；GenBank translation 的合法换行分隔会规范化后比较，其他不一致仍失败。
- overlap <12 bp 阻断；12–14 bp 条件性提示；15–30 bp 为常规设计范围。PCR 输入、协议适用性、密码子表和来源哈希均结构化记录。
- `--out-construct` 同步输出 `.gb/.fa/.dna/.provenance.json`，写入 assembly method、executor、输入 SHA-256、junction 和验证状态。
- 正式验收同时看源码测试、coverage/mutation/property、真实外部后端和 `D:\SnapGene\SnapGene.exe` 官方往返；任何未完成门禁都不能写成通过。

### v0.8.0-dev3 新增（CRISPR 设计链，dev 预览）

| 脚本 | 功能 | 典型用法 |
|---|---|---|
| `design_guides.py` | 注册表驱动 gRNA 扫描；坐标一律为输入参考轴 0-based 半开；线性拓扑不跨末端 | `design_guides.py target.gb --nuclease spcas9-wt --json` |
| `guide_scoring.py` / `azimuth_backend.py` / `deepcpf1_model.py` | SpCas9=Azimuth V3（Doench-2016）；AsCas12a=DeepCpf1（34bp 上下文）；LbCas12a 拒绝模型 | 由统一报告自动调用 |
| `cas_offinder_adapter.py` | 真实 Cas-OFFinder CLI（input/output 文件，v2.4 生产后端与 v3 实验后端）；参考基因组 SHA 绑定；v3 结果强制标注 experimental/production_ready=false | `search_offtargets()` |
| `annotate_offtargets.py` | 脱靶区间与 GenBank feature 真实区间重叠注释，保留全部重叠 feature | `annotate_offtargets.py hits.json --annotation ref.gb` |
| `generate_crispr_design_report.py` | 统一 JSON/Markdown 报告，可一次输出 GenBank+FASTA+.dna；失败返回结构化报告 | `generate_crispr_design_report.py target.gb --nuclease spcas9-wt --reference-fasta ref.fa --annotation ref.gb --cas-offinder C:\tools\cas-offinder.exe` |
| `recommend_protocol.py` | profile 特征→证据匹配；无匹配返回 unavailable | `recommend_protocol.py --profile profile.json` |
| `sequence_upload_consent.py` | 绑定式一次性上传 receipt（默认拒绝） | 由 CRISPOR 适配器调用 |

### v0.9.0-dev1 新增（Natural-language Construction Agent Core）

- `design/spec.py` + `schemas/design-spec-v1.json`：DesignSpec v1（状态机、探索/正式模式、来源溯源）。
- `agent/`：澄清规则、自然语言解析、会话、统一调度器与交付包。
- `planning/method_selector.py`：方法比较（选择/排除证据，评分非成功率）。
- `scripts/run_design_agent.py`：Agent 入口；`scripts/validate_design_spec.py`：规格验证。

### v0.9.0-dev 新增（多源组装规划 + 可行性过滤，dev 预览）

| 脚本/模块 | 功能 | 典型用法 |
|---|---|---|
| `scripts/plan_assembly.py` + `planning/` | M1 多源组装规划器：多质粒+意图→片段分配/组装策略/引物清单/逐步手册/可行性评级 | `plan_assembly.py a.gb b.gb --intent-json intent.json --out-json plan.json --out-markdown plan.md` |
| `rules/` | M2 可行性规则与经验库：安全声明式条件、项目/全局覆盖、版本历史；禁止可执行 `check` | `from rules.engine import evaluate_plan` |
| `scripts/manage_experience_rules.py` | 自然语言经验候选→确认→保存→查看/修改/停用/删除/回滚→清单导出；也提供触发点检查 | `manage_experience_rules.py --text "以后菌落 PCR 超过 1000 bp 时提醒并询问我" --json` |
| `scripts/primer_design_engine.py` | M3 引物引擎：primer3_core 优先、启发式明确回退；四层重试 tailed→binding-only→relaxed-Tm→slide-retry（boundary_offset_5p/3p）；overlap/酶切位点尾巴+NEB 保护碱基；Tm/GC/发夹/二聚体/3'GC 校验；无解附 alternatives | `from primer_design_engine import design_region_primers` |
| `scripts/operation_consent.py` | 发布版知情权/透明性：参数确认、放宽/降级/无解/外部写入结构化询问；未确认不执行；operation log 记录后端/参数/输入 SHA/重试/产物 | `from operation_consent import ConsentBroker` |
| `references/biological-parameters-sources.*` | 全部默认生物学参数单一来源（参数名/默认值/来源/URL/检索日期/代码引用） | 查询参数默认值前先读此文件 |
| `scripts/pcr_strategy.py` | M4 PCR 策略：GC/AT/长片段推荐酶+添加剂+官方 protocol 链接，延伸时间公式化 | `pcr_strategy.py --length 2000 --gc 75` |
| `parts/` + `scripts/parts_library.py` | M5 元件库：骨架/启动子/标签/抗性/ori 带 accession 溯源 | `parts_library.py --type promoter` |
| `scripts/online_sources.py` | M6 NCBI eUtils/BLAST/Addgene 对接骨架；离线显式 `offline-unverified` | `online_sources.py` |

### v0.9.0-dev 打磨（数值平行验证 + 50+ 文献场景套件）

- `scripts/run_scenario_suite.py`：90 个文献/官方协议来源场景全链条模拟，
  结果写入 `reports/scenarios/`，并生成人类可读
  `scenario-validation-human-report.md`（出处/描述/操作/产物四要素）。

### v0.9.0-dev 打磨（数值平行验证 + 真实场景回归）

- `scripts/validation_crosscheck.py`：Tm（Primer3/BioPython Tm_NN/Wallace）、
  酶切位点（Bio.Restriction/直接 motif 扫描）、overlap GC/Tm 独立交叉验证；
  冲突结构化上报。
- `tests/test_e2e_scenarios.py`：师兄骨架+GOI Gibson、Gateway LR、四片段
  Golden Gate、高 GC PCR 四类真实科研场景端到端回归。
- `tests/test_destructive_inputs.py`：空序列/坏路径/恶意规则表达式/短区域/
  空 consent 等破坏性输入。
- `README.md` 新增完整安装/门禁/交叉验证说明。

### v0.8.0-dev3 发布版迭代（release-iteration-requirements.md）

- **primer3 第 4 层 slide-retry**：前三层无解后释放 `FORCE_*_START`，5' 端
  向内滑动 ≤ min(25, n//4) nt，产物窗口 n−100..n+100 bp，Tm 50–72 °C，GC
  保持 20–80%；成功输出 `boundary_offset_5p/3p`；全部无解时给出可执行
  `alternatives`（外扩 20–40 bp / 内部引物对），`--require-primer3` 失败关闭
  并附 alternatives。
- **知情权询问机制**：`operation_consent.ConsentBroker`（ask/auto/回调）；
  `design_primers.py` 与 `plan_assembly.py` 增加 `--consent ask|auto` 与
  `--yes`。未确认的放宽/降级/无解/待确认 construct 写入一律不执行。
- **操作透明**：每个结果带 `operation_log`（后端+版本、参数、输入序列
  SHA-256 前缀、重试路径、consent 决策、写出文件）与 `consent.pending`。
- **参数单一来源**：`references/biological-parameters-sources.md/.json`。
- **生物学正确性审计**：`reports/biological-correctness-and-sourcing-audit.md`（2026-08-20）。
- **论文场景套件扩面**：90 场景（Gibson≥3、Golden Gate≥3、SOEing≥3、
  高 GC/AT≥5、长片段≥3、失败重试链 12、酶切连接≥3、真实载体≥5），含
  pDONR201/pENTR/pDEST/pGEM-T 真实 fixture 工作流与 catalog 引用。

### v0.7.0-dev2 新增（真实 Primer3 设计后端）

- **真正调用 Primer3 选引物**：`scripts/primer3_core_backend.py` 通过 Boulder-IO 调用官方 `primer3_core`，由 Primer3 选择并排序成对引物；不再只是自写候选加几个 Primer3 热力学分数。
- **崩溃隔离**：主程序不导入 primer3-py 的原生扩展。引擎在子进程运行，即使第三方二进制崩溃也不会拖垮主工具。
- **正式任务可失败关闭**：真实引物设计优先使用 `design_primers.py ... --require-primer3`。缺少引擎、执行失败或 Primer3 找不到合格 pair 时返回结构化失败，禁止悄悄改用经验结果。普通 `auto` 模式允许明确警告后降级；`--engine heuristic` 可显式选择探索性经验模式。
- **可审计输出**：`design_engine.selected`、`version`、`verification` 明确区分 `real-external-engine` 与 `unverified-heuristic`。Primer3 指标保留其真实含义（如 `HAIRPIN_TH`、`SELF_ANY_TH`），不再伪装为 dG。
- **Gibson 原生 overhang 语义**：5' overlap 通过 `SEQUENCE_OVERHANG_LEFT/RIGHT` 交给 Primer3；Tm/GC 基于 3' binding，结构指标覆盖完整 tailed oligo。`product_size` 保留结合区产物长度，另报 `primer3_product_size_with_overhangs`。
- **真实集成门禁**：`validate_primer3_integration.py` 必须使用真实 `primer3_core` 返回 5 组普通 PCR pair 和 1 组带 overlap 的 Gibson pair；假模块或 skip 不计为通过。

### v0.6.0-rc2 基线要点

- **发布门禁已建立并达标**（`scripts/coverage_gate.py`、`scripts/mutation_tests.py`、`scripts/property_tests.py`）：12 个核心模块行覆盖 ≥90%、分支 ≥85%（rc2 实测 95.67–100% / 91.67–100%）；12 个指定 mutation 全部被杀（kill rate 100%）；Gibson/In-Fusion/Golden Gate/digest-ligate 各 1,000 成功 + 300 失败、Gateway/TA 各 500 + 200 的固定 seed property 全规模通过。
- **兼容性预检**：`snapgene_compatibility.py` 在导出前识别 `order`、复合 location、Unicode feature 名称和 qualifier 规范化风险，分别给出 `safe` / `core-compatible` / `manual-review-required`，不再把已知差异笼统称为无损。
- **安全交付包**：`export_delivery_bundle.py` 始终生成权威 GenBank、SHA-256 清单和兼容性报告；仅在 core-safe 时默认附送原生 `.dna`。`--allow-core-risk` 是显式人工确认，不是静默降级。
- **诚实门禁**：`validate_roundtrip.py` 的核心比较现包含 `join/order` operator；rich fixture 门禁只接受预检能够提前分类的官方差异，任何未登记的核心损失仍失败。
- **v0.6 功能**：`design_gene_replacement.py`（基因替换设计：定位目标 → 同源臂 → Gibson 引物 → QC → 产物文件）；`design_primers.py --gibson`（真正 Gibson 引物设计，overlap 尾与 binding 区分离报告）；`generate_design_report.py`（统一 design-report JSON/HTML）。

标有“实验性”的克隆功能仍只能做概念预演，不得当作可直接执行的湿实验方案。

需要核对版本变化、兼容性或迁移注意事项时，读取 `references/upgrade-log.md`。

## 环境说明

- 所有脚本位于 `scripts/` 目录，用 Python 3.10+ 运行。
- 依赖：`biopython`、`snapgene_reader`、`sgffp`（原生 `.dna` 写出）。用 `pip install -r requirements.txt` 安装。Primer3 是 GPL 可选外部运行时，不随 MIT Skill 打包；可用 `--primer3-core` 或 `PRIMER3_CORE` 指向其可执行文件。`primer_qc.py` 只做启发式互补评分，不等同于 Primer3。
- 若 `python` 不在 PATH，使用你本机 Python 解释器的完整路径调用，例如
  `<python> scripts/parse_dna.py ...`。
- 大多数脚本用 `--json` 输出 JSON 供程序解析，也支持人类可读文本输出；个别探测脚本（如 `primer3_probe.py`）固定输出其诊断格式，具体以各脚本 `--help` 为准。
- v0.5 字典型 JSON 包含 `schema_version: "0.5.0"`、`ok`、`command`、`data`、`warnings`；失败 envelope 为 `{"ok": false, "error": {"code": ..., "message": ...}}`。Schema 文件见 `references/schemas/`（v0.4 schema 保留为兼容参考）。

## 质量门禁（正式发布前必须全绿）

```bash
python -X utf8 -m unittest discover -s tests -v     # 单元 + rich fixtures
python -X utf8 scripts/smoke_core.py                # 核心合成 smoke
python -X utf8 scripts/property_tests.py            # 全规模 property（1,000+300 × 4 方法，500+200 × 2 方法）
python -X utf8 scripts/mutation_tests.py            # 12 个指定 mutation，kill rate ≥90%
python -X utf8 scripts/coverage_gate.py             # 核心模块行 ≥90%、分支 ≥85%
python -X utf8 scripts/validate_rich_fixtures.py    # 内部 strict + 已声明的官方兼容性差异门禁
python -X utf8 scripts/validate_primer3_integration.py --primer3-core "<primer3_core>"  # 真实引擎，禁止 skip
```

报告落盘于 `reports/`（coverage / mutation / property / rich）。

## 脚本清单

### 读取与分析
| 脚本 | 功能 | 典型用法 |
|---|---|---|
| `check_env.py` | 环境自检：依赖版本、缺失检测 | `check_env.py` |
| `parse_dna.py` | 解析 .dna/.gb → 结构化 JSON（序列信息、features、primers、notes） | `parse_dna.py plasmid.dna --json` |
| `analyze_seq.py` | 序列分析：GC%、长度、反向互补、翻译（6 读框） | `analyze_seq.py seq.fa stats` / `analyze_seq.py seq.fa translate --frame 1` |
| `find_sites.py` | 限制酶位点分析与模拟酶切（片段长度） | `find_sites.py plasmid.gb --enzyme EcoRI,BamHI` |
| `align_seq.py` | 双序列比对（全局 NW / 局部 SW），报告 identity/mismatch/indel | `align_seq.py query.fa ref.fa --mode global` |
| `align_sanger.py` | Sanger 测序 read 比对参考（consensus、覆盖度、确认状态） | `align_sanger.py ref.gb --reads read1.fa read2.fa` |
| `msa.py` | 多序列比对（渐进式），输出 consensus 与对齐 FASTA | `msa.py seq1.fa seq2.fa seq3.fa --out-fasta aln.fa` |
| `assemble_contig.py` | contig 组装（贪心 overlap，CAP3 简化） | `assemble_contig.py --reads reads.fa --min-overlap 20` |
| `methylation.py` | **实验性**甲基化提示；当前不用于判定 dam/dcm/EcoKI 敏感性 | `methylation.py plasmid.dna --enzyme EcoRI,ClaI` |

### 设计与克隆
| 脚本 | 功能 | 典型用法 |
|---|---|---|
| `design_primers.py` | 引物设计：真实 `primer3_core` 或显式启发式降级；正式设计加 `--require-primer3`；Gibson 以 Primer3 原生 overhang 语义分离 5' tail 与 3' binding | `design_primers.py template.gb --start 100 --end 900 --require-primer3 --json`；`design_primers.py template.gb --start 100 --end 900 --gibson --fwd-overlap ACGT... --rev-overlap TGCA... --require-primer3 --json` |
| `simulate_pcr.py` | PCR 扩增模拟（引物定位 + 产物） | `simulate_pcr.py template.fa --fwd ATGC --rev GCAT` |
| `simulate_cloning.py` | Gibson 重叠严格校验：任一 overlap 不匹配即 `OVERLAP_MISMATCH` 失败且不写产物；**digest-ligate 为实验性**，使用共享末端模型校验黏性末端 | `simulate_cloning.py --method gibson --parts a.gb b.gb --overlap 20` |
| `simulate_advanced.py` | **实验性** In-Fusion 严格同源校验；TA/TOPO 需显式 `--vector-cut`、`--vector-end t-tailed`、`--insert-end a-tailed`；Gateway BP/LR 严格校验唯一 att 位点对（显式拓扑、方向、顺序）并迁移 feature | `simulate_advanced.py --method ta --vector vec.dna --insert pcr.fa --vector-cut 0 --vector-end t-tailed --insert-end a-tailed` |
| `golden_gate.py` | **实验性** Golden Gate / Type IIS：共享末端模型、all-or-nothing、统一错误 JSON；载体必须 circular（FASTA 载体加 `--vector-topology circular`） | `golden_gate.py --parts vec.gb ins1.gb --enzyme BsaI` |
| `mutagenesis.py` | 定点突变 / 密码子插入删除（位置、碱基与密码子边界校验）；overlap PCR 尚未实现，调用会明确报错而非返回原模板 | `mutagenesis.py seq.fa --op point --mutation 100:A` |
| `design_gene_replacement.py` | **v0.6** 基因替换设计：定位目标基因 → 同源臂 → Gibson 引物（overlap/binding 分离）→ 替换 CDS QC → 产物 GenBank + design JSON | `design_gene_replacement.py --template p.gb --target-gene cdc15 --replacement hyg.fa --flank-len 40 --out out.gb --json` |
| `codon_optimize.py` | 密码子优化（E. coli/酵母/人类密码子表），默认 auto 识别 DNA/蛋白输入；缺失文件按错误处理，多记录 FASTA 拒绝 | `codon_optimize.py CDS.fa --host ecoli` |
| `protein_tools.py` | 蛋白反向翻译 / 双链寡核苷酸退火 | `protein_tools.py reverse-translate MALTW` |

### 编辑与产出
| 脚本 | 功能 | 典型用法 |
|---|---|---|
| `edit_plasmid.py` | 质粒编辑：插入/删除/替换/点突变/线性化/环化/旋转，自动迁移 feature | `edit_plasmid.py plasmid.gb --op insert --pos 100 --seq AAAA --out out.gb` |
| `annotate.py` | 自动注释：默认正链 3 帧，`--both-strands` 扫 6 帧；输出 feature 表或 GenBank | `annotate.py seq.fa --both-strands --out-gb annotated.gb` |
| `validate_construct.py` | 一键 QC：拓扑、坐标、读框、提前终止、唯一酶切位点、引物、junction | `validate_construct.py construct.gb --json` |
| `simulate_gel.py` | 凝胶电泳模拟（片段→迁移距离/条带） | `simulate_gel.py --fragments 1000,500,200` |
| `draw_map.py` | SVG 质粒图谱（环形/线性，按类型着色、引线标签、图例、双主题） | `draw_map.py plasmid.dna --out map.svg --theme light` |
| `convert.py` | 批量格式转换（.dna/.gb/.fa/.embl 互转） | `convert.py plasmid.dna --out plasmid.gb --format genbank` |
| `batch.py` | 批量操作流水线（parse/validate/sites/convert） | `batch.py DIR --op validate --json` |
| `write_dna.py` | 写出文件：GenBank-SnapGene 兼容格式 / 原生 .dna（sgffp）/ FASTA | `write_dna.py ATGC... --out plasmid.gb --format snapgene-gb` |
| `snapgene_compatibility.py` | **v0.6 rc2** 导出前体检：按格式报告 core/strict 风险与推荐交付方式 | `snapgene_compatibility.py plasmid.gb --json` |
| `export_delivery_bundle.py` | **v0.6 rc2** 安全交付包：权威 GenBank + 可选 `.dna` + 兼容性报告 + 哈希清单 | `export_delivery_bundle.py plasmid.gb --out-dir delivery --json` |
| `generate_design_report.py` | **v0.6** 统一 design-report：汇总 design JSON / assembly JSON / 产物文件 → 独立 HTML + 机器可读 JSON | `generate_design_report.py --design-json d.json --assembly-json a.json --product p.gb --out report.html --json` |
| `validate_roundtrip.py` | 自动语义往返：技能写出→读回；可选官方 SnapGene 转换核对（`--snapgene-exe` / `SNAPGENE_EXE` / 自动发现）；默认对 qualifier 差异产生 warning，`--strict` 时 qualifier 丢失即失败 | `validate_roundtrip.py plasmid.dna --format snapgene-gb --snapgene-exe "<SnapGene.exe>" --strict --json` |

## 坐标约定

- CLI 参数及兼容字段中的 feature/识别序列坐标使用 **1-based 闭区间**（与 SnapGene 一致）；内部 `ConstructModel` 只使用 **0-based 半开区间**。
- 限制酶结果区分识别序列、正链切口和负链切口；优先读取每个 hit 的 `top_cut_boundary_0based` / `bottom_cut_boundary_0based`。兼容字段 `top_cut_first_bases_1based` 仍保留，不得与识别起点混用。
- feature JSON 的 `location` 保留 `operator`、`parts`、各段 strand 与 `wraps_origin`；旧 `segments`、`start`、`end` 同时保留。
- 拓扑：只有显式标注 `circular` 才按环状处理，默认 `linear`（保守，避免误判裸序列）。

## 标准工作流（AI 参考）

1. **读取**：拿到 .dna/.gb 文件先 `parse_dna.py` 结构化，向用户复述质粒要点（拓扑、大小、关键 feature）。
2. **理解需求**：明确任务类型——设计引物 / 找酶切位点 / 编辑质粒 / 组装克隆 / 注释 / QC。
3. **应用经验规则**：涉及验证引物时，先检查 `before_validation_primer_design` 并询问用户是否已有引物；只有用户明确要求才设计。菌落/煮菌 PCR 方案形成后检查 `after_pcr_plan`，超过经验阈值必须显示实际长度、警告并询问。
4. **执行**：调用对应脚本。真实引物设计必须加 `--require-primer3`，并检查 `design_engine.verification == "real-external-engine"`；否则只能称为探索性候选，不得称为 Primer3 验证。将 JSON 结果转述为用户可读结论（含坐标、Tm、引擎来源和风险）。
5. **编辑与产出**：用 `edit_plasmid.py` 做插入/删除/替换/点突变；先运行 `snapgene_compatibility.py`，再用 `export_delivery_bundle.py` 生成带审计报告的交付目录。
6. **验证**：交付前务必 `validate_construct.py` 做 QC，再运行 `validate_roundtrip.py` 核对序列、拓扑、feature operator 与 qualifier；本机有 SnapGene 时传 `--snapgene-exe` 做官方转换验证。

## 常见任务速查

- 环境有问题 / 缺依赖 → `check_env.py`
- 用户问"这个质粒里有哪些 feature/酶切位点" → `parse_dna.py` + `find_sites.py`
- 用户问"帮我设计一段引物" → `design_primers.py`
- 用户问"这段 PCR 产物多长" → `simulate_pcr.py`
- 用户问"在这个位置插入/删除/替换一段" → `edit_plasmid.py`
- 用户问"两个片段能不能用 Gibson 组装 / 酶切连接" → `simulate_cloning.py`
- 用户问"能不能用 Golden Gate / Type IIS 组装" → `golden_gate.py`
- 用户问"怎么引入点突变" → `mutagenesis.py`
- 用户问"优化这个序列的密码子" → `codon_optimize.py`
- 用户给序列要注释 → `annotate.py`
- 用户要"检查这个质粒有没有问题" → `validate_construct.py`
- 用户要"比对测序结果/两条序列" → `align_seq.py` / `align_sanger.py`
- 用户要"看酶切/PCR 产物在胶上的样子" → `simulate_gel.py`
- 用户要"画质粒图谱" → `draw_map.py`
- 用户要"转换文件格式" → `convert.py`
- 用户要"把设计导出成 SnapGene 能打开的文件" → `snapgene_compatibility.py` 后运行 `export_delivery_bundle.py`
- 用户要"确认导出的文件没有丢序列/拓扑/feature" → `validate_roundtrip.py`

## 注意事项

- `.dna` 为 SnapGene 原生二进制（TLV 格式）；读入用 Biopython 的 `snapgene` 解析，失败时回退 `snapgene_reader`。
- 原生 `.dna` 写出用 `sgffp`（MIT，支持 Python 3.10+）。
- 权威交付文件为标准 GenBank；原生 `.dna` 是方便打开的副本，不是信息真值源。含 core 风险时默认不生成 `.dna`，不得为了满足文件扩展名而静默丢语义。
- **官方 SnapGene 核验发现（本机 `D:\SnapGene\SnapGene.exe`，2026-08-16）**：
  - `snapgene-gb`：8 个 rich fixture 中 5 个官方往返 lossless（含正/反 CDS、join 复合、跨原点、Unicode、多值 note）；`db_xref` 前缀（如 `UniProtKB:`）会被 SnapGene 剥除、多值 `note` 会截断、`synonym` 可能丢失（safe 级规范化）；**`order` 复合位置在 SnapGene 往返中不被保留（core 级，feature 会变化）**。
  - 原生 `.dna`：旧比较口径下核心语义官方核验 6/8 通过；**复合 `join` feature 与 Unicode feature 名称经 SnapGene 导出 .dna 后不保（Unicode 会乱码）**。rc2 将 location operator 纳入核心比较后，`order` 也明确列为 core 风险。
  - SnapGene 会按序列重算 CDS `translation`、补充 `transl_table` 等默认 qualifier；手工填写与序列不符的 translation 会被覆盖。
- `edit_plasmid.py` 已能逐段迁移 `CompoundLocation`；原生 `.dna` 写出现在同样保留多段 segments 与 strand，qualifiers 层级差异由 `validate_roundtrip.py` 报告。
- SnapGene 6.0.2 官方导出的 `GenBank - Standard` 可能触发 Biopython 的非标准 LOCUS 列警告；`validate_roundtrip.py` 会将其收集到 `warnings`，并独立判断序列、拓扑、feature 与 qualifier 是否一致。
- **交付等级**：`snapgene-gb` 是优先交付格式；原生 `.dna` 保留序列、拓扑和核心 feature，但不保证全部 qualifier 无损。`strict_passed=false` 时只能描述为 `core-compatible`，不得说“完全无损”。正式交付前必须运行 `validate_roundtrip.py --strict`；strict 失败时可以交付 core-compatible 版本，但必须把 qualifier 差异明确告诉用户。
- 引物 Tm 计算默认使用盐校正公式（Na+ 50mM），输出多种 Tm 供用户参考，不替用户做最终判断；酶切位点尾巴用 `--fwd-site`/`--rev-site` 分别设置。
- 所有模拟结果均为计算预测，交付前需向用户说明可被湿实验验证。
- `experimental: true` 的输出只能作为概念预演；在实现完整末端兼容性、Type IIS 切口几何、feature 迁移和反应约束前，不得据此给出可执行实验结论。
