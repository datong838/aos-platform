/** TWC.2 / TWC.12 / 173 · UI-01 首次启动欢迎（产品话术） */
import { FormEvent, useMemo, useState } from "react";
import { getApiBase, setApiBase } from "@aos-web/api/apiBase";
import { getChannelConfig, shouldSkipWelcomeForce } from "./channel";

export function Welcome({ onEnterShell }: { onEnterShell: () => void }) {
  const channel = useMemo(() => getChannelConfig(), []);
  const [base, setBase] = useState(() => getApiBase());
  const canSkip = shouldSkipWelcomeForce(channel);

  function onSave(e: FormEvent) {
    e.preventDefault();
    setApiBase(base);
    onEnterShell();
  }

  return (
    <div className="aos-desktop-welcome" data-ui="UI-01">
      <h1>欢迎使用 AOS 桌面</h1>
      <p>业务操作系统座舱 · 请连接您的平台</p>
      {canSkip ? (
        <p className="aos-desktop-welcome-hint">
          也可改地址后点「保存并进入」。
        </p>
      ) : null}
      <form onSubmit={onSave}>
        <label>
          平台地址
          <input
            value={base}
            onChange={(e) => setBase(e.target.value)}
            placeholder="https://aos.example.com"
            required={channel.channel === "private"}
            aria-label="平台地址"
          />
        </label>
        <div className="aos-desktop-welcome-actions">
          <button
            type="button"
            className="aos-desktop-welcome-primary"
            onClick={onEnterShell}
          >
            直接进入
          </button>
          <button type="submit" className="aos-desktop-welcome-secondary">
            保存并进入
          </button>
        </div>
      </form>
    </div>
  );
}
