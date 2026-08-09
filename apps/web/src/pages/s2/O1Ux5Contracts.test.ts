import { describe, expect, it } from "vitest";
import { ECOM_ORDER_MAPPING } from "./remainder";
import { overlayIfMatch } from "./ontology";
import { summarizeWikiCoverage } from "./WikiIndexPage";

describe("O1-UX5 页面合同", () => {
  it("电商 OKF 默认绑定真实 Order 而不是测试 WorkOrder", () => {
    expect(ECOM_ORDER_MAPPING.objectType).toBe("Order");
    expect(ECOM_ORDER_MAPPING.columns.every((column) => column.dst.startsWith("Order."))).toBe(true);
  });

  it("Overlay reset 使用服务端 revision 与 base hash 构造强 ETag", () => {
    expect(overlayIfMatch({ ontology_revision: 7, base_schema_sha256: "a".repeat(64) }))
      .toBe(`"ontology-overlay-v1:7:${"a".repeat(64)}"`);
    expect(() => overlayIfMatch({ ontology_revision: 7 })).toThrow(/base schema hash/);
  });

  it("Wiki 索引区分真实覆盖和知识缺口", () => {
    expect(summarizeWikiCoverage([{ covered: true }, { covered: false }, { covered: false }]))
      .toEqual({ covered: 1, gaps: 2, total: 3 });
  });
});
