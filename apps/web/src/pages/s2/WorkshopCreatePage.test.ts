import { describe, expect, it } from "vitest";
import {
  STEPS,
  DOMAINS,
  TEMPLATES,
  OBJ_GROUPS,
  slugify,
  canFinishCreate,
  defaultBoundProps,
  buildCreatePayload,
} from "./WorkshopCreatePage";

describe("WorkshopCreatePage · STEPS 步骤定义", () => {
  it("恰好 4 步（对齐 workshop-create.html）", () => {
    expect(STEPS.length).toBe(4);
  });

  it("步骤含 basic/binding/template/confirm", () => {
    expect(STEPS.map((s) => s.key)).toEqual(["basic", "binding", "template", "confirm"]);
  });

  it("标题对齐视觉稿", () => {
    expect(STEPS.map((s) => s.title)).toEqual(["基本信息", "数据绑定", "模板选择", "确认创建"]);
  });
});

describe("WorkshopCreatePage · DOMAINS 业务域", () => {
  it("包含视觉稿六域", () => {
    expect(DOMAINS).toEqual(["运营", "分析", "风控", "供应链", "客服", "自定义"]);
  });
});

describe("WorkshopCreatePage · TEMPLATES 模板", () => {
  it("包含 4 个模板（空白/表格/仪表盘/对象探索）", () => {
    expect(TEMPLATES.length).toBe(4);
    expect(TEMPLATES.map((t) => t.id)).toEqual(["blank", "table", "dashboard", "explorer"]);
  });

  it("默认推荐为表格列表模板（视觉稿 is-selected）", () => {
    expect(TEMPLATES.find((t) => t.id === "table")?.name).toBe("表格列表模板");
  });
});

describe("WorkshopCreatePage · 数据绑定对象", () => {
  it("业务+用户两组", () => {
    expect(OBJ_GROUPS.map((g) => g.title)).toEqual(["业务对象", "用户对象"]);
  });

  it("Order 默认绑定 5 个属性", () => {
    expect(defaultBoundProps("Order")).toEqual([
      "order_id",
      "customer_name",
      "total_amount",
      "status",
      "created_at",
    ]);
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

describe("WorkshopCreatePage · canFinishCreate", () => {
  it("名称非空 → true", () => {
    expect(canFinishCreate("库存系统")).toBe(true);
  });

  it("名称为空 → false", () => {
    expect(canFinishCreate("")).toBe(false);
    expect(canFinishCreate("   ")).toBe(false);
  });
});

describe("WorkshopCreatePage · buildCreatePayload", () => {
  it("生成完整 payload", () => {
    const payload = buildCreatePayload({
      name: "库存管理系统",
      domain: "供应链",
      icon: "box",
      description: "管理仓库库存",
      objectType: "Order",
      boundProps: ["order_id", "status"],
      template: "table",
    });
    expect(payload.name).toBe("库存管理系统");
    expect(payload.slug).toBe("库存管理系统");
    expect(payload.domain).toBe("供应链");
    expect(payload.icon).toBe("box");
    expect(payload.object_type).toBe("Order");
    expect(payload.bound_props).toEqual(["order_id", "status"]);
    expect(payload.template).toBe("table");
  });

  it("trim 名称和描述", () => {
    const payload = buildCreatePayload({
      name: "  库存系统  ",
      domain: "运营",
      icon: "chart",
      description: "  管理库存  ",
      objectType: "Inventory",
      boundProps: ["sku"],
      template: "blank",
    });
    expect(payload.name).toBe("库存系统");
    expect(payload.description).toBe("管理库存");
  });
});
