/** TWC.11 — Buddy 经典三栏为可选模式，非默认首页 */
export type DesktopViewMode = "cockpit" | "buddy-classic";

export const DEFAULT_DESKTOP_VIEW: DesktopViewMode = "cockpit";

export function isDefaultBuddyClassic(mode: DesktopViewMode): boolean {
  return mode === "buddy-classic" && DEFAULT_DESKTOP_VIEW === "buddy-classic";
}

export function resolveDesktopView(
  requested: DesktopViewMode | null | undefined,
): DesktopViewMode {
  if (requested === "buddy-classic") return "buddy-classic";
  return "cockpit";
}
