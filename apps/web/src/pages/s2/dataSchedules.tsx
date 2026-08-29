import { useMemo, useState } from "react";
import { apiPatch, apiPost } from "../../api/client";
import {
  BpBanner,
  BpLinkRow,
  BpSplit,
  BpTable,
  BpTabs,
  BpToolbar,
} from "./blueprintUi";
import { PipelineWorkflowStepper, S2Chrome, useJsonGet } from "./shared";
import { getPipelineDisplayName } from "./pipelineMeta";

const CRON_PRESETS: { label: string; cron: string; hint: string }[] = [
  { label: "每小时", cron: "0 * * * *", hint: "每小时整点" },
  { label: "每天", cron: "0 2 * * *", hint: "每天 02:00" },
  { label: "每周一", cron: "0 2 * * 1", hint: "每周一 02:00" },
  { label: "自定义", cron: "", hint: "手动编辑 Cron" },
];

function cronHint(cron: string): string {
  if (cron === "0 * * * *") return "每小时整点执行";
  const daily = /^0\s+([01]?\d|2[0-3])\s+\*\s+\*\s+\*$/.exec(cron);
  if (daily) return `每天 ${daily[1].padStart(2, "0")}:00 执行 · Asia/Shanghai`;
  if (cron === "0 2 * * 1") return "每周一 02:00 执行 · Asia/Shanghai";
  return "自定义 Cron · 请确认表达式";
}

export function parseCronFields(cron: string): { label: string; value: string }[] {
  const parts = cron.trim().split(/\s+/);
  const labels = ["分", "时", "日", "月", "周"];
  if (parts.length < 5) {
    return labels.map((label) => ({ label, value: "?" }));
  }
  return labels.map((label, i) => ({ label, value: parts[i] || "*" }));
}

function nextRunLabel(cron: string, tab: "cron" | "upstream"): string {
  if (tab === "upstream") return "上游触发 · 无固定时间";
  if (cron === "0 * * * *") return "下一整点 · Asia/Shanghai";
  if (/^0\s+([01]?\d|2[0-3])\s+\*\s+\*\s+\*$/.test(cron)) return "下一日定时执行 · Asia/Shanghai";
  return "由服务端按 Cron 与 Asia/Shanghai 计算";
}

function formatRunTime(value?: string): string {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.valueOf()) ? value : parsed.toLocaleString("zh-CN", { hour12: false });
}

function formatDuration(ms?: number): string {
  if (!ms) return "—";
  return ms >= 60_000 ? `${Math.floor(ms / 60_000)}分${Math.round((ms % 60_000) / 1000)}秒` : `${Math.round(ms / 1000)}秒`;
}

export function scheduleRunStatusLabel(status?: string): string {
  const normalized = (status || "").trim().toUpperCase();
  if (normalized === "SUCCEEDED" || normalized === "SUCCESS") return "成功";
  if (normalized === "FAILED" || normalized === "ERROR") return "失败";
  if (normalized === "RUNNING" || normalized === "IN_PROGRESS") return "运行中";
  if (normalized === "SCHEDULED" || normalized === "PENDING") return "计划中";
  return normalized ? "待确认" : "未读取";
}

export function isValidScheduleDraft(name: string, pipelineId: string, cron: string): boolean {
  return Boolean(name.trim() && pipelineId.trim() && parseCronFields(cron).every((field) => field.value !== "?"));
}

/** 85 · 对齐 schedules.html · Cron 预设 + Tab + 表格 */
export function SchedulesPage() {
  const { data, err, reload } = useJsonGet<{
    items: {
      id: string;
      cron?: string;
      pipelineId?: string;
      enabled?: boolean;
      name?: string;
      lastRun?: { at?: string };
    }[];
  }>("/v1/schedules");
  const pipelines = useJsonGet<{ items: { id: string; name?: string; displayName?: string }[] }>("/v1/pipelines?page_size=50");
  const [tab, setTab] = useState<"cron" | "upstream">("cron");
  const [cron, setCron] = useState("");
  const [pipelineId, setPipelineId] = useState("");
  const [name, setName] = useState("");
  const [editId, setEditId] = useState<string | null>(null);
  const [localErr, setLocalErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const { data: runs, err: runsErr, loading: runsLoading, reload: reloadRuns } = useJsonGet<{
    items: { id: string; status: string; startedAt?: string; durationMs?: number; rowsWritten?: number; errorCode?: string; errorMessage?: string }[];
  }>(editId ? `/v1/schedules/${encodeURIComponent(editId)}/runs?limit=14` : null);

  const nextRun = useMemo(() => nextRunLabel(cron, tab), [tab, cron]);
  const cronFields = useMemo(() => parseCronFields(cron), [cron]);
  const selectedSchedule = (data?.items || []).find((item) => item.id === editId);
  const validDraft = isValidScheduleDraft(name, pipelineId, cron);

  function pipelineName(targetId?: string): string {
    if (!targetId) return "未关联管道";
    const pipeline = (pipelines.data?.items || []).find((item) => item.id === targetId);
    return pipeline?.displayName || pipeline?.name || getPipelineDisplayName(targetId);
  }

  async function createSch() {
    setLocalErr(null);
    try {
      const item = await apiPost<{ id: string }>("/v1/schedules", {
        cron,
        pipelineId,
        name: name || undefined,
        enabled: true,
      });
      setMsg(`已创建 ${item.id}`);
      setEditId(item.id);
      reload();
    } catch (e) {
      setLocalErr(String((e as Error).message || e));
    }
  }

  async function saveSch() {
    if (!editId) {
      setLocalErr("先点选或新建一条计划");
      return;
    }
    setLocalErr(null);
    try {
      await apiPatch(`/v1/schedules/${encodeURIComponent(editId)}`, {
        cron,
        pipelineId,
        name: name || undefined,
        enabled: true,
      });
      setMsg(`已保存 ${editId}`);
      reload();
    } catch (e) {
      setLocalErr(String((e as Error).message || e));
    }
  }

  async function runNow() {
    if (!editId) {
      setLocalErr("先选择一条真实计划");
      return;
    }
    setLocalErr(null);
    try {
      const result = await apiPost<{ status: string; lastRun?: { rowsWritten?: number } }>(`/v1/schedules/${encodeURIComponent(editId)}/run`, {});
      setMsg(result.status === "succeeded" ? `真实同步完成：${result.lastRun?.rowsWritten ?? 0} 行` : `同步未成功：${result.status}`);
      reload();
      reloadRuns();
    } catch (e) {
      setLocalErr(String((e as Error).message || e));
    }
  }

  return (
    <S2Chrome title="同步计划编辑器" lede="管理栖月汇业务数据的周期同步计划与真实运行记录">
      <PipelineWorkflowStepper current={2} />
      <BpSplit
        left={
          <div className="bp-object-panel">
            <label className="muted" style={{ display: "block", fontSize: "0.75rem" }}>
              计划名称
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                style={{ display: "block", width: "100%", marginTop: 4 }}
              />
            </label>

            <BpTabs
              tabs={[
                { id: "cron", label: "Cron 表达式" },
                { id: "upstream", label: "上游触发" },
              ]}
              active={tab}
              onChange={(id) => setTab(id as "cron" | "upstream")}
            />

            {tab === "cron" ? (
              <>
                <label className="muted" style={{ display: "block", fontSize: "0.75rem" }}>
                  Cron
                  <input
                    value={cron}
                    onChange={(e) => setCron(e.target.value)}
                    className="mono"
                    style={{ display: "block", width: "100%", marginTop: 4 }}
                  />
                </label>
                <p className="muted" style={{ fontSize: "0.65rem" }}>{cronHint(cron)}</p>
                <div className="bp-cron-field-grid" aria-label="cron-fields">
                  {cronFields.map((f) => (
                    <div key={f.label} className="bp-cron-field">
                      <span className="bp-cron-field-label">{f.label}</span>
                      <span className="bp-cron-field-value mono">{f.value}</span>
                    </div>
                  ))}
                </div>
                <div className="bp-cron-presets">
                  {CRON_PRESETS.filter((p) => p.cron).map((p) => (
                    <button
                      key={p.label}
                      type="button"
                      className={`bp-cron-preset${cron === p.cron ? " bp-cron-preset-active" : ""}`}
                      onClick={() => setCron(p.cron)}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              </>
            ) : (
              <div style={{ fontSize: "0.875rem" }}>
                <p className="muted" style={{ fontSize: "0.75rem" }}>
                  上游触发条件尚未由服务端返回，本页不会用客户端固定条件补造。
                </p>
              </div>
            )}

            <label className="muted" style={{ display: "block", marginTop: "1rem", fontSize: "0.75rem" }}>
              关联管道
              <select
                aria-label="关联管道"
                value={pipelineId}
                onChange={(e) => setPipelineId(e.target.value)}
                style={{ display: "block", width: "100%", marginTop: 4 }}
              >
                <option value="">— 请选择真实管道 —</option>
                {(pipelines.data?.items || []).map((pipeline) => (
                  <option key={pipeline.id} value={pipeline.id}>{pipeline.displayName || pipeline.name || getPipelineDisplayName(pipeline.id)}</option>
                ))}
              </select>
            </label>

            <BpToolbar>
              <button type="button" className="btn-primary" disabled={!validDraft || Boolean(editId)} onClick={() => void createSch()}>
                + 新建计划
              </button>
              <button type="button" className="btn-primary" disabled={!editId || !validDraft} onClick={() => void saveSch()}>
                保存计划
              </button>
              <button type="button" onClick={() => void runNow()} disabled={!editId}>
                立即真实同步
              </button>
              <button type="button" className="btn" onClick={() => { reload(); pipelines.reload(); if (editId) reloadRuns(); }}>
                刷新计划
              </button>
            </BpToolbar>

            <BpBanner tone="info">{cron ? cronHint(cron) : "选择已有计划或填写新计划后显示执行周期。"}</BpBanner>

            <div className="bp-cron-next-run">
              <div className="bp-cron-next-label">下次运行</div>
              <div className="bp-cron-next-value">{cron ? nextRun : "尚未选择计划"}</div>
            </div>

            <BpLinkRow
              links={[
                { to: "/data", label: "栖月汇微商城 数据源" },
                { to: "/data/pipelines", label: "管道列表" },
              ]}
            />
          </div>
        }
        right={
          <>
            <div className="bp-ws-section-title">已注册计划</div>
            {(err || pipelines.err || localErr) && <p className="error">{err || pipelines.err || localErr}</p>}
            {msg && <p className="aos-text">{msg}</p>}
            <BpTable
              columns={["名称", "执行周期", "关联管道", "最近真实执行", ""]}
              rows={(data?.items || []).map((s) => [
                s.name || s.id,
                s.cron || "—",
                <span>{pipelineName(s.pipelineId)}<details className="bp-audit-details"><summary>计划审计</summary><span className="mono">计划：{s.id} · 管道：{s.pipelineId || "未读取"}</span></details></span>,
                s.lastRun?.at ? formatRunTime(s.lastRun.at) : "暂无真实记录",
                <button
                  key={s.id}
                  type="button"
                  className="nav-link"
                  onClick={() => {
                    setEditId(s.id);
                    setCron(s.cron || "0 * * * *");
                    setPipelineId(s.pipelineId || "");
                    setName(s.name || "");
                  }}
                >
                  编辑
                </button>,
              ])}
            />
            <p className="muted" style={{ fontSize: "0.75rem" }}>
              当前编辑：{selectedSchedule?.name || (editId ? "已选择计划" : "（未选）")}
            </p>
          </>
        }
      />

      <BpLinkRow
        links={[
          { to: "/data", label: "数据源管理" },
          { to: "/data/pipelines", label: "管道构建" },
        ]}
      />

      <div style={{ marginTop: "1rem", padding: "12px", background: "var(--aos-surface, #f7fafc)", borderRadius: 4, border: "1px solid var(--aos-border, #e2e8f0)" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
          <h4 className="aos-text" style={{ fontSize: "0.8rem", margin: 0 }}>最近真实运行记录</h4>
          <span className="muted" style={{ fontSize: "0.7rem" }}>
            <span style={{ display: "inline-block", width: 8, height: 8, borderRadius: 2, background: "#10B981", marginRight: 4 }} />成功
            <span style={{ display: "inline-block", width: 8, height: 8, borderRadius: 2, background: "#EF4444", margin: "0 4px 0 8px" }} />失败
            <span style={{ display: "inline-block", width: 8, height: 8, borderRadius: 2, background: "#3B82F6", margin: "0 4px 0 8px" }} />运行中
            <span style={{ display: "inline-block", width: 8, height: 8, borderRadius: 2, background: "#D1D5DB", margin: "0 4px 0 8px" }} />计划中
          </span>
        </div>
        {!editId && <p className="muted">选择一个计划后查看其真实执行历史。</p>}
        {editId && runsLoading && <p className="muted">读取真实运行记录…</p>}
        {editId && (runsErr || localErr) && <p className="error">{runsErr || localErr}</p>}
        {editId && !runsLoading && !runsErr && (runs?.items.length || 0) === 0 && <p className="muted">暂无真实运行记录；不会展示示例历史。</p>}
        {editId && (runs?.items || []).map((run) => (
          <div key={run.id} style={{ display: "grid", gridTemplateColumns: "150px 90px 100px 100px 1fr", gap: 8, padding: "7px 0", borderTop: "1px solid var(--aos-border, #e2e8f0)", fontSize: "0.75rem" }}>
            <span>{formatRunTime(run.startedAt)}</span>
            <strong>{scheduleRunStatusLabel(run.status)}</strong>
            <span>{formatDuration(run.durationMs)}</span>
            <span>{run.rowsWritten == null ? "写入行数未读取" : `${run.rowsWritten} 行`}</span>
            <details className="bp-audit-details"><summary>运行审计</summary><span className="muted">状态：{run.status || "未读取"} · 错误：{run.errorCode || run.errorMessage || "无"}</span></details>
          </div>
        ))}
      </div>
    </S2Chrome>
  );
}
