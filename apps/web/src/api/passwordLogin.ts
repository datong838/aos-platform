import { getApiBase } from "./apiBase";
import { applyMeToTenant, clearAccessToken, getTenant, setAccessToken, type MeResponse } from "./tenant";
import { startSessionRefresh, stopSessionRefresh } from "./sessionRefresh";

/** Original server authentication; credentials and refresh tokens never persist. */
export async function loginPassword(username: string, password: string): Promise<void> {
  stopSessionRefresh();
  clearAccessToken();
  try {
    const response = await fetch(`${getApiBase()}/v1/auth/token`, {
      method: "POST", cache: "no-store",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ grantType: "password", username, password }),
    });
    if (!response.ok) throw new Error();
    const tokens = await response.json();
    if (typeof tokens.accessToken !== "string" || !tokens.accessToken.trim()) throw new Error();
    const tenant = getTenant();
    const meResponse = await fetch(`${getApiBase()}/v1/me`, {
      cache: "no-store",
      headers: { Authorization: `Bearer ${tokens.accessToken}`, "X-Org-Id": tenant.orgId, "X-Project-Id": tenant.projectId },
    });
    if (!meResponse.ok) throw new Error();
    const me: MeResponse = await meResponse.json();
    if (!me.subject || !me.orgId || !me.projectId) throw new Error();
    applyMeToTenant(me);
    setAccessToken(tokens.accessToken);
    startSessionRefresh(tokens, me);
  } catch {
    clearAccessToken();
    throw new Error("登录失败，请核对账号、密码及工作区访问权限后重试。");
  }
}
