# 工程审计报告

2026-09-22；基线 `b87a1d8`，开发分支 `codex/real-workflow-readiness-20260907`。本报告保留修复前证据，最终处置见[修复计划](remediation-plan.md)与[最终报告](final-remediation-report.md)。本轮禁止远程推送、发布与表单提交。原 Reader Demo 未提交修改保留。

## 1. Executive Summary

项目具有真实的 DNA 计算、注释处理、文件生成与证据记录能力，但基线不能声称普遍可靠。完整测试可通过，而独立合成反例仍能绕过目标验证并正式交付错误结果。修复优先级是验证与数据完整性，随后是 Trace 真实性、辅助工具、发布边界和文档。不为架构美观重写有效模块。

全仓库受控清点为 393 文件、263 Python 文件、69,058 Python 行（含测试和第三方代码）。逐区域检查源码/入口/调用和测试；自动语法及关键词扫描只用于定位，不作为正确性证明。生成目录另行分类，未把旧日志或缓存当当前能力。清点与复现保存在 `output/audit-20260922/`。

基线标准发现 845 项测试，832 通过、13 跳过，387.359 秒。发布 runner 因两项 Primer3 测试未显式启用而返回失败；开启 `SNAPGENE_RUN_PRIMER3=1` 后对应 32 项通过 31、另 1 项跳过。`pip check` 无冲突。真实 Cas-OFFinder v2/v3 不可用，不能宣称全基因组验证已经执行。

## 2. Current Architecture

宿主依据 SKILL 理解需求，选择 Recipe、ConstructionTask 或组合 Pipeline；Python 工具计算 DNA，Biopython/ConstructModel 表示序列和注释，Primer3 子进程进行引物计算。`runtime_validate` 与 `runtime_gate` 控制正式交付。旧 `planning/` 与 `agent/orchestrator.py` 有独立路径，成熟度与默认入口不同。

Trace 是旁路：runtime 观察实际调用，recorder 追加日志，projection/process 整理并检查引用，宿主提交科学过程，report/render 固定生成离线报告。条件匹配、变化影响是有限规则，不是科学结论或安全批准。外部序列上传有独立同意机制。没有后台服务器、数据库或项目自己的模型推理服务。

## 3. What Works Correctly

已实现实际 PCR→制备→组装路径、复合位置/负链处理、Native/GenBank 导出、哈希绑定交付和追加式 Trace。基线测试已覆盖大量失败路径与 Trace 三档一致性；这些证据有明确范围，不能覆盖下列新反例。现有独立包和历史 CI 是旧提交证据，本轮将重新测试。

## 4. Confirmed Bugs

| ID / 严重性 | 证据、位置与影响 | 修复方向 / 提交前必须修 |
|---|---|---|
| C01 CRITICAL | `core/runtime_validate.py` 的 goal helper 抛错后仍可能保持 goal_ok=True。合成越界元件检查记录 errors，同时 overall=verified，并被 finalize 正式交付 | 异常清零，错误与验证成功不可并存，端到端反例；是 |
| C02 HIGH | 非 composite 的 Handler execute 重建裸 SeqRecord；point_mutation 源 2 features→产物 0。内部终止突变失去 CDS 后仍通过 | 使用实际变换后的完整记录，保留/修订相关注释；检查保存文件；是 |
| C03 HIGH | `product.required_components` 在部分 Handler 不进入公共目标核验；不存在元件也通过 | 合并合法元件契约并统一验证入口；是 |
| C04 HIGH | 已被任务接受的 `.dna` 输入在部分 Handler 被当 FASTA 读，UnicodeDecodeError | 统一真实输入解析，不按两种后缀猜格式；是 |
| T01 HIGH | Trace coverage 的 normalize 丢 source_sha256，同路径换文件仍匹配旧选择 | 保留文件版本身份，缺版本只作有限匹配；是 |
| T02 HIGH | 通用命令采集可能保留 argv 凭据值；原脱敏只看字典键 | 针对实际 argv/失败异常进行脱敏，保留调用事实；是 |
| R01 HIGH | `build_release._collect` 把临时根目录 `.env`、`private.gb` 都标 MIT/redistributable | 打包明确受控来源，拒绝未审核文件/链接，不扩充黑名单冒充许可审查；是 |
| E01 MEDIUM | requirements 已要求 primer3-py，但 check_env 的 core_ok 不考虑必需 Primer3 后端；缺失项输出还有字典/字符串混用风险 | 环境状态与实际入口需要一致，缺失反例；是 |

Core 复现：`output/audit-20260922/core_probes.py` 与 `core-probes/results.json`；数据全部为独立生成，不取用户 CDC15 答案。其他区域最终确认项追加到本报告，不用疑点充数。

## 5. Architectural Problems

重复的输入读取和写出逻辑导致 Handler 丢注释及格式不一致。修复应集中输入/记录保存接口、使用现有坐标操作，不另造目标验证引擎。Recipe 与旧规划器并存可保留，但必须给出入口和成熟度边界；不因代码相似就删除仍被调用的模块。

## 6. Core Skill Problems

上述 C01–C04 直接影响交付正确性。旧 pET/Chr1 注释冲突另作源/产物比较，不能按离编辑位点远就豁免。宿主真实意图理解仍未经受控对照，不能以固定参数回放证明模型行为可靠。

## 7. Safety Module Problems

主要风险是记录遗漏、版本关联过强、凭据进入日志及把声明当事实。T01/T02 必须修。完整性只限已记录事件，文件存在与生成过程不同；普通脚本成功不等于 Core Validation。人类解释仍需复核，报告不能认证 hidden reasoning。

## 8. Testing Problems

基线全绿没有覆盖另一路 Handler 的注释和目标验证异常。测试必须穿过 plan→execute→validate→finalize，并独立检查物理序列/注释/无效输入拒绝。部分旧测试依赖环境开关、受限文件或外部程序，应逐项记录 skip，不把历史成功率作为用户可用性指标。

## 9. Performance Problems

基线测实际导出/读回、含启动的 inspect CLI 与 Trace 重建，每项 3 次；样本 5k/50k/500k bp 与 100/1000 条记录。500k bp inspect 中位约 12.777 秒，导出/读回约 0.477 秒；1000 条 Trace 重建约 1.731 秒，均含 Python allocation instrumentation。暂不据此增加缓存或重写架构。完整方法、环境和原始样本见[benchmark](../guides/benchmark.md)。

## 10. Maintainability Problems

缺少简明的入口分层与新贡献者指南；大体量历史开发手册难以代替当前架构说明。补当前用户/开发文档，历史审计留存。禁止把全部旧 TODO 自动当需求。

## 11. Security/Robustness Problems

发布文件边界与 argv 脱敏有可复现实质风险。固定第三方模型仅从受信任本地安装载入，pickle 不是任意来源安全格式；不引入远程模型加载。所有新增诊断使用假凭据、合成 DNA，不执行破坏性测试。

## 12. Documentation Problems

README 开始的 params.json/pUC19.gb 不是可直接运行的快速开始，两个历史报告链接缺失。第三方说明仍把 Primer3 写作 optional，而实际主依赖已包含它；GPL 子进程不能自动证明所有许可关系无问题。需明确源文件/发行包/依赖各自许可证。

## 13. Technical Debt

历史 CLI 的坐标/返回格式不同；部分旧规划器和低精度启发式仍有用途，但应标实验性和入口边界。结构化日志不是完整宿主轨迹，人工源材料与模型成本测量仍有外部依赖。

## 14. Vibe-Coding Residue

TODO/fallback/except 关键词逐一按上下文检查。合法后端 unavailable 保留；吞掉格式异常、静默回退、固定满分自评不能作为真实能力。未确认的代码味道不升级为严重漏洞。

## 15. Dead/Unused/Placeholder Functionality

`output/build/reports` 为忽略的产物；`third_party` 为带许可的模型/代码；`docs/development*` 为历史材料。保留有价值记录，不清理 Git 历史。关键字 agent 不支持复杂设计，不能与受验证 Pipeline 混淆。未配置外部程序不是假实现，也不是已验证能力。

## 16. Dependency Problems

主环境 pip 无冲突；版本范围尚非完整锁定环境。将保存受测依赖版本/平台，不盲升包。NumPy/Pandas/Torch/HDF5 等仅用于可选评分；评分预测不能替代实验，也不等于 off-target 测试。

## 17. iGEM-Relevant Gaps

官方团队页确认 Tianjin #6404，Foundational Advance，项目 Nezha yeast genome revival。当前规则、专属 GitLab、六项 Best Software 证据、实际用户研究与版权确认逐项记录。已存在 MIT 文本不证明全部资产归团队；代码文档不等于 Wiki/表单已提交。尚无专属软件仓库提交证据。官方来源见 `docs/igem/official-requirements.md`（本周期生成）。

## 18. Recommended Actions

按[修复计划](remediation-plan.md)依次处理：关闭错误正式交付、保留完整记录、修辅助工具与 Trace、限制打包来源、补实际快速开始和工程文档。随后全量回归、重复同一性能测量、隔离发行包验证，形成最终报告，再开始交接教学。

## 19. 后续确认项与最终处置

下表是调查期间新增的确证，不改变上方基线。所有修复均保留原失败材料；最终测试、环境与发布状态见[最终报告](final-remediation-report.md)。

| ID / 严重性 | 复现与影响 | 采用方案、替代取舍 / 状态 |
|---|---|---|
| C05 HIGH | 插入计划与重算字段不一致；负链分层重复反补；不等长整合臂错误切片；计划可自称元件/删除特征以绕过检查 | 从 task/source 派生完整记录和预期，统一写出；未新建规则系统。已修，提交前必须 |
| C06 HIGH | 旧执行器双酶切只用首个酶；S63–65 另有坐标截去第二位点尾部 | 接实际双酶工具；原源序列不改，正例选择完整源，截断例保留为双酶负例。已修，提交前必须 |
| C07 MEDIUM | S89 合法固定边界需39nt结合区，旧搜索最多36而拒绝有解任务 | 短候选失败后复用现有18–40搜索，完整引物仍过结构检查和真实PCR；不降低阈值。已修 |
| T03 MEDIUM | 前态未知或未变化文件被标新产物；坏context形状可写入后令全部报告失败 | 捕获明确before-state，未知仅presence_only；契约检查提前到append前。已修 |
| A01 HIGH | MSA重排gap丢原碱基；Sanger不看反链、单碱基偶合可显示高identity且coverage错误 | 保留去gap不变式；双方向比对、query覆盖与实际列坐标。仍为小规模启发式，未扩成基因组算法。已修 |
| A02 HIGH | DesignSpec拒绝前已变更，拒绝值被当批准；转换/批量失败exit0，可能覆盖目标 | 先验证后提交状态；统一失败退出，默认拒绝覆盖并提供明确原子覆盖选项。已修 |
| A03 MEDIUM | HTML/伪GenBank当verified、BLAST授权查询静默截断至100nt | 验证实际GenBank和accession；超出当前同步能力明确拒绝，不伪装完整BLAST。已修 |
| A04 MEDIUM | 多记录输入/未知扩展回退不一致，坏规则数据可导致异常或错误高评分 | 共享实际记录读取、保留已知格式错误；无效经验不参与评分。已修 |
| V01 HIGH | 旧测试接受CDS降级求通过；mutation指旧转发文件；coverage漏真实Core/Trace且同名目标混淆 | 保留生物输入，纠正断言；测真实实现和完整路径，独立统计行/分支，不降阈值。工具已修，覆盖达标状态单列 |
| V02 MEDIUM | 独立公开包全套测试出现13处错误，通用Trace/长尾PCR测试隐式依赖未获公开分发确认的pBP材料 | 必需测试改用现有公开合成模板/固定随机输入，增加源碱基独立核对；原外部反应与长尾案例单独保留，只有缺外部材料时才skip。不是跳过必需A/B |
| C08 HIGH | 交付时省略execution/validation hash可跳过一致性条件；显式官方验证缺程序仍继续，truthy非布尔回执可放行；失败清理可能影响并发产物 | 23日收尾补修：必需回执哈希、官方验证缺失/假值拒绝、唯一临时目录与仅清理自身目录。公开入口反例含冲突、写读错误、无效回执；不降低门槛 |

旧 pET 的部分标签/调控CDS与完整编码检查冲突；Chr1 的78条CDS缺终止，来源标为同源转移/六框搜索，其中46条下游三碱基为stop。这证明需按源注释与分析用途分开处理，不能自动补整条染色体，也不能把所有错误归为工具误报。原文件未改。

环境更新：完成本地官方 Cas-OFFinder 2.4.1/3.0.0b3 下载后，真实合成参考搜索、中文路径、bulge和两个预测模型全部运行通过。基线的“未安装”不再是本轮最终阻碍；真实生物基因组的适用性仍未由这些小例子建立。

## 20. 重新打开验收后的遗漏项

f6b5904不是原任务的完整收尾。以下问题由旧预览公开接口、实际CLI和原测试源码确认，原失败日志保存在legacy-red.log；新增回归在tests/test_legacy_preview_contract.py。

| ID / 严重性 | 实际影响 | 修复与验收 |
|---|---|---|
| L01 MEDIUM | 预览先写DESIGN-SPEC和hash，再给传入spec补遗漏说明；文件没有说明，调用者还被静默修改 | 先构造独立完整快照，保存后保持一致；核对实际JSON、hash和原调用参数 |
| L02 MEDIUM | 工作文件和交接文件混在preview；旧文件进入返回清单，坏计划被吞后生成空引物CSV | preview/delivery独立原子包，拒绝覆写；坏JSON失败，不留下半包 |
| L03 MEDIUM | 来源丢失未算hash不匹配，混合链向特征摘要抛错；执行失败仍持有前次候选 | 缺/不可读源拒绝；保留None链向；清除旧候选并保留当次失败诊断 |
| L04 MEDIUM | 未验证状态可先写出包再因状态转换报错；冷导入依赖别的模块修改sys.path | 交接先验证状态，所有formal旧入口拒绝；使用明确的包导入路径 |
| V03 MEDIUM | test_v09_agent检测覆盖运行后只跑部分任务并提前return；缺Gateway材料也会跳过后续无关检查 | 同一场景集接受插桩；Gateway单独条件集成；新增真实点突变成功路径与独立预期 |
| D01 MEDIUM | 一批开发文档只有名称/概述，不能让新开发者实际调用和定位故障 | 补实际签名、数据形状、控制流、依赖、扩展例子、状态与错误地图；执行例子而非仅查文件存在 |

以上均属于仓库内能处理的工作，不应仅列为“技术债”后开始教学。外部账户、权属、独立真人和湿实验仍单列，不改写为自动通过。最终数字和门槛见最终报告后续关闭记录。
