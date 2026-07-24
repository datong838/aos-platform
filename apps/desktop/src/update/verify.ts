/**
 * TWC.9 — 更新清单验签（aos-v1；失败拒装）
 * 生产可换 cosign，UI 与门禁语义不变。
 */

export const UPDATE_KEY_ID = "aos-desktop-dev-v1";

export type UpdateManifest = {
  version: string;
  url: string;
  sha256: string;
  notes?: string;
  force?: boolean;
  signature: string;
};

export type VerifyResult =
  | { ok: true }
  | { ok: false; reason: string };

function canonical(m: Pick<UpdateManifest, "version" | "url" | "sha256">): string {
  return `${m.version}\n${m.url}\n${m.sha256}\n${UPDATE_KEY_ID}`;
}

/** 同步 SHA-256 hex（Web Crypto 异步包装见 signManifestAsync） */
export async function sha256Hex(text: string): Promise<string> {
  const data = new TextEncoder().encode(text);
  const digest = await crypto.subtle.digest("SHA-256", data);
  return [...new Uint8Array(digest)]
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

/** 开发/测试：由 canonical 派生合法签名（生产由发布流水线签） */
export async function signManifest(
  m: Pick<UpdateManifest, "version" | "url" | "sha256">,
): Promise<string> {
  const hex = await sha256Hex(`${canonical(m)}\n${UPDATE_KEY_ID}`);
  return `aos-v1:${hex}`;
}

export async function verifyUpdateSignature(
  m: UpdateManifest,
): Promise<VerifyResult> {
  if (!m.version?.trim() || !m.url?.trim() || !m.sha256?.trim()) {
    return { ok: false, reason: "清单字段不完整" };
  }
  if (!m.signature?.startsWith("aos-v1:")) {
    return { ok: false, reason: "未知签名算法或缺失签名" };
  }
  const expected = await signManifest(m);
  if (m.signature !== expected) {
    console.warn("[aos-update]", {
      event: "verify_failed",
      version: m.version,
      reason: "signature_mismatch",
    });
    return { ok: false, reason: "签名校验失败 · 请联系运维/管理员" };
  }
  console.info("[aos-update]", { event: "verify_ok", version: m.version });
  return { ok: true };
}

/**
 * 装前唯一门禁：失败绝不进入下载/安装。
 */
export async function gateInstall(
  m: UpdateManifest,
): Promise<{ allowed: boolean; reason?: string }> {
  const v = await verifyUpdateSignature(m);
  if (!v.ok) {
    return { allowed: false, reason: v.reason };
  }
  return { allowed: true };
}
