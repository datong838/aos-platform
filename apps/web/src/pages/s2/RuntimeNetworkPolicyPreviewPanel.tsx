import { useState } from "react";

import { apiPostUnqueued } from "../../api/client";
import { getAuthRevision, getTenant } from "../../api/tenant";
import { CURRENT_AGNES_HOST } from "./RuntimeEgressPolicyPanel";

export type NetworkActivationPreviewInput = {
  policyId: string; revision: string; expectedHeadVersion: string; host: string;
  egressPolicyId: string; egressRevision: string; egressContentHash: string;
  owner: string; approvalRef: string; effectiveFrom: string; effectiveUntil: string;
};

type Candidate = {
  policyId: string; revision: number; allowedSchemes: ["https"];
  allowedHosts: [typeof CURRENT_AGNES_HOST]; allowedPorts: [443];
  tlsRequired: true; publicFallbackAllowed: false;
  egressPolicyRef: { assetType: "EgressPolicyRevision"; assetId: string; revision: number; contentHash: string };
  effectiveFrom: string; effectiveUntil: string; owner: string; approvalRef: string; lifecycle: "active";
};

type BlockedPreview = {
  policyId: string; candidateRevision: number; headRevision: number; headVersion: number;
  targetContentHash: string | null; bindingHash: string | null;
  activationAllowed: false; blockers: string[];
};

const EMPTY: NetworkActivationPreviewInput = {
  policyId: "", revision: "1", expectedHeadVersion: "0", host: "",
  egressPolicyId: "", egressRevision: "1", egressContentHash: "",
  owner: "", approvalRef: "", effectiveFrom: "", effectiveUntil: "",
};

const BLOCKER_LABELS: Record<string, string> = {
  FORMAL_PRODUCER_UNAVAILABLE: "正式策略动作来源未建立",
  ATOMIC_APPROVAL_CONSUMER_UNAVAILABLE: "独立批准与一次性消费尚未接通",
  HEAD_VERSION_DRIFT: "当前策略 head 版本与预期不一致",
  CANDIDATE_REVISION_DRIFT: "候选修订不是当前下一版",
  EGRESS_DEPENDENCY_INVALID: "精确生效出站策略不可用或不匹配",
  ACTIVE_CANDIDATE_REQUIRED: "预览目标必须是生效候选",
};

function positiveInt(value: string, label: string): number {
  if (!/^[1-9]\d*$/.test(value) || !Number.isSafeInteger(Number(value))) throw new Error(`${label}须为正整数`);
  return Number(value);
}

export function buildNetworkActivationPreview(input: NetworkActivationPreviewInput): { body: Candidate; expectedHeadVersion: number } {
  const policyId = input.policyId.trim();
  const owner = input.owner.trim();
  const approvalRef = input.approvalRef.trim();
  const egressPolicyId = input.egressPolicyId.trim();
  if (!policyId || policyId.length > 200 || !owner || owner.length > 160 || !approvalRef || approvalRef.length > 240) {
    throw new Error("策略 ID、负责人及文本审批引用须明确填写；引用本身不构成批准");
  }
  if (input.host !== CURRENT_AGNES_HOST) throw new Error("须明确选择当前 Agnes HTTPS 主机");
  if (!egressPolicyId || egressPolicyId.length > 200) throw new Error("须填写精确出站策略 ID");
  if (!/^[0-9a-f]{64}$/.test(input.egressContentHash)) throw new Error("出站策略摘要须为精确 64 位小写哈希");
  const revision = positiveInt(input.revision, "候选修订");
  const egressRevision = positiveInt(input.egressRevision, "出站策略修订");
  if (!/^\d+$/.test(input.expectedHeadVersion) || !Number.isSafeInteger(Number(input.expectedHeadVersion))) {
    throw new Error("预期 head 版本须为非负整数");
  }
  const from = new Date(input.effectiveFrom);
  const until = new Date(input.effectiveUntil);
  if (!Number.isFinite(from.getTime()) || !Number.isFinite(until.getTime()) || until <= from) {
    throw new Error("须填写有效的生效起止时间");
  }
  return {
    expectedHeadVersion: Number(input.expectedHeadVersion),
    body: {
      policyId, revision, allowedSchemes: ["https"], allowedHosts: [CURRENT_AGNES_HOST],
      allowedPorts: [443], tlsRequired: true, publicFallbackAllowed: false,
      egressPolicyRef: { assetType: "EgressPolicyRevision", assetId: egressPolicyId,
        revision: egressRevision, contentHash: input.egressContentHash },
      effectiveFrom: from.toISOString(), effectiveUntil: until.toISOString(),
      owner, approvalRef, lifecycle: "active",
    },
  };
}

export function exactBlockedNetworkPreview(value: unknown, candidate: Candidate): value is BlockedPreview {
  if (!value || typeof value !== "object") return false;
  const row = value as Partial<BlockedPreview>;
  const hash = (item: unknown) => typeof item === "string" && /^[0-9a-f]{64}$/.test(item);
  return row.policyId === candidate.policyId && row.candidateRevision === candidate.revision
    && Number.isSafeInteger(row.headRevision) && (row.headRevision ?? -1) >= 0
    && Number.isSafeInteger(row.headVersion) && (row.headVersion ?? -1) >= 0
    && row.activationAllowed === false
    && ((row.targetContentHash === null && row.bindingHash === null)
      || (hash(row.targetContentHash) && hash(row.bindingHash)))
    && Array.isArray(row.blockers)
    && row.blockers.includes("FORMAL_PRODUCER_UNAVAILABLE")
    && row.blockers.includes("ATOMIC_APPROVAL_CONSUMER_UNAVAILABLE")
    && row.blockers.every(item => typeof item === "string" && item.length > 0);
}

export function RuntimeNetworkPolicyPreviewPanel() {
  const [input, setInput] = useState<NetworkActivationPreviewInput>(EMPTY);
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<BlockedPreview | null>(null);
  const [message, setMessage] = useState("只读预览当前阻断项；不会提交策略、申请批准或启用模型出站。");
  const identity = () => { const tenant = getTenant(); return JSON.stringify([tenant.orgId, tenant.projectId, tenant.subject, getAuthRevision()]); };
  const setField = (field: keyof NetworkActivationPreviewInput, value: string) => {
    setInput(previous => ({ ...previous, [field]: value }));
    setPreview(null);
  };

  async function inspect() {
    if (busy) return;
    let request: ReturnType<typeof buildNetworkActivationPreview>;
    try { request = buildNetworkActivationPreview(input); } catch (error) { setMessage((error as Error).message); return; }
    const originalIdentity = identity();
    setBusy(true); setPreview(null); setMessage("正在读取当前策略阻断项…");
    try {
      const result = await apiPostUnqueued<unknown>(
        "/v1/aip/runtime-guard-policies/networks/activation-preview", request.body,
        { "If-Match": String(request.expectedHeadVersion) },
      );
      if (originalIdentity !== identity() || !exactBlockedNetworkPreview(result, request.body)) {
        throw new Error("预览响应或当前身份不一致");
      }
      setPreview(result);
      setMessage("已只读核对当前阻断项；本预览没有激活权限。");
    } catch (error) {
      setMessage(`预览未确认：${(error as Error).message}。刷新身份与权威数据后再查；不能据此运行。`);
    } finally { setBusy(false); }
  }

  return <section className="card" aria-label="网络策略只读激活预览" style={{ padding: 18, marginTop: 16 }}>
    <h2>网络策略激活预览</h2>
    <p>只核候选与当前阻断项。要求精确生效出站策略；文本审批引用不构成批准。此处不能发布或激活。</p>
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 10 }}>
      <label>网络策略 ID<input value={input.policyId} onChange={e => setField("policyId", e.target.value)} /></label>
      <label>候选修订<input value={input.revision} onChange={e => setField("revision", e.target.value)} /></label>
      <label>预期 head 版本<input value={input.expectedHeadVersion} onChange={e => setField("expectedHeadVersion", e.target.value)} /></label>
      <label>当前 Agnes 主机<select value={input.host} onChange={e => setField("host", e.target.value)}><option value="">请选择</option><option value={CURRENT_AGNES_HOST}>{CURRENT_AGNES_HOST}</option></select></label>
      <label>精确出站策略 ID<input value={input.egressPolicyId} onChange={e => setField("egressPolicyId", e.target.value)} /></label>
      <label>出站策略修订<input value={input.egressRevision} onChange={e => setField("egressRevision", e.target.value)} /></label>
      <label>出站策略摘要<input value={input.egressContentHash} onChange={e => setField("egressContentHash", e.target.value)} /></label>
      <label>生效时间<input type="datetime-local" value={input.effectiveFrom} onChange={e => setField("effectiveFrom", e.target.value)} /></label>
      <label>失效时间<input type="datetime-local" value={input.effectiveUntil} onChange={e => setField("effectiveUntil", e.target.value)} /></label>
      <label>负责人<input value={input.owner} onChange={e => setField("owner", e.target.value)} /></label>
      <label>文本审批引用（不构成批准）<input value={input.approvalRef} onChange={e => setField("approvalRef", e.target.value)} /></label>
    </div>
    <button type="button" className="btn" disabled={busy} onClick={() => void inspect()}>只读预览阻断项</button>
    <p role="status">{message}</p>
    {preview && <div aria-label="预览阻断结果">
      <p>当前 head：{preview.headRevision} / 版本 {preview.headVersion}；候选修订 {preview.candidateRevision}。激活：禁止。</p>
      {preview.bindingHash && <details><summary>精确目标摘要（审计用）</summary><code>{preview.targetContentHash}</code><br /><code>{preview.bindingHash}</code></details>}
      <ul>{preview.blockers.map(code => <li key={code}>{BLOCKER_LABELS[code] ?? code}</li>)}</ul>
    </div>}
  </section>;
}
