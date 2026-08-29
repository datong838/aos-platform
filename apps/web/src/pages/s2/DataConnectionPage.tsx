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

const CAPABILITY_LABELS: Record<string, string> = {
  file: "文件读取",
  upload: "文件上传",
  media: "媒体同步",
  ingest: "数据入库",
  s3: "对象存储",
  jdbc: "数据库连接",
  mysql: "MySQL",
  postgres: "PostgreSQL",
  sqlserver: "SQL Server",
  "ssh-tunnel": "SSH 隧道",
  discover: "结构发现",
  rest: "REST API",
  http: "HTTP 请求",
  read: "只读访问",
  pagination: "分页读取",
};

export function connectorCapabilityLabel(capability: string): string {
  return CAPABILITY_LABELS[capability] || capability;
}

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
    return [];
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

  async function handleUninstall(id: string) {
    setMsg("");
    try {
      await apiPost(`/v1/connector-plugins/${encodeURIComponent(id)}/uninstall`, {});
      setMsg(`已卸载连接器插件 · ${id}`);
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
        ]}
      />

      {filtered.length === 0 && (
        <BpBanner tone="warn">
          {catalogItems.length === 0
            ? "当前没有可用连接器，请先部署并注册正式连接器插件"
            : "无匹配连接器 · 调整筛选条件"}
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
                    {connectorCapabilityLabel(cap)}
                  </span>
                ))}
              </div>
              <div
                className="bp-object-actions"
                style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8 }}
              >
                {c.installed ? (
                  <>
                    <Link
                      to={`/data?create=1&connector=${encodeURIComponent(c.id)}`}
                      className="btn-nav"
                    >
                      创建数据源
                    </Link>
                    {c.required ? (
                      <span className="muted" style={{ fontSize: "0.7rem", alignSelf: "center" }}>
                        系统必需 · 不可卸载
                      </span>
                    ) : (
                      <button
                        type="button"
                        className="btn-nav"
                        title="卸载此连接器插件"
                        onClick={() => void handleUninstall(c.id)}
                      >
                        卸载
                      </button>
                    )}
                  </>
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
                  {!c.installed ? "安装后方可创建数据源" : ""}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      <div style={{ marginTop: "1rem" }}>
        <BpBanner tone="info">
          从目录选择已安装连接器后创建数据源；连接参数与凭据仅在受控配置流程中维护。{" "}
          <Link to="/data">返回数据源管理</Link>
        </BpBanner>
      </div>
    </S2Chrome>
  );
}
