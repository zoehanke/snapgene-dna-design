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
