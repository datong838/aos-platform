import { getApiBase } from "./apiBase";
import {
  applyMeToTenant,
  clearAccessToken,
  DEFAULT_TENANT,
  resetTenantToDefault,
  setAccessToken,
  type MeResponse,
} from "./tenant";
import { isLoginGateSkipped } from "../config/devAuthBypass";
import { startSessionRefresh, stopSessionRefresh } from "./sessionRefresh";
import { bootstrapTenantFromMe } from "./client";

const STORAGE_KEY = "aos-web-dev-session-v1";

type Stored = {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
};

function parseStored(raw: string | null): Stored | null {
  if (!raw) return null;
  try {
    const item = JSON.parse(raw) as Partial<Stored>;
    if (typeof item.accessToken !== "string" || !item.accessToken.trim() || item.accessToken.length > 65536
      || typeof item.refreshToken !== "string" || !item.refreshToken.trim() || item.refreshToken.length > 65536
      || !Number.isSafeInteger(item.expiresIn) || item.expiresIn! < 1 || item.expiresIn! > 86400) return null;
    return item as Stored;
  } catch {
    return null;
  }
}

/** Only when login gate is skipped: persist OIDC session across full page reloads. */
export function persistWebDevSession(tokens: { accessToken: string; refreshToken?: string; expiresIn?: number }): void {
  if (!isLoginGateSkipped()) return;
  if (typeof tokens.refreshToken !== "string" || !tokens.refreshToken.trim()) return;
  const expiresIn = Number.isSafeInteger(tokens.expiresIn) && tokens.expiresIn! >= 1 && tokens.expiresIn! <= 86400
    ? tokens.expiresIn!
    : 3600;
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify({
    accessToken: tokens.accessToken,
    refreshToken: tokens.refreshToken,
    expiresIn,
  } satisfies Stored));
}

export function clearWebDevSession(): void {
  sessionStorage.removeItem(STORAGE_KEY);
}

/** Restore in-memory session from sessionStorage; returns whether a usable access token is active. */
export async function restoreWebDevSession(): Promise<boolean> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 5000);
  try {
    return await restoreStoredWebDevSession(controller.signal);
  } finally {
    clearTimeout(timeout);
  }
}

async function restoreStoredWebDevSession(signal: AbortSignal): Promise<boolean> {
  if (!isLoginGateSkipped()) return false;
  const stored = parseStored(sessionStorage.getItem(STORAGE_KEY));
  if (!stored) return false;
  stopSessionRefresh();
  clearAccessToken();
  async function verify(accessToken: string): Promise<MeResponse | null> {
    const meResponse = await fetch(`${getApiBase()}/v1/me`, {
      cache: "no-store",
      signal,
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "X-Org-Id": DEFAULT_TENANT.orgId,
        "X-Project-Id": DEFAULT_TENANT.projectId,
      },
    });
    if (!meResponse.ok) return null;
    const me: MeResponse = await meResponse.json();
    if (!me.subject || me.orgId !== DEFAULT_TENANT.orgId || me.projectId !== DEFAULT_TENANT.projectId
      || me.tokenKind !== "oidc") return null;
    return me;
  }
  let me = await verify(stored.accessToken);
  let active = stored;
  if (!me) {
    try {
      const response = await fetch(`${getApiBase()}/v1/auth/token`, {
        method: "POST",
        cache: "no-store",
        signal,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ grantType: "refresh_token", refreshToken: stored.refreshToken }),
      });
      if (!response.ok) throw new Error();
      const next = parseStored(JSON.stringify(await response.json()));
      if (!next) throw new Error();
      me = await verify(next.accessToken);
      if (!me) throw new Error();
      active = next;
      persistWebDevSession(next);
    } catch {
      clearWebDevSession();
      clearAccessToken();
      return false;
    }
  }
  applyMeToTenant(me);
  setAccessToken(active.accessToken);
  startSessionRefresh(active, me);
  window.dispatchEvent(new Event("aos-auth-updated"));
  return true;
}

/**
 * Keep login optional during development without allowing the dev identity to
 * replace the QYH ecommerce tenant. A verified QYH OIDC session is reused;
 * otherwise the UI stays in the exact QYH scope and protected writes remain
 * unauthenticated/fail-closed.
 */
export async function prepareWebDevelopmentContext(): Promise<void> {
  if (!isLoginGateSkipped()) {
    await bootstrapTenantFromMe();
    return;
  }
  try {
    if (await restoreWebDevSession()) return;
  } catch {
    // Development preview must still mount when session verification is
    // unavailable. Only a verified session may populate the access identity.
    stopSessionRefresh();
    clearAccessToken();
  }
  resetTenantToDefault();
}
