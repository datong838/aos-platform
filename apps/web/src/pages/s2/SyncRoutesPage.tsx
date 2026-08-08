import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiGet, apiPut } from "../../api/client";
import {
  BpBanner,
  BpMetricGrid,
  BpTable,
  BpTabs,
  BpToolbar,
} from "./blueprintUi";
import { S2Chrome, useJsonGet } from "./shared";

// ── Types ──────────────────────────────────────────────────────

export type RouteStatus = "active" | "paused" | "error";

export type SyncRoute = {
  id: string;
  name: string;
  source: string;
  target: string;
  frequency: string;
  status: RouteStatus;
  nextRunAt?: string;
  progress?: number;
  conflicts?: number;
};

// D4 Phase C · C4: 后端 SyncTask API 返回结构（与 SyncRoute 字段名不同，需映射）
export type SyncTaskApi = {
  id: string;
  name: string;
  source_id: string;
  target_dataset?: string;
  mode?: string;       // full|incremental|cdc
  cron_expr?: string;  // "0 * * * *"
  status?: string;     // active|paused|error
  owner?: string;
  config?: Record<string, unknown>;
  org_id?: string;
  project_id?: string;
  created_at?: number;
  updated_at?: number;
};

// D4 Phase C · C4: 后端 SyncRun API 返回结构
export type SyncRunApi = {
  id: string;
  sync_id: string;
  status: string;       // success|failed|running
  started_at: number;
  finished_at: number;
  duration_ms: number;
  rows_synced: number;
  error?: string;
  error_code?: string;
  pipeline_id?: string;
};

// ── Pure functions ─────────────────────────────────────────────

export const ROUTE_STATUS_LABELS: Record<RouteStatus, string> = {
  active: "运行中",
  paused: "已暂停",
  error: "异常",
};

export function routeStatusTone(s: RouteStatus): "ok" | "warn" | "bad" {
  if (s === "active") return "ok";
  if (s === "paused") return "warn";
  return "bad";
}

// D4 Phase C · C4: SyncTask API → SyncRoute（前端展示用）
export function syncTaskToRoute(t: SyncTaskApi): SyncRoute {
  const rawStatus = (t.status || "active").toLowerCase();
  const status: RouteStatus =
    rawStatus === "paused" ? "paused" :
    rawStatus === "error" || rawStatus === "failed" ? "error" : "active";
  return {
    id: t.id,
    name: t.name,
    source: t.source_id,
    target: t.target_dataset || "",
    frequency: cronToFrequency(t.cron_expr, t.mode),
    status,
    nextRunAt: undefined,  // 由后端调度器计算（暂未暴露）
    progress: undefined,
    conflicts: 0,
  };
}

// cron_expr + mode → 中文频率标签
function cronToFrequency(cron?: string, mode?: string): string {
  const modeLabel = mode === "incremental" ? "增量" : mode === "cdc" ? "CDC" : "全量";
  if (!cron) return modeLabel;
  // 简化解析："0 * * * *" → 每小时；"0 0 * * *" → 每天 00:00
  const parts = cron.split(/\s+/);
  if (parts.length !== 5) return modeLabel;
  const [min, hour, dom, mon, dow] = parts;
  if (hour === "*" && min !== "*") return `每${min === "0" ? "小时" : `${min}分钟`} · ${modeLabel}`;
  if (hour !== "*" && min !== "*" && dom === "*" && mon === "*" && dow === "*") {
    return `每天 ${hour.padStart(2, "0")}:${min.padStart(2, "0")} · ${modeLabel}`;
  }
  return `${cron} · ${modeLabel}`;
}

export function computeRouteStats(routes: SyncRoute[]) {
  const total = routes.length;
  const active = routes.filter((r) => r.status === "active").length;
  const paused = routes.filter((r) => r.status === "paused").length;
  const error = routes.filter((r) => r.status === "error").length;
  const conflicts = routes.reduce((sum, r) => sum + (r.conflicts || 0), 0);
  return { total, active, paused, error, conflicts };
}

export function filterRoutesByTab(routes: SyncRoute[], tab: "all" | "active" | "paused" | "error"): SyncRoute[] {
  if (tab === "all") return routes;
  return routes.filter((r) => r.status === tab);
}

export function formatNextRun(iso?: string): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  return d.toLocaleString("zh-CN", { hour12: false });
}

// D4 Phase C · C4: SyncRun 历史展示工具
export function formatRunTime(ts: number): string {
  if (!ts) return "—";
  return new Date(ts * 1000).toLocaleString("zh-CN", { hour12: false });
}

export function formatRunStatus(s: string): string {
  if (s === "success" || s === "succeeded") return "成功";
  if (s === "failed") return "失败";
  if (s === "running") return "运行中";
  return s || "—";
}

export function runStatusTone(s: string): "ok" | "warn" | "bad" {
  if (s === "success" || s === "succeeded") return "ok";
  if (s === "running") return "warn";
  return "bad";
}

export function progressPercent(p?: number): number {
  if (p == null) return 0;
  return Math.max(0, Math.min(100, Math.round(p * 100)));
}

export function toggleRouteStatus(r: SyncRoute): RouteStatus {
  return r.status === "active" ? "paused" : "active";
}

// ── Mock data ──────────────────────────────────────────────────

const DEMO_ROUTES: SyncRoute[] = [
  {
    id: "route-pg-orders",
    name: "订单库全量同步",
    source: "pg-prod",
    target: "dataset:orders",
    frequency: "每小时",
    status: "active",
    nextRunAt: new Date(Date.now() + 30 * 60000).toISOString(),
    progress: 0.72,
    conflicts: 0,
  },
  {
    id: "route-mysql-incremental",
    name: "MySQL 增量同步",
    source: "mysql-orders",
    target: "dataset:orders_clean",
    frequency: "每 15 分钟",
    status: "active",
    nextRunAt: new Date(Date.now() + 8 * 60000).toISOString(),
    progress: 0.45,
    conflicts: 2,
  },
  {
    id: "route-kafka-events",
    name: "Kafka 事件流",
    source: "kafka-events",
    target: "stream:events",
    frequency: "实时",
    status: "active",
    conflicts: 0,
  },
  {
    id: "route-shopify-products",
    name: "Shopify 商品同步",
    source: "shopify-store",
    target: "dataset:products",
    frequency: "每天 02:00",
    status: "paused",
    nextRunAt: new Date(Date.now() + 12 * 3600000).toISOString(),
    conflicts: 0,
  },
  {
    id: "route-s3-archive",
    name: "S3 归档同步",
    source: "s3-datalake",
    target: "dataset:archive",
    frequency: "每周日",
    status: "error",
    conflicts: 5,
  },
  {
    id: "route-rest-weather",
    name: "天气数据拉取",
    source: "rest-weather",
    target: "dataset:weather",
    frequency: "每小时",
    status: "error",
    nextRunAt: new Date(Date.now() - 10 * 60000).toISOString(),
    conflicts: 1,
  },
];

// ── Page Component ─────────────────────────────────────────────

export function SyncRoutesPage() {
  // D4 Phase C · C4: 切换到真实后端 /api/datasource/syncs（带租户隔离）
  const { data, err, reload } = useJsonGet<{ items: SyncTaskApi[]; total?: number }>("/api/datasource/syncs");
  const [tab, setTab] = useState<"all" | "active" | "paused" | "error">("all");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [msg, setMsg] = useState("");

  // D4 Phase C · C4: 展开时拉取 SyncRun 历史
  const [syncRuns, setSyncRuns] = useState<Record<string, SyncRunApi[]>>({});
  const [syncRunsLoading, setSyncRunsLoading] = useState<Record<string, boolean>>({});
  const [syncRunsErr, setSyncRunsErr] = useState<Record<string, string>>({});

  const allRoutes = useMemo(() => {
    const apiItems = data?.items;
    if (apiItems && apiItems.length > 0) {
      // 真实数据：SyncTask → SyncRoute 映射
      return apiItems.map(syncTaskToRoute);
    }
    // 兜底：API 失败或返回空时降级到 DEMO_ROUTES
    return DEMO_ROUTES;
  }, [data?.items]);

  const filtered = useMemo(() => filterRoutesByTab(allRoutes, tab), [allRoutes, tab]);
  const stats = useMemo(() => computeRouteStats(allRoutes), [allRoutes]);

  // D4 Phase C · C4: 展开时拉取该 SyncTask 的 SyncRun 历史
  useEffect(() => {
    if (!expanded) return;
    // 已缓存或正在加载，跳过
    if (syncRuns[expanded] || syncRunsLoading[expanded]) return;
    setSyncRunsLoading((prev) => ({ ...prev, [expanded]: true }));
    setSyncRunsErr((prev) => ({ ...prev, [expanded]: "" }));
    apiGet<{ items: SyncRunApi[]; count?: number }>(
      `/api/datasource/syncs/${encodeURIComponent(expanded)}/runs`,
    )
      .then((res) => {
        setSyncRuns((prev) => ({ ...prev, [expanded]: res.items || [] }));
      })
      .catch((e) => {
        setSyncRunsErr((prev) => ({ ...prev, [expanded]: String((e as Error).message || e) }));
      })
      .finally(() => {
        setSyncRunsLoading((prev) => ({ ...prev, [expanded]: false }));
      });
  }, [expanded, syncRuns, syncRunsLoading]);

  async function handleToggle(id: string, current: RouteStatus) {
    setMsg("");
    try {
      const next = toggleRouteStatus({ status: current } as SyncRoute);
      // D4 Phase C · C4: 后端 update_sync 是 PUT 方法
      await apiPut(`/api/datasource/syncs/${encodeURIComponent(id)}`, {
        status: next,
      });
      setMsg(`已${next === "active" ? "启用" : "暂停"} · ${id}`);
      reload();
    } catch (e) {
      setMsg(String((e as Error).message || e));
    }
  }

  return (
    <S2Chrome title="同步路由" lede="管理数据同步分发路径 · 启用/暂停 + 冲突记录">
      <BpToolbar>
        <Link to="/data/sources/new" className="btn-primary">
          + 新建同步路由
        </Link>
        <Link to="/data" className="btn-nav">
          数据源管理 →
        </Link>
        <Link to="/data/sync-config" className="btn-nav">
          同步配置 →
        </Link>
        <button type="button" className="btn" onClick={() => reload()}>
          刷新
        </button>
      </BpToolbar>

      {err && <p className="error">{err}</p>}
      {msg && <p className="aos-text">{msg}</p>}

      <BpMetricGrid
        items={[
          { label: "路由总数", value: stats.total, tone: "muted" },
          { label: "运行中", value: stats.active, tone: "ok" },
          { label: "已暂停", value: stats.paused, tone: "warn" },
          { label: "异常", value: stats.error, tone: stats.error > 0 ? "bad" : "ok" },
          { label: "冲突总数", value: stats.conflicts, tone: stats.conflicts > 0 ? "warn" : "ok" },
        ]}
      />

      <BpTabs
        tabs={[
          { id: "all", label: `全部 (${stats.total})` },
          { id: "active", label: `运行中 (${stats.active})` },
          { id: "paused", label: `已暂停 (${stats.paused})` },
          { id: "error", label: `异常 (${stats.error})` },
        ]}
        active={tab}
        onChange={(id) => setTab(id as typeof tab)}
      />

      <BpTable
        columns={["路由名", "源", "目标", "频率", "状态", "下次运行", "操作"]}
        rows={filtered.map((r) => {
          const tone = routeStatusTone(r.status);
          const isExpanded = expanded === r.id;
          return [
            <button
              key={r.id}
              type="button"
              className="nav-link"
              style={{ fontWeight: 600 }}
              onClick={() => setExpanded(isExpanded ? null : r.id)}
            >
              {isExpanded ? "▼" : "▶"} {r.name}
            </button>,
            <span className="muted">{r.source}</span>,
            r.target,
            r.frequency,
            <span className={`bp-discover-badge bp-discover-badge-${tone}`}>
              {ROUTE_STATUS_LABELS[r.status]}
            </span>,
            formatNextRun(r.nextRunAt),
            <div key="actions" style={{ display: "flex", gap: 4 }}>
              <button
                type="button"
                className="btn"
                onClick={() => void handleToggle(r.id, r.status)}
              >
                {r.status === "active" ? "暂停" : "启用"}
              </button>
              <Link to={`/data/sync-routes/${encodeURIComponent(r.id)}`} className="btn-nav">
                详情
              </Link>
            </div>,
          ];
        })}
      />

      {filtered.length === 0 && (
        <p className="muted">当前 Tab 无路由 · 切换 Tab 或新建</p>
      )}

      {/* Expanded detail panel */}
      {expanded && (() => {
        const route = filtered.find((r) => r.id === expanded);
        if (!route) return null;
        const pct = progressPercent(route.progress);
        const runs = syncRuns[route.id] || [];
        const runsLoading = syncRunsLoading[route.id];
        const runsErr = syncRunsErr[route.id];
        return (
          <div className="card" style={{ marginTop: "0.75rem" }}>
            <h2 className="aos-text" style={{ fontSize: "0.9rem" }}>
              {route.name} · 详情
            </h2>
            <div className="bp-prop-grid">
              <div>
                <div className="bp-prop-label">ID</div>
                <div className="bp-prop-value mono">{route.id}</div>
              </div>
              <div>
                <div className="bp-prop-label">同步进度</div>
                <div className="bp-prop-value">
                  <div className="bp-progress" style={{ width: 200 }}>
                    <div className="bp-progress-bar" style={{ width: `${pct}%` }} />
                  </div>
                  <span className="muted" style={{ marginLeft: 8 }}>{pct}%</span>
                </div>
              </div>
              <div>
                <div className="bp-prop-label">冲突记录</div>
                <div className={`bp-prop-value ${route.conflicts ? "bp-prop-warn" : "bp-prop-ok"}`}>
                  {route.conflicts || 0} 条
                </div>
              </div>
            </div>

            {/* D4 Phase C · C4: SyncRun 运行历史（真实 API 拉取） */}
            <div style={{ marginTop: "0.75rem" }}>
              <div className="bp-prop-label">运行历史 · 最近 SyncRun</div>
              {runsLoading ? (
                <p className="muted" style={{ fontSize: "0.8rem" }}>加载中…</p>
              ) : runsErr ? (
                <p className="error" style={{ fontSize: "0.8rem" }}>{runsErr}</p>
              ) : runs.length === 0 ? (
                <p className="muted" style={{ fontSize: "0.8rem" }}>暂无运行记录</p>
              ) : (
                <BpTable
                  columns={["运行ID", "状态", "开始时间", "耗时", "行数", "错误"]}
                  rows={runs.slice(0, 10).map((r) => {
                    const tone = runStatusTone(r.status);
                    return [
                      <span key="id" className="mono" style={{ fontSize: "0.8rem" }}>{r.id}</span>,
                      <span key="status" className={`bp-discover-badge bp-discover-badge-${tone}`}>
                        {formatRunStatus(r.status)}
                      </span>,
                      <span key="started" className="muted" style={{ fontSize: "0.8rem" }}>
                        {formatRunTime(r.started_at)}
                      </span>,
                      <span key="dur" className="muted" style={{ fontSize: "0.8rem" }}>
                        {r.duration_ms ? `${r.duration_ms}ms` : "—"}
                      </span>,
                      <span key="rows" className="muted" style={{ fontSize: "0.8rem" }}>
                        {r.rows_synced || 0}
                      </span>,
                      <span key="err" className="muted" style={{ fontSize: "0.75rem", color: r.error ? "#cf222e" : "#6e7781" }}>
                        {r.error ? r.error.slice(0, 60) : "—"}
                      </span>,
                    ];
                  })}
                />
              )}
            </div>

            {route.conflicts && route.conflicts > 0 ? (
              <BpBanner tone="warn">
                检测到 {route.conflicts} 条冲突 · 主键重复/字段类型不匹配 ·{" "}
                <Link to={`/data/sync-routes/${encodeURIComponent(route.id)}/conflicts`}>
                  查看冲突详情 →
                </Link>
              </BpBanner>
            ) : (
              <p className="aos-text" style={{ fontSize: "0.8rem" }}>无冲突</p>
            )}
          </div>
        );
      })()}

      <BpBanner tone="info">
        同步路由决定数据从哪个源分发到哪个目标 · 与「同步配置」任务一一对应 ·{" "}
        冲突需人工处理或配置自动解决策略
      </BpBanner>
    </S2Chrome>
  );
}
