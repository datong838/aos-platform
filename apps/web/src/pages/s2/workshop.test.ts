import { describe, expect, it } from "vitest";

import { buildGraphNodes, resolveObjectSelectionId } from "./workshop";
import {
  buildExplorerSearchParams,
  getExplorerWorkspaceClasses,
  resolveExplorerColumns,
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
      buildExplorerSearchParams("Order", "1", new URLSearchParams("returnTo=%2Fworkshop%2Forders&taskRef=t-1"))
        .toString(),
    ).toBe("type=Order&id=1&returnTo=%2Fworkshop%2Forders&taskRef=t-1");
    expect(
      buildExplorerSearchParams("Order", "1", new URLSearchParams("returnTo=https%3A%2F%2Fevil.example&taskRef=t-1"))
        .toString(),
    ).toBe("type=Order&id=1&taskRef=t-1");
  });
});
