/**
 * TWB.1 — configurable aos-api Base (env default + localStorage override).
 * Web only talks to aos-api; no engine direct calls.
 */
const STORAGE_KEY = "aos-api-base-v1";
const FALLBACK = "http://127.0.0.1:8080";

let runtimeOverride: string | null = null;

export function resolveDefaultApiBase(
  envValue: string | undefined = import.meta.env.VITE_AOS_API_BASE,
): string {
  const v = (envValue || "").trim();
  return v || FALLBACK;
}

function readStored(): string | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const t = raw.trim().replace(/\/$/, "");
    return t || null;
  } catch {
    return null;
  }
}

export function getApiBase(): string {
  if (runtimeOverride) return runtimeOverride.replace(/\/$/, "");
  const stored = readStored();
  if (stored) return stored;
  return resolveDefaultApiBase().replace(/\/$/, "");
}

export function setApiBase(next: string): string {
  const cleaned = next.trim().replace(/\/$/, "");
  if (!cleaned) {
    clearApiBaseOverride();
    return getApiBase();
  }
  runtimeOverride = cleaned;
  try {
    localStorage.setItem(STORAGE_KEY, cleaned);
  } catch {
    /* ignore */
  }
  console.info("[aos-api-base]", { event: "updated", base: cleaned });
  return cleaned;
}

export function clearApiBaseOverride(): void {
  runtimeOverride = null;
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
  console.info("[aos-api-base]", {
    event: "cleared",
    base: resolveDefaultApiBase(),
  });
}

export { STORAGE_KEY, FALLBACK };
