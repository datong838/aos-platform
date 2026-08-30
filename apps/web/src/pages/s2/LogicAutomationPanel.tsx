import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import type { LogicPublication } from "./logicPublicationContracts";
import {
  createLogicAutomation,
  listLogicAutomationRuns,
  listLogicAutomations,
  triggerLogicAutomation,
  updateLogicAutomation,
} from "./logicAutomationApi";
import type { LogicAutomationPolicy, LogicAutomationRun, LogicAutomationTrigger } from "./logicAutomationContracts";

interface Props {
  graphId: string;
  graphRevision: number;
  graphHash: string;
  persisted: boolean;
  publications: readonly LogicPublication[];
}

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : "请求失败，请重试";
}

function requestKey(automationId: string): string {
  const nonce = typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `logic-automation:${automationId}:${nonce}`.slice(0, 200);
}

export function LogicAutomationPanel({ graphId, graphRevision, graphHash, persisted, publications }: Props) {
  const [items, setItems] = useState<LogicAutomationPolicy[]>([]);
  const [runs, setRuns] = useState<Record<string, LogicAutomationRun[]>>({});
  const [name, setName] = useState("经营任务自动化");
  const [publicationId, setPublicationId] = useState("");
  const [triggerType, setTriggerType] = useState<LogicAutomationTrigger>("manual");
  const [schedule, setSchedule] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const publicationOptions = useMemo(
    () => [...publications].sort((a, b) => b.graph_revision - a.graph_revision),
    [publications],
  );

  async function refresh(): Promise<void> {
    if (!persisted) return;
    setError("");
    try {
      const result = await listLogicAutomations(graphId);
      setItems(result.items);
      const histories = await Promise.all(result.items.map(async (item) => [
        item.automation_id,
        (await listLogicAutomationRuns(graphId, item.automation_id)).items,
      ] as const));
      setRuns(Object.fromEntries(histories));
    } catch (loadError) {
      setError(messageOf(loadError));
    }
  }

  useEffect(() => {
    setItems([]);
    setRuns({});
    setPublicationId(publicationOptions[0]?.publication_id || "");
    if (persisted) void refresh();
  }, [graphId, persisted, publicationOptions]);

  async function createPolicy(): Promise<void> {
    if (!publicationId || !name.trim()) return;
    setBusy("create");
    setError("");
    try {
      const created = await createLogicAutomation(graphId, {
        publication_id: publicationId,
        name: name.trim(),
        trigger_type: triggerType,
        schedule: triggerType === "manual" ? "" : schedule.trim(),
      });
      setNotice(`已建立“${created.name}”，绑定正式发布修订 ${created.graph_revision}`);
      await refresh();
    } catch (createError) {
      setError(messageOf(createError));
    } finally {
      setBusy("");
    }
  }

  async function changeStatus(item: LogicAutomationPolicy): Promise<void> {
    setBusy(item.automation_id);
    setError("");
    try {
      const next = item.status === "active" ? "paused" : "active";
      await updateLogicAutomation(graphId, item.automation_id, {
        expected_revision: item.revision,
        status: next,
      });
      setNotice(next === "paused" ? `已暂停“${item.name}”` : `已恢复“${item.name}”`);
      await refresh();
    } catch (updateError) {
      setError(messageOf(updateError));
    } finally {
      setBusy("");
    }
  }

  async function trigger(item: LogicAutomationPolicy): Promise<void> {
    setBusy(`trigger:${item.automation_id}`);
    setError("");
    try {
      const run = await triggerLogicAutomation(graphId, item.automation_id, requestKey(item.automation_id));
      setNotice(`已受理“${item.name}”并创建任务运行；未写入生产业务数据`);
      setRuns((current) => ({ ...current, [item.automation_id]: [run, ...(current[item.automation_id] || [])] }));
    } catch (triggerError) {
      setError(messageOf(triggerError));
    } finally {
      setBusy("");
    }
  }

  return (
    <section className="card" style={{ padding: 18 }} role="tabpanel" id="logic-panel-automation" aria-labelledby="logic-tab-automation" data-testid="logic-automation-panel">
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "start" }}>
        <div>
          <h2 style={{ marginTop: 0, marginBottom: 6 }}>自动化</h2>
          <p style={{ margin: 0, color: "var(--aos-text-secondary)", maxWidth: 680 }}>
            自动化只绑定已通过评测的不可变正式发布。手动触发会建立可审计的任务、计划和运行，不调用外部供应商，也不写生产业务数据。
          </p>
        </div>
        <button type="button" className="btn" onClick={() => void refresh()} disabled={!persisted || Boolean(busy)}>重新读取</button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(160px,1fr))", gap: 10, margin: "14px 0" }}>
        {[
          ["当前业务逻辑", persisted ? graphId : "请先保存"],
          ["当前修订", persisted ? String(graphRevision) : "—"],
          ["自动化规则", String(items.length)],
          ["已记录运行", String(Object.values(runs).reduce((sum, value) => sum + value.length, 0))],
        ].map(([label, value]) => <div key={label} className="notice" style={{ padding: "10px 12px" }}><div className="muted">{label}</div><strong>{value}</strong></div>)}
      </div>

      {persisted && <details className="notice" style={{ padding: 12 }}><summary>当前修订技术标识（审计用）</summary><code>{graphId}@{graphRevision}</code> · <code>{graphHash}</code></details>}
      {error && <div role="alert" className="notice" style={{ marginTop: 10, borderColor: "var(--aos-red-border)", color: "var(--aos-red)" }}>{error}</div>}
      {notice && <div role="status" className="notice" style={{ marginTop: 10, borderColor: "var(--aos-green-border)", color: "var(--aos-green-700)" }}>{notice}</div>}

      <section style={{ border: "1px solid var(--aos-border)", marginTop: 12, padding: 12 }} aria-label="新建自动化规则">
        <h3 style={{ margin: "0 0 8px" }}>新建自动化规则</h3>
        <div style={{ display: "grid", gridTemplateColumns: "minmax(160px,1fr) minmax(220px,1.4fr) minmax(140px,.7fr) minmax(180px,1fr) auto", gap: 8 }}>
          <input aria-label="自动化名称" value={name} onChange={(event) => setName(event.target.value)} />
          <select aria-label="绑定正式发布" value={publicationId} onChange={(event) => setPublicationId(event.target.value)}>
            <option value="">选择正式发布</option>
            {publicationOptions.map((item) => <option key={item.publication_id} value={item.publication_id}>修订 {item.graph_revision} · {new Date(item.created_at).toLocaleString()}</option>)}
          </select>
          <select aria-label="触发方式" value={triggerType} onChange={(event) => setTriggerType(event.target.value as LogicAutomationTrigger)}>
            <option value="manual">人工触发</option>
            <option value="cron">定时触发</option>
            <option value="event">事件触发</option>
          </select>
          <input
            aria-label="触发配置"
            value={schedule}
            disabled={triggerType === "manual"}
            onChange={(event) => setSchedule(event.target.value)}
            placeholder={triggerType === "cron" ? "如 0 9 * * 1-5" : triggerType === "event" ? "如 order.paid" : "人工运行无需配置"}
          />
          <button type="button" className="btn btn-primary" disabled={!publicationId || !name.trim() || (triggerType !== "manual" && !schedule.trim()) || busy === "create"} onClick={() => void createPolicy()}>{busy === "create" ? "建立中…" : "建立规则"}</button>
        </div>
        {!publicationOptions.length && <p className="muted">请先在“编辑”分区完成安全试跑、评测与正式发布。</p>}
      </section>

      <div style={{ display: "grid", gap: 10, marginTop: 12 }}>
        {items.map((item) => (
          <article key={item.automation_id} style={{ border: "1px solid var(--aos-border)", padding: 12 }}>
            <div style={{ display: "flex", alignItems: "start", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
              <div><strong>{item.name}</strong><div className="muted">正式发布修订 {item.graph_revision} · {item.status === "active" ? "运行中" : "已暂停"} · {item.trigger_type === "manual" ? "人工触发" : item.trigger_type === "cron" ? `定时 ${item.schedule}` : `事件 ${item.schedule}`}</div></div>
              <div style={{ display: "flex", gap: 8 }}>
                <button type="button" className="btn" disabled={busy === item.automation_id} onClick={() => void changeStatus(item)}>{item.status === "active" ? "暂停" : "恢复"}</button>
                <button type="button" className="btn btn-primary" disabled={item.status !== "active" || busy === `trigger:${item.automation_id}`} onClick={() => void trigger(item)}>立即运行</button>
              </div>
            </div>
            <ol style={{ margin: "10px 0 0", paddingLeft: 20 }}>
              {(runs[item.automation_id] || []).slice(0, 5).map((run) => <li key={run.run_id}><Link to={`/aip/tasks/${encodeURIComponent(run.task_id)}?runId=${encodeURIComponent(run.task_run_id)}`}>查看任务运行</Link> · Receipt {run.receipt_id} · {new Date(run.created_at).toLocaleString()}</li>)}
            </ol>
            {!(runs[item.automation_id] || []).length && <p className="muted">尚无运行记录；可点击“立即运行”建立首条受控任务。</p>}
          </article>
        ))}
      </div>
      {!items.length && persisted && <div className="notice" style={{ marginTop: 12 }}>当前业务逻辑尚未建立自动化规则。</div>}
    </section>
  );
}
