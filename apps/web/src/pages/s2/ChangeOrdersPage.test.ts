import { describe, expect, it } from "vitest";
import { MOCK_CHANGE_ORDERS, STATUS_TABS } from "./ChangeOrdersPage";

describe("ChangeOrdersPage · MOCK_CHANGE_ORDERS 数据", () => {
  it("有 3 条变更单", () => {
    expect(MOCK_CHANGE_ORDERS).toHaveLength(3);
  });

  it("每条变更单有完整字段", () => {
    for (const o of MOCK_CHANGE_ORDERS) {
      expect(o.id.length).toBeGreaterThan(0);
      expect(o.type.length).toBeGreaterThan(0);
      expect(["pending", "approved", "rejected"]).toContain(o.status);
      expect(o.applicant.length).toBeGreaterThan(0);
      expect(o.description.length).toBeGreaterThan(0);
      expect(o.approvals).toBeInstanceOf(Array);
    }
  });

  it("包含 pending/approved/rejected 三种状态", () => {
    const statuses = new Set(MOCK_CHANGE_ORDERS.map((o) => o.status));
    expect(statuses.has("pending")).toBe(true);
    expect(statuses.has("approved")).toBe(true);
    expect(statuses.has("rejected")).toBe(true);
  });

  it("每条变更单有审批流（approvals）", () => {
    for (const o of MOCK_CHANGE_ORDERS) {
      expect(o.approvals.length).toBeGreaterThanOrEqual(2);
      for (const a of o.approvals) {
        expect(["done", "pending", "rejected"]).toContain(a.status);
      }
    }
  });

  it("每条变更单有目标 Spoke 和 Bundle 版本", () => {
    for (const o of MOCK_CHANGE_ORDERS) {
      expect(o.targetSpoke.length).toBeGreaterThan(0);
      expect(o.bundleVersion.length).toBeGreaterThan(0);
    }
  });
});

describe("ChangeOrdersPage · STATUS_TABS", () => {
  it("有 4 个状态标签", () => {
    expect(STATUS_TABS).toHaveLength(4);
  });

  it("包含 all/pending/approved/rejected", () => {
    const ids = STATUS_TABS.map((t) => t.id);
    expect(ids).toContain("all");
    expect(ids).toContain("pending");
    expect(ids).toContain("approved");
    expect(ids).toContain("rejected");
  });
});
