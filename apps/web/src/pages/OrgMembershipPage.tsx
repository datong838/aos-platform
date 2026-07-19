/** TWA.10 / TWA.11 — 组织与加入：申请、邀请、审批、清数据与删除 */
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { PageChrome } from "../components/PageChrome";
import { apiDelete, apiGet, apiPost } from "../api/client";
import { DEFAULT_TENANT, getTenant, setTenant } from "../api/tenant";
import { clearWorkspaceLocalCache } from "../lib/workspaceCache";

type DirOrg = {
  id: string;
  name: string;
  member?: boolean;
  joinPolicy?: string;
};

type JoinReq = {
  id: string;
  subject: string;
  message?: string;
  status: string;
  createdAt?: string;
};

type InviteOut = {
  token: string;
  invitePath: string;
  role: string;
  expiresAt: string;
  maxUses: number;
};

type DataSummary = {
  empty: boolean;
  total: number;
  counts?: Record<string, number>;
  workspaceCount?: number;
};

export function OrgMembershipPage() {
  const [directory, setDirectory] = useState<DirOrg[]>([]);
  const [pending, setPending] = useState<JoinReq[]>([]);
  const [invite, setInvite] = useState<InviteOut | null>(null);
  const [inviteQrSvg, setInviteQrSvg] = useState("");
  const [applyMsg, setApplyMsg] = useState("");
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [orgName, setOrgName] = useState("");
  const [wsData, setWsData] = useState<DataSummary | null>(null);
  const [orgData, setOrgData] = useState<DataSummary | null>(null);
  const [tenantLabel, setTenantLabel] = useState(() => getTenant());

  const reload = useCallback(async () => {
    setErr("");
    const t = getTenant();
    setTenantLabel(t);
    try {
      const dir = await apiGet<{ items: DirOrg[] }>("/v1/orgs/directory");
      setDirectory(dir.items || []);
      const cur = (dir.items || []).find((i) => i.id === t.orgId);
      setOrgName(cur?.name || t.orgId);
      try {
        const jr = await apiGet<{ items: JoinReq[] }>(
          `/v1/orgs/${encodeURIComponent(t.orgId)}/join-requests`,
        );
        setPending(jr.items || []);
      } catch {
        setPending([]);
      }
      try {
        const wd = await apiGet<DataSummary>(
          `/v1/workspaces/${encodeURIComponent(t.projectId)}/data`,
        );
        setWsData(wd);
      } catch {
        setWsData(null);
      }
      try {
        const od = await apiGet<DataSummary>(
          `/v1/orgs/${encodeURIComponent(t.orgId)}/data`,
        );
        setOrgData(od);
      } catch {
        setOrgData(null);
      }
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
    window.addEventListener("aos-tenant-updated", onWs);
    return () => {
      window.removeEventListener("aos-workspace-changed", onWs);
      window.removeEventListener("aos-tenant-updated", onWs);
    };
  }, [reload]);

  async function onCreateOrg() {
    setErr("");
    setMsg("");
    const name = window.prompt("新组织名称");
    if (!name?.trim()) return;
    try {
      const created = await apiPost<{
        id: string;
        defaultProjectId: string;
        workspaceName: string;
        name: string;
      }>("/v1/orgs", { name: name.trim() });
      clearWorkspaceLocalCache("org-create");
      setTenant({
        orgId: created.id,
        projectId: created.defaultProjectId,
        workspaceName: created.workspaceName,
      });
      setMsg(`已创建组织「${created.name}」并进入`);
      window.dispatchEvent(
        new CustomEvent("aos-workspace-changed", {
          detail: { orgId: created.id, projectId: created.defaultProjectId },
        }),
      );
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  async function onCreateWorkspace() {
    setErr("");
    setMsg("");
    const name = window.prompt("新工作区名称");
    if (!name?.trim()) return;
    try {
      const ws = await apiPost<{ id: string; name: string; orgId: string }>(
        "/v1/workspaces",
        { name: name.trim() },
      );
      clearWorkspaceLocalCache("workspace-create");
      setTenant({
        orgId: ws.orgId,
        projectId: ws.id,
        workspaceName: ws.name,
      });
      setMsg(`已创建工作区「${ws.name}」并进入`);
      window.dispatchEvent(
        new CustomEvent("aos-workspace-changed", {
          detail: { orgId: ws.orgId, projectId: ws.id, name: ws.name },
        }),
      );
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  async function onApply(org: DirOrg) {
    setErr("");
    setMsg("");
    try {
      await apiPost(`/v1/orgs/${encodeURIComponent(org.id)}/join-requests`, {
        message: applyMsg.trim() || `申请加入「${org.name}」`,
      });
      setMsg(`已提交加入「${org.name}」的申请，等待管理员审批`);
      setApplyMsg("");
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  async function onCreateInvite() {
    setErr("");
    setMsg("");
    setInviteQrSvg("");
    try {
      const out = await apiPost<InviteOut>(
        `/v1/orgs/${encodeURIComponent(getTenant().orgId)}/invites`,
        { role: "viewer", maxUses: 20, ttlHours: 168 },
      );
      setInvite(out);
      setMsg("邀请链接已生成");
      try {
        const qr = await apiGet<{ svg: string }>(
          `/v1/org-invites/${encodeURIComponent(out.token)}/qr?origin=${encodeURIComponent(window.location.origin)}`,
        );
        setInviteQrSvg(qr.svg || "");
      } catch {
        setInviteQrSvg("");
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  async function onDecide(id: string, decision: "approve" | "reject") {
    setErr("");
    try {
      await apiPost(
        `/v1/orgs/${encodeURIComponent(getTenant().orgId)}/join-requests/${encodeURIComponent(id)}/decide`,
        { decision, role: "viewer" },
      );
      setMsg(decision === "approve" ? "已批准" : "已拒绝");
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  async function onClearWorkspace() {
    if (!window.confirm("确认清理当前工作区内业务数据？成员不会被移除。")) return;
    setErr("");
    try {
      const t = getTenant();
      const out = await apiPost<DataSummary>(
        `/v1/workspaces/${encodeURIComponent(t.projectId)}/data/clear`,
        {},
      );
      setWsData(out);
      setMsg("当前工作区业务数据已清理");
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  async function onDeleteWorkspace() {
    if (!window.confirm("确认删除当前工作区？须已无业务数据。")) return;
    setErr("");
    try {
      const t = getTenant();
      await apiDelete(`/v1/workspaces/${encodeURIComponent(t.projectId)}`);
      clearWorkspaceLocalCache("workspace-delete");
      setTenant({
        ...t,
        projectId: "dev-project",
        workspaceName: "测试工作区",
      });
      setMsg("工作区已删除，已切回默认工作区（若仍存在）");
      window.dispatchEvent(
        new CustomEvent("aos-workspace-changed", {
          detail: { orgId: t.orgId, projectId: "dev-project" },
        }),
      );
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  async function onClearOrg() {
    if (!window.confirm("确认清理当前组织下全部工作区业务数据？")) return;
    setErr("");
    try {
      const t = getTenant();
      const out = await apiPost<DataSummary>(
        `/v1/orgs/${encodeURIComponent(t.orgId)}/data/clear`,
        {},
      );
      setOrgData(out);
      setMsg("组织业务数据已清理");
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  async function onDeleteOrg() {
    if (!window.confirm("确认删除当前组织？须组织内已无业务数据。此操作不可恢复。"))
      return;
    setErr("");
    try {
      const t = getTenant();
      await apiDelete(`/v1/orgs/${encodeURIComponent(t.orgId)}`);
      clearWorkspaceLocalCache("org-delete");
      setTenant({ ...DEFAULT_TENANT });
      setMsg("组织已删除，已回到默认组织上下文");
      window.dispatchEvent(
        new CustomEvent("aos-workspace-changed", {
          detail: {
            orgId: DEFAULT_TENANT.orgId,
            projectId: DEFAULT_TENANT.projectId,
          },
        }),
      );
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  const inviteUrl =
    invite && typeof window !== "undefined"
      ? `${window.location.origin}${invite.invitePath}`
      : invite?.invitePath || "";

  const wsCounts = wsData?.counts
    ? Object.entries(wsData.counts)
        .map(([k, v]) => `${k}=${v}`)
        .join(" · ")
    : "";

  return (
    <PageChrome
      title="组织与加入"
      lede={`${orgName} · 新建 / 邀请 / 申请 · 清数据与删除`}
    >
      {err ? <p className="aos-error">{err}</p> : null}
      {msg ? <p className="aos-muted">{msg}</p> : null}

      <div className="aos-members-form">
        <button type="button" className="btn-primary" onClick={() => void onCreateOrg()}>
          新建组织
        </button>
        <button type="button" className="btn-primary" onClick={() => void onCreateWorkspace()}>
          新建工作区
        </button>
        <button type="button" className="btn-primary" onClick={() => void onCreateInvite()}>
          生成邀请链接
        </button>
        <Link className="btn-nav" to="/workspace/members">
          工作区成员 →
        </Link>
      </div>

      {invite ? (
        <div className="aos-card" style={{ marginBottom: "1rem" }}>
          <p>
            邀请链接（角色 {invite.role} · 最多 {invite.maxUses} 次 · 至{" "}
            {invite.expiresAt}）
          </p>
          <code style={{ wordBreak: "break-all" }}>{inviteUrl}</code>
          <p className="aos-muted">
            将链接发给对方；对方打开后点「接受邀请」即可加入。也可扫下方二维码。
          </p>
          {inviteQrSvg ? (
            <div
              data-testid="invite-qr"
              style={{ marginTop: "0.75rem", maxWidth: 180 }}
              dangerouslySetInnerHTML={{ __html: inviteQrSvg }}
            />
          ) : null}
        </div>
      ) : null}

      <h3 className="aos-h3">清数据与删除（管理员）</h3>
      <p className="aos-muted">
        当前组织 <code>{tenantLabel.orgId}</code> · 工作区{" "}
        <code>{tenantLabel.projectId}</code>（{tenantLabel.workspaceName}）
      </p>
      <p className="aos-muted" data-testid="org-ws-data-summary">
        工作区数据：
        {wsData == null
          ? "加载中…"
          : wsData.empty
            ? "空（可删）"
            : `共 ${wsData.total} · ${wsCounts}`}
      </p>
      <p className="aos-muted" data-testid="org-org-data-summary">
        组织数据合计：
        {orgData == null
          ? "加载中…"
          : orgData.empty
            ? "空（可删）"
            : `共 ${orgData.total}（${orgData.workspaceCount ?? "?"} 个工作区）`}
      </p>
      <div className="aos-members-form">
        <button type="button" className="btn" onClick={() => void onClearWorkspace()}>
          清理当前工作区数据
        </button>
        <button
          type="button"
          className="btn btn-danger"
          onClick={() => void onDeleteWorkspace()}
          disabled={wsData != null && !wsData.empty}
          title={
            wsData != null && !wsData.empty ? "请先清理工作区数据" : "删除工作区"
          }
        >
          删除当前工作区
        </button>
        <button type="button" className="btn" onClick={() => void onClearOrg()}>
          清理当前组织数据
        </button>
        <button
          type="button"
          className="btn btn-danger"
          onClick={() => void onDeleteOrg()}
          disabled={orgData != null && !orgData.empty}
          title={
            orgData != null && !orgData.empty ? "请先清理组织数据" : "删除组织"
          }
        >
          删除当前组织
        </button>
      </div>

      <h3 className="aos-h3">待审批加入申请（当前组织）</h3>
      {pending.length === 0 ? (
        <p className="aos-muted">暂无待审申请（需组织管理员可见）</p>
      ) : (
        <table className="aos-table">
          <thead>
            <tr>
              <th>申请人</th>
              <th>留言</th>
              <th>时间</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {pending.map((r) => (
              <tr key={r.id}>
                <td>{r.subject}</td>
                <td>{r.message || "—"}</td>
                <td>{r.createdAt || "—"}</td>
                <td>
                  <button
                    type="button"
                    className="btn"
                    onClick={() => void onDecide(r.id, "approve")}
                  >
                    批准
                  </button>{" "}
                  <button
                    type="button"
                    className="btn"
                    onClick={() => void onDecide(r.id, "reject")}
                  >
                    拒绝
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h3 className="aos-h3">发现组织 · 申请加入</h3>
      <div className="aos-members-form">
        <input
          value={applyMsg}
          onChange={(e) => setApplyMsg(e.target.value)}
          placeholder="申请留言（可选）"
          aria-label="申请留言"
        />
      </div>
      <table className="aos-table">
        <thead>
          <tr>
            <th>组织</th>
            <th>状态</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {directory.map((o) => (
            <tr key={o.id}>
              <td>
                {o.name}
                <span className="aos-muted"> · {o.id}</span>
              </td>
              <td>{o.member ? "已加入" : o.joinPolicy || "可申请"}</td>
              <td>
                {o.member ? (
                  "—"
                ) : (
                  <button
                    type="button"
                    className="btn"
                    onClick={() => void onApply(o)}
                  >
                    加入{o.name}
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </PageChrome>
  );
}
