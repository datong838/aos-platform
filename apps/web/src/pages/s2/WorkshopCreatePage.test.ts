import { describe, expect, it } from "vitest";
import {
  STEPS,
  CATEGORIES,
  TEMPLATES,
  MOCK_EXISTING_MODULES,
  slugify,
  canNextFromStep1,
  canNextFromStep2,
  buildCreatePayload,
} from "./WorkshopCreatePage";

describe("WorkshopCreatePage · STEPS 步骤定义", () => {
  it("至少 3 步", () => {
    expect(STEPS.length).toBeGreaterThanOrEqual(3);
  });

  it("步骤含 basic/template/confirm", () => {
    const keys = STEPS.map((s) => s.key);
    expect(keys).toContain("basic");
    expect(keys).toContain("template");
    expect(keys).toContain("confirm");
  });

  it("每个步骤有 key/title/description", () => {
    for (const step of STEPS) {
      expect(step.key.length).toBeGreaterThan(0);
      expect(step.title.length).toBeGreaterThan(0);
      expect(step.description!.length).toBeGreaterThan(0);
    }
  });
});

describe("WorkshopCreatePage · CATEGORIES 分类", () => {
  it("包含 9 个分类", () => {
    expect(CATEGORIES.length).toBe(9);
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

  it("包含订单/风控/客户/资产/分析/工单/库存/财务/营销", () => {
    const names = CATEGORIES.map((c) => c.name);
    expect(names).toEqual(
      expect.arrayContaining([
        "订单",
        "风控",
        "客户",
        "资产",
        "分析",
        "工单",
        "库存",
        "财务",
        "营销",
      ]),
    );
  });
});

describe("WorkshopCreatePage · TEMPLATES 模板", () => {
  it("包含 4 个模板（空白/仪表盘/表单/列表）", () => {
    expect(TEMPLATES.length).toBe(4);
  });

  it("每个模板有 id/name/desc", () => {
    for (const t of TEMPLATES) {
      expect(t.id.length).toBeGreaterThan(0);
      expect(t.name.length).toBeGreaterThan(0);
      expect(t.desc.length).toBeGreaterThan(0);
    }
  });

  it("包含 blank/dashboard/form/table", () => {
    const ids = TEMPLATES.map((t) => t.id);
    expect(ids).toContain("blank");
    expect(ids).toContain("dashboard");
    expect(ids).toContain("form");
    expect(ids).toContain("table");
  });

  it("blank 模板标记为 blank=true", () => {
    const blank = TEMPLATES.find((t) => t.id === "blank");
    expect(blank?.blank).toBe(true);
  });
});

describe("WorkshopCreatePage · MOCK_EXISTING_MODULES", () => {
  it("至少 5 个模块用于复制", () => {
    expect(MOCK_EXISTING_MODULES.length).toBeGreaterThanOrEqual(5);
  });

  it("每个模块有 id/name/category/updated_at", () => {
    for (const m of MOCK_EXISTING_MODULES) {
      expect(m.id.length).toBeGreaterThan(0);
      expect(m.name.length).toBeGreaterThan(0);
      expect(m.category.length).toBeGreaterThan(0);
      expect(m.updated_at.length).toBeGreaterThan(0);
    }
  });
});

describe("WorkshopCreatePage · slugify", () => {
  it("中英混合转 kebab", () => {
    expect(slugify("库存管理系统")).toBe("库存管理系统");
    expect(slugify("Order Management")).toBe("order-management");
  });

  it("去除首尾连字符", () => {
    expect(slugify("  hello world  ")).not.toMatch(/^-|-$/);
  });

  it("合并多个连字符", () => {
    expect(slugify("a---b")).toBe("a-b");
  });

  it("空字符串返回空", () => {
    expect(slugify("")).toBe("");
  });
});

describe("WorkshopCreatePage · canNextFromStep1", () => {
  it("名称和分类非空 → true", () => {
    expect(canNextFromStep1("库存系统", "inventory")).toBe(true);
  });

  it("名称为空 → false", () => {
    expect(canNextFromStep1("", "inventory")).toBe(false);
    expect(canNextFromStep1("   ", "inventory")).toBe(false);
  });

  it("分类为空 → false", () => {
    expect(canNextFromStep1("库存系统", "")).toBe(false);
  });
});

describe("WorkshopCreatePage · canNextFromStep2", () => {
  it("非 copy 模板且 id 非空 → true", () => {
    expect(canNextFromStep2("table", null)).toBe(true);
    expect(canNextFromStep2("dashboard", null)).toBe(true);
  });

  it("copy 模板但未选源 → false", () => {
    expect(canNextFromStep2("copy", null)).toBe(false);
  });

  it("copy 模板且选了源 → true", () => {
    expect(canNextFromStep2("copy", "mod-001")).toBe(true);
  });
});

describe("WorkshopCreatePage · buildCreatePayload", () => {
  it("生成完整 payload", () => {
    const payload = buildCreatePayload({
      name: "库存管理系统",
      category: "inventory",
      description: "管理仓库库存",
      template: "table",
      copyFromId: null,
    });
    expect(payload.name).toBe("库存管理系统");
    expect(payload.slug).toBe("库存管理系统");
    expect(payload.category).toBe("inventory");
    expect(payload.template).toBe("table");
    expect(payload.copy_from).toBeNull();
  });

  it("copy 模板时 copy_from 非空", () => {
    const payload = buildCreatePayload({
      name: "复制的模块",
      category: "order",
      description: "",
      template: "copy",
      copyFromId: "mod-001",
    });
    expect(payload.copy_from).toBe("mod-001");
  });

  it("非 copy 模板时 copy_from 始终为 null", () => {
    const payload = buildCreatePayload({
      name: "新模块",
      category: "risk",
      description: "test",
      template: "dashboard",
      copyFromId: "mod-002",
    });
    expect(payload.copy_from).toBeNull();
  });

  it("trim 名称和描述", () => {
    const payload = buildCreatePayload({
      name: "  库存系统  ",
      category: "inventory",
      description: "  管理库存  ",
      template: "blank",
      copyFromId: null,
    });
    expect(payload.name).toBe("库存系统");
    expect(payload.description).toBe("管理库存");
  });
});
