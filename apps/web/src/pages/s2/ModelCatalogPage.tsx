import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { PageChrome } from "../../components/PageChrome";

// ── Types ──────────────────────────────────────────────────────

type Capability = "chat" | "code" | "vision" | "embedding" | "reasoning" | "function-calling";

export type CatalogModel = {
  id: string;
  name: string;
  provider: string;
  providerSlug: string;
  parameters: string;
  contextWindow: string;
  inputPrice: string;
  outputPrice: string;
  capabilities: Capability[];
  registered: boolean;
};

type ModelFamily = {
  id: string;
  name: string;
  provider: string;
  status: "enabled" | "disabled";
  models: string[];
};

type TabId = "settings" | "enablement" | "registered" | "catalog";

type CatalogFilter = {
  query: string;
  provider: string;
  capability: string;
  priceTier: string;
};

// ── Capability color map ──────────────────────────────────────

export const CAPABILITY_COLORS: Record<Capability, { bg: string; fg: string }> = {
  chat: { bg: "#DBEAFE", fg: "#1D4ED8" },
  code: { bg: "#EDE9FE", fg: "#6D28D9" },
  vision: { bg: "#FCE7F3", fg: "#BE185D" },
  embedding: { bg: "#D1FAE5", fg: "#047857" },
  reasoning: { bg: "#FEF3C7", fg: "#B45309" },
  "function-calling": { bg: "#F1F5F9", fg: "#475569" },
};

// ── Mock catalog data ──────────────────────────────────────────

const CATALOG_MODELS: CatalogModel[] = [
  {
    id: "gpt-5-4-pro",
    name: "GPT-5.4 Pro",
    provider: "OpenAI",
    providerSlug: "openai",
    parameters: "≈1.8T",
    contextWindow: "256K",
    inputPrice: "$10/1M",
    outputPrice: "$30/1M",
    capabilities: ["chat", "vision", "reasoning", "function-calling"],
    registered: true,
  },
  {
    id: "gpt-5-5",
    name: "GPT-5.5",
    provider: "OpenAI",
    providerSlug: "openai",
    parameters: "≈1.8T",
    contextWindow: "256K",
    inputPrice: "$5/1M",
    outputPrice: "$15/1M",
    capabilities: ["chat", "vision", "reasoning", "function-calling"],
    registered: true,
  },
  {
    id: "gpt-5-4-mini",
    name: "GPT-5.4 mini",
    provider: "OpenAI",
    providerSlug: "openai",
    parameters: "≈8B",
    contextWindow: "128K",
    inputPrice: "$0.15/1M",
    outputPrice: "$0.60/1M",
    capabilities: ["chat", "function-calling"],
    registered: true,
  },
  {
    id: "claude-opus-4-7",
    name: "Claude Opus 4.7",
    provider: "Anthropic",
    providerSlug: "anthropic",
    parameters: "≈2T",
    contextWindow: "500K",
    inputPrice: "$15/1M",
    outputPrice: "$75/1M",
    capabilities: ["chat", "vision", "reasoning", "code"],
    registered: true,
  },
  {
    id: "claude-sonnet-4-6",
    name: "Claude Sonnet 4.6",
    provider: "Anthropic",
    providerSlug: "anthropic",
    parameters: "≈400B",
    contextWindow: "200K",
    inputPrice: "$3/1M",
    outputPrice: "$15/1M",
    capabilities: ["chat", "vision", "code"],
    registered: true,
  },
  {
    id: "claude-haiku-4-5",
    name: "Claude Haiku 4.5",
    provider: "Anthropic",
    providerSlug: "anthropic",
    parameters: "≈20B",
    contextWindow: "200K",
    inputPrice: "$0.25/1M",
    outputPrice: "$1.25/1M",
    capabilities: ["chat", "vision"],
    registered: true,
  },
  {
    id: "gemini-2-5-ultra",
    name: "Gemini 2.5 Ultra",
    provider: "Google",
    providerSlug: "google",
    parameters: "≈1.5T",
    contextWindow: "2M",
    inputPrice: "$7/1M",
    outputPrice: "$21/1M",
    capabilities: ["chat", "vision", "reasoning", "code"],
    registered: false,
  },
  {
    id: "gemini-2-5-pro",
    name: "Gemini 2.5 Pro",
    provider: "Google",
    providerSlug: "google",
    parameters: "≈400B",
    contextWindow: "2M",
    inputPrice: "$2.50/1M",
    outputPrice: "$10/1M",
    capabilities: ["chat", "vision", "code"],
    registered: false,
  },
  {
    id: "grok-4-3",
    name: "Grok 4.3",
    provider: "xAI",
    providerSlug: "xai",
    parameters: "≈350B",
    contextWindow: "256K",
    inputPrice: "$5/1M",
    outputPrice: "$15/1M",
    capabilities: ["chat", "reasoning"],
    registered: true,
  },
  {
    id: "deepseek-v3-2",
    name: "DeepSeek V3.2",
    provider: "DeepSeek",
    providerSlug: "deepseek",
    parameters: "≈671B",
    contextWindow: "128K",
    inputPrice: "$0.27/1M",
    outputPrice: "$1.10/1M",
    capabilities: ["chat", "code", "reasoning"],
    registered: false,
  },
  {
    id: "llama-4-maverick-17b",
    name: "Llama 4 Maverick 17B",
    provider: "Meta",
    providerSlug: "meta",
    parameters: "17B",
    contextWindow: "256K",
    inputPrice: "免费",
    outputPrice: "免费",
    capabilities: ["chat", "code"],
    registered: false,
  },
  {
    id: "qwen-3-max",
    name: "Qwen3 Max",
    provider: "Alibaba",
    providerSlug: "alibaba",
    parameters: "≈480B",
    contextWindow: "256K",
    inputPrice: "¥4/1M",
    outputPrice: "¥12/1M",
    capabilities: ["chat", "code", "vision"],
    registered: false,
  },
  {
    id: "text-embedding-3-large",
    name: "Text Embedding 3 Large",
    provider: "OpenAI",
    providerSlug: "openai",
    parameters: "3072d",
    contextWindow: "8K",
    inputPrice: "$0.13/1M",
    outputPrice: "—",
    capabilities: ["embedding"],
    registered: true,
  },
  {
    id: "voyage-3",
    name: "Voyage 3",
    provider: "Voyage AI",
    providerSlug: "voyage",
    parameters: "1024d",
    contextWindow: "32K",
    inputPrice: "$0.12/1M",
    outputPrice: "—",
    capabilities: ["embedding"],
    registered: false,
  },
];

const MODEL_FAMILIES: ModelFamily[] = [
  { id: "openai", name: "OpenAI GPT", provider: "Azure", status: "enabled", models: ["GPT-5.4 Pro", "GPT-5.5", "GPT-5.4 mini"] },
  { id: "anthropic", name: "Anthropic Claude", provider: "AWS Bedrock", status: "enabled", models: ["Claude Opus 4.7", "Claude Sonnet 4.6", "Claude Haiku 4.5"] },
  { id: "xai", name: "xAI Grok", provider: "Palantir Hub", status: "enabled", models: ["Grok 4.3"] },
  { id: "meta", name: "Meta Llama", provider: "Palantir Hub", status: "disabled", models: ["Llama 4 Maverick 17B"] },
  { id: "embedding", name: "Embedding Models", provider: "Azure", status: "enabled", models: ["text-embedding-ada-002", "Text Embedding 3 Large"] },
];

// ── Pure functions (extracted for testing) ────────────────────

export function extractAllProviders(models: CatalogModel[]): string[] {
  const set = new Set<string>();
  for (const m of models) set.add(m.provider);
  return Array.from(set).sort();
}

export function extractAllCapabilities(models: CatalogModel[]): Capability[] {
  const set = new Set<Capability>();
  for (const m of models) for (const c of m.capabilities) set.add(c);
  return Array.from(set).sort();
}

/** Parse a price string like "$10/1M" or "¥4/1M" or "免费" into a numeric per-million value. */
export function parsePricePerMillion(price: string): number {
  if (!price || price === "—" || price === "免费") return 0;
  const m = price.match(/([\d.]+)/);
  return m ? parseFloat(m[1]) : 0;
}

/** Classify a price into tier: free / low / mid / high. */
export function priceTierOf(price: string): "free" | "low" | "mid" | "high" {
  const v = parsePricePerMillion(price);
  if (v === 0) return "free";
  if (v < 1) return "low";
  if (v < 5) return "mid";
  return "high";
}

export function filterCatalogModels(models: CatalogModel[], filter: CatalogFilter): CatalogModel[] {
  const q = filter.query.trim().toLowerCase();
  return models.filter((m) => {
    if (q) {
      const hay = `${m.name} ${m.provider} ${m.id}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    if (filter.provider !== "all" && m.provider !== filter.provider) return false;
    if (filter.capability !== "all" && !m.capabilities.includes(filter.capability as Capability)) return false;
    if (filter.priceTier !== "all") {
      const tier = priceTierOf(m.inputPrice);
      if (tier !== filter.priceTier) return false;
    }
    return true;
  });
}

export function computeCatalogStats(models: CatalogModel[]) {
  const total = models.length;
  const registered = models.filter((m) => m.registered).length;
  const providers = new Set(models.map((m) => m.provider)).size;
  const free = models.filter((m) => priceTierOf(m.inputPrice) === "free").length;
  return { total, registered, providers, free };
}

/** Compare 2-3 models side by side; returns rows of [field, ...values]. */
export function buildComparisonRows(selected: CatalogModel[]) {
  const rows: Array<{ field: string; values: string[] }> = [
    { field: "供应商", values: selected.map((m) => m.provider) },
    { field: "参数量", values: selected.map((m) => m.parameters) },
    { field: "上下文窗口", values: selected.map((m) => m.contextWindow) },
    { field: "输入价格", values: selected.map((m) => m.inputPrice) },
    { field: "输出价格", values: selected.map((m) => m.outputPrice) },
    {
      field: "能力",
      values: selected.map((m) => m.capabilities.join(", ")),
    },
    { field: "已注册", values: selected.map((m) => (m.registered ? "是" : "否")) },
  ];
  return rows;
}

// ── Component ──────────────────────────────────────────────────

export function ModelCatalogPage() {
  const [tab, setTab] = useState<TabId>("catalog");
  const [aipEnabled, setAipEnabled] = useState(true);
  const [orgRestricted, setOrgRestricted] = useState(true);
  const [orgs, setOrgs] = useState<Record<string, boolean>>({
    "组织 Alpha": true,
    "组织 Beta": false,
    "组织 Gamma": false,
    "组织 Delta": false,
    "组织 Epsilon": false,
    "组织 Zeta": false,
  });
  const [orgSearch, setOrgSearch] = useState("");

  // Catalog tab state
  const [catalogFilter, setCatalogFilter] = useState<CatalogFilter>({
    query: "",
    provider: "all",
    capability: "all",
    priceTier: "all",
  });
  const [compareSet, setCompareSet] = useState<Set<string>>(new Set());
  const [showCompare, setShowCompare] = useState(false);
  const [activeLayer, setActiveLayer] = useState<number | null>(null);

  const allProviders = useMemo(() => extractAllProviders(CATALOG_MODELS), []);
  const allCapabilities = useMemo(() => extractAllCapabilities(CATALOG_MODELS), []);
  const filteredModels = useMemo(
    () => filterCatalogModels(CATALOG_MODELS, catalogFilter),
    [catalogFilter],
  );
  const catalogStats = useMemo(() => computeCatalogStats(CATALOG_MODELS), []);
  const compareModels = useMemo(
    () => CATALOG_MODELS.filter((m) => compareSet.has(m.id)),
    [compareSet],
  );

  const filteredOrgs = Object.entries(orgs).filter(([name]) =>
    name.toLowerCase().includes(orgSearch.toLowerCase()),
  );

  function toggleCompare(id: string) {
    setCompareSet((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        if (next.size >= 3) return prev; // max 3
        next.add(id);
      }
      return next;
    });
  }

  return (
    <PageChrome title="模型目录" lede="管理 AIP 启用状态、模型家族和已注册模型">
      <div style={{ maxWidth: "1100px", margin: "0 auto" }}>
        {/* 四层架构示意图（可交互，点击高亮） */}
        <div style={{ background: "#fff", border: "1px solid #E5E7EB", borderRadius: 8, padding: 16, marginBottom: 16 }}>
          <div style={{ fontSize: 11, color: "#6B7280", fontWeight: 600, textTransform: "uppercase", marginBottom: 8 }}>
            模型管理四层架构 · 点击查看详情
          </div>
          <div style={{ display: "flex", alignItems: "stretch", gap: 0 }}>
            {[
              {
                idx: 0,
                label: "L1",
                name: "模型目录",
                desc: "可发现模型清单",
                href: null,
                tone: "blue",
                active: tab === "catalog",
              },
              {
                idx: 1,
                label: "L2",
                name: "模型供应商",
                desc: "凭据 · 连接",
                href: "/aip/model-providers",
                tone: "violet",
              },
              {
                idx: 2,
                label: "L3",
                name: "模型路由",
                desc: "策略 · Fallback · 熔断",
                href: "/aip/model-router",
                tone: "amber",
              },
              {
                idx: 3,
                label: "应用",
                name: "AIP 智能体",
                desc: "选模型 → 推理",
                href: "/aip/agents",
                tone: "green",
              },
            ].map((item, idx, arr) => {
              const isActive = activeLayer === item.idx || (activeLayer === null && item.active);
              const toneColor =
                item.tone === "blue" ? "#2563EB" :
                item.tone === "violet" ? "#7C3AED" :
                item.tone === "amber" ? "#D97706" : "#059669";
              const toneBg =
                item.tone === "blue" ? "#EFF6FF" :
                item.tone === "violet" ? "#F5F3FF" :
                item.tone === "amber" ? "#FFFBEB" : "#F0FDF4";
              return (
                <div key={item.label} style={{ display: "flex", alignItems: "stretch", flex: 1 }}>
                  <button
                    type="button"
                    onClick={() => setActiveLayer(activeLayer === item.idx ? null : item.idx)}
                    style={{
                      flex: 1,
                      textAlign: "center",
                      padding: 14,
                      borderRadius: 8,
                      margin: idx === 0 ? 0 : "0 0 0 4px",
                      background: isActive ? toneBg : "#F9FAFB",
                      border: isActive ? `2px solid ${toneColor}` : "1px solid #E5E7EB",
                      cursor: "pointer",
                      transition: "all 0.15s",
                    }}
                  >
                    <div style={{
                      fontSize: 10,
                      color: isActive ? toneColor : "#9CA3AF",
                      fontWeight: 700,
                      textTransform: "uppercase",
                      marginBottom: 4,
                    }}>{item.label}</div>
                    <div style={{ fontSize: 14, fontWeight: 600, color: isActive ? toneColor : "#374151" }}>{item.name}</div>
                    <div style={{ fontSize: 11, color: "#9CA3AF", marginTop: 2 }}>{item.desc}</div>
                    {item.href && (
                      <Link
                        to={item.href}
                        onClick={(e) => e.stopPropagation()}
                        style={{ display: "inline-block", marginTop: 6, fontSize: 11, color: toneColor, textDecoration: "none" }}
                      >
                        进入 →
                      </Link>
                    )}
                  </button>
                  {idx < arr.length - 1 && (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#D1D5DB" strokeWidth="2" style={{ flexShrink: 0, alignSelf: "center", margin: "0 2px" }}>
                      <path d="M5 12h14M13 6l6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* 统计概览 */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 16 }}>
          {[
            { label: "目录模型总数", value: catalogStats.total, color: "#2563EB" },
            { label: "已注册", value: catalogStats.registered, color: "#059669" },
            { label: "供应商数", value: catalogStats.providers, color: "#7C3AED" },
            { label: "免费模型", value: catalogStats.free, color: "#D97706" },
          ].map((s) => (
            <div key={s.label} style={{ background: "#fff", border: "1px solid #E5E7EB", borderRadius: 8, padding: 14 }}>
              <div style={{ fontSize: 24, fontWeight: 700, color: s.color }}>{s.value}</div>
              <div style={{ fontSize: 12, color: "#6B7280", marginTop: 2 }}>{s.label}</div>
            </div>
          ))}
        </div>

        {/* Tab 导航 */}
        <div style={{ display: "flex", gap: 4, borderBottom: "1px solid #E5E7EB", marginBottom: 16 }}>
          {([
            { id: "catalog", label: `目录浏览 (${catalogStats.total})` },
            { id: "settings", label: "AIP 设置" },
            { id: "enablement", label: "模型启用" },
            { id: "registered", label: `已注册 (${catalogStats.registered})` },
          ] as const).map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              style={{
                padding: "8px 16px",
                fontSize: 13,
                fontWeight: tab === t.id ? 500 : 400,
                borderBottom: tab === t.id ? "2px solid #2563EB" : "2px solid transparent",
                color: tab === t.id ? "#111827" : "#6B7280",
                background: "none",
                border: "none",
                borderTop: "none",
                borderLeft: "none",
                borderRight: "none",
                cursor: "pointer",
              }}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* === Catalog Browse Tab === */}
        {tab === "catalog" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {/* 搜索 + 筛选条 */}
            <div style={{ background: "#fff", border: "1px solid #E5E7EB", borderRadius: 8, padding: 12, display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
              <div style={{ position: "relative", flex: 1, minWidth: 200 }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#9CA3AF" strokeWidth="2" style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)" }}>
                  <circle cx="11" cy="11" r="7" /><path d="M20 20l-3-3" strokeLinecap="round" />
                </svg>
                <input
                  type="search"
                  placeholder="搜索模型名称、供应商..."
                  value={catalogFilter.query}
                  onChange={(e) => setCatalogFilter({ ...catalogFilter, query: e.target.value })}
                  aria-label="catalog-search"
                  style={{ width: "100%", paddingLeft: 34, paddingRight: 12, padding: "8px 12px 8px 34px", fontSize: 13, border: "1px solid #E5E7EB", borderRadius: 6, outline: "none" }}
                />
              </div>
              <select
                value={catalogFilter.provider}
                onChange={(e) => setCatalogFilter({ ...catalogFilter, provider: e.target.value })}
                aria-label="filter-provider"
                style={{ padding: "8px 12px", fontSize: 13, border: "1px solid #E5E7EB", borderRadius: 6, background: "#fff" }}
              >
                <option value="all">所有供应商</option>
                {allProviders.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
              <select
                value={catalogFilter.capability}
                onChange={(e) => setCatalogFilter({ ...catalogFilter, capability: e.target.value })}
                aria-label="filter-capability"
                style={{ padding: "8px 12px", fontSize: 13, border: "1px solid #E5E7EB", borderRadius: 6, background: "#fff" }}
              >
                <option value="all">所有能力</option>
                {allCapabilities.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
              <select
                value={catalogFilter.priceTier}
                onChange={(e) => setCatalogFilter({ ...catalogFilter, priceTier: e.target.value })}
                aria-label="filter-price"
                style={{ padding: "8px 12px", fontSize: 13, border: "1px solid #E5E7EB", borderRadius: 6, background: "#fff" }}
              >
                <option value="all">所有价位</option>
                <option value="free">免费</option>
                <option value="low">低价 (&lt;$1/1M)</option>
                <option value="mid">中价 ($1-$5/1M)</option>
                <option value="high">高价 (&gt;$5/1M)</option>
              </select>
            </div>

            {/* 对比操作条 */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 4px" }}>
              <div style={{ fontSize: 13, color: "#6B7280" }}>
                找到 <strong style={{ color: "#111827" }}>{filteredModels.length}</strong> 个模型
                {compareSet.size > 0 && <> · 已选 <strong style={{ color: "#2563EB" }}>{compareSet.size}</strong>/3 用于对比</>}
              </div>
              {compareSet.size >= 2 && (
                <button
                  type="button"
                  onClick={() => setShowCompare(true)}
                  style={{ padding: "6px 14px", fontSize: 12, fontWeight: 500, border: "none", borderRadius: 6, background: "#2563EB", color: "#fff", cursor: "pointer" }}
                >
                  对比 ({compareSet.size})
                </button>
              )}
            </div>

            {/* 模型卡片网格 */}
            {filteredModels.length === 0 ? (
              <div style={{ background: "#fff", border: "1px solid #E5E7EB", borderRadius: 8, padding: 40, textAlign: "center" }}>
                <p style={{ fontSize: 14, color: "#6B7280", margin: 0 }}>无匹配模型，请调整筛选条件</p>
              </div>
            ) : (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 12 }}>
                {filteredModels.map((m) => {
                  const isSelected = compareSet.has(m.id);
                  const providerInitial = m.provider.charAt(0).toUpperCase();
                  const providerColor =
                    m.providerSlug === "openai" ? "#10A37F" :
                    m.providerSlug === "anthropic" ? "#D97706" :
                    m.providerSlug === "google" ? "#4285F4" :
                    m.providerSlug === "xai" ? "#1D4ED8" :
                    m.providerSlug === "deepseek" ? "#4D6BFE" :
                    m.providerSlug === "meta" ? "#0668E1" :
                    m.providerSlug === "alibaba" ? "#FF6A00" :
                    m.providerSlug === "voyage" ? "#7C3AED" : "#6B7280";
                  return (
                    <div
                      key={m.id}
                      style={{
                        background: "#fff",
                        border: isSelected ? "2px solid #2563EB" : "1px solid #E5E7EB",
                        borderRadius: 8,
                        padding: 14,
                        display: "flex",
                        flexDirection: "column",
                        gap: 10,
                      }}
                    >
                      {/* Header */}
                      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <div style={{
                            width: 32, height: 32, borderRadius: 6, background: providerColor, color: "#fff",
                            display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700, fontSize: 14,
                          }}>
                            {providerInitial}
                          </div>
                          <div>
                            <div style={{ fontSize: 14, fontWeight: 600, color: "#111827" }}>{m.name}</div>
                            <div style={{ fontSize: 11, color: "#9CA3AF" }}>{m.provider}</div>
                          </div>
                        </div>
                        {m.registered && (
                          <span style={{ fontSize: 10, padding: "2px 8px", borderRadius: 10, background: "#D1FAE5", color: "#059669", fontWeight: 500 }}>已注册</span>
                        )}
                      </div>

                      {/* Specs */}
                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, fontSize: 12 }}>
                        <div>
                          <span style={{ color: "#9CA3AF" }}>参数量 </span>
                          <span style={{ fontWeight: 500, color: "#374151" }}>{m.parameters}</span>
                        </div>
                        <div>
                          <span style={{ color: "#9CA3AF" }}>上下文 </span>
                          <span style={{ fontWeight: 500, color: "#374151" }}>{m.contextWindow}</span>
                        </div>
                        <div>
                          <span style={{ color: "#9CA3AF" }}>输入 </span>
                          <span style={{ fontWeight: 500, color: "#374151" }}>{m.inputPrice}</span>
                        </div>
                        <div>
                          <span style={{ color: "#9CA3AF" }}>输出 </span>
                          <span style={{ fontWeight: 500, color: "#374151" }}>{m.outputPrice}</span>
                        </div>
                      </div>

                      {/* Capability tags */}
                      <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                        {m.capabilities.map((cap) => {
                          const c = CAPABILITY_COLORS[cap];
                          return (
                            <span key={cap} style={{
                              fontSize: 10, padding: "2px 8px", borderRadius: 10,
                              background: c.bg, color: c.fg, fontWeight: 500,
                            }}>
                              {cap}
                            </span>
                          );
                        })}
                      </div>

                      {/* Actions */}
                      <div style={{ display: "flex", gap: 6, marginTop: "auto", paddingTop: 8, borderTop: "1px solid #F3F4F6" }}>
                        <label style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 12, color: "#6B7280", cursor: "pointer" }}>
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => toggleCompare(m.id)}
                            disabled={!isSelected && compareSet.size >= 3}
                            style={{ accentColor: "#2563EB" }}
                          />
                          对比
                        </label>
                        {!m.registered ? (
                          <button style={{
                            marginLeft: "auto", padding: "4px 12px", fontSize: 12, fontWeight: 500,
                            border: "none", borderRadius: 6, background: "#2563EB", color: "#fff", cursor: "pointer",
                          }}>
                            注册到供应商
                          </button>
                        ) : (
                          <Link
                            to="/aip/model-router"
                            style={{
                              marginLeft: "auto", padding: "4px 12px", fontSize: 12, fontWeight: 500,
                              border: "1px solid #E5E7EB", borderRadius: 6, background: "#fff", color: "#374151",
                              textDecoration: "none",
                            }}
                          >
                            路由配置 →
                          </Link>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* 对比弹层 */}
            {showCompare && compareModels.length >= 2 && (
              <div style={{
                position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
                background: "rgba(0,0,0,0.4)", zIndex: 50,
                display: "flex", alignItems: "center", justifyContent: "center",
              }} onClick={() => setShowCompare(false)}>
                <div
                  style={{ background: "#fff", borderRadius: 12, padding: 24, maxWidth: 800, width: "90%", maxHeight: "80vh", overflowY: "auto" }}
                  onClick={(e) => e.stopPropagation()}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                    <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>模型对比</h3>
                    <button type="button" onClick={() => setShowCompare(false)} style={{ border: "none", background: "none", fontSize: 20, cursor: "pointer", color: "#6B7280" }}>×</button>
                  </div>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                    <thead>
                      <tr>
                        <th style={{ textAlign: "left", padding: 8, borderBottom: "2px solid #E5E7EB", width: 100, color: "#6B7280", fontSize: 12 }}>属性</th>
                        {compareModels.map((m) => (
                          <th key={m.id} style={{ textAlign: "left", padding: 8, borderBottom: "2px solid #E5E7EB", color: "#111827" }}>
                            {m.name}
                            <div style={{ fontSize: 11, fontWeight: 400, color: "#9CA3AF" }}>{m.provider}</div>
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {buildComparisonRows(compareModels).map((row) => (
                        <tr key={row.field}>
                          <td style={{ padding: 8, borderBottom: "1px solid #F3F4F6", color: "#6B7280", fontSize: 12, fontWeight: 500 }}>{row.field}</td>
                          {row.values.map((v, i) => (
                            <td key={i} style={{ padding: 8, borderBottom: "1px solid #F3F4F6", color: "#374151" }}>{v}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {/* === Settings Tab === */}
        {tab === "settings" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ borderRadius: 8, border: "1px solid #E5E7EB", background: "#fff", overflow: "hidden" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "12px 16px", borderBottom: "1px solid #F3F4F6" }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#7C3AED" strokeWidth="1.5"><circle cx="12" cy="12" r="10" /><path d="M12 16v-4M12 8h.01" strokeLinecap="round" /></svg>
                <h2 style={{ fontSize: 14, fontWeight: 600, color: "#111827", margin: 0 }}>AIP 启用</h2>
              </div>
              <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 20 }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <div style={{ flex: 1 }}>
                    <h3 style={{ fontSize: 14, fontWeight: 500, color: "#111827", margin: 0 }}>启用初始 AIP 功能</h3>
                    <p style={{ fontSize: 12, color: "#6B7280", marginTop: 4, lineHeight: 1.6, margin: "4px 0 0" }}>
                      Palantir AIP 将生成式 AI 与业务运营连接。这些功能和辅助服务利用托管在 Palantir Microsoft Azure 环境中的大语言模型。启用这些功能即表示您同意遵守 Palantir 的 AIP 补充协议。
                    </p>
                  </div>
                  <ToggleSwitch checked={aipEnabled} onChange={setAipEnabled} />
                </div>

                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <div style={{ flex: 1 }}>
                    <h3 style={{ fontSize: 14, fontWeight: 500, color: "#111827", margin: 0 }}>限制 AIP 到指定组织</h3>
                    <p style={{ fontSize: 12, color: "#6B7280", marginTop: 4, lineHeight: 1.6, margin: "4px 0 0" }}>
                      将 AIP 启用限制到特定组织。如果启用此设置，则只有下方选中的组织才能使用 AIP，其他组织将无法使用。
                    </p>
                  </div>
                  <ToggleSwitch checked={orgRestricted} onChange={setOrgRestricted} />
                </div>

                {orgRestricted && (
                  <div style={{ borderTop: "1px solid #F3F4F6", paddingTop: 16 }}>
                    <div style={{ position: "relative", marginBottom: 8 }}>
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#9CA3AF" strokeWidth="2" style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)" }}>
                        <circle cx="11" cy="11" r="7" /><path d="M20 20l-3-3" strokeLinecap="round" />
                      </svg>
                      <input
                        type="search"
                        placeholder="搜索组织..."
                        value={orgSearch}
                        onChange={(e) => setOrgSearch(e.target.value)}
                        style={{ width: "100%", paddingLeft: 36, paddingRight: 16, padding: "8px 16px 8px 36px", fontSize: 13, border: "1px solid #E5E7EB", borderRadius: 8, outline: "none" }}
                      />
                    </div>
                    <div style={{ maxHeight: 160, overflowY: "auto" }}>
                      {filteredOrgs.map(([name, checked]) => (
                        <label key={name} style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 12px", cursor: "pointer", borderRadius: 6, fontSize: 13, color: "#374151" }}>
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => setOrgs((prev) => ({ ...prev, [name]: !prev[name] }))}
                            style={{ accentColor: "#2563EB" }}
                          />
                          {name}
                        </label>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, paddingTop: 16, borderTop: "1px solid #F3F4F6" }}>
              <button style={{ padding: "6px 16px", fontSize: 12, border: "1px solid #E5E7EB", borderRadius: 6, background: "#fff", color: "#374151", cursor: "pointer" }}>取消</button>
              <button style={{ padding: "6px 16px", fontSize: 12, border: "none", borderRadius: 6, background: "#2563EB", color: "#fff", cursor: "pointer" }}>保存到分支</button>
            </div>

            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", fontSize: 12 }}>
              <span style={{ color: "#6B7280", alignSelf: "center" }}>相关:</span>
              <Link to="/aip/model-router" style={{ padding: "6px 12px", borderRadius: 6, border: "1px solid #E5E7EB", color: "#111827", textDecoration: "none" }}>模型路由 →</Link>
              <Link to="/aip/model-providers" style={{ padding: "6px 12px", borderRadius: 6, border: "1px solid #E5E7EB", color: "#111827", textDecoration: "none" }}>模型供应商 →</Link>
            </div>
          </div>
        )}

        {/* === Enablement Tab === */}
        {tab === "enablement" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ background: "#F3F4F6", border: "1px solid #E5E7EB", borderRadius: 8, padding: "12px 16px" }}>
              <p style={{ fontSize: 12, color: "#6B7280", lineHeight: 1.6, margin: 0 }}>
                本页面反映的是从法律角度已启用的模型家族。实际可用的模型可能是这些模型的子集，具体取决于与 Palantir Hub 的连接情况以及地理限制对某些模型可用性的影响。
              </p>
            </div>
            <div style={{ borderRadius: 8, border: "1px solid #E5E7EB", background: "#fff", overflow: "hidden" }}>
              <div style={{ padding: "12px 16px", borderBottom: "1px solid #F3F4F6", fontSize: 14, fontWeight: 600, color: "#111827" }}>
                模型家族 ({MODEL_FAMILIES.length})
              </div>
              {MODEL_FAMILIES.map((f) => (
                <div key={f.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 16px", borderBottom: "1px solid #F3F4F6", fontSize: 13 }}>
                  <div>
                    <div style={{ fontWeight: 500, color: "#111827" }}>{f.name}</div>
                    <div style={{ fontSize: 12, color: "#6B7280" }}>{f.provider}</div>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <span style={{
                      padding: "2px 10px",
                      borderRadius: 12,
                      fontSize: 11,
                      fontWeight: 500,
                      background: f.status === "enabled" ? "#DBEAFE" : "#F3F4F6",
                      color: f.status === "enabled" ? "#1E40AF" : "#6B7280",
                    }}>
                      {f.status === "enabled" ? "已启用" : "未启用"}
                    </span>
                    <button style={{ fontSize: 12, color: "#2563EB", background: "none", border: "none", cursor: "pointer", fontWeight: 500 }}>管理</button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* === Registered Tab === */}
        {tab === "registered" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ borderRadius: 8, border: "1px solid #E5E7EB", background: "#fff", overflow: "hidden" }}>
              <div style={{ padding: "12px 16px", borderBottom: "1px solid #F3F4F6", fontSize: 14, fontWeight: 600, color: "#111827" }}>
                已注册模型 ({MODEL_FAMILIES.filter((f) => f.status === "enabled").flatMap((f) => f.models).length})
              </div>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr>
                    <th style={{ textAlign: "left", padding: "10px 16px", background: "#F9FAFB", borderBottom: "1px solid #E5E7EB", fontWeight: 600, color: "#6B7280", fontSize: 11 }}>模型名称</th>
                    <th style={{ textAlign: "left", padding: "10px 16px", background: "#F9FAFB", borderBottom: "1px solid #E5E7EB", fontWeight: 600, color: "#6B7280", fontSize: 11 }}>供应商</th>
                    <th style={{ textAlign: "left", padding: "10px 16px", background: "#F9FAFB", borderBottom: "1px solid #E5E7EB", fontWeight: 600, color: "#6B7280", fontSize: 11 }}>配额状态</th>
                  </tr>
                </thead>
                <tbody>
                  {MODEL_FAMILIES.filter((f) => f.status === "enabled").flatMap((f) =>
                    f.models.map((m) => ({ model: m, provider: f.provider, family: f.name })),
                  ).map((row) => (
                    <tr key={row.model} style={{ borderBottom: "1px solid #F3F4F6" }}>
                      <td style={{ padding: "10px 16px", fontWeight: 500, color: "#111827" }}>{row.model}</td>
                      <td style={{ padding: "10px 16px", color: "#6B7280", fontSize: 12 }}>{row.provider}</td>
                      <td style={{ padding: "10px 16px" }}>
                        <span style={{ padding: "2px 8px", borderRadius: 12, fontSize: 11, background: "#D1FAE5", color: "#059669" }}>已配额</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </PageChrome>
  );
}

function ToggleSwitch({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      style={{
        width: 48,
        height: 24,
        borderRadius: 12,
        background: checked ? "#2563EB" : "#E5E7EB",
        position: "relative",
        border: "none",
        cursor: "pointer",
        transition: "background 0.15s",
        flexShrink: 0,
      }}
    >
      <div style={{
        position: "absolute",
        top: 2,
        left: checked ? 26 : 2,
        width: 20,
        height: 20,
        borderRadius: "50%",
        background: "#fff",
        transition: "left 0.15s",
        boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
      }} />
    </button>
  );
}
