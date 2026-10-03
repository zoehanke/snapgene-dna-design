# 最小可复现快速开始

从仓库根目录运行，先按[安装](installation.md)配置依赖。下面输入已经随仓库提供，不需要自造 params.json。

```text
python -X utf8 -B scripts/inspect_plasmid.py fixtures/synthetic/pSynthetic-GFP.gb --json
python -X utf8 -B scripts/run_recipe.py --recipe recipe_protein_tagging --params-json fixtures/synthetic/tagging_params.json --out-dir output/quick-start --json
```

第一步读取教学用合成记录。GFP/AmpR 标签是测试标记，不能当荧光或抗性证据。第二步给短 CDS 增加 6xHis，产出 candidate 中的 GenBank、Native DNA、FASTA 和结果 JSON。

该结果是 **component**，不是已经制备的实体模板，也不是完整表达质粒；不加 `--finalize` 冒充正式质粒交付。这个小例子检验安装、计算和文件导出，不是完整克隆验证。

有现成载体/模板时，按[用户指南](user-guide.md)选择任务；完整构建参数见[Recipe](../references/recipes.md)。文件必须实际读回，核对序列和特征。

开发者若要逐阶段理解task、plan、execution和validation，可运行[Core API例子](../examples/core_workflow.py)，在代码中查看实际输入与逐阶段返回结果。

## Trace

需要完整正式文件与Trace的公开工程示例，可运行：

```text
python -X utf8 -B scripts/demo_engineering_cycle.py --out-dir output/demo-new
```

该脚本真实执行inverse PCR配方、交付四份文件、独立读回并生成 `trace/index.html`。路线和任务是预设合成例子，不是AI现场选择或湿实验结果；输出目录必须为空。

```text
python -X utf8 -B scripts/trace_design.py config
```

默认 Full。结果目录会有 `evidence-trace/index.html`。没有宿主提交整理时，页面是明确标注的事实视图，不是完整科学解释。改变模式是全局设置，影响之后的新采集；本说明不会替你改设置。独立脚本用[采集入口](../references/trace-capture.md)，完整整理用[Trace 使用说明](../references/evidence-trace.md)。
