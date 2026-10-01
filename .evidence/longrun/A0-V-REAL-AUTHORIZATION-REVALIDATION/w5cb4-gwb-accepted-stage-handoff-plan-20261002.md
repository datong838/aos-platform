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
