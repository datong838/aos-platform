import type { ActionDraftBundle, ActionExecutionView } from "../../api/aipActions";

export type ActionBoundaryStageState = "complete" | "waiting" | "blocked" | "unknown";

export type ActionBoundaryStage = {
  id: "artifact" | "proposal" | "approval" | "lease" | "attempt" | "receipt" | "effect";
  label: string;
  state: ActionBoundaryStageState;
  detail: string;
};

const COMPLETED_APPROVAL_STATUSES = new Set([
  "approved", "leased", "executing", "applied", "failed", "unknown", "reconciled", "compensated",
]);

const STATE_LABELS: Record<ActionBoundaryStageState, string> = {
  complete: "已闭合",
  waiting: "待继续",
  blocked: "已阻断",
  unknown: "待对账",
};

function effectReviewRef(execution: ActionExecutionView) {
  return execution.receipts
    .flatMap((receipt) => receipt.evidenceRefs)
    .find((reference) => reference.resourceType === "EffectReview" && reference.revision !== null);
}

export function deriveActionBoundaryStages(
  bundle: ActionDraftBundle,
  execution: ActionExecutionView,
): ActionBoundaryStage[] {
  const { proposal } = bundle;
  const latestReceipt = execution.receipts[execution.receipts.length - 1];
  const effectRef = effectReviewRef(execution);
  const rejected = proposal.status === "rejected" || proposal.status === "expired";
  const approvalComplete = COMPLETED_APPROVAL_STATUSES.has(proposal.status)
    && bundle.approvals.some((approval) => approval.decision === "approved");
  const receiptState: ActionBoundaryStageState = !latestReceipt
    ? "waiting"
    : latestReceipt.status === "unknown"
      ? "unknown"
      : latestReceipt.status === "failed"
        ? "blocked"
        : latestReceipt.status === "applied" || latestReceipt.status === "reconciled"
          ? "complete"
          : "waiting";

  const stages: ActionBoundaryStage[] = [
    {
      id: "artifact",
      label: "专业产物",
      state: "complete",
      detail: "Recommendation / ActionDraft 已形成；这不代表外部动作已执行",
    },
    {
      id: "proposal",
      label: "执行提案",
      state: rejected ? "blocked" : "complete",
      detail: rejected ? "Proposal 已拒绝或过期" : `Proposal v${proposal.version} 已从服务端回读`,
    },
    {
      id: "approval",
      label: "人工审批",
      state: rejected ? "blocked" : approvalComplete ? "complete" : "waiting",
      detail: rejected ? "审批链已关闭" : approvalComplete ? "exact Proposal 版本已批准" : "等待 maker-checker 审批",
    },
    {
      id: "lease",
      label: "执行租约",
      state: rejected ? "blocked" : execution.lease ? "complete" : "waiting",
      detail: execution.lease ? `单次租约 attempt ${execution.lease.attempt}` : "尚无服务端执行租约",
    },
    {
      id: "attempt",
      label: "外部尝试",
      state: rejected ? "blocked" : proposal.status === "unknown" ? "unknown" : latestReceipt ? "complete" : "waiting",
      detail: proposal.status === "unknown"
        ? "结果未知，禁止重复执行"
        : latestReceipt
          ? "Attempt 已产生不可变交付凭证"
          : "尚无交付凭证，不能推导 Provider 调用",
    },
    {
      id: "receipt",
      label: "动作结果",
      state: rejected ? "blocked" : receiptState,
      detail: !latestReceipt
        ? "尚无交付凭证，Action 未闭合"
        : latestReceipt.status === "unknown"
          ? "结果未知，等待只读对账"
          : latestReceipt.status === "failed"
            ? "交付凭证确认失败"
            : latestReceipt.status === "applied" || latestReceipt.status === "reconciled"
              ? "交付凭证已证明外部结果"
              : "Provider 已接受，最终结果仍待回读",
    },
    {
      id: "effect",
      label: "效果复核",
      state: receiptState === "unknown" ? "unknown" : receiptState === "blocked" ? "blocked" : "waiting",
      detail: effectRef && receiptState === "complete"
        ? `EffectReview ${effectRef.resourceId} rev ${effectRef.revision} 引用存在，但当前 Receipt 引用不含 contentHash，不能关闭效果轴`
        : receiptState === "unknown"
          ? "外部结果未闭合，禁止推导效果"
          : receiptState === "blocked"
            ? "Action 失败，效果轴保持未达成"
            : "尚无 exact EffectReview 引用",
    },
  ];
  return stages;
}

function stateClass(state: ActionBoundaryStageState): string {
  if (state === "complete") return "border-green-200 bg-green-50 text-green-800";
  if (state === "blocked") return "border-red-200 bg-red-50 text-red-800";
  if (state === "unknown") return "border-amber-300 bg-amber-50 text-amber-900";
  return "border-gray-200 bg-gray-50 text-gray-700";
}

export function ActionBoundaryPanel({
  bundle,
  execution,
}: {
  bundle: ActionDraftBundle;
  execution: ActionExecutionView;
}) {
  const stages = deriveActionBoundaryStages(bundle, execution);
  return (
    <section aria-label="动作与效果边界" data-testid="action-boundary-panel">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-gray-800">动作与效果边界</h3>
          <p className="mt-1 text-xs text-gray-500">专业产物完成 ≠ Action 成功 ≠ Effect 已复核</p>
        </div>
        <span className="rounded border border-blue-200 bg-blue-50 px-2 py-1 text-xs text-blue-900">只读 canonical 投影</span>
      </div>
      <ol className="mt-2 grid gap-2" style={{ gridTemplateColumns: "repeat(auto-fit,minmax(142px,1fr))" }}>
        {stages.map((stage) => (
          <li key={stage.id} className={`rounded border p-2 ${stateClass(stage.state)}`} data-stage={stage.id} data-state={stage.state}>
            <div className="flex items-center justify-between gap-2">
              <strong className="text-xs">{stage.label}</strong>
              <span className="text-xs">{STATE_LABELS[stage.state]}</span>
            </div>
            <p className="mt-1 text-xs">{stage.detail}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}
