# 真实任务测试结论与修复开发文档

日期：2026-09-07。状态：代码修复、真实任务复测与官方文件验收完成。版本：0.9.2。

后续复查已发现本版仍存在错误的通过判据及被改动的测试模板。以上为历史阶段状态，不代表当前验收结论。更正、修复及 0.9.3 证据见 [完整性复查](INTEGRITY-AUDIT-AND-REPAIR-20260907.md)。

## 给项目负责人的结论

五题都生成了文件，但生成文件不能视为任务完成。题 1、2 的主 DNA 序列正确；题 3 的制备来源和表达起始读框有问题；题 5 缺骨架制备步骤；题 6 的 guide 载体缺少 scaffold。还有引物导出和安装入口缺陷。

本轮目标是修通完整设计与交付，不增加 Construct Review，不新建目标验证引擎，不把摘要和测试数量当成可用证据。修复后重新执行这些实际任务，检查订购引物能否从真实模板得到中间体、连接结果是否符合功能要求、交付文件能否被官方 SnapGene 正确读取。

原始安装版与测试包逐文件一致，源码基线为 `52390a0e7443ce9ebf6c828a6484832b38549349`。五名执行代理均为 GPT-5.6-Luna / max，使用全新历史，只接收各自题目和完整源文件。目录由指令隔离，共享文件系统不是操作系统访问沙箱。

## 实际结果

| 任务 | 独立检查结论 | 对交付的影响 |
|---|---|---|
| 1：七模板 URA3 受体 | 7 份实际 PCR 和 Gibson 可重建 5,283 bp 作者成品；官方 SnapGene 回读序列、拓扑和特征位置一致。14 条源文件 Native 引物均不等于订购序列。 | 主 DNA 正确，引物交付错误；推荐 Pipeline 入口还因缺 schema 失败。 |
| 2：EcoFlex 三色 | 3,003、2,935、2,902、4,674 bp 四份主序列与独立参考相同；实际发现并改造 TTAG/GAAG 接口。通过旧实验性入口和额外注释适配脚本完成。 | 部分能力有效，但正常入口、特征传递和方法相关检查未形成可靠流程。 |
| 3：GFP 变体表达 | 克隆引物 `NcoI_reverse_cloning` 在实际库存及已制备突变模板上无所需 3′ 退火段；使用了理论融合片段作为模板，且缺共同同义突变的制备引物。 | 制备链不成立，不能照交付步骤得到文件。 |
| 3：表达上下文 | 5,993 bp 文件中 NcoI 起始读框为 `MDASSSSS*`，第 9 个密码子终止。报告改用下游偏移 4 nt 的 ATG 作 CDS。 | 不能以选取另一段可翻译区间证明原表达设计成立；未实测下游 ATG 的起始效率。 |
| 5：双表达四报告 | 文件 8,236 bp，两个融合 ORF 可以提取。骨架 B1、B2 直接截取，未给实际 PCR 或酶切制备。A2 在完整供体上另有一处满足声明的 20 nt 退火区匹配，截短模板检查掩盖了它。 | 制备链不完整；需从完整源文件核查扩增。8,236 与作者 7,895 bp 的差异本身不作为失败理由。 |
| 6：CDC48 | 编辑后蛋白仅 R105G，90 bp 供体与编辑窗口相同。实际 PCR/组装确实生成交付的 11,240 bp guide 文件，但 guide 后缺 `GTTTTAGAGCTAGAAATA` 共 18 nt scaffold。 | 编辑和供体局部正确，guide 结构不完整。不能只检查 spacer 存在。 |
| 4：计时器 | 原始供体未取得，本轮未执行。 | 材料缺口，不计作 skill 失败。 |

题 3 的表达起始约束参考 [pET 厂商说明](https://www.sigmaaldrich.com/US/en/technical-documents/technical-article/genomics/cloning-and-expression/plasmid-nomenclature)。题 6 原文明确要求引物同时提供 guide 和 Cas9 所需结构序列，见 [Hu et al., 2018，Results 与 Figure 2](https://pmc.ncbi.nlm.nih.gov/articles/PMC5868978/)。

### 参考输入 erratum

root 生成的复测参考 pML104 GenBank 已更正为 `output/retest-materials-20260907/q6/pML104_public_viewer.gb`。原 public viewer 的 AmpR `translation` 保留了 viewer 显示用的逗号及 terminal `*`；修正版只规范化该字段，DNA 序列与坐标未改变，并在 `source_translation` 保留原始字段内容。此项是参考材料格式更正，不是 skill 算法错误。原盲测输入不覆盖，参考 ZIP 不修改。

## 已确认的共同问题

1. **理论序列被当作已制备物料。** 融合设计、序列截取、同义修改的结果可直接进入下一步，宿主模型容易漏掉实际引物或酶切。Recipe 对多片段及骨架制备支持不足，迫使模型写大量胶水。
2. **局部检查代替完整功能上下文。** 题 3 改画 CDS 后局部翻译通过；题 6 spacer 和编辑验证通过，却没有保住 sgRNA scaffold。
3. **方法检查互相冲突。** QuikChange 的互补引物被通用二聚体规则拒绝；突变 Tm 把替换区长度当作实际错配数；qc_only 结果被当成无复制子的质粒。
4. **结构化数据在交接时降级。** Pipeline 不能取步骤输出字段；Recipe 序列化把 `primers` 列表覆盖成字典；新构建的制备引物、中间体和源文件标注没有统一交付。
5. **引物标注损坏。** 标注器把完整 oligo 长度当成退火区长度；Native 导出器又从该区间提取模板序列替代完整 oligo。序列回读自洽，订购序列却已被改掉。部分 GenBank 路径读取还依赖 Windows 默认编码。
6. **安装和发现路径不完整。** 测试包缺 `schemas/construction-task-v1.json`；部分检查入口找不到实际安装在 `D:/SnapGene` 的官方程序。根代理已经用该程序成功读取真实交付文件。

此前集中核查已确认的 PCR 多匹配遗漏、环状突变起点依赖、Golden Gate 只取最外侧切点、旧规划器忽略交付引物，也纳入同一主通路修复。保留 [原核查记录](../snapgene-dna-design/output/main-path-review-20260906/MAIN-PATH-REVIEW.md)，不重新设计审查框架。

## 实施内容

### 1. 修实际反应计算

- 在现有 PCR 工具中正确处理正反链、环状起点和多个候选，明确返回或拒绝歧义，不能悄悄选最短。
- 突变流程按具体方法验证引物；修正实际错配计数和圆形侧翼。补齐可制备的反向 PCR 路线。
- Golden Gate 使用真实切位、方向和圆形模板，拒绝忽略内部切点；与旧入口共享计算。普通双酶切连接正确处理方向及跨原点。
- 旧规划器的组装必须接收已选引物产生的实际扩增产物。

### 2. 让正常入口能完成复合任务

- 扩展现有 Gibson Recipe，接受有序的完整模板与目标区间，设计全部片段的引物，包括骨架，并从实际 PCR 产物组装。
- 保留现有 Pipeline，补步骤字段引用和完整记录传递；制备中间体与引物一并交付。限制规划和复算阶段的写文件等副作用。
- 修正现有 Recipe 结果契约、参数文档和方法检查。复杂融合必须由真实模板 PCR 加尾构成，不能把理论融合 FASTA 当库存。
- 核查表达载体既有起始位点及连接读框；pML104 的 guide 构建必须保留完整 scaffold，并给出实际 PCR/环化路线。HDR 区分插入与替换，不能用空 edit 掩盖编辑模型缺口。

### 3. 修交付与安装

- 完整 oligo、真实退火区和链方向分别保存，覆盖 5′ 尾、负链与跨原点；`.gb` 和 Native `.dna` 都保留正确订购序列。
- 正常流程输出源文件标注副本、实际中间体、最终文件和引物表。文本读写显式 UTF-8。
- 打包包含完整运行依赖文件；从解压后的包运行真实入口。统一 SnapGene 程序发现。原始测试版和失败文件不覆盖。

### 4. 用原题确认修复

先运行针对实际缺陷的少量回归，再执行完整测试套件。随后用修复版重新做五题，独立核对实际引物、模板、切位、功能序列和最终文件。无需为了测试数量增加抽象案例。

新的执行代理仍用 Luna / max，只给题目、源文件和修复版 skill；根代理用外部参照及独立反应推导判断，不能把代理自报“完成”当结果。若再次失败，保留失败证据并继续修复，直到这些任务能够完整交付。

## 证据位置与完成条件

原始执行记录：`output/blind-test-20260907/cases/`。独立检查：`output/blind-test-20260907/examiner/`。目录内 `q1-independent.json`、`q3-independent.json`、`q5-independent.json`、`q6-independent.json` 记录关键复算。官方程序直接读取提交文件的证据位于 `examiner/official/`，没有先重写文件再代替原件检查。

完成条件是完整制备链和实际交付通过本轮任务检查，且解压安装包能重现。代码测试、文件能打开、代理的质量摘要，均只能支持其中一部分。湿实验效率、表达产量及全基因组脱靶不在本次计算验证的结论范围内。

## 最终交付结论

本轮五类任务已形成可重放的实际制备链。最终推荐使用下列文件；旧失败产物保留为诊断证据，不能混作新版成品。

| 任务 | 最终推荐结果 | 主要证据 |
|---|---|---|
| 1：URA3 受体 | 5,283 bp；与作者 pYTK096 按环形起点对齐后逐碱基相同；7 份实际 PCR、14 条引物，BsaI/BsmBI 接口保留 | `output/retest-20260907/cases/q1-final/paper-exact/authoritative/` |
| 2：EcoFlex 三色 | 3,003 / 2,935 / 2,902 / 4,674 bp；四份序列与独立参照相同；受体两处碱基修改由实际 inverse PCR 制备 | `output/retest-20260907/cases/q2/final-replay/` |
| 3：GFP 三变体 | 三份均 5,995 bp；真实 NcoI/BspHI 兼容端连接，实际表达为 MM-His6-TEV-GFP；CDS 762 bp，准确包含首个 Met；仅指定的第 66、145 位氨基酸变化 | `output/retest-20260907/cases/q3/final-replay/release_WT/`、`release_Y66H/`、`release_Y66H_Y145F/` |
| 5：双表达 | 7,895 bp；与作者 pTS1042 逐碱基相同；3 份实际 PCR；两个完整 ORF、A3 接收背景、AmpR 与 ori 保留 | `output/retest-20260907/cases/q5/paper-exact/annotated/authoritative/` |
| 6：CDC48 | guide 11,258 bp，完整 79 nt scaffold；90 bp 双链供体；编辑后记录 3,508 bp；蛋白仅 R105G，PAM TGG→TCG | `output/retest-20260907/cases/q6/final-replay/guide/authoritative/`、`hdr/candidate/` |

题 3 的全插入区域 PCR 为 1,030 bp，空 pET 对照为 404 bp；两个端点引物可用于双向测序，覆盖双接头和两个变体位点。题 6 的 WT/编辑型验证 PCR 均为 249 bp，依靠测序判别，不能靠长度判别。相应订购表和源文件副本保存在各题 `final-replay/verification/` 或 `genomic_verification_compat/`。

修复版第一次盲测仍产生过两个偏差：题 1 的 5,265 bp 版本丢了未来使用的 BsaI 接口；题 3 的兼容酶连接曾出现一处非实际反应产生的连接碱基，且漏标首个 Met。两者均未作为最终成果放行。新一名 Luna / max 执行者只读新版 skill 和原始题面后保住了题 1 的接口；其 5,303 bp 设计与题 5 的 8,540 bp 设计属于有反应证据的其他解，仍保留作对照。最终推荐的题 1、5 使用与论文成品完全一致的路线。

## 实际完成的开发

- **制备链**：完整模板 PCR、多匹配拒绝、环状边界、方法相关的突变引物、全部 Gibson 片段制备、真实 Type IIS 切口以及旧规划器对实际 PCR 产物的使用。
- **真实连接与表达**：删除按期望恢复酶切位点的覆盖分支。反向插入取原扩增子 bottom-strand 切口区间再反向互补。表达起点由原载体上下文经过真实切口投影，检查到指定完整 CDS 终点，不能遇到提前 stop 就把短片段当完整 ORF。新增兼容 vector/insert 酶参数，常规 Recipe 即可完成题 3。
- **任务约束**：Recipe 参数可带 `expected_components` / `forbidden_components`，复用现有目标验证函数检查落盘候选。缺少必需元件时保留候选证据并拒绝交付。skill 明确区分本次反应消耗的位点和后续功能必须保留的位点。
- **文件交付**：完整 oligo 与实际退火区分开保存；源文件拓扑、注释、跨原点端点和 partial CDS 语义保留。标准 GenBank 导出会省略 SnapGene 原生引物包，所以 Native 保真检查使用官方 Native→Native 保存。自定义 tag 使用兼容的 feature 类型；连续 join 分段合并按等价坐标处理，真实间隙和 `order` 语义丢失仍拒绝。
- **正常入口**：Pipeline 保留记录与步骤字段；Recipe 结果不再覆盖标准字段；正常输出中间体、源文件引物副本和订购表；安装包包含 schemas；Windows 主入口与文件读写显式 UTF-8。

修复过程本身还引入并纠正了终止密码子误判、源字典拓扑丢失和非物理酶切边界分支。这些不是原始盲测问题，报告不将它们混记为原版缺陷。

## 验证证据与边界

全量回归：688 项完成，无失败，真实 Primer3 已启用。7 项跳过分别涉及 Cas-OFFinder、独立预测模型和 live NCBI，不能据此声称这些外部集成通过。本轮最后的原生格式兼容修改另有 29 项定向检查通过。

实际反应独立复算见 `output/retest-20260907/examiner/final-assessment.json`、`paper-exact-assessment.json` 与 `q3-final/q3-final-review.json`。官方 SnapGene 6.0.2 读取实际提交文件的证据在 `examiner/official/`、`examiner/official-native/`。文件没有先按答案重写，再替代提交物验收。

桌面图谱已实际查看 7,895 bp 产物，AmpR、ori、两个完整表达 ORF 与原生引物标注可见：[桌面检查截图](../snapgene-dna-design/output/retest-20260907/examiner/snapgene-desktop-q5.png)。数字序列、特征与引物正确性由独立复算和官方回读支持，截图仅证明桌面打开与显示。

题 4 仍缺原始供体，未冒充测试通过。此版本的验收覆盖本轮五类计算设计及交付，不等于湿实验成功率、表达效果或任意未知任务的保证。`order` 注释无法在 Native 中保真时明确拒绝；标准 GB、Native 和论文源文件的细节差异均保留记录。

安装包：`dist/snapgene-dna-design-v0.9.2-redistributable.zip`。本地安装版已更新为 0.9.2，225 个文件与安装包逐一一致；旧版备份在 `C:/Users/祝浩淇/.codex/backups/skills/snapgene-dna-design-v0.9.1-dev2-20260907-112853/`。解压包入口及安装后入口均成功生成 11,258 bp guide 载体。没有提交或推送 Git 变更。

