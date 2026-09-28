import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { createProvisioningSkillBinding, loadSkillBindingCandidate } from "../../api/aipAgentControl/skillBindingProduct";
import type { SkillBindingCandidateResult } from "../../api/aipAgentControl/skillBindingCandidate";

type Role = Parameters<typeof loadSkillBindingCandidate>[0];
type Skill = Parameters<typeof loadSkillBindingCandidate>[1];
type Snapshot = Parameters<typeof loadSkillBindingCandidate>[2];

const blockerLabels: Record<string, string> = {
  TENANT_MISMATCH: "租户与当前工作区不一致",
  AGENT_INSTANCE_UNAVAILABLE: "当前数字同事实例不可用",
  SKILL_CATALOG_DRIFTED: "技能修订与角色目录不一致",
  SKILL_NOT_PUBLISHED: "技能尚未正式发布",
  RUNTIME_POLICY_DRIFTED: "技能运行策略缺失或精确版本已变化",
  BUDGET_POLICY_MISSING: "运行策略缺少正式预算策略",
  SKILL_CAPABILITY_REQUIREMENTS_INVALID: "技能必需能力清单无效",
  SKILL_BINDING_ALREADY_EXISTS: "该数字同事已有此技能绑定，需先核对原记录",
};

function markerKey(snapshot: Snapshot, role: Role, skill: Skill): string {
  return `aos:skill-binding:unresolved:${snapshot.tenant.orgId}:${snapshot.tenant.projectId}:${role.instance?.instanceId || "missing"}:${skill.skillId}:${skill.revision}`;
}

export function SkillBindingCreatePanel({ item, skill, snapshot, onCreated }: {
  item: Role; skill: Skill; snapshot: Snapshot; onCreated: () => void | Promise<void>;
}) {
  const key = useMemo(() => markerKey(snapshot, item, skill), [snapshot, item, skill]);
  const [result, setResult] = useState<SkillBindingCandidateResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState(() => localStorage.getItem(key) !== null);
  const [note, setNote] = useState("");
  const [receiptId, setReceiptId] = useState("");
  useEffect(() => { setPending(localStorage.getItem(key) !== null); setResult(null); setNote(""); }, [key]);

  async function prepare() {
    setBusy(true);
    setResult(null);
    setNote("");
    try {
      setResult(await loadSkillBindingCandidate(item, skill, snapshot));
    } catch (error) {
      setNote(`权威候选读取失败，禁止创建：${String((error as Error).message || error)}`);
    } finally {
      setBusy(false);
    }
  }

  async function create() {
    if (!result?.candidate || pending || busy) return;
    setBusy(true);
    setNote("");
    try {
      const fresh = await loadSkillBindingCandidate(item, skill, snapshot);
      if (!fresh.candidate || JSON.stringify(fresh.candidate) !== JSON.stringify(result.candidate)) {
        setResult(fresh);
        setNote("当前精确候选已变化，请重新核验后再提交。");
        return;
      }
      const bindingId = `skill-binding-${crypto.randomUUID()}`;
      const idempotencyKey = `skill-binding-create-${crypto.randomUUID()}`;
      localStorage.setItem(key, JSON.stringify({ bindingId, idempotencyKey,
        instanceId: fresh.candidate.instanceId, skill: fresh.candidate.skill }));
      setPending(true);
      const verified = await createProvisioningSkillBinding(fresh.candidate, bindingId, idempotencyKey);
      localStorage.removeItem(key);
      setPending(false);
      setReceiptId(verified.receiptId);
      setResult(null);
      setNote("已创建待配置绑定；仍需由原 Owner 评估并激活，当前未启动运行。");
      try { await onCreated(); }
      catch { setNote("绑定与回执已核验；目录刷新失败，请手动刷新只读状态。"); }
    } catch (error) {
      setNote(`绑定结果未核清，禁止重发；请按原幂等键与 Binding/Receipt 对账：${String((error as Error).message || error)}`);
    } finally {
      setBusy(false);
    }
  }

  if (skill.lifecycle !== "published") {
    return <span>正式发布后才能配置绑定 · <Link to="/aip/skill-publish">查看技能发布</Link></span>;
  }
  return <div style={{ marginTop: 6 }}>
    {pending ? <p role="alert">上次绑定结果未核清，禁止重发；请先只读对账原 Binding 与 Receipt。</p> : null}
    <button className="btn" type="button" disabled={busy || pending} onClick={() => void prepare()}>核验绑定候选</button>
    {result?.blockers.length ? <ul>{result.blockers.map((code) => <li key={code}>{blockerLabels[code] || (code.startsWith("CAPABILITY_BINDING_") ? `必需能力绑定未就绪：${code.split(":")[1] || code}` : code)}</li>)}</ul> : null}
    {result?.candidate && !pending ? <div className="notice" role="group" aria-label="待配置技能绑定确认">
      <p>实例 {result.candidate.instanceId} · 技能 {result.candidate.skill.assetId}@{result.candidate.skill.revision} · 能力绑定 {result.candidate.capabilityBindingIds.length} 项 · 预算策略 {result.candidate.budgetPolicyRef.assetId}@{result.candidate.budgetPolicyRef.revision}。</p>
      <p>本动作只创建待配置绑定；评估、激活与运行仍是独立门。</p>
      <button className="btn primary" type="button" disabled={busy} onClick={() => void create()}>确认创建待配置绑定</button>
    </div> : null}
    {note ? <p role="status">{note}</p> : null}
    {receiptId ? <details><summary>绑定回执（审计用）</summary><code>{receiptId}</code></details> : null}
  </div>;
}
