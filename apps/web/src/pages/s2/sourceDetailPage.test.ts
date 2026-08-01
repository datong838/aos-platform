/**
 * W3-C7 · sourceDetailPage 纯函数单测
 */
import { describe, it, expect } from "vitest";
import {
  demoSchemaTree,
  applySchemaTree,
  filterSchemaTree,
  flattenTables,
  schemaPathLabel,
  formatColumnBadge,
  type SchemaNode,
} from "./sourceDetailPage";

describe("W3-C7 demoSchemaTree", () => {
  it("returns jdbc-like public/analytics for default", () => {
    const tree = demoSchemaTree("jdbc");
    expect(tree.some((s) => s.name === "public")).toBe(true);
    expect(flattenTables(tree).some((t) => t.table === "orders")).toBe(true);
  });

  it("returns topics for kafka/stream", () => {
    const tree = demoSchemaTree("kafka");
    expect(tree[0].name).toBe("topics");
    expect(tree[0].tables[0].name).toBe("events");
  });

  it("returns bucket for file/s3", () => {
    const tree = demoSchemaTree("s3");
    expect(tree[0].name).toBe("bucket");
  });
});

describe("W3-C7 filterSchemaTree", () => {
  const sample: SchemaNode[] = [
    {
      name: "public",
      tables: [
        { name: "orders", columns: [{ name: "order_id", datatype: "BIGINT", primary_key: true }] },
        { name: "customers", columns: [{ name: "name", datatype: "VARCHAR" }] },
      ],
    },
    { name: "analytics", tables: [{ name: "events" }] },
  ];

  it("empty query returns all", () => {
    expect(filterSchemaTree(sample, "").length).toBe(2);
  });

  it("filters by table name", () => {
    const f = filterSchemaTree(sample, "order");
    expect(f.length).toBe(1);
    expect(f[0].tables.map((t) => t.name)).toEqual(["orders"]);
  });

  it("filters by column name", () => {
    const f = filterSchemaTree(sample, "order_id");
    expect(f[0].tables[0].name).toBe("orders");
  });
});

describe("W3-C7 flattenTables / badges", () => {
  it("flattens schema.table", () => {
    const flat = flattenTables(demoSchemaTree("postgres"));
    expect(flat.length).toBeGreaterThanOrEqual(3);
    expect(flat[0]).toHaveProperty("schema");
    expect(flat[0]).toHaveProperty("table");
  });

  it("formatColumnBadge", () => {
    expect(formatColumnBadge({ name: "id", datatype: "BIGINT", primary_key: true })).toContain("PK");
    expect(formatColumnBadge({ name: "x", datatype: "VARCHAR", nullable: true })).toContain("NULL");
  });

  it("schemaPathLabel", () => {
    expect(schemaPathLabel(true)).toBe("演示路径");
    expect(schemaPathLabel(false)).toBe("连接器 Schema");
  });
});

describe("Wave 3C W1 · applySchemaTree", () => {
  it("统一同步首表、列、展开状态与来源", () => {
    const tree: SchemaNode[] = [{
      name: "fresh",
      tables: [{ name: "orders", columns: [{ name: "id", datatype: "BIGINT" }] }],
    }];
    const applied = applySchemaTree(tree, { mode: "live" });
    expect(applied.schemaTree).toBe(tree);
    expect(applied.expandedSchemas).toEqual({ fresh: true });
    expect(applied.activeSchemaTable).toEqual({ schema: "fresh", table: "orders" });
    expect(applied.activeColumns).toEqual([{ name: "id", datatype: "BIGINT" }]);
    expect(applied.source).toEqual({ mode: "live" });
    expect(applied.clearPreview).toBe(false);
  });

  it("空树清除旧选择、列与 preview", () => {
    const source = { mode: "fallback" as const, primaryError: "schema failed" };
    const applied = applySchemaTree([], source);
    expect(applied.schemaTree).toEqual([]);
    expect(applied.expandedSchemas).toEqual({});
    expect(applied.activeSchemaTable).toBeNull();
    expect(applied.activeColumns).toEqual([]);
    expect(applied.source).toEqual(source);
    expect(applied.clearPreview).toBe(true);
  });
});
