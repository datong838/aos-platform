import { describe, expect, it } from "vitest";
import {
  CAP_TYPES,
  SEC_LEVELS,
  MOCK_KB_DOCUMENTS,
  DETAILED_TEST_ITEMS,
  DEFAULT_ENV_VARS,
  computeTestStats,
  computeKBStats,
  type KBDocument,
} from "./CapabilityImportPage";

describe("CapabilityImportPage · CAP_TYPES", () => {
  it("包含 C0/C1/C2 三种类型", () => {
    expect(CAP_TYPES.find((c) => c.id === "C0")).toBeTruthy();
    expect(CAP_TYPES.find((c) => c.id === "C1")).toBeTruthy();
    expect(CAP_TYPES.find((c) => c.id === "C2")).toBeTruthy();
  });

  it("每个类型有完整字段", () => {
    for (const ct of CAP_TYPES) {
      expect(ct.subtype.length).toBeGreaterThan(0);
      expect(ct.name.length).toBeGreaterThan(0);
      expect(ct.desc.length).toBeGreaterThan(0);
      expect(ct.example.length).toBeGreaterThan(0);
      expect(ct.subColor.length).toBeGreaterThan(0);
      expect(ct.subBg.length).toBeGreaterThan(0);
    }
  });
});

describe("CapabilityImportPage · SEC_LEVELS", () => {
  it("包含 low/medium/high 三种等级", () => {
    expect(SEC_LEVELS.find((l) => l.id === "low")).toBeTruthy();
    expect(SEC_LEVELS.find((l) => l.id === "medium")).toBeTruthy();
    expect(SEC_LEVELS.find((l) => l.id === "high")).toBeTruthy();
  });

  it("每个等级有 color", () => {
    for (const lvl of SEC_LEVELS) {
      expect(lvl.color.length).toBeGreaterThan(0);
      expect(lvl.label.length).toBeGreaterThan(0);
    }
  });
});

describe("CapabilityImportPage · MOCK_KB_DOCUMENTS", () => {
  it("至少 2 个文档", () => {
    expect(MOCK_KB_DOCUMENTS.length).toBeGreaterThanOrEqual(2);
  });

  it("每个文档有完整字段", () => {
    for (const doc of MOCK_KB_DOCUMENTS) {
      expect(doc.id.length).toBeGreaterThan(0);
      expect(doc.name.length).toBeGreaterThan(0);
      expect(doc.size.length).toBeGreaterThan(0);
      expect(doc.desc.length).toBeGreaterThan(0);
      expect(["indexed", "indexing", "pending"]).toContain(doc.status);
      expect(["pdf", "md", "doc", "txt"]).toContain(doc.icon);
    }
  });

  it("包含至少 1 个已索引文档", () => {
    expect(MOCK_KB_DOCUMENTS.some((d) => d.status === "indexed")).toBe(true);
  });

  it("包含至少 1 个索引中文档", () => {
    expect(MOCK_KB_DOCUMENTS.some((d) => d.status === "indexing")).toBe(true);
  });
});

describe("CapabilityImportPage · DEFAULT_ENV_VARS", () => {
  it("至少 3 个环境变量", () => {
    expect(DEFAULT_ENV_VARS.length).toBeGreaterThanOrEqual(3);
  });

  it("每个变量有 key/value/secret/bound", () => {
    for (const v of DEFAULT_ENV_VARS) {
      expect(v.key.length).toBeGreaterThan(0);
      expect(typeof v.secret).toBe("boolean");
      expect(typeof v.bound).toBe("boolean");
    }
  });

  it("包含至少 1 个 secret 变量", () => {
    expect(DEFAULT_ENV_VARS.some((v) => v.secret)).toBe(true);
  });

  it("包含至少 1 个已绑定变量", () => {
    expect(DEFAULT_ENV_VARS.some((v) => v.bound)).toBe(true);
  });
});

describe("CapabilityImportPage · DETAILED_TEST_ITEMS", () => {
  it("至少 4 个测试项", () => {
    expect(DETAILED_TEST_ITEMS.length).toBeGreaterThanOrEqual(4);
  });

  it("每个测试项有 name/status/detail", () => {
    for (const t of DETAILED_TEST_ITEMS) {
      expect(t.name.length).toBeGreaterThan(0);
      expect(["pass", "pending", "fail"]).toContain(t.status);
      expect(t.detail.length).toBeGreaterThan(0);
    }
  });

  it("包含至少 1 个 pass 项", () => {
    expect(DETAILED_TEST_ITEMS.some((t) => t.status === "pass")).toBe(true);
  });
});

describe("CapabilityImportPage · computeTestStats", () => {
  it("返回 total/pass/pending/fail", () => {
    const stats = computeTestStats(DETAILED_TEST_ITEMS);
    expect(stats).toHaveProperty("total");
    expect(stats).toHaveProperty("pass");
    expect(stats).toHaveProperty("pending");
    expect(stats).toHaveProperty("fail");
  });

  it("total 等于测试项总数", () => {
    const stats = computeTestStats(DETAILED_TEST_ITEMS);
    expect(stats.total).toBe(DETAILED_TEST_ITEMS.length);
  });

  it("pass + pending + fail = total", () => {
    const stats = computeTestStats(DETAILED_TEST_ITEMS);
    expect(stats.pass + stats.pending + stats.fail).toBe(stats.total);
  });

  it("空数组返回全 0", () => {
    const stats = computeTestStats([]);
    expect(stats.total).toBe(0);
    expect(stats.pass).toBe(0);
  });
});

describe("CapabilityImportPage · computeKBStats", () => {
  it("返回 total/indexed/indexing/pending/totalChunks", () => {
    const stats = computeKBStats(MOCK_KB_DOCUMENTS);
    expect(stats).toHaveProperty("total");
    expect(stats).toHaveProperty("indexed");
    expect(stats).toHaveProperty("indexing");
    expect(stats).toHaveProperty("pending");
    expect(stats).toHaveProperty("totalChunks");
  });

  it("total 等于文档总数", () => {
    const stats = computeKBStats(MOCK_KB_DOCUMENTS);
    expect(stats.total).toBe(MOCK_KB_DOCUMENTS.length);
  });

  it("indexed + indexing + pending = total", () => {
    const stats = computeKBStats(MOCK_KB_DOCUMENTS);
    expect(stats.indexed + stats.indexing + stats.pending).toBe(stats.total);
  });

  it("totalChunks 正确汇总", () => {
    const expected = MOCK_KB_DOCUMENTS.reduce((sum, d) => sum + d.chunks, 0);
    const stats = computeKBStats(MOCK_KB_DOCUMENTS);
    expect(stats.totalChunks).toBe(expected);
  });

  it("空数组返回全 0", () => {
    const stats = computeKBStats([]);
    expect(stats.total).toBe(0);
    expect(stats.totalChunks).toBe(0);
  });

  it("自定义文档数据正确计算", () => {
    const custom: KBDocument[] = [
      {
        id: "c1",
        name: "test1.pdf",
        size: "10KB",
        desc: "测试",
        chunks: 5,
        status: "indexed",
        icon: "pdf",
        iconColor: "#DC2626",
      },
      {
        id: "c2",
        name: "test2.md",
        size: "5KB",
        desc: "测试2",
        chunks: 3,
        status: "indexing",
        icon: "md",
        iconColor: "#2563EB",
      },
    ];
    const stats = computeKBStats(custom);
    expect(stats.total).toBe(2);
    expect(stats.indexed).toBe(1);
    expect(stats.indexing).toBe(1);
    expect(stats.totalChunks).toBe(8);
  });
});
