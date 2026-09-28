import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../api/client", () => ({
  apiGet: vi.fn(),
  apiGetAuthoritative: vi.fn(),
  apiPostUnqueued: vi.fn(),
}));
vi.mock("../../api/aipAgentControl", () => ({ aipAgentControl: { runtimeReadiness: vi.fn().mockResolvedValue({ catalog: { items: [] } }) } }));
vi.mock("../../api/tenant", () => ({
  getTenant: () => ({ orgId: "org-org", projectId: "dev-project" }),
}));

import { apiGet, apiGetAuthoritative, apiPostUnqueued } from "../../api/client";
import { SkillPublishPage } from "./SkillPublishPage";

const tenant = { orgId: "org-org", projectId: "dev-project" };

describe("SkillPublishPage W-F4 batch stats", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    localStorage.clear();
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    vi.mocked(apiGet).mockImplementation(async (path: string) => {
      if (path.includes("lifecycle=evaluated")) {
        return {
          tenant,
          count: 1,
          items: [
            {
              skillId: "ecommerce.skill.A01",
              revision: 1,
              lifecycle: "evaluated",
              contentHash: "a".repeat(64),
              canonicalLogicId: "ecommerce.logic.A01",
            },
          ],
        };
      }
      return {
        tenant,
        count: 2,
        items: [
          {
            skillId: "ecommerce.skill.A02",
            revision: 1,
            lifecycle: "published",
            contentHash: "b".repeat(64),
            canonicalLogicId: "ecommerce.logic.A02",
          },
          {
            skillId: "ecommerce.skill.A01",
            revision: 1,
            lifecycle: "evaluated",
            contentHash: "a".repeat(64),
            canonicalLogicId: "ecommerce.logic.A01",
          },
        ],
      };
    });
    vi.mocked(apiGetAuthoritative).mockResolvedValue({
      tenant, skillId: "ecommerce.skill.A01", revision: 1,
      releaseCandidates: [], logicCandidates: [], routeCandidates: [],
      blockers: ["RELEASE_PUBLICATION_UNAVAILABLE", "LOGIC_PUBLICATION_UNAVAILABLE", "MODEL_ROUTE_UNAVAILABLE"],
    });
  });

  afterEach(() => {
    act(() => root.unmount());
    host.remove();
    vi.clearAllMocks();
  });

  it("shows honest first-batch readiness strip", async () => {
    await act(async () => {
      root.render(
        <MemoryRouter>
          <SkillPublishPage />
        </MemoryRouter>,
      );
    });
    await act(async () => undefined);
    const strip = host.querySelector('[data-testid="skill-publish-batch-stats"]');
    expect(strip?.textContent).toContain("已发布技能");
    expect(strip?.textContent).toContain("1");
    expect(strip?.textContent).toContain("需核验业务逻辑权威");
    expect(strip?.textContent).toContain("精确版本");
  });

  it("shows current blockers and never offers a raw-reference publishing form", async () => {
    await act(async () => root.render(<MemoryRouter><SkillPublishPage /></MemoryRouter>));
    await act(async () => undefined);
    expect(vi.mocked(apiGetAuthoritative)).toHaveBeenCalledWith(
      "/v1/aip/skills/ecommerce.skill.A01/revisions/1/publication-options",
    );
    expect(host.textContent).toContain("当前无可发布候选");
    expect(host.textContent).toContain("缺少正式技能发布放行决定与发布事件");
    expect(host.textContent).toContain("缺少当前业务逻辑发布版本");
    expect(host.textContent).toContain("缺少可用的当前模型路由与运行策略");
    expect(host.querySelector('a[href="/aip/logic"]')?.textContent).toContain("业务逻辑");
    expect(host.querySelector('a[href="/aip/model-router"]')?.textContent).toContain("模型路由");
    expect(host.querySelector('p[role="status"]')?.textContent).not.toContain("RELEASE_PUBLICATION_UNAVAILABLE");
    expect(Array.from(host.querySelectorAll('a[href="/aip/agent-registry"]')).some(link => link.textContent === "查看组织绑定状态")).toBe(true);
    expect(host.textContent).toContain("正式绑定创建入口待接线");
    expect(host.querySelector('a[href="/aip/evals"]')?.textContent).toContain("Logic 兼容评测");
    expect(host.textContent).toContain("技能放行须由正式 EvalSuite、EvalReport、ReleaseGate 与发布事件组成");
    expect(host.textContent).not.toContain("去评测确认门绿");
    expect(host.querySelectorAll("input")).toHaveLength(0);
    expect((Array.from(host.querySelectorAll("button")).find((button) => button.textContent?.includes("发布此修订")) as HTMLButtonElement).disabled).toBe(true);
    expect(apiPostUnqueued).not.toHaveBeenCalled();
  });

  it("keeps unknown publication blockers visible for audit without enabling publish", async () => {
    vi.mocked(apiGetAuthoritative).mockResolvedValue({ tenant, skillId: "ecommerce.skill.A01", revision: 1,
      releaseCandidates: [], logicCandidates: [], routeCandidates: [], blockers: ["UNKNOWN_CURRENT_OWNER"] });
    await act(async () => root.render(<MemoryRouter><SkillPublishPage /></MemoryRouter>));
    await act(async () => undefined);
    expect(host.textContent).toContain("当前权威阻断待核对");
    expect(host.querySelector("details")?.textContent).toContain("UNKNOWN_CURRENT_OWNER");
    expect((Array.from(host.querySelectorAll("button")).find((button) => button.textContent?.includes("发布此修订")) as HTMLButtonElement).disabled).toBe(true);
    expect(apiPostUnqueued).not.toHaveBeenCalled();
  });

  it("requires explicit exact choices, then sends an unqueued command once", async () => {
    const hash = "a".repeat(64);
    vi.mocked(apiGetAuthoritative).mockResolvedValue({
      tenant, skillId: "ecommerce.skill.A01", revision: 1, blockers: [],
      releaseCandidates: [{ publicationId: "pub-1", releaseGateDecisionId: "gate-1" }],
      logicCandidates: [{ assetType: "LogicRevision", assetId: "ecommerce.logic.A01", revision: 2, contentHash: hash }],
      routeCandidates: [{
        routeRef: { assetType: "ModelRouteRevision", assetId: "route-1", revision: 1, contentHash: hash },
        policyRef: { assetType: "RuntimePolicyRevision", assetId: "policy-1", revision: 1, contentHash: hash },
      }],
    });
    vi.mocked(apiPostUnqueued).mockRejectedValue(new Error("connection lost after send"));
    vi.spyOn(window, "confirm").mockReturnValue(true);
    await act(async () => root.render(<MemoryRouter><SkillPublishPage /></MemoryRouter>));
    await act(async () => undefined);
    const publish = () => Array.from(host.querySelectorAll("button")).find((button) => button.textContent?.includes("发布此修订")) as HTMLButtonElement;
    expect(publish().disabled).toBe(true);
    const choices = host.querySelectorAll("section select");
    expect(choices).toHaveLength(3);
    for (const choice of choices) {
      await act(async () => { (choice as HTMLSelectElement).value = "0"; choice.dispatchEvent(new Event("change", { bubbles: true })); });
    }
    expect(publish().disabled).toBe(false);
    await act(async () => publish().click());
    expect(apiPostUnqueued).toHaveBeenCalledTimes(1);
    expect(vi.mocked(apiPostUnqueued).mock.calls[0][1]).toMatchObject({
      publicationId: "pub-1", releaseGateDecisionId: "gate-1",
      logicRevisionRef: { assetId: "ecommerce.logic.A01", revision: 2 },
    });
    expect(publish().disabled).toBe(true);
    expect(host.textContent).toContain("禁止重发");
    vi.mocked(window.confirm).mockRestore();
  });
});
