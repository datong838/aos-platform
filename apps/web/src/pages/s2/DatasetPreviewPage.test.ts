import { describe, expect, it } from "vitest";
import {
  TYPE_LABELS,
  TYPE_TONE,
  formatBytes,
  formatNumber,
  formatTimestamp,
  formatNullRate,
  sortRows,
  filterRows,
  filterColumns,
  numericColumns,
  computeColumnStats,
  toCsv,
  nextSortDir,
  type ColumnInfo,
  type DatasetRow,
  type SortState,
} from "./DatasetPreviewPage";

const MOCK_COLS: ColumnInfo[] = [
  { name: "id", type: "STRING", nullable: false, nullRate: 0, uniqueCount: 100 },
  { name: "amount", type: "DECIMAL", nullable: true, nullRate: 0.05, uniqueCount: 95, stats: { min: 1, max: 100, avg: 50, stddev: 28.5 } },
  { name: "qty", type: "INTEGER", nullable: false, nullRate: 0, uniqueCount: 10, stats: { min: 1, max: 10, avg: 5, stddev: 2.8 } },
  { name: "active", type: "BOOLEAN", nullable: false, nullRate: 0, uniqueCount: 2 },
  { name: "ts", type: "TIMESTAMP", nullable: true, nullRate: 0.01, uniqueCount: 80 },
];

const MOCK_ROWS: DatasetRow[] = [
  { id: "r1", amount: 10.5, qty: 2, active: true, ts: "2026-01-01" },
  { id: "r2", amount: 50.0, qty: 5, active: false, ts: null },
  { id: "r3", amount: null, qty: 1, active: true, ts: "2026-01-03" },
];

// ── formatBytes ───────────────────────────────────────
describe("DatasetPreviewPage · formatBytes", () => {
  it("0 → —", () => {
    expect(formatBytes(0)).toBe("—");
  });
  it("negative → —", () => {
    expect(formatBytes(-1)).toBe("—");
  });
  it("< 1024 → bytes", () => {
    expect(formatBytes(512)).toBe("512 B");
  });
  it("KB", () => {
    expect(formatBytes(2048)).toBe("2.0 KB");
  });
  it("MB", () => {
    expect(formatBytes(1048576)).toBe("1.0 MB");
  });
  it("GB", () => {
    expect(formatBytes(1073741824)).toBe("1.00 GB");
  });
});

// ── formatNumber ──────────────────────────────────────
describe("DatasetPreviewPage · formatNumber", () => {
  it("0", () => {
    expect(formatNumber(0)).toBe("0");
  });
  it("1234567", () => {
    expect(formatNumber(1234567)).toBe("1,234,567");
  });
});

// ── formatTimestamp ───────────────────────────────────
describe("DatasetPreviewPage · formatTimestamp", () => {
  it("empty → —", () => {
    expect(formatTimestamp("")).toBe("—");
  });
  it("invalid → —", () => {
    expect(formatTimestamp("invalid")).toBe("—");
  });
  it("recent → 刚刚", () => {
    expect(formatTimestamp(new Date().toISOString())).toBe("刚刚");
  });
  it("minutes ago", () => {
    expect(formatTimestamp(new Date(Date.now() - 30 * 60000).toISOString())).toBe("30 分钟前");
  });
});

// ── formatNullRate ────────────────────────────────────
describe("DatasetPreviewPage · formatNullRate", () => {
  it("0 → 0%", () => {
    expect(formatNullRate(0)).toBe("0%");
  });
  it("very small → <0.1%", () => {
    expect(formatNullRate(0.0001)).toBe("<0.1%");
  });
  it("0.05 → 5.0%", () => {
    expect(formatNullRate(0.05)).toBe("5.0%");
  });
});

// ── sortRows ──────────────────────────────────────────
describe("DatasetPreviewPage · sortRows", () => {
  it("null sort → original", () => {
    const sort: SortState = null;
    expect(sortRows(MOCK_ROWS, sort)).toEqual(MOCK_ROWS);
  });
  it("asc numeric", () => {
    const sorted = sortRows(MOCK_ROWS, { col: "qty", dir: "asc" });
    expect(sorted[0].qty).toBe(1);
    expect(sorted[2].qty).toBe(5);
  });
  it("desc numeric", () => {
    const sorted = sortRows(MOCK_ROWS, { col: "qty", dir: "desc" });
    expect(sorted[0].qty).toBe(5);
  });
  it("null values go last in asc", () => {
    const sorted = sortRows(MOCK_ROWS, { col: "amount", dir: "asc" });
    expect(sorted[2].amount).toBeNull();
  });
  it("string sort", () => {
    const sorted = sortRows(MOCK_ROWS, { col: "id", dir: "asc" });
    expect(sorted[0].id).toBe("r1");
  });
});

// ── filterRows ────────────────────────────────────────
describe("DatasetPreviewPage · filterRows", () => {
  it("empty query → all", () => {
    expect(filterRows(MOCK_ROWS, "")).toHaveLength(3);
  });
  it("match r1", () => {
    expect(filterRows(MOCK_ROWS, "r1")).toHaveLength(1);
  });
  it("no match", () => {
    expect(filterRows(MOCK_ROWS, "xyz")).toHaveLength(0);
  });
});

// ── filterColumns ─────────────────────────────────────
describe("DatasetPreviewPage · filterColumns", () => {
  it("empty query → all", () => {
    expect(filterColumns(MOCK_COLS, "")).toHaveLength(5);
  });
  it("match 'amount'", () => {
    expect(filterColumns(MOCK_COLS, "amount")).toHaveLength(1);
  });
});

// ── numericColumns ────────────────────────────────────
describe("DatasetPreviewPage · numericColumns", () => {
  it("filters INTEGER and DECIMAL", () => {
    const result = numericColumns(MOCK_COLS);
    expect(result).toHaveLength(2);
    expect(result[0].name).toBe("amount");
    expect(result[1].name).toBe("qty");
  });
});

// ── computeColumnStats ────────────────────────────────
describe("DatasetPreviewPage · computeColumnStats", () => {
  it("empty → null", () => {
    expect(computeColumnStats([])).toBeNull();
  });
  it("basic stats", () => {
    const s = computeColumnStats([1, 2, 3, 4, 5]);
    expect(s).not.toBeNull();
    expect(s!.min).toBe(1);
    expect(s!.max).toBe(5);
    expect(s!.avg).toBe(3);
    expect(s!.stddev).toBeCloseTo(Math.sqrt(2), 5);
  });
});

// ── toCsv ─────────────────────────────────────────────
describe("DatasetPreviewPage · toCsv", () => {
  it("empty rows → empty", () => {
    expect(toCsv([], MOCK_COLS)).toBe("");
  });
  it("basic CSV", () => {
    const csv = toCsv([{ id: "a", qty: 1 }], [{ name: "id", type: "STRING", nullable: false, nullRate: 0, uniqueCount: 1 }, { name: "qty", type: "INTEGER", nullable: false, nullRate: 0, uniqueCount: 1 }]);
    expect(csv).toContain("id,qty");
    expect(csv).toContain("a,1");
  });
  it("null value → empty", () => {
    const csv = toCsv([{ id: null, qty: 1 }], [{ name: "id", type: "STRING", nullable: true, nullRate: 0, uniqueCount: 1 }, { name: "qty", type: "INTEGER", nullable: false, nullRate: 0, uniqueCount: 1 }]);
    expect(csv).toContain(",1");
  });
  it("comma in value → quoted", () => {
    const csv = toCsv([{ id: "a,b", qty: 1 }], [{ name: "id", type: "STRING", nullable: false, nullRate: 0, uniqueCount: 1 }, { name: "qty", type: "INTEGER", nullable: false, nullRate: 0, uniqueCount: 1 }]);
    expect(csv).toContain('"a,b"');
  });
});

// ── nextSortDir ───────────────────────────────────────
describe("DatasetPreviewPage · nextSortDir", () => {
  it("null → asc", () => {
    expect(nextSortDir(null, "x")).toEqual({ col: "x", dir: "asc" });
  });
  it("different col → asc", () => {
    expect(nextSortDir({ col: "a", dir: "asc" }, "b")).toEqual({ col: "b", dir: "asc" });
  });
  it("asc → desc", () => {
    expect(nextSortDir({ col: "a", dir: "asc" }, "a")).toEqual({ col: "a", dir: "desc" });
  });
  it("desc → null", () => {
    expect(nextSortDir({ col: "a", dir: "desc" }, "a")).toBeNull();
  });
});

// ── TYPE constants ────────────────────────────────────
describe("DatasetPreviewPage · TYPE_LABELS", () => {
  it("STRING → 字符串", () => {
    expect(TYPE_LABELS.STRING).toBe("字符串");
  });
  it("has 5 types", () => {
    expect(Object.keys(TYPE_LABELS)).toHaveLength(5);
  });
});

describe("DatasetPreviewPage · TYPE_TONE", () => {
  it("INTEGER → ok", () => {
    expect(TYPE_TONE.INTEGER).toBe("ok");
  });
  it("BOOLEAN → muted", () => {
    expect(TYPE_TONE.BOOLEAN).toBe("muted");
  });
});
