# 扩展指南

## 增加原子工具

在 core/tools 的对应领域实现函数，用 ToolSpec 描述参数和副作用类别，在 registry 注册。查 schema 只为验证输入，实际传递必须保留 SeqRecord 的注释。先定义独立预期与无效输入行为，再测直接 API 和 Pipeline 调用。

## 增加 Recipe / task_kind

Recipe 使用 RecipeResult，标清 complete_construct/component/verification，列真实制备输入。Handler 实现现有 plan/execute/recompute/validate_goal 契约；共享输入读取、变换后的记录和落地核验，不能重建裸序列把失败注释擦掉。变更 registry/schema/session 的实际引用。不要用目标序列代替 PCR 结果。

## 扩展 Trace

在应用边界观察，普通 Handler 不埋到处的 Trace 调用。新记录区分 observed/submitted/derived；运行结果才可产生 Validation。新增说明保留出处和时间；新字段不能默默改变旧事件含义。先测旧日志重建、失败隔离、主体引用、三档 DNA 一致性，再测人类详情。

分类可以扩展，事实不能虚构。未知记录进入清楚的记录缺口，不吞掉真实失败；报告不临时调用模型。引入服务、图数据库或新依赖之前，说明解决哪一个已复现问题。
