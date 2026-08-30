// @vitest-environment jsdom
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { AipReadinessActionCard } from "./AipReadinessActionCard";

describe("AipReadinessActionCard", () => {
  it("把运行条件翻译成业务影响、缺失条件、责任方和唯一行动入口", () => {
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <AipReadinessActionCard
          status="需要处理"
          owner="AIP 智能体运行平台"
          ownerHref="/aip/model-runtime"
          impact="当前不能向该智能体下达新的经营任务，已有结果仍可只读查看。"
          missingConditions={["同一数据截止面的模型健康检查", "有效的能力绑定"]}
          reasons={["能力绑定就绪快照已过期", "能力绑定就绪快照已过期"]}
          observedAt="2026-08-23T00:00:00Z"
          expiresAt="2026-08-23T00:15:00Z"
          actionHref="/aip/agent-registry"
          actionLabel="刷新运行准备"
          technicalCodes={["capability_binding_readiness_stale"]}
        />
      </MemoryRouter>,
    );
    expect(html).toContain("责任方");
    expect(html).toContain("AIP 智能体运行平台");
    expect(html).toContain("业务影响");
    expect(html).toContain("当前不能向该智能体下达新的经营任务");
    expect(html).toContain("缺失条件");
    expect(html).toContain("同一数据截止面的模型健康检查");
    expect(html).toContain("证据到期");
    expect(html.match(/能力绑定就绪快照已过期/g)).toHaveLength(1);
    expect(html).toContain("刷新运行准备");
    expect(html).toContain("技术标识（审计用）");
  });

  it("行动不可执行时说明原因并给出责任入口，而不是只留下灰按钮", () => {
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <AipReadinessActionCard
          status="正在核验运行条件"
          owner="模型运行负责人"
          ownerHref="/aip/model-runtime"
          reasons={["正在读取最新状态"]}
          actionLabel="刷新运行准备"
          actionDisabled
          actionDisabledReason="本次刷新尚未完成，请等待当前请求返回。"
        />
      </MemoryRouter>,
    );
    expect(html).toContain("本次刷新尚未完成");
    expect(html).toContain("联系责任方");
    expect(html).toContain('href="/aip/model-runtime"');
  });
});
