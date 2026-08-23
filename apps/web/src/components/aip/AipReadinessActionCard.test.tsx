// @vitest-environment jsdom
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { AipReadinessActionCard } from "./AipReadinessActionCard";

describe("AipReadinessActionCard", () => {
  it("把技术阻断翻译成责任方、到期时间和唯一行动入口", () => {
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <AipReadinessActionCard
          status="需要处理"
          owner="AIP 智能体运行平台"
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
    expect(html).toContain("证据到期");
    expect(html.match(/能力绑定就绪快照已过期/g)).toHaveLength(1);
    expect(html).toContain("刷新运行准备");
    expect(html).toContain("技术标识（审计用）");
  });
});
