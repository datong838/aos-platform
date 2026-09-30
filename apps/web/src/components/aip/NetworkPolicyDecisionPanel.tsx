import { useEffect, useRef, useState } from "react";
import type { ActionProposal } from "../../api/aipActions/contracts";
import { networkDecisionSdk, type NetworkDecisionResult, type NetworkDecisionSdk } from "../../api/aipActions/networkDecision";
import { getAuthRevision, getTenant } from "../../api/tenant";

type Props = {
  proposal: Pick<ActionProposal, "id" | "version" | "proposalHash" | "status" | "expiresAt" | "payload">;
  disabled: boolean;
  onObserved: () => void;
  sdk?: NetworkDecisionSdk;
};

export function NetworkPolicyDecisionPanel({ proposal, disabled, onObserved, sdk = networkDecisionSdk }: Props) {
  const [result, setResult] = useState<NetworkDecisionResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [reason, setReason] = useState("");
  const [identityChanged, setIdentityChanged] = useState(false);
  const busyRef = useRef(false);
  const epoch = useRef(0);
  const context = useRef({ ...getTenant(), revision: getAuthRevision() });
  const observed = useRef(onObserved);
  observed.current = onObserved;
  const sameIdentity = () => {
    const current = getTenant();
    return context.current.orgId === current.orgId && context.current.projectId === current.projectId
      && context.current.subject === current.subject && context.current.revision === getAuthRevision();
  };
  const query = async (refresh: boolean) => {
    if (busyRef.current || !sameIdentity() || identityChanged) return;
    busyRef.current = true; setBusy(true); setError("");
    const generation = epoch.current;
    try {
      const next = await sdk.inquire(proposal.id, proposal.version);
      if (generation !== epoch.current || !sameIdentity()) return;
      setResult(next);
      if (refresh && next.status === "observed") observed.current();
    } catch (e) {
      if (generation !== epoch.current || !sameIdentity()) return;
      setResult(null);
      setError(`审批请求尚无法确认：${e instanceof Error ? e.message : "服务不可用"}`);
    } finally {
      if (generation === epoch.current) { busyRef.current = false; setBusy(false); }
    }
  };
  useEffect(() => {
    context.current = { ...getTenant(), revision: getAuthRevision() };
    setResult(null); setReason(""); setError(""); setIdentityChanged(false);
    busyRef.current = false;
    const invalidated = () => { epoch.current += 1; busyRef.current = false; setBusy(false); setResult(null); setIdentityChanged(true); };
    window.addEventListener("aos-auth-updated", invalidated);
    window.addEventListener("aos-tenant-updated", invalidated);
    void query(false);
    return () => {
      epoch.current += 1;
      window.removeEventListener("aos-auth-updated", invalidated);
      window.removeEventListener("aos-tenant-updated", invalidated);
    };
  }, [proposal.id, proposal.version, sdk]);

  const candidate = proposal.payload.candidate;
  const target = candidate && typeof candidate === "object" && !Array.isArray(candidate)
    ? candidate as Record<string, unknown> : null;
  const expiry = new Date(proposal.expiresAt).getTime();
  const canSubmit = !disabled && !busy && !identityChanged && sameIdentity() && target !== null
    && proposal.status === "drafted" && Number.isFinite(expiry) && expiry > Date.now()
    && result?.status === "not_attempted" && Boolean(reason.trim());
  const submit = async (decision: "approved" | "rejected") => {
    if (!canSubmit || busyRef.current || new Date(proposal.expiresAt).getTime() <= Date.now()) return;
    busyRef.current = true; setBusy(true); setError("");
    setResult({ status: "unresolved" });
    const generation = epoch.current;
    try {
      const next = await sdk.submit(proposal.id, { expectedProposalVersion: proposal.version,
        expectedProposalHash: proposal.proposalHash, decision, reason: reason.trim() });
      if (generation !== epoch.current || !sameIdentity()) return;
      setResult(next);
      if (next.status === "observed") observed.current();
    } catch (e) {
      if (generation !== epoch.current || !sameIdentity()) return;
      setError(`提交结果尚未确认，请查询原审批请求：${e instanceof Error ? e.message : "服务不可用"}`);
    } finally {
      if (generation === epoch.current) { busyRef.current = false; setBusy(false); }
    }
  };

  if (identityChanged) return <p role="alert">身份已变化，请重新读取当前工作区提案。</p>;
  return <section className="w-full space-y-3 rounded border border-blue-200 bg-white p-3" aria-label="网络策略审批">
    <h3 className="font-semibold">网络策略审批</h3>
    <p className="text-sm">仅提交审批决定；配置生效由受控服务处理，批准不代表已生效。</p>
    {(!Number.isFinite(expiry) || expiry <= Date.now()) && <p role="alert">提案已过有效期或有效期不明，审批关闭；请由发起人基于最新配置重新准备提案。</p>}
    {target ? <div className="space-y-2 text-sm">
      <dl className="grid gap-2 sm:grid-cols-2">
        <div><dt className="text-gray-500">策略与修订</dt><dd>{String(target.policyId ?? "未提供")} · {String(target.revision ?? "未提供")}</dd></div>
        <div><dt className="text-gray-500">允许访问的域名</dt><dd>{Array.isArray(target.allowedHosts) ? target.allowedHosts.join("、") : "未提供"}</dd></div>
        <div><dt className="text-gray-500">允许端口</dt><dd>{Array.isArray(target.allowedPorts) ? target.allowedPorts.join("、") : "未提供"}</dd></div>
        <div><dt className="text-gray-500">加密连接</dt><dd>{target.tlsRequired === true ? "必须使用 TLS" : "未确认"}</dd></div>
      </dl>
      <details><summary>查看精确网络策略与出境策略引用</summary><pre className="max-h-56 overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(target, null, 2)}</pre></details>
    </div>
      : <p role="alert">缺少精确网络策略，不能提交审批。</p>}
    {busy && <p role="status">正在核对审批请求…</p>}
    {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
    {result?.status === "unresolved" && <p role="status">原审批请求结果尚未确认，禁止重复提交；请继续查询原请求。</p>}
    {result?.status === "observed" && <p role="status">已查到{result.decision === "approved" ? "批准" : "拒绝"}事件：{result.eventId}。请以最新提案和配置凭证核对后续状态。</p>}
    {proposal.status === "drafted" && <div className="flex flex-wrap items-end gap-2">
      <label className="flex-1 text-sm">网络审批意见<input aria-label="网络审批意见" className="mt-1 block w-full rounded border p-2" value={reason}
        disabled={busy || result?.status !== "not_attempted"} onChange={e => setReason(e.target.value)} /></label>
      <button type="button" className="rounded bg-green-700 px-3 py-2 text-white disabled:opacity-50" disabled={!canSubmit} onClick={() => void submit("approved")}>批准网络策略</button>
      <button type="button" className="rounded border border-red-400 px-3 py-2 text-red-700 disabled:opacity-50" disabled={!canSubmit} onClick={() => void submit("rejected")}>拒绝网络策略</button>
    </div>}
    <button type="button" className="rounded border px-3 py-2 disabled:opacity-50" disabled={busy} onClick={() => void query(true)}>查询原审批请求</button>
  </section>;
}
