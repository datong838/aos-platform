import { describe, expect, it } from "vitest";

import {
  datasetBusinessColumns,
  datasetCellText,
  datasetFieldLabel,
  datasetStatusLabel,
  edgeAgentSourceCount,
} from "./data";

describe("dataset business projection", () => {
  it("边缘代理接入数只统计明确归属代理运行时的数据源", () => {
    expect(edgeAgentSourceCount([
      { runtimeMode: "agent" },
      { runtimeMode: "worker" },
      { runtimeMode: "direct" },
      {},
    ])).toBe(2);
  });
  it("normalizes service states without inventing READY for missing data", () => {
    expect(datasetStatusLabel("READY")).toBe("可读取");
    expect(datasetStatusLabel("running")).toBe("更新中");
    expect(datasetStatusLabel("FAILED")).toBe("读取失败");
    expect(datasetStatusLabel()).toBe("未读取");
  });

  it("uses Chinese business field labels and neutral fallback", () => {
    expect(datasetFieldLabel("order_no")).toBe("订单号");
    expect(datasetFieldLabel("goods_name")).toBe("商品名称");
    expect(datasetFieldLabel("memberId")).toBe("会员标识");
    expect(datasetFieldLabel("totalAmount")).toBe("订单总额");
    expect(datasetFieldLabel("review_quality_bucket")).toBe("评价质量");
    expect(datasetFieldLabel("created_at")).toBe("创建时间");
    expect(datasetFieldLabel("internal_column")).toBe("业务字段");
  });

  it("keeps technical lineage fields in audit instead of the business table", () => {
    expect(
      datasetBusinessColumns([
        "id",
        "type",
        "orderNo",
        "_schemaVersion",
        "_sourceIdentity",
        "_sourceUpdatedAt",
        "updatedAtSourceTimezone",
      ]),
    ).toEqual(["id", "orderNo"]);
  });

  it("localizes confirmed business values without changing unknown values", () => {
    expect(datasetCellText("status", "active")).toBe("正常");
    expect(datasetCellText("currency", "CNY")).toBe("人民币");
    expect(datasetCellText("review_quality_bucket", "high")).toBe("高");
    expect(datasetCellText("orderStatus", 10)).toBe("10");
  });
});
