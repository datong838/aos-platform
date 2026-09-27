import { useState } from "react";

import { apiGetAuthoritative, apiPostUnqueued } from "../../api/client";
import { getAuthRevision, getTenant } from "../../api/tenant";

export const APPROVED_DATA_CLASSES = [
  "public_catalog", "deidentified_order_aggregate", "approved_development_sample", "approved_internal_knowledge",
] as const;
export const PROHIBITED_DATA_CLASSES = [
  "direct_pii", "raw_order_detail", "customer_conversation", "credential",
  "commercial_sensitive", "cross_tenant", "unknown",
] as const;

export type DataPolicyInput = {
  policyId: string; allowed: string[]; effectiveFrom: string; effectiveUntil: string;
  owner: string; approvalRef: string;
};
export type DataPolicyDraft = {
  policyId: string; revision: 1; environment: "development";
  effectiveFrom: string; effectiveUntil: string; owner: string; approvalRef: string;
  lifecycle: "draft"; allowedClassifications: string[]; prohibitedClassifications: string[];
  denyUnknown: true; allowDirectPii: false; allowCommercialSensitive: false; allowCrossTenant: false;
};
type Readback = DataPolicyDraft & { tenant: { orgId: string; projectId: string }; contentHash: string };

export function buildDataPolicyDraft(input: DataPolicyInput): DataPolicyDraft {
  const policyId = input.policyId.trim();
  const owner = input.owner.trim();
  const approvalRef = input.approvalRef.trim();
  if (!policyId || policyId.length > 200 || !owner || owner.length > 160 || !approvalRef || approvalRef.length > 240) {
    throw new Error("策略 ID、负责人和正式审批引用均须明确填写");
  }
  const allowed = [...new Set(input.allowed)].sort();
  if (!allowed.length || allowed.length !== input.allowed.length || allowed.some(value => !APPROVED_DATA_CLASSES.includes(value as typeof APPROVED_DATA_CLASSES[number]))) {
    throw new Error("须明确选择至少一种获准数据类别，且不得重复或越界");
  }
  const from = new Date(input.effectiveFrom);
  const until = new Date(input.effectiveUntil);
  if (!Number.isFinite(from.getTime()) || !Number.isFinite(until.getTime()) || until <= from) {
    throw new Error("须填写有效的策略生效起止时间");
  }
  return {
    policyId, revision: 1, environment: "development", effectiveFrom: from.toISOString(),
    effectiveUntil: until.toISOString(), owner, approvalRef, lifecycle: "draft",
    allowedClassifications: allowed, prohibitedClassifications: [...PROHIBITED_DATA_CLASSES],
    denyUnknown: true, allowDirectPii: false, allowCommercialSensitive: false, allowCrossTenant: false,
  };
}

export function exactDataPolicyReadback(value: unknown, expected: DataPolicyDraft, tenant: { orgId: string; projectId: string }): boolean {
  if (!value || typeof value !== "object") return false;
  const row = value as Partial<Readback>;
  return row.policyId === expected.policyId && row.revision === 1
    && row.tenant?.orgId === tenant.orgId && row.tenant?.projectId === tenant.projectId
    && /^[0-9a-f]{64}$/.test(row.contentHash ?? "")
    && row.environment === expected.environment && row.lifecycle === "draft"
    && row.owner === expected.owner && row.approvalRef === expected.approvalRef
    && typeof row.effectiveFrom === "string" && Date.parse(row.effectiveFrom) === Date.parse(expected.effectiveFrom)
    && typeof row.effectiveUntil === "string" && Date.parse(row.effectiveUntil) === Date.parse(expected.effectiveUntil)
    && JSON.stringify([...row.allowedClassifications ?? []].sort()) === JSON.stringify(expected.allowedClassifications)
    && JSON.stringify(row.prohibitedClassifications) === JSON.stringify(expected.prohibitedClassifications)
    && row.denyUnknown === true && row.allowDirectPii === false
    && row.allowCommercialSensitive === false && row.allowCrossTenant === false;
}

const EMPTY: DataPolicyInput = {
  policyId: "", allowed: [], effectiveFrom: "", effectiveUntil: "", owner: "", approvalRef: "",
};

export function RuntimeDataClassificationPanel() {
  const [input, setInput] = useState<DataPolicyInput>(EMPTY);
  const [attempted, setAttempted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [attemptedBody, setAttemptedBody] = useState<DataPolicyDraft | null>(null);
  const [attemptedIdentity, setAttemptedIdentity] = useState("");
  const [message, setMessage] = useState("仅创建 draft；不会激活策略或授权读取任何数据。");
  const identity = () => { const tenant = getTenant(); return JSON.stringify([tenant.orgId, tenant.projectId, tenant.subject, getAuthRevision()]); };
  const setField = (field: keyof DataPolicyInput, value: string) => setInput(previous => ({ ...previous, [field]: value }));

  async function submit() {
    if (busy || attempted) return;
    let body: DataPolicyDraft;
    try { body = buildDataPolicyDraft(input); } catch (error) { setMessage((error as Error).message); return; }
    const tenant = getTenant();
    const originalIdentity = identity();
    const key = `data-policy-draft-${crypto.randomUUID()}`;
    setAttempted(true); setAttemptedBody(body); setAttemptedIdentity(originalIdentity);
    setBusy(true); setMessage("正在提交唯一草稿命令并做权威回读…");
    try {
      const posted = await apiPostUnqueued<unknown>("/v1/aip/runtime-guard-policies/data-classifications", body,
        { "Idempotency-Key": key, "If-Match": "0" });
      if (originalIdentity !== identity()) throw new Error("提交期间身份或租户已变化");
      const reread = await apiGetAuthoritative<unknown>(`/v1/aip/runtime-guard-policies/data-classifications/${encodeURIComponent(body.policyId)}?revision=1`);
      if (originalIdentity !== identity()) throw new Error("权威回读期间身份或租户已变化");
      if (!exactDataPolicyReadback(posted, body, tenant) || !exactDataPolicyReadback(reread, body, tenant)
          || (posted as Readback).contentHash !== (reread as Readback).contentHash) {
        throw new Error("提交与权威回读不一致");
      }
      setMessage(`数据分类策略 ${body.policyId}@1 已写入并精确回读为 draft；尚未激活。`);
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
      const reread = await apiGetAuthoritative<unknown>(`/v1/aip/runtime-guard-policies/data-classifications/${encodeURIComponent(attemptedBody.policyId)}?revision=1`);
      if (attemptedIdentity !== identity()) throw new Error("身份或租户已变化");
      setMessage(exactDataPolicyReadback(reread, attemptedBody, tenant)
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
      const row = await apiGetAuthoritative<Partial<Readback>>(`/v1/aip/runtime-guard-policies/data-classifications/${encodeURIComponent(policyId)}`);
      if (originalIdentity !== identity() || row.policyId !== policyId || row.tenant?.orgId !== tenant.orgId
          || row.tenant?.projectId !== tenant.projectId || !Number.isSafeInteger(row.revision)
          || !/^[0-9a-f]{64}$/.test(row.contentHash ?? "")) throw new Error("权威身份不一致");
      setMessage(`只读查询：${policyId}@${row.revision}，状态 ${row.lifecycle}；本页不会覆盖现有版本。`);
    } catch { setMessage("未能权威确认当前策略；不能据此认定不存在，亦不能覆盖或重发。"); }
    finally { setBusy(false); }
  }

  return <section className="card" aria-label="数据分类草稿配置" style={{ padding: 18, marginTop: 16 }}>
    <h2>数据分类策略草稿</h2>
    <p>只允许选择获准类别；个人信息、原始订单、客户会话、凭据、商业敏感、跨租户和未知类别始终禁止。审批引用只是草稿字段，不代表审批已核验。</p>
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 10 }}>
      <label>策略 ID<input value={input.policyId} disabled={attempted} onChange={e => setField("policyId", e.target.value)} /></label>
      <label>生效时间<input type="datetime-local" value={input.effectiveFrom} disabled={attempted} onChange={e => setField("effectiveFrom", e.target.value)} /></label>
      <label>失效时间<input type="datetime-local" value={input.effectiveUntil} disabled={attempted} onChange={e => setField("effectiveUntil", e.target.value)} /></label>
      <label>负责人<input value={input.owner} disabled={attempted} onChange={e => setField("owner", e.target.value)} /></label>
      <label>正式审批引用<input value={input.approvalRef} disabled={attempted} onChange={e => setField("approvalRef", e.target.value)} /></label>
    </div>
    <fieldset disabled={attempted} style={{ marginTop: 10 }}><legend>明确选择获准数据类别（不预选）</legend>
      {APPROVED_DATA_CLASSES.map(value => <label key={value} style={{ display: "block" }}>
        <input type="checkbox" checked={input.allowed.includes(value)} onChange={e => setInput(previous => ({ ...previous,
          allowed: e.target.checked ? [...previous.allowed, value] : previous.allowed.filter(item => item !== value),
        }))} />{value}
      </label>)}
    </fieldset>
    <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
      <button type="button" className="btn" disabled={busy} onClick={() => void lookup()}>按 ID 只读查询</button>
      <button type="button" className="btn btn-primary" disabled={busy || attempted} onClick={() => void submit()}>创建 draft 并核对</button>
      <button type="button" className="btn" disabled={busy || !attempted} onClick={() => void reconcile()}>只读核对原命令</button>
    </div>
    <p role="status">{message}</p>
  </section>;
}
