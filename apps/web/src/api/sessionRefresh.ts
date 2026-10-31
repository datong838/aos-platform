import { getApiBase } from "./apiBase";
import { applyMeToTenant, getAccessToken, getTenant, setAccessToken, type MeResponse } from "./tenant";
import { clearWebDevSession, persistWebDevSession } from "./webDevSession";

type Tokens = { accessToken: string; refreshToken: string; expiresIn: number };
type Session = Tokens & { subject: string; orgId: string; projectId: string; timer: ReturnType<typeof setTimeout> | null; detach: () => void };
let active: Session | null = null;

function tokens(value: unknown): Tokens | null {
  if (!value || typeof value !== "object") return null;
  const item = value as Partial<Tokens>;
  if (typeof item.accessToken !== "string" || !item.accessToken.trim() || item.accessToken.length > 65536
    || typeof item.refreshToken !== "string" || !item.refreshToken.trim() || item.refreshToken.length > 65536
    || !Number.isSafeInteger(item.expiresIn) || item.expiresIn! < 1 || item.expiresIn! > 86400) return null;
  return item as Tokens;
}

function current(session: Session): boolean {
  const tenant = getTenant();
  return active === session && getAccessToken() === session.accessToken && tenant.subject === session.subject
    && tenant.orgId === session.orgId && tenant.projectId === session.projectId;
}

export function stopSessionRefresh(): void {
  const session = active;
  active = null;
  if (!session) return;
  if (session.timer !== null) clearTimeout(session.timer);
  session.detach();
  clearWebDevSession();
}

function schedule(session: Session): void {
  const lifetime = session.expiresIn * 1000;
  session.timer = setTimeout(() => { void renew(session); }, lifetime - Math.min(30000, lifetime / 2));
}

async function renew(session: Session): Promise<void> {
  if (!current(session)) return;
  session.timer = null;
  try {
    const response = await fetch(`${getApiBase()}/v1/auth/token`, {
      method: "POST", cache: "no-store", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ grantType: "refresh_token", refreshToken: session.refreshToken }),
    });
    if (!current(session)) return;
    if (!response.ok) throw new Error();
    const next = tokens(await response.json());
    if (!next || !current(session)) throw new Error();
    const identity = await fetch(`${getApiBase()}/v1/me`, {
      cache: "no-store", headers: { Authorization: `Bearer ${next.accessToken}`, "X-Org-Id": session.orgId, "X-Project-Id": session.projectId },
    });
    if (!identity.ok) throw new Error();
    const me = await identity.json() as MeResponse;
    if (me.subject !== session.subject || me.orgId !== session.orgId || me.projectId !== session.projectId || me.tokenKind !== "oidc") throw new Error();
    if (!current(session)) return;
    Object.assign(session, next);
    setAccessToken(next.accessToken);
    persistWebDevSession(next);
    if (!current(session)) return;
    applyMeToTenant(me);
    if (current(session)) schedule(session);
  } catch {
    // A rotation may have occurred remotely: retain the page, never resend.
    if (active === session) stopSessionRefresh();
  }
}

/** Refresh in memory; dev bypass may mirror the session into tab-scoped storage for reload recovery. */
export function startSessionRefresh(value: unknown, me: MeResponse): void {
  stopSessionRefresh();
  const initial = tokens(value);
  if (!initial || me.tokenKind !== "oidc") return;
  const session: Session = { ...initial, subject: me.subject, orgId: me.orgId, projectId: me.projectId, timer: null, detach: () => {} };
  active = session;
  if (!current(session)) { stopSessionRefresh(); return; }
  const changed = () => { if (!current(session) && active === session) stopSessionRefresh(); };
  window.addEventListener("aos-auth-updated", changed);
  window.addEventListener("aos-tenant-updated", changed);
  session.detach = () => {
    window.removeEventListener("aos-auth-updated", changed);
    window.removeEventListener("aos-tenant-updated", changed);
  };
  persistWebDevSession(initial);
  schedule(session);
}
