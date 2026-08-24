import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { PriceGovernanceViewResponse } from "../../api/ecommerceWorkshop";
import { PriceGovernancePage } from "./PriceGovernancePage";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const ids = ["governance", "competitor", "schedule"] as const;
const axes = ["collection", "match", "policy_case", "notification", "advice_handoff", "repricing"] as const;
const cutoff = "2026-08-24T08:00:00Z";
const blocked: PriceGovernanceViewResponse = { schemaVersion: "aos.ecommerce-workshop.price-governance-view/v1", tenant: { orgId: "org-org", projectId: "dev-project" }, resourceRevision: 1, evaluatedAt: cutoff, dataCutoff: cutoff, readiness: "degraded", views: ids.map((viewId) => { const blocker = { code: `PRICE_${viewId.toUpperCase()}_AUTHORITY_NOT_AVAILABLE`, dependency: viewId, requiredAction: "attach exact licensed authority" }; return { viewId, status: "blocked", resourceRevision: 1, dataCutoff: cutoff, readinessAxes: axes.map((axis) => axis === "repricing" ? { axis, status: "disabled", exactRef: null, blockers: [{ code: "PRICE_REPRICING_DISABLED", dependency: "R4", requiredAction: "complete specialized gate" }] } : { axis, status: "blocked", exactRef: null, blockers: [blocker] }), observations: [], authorityRefs: [], blockers: [blocker], countLedger: { input: 0, eligible: 0, excluded: 0, needsReview: 0, unknown: 0, deduplicated: 0 } }; }), page: { limit: 100, count: 0, hasMore: false, nextCursor: null } };

describe("PriceGovernancePage", () => {
  let host: HTMLDivElement; let root: Root;
  beforeEach(() => { host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host); });
  afterEach(() => { act(() => root.unmount()); host.remove(); });
  it("展示三视图六轴且调价恒禁用", async () => { await act(async () => root.render(<PriceGovernancePage client={{ getPriceGovernanceView: vi.fn().mockResolvedValue(blocked) }} />)); expect(host.querySelectorAll('[role="tab"]')).toHaveLength(3); expect(host.querySelectorAll(".price-governance-readiness article")).toHaveLength(6); expect(host.textContent).toContain("调价禁用"); expect(host.textContent).toContain("写入口"); expect(Array.from(host.querySelectorAll("button")).map((item) => item.textContent).join(" ")).not.toMatch(/开始采集|批准策略|发送通知|执行调价/); });
  it("切换竞品视图不制造零价格", async () => { await act(async () => root.render(<PriceGovernancePage client={{ getPriceGovernanceView: vi.fn().mockResolvedValue(blocked) }} />)); const tab = Array.from(host.querySelectorAll<HTMLButtonElement>('[role="tab"]')).find((item) => item.textContent?.includes("竞品同款")); act(() => tab?.click()); expect(host.querySelector('[role="tabpanel"]')?.textContent).toContain("当前没有可挂接的价格 Observation"); });
  it("支持方向键沿三视图循环", async () => { await act(async () => root.render(<PriceGovernancePage client={{ getPriceGovernanceView: vi.fn().mockResolvedValue(blocked) }} />)); const tabs = host.querySelectorAll<HTMLButtonElement>('[role="tab"]'); act(() => tabs[0]?.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true }))); expect(host.querySelector('[role="tabpanel"]')?.getAttribute("aria-label")).toBe("竞品同款"); expect(tabs[1]?.tabIndex).toBe(0); });
});
