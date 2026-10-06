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
python -X utf8 -B tools/smoke_core.py
python -X utf8 -B tools/property_tests.py --quick --out-dir output/property
python -X utf8 -B tools/coverage_gate.py --out-dir output/coverage
```

bash使用`export SNAPGENE_RUN_PRIMER3=1`。真实Primer3跳过会使正式runner失败；`--allow-primer3-skip`仅用于明确的非发布诊断。可选模型、Cas-OFFinder、参考基因组或桌面程序另需实际资源，flag不能代替后端。

mutation、rich fixtures和scenario分别由`tools/mutation_tests.py`、`tools/validate_rich_fixtures.py`、`tools/run_scenario_suite.py`提供，参数以`--help`为准。场景需按executed/partial/blocked记录，不能将总场景数说成构建成功数。

Coverage读取真实模块的行/分支及套件退出码，目标和阈值以[代码](../tools/coverage_gate.py)为准。插桩不能减少实际执行场景。Mutation先证明原版检查通过；失败捕获率不等于实验可靠率。报告中分别写失败、skip、不可用和未核查。

## 真正检查最终结果

从原材料、要求和实际操作独立核验，不能采信宿主自报PASS或仅对照参考序列。允许不同正确路线与环形起点。多轮必须使用上轮真实产物；检查制备、接口、读框、注释、文件和结论。

Core API例子：`python -X utf8 -B snapgene-dna-design/examples/core_workflow.py --out-dir output/api-example`，属于序列文件编辑。实际准备链演示：`python -X utf8 -B snapgene-dna-design/scripts/demo_engineering_cycle.py --out-dir output/demo`，属于预设方案回归，两者都不是宿主陌生任务或湿实验。

单步实际执行与共同交付短例：`python -X utf8 -B snapgene-dna-design/examples/execution_workflow.py --out-dir output/closure-example`。独立闭环反例由`test_execution_closure.py`保留，检查原要求、来源、真正反应、文件及订单用途；新宿主自然任务仍需另一份实际会话证据。实际结果由[当前闭环计划](development-plans/actual-execution-closure.md)管理，不在此复制动态测试数量。

Trace记录完整不等于宿主全流程覆盖或科学结论成立。浏览器动作正常不等于人理解正常。桌面SnapGene格式实测、操作者审查、实验表型和全基因组特异性分别提供证据。

本机6.0.2曾在两个转换任务同时运行时不生成部分GenBank输出，同输入串行复测通过；并发因果尚未受控证实。桌面CLI转换目前串行运行，不宣称并发支持。保留每轮失败及原退出码；某一步原样复测通过不能改写此前整套命令的失败报告。[当前闭环计划](development-plans/actual-execution-closure.md)保留本次实际记录。

## 环境与独立包

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
