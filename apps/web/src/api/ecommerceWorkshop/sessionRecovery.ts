import { getAccessToken, getAuthRevision, getTenant } from "../tenant";

export const WORKSHOP_SESSION_REJECTED = "aos-workshop-session-rejected";
export type WorkshopSessionIdentity = { authRevision: number; orgId: string; projectId: string };
export function workshopSessionIdentity(): WorkshopSessionIdentity {
  const tenant = getTenant();
  return { authRevision: getAuthRevision(), orgId: tenant.orgId, projectId: tenant.projectId };
}
/** Presentation hint only; the server remains the authentication authority. */
export function isCurrentWorkshopSession(value: unknown): value is WorkshopSessionIdentity {
  if (!value || typeof value !== "object" || Array.isArray(value) || Object.keys(value).length !== 3) return false;
  const identity = value as Partial<WorkshopSessionIdentity>;
  const current = workshopSessionIdentity();
  return Boolean(getAccessToken()) && Number.isSafeInteger(identity.authRevision)
    && identity.authRevision === current.authRevision
    && identity.orgId === current.orgId && identity.projectId === current.projectId;
}

export function reportWorkshopSessionRejection(status: number, headers: Record<string, string>, identity: WorkshopSessionIdentity): void {
  if (status !== 401 || typeof window === "undefined" || !isCurrentWorkshopSession(identity)) return;
  let sent: Headers;
  try { sent = new Headers(headers); } catch { return; }
  if (sent.get("Authorization") !== `Bearer ${getAccessToken()}`
      || sent.get("X-Org-Id") !== identity.orgId || sent.get("X-Project-Id") !== identity.projectId) return;
  // Never include credentials, response bodies or operation inputs in events.
  window.dispatchEvent(new CustomEvent(WORKSHOP_SESSION_REJECTED, { detail: { ...identity } }));
}
