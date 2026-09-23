# 证据清单

| 证据 | 用途/功能 | 来源与生成 | 可复现 | 评审/Wiki | 状态 |
|---|---|---|---|---|---|
| 架构/数据流图 | 解释主线与旁路 | docs/architecture.md、data-flow.md及results/engineering-audit-20260922/architecture.svg，对照实际模块 | 是，Mermaid与SVG | BS6 / Design | READY；发布由团队完成 |
| Core正反例 | 证明错误不正式交付、注释保留 | tests/test_engineering_core_audit.py | 是，合成输入 | BS2 / Validation | 已运行，见最终报告 |
| Auxiliary正反例 | 证明不丢碱基、拒绝不改状态 | tests/test_engineering_auxiliary_audit.py | 是 | BS2/BS5 | 已运行 |
| Trace反例 | 版本/脱敏/文件归属 | tests/test_engineering_trace_audit.py、test_trace_report_generalization.py | 是 | BS2 / Safety | 已运行 |
| 发布边界 | 源文件受控、失败exit | test_engineering_release_audit.py | 是 | BS6 / Reproducibility | 已运行 |
| 原/新性能样本与图 | 观察运行成本 | benchmarks/、results/engineering-audit-20260922 | 是，限机器环境 | BS2/BS6 / Results | READY |
| 90场景分布 | 分开执行/partial/blocked | scenario-summary.json及本地原报告 | 是，部分本地外部fixtures受限 | BS2 | 不作为湿实验成功率 |
| 桌面自动往返 | 外部格式互操作 | snapgene-roundtrip.json | 需合法SnapGene环境 | BS1/BS4 | core-compatible；strict未通过 |
| 实际inverse-PCR演示 | 完整工具链与Trace | demo_engineering_cycle.py | 是，公开合成fixture | BS2/BS4/BS5 | 本机执行，预设场景 |
| 可执行Core API例子 | 供开发者逐阶段读实际JSON | examples/core_workflow.py | 是，2500bp公开输入、6个特征 | BS4/BS6 / Integration | 实际执行；文件编辑模型 |
| 实际报告与构建图 | 解释交付结果 | results/engineering-audit-20260922 的SVG、桌面/窄窗截图、browser-check.json | 是，原报告可重建 | BS2/BS5 / Workflow | 实际渲染；非真人理解证明 |
| 真实可选后端 | 验证接口、方向和参考输出 | 官方Cas-OFFinder v2/v3、Azimuth/DeepCpf1，27项无skip | 需依赖和OpenCL | BS2/BS4 | 合成参考已测，非任意基因组 |
| 新用户评价 | 其他团队独立完成任务 | 原始任务、操作记录与反馈 | 需外部人员 | BS3/BS5 | MISSING |
| 湿实验/专家复核 | 生物效果与边界 | 输入版本绑定的实验/独立意见 | 需人员与材料 | BS2/Safety | MISSING |
| 正式视频/Wiki截图 | 答辩与展示 | 团队录制与发布 | 需团队执行 | Presentation/Wiki | MISSING |
| 官方仓库/表单回执 | 资格与提交 | iGEM Dashboard | 需账户动作 | O1/O5 | MISSING |

本地诊断截图和日志不自动作为公开资料；选择可公开合成例子并检查来源/许可。数据可重复不等于外部有效性已验证。
