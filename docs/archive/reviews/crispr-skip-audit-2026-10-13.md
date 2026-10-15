# 原 21 项跳过测试处置

2026-10-13，Core 2.2.4 的开发回归。基线完整公共套件实际捕获 21 项跳过，原始原因、日志和原始输入保留在仓库外。本清单不把跳过当通过，不替代独立陌生题评测。

原原因对应实际 unittest 文本：

| 代号 | 原原因 |
|---|---|
| A | `academic SnapGene fixtures are not present` |
| B | `fixtures/pDONR201.dna not present (academic-only)` |
| C | `Academic golden fixtures not present` |
| D | `set CAS_OFFINDER_EXE to a real cas-offinder binary` |
| E | `set CAS_OFFINDER_EXE_V3 to Cas-OFFinder 3.x` |
| F | `set SNAPGENE_RUN_REAL_MODELS=1 for real model gates` |
| G | `set SNAPGENE_RUN_REAL_MODELS=1` |
| H | `set SNAPGENE_RUN_ONLINE=1 for live NCBI queries` |
| I | `Gateway academic fixtures not packaged` |

| # | 完整测试 ID | 原原因 | 分类、条件与处置 | 本轮结果 |
|---|---|---|---|---|
| 1 | `test_license_real.RealLicenseHashCheckerTests.test_real_restricted_file_is_detected_even_when_renamed` | A | 环境缺外部 academic 文件；需要合法提供的原文件核对受限哈希。保留原案例，不用合成文件冒充 | 继续跳过 |
| 2 | `test_smoke_academic.SmokeAcademicTests.test_smoke_academic_passes` | A | 环境缺原 pDONR201。另发现 wrapper 和 smoke 脚本查项目旧根目录，已统一为 Skill 的 fixtures 目录；源材料与旧预期保留 | 定位修复；材料仍缺，继续跳过 |
| 3 | `test_v03.ContractAndRoundTripTests.test_internal_snapgene_genbank_roundtrip` | B | 环境缺原 pDONR201；合法补齐原文件后运行内部真实格式回读，不能拿别的文件代替此原案例 | 继续跳过 |
| 4 | `test_v04.FailureContractTests.test_roundtrip_reports_and_can_require_qualifier_equality` | B | 环境缺原 pDONR201；内部序列/限定符严格检查保留，不要求桌面程序 | 继续跳过 |
| 5 | `test_v04.GoldenGatewayTests.test_bp_matches_committed_pENTR_EmGFP_fixture` | C | 环境缺 donor/attB 输入及独立 golden 成品；合法补齐后比较真实公共 BP 输出 | 继续跳过 |
| 6 | `test_v04.GoldenGatewayTests.test_gateway_duplicate_att_site_is_rejected` | C | 环境缺原 entry/destination；需要从原 entry 复制 attL1 的失败案例，拒绝阈值不变 | 继续跳过 |
| 7 | `test_v04.GoldenGatewayTests.test_gateway_rejects_misordered_att_pair_instead_of_find_first` | C | 环境缺原 pENTR-D-TOPO/pDEST40；保留原线性材料重注释的次序错误案例 | 继续跳过 |
| 8 | `test_v04.GoldenGatewayTests.test_gateway_requires_explicit_topology` | C | 环境缺 attB/pENTR-D-TOPO/pDEST40；完整方法含外部材料的拓扑拒绝检查，不能只运行其中合成分支就算通过 | 继续跳过 |
| 9 | `test_v04.GoldenGatewayTests.test_lr_matches_committed_pDEST_EmGFP_fixture` | C | 环境缺 entry/destination 与独立 LR golden；保留严格成品及限定符比较 | 继续跳过 |
| 10 | `test_v04.GoldenTATests.test_ta_matches_committed_pGEM_T_fixture_with_explicit_premises` | C | 环境缺 pGEM-T/insert/golden；需要原真实材料及物理端前提，不删除检查 | 继续跳过 |
| 11 | `test_v04.GoldenTATests.test_ta_requires_explicit_end_premises` | C | 环境缺原 pGEM-T/insert；原不声明物理端的失败案例保留 | 继续跳过 |
| 12 | `test_v04.GoldenTATests.test_ta_requires_vector_cut` | C | 环境缺原 pGEM-T/insert；原缺切点拒绝检查保留 | 继续跳过 |
| 13 | `test_v06.SchemaContractTests.test_schemas_validate_real_outputs` | B | 环境缺原 pDONR201 roundtrip 分支；前面的合成分支执行不代表整个方法通过，仍报告 skip | 继续跳过 |
| 14 | `test_v08_dev3.RealCasOffinderIntegrationTests.test_real_binary_end_to_end` | D | 环境未配置二进制，PATH 及实际 adapter.detect 未检出。现在可用 CAS_OFFINDER_EXE 或 PATH 自动发现；还需可用 OpenCL | 继续跳过，未实测二进制 |
| 15 | `test_v08_dev3.RealCasOffinderIntegrationTests.test_real_binary_end_to_end_non_ascii_path` | D | 同上；中文路径和真实二进制输出检查完整保留，不用 mock 当集成通过 | 继续跳过，未实测二进制 |
| 16 | `test_v08_dev3.RealCasOffinderIntegrationTests.test_real_binary_v3_bulge` | E | 环境未配置 CAS_OFFINDER_EXE_V3；须为支持 bulge 的 3.x 和可用 OpenCL，不能用普通 2.x 替代 | 继续跳过，未实测 bulge |
| 17 | `test_v08_dev3.RealModelTests.test_azimuth_real_prediction` | F | 无必要的纯开关跳过：本机依赖与公开模型在。改为依赖/权重齐全自动执行；显式旧开关可强制运行，缺资源会失败。原参考数值和精度未改 | 无开关实跑通过 |
| 18 | `test_v08_dev3.RealModelTests.test_deepcpf1_matches_bioconductor_reference` | F | 同类无必要跳过。真实序列模型和 chromatin 模型均与原独立 Bioconductor 参考数值比较；无依赖时明确列出缺项 | 无开关实跑通过 |
| 19 | `test_v08_gate_coverage.AdditionalCoverageTests.test_guide_scoring_real_available_branch` | G | 同类无必要跳过。两后端资源齐全自动执行，原真实评分路径及所有拒绝断言保留 | 无开关实跑通过 |
| 20 | `test_v09.M6OnlineSourceTests.test_live_ncbi_search` | H | 合理的外部服务隔离条件，不是本机没有网络。默认套件保持离线；SNAPGENE_RUN_ONLINE=1 执行真实 NCBI，请求仅为公开 EGFP 关键词，不上传用户 DNA | 显式联网实跑通过；默认仍显式跳过 |
| 21 | `test_v09_agent.AgentE2ETests.test_gateway_original_external_material` | I | 环境缺原 entry/destination；需要合法提供的原材料跑公共旧宿主链，不能拿合成宿主例当原案例成功 | 继续跳过 |

14 项外部材料继续保留，3 项 Cas-OFFinder 未实测，3 项无必要模型开关已修，1 项外部联网集成实跑通过。模型真实权重和参考数值不改；没有下载或提交用户 DNA、academic 文件，也未安装额外 CI 模型依赖以改变缺失事实。PATH 未检出不等于证明整台机器绝无二进制；本轮只验证公开探测与已配置位置。

Golden类原setUp统一要求BP材料，LR案例即使有自己的素材也可能被无关BP文件缺失挡住。改为各方法检查自身输入及独立golden文件，原八项案例、断言与精度全部保留，缺少的具体文件进入skip原因；当前自身素材仍缺，继续跳过。18项v04公共回归中9项通过、9项跳过；独立素材可用性用例证明只列缺少文件，文件存在时执行原断言，不能借门槛变成PASS。这是资源定位验证，不是外源生物学集成成功。

实际完整套件以本轮公共 `tools/run_test_suite.py --report-json` 的 UTF-8 文件为准；计数与精确 CI 记录见[本轮计划](../plans/crispr-queued-fixes-2026-10-13.md)，提交后自己的回执留仓库外。默认离线与显式联网的 skip 数分别报告；本机默认18项，启用联网且模型资源齐全时17项，均不能计作通过。CI缺少可选依赖时须依据实际报告另计。

新增独立小套件核查真实公开 runner：成功、中文原因 skip、同个 case 的多次子测试失败、class setup 错误及必需 Primer3 skip。JSON/终端分别列 run、passed、skipped、failures、errors；passed 仅由 unittest 的实际 addSuccess 事件计数，不用 run 减记录数冒充。子测试与 class setup 可产生多个 outcome 记录，文件明确计数单位。必需 Primer3 skip 仍退出 1；明确 opt-out 仍标非发布诊断。

首次显式联网完整套件：1238项，1221通过、17跳过、0失败。随后新增逐项素材门槛及第四项边界用例，另跑最终默认离线完整套件；两份实际JSON与日志分别保留，不把不同快照混成重复成功或选择性成绩。

最终默认离线完整套件：1239项，1221通过、18跳过、0失败。真实Primer3门槛通过；三个模型无flag实际运行，联网案例此前单独通过。实际UTF-8 JSON中的18个ID恰为原21个中移除三项模型，原因按真实资源更新。未提供的素材/二进制不补为通过。
