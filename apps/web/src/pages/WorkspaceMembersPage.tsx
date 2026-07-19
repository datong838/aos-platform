/** TWA.7 — 工作区成员管理 */
import { useCallback, useEffect, useState } from "react";
import { PageChrome } from "../components/PageChrome";
import { apiGet, apiPost, apiDelete } from "../api/client";
import { getTenant } from "../api/tenant";

type Member = { subject: string; role: string; orgId?: string; projectId?: string };
type AuditRow = { id: string; ts: string; action: string; actorId: string };

const ROLES = ["owner", "admin", "editor", "viewer"] as const;

export function WorkspaceMembersPage() {
  const tenant = getTenant();
  const [members, setMembers] = useState<Member[]>([]);
  const [audit, setAudit] = useState<AuditRow[]>([]);
  const [subject, setSubject] = useState("");
  const [role, setRole] = useState<string>("viewer");
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");

  const reload = useCallback(async () => {
    setErr("");
    try {
      const wid = getTenant().projectId;
      const [m, a] = await Promise.all([
        apiGet<{ items: Member[] }>(`/v1/workspaces/${encodeURIComponent(wid)}/members`),
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
    try {
      await apiPost(`/v1/workspaces/${encodeURIComponent(getTenant().projectId)}/members`, {
        subject: subject.trim(),
        role,
      });
      setSubject("");
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
      lede={`${tenant.workspaceName} · 成员角色与审计（TWA.7）`}
    >
      {err ? <p className="aos-error">{err}</p> : null}
      {msg ? <p className="aos-muted">{msg}</p> : null}

      <div className="aos-members-form">
        <input
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          placeholder="subject（如 carol）"
          aria-label="成员 subject"
        />
        <select value={role} onChange={(e) => setRole(e.target.value)} aria-label="角色">
          {ROLES.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
        <button type="button" onClick={() => void onAdd()} disabled={!subject.trim()}>
          添加
        </button>
      </div>

      <table className="aos-table">
        <thead>
          <tr>
            <th>成员</th>
            <th>角色</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {members.map((m) => (
            <tr key={m.subject}>
              <td>{m.subject}</td>
              <td>{m.role}</td>
              <td>
                <button type="button" onClick={() => void onRemove(m.subject)}>
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
