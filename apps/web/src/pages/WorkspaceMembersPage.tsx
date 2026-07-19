/** TWA.7 / TWA.12 — 工作区成员（姓名/邮箱/手机） */
import { useCallback, useEffect, useState } from "react";
import { PageChrome } from "../components/PageChrome";
import { apiGet, apiPost, apiDelete } from "../api/client";
import { getTenant } from "../api/tenant";

type Member = {
  subject: string;
  role: string;
  orgId?: string;
  projectId?: string;
  email?: string;
  phone?: string;
  title?: string;
  displayName?: string;
  displayLabel?: string;
};
type AuditRow = { id: string; ts: string; action: string; actorId: string };

const ROLES = ["owner", "admin", "editor", "viewer"] as const;

function looksLikeEmail(v: string): boolean {
  return v.includes("@");
}

function looksLikePhone(v: string): boolean {
  const d = v.replace(/[^\d+]/g, "");
  return (
    d.length >= 8 &&
    (/^\+?\d+$/.test(d) || /^1\d{10}$/.test(v.replace(/\s/g, "")))
  );
}

export function WorkspaceMembersPage() {
  const tenant = getTenant();
  const [members, setMembers] = useState<Member[]>([]);
  const [audit, setAudit] = useState<AuditRow[]>([]);
  const [identity, setIdentity] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [role, setRole] = useState<string>("viewer");
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");

  const reload = useCallback(async () => {
    setErr("");
    try {
      const wid = getTenant().projectId;
      const [m, a] = await Promise.all([
        apiGet<{ items: Member[] }>(
          `/v1/workspaces/${encodeURIComponent(wid)}/members`,
        ),
        apiGet<{ items: AuditRow[] }>("/v1/audit"),
      ]);
      setMembers(m.items || []);
      setAudit((a.items || []).slice(0, 12));
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void reload();
    function onWs() {
      void reload();
    }
    window.addEventListener("aos-workspace-changed", onWs);
    return () => window.removeEventListener("aos-workspace-changed", onWs);
  }, [reload]);

  async function onAdd() {
    setMsg("");
    setErr("");
    const raw = identity.trim();
    if (!raw) return;
    const body: Record<string, string> = { role };
    if (displayName.trim()) body.displayName = displayName.trim();
    if (looksLikeEmail(raw)) {
      body.email = raw;
    } else if (looksLikePhone(raw)) {
      body.phone = raw;
    } else {
      body.subject = raw;
    }
    try {
      await apiPost(
        `/v1/workspaces/${encodeURIComponent(getTenant().projectId)}/members`,
        body,
      );
      setIdentity("");
      setDisplayName("");
      setMsg("已添加成员");
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  async function onRemove(sub: string) {
    setErr("");
    try {
      await apiDelete(
        `/v1/workspaces/${encodeURIComponent(getTenant().projectId)}/members/${encodeURIComponent(sub)}`,
      );
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <PageChrome
      title="工作区成员"
      lede={`${tenant.workspaceName} · 姓名 / 邮箱 / 手机 · 角色与审计`}
    >
      <p className="aos-muted">请用下方表单继续添加真实同事。</p>
      {err ? <p className="aos-error">{err}</p> : null}
      {msg ? <p className="aos-muted">{msg}</p> : null}

      <div className="aos-members-form">
        <input
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          placeholder="姓名（可选）"
          aria-label="姓名"
        />
        <input
          value={identity}
          onChange={(e) => setIdentity(e.target.value)}
          placeholder="邮箱或手机号"
          aria-label="邮箱或手机号"
        />
        <select
          value={role}
          onChange={(e) => setRole(e.target.value)}
          aria-label="角色"
        >
          {ROLES.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
        <button
          type="button"
          className="btn-primary"
          onClick={() => void onAdd()}
          disabled={!identity.trim()}
        >
          添加
        </button>
      </div>

      <table className="aos-table">
        <thead>
          <tr>
            <th>姓名</th>
            <th>邮箱</th>
            <th>手机</th>
            <th>角色</th>
            <th>说明</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {members.map((m) => (
            <tr key={m.subject}>
              <td>{m.displayName || m.displayLabel || m.subject}</td>
              <td>{m.email || "—"}</td>
              <td>{m.phone || "—"}</td>
              <td>{m.role}</td>
              <td className="aos-muted">{m.title || <code>{m.subject}</code>}</td>
              <td>
                <button
                  type="button"
                  className="btn"
                  onClick={() => void onRemove(m.subject)}
                >
                  移除
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3 className="aos-h3">最近审计</h3>
      <ul className="aos-audit-list">
        {audit.map((a) => (
          <li key={a.id}>
            <code>{a.action}</code> · {a.actorId} · {a.ts}
          </li>
        ))}
      </ul>
    </PageChrome>
  );
}
