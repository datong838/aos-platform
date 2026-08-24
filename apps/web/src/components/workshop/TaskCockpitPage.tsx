import { useEffect, useRef, useState } from "react";

import {
  EcommerceWorkshopClientError,
  ecommerceWorkshopClient,
  type TaskCockpitApprovalReviewResponse,
  type TaskCockpitCheckpointPageResponse,
  type TaskCockpitCoreResponse,
  type TaskCockpitProductionContextResponse,
  type TaskCockpitResponsibilityHandoffResponse,
  type TaskCockpitStepPageResponse,
  type TaskCockpitTaskStatus,
} from "../../api/ecommerceWorkshop";
import { AsyncStateBoundary, type AsyncState } from "./AsyncStateBoundary";

type CockpitClient = Pick<typeof ecommerceWorkshopClient, "getTaskCockpitCore" | "listTaskCockpitRunSteps" | "listTaskCockpitRunCheckpoints" | "getTaskCockpitRunProductionContext" | "getTaskCockpitRunResponsibilityHandoffs" | "getTaskCockpitRunApprovalReview">;
type CorePhase = "loading" | "ready" | "empty" | "stale" | "forbidden" | "failed";
type DetailState = { runId: string; phase: "loading" | "ready" | "failed"; steps: TaskCockpitStepPageResponse | null; checkpoints: TaskCockpitCheckpointPageResponse | null; productionContext: TaskCockpitProductionContextResponse | null; responsibilityHandoffs: TaskCockpitResponsibilityHandoffResponse | null; approvalReview: TaskCockpitApprovalReviewResponse | null } | null;
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

export function TaskCockpitPage({ client = ecommerceWorkshopClient }: { client?: CockpitClient }) {
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
    setDetail({ runId, phase: "loading", steps: null, checkpoints: null, productionContext: null, responsibilityHandoffs: null, approvalReview: null });
    void Promise.all([client.listTaskCockpitRunSteps(runId, { limit: 20 }), client.listTaskCockpitRunCheckpoints(runId, { limit: 20 }), client.getTaskCockpitRunProductionContext(runId), client.getTaskCockpitRunResponsibilityHandoffs(runId), client.getTaskCockpitRunApprovalReview(runId)]).then(
      ([steps, checkpoints, productionContext, responsibilityHandoffs, approvalReview]) => { if (requestId === detailRequest.current) setDetail({ runId, phase: "ready", steps, checkpoints, productionContext, responsibilityHandoffs, approvalReview }); },
      () => { if (requestId === detailRequest.current) setDetail({ runId, phase: "failed", steps: null, checkpoints: null, productionContext: null, responsibilityHandoffs: null, approvalReview: null }); },
    );
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

      <section className="task-cockpit-command-blocked" aria-labelledby="task-cockpit-command-title">
        <span className="task-cockpit-command-icon" aria-hidden="true">✦</span>
        <div>
          <h2 id="task-cockpit-command-title">任务指令尚未开放</h2>
          <p>当前只读展示 Task、latest Run、Step 与 Checkpoint；等待生产启动、职责和审批 authority 后再接入命令。</p>
        </div>
        <span className="task-cockpit-readonly-badge">只读模式</span>
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
              {detail?.phase === "ready" && detail.steps && detail.checkpoints && detail.productionContext && detail.responsibilityHandoffs && detail.approvalReview ? <>
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
                <section className="task-cockpit-responsibility" aria-label="本 Run 的精确职责与交接">
                  <div className="task-cockpit-production-refs"><strong>职责与交接 · {detail.responsibilityHandoffs.profile}</strong><span>{detail.responsibilityHandoffs.responsibilityPlanRef.resourceId} · v{detail.responsibilityHandoffs.responsibilityPlanRef.revision}</span><span>编译时就绪；运行就绪需独立验证</span></div>
                  <div className="task-cockpit-responsibility-grid">
                    <div><h4>职责槽位</h4><ul>{detail.responsibilityHandoffs.slots.map((slot) => <li key={slot.slotId}><strong>{slot.responsibilityType}</strong><span>{slot.slotId} → {slot.assignee.resourceId} · v{slot.assignee.version}</span><small>所需能力：{slot.requiredCapabilityIds.join("、")} · 返回阶段：{slot.returnStage}</small><em>运行就绪未验证</em></li>)}</ul></div>
                    <div><h4>交接决定链</h4>{detail.responsibilityHandoffs.handoffs.length ? <ul>{detail.responsibilityHandoffs.handoffs.map((handoff) => <li key={handoff.handoffId}><strong>{handoff.senderInstanceRef.resourceId} → {handoff.receiverInstanceRef.resourceId}</strong><span>{handoff.handoffId} · {handoff.status} · v{handoff.version}</span><small>{handoff.decisions.length ? handoff.decisions.map((decision) => `r${decision.revision} ${decision.decision}`).join(" → ") : "尚无业务决定；consumed 不等于 accepted"}</small></li>)}</ul> : <p>当前 Run 无 canonical Handoff；未使用示例交接填充。</p>}</div>
                  </div>
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
            <p>仅在 Run 携带 canonical productionContract 时展示；业务上下文与策划职责仍失败关闭。</p>
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
