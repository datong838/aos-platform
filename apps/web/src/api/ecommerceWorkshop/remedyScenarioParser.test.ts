import { describe, expect, it } from "vitest";

import { parsePriceGovernanceView } from "./parser";

const cutoff = "2026-08-26T00:00:00Z";
const contentHash = `sha256:${"a".repeat(64)}`;
const blocker = { code: "OPERATIONAL_GATE_REQUIRED", dependency: "workshop.remedy-gate", requiredAction: "provide exact authorized outcome" };
const priceBlocker = { code: "PRICE_AUTHORITY_NOT_AVAILABLE", dependency: "price", requiredAction: "attach exact authority" };
const stageIds = ["price_observation", "match_decision", "price_case", "affected_orders", "operation_case", "customer_handoff", "contact_permit", "action_outcomes", "effect_review"];
const axisIds = ["repricing_applied", "refund_compensation_submitted", "customer_message_accepted", "operation_case_resolved", "effect_mature"];
const root = { resourceType: "PriceCaseRevision", resourceId: "price-case-1", revision: 1, contentHash };

function payload() {
  return { schemaVersion: "aos.ecommerce-workshop.price-governance-view/v2", tenant: { orgId: "org-org", projectId: "dev-project" }, resourceRevision: 3, evaluatedAt: cutoff, dataCutoff: cutoff, readiness: "degraded", views: ["governance", "competitor", "schedule"].map((viewId) => ({ viewId, status: "blocked", resourceRevision: 3, dataCutoff: cutoff, readinessAxes: ["collection", "match", "policy_case", "notification", "advice_handoff", "repricing"].map((axis) => ({ axis, status: axis === "repricing" ? "disabled" : "blocked", exactRef: null, blockers: [priceBlocker] })), observations: [], authorityRefs: [], blockers: [{ ...priceBlocker, code: `PRICE_${viewId.toUpperCase()}_AUTHORITY_NOT_AVAILABLE` }], countLedger: { input: 0, eligible: 0, excluded: 0, needsReview: 0, unknown: 0, deduplicated: 0 } })), remedyScenario: { schemaVersion: "aos.ecommerce-workshop.remedy-scenario/v1", status: "blocked", rootCaseRef: root, remedyBindingHash: "b".repeat(64), evaluatedAt: cutoff, stages: stageIds.map((stageId) => stageId === "price_case" ? { stageId, status: "ready", exactRefs: [root], contribution: "exact PriceCase root", blockers: [] } : { stageId, status: "blocked", exactRefs: [], contribution: "waiting for exact authority", blockers: [blocker] }), ledger: { affectedOrdersExpected: 3, affectedOrdersObserved: 2, eligibleCustomersExpected: 2, eligibleCustomersObserved: 1, actionsExpected: 5, actionsReady: 0, actionsBlocked: 5, actionsUnknown: 0 }, outcomeAxes: axisIds.map((axisId) => ({ axisId, status: "blocked", exactRef: null, blocker })), blockers: [blocker], commands: { reprice: false, refundOrCompensate: false, sendMessage: false, resolveCase: false }, protectedContactResolved: false, externalEffectsAllowed: false }, page: { limit: 100, count: 0, hasMore: false, nextCursor: null } };
}

describe("W8-02 remedy scenario parser", () => {
  it("接受 exact PriceCase 根并保留九阶段五结果轴", () => { const result = parsePriceGovernanceView(payload(), { orgId: "org-org", projectId: "dev-project" }); expect(result.remedyScenario?.rootCaseRef).toEqual(root); expect(result.remedyScenario?.stages).toHaveLength(9); expect(result.remedyScenario?.outcomeAxes).toHaveLength(5); expect(result.remedyScenario?.commands.sendMessage).toBe(false); });
  it("拒绝数量不守恒", () => { const drift = payload(); drift.remedyScenario.ledger.actionsBlocked = 4; expect(() => parsePriceGovernanceView(drift)).toThrow(/不守恒/); });
  it("拒绝受保护联系正文与动作开放", () => { const pii: Record<string, any> = payload(); pii.remedyScenario.mobile = "redacted-test-value"; expect(() => parsePriceGovernanceView(pii)).toThrow(/禁止联系方式/); const action = payload(); action.remedyScenario.commands.sendMessage = true; expect(() => parsePriceGovernanceView(action)).toThrow(/必须全部关闭/); });
  it("拒绝 PriceCase 根未进入 price_case 阶段", () => { const drift = payload(); drift.remedyScenario.stages[2]!.exactRefs = [{ ...root, resourceId: "another-case" }]; expect(() => parsePriceGovernanceView(drift)).toThrow(/根未进入/); });
});
