import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiPost } from "../../api/client";
import {
  BpBanner,
  BpMetricGrid,
  BpToolbar,
} from "./blueprintUi";
import { S2Chrome, useJsonGet } from "./shared";
import type { ConnectorPlugin } from "./dataConnectionUi";

// ── Types ──────────────────────────────────────────────────────

export type ConnectorCategory = "database" | "saas" | "api" | "file" | "stream";

export type ConnectorCatalogCard = {
  id: string;
  name: string;
  category: ConnectorCategory;
  description: string;
  capabilities: string[];
  installed: boolean;
  required?: boolean;
  runtime: "ready" | "stub" | "mock";
};

export type CatalogFilter = {
  query: string;
  category: string;
};

// ── Pure functions ─────────────────────────────────────────────

export const CATEGORY_LABELS: Record<ConnectorCategory, string> = {
  database: "数据库",
  saas: "SaaS",
  api: "API",
  file: "文件",
  stream: "流式",
};

export function filterCatalog(
  items: ConnectorCatalogCard[],
  filter: CatalogFilter,
): ConnectorCatalogCard[] {
  const q = filter.query.trim().toLowerCase();
  return items.filter((c) => {
    if (q && !c.name.toLowerCase().includes(q) && !c.description.toLowerCase().includes(q)) {
      return false;
    }
    if (filter.category !== "all" && c.category !== filter.category) return false;
    return true;
  });
}

export function computeCatalogStats(items: ConnectorCatalogCard[]) {
  const total = items.length;
  const installed = items.filter((c) => c.installed).length;
  const notInstalled = total - installed;
  const required = items.filter((c) => c.required).length;
  return { total, installed, notInstalled, required };
}

// ── Demo catalog (fallback when API returns empty) ─────────────

const DEMO_CATALOG: ConnectorCatalogCard[] = [
  {
    id: "jdbc-mysql",
    name: "MySQL JDBC",
    category: "database",
    description: "MySQL / MariaDB 结构化入库 · 已支持 Niushop 微商城",
    capabilities: ["Batch syncs", "Virtual tables", "Incremental cursor"],
    installed: true,
    required: true,
    runtime: "ready",
  },
  {
    id: "niushop-mysql",
    name: "Niushop 微商城",
    category: "database",
    description: "Niushop 微商城专属 · 预设 8 表映射 + PII 排除",
    capabilities: ["Batch syncs", "Virtual tables", "PII exclusion"],
    installed: true,
    required: true,
    runtime: "ready",
  },
  {
    id: "jdbc-postgres",
    name: "PostgreSQL JDBC",
    category: "database",
    description: "PostgreSQL 结构化入库 · 支持批量同步与流式 CDC",
    capabilities: ["Batch syncs", "Streaming syncs", "Virtual tables"],
    installed: true,
    required: true,
    runtime: "ready",
  },
  {
    id: "jdbc-oracle",
    name: "Oracle JDBC",
    category: "database",
    description: "Oracle 数据库连接器 · 支持批量同步",
    capabilities: ["Batch syncs", "Virtual tables"],
    installed: false,
    runtime: "stub",
  },
  {
    id: "file-local",
    name: "本地文件",
    category: "file",
    description: "本地目录探针 + 可选 ingest · CSV/Excel/JSON",
    capabilities: ["Batch syncs", "Media syncs"],
    installed: true,
    required: true,
    runtime: "ready",
  },
  {
    id: "file-object-store",
    name: "对象存储文件",
    category: "file",
    description: "S3 兼容对象仓原件 · 支持 Parquet/CSV/JSON",
    capabilities: ["Batch syncs", "Media syncs", "File exports"],
    installed: true,
    required: true,
    runtime: "ready",
  },
  {
    id: "rest-api",
    name: "REST API",
    category: "api",
    description: "通用 REST API 拉取 · 支持认证与分页",
    capabilities: ["Batch syncs", "Webhooks", "OAuth2"],
    installed: true,
    runtime: "ready",
  },
  {
    id: "shopify",
    name: "Shopify",
    category: "saas",
    description: "Shopify 电商平台 · 商品/订单/客户 API",
    capabilities: ["Batch syncs", "Webhooks", "Streaming syncs"],
    installed: false,
    runtime: "stub",
  },
  {
    id: "salesforce",
    name: "Salesforce CRM",
    category: "saas",
    description: "Salesforce CRM · 客户/商机/合同",
    capabilities: ["Batch syncs", "Streaming syncs"],
    installed: false,
    runtime: "stub",
  },
  {
    id: "kafka",
    name: "Kafka",
    category: "stream",
    description: "Apache Kafka 事件流 · 实时数据管道",
    capabilities: ["Streaming syncs", "CDC"],
    installed: false,
    runtime: "stub",
  },
];

// ── Page Component ─────────────────────────────────────────────

export function DataConnectionPage() {
  const { data, err, reload } = useJsonGet<{ items: ConnectorPlugin[] }>("/v1/connector-plugins");
  const [filter, setFilter] = useState<CatalogFilter>({ query: "", category: "all" });
  const [msg, setMsg] = useState("");

  // Map ConnectorPlugin to ConnectorCatalogCard
  const catalogItems = useMemo(() => {
    const apiItems = data?.items;
    if (apiItems && apiItems.length > 0) {
      return apiItems.map((p) => ({
        id: p.id,
        name: p.nameZh || p.name || p.id,
        category: inferCategory(p.id),
        description: p.description || "",
        capabilities: p.capabilities || [],
        installed: p.installed || false,
        required: p.required || false,
        runtime: (p.runtime as "ready" | "stub" | "mock") || "stub",
      }));
    }
    return DEMO_CATALOG;
  }, [data?.items]);

  const filtered = useMemo(
    () => filterCatalog(catalogItems, filter),
    [catalogItems, filter],
  );
  const stats = useMemo(() => computeCatalogStats(catalogItems), [catalogItems]);

  async function handleInstall(id: string) {
    setMsg("");
    try {
      await apiPost(`/v1/connector-plugins/${encodeURIComponent(id)}/install`, {});
      setMsg(`已安装连接器插件 · ${id}`);
      reload();
    } catch (e) {
      setMsg(String((e as Error).message || e));
    }
  }

  function inferCategory(id: string): ConnectorCategory {
    if (id.includes("jdbc") || id.includes("postgres") || id.includes("mysql") || id.includes("oracle"))
      return "database";
    if (id.startsWith("file")) return "file";
    if (id.startsWith("rest") || id === "rest-api") return "api";
    if (id === "kafka" || id === "stream") return "stream";
    return "saas";
  }

  return (
    <S2Chrome
      title="连接器目录"
      lede="可用连接器插件 · 选择并安装，然后创建数据源连接"
    >
      <BpToolbar>
        <input
          type="search"
          placeholder="搜索连接器…"
          value={filter.query}
          onChange={(e) => {
            setFilter({ ...filter, query: e.target.value });
          }}
          style={{ minWidth: 200 }}
        />
        <select
          value={filter.category}
          onChange={(e) => {
            setFilter({ ...filter, category: e.target.value });
          }}
        >
          <option value="all">全部分类</option>
          {Object.entries(CATEGORY_LABELS).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
        <button type="button" className="btn" onClick={() => reload()}>
          刷新
        </button>
      </BpToolbar>

      {err && <p className="error">{err}</p>}
      {msg && <p className="aos-text">{msg}</p>}

      <BpMetricGrid
        items={[
          { label: "连接器总数", value: stats.total, tone: "muted" },
          { label: "已安装", value: stats.installed, tone: "ok" },
          { label: "未安装", value: stats.notInstalled, tone: "warn" },
          { label: "必做", value: stats.required, tone: "muted" },
        ]}
      />

      {filtered.length === 0 && (
        <BpBanner tone="warn">
          无匹配连接器 · 调整筛选条件
        </BpBanner>
      )}

      <div
        className="bp-discover-grid"
        style={{ gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))" }}
      >
        {filtered.map((c) => {
          const categoryTone = c.category === "database"
            ? "violet"
            : c.category === "saas"
              ? "amber"
              : c.category === "api"
                ? "amber"
                : c.category === "stream"
                  ? "rose"
                  : "emerald";
          return (
            <div
              key={c.id}
              className={`bp-discover-card bp-discover-${categoryTone}`}
            >
              <div className="bp-discover-head">
                <span className="bp-discover-title">{c.name}</span>
                <span
                  className={`bp-tag ${c.installed ? "bp-tag-ok" : "bp-tag-warn"}`}
                >
                  {c.installed ? "已安装" : "未安装"}
                </span>
              </div>
              <p className="bp-discover-meta">
                {CATEGORY_LABELS[c.category]}
                {c.runtime === "stub" ? " · stub" : ""}
                {c.required ? " · 必做" : ""}
              </p>
              {c.description && (
                <p
                  className="muted"
                  style={{ fontSize: "0.75rem", margin: "0.25rem 0" }}
                >
                  {c.description}
                </p>
              )}
              <div
                style={{
                  display: "flex",
                  gap: 4,
                  flexWrap: "wrap",
                  marginTop: 4,
                }}
              >
                {c.capabilities.map((cap) => (
                  <span
                    key={cap}
                    className="muted"
                    style={{
                      fontSize: "0.65rem",
                      background: "var(--aos-surface-hover)",
                      padding: "1px 4px",
                      borderRadius: 2,
                    }}
                  >
                    {cap}
                  </span>
                ))}
              </div>
              <div
                className="bp-object-actions"
                style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8 }}
              >
                {c.installed ? (
                  <Link
                    to={`/data/sources/new?connector=${encodeURIComponent(c.id)}`}
                    className="btn-nav"
                  >
                    创建数据源
                  </Link>
                ) : (
                  <button
                    type="button"
                    className="btn-nav"
                    onClick={() => void handleInstall(c.id)}
                  >
                    安装
                  </button>
                )}
                <span
                  className="muted"
                  style={{ fontSize: "0.7rem", alignSelf: "center" }}
                >
                  {c.runtime === "stub" ? "stub 仅可装" : ""}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      <div style={{ marginTop: "1rem" }}>
        <BpBanner tone="info">
          连接器目录对齐 <code>data-connection.html</code> 蓝图 · 卡片网格视图 ·{" "}
          <Link to="/data">数据源管理</Link> ·{" "}
          <Link to="/data/sources/new">新建数据源向导</Link>
        </BpBanner>
      </div>
    </S2Chrome>
  );
}
