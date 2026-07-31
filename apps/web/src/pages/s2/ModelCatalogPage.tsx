import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiGet, apiPost } from "../../api/client";
import { PageChrome } from "../../components/PageChrome";
import {
  BpArchitectureBar,
  type BpArchLayerId,
} from "../../components/bp/BpArchitectureBar";

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

export type CatalogSourceMode = "loading" | "live" | "demo";

export type ApiCatalogRow = {
  id?: string;
  provider?: string;
  model?: string;
  displayName?: string;
  capabilities?: string[];
  contextWindow?: number | string;
  inputPrice?: number | string;
  outputPrice?: number | string;
  registered?: boolean;
  registration?: { alias?: string; status?: string } | null;
  parameters?: string;
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

const KNOWN_CAPS = new Set<Capability>([
  "chat", "code", "vision", "embedding", "reasoning", "function-calling",
]);

/** Normalize API capability tokens to UI Capability union. */
export function normalizeCapability(raw: string): Capability | null {
  const s = String(raw || "").trim().toLowerCase().replace(/_/g, "-");
  if (s === "text" || s === "chat") return "chat";
  if (s === "function-calling" || s === "tools") return "function-calling";
  if (KNOWN_CAPS.has(s as Capability)) return s as Capability;
  return null;
}

export function formatContextWindow(n: number | string | undefined): string {
  if (n === undefined || n === null || n === "") return "—";
  if (typeof n === "string" && /[KkMmBb]/.test(n)) return n;
  const v = Number(n);
  if (!Number.isFinite(v) || v <= 0) return "—";
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(v % 1_000_000 === 0 ? 0 : 1)}M`;
  if (v >= 1000) return `${Math.round(v / 1000)}K`;
  return String(v);
}

/**
 * Format API price for UI.
 * Seed 存 $/1K token（如 0.005 → $5/1M）；>=0.1 视为已是 $/1M。
 */
export function formatApiPrice(price: number | string | undefined): string {
  if (price === undefined || price === null || price === "" || price === "—") return "—";
  if (typeof price === "string") {
    if (price.includes("/") || price === "免费") return price;
    const n = parseFloat(price);
    if (!Number.isFinite(n)) return price;
    return formatApiPrice(n);
  }
  if (price === 0) return "免费";
  const perMillion = price < 0.1 ? price * 1000 : price;
  const rounded = perMillion >= 1 ? perMillion.toFixed(2).replace(/\.00$/, "") : perMillion.toFixed(2);
  return `$${rounded}/1M`;
}

export function mapApiCatalogRow(row: ApiCatalogRow): CatalogModel {
  const provider = String(row.provider || "unknown");
  const caps = (row.capabilities || [])
    .map(normalizeCapability)
    .filter((c): c is Capability => c != null);
  return {
    id: String(row.id || row.model || ""),
    name: String(row.displayName || row.model || row.id || "unnamed"),
    provider,
    providerSlug: provider.toLowerCase().replace(/\s+/g, "-"),
    parameters: row.parameters ? String(row.parameters) : "—",
    contextWindow: formatContextWindow(row.contextWindow),
    inputPrice: formatApiPrice(row.inputPrice),
    outputPrice: formatApiPrice(row.outputPrice),
    capabilities: caps.length ? caps : ["chat"],
    registered: Boolean(row.registered ?? row.registration),
  };
}

export function registeredRowsFromModels(models: CatalogModel[]): Array<{ model: string; provider: string; family: string }> {
  return models
    .filter((m) => m.registered)
    .map((m) => ({ model: m.name, provider: m.provider, family: m.provider }));
}

// ── Component ──────────────────────────────────────────────────

export function ModelCatalogPage() {
  const navigate = useNavigate();
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
  const [sourceMode, setSourceMode] = useState<CatalogSourceMode>("loading");
  const [catalogModels, setCatalogModels] = useState<CatalogModel[]>(CATALOG_MODELS);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [registerBusy, setRegisterBusy] = useState<string | null>(null);
  const [registerMsg, setRegisterMsg] = useState<string | null>(null);

  const loadCatalog = useCallback(async () => {
    try {
      let items: ApiCatalogRow[] = [];
      try {
        const admin = await apiGet<{ items?: ApiCatalogRow[] }>("/v1/aip/model-admin/models");
        items = admin.items || [];
      } catch {
        const [cat, reg] = await Promise.all([
          apiGet<{ items?: ApiCatalogRow[] }>("/v1/aip/model-catalog"),
          apiGet<{ items?: Array<{ modelId?: string }> }>("/v1/aip/registered-models").catch(() => ({ items: [] })),
        ]);
        const regSet = new Set((reg.items || []).map((r) => String(r.modelId || "")));
        items = (cat.items || []).map((c) => ({
          ...c,
          registered: regSet.has(String(c.id || "")),
        }));
      }
      setCatalogModels(items.map(mapApiCatalogRow).filter((m) => m.id));
      setSourceMode("live");
      setLoadError(null);
    } catch (e) {
      setCatalogModels(CATALOG_MODELS);
      setSourceMode("demo");
      setLoadError(String((e as Error).message || e));
    }
  }, []);

  useEffect(() => {
    void loadCatalog();
  }, [loadCatalog]);

  const allProviders = useMemo(() => extractAllProviders(catalogModels), [catalogModels]);
  const allCapabilities = useMemo(() => extractAllCapabilities(catalogModels), [catalogModels]);
  const filteredModels = useMemo(
    () => filterCatalogModels(catalogModels, catalogFilter),
    [catalogFilter, catalogModels],
  );
  const catalogStats = useMemo(() => computeCatalogStats(catalogModels), [catalogModels]);
  const compareModels = useMemo(
    () => catalogModels.filter((m) => compareSet.has(m.id)),
    [compareSet, catalogModels],
  );
  const registeredRows = useMemo(() => {
    if (sourceMode === "live") return registeredRowsFromModels(catalogModels);
    return MODEL_FAMILIES.filter((f) => f.status === "enabled").flatMap((f) =>
      f.models.map((m) => ({ model: m, provider: f.provider, family: f.name })),
    );
  }, [sourceMode, catalogModels]);

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

  async function handleRegister(modelId: string) {
    if (sourceMode !== "live") {
      setCatalogModels((prev) =>
        prev.map((m) => (m.id === modelId ? { ...m, registered: true } : m)),
      );
      setRegisterMsg("演示路径：已本地标记为已注册");
      return;
    }
    setRegisterBusy(modelId);
    setRegisterMsg(null);
    try {
      await apiPost(`/v1/aip/model-catalog/${encodeURIComponent(modelId)}/register`, {});
      await loadCatalog();
      setRegisterMsg("注册成功");
    } catch (e) {
      setRegisterMsg(`注册失败：${String((e as Error).message || e)}`);
    } finally {
      setRegisterBusy(null);
    }
  }

  return (
    <PageChrome title="模型目录" lede="管理 AIP 启用状态、模型家族和已注册模型">
      <div className="mc-wrap">
        {sourceMode === "demo" && (
          <div className="w2-a6a7-demo-banner" role="status">
            <span className="w2-a6a7-demo-badge">演示路径</span>
            <span className="w2-a6a7-demo-text">
              模型目录 API 不可用，当前为本地 MOCK{loadError ? ` · ${loadError}` : ""}
            </span>
          </div>
        )}
        {sourceMode === "live" && (
          <div className="w2-a6a7-live-banner" role="status">
            <span className="w2-a6a7-live-badge">Live</span>
            <span className="w2-a6a7-demo-text">目录/已注册已接 `/v1/aip/model-catalog`</span>
          </div>
        )}
        {registerMsg && (
          <div className="w2-a6a7-msg" role="status">{registerMsg}</div>
        )}

        <div className="mc-arch-bar">
          <BpArchitectureBar
            activeLayer="L3"
            onLayerClick={(id: BpArchLayerId) => {
              if (id === "L1") navigate("/aip/model-providers");
              else if (id === "L2") navigate("/aip/model-router");
              else if (id === "AIP") navigate("/aip/studio");
            }}
          />
        </div>

        <div className="mc-stats-grid">
          {[
            { label: "目录模型总数", value: catalogStats.total, color: "var(--aos-accent)" },
            { label: "已注册", value: catalogStats.registered, color: "var(--aos-green-600)" },
            { label: "供应商数", value: catalogStats.providers, color: "var(--aos-purple-600)" },
            { label: "免费模型", value: catalogStats.free, color: "var(--aos-amber-600)" },
          ].map((s) => (
            <div key={s.label} className="mc-stat-card">
              <div className="mc-stat-value" style={{ color: s.color }}>{s.value}</div>
              <div className="mc-stat-label">{s.label}</div>
            </div>
          ))}
        </div>

        <div className="mc-tabs">
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
              className={`mc-tab-btn ${tab === t.id ? "is-active" : ""}`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* === Catalog Browse Tab === */}
        {tab === "catalog" && (
          <div className="mc-catalog-col">
            <div className="mc-filter-bar">
              <div className="mc-search-wrap">
                <svg className="mc-search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="11" cy="11" r="7" /><path d="M20 20l-3-3" strokeLinecap="round" />
                </svg>
                <input
                  type="search"
                  placeholder="搜索模型名称、供应商..."
                  value={catalogFilter.query}
                  onChange={(e) => setCatalogFilter({ ...catalogFilter, query: e.target.value })}
                  aria-label="catalog-search"
                  className="mc-search-input"
                />
              </div>
              <select
                value={catalogFilter.provider}
                onChange={(e) => setCatalogFilter({ ...catalogFilter, provider: e.target.value })}
                aria-label="filter-provider"
                className="mc-filter-select"
              >
                <option value="all">所有供应商</option>
                {allProviders.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
              <select
                value={catalogFilter.capability}
                onChange={(e) => setCatalogFilter({ ...catalogFilter, capability: e.target.value })}
                aria-label="filter-capability"
                className="mc-filter-select"
              >
                <option value="all">所有能力</option>
                {allCapabilities.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
              <select
                value={catalogFilter.priceTier}
                onChange={(e) => setCatalogFilter({ ...catalogFilter, priceTier: e.target.value })}
                aria-label="filter-price"
                className="mc-filter-select"
              >
                <option value="all">所有价位</option>
                <option value="free">免费</option>
                <option value="low">低价 (&lt;$1/1M)</option>
                <option value="mid">中价 ($1-$5/1M)</option>
                <option value="high">高价 (&gt;$5/1M)</option>
              </select>
            </div>

            <div className="mc-compare-bar">
              <div className="mc-compare-info">
                找到 <strong>{filteredModels.length}</strong> 个模型
                {compareSet.size > 0 && <> · 已选 <strong className="accent">{compareSet.size}</strong>/3 用于对比</>}
              </div>
              {compareSet.size >= 2 && (
                <button
                  type="button"
                  onClick={() => setShowCompare(true)}
                  className="mc-compare-btn"
                >
                  对比 ({compareSet.size})
                </button>
              )}
            </div>

            {filteredModels.length === 0 ? (
              <div className="mc-empty">
                <p>无匹配模型，请调整筛选条件</p>
              </div>
            ) : (
              <div className="mc-card-grid">
                {filteredModels.map((m) => {
                  const isSelected = compareSet.has(m.id);
                  const providerInitial = m.provider.charAt(0).toUpperCase();
                  const providerColor =
                    m.providerSlug === "openai" || m.providerSlug.includes("openai") ? "#10A37F" :
                    m.providerSlug.includes("anthropic") ? "#D97706" :
                    m.providerSlug.includes("google") ? "#4285F4" :
                    m.providerSlug.includes("xai") ? "#1D4ED8" :
                    m.providerSlug.includes("deepseek") ? "#4D6BFE" :
                    m.providerSlug.includes("meta") ? "#0668E1" :
                    m.providerSlug.includes("alibaba") ? "#FF6A00" :
                    m.providerSlug.includes("voyage") ? "#7C3AED" : "#6B7280";
                  return (
                    <div
                      key={m.id}
                      className={`mc-model-card ${isSelected ? "is-selected" : ""}`}
                    >
                      <div className="mc-card-header">
                        <div className="mc-card-title-row">
                          <div className="mc-provider-avatar" style={{ background: providerColor }}>
                            {providerInitial}
                          </div>
                          <div>
                            <div className="mc-card-title">{m.name}</div>
                            <div className="mc-card-provider">{m.provider}</div>
                          </div>
                        </div>
                        {m.registered && (
                          <span className="mc-registered-badge">已注册</span>
                        )}
                      </div>

                      <div className="mc-specs-grid">
                        <div>
                          <span className="mc-spec-label">参数量 </span>
                          <span className="mc-spec-value">{m.parameters}</span>
                        </div>
                        <div>
                          <span className="mc-spec-label">上下文 </span>
                          <span className="mc-spec-value">{m.contextWindow}</span>
                        </div>
                        <div>
                          <span className="mc-spec-label">输入 </span>
                          <span className="mc-spec-value">{m.inputPrice}</span>
                        </div>
                        <div>
                          <span className="mc-spec-label">输出 </span>
                          <span className="mc-spec-value">{m.outputPrice}</span>
                        </div>
                      </div>

                      <div className="mc-cap-tags">
                        {m.capabilities.map((cap) => {
                          const c = CAPABILITY_COLORS[cap];
                          return (
                            <span key={cap} className="mc-cap-tag" style={{ background: c.bg, color: c.fg }}>
                              {cap}
                            </span>
                          );
                        })}
                      </div>

                      <div className="mc-card-actions">
                        <label className="mc-compare-label">
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => toggleCompare(m.id)}
                            disabled={!isSelected && compareSet.size >= 3}
                          />
                          对比
                        </label>
                        {!m.registered ? (
                          <button
                            type="button"
                            className="mc-primary-btn"
                            disabled={registerBusy === m.id}
                            onClick={() => void handleRegister(m.id)}
                          >
                            {registerBusy === m.id ? "注册中…" : "注册到供应商"}
                          </button>
                        ) : (
                          <Link
                            to="/aip/model-router"
                            className="mc-secondary-link"
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

            {showCompare && compareModels.length >= 2 && (
              <div className="mc-modal-overlay" onClick={() => setShowCompare(false)}>
                <div
                  className="mc-modal"
                  onClick={(e) => e.stopPropagation()}
                >
                  <div className="mc-modal-header">
                    <h3 className="mc-modal-title">模型对比</h3>
                    <button type="button" onClick={() => setShowCompare(false)} className="mc-modal-close">×</button>
                  </div>
                  <table className="mc-compare-table">
                    <thead>
                      <tr>
                        <th>属性</th>
                        {compareModels.map((m) => (
                          <th key={m.id} className="model-col">
                            {m.name}
                            <div className="model-sub">{m.provider}</div>
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {buildComparisonRows(compareModels).map((row) => (
                        <tr key={row.field}>
                          <td className="field-col">{row.field}</td>
                          {row.values.map((v, i) => (
                            <td key={i}>{v}</td>
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
          <div className="mc-settings-col">
            <div className="mc-panel">
              <div className="mc-panel-header">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="12" cy="12" r="10" /><path d="M12 16v-4M12 8h.01" strokeLinecap="round" /></svg>
                <h2 className="mc-panel-title">AIP 启用</h2>
              </div>
              <div className="mc-panel-body">
                <div className="mc-setting-row">
                  <div className="mc-setting-text">
                    <h3 className="mc-setting-title">启用初始 AIP 功能</h3>
                    <p className="mc-setting-desc">
                      Palantir AIP 将生成式 AI 与业务运营连接。这些功能和辅助服务利用托管在 Palantir Microsoft Azure 环境中的大语言模型。启用这些功能即表示您同意遵守 Palantir 的 AIP 补充协议。
                    </p>
                  </div>
                  <ToggleSwitch checked={aipEnabled} onChange={setAipEnabled} />
                </div>

                <div className="mc-setting-row">
                  <div className="mc-setting-text">
                    <h3 className="mc-setting-title">限制 AIP 到指定组织</h3>
                    <p className="mc-setting-desc">
                      将 AIP 启用限制到特定组织。如果启用此设置，则只有下方选中的组织才能使用 AIP，其他组织将无法使用。
                    </p>
                  </div>
                  <ToggleSwitch checked={orgRestricted} onChange={setOrgRestricted} />
                </div>

                {orgRestricted && (
                  <div className="mc-org-section">
                    <div className="mc-org-search">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <circle cx="11" cy="11" r="7" /><path d="M20 20l-3-3" strokeLinecap="round" />
                      </svg>
                      <input
                        type="search"
                        placeholder="搜索组织..."
                        value={orgSearch}
                        onChange={(e) => setOrgSearch(e.target.value)}
                        className="mc-org-search-input"
                      />
                    </div>
                    <div className="mc-org-list">
                      {filteredOrgs.map(([name, checked]) => (
                        <label key={name} className="mc-org-item">
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => setOrgs((prev) => ({ ...prev, [name]: !prev[name] }))}
                          />
                          {name}
                        </label>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>

            <div className="mc-settings-actions">
              <button className="mc-btn-default">取消</button>
              <button className="mc-btn-primary">保存到分支</button>
            </div>

            <div className="mc-related-links">
              <span className="mc-related-label">相关:</span>
              <Link to="/aip/model-router" className="mc-related-link">模型路由 →</Link>
              <Link to="/aip/model-providers" className="mc-related-link">模型供应商 →</Link>
            </div>
          </div>
        )}

        {/* === Enablement Tab === */}
        {tab === "enablement" && (
          <div className="mc-enablement-col">
            <div className="mc-notice">
              <p>
                本页面反映的是从法律角度已启用的模型家族。实际可用的模型可能是这些模型的子集，具体取决于与 Palantir Hub 的连接情况以及地理限制对某些模型可用性的影响。
              </p>
            </div>
            <div className="mc-family-list">
              <div className="mc-family-header">
                模型家族 ({MODEL_FAMILIES.length})
              </div>
              {MODEL_FAMILIES.map((f) => (
                <div key={f.id} className="mc-family-item">
                  <div>
                    <div className="mc-family-name">{f.name}</div>
                    <div className="mc-family-provider">{f.provider}</div>
                  </div>
                  <div className="mc-family-actions">
                    <span className={`mc-status-badge ${f.status}`}>
                      {f.status === "enabled" ? "已启用" : "未启用"}
                    </span>
                    <button className="mc-manage-btn">管理</button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* === Registered Tab === */}
        {tab === "registered" && (
          <>
          <div className="mc-registered-col">
            <div className="mc-panel">
              <div className="mc-family-header">
                已注册模型 ({registeredRows.length})
              </div>
              <table className="mc-reg-table">
                <thead>
                  <tr>
                    <th>模型名称</th>
                    <th>供应商</th>
                    <th>配额状态</th>
                  </tr>
                </thead>
                <tbody>
                  {registeredRows.length === 0 ? (
                    <tr>
                      <td colSpan={3} className="secondary" style={{ padding: 16 }}>
                        {sourceMode === "live" ? "暂无已注册模型" : "无数据"}
                      </td>
                    </tr>
                  ) : registeredRows.map((row) => (
                    <tr key={`${row.provider}-${row.model}`}>
                      <td className="mc-reg-name">{row.model}</td>
                      <td className="secondary">{row.provider}</td>
                      <td>
                        <span className="mc-quota-badge">已配额</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="mc-notice" style={{ background: "var(--aos-accent-light)", borderColor: "var(--aos-accent-border)" }}>
            <p style={{ color: "var(--aos-text)" }}>
              <strong>自带模型 (BYOM)</strong> — 已注册模型（BYOM）会像 Palantir 提供的模型一样出现在 AIP 各应用的模型选择器中。您可以通过 REST API 源或计算模块来支撑已注册模型。
            </p>
          </div>
          </>
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
        borderRadius: 2,
        background: checked ? "var(--aos-accent)" : "var(--aos-border-strong)",
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
        background: "var(--aos-surface)",
        transition: "left 0.15s",
        boxShadow: "var(--shadow-sm)",
      }} />
    </button>
  );
}
