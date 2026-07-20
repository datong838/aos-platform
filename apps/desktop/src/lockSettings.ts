/** 196m — desktop require-unlock-on-resume settings (default off). */
export const REQUIRE_UNLOCK_KEY = "aos.requireUnlockOnResume";

export function getRequireUnlockOnResume(): boolean {
  try {
    const env =
      typeof import.meta !== "undefined" &&
      (import.meta as { env?: Record<string, string> }).env?.VITE_AOS_REQUIRE_UNLOCK;
    if (env === "1" || env === "true") return true;
  } catch {
    /* ignore */
  }
  if (typeof localStorage === "undefined") return false;
  return localStorage.getItem(REQUIRE_UNLOCK_KEY) === "1";
}

export function setRequireUnlockOnResume(on: boolean): void {
  if (typeof localStorage === "undefined") return;
  if (on) localStorage.setItem(REQUIRE_UNLOCK_KEY, "1");
  else localStorage.removeItem(REQUIRE_UNLOCK_KEY);
}
