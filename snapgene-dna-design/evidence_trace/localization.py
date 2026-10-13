"""Localize shipped presentation text; captured/user text is never passed here."""
from contextlib import contextmanager
from contextvars import ContextVar

_LANGUAGE = ContextVar('trace_report_language', default='zh')

# Only code-owned literals and display enums use this catalogue. Do not apply
# it to a report recursively: that would rewrite original statements/evidence.
ENGLISH = dict(line.split('\t', 1) for line in '''用户要求	User requirement
状态：	Status:\x20
程序检查未通过	A program check failed on its recorded input/version
程序检查结果待确认	A program check remains unresolved
条；本次自动组织的声明关系0条。其他声明关系只有提交记录，不能借此认证科学含义。本报告记录明确提交的任务、真实材料、程序步骤及检查范围。公开理由只来自已提交说明；未观察的宿主行为不补写成事实。	 links; this automatic projection adds zero declared scientific relationships. Other declarations remain submitted statements. Requirements, supplied materials, program steps and scopes are recorded. Missing host activity or rationale is not invented.
记录	Record
（第	 (occurrence\x20
次）	)
折叠	Collapse
…（共 %d 字符）	... (%d characters total)
…（共 %d 项）	... (%d items total)
设计选择	Design choice
程序结果	Program result
产物与文件	Artifacts and files
AI 选择	AI choice
用户选择	User choice
选择者未记录	Chooser not recorded
生物设计记录	Biological design record
程序记录	Program record
记录方式	Record form
用户原话	Submitted verbatim field
提交的要求摘要，原话身份未核实	Submitted requirement summary; verbatim identity not authenticated
作出的选择	Recorded choice
选择者	Chooser
用户说明	User statement
AI 同期公开说明（提交者声明）	Contemporaneous AI explanation (submitter declaration)
已提交的公开说明，发生时间未核实	Submitted public explanation; timing not authenticated
原始公开说明	Original public explanation
根据记录整理	Organized from records
后来补充解释	Later interpretation
事后补充	Later supplement
说明来源未确认	Explanation source unconfirmed
原始理由未记录	Original rationale not recorded
依据与判断	Evidence and assessment
依据	Basis
要求	Requirement
用户	User
原始请求	Original request
相关片段	Relevant excerpt
定位	Locator
来源核对尚无已验证记录	No verified source check recorded
已核对来源；不代表其适用于当前设计	Source checked; applicability to this design is not established
来源核对	Source check
适用条件	Conditions
适用边界	Limits of applicability
程序检查	Program checks
通过本项程序检查	Passed this scoped program check
本项程序检查未通过	Failed this scoped program check
本项未请求或不适用，未作通过判断	Not requested or not applicable; no pass claimed
结果需查看技术记录	See technical records for the result
结果	Result
范围	Scope
仅对应原程序本项检查；同次运行不等于逐项验证每个设计选择	Only this original scoped check; sharing a run does not validate every choice
检查项	Check
检查说明	Check description
检查范围	Check scope
检查对象	Checked object
检查发现	Finding
实际程序返回	Actual program return
正式产物	Authoritative artifact
中间或候选产物	Intermediate or candidate
衍生文件	Derived file
说明文档	Document
验证设计	Verification design
预览文件	Preview file
配套记录文件	Supporting record
文件身份	File role
用途	Purpose
生成记录	Generation record
调用期间新建	Created during the observed call
调用期间修改	Modified during the observed call
本次受观察的写入已返回，文件内容同原版本；不是新DNA序列	Observed write returned with unchanged bytes; not a new DNA sequence
只观察到文件存在，没有证明生成过程	File presence observed; generation not established
输入材料	Input material
生成动作	Generating operation
来源材料	Source material
同次运行的检查（范围分别查看）	Same-run checks (separate scopes)
打开文件	Open file
文件位置	File location
当前无法在原位置打开；请核对是否移动或未随报告提供	Unavailable at its recorded location; it may have moved or was not bundled
采集记录	Captured record
提交的原文材料	Submitted source text
已采集内容	Captured content
材料来源	Material source
从本地文件读取	Read from local file
宿主主动提交	Explicitly submitted by host
执行失败	Execution failed
发生了什么	Observed action
程序调用已返回。调用成功本身不代表生物学验证通过。	Program call returned; execution alone does not establish biological validity.
输入或原文件	Input or prior file
返回后的文件	File after return
返回说明	Return description
序列长度（bp）	Sequence length (bp)
检查文件	Checked file
拓扑	Topology
记录内容	Record content
此记录属于技术过程；完整输入、返回和历史保留在技术文件中	Technical event; complete inputs, returns and history remain in technical files
对应调用	Related call
原始来源	Original source
相关判断	Related assessment
对应用户要求	Responds to requirement
关联记录	Related record
打开原始来源	Open original source
证据内容	Reported evidence
任务判断	Task assessment
文件可读取且符合文件契约	File readability and format contract
计算过程一致性	Computation consistency
序列与注释检查	Sequence and annotation checks
请求的元件检查	Requested components
用户目标检查	Declared goal check
产物序列与实际输入一致	Product sequence matches actual inputs
实际计算制备链检查	Computational preparation chain
当前交付文件回读检查	Delivered-file readback
已声明目标核对	Declared goal check
完整引物PCR计算检查	Full-primer PCR simulation
构建接口PCR方案检查	Junction-PCR design
给定模板的验证方案检查	Verification design on supplied templates
检查材料	Inspect materials
执行构建方案	Execute construction route
导出制备材料与引物	Export preparation materials and primers
标注引物	Annotate primers
转换格式	Convert format
正式交付	Formal delivery
执行设计	Execute design
检查设计	Check design
生成执行方案	Plan execution
检查序列与注释	Check sequence and annotations
核对用户目标	Check declared goal
交付时文件存在，但未采集生成过程；这项观察不判断文件是否符合设计要求	File existed at handoff; generation unobserved. This does not check design compliance
交付时未找到文件	File missing at handoff
文件与已记录版本不同，需要重新核对	File differs from recorded version; recheck required
存在多个匹配生成记录，尚未确定本次交付对应哪一次	Several matching generation records; this handoff is not resolved
已关联生成记录	Linked to generation record
宿主	Host
物种	Organism
菌株	Strain
温度	Temperature
培养基	Medium
检测方法	Assay
构建背景	Construct context
材料检查	Material inspection
引物标注	Primer annotation
格式转换	Format conversion
预览文件包	Preview bundle
目标检查	Goal check
注释与序列检查	Sequence and annotation checks
交付用途	Handoff purpose
交付记录	Handoff record
交付清单中的文件	File in handoff list
身份未记录	Role not recorded
序列	Sequence
方法	Method
材料文件	Material file
模板文件	Template file
起点	Start
终点	End
说明文字	Explanation text
重新判断	Reassess
重新检查依据	Recheck evidence
建议重新运行检查	Rerun suggested
属于旧上下文	Stale context
需要人工复核	Needs review
明确受到影响	Affected
可能受到影响	May be affected
信息不足，影响未知	Insufficient information; impact unknown
在已声明范围内无关	Unrelated within declared scope
影响尚未分类	Impact unclassified
未记录	Not recorded
未提供此条件	Condition not supplied
明确留空	Explicitly empty
结构化内容已变更，完整值见技术记录	Structured value changed; complete value remains in technical records
相关依据的适用性	Applicability of related evidence
本次实际结果	Actual outcome
设计过程尚未整理或组织已陈旧。以下为有限事实记录。	Organization is missing or stale. The following is a limited factual view.
任务与要求	Goal and requirements
设计形成过程	Design process
设计怎样形成	How the design formed
交付文件与检查	Files and checks
查看详细记录	Detailed records
来源与详细记录	Sources and details
来源记录	Source records
未记录任务要求。	No task requirement recorded.
分支	Branch
来源	Source
当前判断	Current assessment
对应判断	Related assessment
限制	Limits
未记录产物。	No artifact recorded.
程序未验证的范围	Unverified scope
需要处理	Needs attention
当前需要处理	Needs attention
交付清单核对	Handoff checks
记录完整性	Record completeness
变化与影响	Changes and impacts
以下为重查建议，不修改原来的科学判断或程序结果。	Recheck suggestions; original scientific assessments and program results remain unchanged.
完整原记录、条件、关系和历史见同目录 graph.json。	Complete records, conditions, relations and history are in graph.json.
用于选择	Used for choice
输入	Inputs
输出与检查对象	Outputs and checked objects
实际调用返回	Actual call returned
实际调用失败	Actual call failed
文件	File
产物	Artifact
执行	Execute
核对项目材料与当前文件版本	Check supplied materials and current file versions
完成供体制备与正式验收	Prepare donor and check formal delivery
汇总给定区域的鉴别结果	Summarize discrimination within supplied regions
整理实验观察与结论范围	Organize reported observations and conclusion scope
保存本次报告与技术记录	Save report and technical records
读取实际目标参考	Read actual target reference
读取实际标记模板	Read actual marker template
核对可用完整PCR模板	Check complete PCR template
核对同源臂、标记片段与目标边界	Check arms, cargo and target boundaries
检查供体左侧接口	Check left donor junction
检查供体右侧接口	Check right donor junction
核查并交付当前供体	Check and deliver current donor
核对真正交付的文件	Verify presented files
记录供体构建的实际结果	Record donor-construction outcome
记录本次实际结果	Record actual outcome
比较两份给定参考区域	Compare supplied reference regions
为选定区间设计检测引物	Design assay primers for selected interval
检查完整引物及当前条件	Check complete primers and conditions
在实际参考上模拟PCR	Simulate PCR on supplied references
读取实验记录文件	Read submitted observation files
本次调用未得到正常返回	Call failed to return normally
未记录原因	Reason not recorded
按明确的参考位点、左右同源臂和标记边界，核对预期	Explicit references, arms and cargo define an expected
 bp 线性供体。这里只建立序列与注释模型，实际制备在后续步骤执行。	 bp linear donor. This is a sequence/annotation model; preparation follows separately.
本次方法未完成	Method incomplete
原因见实际返回。	See actual return for the reason.
由完整模板和本次引物计算得到	Calculated from complete template and current primers:
由实际PCR片段计算组装得到	Simulated assembly from actual PCR fragments:
 bp 供体候选。完整引物、条件及结构质量另行检查；计算产物不等于实际实验成功。	 bp donor candidate. Full primers, conditions and structure are checked separately; simulation is not experimental success.
在本次给定背景参考中未预测产物	No product predicted in the supplied background
给定背景也有预测产物，需要结合具体长度区分	Products also predicted in background; compare actual lengths
背景鉴别尚未完整核查	Background discrimination not fully checked
当前供体的该接口PCR预测为	Current donor junction-PCR predicts
。这是给定序列上的计算方案，不是实测PCR或全基因组特异性结论。	. This is a supplied-sequence calculation, not measured PCR or genome-wide specificity.
当前正式文件已回读，供体序列、计算制备链、实际文件和已声明目标四项核查通过。该结论不包括实际整合、表达或基因组复活。	Current files were read back; donor sequence, simulated preparation, files and declared goal passed scoped checks. Integration, expression and revival were not established.
真正选择交付的文件与本次受检版本一致。回执核对文件归属及完整性，不重新下生物学结论。	Presented files match checked versions. Receipt verifies ownership/integrity without a new biological verdict.
读取本次选定的	Read selected
 bp 序列记录，供后续来源和边界核对。文件存在与版本核对不等于实际菌株身份认证。	 bp record for source/boundary checks. File existence and version do not authenticate strain identity.
程序返回状态	Returned status
。含义与实际范围以该次返回为准。	. Meaning and scope are those of the actual return.
该参考预测扩增产物	Predicted amplicon on this reference:
 bp；不是实测PCR结果。	 bp; not measured PCR.
程序返回实际分子，长度为	Returned molecular length:
程序完成此步骤；参数、实际返回和对应材料保留在详细记录中。	Program step completed; parameters, actual return and materials remain in details.
确定本次任务与检查范围	Define task and check scope
用户提交了本次任务。完整原文保留在任务与要求及来源记录。	Task submitted; original supplied text remains under requirements and sources.
程序验证的文件关系	Program-verified file relationships
程序验证的关系：输出文件与声明输入文件的SHA-256相等。仅文件内容关联，不推断科学支持、物理使用或因果。	Program verifies output/input SHA-256 equality only, not scientific support, physical use or causality.
实际任务过程	Observed workflow
实际记录顺序	Recorded order
按记录展示用户要求、已提交的选择和程序执行。顺序不自动证明科学因果。	Requirements, submitted choices and execution shown from records. Order does not establish causality.
从实际模板扩增片段	Amplify fragment from actual template
组装实际PCR片段	Assemble actual PCR fragments
检查当前供体接口	Check current donor junction
当前任务中的判断	Assessment within current task
Genome Revival：任务过程与证据	Genome Revival: workflow and evidence
任务怎样形成实际结果？	How the task produced its result
Genome Revival Toolkit 结果	Genome Revival Toolkit result
我们要完成什么？	What are we trying to do?
本次得到了什么？	What was obtained?
使用了哪些实际材料？	Which materials were supplied?
程序确认了什么？	What did the program check?
还有哪些范围没有确认？	Which limits remain?
文件在哪里？	Where are the files?
本次任务与实际结果摘要	Task and current outcome summary
检测候选及完整质量状态；失败候选不可当作已通过订单	Assay candidates and full quality status; failed candidates are not approved orders
完整技术结果见同目录 result.json；实际来源版本见 context-snapshot.json。	Complete results: result.json. Actual source versions: context-snapshot.json.
Evidence Trace覆盖本Toolkit公共调用及明确提交的说明，不声称观察到宿主全部行为。	Trace covers these public Toolkit calls and supplied explanations, not all host activity.
完整所选记录	Complete selected record
。声明菌株身份与实际参考文件核对分开。	. Declared strain identity is separate from reference-file checks.
：选定区域长度	: selected lengths
 bp；比对身份比例	 bp; alignment identity
%。最佳比对不证明唯一定位。	%. Best alignment does not establish unique placement.
：完整引物质量	: complete-primer quality
；本区域判断	; discrimination within supplied regions
：菌落数	: reported colony count
未提供	Not supplied
：报告结果	: reported result
。具体条件及原返回见技术记录。	. Conditions and actual returns remain in technical records.
程序核对供体序列、真实计算制备、两侧供体鉴别、保存文件及已声明目标。这里没有进行基因组整合实验。	Checks cover donor sequence, simulated preparation, junction assays, saved files and declared goal. No integration experiment was performed.
仅检查提供的参考和选定区域：比对、逐参考PCR预测、完整引物质量及声明的鉴别条件。没有检验区域外特异性或实际PCR表现。	Checks cover supplied regions, alignment, per-reference PCR, complete primers and declared discrimination. Outside-region specificity and experimental PCR were not tested.
整理已提交的观察与对照，检查数值、引用和记录范围。程序没有重新做实验或认证复活机制。	Submitted observations/controls are organized with numeric, reference and scope checks. No experiment was repeated or revival mechanism authenticated.
实际菌株基因型、实体模板及实验制备效率未由本计算确认。	Actual strain genotype, physical template and preparation efficiency are unverified.
供体接口检查不等于已完成基因组整合；整合与复活需要实验。	Junction checks do not establish integration or revival; those require experiments.
给定参考之外的全基因组特异性未覆盖。	Genome-wide specificity outside supplied references is untested.
实验扩增、条带分离及真实基因型尚未由本计算确认。	Experimental PCR, band separation and actual genotype are unverified.
预测只适用于本次给定参考与区域，不能直接推广到实验株或完整基因组。	Predictions apply to supplied references/regions, not automatically to experimental strains or whole genomes.
数据是研究者提交的记录，程序未独立认证实验真实性。	Observations were submitted by researchers; experiment authenticity was not independently verified.
所选标记不能单独证明整个宿主基因组消除或供体基因组恢复功能。	Selected markers alone cannot establish whole-genome elimination or functional revival.
未检测区域、功能依赖和机制证据仍未覆盖。	Untested regions, functional dependencies and mechanism remain outside scope.
未预测到精确扩增产物	No exact product predicted
存在多个可能产物	Several possible products
预测有扩增产物	Product predicted
预测未确定	Prediction unresolved
在给定参考中预测可区分	Predicted distinguishable within supplied references
不能区分给定参考	Supplied references not distinguishable
鉴别条件待确认	Discrimination conditions unresolved
未检查多背景鉴别	Multi-background discrimination not checked
当前正式文件已核查	Current formal files checked
已完成所述范围内的分析	Analysis completed within stated scope
尚未完成	Incomplete
本次未完成	Unsuccessful
当前任务未完成。	Current task incomplete.
结果未确定	Result unresolved
通过	Passed
未通过	Failed
未完成	Incomplete
不适用	Not applicable
调用输入	Call input
实际返回	Actual return
来源记录不可用	Source record unavailable
关联对象未记录可读名称	Related object lacks a readable name
程序验证：输出与声明输入文件的SHA-256相等；不证明科学支持、物理使用或因果	Program-verified file SHA-256 equality; not scientific support, physical use or causality
声明，程序未验证	Declared; not program-verified
输出 / 检查对象	Outputs / checked objects
查看对象与范围	View object and scope
文件与来源	File and source
适用方面	Supported aspect
条件	Conditions
 项检查通过	 checks passed
 项未通过	 checks failed
 项未知	 checks unresolved
 项记录中的问题。	 recorded issues.
 项已请求检查；	 requested checks;\x20
 项未通过，	 failed;\x20
 项结果未知。	 unresolved.
 项	 items
变化	Changes
待处理	Open items
查看实际程序返回	View actual program return
说明来源未知	Explanation source unknown
检查	Checks
查看依据与完整记录	View basis and complete records
展开	Expand
依据与完整记录	Basis and complete records
新记录尚未纳入原组织。以下显示有限事实，旧组织保存在详细记录。	New facts are outside the old organization. Limited facts shown; old organization remains in details.
尚未提交设计过程组织。以下为已采集事实，不是完整设计解释。	Organization not submitted. Captured facts are shown, not a complete design explanation.
当前待处理	Needs attention
查看具体问题	View issues
程序未验证	Not program-verified
查看全部确认边界	View all limits
结果尚未确定	Outcome unresolved
存在未知的程序检查结果。	Some program checks remain unresolved.
查看对象与范围	View object and scope
下载 Markdown	Download Markdown
记录范围	Record scope
本次结果	Current outcome
 条产物版本记录	 artifact-version records
未记录产物	No artifact recorded
查看文件	View files
对象与检查范围	Objects and check scopes
查看请求来源	View request source
未记录用户要求。请查看已有程序记录。	No user requirement recorded; see available program records.
记录区分用户要求、公开选择与程序结果，供人复核；不作安全判定或展示隐藏思维。	Records distinguish requirements, public choices and program results for review; they do not certify safety or expose hidden thought.
完整	Complete
有缺口	Gaps present
过程组织	Process organization
与记录版本一致	 matches recorded version
已陈旧	 stale
尚未提供	 not supplied
阅读方式	Reading mode
正文	Document
过程图	Process map
图文对照	Split view
详情	Details
图	Map
缺少生成过程记录	Generation unobserved
交付时文件不存在	Missing at handoff
文件版本已变化	File version changed
生成来源尚未确定	Generation unresolved
未记录文件产物。	No file artifact recorded.
程序检查范围	Program check scope
未记录程序验证。	No program validation recorded.
交付清单与生成记录	Handoff and generation records
记录中尚未解释的交付状态	Unexplained recorded handoff status
要求与选择	Requirements and choices
来源、陈述与判断	Sources, statements and assessments
程序与文件	Programs and files
尚未归类的记录	Unassigned records
完整关系记录	Complete relationships
组织版本	Organization versions
原始日志	Original log
采集与组织缺口	Capture and organization gaps
尚无可显示的步骤。	No steps available.
回应该要求	Responds to requirement
没有覆盖的范围	Uncovered scope
虚线：声明或结构性关系，程序未验证其含义	Dashed: declared/structural relationship; meaning not program-verified
实线：程序核验文件SHA-256相等	Solid: program-verified file SHA-256 equality
纵向是实际记录顺序，不表示因果。点击一步，高亮它的上下游。	Vertical order follows recorded events, not causality. Select a step to highlight connected records.
本次记录没有声明步骤之间的依据关系，所以图中没有连线。每一步的来源见“查看依据与完整记录”。	No recorded step relationship; no lines inferred. Each step links to its basis and records.
没有步骤。	No step recorded.
技术记录（完整机器数据）	Technical records (complete machine data)
完整关系保留在机器结果中。关系的含义由原记录注明，阅读顺序不表示因果。	Complete relationships remain in machine data. Meaning is declared in original records; reading order is not causality.
这里显示实际变化、受影响对象及需要重查的内容。	Recorded changes, affected objects and requested rechecks.
组织版本及对应的记录范围保留在机器结果中。	Organization versions and their record scope remain in machine data.
追加日志保存原始采集内容和失败记录。	Append-only log retains original captures and failures.
记录完整性只指已采集记录；未观测的宿主活动不在覆盖范围内。	Completeness covers captured records only; unobserved host activity remains outside scope.
以下为重查建议，不修改原判断或检查结果。	Recheck suggestions; original assessments and check results remain unchanged.
未记录设计变化。	No design change recorded.
关系技术记录	Relationship technical records
记录范围与缺口	Record scope and gaps
打开完整技术文件	Open complete technical file
折叠目录	Collapse navigation
报告章节	Report chapters
记录范围与来源可回查	Record scope and sources remain accessible
目录	Contents
来源与详细记录	Sources and details
返回上一条记录	Previous record
关闭详情	Close details
可读详情	Readable details
完整技术记录	Complete technical records
：	:\x20
；	;\x20
（	 (
）	)
。 	.\x20
。\t.
'''.splitlines() if '\t' in line)
_ENTRIES = sorted(ENGLISH.items(), key=lambda pair: len(pair[0]), reverse=True)


def get_language():
    return _LANGUAGE.get()


def display(mapping, key, default=None):
    """Translate a known display enum, preserving unknown/source values."""
    return tr(mapping[key]) if key in mapping else default


@contextmanager
def language_scope(language=None):
    language = get_language() if language is None else language
    if language not in ('zh', 'en'):
        raise ValueError('Report language must be zh or en')
    token = _LANGUAGE.set(language)
    try:
        yield language
    finally:
        _LANGUAGE.reset(token)


def tr(text):
    if get_language() != 'en' or not isinstance(text, str):
        return text
    if text in ENGLISH:
        return ENGLISH[text]
    for original, english in _ENTRIES:
        text = text.replace(original, english)
    return text
