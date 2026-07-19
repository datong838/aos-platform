/** TWC.3 / 173 · UI-03 登录（产品话术；Dev 入口仅非生产） */
import { FormEvent, useState } from "react";
import { getApiBase } from "@aos-web/api/apiBase";
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
      const raw = ex instanceof Error ? ex.message : String(ex);
      const network =
        /load failed|failed to fetch|networkerror|无法连接|offline/i.test(raw);
      setErr(
        network
          ? "连不上平台，请确认平台已启动后再试"
          : raw || "登录失败",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="aos-desktop-welcome" data-ui="UI-03">
      <h1>登录</h1>
      <p>正在连接 {getApiBase()}</p>
      <form onSubmit={(e) => void onDev(e)}>
        <label>
          账号
          <input
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            disabled={busy}
            aria-label="账号"
            autoComplete="username"
          />
        </label>
        {err ? <p className="aos-desktop-err">{err}</p> : null}
        <div className="aos-desktop-welcome-actions">
          <button type="submit" disabled={busy}>
            {busy ? "登录中…" : "进入"}
          </button>
        </div>
      </form>
    </div>
  );
}
