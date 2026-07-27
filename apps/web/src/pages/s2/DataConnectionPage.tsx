import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiDelete, apiPost } from "../../api/client";
import {
  BpBanner,
  BpMetricGrid,
  BpTable,
  BpToolbar,
} from "./blueprintUi";
import { S2Chrome, useJsonGet } from "./shared";

// ── Types ──────────────────────────────────────────────────────

export type ConnectorCategory = "database" | "saas" | "api" | "file" | "stream";

export type ConnectorStatus = "online" | "syncing" | "error" | "offline";

export type ConnectionCard = {
  id: string;
  name: string;
  category: ConnectorCategory;
  status: ConnectorStatus;
  lastSyncAt?: string;
  tableCount: number;
  description?: string;
};

export type ConnectionFilter = {
  query: string;
  category: string; // "all" | ConnectorCategory
  status: string; // "all" | ConnectorStatus
};

// ── Pure functions ─────────────────────────────────────────────

export const CATEGORY_LABELS: Record<ConnectorCategory, string> = {
  database: "数据库",
  saas: "SaaS",
  api: "API",
  file: "文件",
  stream: "流式",
};

export const STATUS_LABELS: Record<ConnectorStatus, string> = {
  online: "在线",
  syncing: "同步中",
  error: "失败",
  offline: "离线",
};

export function statusTone(s: ConnectorStatus): "ok" | "warn" | "bad" | "muted" {
  if (s === "online") return "ok";
  if (s === "syncing") return "warn";
  if (s === "error") return "bad";
  return "muted";
}

export function filterConnections(
  items: ConnectionCard[],
  filter: ConnectionFilter,
): ConnectionCard[] {
  const q = filter.query.trim().toLowerCase();
  return items.filter((c) => {
    if (q && !c.name.toLowerCase().includes(q) && !c.id.toLowerCase().includes(q)) {
      return false;
    }
    if (filter.category !== "all" && c.category !== filter.category) return false;
    if (filter.status !== "all" && c.status !== filter.status) return false;
    return true;
  });
}

export function computeConnectionStats(items: ConnectionCard[]) {
  const total = items.length;
  const online = items.filter((c) => c.status === "online").length;
  const syncing = items.filter((c) => c.status === "syncing").length;
  const error = items.filter((c) => c.status === "error").length;
  const totalTables = items.reduce((sum, c) => sum + c.tableCount, 0);
  return { total, online, syncing, error, totalTables };
}

export function paginate<T>(items: T[], page: number, pageSize: number): T[] {
  const start = (page - 1) * pageSize;
  return items.slice(start, start + pageSize);
}

export function totalPages(itemCount: number, pageSize: number): number {
  return Math.max(1, Math.ceil(itemCount / pageSize));
}

export function formatLastSync(iso?: string): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  const diff = Date.now() - d.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "刚刚";
  if (mins < 60) return `${mins} 分钟前`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} 小时前`;
  return `${Math.floor(hours / 24)} 天前`;
}

// ── Mock data (demo seeds) ─────────────────────────────────────

const DEMO_CONNECTIONS: ConnectionCard[] = [
  {
    id: "pg-prod",
    name: "PostgreSQL 生产库",
    category: "database",
    status: "online",
    lastSyncAt: new Date(Date.now() - 5 * 60000).toISOString(),
    tableCount: 48,
    description: "跨境电商 · 订单/商品/用户主库",
  },
  {
    id: "mysql-orders",
    name: "MySQL 订单库",
    category: "database",
    status: "syncing",
    lastSyncAt: new Date(Date.now() - 2 * 60000).toISOString(),
    tableCount: 23,
    description: "订单清洗 · 增量同步中",
  },
  {
    id: "shopify-store",
    name: "Shopify 店铺",
    category: "saas",
    status: "online",
    lastSyncAt: new Date(Date.now() - 60 * 60000).toISOString(),
    tableCount: 12,
    description: "商品/订单/客户 · Shopify API",
  },
  {
    id: "salesforce-crm",
    name: "Salesforce CRM",
    category: "saas",
    status: "offline",
    lastSyncAt: new Date(Date.now() - 3 * 86400000).toISOString(),
    tableCount: 0,
    description: "客户/商机 · 需重新授权",
  },
  {
    id: "kafka-events",
    name: "Kafka 事件流",
    category: "stream",
    status: "online",
    lastSyncAt: new Date(Date.now() - 1000).toISOString(),
    tableCount: 5,
    description: "实时事件 · 用户行为/支付",
  },
  {
    id: "rest-weather",
    name: "天气 REST API",
    category: "api",
    status: "error",
    lastSyncAt: new Date(Date.now() - 30 * 60000).toISOString(),
    tableCount: 2,
    description: "定时拉取 · 接口超时",
  },
  {
    id: "s3-datalake",
    name: "S3 数据湖",
    category: "file",
    status: "online",
    lastSyncAt: new Date(Date.now() - 10 * 60000).toISOString(),
    tableCount: 156,
    description: "对象存储 · 历史快照/日志",
  },
  {
    id: "file-local-wo",
    name: "本地文件 · 工单",
    category: "file",
    status: "online",
    lastSyncAt: new Date(Date.now() - 600000).toISOString(),
    tableCount: 1,
    description: "CSV 上传 · demo",
  },
  {
    id: "sap-erp",
    name: "SAP S/4HANA",
    category: "saas",
    status: "offline",
    tableCount: 0,
    description: "ERP · 未配置",
  },
  {
    id: "bigquery-bi",
    name: "BigQuery BI",
    category: "database",
    status: "online",
    lastSyncAt: new Date(Date.now() - 120 * 60000).toISOString(),
    tableCount: 34,
    description: "BI 报表 · 聚合表",
  },
];

// ── Page Component ─────────────────────────────────────────────

const PAGE_SIZE = 6;

export function DataConnectionPage() {
  const { data, err, reload } = useJsonGet<{ items: ConnectionCard[] }>("/v1/sources");
  const [filter, setFilter] = useState<ConnectionFilter>({
    query: "",
    category: "all",
    status: "all",
  });
  const [page, setPage] = useState(1);
  const [showCreate, setShowCreate] = useState(false);
  const [msg, setMsg] = useState("");

  // Fallback to demo data when API has no items
  const allItems = useMemo(() => {
    const apiItems = data?.items;
    if (apiItems && apiItems.length > 0) return apiItems;
    return DEMO_CONNECTIONS;
  }, [data?.items]);

  const filtered = useMemo(
    () => filterConnections(allItems, filter),
    [allItems, filter],
  );
  const stats = useMemo(() => computeConnectionStats(allItems), [allItems]);
  const pageItems = useMemo(() => paginate(filtered, page, PAGE_SIZE), [filtered, page]);
  const pages = totalPages(filtered.length, PAGE_SIZE);

  async function handleSync(id: string) {
    setMsg("");
    try {
      await apiPost(`/v1/sources/${encodeURIComponent(id)}/sync`, {});
      setMsg(`已触发同步 · ${id}`);
      reload();
    } catch (e) {
      setMsg(String((e as Error).message || e));
    }
  }

  async function handleDelete(id: string) {
    setMsg("");
    try {
      await apiDelete(`/v1/sources/${encodeURIComponent(id)}`);
      setMsg(`已删除 · ${id}`);
      reload();
    } catch (e) {
      setMsg(String((e as Error).message || e));
    }
  }

  return (
    <S2Chrome title="数据连接器" lede="连接外部数据系统 · 管理同步与配置">
      <BpToolbar>
        <input
          type="search"
          placeholder="搜索连接器名称/ID…"
          value={filter.query}
          onChange={(e) => {
            setFilter({ ...filter, query: e.target.value });
            setPage(1);
          }}
          style={{ minWidth: 200 }}
        />
        <select
          value={filter.category}
          onChange={(e) => {
            setFilter({ ...filter, category: e.target.value });
            setPage(1);
          }}
        >
          <option value="all">全部分类</option>
          {Object.entries(CATEGORY_LABELS).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
        <select
          value={filter.status}
          onChange={(e) => {
            setFilter({ ...filter, status: e.target.value });
            setPage(1);
          }}
        >
          <option value="all">全部状态</option>
          {Object.entries(STATUS_LABELS).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
        <button type="button" className="btn-primary" onClick={() => setShowCreate(true)}>
          + 新建连接器
        </button>
        <button type="button" className="btn" onClick={() => reload()}>
          刷新
        </button>
      </BpToolbar>

      {err && <p className="error">{err}</p>}
      {msg && <p className="aos-text">{msg}</p>}

      <BpMetricGrid
        items={[
          { label: "连接器总数", value: stats.total, tone: "muted" },
          { label: "在线", value: stats.online, tone: "ok" },
          { label: "同步中", value: stats.syncing, tone: "warn" },
          { label: "失败", value: stats.error, tone: stats.error > 0 ? "bad" : "ok" },
          { label: "表总数", value: stats.totalTables, tone: "muted" },
        ]}
      />

      {pageItems.length === 0 && (
        <BpBanner tone="warn">
          无匹配连接器 · 调整筛选条件或{" "}
          <Link to="/data/sources/new">新建数据源</Link>
        </BpBanner>
      )}

      <div className="bp-discover-grid" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))" }}>
        {pageItems.map((c) => {
          const tone = statusTone(c.status);
          return (
            <div key={c.id} className={`bp-discover-card bp-discover-${tone === "ok" ? "violet" : "muted"}`}>
              <div className="bp-discover-head">
                <span className="bp-discover-title">{c.name}</span>
                <span className={`bp-discover-badge bp-discover-badge-${tone}`}>
                  {STATUS_LABELS[c.status]}
                </span>
              </div>
              <p className="bp-discover-meta">
                {CATEGORY_LABELS[c.category]} · {c.tableCount} 表 · {formatLastSync(c.lastSyncAt)}
              </p>
              {c.description && (
                <p className="muted" style={{ fontSize: "0.75rem", margin: "0.25rem 0" }}>
                  {c.description}
                </p>
              )}
              <div className="bp-object-actions" style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8 }}>
                <Link to={`/data/sources/${encodeURIComponent(c.id)}`} className="btn-nav">
                  详情
                </Link>
                <Link to={`/data/sources/${encodeURIComponent(c.id)}/edit`} className="btn-nav">
                  编辑
                </Link>
                <button type="button" className="btn" onClick={() => void handleSync(c.id)}>
                  同步
                </button>
                <button
                  type="button"
                  className="btn"
                  style={{ color: "var(--aos-red)" }}
                  onClick={() => void handleDelete(c.id)}
                >
                  删除
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {pages > 1 && (
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: "1rem" }}>
          <button
            type="button"
            className="btn"
            disabled={page <= 1}
            onClick={() => setPage(page - 1)}
          >
            ← 上一页
          </button>
          <span className="muted">
            第 {page} / {pages} 页 · 共 {filtered.length} 条
          </span>
          <button
            type="button"
            className="btn"
            disabled={page >= pages}
            onClick={() => setPage(page + 1)}
          >
            下一页 →
          </button>
        </div>
      )}

      {showCreate && (
        <div className="card" style={{ marginTop: "1rem" }}>
          <h2 className="aos-text" style={{ fontSize: "0.95rem" }}>新建连接器向导</h2>
          <p className="muted" style={{ fontSize: "0.8rem" }}>
            点击下方链接进入完整向导流程（5 步：选类型 → 配置 → 选表 → 测试 → 完成）
          </p>
          <Link to="/data/sources/new" className="btn-primary">
            打开向导 →
          </Link>
          <button type="button" className="btn" style={{ marginLeft: 8 }} onClick={() => setShowCreate(false)}>
            取消
          </button>
        </div>
      )}

      <BpTable
        columns={["ID", "名称", "分类", "状态", "表数", "最后同步"]}
        rows={pageItems.map((c) => [
          <span className="muted">{c.id}</span>,
          <strong>{c.name}</strong>,
          CATEGORY_LABELS[c.category],
          <span className={`bp-discover-badge bp-discover-badge-${statusTone(c.status)}`}>
            {STATUS_LABELS[c.status]}
          </span>,
          String(c.tableCount),
          formatLastSync(c.lastSyncAt),
        ])}
      />

      <BpBanner tone="info">
        连接器列表对齐 <code>data-connection.html</code> · 卡片网格+表格双视图 ·{" "}
        <Link to="/data/sync-routes">同步路由</Link> ·{" "}
        <Link to="/data/sync-config">同步配置</Link>
      </BpBanner>
    </S2Chrome>
  );
}
