import { useCallback, useEffect, useRef, useState } from "react";

import {
  aipTasksSdk,
  type AipTasksSdk,
  type TaskRunSnapshot,
  type TaskTimeline,
} from "../../api/aipTasks";
import "./CanonicalTaskRunPanel.css";

type VisibleStatus = "queued" | "running" | "paused" | "succeeded" | "failed" | "cancelled" | "unknown";
type Control = "start" | "pause" | "resume" | "cancel" | "rollback";

export interface CanonicalTaskRunPanelProps {
  graphId: string;
  graphRevision: number;
  graphName: string;
  sdk?: AipTasksSdk;
}

const STATUS_LABELS: Record<VisibleStatus, string> = {
  queued: "等待启动", running: "运行中", paused: "已暂停", succeeded: "已完成",
  failed: "失败", cancelled: "已取消", unknown: "结果待对账",
};

function visibleStatus(timeline: TaskTimeline): VisibleStatus {
  if (timeline.run.status === "unknown") return "unknown";
  if (timeline.task.status === "paused") return "paused";
  return timeline.run.status;
}

function message(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function value(row: Record<string, unknown>, camel: string, snake: string): unknown {
  return row[camel] ?? row[snake];
}

function EvidenceCollection({ title, items, fields }: {
  title: string;
  items: Array<Record<string, unknown>>;
  fields: Array<[string, string, string]>;
}) {
  return (
    <details className="canonical-task-run__collection">
      <summary>{title}（{items.length}）</summary>
      {items.length === 0 ? <p>暂无服务端记录。</p> : (
        <ol>
          {items.map((item, index) => (
            <li key={String(value(item, "id", `${title.toLowerCase()}_id`) ?? index)}>
              {fields.map(([label, camel, snake]) => (
                <span key={camel}><strong>{label}</strong>{String(value(item, camel, snake) ?? "—")}</span>
              ))}
            </li>
          ))}
        </ol>
      )}
    </details>
  );
}

export function CanonicalTaskRunPanel({ graphId, graphRevision, graphName, sdk = aipTasksSdk }: CanonicalTaskRunPanelProps) {
  const [timeline, setTimeline] = useState<TaskTimeline | null>(null);
  const [history, setHistory] = useState<TaskRunSnapshot[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [receipt, setReceipt] = useState("");
  const generation = useRef(0);

  const load = useCallback(async (preferredRunId?: string) => {
    const current = ++generation.current;
    setLoading(true);
    setError("");
    try {
      const runs = await sdk.listRunsByLogic(graphId);
      if (current !== generation.current) return;
      setHistory(runs.items);
      const runId = preferredRunId ?? runs.items[0]?.id;
      if (!runId) {
        setTimeline(null);
        return;
      }
      const next = await sdk.timeline(runId);
      if (current !== generation.current) return;
      if (next.run.logicGraphId !== graphId) throw new Error("服务端返回的 TaskRun 不属于当前 Logic Graph");
      setTimeline(next);
    } catch (loadError) {
      if (current !== generation.current) return;
      setError(message(loadError));
    } finally {
      if (current === generation.current) setLoading(false);
    }
  }, [graphId, sdk]);

  useEffect(() => {
    setTimeline(null);
    setHistory([]);
    setReceipt("");
    void load();
    return () => { generation.current += 1; };
  }, [load]);

  const createApprovedRun = async () => {
    setBusy(true);
    setError("");
    setReceipt("正在创建 Task…");
    try {
      const task = await sdk.createTask({
        type: "logic_graph_run",
        title: `${graphName} · 权威运行`,
        description: `绑定 Logic Graph ${graphId} revision ${graphRevision}`,
      });
      setReceipt("Task 已创建，正在生成精确 PlanRevision…");
      const plan = await sdk.createPlan(task, [{ stepKey: "execute_logic_graph", title: `执行 ${graphName} revision ${graphRevision}` }]);
      const plannedTask = await sdk.getTask(task.id);
      setReceipt("PlanRevision 已生成，正在批准精确 hash…");
      await sdk.approvePlan(plannedTask, plan);
      const approvedTask = await sdk.getTask(task.id);
      setReceipt("批准已接受，正在创建 queued TaskRun…");
      const run = await sdk.createRun(approvedTask, plan, { graphId, revision: graphRevision });
      setReceipt(`创建请求已接受；已从服务端回读 ${run.status} 终态快照。`);
      await load(run.id);
    } catch (createError) {
      setError(message(createError));
      setReceipt("");
    } finally {
      setBusy(false);
    }
  };

  const control = async (operation: Control) => {
    if (!timeline) return;
    setBusy(true);
    setError("");
    setReceipt(`${operation} 请求提交中…`);
    try {
      const accepted = await sdk.control(operation, timeline, `Logic Run Panel ${operation}`);
      setReceipt(`${operation} 请求已接受（${accepted.run.status}）；正在回读 timeline 最终状态…`);
      await load(accepted.run.id);
    } catch (controlError) {
      setError(message(controlError));
      setReceipt("");
    } finally {
      setBusy(false);
    }
  };

  const status = timeline ? visibleStatus(timeline) : null;
  return (
    <section className="canonical-task-run" aria-label="权威任务运行面板">
      <header>
        <div>
          <span className="canonical-task-run__eyebrow">服务端权威记录 · 任务 / 执行计划 / 运行实例</span>
          <h3>权威任务运行</h3>
          <p>绑定 {graphName} · 修订 {graphRevision}；刷新后从服务端恢复，不使用本地完成状态。</p>
        </div>
        <div className="canonical-task-run__actions">
          <button type="button" disabled={busy || loading} onClick={() => void load(timeline?.run.id)}>刷新 / 对账</button>
          <button type="button" disabled={busy || loading} onClick={() => void createApprovedRun()}>
            {timeline ? "新建一次权威运行" : "创建任务、执行计划并批准"}
          </button>
        </div>
      </header>

      {loading && <p role="status" className="canonical-task-run__notice">正在读取服务端任务运行记录…</p>}
      {receipt && <p role="status" className="canonical-task-run__notice is-success">{receipt}</p>}
      {error && <p role="alert" className="canonical-task-run__notice is-error">{error}</p>}

      {!loading && !timeline && !error && (
        <div className="canonical-task-run__empty">当前业务逻辑尚无权威任务运行记录。安全试跑记录不会冒充生产任务运行。</div>
      )}

      {timeline && status && (
        <>
          <div className="canonical-task-run__status-row">
            <span className={`canonical-task-run__status is-${status}`}>{STATUS_LABELS[status]}</span>
            <code>{timeline.run.id}</code>
            <span>任务 {timeline.task.id}</span>
            <span>执行计划修订 {timeline.plan.revision}</span>
            <span>运行版本 {timeline.run.version} / 任务版本 {timeline.task.version}</span>
          </div>

          {status === "unknown" && (
            <div className="canonical-task-run__unknown" role="alert">
              外部动作结果不确定：仅允许刷新和对账，禁止自动重复动作。等待后续对账写入权威观察结果。
            </div>
          )}

          <div className="canonical-task-run__controls" aria-label="任务运行控制">
            <button type="button" disabled={busy || status !== "queued"} onClick={() => void control("start")}>启动</button>
            <button type="button" disabled={busy || status !== "running"} onClick={() => void control("pause")}>暂停</button>
            <button type="button" disabled={busy || status !== "paused"} onClick={() => void control("resume")}>恢复</button>
            <button type="button" disabled={busy || !["queued", "running", "paused"].includes(status)} onClick={() => void control("cancel")}>取消</button>
            <button type="button" disabled={busy || status !== "succeeded"} onClick={() => void control("rollback")}>回滚</button>
            <a href={`/aip/drafts?taskId=${encodeURIComponent(timeline.task.id)}&runId=${encodeURIComponent(timeline.run.id)}`}>
              查看本次受控业务动作
            </a>
          </div>

          <div className="canonical-task-run__facts">
            <div><strong>任务状态</strong><span>{timeline.task.status}</span></div>
            <div><strong>运行状态</strong><span>{timeline.run.status}</span></div>
            <div><strong>执行计划摘要</strong><code>{timeline.plan.contentHash}</code></div>
            <div><strong>最后检查点</strong><span>{timeline.run.lastCheckpointId ?? "尚无"}</span></div>
          </div>

          <div className="canonical-task-run__evidence-grid">
            <EvidenceCollection title="步骤运行" items={timeline.steps} fields={[["步骤", "stepKey", "step_key"], ["状态", "status", "status"], ["尝试", "attempt", "attempt"]]} />
            <EvidenceCollection title="检查点" items={timeline.checkpoints} fields={[["序号", "sequence", "sequence"], ["状态摘要", "stateHash", "state_hash"], ["时间", "createdAt", "created_at"]]} />
            <EvidenceCollection title="运行产物" items={timeline.artifacts} fields={[["类型", "type", "type"], ["内容摘要", "contentHash", "content_hash"], ["时间", "createdAt", "created_at"]]} />
            <EvidenceCollection title="运行证据" items={timeline.evidence} fields={[["类型", "type", "type"], ["来源", "source", "source"], ["时间", "createdAt", "created_at"]]} />
          </div>

          {history.length > 1 && (
            <details className="canonical-task-run__history">
              <summary>当前业务逻辑的历史运行（{history.length}）</summary>
              <ol>{history.map((run) => (
                <li key={run.id}>
                  <button type="button" disabled={busy || run.id === timeline.run.id} onClick={() => void load(run.id)}>
                    {run.id} · {run.status} · r{run.logicRevision ?? "—"}
                  </button>
                </li>
              ))}</ol>
            </details>
          )}
        </>
      )}
    </section>
  );
}
