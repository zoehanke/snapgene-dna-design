# ConstructionTask v1 字段与语义

JSON schema：`schemas/construction-task-v1.json`。公共入口：`core.validate_construction_task` / `plan` / `execute` / `validate` / `finalize`。

## 顶层字段

| 字段 | 要求 | 说明 |
|---|---|---|
| schema_version | `construction-task-v1` | 固定值 |
| task_id / revision | 必填 | 每次语义变化 revision+1 |
| mode | `exploration` / `formal` | 只有 formal 可通过 authoritative gate |
| task_kind | 必填 | 必须在 `core/registry.py` 注册 |
| sources[] | 至少 1 个 | 每源唯一 source_id 与唯一 role；必带证据印章 |
| operation | 按 task_kind | 见下表 |
| target | 按 task_kind | source_id + selection |
| product | 必填 | topology、formats、required/forbidden_components、expected_length |
| method_constraints / approvals / assumptions / provenance | 必填对象或数组 | approvals.user_confirmed_task 为 formal 交付必要条件 |

## source

- `role`：template / backbone / insert / replacement / donor_component / entry / destination / reference。
- `sha256`：允许缺省；程序从文件计算并回填；声称值与实际不符 → `SOURCE_HASH_MISMATCH`。
- `evidence.source_evidence_class`：必填五选一。
- `annotation_status`：reviewed / unreviewed / ambiguous / missing。

## 各 task_kind 的 operation 必填

- `component_amplification`：`homology_arms{left_arm,right_arm}` 可选；`target.selection` 必须 resolved。
- `plasmid_replace`：`replace{interval_0based[a,b), replacement_source_id, replacement_interval_0based}`。
- `plasmid_insert`：`insert{boundary_0based, insert_source_id, interval_0based}`。
- `point_mutation`：`mutations[{position_1based, ref, alt}]`；ref 必须与输入一致。
- `overlap_assembly`：`fragments[{source_id, interval_0based, order, strand?}]` + `overlap_length`。
- `protein_fusion`：`partner5{source_id, interval_0based, strand?}`、`partner3{...}`、`stop_policy stop|no-stop`、`linker{dna}` 可选、`translation_table` 可选（按 host 推导）。
- `integration_donor`：`homology_arms{left_arm, right_arm}`、`locus{source_id, interval_0based, strand}`；`target.selection` 必须 resolved；臂必须匹配座位侧翼。
- `gateway_recombination`：`reaction bp|lr`、`stop_policy`、lr 需 `entry_source_id+destination_source_id`，bp 需 `entry_source_id`（attB 插入片段）+`donor_vector_source_id`（attP 供体载体）。
- `restriction_ligation`：`vector_source_id`、`insert_source_id`、`vector_enzymes[1..2]`、`insert_enzymes` 可选（默认同 vector）、`orientation forward|reverse`；两酶切点不得跨原点。
- `hierarchical_assembly`：`stages[{stage_id, fragments[{source_id|stage_id, interval_0based?, order, strand?}], overlap_length, product_topology}]`；末级拓扑必须等于 `product.topology`。
- `crispr_editing`：`nuclease`、`target_interval_0based`、`guide_strategy{pam?, window_0based?}` 可选、`donor_strategy{donor_source_id?, replacement_interval_0based?, homology_arms?}` 可选。

## 方法成熟度与产物等级

- `method_maturity=validated` 的 kind 在三层验证全过后可进入 authoritative。
- `restriction_ligation` 与 `crispr_editing` 为 `experimental`：plan/execute/validate 正常执行，但整体结论为 `experimental-preview`，闸门以 `GATE_EXPERIMENTAL_METHOD` 拒绝 authoritative。
- 所有结果为序列级计算预测；湿实验结论必须由实验获得。

## 硬错误码

- `TASK_KIND_NOT_REGISTERED` / `TASK_KIND_NOT_IMPLEMENTED`
- `SOURCE_FILE_MISSING` / `SOURCE_HASH_MISMATCH` / `SOURCE_TOPOLOGY_MISMATCH`
- `COMPONENT_BOUNDARY_REQUIRED` / `WHOLE_TEMPLATE_SELECTED_FOR_COMPONENT`
- `REPLACE_INTERVAL_REQUIRED` / `REPLACEMENT_SOURCE_REQUIRED`
- `INSERT_BOUNDARY_REQUIRED` / `INSERT_INTERVAL_REQUIRED`
- `MUTATION_SPEC_REQUIRED` / `REFERENCE_RESIDUE_MISMATCH`
- `UNEXPECTED_VECTOR_BACKBONE_IN_DONOR`
- `GATE_REQUIRES_FORMAL_MODE` / `GATE_VALIDATION_FAILED` / `GATE_APPROVAL_MISSING` / `GATE_HASH_CHAIN_BROKEN` / `GATE_UNRESOLVED_ASSUMPTION`

所有错误对象包含 `status`、`error_code`、`missing_fields`、`questions`、`details` 与 `write_authoritative_artifact:false`。
