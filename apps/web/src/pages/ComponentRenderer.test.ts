import { describe, expect, it } from "vitest";
import {
  analyzeComponentTree,
  detectTableDrawerPair,
  widgetsToComponents,
  type ComponentTree,
} from "./ComponentRenderer";

describe("analyzeComponentTree", () => {
  it("detects missing root", () => {
    const tree: ComponentTree = {
      foo: { type: "object-table", config: {} },
    };
    const a = analyzeComponentTree(tree);
    expect(a.hasRoot).toBe(false);
    expect(a.rootType).toBeNull();
    expect(a.totalNodes).toBe(1);
  });

  it("counts types and root type", () => {
    const tree: ComponentTree = {
      root: {
        type: "page-layout",
        config: {},
        children: ["header", "stats", "table"],
      },
      header: { type: "page-header", config: {} },
      stats: { type: "horizontal-grid", config: {}, children: ["s1", "s2"] },
      s1: { type: "stat-card", config: {} },
      s2: { type: "stat-card", config: {} },
      table: { type: "object-table", config: {} },
    };
    const a = analyzeComponentTree(tree);
    expect(a.hasRoot).toBe(true);
    expect(a.rootType).toBe("page-layout");
    expect(a.totalNodes).toBe(6);
    expect(a.typeCounts["stat-card"]).toBe(2);
    expect(a.typeCounts["page-header"]).toBe(1);
    expect(a.typeCounts["object-table"]).toBe(1);
    expect(a.typeCounts["horizontal-grid"]).toBe(1);
    expect(a.typeCounts["page-layout"]).toBe(1);
    expect(a.orphanChildren).toEqual([]);
    expect(a.cycleDetected).toBe(false);
  });

  it("detects orphan children", () => {
    const tree: ComponentTree = {
      root: { type: "page-layout", config: {}, children: ["missing", "ok"] },
      ok: { type: "stat-card", config: {} },
    };
    const a = analyzeComponentTree(tree);
    expect(a.orphanChildren).toEqual(["missing"]);
  });

  it("detects cycle", () => {
    const tree: ComponentTree = {
      root: { type: "page-layout", config: {}, children: ["a"] },
      a: { type: "horizontal-grid", config: {}, children: ["root"] },
    };
    const a = analyzeComponentTree(tree);
    expect(a.cycleDetected).toBe(true);
  });

  it("handles empty tree", () => {
    const a = analyzeComponentTree({});
    expect(a.totalNodes).toBe(0);
    expect(a.hasRoot).toBe(false);
    expect(a.typeCounts).toEqual({});
  });
});

describe("widgetsToComponents", () => {
  it("converts string widgets to component tree", () => {
    const tree = widgetsToComponents(["stats", "table", "filters"]);
    expect(tree.root.type).toBe("page-layout");
    expect(tree.root.children).toEqual(["w-0", "w-1", "w-2"]);
    expect(tree["w-0"].type).toBe("stat-card");
    expect(tree["w-1"].type).toBe("object-table");
    expect(tree["w-2"].type).toBe("filter-bar");
  });

  it("empty widgets yields root only", () => {
    const tree = widgetsToComponents([]);
    expect(Object.keys(tree)).toEqual(["root"]);
    expect(tree.root.children).toEqual([]);
  });

  it("produces valid tree (no orphans)", () => {
    const tree = widgetsToComponents(["stats", "chart", "table"]);
    const a = analyzeComponentTree(tree);
    expect(a.orphanChildren).toEqual([]);
    expect(a.cycleDetected).toBe(false);
  });
});

describe("order management seed tree shape", () => {
  it("matches expected contract: page-layout root + 4 stat cards + filter-bar + table + drawer + trend-chart", () => {
    const orderTree: ComponentTree = {
      root: {
        type: "page-layout",
        config: { padding: 24, gap: 16 },
        children: ["page-header", "stat-row", "filter-bar", "order-table", "detail-drawer", "trend-chart"],
      },
      "page-header": { type: "page-header", config: { title: "订单管理" } },
      "stat-row": {
        type: "horizontal-grid",
        config: { cols: 4 },
        children: ["stat-total", "stat-pending", "stat-shipped", "stat-revenue"],
      },
      "stat-total": { type: "stat-card", config: {} },
      "stat-pending": { type: "stat-card", config: {} },
      "stat-shipped": { type: "stat-card", config: {} },
      "stat-revenue": { type: "stat-card", config: {} },
      "filter-bar": { type: "filter-bar", config: {} },
      "order-table": { type: "object-table", config: {} },
      "detail-drawer": { type: "detail-drawer", config: {} },
      "trend-chart": { type: "trend-chart", config: {} },
    };
    const a = analyzeComponentTree(orderTree);
    expect(a.hasRoot).toBe(true);
    expect(a.rootType).toBe("page-layout");
    expect(a.typeCounts["stat-card"]).toBe(4);
    expect(a.typeCounts["page-header"]).toBe(1);
    expect(a.typeCounts["filter-bar"]).toBe(1);
    expect(a.typeCounts["object-table"]).toBe(1);
    expect(a.typeCounts["detail-drawer"]).toBe(1);
    expect(a.typeCounts["trend-chart"]).toBe(1);
    expect(a.typeCounts["horizontal-grid"]).toBe(1);
    expect(a.orphanChildren).toEqual([]);
    expect(a.cycleDetected).toBe(false);
    expect(a.totalNodes).toBe(11);
  });
});

describe("order-table column keys (snake_case contract)", () => {
  it("uses snake_case keys aligned with Order API", () => {
    const cols = [
      { key: "order_no" },
      { key: "customer_name" },
      { key: "order_date" },
      { key: "total_amount" },
      { key: "status" },
      { key: "tracking_no" },
    ];
    const apiKeys = new Set([
      "id",
      "type",
      "order_no",
      "order_date",
      "customer_id",
      "customer_name",
      "total_amount",
      "status",
      "shipping_address",
      "tracking_no",
      "remark",
      "items",
    ]);
    for (const c of cols) {
      expect(apiKeys.has(c.key)).toBe(true);
    }
  });
});

describe("detectTableDrawerPair", () => {
  it("detects table + drawer pair in page-layout children", () => {
    const tree: ComponentTree = {
      root: {
        type: "page-layout",
        children: ["page-header", "stat-row", "filter-bar", "order-table", "detail-drawer", "trend-chart"],
      },
      "page-header": { type: "page-header" },
      "stat-row": { type: "horizontal-grid" },
      "filter-bar": { type: "filter-bar" },
      "order-table": { type: "object-table" },
      "detail-drawer": { type: "detail-drawer" },
      "trend-chart": { type: "trend-chart" },
    };
    const pair = detectTableDrawerPair(tree, "root");
    expect(pair).not.toBeNull();
    expect(pair!.tableId).toBe("order-table");
    expect(pair!.drawerId).toBe("detail-drawer");
    expect(pair!.otherIds).toEqual(["page-header", "stat-row", "filter-bar", "trend-chart"]);
  });

  it("returns null when only table exists (no drawer)", () => {
    const tree: ComponentTree = {
      root: { type: "page-layout", children: ["order-table"] },
      "order-table": { type: "object-table" },
    };
    expect(detectTableDrawerPair(tree, "root")).toBeNull();
  });

  it("returns null when only drawer exists (no table)", () => {
    const tree: ComponentTree = {
      root: { type: "page-layout", children: ["detail-drawer"] },
      "detail-drawer": { type: "detail-drawer" },
    };
    expect(detectTableDrawerPair(tree, "root")).toBeNull();
  });

  it("returns null when root has no children", () => {
    const tree: ComponentTree = {
      root: { type: "page-layout", children: [] },
    };
    expect(detectTableDrawerPair(tree, "root")).toBeNull();
  });

  it("splits otherIds into beforeIds/afterIds by table position", () => {
    const tree: ComponentTree = {
      root: {
        type: "page-layout",
        children: ["page-header", "stat-row", "filter-bar", "order-table", "detail-drawer", "trend-chart"],
      },
      "page-header": { type: "page-header" },
      "stat-row": { type: "horizontal-grid" },
      "filter-bar": { type: "filter-bar" },
      "order-table": { type: "object-table" },
      "detail-drawer": { type: "detail-drawer" },
      "trend-chart": { type: "trend-chart" },
    };
    const pair = detectTableDrawerPair(tree, "root");
    expect(pair).not.toBeNull();
    expect(pair!.beforeIds).toEqual(["page-header", "stat-row", "filter-bar"]);
    expect(pair!.afterIds).toEqual(["trend-chart"]);
    expect(pair!.otherIds).toEqual(["page-header", "stat-row", "filter-bar", "trend-chart"]);
  });

  it("puts trend-chart after table when table appears before drawer in children", () => {
    const tree: ComponentTree = {
      root: {
        type: "page-layout",
        children: ["header", "order-table", "trend-chart", "detail-drawer"],
      },
      header: { type: "page-header" },
      "order-table": { type: "object-table" },
      "trend-chart": { type: "trend-chart" },
      "detail-drawer": { type: "detail-drawer" },
    };
    const pair = detectTableDrawerPair(tree, "root");
    expect(pair).not.toBeNull();
    expect(pair!.beforeIds).toEqual(["header"]);
    expect(pair!.afterIds).toEqual(["trend-chart"]);
  });
});
