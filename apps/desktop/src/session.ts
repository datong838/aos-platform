/** TWC.3 — 会话：Access 内存 · Refresh/令牌 → 钥匙串（Tauri）或内存回退 */
import { invoke } from "@tauri-apps/api/core";
import { setAccessToken, clearAccessToken, getAccessToken } from "@aos-web/api/tenant";
import { getApiBase } from "@aos-web/api/apiBase";
import { getTenant } from "@aos-web/api/tenant";

const REFRESH_KEY = "aos.refreshToken";

/** vitest / 浏览器预览回退（非钥匙串；仅开发） */
const memStore = new Map<string, string>();

function isTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

export async function secureSet(key: string, value: string): Promise<void> {
  if (isTauri()) {
    await invoke("secure_set", { key, value });
    return;
  }
  memStore.set(key, value);
  console.info("[aos-desktop-session]", { event: "secure_set_mem", key });
}

export async function secureGet(key: string): Promise<string | null> {
  if (isTauri()) {
    return (await invoke<string | null>("secure_get", { key })) ?? null;
  }
  return memStore.get(key) ?? null;
}

export async function secureDelete(key: string): Promise<void> {
  if (isTauri()) {
    await invoke("secure_delete", { key });
    return;
  }
  memStore.delete(key);
}

export type TokenResponse = {
  accessToken: string;
  expiresIn?: number;
  tokenKind?: string;
  refreshToken?: string;
};

export async function loginDev(opts?: {
  subject?: string;
  orgId?: string;
  projectId?: string;
}): Promise<TokenResponse> {
  const t = getTenant();
  const body = {
    grantType: "dev",
    subject: opts?.subject || "alice",
    orgId: opts?.orgId || t.orgId,
    projectId: opts?.projectId || t.projectId,
    roles: ["developer"],
    markings: ["public", "restricted"],
  };
  const res = await fetch(`${getApiBase()}/v1/auth/token`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { message?: string }).message || `token HTTP ${res.status}`);
  }
  const data = (await res.json()) as TokenResponse;
  await applyTokens(data);
  console.info("[aos-desktop-session]", {
    event: "login_dev_ok",
    subject: body.subject,
    orgId: body.orgId,
    projectId: body.projectId,
    tokenKind: data.tokenKind,
  });
  return data;
}

export async function applyTokens(data: TokenResponse): Promise<void> {
  setAccessToken(data.accessToken);
  const refresh = data.refreshToken || data.accessToken;
  await secureSet(REFRESH_KEY, refresh);
}

export async function restoreSession(): Promise<boolean> {
  const stored = await secureGet(REFRESH_KEY);
  if (!stored) return false;
  setAccessToken(stored);
  console.info("[aos-desktop-session]", { event: "session_restored" });
  return true;
}

export async function logout(): Promise<void> {
  clearAccessToken();
  await secureDelete(REFRESH_KEY);
  console.info("[aos-desktop-session]", { event: "logout" });
}

export function isLoggedIn(): boolean {
  return Boolean(getAccessToken());
}

export { REFRESH_KEY };
