import { useState, useMemo, useEffect } from "react";
import { Link } from "react-router-dom";
import { PageChrome } from "../../components/PageChrome";
import { apiGet } from "../../api/client";

export type WidgetItem = {
  id: string;
  name: string;
  description: string;
  source: "builtin" | "market" | "custom";
  version: string;
  usedBy?: number;
  icon: string;
  installed: boolean;
  canvasKind?: string;
};

/** canvasKind → 已有 SVG 图标 key · 用于把 API 返回的 canvasKind 渲染为彩色图标 */
const KIND_TO_ICON_KEY: Record<string, string> = {
  table: "table",
  graph: "chart",
  action: "form",
  filter: "filter",
  "filter-bar": "filter",
  buddy: "custom",
  overlay: "map",
  metric: "stat",
  "stat-card": "stat",
  "page-header": "hero",
  "detail-drawer": "container",
  "trend-chart": "chart",
  stub: "button",
};

/** 后端 manifest item → 前端 WidgetItem · 名字以 nameZh 为准 */
export function apiItemToWidgetItem(it: {
  id: string;
  name?: string;
  nameZh?: string;
  description?: string;
  version?: string;
  runtime?: string;
  author?: string;
  canvasKind?: string;
  installed?: boolean;
}): WidgetItem {
  const runtime = it.runtime || "inproc";
  const author = it.author || "aos";
  const source: WidgetItem["source"] =
    runtime === "stub" ? "custom" : author === "aos" ? "builtin" : "market";
  return {
    id: it.id,
    name: it.nameZh || it.name || it.id,
    description: businessWidgetDescription(it.description || ""),
    source,
    version: it.version || "0.1.0",
    usedBy: undefined,
    icon: KIND_TO_ICON_KEY[it.canvasKind || ""] || "table",
    installed: it.installed === true,
    canvasKind: it.canvasKind,
  };
}

/** 把服务端目录中的实现术语收拢为面向业务人员的中文说明。 */
export function businessWidgetDescription(input: string): string {
  return input
    .replace(/Object\s*Set/gi, "对象集")
    .replace(/Object\s*Type/gi, "对象类型")
    .replace(/AIP\s*Assist/gi, "智能助手")
    .replace(/\bAIP\b/gi, "智能能力")
    .replace(/\bAction\b/gi, "业务动作")
    .replace(/\bWidget\b/gi, "组件")
    .replace(/\boverlay\b/gi, "浮层")
    .replace(/\bvalidate\b/gi, "安全校验")
    .replace(/\bsection\b/gi, "内容分区")
    .replace(/\bTabs?\b/gi, "分类标签")
    .replace(/\bSelection\b/gi, "选择联动")
    .replace(/\bWiki\b/gi, "知识说明")
    .replace(/\bcount\s*\/\s*sum\b/gi, "计数与汇总")
    .replace(/\btrend\b/gi, "趋势")
    .replace(/\bdateField\b/gi, "日期字段")
    .replace(/\bN\s*天/gi, "指定天数")
    .replace(/\b1-hop\b/gi, "单层")
    .replace(/adjacency_table/gi, "邻接列表")
    .replace(/（非\s*G6\s*[·・]\s*\d+）/gi, "")
    .replace(/（\s*\d+\s*）/g, "")
    .replace(/[·・]?\s*scheme\s*\d+/gi, "")
    .replace(/[·・]?\s*source\s*=\s*[^，。；;（）()]+/gi, "")
    .replace(/\s{2,}/g, " ")
    .replace(/\s+([，。；;、])/g, "$1")
    .trim();
}

const CANVAS_KINDS = new Set(Object.keys(KIND_TO_ICON_KEY));

export function canvasUsePath(item: WidgetItem): string | null {
  if (!item.installed || !item.canvasKind || !CANVAS_KINDS.has(item.canvasKind)) return null;
  return `/workshop/canvas?pluginId=${encodeURIComponent(item.id)}&canvasKind=${encodeURIComponent(item.canvasKind)}`;
}

const SOURCE_LABELS: Record<string, string> = {
  all: "全部",
  builtin: "平台内置",
  market: "市场安装",
  custom: "代码开发",
};

function WidgetIcon({ name }: { name: string }) {
  const paths: Record<string, JSX.Element> = {
    table: (
      <>
        <rect x="3" y="4" width="18" height="16" rx="1" />
        <path d="M3 10h18M9 10v10M15 10v10" strokeLinecap="round" />
      </>
    ),
    chart: (
      <path d="M3 17l6-6 4 4 8-8M14 7h7v7" strokeLinecap="round" strokeLinejoin="round" />
    ),
    form: (
      <>
        <rect x="4" y="3" width="16" height="18" rx="1" />
        <path d="M8 8h8M8 12h8M8 16h4" strokeLinecap="round" />
      </>
    ),
    objectset: (
      <>
        <circle cx="6" cy="12" r="2" />
        <circle cx="18" cy="6" r="2" />
        <circle cx="18" cy="18" r="2" />
        <path d="M8 12h6M15 7.5l-5 3M15 16.5l-5-3" strokeLinecap="round" />
      </>
    ),
    navbar: <path d="M4 6h16M4 12h16M4 18h16" strokeLinecap="round" />,
    hero: (
      <>
        <rect x="3" y="4" width="18" height="10" rx="1" />
        <path d="M3 18h18" strokeLinecap="round" />
      </>
    ),
    container: (
      <>
        <rect x="3" y="3" width="18" height="18" rx="1" />
        <rect x="7" y="7" width="10" height="10" rx="1" />
      </>
    ),
    map: (
      <path d="M9 4l-6 2v14l6-2 6 2 6-2V4l-6 2-6-2zM9 4v14M15 6v14" strokeLinecap="round" strokeLinejoin="round" />
    ),
    timeline: (
      <path d="M12 2v20M6 6h12M6 12h12M6 18h12" strokeLinecap="round" />
    ),
    button: (
      <>
        <rect x="3" y="9" width="18" height="6" rx="3" />
        <path d="M9 12h6" strokeLinecap="round" />
      </>
    ),
    stat: (
      <>
        <rect x="3" y="4" width="18" height="16" rx="2" />
        <path d="M7 14l3-3 3 2 4-5" strokeLinecap="round" strokeLinejoin="round" />
      </>
    ),
    filter: (
      <path d="M4 6h16l-6 7v5l-4-2v-3L4 6z" strokeLinecap="round" strokeLinejoin="round" />
    ),
    kanban: (
      <>
        <rect x="3" y="4" width="5" height="16" rx="1" />
        <rect x="10" y="4" width="5" height="16" rx="1" />
        <rect x="17" y="4" width="4" height="16" rx="1" />
      </>
    ),
    gantt: (
      <>
        <rect x="3" y="4" width="18" height="16" rx="1" />
        <rect x="6" y="8" width="6" height="3" rx="1" fill="currentColor" />
        <rect x="12" y="13" width="6" height="3" rx="1" fill="currentColor" />
      </>
    ),
    calendar: (
      <>
        <rect x="3" y="4" width="18" height="18" rx="2" />
        <path d="M16 2v4M8 2v4M3 10h18" strokeLinecap="round" />
      </>
    ),
    custom: (
      <path d="M12 3l1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5L12 3z" strokeLinecap="round" strokeLinejoin="round" />
    ),
  };
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} aria-hidden="true">
      {paths[name] || paths.table}
    </svg>
  );
}

export function WidgetRegistryPage() {
  const [source, setSource] = useState<string>("all");
  const [query] = useState("");
  const [widgets, setWidgets] = useState<WidgetItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<WidgetItem | null>(null);
  const [catalogNote, setCatalogNote] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await apiGet<{
          items?: Array<{
            id: string;
            name?: string;
            nameZh?: string;
            description?: string;
            version?: string;
            runtime?: string;
            author?: string;
            canvasKind?: string;
            installed?: boolean;
          }>;
        }>("/v1/widget-plugins");
        if (cancelled) return;
        const items = (res.items || []).map(apiItemToWidgetItem);
        setWidgets(items);
        setCatalogNote(items.length ? "组件目录已从当前服务读取" : "当前服务没有返回可用组件");
      } catch {
        if (!cancelled) {
          setWidgets([]);
          setCatalogNote("组件目录服务暂不可用，页面未注入演示组件");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const filtered = useMemo(() => {
    return widgets.filter((w) => {
      if (source !== "all" && w.source !== source) return false;
      if (!query.trim()) return true;
      const q = query.toLowerCase();
      return w.name.toLowerCase().includes(q) || w.description.toLowerCase().includes(q);
    });
  }, [widgets, source, query]);

  const sourceTabs = [
    { id: "all", count: widgets.length },
    { id: "builtin", count: widgets.filter((w) => w.source === "builtin").length },
    { id: "market", count: widgets.filter((w) => w.source === "market").length },
    { id: "custom", count: widgets.filter((w) => w.source === "custom").length },
  ];

  return (
    <PageChrome title="组件注册表" lede="画布可用组件的统一目录，按平台内置、市场安装和代码开发三类展示。">
      <div className="wr-page">
        <div className="wr-tabs">
          {sourceTabs.map((tab) => (
            <button
              key={tab.id}
              className={source === tab.id ? "wr-tab is-active" : "wr-tab"}
              onClick={() => {
                setSource(tab.id);
                if (widgets.length > 0) {
                  setCatalogNote(tab.id === "market" ? "已筛选市场来源目录；当前未开放安装入口" : "组件目录已从当前服务读取");
                }
              }}
            >
              {SOURCE_LABELS[tab.id]}
              <span className="wr-tab-count">({tab.count})</span>
            </button>
          ))}
          <span className="wr-tabs-right">
            {loading ? "加载中…" : `已安装 ${widgets.filter((w) => w.installed).length} / 目录 ${widgets.length}`}
          </span>
        </div>

        <div className="wr-grid">
          {filtered.map((w) => (
            <div
              key={w.id}
              className="wr-card"
              onClick={() => setSelected(w)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  setSelected(w);
                }
              }}
            >
              <div className="wr-card-top">
                <div className={`wr-icon wr-icon-${w.source}`}>
                  <WidgetIcon name={w.icon} />
                </div>
                <span className={`wr-source-tag ${w.source}`}>
                  {w.source === "builtin" ? "内置" : w.source === "market" ? "市场" : "自定义"}
                </span>
              </div>
              <h3>{w.name}</h3>
              <p className="wr-card-desc">{w.description}</p>
              <div className="wr-card-meta">
                <span>{typeof w.usedBy === "number" ? (w.usedBy > 0 ? `被 ${w.usedBy} 个应用使用` : "暂无应用使用") : "使用情况未读取"}</span>
                <span>·</span>
                <span>{w.installed ? "已安装" : "未安装"}</span>
              </div>
            </div>
          ))}
          {!loading && filtered.length === 0 && (
            <div style={{ gridColumn: "1 / -1", opacity: 0.6, padding: "16px", fontSize: "13px" }}>
              没有匹配的组件
            </div>
          )}
        </div>

        {/* 底部创建入口 — 对齐视觉稿 */}
        <div className="wr-callout">
          <div className="wr-callout-actions">
            <Link to="/data/code-repos" className="wr-callout-primary">
              + 从代码仓库创建自定义组件
            </Link>
            <span className="wr-callout-sep">或</span>
            <button
              type="button"
              className="wr-callout-secondary"
              onClick={() => {
                setSource("market");
                setCatalogNote("已切换到市场来源目录；安装能力尚未开放");
              }}
            >
              浏览组件市场
            </button>
          </div>
          <p className="wr-callout-hint">
            自定义组件从代码仓库接入，注册成功后会出现在当前目录
          </p>
          {catalogNote && <p className="wr-callout-hint">{catalogNote}</p>}
        </div>
      </div>

      {selected && (
        <div
          className="wr-modal-overlay"
          role="dialog"
          aria-modal="true"
          aria-label={`${selected.name} 详情`}
          onClick={(e) => {
            if (e.target === e.currentTarget) setSelected(null);
          }}
        >
          <div className="wr-modal">
            <div className="wr-modal-header">
              <div className="wr-modal-title-row">
                <div className={`wr-modal-icon wr-icon-${selected.source}`}>
                  <WidgetIcon name={selected.icon} />
                </div>
                <div>
                  <h2 className="wr-modal-title">{selected.name}</h2>
                  <span className={`wr-source-tag ${selected.source}`}>
                    {selected.source === "builtin"
                      ? "平台内置"
                      : selected.source === "market"
                        ? "市场安装"
                        : "代码开发"}
                  </span>
                </div>
              </div>
              <button
                className="wr-modal-close"
                onClick={() => setSelected(null)}
                aria-label="关闭"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <path d="M18 6L6 18M6 6l12 12" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
            </div>
            <div className="wr-modal-body">
              <p className="wr-modal-desc">{selected.description}</p>
              <dl className="wr-modal-meta">
                <div>
                  <dt>使用次数</dt>
                  <dd>{typeof selected.usedBy === "number" ? (selected.usedBy > 0 ? `${selected.usedBy} 个应用` : "暂未使用") : "当前未读取"}</dd>
                </div>
                <div>
                  <dt>来源</dt>
                  <dd>
                    {selected.source === "builtin"
                      ? "平台内置（随 AOS 发布）"
                      : selected.source === "market"
                        ? "市场安装"
                        : "代码开发（自定义）"}
                  </dd>
                </div>
              </dl>
              <details>
                <summary>审计信息</summary>
                <dl className="wr-modal-meta">
                  <div>
                    <dt>组件标识</dt>
                    <dd><code>{selected.id}</code></dd>
                  </div>
                  <div>
                    <dt>版本</dt>
                    <dd>{selected.version}</dd>
                  </div>
                  <div>
                    <dt>画布类型</dt>
                    <dd>{selected.canvasKind || "未声明"}</dd>
                  </div>
                </dl>
              </details>
            </div>
            <div className="wr-modal-footer">
              <button className="wr-modal-btn wr-modal-btn-secondary" onClick={() => setSelected(null)}>
                关闭
              </button>
              {canvasUsePath(selected) ? (
                <Link className="wr-modal-btn wr-modal-btn-primary" to={canvasUsePath(selected)!} onClick={() => setSelected(null)}>
                  在画布中使用
                </Link>
              ) : (
                <button className="wr-modal-btn wr-modal-btn-primary" disabled title={selected.installed ? "插件未声明可用 canvasKind" : "插件尚未安装"}>
                  {selected.installed ? "暂不可用于画布" : "未安装"}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </PageChrome>
  );
}
