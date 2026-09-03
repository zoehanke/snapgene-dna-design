# Baseline status

Current development baseline: **`0.9.1-dev2` (3+1 Tier Architecture Reconstruction)**.

### Reconstruction Progress Summary (Current State)
1. **阶段 0：基线环境与回归验证**：
   - 修复 Dam/Dcm 甲基化偏移与 Golden Gate 测试用例间距；
   - 基础 21 个单元测试全绿。
2. **阶段 1：28 个 Tier 1 原子工具库（Hands & Feet）**：
   - 全面拆解复合黑盒操作，打造纯粹的物理/数学原语（内切、退火、二聚体扫描、同义突变推荐、读码框校验等）；
   - 31 个原子工具单元测试通过。
3. **阶段 2：7 大全景黄金实验 SOP 配方库（Standard Recipes）**：
   - 杜绝 AI“突发奇想/丢三落四”，严格溯源国际经典手册（CSHL《分子克隆》第 4 版、Nature Protocols、Nature Methods、ACS Synth Biol、NEB 等）；
   - 实现 7 大 SOP：双酶切、Gibson、Golden Gate、CRISPR HDR、定点突变 (SDM)、蛋白表达标签工程、分子质检与验证引物布局；
   - 8 个配方单元测试通过，全局 42 个测试全绿，95 个 smoke 测试通过。
4. **阶段 3：生物学客观底线自检清单（Tier 3: 10 Fundamental Guardrails）**：【已完成】
   - 实现 10 项不可逾越的物理/生物学第一性原理底线检查（BIO-01 ~ BIO-10），包含读码框、终止密码子、酶切冲突、特征方向、CRISPR 防二次切割、U6 Pol III 终止、PCR 引物二聚体、质粒维持要素 (ori+抗性)、Dam/Dcm 甲基化完全阻断、极端长反向重复与发夹。
5. **阶段 4：实验室经验规则轻量调用（Tier 4: Experience Rules）**：【已完成】
   - 激活 33 条人工审核湿实验经验库 (`rules/preloaded_experience_rules.json`)，编写轻量检索器 `core/tools/experience_helper.py`。
6. **阶段 5：去过度工程化说明书重写（SKILL.md）**：【已完成】
   - 彻底废除死锁式自制调度器，全面转向自然语言驱动的 3+1 分层协作范式。
7. **阶段 6：真实科研复合案例端到端实操验证与桌面真机验收（E2E Benchmarks）**：【已完成】
   - 复合案例 A (Gibson 融合表达载体 E2E 全流程)：载体双酶切 + C 端 6xHis 标签与同源臂引入 + 重叠组装模拟 + 坐标重映射 + Tier 3 自检 + SnapGene 二进制交付。
   - 复合案例 B (CRISPR HDR 精准敲入 E2E 全流程)：靶点扫描 + U6 退火引物 + HDR 供体设计 (PAM 同义沉默阻断复切) + 跨接缝质检引物布局 + Tier 3 自检。
   - 桌面真机验收：调用 Windows 原生桌面 `D:\SnapGene\SnapGene.exe` 打开产物并核实二进制文件完备性。
   - 全套 594 个单元测试全绿 (0 fail, 0 error)，95 个核心 smoke 测试全绿。


## Local environment note

`quick_validate.py` passes in the current checkout. Full smoke and environment
checks were not counted as passing: the active Anaconda Python 3.14 environment
is missing `snapgene_reader`, `sgffp`, and `jsonschema`, and `check_env.py`
currently exits with an internal `TypeError` after reporting those missing
dependencies. Install the pinned requirements and repair that checker before
using it as release evidence.
