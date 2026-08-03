import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { CURRENT_STATS } from "../../../api/integrationCases/fixtures";
import { IntegrationCaseStats } from "./IntegrationCaseStats";

describe("IntegrationCaseStats", () => {
  it("formats only server metrics while preserving null and explicit zero", () => {
    const html = renderToStaticMarkup(
      <IntegrationCaseStats scope="current" stats={CURRENT_STATS} />,
    );

    expect(html).toContain("当前案例");
    expect(html).toContain("生产运行");
    expect(html).toContain("数据集行数");
    expect(html).toContain("最大延迟");
    expect(html).toContain("bp-metric-value\">0<");
    expect(html.match(/bp-metric-value\">—</g)).toHaveLength(2);
    expect(html).toContain("已测量 0 / 可计量 1");
  });

  it("does not expose current statistics in reference scope", () => {
    const html = renderToStaticMarkup(
      <IntegrationCaseStats scope="reference" stats={null} />,
    );

    expect(html).toContain("脱敏参考案例不提供当前工作区统计");
    expect(html).not.toContain("生产运行");
    expect(html).not.toContain("数据集行数");
  });

  it("fails closed for a reference response carrying current stats", () => {
    const html = renderToStaticMarkup(
      <IntegrationCaseStats scope="reference" stats={CURRENT_STATS} />,
    );

    expect(html).toContain("参考案例统计响应不符合披露契约");
    expect(html).not.toContain("当前案例");
    expect(html).not.toContain("1.2M");
  });

  it("shows an honest unavailable state instead of invented current values", () => {
    const html = renderToStaticMarkup(
      <IntegrationCaseStats scope="current" stats={null} />,
    );

    expect(html).toContain("当前案例统计暂不可用");
    expect(html).not.toContain("bp-metric-grid");
  });
});
