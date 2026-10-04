# 开发指南

只读本次任务对应的spec、[当前交接](development-plans/README.md)及相关实现/调用方。模块定位看[架构](architecture.md)，测试和打包方法看[testing](testing.md)。旧手册不作为启动前置条件。

## 工作目录与环境

开发命令从项目外层执行；DNA CLI位于`snapgene-dna-design/scripts/`。Skill运行代码不能导入外层tools/tests。既有材料和本机产物不作为另一套源码。

```powershell
git status --short
git branch --show-current
python -m pip install -r snapgene-dna-design/requirements.txt
python -X utf8 -B snapgene-dna-design/scripts/check_env.py --json
```

先确认解释器及必要后端，后续命令用同一个Python。`requirements-tested.txt`记录特定Windows/Python3.12环境，不是跨平台锁文件；可选依赖另看requirements-optional。环境检查失败要处理或明确限制，不能靠改flag制造可用。文本文件和子进程流使用显式UTF-8。

## 一次修改怎样完成

v2开发使用`Molecule`与`ToolResult`，从公共工具接收完整产物，分析读取`.analysis`。参数查询使用`describe_tools.py`，不要查找旧`sequence_output_key`或把工具结果交给字符串/记录猜测器。旧Python调用及Pipeline字段引用需迁移；文件和报告边界才做wire转换。数据定义由[架构](architecture.md#统一分子契约目标架构)维护。

1. 确定用户要求和当前授权范围，保留无关工作区修改。
2. 读实际入口、相关调用方及测试；保留原输入、错误产物和命令，证明原行为为何错误。
3. 提炼通用修复，在独立有效/无效输入上建立预期；不得调用待测实现生成正确答案。
4. 改负责该契约的最小模块，同步调用方。检查实际保存文件，不能只看返回PASS。
5. 按[testing](testing.md)选择检查，保留失败、跳过、人工介入与范围。仅整理文档时检查内容/链接，不额外跑生物模拟。
6. 改长期契约时更新spec；重要原因/反馈追加history；实施证据写对应计划并更新交接索引。
7. 按授权commit/push指定开发分支，核对精确提交CI。main、公开发布、Wiki和表单操作不从开发授权自动推导。

开发与修复的持久原则以[AGENTS](../AGENTS.md)为准。新计划先处置相关未关闭事项，不从历史路线图自动开新阶段。

## 从哪里定位问题

| 症状 | 先检查 |
|---|---|
| 产物和用户要求不同 | 原始要求、Recipe目标或task、goal validation、正式交付证据 |
| 实际PCR/酶切/组装不成立 | 完整模板、完整引物、反应工具和真实中间体，不用期望产物替代反应 |
| 注释或引物坐标丢失 | SeqRecord.features、区间变换、写出和GB/native读回 |
| 无效结果仍交付或覆盖旧文件 | runtime_gate、对应版本回执、每次尝试的临时目录和原子提升 |
| Trace自说自话或打开详情看不懂 | 原记录、design_process/report_plan、引用范围，再到projection/process/report/render |
| Windows或中文路径失败 | 实际sys.executable、路径解析、UTF-8和真实子进程stderr |

追踪顺序是CLI → Recipe/runtime → 工具 → 文件 → 验证 → gate。断点使用同一输入、参数和解释器。示例反例：[源引物坐标](../tests/test_preparation_primer_locations.py)、[交付边界](../tests/test_engineering_core_boundaries.py)。

## 扩展与维护

工具、Recipe、Handler、Schema的修改位置和契约见[架构](architecture.md#外部依赖与扩展位置)。不为当前单机流程先造服务、数据库或验证引擎；新增抽象须解决已证明的问题。

项目没有全仓库mypy/ruff门限，也没有前端构建器。Python语法/导入、JS语法和真实浏览器分别核对，不互相冒充。安装Skill是完整目录交付；ZIP构建不是已经发布，源树通过也不证明已安装包通过。

知识讲解只在对应授权下继续。原14节教学交接尚未完整完成，见[未关闭事项](development-plans/README.md)；不把本指南或旧手册的存在当成已经教学。
