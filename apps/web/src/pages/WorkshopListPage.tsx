import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiGet, apiPost } from "../api/client";
import { PageChrome } from "../components/PageChrome";
import { BpCard } from "../components/bp/BpCard";
import { BpEmpty } from "../components/bp/BpEmpty";

/* ============================================================================
 * 常量与类型（导出用于测试）
 * ========================================================================== */

export type CategoryId =
  | "all"
  | "order"
  | "risk"
  | "customer"
  | "asset"
  | "analytics"
  | "ticket"
  | "inventory"
  | "finance"
  | "marketing";

export interface CategoryDef {
  id: CategoryId;
  name: string;
  color: string;
}

export const CATEGORIES: CategoryDef[] = [
  { id: "all", name: "全部", color: "#374151" },
  { id: "order", name: "订单", color: "#2563EB" },
  { id: "risk", name: "风控", color: "#DC2626" },
  { id: "customer", name: "客户", color: "#7C3AED" },
  { id: "asset", name: "资产", color: "#0891B2" },
  { id: "analytics", name: "分析", color: "#059669" },
  { id: "ticket", name: "工单", color: "#D97706" },
  { id: "inventory", name: "库存", color: "#4F46E5" },
  { id: "finance", name: "财务", color: "#0D9488" },
  { id: "marketing", name: "营销", color: "#DB2777" },
];

export type ModuleStatus = "published" | "draft" | "disabled";

export interface ModuleItem {
  id: string;
  name: string;
  status: string;
  description?: string;
  entryPath?: string;
  objectType?: string;
  buddyBound?: boolean;
  category?: string;
  theme?: string;
  lastOpenedAt?: string;
  widgets?: string[];
}

/** 当 API 不可用时的 fallback mock 数据 */
export const MOCK_MODULES: ModuleItem[] = [
  {
    id: "mod-order-management",
    name: "订单管理系统",
    status: "published",
    description: "统计卡片 · 订单列表 · 趋势图 · 详情面板",
    category: "order",
    lastOpenedAt: new Date(Date.now() - 2 * 3600_000).toISOString(),
    entryPath: "/workshop/orders",
  },
  {
    id: "mod-risk-alert",
    name: "风险告警管理",
    status: "published",
    description: "筛选 · 风控告警表格 · 对象详情 · 活动日志",
    category: "risk",
    lastOpenedAt: new Date(Date.now() - 5 * 3600_000).toISOString(),
    entryPath: "/workshop/module",
  },
  {
    id: "mod-customer-center",
    name: "客户档案中心",
    status: "published",
    description: "客户列表 · 画像卡片 · 标签管理 · 跟进记录",
    category: "customer",
    lastOpenedAt: new Date(Date.now() - 26 * 3600_000).toISOString(),
    entryPath: "/workshop/module",
  },
  {
    id: "mod-asset-tracker",
    name: "资产追踪看板",
    status: "published",
    description: "资产地图 · 实时位置 · 维护日历 · 折旧曲线",
    category: "asset",
    lastOpenedAt: new Date(Date.now() - 48 * 3600_000).toISOString(),
    entryPath: "/workshop/module",
  },
  {
    id: "mod-analytics-dashboard",
    name: "经营分析仪表盘",
    status: "published",
    description: "KPI 卡片 · 趋势图 · 同环比 · 下钻分析",
    category: "analytics",
    lastOpenedAt: new Date(Date.now() - 72 * 3600_000).toISOString(),
    entryPath: "/workshop/module",
  },
  {
    id: "mod-ticket-system",
    name: "工单处理系统",
    status: "draft",
    description: "工单列表 · SLA 计时 · 分派 · 处理流程",
    category: "ticket",
    lastOpenedAt: new Date(Date.now() - 96 * 3600_000).toISOString(),
    entryPath: "/workshop/module",
  },
  {
    id: "mod-inventory-check",
    name: "库存盘点看板",
    status: "published",
    description: "仓库视图 · 盘点任务 · 差异处理 · 入出库记录",
    category: "inventory",
    lastOpenedAt: new Date(Date.now() - 120 * 3600_000).toISOString(),
    entryPath: "/workshop/module",
  },
  {
    id: "mod-finance-reconcile",
    name: "财务对账系统",
    status: "published",
    description: "流水匹配 · 差异标记 · 凭证生成 · 月度报表",
    category: "finance",
    lastOpenedAt: new Date(Date.now() - 144 * 3600_000).toISOString(),
    entryPath: "/workshop/module",
  },
  {
    id: "mod-marketing-campaign",
    name: "营销活动管理",
    status: "disabled",
    description: "活动策划 · 渠道管理 · 效果分析 · A/B 测试",
    category: "marketing",
    lastOpenedAt: new Date(Date.now() - 168 * 3600_000).toISOString(),
    entryPath: "/workshop/module",
  },
];

/* ============================================================================
 * 纯函数（导出用于测试）
 * ========================================================================== */

export function filterModules(
  items: ModuleItem[],
  category: CategoryId,
  query: string,
): ModuleItem[] {
  const q = query.trim().toLowerCase();
  return items.filter((m) => {
    if (category !== "all" && m.category !== category) return false;
    if (!q) return true;
    const name = m.name.toLowerCase();
    const desc = (m.description ?? "").toLowerCase();
    return name.includes(q) || desc.includes(q);
  });
}

export function sortByRecent(items: ModuleItem[]): ModuleItem[] {
  return [...items].sort((a, b) => {
    const aTime = a.lastOpenedAt ? new Date(a.lastOpenedAt).getTime() : 0;
    const bTime = b.lastOpenedAt ? new Date(b.lastOpenedAt).getTime() : 0;
    return bTime - aTime;
  });
}

export function formatRelativeTime(iso: string | undefined): string {
  if (!iso) return "—";
  const diff = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(diff / 60_000);
  if (minutes < 1) return "刚刚";
  if (minutes < 60) return `${minutes} 分钟前`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} 小时前`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days} 天前`;
  return new Date(iso).toLocaleDateString("zh-CN");
}

export function getStatusMeta(status: string): { label: string; bg: string; color: string } {
  if (status === "published") return { label: "已发布", bg: "var(--aos-green-bg)", color: "var(--aos-green-600)" };
  if (status === "draft") return { label: "草稿", bg: "var(--aos-amber-bg)", color: "var(--aos-amber-600)" };
  return { label: "已禁用", bg: "var(--aos-red-bg)", color: "var(--aos-red)" };
}

export function getCategoryName(category: string | undefined): string {
  const found = CATEGORIES.find((c) => c.id === category);
  return found?.name || category || "未分类";
}

export function getCategoryColor(category: string | undefined): string {
  const found = CATEGORIES.find((c) => c.id === category);
  return found?.color || "var(--aos-text-secondary)";
}

/* ============================================================================
 * 页面组件
 * ========================================================================== */

export function WorkshopListPage() {
  const [items, setItems] = useState<ModuleItem[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [filter, setFilter] = useState<CategoryId>("all");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiGet<{ items: ModuleItem[] }>("/v1/modules")
      .then((j) => {
        setItems(j.items?.length ? j.items : MOCK_MODULES);
        setLoading(false);
      })
      .catch(() => {
        // API 不可用时使用 mock 数据
        setItems(MOCK_MODULES);
        setErr(null);
        setLoading(false);
      });
  }, []);

  async function handleTouch(moduleId: string) {
    try {
      await apiPost(`/v1/modules/${moduleId}/touch`, {});
    } catch {
      // ignore
    }
  }

  const sortedItems = useMemo(() => sortByRecent(items), [items]);

  const recentItems = useMemo(() => sortedItems.slice(0, 5), [sortedItems]);

  const filteredItems = useMemo(
    () => filterModules(sortedItems, filter, ""),
    [sortedItems, filter],
  );

  const getEntryPath = (m: ModuleItem) => {
    if (m.id === "mod-order-management") return "/workshop/orders";
    if (m.id === "mod-ops-inbox") return "/workshop/inbox";
    if (m.id === "mod-cop-dashboard") return "/workshop/cop";
    if (m.id === "mod-buddy-assist") return "/workshop/buddy";
    return m.entryPath || "/workshop/inbox";
  };

  return (
    <PageChrome title="工作台 · 应用列表" lede="按业务场景打开模块。点击卡片进入画布编辑。">
      {/* 226 续修 G4：去掉双标题 + 失效 Tailwind 顶栏；卡片网格保持 inline */}
      <div className="wl-page">
        <div className="wl-toolbar">
          <Link to="/workshop/create" data-testid="btn-new-module" className="wl-btn-new">
            <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24" aria-hidden="true">
              <path d="M12 5v14M5 12h14" strokeLinecap="round" />
            </svg>
            新建
          </Link>
        </div>

        {/* 最近使用区 — 横滑卡片 */}
        <BpCard title="最近使用" subtitle="最近打开的 5 个模块" padding="md">
          {recentItems.length > 0 ? (
            <div
              style={{
                display: "flex",
                gap: 12,
                overflowX: "auto",
                paddingBottom: 4,
              }}
              data-testid="recent-scroll"
            >
              {recentItems.map((m) => {
                const entryPath = getEntryPath(m);
                const catColor = getCategoryColor(m.category);
                const catName = getCategoryName(m.category);
                return (
                  <Link
                    key={m.id}
                    to={entryPath}
                    onClick={() => void handleTouch(m.id)}
                    data-testid={`recent-card-${m.id}`}
                    style={{
                      flex: "0 0 200px",
                      maxWidth: 200,
                      border: "1px solid var(--aos-border)",
                      borderRadius: 2,
                      padding: 12,
                      background: "var(--aos-surface)",
                      cursor: "pointer",
                      transition: "box-shadow 0.15s, border-color 0.15s",
                      textDecoration: "none",
                      display: "block",
                    }}
                    className="wl-recent-card"
                  >
                    {/* 缩略图 */}
                    <div
                      style={{
                        width: "100%",
                        height: 60,
                        borderRadius: 4,
                        background: `linear-gradient(135deg, ${catColor}25, ${catColor}08)`,
                        marginBottom: 8,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        border: `1px solid ${catColor}20`,
                      }}
                    >
                      <span style={{ fontSize: 11, fontWeight: 600, color: catColor }}>
                        {m.name.slice(0, 2)}
                      </span>
                    </div>
                    {/* 分类标签 */}
                    <div style={{ marginBottom: 4 }}>
                      <span
                        style={{
                          fontSize: 10,
                          padding: "1px 6px",
                          borderRadius: 3,
                          background: `${catColor}15`,
                          color: catColor,
                          fontWeight: 500,
                        }}
                      >
                        {catName}
                      </span>
                    </div>
                    {/* 名称 */}
                    <div
                      style={{
                        fontSize: 13,
                        fontWeight: 600,
                        color: "var(--aos-text)",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {m.name}
                    </div>
                    {/* 最后打开时间 */}
                    <div style={{ fontSize: 10, color: "var(--aos-faint)", marginTop: 4 }}>
                      {formatRelativeTime(m.lastOpenedAt)}
                    </div>
                  </Link>
                );
              })}
            </div>
          ) : (
            <BpEmpty title="暂无最近使用的模块" description="打开任意模块后会出现在这里" />
          )}
        </BpCard>

        {/* 全部应用区 */}
        <BpCard
          title="全部应用"
          actions={
            <div className="wl-cat-row" data-testid="category-filters">
              {CATEGORIES.map((cat) => (
                <button
                  key={cat.id}
                  type="button"
                  data-testid={`cat-filter-${cat.id}`}
                  className={filter === cat.id ? "wl-cat-btn is-active" : "wl-cat-btn"}
                  onClick={() => setFilter(cat.id)}
                  aria-pressed={filter === cat.id}
                  style={
                    filter === cat.id
                      ? {
                          background: `${cat.color}15`,
                          color: cat.color,
                          borderColor: `${cat.color}40`,
                        }
                      : undefined
                  }
                >
                  {cat.name}
                </button>
              ))}
              <span className="wl-cat-count">
                {filteredItems.length} / {items.length}
              </span>
            </div>
          }
          padding="md"
        >
          {!loading && filteredItems.length > 0 ? (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
                gap: 12,
              }}
              data-testid="app-grid"
            >
              {filteredItems.map((m) => {
                const entryPath = getEntryPath(m);
                const catColor = getCategoryColor(m.category);
                const catName = getCategoryName(m.category);
                const statusMeta = getStatusMeta(m.status);
                return (
                  <div
                    key={m.id}
                    data-testid={`app-card-${m.id}`}
                    style={{
                      border: "1px solid var(--aos-border)",
                      borderRadius: 2,
                      padding: 14,
                      background: "var(--aos-surface)",
                      transition: "box-shadow 0.15s, border-color 0.15s",
                    }}
                    className="wl-app-card"
                  >
                    <Link
                      to={entryPath}
                      onClick={() => void handleTouch(m.id)}
                      style={{ textDecoration: "none", display: "block" }}
                    >
                      {/* 缩略图 */}
                      <div
                        style={{
                          width: "100%",
                          height: 64,
                          borderRadius: 2,
                          background: `linear-gradient(135deg, ${catColor}20, ${catColor}05)`,
                          marginBottom: 10,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          border: `1px solid ${catColor}15`,
                        }}
                      >
                        <span style={{ fontSize: 13, fontWeight: 700, color: catColor }}>
                          {m.name.slice(0, 2)}
                        </span>
                      </div>
                      {/* 分类 + 状态 */}
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                        <span
                          style={{
                            fontSize: 10,
                            padding: "1px 6px",
                            borderRadius: 3,
                            background: `${catColor}15`,
                            color: catColor,
                            fontWeight: 500,
                          }}
                        >
                          {catName}
                        </span>
                        <span
                          style={{
                            fontSize: 10,
                            fontWeight: 500,
                            padding: "1px 6px",
                            borderRadius: 3,
                            background: statusMeta.bg,
                            color: statusMeta.color,
                          }}
                        >
                          {statusMeta.label}
                        </span>
                      </div>
                      {/* 名称 */}
                      <div
                        style={{
                          fontSize: 13,
                          fontWeight: 600,
                          color: "var(--aos-text)",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {m.name}
                      </div>
                      {/* 描述 */}
                      <p style={{ fontSize: 11, color: "var(--aos-text-secondary)", marginTop: 4, lineHeight: 1.4 }}>
                        {m.description || "—"}
                      </p>
                      {/* 最后打开时间 */}
                      <div style={{ fontSize: 10, color: "var(--aos-faint)", marginTop: 8 }}>
                        最后打开：{formatRelativeTime(m.lastOpenedAt)}
                      </div>
                    </Link>
                    {/* 编辑入口 */}
                    <div style={{ marginTop: 8, paddingTop: 8, borderTop: "1px solid var(--aos-divider)" }}>
                      <Link
                        to="/workshop/canvas"
                        className="wl-card-link"
                        style={{ color: "var(--aos-accent)", textDecoration: "none", fontSize: 10 }}
                      >
                        ✏ 编辑画布 →
                      </Link>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : loading ? (
            <div style={{ textAlign: "center", padding: 24, color: "var(--aos-faint)" }}>加载中...</div>
          ) : (
            <BpEmpty
              title={items.length === 0 ? "暂无应用" : "无匹配结果"}
              description={
                items.length === 0
                  ? "点「+ 新建」开始创建第一个应用"
                  : "尝试调整分类筛选条件"
              }
              action={
                items.length === 0 ? (
                  <Link to="/workshop/create" className="btn">
                    + 新建
                  </Link>
                ) : undefined
              }
            />
          )}
        </BpCard>

        {err && <p className="error">{err}</p>}
      </div>
    </PageChrome>
  );
}
