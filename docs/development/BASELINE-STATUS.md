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
4. **阶段 3：生物学客观底线清单（Tier 3: Guardrails）**：【就绪待办】
   - 扩展 `quick_biological_sanity_check`，实现 PAM 复切、Pol III 终止、引物二聚体等纯客观事实报警。

## Local environment note

`quick_validate.py` passes in the current checkout. Full smoke and environment
checks were not counted as passing: the active Anaconda Python 3.14 environment
is missing `snapgene_reader`, `sgffp`, and `jsonschema`, and `check_env.py`
currently exits with an internal `TypeError` after reporting those missing
dependencies. Install the pinned requirements and repair that checker before
using it as release evidence.
