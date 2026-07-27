import { describe, expect, it } from "vitest";
import {
  filterRateLimits,
  filterUserLimits,
  formatTokenCount,
  formatUsd,
  sumUsage,
  usagePercent,
  usageTone,
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
