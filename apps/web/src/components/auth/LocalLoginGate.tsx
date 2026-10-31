import { useEffect, useState, type ReactNode, type FormEvent } from "react";
import { getApiBase } from "../../api/apiBase";
import { getAccessToken } from "../../api/tenant";
import { loginPassword } from "../../api/passwordLogin";
import { bootstrapTenantFromMe } from "../../api/client";
import { isLoginGateSkipped } from "../../config/devAuthBypass";

type LocalPasswordLoginFormProps = {
  description?: string;
  onCancel?: () => void;
};

/** Shared human login form; callers control when it is shown, never how credentials are handled. */
export function LocalPasswordLoginForm({
  description = "登录后进入你有权限访问的组织与工作区。",
  onCancel,
}: LocalPasswordLoginFormProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    const submitted = password;
    setPassword("");
    setBusy(true);
    setError("");
    try {
      await loginPassword(username, submitted);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "登录失败，请重试。");
    } finally {
      setBusy(false);
    }
  }

  return <form onSubmit={submit}>
    <p>{description}</p>
    <label>登录名<input autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} required disabled={busy} /></label>
    <label>密码<input type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required disabled={busy} /></label>
    {error && <p role="alert">{error}</p>}
    <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
      <button type="submit" disabled={busy}>{busy ? "登录中…" : "登录"}</button>
      {onCancel ? <button type="button" disabled={busy} onClick={onCancel}>取消</button> : null}
    </div>
  </form>;
}

/** Read the server's login policy before mounting business catalog consumers. */
export function LocalLoginGate({ children }: { children: ReactNode }) {
  const skipGate = isLoginGateSkipped();
  const [policy, setPolicy] = useState<"loading" | "legacy" | "password" | "error">("loading");
  const [retry, setRetry] = useState(0);
  const [authenticated, setAuthenticated] = useState(Boolean(getAccessToken()));
  useEffect(() => {
    if (skipGate) return;
    const controller = new AbortController();
    setPolicy("loading");
    fetch(`${getApiBase()}/v1/auth/oidc`, { cache: "no-store", signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error();
        const config = await response.json();
        if (config.allowDevToken === true) setPolicy("legacy");
        else if (config.allowDevToken === false && config.tokenUrlConfigured === true && config.grantTypes?.includes("password")) setPolicy("password");
        else throw new Error();
      }).catch(() => { if (!controller.signal.aborted) setPolicy("error"); });
    return () => controller.abort();
  }, [retry, skipGate]);
  useEffect(() => {
    const update = () => setAuthenticated(Boolean(getAccessToken()));
    window.addEventListener("aos-auth-updated", update);
    return () => window.removeEventListener("aos-auth-updated", update);
  }, []);
  useEffect(() => {
    if (!authenticated) return;
    void bootstrapTenantFromMe();
  }, [authenticated]);
  if (skipGate || policy === "legacy" || (policy === "password" && authenticated)) return <>{children}</>;
  return <main style={{ maxWidth: 420, margin: "12vh auto", padding: 24 }}>
    <h1>AOS 登录</h1>
    {policy === "loading" ? <p role="status">正在读取登录配置…</p> : policy === "error" ? <>
      <p role="alert">登录服务暂不可用，请重新读取配置。</p>
      <button onClick={() => setRetry((value) => value + 1)}>重试</button>
    </> : <LocalPasswordLoginForm />}
  </main>;
}
