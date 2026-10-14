# 测试、验收与复现

检查程序行为、实际文件与声明范围。任务成功评分读[题库评分规则](question-bank/scoring-v0.1.md)；这里统一软件回归、性能测量、环境复现和包验证，不维护第二套评分标准。

## 按变更选择检查

| 变更 | 必要检查 |
|---|---|
| 文档整理 | 原约束/未决项保留、相对链接、入口职责及无关文件未动 |
| DNA计算、注释或交付 | 原失败和独立正反例；实际公开入口；最终序列、拓扑、features、完整引物及读回 |
| Trace | 上述相关结果，加Off/Observed/Full一致性、normal/strict故障、旧/新版本、关系范围和报告可读性 |
| HTML/JS | 实际离线浏览器、键盘、窄屏和选择状态；语法检查不是UX验收 |
| 发布/安装 | 适用套件、实际后端、受控打包、仓库外解包公开入口、许可/manifest及精确提交CI |

输入可用公开synthetic/rich fixtures或独立生成材料。原错误输入保留；源注释校订另存并记录介入。外部材料的许可、是否随包分发与回归成功分开。

## 回归命令

从项目根执行，使用依赖齐全的同一个解释器：

```powershell
$env:SNAPGENE_RUN_PRIMER3='1'
python -X utf8 -B -m unittest discover -s tests -p test_preparation_primer_locations.py -v
python -X utf8 -B tools/run_test_suite.py
python -X utf8 -B tools/run_test_suite.py --report-json output/test-results.json
python -X utf8 -B tools/smoke_core.py
python -X utf8 -B tools/property_tests.py --quick --out-dir output/property
python -X utf8 -B tools/coverage_gate.py --out-dir output/coverage
```

bash使用`export SNAPGENE_RUN_PRIMER3=1`。真实Primer3跳过会使正式runner失败；`--allow-primer3-skip`仅用于明确的非发布诊断。可选模型、Cas-OFFinder、参考基因组或桌面程序另需实际资源，flag不能代替后端。

完整runner终端及可选`--report-json`分别写实际通过、skip及原因、失败、错误；UTF-8文件不把skip或部分执行的方法算通过。passed由unittest实际成功事件计数，子测试失败和class setup错误单列，计数单位写入文件。原21项逐项处置见[2026-10-13审计](archive/reviews/crispr-skip-audit-2026-10-13.md)。

官方候选沿用八分片及共享wheel预备：`--shard-count 8 --shard-index 1 --verbose --report-json ci-reports/shard-1.json`。排序后按余数分片，每个完整test case恰归一个shard，subtests不拆；全部八份结果才代表完整套件。分片保留准确skip/失败计数和即时失败详情，非法参数在发现前拒绝。独立六case控制检查无遗漏/重复，失败流式与Primer3门槛照常。GitLab安装Node以执行实际查看器线型回归，不新增Python运行依赖。

旧外源模板从当前树移出；原两项已知集成仅在显式`SNAPGENE_EXTERNAL_REGRESSION_TEMPLATE`合法资源下重放并单列。默认两项测试仍实际执行，改为独立固定种子的3100/4200 bp完整环形输入，公共PCR/逐次中间体、导出及Trace一致性职责不减少。直接Primer3 Boulder独立确认的强发卡原失败与复制退火区域歧义为拒绝边界；默认演示不再要求材料身份。没有把合法缺资源skip算通过。

三个真实模型回归在依赖/权重齐全时自动执行；缺模块/权重明确列出，加载错误或参考数值不符仍失败，不以捕获后端错误作为skip。旧`SNAPGENE_RUN_REAL_MODELS=1`可强制运行资源不足时的失败。普通Cas-OFFinder集成可用`CAS_OFFINDER_EXE`或PATH，3.x bulge仍需明确`CAS_OFFINDER_EXE_V3`及OpenCL。Live NCBI默认离线隔离，使用`SNAPGENE_RUN_ONLINE=1`另做真实集成，失败不能降为skip。academic原素材不随源码分发，须合法单独提供；定位在Skill fixtures目录，不能用合成输入代替原案例。

mutation、rich fixtures和scenario分别由`tools/mutation_tests.py`、`tools/validate_rich_fixtures.py`、`tools/run_scenario_suite.py`提供，参数以`--help`为准。场景需按executed/partial/blocked记录，不能将总场景数说成构建成功数。

Coverage读取真实模块的行/分支及套件退出码，目标和阈值以[代码](../tools/coverage_gate.py)为准。插桩不能减少实际执行场景。Mutation先证明原版检查通过；失败捕获率不等于实验可靠率。报告中分别写失败、skip、不可用和未核查。

## 真正检查最终结果

Kit运行时第一阶段由`tests/test_kit_runtime.py`通过真实`run_kit.py`、`describe_tools.py`、`run_step.py`验证。仅测试生成的包外玩具Kit有独立整数算术预期；检查元数据查询不执行Python、三个坏邻居不影响正常Kit、命名空间、真实步骤文件、加载清单哈希/来源、写副作用在调用前被原分类门拒绝、移除恢复及UTF-8路径。类别声明不是OS沙箱。Core/Trace扫描具体项目标识与依赖，不把通用identity/evidence/construct词汇等同于具体Kit。第二阶段`tests/test_kit_contributions.py`保留v1预期，用包外v2玩具验证既有线性Pipeline、必跑gate、逐行来源规则、卸载恢复、坏邻居隔离及显式Kit自有范围接纳。独立字符串切片/反向互补和整数条件决定预期，不调用被测实现生成答案。原Core诊断接纳不在实现范围；CRISPR没有豁免。官方GitLab CI未执行。

Identity子Skill公开验收在`kits/identity/tests/test_contract.py`，由原完整runner的`tests/test_kit_identity_pilot.py`发现。独立固定种子/23 nt删除及3-prime破坏定义164/141 bp/无精确产物；检查实际run_kit文件、原verify回执及通过run_step调用的inspect工具。`tools/compare_kit_compatibility.py`保留原源码e7b1f16、所有失败/重试和原文件，通过原CLI main在相同输入/工作位置执行；只固定观察时钟与UUID，不替换科学计算。比较不忽略字段：原始字节，或JSON对象键顺序/指定源码前缀的结构比较，HTML其他内容不变。观察时间是软件比较控制量，不是实验记录。原科学模块迁移后字节哈希相同。

Toolkit文件关系回归在`tests/test_toolkit_file_relations.py`：实际文件写入/读取、改名但同字节的输入、改后哈希不匹配、较晚记录的artifact，以及真实多步Construct公共CLI。供体640 bp预期由原target/cargo直接切片拼接；关系逐条绑定实际哈希事实，负例不补关系。现有公共Off/Observed/Full和normal/strict故障测试继续核查DNA、质量与文件语义；不改阅读界面。

固定种子CRISPR夹具由`tests/crispr_synthetic_fixture.py`独立构造，无Core导入或私有材料读取。两种种子生成随机质粒/靶标/定位anchor，明确插反、左移一位后PAM末尾CG、注释链冲突、20 nt假CDS、重复靶标与PCR双核心复制，均配正确对照。`tests/test_crispr_synthetic_fixture.py`真实读取独立生成的native packet，经公共run_step保存文件并检查；PCR预期为原模板的已知环形区间加指定5-prime尾。只入库生成器和构造说明，DNA/结果在临时目录。随机promoter/scaffold仅作定位符，不认证其实验功能；这些是工程回归，不是陌生题或湿实验。

候选因素与载体筛查回归在`tests/test_grna_evaluation.py`：字面构造两种不同正/负向模板，独立坐标、GC算术、0/1/4错配、无NGG、环形跨起点、目标重复但无PAM、真并列、条件U6、未知碱基及Cas12a边界；公共registry与run_step读取独立原生packet并检查实际steps文件。它们是独立输入的工程验证；原A/D材料回放单列，不是隔离陌生题评测或实测自切。

位点报告回归在`tests/test_grna_match_reporting.py`：独立单个位点、无效PAM、真正正负链双位点、插反及回文序列；保留原cassette/制备检查，并检查公共CLI实际文件中当前命中与反向插入假设分开。原E公共回放与独立直接读文件/逐碱基搜索另存仓库外，仍是已知题开发回归。

CRISPR cassette工程回归在`tests/test_grna_cassette.py`：独立拼接输入、原生packet日期、正反转录、跨原点、双靶链/PAM、反插/无PAM/无匹配、多cassette选择、注释冲突、假抗性CDS、实际run_step及中文GenBank读回。模板QC使用同名但不同序列feature，验证继承与新增诊断不混淆，ERR仍退出1。真实用户材料和原失败日志只留仓库外；开发者重放和这些独立构造输入均是工程回归，不计陌生题或自主成功。

gRNA制备回归在`tests/test_grna_preparation.py`：两组独立模板与不同新spacer，目标由原材料直接拼接而非被测工具生成；生成路线后再公开PCR/连接/旋转，验证逐位相等及公共交付文件。Tm用独立公开Biopython API与手写Allawi/SantaLucia NN算术、盐修正交叉核查。正反转录、跨原点、重复spacer/结合核心、poly-T、高GC/重复不可行、sequence_only无制备分别核查；计划与模拟/湿实验状态进入Trace。原2.2.3注释用例显式sequence_only保持其职责，默认制备另测，不删除原失败输入或放宽门禁。

从原材料、要求和实际操作独立核验，不能采信宿主自报PASS或仅对照参考序列。允许不同正确路线与环形起点。多轮必须使用上轮真实产物；检查制备、接口、读框、注释、文件和结论。

Core API例子：`python -X utf8 -B snapgene-dna-design/examples/core_workflow.py --out-dir output/api-example`，属于序列文件编辑。实际准备链演示：`python -X utf8 -B snapgene-dna-design/scripts/demo_engineering_cycle.py --out-dir output/demo`，属于预设方案回归，两者都不是宿主陌生任务或湿实验。

单步实际执行与共同交付短例：`python -X utf8 -B snapgene-dna-design/examples/execution_workflow.py --out-dir output/closure-example`。独立闭环反例由`test_execution_closure.py`保留，检查原要求、来源、真正反应、文件及订单用途；新宿主自然任务仍需另一份实际会话证据。实际结果由[当前闭环计划](archive/plans/actual-execution-closure-v2.2.1.md)管理，不在此复制动态测试数量。

Trace记录完整不等于宿主全流程覆盖或科学结论成立。浏览器动作正常不等于人理解正常。桌面SnapGene格式实测、操作者审查、实验表型和全基因组特异性分别提供证据。

本机6.0.2曾在两个转换任务同时运行时不生成部分GenBank输出，同输入串行复测通过；并发因果尚未受控证实。桌面CLI转换目前串行运行，不宣称并发支持。保留每轮失败及原退出码；某一步原样复测通过不能改写此前整套命令的失败报告。[当前闭环计划](archive/plans/actual-execution-closure-v2.2.1.md)保留本次实际记录。

## 环境与独立包

### 官方源码的替代 CI 与逐文件回读

`.github/workflows/official-source.yml` 的控制提交和实际受测提交单列。工作流从官方公开仓库检出指定完整 Git SHA，先经 `tools/check_official_source.py` 检查 HEAD、清单原字节及全部源文件哈希，再安装官方固定依赖、执行八个互斥分片；所有分片回执保留跳过，不能累计矩阵重复。每份 `source-readback.json` 保存文件、预期哈希、实际哈希、大小和是否相符；清单自身绑定其 Git blob，避免循环写入自己的摘要。原网页保存失败克隆须仍被该入口拒绝，不做换行归一化。

该流程是 GitHub 对实际官方提交的计算测试，不是 GitLab CI；工作流页面的控制提交 SHA 不能代称受测源码 SHA。官方分支的流水线创建、任务执行和科学验证分别记录。平台限制未确认时不推断“官方禁止执行器”，也不为触发 CI 修改 main 或执行器安全设置。

### Genome Revival Toolkit

Toolkit独立工程用例在`tests/test_genome_revival_*.py`、`test_revival_evidence.py`与`test_toolkit_trace_boundaries.py`，同一完整runner会发现它们。覆盖真实公共CLI、独立正反例、版本变更、失败保留、Trace三档和实际文件回执；使用已启用的外部Primer3，不以Mock DNA算法替代。

```text
python -X utf8 -B tools/build_toolkit.py --out-dir output/toolkit-package
```

默认从精确Git提交构包，包内只有一个顶层安装入口；Kit子Skill位于kits/并有相邻清单，同版Core由源树生成vendor子集。`--working-tree`只产出诊断包，不是冻结候选。最终候选须在仓库外解包，核对TOOLKIT-MANIFEST及SHA，清除PYTHONPATH后实际调用四Kit和verify。正常宿主另用独立测试配置安装此包，只给自然请求与必要原材料，不给预先选好的引物、完整参数或参考答案；现用安装保持不变。

`tools/verify_toolkit_kits.py --archive <zip> --source-commit <exact-sha> --out-dir <new-directory>`核验完整包：从空目录解包、逐文件对照实际Git源字节，只有既有第三方声明允许注明生成来源；清单外文件与缺失源映射在执行前拒绝。清除PYTHONPATH后，Core/Trace必须来自安装目录，目录页只暴露四个实际Kit。安装包自带的纯构造生成器决定DNA切片、PCR长度和计数预期，随后通过公共run_kit/verify读取实际文件、英文Trace与CRISPR三项gate。运行环境按包内固定依赖在独立venv安装。该验证属于开发组织的合成回归，不是自然请求路由或湿实验；原诊断包和失败探测保留。官方候选逐文件选择/排除及源码哈希由原build_official_candidate工具生成，不上传，不改官方main。

候选必须经过实际Git提交/干净克隆再核对全部清单字节；只有导出目录哈希相等不够。真实官方许可证的CRLF blob会被广义LF属性重写，因此选包只在继承内容确含CRLF时追加模板/许可证保字节规则，记录原属性哈希和转换理由，许可证及CLAUDE/.claude原字节保留。独立字面CRLF回归和旧LF回归分别运行，不规范化验收哈希来放行。自然语言路由材料见`docs/kit-routing/`，开发者只检查结构，不运行选择评测，不给执行agent预期答案。

已安装的桌面转换器可能对重叠命令返回成功却不生成其中一个文件。原失败不能降为跳过或内部往返替代。validate_roundtrip按本机可执行文件身份持有跨进程转换锁，仍要求真实输出和全部语义检查。test_official_conversion_concurrency用独立I/O生产者复现重叠拒绝，并保留非零退出与缺输出拒绝；真实本机并发CLI检查另存仓库外，不替代无桌面程序环境的缺资源说明。此处只修外部进程调度，不改DNA计算。

开发者指定路线、改选检测窗口和宿主自主完成分别记录。真实材料例不等于陌生评测；局部PCR预测、来源记录、文件核验和湿实验结论也分别报告。报告浏览器及链接可用不替代真人理解试读。当前阶段及实际证据由Toolkit计划（原稿曾公开，现已移出当前树并完整私有备份；历史仍可见）拥有。

记录源码提交、包清单/哈希、解释器、依赖、平台、实际后端、输入条件与人工介入。同平台精确复现可参考Skill内requirements-tested；跨平台或可选后端不沿用未经验证的保证。精确模型token不可得时写未知。

```text
python -X utf8 -B tools/build_release.py snapgene-dna-design output/packages
python -X utf8 -B tools/validate_release_manifest.py output/packages/snapgene-dna-design-v1.0.4-redistributable.zip --package redistributable --version 1.0.4
python -X utf8 -B tools/check_redistributable.py output/packages/snapgene-dna-design-v1.0.4-redistributable.zip
```

包版本以Skill/VERSION为准，升级时替换命令中的版本。Git模式只收集经审核的Skill子树跟踪文件；新文件审核后入索引。非Git树用`--source-list reviewed-files.json`，已有发行包可用RELEASE-MANIFEST。禁止路径越界、符号链接和秘密入包。许可检查不等于法律授权证明。

解包到仓库外，从该目录用真实CLI和独立输入验证；不能借用外层tests/tools或源树fixture。安装验证绑定实际源码提交及清单，不能用另一版本成绩替代。[CI定义](../.github/workflows/test.yml)覆盖Ubuntu/Windows与Python3.10/3.11/3.12，结果必须对应所报提交。

## 性能与任务评测分开

`benchmarks/runtime.py`、`benchmarks/construction.py`测程序耗时；`benchmarks/plot_results.py`绘图另需Matplotlib。保留所有样本、种子、环境、重复数和指标边界；tracemalloc不是完整进程RSS。Trace的合成节点重建不代表复杂科学网络性能。速度不能替代目标正确性，也不能宣称用户成本下降。

分子契约补丁沿用`benchmarks/molecule_contract.py --skill-root <源码Skill根> --output <结果.json>`，同时比较原86d16f2和923b5bc；CPU中位不超过原基线1.5倍，Python分配峰值不超过2倍，不逐轮换基准。包内受影响连续链可用`tools/verify_molecule_residual_package.py --archive <包> --work <仓库外新目录> --report <结果.json>`核查：实际PCR、无裁剪、酶切、末端填补/连接及非零旋转，三档文件、注释、逐碱基值、引物表和检查范围一致。输入由脚本独立生成，404 bp填补连接和400 bp环化旋转的预期来自输入和反应事实；这是工程回归，不是宿主陌生任务评测。

正式任务评测按[评分规则](question-bank/scoring-v0.1.md)隔离材料与答案，冻结代码/包/规则，分别报告回归、保留评测、污染、校订输入、人工介入及全部重复运行。新对话或改文件名不构成陌生评测。本项目目前没有隔离保留评测成功率提高证据。

## 最近已核查的工程证据

统一分子契约v2的代码回归、冻结性能预算和仓库外包实测见[实施计划](development-plans/unified-molecule-contract.md)。旧版无法正确完成的记录链不做虚假速度比较；四组共同可用CPU操作用相同解释器、输入和三次重复比较，另记录真实Primer3子进程及完整CLI成本。不同验证范围、源码/包、原生投影与补充回读分别核查，不把合成回归当陌生任务成功率。

2026-10-03布局提交`d5cfa09`：本机Python3.12的980项中972通过、8跳过，独立包公开CLI及Trace三档回归通过，[六环境CI通过](https://github.com/zoehanke/snapgene-dna-design/actions/runs/37114726717)。这是此前代码的工程基线，不是本次文档整理新跑的结果。

旧937项、54/54覆盖和性能测量属于2026-09-22周期，原结果在[工程摘要](../results/engineering-audit-20260922/)及[档案](archive/README.md)。更晚修复不能直接继承旧覆盖成绩；旧完整后端结果也不能证明当前环境已启用所有后端。当前未关闭验证见[交接](development-plans/README.md)。
