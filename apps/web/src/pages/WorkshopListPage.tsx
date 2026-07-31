import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiPost } from "../api/client";
import { PageChrome } from "../components/PageChrome";

/* ============================================================================
 * 226 · 严格对齐 foundry/html/workshop.html
 * ========================================================================== */

export type CategoryId = "all" | "ops" | "analytics" | "ai";

export interface CategoryDef {
  id: CategoryId;
  name: string;
  /** 兼容旧测试；筛选 UI 不再按色分色 */
  color: string;
}

/** 视觉稿筛选：全部 / 运营 / 分析 / AI 助手 */
export const CATEGORIES: CategoryDef[] = [
  { id: "all", name: "全部", color: "#374151" },
  { id: "ops", name: "运营", color: "#2563EB" },
  { id: "analytics", name: "分析", color: "#059669" },
  { id: "ai", name: "AI 助手", color: "#D97706" },
];

export type AccentTone = "blue" | "purple" | "amber";

export interface CatalogApp {
  id: string;
  name: string;
  eyebrow: string;
  accent: AccentTone;
  /** 最近区描述 */
  recentDesc: string;
  /** 全部区描述 */
  allDesc: string;
  category: Exclude<CategoryId, "all">;
  entryPath: string;
  canvasPath?: string;
  /** 画布入口文案：编辑画布 / 进入编辑器 */
  canvasLabel?: "edit" | "enter";
}

/** 视觉稿「全部应用」9 卡（固定产品目录） */
export const CATALOG_APPS: CatalogApp[] = [
  {
    id: "app-orders",
    name: "订单管理系统",
    eyebrow: "业务应用",
    accent: "blue",
    recentDesc: "统计卡片 · 订单列表 · 趋势图 · 详情面板",
    allDesc: "Order Management Dashboard",
    category: "ops",
    entryPath: "/workshop/orders",
  },
  {
    id: "app-inbox",
    name: "风险告警管理",
    eyebrow: "风控 Inbox",
    accent: "blue",
    recentDesc: "筛选 · 风控告警表格 · 对象详情 · 活动日志",
    allDesc: "Risk Alert Manager · 风控告警筛选 · 处置",
    category: "ops",
    entryPath: "/workshop/inbox",
  },
  {
    id: "app-graph",
    name: "对象探索",
    eyebrow: "本体前端",
    accent: "purple",
    recentDesc: "对象实例 · 属性筛选 · 图表探索 · Actions",
    allDesc: "Object Explorer · 对象实例 · 属性筛选",
    category: "analytics",
    entryPath: "/workshop/graph",
  },
  {
    id: "app-buddy",
    name: "Buddy · 智能助手",
    eyebrow: "智能嵌入",
    accent: "amber",
    recentDesc: "挂在任意模块侧栏 / 表旁",
    allDesc: "挂在任意模块侧栏 / 表旁",
    category: "ai",
    entryPath: "/workshop/buddy",
  },
  {
    id: "app-canvas",
    name: "画布编辑",
    eyebrow: "应用构建",
    accent: "blue",
    recentDesc: "Slate 画布 · 微件 · 布局",
    allDesc: "Slate 画布 · 微件 · 布局",
    category: "ops",
    entryPath: "/workshop/canvas",
    canvasPath: "/workshop/canvas",
    canvasLabel: "enter",
  },
  {
    id: "app-cop",
    name: "态势大屏",
    eyebrow: "态势感知",
    accent: "blue",
    recentDesc: "COP 大屏 · 实时监控",
    allDesc: "COP 大屏 · 实时监控",
    category: "ops",
    entryPath: "/workshop/cop",
  },
  {
    id: "app-publish",
    name: "发布入口",
    eyebrow: "发布管理",
    accent: "blue",
    recentDesc: "版本 · 分支 · 审批",
    allDesc: "版本 · 分支 · 审批",
    category: "ops",
    entryPath: "/workshop/publish",
  },
  {
    id: "app-iface",
    name: "模块接口",
    eyebrow: "系统集成",
    accent: "blue",
    recentDesc: "API · 变量 · 事件",
    allDesc: "API · 变量 · 事件",
    category: "ops",
    entryPath: "/workshop/module-interface",
  },
  {
    id: "app-events",
    name: "事件配置",
    eyebrow: "自动化",
    accent: "blue",
    recentDesc: "触发器 · 动作 · 订阅",
    allDesc: "触发器 · 动作 · 订阅",
    category: "ops",
    entryPath: "/workshop/events",
  },
];

/** 视觉稿「最近使用」默认三卡 */
export const RECENT_DEFAULT_IDS = ["app-orders", "app-inbox", "app-graph"] as const;

/** 兼容旧测试命名 */
export const MOCK_MODULES = CATALOG_APPS.map((a, i) => ({
  id: a.id,
  name: a.name,
  status: "published" as const,
  description: a.allDesc,
  category: a.category,
  lastOpenedAt: new Date(Date.now() - (i + 1) * 3600_000).toISOString(),
  entryPath: a.entryPath,
}));

export type ModuleItem = (typeof MOCK_MODULES)[number];
export type ModuleStatus = "published" | "draft" | "disabled";

/* ============================================================================
 * 纯函数
 * ========================================================================== */

export function filterModules(
  items: { category?: string; name: string; description?: string }[],
  category: CategoryId,
  query: string,
) {
  const q = query.trim().toLowerCase();
  return items.filter((m) => {
    if (category !== "all" && m.category !== category) return false;
    if (!q) return true;
    const name = m.name.toLowerCase();
    const desc = (m.description ?? "").toLowerCase();
    return name.includes(q) || desc.includes(q);
  });
}

export function filterCatalog(apps: CatalogApp[], category: CategoryId): CatalogApp[] {
  if (category === "all") return apps;
  return apps.filter((a) => a.category === category);
}

export function sortByRecent<T extends { lastOpenedAt?: string }>(items: T[]): T[] {
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
 * Page
 * ========================================================================== */

export function WorkshopListPage() {
  const [filter, setFilter] = useState<CategoryId>("all");

  const recentApps = useMemo(
    () =>
      RECENT_DEFAULT_IDS.map((id) => CATALOG_APPS.find((a) => a.id === id)!).filter(Boolean),
    [],
  );

  const filteredApps = useMemo(() => filterCatalog(CATALOG_APPS, filter), [filter]);

  async function handleTouch(id: string) {
    try {
      await apiPost(`/v1/modules/${id}/touch`, {});
    } catch {
      /* 目录卡可能无对应 meta_module · 忽略 */
    }
  }

  return (
    <PageChrome hideHeader>
      <div className="wl-page">
        <div className="wl-head">
          <div className="wl-head-text">
            <h1 className="wl-head-title">应用列表</h1>
            <p className="wl-head-lede">
              按业务场景打开模块。风险告警管理、对象探索、智能助手等都是从这里打开的模块，不是并列产品。
            </p>
          </div>
          <Link to="/workshop/create" data-testid="btn-new-module" className="wl-btn-new">
            <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24" aria-hidden="true">
              <path d="M12 5v14M5 12h14" strokeLinecap="round" />
            </svg>
            新建 Module
          </Link>
        </div>

        {/* 最近使用 */}
        <section className="wl-panel" data-testid="recent-section">
          <div className="wl-panel-head">
            <h2 className="wl-panel-title">最近使用</h2>
            <span className="wl-panel-meta">按打开时间排序</span>
          </div>
          <div className="wl-grid" data-testid="recent-scroll">
            {recentApps.map((app) => (
              <article key={app.id} className="wl-mod-card" data-testid={`recent-card-${app.id}`}>
                <Link
                  to={app.entryPath}
                  className="wl-mod-main"
                  onClick={() => void handleTouch(app.id)}
                >
                  <div className={`wl-mod-eyebrow is-${app.accent}`}>{app.eyebrow}</div>
                  <div className={`wl-mod-title is-${app.accent}`}>{app.name}</div>
                  <p className="wl-mod-desc">{app.recentDesc}</p>
                </Link>
                <div className="wl-mod-actions">
                  <Link to={app.entryPath} onClick={() => void handleTouch(app.id)}>
                    ▶ 打开运行态
                  </Link>
                  <span className="wl-mod-sep">·</span>
                  <Link to={app.canvasPath || "/workshop/canvas"}>✏ 编辑画布 →</Link>
                </div>
              </article>
            ))}
          </div>
        </section>

        {/* 全部应用 */}
        <section className="wl-panel" data-testid="all-section">
          <div className="wl-panel-head">
            <h2 className="wl-panel-title">全部应用</h2>
            <div className="wl-cat-row" data-testid="category-filters">
              {CATEGORIES.map((cat) => (
                <button
                  key={cat.id}
                  type="button"
                  data-testid={`cat-filter-${cat.id}`}
                  className={filter === cat.id ? "wl-cat-btn is-active" : "wl-cat-btn"}
                  onClick={() => setFilter(cat.id)}
                  aria-pressed={filter === cat.id}
                >
                  {cat.name}
                </button>
              ))}
            </div>
          </div>
          <div className="wl-grid" data-testid="app-grid">
            {filteredApps.map((app) => (
              <article key={app.id} className="wl-mod-card" data-testid={`app-card-${app.id}`}>
                <Link
                  to={app.entryPath}
                  className="wl-mod-main"
                  onClick={() => void handleTouch(app.id)}
                >
                  <div className={`wl-mod-eyebrow is-${app.accent}`}>{app.eyebrow}</div>
                  <div className={`wl-mod-title is-${app.accent}`}>{app.name}</div>
                  <p className="wl-mod-desc">{app.allDesc}</p>
                </Link>
                <div className="wl-mod-actions">
                  {app.canvasLabel === "enter" ? (
                    <Link to={app.entryPath} className="wl-mod-enter">
                      ▶ 进入编辑器
                    </Link>
                  ) : (
                    <Link to={app.canvasPath || "/workshop/canvas"}>✏ 编辑画布 →</Link>
                  )}
                </div>
              </article>
            ))}
          </div>
        </section>
      </div>
    </PageChrome>
  );
}
