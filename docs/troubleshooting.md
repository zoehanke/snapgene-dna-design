# 排障

| 症状 | 先看哪里 | 下一步 |
|---|---|---|
| ImportError / 环境失败 | check_env.py、requirements.txt | 在独立环境安装；核对所用 Python |
| Primer3 不可用 | environment 的 primer3_core / PRIMER3_CORE | 使用真实可执行程序；不把启发式当 Primer3 |
| 源文件无法读取 | 文件格式、input_resolution、sg_common | 检查存在、格式和记录数；不把多条记录静默当一条 |
| 验证失败但序列看似相同 | runtime_validate、result.json | 查看错误对象/范围、特征和元件，而非只比 hash |
| 正式交付被拒绝 | runtime_gate、任务授权/假设/证据 | 修真实输入或目标缺口；不要手写 passed |
| 原有 CDS 注释报错 | 原文件与产物 feature.extract | 分清原注释错误、部分域和真实 ORF 破坏；保留证据 |
| Trace 不完整 | events.jsonl、TRACE-MANIFEST.json | 正常模式 DNA 可继续；补录必须声明发生时间和来源 |
| 文件存在却没有生成关联 | handoff 与调用前后文件记录 | 以后写入前启用观察；不补造旧历史 |
| 图或 Markdown 与当前任务不一致 | organization_status / basis | 新事实需要新组织；不覆盖历史 |
| 报告来源链接无效 | 原 locator、原文件是否移动 | 修来源定位；离线正文和可读详情不需要联网 |
| 发布包出现额外文件 | source-list / Git tracked files | 只选择审核过的源文件；检查 RELEASE-MANIFEST |
| Cas-OFFinder 缺失 | 外部程序、OpenCL 与参考基因组 | 标 unavailable，不能写“无脱靶” |

报告问题时附命令、Python/依赖版本、完整错误、最小可公开输入和预期。保留原始私有文件在本机，公开 bug 优先使用合成反例。

转换默认保护已有文件；明确要重写自己的目标时使用 `convert.py --allow-overwrite`。多源同名输出冲突仍需分别命名，不能用覆盖选项绕过。

## 按层定位，不反复改提示词碰运气

| 层 | 常见错误/证据 | 检查函数与文件 | 修复方向 |
|---|---|---|---|
| 输入契约 | 缺字段、选择未解决、来源hash变化 | core/task.py、registry.py、task.json | 改正真实任务或重新绑定来源；不是手写新hash掩盖变化 |
| 计划与执行 | 未注册类型、旧计划、执行失败 | runtime_plan/execute、对应Handler、plan/execution JSON | 使用支持的类型，更新任务后重生成计划 |
| 保存文件检查 | 序列/拓扑/注释不一致、元件缺失 | runtime_validate、feature_ops、实际GB/DNA | 从源与每次变换定位，保留失败文件 |
| 正式交付 | GATE_HASH_CHAIN_BROKEN、GATE_GUARDRAILS_FAILED、GATE_OFFICIAL_ROUNDTRIP_FAILED | runtime_gate、validation与DELIVERY-MANIFEST | 修凭据/实际文件/所要求外部程序；不修改passed字段 |
| Windows目录提升 | WinError 5 / 文件访问被拒绝 | 输出目录占用、权限、原异常与candidate | 关闭占用者/确认权限后重试交付；保留candidate，不用复制覆盖绕过原子提升 |
| 旧预览 | SOURCE_HASH_MISMATCH、SOURCE_UNREADABLE、PREVIEW_VERIFICATION_REQUIRED | agent/session、orchestrator、preview工作区 | 恢复正确输入或重跑实际execute/verify；失败后不能复用旧候选 |
| 记录/组织 | 事件损坏、非法引用、陈旧basis | evidence_trace/recorder、process、events.jsonl | 保留原日志，补正来源或追加新组织 |
| 报告 | 数据完整但正文/详情错位 | report.py、details.py、view.js/css | 先看机器结果中的主体和关联，再判断是否为报告映射问题 |
| 测试基础设施 | 插桩比普通运行慢、外部桌面失败 | coverage目录每步stdout/stderr、coverage.data | 区分测试失败、环境失败与覆盖不足；不要修改场景集求过关 |

最有用的最小问题报告是：具体命令、实际输入版本、期望的序列/特征变化、哪份文件不符、完整错误。报“测试都通过但不好用”时还需提供实际用户目标，才能检查是否测错了问题。
