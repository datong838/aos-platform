import { Fragment, useEffect, useState, type ReactNode } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { apiGet, apiPost } from "../api/client";
import { PageChrome } from "../components/PageChrome";
import {
  BpBanner,
  BpMetricGrid,
  BpPropGrid,
  BpTable,
  BpTabs,
  BpToolbar,
} from "./s2/blueprintUi";
import {
  ConnectorTagLink,
  connectorLabel,
  connectorTone,
  runtimeLabel,
  sourceSubtitle,
  sourceBusinessName,
  SourceNameLink,
  statusZh,
  StoragePillLink,
  type ConnectorPlugin,
  type SourceRow,
} from "./s2/dataConnectionUi";
import { pipelineDisplayTitle, type PipelineMeta } from "./s2/pipelineMeta";

function primaryDatasetRid(sourceId: string | undefined, datasets: DatasetRow[]): string | undefined {
  if (!sourceId) return undefined;
  return datasets.find((d) => d.sourceId === sourceId)?.rid;
}

export function datasetRidForSync(sync: SyncRow, datasets: DatasetRow[]): string | undefined {
  if (!sync.pipelineId) return undefined;
  return datasets.find((dataset) => dataset.pipelineId === sync.pipelineId)?.rid;
}

export function scheduleForSync(sync: SyncRow, schedules: ScheduleRow[]): ScheduleRow | undefined {
  if (sync.scheduleId) {
    const exact = schedules.find((schedule) => schedule.id === sync.scheduleId);
    if (exact) return exact;
  }
  if (!sync.pipelineId) return undefined;
  return schedules.find((schedule) => schedule.pipelineId === sync.pipelineId);
}

export function scheduleBusinessDisplay(schedule?: ScheduleRow): { business: string; raw?: string } {
  const raw = schedule?.cron || schedule?.name;
  if (!raw) return { business: "未读取" };
  const daily = raw.match(/^(\d{1,2}) (\d{1,2}) \* \* \*$/);
  if (daily) return { business: `每日 ${daily[2].padStart(2, "0")}:${daily[1].padStart(2, "0")}`, raw };
  return { business: "按已配置计划执行", raw };
}

type DatasetRow = {
  rid?: string;
  name?: string;
  status?: string;
  pipelineId?: string;
  sourceId?: string;
  objectTypeHint?: string;
};

type DlqRow = {
  id?: string;
  status?: string;
  reason?: string;
  pipelineId?: string;
};

type SyncRow = { id?: string; sourceId?: string; pipelineId?: string; scheduleId?: string; status?: string; finishedAt?: number };
type PipelineRow = PipelineMeta & { status?: string };

type MainTab = "sources" | "syncs" | "agents" | "exports";
type SourceView = "list" | "new";
type RuntimeMode = "direct" | "agent" | "worker";

export function sourceCreatePayload(id: string, type: string, runtimeMode: RuntimeMode) {
  return { id, type, runtimeMode };
}

export function verifyCreatedSource(items: SourceRow[], id: string, runtimeMode: RuntimeMode): boolean {
  return items.some((item) => item.id === id && item.runtimeMode === runtimeMode);
}

export function filterSources(
  items: SourceRow[],
  typeFilter: "all" | "jdbc" | "file",
  statusFilter: "all" | "online" | "attention",
): SourceRow[] {
  return items.filter((source) => {
    const type = (source.type || "").toLowerCase();
    if (typeFilter === "jdbc" && !type.includes("jdbc")) return false;
    if (typeFilter === "file" && !(type === "file" || type.startsWith("file-"))) return false;
    const online = statusZh(source.status) === "在线";
    if (statusFilter === "online" && !online) return false;
    if (statusFilter === "attention" && online) return false;
    return true;
  });
}

export function firstInstalledConnectorId(items: ConnectorPlugin[]): string {
  return items.find((item) => item.installed)?.id || "";
}

export function requestedInstalledConnectorId(items: ConnectorPlugin[], requested?: string | null): string {
  if (requested && items.some((item) => item.id === requested && item.installed)) return requested;
  return firstInstalledConnectorId(items);
}

export type ConnectorCategory = "database" | "saas" | "api" | "file" | "stream";

export function inferConnectorCategory(id: string): ConnectorCategory {
  const lower = id.toLowerCase();
  if (lower.includes("jdbc") || lower.includes("postgres") || lower.includes("mysql") || lower.includes("oracle") || lower.includes("snowflake"))
    return "database";
  if (lower.startsWith("file")) return "file";
  if (lower.startsWith("rest") || lower === "rest-api") return "api";
  if (lower === "kafka" || lower === "stream") return "stream";
  return "saas";
}

export function validateConnConfig(
  category: ConnectorCategory,
  fields: { host: string; port: string; database: string; username: string; password: string; apiUrl: string; apiKey: string; filePath: string },
): Record<string, string> {
  const errors: Record<string, string> = {};
  if (category === "database") {
    if (!fields.host.trim()) errors.host = "主机不能为空";
    if (!fields.port.trim()) errors.port = "端口不能为空";
    else if (!/^\d+$/.test(fields.port)) errors.port = "端口必须为数字";
    else if (Number(fields.port) < 1 || Number(fields.port) > 65535) errors.port = "端口范围 1-65535";
    if (!fields.database.trim()) errors.database = "数据库名不能为空";
    if (!fields.username.trim()) errors.username = "用户名不能为空";
  } else if (category === "api") {
    if (!fields.apiUrl.trim()) errors.apiUrl = "API URL 不能为空";
    else if (!fields.apiUrl.startsWith("http")) errors.apiUrl = "URL 需以 http:// 或 https:// 开头";
  } else if (category === "file") {
    if (!fields.filePath.trim()) errors.filePath = "文件路径不能为空";
  } else if (category === "stream") {
    if (!fields.host.trim()) errors.host = "Broker 地址不能为空";
    if (!fields.database.trim()) errors.database = "Topic 不能为空";
  }
  return errors;
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
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
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
  const [newSourceId, setNewSourceId] = useState("");
  const [connectorType, setConnectorType] = useState("file-local");
  const [runtimeMode, setRuntimeMode] = useState<RuntimeMode>("agent");
  const [wizardStep, setWizardStep] = useState(1);
  const [connectorPlugins, setConnectorPlugins] = useState<ConnectorPlugin[]>([]);
  const [connHost, setConnHost] = useState("");
  const [connPort, setConnPort] = useState("");
  const [connDatabase, setConnDatabase] = useState("");
  const [connUsername, setConnUsername] = useState("");
  const [connPassword, setConnPassword] = useState("");
  const [connApiUrl, setConnApiUrl] = useState("");
  const [connApiKey, setConnApiKey] = useState("");
  const [connFilePath, setConnFilePath] = useState("");
  const [connErrors, setConnErrors] = useState<Record<string, string>>({});
  const [sourceTypeFilter, setSourceTypeFilter] = useState<"all" | "jdbc" | "file">("all");
  const [sourceStatusFilter, setSourceStatusFilter] = useState<"all" | "online" | "attention">("all");

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
  }

  useEffect(() => {
    refresh().catch((e) => setErr(String(e.message || e)));
  }, []);

  const createRequested = searchParams.get("create") === "1";
  const requestedConnector = searchParams.get("connector");
  useEffect(() => {
    if (!createRequested) return;
    setWizardStep(1);
    setConnectorType(requestedInstalledConnectorId(connectorPlugins, requestedConnector));
    setRuntimeMode("agent");
    setNewSourceId("");
    setSourceView("new");
    setTab("sources");
  }, [connectorPlugins, createRequested, requestedConnector]);

  async function createSource() {
    const id = newSourceId.trim() || `src-${Date.now().toString(36)}`;
    setErr(null);
    try {
      const created = await apiPost<SourceRow>("/v1/sources", sourceCreatePayload(id, connectorType, runtimeMode));
      if (created.id !== id || created.runtimeMode !== runtimeMode) {
        throw new Error("创建响应与请求的数据源或运行时不一致");
      }
      const verified = await apiGet<{ items: SourceRow[] }>("/v1/sources");
      if (!verifyCreatedSource(verified.items || [], id, runtimeMode)) {
        throw new Error("服务端重读未找到运行时一致的数据源，已停止跳转");
      }
      setMsg(`已创建并验证数据源 ${id}`);
      setNewSourceId("");
      setWizardStep(1);
      await refresh();
      setSourceView("list");
      setTab("sources");
      navigate(`/data/sources/${encodeURIComponent(id)}`);
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

  function syncBusinessName(sync: SyncRow): string {
    const pipeline = pipelines.find((item) => item.id === sync.pipelineId);
    return `${pipelineDisplayTitle(pipeline || { id: sync.pipelineId || "当前业务数据" })}同步`;
  }

  function targetForSync(sync: SyncRow): ReactNode {
    const source = sources.find((item) => item.id === sync.sourceId);
    if (!source?.id) return "未读取";
    const datasetRid = datasetRidForSync(sync, datasets);
    if (!datasetRid) return "未读取";
    return <StoragePillLink sourceId={source.id} type={source.type} datasetRid={datasetRid} />;
  }

  const pipelineLinkForSource = (sourceId?: string) =>
    sourceId ? `/data/pipelines?sourceId=${encodeURIComponent(sourceId)}` : "/data/pipelines";

  function openNewSource() {
    const connectorId = firstInstalledConnectorId(connectorPlugins);
    setWizardStep(1);
    setConnectorType(connectorId);
    setRuntimeMode("agent");
    setNewSourceId("");
    setSourceView("new");
    setTab("sources");
    navigate(`/data?create=1${connectorId ? `&connector=${encodeURIComponent(connectorId)}` : ""}`);
  }

  function closeNewSource() {
    setSourceView("list");
    navigate("/data", { replace: true });
  }

  const onlineCount = sources.filter((s) => statusZh(s.status) === "在线").length;
  const syncOk = syncs.filter((s) => {
    const v = (s.status || "").toUpperCase();
    return v === "SUCCEEDED" || v === "SUCCESS" || v === "OK";
  }).length;
  const syncFail = syncs.length - syncOk;

  const filteredSources = filterSources(sources, sourceTypeFilter, sourceStatusFilter);

  function sourceRows(): ReactNode[][] {
    if (!filteredSources.length) return [["—", "—", "—", "—", "—", "无匹配数据源"]];
    return filteredSources.map((s) => {
      const sid = s.id || "";
      const dsRid = primaryDatasetRid(sid, datasets);
      return [
        <SourceNameLink key={`n-${sid}`} sourceId={sid} displayName={sourceBusinessName(s, connectorPlugins)} subtitle={sourceSubtitle(s.type)} />,
        <ConnectorTagLink key={`c-${sid}`} sourceId={sid} type={s.type} plugins={connectorPlugins} />,
        <StoragePillLink key={`st-${sid}`} sourceId={sid} type={s.type} datasetRid={dsRid} />,
        <span key={`r-${sid}`} className="aos-text">
          {runtimeLabel(s)}
        </span>,
        <span key={`ls-${sid}`} className="aos-text">
          {lastSyncFor(sid, syncs)}
        </span>,
        <StatusDot key={`ss-${sid}`} status={s.status} />,
      ];
    });
  }

  return (
    <PageChrome
      title="数据源管理"
      lede="管理组织中已接入的数据源实例 · 从外部系统接入平台：先选连接器类型，再创建数据源连接。"
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
                label: "近24小时同步",
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
                label: "失败记录",
                value: dlq.length ? (
                  <span className="data-status data-status-warn">
                    <span className="data-status-dot" aria-hidden />
                    <span>{dlq.length} 条待处理</span>
                  </span>
                ) : (
                  <span className="data-status data-status-ok">
                    <span className="data-status-dot" aria-hidden />
                    <span>无待处理</span>
                  </span>
                ),
                hint: <span>来自失败队列 · 质量检查另行统计</span>,
                tone: dlq.length ? "warn" : "ok",
              },
            ]}
          />

          <div className="filter-bar" style={{ marginTop: "0.75rem", justifyContent: "space-between" }}>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <select aria-label="数据源类型" className="btn" value={sourceTypeFilter} onChange={(event) => setSourceTypeFilter(event.target.value as typeof sourceTypeFilter)}>
                <option value="all">全部类型</option>
                <option value="jdbc">数据库</option>
                <option value="file">文件</option>
              </select>
              <select aria-label="数据源状态" className="btn" value={sourceStatusFilter} onChange={(event) => setSourceStatusFilter(event.target.value as typeof sourceStatusFilter)}>
                <option value="all">全部状态</option>
                <option value="online">在线</option>
                <option value="attention">需关注</option>
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
            <button type="button" className="btn-nav" onClick={closeNewSource}>
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
                选择当前工作区可用的连接器；尚未安装或未具备正式读取能力的连接器不会进入创建流程。
              </p>
              <div className="bp-discover-grid">
                {connectorPlugins.length === 0 ? (
                  <p className="muted" style={{ fontSize: "0.85rem" }}>
                    当前工作区尚无可用连接器，请先完成连接器安装与正式连接配置。
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
                        className="bp-card-hit"
                        style={{
                          cursor: c.installed ? "pointer" : "default",
                          display: "block",
                          width: "100%",
                        }}
                        disabled={!c.installed}
                        onClick={() => c.installed && setConnectorType(c.id)}
                      >
                        <div className="bp-discover-title">
                          {c.nameZh || c.name || c.id}
                        </div>
                        <p className="bp-discover-meta">{c.description || c.id}</p>
                        <p className="muted" style={{ fontSize: "0.7rem", margin: "0.35rem 0 0" }}>
                          {c.installed
                            ? c.runtime === "stub"
                              ? "已安装 · 尚未具备正式读取能力"
                              : "已安装"
                            : "尚未安装"}
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
              <p className="muted" style={{ fontSize: "0.75rem", marginTop: 4 }}>
                连接器：{connectorLabel(connectorType, connectorPlugins)} · 运行时：
                {runtimeMode === "direct" ? "直接连接" : runtimeMode === "agent" ? "代理连接" : "代理工作者"}
              </p>
              {(() => {
                const cat = inferConnectorCategory(connectorType);
                if (cat === "database") {
                  return (
                    <>
                      <label className="muted" style={{ display: "block", marginTop: 8 }}>
                        主机地址
                        <input
                          value={connHost}
                          onChange={(e) => setConnHost(e.target.value)}
                          placeholder="localhost"
                          style={{ display: "block", width: "100%", marginTop: 4 }}
                        />
                        {connErrors.host && <span className="error" style={{ fontSize: "0.7rem" }}>{connErrors.host}</span>}
                      </label>
                      <label className="muted" style={{ display: "block", marginTop: 8 }}>
                        端口
                        <input
                          value={connPort}
                          onChange={(e) => setConnPort(e.target.value)}
                          placeholder={connectorType.includes("postgres") ? "5432" : "3306"}
                          style={{ display: "block", width: "100%", marginTop: 4 }}
                        />
                        {connErrors.port && <span className="error" style={{ fontSize: "0.7rem" }}>{connErrors.port}</span>}
                      </label>
                      <label className="muted" style={{ display: "block", marginTop: 8 }}>
                        数据库名
                        <input
                          value={connDatabase}
                          onChange={(e) => setConnDatabase(e.target.value)}
                          placeholder="mydb"
                          style={{ display: "block", width: "100%", marginTop: 4 }}
                        />
                        {connErrors.database && <span className="error" style={{ fontSize: "0.7rem" }}>{connErrors.database}</span>}
                      </label>
                      <label className="muted" style={{ display: "block", marginTop: 8 }}>
                        用户名
                        <input
                          value={connUsername}
                          onChange={(e) => setConnUsername(e.target.value)}
                          style={{ display: "block", width: "100%", marginTop: 4 }}
                        />
                        {connErrors.username && <span className="error" style={{ fontSize: "0.7rem" }}>{connErrors.username}</span>}
                      </label>
                      <label className="muted" style={{ display: "block", marginTop: 8 }}>
                        数据源名称（可选）
                        <input
                          value={newSourceId}
                          onChange={(e) => setNewSourceId(e.target.value)}
                          placeholder="留空自动生成"
                          style={{ display: "block", width: "100%", marginTop: 4 }}
                        />
                      </label>
                    </>
                  );
                }
                if (cat === "api") {
                  return (
                    <>
                      <label className="muted" style={{ display: "block", marginTop: 8 }}>
                        API URL
                        <input
                          value={connApiUrl}
                          onChange={(e) => setConnApiUrl(e.target.value)}
                          placeholder="https://api.example.com/v1"
                          style={{ display: "block", width: "100%", marginTop: 4 }}
                        />
                        {connErrors.apiUrl && <span className="error" style={{ fontSize: "0.7rem" }}>{connErrors.apiUrl}</span>}
                      </label>
                      <label className="muted" style={{ display: "block", marginTop: 8 }}>
                        数据源名称（可选）
                        <input
                          value={newSourceId}
                          onChange={(e) => setNewSourceId(e.target.value)}
                          placeholder="留空自动生成"
                          style={{ display: "block", width: "100%", marginTop: 4 }}
                        />
                      </label>
                    </>
                  );
                }
                if (cat === "file") {
                  return (
                    <>
                      <label className="muted" style={{ display: "block", marginTop: 8 }}>
                        文件路径
                        <input
                          value={connFilePath}
                          onChange={(e) => setConnFilePath(e.target.value)}
                          placeholder="/data/orders.csv"
                          style={{ display: "block", width: "100%", marginTop: 4 }}
                        />
                        {connErrors.filePath && <span className="error" style={{ fontSize: "0.7rem" }}>{connErrors.filePath}</span>}
                      </label>
                      <label className="muted" style={{ display: "block", marginTop: 8 }}>
                        数据源名称（可选）
                        <input
                          value={newSourceId}
                          onChange={(e) => setNewSourceId(e.target.value)}
                          placeholder="留空自动生成"
                          style={{ display: "block", width: "100%", marginTop: 4 }}
                        />
                      </label>
                    </>
                  );
                }
                if (cat === "stream") {
                  return (
                    <>
                      <label className="muted" style={{ display: "block", marginTop: 8 }}>
                        Broker 地址
                        <input
                          value={connHost}
                          onChange={(e) => setConnHost(e.target.value)}
                          placeholder="broker:9092"
                          style={{ display: "block", width: "100%", marginTop: 4 }}
                        />
                        {connErrors.host && <span className="error" style={{ fontSize: "0.7rem" }}>{connErrors.host}</span>}
                      </label>
                      <label className="muted" style={{ display: "block", marginTop: 8 }}>
                        Topic
                        <input
                          value={connDatabase}
                          onChange={(e) => setConnDatabase(e.target.value)}
                          placeholder="events-topic"
                          style={{ display: "block", width: "100%", marginTop: 4 }}
                        />
                        {connErrors.database && <span className="error" style={{ fontSize: "0.7rem" }}>{connErrors.database}</span>}
                      </label>
                    </>
                  );
                }
                return (
                  <label className="muted" style={{ display: "block", marginTop: 8 }}>
                    数据源名称
                    <input
                      value={newSourceId}
                      onChange={(e) => setNewSourceId(e.target.value)}
                      placeholder="prod-mysql-orders"
                      style={{ display: "block", width: "100%", marginTop: 4 }}
                    />
                  </label>
                );
              })()}
              <BpToolbar>
                <button type="button" className="btn" onClick={() => setWizardStep(2)}>
                  上一步
                </button>
                <button
                  type="button"
                  className="btn"
                  onClick={() => {
                    const cat = inferConnectorCategory(connectorType);
                    const errs = validateConnConfig(cat, {
                      host: connHost, port: connPort, database: connDatabase,
                      username: connUsername, password: connPassword,
                      apiUrl: connApiUrl, apiKey: connApiKey, filePath: connFilePath,
                    });
                    setConnErrors(errs);
                    if (Object.keys(errs).length === 0) {
                      setWizardStep(4);
                    }
                  }}
                >
                  下一步 →
                </button>
              </BpToolbar>
            </>
          )}

          {wizardStep === 4 && (
            <>
              <div className="bp-ws-section-title">凭证</div>
              <BpBanner tone="info">凭证走密钥引用（vault ref）· 不落明文。</BpBanner>
              {(() => {
                const cat = inferConnectorCategory(connectorType);
                if (cat === "database") {
                  return (
                    <label className="muted" style={{ display: "block", marginTop: 8 }}>
                      密码
                      <input
                        type="password"
                        value={connPassword}
                        onChange={(e) => setConnPassword(e.target.value)}
                        placeholder="数据库密码"
                        style={{ display: "block", width: "100%", marginTop: 4 }}
                      />
                    </label>
                  );
                }
                if (cat === "api" || cat === "saas") {
                  return (
                    <label className="muted" style={{ display: "block", marginTop: 8 }}>
                      API Key / OAuth Token
                      <input
                        type="password"
                        value={connApiKey}
                        onChange={(e) => setConnApiKey(e.target.value)}
                        placeholder="粘贴授权凭据"
                        style={{ display: "block", width: "100%", marginTop: 4 }}
                      />
                    </label>
                  );
                }
                return null;
              })()}
              <BpPropGrid
                items={[
                  { label: "连接器", value: connectorLabel(connectorType, connectorPlugins) },
                  {
                    label: "运行时",
                    value: runtimeMode === "direct" ? "直接连接" : runtimeMode === "agent" ? "代理连接" : "代理工作者",
                  },
                  { label: "连接", value: connHost ? `${connHost}${connPort ? ":" + connPort : ""}${connDatabase ? "/" + connDatabase : ""}` : "待填写" },
                  { label: "名称", value: newSourceId.trim() || "（自动生成）" },
                ]}
              />
              <BpToolbar>
                <button type="button" className="btn" onClick={() => setWizardStep(3)}>
                  上一步
                </button>
                <button type="button" className="btn-primary" onClick={() => void createSource()}>
                  创建数据源
                </button>
              </BpToolbar>
            </>
          )}
        </div>
      )}

      {tab === "syncs" && (
        <div style={{ marginTop: "0.75rem" }}>
          <div className="data-section-head">
            <div>
              <h2 className="data-section-title">同步任务</h2>
              <p className="data-section-sub">数据源 → 业务数据集 / 媒体资料 / 实时数据流</p>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
              <ActionLinks
                items={[
                  { to: "/data/sync-config", label: "同步配置" },
                  { to: "/data/sync-routes", label: "同步路由" },
                  { to: "/data/schedules", label: "计划编辑器" },
                  { to: "/data/pipelines", label: "管道构建" },
                ]}
              />
              <Link to="/data/schedules" className="btn-primary">
                + 新建计划
              </Link>
            </div>
          </div>
          <div className="data-conn-table">
            <BpTable
              columns={["同步名称", "数据源", "目标", "调度", "上次运行", "状态"]}
              rows={
                syncs.length
                  ? syncs.map((s) => {
                    const schedule = scheduleBusinessDisplay(scheduleForSync(s, schedules));
                    return [
                      <span key={`nm-${s.id}`} style={{ display: "inline-flex", flexDirection: "column", gap: 4 }}>
                        <Link to={pipelineLinkForSource(s.sourceId)} className="bp-action-link" style={{ fontWeight: 500 }}>
                          {syncBusinessName(s)}
                        </Link>
                        <Link to={pipelineLinkForSource(s.sourceId)} className="bp-action-link" style={{ fontSize: "0.75rem" }}>
                          管道 →
                        </Link>
                        <details><summary>技术审计信息</summary><code>{s.id}</code>{s.pipelineId ? <> · <code>{s.pipelineId}</code></> : null}{s.scheduleId ? <> · <code>{s.scheduleId}</code></> : null}</details>
                      </span>,
                      <span key={`src-${s.id}`}>
                        {sourceBusinessName(sources.find((item) => item.id === s.sourceId) || { id: s.sourceId }, connectorPlugins)}
                        {s.sourceId ? <details><summary>技术审计信息</summary><code>{s.sourceId}</code></details> : null}
                      </span>,
                      <span key={`tg-${s.id}`}>{targetForSync(s)}</span>,
                      <span key={`sc-${s.id}`}>
                        {schedule.business}
                        {schedule.raw ? <details><summary>技术审计信息</summary><code>{schedule.raw}</code></details> : null}
                      </span>,
                      <span key={`lr-${s.id}`} className="muted">
                        {formatRelative(s.finishedAt)}
                      </span>,
                      <SyncStatusText key={`st-${s.id}`} status={s.status} />,
                    ];
                  })
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
              <p className="data-section-sub">通过本机代理安全读取内网数据源</p>
            </div>
            <Link to="/data/agents" className="btn-outline-cyan">
              打开代理管理 →
            </Link>
          </div>
          {edgeAgent ? (
            <div className="data-agent-grid">
              <div className={`data-agent-card${edgeAgent.probeOk === false ? " is-offline" : ""}`}>
                <div className="data-agent-card-head">
                  <span className="data-agent-name">本机边缘代理</span>
                  <span className={edgeAgent.probeOk === false ? "data-sync-status-bad" : "data-sync-status-ok"}>
                    {edgeAgent.probeOk === false ? "离线" : "在线"}
                  </span>
                </div>
                <p className="data-agent-meta">
                  承载数据库与文件数据接入
                </p>
                <p className="data-agent-stats">心跳 · 本机节点</p>
                <details><summary>技术审计信息</summary><code>{edgeAgent.id || "未返回代理标识"}</code>{edgeAgent.outbound != null ? <> · 出站读取 <code>{String(edgeAgent.outbound)}</code></> : null}</details>
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
              <p className="data-section-sub">将受控数据资产交付到外部系统</p>
            </div>
            <Link to="/apollo/assets" className="btn-nav">查看受控资产包 →</Link>
          </div>
          <BpBanner tone="info">当前工作区没有可验证的导出任务。创建跨系统交付前，需先在受控资产包中形成可审计资产；本页不会用客户端记录冒充导出成功。</BpBanner>
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
