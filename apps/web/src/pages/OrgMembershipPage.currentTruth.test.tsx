// @vitest-environment jsdom
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
const api = vi.hoisted(() => ({ apiGet: vi.fn(), apiPost: vi.fn(), apiDelete: vi.fn() }));
vi.mock("../api/client", () => api);
vi.mock("../api/tenant", () => ({
  DEFAULT_TENANT: { orgId: "org-org", projectId: "dev-project", workspaceName: "默认工作区" },
  getTenant: () => ({ orgId: "org-org", projectId: "dev-project", workspaceName: "默认工作区" }),
  setTenant: vi.fn(),
}));

import { OrgMembershipPage } from "./OrgMembershipPage";

describe("OrgMembershipPage current truth", () => {
  let host: HTMLDivElement; let root: Root;
  beforeEach(() => {
    api.apiGet.mockImplementation(async (path: string) => {
      if (path === "/v1/orgs/directory") return { items: [{ id: "org-org", name: "栖月汇商贸有限公司", member: true }, { id: "partner-org", name: "合作伙伴", joinPolicy: "invite_only" }] };
      if (path.includes("join-requests")) return { items: [] };
      return { empty: true, total: 0 };
    });
    host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host);
  });
  afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.clearAllMocks(); });

  it("首屏使用中文状态并折叠精确标识与危险区", async () => {
    await act(async () => root.render(createElement(MemoryRouter, null, createElement(OrgMembershipPage))));
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    expect(host.textContent).toContain("仅限邀请");
    expect(host.textContent).not.toContain("invite_only");
    const danger = host.querySelector<HTMLDetailsElement>('[data-testid="org-admin-danger-zone"]')!;
    expect(danger.open).toBe(false);
    const audits = host.querySelectorAll<HTMLDetailsElement>(".aos-inline-audit");
    expect(audits.length).toBe(2);
    expect(Array.from(audits).every((item) => !item.open)).toBe(true);
    expect(api.apiPost).not.toHaveBeenCalled();
    expect(api.apiDelete).not.toHaveBeenCalled();
  });
});
