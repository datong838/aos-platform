import { describe, expect, it } from "vitest";
import {
  buildComparisonRows,
  businessTokenLabel,
  featureActivationImpactPreview,
  applyPriceAuthority,
  computeCatalogStats,
  extractAllCapabilities,
  extractAllProviders,
  filterCatalogModels,
  formatApiPrice,
  mapApiCatalogRow,
  normalizeCapability,
  parsePricePerMillion,
  priceTierOf,
  registeredRowsFromModels,
  validateRegistrationResponse,
  type CatalogModel,
} from "./ModelCatalogPage";

describe("ModelCatalogPage · 业务中文表达", () => {
  it("把运行合同枚举转成运营人员可理解的中文", () => {
    expect(businessTokenLabel("internal")).toBe("内部开发环境使用");
    expect(businessTokenLabel("tool_execution")).toBe("工具执行");
    expect(businessTokenLabel("unit_mismatch")).toBe("计价单位不匹配");
    expect(businessTokenLabel("AGNES internal authorized model service; AOS self-developed adapter; development pilot and demo only"))
      .toBe("AOS 自研适配器；仅限已授权的开发试点与演示");
  });

  it("未知扩展值保持原值，避免篡改权威事实", () => {
    expect(businessTokenLabel("future_contract_value")).toBe("future_contract_value");
  });
});

describe("ModelCatalogPage · 功能授权影响预览", () => {
  it("明确 revision 推进与无外部副作用边界", () => {
    const preview = featureActivationImpactPreview({
      featureId: "aip.analysis",
      revision: 3,
      contentHash: `sha256:${"a".repeat(64)}`,
      status: "active",
      activatedAt: "2026-08-31T00:00:00Z",
      expiresAt: "2026-09-30T00:00:00Z",
    }, "aip.analysis");
    expect(preview.nextRevision).toBe(4);
    expect(preview.summary).toContain("v3");
    expect(preview.boundary).toContain("不触发模型调用");
  });
});

const MOCK_MODELS: CatalogModel[] = [
  {
    id: "gpt-5",
    name: "GPT-5",
    provider: "OpenAI",
    providerSlug: "openai",
    parameters: "1.8T",
    contextWindow: "256K",
    inputPrice: "$10/1M",
    outputPrice: "$30/1M",
    capabilities: ["chat", "vision", "reasoning"],
    registered: true,
  },
  {
    id: "claude-sonnet",
    name: "Claude Sonnet",
    provider: "Anthropic",
    providerSlug: "anthropic",
    parameters: "400B",
    contextWindow: "200K",
    inputPrice: "$3/1M",
    outputPrice: "$15/1M",
    capabilities: ["chat", "code"],
    registered: false,
  },
  {
    id: "llama-free",
    name: "Llama 4",
    provider: "Meta",
    providerSlug: "meta",
    parameters: "17B",
    contextWindow: "256K",
    inputPrice: "免费",
    outputPrice: "免费",
    capabilities: ["chat"],
    registered: false,
  },
  {
    id: "ada-002",
    name: "Embedding Ada",
    provider: "OpenAI",
    providerSlug: "openai",
    parameters: "1536d",
    contextWindow: "8K",
    inputPrice: "$0.10/1M",
    outputPrice: "—",
    capabilities: ["embedding"],
    registered: true,
  },
];

describe("ModelCatalogPage · extractAllProviders", () => {
  it("返回去重后的供应商列表", () => {
    const providers = extractAllProviders(MOCK_MODELS);
    expect(providers).toEqual(["Anthropic", "Meta", "OpenAI"]);
  });

  it("空数组返回空数组", () => {
    expect(extractAllProviders([])).toEqual([]);
  });
});

describe("ModelCatalogPage · extractAllCapabilities", () => {
  it("返回去重后的能力列表", () => {
    const caps = extractAllCapabilities(MOCK_MODELS);
    expect(caps).toContain("chat");
    expect(caps).toContain("vision");
    expect(caps).toContain("code");
    expect(caps).toContain("embedding");
    expect(caps).toContain("reasoning");
  });

  it("chat 只出现一次（去重）", () => {
    const caps = extractAllCapabilities(MOCK_MODELS);
    const chatCount = caps.filter((c) => c === "chat").length;
    expect(chatCount).toBe(1);
  });
});

describe("ModelCatalogPage · parsePricePerMillion", () => {
  it("解析美元价格", () => {
    expect(parsePricePerMillion("$10/1M")).toBe(10);
    expect(parsePricePerMillion("$0.15/1M")).toBe(0.15);
  });

  it("免费返回 0", () => {
    expect(parsePricePerMillion("免费")).toBe(0);
  });

  it("空值或—保持未知，不冒充免费", () => {
    expect(Number.isNaN(parsePricePerMillion("—"))).toBe(true);
    expect(Number.isNaN(parsePricePerMillion(""))).toBe(true);
  });
});

describe("ModelCatalogPage · priceTierOf", () => {
  it("免费模型归类 free", () => {
    expect(priceTierOf("免费")).toBe("free");
  });

  it("缺失价格归类 unknown", () => {
    expect(priceTierOf("—")).toBe("unknown");
    expect(priceTierOf("价格未知")).toBe("unknown");
  });

  it("低价模型 < $1/1M", () => {
    expect(priceTierOf("$0.15/1M")).toBe("low");
    expect(priceTierOf("$0.10/1M")).toBe("low");
  });

  it("中价模型 $1-$5/1M", () => {
    expect(priceTierOf("$3/1M")).toBe("mid");
  });

  it("高价模型 > $5/1M", () => {
    expect(priceTierOf("$10/1M")).toBe("high");
  });
});

describe("ModelCatalogPage · exact price authority", () => {
  const ref = { assetType: "RegisteredModelRevision", assetId: "model-1", revision: 1, contentHash: "a".repeat(64) };
  it("已注册模型没有 exact 价格时显示未知", () => {
    const result = applyPriceAuthority([{ ...MOCK_MODELS[0], providerModelId: "agnes-2.5-flash" }], []);
    expect(result[0].inputPrice).toBe("价格未知");
    expect(priceTierOf(result[0].inputPrice)).toBe("unknown");
  });
  it("只有 exact 零价审批才显示审批免费", () => {
    const result = applyPriceAuthority([{ ...MOCK_MODELS[0], providerModelId: "agnes-2.5-flash" }], [{ modelRef: ref, providerModelId: "agnes-2.5-flash", outputModalities: ["text"], priceSnapshotRef: null, status: "approved_zero", currency: "CNY", inputTokenPrice: 0, outputTokenPrice: 0, cachedTokenPrice: null, tokenUnit: 1000, effectiveFrom: null, effectiveUntil: null, zeroPriceApprovalRef: "approval://zero", blockerCodes: [] }]);
    expect(result[0].inputPrice).toBe("已审批免费");
    expect(priceTierOf(result[0].inputPrice)).toBe("free");
  });
  it("图像 token 单位不匹配不会显示免费", () => {
    const result = applyPriceAuthority([{ ...MOCK_MODELS[0], providerModelId: "agnes-image" }], [{ modelRef: ref, providerModelId: "agnes-image", outputModalities: ["image"], priceSnapshotRef: null, status: "unit_mismatch", currency: "CNY", inputTokenPrice: 0, outputTokenPrice: 0, cachedTokenPrice: null, tokenUnit: 1000, effectiveFrom: null, effectiveUntil: null, zeroPriceApprovalRef: null, blockerCodes: ["TOKEN_PRICE_UNIT_MISMATCH"] }]);
    expect(result[0].inputPrice).toBe("计价单位待补");
    expect(priceTierOf(result[0].inputPrice)).toBe("unknown");
  });
});

describe("ModelCatalogPage · filterCatalogModels", () => {
  it("all 条件返回全部", () => {
    const result = filterCatalogModels(MOCK_MODELS, {
      query: "",
      provider: "all",
      capability: "all",
      priceTier: "all",
    });
    expect(result.length).toBe(MOCK_MODELS.length);
  });

  it("按供应商筛选 OpenAI", () => {
    const result = filterCatalogModels(MOCK_MODELS, {
      query: "",
      provider: "OpenAI",
      capability: "all",
      priceTier: "all",
    });
    expect(result.length).toBe(2);
    expect(result.every((m) => m.provider === "OpenAI")).toBe(true);
  });

  it("按能力筛选 embedding", () => {
    const result = filterCatalogModels(MOCK_MODELS, {
      query: "",
      provider: "all",
      capability: "embedding",
      priceTier: "all",
    });
    expect(result.length).toBe(1);
    expect(result[0].id).toBe("ada-002");
  });

  it("按价格区间筛选 free", () => {
    const result = filterCatalogModels(MOCK_MODELS, {
      query: "",
      provider: "all",
      capability: "all",
      priceTier: "free",
    });
    expect(result.length).toBe(1);
    expect(result[0].id).toBe("llama-free");
  });

  it("搜索关键词匹配名称", () => {
    const result = filterCatalogModels(MOCK_MODELS, {
      query: "Claude",
      provider: "all",
      capability: "all",
      priceTier: "all",
    });
    expect(result.length).toBe(1);
    expect(result[0].name).toContain("Claude");
  });

  it("搜索关键词匹配供应商", () => {
    const result = filterCatalogModels(MOCK_MODELS, {
      query: "anthropic",
      provider: "all",
      capability: "all",
      priceTier: "all",
    });
    expect(result.length).toBe(1);
    expect(result[0].provider).toBe("Anthropic");
  });

  it("组合条件：OpenAI + high", () => {
    const result = filterCatalogModels(MOCK_MODELS, {
      query: "",
      provider: "OpenAI",
      capability: "all",
      priceTier: "high",
    });
    expect(result.length).toBe(1);
    expect(result[0].id).toBe("gpt-5");
  });

  it("不修改原数组", () => {
    const original = [...MOCK_MODELS];
    filterCatalogModels(MOCK_MODELS, {
      query: "test",
      provider: "OpenAI",
      capability: "all",
      priceTier: "all",
    });
    expect(MOCK_MODELS).toEqual(original);
  });
});

describe("ModelCatalogPage · computeCatalogStats", () => {
  it("返回 total/registered/providers/free", () => {
    const stats = computeCatalogStats(MOCK_MODELS);
    expect(stats).toHaveProperty("total");
    expect(stats).toHaveProperty("registered");
    expect(stats).toHaveProperty("providers");
    expect(stats).toHaveProperty("free");
  });

  it("total 正确", () => {
    expect(computeCatalogStats(MOCK_MODELS).total).toBe(4);
  });

  it("registered 正确", () => {
    expect(computeCatalogStats(MOCK_MODELS).registered).toBe(2);
  });

  it("providers 正确（去重）", () => {
    expect(computeCatalogStats(MOCK_MODELS).providers).toBe(3);
  });

  it("free 正确", () => {
    expect(computeCatalogStats(MOCK_MODELS).free).toBe(1);
  });

  it("空数组返回全 0", () => {
    const stats = computeCatalogStats([]);
    expect(stats.total).toBe(0);
    expect(stats.registered).toBe(0);
    expect(stats.providers).toBe(0);
    expect(stats.free).toBe(0);
  });
});

describe("ModelCatalogPage · buildComparisonRows", () => {
  it("返回属性行", () => {
    const rows = buildComparisonRows([MOCK_MODELS[0], MOCK_MODELS[1]]);
    const fields = rows.map((r) => r.field);
    expect(fields).toContain("供应商");
    expect(fields).toContain("参数量");
    expect(fields).toContain("上下文窗口");
    expect(fields).toContain("输入价格");
  });

  it("每行的 values 长度等于选中模型数", () => {
    const selected = [MOCK_MODELS[0], MOCK_MODELS[1], MOCK_MODELS[2]];
    const rows = buildComparisonRows(selected);
    for (const row of rows) {
      expect(row.values.length).toBe(3);
    }
  });

  it("供应商值正确", () => {
    const rows = buildComparisonRows([MOCK_MODELS[0], MOCK_MODELS[1]]);
    const providerRow = rows.find((r) => r.field === "供应商")!;
    expect(providerRow.values).toEqual(["OpenAI", "Anthropic"]);
  });
});

describe("ModelCatalogPage · mapApiCatalogRow (W2-A7)", () => {
  it("映射 displayName / 能力 / 价格 / registered", () => {
    const m = mapApiCatalogRow({
      id: "mc-gpt-4o",
      provider: "azure-openai",
      model: "gpt-4o",
      displayName: "GPT-4o",
      capabilities: ["text", "vision", "function_calling"],
      contextWindow: 128000,
      inputPrice: 0.005,
      outputPrice: 0.015,
      registered: true,
    });
    expect(m.id).toBe("mc-gpt-4o");
    expect(m.name).toBe("GPT-4o");
    expect(m.providerSlug).toContain("azure-openai");
    expect(m.capabilities).toContain("chat");
    expect(m.capabilities).toContain("function-calling");
    expect(m.contextWindow).toBe("128K");
    expect(m.inputPrice).toBe("$5/1M"); // 0.005 $/1K → $5/1M
    expect(m.registered).toBe(true);
  });

  it("已是 $/1M 量级的价格不二次放大", () => {
    expect(formatApiPrice(3)).toBe("$3/1M");
  });

  it("normalizeCapability 归一化", () => {
    expect(normalizeCapability("text")).toBe("chat");
    expect(normalizeCapability("function_calling")).toBe("function-calling");
    expect(normalizeCapability("unknown-x")).toBeNull();
  });

  it("registeredRowsFromModels 仅已注册", () => {
    const rows = registeredRowsFromModels(MOCK_MODELS);
    expect(rows.length).toBe(2);
    expect(rows.every((r) => MOCK_MODELS.find((m) => m.name === r.model)?.registered)).toBe(true);
  });
});

describe("ModelCatalogPage · 注册响应严格核验", () => {
  it("ok 与 item.modelId 同时匹配才通过", () => {
    expect(validateRegistrationResponse({ ok: true, item: { modelId: "mc-1" } }, "mc-1")).toBe(true);
    expect(validateRegistrationResponse({ ok: false, item: { modelId: "mc-1" } }, "mc-1")).toBe(false);
    expect(validateRegistrationResponse({ ok: true, item: { modelId: "other" } }, "mc-1")).toBe(false);
    expect(validateRegistrationResponse({ ok: true }, "mc-1")).toBe(false);
  });
});
