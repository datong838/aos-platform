import { afterEach, describe, expect, it, vi } from "vitest";
import { loginPassword } from "./passwordLogin";
import { clearAccessToken, getAccessToken, getTenant } from "./tenant";
import { act, createElement } from "react";
import { createRoot } from "react-dom/client";
import { LocalLoginGate } from "../components/auth/LocalLoginGate";

afterEach(() => { vi.unstubAllGlobals(); clearAccessToken(); });
describe("human password login", () => {
  it("uses original grant and canonical me before publishing memory session", async () => {
    const fetch = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ accessToken: "signed", refreshToken: "discard" })))
      .mockResolvedValueOnce(new Response(JSON.stringify({ subject: "human", orgId: "org-org", projectId: "dev-project", workspaceName: "真实工作区", roles: ["admin"], markings: [], tokenKind: "oidc" })));
    vi.stubGlobal("fetch", fetch);
    await loginPassword("user", "private");
    expect(fetch.mock.calls[0][0]).toContain("/v1/auth/token");
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ grantType: "password", username: "user", password: "private" });
    expect(fetch.mock.calls[1][1].headers.Authorization).toBe("Bearer signed");
    expect(getAccessToken()).toBe("signed");
    expect(getTenant().subject).toBe("human");
    expect(localStorage.getItem("access_token")).toBeNull();
    expect(sessionStorage.getItem("refresh_token")).toBeNull();
  });
  it("does not retry rejected credentials or publish a session", async () => {
    const fetch = vi.fn().mockResolvedValue(new Response("private provider detail", { status: 401 }));
    vi.stubGlobal("fetch", fetch);
    await expect(loginPassword("user", "private")).rejects.toThrow("登录失败");
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(getAccessToken()).toBeNull();
  });
  it("rejects incomplete token responses before fetching identity", async () => {
    const fetch = vi.fn().mockResolvedValue(new Response("{}")); vi.stubGlobal("fetch", fetch);
    await expect(loginPassword("user", "private")).rejects.toThrow("登录失败");
    expect(fetch).toHaveBeenCalledTimes(1); expect(getAccessToken()).toBeNull();
  });
  it("does not expose an unverified session when canonical me fails", async () => {
    const fetch = vi.fn().mockResolvedValueOnce(new Response('{"accessToken":"signed"}'))
      .mockResolvedValueOnce(new Response("{}", { status: 403 })); vi.stubGlobal("fetch", fetch);
    await expect(loginPassword("user", "private")).rejects.toThrow("登录失败");
    expect(getAccessToken()).toBeNull();
  });
});

describe("server login policy gate", () => {
  async function renderPolicy(body: unknown, status = 200) {
    vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status })));
    const container = document.createElement("div");
    const root = createRoot(container);
    await act(async () => { root.render(createElement(LocalLoginGate, { children: "business catalog" })); });
    const text = container.textContent;
    await act(async () => root.unmount());
    return text;
  }
  it("preserves the explicitly enabled legacy development UI", async () => {
    expect(await renderPolicy({ allowDevToken: true })).toContain("business catalog");
  });
  it("requires human login before mounting business consumers", async () => {
    const text = await renderPolicy({ allowDevToken: false, tokenUrlConfigured: true, grantTypes: ["password"] });
    expect(text).toContain("登录名"); expect(text).not.toContain("business catalog");
  });
  it("fails closed for unreadable or unsupported login configuration", async () => {
    for (const [body, status] of [[{}, 200], [{ allowDevToken: false }, 200], [{}, 503]] as const) {
      const text = await renderPolicy(body, status);
      expect(text).toContain("登录服务暂不可用"); expect(text).not.toContain("business catalog");
    }
  });
});
