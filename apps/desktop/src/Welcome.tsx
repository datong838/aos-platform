/** TWC.2 / TWC.12 · UI-01 首次启动欢迎（API 不可达） */
import { FormEvent, useMemo, useState } from "react";
import { getApiBase, setApiBase, STORAGE_KEY } from "@aos-web/api/apiBase";
import { LOCAL_PLATFORM_NAME } from "@aos-web/lib/productCopy";
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
      <p>
        渠道：<code>{channel.channel}</code>
        {channel.productLabel ? ` · ${channel.productLabel}` : ""}
      </p>
      <p>
        请连接平台（aos-api）。本产品名是「{LOCAL_PLATFORM_NAME}」相关能力入口，
        <strong>不是</strong> Apollo。
      </p>
      {canSkip ? (
        <p className="aos-desktop-welcome-hint">
          已有渠道包预置地址，可跳过本页直接进入。
        </p>
      ) : null}
      <form onSubmit={onSave}>
        <label>
          平台地址（API Base）
          <input
            value={base}
            onChange={(e) => setBase(e.target.value)}
            placeholder="http://127.0.0.1:8080"
            required={channel.channel === "private"}
          />
        </label>
        <div className="aos-desktop-welcome-actions">
          <button type="submit">保存并进入</button>
          <button type="button" onClick={onEnterShell}>
            {canSkip ? "使用渠道预置，进入座舱" : "稍后配置，先进入座舱"}
          </button>
        </div>
      </form>
      <p className="aos-desktop-welcome-hint">
        存储键 {STORAGE_KEY} · 启停见 72 手册
      </p>
    </div>
  );
}
