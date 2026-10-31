import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { clearAccessToken, setAccessToken } from "../../api/tenant";
import { BudgetRevisionSetupPanel, buildBudgetDraft, exactBudgetDraftReadback, type BudgetDraftInput } from "./BudgetRevisionSetupPanel";

const apiGetAuthoritative = vi.hoisted(() => vi.fn());
const apiPostUnqueued = vi.hoisted(() => vi.fn());
vi.mock("../../api/client", () => ({ apiGetAuthoritative, apiPostUnqueued }));

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

afterEach(() => {
  clearAccessToken();
  vi.clearAllMocks();
});

const INPUT: BudgetDraftInput = {
  budgetId: "qyh-content-first-chain", dailyYuan: "12.34", monthlyYuan: "100.00",
  alertThresholdPct: "80",
  effectiveFrom: "2026-09-27T09:00", effectiveUntil: "2026-10-27T09:00",
  owner: "qyh-budget-owner", overBudgetApprover: "qyh-budget-checker",
};

describe("budget draft configuration boundary", () => {
  it("converts CNY yuan to integer minor units and never activates on create", () => {
    const body = buildBudgetDraft(INPUT);
    expect(body.dailyLimitMinor).toBe(1234);
    expect(body.monthlyLimitMinor).toBe(10000);
    expect(body.lifecycle).toBe("draft");
    expect(body.hardStop).toBe(true);
    expect(body.unknownUsageBehavior).toBe("block");
    expect(body.currency).toBe("CNY");
    expect(body.alertThresholdPct).toBe(80);
  });

  it("rejects imprecise, negative, inverted and unowned budgets", () => {
    expect(() => buildBudgetDraft({ ...INPUT, dailyYuan: "1.234" })).toThrow("最多两位小数");
    expect(() => buildBudgetDraft({ ...INPUT, dailyYuan: "-1" })).toThrow("最多两位小数");
    expect(() => buildBudgetDraft({ ...INPUT, monthlyYuan: "1" })).toThrow("月预算不得小于日预算");
    expect(() => buildBudgetDraft({ ...INPUT, effectiveUntil: INPUT.effectiveFrom })).toThrow("生效起止时间");
    expect(() => buildBudgetDraft({ ...INPUT, overBudgetApprover: " " })).toThrow("审批人");
    expect(() => buildBudgetDraft({ ...INPUT, alertThresholdPct: "" })).toThrow("告警阈值");
    expect(() => buildBudgetDraft({ ...INPUT, alertThresholdPct: "101" })).toThrow("告警阈值");
  });

  it("requires current tenant, exact amount, draft state and hash on readback", () => {
    const body = buildBudgetDraft(INPUT);
    const tenant = { orgId: "org-org", projectId: "dev-project" };
    const row = { ...body, tenant, contentHash: "a".repeat(64),
      effectiveFrom: body.effectiveFrom.replace(".000Z", "+00:00"),
      effectiveUntil: body.effectiveUntil.replace(".000Z", "+00:00") };
    expect(exactBudgetDraftReadback(row, body, tenant)).toBe(true);
    expect(exactBudgetDraftReadback({ ...row, lifecycle: "active" }, body, tenant)).toBe(false);
    expect(exactBudgetDraftReadback({ ...row, dailyLimitMinor: 1235 }, body, tenant)).toBe(false);
    expect(exactBudgetDraftReadback({ ...row, alertThresholdPct: 79 }, body, tenant)).toBe(false);
    expect(exactBudgetDraftReadback({ ...row, tenant: { ...tenant, orgId: "dev-org" } }, body, tenant)).toBe(false);
    expect(exactBudgetDraftReadback({ ...row, contentHash: "not-a-hash" }, body, tenant)).toBe(false);
  });

  it("keeps every formal budget action disabled until a current OIDC session exists", async () => {
    clearAccessToken();
    const host = document.createElement("div");
    const root = createRoot(host);
    await act(async () => root.render(<BudgetRevisionSetupPanel />));

    const buttons = Array.from(host.querySelectorAll<HTMLButtonElement>("button"));
    const action = (label: string) => buttons.find(button => button.textContent === label)!;
    expect(action("按 ID 只读查询").disabled).toBe(true);
    expect(action("确认写入 draft（推荐默认）").disabled).toBe(true);
    expect(action("只读核对原命令").disabled).toBe(true);
    expect(apiGetAuthoritative).not.toHaveBeenCalled();
    expect(apiPostUnqueued).not.toHaveBeenCalled();

    await act(async () => setAccessToken("current-oidc"));
    expect(action("按 ID 只读查询").disabled).toBe(false);
    expect(action("确认写入 draft（推荐默认）").disabled).toBe(false);
    expect(apiGetAuthoritative).not.toHaveBeenCalled();
    expect(apiPostUnqueued).not.toHaveBeenCalled();

    await act(async () => clearAccessToken());
    expect(action("按 ID 只读查询").disabled).toBe(true);
    expect(action("确认写入 draft（推荐默认）").disabled).toBe(true);
    expect(apiGetAuthoritative).not.toHaveBeenCalled();
    expect(apiPostUnqueued).not.toHaveBeenCalled();
    await act(async () => root.unmount());
  });
});
