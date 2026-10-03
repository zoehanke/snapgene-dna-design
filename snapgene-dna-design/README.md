# SnapGene DNA Design Skill

把自然语言需求和真实序列材料转成可检查的DNA设计、制备链、引物及GenBank/SnapGene文件。宿主AI选择路线，程序计算实际反应；文件检查不代表实验成功。

## 安装

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

多轮设计使用上一轮真实产物；源注释冲突必须说明，不以删注释或改变目标制造通过。GenBank/native文件的序列、拓扑、特征和引物应对应；实验表现、全基因组特异性和科学结论另需相应证据。

当前验证包含开发回归，没有隔离陌生评测成功率提高结论。源代码许可见[LICENSE](LICENSE)，第三方素材与模型见[THIRD_PARTY_NOTICE](THIRD_PARTY_NOTICE.md)。本目录是运行使用入口，开发规则在项目根。
