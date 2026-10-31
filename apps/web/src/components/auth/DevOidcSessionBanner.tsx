import { useEffect, useState } from "react";
import { getAccessToken } from "../../api/tenant";
import { isLoginGateSkipped } from "../../config/devAuthBypass";

/** Dev-only: login gate is skipped but API calls still need a restored OIDC session. */
export function DevOidcSessionBanner() {
  const [missing, setMissing] = useState(() => isLoginGateSkipped() && !getAccessToken());
  useEffect(() => {
    if (!isLoginGateSkipped()) return;
    const update = () => setMissing(!getAccessToken());
    update();
    window.addEventListener("aos-auth-updated", update);
    return () => window.removeEventListener("aos-auth-updated", update);
  }, []);
  if (!missing) return null;
  return (
    <div
      role="status"
      className="offline-banner"
      style={{ background: "var(--aos-warning-bg, #3d3420)", borderBottom: "1px solid var(--aos-border, #444)" }}
    >
      <strong>开发模式</strong>
      <span style={{ marginLeft: 8 }}>
        未检测到 OIDC 会话，费用/预算办理可能返回 401。请在 <code>apps/web/.env</code> 临时设{" "}
        <code>VITE_AOS_SKIP_LOGIN_GATE=0</code>、重启 Web 后登录一次，再改回默认；会话会保存在本标签的 sessionStorage。
      </span>
    </div>
  );
}
