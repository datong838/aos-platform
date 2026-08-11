import { describe, expect, it } from "vitest";
import {
  buildLegacyActionDraftRequest,
  computeOrderFunnel,
  filterRiskyOrders,
  filterOverdueShipments,
  type OrderObject,
  type ShipmentObject,
} from "./OrderManagementPage";

describe("OrderManagementPage · legacy Action 兼容边界", () => {
  it("只创建待审草稿，禁止 autoApprove", () => {
    expect(buildLegacyActionDraftRequest("CancelOrder", "order-1", { reason: "用户取消" })).toEqual({
      actionTypeId: "CancelOrder",
      objectType: "Order",
      objectId: "order-1",
      proposed: { reason: "用户取消" },
      autoApprove: false,
    });
  });
});

function makeOrder(overrides: Partial<OrderObject> = {}): OrderObject {
  return { id: "o-default", ...overrides };
}

function makeShipment(overrides: Partial<ShipmentObject> = {}): ShipmentObject {
  return { id: "s-default", ...overrides };
}

describe("OrderManagementPage · computeOrderFunnel", () => {
  it("聚合 total/pending/shipped/delivered 四桶", () => {
    const orders: OrderObject[] = [
      makeOrder({ id: "1", status: "pending" }),
      makeOrder({ id: "2", status: "shipped" }),
      makeOrder({ id: "3", status: "delivered" }),
      makeOrder({ id: "4", status: "cancelled" }),
    ];
    const funnel = computeOrderFunnel(orders);
    expect(funnel.total).toBe(4);
    expect(funnel.pending).toBe(1);
    expect(funnel.shipped).toBe(1);
    expect(funnel.delivered).toBe(1);
  });

  it("空数组返回全 0", () => {
    expect(computeOrderFunnel([])).toEqual({
      total: 0,
      pending: 0,
      shipped: 0,
      delivered: 0,
    });
  });

  it("status 缺失不计入任何桶但计入 total", () => {
    const orders: OrderObject[] = [
      makeOrder({ id: "1" }),
      makeOrder({ id: "2", status: "pending" }),
    ];
    const funnel = computeOrderFunnel(orders);
    expect(funnel.total).toBe(2);
    expect(funnel.pending).toBe(1);
    expect(funnel.shipped).toBe(0);
    expect(funnel.delivered).toBe(0);
  });
});

describe("OrderManagementPage · filterRiskyOrders", () => {
  it("只返回 risk_score > 0.6 的订单", () => {
    const orders: OrderObject[] = [
      makeOrder({ id: "1", risk_score: 0.7 }),
      makeOrder({ id: "2", risk_score: 0.3 }),
      makeOrder({ id: "3", risk_score: 0.9 }),
    ];
    const risky = filterRiskyOrders(orders);
    expect(risky).toHaveLength(2);
    expect(risky.map((o) => o.id).sort()).toEqual(["1", "3"]);
  });

  it("risk_score === 0.6 不返回（严格大于）", () => {
    const orders: OrderObject[] = [
      makeOrder({ id: "1", risk_score: 0.6 }),
      makeOrder({ id: "2", risk_score: 0.61 }),
    ];
    const risky = filterRiskyOrders(orders);
    expect(risky).toHaveLength(1);
    expect(risky[0].id).toBe("2");
  });

  it("risk_score === null 不返回（null 安全降级）", () => {
    const orders: OrderObject[] = [
      makeOrder({ id: "1", risk_score: null }),
      makeOrder({ id: "2", risk_score: 0.8 }),
    ];
    const risky = filterRiskyOrders(orders);
    expect(risky).toHaveLength(1);
    expect(risky[0].id).toBe("2");
  });

  it("risk_score 缺失不返回", () => {
    const orders: OrderObject[] = [
      makeOrder({ id: "1" }),
      makeOrder({ id: "2", risk_score: 0.7 }),
    ];
    const risky = filterRiskyOrders(orders);
    expect(risky).toHaveLength(1);
    expect(risky[0].id).toBe("2");
  });

  it("不修改原数组", () => {
    const orders: OrderObject[] = [
      makeOrder({ id: "1", risk_score: 0.7 }),
      makeOrder({ id: "2", risk_score: 0.3 }),
    ];
    const snapshot = JSON.parse(JSON.stringify(orders));
    filterRiskyOrders(orders);
    expect(JSON.parse(JSON.stringify(orders))).toEqual(snapshot);
  });

  it("空数组返回空", () => {
    expect(filterRiskyOrders([])).toEqual([]);
  });
});

describe("OrderManagementPage · filterOverdueShipments", () => {
  it("只返回 overdue_hours > 0 的运单", () => {
    const shipments: ShipmentObject[] = [
      makeShipment({ id: "1", overdue_hours: 10 }),
      makeShipment({ id: "2", overdue_hours: 0 }),
      makeShipment({ id: "3", overdue_hours: 48 }),
    ];
    const overdue = filterOverdueShipments(shipments);
    expect(overdue).toHaveLength(2);
    expect(overdue.map((s) => s.id).sort()).toEqual(["1", "3"]);
  });

  it("overdue_hours === null 不返回（null 安全降级）", () => {
    const shipments: ShipmentObject[] = [
      makeShipment({ id: "1", overdue_hours: null }),
      makeShipment({ id: "2", overdue_hours: 5 }),
    ];
    const overdue = filterOverdueShipments(shipments);
    expect(overdue).toHaveLength(1);
    expect(overdue[0].id).toBe("2");
  });

  it("overdue_hours 缺失不返回", () => {
    const shipments: ShipmentObject[] = [
      makeShipment({ id: "1" }),
      makeShipment({ id: "2", overdue_hours: 1 }),
    ];
    const overdue = filterOverdueShipments(shipments);
    expect(overdue).toHaveLength(1);
    expect(overdue[0].id).toBe("2");
  });

  it("不修改原数组", () => {
    const shipments: ShipmentObject[] = [
      makeShipment({ id: "1", overdue_hours: 10 }),
      makeShipment({ id: "2", overdue_hours: 0 }),
    ];
    const snapshot = JSON.parse(JSON.stringify(shipments));
    filterOverdueShipments(shipments);
    expect(JSON.parse(JSON.stringify(shipments))).toEqual(snapshot);
  });

  it("空数组返回空", () => {
    expect(filterOverdueShipments([])).toEqual([]);
  });
});
