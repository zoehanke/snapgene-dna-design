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
