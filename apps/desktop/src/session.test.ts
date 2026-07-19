/** TWC.3 session unit tests (memory fallback, no Tauri) */
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  applyTokens,
  isLoggedIn,
  logout,
  restoreSession,
  secureGet,
  secureSet,
  REFRESH_KEY,
} from "./session";
import { clearAccessToken, getAccessToken, tenantAuthHeaders } from "@aos-web/api/tenant";

describe("TWC.3 session", () => {
  beforeEach(async () => {
    clearAccessToken();
    await logout();
  });

  it("stores refresh via secure layer and restores access", async () => {
    await applyTokens({ accessToken: "tok-access-1", tokenKind: "oidc" });
    expect(getAccessToken()).toBe("tok-access-1");
    expect(await secureGet(REFRESH_KEY)).toBe("tok-access-1");
    expect(isLoggedIn()).toBe(true);
    expect(tenantAuthHeaders().Authorization).toBe("Bearer tok-access-1");

    clearAccessToken();
    expect(isLoggedIn()).toBe(false);
    const ok = await restoreSession();
    expect(ok).toBe(true);
    expect(getAccessToken()).toBe("tok-access-1");
  });

  it("logout clears memory and secure entry", async () => {
    await secureSet(REFRESH_KEY, "x");
    await applyTokens({ accessToken: "y" });
    await logout();
    expect(getAccessToken()).toBeNull();
    expect(await secureGet(REFRESH_KEY)).toBeNull();
  });

  it("never logs raw token in applyTokens console payload shape", async () => {
    const spy = vi.spyOn(console, "info").mockImplementation(() => undefined);
    await applyTokens({ accessToken: "super-secret-token", tokenKind: "oidc" });
    const joined = spy.mock.calls.map((c) => JSON.stringify(c)).join(" ");
    expect(joined).not.toContain("super-secret-token");
    spy.mockRestore();
  });
});
