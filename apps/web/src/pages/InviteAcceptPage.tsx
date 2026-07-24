/** TWA.10 — 接受组织邀请深链 */
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { PageChrome } from "../components/PageChrome";
import { apiGet, apiPost } from "../api/client";
import { setTenant } from "../api/tenant";
import { clearWorkspaceLocalCache } from "../lib/workspaceCache";

type Preview = {
  token: string;
  orgId: string;
  orgName: string;
  projectId: string;
  role: string;
  status: string;
  alreadyMember?: boolean;
  expiresAt?: string;
};

export function InviteAcceptPage() {
  const { token = "" } = useParams();
  const navigate = useNavigate();
  const [preview, setPreview] = useState<Preview | null>(null);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      if (!token) {
        setErr("缺少邀请 token");
        return;
      }
      try {
        const p = await apiGet<Preview>(`/v1/org-invites/${encodeURIComponent(token)}`);
        if (!cancelled) setPreview(p);
      } catch (e) {
        if (!cancelled) setErr(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  async function onAccept() {
    if (!token) return;
    setBusy(true);
    setErr("");
    try {
      const out = await apiPost<{
        orgId: string;
        projectId: string;
        orgName: string;
        workspaceName: string;
      }>(`/v1/org-invites/${encodeURIComponent(token)}/accept`, {});
      clearWorkspaceLocalCache("invite-accept");
      setTenant({
        orgId: out.orgId,
        projectId: out.projectId,
        workspaceName: out.workspaceName,
      });
      setMsg(`已加入「${out.orgName}」`);
      window.dispatchEvent(
        new CustomEvent("aos-workspace-changed", {
          detail: { orgId: out.orgId, projectId: out.projectId },
        }),
      );
      navigate("/", { replace: true });
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <PageChrome title="接受组织邀请" lede="通过邀请链接加入组织">
      {err ? <p className="aos-error">{err}</p> : null}
      {msg ? <p className="aos-muted">{msg}</p> : null}
      {preview ? (
        <div>
          <p>
            组织：<strong>{preview.orgName}</strong>
            <span className="aos-muted"> · {preview.orgId}</span>
          </p>
          <p>
            角色：{preview.role} · 状态：{preview.status}
            {preview.expiresAt ? ` · 有效至 ${preview.expiresAt}` : null}
          </p>
          {preview.alreadyMember ? (
            <p className="aos-muted">你已是该组织成员。</p>
          ) : preview.status === "active" ? (
            <button
              type="button"
              className="btn-primary"
              disabled={busy}
              onClick={() => void onAccept()}
            >
              接受邀请并加入
            </button>
          ) : (
            <p className="aos-error">邀请不可用（{preview.status}）</p>
          )}
        </div>
      ) : !err ? (
        <p className="aos-muted">加载邀请…</p>
      ) : null}
      <p style={{ marginTop: "1.5rem" }}>
        <Link to="/org/membership">组织与加入</Link>
      </p>
    </PageChrome>
  );
}
