import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { setTenant } from "../../api/tenant";
import { QYH_AUTHORIZED_EFFECTIVE_UNTIL } from "../../config/qyhCostRenewalDefaults";
import { BudgetCostProposalSetupPanel } from "./BudgetCostProposalSetupPanel";

const readCostActivationCandidate = vi.hoisted(() => vi.fn());
const createCostProposal = vi.hoisted(() => vi.fn());
const apiGetAuthoritative = vi.hoisted(() => vi.fn());

vi.mock("../../api/aipBudgetCost", () => ({ readCostActivationCandidate, createCostProposal }));
vi.mock("../../api/client", () => ({ apiGetAuthoritative }));

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const target = {
  budgetId: "a0v-ecommerce-hard-stop-budget-v1",
  revision: 2,
  environment: "development" as const,
  currency: "CNY" as const,
  dailyLimitMinor: 10_000,
  monthlyLimitMinor: 100_000,
  alertThresholdPct: 80,
  hardStop: true as const,
  unknownUsageBehavior: "block" as const,
  effectiveFrom: "2026-10-31T00:00:00.000Z",
  effectiveUntil: QYH_AUTHORIZED_EFFECTIVE_UNTIL,
  owner: "maker",
  overBudgetApprover: "checker",
  lifecycle: "active" as const,
};

async function flush() {
  await act(async () => { await Promise.resolve(); await Promise.resolve(); });
}

describe("BudgetCostProposalSetupPanel authorized window", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    setTenant({ orgId: "org-org", projectId: "dev-project", workspaceName: "QYH", subject: "maker" });
    apiGetAuthoritative.mockResolvedValue([{ subject: "maker", role: "admin" }, { subject: "checker", role: "admin" }]);
    readCostActivationCandidate.mockResolvedValue({ headVersion: 1, draftRevision: 1, target });
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
  });

  afterEach(() => {
    act(() => root.unmount());
    host.remove();
    vi.clearAllMocks();
  });

  it("enables confirmation only for the exact authorized expiry", async () => {
    await act(async () => root.render(<BudgetCostProposalSetupPanel />));
    await flush();
    const button = host.querySelector<HTMLButtonElement>("button.btn-primary")!;
    expect(button.disabled).toBe(false);
    expect(host.textContent).toContain("2027-03-31 12:00 北京时间");
    expect(host.textContent).not.toContain("3 个月开发默认");
  });

  it("blocks a later rolling target without submitting", async () => {
    readCostActivationCandidate.mockResolvedValue({
      headVersion: 1,
      draftRevision: 1,
      target: { ...target, effectiveUntil: "2027-04-01T04:00:00.000Z" },
    });
    await act(async () => root.render(<BudgetCostProposalSetupPanel />));
    await flush();
    expect(host.querySelector<HTMLButtonElement>("button.btn-primary")!.disabled).toBe(true);
    expect(host.querySelector("[role='alert']")?.textContent).toContain("与授权截止");
    expect(createCostProposal).not.toHaveBeenCalled();
  });
});
