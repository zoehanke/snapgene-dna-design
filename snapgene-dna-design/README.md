# SnapGene DNA Design Skill

把自然语言需求和真实序列材料转成可检查的DNA设计、制备链、引物及GenBank/SnapGene文件。宿主AI选择路线，程序计算实际反应；文件检查不代表实验成功。

当前版本2.2.4。Recipe与原子操作共用实际产物、当前质量检查和正式交付；工作目录支持逐步继续，原材料及失败记录保留。AI选择路线，程序不把正确序列或局部PASS自动当作完整任务完成。

官方 GitLab CI 未执行。GitHub CI、本地序列模拟和文件核验分别提供限定范围的工程证据，不代称官方流水线通过或湿实验验证。

## 安装

交付保存实际中间体、注释源、当前订购表与说明；过期输入、用途或文件错配不能沿用旧检查。完整记录按需读取，默认摘要返回实际计算结果和未就绪原因。

Python 3.10+。复制完整Skill目录，使用同一个Python环境安装依赖并检查环境：

```text
python -m pip install -r requirements.txt
python -X utf8 -B scripts/check_env.py --json
```

引物设计需要真实Primer3程序，可由primer3-py安装包提供。桌面SnapGene、Cas-OFFinder和可选预测模型分别检查。[安装说明](docs/installation.md)

## 怎样使用

向已加载此Skill的AI提供目标、完整源文件、宿主背景、已有材料及必要约束。现成材料先判断复用；新构建从实际模板、最终引物与真实中间体推导。

执行AI从[SKILL.md](SKILL.md)开始，按任务读取[Recipe参考](references/recipes.md)。查看实际接口：

```text
python scripts/describe_tools.py
python scripts/inspect_plasmid.py source.gb --json
python scripts/run_recipe.py --recipe recipe_protein_tagging --params-json fixtures/synthetic/tagging_params.json --out-dir output/quick-start --json
```

最后一条产生带标签的合成教学component，不是完整表达质粒。[快速开始](docs/quick-start.md) · [用户指南](docs/user-guide.md) · [排障](docs/troubleshooting.md)

逐步设计用`scripts/run_step.py`，共同收尾用`scripts/finalize_workflow.py`。Python入口为`core.workflow.run_step`、`core.workflow_validation.validate_candidate`和`core.workflow_delivery.deliver_result`。[完整短例](examples/execution_workflow.py)。原Recipe/Pipeline CLI保留；sanity-only直接提升完整构建已关闭，需要真实执行凭据。

v2.2.0推荐同一工作目录连续调用。第一步JSON提供实际源材料、原要求和本步参数；后续JSON只需方法和参数，引用上一条返回的`product_ref`，不用抄序列或完整历史。多产物须明确选择。

```text
python scripts/describe_tools.py --search digest
python scripts/run_step.py --workspace work --input first-step.json
python scripts/run_step.py --workspace work --input next-step.json
python scripts/run_step.py --workspace work --status
python scripts/finalize_workflow.py --workspace work --candidate-ref "$final.products.0" --deliver --confirmed --out-dir delivery
```

`$final.products.0`替换为实际返回引用。Recipe与原子方法共用这条路径。失败保留已完成材料和具体检查，使用新step_id继续；新增源材料使用新代号。正式构建必需四个检查范围，不能删掉准备检查放行。只交付序列设计时显式用`--result-kind component`。Pipeline也区分component序列设计与construct完整准备，默认component，不把受检设计文件当作制备完成。

目标格式查询`describe_tools.py workflow_requirements`。原文放`original_request`，元件放可执行的`expected_components`/`forbidden_components`；未支持字段明确拒绝，`goal_coverage`列出实际检查范围。序列/编码差异用`compare_sequences`检查真实边界和蛋白差异，结果不建立实验功能。

已有20 nt guide用`check_grna`核对实际转录序列、靶标双链和PAM；换guide用`replace_grna_spacer`，只替换启动子和骨架之间的20 nt并记录旧注释处置。[签名与选择边界](references/recipes.md#existing-guide-cassettes)。默认生成计划中的反向PCR/DpnI/KLD路线并独立模拟；Tm、盐参数、完整引物及纯化建议随结果保存。wet_lab仍为NOT_PERFORMED，显式sequence_only不提供制备链。`validate_construct.py product.gb --template source.dna`区分继承与本次新增/改变的QC问题，保留ERR与退出码。GenBank导出、读取使用显式UTF-8。

## 看交付

- `candidate/`：计算候选；`intermediates/`：实际准备步骤产物。
- `annotated_sources/`和`primer_order_table.tsv`：源图、完整订购引物、真实结合段和坐标。
- `authoritative/`：该运行通过正式门限的`.gb/.dna/.fasta`及清单，仍限定于程序实际检查的范围。
- 直接使用返回的`present_files`主链接；`scripts/verify_delivery.py`核查最后选择是否属于未改变的正式交付，并返回该回执原有的检查范围与任务完成边界。`preparation_quality.json`记录制备引物质量；`verification_quality.json`单独记录最终QC订单、亲本PCR预测与测序覆盖假设。
- 补充测序引物传给QC Recipe的`sequencing_primers`，亲本材料传`background_templates`。[参数与范围](references/recipes.md)。复核后的科学说明放共同收尾的`report_notes`。订单、注释或文稿变更后重新finalize，再呈现当前回执的路径；文稿版本核查不等于自动证明其科学结论。
- Evidence Trace 0.3.4：可选的过程与依据记录，保持DNA主线旁路。泳道图的实线仅表示程序核验文件SHA-256相等，声明或结构关系保持虚线，不认证科学因果。[使用说明](references/evidence-trace.md)

直接调用scripts辅助模块时，在Skill目录把它加入Python导入路径：

```python
import sys
sys.path.insert(0, "scripts")
```

## 能力边界与许可

v2原子工具统一返回`products / analysis / checks`。Python用`result.only_product()`取得单个完整分子，用`result.products[index]`明确选择多个产物，用`result.analysis`读取计算结果。Pipeline用`$step`、`$step.products.0`和`$step.analysis.field`。旧字符串/dict接口及旧计划需迁移；参数查询仍用`scripts/describe_tools.py`。

检查分别报告序列模型、制备模型、文件及用户目标。要求制备时在任务中加入`validation_requirements`的`preparation_model`；只有序列编辑不能算已建立制备链。`.gb/.dna`保留Skill所需分子元数据，FASTA只保存序列。Native补充字段不等于桌面软件原生支持，正式交付仍检查实际native投影。

多轮设计使用上一轮真实产物；源注释冲突必须说明，不以删注释或改变目标制造通过。GenBank/native文件的序列、拓扑、特征和引物应对应；实验表现、全基因组特异性和科学结论另需相应证据。

当前验证包含开发回归，没有隔离陌生评测成功率提高结论。源代码许可见[LICENSE](LICENSE)，第三方素材与模型见[THIRD_PARTY_NOTICE](THIRD_PARTY_NOTICE.md)。本目录是运行使用入口，开发规则在项目根。
