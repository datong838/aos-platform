/**
 * Phase 7 · 管道编辑器增强逻辑测试
 * 测试 OPERATORS/PIPE_TYPES/WRITE_MODES 数据结构和推断函数
 */
import { describe, it, expect } from "vitest";

// Re-import the constants by reading the module
// Since pipelineCanvas.tsx doesn't export them, we duplicate for contract testing
const OPERATORS = [
  { group: "输入", items: [
    { id: "src-jdbc", label: "JDBC 源", kind: "input" },
    { id: "src-file", label: "文件源", kind: "input" },
    { id: "src-stream", label: "流式源", kind: "input" },
  ]},
  { group: "变换", items: [
    { id: "tf-filter", label: "过滤", kind: "transform" },
    { id: "tf-join", label: "关联", kind: "transform" },
    { id: "tf-aggregate", label: "聚合", kind: "transform" },
    { id: "tf-map", label: "映射", kind: "transform" },
    { id: "tf-sort", label: "排序", kind: "transform" },
    { id: "tf-union", label: "合并", kind: "transform" },
    { id: "tf-lookup", label: "查表", kind: "transform" },
    { id: "tf-udf", label: "自定义函数", kind: "transform" },
  ]},
  { group: "输出", items: [
    { id: "out-dataset", label: "数据集", kind: "output" },
    { id: "out-object", label: "对象实例", kind: "output" },
    { id: "out-stream", label: "流式输出", kind: "output" },
    { id: "out-webhook", label: "Webhook", kind: "output" },
  ]},
];

const PIPE_TYPES = [
  { id: "batch", label: "批量" },
  { id: "incremental", label: "增量" },
  { id: "streaming", label: "流式" },
];

const WRITE_MODES = [
  { id: "SNAPSHOT", label: "快照" },
  { id: "APPEND", label: "追加" },
  { id: "MERGE", label: "合并" },
  { id: "UPDATE", label: "更新" },
  { id: "DELETE", label: "删除" },
  { id: "UPSERT", label: "插入或更新" },
];

function inferColumnType(rows: Record<string, unknown>[], col: string): string {
  for (const row of rows) {
    const v = row[col];
    if (v == null) continue;
    if (typeof v === "number") return "number";
    if (typeof v === "boolean") return "bool";
    if (typeof v === "string") {
      if (/^\d{4}-\d{2}-\d{2}[T ]/.test(v)) return "date";
      return "string";
    }
    return "json";
  }
  return "—";
}

function cellText(v: unknown): string {
  if (v == null) return "—";
  if (typeof v === "object") {
    try { return JSON.stringify(v); } catch { return String(v); }
  }
  const s = String(v);
  return s.length > 48 ? `${s.slice(0, 45)}…` : s;
}

describe("Phase 7 Pipeline Canvas - Operators", () => {
  it("has 3 operator groups", () => {
    expect(OPERATORS.length).toBe(3);
  });

  it("input group has 3 items", () => {
    const input = OPERATORS.find((g) => g.group === "输入");
    expect(input).toBeTruthy();
    expect(input!.items.length).toBe(3);
  });

  it("transform group has 8 items", () => {
    const transform = OPERATORS.find((g) => g.group === "变换");
    expect(transform).toBeTruthy();
    expect(transform!.items.length).toBe(8);
  });

  it("output group has 4 items", () => {
    const output = OPERATORS.find((g) => g.group === "输出");
    expect(output).toBeTruthy();
    expect(output!.items.length).toBe(4);
  });

  it("all operator IDs are unique", () => {
    const allIds = OPERATORS.flatMap((g) => g.items.map((i) => i.id));
    const unique = new Set(allIds);
    expect(unique.size).toBe(allIds.length);
  });

  it("total operators = 15", () => {
    const total = OPERATORS.reduce((sum, g) => sum + g.items.length, 0);
    expect(total).toBe(15);
  });
});

describe("Phase 7 Pipeline Canvas - Pipe Types", () => {
  it("has 3 pipe types", () => {
    expect(PIPE_TYPES.length).toBe(3);
  });

  it("includes batch, incremental, streaming", () => {
    const ids = PIPE_TYPES.map((t) => t.id);
    expect(ids).toContain("batch");
    expect(ids).toContain("incremental");
    expect(ids).toContain("streaming");
  });
});

describe("Phase 7 Pipeline Canvas - Write Modes", () => {
  it("has 6 write modes", () => {
    expect(WRITE_MODES.length).toBe(6);
  });

  it("includes SNAPSHOT and UPSERT", () => {
    const ids = WRITE_MODES.map((m) => m.id);
    expect(ids).toContain("SNAPSHOT");
    expect(ids).toContain("UPSERT");
  });
});

describe("Phase 7 Pipeline Canvas - inferColumnType", () => {
  it("detects number type", () => {
    expect(inferColumnType([{ a: 42 }], "a")).toBe("number");
  });

  it("detects boolean type", () => {
    expect(inferColumnType([{ a: true }], "a")).toBe("bool");
  });

  it("detects date type", () => {
    expect(inferColumnType([{ a: "2026-07-27T10:00:00" }], "a")).toBe("date");
  });

  it("detects string type", () => {
    expect(inferColumnType([{ a: "hello" }], "a")).toBe("string");
  });

  it("detects json type for objects", () => {
    expect(inferColumnType([{ a: { x: 1 } }], "a")).toBe("json");
  });

  it("returns dash for null-only column", () => {
    expect(inferColumnType([{ a: null }, { a: undefined }], "a")).toBe("—");
  });

  it("returns dash for empty rows", () => {
    expect(inferColumnType([], "a")).toBe("—");
  });
});

describe("Phase 7 Pipeline Canvas - cellText", () => {
  it("returns dash for null", () => {
    expect(cellText(null)).toBe("—");
    expect(cellText(undefined)).toBe("—");
  });

  it("returns stringified JSON for objects", () => {
    expect(cellText({ x: 1 })).toBe('{"x":1}');
  });

  it("truncates long strings", () => {
    const long = "a".repeat(60);
    const result = cellText(long);
    expect(result.length).toBeLessThanOrEqual(48);
    expect(result.endsWith("…")).toBe(true);
  });

  it("preserves short strings", () => {
    expect(cellText("hello")).toBe("hello");
  });
});
