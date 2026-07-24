import { beforeEach, describe, expect, it } from "vitest";
import {
  applyMeToTenant,
  getTenant,
  setTenant,
  tenantAuthHeaders,
  DEFAULT_TENANT,
  STORAGE_KEY,
} from "./tenant";

describe("TWA.2 tenant context", () => {
  beforeEach(() => {
    sessionStorage.clear();
    setTenant({ ...DEFAULT_TENANT });
  });

  it("defaults to 测试工作区 / dev-project", () => {
    const t = getTenant();
    expect(t.projectId).toBe("dev-project");
    expect(t.workspaceName).toBe("测试工作区");
    expect(t.orgId).toBe("dev-org");
  });

  it("auth headers come from context not literals scattered", () => {
    setTenant({ orgId: "org-x", projectId: "prj-y", workspaceName: "Y" });
    const h = tenantAuthHeaders();
    expect(h["X-Org-Id"]).toBe("org-x");
    expect(h["X-Project-Id"]).toBe("prj-y");
    expect(h.Authorization).toMatch(/^Bearer /);
  });

  it("applyMeToTenant maps workspaceName", () => {
    applyMeToTenant({
      subject: "u",
      orgId: "dev-org",
      projectId: "dev-project",
      workspaceName: "测试工作区",
      roles: [],
      markings: [],
      tokenKind: "dev",
    });
    expect(getTenant().workspaceName).toBe("测试工作区");
    const raw = sessionStorage.getItem(STORAGE_KEY);
    expect(raw).toContain("dev-project");
  });

  it("persists across getTenant", () => {
    setTenant({ orgId: "o1", projectId: "p1", workspaceName: "W1" });
    expect(getTenant().projectId).toBe("p1");
  });

  it("TWA.3 switch updates headers for subsequent calls", () => {
    setTenant({
      orgId: "dev-org",
      projectId: "prj-ops",
      workspaceName: "生产运营工作区",
    });
    const h = tenantAuthHeaders();
    expect(h["X-Project-Id"]).toBe("prj-ops");
    expect(getTenant().workspaceName).toBe("生产运营工作区");
  });

  it("TWC.3 access token override changes Authorization", async () => {
    const { setAccessToken, clearAccessToken } = await import("./tenant");
    setAccessToken("jwt-demo");
    expect(tenantAuthHeaders().Authorization).toBe("Bearer jwt-demo");
    clearAccessToken();
    expect(tenantAuthHeaders().Authorization).toBe("Bearer dev");
  });
});
