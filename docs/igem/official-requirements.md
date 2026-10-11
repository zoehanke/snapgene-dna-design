# iGEM 2026 官方要求核对

核对日期：2026-10-11。本文件管理官方规则，版本与提交操作见[GitLab交接](gitlab-migration.md)。依据当前官方页面、部署中的公开页面代码、匿名团队/日历/GitLab API；未访问个人账号。抓取和 SHA-256 保存在本机审查目录的 `igem/SOURCE-INDEX.json`。普通页面抓取仅得到 JavaScript 外壳，失败的浏览器渲染不计为验证。以下为转述，不是官方规则副本。

## 已核实要求

| 编号 | 类型 | 要求与当前判断 | 官方来源 |
|---|---|---|---|
| O1 | 参奖资格 | Best Software 要求有文档、OSI 批准许可和专属 iGEM GitLab 源码 | [Best Software](https://competition.igem.org/judging/awards/special) |
| O2 | 参奖资格 | Software & AI Village 不参评；团队6404/Tianjin公开记录为 Foundational Advance，只证明不受这项排除 | [奖项](https://competition.igem.org/judging/awards/special)、[团队](https://teams.igem.org/6404) |
| O3 | Wiki | 评审标准页为 `/software`，准备路径 `https://2026.igem.wiki/tianjin/software` | [奖项](https://competition.igem.org/judging/awards/special) |
| O4 | 正式交付 | 最多五个软件仓库；Attributions Form 必填，表单直接在团队页展示，不要求 Wiki iframe | [Software](https://teams.igem.org/go/deliverables/software/requirements)、[Attributions](https://teams.igem.org/go/deliverables/attributions/requirements) |
| O5 | 官方截止 | Wiki、Judging、Attributions、Registry、Software：10月21日15:00 UTC，北京23:00；Presentation Video：10月28日同一时间 | [2026日历](https://competition.igem.org/calendar) |
| O6 | 独立交付 | 软件不能替代其他必需表单、视频或评审活动；实际完成状态需逐项确认 | [Deliverables](https://competition.igem.org/deliverables) |
| O7 | 许可 | MIT 为 OSI 批准许可；原代码许可不自动覆盖外部序列、图片、模型和依赖 | [OSI MIT](https://opensource.org/license/mit) |
| O8 | 实验边界 | AI计算、局部检测或 Trace 完整不能替代实验事实、安全审核及人的责任 | [团队AI政策](https://igem.org/legal?tab=ai-policy-teams)、[安全政策](https://responsibility.igem.org/safety-policies) |
| O9 | 安全日程 | 最终 Project Safety Form 10月7日、Check-In 9月23日截止，均15:00 UTC；日期已过，本轮未核查团队提交/批准回执 | [2026日历](https://competition.igem.org/calendar) |
| O10 | 软件内容 | 每仓库有说明用途/用户/安装/运行/主结果复现的 README、OSI LICENSE、可复现构建运行步骤和固定依赖；提交源码，不用编译二进制代替；Git仓库小于50MB | [Software要求](https://teams.igem.org/go/deliverables/software/requirements) |
| O11 | 源码位置 | 本队官方模板要求全部软件源码进入专属仓库 `main`，Wiki Freeze 时自动生成评审 Release。当前公开 main 仍是模板，不能称已提交本软件 | [本队官方模板](https://gitlab.igem.org/2026/software/tianjin/igem-tianjin2026/-/blob/main/README.md) |
| O12 | Wiki内容 | 静态站点由 GitLab CI 构建，固定依赖；运行资产托管在 iGEM，视频/音频用 Video Universe；页脚保留 CC-BY 4.0 和 Wiki源码链接；不引入外部CDN、字体/API运行请求 | [Wiki要求](https://teams.igem.org/go/deliverables/wiki/requirements) |
| O13 | AI与证据 | README披露模型、已知训练/微调来源、评估和限制；Attributions单列AI用途及人的核查。科研内容来自团队真实工作；不能把AI生成/修改的图像当实验或计算证据 | [Software](https://teams.igem.org/go/deliverables/software/requirements)、[Wiki](https://teams.igem.org/go/deliverables/wiki/requirements)、[Attributions](https://teams.igem.org/go/deliverables/attributions/requirements) |
| O14 | 人工提交 | 官方账号、声明、选项、表单和最终提交由负责的真人执行，AI仅辅助准备。不能因后续写入授权而让AI代操作iGEM个人账号 | [通用AI政策§2.2](https://igem.org/legal?tab=ai-policy) |

Software交付概览另列 CI/CD 配置；详细要求页推荐持续测试，未规定必须 Docker 或某种语言。准备实际可用的 GitLab CI，不把 GitHub CI 称为 GitLab CI。

## 评审维度与建议

Best Software：**BS1** 标准/格式兼容；**BS2** 验证；**BS3** 其他项目价值；**BS4** 外部集成；**BS5** 易用；**BS6** 可维护与可复现。SBOL 是示例，未要求必须实现；实验、测试数据和 benchmarking 均可提供验证证据，不等于必须增加湿实验或大型平台。[评审来源](https://competition.igem.org/judging/awards/special)

官方建议 Apache-2.0，MIT 同样可接受；大型数据/模型/媒体用长期数据归档，不塞进源码仓库；保留清晰历史、限制和复现说明。建议不是另造模块或换许可证的任务。[Software资源](https://teams.igem.org/go/deliverables/software/requirements)

## 团队状态与待人工事项

公开API已确认团队6404/Tianjin、2026、accepted、Foundational Advance，并列出：

- 专属软件：[igem-tianjin2026](https://gitlab.igem.org/2026/software/tianjin/igem-tianjin2026)。只读 main 为 `241b12fcad038e9f56fac563438f717f38e40644`，根目录仅 `.claude/`、`CLAUDE.md`、`LICENSE`、`README.md`。
- Wiki源码：[2026/tianjin](https://gitlab.igem.org/2026/tianjin)；站点：[Tianjin Wiki](https://2026.igem.wiki/tianjin)。两者不等于软件仓库。

**未核实：**个人写权限、正式表单保存/提交、安全批准、奖项自荐及最终回执。未推送或部署本轮 Toolkit。负责人需要审定科学事实、作者/外部资产权属和AI披露，再亲自完成官方操作及回执核对。

本轮本地技术准备已有9bc9aa3冻结包、实际工程/独立包及自然宿主主候选证据；额外宿主文稿和原请求摘要边界如实保留。源码r2已从新本地Git目录运行原套件与builder，额外资源skip未改门限。它们不替代正式远端main、Linux/GitLab CI、权属批准或官方提交回执。具体状态由[GitLab交接](gitlab-migration.md)和[Wiki证据段](software-wiki-draft.md)拥有。

10月15日代码冻结、16日上传、17日内部验收是本队内部计划，不能表述成iGEM官方截止。本轮本地候选与验证见[实施记录](../archive/plans/genome-revival-toolkit-v0.1.md)；后续授权看[当前交接](../development-plans/README.md)。
