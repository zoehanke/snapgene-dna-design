---
name: "snapgene-dna-design"
description: "SnapGene-compatible DNA plasmid design toolkit. Parses .dna/.gb files, analyzes sequences, finds restriction sites, designs primers, runs validated basic simulations plus clearly labeled experimental cloning approximations, annotates features, and exports SnapGene-readable files. Invoke when user asks to design or analyze a plasmid, work with SnapGene .dna files, design primers, simulate cloning, find restriction sites, or generate construct files (质粒设计、引物设计、酶切分析、克隆模拟、SnapGene 文件处理)."
---

# SnapGene DNA Design

面向合成生物学的质粒与 DNA 构建设计工具链。当前版本：**v0.9.1-dev1（架构恢复开发版）**。

## 用途与触发条件

当用户需要以下任一任务时使用本 Skill：

- 从质粒/模板中扩增一个明确组件（cassette、启动子、CDS、标记盒、线性供体）；
- 在质粒中插入或替换一个明确区域；
- 对模板做明确的点突变；
- 阅读、分析、转换、验证或绘制 SnapGene `.dna` / GenBank `.gb` 文件；
- 设计引物并模拟 PCR（低层工具，预览级）。

## 核心原则：LLM 负责理解，程序负责计算与闸门

**LLM 必须做：**

1. 理解自然语言与文件指代；
2. 区分模板、骨架、组件、供体、插入物和参考序列；
3. 识别任务类型（扩增、插入、替换、突变等）；
4. 生成 `ConstructionTask` JSON；
5. 展示缺失字段、冲突和候选边界，并把用户回答写回 task；
6. 比较可行方法并解释取舍。

**LLM 禁止做：**

1. 手写或修改最终 DNA 序列；
2. 猜测未提供的坐标、边界、方向或突变；
3. 静默改变任务类型；
4. 把探索性方案升级为正式方案；
5. 绕过 planner、validator 或 authoritative gate。

**程序禁止做：**

1. 按文件名、文件顺序或全长区间补默认值；
2. 默认 mutation（历史 `100:A` 已移除）；
3. 把 insert 静默变成 replace，或把 component 静默变成 whole record；
4. 让 experimental 方法产出 authoritative 产物。

## ConstructionTask 入口（正式构建唯一路径）

所有正式构建先由 LLM 生成 `ConstructionTask v1` JSON（schema：`schemas/construction-task-v1.json`），再调用统一 runtime：

```python
from core import (validate_construction_task, plan, execute,
                  validate, finalize)

task = validate_construction_task(task_json)   # schema + 语义校验，失败即拒绝
task, plan = plan(task_json)                    # 专用 planner，字段缺失即拒绝
execution = execute(task, plan, out_dir)        # 只写 intermediate/
report = validate(task, plan, execution)        # artifact/computation/goal 三层
delivery = finalize(task, plan, execution, report, out_dir)  # 唯一 authoritative 出口
```

公共 seam 只有这五个函数。`finalize` 只接受 `mode=formal`、用户确认、`verified` 且 `method_maturity=validated` 的构建；失败时不创建 `authoritative/`。

## task kind 路由表

| task_kind | 状态 | 必填关键字段 | 产物拓扑 |
|---|---|---|---|
| `component_amplification` | 已迁移 | template + 明确 feature/interval；环状全长与近全长默认拒绝 | linear |
| `plasmid_replace` | 已迁移 | backbone + replace interval + replacement interval | circular |
| `plasmid_insert` | 已迁移 | backbone + 唯一插入边界 + insert interval | circular |
| `point_mutation` | 已迁移 | `mutations[{position_1based, ref, alt}]` | 同模板 |
| `overlap_assembly` | 已迁移 | 全部片段显式 interval + order + overlap_length；overlap 不匹配即拒绝 | circular/linear |
| `protein_fusion` | 已迁移 | partner5/partner3 显式区间 + stop_policy + 可选 linker；读框与翻译强制校验 | linear |
| `integration_donor` | 已迁移 | template 组件边界 + homology_arms + locus；臂与座位强制匹配 | linear |
| `gateway_recombination` | 已迁移 | reaction bp/lr + entry/destination source + stop_policy；唯一 att 对强制校验 | circular |
| `restriction_ligation` | 已迁移（experimental） | vector/insert + enzymes + orientation；位点唯一、黏端兼容、闭环强制校验 | circular |
| `hierarchical_assembly` | 已迁移 | stages 图 + 每级 fragments/overlap/topology；逐级独立验证 | circular/linear |
| `crispr_editing` | 已迁移（experimental） | nuclease + reference + target interval + guide/donor 策略 | 同 reference |

`method_maturity=experimental` 的 kind（restriction_ligation、crispr_editing）产物只能为 `experimental-preview`，闸门拒绝其进入 authoritative。未注册 kind 返回 `TASK_KIND_NOT_REGISTERED`，不退回通用组装器。

## 三层验证

- `artifact-valid`：文件可读、序列非空、拓扑正确、feature 坐标/strand 合法、CDS 一致、格式往返符合声明等级。
- `computation-valid`：从记录的输入与 transformation 独立重建序列，与产物一致。
- `goal-valid`：required/forbidden 组件、操作类型、区间、方向、拓扑满足用户目标；供体做骨架污染检查。

```text
verified = artifact-valid AND computation-valid AND goal-valid
```

## 唯一正式产物闸门

只有 `core.finalize()` 可生成：

```text
authoritative/construct.gb
authoritative/construct.fasta
authoritative/construct.dna
authoritative/DELIVERY-MANIFEST.json
```

其他脚本只能写 `preview/`、`intermediate/`、`experimental-preview/`。`.gb/.dna` 扩展名不构成权威性；权威性只由 `DELIVERY-MANIFEST.json` 中的 `artifact_class=authoritative` 与闸门签发决定。

## 隐私、来源与实验性结果硬规则

- 任何序列上传默认拒绝；在线服务（BLAST/CRISPOR 等）需用户明确同意。
- 每个来源必须携带 `source_evidence_class`（`user-provided` / `public-record` / `internal-fixture` / `synthetic-fixture` / `heuristic`）与 SHA-256；派生产物等级不得高于最弱关键来源。
- `method_maturity=experimental` 的产物只能是 `experimental-preview`，不得进入 authoritative，也不得声称可下单或用于湿实验。
- 所有计算结果均为序列级预测；湿实验结论必须由实验获得。

## 低层工具与旧路径

大多数脚本支持 `--json`，可直接作为**预览级**工具使用（设计引物、找酶切位点、模拟 PCR 等），但直接脚本产物不是权威交付。v0.9.0 的关键词 Agent 正式路径已弃用（`run_design_agent.py --mode formal` 返回 `LEGACY_AGENT_FORMAL_DEPRECATED`）。

## 参考资料

- `references/architecture-decision-record-v091.md`：本次架构恢复的决策与迁移状态。
- `references/construction-task-v1.md`：ConstructionTask 字段与语义。
- `references/SKILL-v090-legacy.md`：v0.9.0 完整历史说明（只读存档）。
- `references/upgrade-log.md`：版本变化与兼容性。
- `references/biological-parameters-sources.md`：默认参数与来源。
- `references/source-policy.md` 与 `references/privacy-and-consent.md`：来源与隐私政策。
