import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../api/client", () => ({
  apiGet: vi.fn(),
}));
vi.mock("../../api/tenant", () => ({
  getTenant: () => ({ orgId: "org-org", projectId: "dev-project" }),
}));

import { apiGet } from "../../api/client";
import { SkillPublishPage } from "./SkillPublishPage";

const tenant = { orgId: "org-org", projectId: "dev-project" };

describe("SkillPublishPage W-F4 batch stats", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
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
    expect(strip?.textContent).toContain("仍待 Logic 权威进库");
    expect(strip?.textContent).toContain("不在此页伪造发布");
  });
});
