# 扩展指南

## 增加原子工具

在 core/tools 的对应领域实现函数，用 ToolSpec 描述参数和副作用类别，在 registry 注册。查 schema 只为验证输入，实际传递必须保留 SeqRecord 的注释。先定义独立预期与无效输入行为，再测直接 API 和 Pipeline 调用。

## 增加 Recipe / task_kind

Recipe 使用 RecipeResult，标清 complete_construct/component/verification，列真实制备输入。Handler 实现现有 plan/execute/recompute/validate_goal 契约；共享输入读取、变换后的记录和落地核验，不能重建裸序列把失败注释擦掉。变更 registry/schema/session 的实际引用。不要用目标序列代替 PCR 结果。

## 扩展 Trace

在应用边界观察，普通 Handler 不埋到处的 Trace 调用。新记录区分 observed/submitted/derived；运行结果才可产生 Validation。新增说明保留出处和时间；新字段不能默默改变旧事件含义。先测旧日志重建、失败隔离、主体引用、三档 DNA 一致性，再测人类详情。

分类可以扩展，事实不能虚构。未知记录进入清楚的记录缺口，不吞掉真实失败；报告不临时调用模型。引入服务、图数据库或新依赖之前，说明解决哪一个已复现问题。

## 原子工具注册示例

下面是一个用于理解接口的内存检查工具，不是已增加的新产品功能。先import现有工具完成默认注册，再注册自己的名称：

```python
from core.tools import get_tool
from core.tools.registry import ToolSpec, register_tool
from core.io.input_resolution import resolve_sequence_record

def count_ambiguous(template):
    record = resolve_sequence_record(template)
    return {"ambiguous_base_count": sum(b not in "ACGT" for b in str(record.seq).upper())}

register_tool(ToolSpec(
    name="example_count_ambiguous", callable=count_ambiguous, category="inspect",
    description="Count ambiguous bases without modifying the input record.",
    parameters_schema={"type": "object", "properties": {"template": {"type": "string"}},
                       "required": ["template"], "additionalProperties": False},
    result_type="object",
))
assert get_tool("example_count_ambiguous").execute(template="ACNT")["ambiguous_base_count"] == 1
```

`category`表达副作用，不能给网络调用伪填compute。`parameters_schema`约束参数形状，`result_type`和`sequence_output_key`告诉Pipeline是否存在可传递的DNA。上述工具只产出分析值，不能被选为最终DNA输出；加入真实产品时还须在默认初始化入口注册，并增加调用方/独立测试和必要文档。

## Handler实现清单

新增任务类型需要同时检查[construction-task-v1.json](../schemas/construction-task-v1.json)、`core/registry.py`的类型/语义校验与`core/handlers/__init__.py`的HANDLERS映射。实现`validate_contract`、`clarify`、`plan`、`recompute`、`validate_goal`；优先使用现有基类写出，不另建交付出口。计划必须包含真实变换后的features及作用范围；不能从产物倒推一份总能通过的“预期”。

扩展验收应包括：独立预期的有效任务；关键边界错误；源注释保留；保存后读回；不完整证据不能正式交付。只测一个固定教程答案不够。实验性方法仍按实际成熟度处理，不通过改标签进入正式交付。

## Schema兼容与修改范围

外部使用者可能保存过任务、计划和Trace日志。新增可选字段应有清楚的缺失语义；改变字段含义要显式版本化或要求重生成，不能默默把旧报告当新证据。图、报告和事件三者的兼容职责不同：旧事件保留，旧组织可能陈旧，报告可重建。

决定职责变化时更新对应spec；原因和被放弃方案追加history；具体代码和验证写阶段计划。不要把一次实现选择变成永远禁止替代方案的规则。
