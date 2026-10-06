# SnapGene DNA Design Skill

把自然语言需求和真实序列材料转成可检查的DNA设计、制备链、引物及GenBank/SnapGene文件。宿主AI选择路线，程序计算实际反应；文件检查不代表实验成功。

v2.0.2保留v2公共接口，修复实际工作流中的GenBank重复元数据、文献引用JSON传递、原引物注释回读及guide制备追溯。Pipeline导出后续步骤实际使用的DNA产物；inverse PCR使用共享Primer3设计器，无合格引物时明确拒绝。Recipe的`--json`失败结果包含错误、具体编码区和已有候选文件。

## 安装

v2.1.0新增共同单步、候选核查和交付入口。Recipe与原子工具可混合，默认返回简短摘要，完整记录按需读取。交付保存实际中间体、注释源、当前订购表与说明；过期输入、用途或文件错配会阻止相应范围通过。重叠搜索取消隐藏60 nt上限，完全吞并一个输入片段时明确拒绝。

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

## 看交付

- `candidate/`：计算候选；`intermediates/`：实际准备步骤产物。
- `annotated_sources/`和`primer_order_table.tsv`：源图、完整订购引物、真实结合段和坐标。
- `authoritative/`：该运行通过正式门限的`.gb/.dna/.fasta`及清单，仍限定于程序实际检查的范围。
- Evidence Trace：可选的过程与依据记录，保持DNA主线旁路。[使用说明](references/evidence-trace.md)

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
