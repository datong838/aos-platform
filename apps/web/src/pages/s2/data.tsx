import { useEffect, useMemo, useState, type MouseEvent as ReactMouseEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { apiDelete, apiGet, apiPost } from "../../api/client";
import {
  BpBanner,
  BpMetricGrid,
  BpPropGrid,
  BpSplit,
  BpTable,
  BpTabs,
  BpToolbar,
} from "./blueprintUi";
import { JsonBlock, PipelineWorkflowStepper, S2Chrome, useJsonGet } from "./shared";
import {
  TABLE_LABELS,
  buildStatusBadge,
  getPipelineDisplayName,
  getSourceDisplayName,
  pipelineDisplayTitle,
  pipelineFlowLine,
  pipelineStatusKey,
  tableKeyFromBlob,
  type PipelineMeta,
} from "./pipelineMeta";

type PipelineRow = PipelineMeta & {
  vectorCollection?: string;
  config?: { decommissioned?: boolean; [k: string]: unknown };
  nodes?: unknown[];
};
type BuildLogLine = { time?: string; level?: "INFO" | "WARN" | "ERROR" | "DEBUG"; msg?: string };
type BuildRow = {
  id?: string;
  status?: string;
  tasks?: { name: string; status?: string; ok?: boolean }[];
  pipelineId?: string;
  pipelineName?: string;
  startedAt?: number;
  finishedAt?: number;
  duration?: number;
  rowsRead?: number;
  rowsWritten?: number;
  mode?: string;
  logs?: BuildLogLine[];
};
type DatasetRow = {
  rid: string;
  name?: string;
  displayName?: string;
  status?: string;
  pipelineId?: string;
  objectTypeHint?: string;
  sourceId?: string;
};

export function buildStageLabel(name?: string): string {
  const normalized = (name || "").trim().toLowerCase();
  if (normalized === "ingest" || normalized === "extract" || normalized === "source") return "读取数据";
  if (normalized === "transform" || normalized === "validate") return "处理数据";
  if (normalized === "sink" || normalized === "load" || normalized === "output") return "写入数据";
  return name?.trim() || "未命名阶段";
}

export function buildCountLabel(value?: number): string {
  return value == null ? "未读取" : value.toLocaleString("zh-CN");
}

export function datasetStatusLabel(status?: string): string {
  const normalized = (status || "").trim().toUpperCase();
  if (normalized === "READY" || normalized === "SUCCEEDED" || normalized === "SUCCESS") return "可读取";
  if (normalized === "RUNNING" || normalized === "IN_PROGRESS") return "更新中";
  if (normalized === "FAILED" || normalized === "ERROR") return "读取失败";
  return normalized ? "待确认" : "未读取";
}

const DATASET_FIELD_LABELS: Record<string, string> = {
  id: "业务标识",
  name: "名称",
  title: "标题",
  status: "业务状态",
  type: "对象类型",
  code: "业务编码",
  order_no: "订单号",
  orderNo: "订单号",
  goods_id: "商品标识",
  goods_name: "商品名称",
  product_id: "商品标识",
  product_name: "商品名称",
  productId: "商品标识",
  shop_id: "店铺标识",
  shopId: "店铺标识",
  member_id: "会员标识",
  memberId: "会员标识",
  customer_name: "客户名称",
  amount: "金额",
  total_amount: "总金额",
  totalAmount: "订单总额",
  currency: "币种",
  currencyScale: "金额精度",
  pay_status: "支付状态",
  payStatus: "支付状态",
  order_status: "订单状态",
  orderStatus: "订单状态",
  delivery_status: "发货状态",
  deliveryStatus: "发货状态",
  risk_score: "风险评分",
  review_quality_bucket: "评价质量",
  is_delete: "删除状态",
  isDelete: "删除状态",
  content: "内容",
  score: "评分",
  created_at: "创建时间",
  createdAt: "创建时间",
  updated_at: "更新时间",
  updatedAt: "更新时间",
};

export function datasetFieldLabel(field: string): string {
  return DATASET_FIELD_LABELS[field] || "业务字段";
}

const DATASET_AUDIT_ONLY_FIELDS = new Set([
  "type",
  "_schemaVersion",
  "_sourceIdentity",
  "_sourceUpdatedAt",
  "createdAtSourceTimezone",
  "updatedAtSourceTimezone",
]);

export function datasetBusinessColumns(fields: string[]): string[] {
  return fields.filter((field) => !DATASET_AUDIT_ONLY_FIELDS.has(field));
}

export function datasetCellText(field: string, value: unknown): string {
  if (value == null) return "—";
  const normalized = String(value).trim().toLowerCase();
  if (field === "status") {
    if (normalized === "active") return "正常";
    if (normalized === "inactive") return "停用";
  }
  if (field === "currency" && normalized === "cny") return "人民币";
  if (field === "review_quality_bucket") {
    if (normalized === "high") return "高";
    if (normalized === "medium") return "中";
    if (normalized === "low") return "低";
  }
  return cellText(value);
}

type PreviewResult = {
  columns?: string[];
  rows?: Record<string, unknown>[];
  total?: number;
  objectType?: string;
  detail?: string;
  source?: string;
};

function tableKeyFromDataset(d: DatasetRow): string | null {
  return tableKeyFromBlob(d.rid, d.pipelineId, d.name);
}

function datasetLabel(d: DatasetRow): { title: string; ot: string; table: string | null } {
  const table = tableKeyFromDataset(d);
  const mapped = table ? TABLE_LABELS[table] : undefined;
  const ot = (d.objectTypeHint || mapped?.ot || "—").trim();
  const title =
    (d.displayName || "").trim() ||
    (mapped?.zh ? mapped.zh : "") ||
    (d.name && !String(d.name).startsWith("pipe-") ? String(d.name) : "") ||
    mapped?.zh ||
    ot ||
    d.rid;
  return { title, ot, table };
}

function cellText(v: unknown): string {
  if (v == null) return "—";
  if (typeof v === "object") {
    try {
      return JSON.stringify(v);
    } catch {
      return String(v);
    }
  }
  const s = String(v);
  return s.length > 80 ? `${s.slice(0, 77)}…` : s;
}

// MediaSetsPage 已迁移到独立文件 ./MediaSetsPage.tsx
export { MediaSetsPage } from "./MediaSetsPage";

/** 186w · 对齐 pipeline-list.html（图2）· 左项目树 + 右最近编辑大卡 → 画布 */
export function PipelinesPage() {
  const [searchParams] = useSearchParams();
  const sourceFilter = searchParams.get("sourceId")?.trim() || "";
  const { data, err, reload } = useJsonGet<{ items: PipelineRow[] }>("/v1/pipelines");
  const { data: dsData } = useJsonGet<{ items: DatasetRow[] }>("/v1/datasets");

  // Phase 7: 搜索 + 状态过滤
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("");

  const items = useMemo(() => {
    const all = data?.items || [];
    let filtered = all;
    if (sourceFilter) filtered = filtered.filter((p) => p.sourceId === sourceFilter);
    if (statusFilter) filtered = filtered.filter((p) => pipelineStatusKey(p.lastBuild?.status) === statusFilter);
    if (search.trim()) {
      const q = search.toLowerCase();
      filtered = filtered.filter((p) =>
        p.id.toLowerCase().includes(q) ||
        pipelineDisplayTitle(p).toLowerCase().includes(q) ||
        (p.sourceId || "").toLowerCase().includes(q)
      );
    }
    return filtered;
  }, [data?.items, sourceFilter, search, statusFilter]);

  const datasets = dsData?.items || [];

  // Phase 7: 统计卡片
  const stats = useMemo(() => {
    const all = data?.items || [];
    const success = all.filter((p) => pipelineStatusKey(p.lastBuild?.status) === "success").length;
    const failed = all.filter((p) => pipelineStatusKey(p.lastBuild?.status) === "failed").length;
    const running = all.filter((p) => pipelineStatusKey(p.lastBuild?.status) === "running").length;
    return { total: all.length, success, failed, running };
  }, [data?.items]);

  const [busy, setBusy] = useState<Record<string, string>>({});
  const [flash, setFlash] = useState<string | null>(null);
  const nav = useNavigate();

  function showFlash(msg: string) {
    setFlash(msg);
    window.setTimeout(() => setFlash((cur) => (cur === msg ? null : cur)), 4000);
  }

  function isDecommissioned(p: PipelineRow): boolean {
    return Boolean((p.config as Record<string, unknown> | null | undefined)?.decommissioned);
  }

  async function doDecommission(p: PipelineRow, ev: ReactMouseEvent) {
    ev.preventDefault();
    ev.stopPropagation();
    const name = pipelineDisplayTitle(p);
    if (!window.confirm(`确定作废管道「${name}」？\n\n作废后：\n• 不可执行 build\n• 可随时「恢复」\n• 需要删除时，作废后再走删除审批`)) return;
    setBusy((s) => ({ ...s, [p.id]: "decommission" }));
    try {
      await apiPost(`/v1/pipelines/${encodeURIComponent(p.id)}/decommission`, {});
      showFlash(`「${name}」已作废`);
      reload();
    } catch (e) {
      window.alert(`作废失败：${(e as Error).message || e}`);
    } finally {
      setBusy((s) => ({ ...s, [p.id]: "" }));
    }
  }

  async function doRestore(p: PipelineRow, ev: ReactMouseEvent) {
    ev.preventDefault();
    ev.stopPropagation();
    setBusy((s) => ({ ...s, [p.id]: "restore" }));
    try {
      await apiPost(`/v1/pipelines/${encodeURIComponent(p.id)}/restore`, {});
      showFlash(`管道已恢复`);
      reload();
    } catch (e) {
      window.alert(`恢复失败：${(e as Error).message || e}`);
    } finally {
      setBusy((s) => ({ ...s, [p.id]: "" }));
    }
  }

  async function doDelete(p: PipelineRow, ev: ReactMouseEvent) {
    ev.preventDefault();
    ev.stopPropagation();
    const name = pipelineDisplayTitle(p);
    if (!isDecommissioned(p)) {
      window.alert(`请先作废管道再删除（已内置防护：作废→删除两步）。`);
      return;
    }
    const confirmId = window.prompt(
      `⚠️ 不可逆操作：删除管道「${name}」\n\n审批通过后，管道及关联数据集将被物理删除。\n请输入管道 ID 「${p.id}」确认。`,
      ""
    );
    if (confirmId !== p.id) return;
    const cascade = window.confirm(
      `是否同时删除关联输出数据集？\n确定 → 级联删除管道 + 输出数据集\n取消 → 仅删除管道（数据集保留）`
    );
    setBusy((s) => ({ ...s, [p.id]: "delete" }));
    try {
      const res = (await apiDelete(
        `/v1/pipelines/${encodeURIComponent(p.id)}?cascadeDataset=${cascade ? "true" : "false"}`
      )) as unknown as { deleteRequest: { id: string; status: string }; message?: string };
      showFlash(
        `删除请求已提交（req=${res.deleteRequest.id}, status=${res.deleteRequest.status}）。待 admin 审批通过后实际删除。`
      );
      reload();
    } catch (e) {
      window.alert(`提交删除失败：${(e as Error).message || e}`);
    } finally {
      setBusy((s) => ({ ...s, [p.id]: "" }));
    }
  }

  const goCanvas = (id: string) => nav(`/data/pipelines/${encodeURIComponent(id)}`);

  return (
    <S2Chrome title="管道构建" lede={`栖月汇电商数据项目 · 当前显示 ${items.length} / ${stats.total} 条管道`}>
      <PipelineWorkflowStepper current={0} />
      <BpToolbar>
        {flash && (
          <span
            style={{
              padding: "4px 10px",
              background: "var(--aos-ok, #16a34a)",
              color: "#fff",
              borderRadius: 3,
              fontSize: "0.75rem",
            }}
            role="status"
          >
            {flash}
          </span>
        )}
        <button type="button" className="btn" onClick={() => reload()}>
          刷新
        </button>
        <Link to="/data/pipeline-proposals" className="btn-nav">
          管道提案 →
        </Link>
        {items[0] && (
          <Link to={`/data/pipelines/${encodeURIComponent(items[0].id)}`} className="btn-nav-accent">
            打开画布 →
          </Link>
        )}
        {sourceFilter && (
          <Link to="/data/pipelines" className="btn-nav">
            清除来源筛选 ×
          </Link>
        )}
        {/* Phase 7: 搜索框 */}
        <input
          type="search"
          placeholder="搜索管道…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ fontSize: "0.8rem", padding: "2px 8px", border: "1px solid var(--aos-border, #cbd5e0)", borderRadius: 3, minWidth: 150 }}
        />
        {/* Phase 7: 状态过滤 */}
        <select
          aria-label="管道状态"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          style={{ fontSize: "0.8rem", padding: "2px 6px", border: "1px solid var(--aos-border, #cbd5e0)", borderRadius: 3 }}
        >
          <option value="">全部状态</option>
          <option value="success">成功</option>
          <option value="failed">失败</option>
          <option value="running">运行中</option>
          <option value="unknown">未知</option>
        </select>
      </BpToolbar>

      {/* Phase 7: 统计概览 */}
      <div style={{ display: "flex", gap: 12, padding: "8px 0", marginBottom: 8 }}>
        <div style={{ padding: "6px 12px", background: "var(--aos-surface, #f7fafc)", borderRadius: 4, border: "1px solid var(--aos-border, #e2e8f0)", fontSize: "0.75rem" }}>
          <span className="muted">总计 </span><strong>{stats.total}</strong>
        </div>
        <div style={{ padding: "6px 12px", background: "#f0fff4", borderRadius: 4, border: "1px solid #c6f6d5", fontSize: "0.75rem" }}>
          <span style={{ color: "#22543d" }}>成功 </span><strong style={{ color: "#22543d" }}>{stats.success}</strong>
        </div>
        <div style={{ padding: "6px 12px", background: "#fff5f5", borderRadius: 4, border: "1px solid #fed7d7", fontSize: "0.75rem" }}>
          <span style={{ color: "#742a2a" }}>失败 </span><strong style={{ color: "#742a2a" }}>{stats.failed}</strong>
        </div>
        <div style={{ padding: "6px 12px", background: "#ebf8ff", borderRadius: 4, border: "1px solid #bee3f8", fontSize: "0.75rem" }}>
          <span style={{ color: "#2a4365" }}>运行中 </span><strong style={{ color: "#2a4365" }}>{stats.running}</strong>
        </div>
      </div>

      {sourceFilter && !search && !statusFilter && (
        <BpBanner tone="info">
          已按来源系统筛选；精确来源标识见审计信息。
        </BpBanner>
      )}
      {err && <p className="error">{err}</p>}

      <div className="bp-pipe-list-shell">
        <aside className="bp-pipe-tree">
          <div className="bp-pipe-tree-head">
            <div className="bp-section-label">项目</div>
            <div className="bp-pipe-project">
              <span className="bp-pipe-project-icon" aria-hidden />
              栖月汇电商数据项目
            </div>
          </div>
          <nav className="bp-pipe-tree-nav">
            <div className="bp-section-label">管道</div>
            {items.map((p) => (
              <Link
                key={p.id}
                to={`/data/pipelines/${encodeURIComponent(p.id)}`}
                className="bp-pipe-tree-link"
                title={p.id}
              >
                {pipelineDisplayTitle(p)}
              </Link>
            ))}
            {items.length === 0 && <p className="muted">暂无管道</p>}
            <div className="bp-section-label bp-pipe-tree-gap">媒体集</div>
            <Link to="/data/media-sets" className="bp-pipe-tree-link bp-pipe-tree-link-muted">
              媒体集浏览
            </Link>
            <div className="bp-section-label bp-pipe-tree-gap">数据集</div>
            {datasets.slice(0, 8).map((d) => (
              <Link
                key={d.rid}
                to={`/data/datasets?rid=${encodeURIComponent(d.rid)}`}
                className="bp-pipe-tree-link bp-pipe-tree-link-muted"
                title={d.rid}
              >
                {datasetLabel(d).title}
              </Link>
            ))}
            <Link to="/data/datasets" className="bp-pipe-tree-link bp-pipe-tree-link-muted">
              全部数据集 →
            </Link>
          </nav>
        </aside>

        <div className="bp-pipe-list-main">
          <h2 className="bp-pipe-list-section">最近编辑</h2>
          <div className="bp-pipe-card-grid">
            {items.map((p) => {
              const badge = buildStatusBadge(p.lastBuild?.status);
              const decom = isDecommissioned(p);
              const loading = busy[p.id];
              return (
                <div
                  key={p.id}
                  className="bp-pipe-card"
                  onClick={() => goCanvas(p.id)}
                  role="link"
                  tabIndex={0}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") goCanvas(p.id);
                  }}
                  style={{ cursor: "pointer" }}
                >
                  <div className="bp-pipe-card-top">
                    <div>
                      <div className="bp-pipe-card-title">
                        {pipelineDisplayTitle(p)}
                        {decom && (
                          <span
                            className="bp-pipe-badge bp-pipe-badge-muted"
                            style={{
                              marginLeft: 6,
                              fontSize: "0.625rem",
                              background: "var(--aos-muted, #e2e8f0)",
                              color: "var(--aos-muted-fg, #475569)",
                            }}
                          >
                            已作废
                          </span>
                        )}
                      </div>
                      <div className="bp-pipe-card-flow">{pipelineFlowLine(p)}</div>
                    </div>
                    <span className={`bp-pipe-badge bp-pipe-badge-${badge.tone}`}>{badge.label}</span>
                  </div>
                  <div className="bp-pipe-card-meta">
                    <span>运行分支：主分支</span>
                    <span>最近构建：{badge.label}</span>
                    <span>{p.nodes ? `${p.nodes.length} 个处理节点` : "处理节点未读取"}</span>
                  </div>
                  <details className="bp-audit-details" onClick={(event) => event.stopPropagation()} style={{ marginTop: 6 }}>
                    <summary>管道审计</summary>
                    <p className="muted">管道标识：{p.id} · 来源标识：{p.sourceId || "未读取"}</p>
                    <p className="muted">数据集：{p.datasetRid || "未读取"} · 原始构建状态：{p.lastBuild?.status || "未读取"}</p>
                  </details>
                  <div
                    className="bp-pipe-card-actions"
                    onClick={(ev) => {
                      ev.stopPropagation();
                      ev.preventDefault();
                    }}
                    style={{
                      marginTop: 8,
                      display: "flex",
                      gap: 6,
                      flexWrap: "wrap",
                      borderTop: "1px solid var(--aos-border, #e2e8f0)",
                      paddingTop: 8,
                    }}
                  >
                    {!decom ? (
                      <button
                        type="button"
                        className="btn"
                        disabled={Boolean(loading)}
                        onClick={(ev) => doDecommission(p, ev)}
                        style={{ padding: "2px 8px", fontSize: "0.7rem", minWidth: 56 }}
                      >
                        {loading === "decommission" ? "作废中…" : "作废"}
                      </button>
                    ) : (
                      <button
                        type="button"
                        className="btn"
                        disabled={Boolean(loading)}
                        onClick={(ev) => doRestore(p, ev)}
                        style={{ padding: "2px 8px", fontSize: "0.7rem", minWidth: 56 }}
                      >
                        {loading === "restore" ? "恢复中…" : "恢复"}
                      </button>
                    )}
                    <button
                      type="button"
                      className="btn btn-danger"
                      disabled={Boolean(loading) || !decom}
                      title={!decom ? "删除前请先作废管道" : "提交删除审批请求"}
                      onClick={(ev) => doDelete(p, ev)}
                      style={{ padding: "2px 8px", fontSize: "0.7rem", minWidth: 56 }}
                    >
                      {loading === "delete" ? "提交中…" : "删除"}
                    </button>
                    <button
                      type="button"
                      className="btn"
                      onClick={(ev) => {
                        ev.stopPropagation();
                        ev.preventDefault();
                        goCanvas(p.id);
                      }}
                      style={{ padding: "2px 8px", fontSize: "0.7rem", minWidth: 72 }}
                    >
                      打开画布
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
          {items.length === 0 && (
            <p className="muted">
              当前没有可读取的管道；请先到 <Link to="/data">数据源管理</Link> 配置正式来源并完成安全预检。
            </p>
          )}
        </div>
      </div>
    </S2Chrome>
  );
}

/** 77 · 搭建操作工作台：执行管道 + 查看日志 + 数据预览 */
export function BuildsPage() {
  const { data, err, reload } = useJsonGet<{ items: BuildRow[] }>("/v1/builds");
  const { data: pipelinesData } = useJsonGet<{ items: PipelineRow[] }>("/v1/pipelines");
  const { data: datasetsData } = useJsonGet<{ items: DatasetRow[] }>("/v1/datasets");
  const [selected, setSelected] = useState<string | null>(null);
  const [executingIds, setExecutingIds] = useState<Set<string>>(new Set());
  const [runMode, setRunMode] = useState<"incremental" | "full">("incremental");
  const [pendingExecution, setPendingExecution] = useState<string | null>(null);

  const builds = data?.items || [];
  const pipelines = pipelinesData?.items || [];
  const datasets = datasetsData?.items || [];
  const active = builds.find((b) => b.id === selected) || builds[0];

  function taskIcon(t: { status?: string; ok?: boolean }): string {
    if (t.status === "SUCCEEDED" || t.ok) return "✅";
    if (t.status === "FAILED" || t.status === "ERROR") return "❌";
    if (t.status === "RUNNING") return "🔄";
    return "⏳";
  }

  function statusBadge(status?: string): { text: string; cls: string } {
    switch ((status || "").toUpperCase()) {
      case "SUCCEEDED":
        return { text: "成功", cls: "badge-ok" };
      case "FAILED":
      case "ERROR":
        return { text: "失败", cls: "badge-err" };
      case "RUNNING":
        return { text: "运行中", cls: "badge-run" };
      default:
        return { text: status ? "待确认" : "未读取", cls: "badge-muted" };
    }
  }

  function formatTime(ts?: number): string {
    if (!ts) return "—";
    return new Date(ts * 1000).toLocaleString("zh-CN", { hour12: false });
  }

  function formatDuration(sec?: number): string {
    if (!sec) return "—";
    if (sec < 60) return `${sec.toFixed(1)} 秒`;
    return `${Math.floor(sec / 60)} 分 ${(sec % 60).toFixed(0)} 秒`;
  }

  function findDatasetRid(pipelineId?: string): string | undefined {
    if (!pipelineId) return undefined;
    return datasets.find((d) => d.pipelineId === pipelineId)?.rid;
  }

  async function executePipeline(pipelineId: string) {
    if (!pipelineId) return;
    if (executingIds.has(pipelineId)) return;
    setExecutingIds((prev) => new Set(prev).add(pipelineId));
    try {
      await apiPost<{ buildId: string }>(`/v1/pipelines/${encodeURIComponent(pipelineId)}/execute`, {
        mode: runMode,
      });
      // 刷新 builds 列表
      await reload();
    } catch (e) {
      alert(`执行失败：${(e as Error).message}`);
    } finally {
      setExecutingIds((prev) => {
        const next = new Set(prev);
        next.delete(pipelineId);
        return next;
      });
    }
  }

  async function executeAllActive() {
    const toRun = pipelines.filter((p) => !p?.config?.decommissioned);
    for (const p of toRun) {
      await executePipeline(p.id);
    }
  }

  function requestExecution(pipelineId: string) {
    if (pipelineId) setPendingExecution(pipelineId);
  }

  async function confirmExecution() {
    const target = pendingExecution;
    setPendingExecution(null);
    if (!target) return;
    if (target === "__all__") await executeAllActive();
    else await executePipeline(target);
  }

  const pendingBuild = builds.find((build) => build.pipelineId === pendingExecution);
  const pendingPipelineName = pendingBuild?.pipelineName || pendingBuild?.pipelineId || "当前管道";

  return (
    <S2Chrome title="搭建" lede="查看真实数据处理记录、阶段、日志与输出数据">
      <PipelineWorkflowStepper current={3} />

      {/* 顶部工具栏 */}
      <BpToolbar>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <Link to="/data/pipelines" className="btn-nav">
            ← 管道列表
          </Link>
          <button type="button" className="btn" onClick={() => reload()}>
            刷新
          </button>
          <div style={{ width: 1, height: 24, background: "var(--aos-border)", margin: "0 4px" }} />
          <select
            aria-label="执行模式"
            value={runMode}
            onChange={(e) => setRunMode(e.target.value as "incremental" | "full")}
            style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid var(--aos-border)", fontSize: 13 }}
          >
            <option value="incremental">增量模式</option>
            <option value="full">全量模式</option>
          </select>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => active?.pipelineId && requestExecution(active.pipelineId)}
            disabled={!active?.pipelineId || executingIds.has(active.pipelineId || "")}
          >
            {executingIds.has(active?.pipelineId || "") ? "执行中..." : "执行当前管道"}
          </button>
          <button
            type="button"
            className="btn"
            onClick={() => setPendingExecution("__all__")}
            disabled={executingIds.size > 0}
          >
            批量执行全部
          </button>
          {active?.pipelineId && findDatasetRid(active.pipelineId) && (
            <Link
              to={`/data/datasets?rid=${encodeURIComponent(findDatasetRid(active.pipelineId)!)}`}
              className="btn btn-nav"
              style={{ background: "var(--aos-blue-50)", color: "var(--aos-blue-600)" }}
            >
              查看数据集 →
            </Link>
          )}
        </div>
      </BpToolbar>

      {pendingExecution && (
        <BpBanner tone="warn">
          <strong>{pendingExecution === "__all__" ? "确认批量执行全部可用管道" : `确认执行“${pendingPipelineName}”`}</strong>
          <p className="muted">执行模式：{runMode === "full" ? "全量（将重新处理完整数据范围）" : "增量（处理新增与变化数据）"}。确认后会产生真实数据处理记录。</p>
          <BpToolbar>
            <button type="button" className="btn" onClick={() => setPendingExecution(null)}>取消</button>
            <button type="button" className="btn-primary" onClick={() => void confirmExecution()}>确认执行</button>
          </BpToolbar>
        </BpBanner>
      )}

      {err && <p className="error">{err}</p>}

      <BpSplit
        left={
          <div style={{ minWidth: 280 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <h2 className="aos-text" style={{ fontSize: "0.875rem", margin: 0 }}>
                搭建历史（{builds.length}）
              </h2>
            </div>

            {builds.length === 0 && (
              <div className="card" style={{ textAlign: "center", padding: "32px 16px", color: "var(--aos-text-muted)" }}>
                <p>暂无搭建记录</p>
                <button type="button" className="btn btn-primary" onClick={() => setPendingExecution("__all__")}>
                  执行可用管道
                </button>
              </div>
            )}

            {builds.map((b) => {
              const badge = statusBadge(b.status);
              const isRunning = executingIds.has(b.pipelineId || "");
              const dsRid = findDatasetRid(b.pipelineId);
              return (
                <div
                  key={`${b.pipelineId}-${b.id}`}
                  className={b.id === active?.id ? "card" : "card"}
                  style={{
                    marginBottom: 8,
                    padding: "12px 14px",
                    cursor: "pointer",
                    border: b.id === active?.id ? "2px solid var(--aos-blue-400)" : "1px solid var(--aos-border)",
                    background: b.id === active?.id ? "var(--aos-blue-50)" : undefined,
                  }}
                  onClick={() => setSelected(b.id || null)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") setSelected(b.id || null);
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 6 }}>
                    <strong style={{ fontSize: "0.9rem" }}>
                      {b.pipelineName || b.pipelineId || b.id}
                    </strong>
                    <span
                      className={badge.cls}
                      style={{
                        padding: "2px 8px",
                        borderRadius: 4,
                        fontSize: 11,
                        fontWeight: 600,
                      }}
                    >
                      {isRunning ? "⏳ 执行中" : badge.text}
                    </span>
                  </div>

                  <details className="bp-audit-details" style={{ marginBottom: 8 }} onClick={(event) => event.stopPropagation()}>
                    <summary>搭建审计</summary>
                    <span className="muted">构建：{b.id || "未读取"} · 管道：{b.pipelineId || "未读取"} · 原始状态：{b.status || "未读取"}</span>
                  </details>

                  {/* 统计信息 */}
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "1fr 1fr",
                      gap: 4,
                      fontSize: "0.72rem",
                      marginBottom: 8,
                    }}
                  >
                    <div style={{ color: "var(--aos-text-muted)" }}>
                      耗时：<span className="aos-text">{formatDuration(b.duration)}</span>
                    </div>
                    <div style={{ color: "var(--aos-text-muted)" }}>
                      写入：<span className="aos-text">{buildCountLabel(b.rowsWritten)}</span>
                    </div>
                  </div>

                  {/* 操作按钮 */}
                  <div style={{ display: "flex", gap: 6, marginTop: 6 }} onClick={(e) => e.stopPropagation()}>
                    <button
                      type="button"
                      className="btn btn-small"
                      onClick={() => b.pipelineId && requestExecution(b.pipelineId)}
                      disabled={isRunning}
                      style={{ padding: "4px 10px", fontSize: 12, flex: 1 }}
                    >
                      {isRunning ? "执行中" : "执行"}
                    </button>
                    {dsRid && (
                      <Link
                        to={`/data/datasets?rid=${encodeURIComponent(dsRid)}`}
                        className="btn btn-small btn-nav"
                        style={{ padding: "4px 10px", fontSize: 12, flex: 1 }}
                      >
                        查看数据
                      </Link>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        }
        right={
          active ? (
            <div style={{ paddingRight: 8 }}>
              {/* 标题区 */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
                <div>
                  <h1
                    className="aos-text"
                    style={{ fontSize: "1.35rem", fontWeight: 700, margin: 0, marginBottom: 4 }}
                  >
                    {active.pipelineName || active.pipelineId || active.id}
                  </h1>
                  <p className="muted" style={{ margin: 0, fontSize: "0.78rem" }}>
                    管道：
                    {active.pipelineId ? (
                      <Link to={`/data/pipelines/${encodeURIComponent(active.pipelineId)}`}>
                        {active.pipelineName || active.pipelineId}
                      </Link>
                    ) : (
                      "—"
                    )}
                    {" · 模式："}
                    <span className="aos-text">{active.mode === "full" ? "全量" : "增量"}</span>
                  </p>
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={() => active.pipelineId && requestExecution(active.pipelineId)}
                    disabled={executingIds.has(active.pipelineId || "")}
                  >
                    {executingIds.has(active.pipelineId || "") ? "执行中..." : "执行当前管道"}
                  </button>
                </div>
              </div>

              {/* 统计卡片 */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(4, 1fr)",
                  gap: 12,
                  marginBottom: 20,
                }}
              >
                {[
                  { label: "执行状态", value: statusBadge(active.status).text, highlight: active.status === "SUCCEEDED" },
                  { label: "执行耗时", value: formatDuration(active.duration) },
                  { label: "读取记录", value: buildCountLabel(active.rowsRead) },
                  { label: "写入记录", value: buildCountLabel(active.rowsWritten), highlight: true },
                ].map((s) => (
                  <div
                    key={s.label}
                    className="card"
                    style={{
                      padding: "14px 16px",
                      borderLeft: s.highlight ? "3px solid var(--aos-blue-500)" : "3px solid var(--aos-border)",
                    }}
                  >
                    <div style={{ fontSize: "0.72rem", color: "var(--aos-text-muted)", marginBottom: 4 }}>{s.label}</div>
                    <div
                      style={{
                        fontSize: "1.25rem",
                        fontWeight: 700,
                        color: s.highlight ? "var(--aos-blue-600)" : "var(--aos-text)",
                      }}
                    >
                      {s.value}
                    </div>
                  </div>
                ))}
              </div>

              {/* 执行任务 */}
              <div className="card" style={{ padding: 16, marginBottom: 20 }}>
                <h2
                  className="aos-text"
                  style={{
                    fontSize: "0.875rem",
                    fontWeight: 600,
                    margin: 0,
                    marginBottom: 12,
                    paddingBottom: 8,
                    borderBottom: "1px solid var(--aos-border)",
                  }}
                >
                  执行阶段（{(active.tasks || []).length} 步）
                </h2>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {(active.tasks || []).map((t, idx) => {
                    const done = t.status === "SUCCEEDED" || t.ok;
                    const running = t.status === "RUNNING";
                    const failed = t.status === "FAILED" || t.status === "ERROR";
                    return (
                      <div
                        key={t.name}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          padding: "10px 14px",
                          borderRadius: 8,
                          background: running
                            ? "var(--aos-blue-50)"
                            : failed
                              ? "var(--aos-red-50)"
                              : "var(--aos-gray-50)",
                          border: `1px solid ${running ? "var(--aos-blue-200)" : failed ? "var(--aos-red-200)" : "var(--aos-border)"}`,
                        }}
                      >
                        <div
                          style={{
                            width: 22,
                            height: 22,
                            borderRadius: "50%",
                            background: done
                              ? "var(--aos-green-500)"
                              : failed
                                ? "var(--aos-red-500)"
                                : running
                                  ? "var(--aos-blue-500)"
                                  : "var(--aos-gray-300)",
                            color: "white",
                            fontSize: 12,
                            fontWeight: 700,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            marginRight: 12,
                          }}
                        >
                          {done ? "✓" : running ? "…" : failed ? "✕" : idx + 1}
                        </div>
                        <div style={{ flex: 1 }}>
                          <strong style={{ fontSize: "0.85rem" }} className="aos-text">
                            {taskIcon(t)} {buildStageLabel(t.name)}
                          </strong>
                          <div style={{ fontSize: "0.7rem", color: "var(--aos-text-muted)" }}>
                            {idx === 0 && "从数据源读取原始数据"}
                            {idx === 1 && "清洗、过滤、转换、校验"}
                            {idx === 2 && "写入数据集表并生成索引"}
                          </div>
                          <details className="bp-audit-details" style={{ marginTop: 4 }}>
                            <summary>阶段审计</summary>
                            <span className="muted">原始阶段：{t.name} · 原始状态：{t.status || "未读取"}</span>
                          </details>
                        </div>
                        <span
                          className="aos-text"
                          style={{
                            fontSize: "0.75rem",
                            fontWeight: 600,
                            color: done
                              ? "var(--aos-green-600)"
                              : failed
                                ? "var(--aos-red-600)"
                                : running
                                  ? "var(--aos-blue-600)"
                                  : "var(--aos-text-muted)",
                          }}
                        >
                          {done ? "完成" : running ? "进行中" : failed ? "失败" : "等待"}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* 执行日志 */}
              <div className="card" style={{ padding: 0, overflow: "hidden" }}>
                <div
                  style={{
                    padding: "12px 16px",
                    background: "var(--aos-gray-50)",
                    borderBottom: "1px solid var(--aos-border)",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <h2
                    className="aos-text"
                    style={{ fontSize: "0.875rem", fontWeight: 600, margin: 0 }}
                  >
                    执行日志（{(active.logs || []).length} 条）
                  </h2>
                  <span className="muted" style={{ fontSize: "0.72rem" }}>
                    开始：{formatTime(active.startedAt)} · 结束：{formatTime(active.finishedAt)}
                  </span>
                </div>
                <div
                  style={{
                    maxHeight: 260,
                    overflowY: "auto",
                    padding: "12px 16px",
                    fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                    fontSize: "0.75rem",
                    lineHeight: 1.7,
                    background: "#0f172a",
                    color: "#e2e8f0",
                  }}
                >
                  {(active.logs || []).length === 0 && (
                    <div style={{ color: "#94a3b8", fontStyle: "italic" }}>暂无日志</div>
                  )}
                  {(active.logs || []).map((log, idx) => (
                    <div key={idx} style={{ display: "flex", gap: 10 }}>
                      <span style={{ color: "#64748b", minWidth: 60 }}>{log.time}</span>
                      <span
                        style={{
                          minWidth: 52,
                          fontWeight: 700,
                          color:
                            log.level === "ERROR"
                              ? "#f87171"
                              : log.level === "WARN"
                                ? "#fbbf24"
                                : log.level === "DEBUG"
                                  ? "#94a3b8"
                                  : "#60a5fa",
                        }}
                      >
                        [{log.level}]
                      </span>
                      <span>{log.msg}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                minHeight: 400,
                color: "var(--aos-text-muted)",
              }}
            >
              <div style={{ fontSize: 48, marginBottom: 12 }}>⚙️</div>
              <p style={{ fontSize: "0.9rem", marginBottom: 16 }}>选择左侧搭建记录查看执行详情</p>
              <button type="button" className="btn btn-primary" onClick={executeAllActive}>
                🚀 立即执行第一个搭建
              </button>
            </div>
          )
        }
      />
    </S2Chrome>
  );
}

export { SchedulesPage } from "./dataSchedules";

/** 77 · 对齐 dataset.html · 182w §4.2 可读性 */
export function DatasetsPage() {
  const [searchParams] = useSearchParams();
  const ridParam = searchParams.get("rid");
  const sourceIdParam = searchParams.get("sourceId");
  const { data, err, reload } = useJsonGet<{ items: DatasetRow[] }>("/v1/datasets");
  const [tab, setTab] = useState("preview");
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<DatasetRow | null>(null);
  const [hist, setHist] = useState<{ items?: unknown[] } | null>(null);
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const [previewErr, setPreviewErr] = useState<string | null>(null);
  const [loadingPrev, setLoadingPrev] = useState(false);

  const items = useMemo(() => {
    const all = data?.items || [];
    if (sourceIdParam) return all.filter((d) => d.sourceId === sourceIdParam);
    return all;
  }, [data?.items, sourceIdParam]);
  const active = useMemo(() => {
    if (!items.length) return null;
    return items.find((d) => d.rid === selected) || items[0];
  }, [items, selected]);
  const rid = active?.rid || "";
  const label = active ? datasetLabel(active) : null;

  async function loadPreviewFor(row: DatasetRow) {
    setLoadingPrev(true);
    setPreviewErr(null);
    const { ot, table } = datasetLabel(row);
    try {
      let result: PreviewResult;
      try {
        result = await apiPost<PreviewResult>("/v1/analytics/datasets/preview", {
          datasetRid: row.rid,
          limit: 40,
        });
      } catch (datasetPreviewError) {
        if (!ot || ot === "—") throw datasetPreviewError;
        result = await apiPost<PreviewResult>("/v1/analytics/objects/list", {
          objectType: ot,
          limit: 40,
        });
        result = { ...result, objectType: ot, source: result.source || "objects-list" };
      }
      if ((!result.rows || result.rows.length === 0) && ot && ot !== "—") {
        result = await apiPost<PreviewResult>("/v1/analytics/objects/list", {
          objectType: ot,
          limit: 40,
        });
        result = { ...result, objectType: ot, source: result.source || "objects-list" };
      }
      setPreview(result);
      if (!result.rows?.length && result.detail) setPreviewErr(String(result.detail));
    } catch (e) {
      setPreview(null);
      setPreviewErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoadingPrev(false);
    }
    void table;
  }

  async function openDataset(id: string) {
    setSelected(id);
    setTab("preview");
    const d = await apiGet<DatasetRow>(`/v1/datasets/${encodeURIComponent(id)}`);
    setDetail(d);
    const h = await apiGet<{ items: unknown[] }>(`/v1/datasets/${encodeURIComponent(id)}/history`);
    setHist(h);
    await loadPreviewFor({ ...d, rid: id });
  }

  useEffect(() => {
    if (ridParam && items.some((d) => d.rid === ridParam)) {
      void openDataset(ridParam).catch(console.error);
      return;
    }
    if (!selected && items[0]?.rid) {
      void openDataset(items[0].rid).catch(console.error);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- 深链 rid / 列表首次加载
  }, [items.length, ridParam, sourceIdParam]);

  const previewColumns = useMemo(() => {
    if (preview?.columns?.length) return datasetBusinessColumns(preview.columns);
    const row0 = preview?.rows?.[0];
    if (!row0) return ["id"];
    return datasetBusinessColumns(Object.keys(row0));
  }, [preview]);

  const previewTableRows = useMemo(() => {
    return (preview?.rows || []).map((r) =>
      previewColumns.map((c) => <span key={c}>{datasetCellText(c, r[c])}</span>),
    );
  }, [preview, previewColumns]);

  return (
    <S2Chrome title="数据集预览" lede="选择真实业务数据集，查看采样记录、历史、详情与健康状态">
      <PipelineWorkflowStepper current={4} />

      <BpToolbar>
        <button
          type="button"
          className="btn"
          onClick={() => {
            reload();
            if (rid) void openDataset(rid).catch(console.error);
          }}
        >
          刷新
        </button>
        <Link to="/data/lineage" className="btn-nav">
          在沿袭中打开 →
        </Link>
        <Link to="/analytics" className="btn-nav">
          分析读数 →
        </Link>
      </BpToolbar>
      {err && <p className="error">{err}</p>}
      {sourceIdParam && items.length > 0 && (
        <BpBanner tone="info">
          已按数据源“{getSourceDisplayName(sourceIdParam)}”筛选 ·{" "}
          <Link to="/data/datasets" className="nav-link">
            查看全部数据集
          </Link>
        </BpBanner>
      )}

      {!items.length && (
        <p className="muted">
          当前没有可读取的数据集；请先到 <Link to="/data">数据源管理</Link> 完成正式来源配置与安全预检。
        </p>
      )}

      {items.length > 0 && (
        <BpSplit
          left={
            <ul className="card-list" style={{ gap: "0.4rem" }}>
              {items.map((d) => {
                const L = datasetLabel(d);
                const on = d.rid === rid;
                return (
                  <li key={d.rid}>
                    <button
                      type="button"
                      className={on ? "nav-link card active" : "nav-link card"}
                      onClick={() => void openDataset(d.rid).catch(console.error)}
                    >
                      <span className="nav-link-title">{L.title}</span>
                      <span className="nav-link-meta">
                        业务数据集 · {datasetStatusLabel(d.status)}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          }
          right={
            rid && label ? (
              <>
                <BpTabs
                  active={tab}
                  onChange={setTab}
                  tabs={[
                    { id: "preview", label: "预览" },
                    { id: "history", label: "历史" },
                    { id: "details", label: "详情" },
                    { id: "health", label: "健康" },
                  ]}
                />
                {tab === "preview" && (
                  <>
                    <h1 className="aos-text" style={{ fontSize: "1.25rem", margin: "0.5rem 0 0.25rem" }}>
                      {label.title}
                    </h1>
                    <p className="muted" style={{ marginTop: 0 }}>
                      当前展示正式来源的采样记录；精确对象类型、来源表与数据集标识见审计信息。
                    </p>
                    <details className="bp-audit-details" style={{ marginBottom: 10 }}>
                      <summary>数据集审计</summary>
                      <p className="muted">数据集：{rid} · 对象类型：{label.ot} · 来源表：{label.table || "未读取"}</p>
                    </details>
                    <BpMetricGrid
                      items={[
                        {
                          label: "本页采样",
                          value: preview?.rows?.length ?? 0,
                          tone: "muted",
                        },
                        {
                          label: "库内总数",
                          value: preview?.total ?? "—",
                          tone: "ok",
                        },
                        {
                          label: "状态",
                          value: datasetStatusLabel(detail?.status || active?.status),
                          tone: "ok",
                        },
                        {
                          label: "关联管道",
                          value: getPipelineDisplayName(detail?.pipelineId || active?.pipelineId, detail?.name || active?.name),
                          tone: "muted",
                        },
                      ]}
                    />
                    {previewErr && <p className="error">{previewErr}</p>}
                    {loadingPrev && <p className="muted">加载预览…</p>}
                    {!loadingPrev && previewTableRows.length > 0 && (
                      <>
                        <BpTable columns={previewColumns.map(datasetFieldLabel)} rows={previewTableRows} />
                        <details className="bp-audit-details" style={{ marginTop: 8 }}>
                          <summary>字段审计</summary>
                          <p className="muted">原始字段：{previewColumns.join("、")}</p>
                        </details>
                      </>
                    )}
                    {!loadingPrev && !previewTableRows.length && !previewErr && (
                      <BpBanner tone="warn">
                        当前业务数据集暂无实例记录。请核对正式同步状态，或到{" "}
                        <Link to="/ontology/objects">对象浏览</Link> 核对。
                      </BpBanner>
                    )}
                  </>
                )}
                {tab === "history" && (
                  <ul className="card-list">
                    {(hist?.items || []).map((h, i) => (
                      <li key={i} className="card">
                        <strong>第 {i + 1} 条数据集历史</strong>
                        <details className="bp-audit-details" style={{ marginTop: 6 }}>
                          <summary>历史记录审计</summary>
                          <JsonBlock value={h} />
                        </details>
                      </li>
                    ))}
                    {(hist?.items?.length || 0) === 0 && <p className="muted">无历史版本</p>}
                  </ul>
                )}
                {tab === "details" && (detail || active) && (
                  <>
                    <BpPropGrid items={[
                      { label: "数据集名称", value: label.title },
                      { label: "数据状态", value: datasetStatusLabel((detail || active)?.status) },
                      { label: "来源系统", value: getSourceDisplayName((detail || active)?.sourceId) },
                      { label: "关联管道", value: getPipelineDisplayName((detail || active)?.pipelineId, (detail || active)?.name) },
                    ]} />
                    <details style={{ marginTop: "0.75rem" }}>
                      <summary className="muted">数据集审计</summary>
                      <JsonBlock value={detail || active} />
                    </details>
                  </>
                )}
                {tab === "health" && (
                  <BpBanner tone="info">
                    数据集连通性与新鲜度见 <Link to="/data/health">数据健康</Link>；业务关系完整性见{" "}
                    <Link to="/ontology/graph-health">图谱健康度</Link>
                  </BpBanner>
                )}
              </>
            ) : (
              <p className="muted">在左侧选择一个数据集</p>
            )
          }
        />
      )}
    </S2Chrome>
  );
}

/** 77 · 对齐 health.html */
export function DataHealthPage() {
  const store = useJsonGet<Record<string, unknown>>("/v1/object-store/health");
  const mysql = useJsonGet<Record<string, unknown>>("/v1/connectors/jdbc-mysql/health");
  const dlq = useJsonGet<{ items: { id: string; reason?: string; status?: string }[] }>("/v1/dlq");

  const dlqCount = dlq.data?.items?.length || 0;
  const storeOk = store.data && (store.data as { ok?: boolean }).ok !== false;
  const mysqlOk = mysql.data && (mysql.data as { ok?: boolean }).ok !== false;
  const warn = (!storeOk ? 1 : 0) + (!mysqlOk ? 1 : 0);
  const bad = dlqCount > 0 ? 1 : 0;
  const ok = 2 - warn;

  return (
    <S2Chrome title="数据健康" lede="对齐 health · L1 连通/新鲜度（≠ 图谱健康）">
      <BpToolbar>
        <button
          type="button"
          className="btn"
          onClick={() => {
            store.reload();
            mysql.reload();
            dlq.reload();
          }}
        >
          刷新
        </button>
        <Link to="/data" className="btn-nav">
          返回数据源管理
        </Link>
        <Link to="/ontology/graph-health" className="btn-nav">
          图谱健康度 →
        </Link>
      </BpToolbar>
      {(store.err || mysql.err || dlq.err) && (
        <p className="error">{store.err || mysql.err || dlq.err}</p>
      )}

      <BpBanner tone="info">
        分责：本页 L1 Dataset/Source · 悬空 Link/属性冲突 →{" "}
        <Link to="/ontology/graph-health">图谱健康度</Link>
      </BpBanner>

      <BpMetricGrid
        items={[
          { label: "健康", value: ok, tone: "ok" },
          { label: "告警", value: warn, tone: warn > 0 ? "warn" : "ok" },
          { label: "严重", value: bad, tone: bad > 0 ? "bad" : "ok" },
        ]}
      />
      {dlqCount > 0 && (
        <p className="error" style={{ marginTop: 8 }}>
          DLQ 死信 <strong>{dlqCount}</strong>
        </p>
      )}

      <BpTable
        columns={["资源", "检查项", "状态", "详情", "上次检查"]}
        rows={[
          [
            "MinIO Object Store",
            "连通性",
            storeOk ? <span className="aos-text">通过</span> : <span className="error">失败</span>,
            String((store.data as { mode?: string })?.mode || "probe"),
            "刚刚",
          ],
          [
            "MySQL Connector",
            "连通性",
            mysqlOk ? <span className="aos-text">通过</span> : <span className="error">失败</span>,
            String((mysql.data as { message?: string })?.message || "probe"),
            "刚刚",
          ],
          [
            <Link to="/data/datasets">WorkOrder-demo</Link>,
            "新鲜度",
            <span className="aos-text">通过</span>,
            "数据集 READY",
            "—",
          ],
        ]}
      />

      {dlqCount > 0 && (
        <>
          <h2 className="aos-text" style={{ fontSize: "0.875rem", marginTop: "1rem" }}>
            DLQ
          </h2>
          <ul className="card-list">
            {(dlq.data?.items || []).map((d) => (
              <li key={d.id} className="card">
                <strong>{d.id}</strong> <span className="muted">{d.reason}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </S2Chrome>
  );
}

export function edgeAgentSourceCount(items: { runtimeMode?: string }[]): number {
  return items.filter((item) => item.runtimeMode === "agent" || item.runtimeMode === "worker").length;
}

/** 边缘代理 · 当前权威只读视图 */
export function EdgeAgentsPage() {
  const { data, err, reload } = useJsonGet<{ id: string; probeOk?: boolean; outbound?: boolean }>(
    "/v1/edge/agents/local",
  );
  const { data: sourceData, err: sourceErr, reload: reloadSources } = useJsonGet<{ items: { runtimeMode?: string }[] }>(
    "/v1/sources",
  );
  const [selected, setSelected] = useState("edge-local");

  const agents = data
    ? [
        {
          id: data.id || "edge-local",
          name: "本机边缘代理",
          region: "本机节点",
          sources: edgeAgentSourceCount(sourceData?.items || []),
          online: data.probeOk !== false,
        },
      ]
    : [];

  const active = agents.find((a) => a.id === selected) || agents[0];

  return (
    <S2Chrome title="边缘代理" lede="查看本机代理运行状态与当前接入的数据源">
      <BpToolbar>
        <button type="button" className="btn" onClick={() => { reload(); reloadSources(); }}>
          刷新
        </button>
      </BpToolbar>
      {err && <p className="error">{err}</p>}
      {sourceErr && <p className="error">数据源目录读取失败：{sourceErr}</p>}

      <BpSplit
        left={
          <ul className="card-list">
            {agents.map((a) => (
              <li key={a.id}>
                <button
                  type="button"
                  className={a.id === selected ? "nav-link active card" : "nav-link card"}
                  style={{ width: "100%", textAlign: "left" }}
                  onClick={() => setSelected(a.id)}
                >
                  <strong>{a.name}</strong>{" "}
                  <span className={a.online ? "aos-text" : "error"}>{a.online ? "在线" : "离线"}</span>
                  <div className="muted" style={{ fontSize: "0.7rem" }}>
                    {a.region} · {a.sources} 数据源
                  </div>
                </button>
              </li>
            ))}
          </ul>
        }
        right={
          active ? (
            <>
              <h1 className="aos-text" style={{ fontSize: "1.1rem" }}>
                {active.name}
              </h1>
              <p className="muted">安全读取当前工作区已登记的内网数据源</p>
              <BpTable
                columns={["项目", "当前状态"]}
                rows={[
                  ["部署位置", active.region],
                  ["接入数据源", `${active.sources} 个`],
                  ["运行状态", active.online ? "在线" : "离线"],
                ].map(([k, v]) => [<span className="muted">{k}</span>, v])}
              />
              <details style={{ marginTop: 12 }}>
                <summary>技术审计信息</summary>
                <code>{active.id}</code>
                <p className="muted">探针 {String(data?.probeOk)} · 出站读取 {String(data?.outbound)}</p>
              </details>
            </>
          ) : (
            <p className="muted">无代理</p>
          )
        }
      />
    </S2Chrome>
  );
}
