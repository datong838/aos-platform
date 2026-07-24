/** Appearance — localStorage key `aos-appearance` per T-UI §4.4 */
export type AppearancePreference = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

export const APPEARANCE_STORAGE_KEY = "aos-appearance";

export function readAppearancePreference(
  storage: Pick<Storage, "getItem"> = localStorage,
): AppearancePreference {
  const raw = storage.getItem(APPEARANCE_STORAGE_KEY);
  if (raw === "light" || raw === "dark" || raw === "system") return raw;
  return "dark";
}

export function resolveTheme(
  preference: AppearancePreference,
  systemDark: boolean,
): ResolvedTheme {
  if (preference === "light") return "light";
  if (preference === "dark") return "dark";
  return systemDark ? "dark" : "light";
}

export function applyThemeToDocument(
  theme: ResolvedTheme,
  el: HTMLElement = document.documentElement,
): void {
  el.setAttribute("data-aos-theme", theme);
}

export function persistAppearance(
  preference: AppearancePreference,
  storage: Pick<Storage, "setItem"> = localStorage,
): void {
  storage.setItem(APPEARANCE_STORAGE_KEY, preference);
}
