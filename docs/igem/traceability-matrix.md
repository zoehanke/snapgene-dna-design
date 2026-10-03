# 主张追踪表

规则来源：[official-requirements](official-requirements.md)。用稳定维度编号连接一次事实，而不在每页重复规则全文。

| 规则/维度 | 项目要求 / Spec | 功能与实现 | 测试 | 数据/文档 | Wiki位置 / 状态 |
|---|---|---|---|---|---|
| O1 开源/文档/GitLab | core release contract | LICENSE、build_release、source selection | engineering_release | attribution、gitlab-migration | Availability / 部分满足，提交未完成 |
| O2 Village | 官方资格 | Tianjin#6404公开页面 | 无软件测试可代替 | official-requirements | Project / 已核实这一条件 |
| O3 标准URL | 官方文档入口 | `/tianjin/software` | 发布后人工链接核验 | software-wiki-draft | 全文 / 待发布 |
| O4/O5 提交制度和freeze | 当前规则 | 团队Dashboard动作 | 不适用 | submission-checklist | Submission / 需团队动作 |
| BS1 | core annotation/coordinate | input_resolution、construct_model、snapgene_io | primer_io、preparation_primer_locations、final_feature_restoration | standards-compatibility、roundtrip JSON | Interoperability / 已测有限范围 |
| BS2 | core correctness/gates | runtime_validate、runtime_gate、handlers/recipes | engineering_core、planning_restriction、property/mutation | validation、benchmark、公开JSON | Validation/Results / 程序已测，外部证据缺 |
| BS3 | general R&D goal | Recipe/Pipeline复用接口 | 公开demo/多类回归 | user-guide | Contribution / 外部采用未测 |
| BS4 | external integration boundary | Primer3、file I/O、local model adapters | real model/file CLI/roundtrip | integration、environment | Integration / Cas-OFFinder合成参考与模型已实跑，真实基因组外推未验证 |
| BS5 | task-first, readable report | SKILL、details/report/view、CLI errors | trace generalization、auxiliary | quick-start、troubleshooting、browser evidence | User Experience / 独立用户证据缺 |
| BS6 | maintainability/reproducibility | shared Handler writer、registry、tests/build | 全量suite、环境/包测试 | architecture、developer-guide、reproducibility | Design/Availability / 详见final report |
| Safety相关 | safety spec边界 | runtime/recorder/process/applicability/impact | engineering_trace、phase2/3、三档A/B | safety-module-evidence | Safety / 审查支持，不是安全裁决 |

工程新测试对应完整文件名：tests/test_engineering_core_audit.py、test_engineering_trace_audit.py、test_engineering_auxiliary_audit.py、test_engineering_release_audit.py；所有最终数字与遗留以 docs/final-remediation-report.md 为准。

## 直接证据入口

下面补齐可点击的具体文件，避免评审或接手者还需猜缩写对应哪个实现。

| 维度 | 需求与Spec | 实现 | 可执行检查 | 数据/方法 | 面向用户的说明与Wiki位置 |
|---|---|---|---|---|---|
| BS1 格式/注释 | [Core契约](../../specs/core-skill.md) | [snapgene_io](../../snapgene-dna-design/core/tools/snapgene_io.py)、[construct_model](../../snapgene-dna-design/core/models/construct_model.py) | [引物往返](../../tests/test_primer_io_repair.py)、[位置变换](../../tests/test_preparation_primer_locations.py) | [实际桌面结果](../../results/engineering-audit-20260922/snapgene-roundtrip.json) | [标准表](standards-compatibility.md)；Wiki Interoperability |
| BS2 正确性 | [Core验收](../../specs/core-skill.md) | [validate](../../snapgene-dna-design/core/runtime_validate.py)、[gate](../../snapgene-dna-design/core/runtime_gate.py) | [Core反例](../../tests/test_engineering_core_audit.py)、[交付边界](../../tests/test_engineering_core_boundaries.py) | [测量方法](../testing.md)、[当前汇总](../../results/engineering-audit-20260922/validation-summary.json) | [验证](../testing.md)；Wiki Validation/Results |
| BS3 实际用途 | [主目标](../../specs/core-skill.md) | [Recipes](../../snapgene-dna-design/core/recipes/__init__.py)、[Pipeline](../../snapgene-dna-design/core/handlers/composite_pipeline.py) | [实际制备Demo](../../snapgene-dna-design/scripts/demo_engineering_cycle.py) | [需补外部证据](external-evidence-needed.md) | [用户指南](../../snapgene-dna-design/docs/user-guide.md)；Wiki Contribution |
| BS4 集成 | [接口边界](../../specs/core-skill.md) | [Core API](../../snapgene-dna-design/core/__init__.py)、[Primer3](../../snapgene-dna-design/scripts/primer3_core_backend.py) | [可选后端真实测试](../../tests/test_v08_dev3.py)、[可执行API](../../snapgene-dna-design/examples/core_workflow.py) | [受测依赖](../../snapgene-dna-design/requirements-tested.txt) | [集成](../architecture.md)；Wiki Integration |
| BS5 可读使用 | [报告契约](../../specs/safety-module.md) | [report](../../snapgene-dna-design/evidence_trace/report.py)、[details](../../snapgene-dna-design/evidence_trace/details.py) | [报告独立案例](../../tests/test_trace_report_generalization.py) | [浏览器检查](../../results/engineering-audit-20260922/browser-check.json)、[截图](../../results/engineering-audit-20260922/trace-desktop.png) | [快速开始](../../snapgene-dna-design/docs/quick-start.md)；Wiki User Experience；独立用户证据仍缺 |
| BS6 维护/复现 | [开发规则](../../AGENTS.md) | [工具注册](../../snapgene-dna-design/core/tools/registry.py)、[构建](../../tools/build_release.py) | [包边界](../../tests/test_engineering_release_audit.py)、[旧预览契约](../../tests/test_legacy_preview_contract.py) | [环境与复现](../testing.md) | [开发](../developer-guide.md)、[扩展](../architecture.md)；Wiki Design/Availability |
| Safety审查支持 | [Safety Spec](../../specs/safety-module.md) | [runtime](../../snapgene-dna-design/evidence_trace/runtime.py)、[process](../../snapgene-dna-design/evidence_trace/process.py) | [来源/采集反例](../../tests/test_engineering_trace_audit.py)、[组织边界](../../tests/test_engineering_process_boundaries.py) | [证据强度与限制](safety-module-evidence.md) | Wiki Safety；外部效果未验证 |

程序结果、原始源码和官网规则各自支持不同主张。未上传的Wiki/仓库仍标待发布，不能从这些本地链接推断官方已接收。
