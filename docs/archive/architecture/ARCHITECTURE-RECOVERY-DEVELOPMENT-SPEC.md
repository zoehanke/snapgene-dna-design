# SnapGene DNA Design v0.9.1 架构恢复开发说明

状态：强制实施规范  
基线：v0.9.0，只读保留  
开发目录：`<workspace>`
目标版本：v0.9.1  
首要目标：解除低效程序对 LLM 生物学理解能力的错误压缩，同时以确定性程序约束序列计算、验证和正式交付。

## 1. 开发目标

把当前“DNA 工具箱加薄弱 Agent 壳”重构为：

```text
LLM 理解用户目标
→ ConstructionTask 冻结生物学意图
→ 专用任务规划器形成可执行方案
→ 确定性工具计算序列
→ 文件、计算、目标三层验证
→ 唯一正式产物闸门
→ 可追溯交付
```

重构必须同时满足：

1. 保留 LLM 对自然语言、生物学语境、复杂需求和方案比较的能力。
2. 禁止关键词解析器把 LLM 已理解的语义压缩成错误默认值。
3. 禁止 LLM 直接猜测序列、坐标、方向、边界或替用户作出生物学决定。
4. 所有精确序列操作由确定性工具执行。
5. 每个正式产物必须证明“文件正确、计算正确、目标正确”。
6. 任何信息不足、实验性算法或证据不足的结果只能澄清、阻断或输出预览。
7. v0.9.0、原审计报告、原错误产物和原测试证据不得覆盖或改写。

## 2. 暂停范围

本规范完成前暂停新增以下能力：

1. 新核酸酶或 CRISPR 后端。
2. 新协议网站和在线数据源。
3. 新克隆方法。
4. 新经验规则类别。
5. 与本次架构恢复无关的界面和报告扩展。

允许工作仅限：中央契约、任务路由、规划器迁移、验证、交付闸门、回归测试、文档精简和必要兼容修复。

## 3. 当前问题与强制修复

| 编号 | 当前问题 | 风险 | 强制修复 |
|---|---|---|---|
| A01 | `nl_parser.py` 依赖关键词识别任务 | 丢失 LLM 已理解的生物学语义 | Skill 模式由 LLM 直接生成 ConstructionTask；旧解析器退出正式路径 |
| A02 | `_file_role_candidates()` 根据文件名猜骨架 | 模板、骨架、供体、插入物角色错误 | 文件角色必须来自用户陈述、可计算证据或显式确认 |
| A03 | `_intent_for_plan()` 默认第一个文件为骨架 | 错误选定骨架 | 缺少 `source.role` 时必须澄清或阻断 |
| A04 | 未指定片段区间时默认 `[0, 全长]` | S05、S06 类错误 | 组件操作必须有 feature、interval 或 junction；缺失时不得执行 |
| A05 | 点突变缺失时默认 `100:A` | 生成无关突变 | `mutations[]` 必填；缺失返回 `MUTATION_SPEC_REQUIRED` |
| A06 | 插入与替换共用通用组装模型 | MCS 残余、错误串联 | `plasmid_insert` 与 `plasmid_replace` 使用不同 planner 和 schema |
| A07 | DesignSpec 内部字段过于自由 | 状态完整但生物学目标不完整 | 引入严格 ConstructionTask v1；DesignSpec 只管理会话与版本 |
| A08 | 通用 planner 把任务简化成骨架加片段 | 无法表达 PCR cassette、整合供体、融合等 | 按 `task_kind` 路由至专用 planner |
| A09 | `validate_construct` 只检查内部自洽 | 错误目标仍可 PASS | 建立 artifact、computation、goal 三层验证 |
| A10 | `verified` 同时代表多种含义 | 文件正确被误写成生物学正确 | 验证状态分层保存；`verified` 只由三层全过派生 |
| A11 | `ready_for_wet_lab` 由技术状态直接推导 | 过度承诺 | 正式就绪要求三层验证、成熟算法、证据和审批同时满足 |
| A12 | 多个脚本可直接写正式 `.gb/.dna` | 绕过 Agent 和验证 | 底层脚本只能生成中间或预览产物；唯一闸门生成权威交付物 |
| A13 | `--consent auto` 可进入正式流程 | 自动代替用户作决定 | 自动确认不得覆盖生物学选择、放宽、边界、引物订购或外部上传 |
| A14 | experimental 方法可形成正式外观产物 | 概念模拟被误认为可执行方案 | experimental 永久限定为 `experimental-preview` |
| A15 | 来源类型没有进入核心模型 | 内部夹具冒充公开复现 | 所有来源和产物携带独立证据印章 |
| A16 | 方法成熟度与来源可信度混合 | 审计结论混乱 | `source_evidence_class` 与 `method_maturity` 分开记录 |
| A17 | 真值可由同类算法生成 | 程序与真值同时错误仍 PASS | 真值必须先冻结、独立来源、带哈希；禁止从被测输出反推 |
| A18 | 内部或合成 fixture 被写成论文复现 | 生物学证据强度虚高 | 报告必须使用精确验证标签，不允许升级证据等级 |
| A19 | feature 注释被默认信任 | 缺失、重名、错误注释导致错选范围 | 注释状态进入任务；证据不足必须列候选并澄清 |
| A20 | 子代理可手工调用低层脚本纠偏 | 修复不可复现 | 所有纠偏必须形成 ConstructionTask revision 和 plan diff |
| A21 | 状态机不记录算法成熟度和目标验证 | 无法判断是否可交付 | 状态、验证、证据、成熟度独立建模 |
| A22 | SKILL.md 混入大量历史和功能细节 | 核心门禁被稀释 | 按渐进披露重写，主文件只保留路由和硬不变量 |
| A23 | 失败路径可能留下正式命名文件 | 用户误用失败产物 | 原子写入临时目录；闸门失败时不产生 authoritative 产物 |
| A24 | 审计评分把 N/A 计满分 | 阻断场景分数虚高 | N/A 不计分；构建成功与正确阻断分开统计 |
| A25 | 报告中的 PASS 定义不统一 | 内部回归、合成模拟、公开复现混用 | 使用固定 verdict 词汇和证据要求 |

## 4. 核心架构

### 4.1 LLM 意图层

LLM 负责：

1. 理解自然语言和文件指代。
2. 区分模板、骨架、组件、供体、插入物和参考序列。
3. 识别插入、替换、扩增、融合、突变、整合、重组和分层组装。
4. 生成候选 ConstructionTask。
5. 展示缺失字段、冲突和候选边界。
6. 记录用户回答并生成新 revision。
7. 比较可行方法并解释取舍。

LLM 不负责：

1. 手写或修改最终 DNA 序列。
2. 猜测未提供的坐标、边界、方向或突变。
3. 静默改变用户任务类型。
4. 把探索性方案升级为正式方案。
5. 绕过 planner、validator 或交付闸门。

### 4.2 ConstructionTask v1

ConstructionTask 是生物学任务的唯一执行契约。DesignSpec 保留会话、来源、问题、回答和 revision；planner 只接收已通过 schema 与语义验证的 ConstructionTask。

最小结构：

```json
{
  "schema_version": "construction-task-v1",
  "task_id": "task-...",
  "revision": 1,
  "mode": "exploration",
  "task_kind": "component_amplification",
  "raw_request": "...",
  "sources": [
    {
      "source_id": "template-1",
      "path": "template.gb",
      "role": "template",
      "sha256": "...",
      "topology": "circular",
      "annotation_status": "reviewed",
      "evidence": {
        "source_evidence_class": "user-provided",
        "accession": null,
        "version": null,
        "citation": null,
        "retrieved_at": null
      }
    }
  ],
  "operation": {},
  "target": {
    "source_id": "template-1",
    "selection": {
      "kind": "feature",
      "feature_id": "...",
      "interval_0based": null,
      "strand": 1
    },
    "resolution_status": "resolved",
    "resolution_evidence": []
  },
  "product": {
    "topology": "linear",
    "required_components": [],
    "forbidden_components": [],
    "expected_length": null,
    "formats": ["gb", "fasta", "dna"]
  },
  "method_constraints": {},
  "approvals": {},
  "assumptions": [],
  "provenance": []
}
```

硬不变量：

1. `task_kind` 必须来自注册表。
2. 每个 source 必须有唯一角色、内容哈希和证据印章。
3. 影响序列的 selection 必须为 `resolved`。
4. `resolved` 必须有用户证据、公开来源或确定性计算证据。
5. 语义字段不得通过文件顺序、文件名或全长区间默认值补齐。
6. 可计算事实允许程序填写，例如长度、GC、哈希、feature 候选、酶切位点。
7. 生物学决定必须来自用户、可信来源或显式审批。
8. 每次改变 selection、operation、product 或方法约束都增加 revision 并保存 diff。

### 4.3 证据印章

来源可信度与算法成熟度使用两个独立维度。

`source_evidence_class`：

```text
user-provided
public-record
internal-fixture
synthetic-fixture
heuristic
```

`method_maturity`：

```text
validated
experimental
```

每个来源、派生片段、引物、组装结果和最终产物必须保留：

1. source ID。
2. accession 与版本，若存在。
3. 原始文件 SHA-256。
4. 原始区间与 strand。
5. 执行的 transformation。
6. 使用的软件、版本和参数。
7. method maturity。
8. 验证范围。

派生产物的证据等级不得高于其最弱关键来源。报告不得把 `internal-fixture` 或 `synthetic-fixture` 描述为公开质粒复现。

### 4.4 严格路由器

路由器只执行两件事：

1. 根据 `task_kind` 选择专用 planner。
2. 检查该 planner 的必填字段是否完整。

路由器不得：

1. 猜 source role。
2. 猜 interval。
3. 猜 mutation。
4. 把 replace 改为 insert。
5. 把 component 改为 whole record。
6. 静默换方法。

错误返回必须包含：

```json
{
  "status": "needs-clarification",
  "error_code": "COMPONENT_BOUNDARY_REQUIRED",
  "missing_fields": ["target.selection"],
  "questions": [],
  "write_authoritative_artifact": false
}
```

### 4.5 专用任务规划器

| task_kind | 必填字段 | 关键不变量 |
|---|---|---|
| `component_amplification` | template、明确 feature 或 interval、引物策略、linear product | 环状模板全长默认拒绝；目标为 component 时不得含模板骨架 |
| `plasmid_insert` | backbone、单一插入边界、insert、方向、topology | 原骨架序列不删除；插入边界必须唯一 |
| `plasmid_replace` | backbone、replace interval 或两个 junction、replacement、方向 | 明确删除区间后再插入；不得退化为 insert |
| `protein_fusion` | 两个 CDS、顺序、frame、stop policy、linker policy | 融合读框、起止密码子、标签方向必须显式验证 |
| `integration_donor` | locus、host、strand、donor component、homology arms、linear product | 禁止意外细菌骨架；同源臂方向和目标座位必须匹配 |
| `point_mutation` | `mutations[{pos1, ref, alt}]` 或蛋白突变加密码子审批 | 禁止默认 mutation；ref 必须与输入一致 |
| `gateway_recombination` | reaction、Entry、Destination、att pair、stop/tag policy | BP 与 LR 分阶段；需要的中间体必须交付 |
| `restriction_ligation` | vector cut sites、insert ends、orientation、frame | 位点唯一性、末端兼容、方向和闭环必须验证 |
| `overlap_assembly` | 全部片段明确区间、顺序、topology、overlap policy | 闭环 junction 必须验证；不得使用完整文件默认片段 |
| `hierarchical_assembly` | stage graph、level、modules、acceptors、每级产物 | 每一级独立执行和验证；缺模块不得编造最终序列 |
| `crispr_editing` | nuclease、reference、target、guide strategy、donor strategy、host | 模型适用性、参考版本、脱靶覆盖和供体约束必须显式 |

通用 planner 仅允许处理已经显式给出全部片段区间、顺序、操作和拓扑的 `overlap_assembly`。它不得作为未知任务的兜底入口。

### 4.6 确定性执行层

执行器只接受已验证 planner 输出。执行器必须：

1. 返回结果对象，不直接声明正式交付。
2. 记录输入哈希、区间、方向、参数、后端和版本。
3. 使用原子临时目录写中间文件。
4. 失败时清理或隔离未完成产物。
5. 输出 `intermediate`、`preview` 或 `experimental-preview` artifact class。
6. 不允许调用者用文件名把中间文件伪装成权威产物。

现有读取、Primer3、PCR、组装、feature 迁移和 SnapGene 工具继续复用。重构不得用 LLM 或新字符串拼接代码替代已验证算法。

## 5. 三层验证

### 5.1 artifact-valid

验证文件和数据结构：

1. 文件可读取。
2. 序列非空。
3. 拓扑正确表达。
4. feature 坐标、strand、复合 location 合法。
5. CDS 注释与序列一致。
6. 格式转换和 SnapGene 往返符合声明等级。

### 5.2 computation-valid

验证确定性计算：

1. 提取区间和方向正确。
2. 反向互补正确。
3. PCR binding、tail 和产物一致。
4. junction、overhang 和 overlap 正确。
5. 插入、替换、删除和闭环算法符合 plan。
6. CDS、融合读框、起止密码子和 translation 正确。
7. 输出序列能从记录的输入与 transformation 独立重建。

### 5.3 goal-valid

按 task kind 验证用户目标：

1. required components 全部存在。
2. forbidden components 全部不存在。
3. source roles、选择区间、操作类型和方向正确。
4. product topology 与预期一致。
5. 插入与替换没有混淆。
6. component 与 whole record 没有混淆。
7. 公开复现任务达到声明的等价标准。
8. 多件和多阶段任务没有丢件或跳过中间体。
9. 产物没有超出用户确认的范围。

最终验证状态只能由以下表达式得到：

```text
verified = artifact-valid AND computation-valid AND goal-valid
```

任何单层失败都必须阻止正式交付。验证报告保存每层状态、检查项、证据、错误码和 task revision hash。

## 6. 唯一正式产物闸门

建立一个深模块作为唯一正式交付 seam。外部 interface 只接收：

```text
finalize(task, plan, execution, validation) → delivery 或明确失败
```

闸门必须同时验证：

1. ConstructionTask schema 与语义有效。
2. task、plan、execution、validation 哈希链一致。
3. 三层验证全部通过。
4. `method_maturity == validated`。
5. 正式模式所需用户审批齐全。
6. 不存在未解决 assumption、source conflict 或 must ask。
7. 所有正式产物来自同一次经过验证的 execution。

只有闸门能生成：

```text
authoritative/construct.gb
authoritative/construct.fasta
authoritative/construct.dna
authoritative/DELIVERY-MANIFEST.json
```

其他脚本生成的文件必须位于：

```text
preview/
intermediate/
experimental-preview/
```

`.gb` 或 `.dna` 扩展名不代表正式产物。权威性只由 manifest 中的 artifact class、验证哈希和闸门签发状态决定。

失败行为：

1. 不创建 authoritative 目录。
2. 不留下半写入 manifest。
3. 返回稳定错误码。
4. 保留必要的预览和调试证据，但明确不可下单、不可用于湿实验。

## 7. 用户确认与自动化

自动确认仅允许无生物学意义的操作，例如选择默认报告文件名。以下内容必须由用户、可信来源或显式任务约束确定：

1. source role。
2. component boundary。
3. replace interval。
4. mutation 和密码子选择。
5. fusion linker 与 stop policy。
6. 核酸酶或载体体系变更。
7. 删除用户要求的元件。
8. 方法降级、参数大幅放宽和 heuristic 替代。
9. 序列上传。
10. 正式引物订购和湿实验使用声明。

`--auto-confirm` 和 `--yes` 不得满足这些审批。formal 模式遇到此类缺失必须返回 `needs-clarification`。

## 8. 注释与组件边界

组件解析按以下证据顺序进行：

1. 用户明确 interval 或 junction。
2. 唯一且完整的 feature。
3. 带 accession、版本和来源的标准方法边界。
4. 多 feature 组成的候选组件。

如果存在重名 feature、重叠 feature、缺失调控区、跨原点、负链、注释不完整或多个合理边界，resolver 必须返回候选列表和差异，不得选取全长作为兜底。

对线性整合供体额外执行 backbone contamination 检查。检查至少包含：

```text
bla/AmpR
细菌复制起点
lacZ
ccdB
非目标筛选标记
非目标载体 backbone feature
目标 component 之外的大段模板序列
```

注释不足时不得声明“无骨架污染”。必须结合模板覆盖比例、拓扑、已知 feature 和来源证据决定澄清或阻断。

## 9. 回归事故规格

### 9.1 S01 点突变

输入：用户要求 R335L 与 K337G。

必须：

1. 解析为结构化蛋白突变并要求密码子策略，或提出明确问题。
2. 读取参考氨基酸并验证 R335、K337 与输入一致。
3. 未确认核苷酸替换时不得生成正式产物。
4. 任何执行记录不得出现默认 `100:A`。

失败码：`MUTATION_SPEC_REQUIRED`、`REFERENCE_RESIDUE_MISMATCH` 或 `CODON_CHOICE_REQUIRED`。

### 9.2 S05 MCS 替换

输入：pUC19 加 ins1、ins2，替换指定 MCS。

必须：

1. task kind 为 `plasmid_replace`。
2. replace interval 或两个 junction 必须明确。
3. 缺少 interval 时失败关闭且无 authoritative 产物。
4. 显式信息完整时生成正确替换产物。
5. 旧 3386 bp 完整串联方案必须被 goal validator 拒绝。

失败码：`REPLACE_INTERVAL_REQUIRED`、`OPERATION_TYPE_MISMATCH`。

### 9.3 S06 cassette 扩增

输入：从 pFA6a 模板扩增 URA3-Kan cassette，添加同源尾，输出线性供体。

必须：

1. template 与 component 分离建模。
2. component boundary 必须有 feature、interval 或标准位点证据。
3. 边界不确定时提问，不得使用完整环状模板。
4. 正确回归使用冻结真值验证约 2646 bp cassette 与约 2736 bp 含尾供体。
5. 旧 5194 bp 供体必须触发 backbone contamination 阻断。
6. 原始错误供体、日志和审计结论永久保留在 before-fix 证据中。

失败码：`COMPONENT_BOUNDARY_REQUIRED`、`WHOLE_TEMPLATE_SELECTED_FOR_COMPONENT`、`UNEXPECTED_VECTOR_BACKBONE_IN_DONOR`。

### 9.4 S08 启动子替换

输入：复现公开 pGL3 启动子构建。

必须：

1. 明确任务是 insert、replace 还是 public record reproduction。
2. 复现模式必须绑定 accession、版本和 junction 真值。
3. 需要删除 MCS 时必须形成 replace interval。
4. 只插入并保留 MCS 的方案不能标记为公开复现 PASS。
5. 用户接受替代设计后可生成 alternative preview，并明确与公开记录差异。

失败码：`REPRODUCTION_BOUNDARY_REQUIRED`、`PUBLIC_RECORD_MISMATCH`。

## 10. 测试策略

### 10.1 公共测试 seam

测试只通过以下公共 seam：

1. `validate_construction_task(task)`。
2. `plan(task)`。
3. `execute(task, plan)`。
4. `validate(task, plan, execution)`。
5. `finalize(task, plan, execution, validation)`。
6. Skill 自然语言端到端入口。

不得围绕私有函数、生成措辞或内部调用次数写核心验收测试。

### 10.2 TDD 顺序

每个垂直切片执行：

```text
历史事故负例变红
→ 最小契约实现
→ 正例变绿
→ 原历史任务重新运行
→ 全量回归
```

优先顺序：

1. ConstructionTask schema 与危险默认值负例。
2. authoritative gate。
3. `component_amplification` 完整闭环。
4. `plasmid_replace` 完整闭环。
5. `point_mutation` 完整闭环。
6. 其他 task kind 逐个迁移。

### 10.3 必测边界

1. 空文件、空序列、坏碱基和坏路径。
2. 正链与负链。
3. 环状跨原点 interval。
4. feature 重名、重叠、复合 location 和缺失注释。
5. component 等于近乎全长模板。
6. 模板含多个抗性和复制元件。
7. insert 与 replace 的同输入差异。
8. CDS 起止密码子、frame、linker 和 stop policy。
9. 多件、多阶段任务缺少一个中间体。
10. experimental 方法尝试正式交付。
11. source hash 或 task revision 改变后复用旧验证。
12. 失败后 authoritative 目录和 manifest 不存在。
13. 低层脚本产物不能被 delivery 误收为 authoritative。
14. 用户明确要求 whole record 时允许，但必须记录审批和用途。

## 11. 真值与审计治理

每个外部场景的 truth 必须在运行被测系统前创建并冻结：

1. 保存来源、accession、版本、检索日期和 SHA-256。
2. 保存构建操作、边界和等价比较规则。
3. truth 目录对设计执行方只读或不可见。
4. 禁止使用被测算法生成唯一 truth。
5. 禁止根据实际输出修改 truth 以获得 PASS。
6. 原始失败与修复后结果并列保存。

固定 verdict：

```text
PUBLIC_RECORD_REPRODUCTION_PASS
USER_SPECIFIED_CONSTRUCTION_PASS
INTERNAL_FIXTURE_REGRESSION_PASS
SYNTHETIC_COMPUTATIONAL_PASS
EXPERIMENTAL_PREVIEW_ONLY
PARTIAL
BLOCKED_AS_DESIGNED
FAIL
```

`BLOCKED_AS_DESIGNED` 与构建成功分开统计。N/A 维度不计分，不按满分处理。

## 12. 旧路径迁移

1. v0.9.0 保持只读，记录目录哈希。
2. v0.9.1 开发只在独立工作副本进行。
3. 新增 ConstructionTask 和中央运行时后，旧 `nl_parser → _intent_for_plan → generic planner` 正式路径标记 deprecated。
4. 兼容 adapter 只能把字段完整的旧 intent 转换为 ConstructionTask。
5. 含危险默认值的旧 intent 必须拒绝转换。
6. 每迁移一个 task kind，旧任务分支停止接受 formal 模式。
7. 全部 task kind 迁移前，旧脚本仍可作为明确参数的低层工具使用，但输出只能是 preview 或 intermediate。
8. 所有正式调用最终收敛到统一 runtime 和 authoritative gate。

不允许一次性重写底层算法。采用逐 task kind 垂直迁移，保留已验证工具并替换错误调度层。

## 13. SKILL.md 重构

主 `SKILL.md` 只保留：

1. Skill用途和触发条件。
2. LLM职责与禁止越权范围。
3. ConstructionTask 入口。
4. task kind 路由表。
5. 三层验证与正式闸门。
6. 隐私、来源和实验性结果硬规则。
7. 指向按任务加载的 references。

历史版本、完整CLI清单、长篇兼容性说明和方法细节移入 references。每个 reference 必须由明确触发条件指向。删除重复、过时和可从 `--help` 直接获取的内容。

## 14. 发布验收

v0.9.1-rc1 只有满足以下条件才能生成：

1. A01 至 A25 全部关闭并有对应证据。
2. S01、S05、S06、S08 历史负例全部稳定捕获。
3. 四个修复后正例通过相同自然语言入口。
4. 不存在危险默认值的代码路径。
5. 所有 formal 构建只经过 authoritative gate。
6. experimental 结果无法进入 authoritative 目录。
7. 三层验证有独立测试且能分别失败。
8. truth 冻结和证据印章测试通过。
9. 源码、academic ZIP、redistributable ZIP 全量测试通过。
10. coverage、mutation、property、smoke、schema、manifest 和 license 门禁通过。
11. 本机 `<workspace>` 官方往返按声明等级通过。
12. 至少一轮独立自然语言前向测试，评估方看不到 truth 和历史错误提示。
13. 真人能够从报告区分公开复现、用户指定构建、内部回归、合成测试和实验性预览。
14. 无开放 P0、P1；任何未实现 task kind 不得在 Skill 中宣称支持。

v0.9.1 正式版额外要求真人独立生物学验收。不得覆盖或重新上传同版本号的 v0.9.0 包。

## 15. 开发交付物

开发完成时必须提供：

1. 架构决策记录，说明 ConstructionTask、专用 planner、三层验证和单一闸门。
2. ConstructionTask v1 schema 与迁移说明。
3. task kind 注册表及每类必填字段。
4. 统一 runtime、validator 和 authoritative gate。
5. S01、S05、S06、S08 修复前后证据。
6. 证据印章和 truth 治理实现。
7. 精简后的 SKILL.md 与按任务拆分的 references。
8. 全量测试和发布门禁报告。
9. 人类可读的生物学验收报告。
10. v0.9.1 变更日志，明确说明 v0.9.0 的架构缺陷及修复范围。

## 16. 完成定义

本任务不是以“新增 schema”“测试通过”或“修复 S06”作为完成标准。

完成必须同时证明：

```text
LLM 的语义没有被低效关键词解析器丢失
生物学决定没有被危险默认值替代
每类任务在计算前具有完整显式契约
所有序列由确定性工具生成
错误计划无法写出权威产物
验证覆盖文件、计算和用户目标
证据等级贯穿输入到交付
历史事故在公共入口稳定回归
正式发布声明与实际支持范围一致
```

任何一项缺失，架构恢复未完成。
