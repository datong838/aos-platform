import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";

const evidenceDir = path.dirname(fileURLToPath(import.meta.url));
const baseUrl = "http://127.0.0.1:8434";
const tenant = { orgId: "org-org", projectId: "dev-project" };
const cutoff = "2026-09-10T05:00:00Z";
const hash = `sha256:${"a".repeat(64)}`;

const specs = [
  { key: "cockpit", route: "/workshop/cockpit", moduleId: "ecommerce.task-cockpit", tabs: ".task-cockpit-visual-command select option", minimumTabs: 10, marker: /任务|可信空/ },
  { key: "content-campaign", route: "/workshop/content-campaign", moduleId: "ecommerce.content-campaign", tabs: ".content-campaign-toolbar button", minimumTabs: 3, marker: /活动列表|AI 策划助手/ },
  { key: "operations", route: "/workshop/operations", moduleId: "ecommerce.operations", tabs: ".operations-queue-filter", minimumTabs: 4, marker: /统一待办|业务处理流程/ },
  { key: "creator-growth", route: "/workshop/creator-growth", moduleId: "ecommerce.creator-growth", tabs: ".creator-growth-toolbar button", minimumTabs: 5, marker: /达人与机构|候选匹配概览/ },
  { key: "media-studio", route: "/workshop/media-studio", moduleId: "ecommerce.media-studio", tabs: "main [role='tab']", minimumTabs: 3, marker: /内容生产|生产准备/ },
  { key: "analyst", route: "/workshop/analyst", moduleId: "ecommerce.analyst", tabs: "main [role='tab']", minimumTabs: 7, marker: /经营|关键假设和不确定性/ },
  { key: "price-governance", route: "/workshop/price-governance", moduleId: "ecommerce.price-governance", tabs: "main [role='tab']", minimumTabs: 3, marker: /价格治理任务链|调价禁用/ },
  { key: "customer", route: "/workshop/customer", moduleId: "ecommerce.customer", tabs: "main [role='tab']", minimumTabs: 4, marker: /客户关系处理计划|不展示客户明细/ },
];
const viewports = [{ width: 1280, height: 720 }, { width: 1440, height: 900 }, { width: 1920, height: 1080 }];

const modules = specs.map((spec, index) => ({
  moduleId: spec.moduleId, displayName: spec.key, menuLabel: spec.key, route: spec.route,
  slot: "workshop.primary.ecommerce", order: index + 1,
  installationRef: { installationId: `11111111-1111-4111-8111-${String(index + 1).padStart(12, "0")}`, revision: 8, compositionId: `22222222-2222-4222-8222-${String(index + 1).padStart(12, "0")}`, lockRevision: 12, lockHash: hash, overlayRevision: "ar2-7e-ready-r1" },
  moduleRef: { publisher: "aos.ecommerce", bundleId: "solution.ecommerce.growth", version: "1.0.0", bundleContentHash: hash, moduleArtifactRef: `bundle://${spec.moduleId}`, moduleArtifactHash: hash },
  readiness: "available", blockers: [], permissions: { roles: ["operator"], markings: ["public"], dataScopes: ["ecommerce:read"], actionTypes: [] },
  requiredObjects: [], requiredCapabilities: [], requiredAipFeatures: [], viewRefs: [], evalPackRefs: [], productionContractRefs: [], responsibilityTemplateRefs: [], impactCalculatorRefs: [], legacyAssetRefs: [], legacyRoutes: [], minimumRuntimeVersion: "1.0.0", dependencyRefs: [], lastReceiptRef: null,
}));

const blocker = (prefix, id) => ({ code: `${prefix}_${id.toUpperCase().replaceAll("-", "_")}_AUTHORITY_NOT_AVAILABLE`, dependency: id, requiredAction: "attach exact current authority" });
const pageInfo = (count = 0, limit = 100) => ({ limit, count, hasMore: false, nextCursor: null });
const ref = (resourceType, resourceId) => ({ resourceType, resourceId, revision: 1, contentHash: hash, receiptId: `receipt-${resourceId}` });

const fixtures = new Map();
const put = (pathname, value) => fixtures.set(pathname, value);

put("/api/v1/ecommerce-workshop/views/task-cockpit", {
  schemaVersion: "aos.ecommerce-workshop.task-cockpit/v1", tenant, evaluatedAt: cutoff, taskCutoff: cutoff,
  stateConsistency: "current_state_per_page", readiness: "degraded", blockers: [blocker("TASK_COCKPIT", "business-context")], items: [], page: pageInfo(0, 20),
});
put("/api/v1/ecommerce-workshop/views/task-cockpit/dispatch-scenario", {
  schemaVersion: "aos.ecommerce-workshop.dispatch-scenario/v1", status: "blocked", rootTaskGraphRef: null, rootTaskRunRef: null, dispatchBindingHash: null, evaluatedAt: cutoff,
  composition: { atomicSkillRefs: [], logicRevisionRef: null, roleBindings: [] }, stages: [], ledger: { tasksExpected: 0, tasksObserved: 0, handoffsExpected: 0, handoffsObserved: 0, decisionsExpected: 0, decisionsRecorded: 0, accepted: 0, rejected: 0, requestMore: 0, returned: 0, takeoverRequested: 0, takeoverDecided: 0, activeOwnerCount: 0 },
  outcomeAxes: [], blockers: [blocker("TASK_COCKPIT", "dispatch")], commands: { dispatch: false, decideHandoff: false, requestTakeover: false, approveTakeover: false, mutateOwner: false }, externalEffectsAllowed: false,
});
put("/api/v1/ecommerce-workshop/views/task-cockpit/batch-scenario", {
  schemaVersion: "aos.ecommerce-workshop.batch-scenario/v1", status: "blocked", batchPreparationRevisionRef: null, batchStartDecisionRef: null, batchStartBindingHash: null, evaluatedAt: cutoff,
  composition: { atomicSkillRefs: [], logicRevisionRef: null, roleBindings: [] }, preparationDecisions: [], childOutcomes: [], stages: [], ledger: { frozenTotal: 0, included: 0, excluded: 0, blocked: 0, preparationUnknown: 0, childrenExpected: 0, childrenObserved: 0, succeeded: 0, failed: 0, cancelled: 0, childUnknown: 0, reconciled: 0, reconcileReceiptsObserved: 0 }, outcomeAxes: [], sideEffectLedger: { prepareExternalCalls: 0, providerCalls: 0, actionAttempts: 0, externalEffects: 0 }, blockers: [blocker("TASK_COCKPIT", "batch")], commands: { prepare: false, start: false, cancel: false, reconcile: false }, automaticRetryAllowed: false, externalEffectsAllowed: false, releaseAllowed: false,
});

const contentSlices = ["plan", "calendar", "content"].map((sliceId) => ({ sliceId, status: "blocked", dataCutoff: cutoff, authorityRefs: [], items: [], blockers: [blocker("CANONICAL", sliceId)], countLedger: { eligible: 0, attached: 0, unmatched: 0, conflicted: 0 } }));
put("/api/v1/ecommerce-workshop/views/content-campaign", { schemaVersion: "aos.ecommerce-workshop.content-campaign-view/v1", tenant, evaluatedAt: cutoff, dataCutoff: cutoff, readiness: "degraded", slices: contentSlices, page: pageInfo() });
put("/api/v1/ecommerce-workshop/views/content-campaign/real-inputs", { schemaVersion: "aos.ecommerce-workshop.content-campaign-inputs/v1", tenant, evaluatedAt: cutoff, dataCutoff: cutoff, status: "ready", products: [], inventory: [], plans: [], ledger: { products: 0, inventory: 0, plans: 0, unmatchedInventory: 0 }, unavailableGroups: [] });

const operationIds = ["orders", "orderLines", "inventory", "shipments", "payments", "aftersaleEvents", "operationCases"];
put("/api/v1/ecommerce-workshop/views/operations", { schemaVersion: "aos.ecommerce-workshop.operations-view/v1", tenant, evaluatedAt: cutoff, dataCutoff: cutoff, readiness: "degraded", slices: operationIds.map((sliceId) => ({ sliceId, status: "ready", dataCutoff: cutoff, authorityRefs: [ref("ReadAuthority", sliceId)], blockers: [], countLedger: { sourceTotal: 0, attached: 0, unmatched: 0, conflicted: 0 } })), page: pageInfo(0, 50) });
put("/api/v1/ecommerce-workshop/views/operations/cases", { schemaVersion: "aos.ecommerce-workshop.operation-case-workspace/v1", tenant, status: "ready", evaluatedAt: cutoff, dataCutoff: cutoff, sources: ["orders", "inventory", "shipments", "aftersaleEvents", "payments", "operationCases"].map((sourceId) => ({ sourceId, status: "ready", count: 0, blocker: null })), cases: [], candidates: [], availableRefs: [], ledger: { sourceTotal: 0, assigned: 0, unassigned: 0, candidates: 0, openCases: 0, pausedCases: 0, closedCases: 0 }, externalEffectAllowed: false });
put("/api/v1/ecommerce-workshop/commands/operations/readiness", { schemaVersion: "aos.ecommerce-workshop.operation-command-readiness/v1", tenant, evaluatedAt: cutoff, commands: ["classify", "createCase", "changeMembership", "manageSla", "automationKill", "refund"].map((commandId) => ({ commandId, label: commandId, status: "blocked", risk: "controlled", sideEffect: "internalAuthority", blockers: [blocker("OPERATION_COMMAND", commandId)] })) });

const creatorStages = ["candidate", "outreach", "contract", "delivery", "relationship"];
put("/api/v1/ecommerce-workshop/views/creator-growth", { schemaVersion: "aos.ecommerce-workshop.creator-growth-view/v1", tenant, evaluatedAt: cutoff, dataCutoff: cutoff, readiness: "degraded", slices: creatorStages.map((businessStage) => ({ businessStage, workflowPhases: ["discovery", "evidence", "matching", "batch_prepare", "start"], status: "blocked", dataCutoff: cutoff, authorityRefs: [], blockers: [blocker("CANONICAL_CREATOR", businessStage)], countLedger: { input: 0, eligible: 0, excluded: 0, needsReview: 0, unknown: 0, deduplicated: 0 } })), page: pageInfo() });
put("/api/v1/ecommerce-workshop/views/creator-growth/contributions", { schemaVersion: "aos.ecommerce-workshop.creator-prepare/v1", tenant, evaluatedAt: cutoff, atomicSkillRefs: [], logicRef: null, primaryColleague: "导购顾问", collaboratorColleagues: ["数据参谋", "内容官", "活动策划师"], latestBatch: null, blockers: ["CREATOR_BATCH_PREPARATION_NOT_AVAILABLE"], allowedCommands: ["PREPARE_CREATOR_BATCH"], externalEffectsAllowed: false });
put("/api/v1/ecommerce-workshop/views/creator-growth/lifecycle", { schemaVersion: "aos.ecommerce-workshop.creator-lifecycle/v1", tenant, evaluatedAt: cutoff, latestStart: null, ledger: { eligibleItems: 0, lanes: 0, prepared: 0, accepted: 0, applied: 0, failed: 0, unknown: 0, disputed: 0, completed: 0 }, contracts: [], deliveries: [], relationships: [], blockers: ["CREATOR_BATCH_START_NOT_AVAILABLE"], allowedCommands: ["START_CREATOR_BATCH_GOVERNANCE"], externalEffectsAllowed: false });
put("/api/v1/ecommerce-workshop/views/creator-growth/workflow/drafts", { tenant, items: [], count: 0 });

put("/api/v1/ecommerce-workshop/views/media-studio", { schemaVersion: "aos.ecommerce-workshop.media-studio-view/v1", tenant, evaluatedAt: cutoff, dataCutoff: cutoff, readiness: "degraded", slices: ["context", "execution", "delivery"].map((sliceId) => ({ sliceId, status: "blocked", dataCutoff: cutoff, readinessAxes: ["module", "capability", "assignee", "provider", "budget", "publication"].map((axis) => ({ axis, status: "target", exactRef: null, targetContractRef: `ADR-86#${axis}`, gaps: ["missing authority"], blockers: [blocker("MEDIA", axis)] })), authorityRefs: [], blockers: [blocker("MEDIA", sliceId)], countLedger: { denominator: 6, ready: 0, target: 6, blocked: 0, unknown: 0, conflict: 0, notApplicable: 0 } })), page: pageInfo() });
put("/api/v1/ecommerce-workshop/views/media-studio/workflow/drafts", { tenant, items: [], count: 0 });
const fullVideoBlocker = blocker("FULL_VIDEO", "external-gate");
put("/api/v1/ecommerce-workshop/views/media-studio/full-production-scenario", { schemaVersion: "aos.ecommerce-workshop.full-video-scenario/v1", status: "blocked", rootBriefRef: null, taskRunRef: null, fullProductionBindingHash: null, composition: null, evaluatedAt: cutoff, responsibilities: ["media.producer", "media.director", "media.screenwriter", "media.art", "media.storyboard", "media.capture", "media.post", "media.review"].map((responsibilityId) => ({ responsibilityId, label: responsibilityId, status: "blocked", assigneeRef: null, skillBindingRef: null, independentReviewRequired: responsibilityId === "media.review", blocker: fullVideoBlocker })), stages: ["brief_profile", "compile_start", "script_art", "storyboard_capture", "post_review", "publish_delivery", "settlement_effect"].map((stageId) => ({ stageId, status: "blocked", exactRefs: [], contribution: "等待 exact authority", blocker: fullVideoBlocker })), faultRecovery: ["crash_before_submit", "crash_after_submit_before_receipt", "lease_fence_loss", "webhook_ordering", "timeout_cancel_late_result", "checkpoint_drift", "capacity_budget_race", "restart_partition", "malicious_artifact"].map((faultId) => ({ faultId, status: "blocked", recoveryDecision: "等待恢复证据", authorityRefs: [], blocker: fullVideoBlocker, automaticRetryAllowed: false })), ledger: { responsibilitiesExpected: 8, responsibilitiesObserved: 0, stagesExpected: 7, stagesObserved: 0, attemptsExpected: 0, attemptsObserved: 0, artifactsExpected: 0, artifactsObserved: 0, mediaGatesExpected: 4, mediaGatesObserved: 0, faultCasesExpected: 9, faultCasesObserved: 0, usageBucketsExpected: 0, usageBucketsObserved: 0 }, blockers: [fullVideoBlocker], commands: { prepare: false, start: false, resume: false, takeover: false, cancel: false, reconcile: false, publish: false, settle: false }, externalEffectsAllowed: false, releaseAllowed: false });

const analystIds = ["overview", "drivers", "diagnosis", "plan", "effects", "evidence", "quality"];
put("/api/v1/ecommerce-workshop/views/analyst", { schemaVersion: "aos.ecommerce-workshop.analyst-view/v1", tenant, resourceRevision: 1, evaluatedAt: cutoff, dataCutoff: cutoff, readiness: "degraded", views: analystIds.map((viewId) => ({ viewId, status: "blocked", resourceRevision: 1, dataCutoff: cutoff, readinessAxes: ["metric_query", "model", "eval", "plan_materialization", "professional_handoff"].map((axis) => ({ axis, status: "blocked", exactRef: null, blockers: [blocker("ANALYST", viewId)] })), metrics: [], authorityRefs: [], blockers: [blocker("ANALYST", viewId)], countLedger: { denominator: 0, ready: 0, unknown: 0, blocked: 0, conflict: 0 } })), page: pageInfo() });
const learningBlocker = blocker("LEARNING", "revocation-impact");
put("/api/v1/ecommerce-workshop/views/analyst/learning-scenario", { schemaVersion: "aos.ecommerce-workshop.learning-scenario/v1", status: "blocked", rootEffectReviewRef: null, maturityPolicyRef: null, learningBindingHash: null, composition: null, evaluatedAt: cutoff, stages: ["effect_review", "maturity", "memory_candidate", "governance", "promotion", "knowledge_query", "revocation_impact"].map((stageId) => ({ stageId, status: "blocked", exactRefs: [], contribution: "等待 exact authority", blockers: [learningBlocker] })), ledger: { reviewsExpected: 0, reviewsObserved: 0, candidatesExpected: 0, candidatesObserved: 0, promotionsExpected: 0, promotionsObserved: 0, citationsExpected: 0, citationsObserved: 0, historicalExposures: 0, retainedExposures: 0, impactRefsExpected: 0, impactRefsObserved: 0 }, outcomeAxes: ["effect_mature", "candidate_governed", "knowledge_promoted", "future_query_authorized", "revocation_impact_recorded"].map((axisId) => ({ axisId, status: "blocked", exactRef: null, blocker: learningBlocker })), blockers: [learningBlocker], commands: { submitCandidate: false, approveCandidate: false, promoteCandidate: false, publishWiki: false, revokeKnowledge: false }, externalEffectsAllowed: false });

const priceIds = ["governance", "competitor", "schedule"];
put("/api/v1/ecommerce-workshop/views/price-governance", { schemaVersion: "aos.ecommerce-workshop.price-governance-view/v1", tenant, resourceRevision: 1, evaluatedAt: cutoff, dataCutoff: cutoff, readiness: "degraded", views: priceIds.map((viewId) => ({ viewId, status: "blocked", resourceRevision: 1, dataCutoff: cutoff, readinessAxes: ["collection", "match", "policy_case", "notification", "advice_handoff", "repricing"].map((axis) => ({ axis, status: axis === "repricing" ? "disabled" : "blocked", exactRef: null, blockers: [blocker("PRICE", viewId)] })), observations: [], authorityRefs: [], blockers: [blocker("PRICE", viewId)], countLedger: { input: 0, eligible: 0, excluded: 0, needsReview: 0, unknown: 0, deduplicated: 0 } })), page: pageInfo() });
put("/api/v1/ecommerce-workshop/views/price-governance/contributions", { schemaVersion: "aos.ecommerce-workshop.price-research/v1", tenant, evaluatedAt: cutoff, atomicSkillRefs: [], logicRef: null, primaryColleague: "数据参谋", collaboratorColleagues: ["活动策划师", "导购顾问"], latestBatch: null, blockers: ["PRICE_RESEARCH_BATCH_NOT_AVAILABLE"], allowedCommands: ["PREPARE_PRICE_RESEARCH_BATCH", "FREEZE_PRICE_RESEARCH_BATCH"], externalEffectsAllowed: false });
put("/api/v1/ecommerce-workshop/views/price-governance/dispositions", { schemaVersion: "aos.ecommerce-workshop.price-disposition/v1", tenant, evaluatedAt: cutoff, atomicSkillIds: ["compile-price-case", "prepare-price-advice", "prepare-price-notice", "prepare-price-handoff", "evaluate-reprice-specialized-gate"], logicId: "ecommerce-price-governance", primaryColleague: "数据参谋", collaboratorColleagues: ["活动策划师", "导购顾问"], caseCount: 0, dispositionCounts: { internal_advice: 0, external_notice: 0, module_handoff: 0, repricing: 0 }, latestDisposition: null, latestObservation: null, blockers: ["PRICE_DISPOSITION_AUTHORITY_UNAVAILABLE", "PRICE_CASE_NOT_AVAILABLE", "PRICE_DISPOSITION_NOT_AVAILABLE", "PRICE_NOTICE_OPERATIONAL_AUTHORITY_NOT_GRANTED", "PRICE_REPRICE_OPERATIONAL_AUTHORITY_NOT_GRANTED"], allowedCommands: ["COMPILE_PRICE_CASE", "CREATE_PRICE_DISPOSITION_CONTRACT", "PREPARE_PRICE_DISPOSITION", "FREEZE_PRICE_DISPOSITION", "RECORD_PRICE_DISPOSITION_OBSERVATION"], repricingEnabled: false, externalEffectsAllowed: false });

const customerIds = ["customer", "segment", "journey", "dialogue"];
put("/api/v1/ecommerce-workshop/views/customer", { schemaVersion: "aos.ecommerce-workshop.customer-view/v1", tenant, resourceRevision: 1, evaluatedAt: cutoff, dataCutoff: cutoff, readiness: "degraded", views: customerIds.map((viewId) => ({ viewId, status: "blocked", resourceRevision: 1, dataCutoff: cutoff, readinessAxes: ["customer_lite", "consent", "segment", "journey", "dialogue", "outreach_batch"].map((axis) => ({ axis, status: "blocked", exactRef: null, blockers: [blocker("CUSTOMER", viewId)] })), items: [], authorityRefs: [], blockers: [blocker("CUSTOMER", viewId)], countLedger: { input: 0, eligible: 0, excluded: 0, unknown: 0, deduplicated: 0 } })), page: pageInfo() });
put("/api/v1/ecommerce-workshop/views/customer/contributions", { schemaVersion: "aos.ecommerce-workshop.customer-lifecycle/v1", tenant, evaluatedAt: cutoff, atomicSkillIds: ["build-evidence-pack"], logicId: "ecommerce-customer-relationship", primaryColleague: "私域管家", collaboratorColleagues: ["内容官", "客服专员", "导购顾问", "数据参谋"], consentPolicyCount: 0, segmentCount: 0, journeyCount: 0, dialogueCount: 0, latestBatch: null, blockers: ["CUSTOMER_CONTACT_RESOLUTION_NOT_AUTHORIZED"], allowedCommands: [], contactResolutionAllowed: false, startAllowed: false, sendAllowed: false, externalEffectsAllowed: false });
put("/api/v1/ecommerce-workshop/views/customer/contact-contributions", { schemaVersion: "aos.ecommerce-workshop.customer-contact-governance/v1", tenant, evaluatedAt: cutoff, atomicSkillIds: ["build-evidence-pack"], logicId: "ecommerce-customer-relationship", primaryColleague: "私域管家", collaboratorColleagues: ["内容官", "客服专员", "导购顾问", "数据参谋"], latestStart: null, ledger: { frozenEligible: 0, reserved: 0, skippedWithdrawn: 0, cancelled: 0, accepted: 0, applied: 0, failed: 0, unknown: 0, disputed: 0 }, frequencyPolicyCount: 0, withdrawalCount: 0, blockers: ["CUSTOMER_CONTACT_GOVERNANCE_NOT_PREPARED"], allowedCommands: [], permitRedemptionAllowed: false, contactResolutionAllowed: false, providerDispatchAllowed: false, sendAllowed: false, externalEffectsAllowed: false });

function reply(route, body, status = 200) { return route.fulfill({ status, contentType: "application/json; charset=utf-8", body: JSON.stringify(body) }); }
async function installRoutes(page) {
  const requests = []; const responses = []; const unknownGets = [];
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request(); const url = new URL(request.url()); const pathname = url.pathname;
    requests.push({ method: request.method(), pathname, search: url.search, orgId: request.headers()["x-org-id"] ?? null, projectId: request.headers()["x-project-id"] ?? null });
    if (request.method() !== "GET") { responses.push({ pathname, status: 405 }); return reply(route, { code: "READ_ONLY_ACCEPTANCE", message: "write denied" }, 405); }
    if (pathname === "/api/v1/me") return reply(route, { subject: "ar2-7e-ready", ...tenant, workspaceName: "AR2-7E 隔离验收", roles: ["operator"], markings: ["public"], tokenKind: "fixture" });
    if (pathname === "/api/v1/orgs") return reply(route, { items: [{ id: tenant.orgId, name: tenant.orgId }], currentOrgId: tenant.orgId });
    if (pathname === "/api/v1/workspaces") return reply(route, { items: [{ id: tenant.projectId, orgId: tenant.orgId, name: "AR2-7E 隔离验收" }], currentProjectId: tenant.projectId });
    if (pathname === "/api/v1/health") return reply(route, { status: "ok" });
    if (pathname === "/api/v1/ecommerce-workshop/modules") return reply(route, { schemaVersion: "aos.ecommerce-workshop/v1", tenant, evaluatedAt: cutoff, dataCutoff: cutoff, items: modules, count: modules.length });
    if (fixtures.has(pathname)) return reply(route, fixtures.get(pathname));
    if (pathname === "/api/v1/aip/capability-catalog") return reply(route, { tenant, items: [], count: 0, availableCount: 0 });
    if (pathname === "/api/v1/aip/agent-registry") return reply(route, { tenant, items: [], stats: { definitionCount: 0, installedCount: 0, runnableCount: 0, skillDefinitionCount: 0, capabilityDefinitionCount: 0 } });
    if (["/api/v1/aip/memory-authority/improvement-observations", "/api/v1/aip/memory-authority/candidates", "/api/v1/aip/memory-authority/memories"].includes(pathname)) return reply(route, []);
    if (pathname === "/api/v1/ecommerce-workshop/source-readiness") return reply(route, { schemaVersion: "aos.ecommerce-workshop.source-readiness/v1", tenant, checkedAt: cutoff, cutoffAt: cutoff, status: "empty", sources: [], receiptRef: null, investigation: null });
    const closureMatch = pathname.match(/^\/api\/v1\/ecommerce-workshop\/views\/(creator|price|customer)\/closure-contributions$/);
    if (closureMatch) return reply(route, { schemaVersion: "aos.ecommerce-workshop.three-module-closure/v1", tenant, module: closureMatch[1], evaluatedAt: cutoff, atomicSkillIds: [`${closureMatch[1]}-read-only`], logicId: `ecommerce-${closureMatch[1]}-read-only`, primaryColleague: "数字同事", collaboratorColleagues: [], latestClosure: null, latestUsage: null, latestEffect: null, latestHandoff: null, blockers: ["THREE_MODULE_CLOSURE_NOT_COMPILED", "THREE_MODULE_USAGE_NOT_BOUND", "THREE_MODULE_EFFECT_NOT_BOUND", "THREE_MODULE_HANDOFF_NOT_BOUND"], allowedCommands: ["COMPILE_THREE_MODULE_CLOSURE", "BIND_CANONICAL_USAGE", "BIND_CANONICAL_EFFECT_REVIEW", "BIND_CANONICAL_HANDOFF"], handoffConsumeAllowed: false, memoryPromotionAllowed: false, externalEffectsAllowed: false });
    if (pathname === "/api/v1/aip/async-jobs") return reply(route, { tenant, items: [], count: 0 });
    if (pathname.startsWith("/api/v1/ecommerce/investigations")) return reply(route, { tenant, items: [], count: 0 });
    unknownGets.push(pathname); responses.push({ pathname, status: 418 });
    return reply(route, { code: "UNDECLARED_READY_FIXTURE", message: pathname }, 418);
  });
  page.on("response", (response) => { if (response.url().includes("/api/v1/")) responses.push({ pathname: new URL(response.url()).pathname, status: response.status() }); });
  return { requests, responses, unknownGets };
}

async function interact(page, spec) {
  const observed = { tabLabels: [], tabSelections: [], searchRoundTrip: null };
  const tabs = page.locator(spec.tabs);
  const count = await tabs.count();
  observed.tabLabels = await tabs.allTextContents();
  if (spec.key === "cockpit") {
    const select = page.locator(".task-cockpit-visual-command select");
    await select.selectOption("completed"); await page.waitForTimeout(100); await select.selectOption("");
    observed.tabSelections = ["已完成", "全部状态"];
  } else {
    const interactionCount = spec.key === "content-campaign" ? Math.min(3, count) : count;
    for (let index = 0; index < interactionCount; index += 1) {
      const tab = tabs.nth(index);
      if (await tab.isVisible() && await tab.isEnabled()) { await tab.click(); await page.waitForTimeout(40); observed.tabSelections.push((await tab.textContent())?.trim() ?? String(index)); }
    }
  }
  if (spec.key === "operations") {
    const search = page.locator('[aria-label="搜索运营待办"]');
    if (await search.count()) { await search.fill("payments"); await search.fill(""); observed.searchRoundTrip = true; }
  }
  if (spec.key === "creator-growth") {
    const search = page.locator('input[aria-label="检索达人或机构"]');
    if (await search.count()) { await search.fill("隔离验收"); await search.fill(""); observed.searchRoundTrip = true; }
  }
  return observed;
}

async function runUnit(browser, spec, viewport) {
  const context = await browser.newContext({ viewport });
  await context.addInitScript((value) => sessionStorage.setItem("aos-tenant-v1", JSON.stringify(value)), { ...tenant, workspaceName: "AR2-7E 隔离验收", subject: "ar2-7e-ready", roles: ["operator"] });
  const page = await context.newPage(); const pageErrors = []; const consoleErrors = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("console", (message) => { if (message.type() === "error") consoleErrors.push(message.text()); });
  const transport = await installRoutes(page); const failures = [];
  try {
    await page.goto(`${baseUrl}${spec.route}`, { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.locator(`.ecommerce-workshop-shell[data-module-id="${spec.moduleId}"]`).waitFor({ timeout: 10000 });
    await page.waitForTimeout(450);
    const text = await page.locator("main").first().innerText();
    const observed = await interact(page, spec);
    const tabCount = observed.tabLabels.length;
    const navCount = await page.locator(".nav [data-workshop-module-id]").count();
    const activeNavCount = await page.locator(".nav a[aria-current='page']").count();
    const h1Count = await page.locator("h1").count();
    const headerActions = await page.locator(".workshop-visual-header-actions button").evaluateAll((buttons) => buttons.map((button) => ({ label: button.textContent?.trim() ?? "", disabled: button.disabled })));
    const unauthorizedActions = headerActions.filter((item) => !item.disabled && !["筛选", "查看内容计划"].includes(item.label));
    const layout = await page.evaluate(() => ({ clientWidth: document.documentElement.clientWidth, scrollWidth: document.documentElement.scrollWidth, horizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1 }));
    const workshopRequests = transport.requests.filter((item) => item.pathname.startsWith("/api/v1/ecommerce-workshop/"));
    const nonGet = workshopRequests.filter((item) => item.method !== "GET");
    const tenantDrift = workshopRequests.filter((item) => item.orgId !== tenant.orgId || item.projectId !== tenant.projectId);
    const serverErrors = transport.responses.filter((item) => item.status >= 500);
    if (navCount !== 8) failures.push(`nav_count_${navCount}`);
    if (activeNavCount !== 1) failures.push(`active_nav_${activeNavCount}`);
    if (h1Count !== 1) failures.push(`h1_count_${h1Count}`);
    if (tabCount < spec.minimumTabs) failures.push(`tabs_${tabCount}_below_${spec.minimumTabs}`);
    if (!spec.marker.test(text)) failures.push("page_marker_missing");
    if (unauthorizedActions.length) failures.push(`unauthorized_actions_${unauthorizedActions.map((item) => item.label).join("|")}`);
    if (layout.horizontalOverflow) failures.push("horizontal_overflow");
    if (nonGet.length) failures.push("non_get_workshop_request");
    if (tenantDrift.length) failures.push("tenant_header_drift");
    if (transport.unknownGets.length) failures.push(`unknown_get_${transport.unknownGets.join("|")}`);
    if (serverErrors.length) failures.push("http_5xx");
    if (pageErrors.length) failures.push("page_errors");
    if (consoleErrors.length) failures.push("console_errors");
    const collapse = page.getByRole("button", { name: "折叠侧栏" }); await collapse.click(); await page.getByRole("button", { name: "展开侧栏" }).click();
    await page.screenshot({ path: path.join(evidenceDir, `ar2-7e-ready-${spec.key}-${viewport.width}x${viewport.height}.png`), fullPage: true });
    return { spec: { key: spec.key, route: spec.route, moduleId: spec.moduleId }, viewport, result: failures.length ? "FAIL" : "PASS", failures, observed, navCount, activeNavCount, h1Count, headerActions, layout, pageErrors, consoleErrors, ...transport };
  } catch (error) {
    failures.push(error instanceof Error ? error.message : String(error));
    await page.screenshot({ path: path.join(evidenceDir, `ar2-7e-ready-${spec.key}-diagnostic-${viewport.width}x${viewport.height}.png`), fullPage: true }).catch(() => {});
    return { spec: { key: spec.key, route: spec.route, moduleId: spec.moduleId }, viewport, result: "FAIL", failures, pageErrors, consoleErrors, ...transport };
  } finally { await context.close(); }
}

const browser = await chromium.launch({ executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", headless: true });
const results = []; let stoppedEarly = false; let consecutiveFailures = 0;
try {
  outer: for (const spec of specs) for (const viewport of viewports) {
    const result = await runUnit(browser, spec, viewport); results.push(result);
    console.log(`${spec.key} ${viewport.width}x${viewport.height}: ${result.result}${result.failures.length ? ` ${result.failures.join(",")}` : ""}`);
    consecutiveFailures = result.result === "PASS" ? 0 : consecutiveFailures + 1;
    if (consecutiveFailures >= 2) { stoppedEarly = true; break outer; }
  }
} finally { await browser.close(); }

const counts = {
  passed: results.filter((item) => item.result === "PASS").length, total: results.length,
  screenshots: results.filter((item) => item.result === "PASS").length,
  nonGetWorkshopRequests: results.flatMap((item) => item.requests ?? []).filter((item) => item.pathname.startsWith("/api/v1/ecommerce-workshop/") && item.method !== "GET").length,
  unknownGets: results.reduce((sum, item) => sum + (item.unknownGets?.length ?? 0), 0),
  tenantHeaderDrift: results.flatMap((item) => item.requests ?? []).filter((item) => item.pathname.startsWith("/api/v1/ecommerce-workshop/") && (item.orgId !== tenant.orgId || item.projectId !== tenant.projectId)).length,
  http5xx: results.flatMap((item) => item.responses ?? []).filter((item) => item.status >= 500).length,
  pageErrors: results.reduce((sum, item) => sum + item.pageErrors.length, 0), consoleErrors: results.reduce((sum, item) => sum + item.consoleErrors.length, 0),
  horizontalOverflow: results.filter((item) => item.layout?.horizontalOverflow).length, stoppedEarly,
};
const evidence = { schemaVersion: "aos.ar2-7e-eight-workbench-ready-browser/v1", generatedAt: new Date().toISOString(), baseUrl, authority: "AOS-000572 / AR2_7D_RUNTIME_WIRING_CANONICAL_ROUTER_GREEN", fixtureBoundary: "contract-valid isolated degraded and trustworthy-empty projections; no real tenant facts", result: results.length === 24 && results.every((item) => item.result === "PASS") ? "PASS" : "FAIL", counts, results, boundaries: ["All Workshop requests remained GET and exact-tenant scoped.", "Fixtures contain no real business facts and authorize no Provider, publication, or external effect.", "Header business preparation actions remained disabled because actionTypes is empty."] };
fs.writeFileSync(path.join(evidenceDir, "ar2-7e-eight-workbench-ready-browser.json"), `${JSON.stringify(evidence, null, 2)}\n`);
console.log(JSON.stringify({ result: evidence.result, counts }, null, 2));
if (evidence.result !== "PASS") process.exitCode = 1;
