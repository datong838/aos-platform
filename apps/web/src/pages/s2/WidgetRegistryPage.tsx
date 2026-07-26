import { useState, useMemo, useEffect } from "react";
import { PageChrome } from "../../components/PageChrome";
import { BpToolbar } from "../../components/bp/BpToolbar";
import { apiGet } from "../../api/client";

type WidgetItem = {
  id: string;
  name: string;
  description: string;
  source: "builtin" | "market" | "custom";
  version: string;
  usedBy: number;
  icon: string;
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
function apiItemToWidgetItem(it: {
  id: string;
  name?: string;
  nameZh?: string;
  description?: string;
  version?: string;
  runtime?: string;
  author?: string;
  canvasKind?: string;
}): WidgetItem {
  const runtime = it.runtime || "inproc";
  const author = it.author || "aos";
  const source: WidgetItem["source"] =
    runtime === "stub" ? "custom" : author === "aos" ? "builtin" : "market";
  return {
    id: it.id,
    name: it.nameZh || it.name || it.id,
    description: it.description || "",
    source,
    version: it.version || "0.1.0",
    usedBy: 0,
    icon: KIND_TO_ICON_KEY[it.canvasKind || ""] || "table",
  };
}

const WIDGETS: WidgetItem[] = [
  { id: "table", name: "数据表格", description: "展示 ObjectSet 的行数据，支持排序、筛选、分页、行内编辑", source: "builtin", version: "v3.2.1", usedBy: 8, icon: "table" },
  { id: "chart", name: "趋势图", description: "折线/面积/柱状/组合图，绑定 ObjectType 数值字段和分组维度", source: "builtin", version: "v3.2.1", usedBy: 6, icon: "chart" },
  { id: "form", name: "编辑表单", description: "基于 ObjectType 自动生成字段表单，支持 Action 提交", source: "builtin", version: "v3.1.0", usedBy: 5, icon: "form" },
  { id: "objectset", name: "对象集视图", description: "ObjectSet 的多视图容器（表格/卡片/地图切换），核心交互组件", source: "builtin", version: "v3.2.1", usedBy: 12, icon: "objectset" },
  { id: "navbar", name: "导航栏", description: "顶部/侧边导航，Tab 切换，绑定页面路由", source: "builtin", version: "v3.0.0", usedBy: 10, icon: "navbar" },
  { id: "hero", name: "Hero 区", description: "大标题 + 描述 + 背景图，页面顶部视觉入口", source: "builtin", version: "v3.0.0", usedBy: 4, icon: "hero" },
  { id: "container", name: "容器", description: "嵌套布局容器，支持栅格/堆叠/选项卡排列子组件", source: "builtin", version: "v3.2.1", usedBy: 14, icon: "container" },
  { id: "map", name: "地图", description: "地理可视化，绑定 ObjectType 的经纬度字段，支持标记/热力图/路径", source: "builtin", version: "v2.8.0", usedBy: 3, icon: "map" },
  { id: "timeline", name: "时间线", description: "按时间排序的事件列表，支持双向滚动、筛选节点", source: "builtin", version: "v2.5.0", usedBy: 2, icon: "timeline" },
  { id: "button", name: "按钮", description: "触发 Action 或跳转，支持主/次/文字三种样式", source: "builtin", version: "v3.2.1", usedBy: 15, icon: "button" },
  { id: "stat", name: "统计卡片", description: "KPI 数值展示，支持趋势小图、目标对比", source: "builtin", version: "v3.1.0", usedBy: 7, icon: "stat" },
  { id: "filter", name: "筛选器", description: "多维度筛选面板，输出 ObjectSet Filter 变量", source: "builtin", version: "v3.0.0", usedBy: 9, icon: "filter" },
  { id: "kanban", name: "看板", description: "按状态分列的卡片看板，支持拖拽排序", source: "market", version: "v1.2.0", usedBy: 2, icon: "kanban" },
  { id: "gantt", name: "甘特图", description: "项目时间线可视化，绑定开始/结束时间字段", source: "market", version: "v1.0.0", usedBy: 1, icon: "gantt" },
  { id: "calendar", name: "日历", description: "月/周/日视图，绑定日期字段和事件标题", source: "market", version: "v1.1.0", usedBy: 3, icon: "calendar" },
  { id: "custom-chart", name: "自定义图表", description: "基于 ECharts 的完全自定义图表，支持 JSON 配置", source: "custom", version: "v0.9.0", usedBy: 1, icon: "custom" },
];

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
  const [query, setQuery] = useState("");
  const [widgets, setWidgets] = useState<WidgetItem[]>(WIDGETS);
  const [loading, setLoading] = useState(true);

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
        const items = (res.items || [])
          .filter((it) => it.installed)
          .map(apiItemToWidgetItem);
        if (items.length) {
          setWidgets(items);
        } else {
          setWidgets(WIDGETS);
        }
      } catch {
        if (!cancelled) setWidgets(WIDGETS);
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
    <PageChrome title="组件注册表" lede="画布编辑器中所有可用 Widget 的统一目录">
      <div className="wr-page">
        <div className="wr-header">
          <h1>组件注册表</h1>
          <p>画布编辑器中所有可用 Widget 的统一目录。来源分三类：平台内置 / 市场安装 / 代码开发。安装新组件后画布编辑器自动发现并列出。</p>
        </div>

        <BpToolbar
          search={{ value: query, onChange: setQuery, placeholder: "搜索组件名称或描述…" }}
          count={filtered.length}
        />

        <div className="wr-tabs">
          {sourceTabs.map((tab) => (
            <button
              key={tab.id}
              className={source === tab.id ? "wr-tab is-active" : "wr-tab"}
              onClick={() => setSource(tab.id)}
            >
              {SOURCE_LABELS[tab.id]}
              <span className="wr-tab-count">({tab.count})</span>
            </button>
          ))}
          <span className="wr-tabs-right">
            {loading ? "加载中…" : `已安装 ${widgets.length} 个组件`}
          </span>
        </div>

        <div className="wr-grid">
          {filtered.map((w) => (
            <div key={w.id} className="wr-card">
              <div className="wr-card-top">
                <div className="wr-icon">
                  <WidgetIcon name={w.icon} />
                </div>
                <span className={`wr-source-tag ${w.source}`}>
                  {w.source === "builtin" ? "内置" : w.source === "market" ? "市场" : "自定义"}
                </span>
              </div>
              <h3>{w.name}</h3>
              <p className="wr-card-desc">{w.description}</p>
              <div className="wr-card-meta">
                <span>{w.version}</span>
                <span>·</span>
                <span>被 {w.usedBy} 个应用使用</span>
              </div>
            </div>
          ))}
          {!loading && filtered.length === 0 && (
            <div style={{ gridColumn: "1 / -1", opacity: 0.6, padding: "16px", fontSize: "13px" }}>
              没有匹配的组件
            </div>
          )}
        </div>
      </div>
    </PageChrome>
  );
}
