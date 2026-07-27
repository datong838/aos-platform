import { describe, expect, it } from "vitest";
import {
  CATEGORIES,
  MOCK_MODULES,
  filterModules,
  sortByRecent,
  formatRelativeTime,
  getStatusMeta,
  getCategoryName,
  getCategoryColor,
} from "./WorkshopListPage";

describe("WorkshopListPage · CATEGORIES 分类定义", () => {
  it("包含 10 个（全部 + 9 分类）", () => {
    expect(CATEGORIES.length).toBe(10);
  });

  it("第一个是「全部」", () => {
    expect(CATEGORIES[0].id).toBe("all");
    expect(CATEGORIES[0].name).toBe("全部");
  });

  it("包含 9 个业务分类", () => {
    const ids = CATEGORIES.map((c) => c.id);
    expect(ids).toEqual(
      expect.arrayContaining([
        "order",
        "risk",
        "customer",
        "asset",
        "analytics",
        "ticket",
        "inventory",
        "finance",
        "marketing",
      ]),
    );
  });

  it("每个分类有 id/name/color", () => {
    for (const cat of CATEGORIES) {
      expect(cat.id.length).toBeGreaterThan(0);
      expect(cat.name.length).toBeGreaterThan(0);
      expect(cat.color.length).toBeGreaterThan(0);
    }
  });

  it("ID 唯一", () => {
    const ids = CATEGORIES.map((c) => c.id);
    expect(new Set(ids).size).toBe(ids.length);
  });
});

describe("WorkshopListPage · MOCK_MODULES", () => {
  it("至少 9 个 mock 模块", () => {
    expect(MOCK_MODULES.length).toBeGreaterThanOrEqual(9);
  });

  it("覆盖全部 9 个分类", () => {
    const cats = new Set(MOCK_MODULES.map((m) => m.category));
    expect(cats.has("order")).toBe(true);
    expect(cats.has("risk")).toBe(true);
    expect(cats.has("customer")).toBe(true);
    expect(cats.has("asset")).toBe(true);
    expect(cats.has("analytics")).toBe(true);
    expect(cats.has("ticket")).toBe(true);
    expect(cats.has("inventory")).toBe(true);
    expect(cats.has("finance")).toBe(true);
    expect(cats.has("marketing")).toBe(true);
  });

  it("每个模块有 id/name/status/category/lastOpenedAt", () => {
    for (const m of MOCK_MODULES) {
      expect(m.id.length).toBeGreaterThan(0);
      expect(m.name.length).toBeGreaterThan(0);
      expect(m.status.length).toBeGreaterThan(0);
      expect(m.category!.length).toBeGreaterThan(0);
      expect(m.lastOpenedAt!.length).toBeGreaterThan(0);
    }
  });
});

describe("WorkshopListPage · filterModules", () => {
  it("category=all 返回全部", () => {
    const result = filterModules(MOCK_MODULES, "all", "");
    expect(result.length).toBe(MOCK_MODULES.length);
  });

  it("category=order 只返回订单模块", () => {
    const result = filterModules(MOCK_MODULES, "order", "");
    expect(result.every((m) => m.category === "order")).toBe(true);
    expect(result.length).toBeGreaterThan(0);
  });

  it("query 模糊搜索名称", () => {
    const result = filterModules(MOCK_MODULES, "all", "订单");
    expect(result.length).toBeGreaterThan(0);
    expect(result.every((m) => m.name.includes("订单") || m.description?.includes("订单"))).toBe(true);
  });

  it("query + category 同时生效", () => {
    const result = filterModules(MOCK_MODULES, "risk", "告警");
    expect(result.length).toBeGreaterThan(0);
    expect(result.every((m) => m.category === "risk")).toBe(true);
  });

  it("无匹配返回空数组", () => {
    const result = filterModules(MOCK_MODULES, "all", "不存在的模块xyz");
    expect(result).toEqual([]);
  });

  it("query 大小写不敏感", () => {
    const lower = filterModules(MOCK_MODULES, "all", "order");
    const upper = filterModules(MOCK_MODULES, "all", "ORDER");
    expect(lower.length).toBe(upper.length);
  });
});

describe("WorkshopListPage · sortByRecent", () => {
  it("按 lastOpenedAt 降序排列", () => {
    const sorted = sortByRecent(MOCK_MODULES);
    for (let i = 1; i < sorted.length; i++) {
      const prev = new Date(sorted[i - 1].lastOpenedAt!).getTime();
      const curr = new Date(sorted[i].lastOpenedAt!).getTime();
      expect(prev).toBeGreaterThanOrEqual(curr);
    }
  });

  it("不修改原数组", () => {
    const original = [...MOCK_MODULES];
    sortByRecent(MOCK_MODULES);
    expect(MOCK_MODULES).toEqual(original);
  });
});

describe("WorkshopListPage · formatRelativeTime", () => {
  it("1 分钟内 → 刚刚", () => {
    expect(formatRelativeTime(new Date(Date.now() - 30_000).toISOString())).toBe("刚刚");
  });

  it("分钟级", () => {
    expect(formatRelativeTime(new Date(Date.now() - 5 * 60_000).toISOString())).toContain("分钟前");
  });

  it("小时级", () => {
    expect(formatRelativeTime(new Date(Date.now() - 3 * 3600_000).toISOString())).toContain("小时前");
  });

  it("天级", () => {
    expect(formatRelativeTime(new Date(Date.now() - 3 * 86400_000).toISOString())).toContain("天前");
  });

  it("undefined → —", () => {
    expect(formatRelativeTime(undefined)).toBe("—");
  });
});

describe("WorkshopListPage · getStatusMeta", () => {
  it("published → 已发布/绿色", () => {
    const meta = getStatusMeta("published");
    expect(meta.label).toBe("已发布");
    expect(meta.color).toBe("#059669");
  });

  it("draft → 草稿/黄色", () => {
    const meta = getStatusMeta("draft");
    expect(meta.label).toBe("草稿");
    expect(meta.color).toBe("#D97706");
  });

  it("disabled → 已禁用/红色", () => {
    const meta = getStatusMeta("disabled");
    expect(meta.label).toBe("已禁用");
    expect(meta.color).toBe("#DC2626");
  });
});

describe("WorkshopListPage · getCategoryName", () => {
  it("order → 订单", () => {
    expect(getCategoryName("order")).toBe("订单");
  });

  it("risk → 风控", () => {
    expect(getCategoryName("risk")).toBe("风控");
  });

  it("undefined → 未分类", () => {
    expect(getCategoryName(undefined)).toBe("未分类");
  });
});

describe("WorkshopListPage · getCategoryColor", () => {
  it("order → 蓝色系", () => {
    expect(getCategoryColor("order")).toBe("#2563EB");
  });

  it("risk → 红色系", () => {
    expect(getCategoryColor("risk")).toBe("#DC2626");
  });

  it("undefined → 灰色默认", () => {
    expect(getCategoryColor(undefined)).toBe("#6B7280");
  });
});
