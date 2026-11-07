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

  it("keeps QYH preview usable when stored-session verification loses the network", async () => {
    vi.stubEnv("VITE_AOS_SKIP_LOGIN_GATE", "1");
    persistWebDevSession({ accessToken: "qyh-access", refreshToken: "qyh-refresh", expiresIn: 3600 });
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network unavailable")));
    setTenant({ orgId: "dev-org", projectId: "dev-project", subject: "foreign", workspaceName: "其他" });

    await expect(prepareWebDevelopmentContext()).resolves.toBeUndefined();

    expect(getAccessToken()).toBeNull();
    expect(getTenant()).toEqual(DEFAULT_TENANT);
  });

  it("bounds unresponsive stored-session checks before showing QYH preview", async () => {
    vi.useFakeTimers();
    try {
      vi.stubEnv("VITE_AOS_SKIP_LOGIN_GATE", "1");
      persistWebDevSession({ accessToken: "qyh-access", refreshToken: "qyh-refresh", expiresIn: 3600 });
      const fetch = vi.fn((_url, options: RequestInit) => new Promise((_resolve, reject) => {
        options.signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
      }));
      vi.stubGlobal("fetch", fetch);
      let completed = false;
      const pending = prepareWebDevelopmentContext().then(() => { completed = true; });
      await vi.advanceTimersByTimeAsync(4999);
      expect(completed).toBe(false);
      await vi.advanceTimersByTimeAsync(1);
      expect(completed).toBe(true);
      await pending;
      expect(fetch).toHaveBeenCalledTimes(1);
      expect(getAccessToken()).toBeNull();
      expect(getTenant()).toEqual(DEFAULT_TENANT);
      expect(vi.getTimerCount()).toBe(0);
    } finally {
      vi.useRealTimers();
    }
  });

  it("shares the startup deadline with refresh instead of restarting its wait", async () => {
    const unauthorized = { ok: false } as Response;
    vi.useFakeTimers();
    try {
      vi.stubEnv("VITE_AOS_SKIP_LOGIN_GATE", "1");
      persistWebDevSession({ accessToken: "qyh-access", refreshToken: "qyh-refresh", expiresIn: 3600 });
      const fetch = vi.fn()
        .mockImplementationOnce(() => new Promise(resolve => {
          setTimeout(() => resolve(unauthorized), 4000);
        }))
        .mockImplementationOnce((_url, options: RequestInit) => new Promise((_resolve, reject) => {
          options.signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
        }));
      vi.stubGlobal("fetch", fetch);
      let completed = false;
      const pending = prepareWebDevelopmentContext().then(() => { completed = true; });
      await vi.advanceTimersByTimeAsync(4999);
      expect(fetch).toHaveBeenCalledTimes(2);
      expect(completed).toBe(false);
      expect(fetch.mock.calls[0][1].signal).toBe(fetch.mock.calls[1][1].signal);
      await vi.advanceTimersByTimeAsync(1);
      await pending;
      expect(completed).toBe(true);
      expect(getAccessToken()).toBeNull();
      expect(getTenant()).toEqual(DEFAULT_TENANT);
    } finally {
      vi.useRealTimers();
    }
  });
});
