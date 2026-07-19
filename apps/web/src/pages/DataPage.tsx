import { Fragment, useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { apiGet, apiPost } from "../api/client";
import { PageChrome } from "../components/PageChrome";
import {
  BpBanner,
  BpLinkRow,
  BpMetricGrid,
  BpPropGrid,
  BpTable,
  BpTabs,
  BpToolbar,
} from "./s2/blueprintUi";

type DatasetRow = {
  rid?: string;
  name?: string;
  status?: string;
  pipelineId?: string;
  sourceId?: string;
  objectTypeHint?: string;
};

type BuildRow = {
  id?: string;
  status?: string;
  pipelineId?: string;
};

type DlqRow = {
  id?: string;
  status?: string;
  reason?: string;
  pipelineId?: string;
};

type SourceRow = { id?: string; type?: string; status?: string; runtimeMode?: string; pluginId?: string };
type SyncRow = { id?: string; sourceId?: string; status?: string; finishedAt?: number };
type PipelineRow = { id?: string; sourceId?: string; status?: string };
type ConnectorPlugin = {
  id: string;
  nameZh?: string;
  name?: string;
  description?: string;
  installed?: boolean;
  required?: boolean;
  runtime?: string;
  capabilities?: string[];
};

type MainTab = "sources" | "syncs" | "agents" | "exports";
type SourceView = "list" | "new" | "detail";
type RuntimeMode = "direct" | "agent" | "worker";

function statusZh(s?: string): string {
  const v = (s || "").toUpperCase();
  if (!s) return "—";
  if (v === "SUCCEEDED" || v === "SUCCESS" || v === "OK" || v === "ACTIVE" || v === "ONLINE" || v === "REGISTERED")
    return "在线";
  if (v === "RUNNING" || v === "IN_PROGRESS") return "同步中";
  if (v === "FAILED" || v === "ERROR") return "失败";
  if (v === "OPEN") return "打开";
  return s;
}

function connectorLabel(t?: string, plugins?: ConnectorPlugin[]): string {
  if (!t) return "—";
  const hit = plugins?.find((p) => p.id === t);
  if (hit) return hit.nameZh || hit.name || t;
  if (t === "file" || t === "file-local") return "本地文件";
  if (t === "file-object-store") return "对象存储文件";
  if (t === "jdbc" || t === "jdbc-mysql") return "MySQL JDBC";
  return t;
}

function connectorTone(t?: string): "sky" | "emerald" | "amber" | "muted" | "violet" {
  if (t?.includes("jdbc") || t === "mysql") return "sky";
  if (t?.startsWith("file") || t === "file") return "emerald";
  if (t?.startsWith("rest")) return "amber";
  return "muted";
}

function storageLabel(t?: string): { text: string; kind: "dataset" | "media" | "stream" } {
  if (t === "file" || t?.startsWith("file")) return { text: "媒体集·文档", kind: "media" };
  return { text: "数据集", kind: "dataset" };
}

function sourceSubtitle(t?: string): string {
  if (t === "file" || t === "file-local") return "文件接入 · 本地 / 上传";
  if (t === "file-object-store") return "文件接入 · 对象存储";
  if (t === "jdbc" || t === "jdbc-mysql") return "结构化入库 · MySQL";
  if (t?.startsWith("jdbc")) return "结构化入库 · JDBC";
  return "外部系统接入";
}

function runtimeLabel(s: SourceRow): string {
  const mode = (s.runtimeMode || "").toLowerCase();
  if (mode === "agent") return "代理 · agent-local";
  if (mode === "worker") return "代理工作者";
  if (mode === "direct") return "直接连接";
  if (s.type === "jdbc") return "代理 · agent-local";
  return "直接连接";
}

function formatRelative(ts?: number): string {
  if (!ts || !Number.isFinite(ts)) return "—";
  const sec = Math.max(0, Math.round(Date.now() / 1000 - ts));
  if (sec < 60) return "刚刚";
  if (sec < 3600) return `${Math.floor(sec / 60)} 分钟前`;
  if (sec < 86400) return `${Math.floor(sec / 3600)} 小时前`;
  return `${Math.floor(sec / 86400)} 天前`;
}

function lastSyncFor(sourceId: string | undefined, syncs: SyncRow[]): string {
  if (!sourceId) return "—";
  const linked = syncs.filter((s) => s.sourceId === sourceId);
  if (!linked.length) return "—";
  const latest = linked.reduce((a, b) => ((a.finishedAt || 0) >= (b.finishedAt || 0) ? a : b));
  const st = (latest.status || "").toUpperCase();
  if (st === "RUNNING" || st === "IN_PROGRESS") return "持续运行";
  return formatRelative(latest.finishedAt);
}

function StatusDot({ status }: { status?: string }) {
  const label = statusZh(status);
  const v = (status || "").toUpperCase();
  let tone: "ok" | "warn" | "run" | "bad" | "muted" = "muted";
  if (label === "在线" || v === "SUCCEEDED" || v === "REGISTERED" || v === "ACTIVE") tone = "ok";
  else if (label === "同步中") tone = "run";
  else if (label === "失败") tone = "bad";
  else if (v.includes("WARN") || v.includes("ALERT")) tone = "warn";
  return (
    <span className={`data-status data-status-${tone}`}>
      <span className="data-status-dot" aria-hidden />
      <span>{label}</span>
    </span>
  );
}

function ConnectorTag({ type }: { type?: string }) {
  return <span className={`data-tag data-tag-${connectorTone(type)}`}>{connectorLabel(type)}</span>;
}

function StoragePill({ type }: { type?: string }) {
  const s = storageLabel(type);
  return <span className={`data-storage data-storage-${s.kind}`}>{s.text}</span>;
}

function syncRunStatus(s?: string): { label: string; tone: "ok" | "run" | "bad" | "muted" } {
  const v = (s || "").toUpperCase();
  if (v === "SUCCEEDED" || v === "SUCCESS" || v === "OK") return { label: "成功", tone: "ok" };
  if (v === "RUNNING" || v === "IN_PROGRESS") return { label: "运行中", tone: "run" };
  if (v === "FAILED" || v === "ERROR") return { label: "失败", tone: "bad" };
  if (!s) return { label: "—", tone: "muted" };
  return { label: statusZh(s), tone: "muted" };
}

function SyncStatusText({ status }: { status?: string }) {
  const { label, tone } = syncRunStatus(status);
  return <span className={`data-sync-status-${tone}`}>{label}</span>;
}

function ActionLinks({ items }: { items: { to?: string; label: string; onClick?: () => void }[] }) {
  return (
    <div className="bp-action-links">
      {items.map((it, i) => (
        <Fragment key={it.label}>
          {i > 0 ? <span className="bp-action-sep">·</span> : null}
          {it.to ? (
            <Link to={it.to} className="bp-action-link">
              {it.label}
            </Link>
          ) : (
            <button type="button" className="bp-action-link" onClick={it.onClick}>
              {it.label}
            </button>
          )}
        </Fragment>
      ))}
    </div>
  );
}

type ScheduleRow = { id?: string; pipelineId?: string; cron?: string; name?: string; enabled?: boolean };
type EdgeAgent = { id?: string; probeOk?: boolean; outbound?: boolean };

/** 74/76 · 对齐 data-connection · 六列表 · 蓝图按钮风格 */
export function DataPage() {
  const [tab, setTab] = useState<MainTab>("sources");
  const [sourceView, setSourceView] = useState<SourceView>("list");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [datasets, setDatasets] = useState<DatasetRow[]>([]);
  const [dlq, setDlq] = useState<DlqRow[]>([]);
  const [sources, setSources] = useState<SourceRow[]>([]);
  const [syncs, setSyncs] = useState<SyncRow[]>([]);
  const [pipelines, setPipelines] = useState<PipelineRow[]>([]);
  const [schedules, setSchedules] = useState<ScheduleRow[]>([]);
  const [edgeAgent, setEdgeAgent] = useState<EdgeAgent | null>(null);
  const [mediaCount, setMediaCount] = useState(0);
  const [selectedSource, setSelectedSource] = useState<SourceRow | null>(null);
  const [newSourceId, setNewSourceId] = useState("");
  const [connectorType, setConnectorType] = useState("file-local");
  const [runtimeMode, setRuntimeMode] = useState<RuntimeMode>("agent");
  const [wizardStep, setWizardStep] = useState(1);
  /** 前端记忆新建时的运行时（API 暂未持久化 runtimeMode） */
  const [runtimeById, setRuntimeById] = useState<Record<string, RuntimeMode>>({});
  const [connectorPlugins, setConnectorPlugins] = useState<ConnectorPlugin[]>([]);

  async function refresh() {
    const [ds, d, src, syn, pipes, media, sch, agent, cps] = await Promise.all([
      apiGet<{ items: DatasetRow[] }>("/v1/datasets"),
      apiGet<{ items: DlqRow[] }>("/v1/dlq"),
      apiGet<{ items: SourceRow[] }>("/v1/sources"),
      apiGet<{ items: SyncRow[] }>("/v1/syncs"),
      apiGet<{ items: PipelineRow[] }>("/v1/pipelines"),
      apiGet<{ items: unknown[] }>("/v1/media-sets"),
      apiGet<{ items: ScheduleRow[] }>("/v1/schedules").catch(() => ({ items: [] as ScheduleRow[] })),
      apiGet<EdgeAgent>("/v1/edge/agents/local").catch(() => null),
      apiGet<{ items: ConnectorPlugin[] }>("/v1/connector-plugins").catch(() => ({ items: [] as ConnectorPlugin[] })),
    ]);
    setDatasets(ds.items || []);
    setDlq(d.items || []);
    setSources(src.items || []);
    setSyncs(syn.items || []);
    setPipelines(pipes.items || []);
    setMediaCount((media.items || []).length);
    setSchedules(sch.items || []);
    setEdgeAgent(agent);
    setConnectorPlugins(cps.items || []);
    if (selectedSource?.id) {
      const found = (src.items || []).find((s) => s.id === selectedSource.id);
      if (found) setSelectedSource(enrichSource(found));
    }
  }

  function enrichSource(s: SourceRow): SourceRow {
    if (s.runtimeMode) return s;
    const remembered = s.id ? runtimeById[s.id] : undefined;
    return remembered ? { ...s, runtimeMode: remembered } : s;
  }

  useEffect(() => {
    refresh().catch((e) => setErr(String(e.message || e)));
  }, []);

  async function createSource() {
    const id = newSourceId.trim() || `src-${Date.now().toString(36)}`;
    setErr(null);
    try {
      const created = await apiPost<SourceRow>("/v1/sources", { id, type: connectorType });
      setRuntimeById((prev) => ({ ...prev, [id]: runtimeMode }));
      setMsg(`已创建数据源 ${id}`);
      setNewSourceId("");
      setWizardStep(1);
      await refresh();
      setSelectedSource({
        id,
        type: created.type || connectorType,
        status: "registered",
        runtimeMode,
        pluginId: created.pluginId,
      });
      setSourceView("detail");
      setTab("sources");
    } catch (e) {
      setErr(String((e as Error).message || e));
    }
  }

  async function installConnector(pluginId: string) {
    setErr(null);
    try {
      await apiPost(`/v1/connector-plugins/${encodeURIComponent(pluginId)}/install`, {});
      setMsg(`已安装连接器插件 ${pluginId}`);
      setConnectorType(pluginId);
      await refresh();
    } catch (e) {
      setErr(String((e as Error).message || e));
    }
  }

  async function createSyncJob() {
    setErr(null);
    if (!sources.length) {
      setErr("请先新建数据源");
      setTab("sources");
      setSourceView("new");
      return;
    }
    try {
      const sourceId = sources[0].id!;
      const sync = await apiPost<{ id: string }>("/v1/syncs", { sourceId });
      setMsg(`已创建同步 ${sync.id}`);
      await refresh();
      setTab("syncs");
    } catch (e) {
      setErr(String((e as Error).message || e));
    }
  }

  function scheduleForSource(sourceId?: string): string {
    if (!sourceId) return "—";
    const pipeIds = new Set(pipelines.filter((p) => p.sourceId === sourceId).map((p) => p.id));
    const hit = schedules.find((s) => s.pipelineId && pipeIds.has(s.pipelineId));
    if (hit?.cron) return hit.cron;
    if (hit?.name) return hit.name;
    return "—";
  }

  function targetForSource(sourceId?: string): ReactNode {
    const src = sources.find((s) => s.id === sourceId);
    if (!src) return "—";
    const ds = datasets.find((d) => d.sourceId === sourceId);
    if (ds?.name || ds?.rid) {
      return <span className="data-storage data-storage-dataset">{ds.name || ds.rid}</span>;
    }
    return <StoragePill type={src.type} />;
  }

  const linkedSyncs = syncs.filter((s) => s.sourceId === selectedSource?.id);
  const linkedPipelines = pipelines.filter((p) => p.sourceId === selectedSource?.id);

  const pipelineLinkForSource = (sourceId?: string) =>
    sourceId ? `/data/pipelines?sourceId=${encodeURIComponent(sourceId)}` : "/data/pipelines";

  function openNewSource() {
    setWizardStep(1);
    setConnectorType("file");
    setRuntimeMode("agent");
    setNewSourceId("");
    setSourceView("new");
    setTab("sources");
  }

  function openSourceDetail(s: SourceRow) {
    setSelectedSource(enrichSource(s));
    setSourceView("detail");
    setTab("sources");
  }

  const onlineCount = sources.filter((s) => statusZh(s.status) === "在线").length;
  const syncOk = syncs.filter((s) => {
    const v = (s.status || "").toUpperCase();
    return v === "SUCCEEDED" || v === "SUCCESS" || v === "OK";
  }).length;
  const syncFail = syncs.length - syncOk;

  function sourceRows(): ReactNode[][] {
    if (!sources.length) return [["—", "—", "—", "—", "—", "暂无数据源"]];
    return sources.map((raw) => {
      const s = enrichSource(raw);
      return [
        <button key={`n-${s.id}`} type="button" className="data-src-name" onClick={() => openSourceDetail(s)}>
          <span className="data-src-title">{s.id}</span>
          <span className="data-src-sub">{sourceSubtitle(s.type)}</span>
        </button>,
        <ConnectorTag key={`c-${s.id}`} type={s.type} />,
        <StoragePill key={`st-${s.id}`} type={s.type} />,
        <span key={`r-${s.id}`} className="aos-text">
          {runtimeLabel(s)}
        </span>,
        <span key={`ls-${s.id}`} className="aos-text">
          {lastSyncFor(s.id, syncs)}
        </span>,
        <StatusDot key={`ss-${s.id}`} status={s.status} />,
      ];
    });
  }

  return (
    <PageChrome
      title="数据连接"
      lede="把外部系统接入平台：先管数据源，再看同步与代理。日常从「数据源」列表运营。"
    >
      <BpTabs
        tabs={[
          { id: "sources", label: "数据源" },
          { id: "syncs", label: "同步" },
          { id: "agents", label: "代理" },
          { id: "exports", label: "导出" },
        ]}
        active={tab}
        onChange={(id) => setTab(id as MainTab)}
      />

      {msg && (
        <p className="aos-text" style={{ marginTop: "0.75rem" }}>
          {msg}
        </p>
      )}
      {err && <p className="error">{err}</p>}

      {tab === "sources" && sourceView === "list" && (
        <>
          <BpMetricGrid
            items={[
              {
                label: "数据源总数",
                value: sources.length,
                hint:
                  sources.length === 0
                    ? "暂无登记"
                    : `${onlineCount} 在线${sources.length - onlineCount ? ` · ${sources.length - onlineCount} 需关注` : ""}`,
                tone: sources.length ? "ok" : "warn",
              },
              {
                label: "今日同步",
                value: syncs.length,
                hint:
                  syncs.length === 0
                    ? "尚无同步任务"
                    : `成功 ${syncOk}${syncFail > 0 ? ` · 失败 ${syncFail}` : ""}`,
                tone: syncFail > 0 ? "warn" : "muted",
              },
              {
                label: "数据体量",
                value: datasets.length || mediaCount ? `${datasets.length + mediaCount}` : "—",
                hint: `数据集 ${datasets.length} · 媒体集 ${mediaCount}`,
                tone: datasets.length || mediaCount ? "ok" : "muted",
              },
              {
                label: "数据健康",
                value: dlq.length ? (
                  <span className="data-status data-status-warn">
                    <span className="data-status-dot" aria-hidden />
                    <span>{dlq.length} 告警</span>
                  </span>
                ) : (
                  <span className="data-status data-status-ok">
                    <span className="data-status-dot" aria-hidden />
                    <span>正常</span>
                  </span>
                ),
                hint: (
                  <Link to="/data/health" className="nav-link">
                    查看健康检查 →
                  </Link>
                ),
                tone: dlq.length ? "warn" : "ok",
              },
            ]}
          />

          <div className="filter-bar" style={{ marginTop: "0.75rem", justifyContent: "space-between" }}>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <select className="btn" disabled title="筛选占位 · 对齐蓝图">
                <option>全部类型</option>
                <option>JDBC</option>
                <option>文件</option>
              </select>
              <select className="btn" disabled title="筛选占位 · 对齐蓝图">
                <option>全部状态</option>
                <option>在线</option>
                <option>告警</option>
              </select>
              <button type="button" className="btn" onClick={() => void refresh().catch((e) => setErr(String(e)))}>
                刷新
              </button>
            </div>
            <button type="button" className="btn-primary" onClick={openNewSource}>
              + 新建数据源
            </button>
          </div>

          <div id="data-sources" className="data-conn-table" style={{ marginTop: "0.75rem" }}>
            <BpTable columns={["名称", "连接器", "存储类型", "运行时", "上次同步", "状态"]} rows={sourceRows()} />
          </div>
        </>
      )}

      {tab === "sources" && sourceView === "new" && (
        <div className="bp-object-panel" style={{ marginTop: "0.75rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 12 }}>
            <div>
              <div className="bp-object-title">新建数据源</div>
              <p className="muted" style={{ fontSize: "0.8rem", marginTop: 4 }}>
                配置连接器、运行时与凭证，将外部系统接入数据湖仓。
              </p>
            </div>
            <button type="button" className="nav-link" onClick={() => setSourceView("list")}>
              ← 返回列表
            </button>
          </div>

          <div className="data-wizard-steps" aria-label="新建步骤">
            {(["连接器", "运行时", "连接", "凭证"] as const).map((label, i) => {
              const n = i + 1;
              const active = wizardStep === n;
              const done = wizardStep > n;
              return (
                <div key={label} className="data-wizard-step">
                  <span className={`data-wizard-dot${active ? " is-active" : ""}${done ? " is-done" : ""}`}>
                    {n}
                  </span>
                  <span className={active ? "aos-text" : "muted"} style={{ fontSize: "0.8rem" }}>
                    {label}
                  </span>
                  {n < 4 && <span className="data-wizard-line" />}
                </div>
              );
            })}
          </div>

          {wizardStep === 1 && (
            <>
              <div className="bp-ws-section-title">选择连接器插件</div>
              <p className="muted" style={{ fontSize: "0.75rem" }}>
                目录来自 `plugins/connectors` · 对齐 20 §3.1 · stub 仅可装不可拉数
              </p>
              <div className="bp-discover-grid">
                {connectorPlugins.length === 0 ? (
                  <p className="muted" style={{ fontSize: "0.85rem" }}>
                    暂无连接器插件目录 · 请确认 API `/v1/connector-plugins` 与 `plugins/connectors` 可用
                  </p>
                ) : (
                  connectorPlugins.map((c) => {
                  const tone = connectorTone(c.id);
                  const selected = connectorType === c.id;
                  return (
                    <div
                      key={c.id}
                      className={`bp-discover-card bp-discover-${tone}`}
                      style={{
                        borderColor: selected ? "rgba(56,189,248,0.55)" : undefined,
                        textAlign: "left",
                      }}
                    >
                      <button
                        type="button"
                        style={{
                          all: "unset",
                          cursor: c.installed ? "pointer" : "default",
                          display: "block",
                          width: "100%",
                        }}
                        disabled={!c.installed}
                        onClick={() => c.installed && setConnectorType(c.id)}
                      >
                        <div className="bp-discover-title">
                          {c.nameZh || c.name || c.id}
                          {c.runtime === "stub" ? " · stub" : ""}
                          {c.required ? " · 必做" : ""}
                        </div>
                        <p className="bp-discover-meta">{c.description || c.id}</p>
                        <p className="muted" style={{ fontSize: "0.7rem", margin: "0.35rem 0 0" }}>
                          {c.installed ? "已安装" : "未安装"}
                        </p>
                      </button>
                      {!c.installed && (
                        <button
                          type="button"
                          className="btn-nav"
                          style={{ marginTop: 8 }}
                          onClick={() => void installConnector(c.id)}
                        >
                          安装
                        </button>
                      )}
                    </div>
                  );
                })
                )}
              </div>
              <button
                type="button"
                className="btn"
                style={{ marginTop: 12 }}
                disabled={!connectorPlugins.find((p) => p.id === connectorType)?.installed && connectorPlugins.length > 0}
                onClick={() => setWizardStep(2)}
              >
                下一步 →
              </button>
            </>
          )}

          {wizardStep === 2 && (
            <>
              <div className="bp-ws-section-title">运行时模式</div>
              <div className="data-runtime-stack">
                {(
                  [
                    {
                      id: "direct" as const,
                      title: "直接连接",
                      desc: "公网可达的数据库 / 接口，由平台侧直连拉取。",
                    },
                    {
                      id: "agent" as const,
                      title: "代理连接",
                      desc: "内网源通过边缘代理出站拉取（推荐 VPC / 专网）。",
                    },
                    {
                      id: "worker" as const,
                      title: "代理工作者",
                      desc: "高吞吐批量同步时使用专用工作者节点。",
                    },
                  ] as const
                ).map((m) => (
                  <button
                    key={m.id}
                    type="button"
                    className={`data-runtime-card${runtimeMode === m.id ? " is-selected" : ""}`}
                    onClick={() => setRuntimeMode(m.id)}
                  >
                    <div className="aos-text" style={{ fontWeight: 500 }}>
                      {m.title}
                    </div>
                    <p className="muted" style={{ fontSize: "0.75rem", marginTop: 4 }}>
                      {m.desc}
                    </p>
                  </button>
                ))}
              </div>
              <BpToolbar>
                <button type="button" className="btn" onClick={() => setWizardStep(1)}>
                  上一步
                </button>
                <button type="button" className="btn" onClick={() => setWizardStep(3)}>
                  下一步 →
                </button>
              </BpToolbar>
            </>
          )}

          {wizardStep === 3 && (
            <>
              <div className="bp-ws-section-title">连接配置</div>
              <label className="muted" style={{ display: "block", marginTop: 8 }}>
                数据源名称{" "}
                <input
                  value={newSourceId}
                  onChange={(e) => setNewSourceId(e.target.value)}
                  placeholder="prod-mysql-orders"
                  style={{ minWidth: "16rem" }}
                />
              </label>
              <p className="muted" style={{ fontSize: "0.75rem", marginTop: 8 }}>
                连接器：{connectorLabel(connectorType, connectorPlugins)} · 运行时：
                {runtimeMode === "direct" ? "直接连接" : runtimeMode === "agent" ? "代理连接" : "代理工作者"}
              </p>
              <BpToolbar>
                <button type="button" className="btn" onClick={() => setWizardStep(2)}>
                  上一步
                </button>
                <button type="button" className="btn" onClick={() => setWizardStep(4)}>
                  下一步 →
                </button>
              </BpToolbar>
            </>
          )}

          {wizardStep === 4 && (
            <>
              <div className="bp-ws-section-title">凭证</div>
              <BpBanner tone="info">凭证走密钥引用（vault ref）· 不落明文。</BpBanner>
              <BpPropGrid
                items={[
                  { label: "连接器", value: connectorLabel(connectorType, connectorPlugins) },
                  {
                    label: "运行时",
                    value: runtimeMode === "direct" ? "直接连接" : runtimeMode === "agent" ? "代理连接" : "代理工作者",
                  },
                  { label: "凭证", value: "密钥引用" },
                  { label: "名称", value: newSourceId.trim() || "（自动生成）" },
                ]}
              />
              <BpToolbar>
                <button type="button" className="btn" onClick={() => setWizardStep(3)}>
                  上一步
                </button>
                <button type="button" className="btn" onClick={() => void createSource()}>
                  创建数据源
                </button>
              </BpToolbar>
            </>
          )}
        </div>
      )}

      {tab === "sources" && sourceView === "detail" && (
        <div className="bp-object-panel" style={{ marginTop: "0.75rem" }}>
          {selectedSource ? (
            <>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                <div>
                  <div className="bp-object-title">{selectedSource.id}</div>
                  <p className="muted" style={{ fontSize: "0.75rem", marginTop: 4 }}>
                    {sourceSubtitle(selectedSource.type)}
                  </p>
                </div>
                <button type="button" className="nav-link" onClick={() => setSourceView("list")}>
                  ← 返回列表
                </button>
              </div>
              <BpPropGrid
                items={[
                  { label: "连接器", value: <ConnectorTag type={selectedSource.type} /> },
                  { label: "存储类型", value: <StoragePill type={selectedSource.type} /> },
                  { label: "运行时", value: runtimeLabel(selectedSource) },
                  { label: "上次同步", value: lastSyncFor(selectedSource.id, syncs) },
                  { label: "状态", value: <StatusDot status={selectedSource.status} /> },
                  { label: "关联同步", value: String(linkedSyncs.length) },
                ]}
              />
              <div className="bp-ws-section-title">关联同步</div>
              <BpTable
                columns={["同步编号", "状态", "完成时间", ""]}
                rows={
                  linkedSyncs.length
                    ? linkedSyncs.map((s) => [
                        s.id,
                        statusZh(s.status),
                        formatRelative(s.finishedAt),
                        <Link key={String(s.id)} to={pipelineLinkForSource(s.sourceId)} className="nav-link">
                          管道 →
                        </Link>,
                      ])
                    : [["—", "—", "—", ""]]
                }
              />
              <div className="bp-ws-section-title">关联管道</div>
              <BpTable
                columns={["管道编号", "状态", ""]}
                rows={
                  linkedPipelines.length
                    ? linkedPipelines.map((p) => [
                        p.id,
                        statusZh(p.status),
                        <span key={String(p.id)}>
                          <Link to="/data/pipelines" className="nav-link">
                            管道
                          </Link>
                          {" · "}
                          <Link to="/data/builds" className="nav-link">
                            构建
                          </Link>
                          {" · "}
                          <Link to="/data/datasets" className="nav-link">
                            数据集
                          </Link>
                        </span>,
                      ])
                    : [["—", "—", ""]]
                }
              />
              <BpLinkRow
                links={[
                  { to: pipelineLinkForSource(selectedSource.id), label: "按数据源过滤管道" },
                  { to: "/data/datasets", label: "数据集" },
                ]}
              />
            </>
          ) : (
            <p className="muted">
              请从列表选择一条记录 ·{" "}
              <button type="button" className="nav-link" onClick={() => setSourceView("list")}>
                返回列表
              </button>
            </p>
          )}
        </div>
      )}

      {tab === "syncs" && (
        <div style={{ marginTop: "0.75rem" }}>
          <div className="data-section-head">
            <div>
              <h2 className="data-section-title">同步任务</h2>
              <p className="data-section-sub">对标 Foundry Syncs · 源 → Dataset / MediaSet / Stream</p>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
              <ActionLinks
                items={[
                  { to: "/data/schedules", label: "计划编辑器" },
                  { to: "/data/pipelines", label: "管道构建" },
                ]}
              />
              <button type="button" className="btn-primary" onClick={() => void createSyncJob()}>
                + 新建同步
              </button>
            </div>
          </div>
          <div className="data-conn-table">
            <BpTable
              columns={["同步名称", "数据源", "目标", "调度", "上次运行", "状态"]}
              rows={
                syncs.length
                  ? syncs.map((s) => [
                      <span key={`nm-${s.id}`} style={{ display: "inline-flex", flexDirection: "column", gap: 4 }}>
                        <Link to={pipelineLinkForSource(s.sourceId)} className="bp-action-link" style={{ fontWeight: 500 }}>
                          {s.id}
                        </Link>
                        <Link to={pipelineLinkForSource(s.sourceId)} className="bp-action-link" style={{ fontSize: "0.75rem" }}>
                          管道 →
                        </Link>
                      </span>,
                      <span key={`src-${s.id}`} className="muted">
                        {s.sourceId || "—"}
                      </span>,
                      <span key={`tg-${s.id}`}>{targetForSource(s.sourceId)}</span>,
                      <span key={`sc-${s.id}`} className="muted">
                        {scheduleForSource(s.sourceId)}
                      </span>,
                      <span key={`lr-${s.id}`} className="muted">
                        {formatRelative(s.finishedAt)}
                      </span>,
                      <SyncStatusText key={`st-${s.id}`} status={s.status} />,
                    ])
                  : [["—", "—", "—", "—", "—", "暂无同步"]]
              }
            />
          </div>
        </div>
      )}

      {tab === "agents" && (
        <div style={{ marginTop: "0.75rem" }}>
          <div className="data-section-head">
            <div>
              <h2 className="data-section-title">边缘代理</h2>
              <p className="data-section-sub">内网源通过 Agent 出站拉取</p>
            </div>
            <Link to="/data/agents" className="btn-outline-cyan">
              打开代理管理 →
            </Link>
          </div>
          {edgeAgent ? (
            <div className="data-agent-grid">
              <div className={`data-agent-card${edgeAgent.probeOk === false ? " is-offline" : ""}`}>
                <div className="data-agent-card-head">
                  <span className="data-agent-name">{edgeAgent.id || "agent-local"}</span>
                  <span className={edgeAgent.probeOk === false ? "data-sync-status-bad" : "data-sync-status-ok"}>
                    {edgeAgent.probeOk === false ? "离线" : "在线"}
                  </span>
                </div>
                <p className="data-agent-meta">
                  默认代理 · 承载 JDBC / 文件
                  {edgeAgent.outbound != null ? ` · outbound=${String(edgeAgent.outbound)}` : ""}
                </p>
                <p className="data-agent-stats">心跳 · 本机节点</p>
              </div>
            </div>
          ) : (
            <p className="muted" style={{ marginTop: "0.75rem" }}>
              暂无已登记代理 ·{" "}
              <Link to="/data/agents" className="bp-action-link">
                打开代理管理 →
              </Link>
            </p>
          )}
        </div>
      )}

      {tab === "exports" && (
        <div style={{ marginTop: "0.75rem" }}>
          <div className="data-section-head">
            <div>
              <h2 className="data-section-title">导出任务</h2>
              <p className="data-section-sub">Dataset / Object → 外部系统（JDBC / S3 / REST）</p>
            </div>
            <button type="button" className="btn-ghost" disabled title="导出创建后置接线">
              + 新建导出
            </button>
          </div>
          <div className="data-conn-table">
            <BpTable
              columns={["导出名称", "源", "目标", "调度", "上次导出", "状态"]}
              rows={[["—", "—", "—", "—", "—", "暂无导出"]]}
            />
          </div>
          <div style={{ marginTop: "0.75rem" }}>
            <ActionLinks
              items={[
                { to: "/data/datasets", label: "数据集" },
                { to: "/apollo/assets", label: "资产包" },
              ]}
            />
          </div>
        </div>
      )}
    </PageChrome>
  );
}
