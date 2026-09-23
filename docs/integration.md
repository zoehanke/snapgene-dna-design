# 实际集成

| 接口 | 输入/输出 | 实际机制 | 限制/失败 |
|---|---|---|---|
| 宿主 Skill | 请求→CLI 参数/JSON→结果 | SKILL.md + scripts；agents/openai.yaml 为元数据 | 不接管闭源宿主，不保证全部检索可见 |
| Python API | ConstructionTask→plan/execute/validate/finalize | core/__init__.py 导出 | 不是 HTTP 服务 |
| Pipeline 工具 | JSON 参数/SeqRecord→结构化结果 | registry ToolSpec | 不同工具有明确副作用类别 |
| Biopython | FASTA/GB/EMBL/SeqRecord | parser、feature extraction、序列工具 | 格式可读不等于注释正确 |
| Native SnapGene | .dna 与 .gb 双向 | sgffp、snapgene_reader、snapgene_io | Native 解析验证与桌面软件实测分开 |
| Primer3 | Boulder-IO→cores/结构指标 | primer3_core 子进程 | 实际后端缺失不可冒充预测成功 |
| Cas-OFFinder | 参考基因组/guide→命中 | 外部程序与OpenCL | 官方2.4.1/3.0.0b3在本机合成参考运行通过；真实全基因组验证缺证据 |
| Azimuth / DeepCpf1 | 合适上下文→预测分数 | 本地受信任模型与可选依赖 | 训练域外适用性和实验效果未验证 |
| NCBI | 关键词/accession→检索/记录 | urllib eUtils，超时和offline状态 | 关键词连通性不等于所有检索可用 |
| Addgene | 标识→官方链接 | 链接辅助 | 不是完整库存/序列API |

外部序列上传必须遵循 [privacy-and-consent](../references/privacy-and-consent.md)。项目不会因“本地Skill”自动保证宿主不上传数据。外部模型 pickle 仅适用于可信安装内容，不能接收任意下载的模型并宣称安全。

低层脚本还不是独立 pip 包；需要直接调其 helper 时从仓库根目录显式加入 scripts：

```python
import sys
sys.path.insert(0, "scripts")
from primer3_core_backend import probe_primer3_core
print(probe_primer3_core())
```

支持版本、实测环境见[复现](reproducibility.md)，格式测试见[兼容表](igem/standards-compatibility.md)。

## 实际Python接口

API是其他程序调用本项目的函数接口。`core`没有常驻服务；每次调用传入字典，获得返回值或异常。精确签名见源码，下面列出接手时最重要的约定：

| 调用 | 返回 | 副作用 / 错误 |
|---|---|---|
| `validate_construction_task(task, base_dir=None)` | 补齐计算字段的任务字典 | 读取并绑定源文件；无效任务抛`TaskValidationError` |
| `plan(task, base_dir=None)` | **二元组**`(validated_task, plan)` | 不可只取plan后继续传原始未解析task；未知task_kind拒绝 |
| `execute(task, plan, out_dir)` | execution字典 | 写intermediate文件；检测任务/计划变更 |
| `validate(task, plan, execution)` | 三层结果字典 | 重新读取文件；检查失败记录在结果中，不等于抛异常 |
| `finalize(task, plan, execution, validation, out_dir)` | directory、files、manifest_sha256 | 正式文件原子交付；拒绝时抛`GateRejected`，不能覆盖已有authoritative |

可直接运行的完整API例子是 [examples/core_workflow.py](../examples/core_workflow.py)：

```text
python -X utf8 -B examples/core_workflow.py --out-dir output/api-example
```

它读取公开2500bp合成记录，明确修改第100个碱基，保留6个源特征，逐阶段保存JSON并独立读回核对。此例是序列文件编辑；实际PCR制备另运行 `scripts/demo_engineering_cycle.py`。两种例子不能交换解释。

```python
from core import plan, execute, validate, finalize
task, planned = plan(task)
execution = execute(task, planned, "output/work")
validation = validate(task, planned, execution)
delivery = finalize(task, planned, execution, validation, "output/delivery")
```

此片段中的`task`由完整例子提供。调用方应读取`validation["errors"]`，不能自行填写成功字段；修改任务后重做计划与验证。`CoreError`的`error_code`提供机器分流依据，`message`解释原因；CLI会将其转换为结构化错误与非零退出码。

## Recipe、工具和Trace接口如何分开

- `core.recipes`的函数返回[RecipeResult](../core/recipes/contract.py)。`result_kind`区分construct/component/primers/verification/protocol；`completeness`区分完整构建、组件和QC。`to_dict()`用于JSON交付，`details`保存配方特有结果，不允许覆盖通用字段。
- `core.tools.get_tool(name)`返回[ToolSpec](../core/tools/registry.py)。调用`tool.execute(**params)`会验证参数、应用别名、绑定函数签名，随后调用真实工具。工具返回值可能是SeqRecord、字典或分析值，不能都当DNA。
- `traced_run(route)`用于应用入口；`observe(stage, fn, ...)`观察一次实际调用。直接调用裸Core API不会自动获得宿主的公开理由或完整Trace，完整用法见[采集说明](../references/trace-capture.md)。
- [Recorder](../evidence_trace/recorder.py)负责追加；`organize(recorder, packet)`接收宿主/研究者整理；`Recorder.render()`重建机器图与报告。`ingest()`不能把宿主提交的字典冒充程序Validation。

## 外部程序、网络与重试

Primer3使用本地可执行程序和明确输入，不通过远程模型计算序列。Cas-OFFinder需另备实际参考序列和OpenCL运行环境。SnapGene桌面转换需合法安装；明确要求官方验证时，缺少程序会失败，不能降为“已验证”。

NCBI关键词/accession检索与上传完整DNA是不同操作。网络失败、伪GenBank或accession不匹配不得改记成功；长BLAST查询当前明确拒绝，尚非完整异步BLAST服务。网络同意说明在[隐私与同意](../references/privacy-and-consent.md)。重跑前检查错误和输出目录，使用新目录保留前次产物与证据。
