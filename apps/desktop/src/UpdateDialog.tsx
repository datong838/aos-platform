/** TWC.9 · UI-10 更新对话框 */
import type { UpdateManifest } from "./update/verify";
import { gateInstall } from "./update/verify";

type Props = {
  open: boolean;
  manifest: UpdateManifest | null;
  error?: string;
  onClose: () => void;
  onInstalled?: () => void;
};

export function UpdateDialog({
  open,
  manifest,
  error,
  onClose,
  onInstalled,
}: Props) {
  if (!open) return null;

  async function onInstall() {
    if (!manifest) return;
    const g = await gateInstall(manifest);
    if (!g.allowed) {
      window.alert(g.reason || "签名校验失败 · 请联系运维/管理员");
      console.warn("[aos-update]", {
        event: "install_blocked",
        version: manifest.version,
        reason: g.reason,
      });
      return;
    }
    // 真下载安装器后置；本刀门禁通过后仅记录放行（禁跳过验签）
    console.info("[aos-update]", {
      event: "install_allowed",
      version: manifest.version,
      urlHost: safeHost(manifest.url),
    });
    window.alert(
      `签名校验通过 · 版本 ${manifest.version}（正式下载安装通道后置）`,
    );
    onInstalled?.();
    onClose();
  }

  return (
    <div className="aos-desktop-about-backdrop" role="dialog" aria-label="软件更新">
      <div className="aos-desktop-about" data-ui="UI-10">
        <h2>软件更新</h2>
        {error ? (
          <p className="aos-desktop-update-err">{error}</p>
        ) : null}
        {manifest ? (
          <>
            <p>
              发现新版本 <strong>{manifest.version}</strong>
            </p>
            <p className="aos-muted">{manifest.notes || "暂无发行说明"}</p>
            <dl>
              <dt>校验</dt>
              <dd>
                <code>sha256={manifest.sha256.slice(0, 12)}…</code>
              </dd>
            </dl>
            <div className="aos-desktop-update-actions">
              {!manifest.force ? (
                <button type="button" onClick={onClose}>
                  稍后
                </button>
              ) : null}
              <button type="button" className="aos-desktop-update-primary" onClick={() => void onInstall()}>
                下载并安装
              </button>
            </div>
          </>
        ) : (
          <>
            <p>当前已是最新，或未配置更新源。</p>
            <button type="button" onClick={onClose}>
              关闭
            </button>
          </>
        )}
      </div>
    </div>
  );
}

function safeHost(url: string): string {
  try {
    return new URL(url).host;
  } catch {
    return "(invalid-url)";
  }
}
