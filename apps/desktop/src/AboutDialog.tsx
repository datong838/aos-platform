/** TWC.4 · UI-07 关于本机 */
import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { getApiBase } from "@aos-web/api/apiBase";

type About = {
  productName: string;
  version: string;
  identifier: string;
};

export function AboutDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [info, setInfo] = useState<About | null>(null);

  useEffect(() => {
    if (!open) return;
    void (async () => {
      try {
        const a = await invoke<About>("about_info");
        setInfo(a);
      } catch {
        setInfo({
          productName: "AOS 桌面",
          version: "0.2.0-web",
          identifier: "com.aos.desktop",
        });
      }
    })();
  }, [open]);

  if (!open) return null;

  return (
    <div className="aos-desktop-about-backdrop" role="dialog" aria-label="关于本机">
      <div className="aos-desktop-about" data-ui="UI-07">
        <h2>{info?.productName || "AOS 桌面"}</h2>
        <dl>
          <dt>版本</dt>
          <dd>{info?.version || "…"}</dd>
          <dt>标识</dt>
          <dd>
            <code>{info?.identifier}</code>
          </dd>
          <dt>平台地址</dt>
          <dd>
            <code>{getApiBase()}</code>
          </dd>
          <dt>说明</dt>
          <dd>连接企业 AI 操作系统的桌面座舱</dd>
        </dl>
        <button type="button" onClick={onClose}>
          关闭
        </button>
      </div>
    </div>
  );
}
