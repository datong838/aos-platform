import { describe, expect, it } from "vitest";
import {
  deriveOtDetailMeta,
  buildOtMetaKvItems,
  buildLinkGraphLayout,
  businessObjectLabel,
  businessDetailItems,
} from "./objectTypeDetail";

describe("objectTypeDetail · deriveOtDetailMeta", () => {
  it("只保留权威响应明确可知的名称，不推导存储治理事实", () => {
    const m = deriveOtDetailMeta("Order", "订单", [
      { name: "orderId", type: "string" },
      { name: "title", type: "string" },
    ]);
    expect(m.apiName).toBe("Order");
    expect(m.displayName).toBe("订单");
    expect(m.rid).toBeUndefined();
    expect(m.primaryKey).toBeUndefined();
    expect(m.backingDataset).toBeUndefined();
    expect(m.pluralName).toBeUndefined();
  });

  it("属性为空时也不伪造主键、标题字段或复数名称", () => {
    const m = deriveOtDetailMeta("Site", "Site", []);
    expect(m.primaryKey).toBeUndefined();
    expect(m.titleKey).toBeUndefined();
    expect(m.pluralName).toBeUndefined();
  });
});

describe("objectTypeDetail · businessObjectLabel", () => {
  it("优先采用服务端水合的业务显示名", () => {
    expect(businessObjectLabel({ id: "internal-1", _displayLabel: "订单 · 20260828001" }, "订单"))
      .toBe("订单 · 20260828001");
  });

  it("从真实业务编码形成可识别标签且不暴露内部 id", () => {
    expect(businessObjectLabel({ id: "internal-1", orderNo: "20260828001" }, "订单"))
      .toBe("订单 · 20260828001");
  });

  it("确无业务标识时使用带顺序的中性占位", () => {
    expect(businessObjectLabel({ id: "internal-1" }, "订单", 2)).toBe("第 3 条业务实例");
  });
});

describe("objectTypeDetail · businessDetailItems", () => {
  it("只把权威业务字段以中文标签放入主视图", () => {
    const items = businessDetailItems({
      id: "internal-1",
      type: "Order",
      orderNo: "20260828001",
      totalAmount: "99.00",
      currency: "CNY",
      memberId: "71",
    });
    expect(items).toEqual([
      { label: "订单号", value: "20260828001" },
      { label: "订单金额", value: "99.00" },
      { label: "币种", value: "CNY" },
      { label: "会员标识", value: "71" },
    ]);
    expect(items.some((item) => item.value === "internal-1" || item.value === "Order")).toBe(false);
  });
});

describe("objectTypeDetail · buildOtMetaKvItems", () => {
  it("只展示当前上下文与权威响应存在的字段", () => {
    const items = buildOtMetaKvItems({
      typeId: "Order",
      typeName: "订单",
      branchId: "main",
      properties: [{ name: "id" }, { name: "title" }],
      funnelStage: "live",
    });
    expect(items).toHaveLength(5);
    const labels = items.map((i) => i.label);
    expect(labels).toContain("对象类型标识");
    expect(labels).not.toContain("资源标识");
    expect(labels).not.toContain("承载数据集");
    expect(items.find((i) => i.label === "业务漏斗")?.value).toBe("已生效");
    expect(items.find((i) => i.label === "业务漏斗")?.tone).toBe("ok");
  });

  it("merges API meta over derived defaults", () => {
    const items = buildOtMetaKvItems({
      typeId: "Order",
      typeName: "订单",
      branchId: "dev",
      meta: { backingDataset: "ds/orders_v2", visibility: "PII" },
    });
    expect(items.find((i) => i.label === "承载数据集")?.value).toBe("ds/orders_v2");
    expect(items.find((i) => i.label === "可见范围")?.value).toBe("PII");
    expect(items.find((i) => i.label === "分支")?.value).toBe("dev");
  });
});

describe("objectTypeDetail · buildLinkGraphLayout", () => {
  it("places center node and neighbor edges", () => {
    const layout = buildLinkGraphLayout("Order", [
      { id: "lt1", srcType: "Order", dstType: "Customer", rel: "placed_by" },
      { id: "lt2", srcType: "Order", dstType: "OrderItem", rel: "has_item" },
    ]);
    expect(layout.nodes.some((n) => n.role === "center" && n.id === "Order")).toBe(true);
    expect(layout.nodes.filter((n) => n.role === "neighbor")).toHaveLength(2);
    expect(layout.edges).toHaveLength(2);
    expect(layout.edges[0].label).toBe("placed_by");
  });

  it("handles empty links with center only", () => {
    const layout = buildLinkGraphLayout("Site", []);
    expect(layout.nodes).toHaveLength(1);
    expect(layout.edges).toHaveLength(0);
  });
});
