import { describe, expect, it } from "vitest";
import { ECOM_ORDER_MAPPING } from "./remainder";
import { overlayDiffRows, overlayIfMatch, overlayModeLabel, overlayTargetKindLabel } from "./ontology";
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

  it("Overlay 对比覆盖显示名、可见属性、扩展属性与组织策略", () => {
    const rows = overlayDiffRows(
      {
        target_kind: "ObjectType",
        target_id: "Order",
        ontology_revision: 2,
        mode: "override",
        is_active: true,
        display_name: "栖月汇订单",
        visible_properties: ["orderNo", "createdAt"],
        extended_properties: { channel: { type: "string" } },
        policies: { schemaVersion: 1, readRoles: ["operator"] },
      },
      {
        target_kind: "ObjectType",
        target_id: "Order",
        ontology_revision: 1,
        mode: "inherit",
        is_active: false,
      },
    );
    expect(rows.map(([field]) => field)).toEqual(["模式", "显示名", "可见属性", "扩展属性", "组织策略"]);
    expect(rows[2]).toEqual(["可见属性", "orderNo、createdAt", "—"]);
    expect(rows[3][1]).toBe("channel");
    expect(rows[0]).toEqual(["模式", "组织覆盖", "继承安装模板"]);
    expect(overlayTargetKindLabel("ObjectType")).toBe("对象类型");
    expect(overlayTargetKindLabel("LinkType")).toBe("关系类型");
    expect(overlayModeLabel("inherit")).toBe("继承安装模板");
  });

  it("Wiki 索引区分真实覆盖和知识缺口", () => {
    expect(summarizeWikiCoverage([{ covered: true }, { covered: false }, { covered: false }]))
      .toEqual({ covered: 1, gaps: 2, total: 3 });
  });
});
