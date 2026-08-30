# SnapGene DNA Design v0.9.0 生物学技术审计报告

## 1. 审计对象与结论

- 版本：`0.9.0`（RC1 审计历史见升级日志；本文件当前指向正式版）
- 源码：`D:\codex_project\snapgene-dna-design-v0.9.0-work`
- 本机 SnapGene：`D:\SnapGene\SnapGene.exe`
- 性质：开发快照；本轮热修后达到 RC 验收候选，不自动标记正式版。

本轮没有把“测试通过”写成“湿实验一定成功”。审计确认的是：坐标、拓扑、
序列变换、构建失败契约、来源和规则安全边界按声明执行；真实构建仍需结合
宿主、菌株、质粒背景、试剂和实验结果人工确认。

## 2. 本轮修复的高优先级问题

1. 经验规则以前只明确拒绝 `check`，现在递归拒绝顶层、嵌套对象和列表中的
   `check`/`eval`；规则不能携带 Python 可执行表达式。
2. `schemas/experience-rule-v1.json` 改为 `urn:` 标识、严格声明式条件和
   顶层未知字段拒绝；当前规则、预存规则、待确认候选统一校验。
3. `block` 动作以前可以被 acknowledge 参数绕过；现在 `block` 是硬阻断，
   不写出被阻断的 PCR 产物并返回非零退出码。确认参数仅适用于 warn/ask。

## 3. 生物学语义审查范围

- **坐标与拓扑**：0-based 半开内部坐标、1-based CLI 显示、负链参考轴映射、
  线性末端不伪造 wrap、环状跨原点显式 segments、`end=n` 边界。
- **构建算法**：Gibson/overlap、Golden Gate、digest-ligate、In-Fusion、
  Gateway、TA/TOPO 的输入约束、overlap/末端兼容性、闭环 junction 和
  feature 迁移；不可执行输入不写最终构建物。
- **引物与 PCR**：Primer3 core 优先、回退明确标注、binding/tail 分离、Tm/GC/
  发夹/二聚体检查、验证引物需用户明确请求、菌落 PCR 超阈值需确认。
- **CRISPR**：核酸酶注册表、PAM 扫描、正负链、候选覆盖统计、Cas-OFFinder
  参考基因组绑定、on-target 模型适用性和 unavailable 语义；未完成全基因组
  搜索不得声称低脱靶。
- **来源与隐私**：协议、模型、元件和在线查询记录来源、版本、适用性与哈希；
  用户序列上传默认拒绝，短序列/序列样文本不会在未经授权时发往网络。

## 4. 实测证据

| 门禁/检查 | 实测结果 |
|---|---|
| 经验规则专项 | 22/22 OK |
| 源码全量 unittest（默认） | 449 OK，13 skip，0 failure/error |
| academic ZIP 解压测试 | 449 OK，13 skip，0 failure/error |
| redistributable ZIP 解压测试 | 421 OK，15 skip，0 failure/error |
| coverage | `gate_ok=true`、`suites_ok=true`；核心行/分支阈值全部通过 |
| mutation | 12/12 killed，100% |
| property | Gibson/In-Fusion/Golden Gate/digest-ligate 各 1000 成功+300 失败；Gateway/TA 各 500 成功+200 失败，全部 PASS |
| 场景套件 | 90/90 PASS |
| 规则文件 Schema | 4 条当前/预存/待确认规则，0 个错误 |
| 真实外部后端 | rc1 全开关 449 tests OK；真实 primer3_core 2.6.1、Cas-OFFinder v2/v3、Azimuth/DeepCpf1、在线 NCBI 均执行 |
| ZIP/manifest/许可 | 两包 `testzip=None`；manifest 通过；academic 10/10 受限哈希；redis 0 受限哈希；无 pyc/cache |

## 5. SnapGene 官方核验的诚实边界

rc1 关闭 SnapGene GUI 后使用 `D:\SnapGene\SnapGene.exe` 执行官方 rich-fixture 门禁：
`rich declared compatibility gate: PASS`；`snapgene-gb` 官方往返通过；`.dna`
的第三方规范化差异按已声明分类接受。证据：`reports/rc1-rich-official/` 与
`reports/rc1-rich-official.log`。

## 6. 发布判定与后续规则

- 本轮 P0/P1：规则可执行字段注入、`block` 绕过，均已修复并有回归测试。
- P2 文档、额外模型、额外协议来源不会无限阻断当前版本；它们登记到升级日志
  和后续补丁/次版本，不得混入 RC 必修项。
- RC1 冻结验收已完成；正式版技术门禁见 FINAL-TECHNICAL-VALIDATION.md；
  关闭 SnapGene GUI 后完成官方复核、独立审查和最终包复跑即可决定 RC。
- 正式 `v0.9.0` 的含义是“已知高优先级问题关闭且发布门禁可重现”，不是
  “未来永远不会有小问题”。新发现的小问题按 `v0.9.1` 等补丁版本处理。

## 7. 不得省略的人工复核

1. 真实任务的物种/菌株/倍性、必需基因和互补策略。
2. 引物特异性、全基因组脱靶参考版本、读框/标签/启动子关系。
3. 厂商协议的当前版本、实验室实际库存和设备条件。
4. 含 `order`、复合 join、Unicode 名称或原生 `.dna` qualifier 的构建物，
   必须保留 GenBank 权威文件并在 SnapGene 中人工检查。
