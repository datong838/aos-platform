/**
 * TWC.9 — 检查更新（清单可注入；无 CDN 时返回 null）
 */
import type { UpdateManifest } from "./verify";
import { verifyUpdateSignature } from "./verify";

const INJECT_KEY = "aos-update-manifest-v1";

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

export async function checkDesktopUpdate(
  currentVersion = "0.1.0",
): Promise<UpdateCheckResult> {
  let raw: string | null = null;
  try {
    raw = localStorage.getItem(INJECT_KEY);
  } catch {
    raw = null;
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
