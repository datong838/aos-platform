import { useEffect, useRef, useState } from "react";

import {
  EcommerceWorkshopClientError,
  ecommerceWorkshopClient,
  type TaskCockpitCheckpointPageResponse,
  type TaskCockpitCoreResponse,
  type TaskCockpitStepPageResponse,
  type TaskCockpitTaskStatus,
} from "../../api/ecommerceWorkshop";
import { AsyncStateBoundary, type AsyncState } from "./AsyncStateBoundary";

type CockpitClient = Pick<typeof ecommerceWorkshopClient, "getTaskCockpitCore" | "listTaskCockpitRunSteps" | "listTaskCockpitRunCheckpoints">;
type CorePhase = "loading" | "ready" | "empty" | "stale" | "forbidden" | "failed";
type DetailState = { runId: string; phase: "loading" | "ready" | "failed"; steps: TaskCockpitStepPageResponse | null; checkpoints: TaskCockpitCheckpointPageResponse | null } | null;
const TASK_STATUSES: readonly { value: "" | TaskCockpitTaskStatus; label: string }[] = [
  { value: "", label: "全部状态" }, { value: "pending", label: "待规划" }, { value: "planning", label: "规划中" }, { value: "awaiting_approval", label: "待审批" }, { value: "approved", label: "已批准" }, { value: "executing", label: "执行中" }, { value: "paused", label: "已暂停" }, { value: "completed", label: "已完成" }, { value: "failed", label: "失败" }, { value: "cancelled", label: "已取消" }, { value: "rolled_back", label: "已回滚" },
];

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
    setDetail({ runId, phase: "loading", steps: null, checkpoints: null });
    void Promise.all([client.listTaskCockpitRunSteps(runId, { limit: 20 }), client.listTaskCockpitRunCheckpoints(runId, { limit: 20 })]).then(
      ([steps, checkpoints]) => { if (requestId === detailRequest.current) setDetail({ runId, phase: "ready", steps, checkpoints }); },
      () => { if (requestId === detailRequest.current) setDetail({ runId, phase: "failed", steps: null, checkpoints: null }); },
    );
  };

  const content = response ? (
    <div className="task-cockpit-read-model">
      <section className="task-cockpit-scope" aria-labelledby="task-cockpit-scope-title">
        <h2 id="task-cockpit-scope-title">当前只读范围</h2>
        <p>已接入 Task、latest Run、Step 与 Checkpoint；未接入的生产阶段、职责交接和业务上下文在下方明确阻断。</p>
        <dl><div><dt>评估时间</dt><dd>{formatTime(response.evaluatedAt)}</dd></div><div><dt>成员截止</dt><dd>{formatTime(response.taskCutoff)}</dd></div><div><dt>状态一致性</dt><dd>逐页读取当前权威状态</dd></div></dl>
      </section>
      <section className="task-cockpit-blockers" aria-labelledby="task-cockpit-blockers-title">
        <h2 id="task-cockpit-blockers-title">尚未接入的权威范围</h2>
        <ul>{response.blockers.map((blocker) => <li key={blocker.code}><strong>{blocker.code}</strong><span>{blocker.severity} · {blocker.dependency}</span><p>{blocker.requiredAction}</p></li>)}</ul>
      </section>
      <section className="task-cockpit-tasks" aria-labelledby="task-cockpit-tasks-title">
        <div className="task-cockpit-section-heading"><h2 id="task-cockpit-tasks-title">任务权威集合</h2><span>{response.page.count} 项（当前页）</span></div>
        {response.items.length === 0 ? <p role="status">当前权威 Task 集合为空；没有使用示例任务填充。</p> : null}
        {response.items.map((task) => {
          const detailId = `task-cockpit-run-${task.run?.runId ?? task.taskId}`;
          const isOpen = Boolean(task.run && detail?.runId === task.run.runId);
          return <article className="task-cockpit-card" key={task.taskId}>
            <div className="task-cockpit-card-heading"><div><p>{task.taskType}</p><h3>{task.title}</h3></div><span>{task.status}</span></div>
            <dl><div><dt>优先级</dt><dd>{task.priority}</dd></div><div><dt>Task 版本</dt><dd>v{task.version}</dd></div><div><dt>最近更新</dt><dd>{formatTime(task.updatedAt)}</dd></div><div><dt>Run</dt><dd>{task.run ? `${task.run.status} · v${task.run.version}` : "尚无 Run"}</dd></div></dl>
            {task.run ? <button type="button" aria-expanded={isOpen} aria-controls={detailId} onClick={() => toggleDetails(task.run!.runId)}>{isOpen ? "收起运行明细" : "查看运行明细"}</button> : null}
            {isOpen ? <div id={detailId} className="task-cockpit-run-detail">
              {detail?.phase === "loading" ? <div role="status">正在读取 Step 与 Checkpoint…</div> : null}
              {detail?.phase === "failed" ? <div role="alert">运行明细读取失败；未使用空集合代替。</div> : null}
              {detail?.phase === "ready" && detail.steps && detail.checkpoints ? <>
                <table><caption>Step（{detail.steps.page.count} 项，当前页）</caption><thead><tr><th scope="col">步骤</th><th scope="col">尝试</th><th scope="col">状态</th><th scope="col">输入/输出/错误</th></tr></thead><tbody>{detail.steps.items.length ? detail.steps.items.map((step) => <tr key={step.stepRunId}><th scope="row">{step.stepKey}</th><td>{step.attempt}</td><td>{step.status}</td><td>{step.hasInputRefs ? "有" : "无"}/{step.hasOutputRefs ? "有" : "无"}/{step.hasError ? "有" : "无"}</td></tr>) : <tr><td colSpan={4}>当前权威 Step 集合为空</td></tr>}</tbody></table>
                <table><caption>Checkpoint（{detail.checkpoints.page.count} 项，当前页）</caption><thead><tr><th scope="col">序号</th><th scope="col">步骤</th><th scope="col">状态哈希</th><th scope="col">产物数</th></tr></thead><tbody>{detail.checkpoints.items.length ? detail.checkpoints.items.map((checkpoint) => <tr key={checkpoint.checkpointId}><th scope="row">{checkpoint.sequence}</th><td>{checkpoint.stepKey ?? "未绑定步骤"}</td><td>{checkpoint.stateHash}</td><td>{checkpoint.artifactCount}</td></tr>) : <tr><td colSpan={4}>当前权威 Checkpoint 集合为空</td></tr>}</tbody></table>
                {detail.steps.page.hasMore || detail.checkpoints.page.hasMore ? <p role="status">运行明细仍有后续页；本子波不截断冒充完整集合。</p> : null}
              </> : null}
            </div> : null}
          </article>;
        })}
        {response.page.hasMore && response.page.nextCursor ? <button type="button" onClick={() => load(status, response.page.nextCursor ?? undefined)}>读取下一页</button> : null}
      </section>
    </div>
  ) : null;

  return <section className="task-cockpit-page" aria-label="日常任务总控只读视图">
    <div className="task-cockpit-toolbar"><label htmlFor="task-cockpit-status">任务状态</label><select id="task-cockpit-status" value={status} onChange={(event) => { const next = event.target.value as "" | TaskCockpitTaskStatus; setStatus(next); load(next); }}>{TASK_STATUSES.map((item) => <option key={item.value || "all"} value={item.value}>{item.label}</option>)}</select><button type="button" onClick={() => load(status, undefined, Boolean(response))}>重新读取</button></div>
    <AsyncStateBoundary state={stateFor(phase)} dataCutoff={response?.taskCutoff} title={phase === "stale" ? "游标或当前快照已变化" : undefined} description={phase === "stale" ? "保留已标记内容；请重新读取首屏，不会自动重放旧游标。" : undefined} action={phase === "stale" || phase === "failed" ? <button type="button" onClick={() => load(status)}>重新读取首屏</button> : undefined}>{content}</AsyncStateBoundary>
  </section>;
}
