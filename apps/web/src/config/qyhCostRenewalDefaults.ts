/** 用户明确授权的唯一截止：2027-03-31 12:00（北京时间）。 */
export const QYH_AUTHORIZED_EFFECTIVE_UNTIL = "2027-03-31T04:00:00.000Z";

export type AuthorizedQyhWindow = { effectiveFrom: string; effectiveUntil: string };

/** 开始时间允许略早于当前时点；截止时间不得滚动或扩大。 */
export function computeAuthorizedQyhWindow(reference = new Date()): AuthorizedQyhWindow {
  const effectiveFrom = new Date(reference.getTime() - 60_000);
  return { effectiveFrom: effectiveFrom.toISOString(), effectiveUntil: QYH_AUTHORIZED_EFFECTIVE_UNTIL };
}

export function targetMatchesAuthorizedQyhWindow(target: { effectiveFrom: string; effectiveUntil: string }, reference = new Date()): boolean {
  const from = Date.parse(target.effectiveFrom);
  const until = Date.parse(target.effectiveUntil);
  const now = reference.getTime();
  if (!Number.isFinite(from) || !Number.isFinite(until) || until <= from) return false;
  return from <= now && now < until && until === Date.parse(QYH_AUTHORIZED_EFFECTIVE_UNTIL);
}

/** 栖月汇授权默认；费用提议 target 须与 activation-candidate 字节级一致。 */
export const QYH_COST_RENEWAL = {
  tenant: { orgId: "org-org", projectId: "dev-project" } as const,
  budgetId: "a0v-ecommerce-hard-stop-budget-v1",
  authorization: {
    providerModelId: "agnes-2.5-flash",
    currency: "CNY" as const,
    dailyLimitMinor: 10_000,
    monthlyLimitMinor: 100_000,
    get window() {
      return computeAuthorizedQyhWindow();
    },
  },
  provider: {
    assetType: "ProviderInstanceRevision" as const,
    assetId: "a0v-agnes-text-readonly-dev",
    revision: 1,
    contentHash: "66941c4bb51757f5d95a6149580f7bbb3dbe86debb2035747fa96229efb06982",
  },
  risk: { perRequestRiskMinor: 10, totalRiskMinor: 100, maxRequests: 10 },
};

export type QyhBudgetDraftInput = {
  budgetId: string;
  dailyYuan: string;
  monthlyYuan: string;
  alertThresholdPct: string;
  effectiveFrom: string;
  effectiveUntil: string;
  owner: string;
  overBudgetApprover: string;
};

export function defaultBudgetDraftInput(reference = new Date()): QyhBudgetDraftInput {
  const { effectiveFrom, effectiveUntil } = computeAuthorizedQyhWindow(reference);
  return {
    budgetId: QYH_COST_RENEWAL.budgetId,
    dailyYuan: "100",
    monthlyYuan: "1000",
    alertThresholdPct: "80",
    effectiveFrom: effectiveFrom.slice(0, 16),
    effectiveUntil: effectiveUntil.slice(0, 16),
    owner: "dev-budget-owner",
    overBudgetApprover: "dev-budget-approver",
  };
}

export function authorizedQyhWindowLabel(reference = new Date()): string {
  const { effectiveFrom, effectiveUntil } = computeAuthorizedQyhWindow(reference);
  return `${effectiveFrom} → ${effectiveUntil}（固定截止：2027-03-31 12:00 北京时间）`;
}

/** 费用父链：用户只需点「确认」，选项由推荐默认填充。 */
export const COST_CONFIRM_DEFAULTS = {
  decide: "approved",
  consume: "consume",
  configure: "configure",
} as const;

export function resolveDevCheckerSubject(members: { subject: string; role?: string }[], maker?: string): string {
  const env = import.meta.env.VITE_AOS_DEV_CHECKER_SUBJECT?.trim();
  if (env && env !== maker) return env;
  const me = maker ?? "";
  const admin = members.find((m) => m.subject && m.subject !== me && (m.role === "admin" || m.role === "owner"));
  if (admin?.subject) return admin.subject;
  const other = members.find((m) => m.subject && m.subject !== me);
  return other?.subject ?? "";
}
