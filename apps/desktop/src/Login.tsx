/** TWC.3 · UI-03 登录 */
import { FormEvent, useState } from "react";
import { getApiBase } from "@aos-web/api/apiBase";
import { LOCAL_PLATFORM_NAME } from "@aos-web/lib/productCopy";
import { loginDev } from "./session";

export function Login({ onLoggedIn }: { onLoggedIn: () => void }) {
  const [subject, setSubject] = useState("alice");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function onDev(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      await loginDev({ subject: subject.trim() || "alice" });
      onLoggedIn();
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : String(ex));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="aos-desktop-welcome" data-ui="UI-03">
      <h1>登录 AOS 桌面</h1>
      <p>
        连接 <code>{getApiBase()}</code> · 会话 Refresh 存钥匙串（生产）· Access 仅内存
      </p>
      <form onSubmit={(e) => void onDev(e)}>
        <label>
          开发账号 subject（非生产）
          <input
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            disabled={busy}
          />
        </label>
        {err ? <p className="aos-desktop-err">{err}</p> : null}
        <div className="aos-desktop-welcome-actions">
          <button type="submit" disabled={busy}>
            {busy ? "登录中…" : "开发令牌登录"}
          </button>
        </div>
      </form>
      <p className="aos-desktop-welcome-hint">
        企业 OIDC：请使用系统浏览器回调 <code>aos://auth/callback</code>（TWC.5）。
        勿将「{LOCAL_PLATFORM_NAME}」称为 Apollo。
      </p>
    </div>
  );
}
