# 开发指南

先读 AGENTS、对应 spec、当前计划和 history。检查 Git 状态，保留他人修改。复现用户问题后建立最小独立正反例，再改生产代码；同一示例变绿不是完成标准。

## 常用命令

从项目外层运行；DNA CLI位于`snapgene-dna-design/scripts/`，开发工具位于`tools/`。

```text
python -X utf8 -B -m unittest discover -s tests
python -X utf8 -B tools/run_test_suite.py
python -X utf8 -B tools/property_tests.py --quick --out-dir output/property
python -X utf8 -B tools/run_scenario_suite.py --out-dir output/scenarios
python -X utf8 -B benchmarks/runtime.py output/benchmarks.json
python -X utf8 -B tools/build_release.py snapgene-dna-design output/packages
```

发布 runner 要求真实 Primer3 测试启用。PowerShell：`$env:SNAPGENE_RUN_PRIMER3='1'`；bash：`export SNAPGENE_RUN_PRIMER3=1`。其他真实后端另需各自资源，不伪造 flag 代替程序。

项目没有配置全仓库 mypy/ruff 门限，也没有 JavaScript 构建器。Python AST/实际导入、`node --check snapgene-dna-design/evidence_trace/view.js` 和实际浏览器分别检查语法与交互，不把语法检查写成类型检查或 UX 验收。

## 调试

从用户入口向下跟踪：CLI→runtime/Recipe→工具→保存文件→验证→gate。同时读输入和输出，不只看返回布尔值。Trace 可提供日志，但它本身也要测失败；正常模式不能拖死已正确的 DNA 操作。

变更契约要同步 spec；说明原因写 history；执行证据写计划/结果。开发结束按授权提交并推送指定开发分支，检查该提交的CI；不自动合并或推送main。测试资料、密钥和临时环境不能入包。

## 技术栈及实际职责

| 技术 | 在本项目中做什么 | 对应位置 / 缺失影响 |
|---|---|---|
| Python与标准库 | CLI、文件、JSON、子进程、测试 | scripts/core/evidence_trace；主运行环境 |
| Biopython | 序列、SeqRecord、Feature、遗传密码表和酶信息 | core/tools/models；失去实际生物序列处理基础 |
| jsonschema | 检查结构和参数类型 | core/task、ToolSpec；不能替代生物学检查 |
| primer3-py / Primer3 | 提供实际Primer3程序及引物热力学/结构计算 | scripts/primer3_core_backend；缺失时相应设计不可用 |
| sgffp / snapgene_reader | Native文件写读与相应元数据 | snapgene_io/sg_common；不等于桌面程序验收 |
| NumPy及可选ML库 | 数值依赖与预测模型 | NumPy也可由核心依赖引入；Pandas/sklearn/Torch/h5py用于可选评分 |
| 原生HTML/CSS/JS | 离线报告与交互 | evidence_trace/render.py、view.css、view.js；无React或前端打包服务 |
| unittest / coverage | 检查行为、量化代码是否执行 | tests、coverage_gate；通过次数不证明生物学通用正确 |

requirements声明安装依赖，pip负责解析和安装；虚拟环境隔离依赖。import把Python模块载入当前进程，不是下载或启动服务。程序自己的计算规则在Core与scripts，Biopython提供数据结构/基础算法，宿主模型负责需求和选择，三者不能混称“AI自动完成”。

## 一次改动怎样落实

以“某次PCR后的引物注释位置错了”为例：

1. 保留完整模板、完整引物、参数、错误产物与调用命令；先明确0-based/1-based约定。
2. 从run_recipe或run_pipeline进入对应工具，核对返回的实际PCR片段与SeqRecord.features，定位错误发生在计算、坐标迁移还是文件导出。
3. 写一个独立正例和一个能捕获错误的负例，例如跨原点完整结合区与线性产品被切断的结合区；不能只复用实现本身算预期。
4. 修负责该行为的最小模块，检查调用方是否仍传完整记录。对源码和导出的.gb/.dna分别验证。
5. 若修改了Trace边界，比较三档产物并注入正常模式采集失败；若仅修改文案，不运行整套生物模拟。
6. 记录结果、真实skip和限制，再更新相关spec/计划；最后按授权提交。操作系统/桌面程序相关结果必须在实际环境验证。

实际反例可读 [test_preparation_primer_locations.py](../../../tests/test_preparation_primer_locations.py)；交付失败边界可读 [test_engineering_core_boundaries.py](../../../tests/test_engineering_core_boundaries.py)。

## 测试选择与失败排查

```text
python -X utf8 -B -m unittest discover -s tests -p test_legacy_preview_contract.py -v
python -X utf8 -B tools/coverage_gate.py --out-dir output/coverage
```

先跑改动涉及的测试，再跑必要整套检查。覆盖工具会保留各步stdout/stderr、coverage.data和JSON；先看失败测试与对象，再看百分比。插桩期间也必须执行同样的场景，不能因检测到COVERAGE_PROCESS_START而提前return。通过针对性测试不意味着整套门槛已通过。

需要断点时，在CLI调用主函数前或发生错误的工具函数设置断点，以同一命令和参数启动；记录`sys.executable`确认调试器没有切换到另一套Python。无需先掌握所有文件，优先跟踪一个输入到一个真实产物。

CI定义在[.github/workflows/test.yml](../../../.github/workflows/test.yml)，矩阵为Ubuntu/Windows与Python 3.10/3.11/3.12。本轮将其改为明确启用真实Primer3并调用正式runner，另执行环境检查，避免核心后端测试默认skip。配置变更不等于云端执行通过；以对应提交的真实CI结果为准。

## 构建、安装和发布不同

本项目没有编译成服务器的“部署”。build_release选择受控文件并打ZIP；安装Skill是把完整目录交给宿主加载；公开发布还需要授权、许可和验证。新增受控文件先暂存，否则默认打包不会纳入未跟踪内容。解包后从仓库外运行，才能发现偷偷依赖开发目录或外部fixture的问题。

Git推送遵循当前任务授权；公开发布、iGEM发布和表单提交需单独授权。正式迁移见[迁移说明](../../igem/gitlab-migration.md)。

## 知识交接顺序

工程闭合后按用户要求分章讲解，不把下面的目录算作已经教学：①项目与用户流程；②10–20个关键文件；③技术栈；④模块与依赖；⑤启动执行；⑥Core完整流程；⑦Trace完整流程；⑧数据结构；⑨本项目实际用到的编程概念；⑩开发命令与调试；⑪故障地图；⑫技术债；⑬必须/应该/暂可黑箱的知识；⑭整体模型。每章连接实际文件、输入输出和小段代码，留自然停顿。
