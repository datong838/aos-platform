import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiGet, apiPost } from "../api/client";
import { PageChrome } from "../components/PageChrome";
import { BpCard } from "../components/bp/BpCard";
import { BpEmpty } from "../components/bp/BpEmpty";
import { BpToolbar } from "../components/bp/BpToolbar";

type ModuleItem = {
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
};

const CATEGORY_ALL = "全部";

const CATEGORY_TONE: Record<string, "blue" | "amber" | "neutral" | "green"> = {
  运营: "blue",
  业务应用: "blue",
  风控: "amber",
  "风控 Inbox": "amber",
  本体前端: "neutral",
  "AI 助手": "amber",
  智能嵌入: "amber",
  态势感知: "blue",
  分析: "blue",
  应用构建: "green",
  系统集成: "neutral",
  态势大屏: "blue",
  发布管理: "blue",
  自动化: "blue",
};

export function WorkshopListPage() {
  const [items, setItems] = useState<ModuleItem[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>(CATEGORY_ALL);
  const [query, setQuery] = useState("");

  useEffect(() => {
    apiGet<{ items: ModuleItem[] }>("/v1/modules")
      .then((j) => setItems(j.items))
      .catch((e) => setErr(String(e.message || e)));
  }, []);

  async function handleTouch(moduleId: string) {
    try {
      await apiPost(`/v1/modules/${moduleId}/touch`, {});
      const j = await apiGet<{ items: ModuleItem[] }>("/v1/modules");
      setItems(j.items);
    } catch {
    }
  }

  const sortedItems = useMemo(() => {
    return [...items].sort((a, b) => {
      const aTime = a.lastOpenedAt ? new Date(a.lastOpenedAt).getTime() : 0;
      const bTime = b.lastOpenedAt ? new Date(b.lastOpenedAt).getTime() : 0;
      return bTime - aTime;
    });
  }, [items]);

  const recentlyUsed = sortedItems.slice(0, 3);

  const categories = useMemo(() => {
    const set = new Set<string>();
    items.forEach((m) => {
      if (m.category) set.add(m.category);
    });
    return [CATEGORY_ALL, ...Array.from(set)];
  }, [items]);

  const filteredItems = useMemo(() => {
    const q = query.trim().toLowerCase();
    return sortedItems.filter((m) => {
      if (filter !== CATEGORY_ALL && m.category !== filter) return false;
      if (!q) return true;
      const name = m.name.toLowerCase();
      const desc = (m.description ?? "").toLowerCase();
      return name.includes(q) || desc.includes(q);
    });
  }, [sortedItems, filter, query]);

  const getEntryPath = (m: ModuleItem) => {
    if (m.id === "mod-order-management") return "/workshop/orders";
    if (m.id === "mod-ops-inbox") return "/workshop/inbox";
    if (m.id === "mod-cop-dashboard") return "/workshop/cop";
    if (m.id === "mod-buddy-assist") return "/workshop/buddy";
    return m.entryPath || "/workshop/inbox";
  };

  const renderModuleCard = (m: ModuleItem, showBothLinks = false) => {
    const entryPath = getEntryPath(m);
    const tone = CATEGORY_TONE[m.category ?? "运营"] ?? "blue";
    const toneCls = `wl-cat-label ${tone}`;
    return (
      <div key={m.id} className="aos-module-card group" style={{ cursor: "default" }}>
        <Link to={entryPath} className="block" onClick={() => void handleTouch(m.id)}>
          <div style={{ marginBottom: 6 }}>
            <span className={toneCls}>{m.category || "业务应用"}</span>
          </div>
          <div className="text-gray-900 font-medium text-[13px] group-hover:text-[var(--aos-accent)] transition-colors">
            {m.name}
          </div>
          <p className="text-[11px] text-gray-500 mt-1.5">{m.description || "—"}</p>
        </Link>
        <div className="mt-2 flex gap-2 text-[10px]">
          {showBothLinks && (
            <>
              <Link
                to={entryPath}
                className="text-[var(--aos-accent)] hover:underline"
                onClick={() => void handleTouch(m.id)}
              >
                ▶ 打开运行态
              </Link>
              <span className="text-gray-400">·</span>
            </>
          )}
          <Link to="/workshop/canvas" className="text-[var(--aos-accent)] hover:underline">
            ✏ 编辑画布 →
          </Link>
        </div>
      </div>
    );
  };

  return (
    <PageChrome title="工作台 · 应用列表" lede="按业务场景打开模块">
      <div className="max-w-[1100px] mx-auto space-y-6 py-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-[13px] font-medium text-gray-900 tracking-tight leading-snug">应用列表</h1>
            <p className="mt-1.5 text-gray-600 text-[13px] leading-relaxed">
              按业务场景打开模块。风险告警管理、对象探索、智能助手等都是从这里打开的模块，不是并列产品。
            </p>
          </div>
          <Link
            to="/workshop/create"
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-[13px] font-medium text-white transition-colors"
            style={{ background: "var(--aos-accent)" }}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path d="M12 5v14M5 12h14" strokeLinecap="round" />
            </svg>
            新建 Module
          </Link>
        </div>

        {err && <p className="error">{err}</p>}

        <BpToolbar
          search={{ value: query, onChange: setQuery, placeholder: "搜索应用名称或描述…" }}
          count={filteredItems.length}
        />

        <BpCard
          title="最近使用"
          subtitle="按打开时间排序"
          padding="md"
        >
          {recentlyUsed.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {recentlyUsed.map((m) => renderModuleCard(m, true))}
            </div>
          ) : (
            <BpEmpty title="暂无最近使用的模块" description="打开任意模块后会出现在这里" />
          )}
        </BpCard>

        <BpCard
          title="全部应用"
          actions={
            <div className="flex gap-1 items-center">
              {categories.map((cat) => (
                <button
                  key={cat}
                  type="button"
                  className={filter === cat ? "wl-cat-btn is-active" : "wl-cat-btn"}
                  onClick={() => setFilter(cat)}
                  aria-pressed={filter === cat}
                >
                  {cat}
                </button>
              ))}
              <span className="text-[11px] text-gray-400 ml-2">{filteredItems.length} / {items.length}</span>
            </div>
          }
          padding="md"
        >
          {filteredItems.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {filteredItems.map((m) => renderModuleCard(m))}
            </div>
          ) : (
            <BpEmpty
              title={items.length === 0 ? "暂无应用" : "无匹配结果"}
              description={
                items.length === 0
                  ? "点「新建 Module」开始创建第一个应用"
                  : "尝试调整搜索关键词或筛选条件"
              }
              action={
                items.length === 0 ? (
                  <Link to="/workshop/create" className="btn">新建 Module</Link>
                ) : undefined
              }
            />
          )}
        </BpCard>
      </div>
    </PageChrome>
  );
}
