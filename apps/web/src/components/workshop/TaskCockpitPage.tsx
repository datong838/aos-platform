import { useEffect, useRef, useState } from "react";

import {
  EcommerceWorkshopClientError,
  ecommerceWorkshopClient,
  type TaskCockpitActionReceiptResponse,
  type TaskCockpitApprovalReviewResponse,
  type TaskCockpitCheckpointPageResponse,
  type TaskCockpitCoreResponse,
  type TaskCockpitProductionContextResponse,
  type TaskCockpitResponsibilityHandoffResponse,
  type ResponsibilityAssignmentObservation,
  type TaskCockpitSkillContributionResponse,
  type TaskCockpitStepPageResponse,
  type TaskCockpitTaskStatus,
} from "../../api/ecommerceWorkshop";
import { AsyncStateBoundary, type AsyncState } from "./AsyncStateBoundary";
import { useSourceReadinessSnapshot } from "./SourceReadinessContext";
import { aipAgentControl, type IssuedHandoff } from "../../api/aipAgentControl";
import type { ModuleHandoffCompileResponse, TaskCockpitTask, TaskCockpitRun } from "../../api/ecommerceWorkshop";

type CockpitClient = Pick<typeof ecommerceWorkshopClient, "getTaskCockpitCore" | "listTaskCockpitRunSteps" | "listTaskCockpitRunCheckpoints" | "getTaskCockpitRunProductionContext" | "getTaskCockpitRunResponsibilityHandoffs" | "compileTaskCockpitRunHandoff" | "getTaskCockpitRunApprovalReview" | "getTaskCockpitRunActionReceipts" | "getTaskCockpitRunSkillContributions"> & Partial<Pick<typeof ecommerceWorkshopClient, "getResponsibilityAssignmentObservation">>;
type HandoffCommandClient = Pick<typeof aipAgentControl, "issueHandoff" | "consumeHandoff" | "listHandoffDecisions" | "createHandoffDecision">;
type CorePhase = "loading" | "ready" | "empty" | "stale" | "forbidden" | "failed";
type SkillContributionState = { phase: "loading" | "ready" | "failed"; response: TaskCockpitSkillContributionResponse | null };
type AssignmentObservationState = { phase: "loading" | "ready" | "failed"; response: ResponsibilityAssignmentObservation | null };
type DetailState = { runId: string; phase: "loading" | "ready" | "failed"; steps: TaskCockpitStepPageResponse | null; checkpoints: TaskCockpitCheckpointPageResponse | null; productionContext: TaskCockpitProductionContextResponse | null; responsibilityHandoffs: TaskCockpitResponsibilityHandoffResponse | null; approvalReview: TaskCockpitApprovalReviewResponse | null; actionReceipts: TaskCockpitActionReceiptResponse | null; skillContributions: SkillContributionState; assignmentObservation: AssignmentObservationState } | null;
const TASK_STATUSES: readonly { value: "" | TaskCockpitTaskStatus; label: string }[] = [
  { value: "", label: "全部状态" }, { value: "pending", label: "待规划" }, { value: "planning", label: "规划中" }, { value: "awaiting_approval", label: "待审批" }, { value: "approved", label: "已批准" }, { value: "executing", label: "执行中" }, { value: "paused", label: "已暂停" }, { value: "completed", label: "已完成" }, { value: "failed", label: "失败" }, { value: "cancelled", label: "已取消" }, { value: "rolled_back", label: "已回滚" },
];
const ACTIVE_TASK_STATUSES = new Set<TaskCockpitTaskStatus>(["planning", "awaiting_approval", "approved", "executing", "paused"]);

function errorPhase(error: unknown): CorePhase {
  if (!(error instanceof EcommerceWorkshopClientError)) return "failed";
  if (error.status === 401 || error.status === 403) return "forbidden";
  if (error.status === 409 && error.body.code === "TASK_COCKPIT_CURSOR_STALE") return "stale";
  return "failed";
}
function stateFor(phase: CorePhase): AsyncState {
  if (phase === "ready" || phase === "empty") return "ready";
  return phase;
}
function formatTime(value: string | null): string { return value ? new Date(value).toLocaleString("zh-CN", { hour12: false }) : "尚未发生"; }
function blockerMatches(dependency: string, tokens: readonly string[]): boolean {
  const normalized = dependency.toLowerCase();
  return tokens.some((token) => normalized.includes(token));
}

function TaskCockpitBusinessContext() {
  const snapshot = useSourceReadinessSnapshot();
  if (!snapshot) {
    return <section className="task-cockpit-business-context is-failed" aria-label="业务上下文独立快照"><strong>业务上下文未装配</strong><p>未取得 Shell 的 canonical SourceReadiness 快照；不以空值代替。</p></section>;
  }
  if (snapshot.phase !== "ready" || !snapshot.response) {
    const label = snapshot.phase === "loading" ? "正在读取业务上下文" : snapshot.phase === "forbidden" ? "业务上下文无访问权限" : "业务上下文读取失败";
    return <section className={`task-cockpit-business-context is-${snapshot.phase}`} aria-label="业务上下文独立快照"><strong>{label}</strong><p>SourceReadiness 有独立 cutoff；不与 Task cutoff 混算，也不把未知状态解释为空。</p>{snapshot.phase === "failed" ? <button type="button" onClick={snapshot.reload}>重新读取 SourceReadiness</button> : null}</section>;
  }
  const response = snapshot.response;
  const readyCount = response.sources.filter((source) => source.status === "ready").length;
  const blockers = [...new Set(response.sources.flatMap((source) => source.blockers))].sort();
  return <section className={`task-cockpit-business-context is-${response.status}`} aria-label="业务上下文独立快照">
    <div><p className="ecommerce-workshop-eyebrow">业务上下文 · 独立 SourceReadiness 快照</p><strong>{response.status}</strong></div>
    <dl><div><dt>就绪源</dt><dd>{readyCount} / {response.sources.length}</dd></div><div><dt>检查时间</dt><dd>{formatTime(response.checkedAt)}</dd></div><div><dt>数据 cutoff</dt><dd>{formatTime(response.cutoffAt)}</dd></div><div><dt>EvidencePack</dt><dd>{response.receiptRef ? `${response.receiptRef.resourceId} · r${response.receiptRef.revision}` : "无 exact EvidencePack Receipt"}</dd></div></dl>
    <p>{blockers.length ? `当前 blocker：${blockers.join(" · ")}` : "当前响应未声明 blocker；仍以 exact Receipt 和独立 cutoff 为准。"}</p>
  </section>;
}

function ModuleHandoffCommandPanel({ task, run, responsibility, workshopClient, commandClient, onRefresh }: { task: TaskCockpitTask; run: TaskCockpitRun; responsibility: TaskCockpitResponsibilityHandoffResponse; workshopClient: CockpitClient; commandClient: HandoffCommandClient; onRefresh: () => void }) {
  const slots = responsibility.slots.filter((slot) => slot.assignee.kind === "agent_instance");
  const [sourceModuleId, setSourceModuleId] = useState("ecommerce.content-campaign");
  const [targetModuleId, setTargetModuleId] = useState("ecommerce.media-studio");
  const [sourceSlotId, setSourceSlotId] = useState(slots[0]?.slotId ?? "");
  const [targetSlotId, setTargetSlotId] = useState(slots[1]?.slotId ?? "");
  const [purpose, setPurpose] = useState("跨模块受控协作");
  const [requestedOutcome, setRequestedOutcome] = useState("返回可审计的业务决定");
  const [phase, setPhase] = useState<"idle" | "compiling" | "compiled" | "issuing" | "issued" | "consuming" | "consumed" | "deciding" | "decided" | "failed">("idle");
  const [compiled, setCompiled] = useState<ModuleHandoffCompileResponse | null>(null);
  const [issued, setIssued] = useState<IssuedHandoff | null>(null);
  const [ephemeralToken, setEphemeralToken] = useState<string | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const commandId = () => `${run.runId}-${Date.now()}-${globalThis.crypto?.randomUUID?.() ?? Math.random().toString(36).slice(2)}`;
  const compile = () => {
    setPhase("compiling"); setFailure(null); setCompiled(null); setIssued(null); setEphemeralToken(null);
    const handoffId = `handoff-${commandId()}`.slice(0, 200);
    void workshopClient.compileTaskCockpitRunHandoff(run.runId, { handoffId, taskRef: { resourceType: "Task", resourceId: task.taskId, revision: String(task.version), authority: "postgresql" }, runRef: { resourceType: "TaskRun", resourceId: run.runId, revision: String(run.version), authority: "postgresql" }, sourceModuleId, targetModuleId, sourceSlotId, targetSlotId, purpose, requestedOutcome, objectRefs: [], artifactRefs: [], evidenceRefs: [], context: {}, allowedContextFields: [], markings: ["public"], expiresAt: new Date(Date.now() + 15 * 60_000).toISOString(), correlationRef: null }).then((result) => { setCompiled(result); setPhase("compiled"); }, (error: unknown) => { setFailure(error instanceof Error ? error.message : "编译失败"); setPhase("failed"); });
  };
  const issue = () => {
    if (!compiled?.issueCommand) return;
    setPhase("issuing"); setFailure(null);
    void commandClient.issueHandoff(compiled.issueCommand, `issue-${commandId()}`.slice(0, 200)).then((result) => { setIssued(result); setEphemeralToken(result.bearerToken); setPhase("issued"); }, (error: unknown) => { setFailure(error instanceof Error ? error.message : "签发失败"); setPhase("failed"); });
  };
  const consume = () => {
    if (!issued || !ephemeralToken || !compiled?.issueCommand) return;
    setPhase("consuming"); setFailure(null);
    void commandClient.consumeHandoff(issued.handoff.handoffId, { bearerToken: ephemeralToken, receiverInstance: compiled.issueCommand.envelope.receiverInstance }).then(() => { setEphemeralToken(null); setPhase("consumed"); }, (error: unknown) => { setFailure(error instanceof Error ? error.message : "接收失败"); setPhase("failed"); });
  };
  const accept = () => {
    if (!issued || !compiled?.issueCommand) return;
    setPhase("deciding"); setFailure(null);
    void commandClient.listHandoffDecisions(issued.handoff.handoffId).then((timeline) => commandClient.createHandoffDecision(issued.handoff.handoffId, { decision: "accepted", expectedHeadVersion: timeline.headVersion, reasonCode: null, gapCodes: [], returnRefs: [], correlationRef: null, receiverInstance: compiled.issueCommand!.envelope.receiverInstance }, `decision-${commandId()}`.slice(0, 200))).then(() => { setPhase("decided"); onRefresh(); }, (error: unknown) => { setFailure(error instanceof Error ? error.message : "决定失败"); setPhase("failed"); });
  };
  const invalid = !sourceModuleId || !targetModuleId || sourceModuleId === targetModuleId || !sourceSlotId || !targetSlotId || sourceSlotId === targetSlotId || !purpose.trim() || !requestedOutcome.trim();
  return <div className="task-cockpit-handoff-command" aria-label="模块交接受控命令">
    <div className="task-cockpit-production-refs"><strong>模块交接 · 显式受控命令</strong><span>compile → issue → consume → decision</span><span>不会自动启动 AgentRun</span></div>
    <p className="task-cockpit-approval-boundary">编译零副作用；签发后 bearer 仅保存在当前页面内存，成功接收即清除。consumed 仍不等于 accepted。</p>
    <div className="task-cockpit-handoff-command-grid">
      <label>来源模块<input value={sourceModuleId} onChange={(event) => setSourceModuleId(event.target.value)} /></label>
      <label>目标模块<input value={targetModuleId} onChange={(event) => setTargetModuleId(event.target.value)} /></label>
      <label>来源职责<select value={sourceSlotId} onChange={(event) => setSourceSlotId(event.target.value)}>{slots.map((slot) => <option value={slot.slotId} key={slot.slotId}>{slot.slotId}</option>)}</select></label>
      <label>目标职责<select value={targetSlotId} onChange={(event) => setTargetSlotId(event.target.value)}>{slots.map((slot) => <option value={slot.slotId} key={slot.slotId}>{slot.slotId}</option>)}</select></label>
      <label>目的<input value={purpose} onChange={(event) => setPurpose(event.target.value)} /></label>
      <label>期望结果<input value={requestedOutcome} onChange={(event) => setRequestedOutcome(event.target.value)} /></label>
    </div>
    <div className="task-cockpit-handoff-actions"><button type="button" disabled={invalid || phase === "compiling"} onClick={compile}>编译交接</button>{compiled?.readiness === "ready" ? <button type="button" disabled={phase === "issuing" || Boolean(issued)} onClick={issue}>确认签发</button> : null}{issued && ephemeralToken ? <button type="button" disabled={phase === "consuming"} onClick={consume}>安全接收</button> : null}{issued && phase === "consumed" ? <button type="button" onClick={accept}>接受交接</button> : null}</div>
    {compiled?.readiness === "blocked" ? <p role="status">编译阻断：{compiled.blockers.map((item) => `${item.code} · ${item.requiredAction}`).join("；")}</p> : null}
    {compiled?.readiness === "ready" && !issued ? <p role="status">编译完成：零副作用；需再次确认才会签发 canonical Handoff。</p> : null}
    {issued ? <p role="status">{issued.handoff.handoffId} · {phase}{ephemeralToken ? " · 一次性凭证尚未接收" : " · 页面未保留凭证"}</p> : null}
    {phase === "decided" ? <p role="status">accepted Decision 已追加；未启动或完成下游任务。</p> : null}
    {failure ? <p role="alert">{failure}</p> : null}
  </div>;
}

export function TaskCockpitPage({ client = ecommerceWorkshopClient, handoffClient = aipAgentControl }: { client?: CockpitClient; handoffClient?: HandoffCommandClient }) {
  const [phase, setPhase] = useState<CorePhase>("loading");
  const [response, setResponse] = useState<TaskCockpitCoreResponse | null>(null);
  const [status, setStatus] = useState<"" | TaskCockpitTaskStatus>("");
  const [detail, setDetail] = useState<DetailState>(null);
  const coreRequest = useRef(0);
  const detailRequest = useRef(0);

  const load = (nextStatus: "" | TaskCockpitTaskStatus, cursor?: string, preserve = false) => {
    const requestId = ++coreRequest.current;
    if (!preserve) setResponse(null);
    setPhase(preserve && response ? "stale" : "loading");
    setDetail(null);
    void client.getTaskCockpitCore({ status: nextStatus || undefined, limit: 20, cursor }).then(
      (next) => {
        if (requestId !== coreRequest.current) return;
        setResponse(next);
        setPhase(next.items.length === 0 ? "empty" : "ready");
      },
      (error: unknown) => {
        if (requestId !== coreRequest.current) return;
        setPhase(errorPhase(error));
        if (!preserve) setResponse(null);
      },
    );
  };

  useEffect(() => {
    load("", undefined, false);
    return () => { coreRequest.current += 1; detailRequest.current += 1; };
    // client identity is fixed for the mounted page; tenant change unmounts through Host.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client]);

  const toggleDetails = (runId: string) => {
    if (detail?.runId === runId) { detailRequest.current += 1; setDetail(null); return; }
    const requestId = ++detailRequest.current;
    setDetail({ runId, phase: "loading", steps: null, checkpoints: null, productionContext: null, responsibilityHandoffs: null, approvalReview: null, actionReceipts: null, skillContributions: { phase: "loading", response: null }, assignmentObservation: { phase: "loading", response: null } });
    void Promise.all([client.listTaskCockpitRunSteps(runId, { limit: 20 }), client.listTaskCockpitRunCheckpoints(runId, { limit: 20 }), client.getTaskCockpitRunProductionContext(runId), client.getTaskCockpitRunResponsibilityHandoffs(runId), client.getTaskCockpitRunApprovalReview(runId), client.getTaskCockpitRunActionReceipts(runId)]).then(
      ([steps, checkpoints, productionContext, responsibilityHandoffs, approvalReview, actionReceipts]) => { if (requestId === detailRequest.current) setDetail((current) => current?.runId === runId ? { ...current, phase: "ready", steps, checkpoints, productionContext, responsibilityHandoffs, approvalReview, actionReceipts } : current); },
      () => { if (requestId === detailRequest.current) setDetail((current) => current?.runId === runId ? { ...current, phase: "failed", steps: null, checkpoints: null, productionContext: null, responsibilityHandoffs: null, approvalReview: null, actionReceipts: null } : current); },
    );
    void client.getTaskCockpitRunSkillContributions(runId).then(
      (next) => { if (requestId === detailRequest.current) setDetail((current) => current?.runId === runId ? { ...current, skillContributions: { phase: "ready", response: next } } : current); },
      () => { if (requestId === detailRequest.current) setDetail((current) => current?.runId === runId ? { ...current, skillContributions: { phase: "failed", response: null } } : current); },
    );
    if (client.getResponsibilityAssignmentObservation) {
      void client.getResponsibilityAssignmentObservation(runId).then(
        (next) => { if (requestId === detailRequest.current) setDetail((current) => current?.runId === runId ? { ...current, assignmentObservation: { phase: "ready", response: next } } : current); },
        () => { if (requestId === detailRequest.current) setDetail((current) => current?.runId === runId ? { ...current, assignmentObservation: { phase: "failed", response: null } } : current); },
      );
    } else {
      setDetail((current) => current?.runId === runId ? { ...current, assignmentObservation: { phase: "failed", response: null } } : current);
    }
  };

  const content = response ? (() => {
    const latestRunCount = response.items.filter((task) => task.run !== null).length;
    const activeTaskCount = response.items.filter((task) => ACTIVE_TASK_STATUSES.has(task.status)).length;
    const blockingCount = response.blockers.filter((blocker) => blocker.severity === "blocking").length;
    const warningCount = response.blockers.filter((blocker) => blocker.severity === "warning").length;
    const executionBlockers = response.blockers.filter((blocker) => blockerMatches(blocker.dependency, ["responsibility", "handoff", "assignee"]));
    const planningBlockers = response.blockers.filter((blocker) => blockerMatches(blocker.dependency, ["stage", "business", "approval", "issue"]));
    const dependencyTags = [...new Set(response.blockers.map((blocker) => blocker.dependency))];

    return <div className="task-cockpit-read-model">
      <section className="task-cockpit-metrics" aria-label="当前任务权威指标">
        <h2 className="sr-only">当前任务权威指标与当前只读范围</h2>
        <div><span>当前页任务</span><strong>{response.page.count}</strong><small>仅当前权威页</small></div>
        <div><span>活跃状态</span><strong>{activeTaskCount}</strong><small>由 Task 状态计算</small></div>
        <div><span>latest Run</span><strong>{latestRunCount}</strong><small>未补造缺失 Run</small></div>
        <div className={blockingCount ? "is-blocked" : "is-clear"}><span>阻断</span><strong>{blockingCount}</strong><small>blocking blocker</small></div>
        <div className={warningCount ? "is-warning" : "is-clear"}><span>待接入</span><strong>{warningCount}</strong><small>warning blocker</small></div>
        <div className="task-cockpit-metric-cutoff"><span>评估时间</span><strong>{formatTime(response.evaluatedAt)}</strong><small>成员截止 {formatTime(response.taskCutoff)}</small></div>
      </section>

      <TaskCockpitBusinessContext />

      <section className="task-cockpit-command-blocked" aria-labelledby="task-cockpit-command-title">
        <span className="task-cockpit-command-icon" aria-hidden="true">✦</span>
        <div>
          <h2 id="task-cockpit-command-title">通用任务指令仍失败关闭</h2>
          <p>Task、Run、Step 与 Checkpoint 保持只读；仅在 Run 明细内开放经过 compiler 与 canonical authority 的模块交接命令。</p>
        </div>
        <span className="task-cockpit-readonly-badge">受控交接</span>
      </section>

      <div className="task-cockpit-board">
        <aside className="task-cockpit-role-lane" aria-labelledby="task-cockpit-execution-title">
          <h2 id="task-cockpit-execution-title">执行组</h2>
          <div className="task-cockpit-lane-state">
            <span aria-hidden="true">◎</span>
            <strong>职责视图未接入</strong>
            <p>不使用视觉稿中的六角色在线状态或任务数量代替权威分配。</p>
          </div>
          {executionBlockers.map((blocker) => <div className="task-cockpit-lane-blocker" key={blocker.code}><span>{blocker.dependency}</span><p>{blocker.requiredAction}</p></div>)}
        </aside>

        <section className="task-cockpit-tasks" aria-labelledby="task-cockpit-tasks-title">
          <div className="task-cockpit-tasks-header">
            <div className="task-cockpit-section-heading"><h2 id="task-cockpit-tasks-title">当日任务流 · 执行进度</h2><span>{response.page.count} 项（当前页）</span></div>
          </div>
          {response.items.length === 0 ? <p className="task-cockpit-empty" role="status">当前权威 Task 集合为空；没有使用示例任务填充。</p> : null}
          {response.items.map((task) => {
          const detailId = `task-cockpit-run-${task.run?.runId ?? task.taskId}`;
          const isOpen = Boolean(task.run && detail?.runId === task.run.runId);
          return <article className={`task-cockpit-card is-${task.status}`} key={task.taskId}>
            <div className="task-cockpit-card-heading"><div><p>{task.taskType} · {task.taskId}</p><h3>{task.title}</h3></div><span>{task.status}</span></div>
            <div className="task-cockpit-progress" aria-label={`优先级 ${task.priority}`}><span style={{ width: `${Math.max(4, Math.min(100, task.priority))}%` }} /></div>
            <dl><div><dt>优先级</dt><dd>{task.priority}</dd></div><div><dt>Task 版本</dt><dd>v{task.version}</dd></div><div><dt>最近更新</dt><dd>{formatTime(task.updatedAt)}</dd></div><div><dt>Run</dt><dd>{task.run ? `${task.run.status} · v${task.run.version}` : "尚无 Run"}</dd></div></dl>
            {task.run ? <button type="button" aria-expanded={isOpen} aria-controls={detailId} onClick={() => toggleDetails(task.run!.runId)}>{isOpen ? "收起运行明细" : "查看运行明细"}</button> : null}
            {isOpen ? <div id={detailId} className="task-cockpit-run-detail">
              {detail?.phase === "loading" ? <div role="status">正在读取 Stage、职责交接、审批复核、Step 与 Checkpoint…</div> : null}
              {detail?.phase === "failed" ? <div role="alert">运行明细读取失败；未使用空集合代替。</div> : null}
              {detail?.skillContributions.phase === "loading" ? <section className="task-cockpit-skill-contributions is-loading" aria-label="本 Run 的专业 Skill 贡献"><strong>正在独立读取专业 Skill 贡献…</strong><p>该读取不阻塞原有运行明细。</p></section> : null}
              {detail?.skillContributions.phase === "failed" ? <section className="task-cockpit-skill-contributions is-failed" aria-label="本 Run 的专业 Skill 贡献" role="alert"><strong>专业 Skill 贡献读取失败</strong><p>原有 Stage、职责、审批、回执、Step 与 Checkpoint 保持可用；未用空集合掩盖失败。</p></section> : null}
              {detail?.skillContributions.phase === "ready" && detail.skillContributions.response ? <section className={`task-cockpit-skill-contributions is-${detail.skillContributions.response.projectionStatus}`} aria-label="本 Run 的专业 Skill 贡献">
                <div className="task-cockpit-production-refs"><strong>专业 Skill 贡献 · 只读</strong><span>{detail.skillContributions.response.items.length} 项 canonical AgentRun</span><span>评估于 {formatTime(detail.skillContributions.response.evaluatedAt)}</span></div>
                {detail.skillContributions.response.blockerCodes.length ? <p className="task-cockpit-approval-boundary">失败关闭：{detail.skillContributions.response.blockerCodes.join("、")}</p> : null}
                {detail.skillContributions.response.items.length ? <ul>{detail.skillContributions.response.items.map((contribution) => <li className={`is-${contribution.readiness.status}`} key={contribution.contributionId}>
                  <div><strong>{contribution.displayName}</strong><span>{contribution.runProjection.status} · {contribution.readiness.status}/{contribution.readiness.freshness}</span></div>
                  <p>{contribution.purpose}</p>
                  <small>角色 {contribution.roleRef.resourceId} · 实例 {contribution.assigneeRef.resourceId} · Skill {contribution.skillRevisionRef.resourceId}@{contribution.skillRevisionRef.revision}</small>
                  <small>Logic {contribution.logicRevisionRef.resourceId}@{contribution.logicRevisionRef.revision} · Binding {contribution.bindingRef.resourceId}@{contribution.bindingRef.revision ?? "未版本化"}</small>
                  <small>输入 {contribution.inputRefs.length} · 输出产物 {contribution.outputArtifactRefs.length} · 允许命令 {contribution.allowedCommands.length}</small>
                  {contribution.readiness.reasonCodes.length ? <em>等待：{contribution.readiness.reasonCodes.join("、")}</em> : <em>Binding 新鲜有效；仍仅展示贡献，不开放命令。</em>}
                </li>)}</ul> : <p>当前 Run 无 canonical AgentRun 贡献；没有制造六数字同事或示例 Skill。</p>}
              </section> : null}
              {detail?.phase === "ready" && detail.steps && detail.checkpoints && detail.productionContext && detail.responsibilityHandoffs && detail.approvalReview && detail.actionReceipts ? <>
                <section className="task-cockpit-production-context" aria-label="本 Run 的精确 Stage 编排">
                  <div className="task-cockpit-production-refs"><strong>Stage 编排 · {detail.productionContext.compilerVersion}</strong><span>Plan {detail.productionContext.planRef.resourceId} · v{detail.productionContext.planRef.revision}</span><span>模板 {detail.productionContext.stageTemplateRef.resourceId} · 职责 {detail.productionContext.responsibilityPlanRef.resourceId}</span></div>
                  <ol>{detail.productionContext.stages.map((stage) => <li className={`is-${stage.applicabilityResult}`} key={stage.stageId}><div><strong>{stage.title}</strong><span>{stage.stageId}</span></div><span>{stage.applicabilityResult === "applicable" ? "适用" : "不适用"}</span><small>依赖：{stage.dependsOn.length ? stage.dependsOn.join("、") : "无"} · 必需槽位：{stage.requiredSlotIds.length ? stage.requiredSlotIds.join("、") : "无"}</small></li>)}</ol>
                </section>
                <section className="task-cockpit-approval-review" aria-label="本 Run 的审批与 ReviewIssue 证据">
                  <div className="task-cockpit-production-refs"><strong>审批与复核</strong><span>Plan {detail.approvalReview.planApproval.approvalStatus} · v{detail.approvalReview.planApproval.planRef.revision}</span><span>{detail.approvalReview.actionApprovalCount} 个 Action Proposal · {detail.approvalReview.reviewIssueCount} 个 ReviewIssue</span></div>
                  <p className="task-cockpit-approval-boundary">打开不等于批准；批准不等于应用。这里只提供只读定位，目的页仍须重新鉴权。</p>
                  <div className="task-cockpit-approval-review-grid">
                    <div><h4>Action 审批证据</h4>{detail.approvalReview.actionApprovals.length ? <ul>{detail.approvalReview.actionApprovals.map((approval) => <li key={approval.proposalRef.resourceId}><strong>{approval.actionTypeId}</strong><span>{approval.proposalRef.resourceId} · v{approval.proposalRef.revision} · {approval.status}</span><small>{approval.decisions.length ? approval.decisions.map((decision) => `${decision.decision} · ${decision.actorId}`).join(" → ") : "尚无 canonical ApprovalEvent"}</small><em>{approval.navigation.commandReadiness === "destination_reauthorization_required" ? "目的页重新鉴权" : "只读事实"}</em></li>)}</ul> : <p>当前 Run 无 canonical Action Proposal。</p>}</div>
                    <div><h4>ReviewIssue 归因</h4>{detail.approvalReview.reviewIssues.length ? <ul>{detail.approvalReview.reviewIssues.map((issue) => <li key={issue.issueId}><strong>{issue.severity} · {issue.status}</strong><span>{issue.issueId} · v{issue.version} · {issue.returnStage}</span><small>{issue.artifactId} · evidence {issue.evidenceCount} · {issue.events.map((event) => `${event.sequence}:${event.eventType}`).join(" → ")}</small><em>{issue.lineageReadiness === "attempt_exact" && issue.returnLineage ? `${issue.returnLineage.stepRunId} · attempt ${issue.returnLineage.attempt}` : "attempt 未解析；保持失败关闭"}</em></li>)}</ul> : <p>当前 Run 无 canonical ReviewIssue。</p>}</div>
                  </div>
                </section>
                <section className="task-cockpit-action-receipts" aria-label="本 Run 的 Action 回执与对账证据">
                  <div className="task-cockpit-production-refs"><strong>Action 回执与对账</strong><span>{detail.actionReceipts.proposalCount} 个 Proposal · {detail.actionReceipts.receiptCount} 个 Receipt</span><span>{detail.actionReceipts.reconcileRequiredCount} 个 unknown 待对账 · {detail.actionReceipts.reconciledReceiptCount} 个已追加对账回执</span></div>
                  <p className="task-cockpit-approval-boundary">unknown 不等于失败；禁止重复执行。只有新的 immutable reconcile Receipt 才能关闭待对账状态。</p>
                  {detail.actionReceipts.executions.length ? <ul>{detail.actionReceipts.executions.map((execution) => <li className={`is-${execution.reconciliationState}`} key={execution.proposalRef.resourceId}><strong>{execution.actionTypeId}</strong><span>{execution.proposalRef.resourceId} · v{execution.proposalRef.revision} · {execution.proposalStatus}</span><small>{execution.leaseId ? `attempt ${execution.attempt} · ${execution.receipts.length} 条回执` : "尚无 ExecutionLease/Receipt"}</small><em>{execution.reconciliationState === "required" ? "unknown：仅允许授权 provider 回读对账" : execution.reconciliationState === "resolved" ? `已对账：${execution.receipts.find((receipt) => receipt.receiptKind === "reconcile")?.resolvedStatus ?? "terminal"}` : execution.reconciliationState === "not_required" ? "回执已明确，无需对账" : "尚未执行"}</em>{execution.receipts.length ? <ol>{execution.receipts.map((receipt) => <li key={receipt.receiptId}><span>{receipt.receiptKind} · {receipt.status}</span><small>{receipt.providerRequestPresent ? "provider request ref 已封存" : "provider request ref 缺失"} · evidence {receipt.evidenceCount}</small></li>)}</ol> : null}</li>)}</ul> : <p>当前 Run 无 canonical Action Receipt；没有用示例回执填充。</p>}
                </section>
                <section className="task-cockpit-responsibility" aria-label="本 Run 的精确职责与交接">
                  <div className="task-cockpit-production-refs"><strong>职责与交接 · {detail.responsibilityHandoffs.profile}</strong><span>{detail.responsibilityHandoffs.responsibilityPlanRef.resourceId} · v{detail.responsibilityHandoffs.responsibilityPlanRef.revision}</span><span>编译时就绪；运行就绪需独立验证</span></div>
                  <div className="task-cockpit-responsibility-grid">
                    <div><h4>职责槽位</h4><p className="task-cockpit-approval-boundary">Resolution Receipt 无 expiry，只证明观测时状态，不代表当前 ready。</p><ul>{detail.responsibilityHandoffs.slots.map((slot) => {
                      const latestReceipt = slot.assignee.resolutionReceipts.at(-1);
                      const readinessLabel = slot.assignee.operationalReadiness === "resolved_at_observation" ? "观测时已解析" : slot.assignee.operationalReadiness === "blocked_at_observation" ? "观测时阻断" : "未验证";
                      return <li className={`is-${slot.assignee.operationalReadiness}`} key={slot.slotId}><strong>{slot.responsibilityType}</strong><span>{slot.slotId} → {slot.assignee.resourceId} · v{slot.assignee.version}</span><small>所需能力：{slot.requiredCapabilityIds.join("、")} · 返回阶段：{slot.returnStage}</small><em>{readinessLabel}{latestReceipt ? ` · ${formatTime(latestReceipt.createdAt)}` : " · 无 exact Receipt"}</em>{latestReceipt?.blockerCodes.length ? <small>阻断：{latestReceipt.blockerCodes.join("、")}</small> : null}</li>;
                    })}</ul></div>
                    <div><h4>交接决定链</h4>{detail.responsibilityHandoffs.handoffs.length ? <ul>{detail.responsibilityHandoffs.handoffs.map((handoff) => <li key={handoff.handoffId}><strong>{handoff.senderInstanceRef.resourceId} → {handoff.receiverInstanceRef.resourceId}</strong><span>{handoff.handoffId} · {handoff.status} · v{handoff.version}</span><small>{handoff.decisions.length ? handoff.decisions.map((decision) => `r${decision.revision} ${decision.decision}`).join(" → ") : "尚无业务决定；consumed 不等于 accepted"}</small></li>)}</ul> : <p>当前 Run 无 canonical Handoff；未使用示例交接填充。</p>}</div>
                  </div>
                  <div className={`task-cockpit-assignment-control is-${detail.assignmentObservation.phase}`} aria-label="职责覆盖 Readiness 改派与人工接管四轴">
                    <h4>职责控制四轴</h4>
                    <dl>
                      <div><dt>结构覆盖</dt><dd>{detail.responsibilityHandoffs.compiledRequiredSlotIds.length} / {detail.responsibilityHandoffs.compiledRequiredSlotIds.length} 必需槽位已覆盖</dd></div>
                      <div><dt>当前可执行</dt><dd>{detail.responsibilityHandoffs.slots.every((slot) => slot.assignee.operationalReadiness === "resolved_at_observation") ? "仅观测时已解析；当前时刻仍须重验" : "未证实；保持失败关闭"}</dd></div>
                      <div><dt>启动前改派</dt><dd>TaskRun 已存在；禁止改写 frozen Plan，必须使用运行中接管</dd></div>
                      <div><dt>运行中接管</dt><dd>{detail.assignmentObservation.phase === "ready" && detail.assignmentObservation.response ? `${detail.assignmentObservation.response.takeoverRequests.length} 个请求 · ${detail.assignmentObservation.response.takeoverDecisions.length} 个决定 · ${detail.assignmentObservation.response.assignmentLeases.length} 个当前 Lease` : detail.assignmentObservation.phase === "loading" ? "正在读取独立 authority" : "独立 authority 不可用；不解释为空"}</dd></div>
                    </dl>
                    {detail.assignmentObservation.phase === "ready" && detail.assignmentObservation.response?.takeoverRequests.some((request) => request.safetyState === "provider_outcome_unknown") ? <p role="alert">Provider outcome unknown：必须先追加对账证据，禁止接管或重放。</p> : null}
                    <div className="task-cockpit-assignment-actions"><button type="button" disabled aria-describedby={`reassign-blocker-${task.taskId}`}>生成改派后继</button><small id={`reassign-blocker-${task.taskId}`}>TASK_RUN_EXISTS_USE_TAKEOVER：当前 Run 已存在。</small><button type="button" disabled aria-describedby={`takeover-blocker-${task.taskId}`}>申请人工接管</button><small id={`takeover-blocker-${task.taskId}`}>命令入口尚未取得 exact Step、Resolution Receipt、maker-checker 与安全点重验，不执行副作用。</small></div>
                  </div>
                  <ModuleHandoffCommandPanel task={task} run={task.run!} responsibility={detail.responsibilityHandoffs} workshopClient={client} commandClient={handoffClient} onRefresh={() => toggleDetails(task.run!.runId)} />
                </section>
                <table><caption>Step（{detail.steps.page.count} 项，当前页）</caption><thead><tr><th scope="col">步骤</th><th scope="col">尝试</th><th scope="col">状态</th><th scope="col">输入/输出/错误</th></tr></thead><tbody>{detail.steps.items.length ? detail.steps.items.map((step) => <tr key={step.stepRunId}><th scope="row">{step.stepKey}</th><td>{step.attempt}</td><td>{step.status}</td><td>{step.hasInputRefs ? "有" : "无"}/{step.hasOutputRefs ? "有" : "无"}/{step.hasError ? "有" : "无"}</td></tr>) : <tr><td colSpan={4}>当前权威 Step 集合为空</td></tr>}</tbody></table>
                <table><caption>Checkpoint（{detail.checkpoints.page.count} 项，当前页）</caption><thead><tr><th scope="col">序号</th><th scope="col">步骤</th><th scope="col">状态哈希</th><th scope="col">产物数</th></tr></thead><tbody>{detail.checkpoints.items.length ? detail.checkpoints.items.map((checkpoint) => <tr key={checkpoint.checkpointId}><th scope="row">{checkpoint.sequence}</th><td>{checkpoint.stepKey ?? "未绑定步骤"}</td><td>{checkpoint.stateHash}</td><td>{checkpoint.artifactCount}</td></tr>) : <tr><td colSpan={4}>当前权威 Checkpoint 集合为空</td></tr>}</tbody></table>
                {detail.steps.page.hasMore || detail.checkpoints.page.hasMore ? <p role="status">运行明细仍有后续页；本子波不截断冒充完整集合。</p> : null}
              </> : null}
            </div> : null}
          </article>;
        })}
        {response.page.hasMore && response.page.nextCursor ? <button type="button" onClick={() => load(status, response.page.nextCursor ?? undefined)}>读取下一页</button> : null}
        </section>

        <aside className="task-cockpit-role-lane" aria-labelledby="task-cockpit-planning-title">
          <h2 id="task-cockpit-planning-title">策划组</h2>
          <div className="task-cockpit-lane-state">
            <span aria-hidden="true">◇</span>
            <strong>Stage 按 Run 精确展开</strong>
            <p>仅在 Run 携带 canonical productionContract 时展示；业务上下文见独立 SourceReadiness 快照，不与 Task cutoff 混算。</p>
          </div>
          {planningBlockers.map((blocker) => <div className="task-cockpit-lane-blocker" key={blocker.code}><span>{blocker.dependency}</span><p>{blocker.requiredAction}</p></div>)}
        </aside>

        <aside className="task-cockpit-review" aria-labelledby="task-cockpit-review-title">
          <div className="task-cockpit-section-heading"><h2 id="task-cockpit-review-title">复盘 · 权威缺口</h2><span>{response.blockers.length} 项</span></div>
          <p>没有用静态复盘示例代替真实 EffectReview；以下内容逐项来自当前响应。</p>
          <ul>{response.blockers.map((blocker) => <li className={`is-${blocker.severity}`} key={blocker.code}><strong>{blocker.code}</strong><span>{blocker.severity} · {blocker.dependency}</span><p>{blocker.requiredAction}</p></li>)}</ul>
        </aside>
      </div>

      <section className="task-cockpit-capabilities" aria-labelledby="task-cockpit-capabilities-title">
        <h2 id="task-cockpit-capabilities-title">共享能力 · 待接入</h2>
        <div>{dependencyTags.map((dependency) => <span key={dependency}>{dependency}</span>)}</div>
        <p>这里只展示 blocker dependency，不声明 Agent、Binding 或 Capability 可运行。</p>
      </section>
    </div>;
  })() : null;

  return <section className="task-cockpit-page" aria-label="日常任务总控只读视图">
    <div className="task-cockpit-toolbar">
      <label htmlFor="task-cockpit-status">任务状态</label>
      <select id="task-cockpit-status" value={status} onChange={(event) => { const next = event.target.value as "" | TaskCockpitTaskStatus; setStatus(next); load(next); }}>{TASK_STATUSES.map((item) => <option key={item.value || "all"} value={item.value}>{item.label}</option>)}</select>
      <button type="button" onClick={() => load(status, undefined, Boolean(response))}>重新读取</button>
    </div>
    <AsyncStateBoundary state={stateFor(phase)} dataCutoff={response?.taskCutoff} title={phase === "stale" ? "游标或当前快照已变化" : undefined} description={phase === "stale" ? "保留已标记内容；请重新读取首屏，不会自动重放旧游标。" : undefined} action={phase === "stale" || phase === "failed" ? <button type="button" onClick={() => load(status)}>重新读取首屏</button> : undefined}>{content}</AsyncStateBoundary>
  </section>;
}
