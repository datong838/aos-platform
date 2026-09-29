import { useEffect, useMemo, useState } from "react";
import {
  activateSkillBinding, evaluateSkillBinding, loadSkillBindingEvaluationCandidate,
  previewSkillBindingEvaluation, readSkillBindingForReconciliation,
} from "../../api/aipAgentControl/skillBindingLifecycleProduct";

type Binding = Parameters<typeof loadSkillBindingEvaluationCandidate>[0] & {
  readiness: string; dependencySnapshotHash: string | null; readinessExpiresAt: string | null;
};
type Role = Parameters<typeof loadSkillBindingEvaluationCandidate>[1];
type Skill = Parameters<typeof loadSkillBindingEvaluationCandidate>[2];
type Candidate = NonNullable<Awaited<ReturnType<typeof loadSkillBindingEvaluationCandidate>>["candidate"]>;
type Prepared = { candidate: Candidate; snapshotHash: string; mode: "evaluate" | "activate"; expiresAt: string };

const labels: Record<string, string> = {
  TENANT_MISMATCH: "绑定、技能或运行策略不属于当前工作区",
  BINDING_STATUS_NOT_EVALUABLE: "绑定状态不允许评估",
  BINDING_VERSION_INVALID: "绑定版本无效",
  AGENT_INSTANCE_NOT_ACTIVE: "数字同事尚未正式启用",
  SKILL_EXACT_PUBLICATION_MISSING: "技能未正式发布或精确修订已变化",
  SKILL_DEPENDENCY_REF_MISSING: "技能缺正式模型路由、策略或评测放行引用",
  RUNTIME_POLICY_DRIFTED: "运行策略已变化或未启用",
  BUDGET_POLICY_DRIFTED: "绑定预算与当前运行策略不一致",
  CAPABILITY_BINDING_IDS_INVALID: "能力绑定清单无效",
};

function markerKey(binding: Binding): string {
  return `aos:skill-binding:lifecycle:unresolved:${binding.tenant.orgId}:${binding.tenant.projectId}:${binding.bindingId}`;
}

export function SkillBindingLifecyclePanel({ item, skill, binding, onUpdated }: {
  item: Role; skill: Skill; binding: Binding; onUpdated: () => void | Promise<void>;
}) {
  const key = useMemo(() => markerKey(binding), [binding.tenant.orgId, binding.tenant.projectId, binding.bindingId]);
  const [prepared, setPrepared] = useState<Prepared | null>(null);
  const [blockers, setBlockers] = useState<string[]>([]);
  const [pending, setPending] = useState(() => localStorage.getItem(key) !== null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const [receiptId, setReceiptId] = useState("");
  useEffect(() => {
    setPrepared(null); setBlockers([]); setNote("");
    setPending(localStorage.getItem(key) !== null);
  }, [key, binding.version, binding.dependencySnapshotHash]);

  async function prepare() {
    if (busy || pending) return;
    setBusy(true); setPrepared(null); setBlockers([]); setNote("");
    try {
      const loaded = await loadSkillBindingEvaluationCandidate(binding, item, skill);
      if (!loaded.candidate) { setBlockers(loaded.blockers); return; }
      const preview = await previewSkillBindingEvaluation(loaded.candidate);
      if (preview.readiness !== "available" || typeof preview.dependencySnapshotHash !== "string"
          || typeof preview.expiresAt !== "string" || Date.parse(preview.expiresAt) <= Date.now()) {
        const reasons = Array.isArray(preview.reasons) ? preview.reasons.join("、") : "正式来源尚未就绪";
        setNote(`当前预览未可用，禁止提交：${reasons || "正式来源尚未就绪"}`);
        return;
      }
      const mode = binding.readiness === "available"
        && binding.dependencySnapshotHash === preview.dependencySnapshotHash
        && typeof binding.readinessExpiresAt === "string"
        && Date.parse(binding.readinessExpiresAt) > Date.now() ? "activate" : "evaluate";
      setPrepared({ candidate: loaded.candidate, snapshotHash: preview.dependencySnapshotHash,
        expiresAt: preview.expiresAt, mode });
    } catch (error) {
      setNote(`权威预览失败，禁止提交：${String((error as Error).message || error)}`);
    } finally { setBusy(false); }
  }

  async function confirm() {
    if (!prepared || pending || busy) return;
    if (Date.parse(prepared.expiresAt) <= Date.now()) {
      setPrepared(null); setNote("预览已过期，请重新核验。");
      return;
    }
    setBusy(true); setNote("");
    try {
      const fresh = await loadSkillBindingEvaluationCandidate(binding, item, skill);
      if (!fresh.candidate || JSON.stringify(fresh.candidate) !== JSON.stringify(prepared.candidate)) {
        setPrepared(null); setBlockers(fresh.blockers);
        setNote("精确候选已变化，请重新核验。");
        return;
      }
      const preview = await previewSkillBindingEvaluation(fresh.candidate);
      if (preview.readiness !== "available" || preview.dependencySnapshotHash !== prepared.snapshotHash
          || typeof preview.expiresAt !== "string" || Date.parse(preview.expiresAt) <= Date.now()) {
        setPrepared(null); setNote("依赖快照已变化或过期，请重新核验。");
        return;
      }
      const idempotencyKey = `skill-binding-${prepared.mode}-${crypto.randomUUID()}`;
      const markBeforeSend = () => {
        localStorage.setItem(key, JSON.stringify({ operation: prepared.mode, idempotencyKey,
          bindingId: binding.bindingId, expectedVersion: binding.version, snapshotHash: prepared.snapshotHash }));
        setPending(true);
      };
      const verified = prepared.mode === "evaluate"
        ? await evaluateSkillBinding(fresh.candidate, prepared.snapshotHash, idempotencyKey, markBeforeSend)
        : await activateSkillBinding(fresh.candidate, binding.version, prepared.snapshotHash, idempotencyKey, markBeforeSend);
      localStorage.removeItem(key); setPending(false); setPrepared(null);
      setReceiptId(verified.receiptId);
      setNote(prepared.mode === "evaluate"
        ? "评估及回执已核验；激活仍需重新核验当前新鲜状态。"
        : "激活及回执已核验；运行 Host 仍受独立正式授权门控制。");
      try { await onUpdated(); }
      catch { setNote("绑定及回执已核验；目录刷新失败，请重新读取只读状态。"); }
    } catch (error) {
      setNote(localStorage.getItem(key)
        ? `绑定命令结果未核清，禁止重发；请按原幂等键与 Receipt 只读对账：${String((error as Error).message || error)}`
        : `绑定命令未发送，请重新核验：${String((error as Error).message || error)}`);
    } finally { setBusy(false); }
  }

  async function reconcile() {
    setBusy(true);
    try {
      const observed = await readSkillBindingForReconciliation(binding.bindingId);
      setNote(`只读回读绑定状态 ${observed.status}、版本 ${observed.version}；尚未核对原 Receipt，继续禁止重发。`);
    } catch (error) {
      setNote(`只读对账失败，继续禁止重发：${String((error as Error).message || error)}`);
    } finally { setBusy(false); }
  }

  if (skill.lifecycle !== "published") return <span>技能须正式发布后才能评估或激活绑定。</span>;
  if (binding.status === "active") return <span>技能绑定已激活；运行仍受独立准入门控制。</span>;
  if (binding.status !== "provisioning" && binding.status !== "suspended") return <span>当前绑定状态不允许评估或激活。</span>;
  return <div style={{ marginTop: 6 }}>
    {pending ? <div role="alert">上次绑定命令结果未核清，禁止重发。<button className="btn" type="button" disabled={busy} onClick={() => void reconcile()}>只读对账</button></div> : null}
    {!pending ? <button className="btn" type="button" disabled={busy} onClick={() => void prepare()}>
      {binding.readiness === "available" && binding.dependencySnapshotHash
        && binding.readinessExpiresAt && Date.parse(binding.readinessExpiresAt) > Date.now()
        ? "核验激活候选" : "核验评估候选"}
    </button> : null}
    {blockers.length ? <ul>{blockers.map((code) => <li key={code}>{labels[code] || code}</li>)}</ul> : null}
    {prepared && !pending ? <div className="notice" role="group" aria-label="技能绑定评估激活确认">
      <p>绑定 {binding.bindingId} · 技能 {prepared.candidate.skill.assetId}@{prepared.candidate.skill.revision} · 预算 {prepared.candidate.budgetPolicyRef.assetId}@{prepared.candidate.budgetPolicyRef.revision} · 快照到期 {new Date(prepared.expiresAt).toLocaleString()}。</p>
      <p>{prepared.mode === "evaluate" ? "本动作记录当前依赖评估；评估通过后还须独立激活。" : "本动作只激活该技能绑定；不会启用 Host 或触发 Run。"}</p>
      <button className="btn primary" type="button" disabled={busy} onClick={() => void confirm()}>
        {prepared.mode === "evaluate" ? "确认评估绑定" : "确认激活绑定"}
      </button>
    </div> : null}
    {note ? <p role="status">{note}</p> : null}
    {receiptId ? <details><summary>绑定回执（审计用）</summary><code>{receiptId}</code></details> : null}
  </div>;
}
