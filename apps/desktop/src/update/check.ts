/**
 * TWC.9 / 199m — 检查更新（注入清单 · 或远程 manifest URL）
 */
import type { UpdateManifest } from "./verify";
import { verifyUpdateSignature } from "./verify";

const INJECT_KEY = "aos-update-manifest-v1";
export const UPDATE_SOURCE_URL_KEY = "aos-update-source-url";

export type UpdateCheckResult =
  | { status: "none" }
  | { status: "available"; manifest: UpdateManifest }
  | { status: "invalid"; reason: string };

/** 测试/运维注入清单（localStorage）；正式环境改为更新源 URL */
export function injectUpdateManifest(m: UpdateManifest | null): void {
  try {
    if (!m) localStorage.removeItem(INJECT_KEY);
    else localStorage.setItem(INJECT_KEY, JSON.stringify(m));
  } catch {
    /* ignore */
  }
}

export function setUpdateSourceUrl(url: string | null): void {
  try {
    if (!url) localStorage.removeItem(UPDATE_SOURCE_URL_KEY);
    else localStorage.setItem(UPDATE_SOURCE_URL_KEY, url.trim());
  } catch {
    /* ignore */
  }
}

export function getUpdateSourceUrl(): string | null {
  try {
    const env =
      typeof import.meta !== "undefined" &&
      (import.meta as { env?: Record<string, string> }).env
        ?.VITE_AOS_UPDATE_MANIFEST_URL;
    if (env && String(env).trim()) return String(env).trim();
  } catch {
    /* ignore */
  }
  try {
    const u = localStorage.getItem(UPDATE_SOURCE_URL_KEY);
    return u && u.trim() ? u.trim() : null;
  } catch {
    return null;
  }
}

async function loadManifestRaw(): Promise<string | null> {
  const source = getUpdateSourceUrl();
  if (source) {
    const res = await fetch(source);
    if (!res.ok) {
      throw new Error(`更新源 HTTP ${res.status}`);
    }
    return await res.text();
  }
  try {
    return localStorage.getItem(INJECT_KEY);
  } catch {
    return null;
  }
}

export async function checkDesktopUpdate(
  currentVersion = "0.1.0",
): Promise<UpdateCheckResult> {
  let raw: string | null = null;
  try {
    raw = await loadManifestRaw();
  } catch (e) {
    return {
      status: "invalid",
      reason: e instanceof Error ? e.message : String(e),
    };
  }
  if (!raw) {
    console.info("[aos-update]", { event: "check", status: "none" });
    return { status: "none" };
  }
  let manifest: UpdateManifest;
  try {
    manifest = JSON.parse(raw) as UpdateManifest;
  } catch {
    return { status: "invalid", reason: "清单 JSON 无效" };
  }
  const v = await verifyUpdateSignature(manifest);
  if (!v.ok) {
    return { status: "invalid", reason: v.reason };
  }
  if (manifest.version === currentVersion) {
    return { status: "none" };
  }
  console.info("[aos-update]", {
    event: "check",
    status: "available",
    version: manifest.version,
  });
  return { status: "available", manifest };
}

export { INJECT_KEY };
