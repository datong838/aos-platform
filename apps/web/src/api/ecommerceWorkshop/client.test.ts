import { describe, expect, it, vi } from "vitest";
import { EcommerceWorkshopClient, EcommerceWorkshopClientError } from "./client";

const hash = (value: string) => `sha256:${value.repeat(64)}`;
const module = { moduleId: "ecommerce.operations", displayName: "统一运营驾驶舱", menuLabel: "统一运营驾驶舱", route: "/workshop/operations", slot: "workshop.primary.ecommerce", order: 30, installationRef: { installationId: "11111111-1111-4111-8111-111111111111", revision: 5, compositionId: "22222222-2222-4222-8222-222222222222", lockRevision: 1, lockHash: hash("a"), overlayRevision: "overlay-5" }, moduleRef: { publisher: "aos", bundleId: "solution.ecommerce.operations-base", version: "1.1.0", bundleContentHash: hash("b"), moduleArtifactRef: "bundle://catalog/solutions/ecommerce-operations-base/content/workshops/ecommerce.operations.json", moduleArtifactHash: hash("c") }, readiness: "unknown", blockers: [{ dependencyType: "object", dependencyId: "Order", state: "unknown", reasonCode: "OBJECT_READINESS_UNVERIFIED", recoverable: true, requiredAction: "接入 reader", ref: null }], permissions: { roles: [], markings: [], dataScopes: ["ecommerce.workshop.read"], actionTypes: [] }, requiredObjects: ["Order"], requiredCapabilities: [], requiredAipFeatures: [], viewRefs: [], evalPackRefs: [], productionContractRefs: [], responsibilityTemplateRefs: [], impactCalculatorRefs: [], legacyAssetRefs: [], legacyRoutes: [], minimumRuntimeVersion: "1.7.0", lastReceiptRef: null };
const envelope = { schemaVersion: "aos.ecommerce-workshop/v1", tenant: { orgId: "org-org", projectId: "dev-project" }, evaluatedAt: "2026-08-14T00:00:00Z", dataCutoff: null };
const ok = (payload: unknown) => new Response(JSON.stringify(payload), { status: 200, headers: { "Content-Type": "application/json" } });
const cockpitBase = { schemaVersion: "aos.ecommerce-workshop.task-cockpit/v1", tenant: { orgId: "org-org", projectId: "dev-project" }, evaluatedAt: "2026-08-15T10:00:00Z", stateConsistency: "current_state_per_page" };
const emptyPage = { limit: 20, count: 0, hasMore: false, nextCursor: null };
const blockers = [
  { code: "TASK_COCKPIT_STAGE_MAPPING_RUN_SCOPED", severity: "warning", dependency: "stage", requiredAction: "按 Run 展开" },
  { code: "TASK_COCKPIT_BUSINESS_CONTEXT_BLOCKED", severity: "blocking", dependency: "business", requiredAction: "等待 W2-00" },
];
const core = { ...cockpitBase, taskCutoff: "2026-08-15T10:00:00Z", readiness: "degraded", blockers, items: [], page: emptyPage };
const details = { ...cockpitBase, runId: "run-1", membershipCutoff: "2026-08-15T10:00:00Z", items: [], page: emptyPage };
const productionContext = { schemaVersion: cockpitBase.schemaVersion, tenant: cockpitBase.tenant, runId: "run:1", taskId: "task-1", evaluatedAt: cockpitBase.evaluatedAt, planRef: { resourceType: "PlanRevision", resourceId: "plan-1", revision: 2, contentHash: "a".repeat(64) }, stageTemplateRef: { resourceType: "StageTemplateRevision", resourceId: "template-1", revision: 1, contentHash: "b".repeat(64) }, responsibilityPlanRef: { resourceType: "ResponsibilityPlanRevision", resourceId: "responsibility-1", revision: 1, contentHash: "c".repeat(64) }, compilerVersion: "w2c.v1", stages: [{ stageId: "collect", title: "采集", dependsOn: [], requiredSlotIds: ["collector"], applicabilityResult: "applicable", evaluatedProfile: "standard" }], applicableStageIds: ["collect"], notApplicableStageIds: [] };
const responsibilityHandoffs = { schemaVersion: cockpitBase.schemaVersion, tenant: cockpitBase.tenant, runId: "run:1", taskId: "task-1", evaluatedAt: cockpitBase.evaluatedAt, responsibilityPlanRef: productionContext.responsibilityPlanRef, profile: "standard", lifecycle: "frozen", compilationReadiness: "ready_at_compile", compiledRequiredSlotIds: ["collector"], slots: [{ slotId: "collector", responsibilityType: "collection", requiredCapabilityIds: ["ecommerce.collect"], returnStage: "collect", assignee: { kind: "agent_instance", resourceId: "agent-collector", version: 2, operationalReadiness: "unverified", resolutionReceipts: [] } }], handoffs: [{ handoffId: "handoff-1", status: "consumed", version: 2, senderInstanceRef: { resourceType: "AgentInstance", resourceId: "agent-collector", revision: 2, contentHash: "d".repeat(64) }, receiverInstanceRef: { resourceType: "AgentInstance", resourceId: "agent-review", revision: 1, contentHash: "e".repeat(64) }, expiresAt: "2026-08-15T11:00:00Z", consumedAt: "2026-08-15T10:30:00Z", createdAt: "2026-08-15T10:00:00Z", decisions: [{ decisionId: "decision-1", revision: 1, decision: "accepted", reasonCode: null, gapCodes: [], contentHash: "f".repeat(64), createdAt: "2026-08-15T10:30:00Z" }] }] };
const approvalHash = "a".repeat(64);
const actionProposalRef = { resourceType: "ActionProposalRevision", resourceId: "proposal-1", revision: 1, contentHash: approvalHash };
const approvalReview = { schemaVersion: cockpitBase.schemaVersion, tenant: cockpitBase.tenant, runId: "run:1", taskId: "task-1", evaluatedAt: cockpitBase.evaluatedAt, planApproval: { planRef: productionContext.planRef, approvalStatus: "approved", approvedBy: "reviewer-1", approvedAt: "2026-08-15T08:50:00Z", navigation: { routeIdentity: "aip.task-plan", routePath: "/aip/studio?taskId=task-1&runId=run%3A1", targetRef: productionContext.planRef, commandReadiness: "read_only_fact", requiredPermission: "aip.plan.read", blockerCodes: ["NO_APPROVAL_COMMAND"], returnFocusToken: approvalHash } }, actionApprovals: [{ proposalRef: actionProposalRef, actionTypeId: "ecommerce.case.classify", status: "approved", expiresAt: "2026-08-15T11:00:00Z", decisions: [{ approvalEventId: "approval-1", proposalVersion: 1, proposalHash: approvalHash, decision: "approved", actorId: "reviewer-1", expiresAt: null, createdAt: "2026-08-15T09:10:00Z" }], navigation: { routeIdentity: "aip.action-drafts", routePath: "/aip/drafts?taskId=task-1&runId=run%3A1&proposalId=proposal-1", targetRef: actionProposalRef, commandReadiness: "destination_reauthorization_required", requiredPermission: "aip.action.approval.decide", blockerCodes: ["DESTINATION_REAUTHORIZATION_REQUIRED"], returnFocusToken: approvalHash } }], reviewIssues: [], actionApprovalCount: 1, reviewIssueCount: 0, unresolvedAttemptCount: 0 };
const actionReceipts = { schemaVersion: cockpitBase.schemaVersion, tenant: cockpitBase.tenant, runId: "run:1", taskId: "task-1", evaluatedAt: cockpitBase.evaluatedAt, executions: [{ proposalRef: actionProposalRef, actionTypeId: "ecommerce.case.classify", proposalStatus: "unknown", leaseId: "lease-1", attempt: 1, receipts: [{ receiptId: "receipt-1", receiptKind: "initial", status: "unknown", leaseId: "lease-1", requestFingerprint: approvalHash, providerRequestPresent: true, evidenceCount: 0, supersedesReceiptId: null, resolvedStatus: null, createdAt: "2026-08-15T09:30:00Z" }], reconciliationState: "required" }], proposalCount: 1, receiptCount: 1, unknownReceiptCount: 1, reconcileRequiredCount: 1, reconciledReceiptCount: 0 };
const sourcePipelines = ["P01-shop-qyh", "P02-product-qyh", "P03-product-sku-qyh", "P04-category-qyh", "P05-order-qyh", "P06-order-line-qyh", "P07-shipment-qyh", "P08-customer-lite-qyh", "P09-weapp-qyh", "P10-system-config-qyh", "P11-product-review-qyh", "P12-payment-qyh"];
const sourceCheckedAt = "2026-08-21T14:00:00Z";
const sourceBlockers = ["FRESHNESS_POLICY_REF_MISSING", "QUALITY_POLICY_REF_MISSING", "QUERY_CAPABILITY_REF_MISSING", "RECONCILIATION_POLICY_REF_MISSING", "SOURCE_CONFIG_EXACT_REF_MISSING"];
const sourceReadiness = { schemaVersion: "aos.source-readiness/v1", tenant: { orgId: "org-org", projectId: "dev-project" }, checkedAt: sourceCheckedAt, cutoffAt: sourceCheckedAt, status: "blocked", receiptRef: null, sources: sourcePipelines.map((pipelineId) => ({ schemaVersion: "aos.source-readiness/v1", tenant: { orgId: "org-org", projectId: "dev-project" }, sourceId: "niushop-qyh", pipelineId, objectType: "Object", status: "blocked", checkedAt: sourceCheckedAt, observedAt: sourceCheckedAt, sourceEventAt: null, projectedAt: sourceCheckedAt, dataCutoff: sourceCheckedAt, freshnessExpiresAt: null, sourceConfigRef: null, mappingRef: null, schemaRef: null, maskingPolicyRef: null, freshnessPolicyRef: null, qualityPolicyRef: null, reconciliationPolicyRef: null, queryCapabilityRef: null, latestRun: { runId: "run-1", status: "succeeded", scheduledFor: sourceCheckedAt, startedAt: sourceCheckedAt, finishedAt: sourceCheckedAt, rowsWritten: 1, errorCode: null }, counts: { sourceTotal: 1, sourceActive: 1, sourceDeleted: 0, projectionTotal: 1, unexplainedDelta: 0 }, quality: { status: "unknown", ruleRef: null, summary: null }, reconciliation: { status: "unknown", ruleRef: null, summary: null }, reasons: sourceBlockers, blockers: sourceBlockers })) };
const operationIds = ["orders", "orderLines", "inventory", "shipments", "payments", "aftersaleEvents", "operationCases"];
const operations = { schemaVersion: "aos.ecommerce-workshop.operations-view/v1", tenant: envelope.tenant, evaluatedAt: "2026-08-24T08:00:00Z", dataCutoff: "2026-08-24T08:00:00Z", readiness: "degraded", slices: operationIds.map((sliceId) => ({ sliceId, status: "ready", dataCutoff: "2026-08-24T08:00:00Z", authorityRefs: [{ resourceType: "ReadAuthority", resourceId: sliceId, revision: 1, contentHash: hash("d"), receiptId: "receipt-1" }], blockers: [], countLedger: { sourceTotal: 0, attached: 0, unmatched: 0, conflicted: 0 } })), page: { limit: 50, count: 0, hasMore: false, nextCursor: null } };
const commandIds = ["classify", "createCase", "changeMembership", "manageSla", "automationKill", "refund"] as const;
const commandReadiness = { schemaVersion: "aos.ecommerce-workshop.operation-command-readiness/v1", tenant: envelope.tenant, evaluatedAt: "2026-08-24T08:00:00Z", commands: commandIds.map((commandId, index) => ({ commandId, label: `命令${index}`, status: "blocked", risk: index > 3 ? "high" : "controlled", sideEffect: index === 5 ? "external" : "internalAuthority", blockers: [{ code: "OPERATION_COMMAND_HANDLER_NOT_BOUND", dependency: "W3-12B2", requiredAction: "完成 exact command gate" }] })) };
const commandObservation = { schemaVersion: "aos.ecommerce-workshop.operation-command-observation/v1", tenant: envelope.tenant, proposalId: "proposal:1", leaseId: "lease:1", commandId: "classify", status: "applied", proposalHash: "a".repeat(64), receiptId: "receipt-1", requestFingerprint: "b".repeat(64), operationReceiptId: "operation-receipt-1", replayAllowed: false };

describe("EcommerceWorkshopClient", () => {
  it("只发两个 canonical GET，并沿用会话鉴权头", async () => {
    const fetch = vi.fn().mockResolvedValueOnce(ok({ ...envelope, items: [module], count: 1 })).mockResolvedValueOnce(ok({ ...envelope, item: module }));
    const client = new EcommerceWorkshopClient({ fetch, getBaseUrl: () => "http://api.test", getAuthHeaders: () => ({ Authorization: "Bearer test" }) });
    await expect(client.listModules()).resolves.toMatchObject({ count: 1 });
    await expect(client.getModuleReadiness("ecommerce.operations")).resolves.toMatchObject({ item: { moduleId: "ecommerce.operations" } });
    expect(fetch).toHaveBeenNthCalledWith(1, "http://api.test/v1/ecommerce-workshop/modules", expect.objectContaining({ method: "GET", headers: expect.objectContaining({ Authorization: "Bearer test" }) }));
    expect(fetch).toHaveBeenNthCalledWith(2, "http://api.test/v1/ecommerce-workshop/modules/ecommerce.operations/readiness", expect.objectContaining({ method: "GET" }));
  });
  it("HTTP error、network 和无效 moduleId 不伪装为空态", async () => {
    const denied = new EcommerceWorkshopClient({ fetch: vi.fn().mockResolvedValue(new Response(JSON.stringify({ code: "FORBIDDEN", message: "denied", details: null, traceId: "trace-1" }), { status: 403 })), getBaseUrl: () => "", getAuthHeaders: () => ({}) });
    await expect(denied.listModules()).rejects.toMatchObject({ status: 403, body: { code: "FORBIDDEN" } });
    const network = new EcommerceWorkshopClient({ fetch: vi.fn().mockRejectedValue(new Error("offline")), getBaseUrl: () => "", getAuthHeaders: () => ({}) });
    await expect(network.listModules()).rejects.toBeInstanceOf(EcommerceWorkshopClientError);
    await expect(network.getModuleReadiness("bad")).rejects.toBeInstanceOf(TypeError);
  });
  it("只发 canonical SourceReadiness GET 并保留 blocked", async () => {
    const fetch = vi.fn().mockResolvedValue(ok(sourceReadiness));
    const client = new EcommerceWorkshopClient({ fetch, getBaseUrl: () => "http://api.test", getAuthHeaders: () => ({ Authorization: "Bearer test" }) });
    const result = await client.getSourceReadiness();
    expect(result.status).toBe("blocked");
    expect(result.sources).toHaveLength(12);
    expect(result.sources[0].pipelineId).toBe("P01-shop-qyh");
    expect(fetch).toHaveBeenCalledWith("http://api.test/v1/ecommerce-workshop/source-readiness", expect.objectContaining({ method: "GET", headers: expect.objectContaining({ Authorization: "Bearer test" }) }));
  });
  it("只发 canonical Operations GET 且不接受 scope 查询注入", async () => {
    const fetch = vi.fn().mockResolvedValue(ok(operations));
    const client = new EcommerceWorkshopClient({ fetch, getBaseUrl: () => "http://api.test", getAuthHeaders: () => ({ Authorization: "Bearer test" }) });
    const parsed = await client.getOperationsView();
    expect(parsed.slices).toHaveLength(7);
    expect(parsed.slices[0]).toMatchObject({ sliceId: "orders" });
    expect(fetch).toHaveBeenCalledWith("http://api.test/v1/ecommerce-workshop/views/operations", expect.objectContaining({ method: "GET", headers: expect.objectContaining({ Authorization: "Bearer test" }) }));
  });
  it("只发 canonical Operations command-readiness GET 并严格解析", async () => {
    const fetch = vi.fn().mockResolvedValue(ok(commandReadiness));
    const client = new EcommerceWorkshopClient({ fetch, getBaseUrl: () => "http://api.test", getAuthHeaders: () => ({ Authorization: "Bearer test" }) });
    const parsed = await client.getOperationCommandReadiness();
    expect(parsed.commands.map((item) => item.commandId)).toEqual(commandIds);
    expect(fetch).toHaveBeenCalledWith("http://api.test/v1/ecommerce-workshop/commands/operations/readiness", expect.objectContaining({ method: "GET", headers: expect.objectContaining({ Authorization: "Bearer test" }) }));
  });
  it("只发 exact proposal/lease observation GET 并拒绝 scope/path 漂移", async () => {
    const fetch = vi.fn().mockResolvedValue(ok(commandObservation));
    const client = new EcommerceWorkshopClient({ fetch, getBaseUrl: () => "http://api.test", getAuthHeaders: () => ({ Authorization: "Bearer test" }) });
    await expect(client.getOperationCommandObservation("proposal:1", "lease:1")).resolves.toMatchObject({ status: "applied", replayAllowed: false });
    expect(fetch).toHaveBeenCalledWith("http://api.test/v1/ecommerce-workshop/commands/operations/observations/proposal%3A1/leases/lease%3A1", expect.objectContaining({ method: "GET", headers: expect.objectContaining({ Authorization: "Bearer test" }) }));
    await expect(client.getOperationCommandObservation("bad/proposal", "lease:1")).rejects.toBeInstanceOf(TypeError);
    const drift = new EcommerceWorkshopClient({ fetch: vi.fn().mockResolvedValue(ok({ ...commandObservation, leaseId: "lease:2" })), getBaseUrl: () => "", getAuthHeaders: () => ({}) });
    await expect(drift.getOperationCommandObservation("proposal:1", "lease:1")).rejects.toThrow("leaseId 漂移");
  });
  it("SourceReadiness 的 forbidden、network、non-JSON 与 parser drift 均失败关闭", async () => {
    const denied = new EcommerceWorkshopClient({ fetch: vi.fn().mockResolvedValue(new Response(JSON.stringify({ code: "FORBIDDEN", message: "denied", details: null, traceId: "trace-3" }), { status: 403 })), getBaseUrl: () => "", getAuthHeaders: () => ({}) });
    await expect(denied.getSourceReadiness()).rejects.toMatchObject({ status: 403, operationId: "ecommerceWorkshopSourceReadinessGet" });
    const network = new EcommerceWorkshopClient({ fetch: vi.fn().mockRejectedValue(new Error("offline")), getBaseUrl: () => "", getAuthHeaders: () => ({}) });
    await expect(network.getSourceReadiness()).rejects.toMatchObject({ status: 0, operationId: "ecommerceWorkshopSourceReadinessGet" });
    const nonJson = new EcommerceWorkshopClient({ fetch: vi.fn().mockResolvedValue(new Response("not-json", { status: 200 })), getBaseUrl: () => "", getAuthHeaders: () => ({}) });
    await expect(nonJson.getSourceReadiness()).rejects.toMatchObject({ status: 0, body: { code: "INVALID_SUCCESS_RESPONSE" } });
    const drift = new EcommerceWorkshopClient({ fetch: vi.fn().mockResolvedValue(ok({ ...sourceReadiness, status: "ready" })), getBaseUrl: () => "", getAuthHeaders: () => ({}) });
    await expect(drift.getSourceReadiness()).rejects.toBeInstanceOf(TypeError);
  });
  it("只发七条 Task Cockpit canonical GET 并规范编码 query", async () => {
    const fetch = vi.fn().mockResolvedValueOnce(ok(core)).mockResolvedValueOnce(ok(details)).mockResolvedValueOnce(ok(details)).mockResolvedValueOnce(ok(productionContext)).mockResolvedValueOnce(ok(responsibilityHandoffs)).mockResolvedValueOnce(ok(approvalReview)).mockResolvedValueOnce(ok(actionReceipts));
    const client = new EcommerceWorkshopClient({ fetch, getBaseUrl: () => "http://api.test/", getAuthHeaders: () => ({ Authorization: "Bearer test" }) });
    await client.getTaskCockpitCore({ status: "cancelled", limit: 20, cursor: "cursor+/=" });
    await client.listTaskCockpitRunSteps("run:1", { limit: 20 });
    await client.listTaskCockpitRunCheckpoints("run:1");
    await expect(client.getTaskCockpitRunProductionContext("run:1")).resolves.toMatchObject({ compilerVersion: "w2c.v1", stages: [{ stageId: "collect" }] });
    await expect(client.getTaskCockpitRunResponsibilityHandoffs("run:1")).resolves.toMatchObject({ profile: "standard", handoffs: [{ status: "consumed" }] });
    await expect(client.getTaskCockpitRunApprovalReview("run:1")).resolves.toMatchObject({ planApproval: { approvalStatus: "approved" }, actionApprovalCount: 1 });
    await expect(client.getTaskCockpitRunActionReceipts("run:1")).resolves.toMatchObject({ executions: [{ reconciliationState: "required" }], reconcileRequiredCount: 1 });
    expect(fetch).toHaveBeenNthCalledWith(1, "http://api.test/v1/ecommerce-workshop/views/task-cockpit?status=cancelled&limit=20&cursor=cursor%2B%2F%3D", expect.objectContaining({ method: "GET", headers: expect.objectContaining({ Authorization: "Bearer test" }) }));
    expect(fetch).toHaveBeenNthCalledWith(2, "http://api.test/v1/ecommerce-workshop/views/task-cockpit/runs/run%3A1/steps?limit=20", expect.objectContaining({ method: "GET" }));
    expect(fetch).toHaveBeenNthCalledWith(3, "http://api.test/v1/ecommerce-workshop/views/task-cockpit/runs/run%3A1/checkpoints", expect.objectContaining({ method: "GET" }));
    expect(fetch).toHaveBeenNthCalledWith(4, "http://api.test/v1/ecommerce-workshop/views/task-cockpit/runs/run%3A1/production-context", expect.objectContaining({ method: "GET" }));
    expect(fetch).toHaveBeenNthCalledWith(5, "http://api.test/v1/ecommerce-workshop/views/task-cockpit/runs/run%3A1/responsibility-handoffs", expect.objectContaining({ method: "GET" }));
    expect(fetch).toHaveBeenNthCalledWith(6, "http://api.test/v1/ecommerce-workshop/views/task-cockpit/runs/run%3A1/approval-review-issues", expect.objectContaining({ method: "GET" }));
    expect(fetch).toHaveBeenNthCalledWith(7, "http://api.test/v1/ecommerce-workshop/views/task-cockpit/runs/run%3A1/action-receipts", expect.objectContaining({ method: "GET" }));
  });
  it("409 stale cursor 与参数错误失败关闭，不伪装为空页", async () => {
    const stale = new EcommerceWorkshopClient({ fetch: vi.fn().mockResolvedValue(new Response(JSON.stringify({ code: "TASK_COCKPIT_CURSOR_STALE", message: "refresh", details: null, traceId: "trace-2" }), { status: 409 })), getBaseUrl: () => "", getAuthHeaders: () => ({}) });
    await expect(stale.listTaskCockpitRunSteps("run-1", { cursor: "old" })).rejects.toMatchObject({ status: 409, body: { code: "TASK_COCKPIT_CURSOR_STALE" }, operationId: "ecommerceWorkshopTaskCockpitRunStepsList" });
    await expect(stale.getTaskCockpitCore({ limit: 0 })).rejects.toBeInstanceOf(TypeError);
    await expect(stale.listTaskCockpitRunCheckpoints("bad/run")).rejects.toBeInstanceOf(TypeError);
    await expect(stale.getTaskCockpitCore({ cursor: " spaced " })).rejects.toBeInstanceOf(TypeError);
  });
});
