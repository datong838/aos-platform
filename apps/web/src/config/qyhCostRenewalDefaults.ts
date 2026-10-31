/** 开发默认：连续 3 个月有效，不依赖正式续期截止日。 */
export const STABLE_DEV_MONTHS = 3;

export type StableDevWindow = { effectiveFrom: string; effectiveUntil: string };

export function addUtcMonths(from: Date, months: number): Date {
  const d = new Date(from.getTime());
  d.setUTCMonth(d.getUTCMonth() + months);
  return d;
}

/** 滚动开发窗：从略早于「现在」起算，至少覆盖 STABLE_DEV_MONTHS 个自然月。 */
export function computeStableDevWindow(reference = new Date()): StableDevWindow {
  const effectiveFrom = new Date(reference.getTime() - 60_000);
  const effectiveUntil = addUtcMonths(reference, STABLE_DEV_MONTHS);
  return { effectiveFrom: effectiveFrom.toISOString(), effectiveUntil: effectiveUntil.toISOString() };
}

export function minimumStableDevUntil(reference = new Date()): number {
  return addUtcMonths(reference, STABLE_DEV_MONTHS).getTime();
}

export function targetCoversStableDev(target: { effectiveFrom: string; effectiveUntil: string }, reference = new Date()): boolean {
  const from = Date.parse(target.effectiveFrom);
  const until = Date.parse(target.effectiveUntil);
  const now = reference.getTime();
  if (!Number.isFinite(from) || !Number.isFinite(until) || until <= from) return false;
  return from <= now && until >= minimumStableDevUntil(reference);
}

/** 栖月汇开发默认（非正式续期材料）；费用提议 target 须与 activation-candidate 字节级一致。 */
export const QYH_COST_RENEWAL = {
  tenant: { orgId: "org-org", projectId: "dev-project" } as const,
  budgetId: "a0v-ecommerce-hard-stop-budget-v1",
  authorization: {
    providerModelId: "agnes-2.5-flash",
    currency: "CNY" as const,
    dailyLimitMinor: 10_000,
    monthlyLimitMinor: 100_000,
    get window() {
      return computeStableDevWindow();
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
  const { effectiveFrom, effectiveUntil } = computeStableDevWindow(reference);
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

export function stableDevWindowLabel(reference = new Date()): string {
  const { effectiveFrom, effectiveUntil } = computeStableDevWindow(reference);
  return `${effectiveFrom} → ${effectiveUntil}（${STABLE_DEV_MONTHS} 个月，无需中途续期）`;
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
