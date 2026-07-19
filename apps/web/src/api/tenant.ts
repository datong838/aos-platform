/**
 * TWA.2 — 会话租户上下文（工作区 = project_id）
 * 真源：GET /v1/me；禁止各页散落写死 X-Org-Id / X-Project-Id
 */
export type TenantContext = {
  orgId: string;
  projectId: string;
  workspaceName: string;
  subject?: string;
  roles?: string[];
};

const STORAGE_KEY = "aos-tenant-v1";

/** 开发默认落入「测试工作区」（技术 id 暂与历史种子兼容为 dev-project） */
const DEFAULT_TENANT: TenantContext = {
  orgId: "dev-org",
  projectId: "dev-project",
  workspaceName: "测试工作区",
};

let current: TenantContext = loadStored() ?? { ...DEFAULT_TENANT };

/** Access token 覆盖（桌面登录 TWC.3；Web 默认仍 Bearer dev） */
let accessTokenOverride: string | null = null;

export function setAccessToken(token: string | null) {
  accessTokenOverride = token && token.trim() ? token.trim() : null;
  console.info("[aos-tenant]", {
    event: "access_token_set",
    present: Boolean(accessTokenOverride),
  });
}

export function getAccessToken(): string | null {
  return accessTokenOverride;
}

export function clearAccessToken() {
  accessTokenOverride = null;
}

function loadStored(): TenantContext | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as TenantContext;
    if (parsed?.orgId && parsed?.projectId) return parsed;
  } catch {
    /* ignore */
  }
  return null;
}

function persist(t: TenantContext) {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(t));
  } catch {
    /* ignore */
  }
}

export function getTenant(): TenantContext {
  return current;
}

export function setTenant(partial: Partial<TenantContext>) {
  current = {
    ...current,
    ...partial,
    workspaceName:
      partial.workspaceName ||
      (partial.projectId === "dev-project" || partial.projectId === "test-workspace"
        ? "测试工作区"
        : partial.workspaceName || current.workspaceName),
  };
  persist(current);
  console.info("[aos-tenant]", {
    orgId: current.orgId,
    projectId: current.projectId,
    workspaceName: current.workspaceName,
  });
  if (typeof window !== "undefined") {
    window.dispatchEvent(
      new CustomEvent("aos-tenant-updated", { detail: { ...current } }),
    );
  }
}

export function tenantAuthHeaders(): Record<string, string> {
  const t = getTenant();
  const bearer = accessTokenOverride || "dev";
  return {
    Authorization: `Bearer ${bearer}`,
    "X-Org-Id": t.orgId,
    "X-Project-Id": t.projectId,
    "Content-Type": "application/json",
  };
}

export type MeResponse = {
  subject: string;
  orgId: string;
  projectId: string;
  workspaceName?: string;
  roles: string[];
  markings: string[];
  tokenKind: string;
};

/** 用 /v1/me 刷新上下文（须在 API 可达后调用） */
export function applyMeToTenant(me: MeResponse) {
  setTenant({
    orgId: me.orgId,
    projectId: me.projectId,
    workspaceName:
      me.workspaceName ||
      (me.projectId === "dev-project" || me.projectId === "test-workspace"
        ? "测试工作区"
        : me.projectId),
    subject: me.subject,
    roles: me.roles || [],
  });
}

export { DEFAULT_TENANT, STORAGE_KEY };
