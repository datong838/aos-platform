import { describe, expect, it } from "vitest";
import {
  deriveOtDetailMeta,
  buildOtMetaKvItems,
  buildLinkGraphLayout,
} from "./objectTypeDetail";

describe("objectTypeDetail · deriveOtDetailMeta", () => {
  it("derives PK/TitleKey/RID from properties", () => {
    const m = deriveOtDetailMeta("Order", "订单", [
      { name: "orderId", type: "string" },
      { name: "title", type: "string" },
    ]);
    expect(m.rid).toBe("ri.ontology.main.object-type.order");
    expect(m.primaryKey).toBe("orderId");
    expect(m.titleKey).toBe("title");
    expect(m.backingDataset).toBe("ds/order");
    expect(m.pluralName).toBe("订单s");
  });

  it("falls back when properties empty", () => {
    const m = deriveOtDetailMeta("Site", "Site", []);
    expect(m.primaryKey).toBe("id");
    expect(m.titleKey).toBe("id");
    expect(m.pluralName).toBe("Sites");
  });
});

describe("objectTypeDetail · buildOtMetaKvItems", () => {
  it("returns at least 12 KV items toward visual draft", () => {
    const items = buildOtMetaKvItems({
      typeId: "Order",
      typeName: "订单",
      branchId: "main",
      properties: [{ name: "id" }, { name: "title" }],
      funnelStage: "live",
    });
    expect(items.length).toBeGreaterThanOrEqual(12);
    const labels = items.map((i) => i.label);
    expect(labels).toContain("RID");
    expect(labels).toContain("PK");
    expect(labels).toContain("TitleKey");
    expect(labels).toContain("BackingDataset");
    expect(labels).toContain("Sync 策略");
    expect(labels).toContain("可见性");
    expect(items.find((i) => i.label === "管道")?.tone).toBe("ok");
  });

  it("merges API meta over derived defaults", () => {
    const items = buildOtMetaKvItems({
      typeId: "Order",
      typeName: "订单",
      branchId: "dev",
      meta: { backingDataset: "ds/orders_v2", visibility: "PII" },
    });
    expect(items.find((i) => i.label === "BackingDataset")?.value).toBe("ds/orders_v2");
    expect(items.find((i) => i.label === "可见性")?.value).toBe("PII");
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
