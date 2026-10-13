# v0.9.1 架构恢复：可观察、可复现、可否证的验收条件（更新）

状态：**COMPLETE**。宏观目标主流程、全部 11 个 task kind、全部门禁与独立盲测均完成；最终报告 FINAL-REPORT-V091-DEV1.md 判定 ACCEPTED。

## 0. 宏观目标（不可降级）

从用户自然语言和原始文件开始，在不预知目标区间、角色、方向、突变、同源臂或最终答案的前提下，系统完成：

```text
理解 → 澄清 → ConstructionTask 冻结 → 专用 planner → 确定性执行
→ 文件/计算/目标三层验证 → 唯一 authoritative 闸门 → 可追溯交付
```

## 1. 原始要求 → 验收条件 → 实现 → 证据 对应表

| # | 原始要求 | 验收条件 | 当前实现 | 当前证据 | 状态 |
|---|---|---|---|---|---|
| AC-1 | 自然语言主入口 | S01/S05/S06/S08 原始请求 + 原始文件，truth 不可见，LLM 产出留空 draft | SKILL.md 协议 + `run_construction_task.py` | e2e-rerun/S01|S05|S06|S08 + 原 e2e 目录 | ✅ |
| AC-2 | 澄清闭环 | 缺失字段问题；回答写回；revision+diff；auto-confirmed 不填生物学字段 | `core/session.py` + CLI | test_construction_task_session.py + 11 条 NL 场景 run1 exit 3 | ✅ |
| AC-3 | ConstructionTask 严格契约 | 缺 selection/interval/mutation/角色稳定报错 | `core/task.py` + schema 11 kind shape | 单元测试 + 历史事故测试 | ✅ |
| AC-4 | 专用 planner | 11 个 kind 各有 planner；未注册 kind 拒绝 | `core/runtime_plan.py` | 单元 + NL e2e | ✅ |
| AC-5 | 确定性执行 | 同 task 重跑同序列/哈希；中间产物只写 intermediate/ | `core/runtime_execute.py` | 单元 + 重跑证据 | ✅ |
| AC-6 | 三层验证 | 三层可分别失败；goal 从 false 开始、必查项执行并通过才 true | `core/runtime_validate.py` | 单元（含 required 缺失、篡改、污染、负链、wrap、near-full） | ✅ |
| AC-7 | 唯一闸门 | 只有 finalize 写 authoritative；篡改 task/中间文件关闭失败 | `core/runtime_gate.py` | 单元（GATE_HASH_CHAIN_BROKEN / GATE_ARTIFACT_TAMPERED） | ✅ |
| AC-8 | 证据印章 | 来源与产物带 evidence class；manifest 记录 interval/strand/transformation/software/validation_scope/parent_hashes | `core/evidence.py` | manifest 内容 + 单测 | ✅ |
| AC-9 | S01 回归 | 原始 NL 缺坐标→澄清；密码子选择→正例；如实分级 | NL 重跑 | e2e-rerun/S01（6835 bp delivered） | ✅ |
| AC-10 | S05 回归 | 缺区间→拒绝；补齐→3260 bp | NL 重跑 | e2e-rerun/S05 | ✅ |
| AC-11 | S06 回归 | feature 推导边界与臂；无 bla/ori | NL 重跑 | e2e-rerun/S06（2696 bp delivered） | ✅ |
| AC-12 | S08 回归 | 缺区间持续阻断；无 authoritative | NL 重跑 | e2e-rerun/S08（exit 3/3） | ✅ |
| AC-12b | S08 正例 | 信息补齐后交付 | NL 重跑 | e2e-rerun/S08pos（8149 bp，USER_SPECIFIED_CONSTRUCTION_PASS） | ✅ |
| AC-13 | 可用替代入口 | 命令行/会话完整运行 | `run_construction_task.py` + session | CLI 单测 + 11 条 NL 场景 | ✅ |
| AC-14 | truth 治理 | truth 先冻结、独立来源、哈希 | blind-test/truths/BLIND-TRUTHS.json（SHA-256 冻结） | 盲测包 | ✅ |
| AC-15 | 固定 verdict | 报告用固定词汇，N/A 不计分 | `generate_construction_report.py` | S01 report.md verdict 验证 | ✅ |
| AC-16 | SKILL.md 协议 | LLM 不预填生物学决定 | SKILL.md 重写 | 11 条 NL 场景行为 | ✅ |
| AC-17 | 旧路径收口 | 旧 formal 拒绝；exploration 只出 preview；危险默认无残留 | formal CLI+库级拒绝；export_delivery_bundle 降级；orchestrator 输出入 preview/ | 单测 + 旁路扫描 | ✅ |
| AC-18 | 全量发布门禁 | unittest/smoke/quick/compile/coverage/mutation/property/rich/真实 primer3/SnapGene/打包 | 全部运行 | reports/v0.9.1-architecture-recovery/gates/ | ✅ |
| AC-19 | 独立盲测 | 未接触 truth 的独立 AI 前向测试 | blind-package + truths + 独立 AI 执行 | BLIND-EVALUATION.json：6/7 PASS、首次失败保留、未见重测 PASS | ✅ |

## 2. 决定性缺口

全部闭环：

1. ~~没有自然语言主入口~~ 已闭环。
2. ~~没有澄清闭环~~ 已闭环。
3. ~~没有替代入口~~ 已闭环。
4. ~~没有 NL 级负例与正例~~ 已闭环（4 事故 + S08 正例 + 6 新 kind）。
5. ~~证据印章未贯通~~ manifest 已贯通；报告工具已实现。
6. ~~旧兼容层危险默认~~ formal 全拒；exploration 仅 preview。
7. ~~发布门禁未运行~~ 全部运行（coverage exit 0 复跑确认）。
8. ~~rc1 完成定义未满足~~ 八条完成证明已形成证据链并签署。

## 3. 剩余工作

无。独立盲测完成并评估；coverage 门禁复跑 exit 0；最终报告签署 ACCEPTED。
