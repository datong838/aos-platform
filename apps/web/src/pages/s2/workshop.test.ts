import { describe, expect, it } from "vitest";

import { buildGraphNodes, buildObjectTimeline, resolveObjectSelectionId } from "./workshop";
import {
  buildExplorerSearchParams,
  filterOperationalObjects,
  formatExplorerValue,
  getExplorerWorkspaceClasses,
  resolveExplorerColumns,
  resolveSavedExplorerColumns,
  toggleObjectSelection,
} from "../../components/ontology/ObjectExplorerWorkspace";

describe("O1-UX0 · Object Explorer graph identity", () => {
  it("preserves neighbor type and collision-safe key", () => {
    const graph = buildGraphNodes(
      { id: "1", title: "订单 1" },
      [
        { id: "12", type: "Payment", rel: "Order.hasPayment" },
        { id: "12", type: "OrderLine", rel: "Order.lines" },
      ],
      "Order",
    );

    expect(graph.center).toMatchObject({ key: "Order:1", type: "Order", id: "1" });
    expect(graph.outer).toEqual([
      expect.objectContaining({ key: "Payment:12:Order.hasPayment", type: "Payment", id: "12" }),
      expect.objectContaining({ key: "OrderLine:12:Order.lines", type: "OrderLine", id: "12" }),
    ]);
  });

  it("resolves an authoritative neighbor reference to the target list identity", () => {
    expect(
      resolveObjectSelectionId(
        [{ id: "1" }, { id: "2", _sourceIdentity: { externalId: "niushop:1:2" } }],
        "niushop:1:2",
      ),
    ).toBe("2");
    expect(resolveObjectSelectionId([{ id: "1" }, { id: "2" }], "niushop:1:2")).toBe("2");
  });
});

describe("对象探索 · 权威时间线", () => {
  it("只从对象真实时间字段形成中文时间线", () => {
    expect(buildObjectTimeline({
      createdAt: "2026-08-28T04:55:49Z",
      updatedAt: "2026-08-28T04:56:00Z",
      _sourceUpdatedAt: "2026-08-28T22:00:04Z",
      fakeTime: "2026-01-01",
    })).toEqual([
      { label: "业务记录创建", value: "2026-08-28T04:55:49Z" },
      { label: "业务记录更新", value: "2026-08-28T04:56:00Z" },
      { label: "来源数据同步", value: "2026-08-28T22:00:04Z" },
    ]);
  });

  it("无真实时间字段时保持可信空", () => {
    expect(buildObjectTimeline({ id: "internal-1" })).toEqual([]);
  });
});

describe("O1-UX1 · Object Explorer workspace contracts", () => {
  it("uses composed schema order and metadata instead of the first object row", () => {
    const result = resolveExplorerColumns(
      [
        { name: "status", displayName: "状态", type: "string" },
        { name: "totalAmount", displayName: "金额", type: "number", unit: "CNY" },
        { name: "mobile", displayName: "手机号", type: "string", pii: true },
      ],
      [{ id: "1", title: "订单 1", ignoredOnFirstRow: "x" }],
    );

    expect(result.source).toBe("schema");
    expect(result.schemaIncomplete).toBe(false);
    expect(result.columns).toEqual([
      expect.objectContaining({ key: "id", label: "ID" }),
      expect.objectContaining({ key: "status", label: "状态", type: "string" }),
      expect.objectContaining({ key: "totalAmount", label: "金额", unit: "CNY" }),
      expect.objectContaining({ key: "mobile", label: "手机号", pii: true }),
    ]);
  });

  it("falls back to a stable union of every loaded row when schema properties are missing", () => {
    const result = resolveExplorerColumns(
      {},
      [
        { id: "1", title: "订单 1", status: "paid", _sourceIdentity: {} },
        { id: "2", title: "订单 2", totalAmount: "99.00", createdAt: "2026-08-09" },
      ],
    );

    expect(result.source).toBe("object-union");
    expect(result.schemaIncomplete).toBe(true);
    expect(result.columns.map((column) => column.key)).toEqual([
      "id",
      "title",
      "createdAt",
      "status",
      "totalAmount",
    ]);
  });

  it("uses real canonical Order fields instead of stale demo schema keys", () => {
    const result = resolveExplorerColumns(
      [
        { name: "order_no", type: "string" },
        { name: "customer_name", type: "string" },
        { name: "order_date", type: "string" },
        { name: "total_amount", type: "number" },
      ],
      [{
        id: "niushop:1:1",
        orderNo: "2026012421121001",
        memberId: "1",
        createdAt: "2026-01-24T13:12:34Z",
        totalAmount: "15.00",
        orderStatus: "1",
        payStatus: "1",
        deliveryStatus: "0",
      }],
      "Order",
    );

    expect(result.source).toBe("domain-profile");
    expect(result.columns.map((column) => column.key)).toEqual([
      "id",
      "memberId",
      "createdAt",
      "totalAmount",
      "orderStatus",
      "payStatus",
      "deliveryStatus",
    ]);
    expect(result.columns.map((column) => column.label)).toEqual([
      "订单",
      "会员 ID",
      "下单时间",
      "订单金额",
      "订单状态",
      "支付状态",
      "发货状态",
    ]);
  });

  it("replays an old exploration that explicitly saved the duplicate order number column", () => {
    const defaults = resolveExplorerColumns({}, [{ id: "1", orderNo: "NO-1", createdAt: "2026-01-01" }], "Order").columns;
    const restored = resolveSavedExplorerColumns([
      { key: "id", label: "订单" },
      { key: "orderNo", label: "订单号" },
      { key: "createdAt", label: "下单时间", type: "datetime" },
    ], defaults);
    expect(restored.map((column) => column.key)).toEqual(["id", "orderNo", "createdAt"]);
  });

  it("shows only real Product properties from listed products", () => {
    const result = resolveExplorerColumns(
      {},
      [{
        id: "niushop:1:1",
        title: "显瘦保暖打底裤",
        price: "59.00",
        stock: "20",
        saleNum: "8",
        categoryId: ",1,3,",
        state: "1",
        updatedAt: "2026-01-10T06:12:12Z",
      }],
      "Product",
    );

    expect(result.source).toBe("domain-profile");
    expect(result.columns.map((column) => column.key)).toEqual([
      "id",
      "title",
      "price",
      "stock",
      "saleNum",
      "categoryId",
      "state",
      "updatedAt",
    ]);
  });

  it("keeps only effective online orders and actually listed products", () => {
    expect(filterOperationalObjects("Order", [
      { id: "1", status: "active", isDelete: 0 },
      { id: "2", status: "inactive", isDelete: 0 },
      { id: "3", status: "active", isDelete: 1 },
    ])).toEqual([{ id: "1", status: "active", isDelete: 0 }]);

    expect(filterOperationalObjects("Product", [
      { id: "1", status: "active", isDelete: 0, state: 1 },
      { id: "2", status: "active", isDelete: 0, state: 0 },
      { id: "3", status: "active", isDelete: 1, state: 1 },
    ])).toEqual([{ id: "1", status: "active", isDelete: 0, state: 1 }]);
  });

  it("formats money, time, and commerce statuses without mutating canonical values", () => {
    expect(formatExplorerValue("Order", "totalAmount", "15.00")).toBe("¥15.00");
    expect(formatExplorerValue("Order", "createdAt", "2026-01-24T13:12:34Z")).toContain("2026");
    expect(formatExplorerValue("Order", "payStatus", "1")).toBe("已支付");
    expect(formatExplorerValue("Product", "state", "1")).toBe("已上架");
    expect(formatExplorerValue("Order", "orderNo", "2026012421121001")).toBe("2026012421121001");
  });

  it("keeps row detail selection independent from multi-select state", () => {
    expect(toggleObjectSelection([], "Order:1")).toEqual(["Order:1"]);
    expect(toggleObjectSelection(["Order:1", "Order:2"], "Order:1")).toEqual(["Order:2"]);
  });

  it("derives honest workspace classes for drawer and focus mode", () => {
    expect(getExplorerWorkspaceClasses({ detailOpen: true, focusMode: false })).toContain(
      "has-detail",
    );
    expect(getExplorerWorkspaceClasses({ detailOpen: false, focusMode: true })).toContain(
      "is-focus",
    );
  });

  it("preserves only safe in-app deep-link context", () => {
    expect(
      buildExplorerSearchParams("Order", "1", new URLSearchParams("returnTo=%2Fworkshop%2Forders&taskRef=t-1&shareRef=opaque_share_ref_123456"))
        .toString(),
    ).toBe("type=Order&id=1&returnTo=%2Fworkshop%2Forders&taskRef=t-1&shareRef=opaque_share_ref_123456");
    expect(
      buildExplorerSearchParams("Order", "1", new URLSearchParams("returnTo=https%3A%2F%2Fevil.example&taskRef=t-1"))
        .toString(),
    ).toBe("type=Order&id=1&taskRef=t-1");
    expect(
      buildExplorerSearchParams("Order", "1", new URLSearchParams("shareRef=%3Cscript%3E"))
        .toString(),
    ).toBe("type=Order&id=1");
  });
});
