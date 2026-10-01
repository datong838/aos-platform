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
