import { useEffect, useState } from "react";
import { sendGuardDecision, type GuardDecisionInput } from "../../api/aipGuardPolicyApproval";
import { getAuthRevision, getTenant } from "../../api/tenant";

const EMPTY: GuardDecisionInput = { proposalId: "", proposalVersion: "1", proposalHash: "", decision: "" };

export function GuardPolicyApprovalPanel() {
  const [input, setInput] = useState<GuardDecisionInput>(EMPTY);
  const [key, setKey] = useState("");
  const [attempted, setAttempted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [identity, setIdentity] = useState("");
  const [message, setMessage] = useState("仅审核机器起草的精确提案；审批不会自动激活策略或调用模型。");
  const currentIdentity = () => { const tenant = getTenant(); return JSON.stringify([tenant.orgId, tenant.projectId, tenant.subject, getAuthRevision()]); };
  useEffect(() => {
    const changed = () => { setInput(EMPTY); setKey(""); setAttempted(false); setMessage("身份已变化，请重新读取并核对提案。"); };
    window.addEventListener("aos-auth-updated", changed); window.addEventListener("aos-tenant-updated", changed);
    return () => { window.removeEventListener("aos-auth-updated", changed); window.removeEventListener("aos-tenant-updated", changed); };
  }, []);
  const field = (name: keyof GuardDecisionInput, value: string) => setInput(previous => ({ ...previous, [name]: value }));

  async function submit(inquiry: boolean) {
    if (busy || (attempted && !inquiry)) return;
    const originalIdentity = inquiry ? identity : currentIdentity();
    if (inquiry && originalIdentity !== currentIdentity()) { setMessage("身份或租户已变化；不能查询或重发原请求。"); return; }
    const idempotencyKey = inquiry ? key : `guard-decision-${crypto.randomUUID()}`;
    if (!inquiry) { setAttempted(true); setKey(idempotencyKey); setIdentity(originalIdentity); }
    setBusy(true); setMessage(inquiry ? "正在只读查询原审批请求…" : "正在提交唯一审批请求…");
    try {
      const result = await sendGuardDecision(input, idempotencyKey, inquiry);
      if (originalIdentity !== currentIdentity()) throw new Error("审批期间身份或租户已变化");
      setMessage(result.status === "observed"
        ? `审批事件 ${result.approvalEventId} 已权威确认；策略仍未激活。`
        : "结果仍未知；原请求已冻结，只能继续查询，不能重发。");
    } catch (error) {
      setMessage(`审批未确认：${(error as Error).message}。保留原请求，只能查询，不能换键重发。`);
    } finally { setBusy(false); }
  }

  return <section className="card" aria-label="守护策略真人审批" style={{ padding: 18, marginTop: 16 }}>
    <h2>出站、数据与配额策略审批</h2>
    <p>请从机器起草的正式提案复制精确 ID、版本和摘要。批准或拒绝必须明确选择；此处只记录审批事件，不消费、不激活。</p>
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 10 }}>
      <label>提案 ID<input value={input.proposalId} disabled={attempted} onChange={e => field("proposalId", e.target.value)} /></label>
      <label>提案版本<input value={input.proposalVersion} disabled={attempted} onChange={e => field("proposalVersion", e.target.value)} /></label>
      <label>提案摘要<input value={input.proposalHash} disabled={attempted} onChange={e => field("proposalHash", e.target.value)} /></label>
      <label>真人决定<select value={input.decision} disabled={attempted} onChange={e => field("decision", e.target.value)}>
        <option value="">请选择</option><option value="approved">批准</option><option value="rejected">拒绝</option>
      </select></label>
    </div>
    <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
      <button type="button" className="btn btn-primary" disabled={busy || attempted} onClick={() => void submit(false)}>提交一次审批</button>
      <button type="button" className="btn" disabled={busy || !attempted} onClick={() => void submit(true)}>查询原请求</button>
    </div>
    <p role="status">{message}</p>
  </section>;
}
