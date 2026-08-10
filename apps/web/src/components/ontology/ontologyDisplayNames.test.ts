import { describe, expect, it } from "vitest";

import {
  getObjectDisplayLabel,
  getObjectTypeDisplayName,
  getRelationTypeDisplayName,
  getSourceIdentityLabel,
  getSourceRecordLabel,
} from "./ontologyDisplayNames";

describe("O1-UX8 · readable commerce object labels", () => {
  it("uses the server display projection while preserving the canonical id", () => {
    const order = {
      id: "niushop:1:20",
      orderNo: "2026030723225001",
      _displayLabel: "订单 · 2026030723225001",
      _sourceRecordLabel: "源记录 #20",
      _sourceIdentityLabel: "Niushop 微商城 · 站点 1 · 源记录 #20",
    };

    expect(getObjectDisplayLabel("Order", order)).toBe("订单 · 2026030723225001");
    expect(getSourceRecordLabel(order)).toBe("源记录 #20");
    expect(getSourceIdentityLabel(order)).toContain("站点 1");
    expect(order.id).toBe("niushop:1:20");
  });

  it("falls back to readable Chinese text without guessing a business key", () => {
    expect(getObjectDisplayLabel("Payment", { id: "niushop:1:16" })).toBe(
      "支付记录 · 源记录 #16",
    );
    expect(getObjectDisplayLabel("UnknownType", { id: "opaque-id" })).toBe(
      "UnknownType · 系统记录 opaque-id",
    );
  });

  it("translates graph type and relation labels without changing identifiers", () => {
    expect(getObjectTypeDisplayName("OrderLine")).toBe("订单明细");
    expect(getRelationTypeDisplayName("Order.hasPayment")).toBe("订单对应支付记录");
    expect(getRelationTypeDisplayName("Unknown.rel")).toBe("Unknown.rel");
  });
});
