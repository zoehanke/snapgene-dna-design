# 用户指南

## 先确定实际任务

告诉宿主目标、实际源文件、已拥有的实体材料以及边界/方向等约束。现有供体满足目标时可直接得出复用结论；需要制备和需要重新设计是不同任务。只有改变必要动作的未知信息才需澄清。

| 需求 | 入口 | 交付解释 |
|---|---|---|
| 检查现有材料 | inspect_plasmid.py | 文件层事实，不保证培养/表型 |
| 逐步设计或修订路线 | run_step.py --workspace | 续用实际product_ref，查看当前检查和保留的失败 |
| 标准制备与构建 | run_recipe.py | 配方计算、制备产物、引物及候选 |
| 多步组合 | run_pipeline.py | 每步引用真实中间记录；明确 output_step |
| 结构化任务 | run_construction_task.py | 任务、计划、执行、验证与正式交付 |
| 旧确定性意图规划 | plan_assembly.py | 有限语法/能力；不假装任意自然语言理解 |

Recipe 精确参数只在[配方参考](../references/recipes.md)维护；CLI 执行前用 `--help`。实际产物引用`$step.products.0`，分析读取`$step.analysis.field`；传整份记录保留注释。多产物明确选择。新增源材料代号不能与已有步骤重名。

Pipeline默认component，只交付注明范围的序列设计。需要完整制备时用`--result-kind construct`，四个范围必须通过。逐步工作用`finalize_workflow.py --workspace`收尾，默认同样要求完整构建；单纯序列设计显式选择component。

## 看结果

candidate/intermediate 表示计算或待核验产物；authoritative 表示通过该运行正式门限，仍只证明声明的计算范围。PCR 表应包含完整订购引物、实际结合核心、方向、源坐标与后续使用。不要从期望目标序列反推 PCR 一定成功。

核对产品序列、拓扑、目标元件、保留骨架特征和引物。失败保留错误与候选，不能删注释或改目标来通过。确实需要完整构建提升时，Recipe 使用 `--finalize --confirmed`，其中 confirmed 对应用户已有授权；组件和 QC 不因此变成完整构建。

## 看证据

先读任务、设计过程、文件与检查。点选择看本人留下的公开理由和具体依据；支持/反对/限制按对象区分。Trace 不判断 safe/unsafe，不恢复隐藏思维，也不保证捕获全部宿主行为。记录缺口影响追溯；真实缺文件、错误版本和失败检查影响交付，分别处理。

## 准确使用边界

Python 和格式往返证明的是序列文件及有限反应模型。预测评分不证明编辑效率；局部匹配不证明全基因组唯一；DNA 构建不证明功能复活或生态安全。具体失败看[排障](troubleshooting.md)。

## 一个完整例子怎样使用

先用公开工程示例确认本机安装与整条执行路线：

```text
python -X utf8 -B scripts/demo_engineering_cycle.py --out-dir output/my-first-demo
```

该例明确是合成材料和预设路线。它实际运行inverse PCR、生成制备记录、正式文件和Trace，再独立核对源与产物。不要把其中短CDS的GFP标签解释成经过荧光实验验证的基因。

打开结果时，先读任务和最终文件，再查完整引物与制备步骤。`.dna`供桌面SnapGene检查；`.gb`保留可读的序列与特征；FASTA只带序列。`trace/index.html`解释此次操作和检查。所用路径见脚本打印结果；不要从文件夹里随便找一个历史同名文件当本次产物。

自己的任务由宿主根据实际来源填写Recipe参数，签名见[配方参考](../references/recipes.md)。多步流程中，后一反应引用前一真实产物；有后置分析步骤时，用`output_step`明确交付哪个序列结果。更改目标或来源后使用新输出目录，保留前次记录。

## 出错时怎么判断

- 入口要求澄清：读具体缺少的参数，只补会改变这次设计的信息。
- 计算或验证失败：查看result.json中的对象、错误及candidate；此时不能将candidate改名当authoritative。
- Trace不完整：查看记录缺口，DNA结果和验证另行判断；后补说明保留其来源。
- 目录已有正式文件或预览交接包：换新输出目录；程序保留旧包，避免混入残留文件。

旧`run_design_agent.py`仅供兼容预览和规则维护。它的工作文件在`preview/`，交接包在`preview/delivery/`，不能成为正式构建或可订购证明。日常新设计使用Recipe、Pipeline或ConstructionTask。
