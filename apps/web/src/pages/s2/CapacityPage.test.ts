import { describe, expect, it } from "vitest";
import {
  filterRateLimits,
  filterUserLimits,
  formatTokenCount,
  formatUsd,
  isCapacityLiveSuccess,
  authoritativeCostLabel,
  mapApiLimitToUserLimit,
  mapUsageItemsToBuckets,
  nextQuotaRevisionBody,
  projectQuotaFromLimit,
  rateLimitsFromRuntimePools,
  sumUsage,
  usagePercent,
  usageTone,
  usageBucketsFromAuthority,
  validateLimitSnapshot,
  type RateLimit,
  type UsageBucket,
  type UserLimit,
} from "./CapacityPage";

const MOCK_LIMITS: RateLimit[] = [
  { model: "GPT-5", provider: "OpenAI", tokensPerMin: "1.5M", requestsPerMin: "1K" },
  { model: "Claude", provider: "Anthropic", tokensPerMin: "8M", requestsPerMin: "900" },
  { model: "Grok", provider: "xAI", tokensPerMin: "1M", requestsPerMin: "200" },
];

const MOCK_USERS: UserLimit[] = [
  { user: "alice@corp", team: "数据平台", rpmLimit: 60, tpmLimit: 200_000, dailyBudgetUsd: 50, usedTodayUsd: 12.4 },
  { user: "bob@corp", team: "数据平台", rpmLimit: 60, tpmLimit: 200_000, dailyBudgetUsd: 50, usedTodayUsd: 48.2 },
  { user: "carol@corp", team: "风控", rpmLimit: 30, tpmLimit: 100_000, dailyBudgetUsd: 20, usedTodayUsd: 5.1 },
];

const MOCK_BUCKETS: UsageBucket[] = [
  { period: "today", label: "今日", totalRequests: 100, totalTokens: 500_000, totalCostUsd: 10 },
  { period: "week", label: "本周", totalRequests: 700, totalTokens: 3_500_000, totalCostUsd: 70 },
];

describe("CapacityPage · formatTokenCount", () => {
  it("小于 1000 原样返回", () => {
    expect(formatTokenCount(500)).toBe("500");
  });

  it("千级别加 K", () => {
    expect(formatTokenCount(1500)).toBe("1.5K");
  });

  it("百万级别加 M", () => {
    expect(formatTokenCount(2_400_000)).toBe("2.40M");
  });

  it("十亿级别加 B", () => {
    expect(formatTokenCount(1_500_000_000)).toBe("1.50B");
  });
});

describe("CapacityPage · formatUsd", () => {
  it("小于 1000 加 $ 前缀", () => {
    expect(formatUsd(42.5)).toBe("$42.50");
  });

  it("大于等于 1000 加 K 后缀", () => {
    expect(formatUsd(3920.75)).toBe("$3.92K");
  });

  it("0 返回 $0.00", () => {
    expect(formatUsd(0)).toBe("$0.00");
  });
});

describe("CapacityPage · usagePercent", () => {
  it("正常计算百分比", () => {
    expect(usagePercent(50, 100)).toBe(50);
    expect(usagePercent(75, 100)).toBe(75);
  });

  it("超过 100 截断为 100", () => {
    expect(usagePercent(150, 100)).toBe(100);
  });

  it("配额为 0 返回 0", () => {
    expect(usagePercent(50, 0)).toBe(0);
  });

  it("0 用量返回 0", () => {
    expect(usagePercent(0, 100)).toBe(0);
  });
});

describe("CapacityPage · usageTone", () => {
  it("< 70 返回 ok", () => {
    expect(usageTone(50)).toBe("ok");
    expect(usageTone(69)).toBe("ok");
  });

  it("70-89 返回 warn", () => {
    expect(usageTone(70)).toBe("warn");
    expect(usageTone(89)).toBe("warn");
  });

  it(">= 90 返回 danger", () => {
    expect(usageTone(90)).toBe("danger");
    expect(usageTone(100)).toBe("danger");
  });
});

describe("CapacityPage · filterRateLimits", () => {
  it("all 返回全部", () => {
    expect(filterRateLimits(MOCK_LIMITS, "all").length).toBe(3);
  });

  it("按供应商筛选 OpenAI", () => {
    const result = filterRateLimits(MOCK_LIMITS, "OpenAI");
    expect(result.length).toBe(1);
    expect(result[0].provider).toBe("OpenAI");
  });

  it("不存在的供应商返回空", () => {
    expect(filterRateLimits(MOCK_LIMITS, "NotFound").length).toBe(0);
  });
});

describe("CapacityPage · filterUserLimits", () => {
  it("all 返回全部", () => {
    expect(filterUserLimits(MOCK_USERS, "all").length).toBe(3);
  });

  it("按团队筛选", () => {
    const result = filterUserLimits(MOCK_USERS, "数据平台");
    expect(result.length).toBe(2);
    expect(result.every((u) => u.team === "数据平台")).toBe(true);
  });

  it("不存在的团队返回空", () => {
    expect(filterUserLimits(MOCK_USERS, "不存在").length).toBe(0);
  });
});

describe("CapacityPage · sumUsage", () => {
  it("累加多个 bucket", () => {
    const result = sumUsage(MOCK_BUCKETS);
    expect(result.requests).toBe(800);
    expect(result.tokens).toBe(4_000_000);
    expect(result.cost).toBe(80);
  });

  it("空数组返回全 0", () => {
    const result = sumUsage([]);
    expect(result).toEqual({ requests: 0, tokens: 0, cost: 0 });
  });

  it("单个 bucket 正确", () => {
    const result = sumUsage([MOCK_BUCKETS[0]]);
    expect(result.requests).toBe(100);
    expect(result.cost).toBe(10);
  });
});

describe("CapacityPage · mapUsageItemsToBuckets (W2-A6)", () => {
  const now = new Date("2026-07-29T12:00:00Z");

  it("聚合今日/近7天/近30天", () => {
    const items = [
      { day: "2026-07-29", totalRequests: 10, totalTokens: 100, cost: 1 },
      { day: "2026-07-28", totalRequests: 20, totalTokens: 200, cost: 2 },
      { day: "2026-07-01", totalRequests: 30, totalTokens: 300, cost: 3 },
      { day: "2026-06-01", totalRequests: 999, totalTokens: 999, cost: 9 },
    ];
    const buckets = mapUsageItemsToBuckets(items, now);
    const today = buckets.find((b) => b.period === "today")!;
    const week = buckets.find((b) => b.period === "week")!;
    const month = buckets.find((b) => b.period === "month")!;
    expect(today.totalRequests).toBe(10);
    expect(week.totalRequests).toBe(30); // 29+28
    expect(month.totalRequests).toBe(60); // 29+28+01
  });

  it("空 items 返回 0 桶（非 mock）", () => {
    const buckets = mapUsageItemsToBuckets([], now);
    expect(buckets.every((b) => b.totalRequests === 0)).toBe(true);
  });
});

describe("CapacityPage · mapApiLimitToUserLimit", () => {
  it("映射 scopeKey 与限额", () => {
    const u = mapApiLimitToUserLimit({ scopeKey: "alice", rpmLimit: 120, tpmLimit: 500000 });
    expect(u.user).toBe("alice");
    expect(u.rpmLimit).toBe(120);
    expect(u.tpmLimit).toBe(500000);
    expect(u.team).toBe("—");
  });
});

describe("CapacityPage · projectQuotaFromLimit", () => {
  it("null 返回空", () => {
    expect(projectQuotaFromLimit(null, 100)).toEqual([]);
  });

  it("合成项目 TPM 条", () => {
    const q = projectQuotaFromLimit({ rpmLimit: 60, tpmLimit: 1000 }, 400);
    expect(q.length).toBe(1);
    expect(q[0].used).toBe(400);
    expect(q[0].quota).toBe(1000);
  });
});

describe("CapacityPage · isCapacityLiveSuccess", () => {
  it("usage 成功 → live", () => {
    expect(isCapacityLiveSuccess(true)).toBe("live");
  });
  it("usage 失败 → error", () => {
    expect(isCapacityLiveSuccess(false)).toBe("error");
  });
});

describe("CapacityPage · 限额写后重读严格核验", () => {
  it("scope、scopeKey、RPM、TPM 全部一致才通过", () => {
    const draft = { rpmLimit: 120, tpmLimit: 500000 };
    expect(validateLimitSnapshot({ scope: "project", scopeKey: "default", ...draft }, "project", "default", draft)).toBe(true);
    expect(validateLimitSnapshot({ scope: "user", scopeKey: "default", ...draft }, "project", "default", draft)).toBe(false);
    expect(validateLimitSnapshot({ scope: "project", scopeKey: "other", ...draft }, "project", "default", draft)).toBe(false);
    expect(validateLimitSnapshot({ scope: "project", scopeKey: "default", rpmLimit: 60, tpmLimit: 500000 }, "project", "default", draft)).toBe(false);
  });
});

describe("CapacityPage · exact runtime authority", () => {
  it("只从完整 quota head 构造下一版本，保留安全边界", () => {
    const H = "a".repeat(64);
    const body = nextQuotaRevisionBody({
      quotaPolicyRef: { assetType: "QuotaPolicyRevision", assetId: "quota-1", revision: 1, contentHash: H },
      headRef: { assetType: "QuotaPolicyRevision", assetId: "quota-1", revision: 2, contentHash: H }, headVersion: 2,
      status: "active", lifecycle: "active", owner: "fde", approvalRef: "approval:quota", rpmLimit: 40, tpmLimit: 40000,
      maxConcurrency: 2, maxInputTokens: 8000, maxOutputTokens: 2000, hourlyRequestLimit: 50, dailyRequestLimit: 200,
      overflowBehavior: "reject", reservationLeaseSeconds: 60, allowPublicProviderFallback: false, allowAutoScale: false,
      effectiveFrom: "2026-08-01T00:00:00Z", effectiveUntil: "2026-09-30T00:00:00Z", blockerCodes: [],
    }, 45, 45000);
    expect(body).toMatchObject({ policyId: "quota-1", revision: 3, rpmLimit: 45, tpmLimit: 45000, allowPublicProviderFallback: false, allowAutoScale: false });
  });
  it("无 Usage Receipt 时显示未观测而非 $0", () => {
    expect(authoritativeCostLabel({ tenant: { orgId: "org-org", projectId: "dev-project" }, modelPrices: [], budgets: [], quotas: [], usage: { state: "unobserved", receiptCount: 0, measuredCount: 0, estimatedCount: 0, unknownCount: 0, adjustmentCount: 0, costTotals: {}, latestObservedAt: null, truncated: false, periods: [] }, generatedAt: "2026-08-21T00:00:00Z" })).toBe("未观测");
  });
  it("已有状态但没有成本凭证时说明尚无实际调用，不误导成零成本", () => {
    expect(authoritativeCostLabel({ tenant: { orgId: "org-org", projectId: "dev-project" }, modelPrices: [], budgets: [], quotas: [], usage: { state: "measured", receiptCount: 0, measuredCount: 0, estimatedCount: 0, unknownCount: 0, adjustmentCount: 0, costTotals: {}, latestObservedAt: null, truncated: false, periods: [] }, generatedAt: "2026-08-21T00:00:00Z" })).toBe("尚无实际模型调用记录");
  });
  it("容量表来自 exact pool，不使用静态供应商模型", () => {
    const limits = rateLimitsFromRuntimePools([{ poolId: "pool-1", revision: 1, contentHash: "a".repeat(64), routeRef: { assetType: "ModelRouteRevision", assetId: "route-1", revision: 1, contentHash: "a".repeat(64) }, modelRef: { assetType: "RegisteredModelRevision", assetId: "agnes-text", revision: 1, contentHash: "a".repeat(64) }, providerRef: { assetType: "ProviderInstanceRevision", assetId: "agnes-provider", revision: 1, contentHash: "a".repeat(64) }, maxConcurrency: 2, maxTokenUnits: 8, tokenUnitPerReservation: 1, leaseSeconds: 60, activeReservations: 1, reservedTokenUnits: 1, lifecycle: "active" }]);
    expect(limits).toEqual([{ model: "agnes-text", provider: "agnes-provider", tokensPerMin: "每次租约 1 个模型用量单位", requestsPerMin: "当前并发 1/2" }]);
  });
  it("按权威周期汇总 Token，缺少凭证时保留未观测", () => {
    const cost = { tenant: { orgId: "org-org", projectId: "dev-project" }, modelPrices: [], budgets: [], quotas: [], usage: { state: "measured" as const, receiptCount: 2, measuredCount: 2, estimatedCount: 0, unknownCount: 0, adjustmentCount: 0, costTotals: {}, latestObservedAt: "2026-08-21T00:00:00Z", truncated: false, periods: [{ period: "today" as const, timeZone: "Asia/Shanghai", startsAt: "2026-08-21T00:00:00Z", endsAt: "2026-08-21T12:00:00Z", receiptCount: 2, measuredCount: 2, estimatedCount: 0, unknownCount: 0, quantityTotals: { "input_token:token": 12, "output_token:token": 8 }, providerCounts: { agnes: 2 }, attributionDimensions: [] }] }, generatedAt: "2026-08-21T12:00:00Z" };
    const buckets = usageBucketsFromAuthority(cost);
    expect(buckets[0]).toMatchObject({ observed: true, receiptCount: 2, totalTokens: 20, timeZone: "Asia/Shanghai" });
    expect(buckets[1]).toMatchObject({ observed: false, totalTokens: 0 });
  });
});
