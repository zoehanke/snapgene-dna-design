# 仓库地图

这里是单一开发源，使用 Git 分支与标签记录版本；输出目录和发行包不作为另一套开发源。

| 区域 | 运行职责 | 修改注意 |
|---|---|---|
| SKILL.md / agents/openai.yaml | 宿主操作指导和元数据 | 提示会影响实际设计；报告任务后置 |
| core/ | task/runtime、Handler、Recipe、原子工具和记录模型 | DNA 正确性主线 |
| evidence_trace/ | 采集、日志、版本、组织、报告 | 不更改主线参数/产物 |
| scripts/ | 用户入口、外部后端、测试与发布命令 | 不同旧接口坐标有差异 |
| planning/、agent/、design/、rules/ | 历史规划/会话/规则与部分当前 Pipeline 接口 | 不按目录名判断弃用 |
| schemas/ | JSON 契约 | 改动需同步调用方和测试 |
| fixtures/、tests/data/ | 合成与外部回归材料 | parser fixture 不一定是有效生物设计；许可不同 |
| tests/ | 单元、接口、回归与部分真实后端测试 | skip 与通过分开 |
| benchmarks/、results/ | 可重复性能方法与公开摘要 | 不提交用户 DNA/秘密 |
| examples/ | 可直接运行的开发接口例子 | 解释作用范围，与实际制备demo分开 |
| references/ | 精确参数与方法说明 | CLI 签名仍以源码为准 |
| specs/、docs/ | 当前契约、原因、计划和实证 | 当前 spec 与历史审计分开 |
| third_party/ | Azimuth 转换代码及模型、DeepCpf1 权重和许可证 | 不随意编辑/替换，保留来源和哈希 |
| output/、build/、reports/ | 本地生成和诊断，Git 忽略 | 不当成源代码，不随便删除有用证据 |
| dist/ | 包配置或历史发行说明 | ZIP 不自动代表当前源码 |

## 优先读的 18 个位置

SKILL.md；两个 spec；core/__init__.py；core/task.py；core/session.py；core/runtime_plan.py；core/runtime_execute.py；core/runtime_validate.py；core/runtime_gate.py；core/handlers/base.py；core/tools/registry.py；core/models/construct_model.py；scripts/run_recipe.py；evidence_trace/runtime.py；evidence_trace/recorder.py；evidence_trace/process.py；evidence_trace/report.py。

根据实际函数调用再进入 Recipe、Handler 和工具。主入口之外还有许多小 CLI，不需要初学者先记住全部文件。清点快照在 results/engineering-audit-20260922/discovery.json；它记录覆盖范围，不证明每个分支正确。
