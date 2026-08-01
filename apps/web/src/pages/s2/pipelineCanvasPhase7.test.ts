/**
 * Phase 7 · 管道编辑器增强逻辑测试
 * 测试 OPERATORS/PIPE_TYPES/WRITE_MODES 数据结构和推断函数
 */
import { describe, it, expect } from "vitest";
import { OPERATORS, PIPE_TYPES, WRITE_MODES, inferColumnType, cellText } from "./pipelineCanvas";

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
