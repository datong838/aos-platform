import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { startSessionRefresh, stopSessionRefresh } from "./sessionRefresh";
import { clearAccessToken, getAccessToken, getTenant, setAccessToken, setTenant } from "./tenant";

const me = { subject: "human", orgId: "org-org", projectId: "dev-project", roles: ["admin"], markings: [], tokenKind: "oidc" };
const tokens = (suffix: string) => ({ accessToken: `access-${suffix}`, refreshToken: `refresh-${suffix}`, expiresIn: 60 });
const response = (value: unknown) => new Response(JSON.stringify(value));

beforeEach(() => { vi.useFakeTimers(); setTenant(me); setAccessToken("access-old"); });
afterEach(() => { stopSessionRefresh(); clearAccessToken(); vi.useRealTimers(); vi.unstubAllGlobals(); });

describe("human session renewal", () => {
  it("renews the same human and rotates only the tab-scoped development session", async () => {
    const fetch = vi.fn().mockResolvedValueOnce(response(tokens("new"))).mockResolvedValueOnce(response(me))
      .mockResolvedValueOnce(response(tokens("next"))).mockResolvedValueOnce(response(me));
    vi.stubGlobal("fetch", fetch);
    startSessionRefresh(tokens("old"), me);
    await vi.advanceTimersByTimeAsync(30_000);
    expect(getAccessToken()).toBe("access-new");
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ grantType: "refresh_token", refreshToken: "refresh-old" });
    expect(fetch.mock.calls[1][1].headers.Authorization).toBe("Bearer access-new");
    await vi.advanceTimersByTimeAsync(30_000);
    expect(JSON.parse(fetch.mock.calls[2][1].body).refreshToken).toBe("refresh-new");
    expect(getAccessToken()).toBe("access-next");
    for (let n = 0; n < localStorage.length; n++) {
      expect(localStorage.getItem(localStorage.key(n)!)).not.toMatch(/refresh-(old|new|next)|access-(old|new|next)/);
    }
    expect(Array.from({ length: sessionStorage.length }, (_, index) => sessionStorage.key(index)).sort())
      .toEqual(["aos-tenant-v1", "aos-web-dev-session-v1"]);
    expect(JSON.parse(sessionStorage.getItem("aos-web-dev-session-v1")!)).toEqual(tokens("next"));
  });

  it.each(["rejected", "network"])("does not retry %s renewal or log out the current page", async (failure) => {
    const fetch = failure === "network" ? vi.fn().mockRejectedValue(new TypeError("unknown")) : vi.fn().mockResolvedValue(new Response("{}", { status: 401 }));
    vi.stubGlobal("fetch", fetch); startSessionRefresh(tokens("old"), me);
    await vi.advanceTimersByTimeAsync(300_000);
    expect(fetch).toHaveBeenCalledTimes(1); expect(getAccessToken()).toBe("access-old");
  });

  it.each([{ ...me, subject: "other" }, { ...me, projectId: "other" }])("rejects changed verified identity", async (changed) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(response(tokens("new"))).mockResolvedValueOnce(response(changed)));
    startSessionRefresh(tokens("old"), me); await vi.advanceTimersByTimeAsync(30_000);
    expect(getAccessToken()).toBe("access-old"); expect(getTenant().subject).toBe("human"); expect(getTenant().projectId).toBe("dev-project");
  });

  it("cancels on logout or tenant change", async () => {
    const fetch = vi.fn(); vi.stubGlobal("fetch", fetch);
    startSessionRefresh(tokens("old"), me); clearAccessToken(); await vi.advanceTimersByTimeAsync(30_000);
    expect(fetch).not.toHaveBeenCalled();
    setAccessToken("access-old"); startSessionRefresh(tokens("old"), me); setTenant({ projectId: "other" });
    await vi.advanceTimersByTimeAsync(30_000); expect(fetch).not.toHaveBeenCalled();
  });

  it("ignores an old refresh response after a new login", async () => {
    let resolve!: (value: Response) => void;
    const fetch = vi.fn().mockReturnValue(new Promise<Response>((done) => { resolve = done; }));
    vi.stubGlobal("fetch", fetch); startSessionRefresh(tokens("old"), me);
    await vi.advanceTimersByTimeAsync(30_000); setAccessToken("another-login"); resolve(response(tokens("late")));
    await vi.advanceTimersByTimeAsync(0);
    expect(getAccessToken()).toBe("another-login"); expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("keeps legacy login working when no usable refresh metadata was returned", async () => {
    const fetch = vi.fn(); vi.stubGlobal("fetch", fetch);
    startSessionRefresh({ accessToken: "access-old" }, me); await vi.advanceTimersByTimeAsync(300_000);
    expect(fetch).not.toHaveBeenCalled(); expect(getAccessToken()).toBe("access-old");
  });
});
