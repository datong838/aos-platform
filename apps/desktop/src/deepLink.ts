/**
 * TWC.5 — aos:// 深链解析与白名单
 * 例：aos://open/workshop/inbox · aos://open/ontology?id=x · aos://auth/callback?...
 */
import { navPages } from "@aos-web/nav";

export type DeepLinkKind = "open" | "auth_callback" | "rejected";

export type DeepLinkResult = {
  kind: DeepLinkKind;
  path?: string;
  search?: string;
  raw: string;
  reason?: string;
};

const PENDING_KEY = "aos.desktop.pendingDeepLink";

function allowedPaths(): Set<string> {
  return new Set(navPages().map((p) => p.path));
}

/** 最长前缀匹配：/ontology/foo → /ontology 若登记 */
function matchWhitelistedPath(pathname: string): string | null {
  const exact = allowedPaths();
  if (exact.has(pathname)) return pathname;
  const candidates = [...exact]
    .filter((p) => p !== "/" && pathname.startsWith(p + "/"))
    .sort((a, b) => b.length - a.length);
  if (candidates[0]) return pathname; // nested under known page
  // also allow exact parent if path is parent itself
  if (exact.has(pathname)) return pathname;
  return null;
}

export function parseAosDeepLink(raw: string): DeepLinkResult {
  const trimmed = raw.trim();
  let url: URL;
  try {
    url = new URL(trimmed);
  } catch {
    return { kind: "rejected", raw: trimmed, reason: "invalid_url" };
  }
  if (url.protocol !== "aos:") {
    return { kind: "rejected", raw: trimmed, reason: "not_aos_scheme" };
  }

  // aos://open/workshop/inbox → host=open, pathname=/workshop/inbox
  // aos://auth/callback → host=auth, pathname=/callback
  const host = (url.hostname || "").toLowerCase();
  if (host === "auth" && (url.pathname === "/callback" || url.pathname === "callback")) {
    return {
      kind: "auth_callback",
      path: "/auth/callback",
      search: url.search || "",
      raw: trimmed,
    };
  }

  if (host === "open") {
    let path = url.pathname || "/";
    if (!path.startsWith("/")) path = `/${path}`;
    if (path.length > 1 && path.endsWith("/")) path = path.slice(0, -1);
    const matched = matchWhitelistedPath(path);
    if (!matched) {
      return {
        kind: "rejected",
        raw: trimmed,
        path,
        reason: "path_not_whitelisted",
      };
    }
    return {
      kind: "open",
      path: matched,
      search: url.search || "",
      raw: trimmed,
    };
  }

  return { kind: "rejected", raw: trimmed, reason: "unknown_host" };
}

export function queuePendingDeepLink(raw: string): void {
  try {
    sessionStorage.setItem(PENDING_KEY, raw);
  } catch {
    /* ignore */
  }
  console.info("[aos-deeplink]", { event: "queued" });
}

export function takePendingDeepLink(): string | null {
  try {
    const v = sessionStorage.getItem(PENDING_KEY);
    if (v) sessionStorage.removeItem(PENDING_KEY);
    return v;
  } catch {
    return null;
  }
}

export function navigateFromDeepLink(result: DeepLinkResult): boolean {
  if (result.kind !== "open" || !result.path) return false;
  const target = `${result.path}${result.search || ""}`;
  window.history.pushState({}, "", target);
  window.dispatchEvent(new PopStateEvent("popstate"));
  console.info("[aos-deeplink]", {
    event: "navigated",
    path: result.path,
  });
  return true;
}

export { PENDING_KEY };
