import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiPost } from "../../api/client";
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
  const { data, err, reload } = useJsonGet<{ items: SyncRoute[] }>("/v1/sync-routes");
  const [tab, setTab] = useState<"all" | "active" | "paused" | "error">("all");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [msg, setMsg] = useState("");

  const allRoutes = useMemo(() => {
    const apiItems = data?.items;
    if (apiItems && apiItems.length > 0) return apiItems;
    return DEMO_ROUTES;
  }, [data?.items]);

  const filtered = useMemo(() => filterRoutesByTab(allRoutes, tab), [allRoutes, tab]);
  const stats = useMemo(() => computeRouteStats(allRoutes), [allRoutes]);

  async function handleToggle(id: string, current: RouteStatus) {
    setMsg("");
    try {
      const next = toggleRouteStatus({ status: current } as SyncRoute);
      await apiPost(`/v1/sync-routes/${encodeURIComponent(id)}/status`, {
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
          数据连接器 →
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
