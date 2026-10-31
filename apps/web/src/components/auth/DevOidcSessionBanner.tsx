import { useEffect, useState } from "react";
import { getAccessToken } from "../../api/tenant";
import { isLoginGateSkipped } from "../../config/devAuthBypass";
import { LocalPasswordLoginForm } from "./LocalLoginGate";

/** Dev-only: login gate is skipped but API calls still need a restored OIDC session. */
export function DevOidcSessionBanner() {
  const [missing, setMissing] = useState(() => isLoginGateSkipped() && !getAccessToken());
  const [expanded, setExpanded] = useState(false);
  useEffect(() => {
    if (!isLoginGateSkipped()) return;
    const update = () => {
      const nextMissing = !getAccessToken();
      setMissing(nextMissing);
      if (!nextMissing) setExpanded(false);
    };
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
        当前可继续开发预览；费用、预算和配置办理仍需本人真实登录。
      </span>
      <button type="button" style={{ marginLeft: 8 }} aria-expanded={expanded} onClick={() => setExpanded((value) => !value)}>
        {expanded ? "收起登录" : "办理前登录"}
      </button>
      {expanded ? <div role="dialog" aria-label="开发期按需登录" style={{ maxWidth: 420, padding: "12px 0 4px" }}>
        <LocalPasswordLoginForm
          description="仅为当前标签建立本人 OIDC 会话；登录不会自动发起费用、预算或配置操作。"
          onCancel={() => setExpanded(false)}
        />
      </div> : null}
    </div>
  );
}
