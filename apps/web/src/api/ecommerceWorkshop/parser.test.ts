import { describe, expect, it } from "vitest";
import { parseContentCampaignView, parseEcommerceWorkshopModuleList, parseEcommerceWorkshopModuleReadiness, parseOperationCommandObservation, parseOperationCommandReadiness, parseOperationsView, parseSourceReadinessEnvelope, parseTaskCockpitActionReceipts, parseTaskCockpitApprovalReview, parseTaskCockpitCheckpoints, parseTaskCockpitCore, parseTaskCockpitProductionContext, parseTaskCockpitResponsibilityHandoffs, parseTaskCockpitSteps, parseWorkshopSharedContext } from "./parser";

const hash = (value: string) => `sha256:${value.repeat(64)}`;
const blocker = { dependencyType: "aip_feature", dependencyId: "aip.task-runtime", state: "unknown", reasonCode: "AIP_FEATURE_UNVERIFIED", recoverable: true, requiredAction: "等待 canonical reader 回读", ref: null };
const module = {
  moduleId: "ecommerce.operations", displayName: "统一运营驾驶舱", menuLabel: "统一运营驾驶舱", route: "/workshop/operations", slot: "workshop.primary.ecommerce", order: 30,
  installationRef: { installationId: "11111111-1111-4111-8111-111111111111", revision: 5, compositionId: "22222222-2222-4222-8222-222222222222", lockRevision: 1, lockHash: hash("a"), overlayRevision: "overlay-5" },
  moduleRef: { publisher: "aos", bundleId: "solution.ecommerce.operations-base", version: "1.1.0", bundleContentHash: hash("b"), moduleArtifactRef: "bundle://catalog/solutions/ecommerce-operations-base/content/workshops/ecommerce.operations.json", moduleArtifactHash: hash("c") },
  readiness: "unknown", blockers: [blocker], permissions: { roles: [], markings: [], dataScopes: ["ecommerce.workshop.read"], actionTypes: [] },
  requiredObjects: ["Order"], requiredCapabilities: ["performance.review"], requiredAipFeatures: ["aip.task-runtime"], viewRefs: [], evalPackRefs: [], productionContractRefs: [], responsibilityTemplateRefs: [], impactCalculatorRefs: [], legacyAssetRefs: [], legacyRoutes: ["/workshop/orders"], minimumRuntimeVersion: "1.7.0", lastReceiptRef: null,
};
const list = { schemaVersion: "aos.ecommerce-workshop/v1", tenant: { orgId: "org-org", projectId: "dev-project" }, evaluatedAt: "2026-08-14T00:00:00Z", dataCutoff: null, items: [module], count: 1 };

describe("ecommerceWorkshop strict parser", () => {
  it("解析 exact module list/readiness 并保留 blocked 证据", () => {
    expect(parseEcommerceWorkshopModuleList(list)).toMatchObject({ count: 1, items: [{ moduleId: "ecommerce.operations", readiness: "unknown" }] });
    expect(parseEcommerceWorkshopModuleReadiness({ schemaVersion: list.schemaVersion, tenant: list.tenant, evaluatedAt: list.evaluatedAt, dataCutoff: null, item: module }).item.blockers).toHaveLength(1);
  });
  it("extra、unknown enum、hash/ref 漂移全部失败关闭", () => {
    expect(() => parseEcommerceWorkshopModuleList({ ...list, extra: true })).toThrow("字段漂移");
    expect(() => parseEcommerceWorkshopModuleList({ ...list, items: [{ ...module, readiness: "future" }] })).toThrow("未知枚举");
    expect(() => parseEcommerceWorkshopModuleList({ ...list, items: [{ ...module, moduleRef: { ...module.moduleRef, moduleArtifactHash: "bad" } }] })).toThrow("SHA-256");
    expect(() => parseEcommerceWorkshopModuleList({ ...list, items: [{ ...module, moduleRef: { ...module.moduleRef, version: "01.2.3" } }] })).toThrow("SemVer");
    expect(() => parseEcommerceWorkshopModuleList({ ...list, items: [{ ...module, minimumRuntimeVersion: "v1.7" }] })).toThrow("SemVer");
    expect(() => parseEcommerceWorkshopModuleList({ ...list, items: [{ ...module, installationRef: { ...module.installationRef, installationId: "NOT-UUID" } }] })).toThrow("UUID");
  });
  it("readiness/blocker、排序和 count 不一致失败关闭", () => {
    expect(() => parseEcommerceWorkshopModuleList({ ...list, items: [{ ...module, readiness: "available" }] })).toThrow("不一致");
    expect(() => parseEcommerceWorkshopModuleList({ ...list, count: 2 })).toThrow("count");
    expect(() => parseEcommerceWorkshopModuleList({ ...list, items: [{ ...module, requiredObjects: ["Z", "A"] }] })).toThrow("排序");
  });
});

const sharedToken = `ctx_${"a".repeat(40)}`;
const sharedRef = { authority: "task-authority", resourceType: "TaskRevision", resourceId: "task-1", revision: 3, contentHash: hash("a"), receiptId: "receipt-1" };
const sharedContext = { schemaVersion: "aos.ecommerce-workshop.shared-context/v1", tenant: { orgId: "org-org", projectId: "dev-project" }, context: { contextId: sharedToken, status: "ready", sourceModuleId: "ecommerce.task-cockpit", sourceViewId: "task", sourceRoute: "/workshop/task-cockpit", primaryRef: sharedRef, relatedRefs: [], purpose: "review", permissionDecisionRef: { ...sharedRef, resourceId: "permission-1" }, disclosurePolicyRef: { ...sharedRef, resourceId: "policy-1" }, markings: ["public"], disclosure: "allowed", evaluatedAt: "2026-08-24T08:00:00Z", dataCutoff: "2026-08-24T08:00:00Z", expiresAt: "2026-08-24T09:00:00Z", freshness: "fresh", readiness: "ready", filterSummary: null, lineageRefs: [], blockers: [] }, timeline: [{ eventKey: "event-1", eventType: "task", sourceRef: sharedRef, authoritySequence: 1, occurredAt: "2026-08-24T08:00:00Z", recordedAt: "2026-08-24T08:00:00Z", actorKind: "system", safeSummary: "任务已接受", status: "accepted", reasonCode: null, causationRef: null, correlationRef: null, attempt: null, receiptRef: null, originalRefs: [], late: false, duplicate: false, superseded: false, unknown: false, reconciled: false, stale: false }], navigationTargets: [{ targetId: "target_abcdefghijklmnop", status: "available", moduleId: "ecommerce.customer", viewId: "customer", route: "/workshop/customer", subjectRef: sharedRef, filterSummary: "同一任务", focusAnchor: null, scrollAnchor: null, blockers: [] }], page: { limit: 100, count: 1, hasMore: false, nextCursor: null } };

describe("shared context strict parser", () => {
  it("保留 exact context、稳定 timeline 与服务端 resolved target", () => expect(parseWorkshopSharedContext(sharedContext, sharedToken)).toMatchObject({ context: { status: "ready", purpose: "review" }, timeline: [{ eventKey: "event-1" }], navigationTargets: [{ route: "/workshop/customer" }] }));
  it("拒绝 token、extra、伪 ready、顺序与 non-ready disclosure 漂移", () => {
    expect(() => parseWorkshopSharedContext(sharedContext, "bad")).toThrow("token");
    expect(() => parseWorkshopSharedContext({ ...sharedContext, extra: true }, sharedToken)).toThrow("字段漂移");
    expect(() => parseWorkshopSharedContext({ ...sharedContext, context: { ...sharedContext.context, permissionDecisionRef: null } }, sharedToken)).toThrow("伪 ready");
    expect(() => parseWorkshopSharedContext({ ...sharedContext, timeline: [{ ...sharedContext.timeline[0], eventKey: "z", authoritySequence: 2 }, sharedContext.timeline[0]], page: { ...sharedContext.page, count: 2 } }, sharedToken)).toThrow("order");
    expect(() => parseWorkshopSharedContext({ ...sharedContext, context: { ...sharedContext.context, status: "forbidden", blockers: [{ code: "CONTEXT_FORBIDDEN", dependency: "permission", requiredAction: "reauthorize" }] } }, sharedToken)).toThrow("泄露");
  });
});

const operationSliceIds = ["orders", "orderLines", "inventory", "shipments", "payments", "aftersaleEvents", "operationCases"];
const operationSlice = (sliceId: string, status = "ready") => ({ sliceId, status, dataCutoff: "2026-08-24T08:00:00Z", authorityRefs: status === "ready" ? [{ resourceType: "ReadAuthority", resourceId: `${sliceId}.v1`, revision: 1, contentHash: hash("d"), receiptId: "receipt-1" }] : [], blockers: status === "blocked" ? [{ code: "DEPENDENCY_NOT_READY", dependency: `ecommerce.${sliceId}`, requiredAction: "接入 exact authority" }] : [], countLedger: { sourceTotal: status === "ready" ? 1 : 0, attached: status === "ready" ? 1 : 0, unmatched: 0, conflicted: 0 } });
const operations = { schemaVersion: "aos.ecommerce-workshop.operations-view/v1", tenant: { orgId: "org-org", projectId: "dev-project" }, evaluatedAt: "2026-08-24T08:00:00Z", dataCutoff: "2026-08-24T08:00:00Z", readiness: "degraded", slices: operationSliceIds.map((id) => operationSlice(id)), page: { limit: 50, count: 7, hasMore: false, nextCursor: null } };
const commandIds = ["classify", "createCase", "changeMembership", "manageSla", "automationKill", "refund"] as const;
const commandReadiness = { schemaVersion: "aos.ecommerce-workshop.operation-command-readiness/v1", tenant: { orgId: "org-org", projectId: "dev-project" }, evaluatedAt: "2026-08-24T08:00:00Z", commands: commandIds.map((commandId, index) => ({ commandId, label: `命令${index + 1}`, status: "blocked", risk: index > 3 ? "high" : "controlled", sideEffect: index === 5 ? "external" : "internalAuthority", blockers: [{ code: index === 5 ? "EXTERNAL_ACTION_GATE_NOT_BOUND" : "OPERATION_COMMAND_HANDLER_NOT_BOUND", dependency: "W3-12B2", requiredAction: "完成 exact command gate" }] })) };

describe("operation command readiness strict parser", () => {
  it("接受 canonical blocked 命令并拒绝 false-ready、顺序、extra 与 tenant 漂移", () => {
    expect(parseOperationCommandReadiness(commandReadiness).commands).toHaveLength(6);
    expect(() => parseOperationCommandReadiness({ ...commandReadiness, extra: true })).toThrow("字段漂移");
    expect(() => parseOperationCommandReadiness({ ...commandReadiness, commands: [...commandReadiness.commands].reverse() })).toThrow("canonical order");
    expect(() => parseOperationCommandReadiness({ ...commandReadiness, commands: [{ ...commandReadiness.commands[0], status: "ready" }, ...commandReadiness.commands.slice(1)] })).toThrow("伪 ready");
    expect(() => parseOperationCommandReadiness({ ...commandReadiness, tenant: { orgId: "dev-org", projectId: "dev-project" } }, { orgId: "org-org", projectId: "dev-project" })).toThrow("tenant 漂移");
  });
});

const commandObservation = {
  schemaVersion: "aos.ecommerce-workshop.operation-command-observation/v1",
  tenant: { orgId: "org-org", projectId: "dev-project" },
  proposalId: "proposal-1",
  leaseId: "lease-1",
  commandId: "classify",
  status: "applied",
  proposalHash: "a".repeat(64),
  receiptId: "receipt-1",
  requestFingerprint: "b".repeat(64),
  operationReceiptId: "operation-receipt-1",
  replayAllowed: false,
};

describe("operation command observation strict parser", () => {
  it("保留 exact proposal/lease/receipt 证据并固定禁止 replay", () => {
    expect(parseOperationCommandObservation(commandObservation, commandObservation.tenant, "proposal-1", "lease-1")).toMatchObject({ status: "applied", replayAllowed: false });
    expect(parseOperationCommandObservation({ ...commandObservation, status: "unknown", receiptId: null, requestFingerprint: null, operationReceiptId: null }).status).toBe("unknown");
  });
  it("拒绝 extra、未知状态、坏 hash、伪 replay、tenant 与 path ref 漂移", () => {
    expect(() => parseOperationCommandObservation({ ...commandObservation, extra: true })).toThrow("字段漂移");
    expect(() => parseOperationCommandObservation({ ...commandObservation, status: "future" })).toThrow("未知枚举");
    expect(() => parseOperationCommandObservation({ ...commandObservation, proposalHash: "bad" })).toThrow("SHA-256");
    expect(() => parseOperationCommandObservation({ ...commandObservation, replayAllowed: true })).toThrow("replay");
    expect(() => parseOperationCommandObservation(commandObservation, { orgId: "dev-org", projectId: "dev-project" })).toThrow("tenant 漂移");
    expect(() => parseOperationCommandObservation(commandObservation, commandObservation.tenant, "proposal-2", "lease-1")).toThrow("proposalId 漂移");
    expect(() => parseOperationCommandObservation(commandObservation, commandObservation.tenant, "proposal-1", "lease-2")).toThrow("leaseId 漂移");
  });
});

describe("operations view strict parser", () => {
  it("保留 ordered 七切片、exact authority 与数量守恒", () => {
    const parsed = parseOperationsView(operations);
    expect(parsed).toMatchObject({ page: { count: 7 } });
    expect(parsed.slices).toHaveLength(7);
    expect(parsed.slices[0]).toMatchObject({ sliceId: "orders", status: "ready" });
  });
  it("拒绝 extra、错序、伪 ready、count 和 tenant 漂移", () => {
    expect(() => parseOperationsView({ ...operations, extra: true })).toThrow("字段漂移");
    expect(() => parseOperationsView({ ...operations, slices: [...operations.slices].reverse() })).toThrow("canonical order");
    expect(() => parseOperationsView({ ...operations, slices: [{ ...operations.slices[0], authorityRefs: [] }, ...operations.slices.slice(1)] })).toThrow("伪 ready");
    expect(() => parseOperationsView({ ...operations, page: { ...operations.page, count: 6 } })).toThrow("count");
    expect(() => parseOperationsView({ ...operations, page: { ...operations.page, hasMore: true, nextCursor: "synthetic" } })).toThrow("cursor");
    expect(() => parseOperationsView({ ...operations, tenant: { orgId: "dev-org", projectId: "dev-project" } }, { orgId: "org-org", projectId: "dev-project" })).toThrow("tenant 漂移");
  });
});

const campaignCutoff = "2026-08-24T13:00:00Z";
const campaignRef = (resourceType: string, resourceId: string, value = "e") => ({ resourceType, resourceId, revision: 1, contentHash: hash(value), receiptId: `receipt-${resourceId}` });
const contentVariant = { ...campaignRef("ContentVariant", "variant-1", "f"), intentRef: campaignRef("MasterContentIntentRevision", "intent-1"), masterArtifactRef: { artifactId: "master-1", contentHash: hash("a") }, variantArtifactRef: { artifactId: "variant-1", contentHash: hash("f") }, relationId: "relation-1", relationType: "variant_of" };
const campaignSlices = [
  { sliceId: "plan", status: "ready", dataCutoff: campaignCutoff, authorityRefs: [campaignRef("CampaignRevision", "campaign-1")], items: [campaignRef("CampaignRevision", "campaign-1")], blockers: [], countLedger: { eligible: 1, attached: 1, unmatched: 0, conflicted: 0 } },
  { sliceId: "calendar", status: "ready", dataCutoff: campaignCutoff, authorityRefs: [], items: [], blockers: [], countLedger: { eligible: 0, attached: 0, unmatched: 0, conflicted: 0 } },
  { sliceId: "content", status: "ready", dataCutoff: campaignCutoff, authorityRefs: [campaignRef("MasterContentIntentRevision", "intent-1")], items: [campaignRef("MasterContentIntentRevision", "intent-1"), contentVariant], blockers: [], countLedger: { eligible: 2, attached: 2, unmatched: 0, conflicted: 0 } },
];
const contentCampaign = { schemaVersion: "aos.ecommerce-workshop.content-campaign-view/v1", tenant: { orgId: "org-org", projectId: "dev-project" }, evaluatedAt: campaignCutoff, dataCutoff: campaignCutoff, readiness: "degraded", slices: campaignSlices, page: { limit: 100, count: 3, hasMore: false, nextCursor: null } };
describe("content campaign strict parser", () => {
  it("保留 canonical 三切片、可信空与 ContentVariant exact lineage", () => { const parsed = parseContentCampaignView(contentCampaign); expect(parsed.slices.map((item) => item.sliceId)).toEqual(["plan", "calendar", "content"]); expect(parsed.slices[1]).toMatchObject({ status: "ready", items: [], countLedger: { eligible: 0 } }); expect(parsed.slices[2].items[1]).toMatchObject({ resourceType: "ContentVariant", relationType: "variant_of" }); });
  it("拒绝 extra、错序、伪 ready、重复 identity、数量、lineage、cursor 与 tenant 漂移", () => { expect(() => parseContentCampaignView({ ...contentCampaign, extra: true })).toThrow("字段漂移"); expect(() => parseContentCampaignView({ ...contentCampaign, slices: [...campaignSlices].reverse() })).toThrow("canonical order"); expect(() => parseContentCampaignView({ ...contentCampaign, slices: [{ ...campaignSlices[0], authorityRefs: [] }, ...campaignSlices.slice(1)] })).toThrow("伪 ready"); expect(() => parseContentCampaignView({ ...contentCampaign, slices: [{ ...campaignSlices[0], authorityRefs: [campaignSlices[0].authorityRefs[0], campaignSlices[0].authorityRefs[0]] }, ...campaignSlices.slice(1)] })).toThrow("identity 重复"); expect(() => parseContentCampaignView({ ...contentCampaign, page: { ...contentCampaign.page, count: 2 } })).toThrow("count"); const badVariant = { ...contentVariant, resourceId: "other" }; expect(() => parseContentCampaignView({ ...contentCampaign, slices: [...campaignSlices.slice(0, 2), { ...campaignSlices[2], items: [campaignSlices[2].items[0], badVariant] }] })).toThrow("lineage"); expect(() => parseContentCampaignView({ ...contentCampaign, page: { ...contentCampaign.page, hasMore: true, nextCursor: "x" } })).toThrow("cursor"); expect(() => parseContentCampaignView(contentCampaign, { orgId: "dev-org", projectId: "dev-project" })).toThrow("tenant 漂移"); });
});

const sourcePipelines = ["P01-shop-qyh", "P02-product-qyh", "P03-product-sku-qyh", "P04-category-qyh", "P05-order-qyh", "P06-order-line-qyh", "P07-shipment-qyh", "P08-customer-lite-qyh", "P09-weapp-qyh", "P10-system-config-qyh", "P11-product-review-qyh", "P12-payment-qyh"];
const sourceCheckedAt = "2026-08-21T14:00:00Z";
const sourceBlockers = ["FRESHNESS_POLICY_REF_MISSING", "QUALITY_POLICY_REF_MISSING", "QUERY_CAPABILITY_REF_MISSING", "RECONCILIATION_POLICY_REF_MISSING", "SOURCE_CONFIG_EXACT_REF_MISSING"];
const sourceItem = (pipelineId: string, status = "blocked") => ({
  schemaVersion: "aos.source-readiness/v1", tenant: { orgId: "org-org", projectId: "dev-project" }, sourceId: "niushop-qyh", pipelineId, objectType: "Object", status, checkedAt: sourceCheckedAt,
  observedAt: sourceCheckedAt, sourceEventAt: null, projectedAt: sourceCheckedAt, dataCutoff: sourceCheckedAt, freshnessExpiresAt: null,
  sourceConfigRef: null, mappingRef: null, schemaRef: null, maskingPolicyRef: null, freshnessPolicyRef: null, qualityPolicyRef: null, reconciliationPolicyRef: null, queryCapabilityRef: null,
  latestRun: { runId: "run-1", status: "succeeded", scheduledFor: sourceCheckedAt, startedAt: sourceCheckedAt, finishedAt: sourceCheckedAt, rowsWritten: 1, errorCode: null },
  counts: { sourceTotal: 1, sourceActive: 1, sourceDeleted: 0, projectionTotal: 1, unexplainedDelta: 0 },
  quality: { status: "unknown", ruleRef: null, summary: null }, reconciliation: { status: "unknown", ruleRef: null, summary: null }, reasons: sourceBlockers, blockers: sourceBlockers,
});
const sourceEnvelope = (status = "blocked") => ({ schemaVersion: "aos.source-readiness/v1", tenant: { orgId: "org-org", projectId: "dev-project" }, checkedAt: sourceCheckedAt, cutoffAt: sourceCheckedAt, status, sources: sourcePipelines.map((pipelineId) => sourceItem(pipelineId, status)), receiptRef: null });

describe("source readiness strict parser", () => {
  it.each(["blocked", "unknown", "empty", "forbidden"])("诚实保留 %s 与 ordered P01-P12", (status) => {
    const parsed = parseSourceReadinessEnvelope(sourceEnvelope(status));
    expect(parsed.status).toBe(status);
    expect(parsed.sources).toHaveLength(12);
    expect(parsed.sources[0].pipelineId).toBe("P01-shop-qyh");
  });
  it("只在 exact authority 与 policy/run/freshness 全部闭合时接受 ready", () => {
    const exactRef = { resourceType: "Policy", resourceId: "policy-1", revision: "1", contentHash: "a".repeat(64), authority: "Data" };
    const base = sourceEnvelope("ready");
    const ready = { ...base, sources: base.sources.map((item) => ({ ...item, freshnessExpiresAt: "2026-08-22T14:00:00Z", sourceConfigRef: exactRef, mappingRef: exactRef, schemaRef: exactRef, maskingPolicyRef: exactRef, freshnessPolicyRef: exactRef, qualityPolicyRef: exactRef, reconciliationPolicyRef: exactRef, queryCapabilityRef: exactRef, quality: { status: "pass", ruleRef: exactRef, summary: "pass" }, reconciliation: { status: "pass", ruleRef: exactRef, summary: "pass" }, reasons: [], blockers: [] })) };
    expect(parseSourceReadinessEnvelope(ready).status).toBe("ready");
  });
  it("拒绝字段、枚举、顺序、tenant、checkedAt 与 aggregate 漂移", () => {
    expect(() => parseSourceReadinessEnvelope({ ...sourceEnvelope(), extra: true })).toThrow("字段漂移");
    expect(() => parseSourceReadinessEnvelope({ ...sourceEnvelope(), status: "future" })).toThrow("未知枚举");
    const reversed = sourceEnvelope(); reversed.sources = [...reversed.sources].reverse();
    expect(() => parseSourceReadinessEnvelope(reversed)).toThrow("ordered P01-P12");
    const tenantDrift = sourceEnvelope(); tenantDrift.sources[0] = { ...tenantDrift.sources[0], tenant: { orgId: "dev-org", projectId: "dev-project" } };
    expect(() => parseSourceReadinessEnvelope(tenantDrift)).toThrow("tenant 漂移");
    const checkedAtDrift = sourceEnvelope(); checkedAtDrift.sources[0] = { ...checkedAtDrift.sources[0], checkedAt: "2026-08-21T14:00:01Z" };
    expect(() => parseSourceReadinessEnvelope(checkedAtDrift)).toThrow("checkedAt 漂移");
    expect(() => parseSourceReadinessEnvelope({ ...sourceEnvelope(), status: "empty" })).toThrow("aggregate status 漂移");
  });
  it("拒绝伪 ready、坏 exact ref hash 与非排序 blocker", () => {
    expect(() => parseSourceReadinessEnvelope(sourceEnvelope("ready"))).toThrow("伪 ready");
    expect(() => parseSourceReadinessEnvelope({ ...sourceEnvelope(), receiptRef: { resourceType: "Receipt", resourceId: "receipt-1", revision: "1", contentHash: "bad", authority: "Data" } })).toThrow("SHA-256");
    const unsorted = sourceEnvelope(); unsorted.sources[0] = { ...unsorted.sources[0], blockers: [...sourceBlockers].reverse() };
    expect(() => parseSourceReadinessEnvelope(unsorted)).toThrow("唯一且排序");
  });
});

const cockpitBase = { schemaVersion: "aos.ecommerce-workshop.task-cockpit/v1", tenant: { orgId: "org-org", projectId: "dev-project" }, evaluatedAt: "2026-08-15T10:00:00Z", stateConsistency: "current_state_per_page" };
const page = { limit: 20, count: 1, hasMore: false, nextCursor: null };
const run = { runId: "run-1", planRevisionId: "plan-1", status: "running", version: 1, startedAt: null, finishedAt: null, createdAt: "2026-08-15T09:00:00Z", updatedAt: "2026-08-15T09:01:00Z" };
const task = { taskId: "task-1", taskType: "daily", title: "每日巡检", status: "executing", priority: 50, version: 1, currentPlanRevisionId: "plan-1", createdAt: "2026-08-15T08:00:00Z", updatedAt: "2026-08-15T09:01:00Z", run };
const cockpitCore = { ...cockpitBase, taskCutoff: "2026-08-15T10:00:00Z", readiness: "degraded", blockers: [
  { code: "TASK_COCKPIT_STAGE_MAPPING_RUN_SCOPED", severity: "warning", dependency: "stage", requiredAction: "按 Run 展开" },
  { code: "TASK_COCKPIT_BUSINESS_CONTEXT_INDEPENDENT_SNAPSHOT", severity: "warning", dependency: "business-context:ecommerce.source-readiness", requiredAction: "按独立 cutoff 展示" },
], items: [task], page };
const step = { stepRunId: "step-1", stepKey: "collect", attempt: 1, status: "running", tokenCount: 12, costAmount: "0.0100", hasInputRefs: true, hasOutputRefs: false, hasError: false, createdAt: "2026-08-15T09:00:00Z", updatedAt: "2026-08-15T09:01:00Z" };
const checkpoint = { checkpointId: "checkpoint-1", sequence: 1, schemaVersion: 1, stepKey: "collect", stateHash: "state-1", artifactCount: 0, createdAt: "2026-08-15T09:02:00Z" };
const steps = { ...cockpitBase, runId: "run-1", membershipCutoff: "2026-08-15T10:00:00Z", items: [step], page };
const checkpoints = { ...cockpitBase, runId: "run-1", membershipCutoff: "2026-08-15T10:00:00Z", items: [checkpoint], page };
const rawHash = "a".repeat(64);
const productionContext = { schemaVersion: cockpitBase.schemaVersion, tenant: cockpitBase.tenant, runId: "run-1", taskId: "task-1", evaluatedAt: cockpitBase.evaluatedAt, planRef: { resourceType: "PlanRevision", resourceId: "plan-1", revision: 2, contentHash: rawHash }, stageTemplateRef: { resourceType: "StageTemplateRevision", resourceId: "template-1", revision: 1, contentHash: rawHash }, responsibilityPlanRef: { resourceType: "ResponsibilityPlanRevision", resourceId: "responsibility-1", revision: 1, contentHash: rawHash }, compilerVersion: "w2c.v1", stages: [{ stageId: "collect", title: "采集", dependsOn: [], requiredSlotIds: ["collector"], applicabilityResult: "applicable", evaluatedProfile: "standard" }], applicableStageIds: ["collect"], notApplicableStageIds: [] };
const responsibilityHandoffs = { schemaVersion: cockpitBase.schemaVersion, tenant: cockpitBase.tenant, runId: "run-1", taskId: "task-1", evaluatedAt: cockpitBase.evaluatedAt, responsibilityPlanRef: productionContext.responsibilityPlanRef, profile: "standard", lifecycle: "frozen", compilationReadiness: "ready_at_compile", compiledRequiredSlotIds: ["collector"], slots: [{ slotId: "collector", responsibilityType: "collection", requiredCapabilityIds: ["ecommerce.collect"], returnStage: "collect", assignee: { kind: "agent_instance", resourceId: "agent-collector", version: 2, operationalReadiness: "unverified", resolutionReceipts: [] } }], handoffs: [{ handoffId: "handoff-1", status: "consumed", version: 2, senderInstanceRef: { resourceType: "AgentInstance", resourceId: "agent-collector", revision: 2, contentHash: rawHash }, receiverInstanceRef: { resourceType: "AgentInstance", resourceId: "agent-review", revision: 1, contentHash: rawHash }, expiresAt: "2026-08-15T11:00:00Z", consumedAt: "2026-08-15T10:30:00Z", createdAt: "2026-08-15T10:00:00Z", decisions: [{ decisionId: "decision-1", revision: 1, decision: "accepted", reasonCode: null, gapCodes: [], contentHash: rawHash, createdAt: "2026-08-15T10:30:00Z" }] }] };
const proposalRef = { resourceType: "ActionProposalRevision", resourceId: "proposal-1", revision: 1, contentHash: rawHash };
const approvalReview = { schemaVersion: cockpitBase.schemaVersion, tenant: cockpitBase.tenant, runId: "run-1", taskId: "task-1", evaluatedAt: cockpitBase.evaluatedAt, planApproval: { planRef: productionContext.planRef, approvalStatus: "approved", approvedBy: "reviewer-1", approvedAt: "2026-08-15T08:50:00Z", navigation: { routeIdentity: "aip.task-plan", routePath: "/aip/studio?taskId=task-1&runId=run-1", targetRef: productionContext.planRef, commandReadiness: "read_only_fact", requiredPermission: "aip.plan.read", blockerCodes: ["NO_APPROVAL_COMMAND"], returnFocusToken: rawHash } }, actionApprovals: [{ proposalRef, actionTypeId: "ecommerce.case.classify", status: "approved", expiresAt: "2026-08-15T11:00:00Z", decisions: [{ approvalEventId: "approval-1", proposalVersion: 1, proposalHash: rawHash, decision: "approved", actorId: "reviewer-1", expiresAt: "2026-08-15T11:00:00Z", createdAt: "2026-08-15T09:10:00Z" }], navigation: { routeIdentity: "aip.action-drafts", routePath: "/aip/drafts?taskId=task-1&runId=run-1&proposalId=proposal-1", targetRef: proposalRef, commandReadiness: "destination_reauthorization_required", requiredPermission: "aip.action.approval.decide", blockerCodes: ["DESTINATION_REAUTHORIZATION_REQUIRED"], returnFocusToken: rawHash } }], reviewIssues: [{ issueId: "issue-1", version: 1, status: "open", severity: "warning", ruleRef: { resourceType: "EvalRuleRevision", resourceId: "rule-1", revision: 1, contentHash: rawHash }, artifactId: "artifact-1", artifactHash: rawHash, evalReportRef: { resourceType: "EvalReportRevision", resourceId: "report-1", revision: 1, contentHash: rawHash }, returnStage: "collect", evidenceCount: 0, lineageReadiness: "attempt_unresolved", returnLineage: null, events: [{ eventId: "issue-event-1", sequence: 1, eventType: "opened", issueVersion: 1, payloadHash: rawHash, actor: "reviewer-1", createdAt: "2026-08-15T09:20:00Z" }] }], actionApprovalCount: 1, reviewIssueCount: 1, unresolvedAttemptCount: 1 };
const initialActionReceipt = { receiptId: "receipt-1", receiptKind: "initial", status: "unknown", leaseId: "lease-1", requestFingerprint: rawHash, providerRequestPresent: true, evidenceCount: 0, supersedesReceiptId: null, resolvedStatus: null, createdAt: "2026-08-15T09:30:00Z" };
const actionReceipts = { schemaVersion: cockpitBase.schemaVersion, tenant: cockpitBase.tenant, runId: "run-1", taskId: "task-1", evaluatedAt: cockpitBase.evaluatedAt, executions: [{ proposalRef, actionTypeId: "ecommerce.case.classify", proposalStatus: "unknown", leaseId: "lease-1", attempt: 1, receipts: [initialActionReceipt], reconciliationState: "required" }], proposalCount: 1, receiptCount: 1, unknownReceiptCount: 1, reconcileRequiredCount: 1, reconciledReceiptCount: 0 };

describe("task cockpit strict parser", () => {
  it("保留 Task/Run/Step/Checkpoint、decimal 与 current-state 语义", () => {
    expect(parseTaskCockpitCore(cockpitCore)).toMatchObject({ readiness: "degraded", items: [{ run: { runId: "run-1" } }] });
    expect(parseTaskCockpitSteps(steps).items[0]).toMatchObject({ costAmount: "0.0100", hasInputRefs: true });
    expect(parseTaskCockpitCheckpoints(checkpoints).items[0]).toMatchObject({ checkpointId: "checkpoint-1", artifactCount: 0 });
    expect(parseTaskCockpitProductionContext(productionContext)).toMatchObject({ compilerVersion: "w2c.v1", stages: [{ stageId: "collect", applicabilityResult: "applicable" }] });
    expect(parseTaskCockpitResponsibilityHandoffs(responsibilityHandoffs)).toMatchObject({ profile: "standard", slots: [{ assignee: { operationalReadiness: "unverified" } }], handoffs: [{ status: "consumed", decisions: [{ revision: 1 }] }] });
    expect(parseTaskCockpitApprovalReview(approvalReview)).toMatchObject({ planApproval: { approvalStatus: "approved" }, actionApprovals: [{ status: "approved" }], reviewIssues: [{ lineageReadiness: "attempt_unresolved" }] });
    expect(parseTaskCockpitActionReceipts(actionReceipts)).toMatchObject({ executions: [{ proposalStatus: "unknown", reconciliationState: "required", receipts: [{ providerRequestPresent: true }] }], reconcileRequiredCount: 1 });
  });
  it("按 exact slot subject 保留 assignee resolution 观测且不升级为当前 ready", () => {
    const resolution = { receiptId: "receipt-resolution-1", subjectId: "responsibility-plan:responsibility-1@1/slot:collector", kind: "agent_instance", resourceId: "agent-collector", version: 2, status: "resolved", blockerCodes: [], contentHash: rawHash, createdAt: "2026-08-15T09:40:00Z" };
    const payload = { ...responsibilityHandoffs, slots: [{ ...responsibilityHandoffs.slots[0], assignee: { ...responsibilityHandoffs.slots[0].assignee, operationalReadiness: "resolved_at_observation", resolutionReceipts: [resolution] } }] };
    expect(parseTaskCockpitResponsibilityHandoffs(payload).slots[0].assignee).toMatchObject({ operationalReadiness: "resolved_at_observation", resolutionReceipts: [{ receiptId: "receipt-resolution-1" }] });
    expect(() => parseTaskCockpitResponsibilityHandoffs({ ...payload, slots: [{ ...payload.slots[0], assignee: { ...payload.slots[0].assignee, resolutionReceipts: [{ ...resolution, subjectId: "responsibility-plan:other@1/slot:collector" }] } }] })).toThrow("exact ref 漂移");
  });
  it("拒绝 extra、未知状态、坏 decimal、重复 identity 和 count/cursor 漂移", () => {
    expect(() => parseTaskCockpitCore({ ...cockpitCore, extra: true })).toThrow("字段漂移");
    expect(() => parseTaskCockpitCore({ ...cockpitCore, items: [{ ...task, status: "future" }] })).toThrow("未知枚举");
    expect(() => parseTaskCockpitSteps({ ...steps, items: [{ ...step, costAmount: "NaN" }] })).toThrow("decimal");
    expect(() => parseTaskCockpitSteps({ ...steps, items: [step, step], page: { ...page, count: 2 } })).toThrow("identity");
    expect(() => parseTaskCockpitCheckpoints({ ...checkpoints, page: { ...page, hasMore: true } })).toThrow("cursor");
    expect(() => parseTaskCockpitCore({ ...cockpitCore, blockers: [] })).toThrow("数量");
    expect(() => parseTaskCockpitProductionContext({ ...productionContext, stageTemplateRef: { ...productionContext.stageTemplateRef, resourceType: "BundleRevision" } })).toThrow("resourceType 漂移");
    expect(() => parseTaskCockpitProductionContext({ ...productionContext, applicableStageIds: [], notApplicableStageIds: [] })).toThrow("partition 漂移");
    expect(() => parseTaskCockpitResponsibilityHandoffs({ ...responsibilityHandoffs, slots: [{ ...responsibilityHandoffs.slots[0], assignee: { ...responsibilityHandoffs.slots[0].assignee, operationalReadiness: "available" } }] })).toThrow("未知枚举");
    expect(() => parseTaskCockpitResponsibilityHandoffs({ ...responsibilityHandoffs, handoffs: [{ ...responsibilityHandoffs.handoffs[0], decisions: [{ ...responsibilityHandoffs.handoffs[0].decisions[0], revision: 2 }] }] })).toThrow("timeline 漂移");
    expect(() => parseTaskCockpitResponsibilityHandoffs({ ...responsibilityHandoffs, compiledRequiredSlotIds: ["reviewer"] })).toThrow("覆盖");
    expect(() => parseTaskCockpitResponsibilityHandoffs({ ...responsibilityHandoffs, responsibilityPlanRef: { ...responsibilityHandoffs.responsibilityPlanRef, contentHash: "bad" } })).toThrow("SHA-256");
    expect(() => parseTaskCockpitApprovalReview({ ...approvalReview, actionApprovals: [{ ...approvalReview.actionApprovals[0], decisions: [{ ...approvalReview.actionApprovals[0].decisions[0], proposalHash: "b".repeat(64) }] }] })).toThrow("decision exact ref 漂移");
    expect(() => parseTaskCockpitApprovalReview({ ...approvalReview, reviewIssues: [{ ...approvalReview.reviewIssues[0], events: [{ ...approvalReview.reviewIssues[0].events[0], sequence: 2 }] }] })).toThrow("event timeline 漂移");
    expect(() => parseTaskCockpitApprovalReview({ ...approvalReview, reviewIssues: [{ ...approvalReview.reviewIssues[0], status: "returned" }] })).toThrow("attempt lineage 漂移");
    expect(() => parseTaskCockpitApprovalReview({ ...approvalReview, reviewIssueCount: 2 })).toThrow("count ledger 漂移");
    expect(() => parseTaskCockpitActionReceipts({ ...actionReceipts, receiptCount: 2 })).toThrow("count ledger 漂移");
    expect(() => parseTaskCockpitActionReceipts({ ...actionReceipts, executions: [{ ...actionReceipts.executions[0], receipts: [initialActionReceipt, { ...initialActionReceipt, receiptId: "receipt-2", receiptKind: "reconcile", status: "reconciled", requestFingerprint: "b".repeat(64), supersedesReceiptId: "receipt-1", resolvedStatus: "applied" }], reconciliationState: "resolved" }], receiptCount: 2, reconciledReceiptCount: 1, reconcileRequiredCount: 0 })).toThrow("receipt chain 漂移");
    expect(() => parseTaskCockpitActionReceipts({ ...actionReceipts, executions: [{ ...actionReceipts.executions[0], receipts: [{ ...initialActionReceipt, providerId: "provider-secret" }] }] })).toThrow("字段漂移");
  });
  it("只把 canonical 200 空页识别为空", () => {
    expect(parseTaskCockpitSteps({ ...steps, items: [], page: { limit: 20, count: 0, hasMore: false, nextCursor: null } }).items).toEqual([]);
  });
});
