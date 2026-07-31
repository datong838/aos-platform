import { describe, expect, it } from "vitest";
import {
  CATEGORIES,
  CATALOG_APPS,
  MOCK_MODULES,
  RECENT_DEFAULT_IDS,
  filterModules,
  filterCatalog,
  sortByRecent,
  formatRelativeTime,
  getStatusMeta,
  getCategoryName,
  getCategoryColor,
} from "./WorkshopListPage";

describe("WorkshopListPage · CATEGORIES 分类定义", () => {
  it("对齐视觉稿：全部 / 运营 / 分析 / AI 助手", () => {
    expect(CATEGORIES.map((c) => c.id)).toEqual(["all", "ops", "analytics", "ai"]);
    expect(CATEGORIES.map((c) => c.name)).toEqual(["全部", "运营", "分析", "AI 助手"]);
  });

  it("第一个是「全部」", () => {
    expect(CATEGORIES[0].id).toBe("all");
    expect(CATEGORIES[0].name).toBe("全部");
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

describe("WorkshopListPage · CATALOG_APPS 视觉稿目录", () => {
  it("包含视觉稿 9 张全部应用卡", () => {
    expect(CATALOG_APPS).toHaveLength(9);
    expect(CATALOG_APPS.map((a) => a.name)).toEqual([
      "订单管理系统",
      "风险告警管理",
      "对象探索",
      "Buddy · 智能助手",
      "画布编辑",
      "态势大屏",
      "发布入口",
      "模块接口",
      "事件配置",
    ]);
  });

  it("最近默认三卡对齐视觉稿", () => {
    expect([...RECENT_DEFAULT_IDS]).toEqual(["app-orders", "app-inbox", "app-graph"]);
  });

  it("MOCK_MODULES 与目录等长", () => {
    expect(MOCK_MODULES.length).toBe(CATALOG_APPS.length);
  });
});

describe("WorkshopListPage · filterCatalog", () => {
  it("all 返回全部", () => {
    expect(filterCatalog(CATALOG_APPS, "all")).toHaveLength(9);
  });

  it("ai 仅 Buddy", () => {
    const r = filterCatalog(CATALOG_APPS, "ai");
    expect(r).toHaveLength(1);
    expect(r[0].name).toBe("Buddy · 智能助手");
  });

  it("analytics 含对象探索", () => {
    const r = filterCatalog(CATALOG_APPS, "analytics");
    expect(r.some((a) => a.id === "app-graph")).toBe(true);
  });
});

describe("WorkshopListPage · filterModules", () => {
  it("category=all 返回全部", () => {
    const result = filterModules(MOCK_MODULES, "all", "");
    expect(result.length).toBe(MOCK_MODULES.length);
  });

  it("category=ops 只返回运营", () => {
    const result = filterModules(MOCK_MODULES, "ops", "");
    expect(result.every((m) => m.category === "ops")).toBe(true);
    expect(result.length).toBeGreaterThan(0);
  });

  it("query 模糊搜索名称", () => {
    const result = filterModules(MOCK_MODULES, "all", "订单");
    expect(result.length).toBeGreaterThan(0);
    expect(result.every((m) => m.name.includes("订单") || m.description?.includes("订单"))).toBe(true);
  });

  it("无匹配返回空数组", () => {
    const result = filterModules(MOCK_MODULES, "all", "不存在的模块xyz");
    expect(result).toEqual([]);
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

  it("undefined → —", () => {
    expect(formatRelativeTime(undefined)).toBe("—");
  });
});

describe("WorkshopListPage · getStatusMeta", () => {
  it("published → 已发布/绿色", () => {
    const meta = getStatusMeta("published");
    expect(meta.label).toBe("已发布");
    expect(meta.color).toBe("var(--aos-green-600)");
  });
});

describe("WorkshopListPage · getCategoryName/Color", () => {
  it("ops → 运营", () => {
    expect(getCategoryName("ops")).toBe("运营");
  });

  it("ops → 蓝色系", () => {
    expect(getCategoryColor("ops")).toBe("#2563EB");
  });

  it("undefined → 未分类 / 灰色", () => {
    expect(getCategoryName(undefined)).toBe("未分类");
    expect(getCategoryColor(undefined)).toBe("var(--aos-text-secondary)");
  });
});
