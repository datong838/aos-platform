import { useEffect, useState } from "react";
import { clearAccessToken } from "../../api/tenant";
import { WORKSHOP_SESSION_REJECTED, isCurrentWorkshopSession, type WorkshopSessionIdentity } from "../../api/ecommerceWorkshop/sessionRecovery";

export function WorkshopSessionRecovery() {
  const [identity, setIdentity] = useState<WorkshopSessionIdentity | null>(null);
  useEffect(() => {
    const rejected = (event: Event) => {
      const detail: unknown = (event as CustomEvent<unknown>).detail;
      if (isCurrentWorkshopSession(detail)) setIdentity({ ...detail });
    };
    const changed = () => setIdentity(null);
    window.addEventListener(WORKSHOP_SESSION_REJECTED, rejected);
    window.addEventListener("aos-auth-updated", changed);
    window.addEventListener("aos-tenant-updated", changed);
    return () => {
      window.removeEventListener(WORKSHOP_SESSION_REJECTED, rejected);
      window.removeEventListener("aos-auth-updated", changed);
      window.removeEventListener("aos-tenant-updated", changed);
    };
  }, []);
  if (!identity) return null;
  return <section className="ecommerce-workshop-state is-forbidden" role="alert" aria-label="登录状态需要确认">
    <strong>登录状态需要重新确认</strong>
    <p>当前登录身份未通过服务校验。请先记录未保存的输入；重新登录后先回读原操作记录，系统不会自动重发操作。</p>
    <button type="button" onClick={() => {
      // A delayed click must never invalidate a newer session or tenant.
      if (isCurrentWorkshopSession(identity)) clearAccessToken();
      setIdentity(null);
    }}>重新登录</button>
  </section>;
}
