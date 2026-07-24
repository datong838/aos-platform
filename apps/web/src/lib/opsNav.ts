/** TWC.7 / TWB.2 — 运维交付（Apollo）侧栏展开策略 */
const STORAGE_KEY = "aos-ops-nav-open-v1";

const OPS_ADMIN_ROLES = new Set([
  "platform_admin",
  "admin",
  "developer",
  "dev",
]);

export function isDesktopShell(): boolean {
  if (typeof document === "undefined") return false;
  return Boolean(document.querySelector('[data-shell="desktop"]'));
}

export function rolesExpandOpsByDefault(roles: string[] | undefined): boolean {
  if (!roles?.length) return false;
  return roles.some((r) => OPS_ADMIN_ROLES.has(String(r).toLowerCase()));
}

/** 手动偏好优先；否则桌面 + 运维角色 → 默认展开；其余折叠 */
export function resolveOpsNavDefaultOpen(roles?: string[]): boolean {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw === "1") return true;
    if (raw === "0") return false;
  } catch {
    /* ignore */
  }
  if (isDesktopShell() && rolesExpandOpsByDefault(roles)) return true;
  return false;
}

export function persistOpsNavOpen(open: boolean): void {
  try {
    localStorage.setItem(STORAGE_KEY, open ? "1" : "0");
  } catch {
    /* ignore */
  }
  console.info("[aos-ops-nav]", { event: "persist", open });
}

export function expandOpsNav(): void {
  persistOpsNavOpen(true);
  window.dispatchEvent(new CustomEvent("aos-ops-nav-expand"));
}

export { STORAGE_KEY, OPS_ADMIN_ROLES };
