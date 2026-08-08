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

const CRON_PRESETS: { label: string; cron: string; hint: string }[] = [
  { label: "每小时", cron: "0 * * * *", hint: "每小时整点" },
  { label: "每天", cron: "0 2 * * *", hint: "每天 02:00" },
  { label: "每周一", cron: "0 2 * * 1", hint: "每周一 02:00" },
  { label: "自定义", cron: "", hint: "手动编辑 Cron" },
];

// 近 14 次运行历史（UI 展示种子数据，后端暂无 Schedule Run History API）
const RUN_HISTORY: { status: "success" | "failed" | "running" | "scheduled"; time: string; duration: string }[] = [
  { status: "success", time: "2026-07-27 02:00", duration: "3m 24s" },
  { status: "success", time: "2026-07-26 02:00", duration: "3m 12s" },
  { status: "success", time: "2026-07-25 02:00", duration: "4m 01s" },
  { status: "failed", time: "2026-07-24 02:00", duration: "1m 30s" },
  { status: "success", time: "2026-07-23 02:00", duration: "3m 45s" },
  { status: "success", time: "2026-07-22 02:00", duration: "3m 33s" },
  { status: "success", time: "2026-07-21 02:00", duration: "3m 58s" },
  { status: "running", time: "2026-07-20 02:00", duration: "2m 15s…" },
  { status: "success", time: "2026-07-19 02:00", duration: "3m 09s" },
  { status: "success", time: "2026-07-18 02:00", duration: "3m 27s" },
  { status: "scheduled", time: "2026-07-17 02:00", duration: "—" },
  { status: "success", time: "2026-07-16 02:00", duration: "3m 51s" },
  { status: "success", time: "2026-07-15 02:00", duration: "3m 40s" },
  { status: "success", time: "2026-07-14 02:00", duration: "3m 22s" },
];

function cronHint(cron: string): string {
  if (cron === "0 * * * *") return "每小时整点执行";
  if (cron === "0 2 * * *") return "每天 02:00 执行 · Asia/Shanghai";
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
  if (cron === "0 2 * * *") return "2026-07-19 02:00:00 · Asia/Shanghai";
  if (cron === "0 2 * * 1") return "2026-07-21 02:00:00 · Asia/Shanghai（周一）";
  if (cron === "0 * * * *") return "下一整点 · Asia/Shanghai";
  return "按自定义 Cron 计算 · Asia/Shanghai";
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
    }[];
  }>("/v1/schedules");
  const [tab, setTab] = useState<"cron" | "upstream">("cron");
  const [cron, setCron] = useState("0 2 * * *");
  const [pipelineId, setPipelineId] = useState("");
  const [name, setName] = useState("订单清洗 · 每日增量");
  const [editId, setEditId] = useState<string | null>(null);
  const [upstreamA, setUpstreamA] = useState(true);
  const [upstreamB, setUpstreamB] = useState(false);
  const [localErr, setLocalErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const nextRun = useMemo(() => nextRunLabel(cron, tab), [tab, cron]);
  const cronFields = useMemo(() => parseCronFields(cron), [cron]);

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

  return (
    <S2Chrome title="同步计划编辑器" lede="Cron 调度与上游触发 · GET/POST/PATCH /v1/schedules">
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
                  当上游数据集或管道构建成功时触发本计划。
                </p>
                <label style={{ display: "block", marginTop: 8 }}>
                  <input type="checkbox" checked={upstreamA} onChange={(e) => setUpstreamA(e.target.checked)} />{" "}
                  栖月汇-订单（P05）· 同步完成
                </label>
                <label style={{ display: "block", marginTop: 4 }}>
                  <input type="checkbox" checked={upstreamB} onChange={(e) => setUpstreamB(e.target.checked)} />{" "}
                  栖月汇-发货（P07）· 搭建成功触发
                </label>
              </div>
            )}

            <label className="muted" style={{ display: "block", marginTop: "1rem", fontSize: "0.75rem" }}>
              关联 Pipeline
              <input
                value={pipelineId}
                onChange={(e) => setPipelineId(e.target.value)}
                style={{ display: "block", width: "100%", marginTop: 4 }}
              />
            </label>

            <BpToolbar>
              <button type="button" className="btn-primary" onClick={() => void createSch()}>
                + 新建计划
              </button>
              <button type="button" className="btn-primary" onClick={() => void saveSch()}>
                保存计划
              </button>
            </BpToolbar>

            <BpBanner tone="info">{cronHint(cron)}</BpBanner>

            <div className="bp-cron-next-run">
              <div className="bp-cron-next-label">下次运行</div>
              <div className="bp-cron-next-value">{nextRun}</div>
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
            {(err || localErr) && <p className="error">{err || localErr}</p>}
            {msg && <p className="aos-text">{msg}</p>}
            <BpTable
              columns={["名称", "Cron", "Pipeline", ""]}
              rows={(data?.items || []).map((s) => [
                s.name || s.id,
                s.cron || "—",
                s.pipelineId || "—",
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
              当前编辑：{editId || "（未选）"}
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

      {/* Phase 7: 运行历史可视化条形图 */}
      <div style={{ marginTop: "1rem", padding: "12px", background: "var(--aos-surface, #f7fafc)", borderRadius: 4, border: "1px solid var(--aos-border, #e2e8f0)" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
          <h4 className="aos-text" style={{ fontSize: "0.8rem", margin: 0 }}>近 14 次运行历史</h4>
          <span className="muted" style={{ fontSize: "0.7rem" }}>
            <span style={{ display: "inline-block", width: 8, height: 8, borderRadius: 2, background: "#10B981", marginRight: 4 }} />成功
            <span style={{ display: "inline-block", width: 8, height: 8, borderRadius: 2, background: "#EF4444", margin: "0 4px 0 8px" }} />失败
            <span style={{ display: "inline-block", width: 8, height: 8, borderRadius: 2, background: "#3B82F6", margin: "0 4px 0 8px" }} />运行中
            <span style={{ display: "inline-block", width: 8, height: 8, borderRadius: 2, background: "#D1D5DB", margin: "0 4px 0 8px" }} />计划中
          </span>
        </div>
        <div style={{ display: "flex", gap: 2, alignItems: "flex-end", height: 28 }}>
          {RUN_HISTORY.map((r, i) => (
            <div
              key={i}
              className={`bp-sched-run-bar bp-sched-run-bar-${r.status}`}
              style={{
                width: 12,
                height: r.status === "success" ? 28 : r.status === "failed" ? 20 : r.status === "running" ? 24 : 16,
                borderRadius: 2,
                background: r.status === "success" ? "#10B981" : r.status === "failed" ? "#EF4444" : r.status === "running" ? "#3B82F6" : "#D1D5DB",
              }}
              title={`${r.time} · ${r.status} · ${r.duration}`}
            />
          ))}
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4, fontSize: "0.65rem", color: "var(--aos-text-muted, #718096)" }}>
          <span>14 天前</span>
          <span>今天</span>
        </div>
      </div>
    </S2Chrome>
  );
}
