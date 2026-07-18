import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiPatch, apiPost } from "../../api/client";
import {
  BpBanner,
  BpLinkRow,
  BpSplit,
  BpTable,
  BpTabs,
  BpToolbar,
} from "./blueprintUi";
import { S2Chrome, useJsonGet } from "./shared";

const CRON_PRESETS: { label: string; cron: string; hint: string }[] = [
  { label: "每小时", cron: "0 * * * *", hint: "每小时整点" },
  { label: "每天", cron: "0 2 * * *", hint: "每天 02:00" },
  { label: "每周一", cron: "0 2 * * 1", hint: "每周一 02:00" },
  { label: "自定义", cron: "", hint: "手动编辑 Cron" },
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
  const [pipelineId, setPipelineId] = useState("demo-pipe-wo");
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
                  raw_orders 同步完成
                </label>
                <label style={{ display: "block", marginTop: 4 }}>
                  <input type="checkbox" checked={upstreamB} onChange={(e) => setUpstreamB(e.target.checked)} />{" "}
                  库存聚合管道 #build-8842
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
              <button type="button" className="btn" onClick={() => void createSch()}>
                新建
              </button>
              <button type="button" className="btn" onClick={() => void saveSch()}>
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
                { to: "/data", label: "prod-mysql-orders 同步" },
                { to: "/data/pipelines", label: "订单清洗管道" },
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
          { to: "/data", label: "数据连接" },
          { to: "/data/pipelines", label: "管道构建" },
        ]}
      />
    </S2Chrome>
  );
}
