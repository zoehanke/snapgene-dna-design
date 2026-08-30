你接手 SnapGene DNA Design v0.9.1 的架构恢复开发。以下路径声明优先于任何旧报告、旧提示词或旧目录名。

## 一、项目目标

这是自然语言 DNA 构建 Agent，不是普通 DNA 脚本集合。

用户提供自然语言目标和原始序列文件。LLM 负责理解生物学意图、识别歧义、提出澄清问题。确定性程序负责坐标、序列、方向、阅读框、组装、验证和文件写入。

完整主线必须是：

```text
自然语言需求
→ 生物学意图理解
→ 必要澄清
→ ConstructionTask
→ 专用任务处理器
→ 确定性执行
→ artifact/computation/goal 三层验证
→ 唯一正式交付闸门
→ GenBank/FASTA/SnapGene 与报告
```

约束程序不能削弱 LLM 的语义理解。不能使用文件顺序、文件名关键词、整条序列默认值替代生物学判断。无法从序列计算的用户意图必须询问。

## 二、工作目录与文件边界

当前唯一开发目录：

```text
D:\codex_project\github\snapgene-dna-design
```

当前基线版本：

```text
0.9.1-dev1
```

本轮目标版本：

```text
0.9.1-dev2
```

不得复制新的版本目录。不得创建：

```text
snapgene-dna-design-v0.9.1-dev2-work
snapgene-dna-design-v0.9.2-dev1-work
```

本轮开发必须在当前 Git 仓库中创建分支：

```text
recovery/v0.9.1-dev2
```

所有源码、测试、架构和文档修改，只能发生在：

```text
D:\codex_project\github\snapgene-dna-design
```

发布包和构建产物：

```text
D:\codex_project\output\snapgene-dna-design
```

独立审查报告和失败证据：

```text
D:\codex_project\audit\snapgene-dna-design
```

临时测试文件：

```text
D:\codex_project\.tmp\snapgene-dna-design
```

真实或受限 DNA 文件：

```text
D:\codex_project\private-fixtures\snapgene-dna-design
```

历史版本只读目录：

```text
D:\codex_project\archive\snapgene-dna-design
```

全局已安装 Skill：

```text
C:\Users\祝浩淇\.codex\skills\snapgene-dna-design
```

全局 Skill 不是开发目标，不得修改它，也不得用它替代当前源码目录。

本机 SnapGene：

```text
D:\SnapGene\SnapGene.exe
```

开始开发前必须阅读：

```text
D:\codex_project\github\snapgene-dna-design\README.md
D:\codex_project\github\snapgene-dna-design\SKILL.md
D:\codex_project\github\snapgene-dna-design\docs\development\BASELINE-STATUS.md
D:\codex_project\github\snapgene-dna-design\docs\development\DEVELOPER-MANUAL.md
D:\codex_project\github\snapgene-dna-design\docs\architecture\ARCHITECTURE-RECOVERY-DEVELOPMENT-SPEC.md
D:\codex_project\github\snapgene-dna-design\docs\architecture\ACCEPTANCE-CRITERIA-V091.md
```

如果需要查看旧版本报告，只能从以下历史目录读取，不得修改：

```text
D:\codex_project\archive\snapgene-dna-design\legacy-worktrees
```

开发前先检查：

```powershell
Set-Location 'D:\codex_project\github\snapgene-dna-design'
git status
Get-Content VERSION
```

如果发现工作区存在用户未提交修改，必须先记录并停止，不得覆盖。

不得修改：

```text
D:\codex_project\archive
D:\codex_project\output
D:\codex_project\audit
D:\codex_project\private-fixtures
```

不得修改历史真值、首次失败证据、旧审计结论或冻结规范。版本必须使用 Git 分支、提交和标签管理，不得通过复制文件夹管理版本。

## 三、当前判定

dev1 独立复审结论：

```text
REJECTED_AS_UNSAFE_AND_OVERCLAIMED
P0 >= 3
P1 >= 5
```

原有 518 项测试确实通过，但三个新对抗用例仍能生成正式 authoritative 产物。因此测试数量不能作为完成依据。

## 四、本轮核心任务

本轮不是针对三个样例打补丁。必须修复它们代表的通用架构缺陷。

### P0-01 统一区间语义

当前 `_arc()` 会把线性记录的 `[a,a)` 解释成整条序列。

必须建立统一、拓扑感知的区间模型，所有 task kind 共同使用。

线性记录：

```text
0 <= start < end <= length
```

必须拒绝：

```text
start == end
start > end
负坐标
超过长度
隐式 modulo
```

环状记录：

```text
start < end
```

表示普通区间。

```text
start > end
```

只能在 schema 明确声明 `wrap_origin=true` 时表示跨原点。

```text
start == end
```

默认拒绝。只有明确的 whole-record 操作、用途和用户确认才能使用。

必须覆盖：

```text
component_amplification
plasmid_replace
plasmid_insert
overlap_assembly
protein_fusion
integration_donor
hierarchical_assembly
crispr_editing
```

不得在不同 planner 中复制不同区间规则。

必须加入回归：

```text
线性 [2,2) 不得变成整条模板
线性 [8,3) 必须拒绝
环状跨原点必须显式声明
全长选择必须显式审批
```

所有失败必须无 authoritative 产物。

### P0-02 重建 goal validation

当前 required component 只要出现在任意输入文件的 feature 中，就可能被认为已进入最终产物。

必须删除这种验证方式。

每个必需组件必须形成可追踪证据链：

```text
component_id
source_id
source_sha256
source_interval
source_strand
transformation_step
product_interval 或 product_junction
expected_sequence_sha256
observed_sequence_sha256
verification_result
```

goal validator 必须检查最终产物中的实际序列、方向、数量、位置、边界和 junction。

禁止：

```text
从未参与构建的输入文件推断组件存在
只按 feature 名称判断组件存在
只按 product label 判断组件存在
只检查短名称是否出现在 DNA 字符串
```

forbidden component 必须使用序列和 transformation trace 检查，不能只依赖标签。

必须加入回归：

```text
requiredX 只存在于未使用 decoy 输入
最终产物不含 requiredX 序列
结果必须 goal_valid=false
不得生成 authoritative
```

### P0-03 重建不可伪造交付链

当前调用方可以修改：

```text
plan.method_maturity
execution.method_maturity
validation.overall
```

然后把 experimental 结果交付为 authoritative。

必须实现不可伪造的数据链。

至少要求：

1. PlanResult、ExecutionResult、ValidationResult 使用不可变结构或重新序列化验证。
2. plan 哈希覆盖完整语义计划，包括：
   ```text
   task hash
   task revision
   task kind
   handler identity/version
   method maturity
   sources
   source hashes
   intervals
   strands
   operations
   steps
   topology
   expected components
   forbidden components
   product sequence hash
   ```
3. execution 哈希绑定完整 plan 哈希和实际产物哈希。
4. validation 哈希绑定 task、plan、execution 和全部检查结果。
5. finalize 必须独立重新计算完整 hash chain。
6. finalize 必须重新检查来源文件当前 SHA，防止验证后来源被修改。
7. finalize 不能信任调用方传入的 `overall=true` 或 `method_maturity=validated`。
8. experimental 方法无论如何不得进入 authoritative。
9. 删除 `runtime_execute.py` 中发现异常后执行 `pass` 的无效检查。

必须加入回归：

```text
修改 plan maturity
修改 execution maturity
修改 validation overall
修改 validation 三个布尔值
修改 plan steps
修改 product metadata
修改来源文件
修改中间 GB
修改中间 FASTA
```

以上任何操作都必须稳定拒绝，且不留下 authoritative 目录。

## 五、P1 必修

### P1-01 最终三格式验证

当前 `.dna` 在验证完成后才生成，只检查写入进程退出码。

正确流程：

```text
生成 GB/FASTA/DNA 到临时目录
→ 分别重新读取
→ 比较序列、拓扑、feature、关键 qualifier
→ 比较三格式语义一致性
→ 使用 D:\SnapGene\SnapGene.exe 做官方 roundtrip
→ 达到声明的 compatibility grade
→ 原子移动到 authoritative
```

任一用户要求的格式验证失败，不能正式交付该格式。

不得把以下结果写成门禁全绿：

```text
core_passed=false
delivery_grade=failed
required format missing
official verification not executed
```

### P1-02 ConstructionTask 严格化

正式任务必须包含明确的 goal assertions。

至少包括：

```text
required_components
forbidden_components
expected_topology
expected_operation
expected_junctions
copy_count_constraints
orientation_constraints
frame_constraints
```

适用字段可以为空数组，但必须显式存在并记录为什么为空。

operation 子结构改为 `additionalProperties:false`。未知字段必须拒绝，不能静默忽略。

### P1-03 每类任务真正封装

当前 `runtime_plan.py` 和 `runtime_validate.py` 是超过千行的重复分支。

建立统一 TaskHandler 接口，例如：

```text
TaskHandler
  validate_contract(task)
  clarify(task)
  plan(task)
  execute(task, plan)
  recompute(task)
  validate_goal(task, plan, product)
  delivery_policy(task, validation)
```

11 个 task kind 必须由注册表绑定到 handler。

注册表必须成为唯一事实源。禁止在 session、planner、executor、validator 中维护多套 kind switch。

可以按任务族复用公共模块，但不能让所有任务继续堆在一个巨型文件里。

### P1-04 生物学边界修复

必须处理：

1. integration donor 默认要求左右同源臂同时存在。
2. 线性参考序列边界不足时禁止 modulo 环绕。
3. 单臂 donor 只能作为明确的特殊策略，并要求用户确认和证据。
4. Gateway stop policy 只能检查目标阅读框，不能在三个 frame 中任选一个 stop。
5. CDS translation table 必须来自 feature、宿主或用户确认，禁止统一硬编码 table 11。
6. plasmid_replace 必须支持显式环状跨原点替换，或明确拒绝并解释。
7. experimental 验证中任一层失败时，overall 必须是 `failed`，不能无条件标记 `experimental-preview`。

### P1-05 CLI 失败关闭

损坏 JSON、文件不存在、编码问题、权限异常、SnapGene 失败、依赖崩溃都必须：

```text
返回结构化错误
非零退出码
result.json 可读
无 authoritative
无半成品正式目录
```

不能输出未捕获堆栈作为唯一结果。

### P1-06 盲测和 truth 治理

不得修改已有 truth 来获得 PASS。

现有 B03/B04 勘误必须保留为证据问题，不能称作冻结盲测通过。

新盲测要求：

1. truth 在运行前生成。
2. 记录创建时间和 SHA-256。
3. 执行方不可读取 truth。
4. 评估方与开发方分离。
5. 首次失败永久保留。
6. synthetic fixture 标记为 `synthetic-fixture`。
7. 禁止把 synthetic fixture 写成 `user-provided`。
8. 禁止把合成计算测试写成真实科研构建验证。
9. 开发 AI 不得自行宣布独立盲测通过。

本轮只准备新的 blind package 和评估协议。独立执行留给后续审查 AI。

### P1-07 S06 真值问题

规范要求约 2646 bp cassette 和约 2736 bp 含尾供体。

当前开发报告改用 `[69,2675)` 并建立“修正真值 v2”，得到 2696 bp。

必须：

1. 恢复并列展示所有历史候选边界。
2. 说明 `[41,2687)` 与 `[69,2675)` 分别代表什么生物学区域。
3. 使用公开记录、feature、引物边界或论文证据裁决。
4. 不得由被测 planner 自己生成唯一 truth。
5. 无法裁决时状态必须是 `needs-biological-review`。
6. 未裁决前不得把任一版本写成公开真值复现 PASS。

### P1-08 发布包修复

`build_release.py` 中 `EXCLUDE_PREFIXES` 重复赋值必须修复。

要求：

1. academic 和 redistributable ZIP 不得内嵌过期 `release/SHA256SUMS.txt`。
2. ZIP 内 `RELEASE-MANIFEST.json` 只记录包内文件。
3. ZIP 自身 SHA 写在包外的 `SHA256SUMS.txt`。
4. redistributable 不含受限 `.dna`。
5. source ZIP 必须明确是 academic source 还是 redistributable source。
6. 不允许把含受限 fixtures 的 source ZIP 当成可公开源码包。
7. 不含 reports、blind truths、临时文件、缓存、`.pyc`、`__pycache__`。
8. 解压后重新运行 quick validate、smoke 和核心回归。

## 六、必须先红后绿

开发前先在 dev2 中加入以下失败测试，并保存修改前结果：

```text
test_linear_zero_width_interval_rejected
test_linear_reverse_interval_rejected
test_unused_source_cannot_satisfy_required_component
test_plan_maturity_tamper_rejected
test_validation_boolean_tamper_rejected
test_source_changed_after_validation_rejected
test_fasta_gb_mismatch_rejected
test_dna_semantic_mismatch_rejected
test_experimental_validation_failure_is_failed
test_linear_integration_arm_boundary_no_wrap
test_gateway_stop_checked_in_declared_frame
test_translation_table_preserved
```

测试必须先在旧实现上失败，再修程序使其通过。

禁止直接写一组只在新代码上运行的测试，然后声称完成 TDD。

## 七、禁止事项

1. 禁止修改测试期望来适配错误输出。
2. 禁止修改冻结 truth 获得 PASS。
3. 禁止删除或覆盖首次失败。
4. 禁止把 fixture、mock、synthetic 测试写成真实后端或真实科研验证。
5. 禁止用测试总数替代验收结论。
6. 禁止把“代码存在”写成“能力完成”。
7. 禁止只修三个已知输入。
8. 禁止自行宣布 `COMPLETE`、`ACCEPTED`、`READY_FOR_RC1` 或 `P0=0`。
9. 禁止发布正式版或 RC。
10. 未解决项不得放入“已知限制”后结束任务。

## 八、验证要求

必须运行并保存原始日志：

```text
完整 unittest
历史事故回归
新增 P0/P1 对抗测试
property tests
mutation tests
coverage
smoke_core
smoke_academic
quick_validate
compileall
Unicode 路径
academic ZIP 解压测试
redistributable ZIP 解压测试
SnapGene 官方 roundtrip
三格式语义一致性
```

518 项旧测试必须继续通过。新增测试数量单独报告。

测试全绿不自动代表任务完成。必须逐条对照本提示词验收。

## 九、报告要求

唯一主报告：

```text
D:\codex_project\audit\snapgene-dna-design\DEV2-RECOVERY-REPORT.md
```

报告不能只写“已完成”。必须提供具体证据。

固定结构：

```text
# v0.9.1-dev2 Architecture Recovery Report

## 1. 最终状态
## 2. dev1 三个 P0 的原始复现输出
## 3. 根因分析
## 4. 通用架构修改
## 5. 区间模型及全部边界行为
## 6. goal evidence trace 示例
## 7. hash chain 覆盖字段
## 8. 篡改测试逐项结果
## 9. 11 个 task handler 的实际结构
## 10. 三格式验证结果
## 11. SnapGene 官方核验逐文件结果
## 12. S06 边界证据与未决事项
## 13. 盲测治理状态
## 14. 发布包内容与哈希
## 15. 实际命令、退出码和测试数字
## 16. 未完成要求
## 17. 下一阶段资格
```

每个问题使用表格：

```text
| 编号 | 原始缺陷 | 修改文件/行号 | 修改方法 | 失败前证据 | 修复后证据 | 是否完成 |
```

报告必须明确区分：

```text
代码实现
单元测试
合成验证
公开记录复现
真实后端验证
独立盲测
真人生物学验收
```

如果任何 P0、P1、truth 冲突、SnapGene core failure 或发布污染未解决，最终状态必须写：

```text
INCOMPLETE
REJECTED_FOR_RC
```

不得使用模糊措辞掩盖未完成项。
