import { afterEach, describe, expect, it, vi } from "vitest";
import {
  clearAccessToken,
  DEFAULT_TENANT,
  getAccessToken,
  getTenant,
  resetTenantToDefault,
  setTenant,
} from "./tenant";
import {
  clearWebDevSession,
  persistWebDevSession,
  prepareWebDevelopmentContext,
} from "./webDevSession";

const qyhMe = {
  subject: "human-qyh",
  orgId: "org-org",
  projectId: "dev-project",
  workspaceName: "栖月汇",
  roles: ["admin"],
  markings: [],
  tokenKind: "oidc",
};

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  clearWebDevSession();
  clearAccessToken();
  sessionStorage.clear();
  resetTenantToDefault();
});

describe("QYH development login bypass", () => {
  it("keeps login optional while restoring the exact QYH tenant without /v1/me", async () => {
    vi.stubEnv("VITE_AOS_SKIP_LOGIN_GATE", "1");
    setTenant({ orgId: "dev-org", projectId: "dev-project", workspaceName: "错误开发租户", subject: "developer" });
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);

    await prepareWebDevelopmentContext();

    expect(fetch).not.toHaveBeenCalled();
    expect(getAccessToken()).toBeNull();
    expect(getTenant()).toEqual(DEFAULT_TENANT);
  });

  it("rejects a restored foreign-tenant session and remains in QYH development context", async () => {
    vi.stubEnv("VITE_AOS_SKIP_LOGIN_GATE", "1");
    persistWebDevSession({ accessToken: "foreign-access", refreshToken: "foreign-refresh", expiresIn: 3600 });
    const fetch = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...qyhMe, orgId: "dev-org", subject: "foreign" })))
      .mockResolvedValueOnce(new Response("{}", { status: 401 }));
    vi.stubGlobal("fetch", fetch);

    await prepareWebDevelopmentContext();

    expect(fetch.mock.calls[0][1].headers["X-Org-Id"]).toBe("org-org");
    expect(getAccessToken()).toBeNull();
    expect(getTenant()).toEqual(DEFAULT_TENANT);
  });

  it("restores a verified QYH OIDC session without a second tenant bootstrap", async () => {
    vi.stubEnv("VITE_AOS_SKIP_LOGIN_GATE", "1");
    persistWebDevSession({ accessToken: "qyh-access", refreshToken: "qyh-refresh", expiresIn: 3600 });
    const fetch = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify(qyhMe)));
    vi.stubGlobal("fetch", fetch);

    await prepareWebDevelopmentContext();

    expect(fetch).toHaveBeenCalledTimes(1);
    expect(getAccessToken()).toBe("qyh-access");
    expect(getTenant()).toMatchObject({ orgId: "org-org", projectId: "dev-project", subject: "human-qyh" });
  });
});
