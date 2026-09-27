import { useState } from "react";

import { apiGetAuthoritative, apiPostUnqueued } from "../../api/client";
import { getAuthRevision, getTenant } from "../../api/tenant";

export const CURRENT_AGNES_HOST = "api.agnes-ai.cn" as const;
export type EgressDraftInput = {
  policyId: string; host: string; owner: string; approvalRef: string;
  effectiveFrom: string; effectiveUntil: string;
};
export type EgressDraft = {
  policyId: string; revision: 1; environment: "development";
  effectiveFrom: string; effectiveUntil: string; owner: string; approvalRef: string;
  lifecycle: "draft"; allowedSchemes: ["https"]; allowedHosts: [typeof CURRENT_AGNES_HOST];
  allowedPorts: [443]; allowPublicFallback: false; unknownDestinationBehavior: "block";
  regionState: "unknown"; region: null;
};
type Readback = EgressDraft & { tenant: { orgId: string; projectId: string }; contentHash: string };

export function buildEgressDraft(input: EgressDraftInput): EgressDraft {
  const policyId = input.policyId.trim();
  const owner = input.owner.trim();
  const approvalRef = input.approvalRef.trim();
  if (!policyId || policyId.length > 200 || !owner || owner.length > 160 || !approvalRef || approvalRef.length > 240) {
    throw new Error("策略 ID、负责人和正式审批引用均须明确填写");
  }
  if (input.host !== CURRENT_AGNES_HOST) throw new Error("须明确选择当前批准的 Agnes 出站主机");
  const from = new Date(input.effectiveFrom);
  const until = new Date(input.effectiveUntil);
  if (!Number.isFinite(from.getTime()) || !Number.isFinite(until.getTime()) || until <= from) {
    throw new Error("须填写有效的策略生效起止时间");
  }
  return {
    policyId, revision: 1, environment: "development", effectiveFrom: from.toISOString(),
    effectiveUntil: until.toISOString(), owner, approvalRef, lifecycle: "draft",
    allowedSchemes: ["https"], allowedHosts: [CURRENT_AGNES_HOST], allowedPorts: [443],
    allowPublicFallback: false, unknownDestinationBehavior: "block", regionState: "unknown", region: null,
  };
}

export function exactEgressReadback(value: unknown, expected: EgressDraft, tenant: { orgId: string; projectId: string }): boolean {
  if (!value || typeof value !== "object") return false;
  const row = value as Partial<Readback>;
  return row.policyId === expected.policyId && row.revision === 1
    && row.tenant?.orgId === tenant.orgId && row.tenant?.projectId === tenant.projectId
    && /^[0-9a-f]{64}$/.test(row.contentHash ?? "")
    && row.environment === "development" && row.lifecycle === "draft"
    && row.owner === expected.owner && row.approvalRef === expected.approvalRef
    && typeof row.effectiveFrom === "string" && Date.parse(row.effectiveFrom) === Date.parse(expected.effectiveFrom)
    && typeof row.effectiveUntil === "string" && Date.parse(row.effectiveUntil) === Date.parse(expected.effectiveUntil)
    && JSON.stringify(row.allowedSchemes) === '["https"]'
    && JSON.stringify(row.allowedHosts) === JSON.stringify([CURRENT_AGNES_HOST])
    && JSON.stringify(row.allowedPorts) === "[443]" && row.allowPublicFallback === false
    && row.unknownDestinationBehavior === "block" && row.regionState === "unknown" && row.region === null;
}

const EMPTY: EgressDraftInput = {
  policyId: "", host: "", owner: "", approvalRef: "", effectiveFrom: "", effectiveUntil: "",
};

export function RuntimeEgressPolicyPanel() {
  const [input, setInput] = useState<EgressDraftInput>(EMPTY);
  const [attempted, setAttempted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [attemptedBody, setAttemptedBody] = useState<EgressDraft | null>(null);
  const [attemptedIdentity, setAttemptedIdentity] = useState("");
  const [message, setMessage] = useState("仅创建 draft；不会激活出站、发起模型调用或确认地域。");
  const identity = () => { const tenant = getTenant(); return JSON.stringify([tenant.orgId, tenant.projectId, tenant.subject, getAuthRevision()]); };
  const setField = (field: keyof EgressDraftInput, value: string) => setInput(previous => ({ ...previous, [field]: value }));

  async function submit() {
    if (busy || attempted) return;
    let body: EgressDraft;
    try { body = buildEgressDraft(input); } catch (error) { setMessage((error as Error).message); return; }
    const tenant = getTenant();
    const originalIdentity = identity();
    const key = `egress-draft-${crypto.randomUUID()}`;
    setAttempted(true); setAttemptedBody(body); setAttemptedIdentity(originalIdentity);
    setBusy(true); setMessage("正在提交唯一草稿命令并做权威回读…");
    try {
      const posted = await apiPostUnqueued<unknown>("/v1/aip/runtime-guard-policies/egress", body,
        { "Idempotency-Key": key, "If-Match": "0" });
      if (originalIdentity !== identity()) throw new Error("提交期间身份或租户已变化");
      const reread = await apiGetAuthoritative<unknown>(`/v1/aip/runtime-guard-policies/egress/${encodeURIComponent(body.policyId)}?revision=1`);
      if (originalIdentity !== identity()) throw new Error("权威回读期间身份或租户已变化");
      if (!exactEgressReadback(posted, body, tenant) || !exactEgressReadback(reread, body, tenant)
          || (posted as Readback).contentHash !== (reread as Readback).contentHash) throw new Error("提交与权威回读不一致");
      setMessage(`出站策略 ${body.policyId}@1 已写入并精确回读为 draft；尚未激活。`);
    } catch (error) {
      setMessage(`提交结果未确认：${(error as Error).message}。只读对账，勿换幂等键重发。`);
    } finally { setBusy(false); }
  }

  async function reconcile() {
    if (!attemptedBody || busy) return;
    if (attemptedIdentity !== identity()) { setMessage("身份或租户已变化；回原作用域核对，不能重发。"); return; }
    const tenant = getTenant();
    setBusy(true);
    try {
      const reread = await apiGetAuthoritative<unknown>(`/v1/aip/runtime-guard-policies/egress/${encodeURIComponent(attemptedBody.policyId)}?revision=1`);
      if (attemptedIdentity !== identity()) throw new Error("身份或租户已变化");
      setMessage(exactEgressReadback(reread, attemptedBody, tenant)
        ? `只读核对：${attemptedBody.policyId}@1 draft 存在；尚未激活。`
        : "只读核对与原请求不一致；冻结此命令，需人工排查。");
    } catch { setMessage("只读核对仍无法确认；冻结此命令，勿重发。"); }
    finally { setBusy(false); }
  }

  async function lookup() {
    const policyId = input.policyId.trim();
    if (!policyId || policyId.length > 200 || busy) { setMessage("先填写有效策略 ID，再只读查询。"); return; }
    const tenant = getTenant();
    const originalIdentity = identity();
    setBusy(true);
    try {
      const row = await apiGetAuthoritative<Partial<Readback>>(`/v1/aip/runtime-guard-policies/egress/${encodeURIComponent(policyId)}`);
      if (originalIdentity !== identity() || row.policyId !== policyId || row.tenant?.orgId !== tenant.orgId
          || row.tenant?.projectId !== tenant.projectId || !Number.isSafeInteger(row.revision)
          || !/^[0-9a-f]{64}$/.test(row.contentHash ?? "")) throw new Error("权威身份不一致");
      setMessage(`只读查询：${policyId}@${row.revision}，状态 ${row.lifecycle}；本页不会覆盖现有版本。`);
    } catch { setMessage("未能权威确认当前策略；不能据此认定不存在，亦不能覆盖或重发。"); }
    finally { setBusy(false); }
  }

  return <section className="card" aria-label="出站策略草稿配置" style={{ padding: 18, marginTop: 16 }}>
    <h2>出站策略草稿</h2>
    <p>本入口只建草稿。HTTPS/443、禁止公网回退、未知目的地阻断为固定边界；当前主机须主动选择，地域仍为未知，不能用于真实出站。</p>
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 10 }}>
      <label>策略 ID<input value={input.policyId} disabled={attempted} onChange={e => setField("policyId", e.target.value)} /></label>
      <label>当前 Agnes 主机<select value={input.host} disabled={attempted} onChange={e => setField("host", e.target.value)}>
        <option value="">请选择</option><option value={CURRENT_AGNES_HOST}>{CURRENT_AGNES_HOST}</option>
      </select></label>
      <label>生效时间<input type="datetime-local" value={input.effectiveFrom} disabled={attempted} onChange={e => setField("effectiveFrom", e.target.value)} /></label>
      <label>失效时间<input type="datetime-local" value={input.effectiveUntil} disabled={attempted} onChange={e => setField("effectiveUntil", e.target.value)} /></label>
      <label>负责人<input value={input.owner} disabled={attempted} onChange={e => setField("owner", e.target.value)} /></label>
      <label>正式审批引用<input value={input.approvalRef} disabled={attempted} onChange={e => setField("approvalRef", e.target.value)} /></label>
    </div>
    <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
      <button type="button" className="btn" disabled={busy} onClick={() => void lookup()}>按 ID 只读查询</button>
      <button type="button" className="btn btn-primary" disabled={busy || attempted} onClick={() => void submit()}>创建 draft 并核对</button>
      <button type="button" className="btn" disabled={busy || !attempted} onClick={() => void reconcile()}>只读核对原命令</button>
    </div>
    <p role="status">{message}</p>
  </section>;
}
