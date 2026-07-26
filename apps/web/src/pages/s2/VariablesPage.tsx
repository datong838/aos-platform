import { useState, useMemo } from "react";
import { PageChrome } from "../../components/PageChrome";
import { BpToolbar } from "../../components/bp/BpToolbar";

type VarType = "ObjectSet" | "Object" | "String" | "Number" | "Boolean" | "DateRange" | "Array";
type VarScope = "page" | "app" | "global";

type VariableItem = {
  id: string;
  name: string;
  type: VarType;
  scope: VarScope;
  initialValue: string;
  bindings: string[];
  description?: string;
  isSystem?: boolean;
};

/**按类型分组的类别（合并为 5 大组，便于左侧分组导航）*/
export type VarTypeGroup = "data" | "scalar" | "flag" | "time" | "list";

/**将 VarType 映射到 5 大分组（纯函数，便于测试）*/
export function classifyVarType(type: VarType): VarTypeGroup {
  switch (type) {
    case "ObjectSet":
    case "Object":
      return "data";
    case "String":
    case "Number":
      return "scalar";
    case "Boolean":
      return "flag";
    case "DateRange":
      return "time";
    case "Array":
      return "list";
  }
}

export const VAR_TYPE_GROUP_LABELS: Record<VarTypeGroup, string> = {
  data: "数据对象",
  scalar: "标量",
  flag: "布尔",
  time: "时间",
  list: "数组",
};

const VARIABLES: VariableItem[] = [
  { id: "all_orders", name: "all_orders", type: "ObjectSet", scope: "page", initialValue: "Order · 全量查询 (status != archived)", bindings: ["📊 订单表格", "📈 统计卡片"], description: "全部订单对象集" },
  { id: "selected_order", name: "selected_order", type: "Object", scope: "page", initialValue: "← 表格行选中事件写入", bindings: ["📋 详情面板", "🔧 操作按钮组"] },
  { id: "filter_status", name: "filter_status", type: "String", scope: "page", initialValue: '"all"', bindings: ["🔍 筛选下拉", "📊 订单表格"] },
  { id: "date_range", name: "date_range", type: "DateRange", scope: "page", initialValue: "{ start: now-7d, end: now }", bindings: ["📅 日期选择器", "📊 订单表格", "📈 统计卡片"] },
  { id: "search_keyword", name: "search_keyword", type: "String", scope: "page", initialValue: '""', bindings: ["🔍 搜索框"] },
  { id: "is_loading", name: "is_loading", type: "Boolean", scope: "page", initialValue: "false", bindings: ["⏳ 加载遮罩"] },
  { id: "page_num", name: "page_num", type: "Number", scope: "page", initialValue: "1", bindings: ["📄 分页器"] },
  { id: "current_user", name: "current_user", type: "Object", scope: "app", initialValue: "$user · 系统注入", bindings: ["👤 用户头像", "🔒 权限判断"], isSystem: true },
  { id: "app_theme", name: "app_theme", type: "String", scope: "app", initialValue: '"light"', bindings: ["🎨 全局样式"] },
  { id: "notification_count", name: "notification_count", type: "Number", scope: "app", initialValue: "0 · WebSocket 推送", bindings: ["🔔 通知徽章"] },
  { id: "ENV", name: "ENV", type: "String", scope: "global", initialValue: '"production"', bindings: ["🌐 全部页面"], isSystem: true },
  { id: "API_BASE_URL", name: "API_BASE_URL", type: "String", scope: "global", initialValue: '"https://aos-api.internal/v1"', bindings: ["🌐 全部页面"], isSystem: true },
];

const TYPE_LABELS: Record<VarType, string> = {
  ObjectSet: "▢ ObjectSet",
  Object: "● Object",
  String: "Aa String",
  Number: "# Number",
  Boolean: "✓ Boolean",
  DateRange: "📅 DateRange",
  Array: "[] Array",
};

const SCOPE_LABELS: Record<VarScope, string> = {
  page: "页面级",
  app: "应用级",
  global: "全局",
};

const SCOPE_TABS = [
  { id: "all", label: "全部", count: VARIABLES.length },
  { id: "page", label: "页面级", count: VARIABLES.filter((v) => v.scope === "page").length },
  { id: "app", label: "应用级", count: VARIABLES.filter((v) => v.scope === "app").length },
  { id: "global", label: "全局", count: VARIABLES.filter((v) => v.scope === "global").length },
];

function VarTypeIcon({ type }: { type: VarType }) {
  const colors: Record<VarType, string> = {
    ObjectSet: "#60A5FA",
    Object: "#818CF8",
    String: "#34D399",
    Number: "#FBBF24",
    Boolean: "#F472B6",
    DateRange: "#A78BFA",
    Array: "#F87171",
  };
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke={colors[type]} strokeWidth={1.5} style={{ width: 16, height: 16 }}>
      {type === "ObjectSet" && (
        <>
          <rect x="3" y="3" width="7" height="7" rx="1" />
          <rect x="14" y="3" width="7" height="7" rx="1" />
          <rect x="3" y="14" width="7" height="7" rx="1" />
          <rect x="14" y="14" width="7" height="7" rx="1" />
        </>
      )}
      {type === "Object" && (
        <>
          <circle cx="12" cy="12" r="3" />
          <circle cx="12" cy="12" r="9" />
        </>
      )}
      {type === "String" && (
        <path d="M4 7V5a1 1 0 011-1h14a1 1 0 011 1v2M4 7h16M4 7l2 13h12l2-13M9 11v5M15 11v5" strokeLinecap="round" />
      )}
      {type === "Number" && (
        <path d="M12 2v20M2 12h20" strokeLinecap="round" />
      )}
      {type === "Boolean" && (
        <>
          <path d="M9 12l2 2 4-4M12 2a10 10 0 100 20 10 10 0 000-20z" strokeLinecap="round" strokeLinejoin="round" />
        </>
      )}
      {type === "DateRange" && (
        <>
          <rect x="3" y="4" width="18" height="16" rx="1" />
          <path d="M3 9h18M8 4V2M16 4V2" strokeLinecap="round" />
        </>
      )}
      {type === "Array" && (
        <path d="M4 6h16v12H4zM8 10h2v4H8zM14 10h2v4h-2z" strokeLinecap="round" />
      )}
    </svg>
  );
}

export function VariablesPage() {
  const [scope, setScope] = useState<string>("all");
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(VARIABLES[0]?.id ?? null);
  const [typeGroup, setTypeGroup] = useState<VarTypeGroup | "all">("all");

  const filtered = useMemo(() => {
    return VARIABLES.filter((v) => {
      if (scope !== "all" && v.scope !== scope) return false;
      if (typeGroup !== "all" && classifyVarType(v.type) !== typeGroup) return false;
      if (!query.trim()) return true;
      const q = query.toLowerCase();
      return v.name.toLowerCase().includes(q) || v.initialValue.toLowerCase().includes(q);
    });
  }, [scope, query, typeGroup]);

  const selected = useMemo(
    () => VARIABLES.find((v) => v.id === selectedId) ?? filtered[0] ?? null,
    [selectedId, filtered],
  );

  /**5 类型分组的计数（用于左侧分组导航）*/
  const groupCounts = useMemo(() => {
    const counts: Record<VarTypeGroup, number> = { data: 0, scalar: 0, flag: 0, time: 0, list: 0 };
    for (const v of VARIABLES) {
      counts[classifyVarType(v.type)]++;
    }
    return counts;
  }, []);

  const stats = {
    total: VARIABLES.length,
    page: VARIABLES.filter((v) => v.scope === "page").length,
    app: VARIABLES.filter((v) => v.scope === "app").length,
    global: VARIABLES.filter((v) => v.scope === "global").length,
  };

  return (
    <PageChrome title="变量管理器" lede="订单管理 · 集中管理页面级、应用级和全局变量">
      <div className="vr-page">
        <div className="vr-header">
          <div>
            <h1>变量管理器</h1>
            <p>订单管理 · 集中管理页面级、应用级和全局变量</p>
          </div>
        </div>

        <BpToolbar
          search={{ value: query, onChange: setQuery, placeholder: "搜索变量名或初始值…" }}
          count={filtered.length}
        />

        <div className="vr-scope-tabs">
          {SCOPE_TABS.map((tab) => (
            <button
              key={tab.id}
              className={scope === tab.id ? "vr-scope-tab is-active" : "vr-scope-tab"}
              onClick={() => setScope(tab.id)}
            >
              {tab.label}
              <span style={{ marginLeft: 4, opacity: 0.6 }}>({tab.count})</span>
            </button>
          ))}
        </div>

        <div className="grid grid-cols-4 gap-3 mb-5">
          <div className="aos-panel p-3">
            <div className="text-[10px] text-gray-500 mb-1">总变量数</div>
            <div className="text-xl font-semibold text-gray-900">{stats.total}</div>
          </div>
          <div className="aos-panel p-3">
            <div className="text-[10px] text-gray-500 mb-1">页面级</div>
            <div className="text-xl font-semibold" style={{ color: "#2563EB" }}>{stats.page}</div>
          </div>
          <div className="aos-panel p-3">
            <div className="text-[10px] text-gray-500 mb-1">应用级</div>
            <div className="text-xl font-semibold" style={{ color: "#059669" }}>{stats.app}</div>
          </div>
          <div className="aos-panel p-3">
            <div className="text-[10px] text-gray-500 mb-1">全局</div>
            <div className="text-xl font-semibold" style={{ color: "#D97706" }}>{stats.global}</div>
          </div>
        </div>

        <div className="vr-table-wrap">
          <table className="w-full text-xs">
            <thead className="bg-gray-50 text-gray-500 text-left">
              <tr>
                <th className="px-4 py-2.5 w-8"></th>
                <th className="px-4 py-2.5">名称</th>
                <th className="px-4 py-2.5">类型</th>
                <th className="px-4 py-2.5">作用域</th>
                <th className="px-4 py-2.5">初始值 / 数据源</th>
                <th className="px-4 py-2.5">绑定微件</th>
                <th className="px-4 py-2.5">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {filtered.map((v) => (
                <tr key={v.id} className="table-row-hover" style={{ borderLeft: `3px solid ${v.scope === "page" ? "#3B82F6" : v.scope === "app" ? "#10B981" : "#F59E0B"}` }}>
                  <td className="px-4 py-3">
                    <VarTypeIcon type={v.type} />
                  </td>
                  <td className="px-4 py-3 font-mono text-gray-900 font-medium">{v.name}</td>
                  <td className="px-4 py-3">
                    <span className={`vr-type-badge vr-type-${v.type}`}>{TYPE_LABELS[v.type]}</span>
                  </td>
                  <td className="px-4 py-3">
                    <span style={{
                      color: v.scope === "page" ? "#2563EB" : v.scope === "app" ? "#059669" : "#D97706",
                      fontSize: 10,
                      fontWeight: 500,
                    }}>
                      {SCOPE_LABELS[v.scope]}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-600" style={{ fontFamily: "monospace", fontSize: 11 }}>{v.initialValue}</td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {v.bindings.map((b, i) => (
                        <span key={i} style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 4,
                          padding: "2px 8px",
                          borderRadius: 4,
                          fontSize: 10,
                          background: "#F9FAFB",
                          border: "0.5px solid #E5E7EB",
                        }}>
                          {b}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    {v.isSystem ? (
                      <span style={{ color: "#9CA3AF", fontSize: 10 }}>系统变量</span>
                    ) : (
                      <button style={{ color: "#4F46E5", fontSize: 11, textDecoration: "underline", background: "none", border: "none", cursor: "pointer" }}>
                        编辑
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="mt-5 aos-panel p-4">
          <h3 className="text-sm font-medium text-gray-900 mb-3">数据流图</h3>
          <div className="text-[11px] text-gray-600 leading-relaxed">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="px-2 py-1 rounded bg-blue-50 text-blue-700 font-mono font-medium">all_orders</span>
              <span className="text-gray-400">→ 行选中 →</span>
              <span className="px-2 py-1 rounded bg-indigo-50 text-indigo-700 font-mono font-medium">selected_order</span>
              <span className="text-gray-400">→ 读取 →</span>
              <span className="px-2 py-0.5 rounded border border-gray-200 text-gray-600">📋 详情面板</span>
            </div>
            <div className="flex items-center gap-2 flex-wrap mt-2">
              <span className="px-2 py-1 rounded bg-green-50 text-green-700 font-mono font-medium">filter_status</span>
              <span className="text-gray-400">+→</span>
              <span className="px-2 py-1 rounded bg-purple-50 text-purple-700 font-mono font-medium">date_range</span>
              <span className="text-gray-400">+→</span>
              <span className="px-2 py-1 rounded bg-yellow-50 text-yellow-700 font-mono font-medium">search_keyword</span>
              <span className="text-gray-400">→ 联合过滤 →</span>
              <span className="px-2 py-1 rounded bg-blue-50 text-blue-700 font-mono font-medium">all_orders</span>
            </div>
            <div className="mt-3 text-[10px] text-gray-400">
              💡 页面级变量仅当前页面可见；应用级变量跨页面共享；全局变量在所有应用中可用（如环境配置、API 地址）。
            </div>
          </div>
        </div>
      </div>
    </PageChrome>
  );
}
