# GW-b｜已接受方案阶段决策进入内容 Handoff 的正式来源

基线 2026-10-02 05:33 CST，AOS-001096 / m1 `840841e7`。复习 231-5 §5–6、231-9 §2/§5 与 D-waves BG00GW-b。`read_approved_stage_handoff_source` 已验证当前 `AnalystStageDecisionRevision(accept)`、原 draft、获批 successor、StageAttempt/EvalReport/Artifact 和时限；但 `ReviewAdvanceHostService` 的 ACCEPT 仍强制 OPEN `ReviewIssueRevision`。现有 `test_analyst_stage_handoff_source_pg.py` 决策由 fixture 发布，不能充当真实人工批准。

## 预期合同与文件级施工

1. `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_business_investigation_review_command.py`：原 `ReviewHandoffRequest` 将 Issue 与四个 AIP Artifact 固定为必需；先审查其上游输入与应用调用点，再决定新增独立接受阶段命令，还是显式扩展有歧视字段的 v2 合同。不能让旧 producer 输出宿主不认识的新命令。
2. `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py`：保持历史 Issue 驱动 Review 合同；新增严格的“已接受方案阶段”来源分支，必须带当前 `stageDecisionRef`、获批 `growthPlanRef`、原 TaskRun/Plan/StageAttempt/EvalReport/Artifact 精确引用，并通过原 `read_approved_stage_handoff_source`。不得在无 Issue 时直接放行；只有正式阶段 accept 可替代 Issue。Handoff/Task/Brief 的 hash 与 receipt 绑定分支种类和来源引用，避免跨路径重放。
3. `services/aos-api/aos_api/ecommerce_analyst_stage_handoff_source.py`：仅补必要的同事务只读来源验证接口，不复制 StageDecision/Plan authority，不写新批准。若现有接口足够则不改。
4. `services/aos-api/tests/extension_runtime/test_ecommerce_review_advance_host.py` 与 bundle producer 对应测试先写 RED，覆盖无 Issue 且无 Decision 失败、有效 Decision 形状进入独立来源分支、旧 Issue 命令兼容、篡改 requestHash/DecisionRef 拒绝。PG 联合正向必须复用原 `AnalystStageDecisionStore`、原批准 GrowthPlan 与原 Review command producer；不能 monkeypatch 来源读取或手插 ReviewIssue。
5. 专项及原 Review/TaskRun/Brief 相邻回归、静态、方案复审、verification、m1 精确提交与 AOS/Prime/D-waves 同步。真实权威库只读，Host/worker/Provider 不启用。浏览器在该后端来源合同波不适用；到当前实例可运行后另行验收。

## 安全门与回退

已核：producer `ReviewHandoffRequest` 强制 Issue OPEN 与四种 `ArtifactRevision`；`AnalystStageDecisionRevision` 的 subject artifact 是 `Artifact`，不是同一组四种 AIP artifact。直接把 Issue 改 nullable 会失去跨域 lineage 与原 Response hash 合同。先明确 StageDecision→Handoff 的 artifact 映射/读者和 v2 command 身份，再 RED；不得把 Stage Artifact 冒充 AIP ArtifactRevision。若这个改动需要新公共业务语义或新增权限，先更新上位方案审查后编码。失败时只留下 RED 和来源缺口，不填假 Issue、假 EvalReport、假 TaskRun 或人工 Run。

## 2026-10-02 05:45 下游合同复核补充

原 `ContentTaskSpec` 在 `ecommerce_content_campaign_workflow_contracts.py` 要求四个互异 `ArtifactRevision`；宿主 `_strict_review_accept_command` 再次锁定同一数组。`_review_lineage` 把四引用写入 Task.goal 和 Brief.spec，内容生成 `_task_brief_authority` 逐项与 Review 来源比对，内容评审 `_task_brief_authority` 也比对 `sourceArtifactRefs`，且评审还有原 ReviewIssue 的独立权威检查。获批 `GrowthPlanRevision` / accepted `AnalystStageDecisionRevision` 只含一条 `generationArtifactRef: Artifact`，并不存在可证明的四个 Investigation ArtifactRevision 映射。

因此 GW-b 的最小**完整**改动单元必须沿着 Handoff→Task/Brief→内容生成→内容评审建立单一的 accepted-stage 来源种类与 exact 引用验证；旧 Issue 合同保持原样。不能只在宿主接受 `stageDecisionRef`，让下游因四引用或 Issue 缺失而失败。拟新增的分支需绑定当前原 TaskRun、Plan、StageAttempt、EvalReport、Artifact、accepted Decision、获批 GrowthPlan、原人工 reviewer 与截止时间；Task/Brief 需独立 schema 版本和回执 hash，所有后续消费者以同一来源种类重验，不凭调用方提交的四个假 Artifact 填空。第一项 RED 应跨 producer→宿主→Task/Brief→生成入口验证 exact lineage；若原内容评审仍强制 Issue，同波至少保持失败封闭并登记下一项，不得称首链正向。

这属于 231-5 `handoff_pending` 到 `content_running/content_review` 的既定工作范围，但修改触及新的公共 TaskBrief schema。编码前先补 231 上位合同和旧/新 schema 兼容矩阵；现阶段没有可安全宣称的单文件 Host 修复。

## GW-b-1 有界语法切片（05:50）

231-5 §9 已补旧/新来源矩阵。先在宿主加独立 `accepted-stage-v1` envelope 解析与 requestHash/exact refs/单 Artifact 形状校验，并在 `revalidate`、`execute`、Receipt verify 三处继续失败封闭。旧 `review_handoff.advance` Issue 命令保持原校验。此切片只证明新来源不能混入旧 Issue 回执或产生 Task/Brief；没有 bundle producer、原 Owner 验证及下游 schema，**不是** Handoff/业务 GREEN。后续只有在 producer 与 Host Owner 可同波联测时才允许发出这一命令；随后接 Task/Brief v3 与生成/评审共同来源复核。此分段先隔离可复核的协议歧视字段，绝不开放业务运行。

## GW-b-2a 原 Owner 同事务读取（06:08）

Host 仅在新来源 envelope/dispatch 校验后，调用现有 `read_approved_stage_handoff_source` 回读当前人工决定与获批 successor，再逐项对齐原 Artifact/EvalReport/ResponsibilityPlan/截止时间。这个读取和禁入都在原 `ReviewAdvanceHostService.revalidate` 内；`execute` 继续拒绝，bundle 暂不发出新命令。隔离 PG 原 Store fixture 用于代码正反测试，不是当前真实人工批准。下一步必须让 bundle producer 生成同一 exact 命令，并补原 Occurrence/Case/Run/Analysis Receipt 与 Stage TaskRun 的真来源关联；之后 Task/Brief v3、内容生成与评审同步接线。只做此读取不会解锁 Handoff。

## GW-b-2b bundle producer 文件级计划（06:12）

先在 `ecommerce_content_campaign_workflow_contracts.py` 给 `ContentTaskSpec` 增显式来源种类：默认旧 Issue 路径仍要求四个 `ArtifactRevision`；仅 `accepted-stage-v1` 允许一个原 `Artifact`。再在 `ecommerce_business_investigation_review_command.py` 新增独立强类型 `AcceptedStageHandoffRequest`，使用包内现有 `AnalystExactRef`、`EvalStageAttemptRef` 与原 `ExactRef`，输出宿主 GW-b-1 已冻结的字段；`ecommerce_business_investigation_handoff.py` 暴露纯命令构造。`test_ecommerce_review_handoff_content_runtime.py` 先 RED 并验证输出被宿主严格 parser 接受，跨来源/布尔修订/哈希漂移拒绝。生产 application 的 `advance_review` 与 Receipt parser 在 Task/Brief v3 和完整 Owner 联合校验前不发此命令，Host `execute` 保持禁入。下一切片再接原 BI↔Stage TaskRun 与 Task/Brief/生成评审，不能以纯 producer GREEN 代替首链。

GW-b-2b 施工结果：bundle 纯命令生产与宿主语法 parser 联合 GREEN；不接 `advance_review`/transport。下一波需要原 Occurrence/Case/Run/Analysis Receipt 与阶段 TaskRun/Plan/Decision 的同源核验，随后 Task/Brief v3 和内容生成/评审同源校验；当前 runtime 仍禁入。

## GW-b-2c1 原 Analysis Receipt 至阶段 TaskRun 文件级计划（06:25）

现有 `ReviewAdvanceHostService._revalidate_analysis_runtime` 已锁原 AnalysisRuntimeReceipt、BI Run/State、原 compilation receipt、AIP Task/Plan/TaskRun，并通过 `BusinessInvestigationRuntimeBinder._binding_from_lineage` 校验 Run/Case/Plan 同源；末尾却只准整个 TaskRun `SUCCEEDED`。原 `read_stage_review_runtime_authority` 允许当前阶段已成功而 TaskRun 仍 `RUNNING`/`PAUSED`，故不能直接复用旧终态条件，也不能把原四 Artifact 当阶段 Artifact。先在此方法增加仅由已核的 accepted Stage TaskRun ID 触发的受限状态集合，原 Issue 分支默认仍只认 `SUCCEEDED`；新分支先读原 accepted Decision，再调用原 Analysis Receipt 链校验与 Stage TaskRun ID 相等，然后继续拒绝 Task/Brief 创建。`test_ecommerce_review_analysis_runtime_authority.py` 先 RED，覆盖运行中原 TaskRun 同源正向、不同 TaskRun/Plan/Case/Receipt 反向、原 Issue 运行中仍拒绝。该测试快照不是真实当前运行；后续须用隔离 PG 原生产者联测，并补 Occurrence 当前权威、Stage Eval/permission 及 Task/Brief v3。不能据此开启 Host。

GW-b-2c1 施工结果：原 Analysis Receipt/compilation/TaskRun 读者在 accepted-stage 来源下允许同 ID 的 RUNNING/PAUSED/SUCCEEDED；旧 Issue 分支保留 SUCCEEDED。隔离 PG 原 StageDecision 可以读通，但缺原 Analysis Receipt 时新分支按原读者拒绝。下一项 2c2 必须补当前 Occurrence/Case 和原 BI→Stage 的 PG 联合正向，重验当前 Stage Eval/permission，不能用读者快照替代实际生产者。

## GW-b-2c2 当前 Occurrence/Case 入口与联合源文件级计划（06:50）

231-5 §9 要求新旧来源共享当前安装、调度与 Case 的精确引用。现有宿主 `revalidate` 在 accepted-stage 分支之前直接返回，跳过旧路径对 `AutomationOccurrence` 的当前 payload hash 和 `BusinessInvestigationCaseRevision` 当前 head 的校验；`_revalidate_analysis_runtime` 虽核 Run 的 Case ref，却不能证明 Case head 与 Occurrence 当前状态。本波先将既有两项读取抽成宿主私有共用方法，使两种来源在同一 `HostTransaction` 先核当前 Occurrence/Case，再各走原分支；不扩大其他业务判断或改变旧命令形状。文件仅 `ecommerce_growth_runtime_adapters.py`、`test_ecommerce_review_advance_host.py`、`test_analyst_stage_handoff_source_pg.py`。测试先 RED：accepted-stage 在缺 Occurrence、错 Case hash 时必须早于 Stage/Analysis 读者失败；原 Issue 路径仍可通过。隔离 PG 现有 Stage fixture 缺 Occurrence/Case，只能证明失败顺序；要做全链正向，还须用原 Case/Occurrence/Analysis/Stage/Eval/permission 生产者组装同租户同事务 fixture，不用手插假批准或新 ReviewIssue。此阶段 `execute` 保持拒绝，随后继续 PG 联合正向、Stage Eval/permission 与 Task/Brief v3，不能将入口 GREEN 宣称为 Handoff。

GW-b-2c2a 施工结果：两个 RED 均先触及 Stage 读者（2 failed），共用入口改动后六文件 85 passed；旧 Issue 分支保留原校验。现有隔离 PG Stage fixture 因无当前 Occurrence 在原来源读取前拒绝；这说明失败顺序正确，**尚未证明当前 Occurrence/Case 的生产者联合正向**。下一切片须将原 Case/Occurrence/Analysis/Stage/Eval/permission 真实测试生产者连接起来，不能通过 monkeypatch 声称 PG 联合通过。

## GW-b-2c2b 评审后 Eval 来源的历史 draft 边界（06:55）

复核 `ecommerce_analyst_stage_review_command._subject`：原人工评审当时要求 GrowthPlan draft 为当前 head，这对发表 accept 是正确的；其后 `EcommerceAnalystGrowthPlanApprovalService.approve` 发布相同内容的 APPROVED successor，draft 不再 current。若 Handoff 直接调用 `read_stage_review_eval_source_authority`，会在读取 solution-design subject 时因“current growth draft unavailable”误拒合法历史批准。上位 231-5 §9 明定当前 accepted Decision＋历史 draft＋获批 successor 作为交接锚，不能修改原评审时的 current 要求。

文件级计划：在 `ecommerce_analyst_stage_review_command.py` 的 Eval 来源只读接口增显式 `approved_stage_source` 参数，仅 `solution-design` 允许使用经 `read_approved_stage_handoff_source` 核验的同一历史 draft；它必须与 Decision.subjectRef、当前获批 successor.priorRef 和内容 hash 完全一致，其余 portrait/diagnosis、原人工决策路径保持 current 检查。宿主 `ecommerce_growth_runtime_adapters.py` 在当前 Occurrence/Case、Owner、原 Analysis 链后调用原阶段 Runtime、责任/人类 reviewer、Eval 来源读者，任何一步缺失拒绝且 `execute` 仍关。`test_analyst_stage_handoff_source_pg.py` 先 RED：已批准后旧 Eval 读者因 draft 非 current 失败；显式获批来源只越过该一条 current 判断，并在缺原 Decision/Insight 当前来源时继续失败。不能从此 fixture 声称完整 PG 正向或真人批准；下一切片继续原生产者联合正向及 Task/Brief v3。

GW-b-2c2b 施工结果：隔离 PG RED 为 `approved_stage_source` 参数缺失；新增参数只接受原 Owner 读者产出的来源对象并核 Decision、subject/priorRef、draft revision/hash/tenant，原人工评审无参数路径不变。宿主在原 Analysis 后再读阶段 Runtime、当前责任人及 Eval 来源，最后仍以 Task/Brief 未接线拒绝。隔离 PG 通过“旧 current draft 拒绝→获批来源越过该时间边界→缺原 Decision/Insight 拒绝”和篡改 draft hash 拒绝；缺原 TaskRun 也拒绝。九文件 134 passed。**尚无完整原生产者 PG 正向，更不是当前真人首链。** 下一项继续联合生产者与 Task/Brief v3，不能把本阶段来源检查单独当业务准入。

## GW-b-2c2c 原生产者 PG 联合证明施工表（07:00）

复查现有测试：`test_analyst_stage_handoff_source_pg.py` 通过原 StageDecisionStore 与原 GrowthPlan Approval Service 产生决策及 successor，但没有 Occurrence、Case、AnalysisReceipt、AIP TaskRun/Step/Checkpoint、AgentRun、Eval 执行与当前 reviewer；`test_ecommerce_analysis_run_resume_pg.py` 有原 Case/Run/AIP Task 操作，却有测试直接插入前置 DataRequirement、安装与派发绑定；`test_automation_occurrences_pg.py` 使用 `AutomationOccurrenceStore.put_binding/record_scheduled`，但安装/派发为独立 schema 夹具；`test_analyst_structure_eval_pg.py` 有真实隔离 Eval 执行，但目标/输入/合同仍为 fixture。当前没有一项测试可当作已联合的原生产者证明。

目标新测试文件 `services/aos-api/tests/extension_runtime/test_accepted_stage_handoff_original_chain_pg.py`：仅对 `aos_test_*` 独立 PG，先复用正式安装/配置测试 producer 建 exact 安装和 dispatch；以 `AutomationOccurrenceStore` 形成当前 Occurrence，以 `BusinessInvestigationCaseStore`、原 Run/Analysis Host 与 AIP TaskStore 形成同一 Case/Run/AnalysisReceipt/TaskRun/Plan，再走原 Stage Attempt/AgentRun/Artifact/Eval/Responsibility/人工决策/获批 successor。每段记录原 Receipt、scope、当前/历史版本，并在同一 HostTransaction 先正向 revalidate 到 Task/Brief 禁入，再逐项做租户、撤销、过期、hash 与跨 Run/Plan 负向；不直接插伪造业务 Receipt。现有各测试 fixture 只能作 API 用法参考，不复制高权限 seed 来冒充正式安装。若正式安装测试 producer 不可组合，先只读审计该依赖并修产品接线，不把直接 SQL fixture 当联合正向。测试证明仅为隔离 PG 代码路径，正式当前安装/真人/自然任务仍需独立验收。

首个可独立检验的前缀：在现有 `test_analyst_stage_handoff_source_pg.py` fixture 的测试库内用原 `BusinessInvestigationCaseStore` 写当前 Case，使用原 `AutomationOccurrenceStore` 与受限 runtime 身份写当前 Occurrence；仅安装/dispatch 测试控制面可由独立测试夹具搭建，并须明确不构成正式签名安装。将这两个原业务 producer 的结果放入 accepted-stage 命令，同一 HostTransaction 应越过当前 Occurrence/Case，下一缺失点明确为原 AnalysisRuntimeReceipt。由此固定接入顺序，但不宣称完整 GW-b-2c2c 正向；后续再取正式安装 producer 和原 Analysis 等联合。

## GW-b-2c2c0 前缀修正与复审（07:08）

原始 RED 中直接插入 `bundle_installation` 被 `fk_bundle_installation_current_revision` 拒绝。只在隔离 `aos_test_*_ti4_test` PG 内，改用原 `PostgresCompositionStore.create_or_get` 与 `PostgresInstallationStore.create_draft` 形成有合法 revision 的测试安装；`extension_runtime_binding`/dispatch 仍是测试控制面夹具，不能当作当前签名正式安装。原 Case 与 Occurrence 分别经其 Store 产生；同一 HostTransaction 的预期下一拒绝点是缺 `AnalysisRuntimeReceipt`。本切片只证明前缀接线及失败封闭，不改变 Host、发布或真实库。随后 GW-b-2c2c1 必须引入正式签名安装 producer 和原 Analysis/Stage/AgentRun/Eval/权限联合链，保留 Task/Brief v3 为后续门。

## GW-b-2c2c1 签名安装与原 Analysis 联合方案（07:20）

复习 231-5 §5/§9 和 231-9 §2/§4：获批阶段需真实同安装代次的 Analysis、TaskRun 与阶段来源，不能把测试 draft 或页面200当放行。`signed_installation_case.run_signed_installation` 已由原 RegistryService、Composition、InstallationService、RuntimeLifecycleService 和 test-only OCI 实施签名安装/verify，但现有 `package_probe` 位于 draft 前，现有生命周期测试又只迁移至 `a0v_028` 的局部 schema，不能承载当下 Stage/Analysis 表。`test_ecommerce_analysis_run_resume_pg.py` 的原 Analysis 片段位于独立 schema，前置安装/派发以 `session_replication_role=replica` 直插，不能挪作正式安装证明。

文件级施工：

1. `services/aos-api/tests/extension_runtime/signed_installation_case.py`：仅增可选 `verified_probe` 测试钩子，放在原 verify 成功、active/binding 回读之后、停止 test-only OCI 前；默认 `None` 保持既有测试合同。完整 schema 的 worker 身份门要求 `current_user=aos_runtime`，故辅助入口再增可选 `worker_connect` 精确注入正式 runtime 角色连接，默认沿用原 `connect`。不得给生产服务添加捷径。
2. 新 `services/aos-api/tests/extension_runtime/test_accepted_stage_signed_source_pg.py`：要求 `AOS_EXTENSION_PG_TEST=1` 与 `AOS_EXTENSION_OCI_TEST=1`，只对自动创建的完整 disposable PG；原 OCI helper 固定使用 `colima-aos-extension` 中一次性隔离容器（只用新随机名字，不连接当前权威 PG），测试后必须回读清理。先 RED 证明 helper 尚无 verified hook，再用原签名 producer 回读 active 安装/binding 与隔离权限。后续在同一测试事实中加入原 Case/Occurrence/Analysis/Stage/AgentRun/Eval，任何一步未联通应保留精确失败和原因。
3. 验证：专项 OCI+PG、原签名安装相邻测试、c2c0 测试、静态及 diff check。测试 green 只代表隔离路径；当前正式安装、真人批准与自然首链仍需独立证据。若完整 disposable DB 的身份/策略比历史局部 schema 更严格，按原正式接口补 fixture 身份/来源，不使用 `session_replication_role=replica` 或高权限跳过合同。

GW-b-2c2c1a 先收口签名安装 producer：新 hook RED 是接口缺失；修后完整 PG 暴露 runtime 角色门、schema migration 权限与 verify 准入参数的历史测试 helper 缺口，均以原角色/owner 和现有受限服务参数修正。`preparation_admission=lambda:True` 仅为测试 Host 准入 seam，不能视为当前正式 Host assignment。新测试证明 test-only 签名、apply、verify、active 安装与仍 fenced/disabled 的 binding 在完整 schema 可组合；**还没有同一测试中的原 Analysis Receipt、派发、Case/Occurrence 与 Stage 联合链**。GW-b-2c2c1b 继续这些原 producer，不沿用 c2c0 的 raw binding/dispatch 夹具。
