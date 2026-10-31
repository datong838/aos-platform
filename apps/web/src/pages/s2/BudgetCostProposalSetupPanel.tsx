import { useEffect, useState } from "react";
import { apiGetAuthoritative } from "../../api/client";
import { createCostProposal, readCostActivationCandidate, type CostProposalCreateBody } from "../../api/aipBudgetCost";
import {
  QYH_COST_RENEWAL,
  STABLE_DEV_MONTHS,
  stableDevWindowLabel,
  targetCoversStableDev,
  resolveDevCheckerSubject,
} from "../../config/qyhCostRenewalDefaults";
import type { BudgetTarget } from "../../api/aipBudgetActivation";
import { getAuthRevision, getTenant } from "../../api/tenant";
import { useBudgetRequestGuard } from "./useBudgetRequestGuard";

type Member = { subject: string; role?: string };

export function BudgetCostProposalSetupPanel() {
  const [checker, setChecker] = useState("");
  const [members, setMembers] = useState<Member[]>([]);
  const [candidateReady, setCandidateReady] = useState(false);
  const [candidateError, setCandidateError] = useState("");
  const [attempted, setAttempted] = useState(false);
  const [candidateTarget, setCandidateTarget] = useState<BudgetTarget | null>(null);
  const [message, setMessage] = useState(`三月开发默认：${stableDevWindowLabel()}；提交前读取权威预算候选第 2 版，须覆盖满 ${STABLE_DEV_MONTHS} 个月。`);
  const guard = useBudgetRequestGuard(() => {
    setAttempted(false);
    setMessage("身份或工作区已变化，请重新读取预算候选。");
  });

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const candidate = await readCostActivationCandidate(QYH_COST_RENEWAL.budgetId);
        if (!cancelled) {
          setCandidateTarget(candidate.target);
          if (!targetCoversStableDev(candidate.target)) {
            setCandidateReady(false);
            setCandidateError(`权威候选有效期不足 ${STABLE_DEV_MONTHS} 个月（至 ${candidate.target.effectiveUntil}）。请先按页顶预算草稿默认调整并激活候选。`);
          } else {
            setCandidateReady(true);
            setCandidateError("");
          }
        }
      } catch (e) {
        if (!cancelled) { setCandidateReady(false); setCandidateError((e as Error).message); }
      }
    })();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    const projectId = getTenant().projectId;
    if (!projectId) return;
    void apiGetAuthoritative<Member[]>(`/v1/workspaces/${encodeURIComponent(projectId)}/members`)
      .then((list) => {
        if (!Array.isArray(list)) return;
        const filtered = list.filter((m) => typeof m.subject === "string");
        setMembers(filtered);
        const me = getTenant().subject;
        const picked = resolveDevCheckerSubject(filtered, me);
        if (picked) setChecker((c) => c || picked);
      })
      .catch(() => { /* 成员列表不可用时仍允许手填 checker */ });
  }, []);

  async function submit() {
    if (guard.busyRef.current || attempted) return;
    const tenant = getTenant();
    const maker = tenant.subject;
    const checkerSubject = checker.trim();
    if (!maker || !checkerSubject || checkerSubject === maker) {
      setMessage("须指定与发起人不同的独立审核人登录名。");
      return;
    }
    let candidate;
    try {
      candidate = await readCostActivationCandidate(QYH_COST_RENEWAL.budgetId);
      if (!targetCoversStableDev(candidate.target)) {
        setMessage(`预算候选未覆盖 ${STABLE_DEV_MONTHS} 个月开发窗（至 ${candidate.target.effectiveUntil}），不能发起；请先更新预算 draft。`);
        setAttempted(false);
        return;
      }
    } catch (e) { setMessage(`无法读取预算候选：${(e as Error).message}`); return; }
    const body: CostProposalCreateBody = {
      schemaVersion: 1,
      tenant: { ...QYH_COST_RENEWAL.tenant },
      target: candidate.target,
      draftRevision: candidate.draftRevision,
      expectedHeadVersion: candidate.headVersion,
      makerSubject: maker,
      checkerSubject,
      basis: {
        kind: "development_risk_proposal",
        provider: { ...QYH_COST_RENEWAL.provider },
        providerModelId: QYH_COST_RENEWAL.authorization.providerModelId,
        ...QYH_COST_RENEWAL.risk,
      },
    };
    const identity = JSON.stringify([tenant.orgId, tenant.projectId, maker, getAuthRevision()]);
    const key = `cost-proposal-${QYH_COST_RENEWAL.budgetId}-${candidate.headVersion}`;
    setAttempted(true);
    guard.busyRef.current = true;
    setMessage("正在提交唯一费用提议…");
    try {
      const created = await createCostProposal(body, key);
      const after = getTenant();
      if (identity !== JSON.stringify([after.orgId, after.projectId, after.subject, getAuthRevision()])) {
        throw new Error("提交期间身份已变化");
      }
      setMessage(`费用提议已登记：${created.proposalId}（开发窗至 ${candidate.target.effectiveUntil}）。请在下方继续 decide → consume → configure。`);
      window.dispatchEvent(new CustomEvent("aos-cost-proposal-created", { detail: { proposalId: created.proposalId } }));
    } catch (e) {
      setAttempted(false);
      setMessage(`提议未确认：${(e as Error).message}。请只读对账，勿换幂等键重发。`);
    } finally {
      guard.busyRef.current = false;
    }
  }

  const me = getTenant().subject ?? "（未识别登录名）";
  return (
    <section className="card" aria-label="费用提议发起" style={{ padding: 18, marginTop: 16 }}>
      <h2>费用提议发起（{STABLE_DEV_MONTHS} 个月开发默认）</h2>
      <p>
        预算 <code>{QYH_COST_RENEWAL.budgetId}</code> · 模型 {QYH_COST_RENEWAL.authorization.providerModelId} ·
        日 ¥{(QYH_COST_RENEWAL.authorization.dailyLimitMinor / 100).toFixed(0)} / 月 ¥{(QYH_COST_RENEWAL.authorization.monthlyLimitMinor / 100).toFixed(0)} ·
        风险 {QYH_COST_RENEWAL.risk.perRequestRiskMinor}/{QYH_COST_RENEWAL.risk.totalRiskMinor}/{QYH_COST_RENEWAL.risk.maxRequests}（单次/总/次数）。
      </p>
      <p>目标开发窗（默认）：{stableDevWindowLabel()}。正式续期截止单独办理，此处只保证开发期不断档。</p>
      {candidateTarget && <p>权威候选第 2 版有效期：{candidateTarget.effectiveFrom} → {candidateTarget.effectiveUntil}</p>}
      <p>发起人（当前登录）：<strong>{me}</strong> · 独立审核人（推荐默认）：<strong>{checker || "加载中…"}</strong></p>
      {!candidateReady && <p role="alert">{candidateError || "正在读取预算候选…"}</p>}
      <input type="hidden" aria-label="独立审核人登录名" value={checker} readOnly />
      <details style={{ marginTop: 8 }}>
        <summary>高级：更换审核人</summary>
        <label>
          独立审核人登录名
          <input
            list="aos-cost-checker-members"
            value={checker}
            maxLength={200}
            disabled={attempted || guard.busy}
            onChange={(e) => setChecker(e.target.value)}
          />
        </label>
        <datalist id="aos-cost-checker-members">
          {members.filter((m) => m.subject !== me).map((m) => (
            <option key={m.subject} value={m.subject}>{m.role ?? "member"}</option>
          ))}
        </datalist>
      </details>
      <div style={{ marginTop: 12 }}>
        <button type="button" className="btn btn-primary" disabled={!candidateReady || attempted || guard.busy || !checker.trim()} onClick={() => void submit()}>
          确认发起（推荐默认已填）
        </button>
      </div>
      <p role="status">{message}</p>
    </section>
  );
}
