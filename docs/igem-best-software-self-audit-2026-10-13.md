# iGEM Best Software 自查与公开内容审计

核查日期：2026-10-13。源码快照：开发分支 `codex/crispr-skill-fixes-20261012`，提交 `4536bd77b1d24d10d5bdd3338dc7c959b8db9c0b`。本报告是日期审计，产品契约、安装方法和比赛规则仍由原有文档负责。

结论：源码、文档、公共入口回归和 CI 有证据；跨项目效用、新用户易用性、隔离陌生题成绩及湿实验效果仍缺足够证据。官方 iGEM GitLab 已有候选源码和成功流水线，但快照使用 Core 2.2.2，没有本轮 Core 2.2.4 修复。公开内容中有许可待核实的外源 DNA、参考图、个人路径和未发布稿件。未确认真实凭据，也未发现所提供用户源 DNA 的完整文件或完整序列匹配；这个结果不能排除片段、衍生构建或其他用户材料。

## 范围与判定依据

原状态：旧比赛文档仍写官方仓库只有模板；部分外部素材虽从发行包排除，仍存在于公开 Git 中；历史测试数量与当前环境也不同。它们不足以证明当前提交状态、完整公开权属或本版通过情况。依据来自实际源码、当前公开远端、对应提交的执行记录及官方要求，不按样例身份豁免，也不把声明当验收结果。

本轮只读代码、已跟踪文件和本地可达 Git 历史；仅新增本报告及开发文档路由。不修代码、不删除文件、不改写历史、不操作 `main`，不代团队填写表单或发布 Wiki。

2026 官方 Best Software 资格包括文档、OSI 批准许可、专属 iGEM GitLab 源码；Software & AI Village 不参评，标准 Wiki 路径为 `/software`。六个评审维度是标准兼容、验证、其他项目价值、外部集成、易用性及可维护文档。SBOL 是标准示例，不是强制新增功能。实验、测试数据和 benchmark 都可支撑验证，仍须限定证据范围。[官方评审标准](https://competition.igem.org/judging/special-prizes)

Software 交付要求还包括陌生读者可用的 README、安装运行及主结果复现、固定依赖、源码和许可证；仓库容量限制为 50 MB。AI 使用需披露模型、数据来源、评估与限制。CI/CD 有官方建议，不要求为此增加新平台。[Software 要求](https://teams.igem.org/go/deliverables/software/requirements)

普通 HTTP 页面是 JavaScript 外壳。本次另核对官方正在部署的 Software/Awards 页面代码，及官方 GitLab 的公开 tree、README、SOURCE.json、提交和流水线 API。没有把只取得页面外壳算内容验证。日期抓取和原始执行回执保留在仓库外，未上传用户序列。

## 逐项证据

“有证据”指列出的事实可核查；“薄弱”指范围有限；“缺失”指本次没有找到相应验收证据。此表不预测获奖分数。

| 项目 | 有证据，仓库位置 | 薄弱或缺失 |
|---|---|---|
| 文档及可维护性，BS6 | [开发路由](README.md)、[架构](architecture.md)、[Core spec](../specs/core-skill.md)、[Toolkit spec](../specs/genome-revival-toolkit.md)、[Core 入口](../snapgene-dna-design/SKILL.md)、[Toolkit 入口](../genome-revival-toolkit/SKILL.md)、[工具签名](../snapgene-dna-design/references/recipes.md) | 文档体系存在，不等于新用户已能理解。Toolkit README 和架构中的旧版本文字仍需和实际构包版本核对；本轮不修改它们。 |
| 开源许可 | [根 LICENSE](../LICENSE)、[Core LICENSE](../snapgene-dna-design/LICENSE)、[Toolkit LICENSE](../genome-revival-toolkit/LICENSE)、[第三方 notice](../snapgene-dna-design/THIRD_PARTY_NOTICE.md)、[归属清单](attribution.md) | MIT 是 [OSI 批准许可](https://opensource.org/license/mit)。原代码许可不覆盖外部 DNA、图像、模型和依赖；部分素材发布权及版权署名仍待团队确认。 |
| 安装说明 | [Core 安装](../snapgene-dna-design/docs/installation.md)、[快速开始](../snapgene-dna-design/docs/quick-start.md)、[Toolkit README](../genome-revival-toolkit/README.md)、[排障](../snapgene-dna-design/docs/troubleshooting.md)、[环境检查](../snapgene-dna-design/scripts/check_env.py) | Python、依赖、解释器和可选后端条件有说明。缺少未参与开发的新用户从干净环境独立安装并完成任务的当前记录。基础安装不代表全部可选模型、OpenCL、网络或桌面程序可用。 |
| 可用性，BS5 | [公共 Core 示例](../snapgene-dna-design/examples/execution_workflow.py)、[Toolkit 字段说明](../genome-revival-toolkit/references/workflows.md)、[公共 CLI 回归](../tests/test_genome_revival_public.py)、[失败与证据限制](igem/external-evidence-needed.md) | 原真实案例推动了修复；开发者回归和一次自然宿主 pilot 不能替代独立真人易用性测试。缺少跨研究者完成率、帮助次数及错误理解记录。 |
| 测试，BS2 | [测试方法](testing.md)、[完整 runner](../tools/run_test_suite.py)、[CI 配置](../.github/workflows/test.yml)、[合成 CRISPR 正反例](../tests/test_crispr_synthetic_fixture.py)、[Toolkit 文件关系正反例](../tests/test_toolkit_file_relations.py)、[逐项 skip 审计](archive/reviews/crispr-skip-audit-2026-10-13.md) | 本轮完整本地执行 1245 项，1227 通过、18 跳过、0 失败/错误，真实 Primer3 门槛通过。跳过均单列，不算通过；完整可选后端覆盖没有成立。历史 54/54 或旧测试总数不是本版成绩。 |
| 可复现，BS6 | [精确受测依赖](../snapgene-dna-design/requirements-tested.txt)、[Core 构包](../tools/build_release.py)、[Toolkit 构包](../tools/build_toolkit.py)、[Toolkit 版本记录测试](../tests/test_genome_revival_package.py)、[当前合成构造说明](../tests/crispr_synthetic_fixture.py) | 固定种子、构造预期、清单及公开命令可复查。支持范围依赖文件使用版本区间；精确依赖快照来自特定 Windows 环境。未本轮重新证明所有平台、后端及正式发布包。 |
| 格式及标准兼容，BS1 | [序列元数据编码](../snapgene-dna-design/core/io/molecule_codec.py)、[文件读写](../snapgene-dna-design/core/tools/snapgene_io.py)、[rich 格式夹具](../tools/build_rich_fixtures.py)、[真实文件回读回归](../tests/test_grna_cassette.py) | 有 GenBank、FASTA、SnapGene native 的程序读写证据，含环状坐标、注释和 UTF-8。未找到 SBOL 互操作验收或所有桌面版本完整 round-trip 证明，不将程序解析等同桌面兼容。 |
| 外部集成，BS4 | [Core 注册工具](../snapgene-dna-design/core/tools/registry.py)、[单步 CLI](../snapgene-dna-design/scripts/run_step.py)、[Toolkit CLI](../genome-revival-toolkit/scripts/run_toolkit.py)、[实际 Primer3 回归](../tests/test_preparation_primer_locations.py)、[网络隐私契约](../snapgene-dna-design/references/privacy-and-consent.md) | 公共 API/CLI 和同源 Core 复用有代码及运行证据。可选服务成功需各自真实环境；不是所有集成都已执行。没有独立团队接入现有系统的效果证据。 |
| 其他项目价值，BS3 | [Core 用途](../snapgene-dna-design/README.md)、[通用 gRNA spec](../specs/core-skill.md)、[通用合成回归](../tests/test_grna_evaluation.py)、[性能入口](../benchmarks/runtime.py) | 实现不依赖特定质粒名，独立构造输入说明可泛化的机制。缺少未参与开发团队的真实采用，以及冻结条件下与现有解决方案的当前对照。不能据候选数量或单测通过声称普遍可靠。 |
| 与参赛项目关联 | [Toolkit 三 Kit](../genome-revival-toolkit/README.md)、[Project Context 样式](../genome-revival-toolkit/assets/project-context-template.json)、[科学范围 spec](../specs/genome-revival-toolkit.md)、Wiki 草稿（原稿曾公开，现已移出当前树并完整私有备份；历史仍可见）、实施证据与未决事项（原稿曾公开，现已移出当前树并完整私有备份；历史仍可见） | Genome Revival 的供体构建、指定区域鉴别和提交观察比较有明确使用场景。计算制备、局部 PCR 及观察整理不证明全基因组消除或复活。缺少本系统产物的湿实验功能验证和独立生物学专家复核。 |
| 可信的验证证据，BS2 | [工程评分边界](question-bank/scoring-v0.1.md)、[本轮实施及原失败处置](archive/plans/queued-fixtures-and-trace-2026-10-13.md)、[预备路线回归](../tests/test_grna_preparation.py)、[文件关系实现](../snapgene-dna-design/evidence_trace/projection.py) | 预期由输入构造决定，实际公共入口和生成文件可核查；Tm 有独立公开方法交叉计算。已知题、独立工程输入、人工辅助及隔离陌生评测分开。本轮没有陌生题成功率、湿实验、科学因果或真人报告理解证据。 |

## 当前远端和执行证据

| 记录 | 实际状态与范围 |
|---|---|
| 任务 4，`794d3c76ba319c65ba2914f5b8a9df7ade4a6b1e` | [六环境 CI 成功](https://github.com/zoehanke/snapgene-dna-design/actions/runs/38306429938)。两种固定种子，14 次实际 public run_step 读取独立生成 native 文件；五类失败与正确对照及重复 PCR 结合边界。属于工程回归。 |
| 任务 5，`4536bd77b1d24d10d5bdd3338dc7c959b8db9c0b` | [本提交六环境 CI 成功](https://github.com/zoehanke/snapgene-dna-design/actions/runs/38309539547)。各环境运行 1245 项，Windows 每环境 1222 通过/23 跳过，Ubuntu 每环境 1221 通过/24 跳过，均无失败/错误；环境 skip 不算通过。真实 Toolkit Construct 13 步，640 bp 供体与独立构造逐位相等；2 条程序文件关系绑定 6 条哈希事实，不匹配反例 0 条。只证明观察到的输出和声明输入字节相同，不证明物理使用或科学因果。 |
| 官方 GitLab `main`，`0c764c6ce5c7b3e294179af5b59e917c9663dc51` | [当前 README](https://gitlab.igem.org/2026/software/tianjin/igem-tianjin2026/-/blob/0c764c6ce5c7b3e294179af5b59e917c9663dc51/README.md)及根目录有源码、tests、tools、LICENSE、`.gitlab-ci.yml`；[流水线 748177 成功](https://gitlab.igem.org/2026/software/tianjin/igem-tianjin2026/-/pipelines/748177)，核对了同一 SHA。 |
| 官方源码版本 | [SOURCE.json](https://gitlab.igem.org/2026/software/tianjin/igem-tianjin2026/-/blob/0c764c6ce5c7b3e294179af5b59e917c9663dc51/SOURCE.json)记录 Toolkit 0.1.0、Core 2.2.2、Trace 0.3.3，候选源码来自 `9bc9aa3`。本轮开发修复尚未包含；官方流水线不是本轮开发提交的 CI。 |

[旧官方要求 O11](igem/official-requirements.md)、[GitLab 交接](igem/gitlab-migration.md)和[提交检查表](igem/submission-checklist.md)的“尚无源码/远端 CI”描述已有反证。本轮只记录日期状态，不修改这些文件。官方源码存在及流水线成功，也不等于奖项自荐、Attributions、Wiki `/software` 发布、版权审定或正式冻结提交已完成。这些回执本轮未取得；团队 Village 当前状态及官方仓库实际容量也未重新确认。

## 已提交文件与 Git 历史的公开风险

只读扫描 `git rev-list --objects --all` 中本地可达对象，再用 `git cat-file` 读取内容。快照包含 152 个可达提交、2080 个唯一 blob、591 个当前跟踪文件，blob 解压总量 33,165,832 字节。该数不是 GitLab 仓库存储容量，也不是全部远端、dangling 或已经删除的历史。

检查文本凭据模式、绝对路径、18 个 DNA 文件 blob 版本；对已提供用户源文件做完整字节及规范化完整 DNA 序列比较；结合归属清单人工检查外部图像和稿件。仅记录类型、文件位置和提交，不公开凭据候选值、私人 DNA、材料哈希或个人路径原文。

| 类别 | 已核查发现及具体位置 | 结论和未解决事项 |
|---|---|---|
| 所提供用户源 DNA | 8 个源文件、4 个唯一指纹的完整字节匹配 0，规范化完整序列匹配 0；[本轮 fixture 生成器](../tests/crispr_synthetic_fixture.py)没有私有文件读取、材料名称或材料哈希依赖 | 未确认原用户源文件入库。片段、变更后的成品、代码/日志嵌入序列及其他用户材料不被这项完整匹配排除。 |
| 外源 DNA 许可待核实 | 当前跟踪 tests/data/pBP-eGFP.gb（原内部定位，未随当前公开树分发；不是可点击文件），其公开来源及待核实权利已记于 [归属清单](attribution.md)；历史首次引入 `16b8fe4`。另有 [synthetic/rich 来源生成器](../tools/build_rich_fixtures.py)及对应夹具 | 已知外源文件仍在公共源码，不能因发行包排除而称没有公开。未把它误报为上述用户 DNA。需要素材权利审定；本轮不删除或代授权。 |
| 用户提供的参考图 | 当前跟踪 evidence-trace-report-reference.png（原公开资料，已移出当前树；历史仍可见），许可状态见 [归属清单](attribution.md)；首次引入 `30b5c9c`，当前路径整理于 `05ff2ee` | “不随发行包”没有解决 Git 公共可见性。发布授权未确认；没有删除、改图或改历史。 |
| 本地及个人绝对路径 | 291 条候选为 blob 版本与行的命中，涉及 40 个路径，不是 291 个隐私泄露。[旧本地设置](archive/development/LOCAL-SETUP.md)、[旧 reviewer guide](archive/development/REVIEWER-GUIDE.md)、[旧架构草案](archive/architecture/ARCHITECTURE-RECOVERY-DEVELOPMENT-SPEC.md)、[构建闭环记录](archive/plans/actual-execution-closure-v2.2.1.md)有本地目录；历史 `docs/igem/assets/verification-summary.json`、`docs/igem/project-software-handoff.md` 在 `5c6e06f`、`cf50000` 可达 | 用户目录、工作区和测试材料路径需逐项审查。通用 `Program Files` 发现路径或刻意构造的 Windows 测试字符串另属运行逻辑，不一概列为泄露。报告不重复个人用户名和完整路径。 |
| 凭据 | 9 个规则命中来自历史 SKILL 示例和 [旧可用性计划](archive/plans/real-task-usability-v2.0.2.md)中的 `task-…` 名称，匹配到其中的 `sk-` 子串；已逐项核对上下文 | 这 9 项为误报，未确认真实 API token、私钥或密码。规则覆盖有限，未进行账号有效性测试；不据此保证全部历史无秘密。 |
| 未发布文稿及项目材料 | Software Wiki draft（原稿曾公开，现已移出当前树并完整私有备份；历史仍可见）、安全阶段阅读稿（原稿曾公开，现已移出当前树并完整私有备份；历史仍可见）、项目实施记录（原稿曾公开，现已移出当前树并完整私有备份；历史仍可见）；历史 `docs/igem/project-software-handoff.md` | 草稿明确未发布或需审定，但公共仓库已能阅读。科研内容、发表时间、团队同意和外部贡献须负责人确认；“draft”标签不提供访问隔离。 |
| 评测答案公开 | candidate tasks（原公开资料，已移出当前树；历史仍可见）、human answer key（原公开资料，已移出当前树；历史仍可见）当前已跟踪。本轮只核查路径和公开状态，没有据答案评测程序 | 不是凭据或已确认私人 DNA；但这些题目和答案不能再作未接触的 heldout 成绩。未来陌生评测须独立管理。 |

发行排除由 [Core builder](../tools/build_release.py)和[归属清单](attribution.md)提供可核查依据；它只管生成的包，不改变 Git 历史。公开风险处置属于后续明确授权事项，本次没有删除素材、替换历史、撤销凭据或更改账号设置。

## 验证与未做事项

本次报告核对官方当前页面内容、公开 GitLab 精确提交与流水线、本地当前文件和可达 Git 对象；文档提交另检查链接、UTF-8、Git 差异和自己的精确 CI。不为文档改动重复生物回归，不借旧版 CI 作为新提交结论。

没有执行湿实验、独立真人试用、隔离陌生题评测或专家科学审定；没有重做全部外部后端、所有发行包及官方仓库完整历史扫描。历史自动检查没有覆盖未知用户序列片段、所有压缩/二进制载荷及未获取对象。没有修改科学范围、代码、阅读界面、main、原用户材料或原失败记录。
