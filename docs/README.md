# 开发文档入口

先按本次任务选文档，不通读整个docs。开发规则由[AGENTS](../AGENTS.md)管理，产品契约由spec管理。

| 要做什么 | 读什么 |
|---|---|
| 修改主设计、CLI、交付或接口 | [Core spec](../specs/core-skill.md)；需要定位模块时读[架构](architecture.md) |
| 修改Evidence Trace | [安全模块spec](../specs/safety-module.md)；修改报告时加读[阅读与界面规范](trace-report/design.md) |
| 环境、调试、扩展与提交 | [开发指南](developer-guide.md) |
| 测试、复现、打包或性能测量 | [测试与验收](testing.md)；任务评分另读[评分规则](question-bank/scoring-v0.1.md) |
| 接续工作或建立计划 | [当前状态与未关闭事项](development-plans/README.md) |
| 查设计为何改变 | [项目历史](history.md) |
| 处理比赛材料、题库或许可 | [iGEM入口](igem/README.md)、[题库入口](question-bank/README.md)、[许可归属](attribution.md) |

默认不读[历史档案](archive/README.md)。旧审查、已结束计划及旧手册用于追溯特定问题，不是当前规则或自动待办。历史测试数量也不是当前验证。

维护时只更新负责该内容的文档：spec管契约，架构管模块/数据/接口，开发指南管操作，testing管验证方法，计划索引管当前交接，history管重要原因。不要再为同一职责创建第二份“最新指南”。

三份旧案例资料暂保留原路径，供未提交的Reader Demo引用；它们不属于默认开发阅读入口。
