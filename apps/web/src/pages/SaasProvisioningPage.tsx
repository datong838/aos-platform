/** TWB.6 — SaaS 开通台（运维面；非业务一级） */
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { PageChrome } from "../components/PageChrome";
import { apiGet, apiPost, apiPatch } from "../api/client";
import { BpBanner } from "./s2/blueprintUi";

type Tenant = {
  orgId: string;
  orgName: string;
  plan: string;
  status: string;
  ownerSubject: string;
  quota: {
    maxWorkspaces: number;
    maxMembers: number;
    maxStorageGb: number;
  };
};

export function SaasProvisioningPage() {
  const [items, setItems] = useState<Tenant[]>([]);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [orgId, setOrgId] = useState("");
  const [orgName, setOrgName] = useState("");
  const [owner, setOwner] = useState("alice");
  const [plan, setPlan] = useState("starter");

  const reload = useCallback(async () => {
    setErr("");
    try {
      const res = await apiGet<{ items: Tenant[] }>("/v1/ops/tenants");
      setItems(res.items || []);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  async function onProvision(e: FormEvent) {
    e.preventDefault();
    setMsg("");
    setErr("");
    try {
      await apiPost("/v1/ops/tenants", {
        orgId,
        orgName: orgName || orgId,
        ownerSubject: owner,
        plan,
      });
      setMsg(`已开通 ${orgId}`);
      setOrgId("");
      setOrgName("");
      await reload();
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : String(ex));
    }
  }

  async function bumpQuota(t: Tenant) {
    setErr("");
    try {
      await apiPatch(`/v1/ops/tenants/${encodeURIComponent(t.orgId)}/quota`, {
        maxWorkspaces: (t.quota?.maxWorkspaces || 5) + 5,
      });
      setMsg(`已上调 ${t.orgId} 工作区配额`);
      await reload();
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : String(ex));
    }
  }

  return (
    <PageChrome
      title="SaaS 开通"
      lede="我方运维开通租户 Org 与配额 · 计费外置 · 不面向租户业务员"
    >
      <BpBanner tone="info">
        属<strong>运维交付面</strong>。业务座舱只做组织/工作区管理；开通台不出现在业务一级推销。
      </BpBanner>

      {err ? <p className="aos-err">{err}</p> : null}
      {msg ? <p className="aos-muted">{msg}</p> : null}

      <form className="aos-saas-form" onSubmit={(e) => void onProvision(e)} data-ui="TWB-6">
        <label>
          Org Id
          <input
            value={orgId}
            onChange={(e) => setOrgId(e.target.value)}
            placeholder="acme-corp"
            required
          />
        </label>
        <label>
          显示名
          <input
            value={orgName}
            onChange={(e) => setOrgName(e.target.value)}
            placeholder="Acme 公司"
          />
        </label>
        <label>
          Owner
          <input value={owner} onChange={(e) => setOwner(e.target.value)} required />
        </label>
        <label>
          Plan
          <select value={plan} onChange={(e) => setPlan(e.target.value)}>
            <option value="starter">starter</option>
            <option value="team">team</option>
            <option value="business">business</option>
          </select>
        </label>
        <button type="submit" className="btn-nav">
          开通租户
        </button>
      </form>

      <h3 className="aos-section-title">已开通</h3>
      <ul className="aos-saas-list">
        {items.length === 0 ? (
          <li className="aos-muted">暂无 SaaS 租户记录</li>
        ) : (
          items.map((t) => (
            <li key={t.orgId}>
              <strong>{t.orgName}</strong>
              <span className="aos-muted">
                {" "}
                · {t.orgId} · {t.plan} · owner={t.ownerSubject}
              </span>
              <div className="aos-muted">
                配额：工作区 {t.quota.maxWorkspaces} · 成员 {t.quota.maxMembers} · 存储{" "}
                {t.quota.maxStorageGb}GB
              </div>
              <button
                type="button"
                className="btn-nav"
                onClick={() => void bumpQuota(t)}
              >
                +5 工作区配额
              </button>
            </li>
          ))
        )}
      </ul>
    </PageChrome>
  );
}
