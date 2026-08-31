import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiGet, apiPost } from "../../api/client";
import { aipModelRuntime, type ExactRuntimeRef, type ModelPriceAuthoritySummary } from "../../api/aipModelRuntime";
import { aipFeatureActivation, type AipFeatureActivationList } from "../../api/aipFeatureActivation";
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
  providerModelId?: string;
  priceAuthorityStatus?: ModelPriceAuthoritySummary["status"];
  description?: string;
  status?: string;
  inputModalities?: string[];
  outputModalities?: string[];
  usageBasis?: string;
  limitations?: string[];
  runtimeModelRef?: ExactRuntimeRef;
  providerRef?: ExactRuntimeRef;
  routeRefs?: ExactRuntimeRef[];
  evalGateRef?: ExactRuntimeRef;
  healthLabel?: string;
  healthExpiresAt?: string;
  capacityPoolCount?: number;
};

type TabId = "settings" | "enablement" | "registered" | "catalog";

type CatalogFilter = {
  query: string;
  provider: string;
  capability: string;
  priceTier: string;
};

export type CatalogSourceMode = "loading" | "live" | "error";

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
  description?: string;
  status?: string;
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

const CAPABILITY_LABELS: Record<Capability, string> = {
  chat: "对话生成",
  code: "代码生成",
  vision: "图像理解",
  embedding: "语义向量",
  reasoning: "复杂推理",
  "function-calling": "工具调用",
};

const BUSINESS_TOKEN_LABELS: Record<string, string> = {
  internal: "内部开发环境使用",
  development_only: "仅开发环境使用",
  tool_execution: "工具执行",
  structured_output: "结构化输出",
  image: "图像",
  audio: "音频",
  video: "视频",
  text: "文本",
  chat: "对话",
  llm: "大语言模型",
  priced: "计价已确认",
  approved_zero: "零价已审批",
  unit_mismatch: "计价单位不匹配",
  unknown: "尚无可验证计价结论",
};

export function businessTokenLabel(value: string): string {
  const normalized = String(value || "").trim().toLowerCase();
  if (normalized.includes("aos self-developed adapter") && normalized.includes("development pilot and demo only")) {
    return "AOS 自研适配器；仅限已授权的开发试点与演示";
  }
  return BUSINESS_TOKEN_LABELS[normalized] || value || "未声明";
}

export function featureActivationImpactPreview(
  current: AipFeatureActivationList["items"][number] | undefined,
  featureId: string,
) {
  const revision = current?.revision || 0;
  return {
    nextRevision: revision + 1,
    summary: current
      ? `${featureId} 将从 v${revision} 续期为 v${revision + 1}`
      : `${featureId || "待填写功能"} 将创建 v1 授权`,
    boundary: "仅变更当前租户的功能授权；不安装 Provider、不切换路由、不触发模型调用",
  };
}

// ── Mock catalog data ──────────────────────────────────────────

export const CATALOG_MODELS: CatalogModel[] = [
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
  if (!price || price === "—" || price.includes("未知") || price.includes("待补")) return Number.NaN;
  if (price === "免费" || price.includes("审批免费")) return 0;
  const m = price.match(/([\d.]+)/);
  return m ? parseFloat(m[1]) : 0;
}

/** Classify a price into tier: free / low / mid / high. */
export function priceTierOf(price: string): "unknown" | "free" | "low" | "mid" | "high" {
  const v = parsePricePerMillion(price);
  if (!Number.isFinite(v)) return "unknown";
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
    providerModelId: String(row.model || row.id || ""),
    description: String(row.description || ""),
    status: String(row.status || "unknown"),
  };
}

export function applyPriceAuthority(
  models: CatalogModel[],
  authorities: ModelPriceAuthoritySummary[],
): CatalogModel[] {
  const byProviderModel = new Map(authorities.map((item) => [item.providerModelId, item]));
  const format = (amount: number | null, item: ModelPriceAuthoritySummary) => {
    if (item.status === "approved_zero") return "已审批免费";
    if (item.status === "unit_mismatch") return "计价单位待补";
    if (item.status !== "priced" || amount === null || !item.currency || !item.tokenUnit) return "价格未知";
    const symbol = item.currency === "CNY" ? "¥" : `${item.currency} `;
    return `${symbol}${amount}/${item.tokenUnit} token`;
  };
  return models.map((model) => {
    const authority = byProviderModel.get(model.providerModelId || "");
    if (!authority) return model.registered ? { ...model, inputPrice: "价格未知", outputPrice: "价格未知", priceAuthorityStatus: "unknown" } : model;
    return {
      ...model,
      inputPrice: format(authority.inputTokenPrice, authority),
      outputPrice: format(authority.outputTokenPrice, authority),
      priceAuthorityStatus: authority.status,
    };
  });
}

export function registeredRowsFromModels(models: CatalogModel[]): Array<{ model: string; provider: string; family: string }> {
  return models
    .filter((m) => m.registered)
    .map((m) => ({ model: m.name, provider: m.provider, family: m.provider }));
}

export function validateRegistrationResponse(
  response: { ok?: boolean; item?: { modelId?: string } } | null | undefined,
  modelId: string,
): boolean {
  return response?.ok === true && response.item?.modelId === modelId;
}

// ── Component ──────────────────────────────────────────────────

export function ModelCatalogPage() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<TabId>("catalog");
  const [activation, setActivation] = useState<AipFeatureActivationList | null>(null);
  const [activationError, setActivationError] = useState<string | null>(null);
  const [activationBusy, setActivationBusy] = useState<string | null>(null);
  const [activationMessage, setActivationMessage] = useState<string | null>(null);
  const [featureId, setFeatureId] = useState("aip.analysis");
  const [featureHash, setFeatureHash] = useState("");
  const [featureExpiry, setFeatureExpiry] = useState("");

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
  const [catalogModels, setCatalogModels] = useState<CatalogModel[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [registerBusy, setRegisterBusy] = useState<string | null>(null);
  const [registerMsg, setRegisterMsg] = useState<string | null>(null);
  const [expandedModel, setExpandedModel] = useState<string | null>(null);

  const loadCatalog = useCallback(async () => {
    try {
      let items: ApiCatalogRow[] = [];
      let loaded = false;
      try {
        const admin = await apiGet<{ items?: ApiCatalogRow[] }>("/v1/aip/model-admin/models");
        if ((admin.items || []).length > 0) {
          items = admin.items || [];
          loaded = true;
        }
      } catch {
        /* fall through to Phase-2 catalog */
      }
      if (!loaded) {
        const [cat, reg] = await Promise.all([
          apiGet<{ items?: ApiCatalogRow[] }>("/v1/aip/model-catalog"),
          apiGet<{ items?: Array<{ modelId?: string }> }>("/v1/aip/registered-models"),
        ]);
        const regSet = new Set((reg.items || []).map((r) => String(r.modelId || "")));
        items = (cat.items || []).map((c) => ({
          ...c,
          registered: regSet.has(String(c.id || "")),
        }));
      }
      const [cost, overview] = await Promise.all([aipModelRuntime.costOverview(), aipModelRuntime.overview()]);
      const runtimeModels = await Promise.all(overview.models.map((item) => aipModelRuntime.model(item.ref.assetId, item.ref.revision)));
      const providers = await Promise.all(overview.providers.map((item) => aipModelRuntime.provider(item.ref.assetId)));
      const plugins = await Promise.all(providers.map((item) => aipModelRuntime.providerPlugin(item.pluginRef.assetId, item.pluginRef.revision)));
      const enriched = items.map(mapApiCatalogRow).filter((model) => model.id).map((model) => {
        const runtimeModel = runtimeModels.find((item) => item.providerModelId === model.providerModelId);
        if (!runtimeModel) return model;
        const provider = providers.find((item) => item.providerInstanceId === runtimeModel.provider.assetId);
        const plugin = provider ? plugins.find((item) => item.providerPluginId === provider.pluginRef.assetId && item.revision === provider.pluginRef.revision) : undefined;
        const routes = overview.routes.filter((item) => item.dependencyRefs.some((ref) => ref.assetType === "RegisteredModelRevision" && ref.assetId === runtimeModel.registeredModelId));
        const health = overview.healthObservations.find((item) => item.provider.assetId === runtimeModel.provider.assetId && item.provider.revision === runtimeModel.provider.revision && item.provider.contentHash === runtimeModel.provider.contentHash);
        const price = cost.modelPrices.find((item) => item.providerModelId === runtimeModel.providerModelId);
        const limitations = [
          ...(plugin?.deniedCapabilities || []).map((item) => `禁止能力：${businessTokenLabel(item)}`),
          ...(price && price.status !== "priced" && price.status !== "approved_zero" ? [`计价权威：${businessTokenLabel(price.status)}`] : []),
          ...(!health || Date.parse(health.expiresAt) <= Date.now() ? ["当前 Health 缺失或已过期，运行必须失败关闭"] : []),
        ];
        return {
          ...model,
          parameters: "供应商未披露",
          contextWindow: formatContextWindow(runtimeModel.contextWindow),
          capabilities: runtimeModel.capabilities.map(normalizeCapability).filter((item): item is Capability => item != null),
          inputModalities: runtimeModel.inputModalities,
          outputModalities: runtimeModel.outputModalities,
          usageBasis: businessTokenLabel(plugin?.usageBasis || ""),
          limitations,
          runtimeModelRef: { assetType: "RegisteredModelRevision", assetId: runtimeModel.registeredModelId, revision: runtimeModel.revision, contentHash: runtimeModel.contentHash },
          providerRef: runtimeModel.provider,
          routeRefs: routes.map((item) => item.ref),
          evalGateRef: runtimeModel.evalGateRef,
          healthLabel: health ? (Date.parse(health.expiresAt) > Date.now() ? health.status : "已过期") : "缺失",
          healthExpiresAt: health?.expiresAt,
          capacityPoolCount: overview.capacityPools.filter((item) => item.modelRef.assetId === runtimeModel.registeredModelId && item.modelRef.revision === runtimeModel.revision && item.modelRef.contentHash === runtimeModel.contentHash).length,
        };
      });
      setCatalogModels(applyPriceAuthority(enriched, cost.modelPrices));
      setSourceMode("live");
      setLoadError(null);
    } catch (e) {
      setCatalogModels([]);
      setSourceMode("error");
      setLoadError(String((e as Error).message || e));
    }
  }, []);

  useEffect(() => {
    void loadCatalog();
  }, [loadCatalog]);

  const loadActivations = useCallback(async () => {
    try {
      setActivation(await aipFeatureActivation.list());
      setActivationError(null);
    } catch (error) {
      setActivation(null);
      setActivationError(String((error as Error).message || error));
    }
  }, []);

  useEffect(() => { void loadActivations(); }, [loadActivations]);

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
    return [];
  }, [sourceMode, catalogModels]);

  const providerFamilies = useMemo(() => Array.from(new Set(catalogModels.map((model) => model.provider))).map((provider) => ({
    provider,
    models: catalogModels.filter((model) => model.provider === provider),
  })), [catalogModels]);
  const activationPreview = useMemo(() => featureActivationImpactPreview(
    activation?.items.find((item) => item.featureId === featureId),
    featureId,
  ), [activation, featureId]);

  async function handleActivateFeature() {
    const current = activation?.items.find((item) => item.featureId === featureId);
    if (!/^aip\.[a-z0-9]+(?:[.-][a-z0-9]+)*$/.test(featureId) || !/^sha256:[0-9a-f]{64}$/.test(featureHash) || !featureExpiry) {
      setActivationMessage("请填写合法功能标识、已评审内容哈希和到期时间");
      return;
    }
    setActivationBusy(featureId);
    setActivationMessage(null);
    try {
      const response = await aipFeatureActivation.activate({ featureId, expectedRevision: current?.revision || 0, contentHash: featureHash, expiresAt: new Date(featureExpiry).toISOString() }, crypto.randomUUID());
      await loadActivations();
      setActivationMessage(`功能授权已保存并重读 · v${response.receipt.revision} · Receipt ${response.receipt.receiptId}`);
    } catch (error) {
      setActivationMessage(`保存失败：${String((error as Error).message || error)}`);
    } finally {
      setActivationBusy(null);
    }
  }

  async function handleRevokeFeature(targetFeatureId: string, revision: number) {
    setActivationBusy(targetFeatureId);
    setActivationMessage(null);
    try {
      const response = await aipFeatureActivation.revoke({ featureId: targetFeatureId, expectedRevision: revision }, crypto.randomUUID());
      await loadActivations();
      setActivationMessage(`功能授权已撤销并重读 · Receipt ${response.receipt.receiptId}`);
    } catch (error) {
      setActivationMessage(`撤销失败：${String((error as Error).message || error)}`);
    } finally {
      setActivationBusy(null);
    }
  }

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
    if (sourceMode !== "live") return;
    setRegisterBusy(modelId);
    setRegisterMsg(null);
    try {
      const written = await apiPost<{ ok?: boolean; item?: { modelId?: string } }>(`/v1/aip/model-catalog/${encodeURIComponent(modelId)}/register`, {});
      if (!validateRegistrationResponse(written, modelId)) throw new Error("注册响应 ok/modelId 与目标不一致");
      let registered: { items?: Array<{ modelId?: string }> };
      try {
        registered = await apiGet<{ items?: Array<{ modelId?: string }> }>("/v1/aip/registered-models");
      } catch (e) {
        setRegisterMsg(`注册写入已提交但重读核验失败：${String((e as Error).message || e)}`);
        return;
      }
      if (!(registered.items || []).some((item) => item.modelId === modelId)) {
        setRegisterMsg("注册写入已提交但重读核验失败：已注册列表缺少目标模型");
        return;
      }
      setCatalogModels((prev) => prev.map((model) => model.id === modelId ? { ...model, registered: true } : model));
      setRegisterMsg("模型已注册并完成重读核验");
    } catch (e) {
      setRegisterMsg(`注册失败：${String((e as Error).message || e)}`);
    } finally {
      setRegisterBusy(null);
    }
  }

  return (
    <PageChrome title="模型目录" lede="浏览、筛选并注册当前组织可用的真实模型；读取失败时不回落本地演示目录。">
      <div className="mc-wrap">
        {sourceMode === "error" && (
          <div className="w2-a6a7-demo-banner" role="alert">
            <span className="w2-a6a7-demo-badge">不可用</span>
            <span className="w2-a6a7-demo-text">
              模型目录读取失败，已停止展示本地模拟数据{loadError ? ` · ${loadError}` : ""}
            </span>
          </div>
        )}
        {sourceMode === "live" && (
          <div className="w2-a6a7-live-banner" role="status">
            <span className="w2-a6a7-live-badge">真实数据</span>
            <span className="w2-a6a7-demo-text">模型目录和已注册列表均来自当前组织的权威服务</span>
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
            { label: "当前筛选", value: filteredModels.length, color: "var(--aos-amber-600)" },
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
            { id: "settings", label: "平台设置" },
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
                {allCapabilities.map((c) => <option key={c} value={c}>{CAPABILITY_LABELS[c]}</option>)}
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
                <option value="unknown">价格未知/单位待补</option>
              </select>
              <span className="notice" style={{ padding: "6px 10px" }} role="status">
                筛选命中 {filteredModels.length} / {catalogStats.total}
              </span>
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
                              {CAPABILITY_LABELS[cap]}
                            </span>
                          );
                        })}
                      </div>

                      <div className="muted" style={{ marginTop: 10 }}>
                        输入模态：{m.inputModalities?.map(businessTokenLabel).join("、") || "未声明"} · 输出模态：{m.outputModalities?.map(businessTokenLabel).join("、") || "未声明"} · 使用许可：{m.usageBasis || "未声明"}
                      </div>

                      <div className="mc-card-actions">
                        <label className="mc-compare-label">
                          <input
                            type="checkbox"
                            aria-label={`将 ${m.name} 加入模型对比`}
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
                            disabled={sourceMode !== "live" || registerBusy === m.id}
                            title={sourceMode !== "live" ? "演示目录不可注册" : undefined}
                            onClick={() => void handleRegister(m.id)}
                          >
                            {registerBusy === m.id ? "注册中…" : "注册到供应商"}
                          </button>
                        ) : (
                          <button type="button" className="mc-secondary-link" onClick={() => setExpandedModel(expandedModel === m.id ? null : m.id)}>
                            {expandedModel === m.id ? "收起运行关系" : "查看运行关系"}
                          </button>
                        )}
                      </div>
                      {expandedModel === m.id ? <div className="notice" style={{ marginTop: 12 }} role="region" aria-label={`${m.name} 运行关系`}>
                        <strong>运行关系与边界</strong>
                        <p>{m.description || "当前目录未提供业务描述"}</p>
                        <p>目录状态：{m.status || "未知"} · 模型版本：{m.runtimeModelRef ? `${m.runtimeModelRef.assetId}@${m.runtimeModelRef.revision}` : "未发布"}</p>
                        <p>Provider：{m.providerRef?.assetId || "未绑定"} · Route：{m.routeRefs?.map((item) => `${item.assetId}@${item.revision}`).join("、") || "未绑定"}</p>
                        <p>Eval：{m.evalGateRef ? `${m.evalGateRef.assetId}@${m.evalGateRef.revision}` : "未绑定"} · Health：{m.healthLabel || "未知"}{m.healthExpiresAt ? `（截止 ${new Date(m.healthExpiresAt).toLocaleString("zh-CN")}）` : ""} · Capacity：{m.capacityPoolCount ?? 0} 个 exact 池</p>
                        <p>限制：{m.limitations?.join("；") || "当前权威未声明额外限制"}</p>
                        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                          {m.providerRef ? <Link className="btn btn-nav" to={`/aip/model-providers/${encodeURIComponent(m.providerRef.assetId)}`}>供应商权威</Link> : null}
                          <Link className="btn btn-nav" to="/aip/model-router">路由与策略</Link>
                          <Link className="btn btn-nav" to="/aip/evals">评测门控</Link>
                          <Link className="btn btn-nav" to="/aip/capacity">容量与用量</Link>
                          <Link className="btn btn-nav" to={`/aip/agents?modelId=${encodeURIComponent(m.runtimeModelRef?.assetId || m.id)}`}>消费数字同事</Link>
                        </div>
                      </div> : null}
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
                    <button type="button" aria-label="关闭模型对比" onClick={() => setShowCompare(false)} className="mc-modal-close">×</button>
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
                <h2 className="mc-panel-title">当前租户 AIP 功能授权</h2>
              </div>
              <div className="mc-panel-body">
                <p className="mc-setting-desc">
                  {activation ? `组织 ${activation.tenant.orgId} · 工作区 ${activation.tenant.projectId} · ${activation.items.filter((item) => item.status === "active" && (!item.expiresAt || Date.parse(item.expiresAt) > Date.now())).length} 项有效授权` : "正在读取当前租户的功能授权"}
                </p>
                {activationError && <div className="w2-a6a7-demo-banner" role="alert">功能授权读取失败 · {activationError}</div>}
                <div className="mc-family-list">
                  {(activation?.items || []).length === 0 && !activationError ? <div className="mc-empty"><p>当前租户尚无 AIP 功能授权</p></div> : null}
                  {(activation?.items || []).map((item) => {
                    const active = item.status === "active" && (!item.expiresAt || Date.parse(item.expiresAt) > Date.now());
                    return <div key={item.featureId} className="mc-family-item">
                      <div><div className="mc-family-name">{item.featureId}</div><div className="mc-family-provider">版本 {item.revision} · {item.expiresAt ? `有效至 ${new Date(item.expiresAt).toLocaleString("zh-CN")}` : "无到期时间"}</div></div>
                      <div className="mc-family-actions"><span className={`mc-status-badge ${active ? "enabled" : "disabled"}`}>{active ? "已授权" : item.status === "revoked" ? "已撤销" : "已过期"}</span>{active && <button type="button" className="mc-manage-btn" disabled={activationBusy === item.featureId} onClick={() => void handleRevokeFeature(item.featureId, item.revision)}>{activationBusy === item.featureId ? "处理中…" : "撤销授权"}</button>}</div>
                    </div>;
                  })}
                </div>
                <details style={{ marginTop: 16 }}>
                  <summary>新增或续期功能授权</summary>
                  <p className="mc-setting-desc">仅接受已评审内容的精确哈希；保存产生版本化 Receipt，不代表模型供应商已经可调用。</p>
                  <div className="mc-org-list">
                    <label className="mc-org-item">功能标识<input aria-label="功能标识" value={featureId} onChange={(event) => setFeatureId(event.target.value)} placeholder="aip.analysis" /></label>
                    <label className="mc-org-item">评审内容哈希<input aria-label="评审内容哈希" value={featureHash} onChange={(event) => setFeatureHash(event.target.value)} placeholder="sha256:…" /></label>
                    <label className="mc-org-item">授权到期时间<input type="datetime-local" aria-label="授权到期时间" value={featureExpiry} onChange={(event) => setFeatureExpiry(event.target.value)} /></label>
                  </div>
                  <div className="notice" role="status" style={{ marginTop: 12 }}>
                    <strong>影响预览 · {activationPreview.summary}</strong>
                    <div>{activationPreview.boundary}</div>
                    <div>保存采用当前 revision 的 CAS；冲突时失败关闭并要求重新读取。</div>
                  </div>
                </details>
              </div>
            </div>

            <div className="mc-settings-actions">
              <button type="button" className="mc-btn-default" onClick={() => void loadActivations()}>重新读取</button>
              <button type="button" className="mc-btn-primary" disabled={Boolean(activationBusy) || Boolean(activationError)} onClick={() => void handleActivateFeature()}>{activationBusy ? "保存中…" : "保存功能授权"}</button>
            </div>
            {activationMessage && <div className="w2-a6a7-msg" role="status">{activationMessage}</div>}

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
                本页只显示当前租户权威目录中的模型和注册状态。已注册不等于可调用；最终运行状态仍由供应商健康、路由、价格、容量与评测共同决定。
              </p>
            </div>
            <div className="mc-family-list">
              <div className="mc-family-header">
                当前供应商 ({providerFamilies.length})
              </div>
              {providerFamilies.map((family) => (
                <div key={family.provider} className="mc-family-item">
                  <div>
                    <div className="mc-family-name">{family.provider}</div>
                    <div className="mc-family-provider">{family.models.map((model) => model.name).join("、")}</div>
                  </div>
                  <div className="mc-family-actions">
                    <span className={`mc-status-badge ${family.models.every((model) => model.registered) ? "enabled" : "disabled"}`}>{family.models.filter((model) => model.registered).length}/{family.models.length} 已注册</span>
                    <button type="button" className="mc-manage-btn" onClick={() => navigate("/aip/model-router")}>配置路由</button>
                  </div>
                </div>
              ))}
              {providerFamilies.length === 0 && <div className="mc-empty"><p>{sourceMode === "error" ? "权威模型目录不可用" : "当前租户尚无模型"}</p></div>}
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
