import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";

const evidenceDir = path.dirname(fileURLToPath(import.meta.url));
const baseUrl = "http://127.0.0.1:8434";
const tenant = { orgId: "org-org", projectId: "dev-project" };
const cutoff = "2026-08-15T10:00:00Z";
const hash = `sha256:${"a".repeat(64)}`;
const rawHash = "a".repeat(64);
const viewports = [{ width: 1280, height: 720 }, { width: 1440, height: 900 }, { width: 1920, height: 1080 }];
const moduleSpecs = [
  ["ecommerce.task-cockpit", "任务总控", "/workshop/cockpit"],
  ["ecommerce.content-campaign", "内容活动", "/workshop/content-campaign"],
  ["ecommerce.operations", "运营履约", "/workshop/operations"],
  ["ecommerce.creator-growth", "达人增长", "/workshop/creator-growth"],
  ["ecommerce.media-studio", "媒体工坊", "/workshop/media-studio"],
  ["ecommerce.analyst", "经营分析", "/workshop/analyst"],
  ["ecommerce.price-governance", "价格治理", "/workshop/price-governance"],
  ["ecommerce.customer", "客户经营", "/workshop/customer"],
];
const modules = moduleSpecs.map(([moduleId, label, route], index) => ({
  moduleId, displayName: label, menuLabel: label, route, slot: "workshop.primary.ecommerce", order: index + 1,
  installationRef: { installationId: `11111111-1111-4111-8111-${String(index + 1).padStart(12, "0")}`, revision: 8, compositionId: `22222222-2222-4222-8222-${String(index + 1).padStart(12, "0")}`, lockRevision: 12, lockHash: hash, overlayRevision: "ar2-7e-cockpit-rich-r1" },
  moduleRef: { publisher: "aos.ecommerce", bundleId: "solution.ecommerce.growth", version: "1.0.0", bundleContentHash: hash, moduleArtifactRef: `bundle://${moduleId}`, moduleArtifactHash: hash },
  readiness: "available", blockers: [], permissions: { roles: ["operator"], markings: ["public"], dataScopes: ["ecommerce:read"], actionTypes: [] },
  requiredObjects: [], requiredCapabilities: [], requiredAipFeatures: [], viewRefs: [], evalPackRefs: [], productionContractRefs: [], responsibilityTemplateRefs: [], impactCalculatorRefs: [], legacyAssetRefs: [], legacyRoutes: [], minimumRuntimeVersion: "1.0.0", dependencyRefs: [], lastReceiptRef: null,
}));

const warning = { code: "TASK_COCKPIT_BUSINESS_CONTEXT_INDEPENDENT_SNAPSHOT", severity: "warning", dependency: "business-context:ecommerce.source-readiness", requiredAction: "按独立 cutoff 展示" };
const pageInfo = (count, limit = 20) => ({ limit, count, hasMore: false, nextCursor: null });
const task = (taskId, title, status, updatedAt, runStatus = null) => ({
  taskId, taskType: "daily", title, status, priority: 50, version: 1, currentPlanRevisionId: runStatus ? "plan-1" : null,
  createdAt: status === "pending" ? "2026-08-15T09:45:00Z" : "2026-08-15T08:00:00Z", updatedAt,
  run: runStatus ? { runId: `run-${taskId}`, planRevisionId: "plan-1", status: runStatus, version: 1, startedAt: "2026-08-15T08:10:00Z", finishedAt: runStatus === "running" ? null : updatedAt, createdAt: "2026-08-15T08:00:00Z", updatedAt } : null,
});
const baseTasks = [
  task("task-active", "检查今日订单履约风险", "executing", "2026-08-15T09:01:00Z", "running"),
  task("task-done", "复盘朋友圈内容表现", "completed", "2026-08-15T09:20:00Z", "succeeded"),
  task("task-failed", "处理拼多多价格异常", "failed", "2026-08-15T09:25:00Z", "failed"),
  task("task-cancelled", "中差评挽回跟进", "cancelled", "2026-08-15T09:28:00Z", "cancelled"),
  task("task-tomorrow", "准备明日会员分层复盘", "pending", "2026-08-15T09:45:00Z"),
];
const cockpitCore = (createdTask, statusFilter = "") => {
  const items = createdTask ? [createdTask, ...baseTasks] : baseTasks;
  const filtered = statusFilter ? items.filter((item) => item.status === statusFilter) : items;
  return { schemaVersion: "aos.ecommerce-workshop.task-cockpit/v1", tenant, evaluatedAt: cutoff, taskCutoff: cutoff, stateConsistency: "current_state_per_page", readiness: "degraded", blockers: [warning], items: filtered, page: pageInfo(filtered.length) };
};

const exactRef = (resourceType, resourceId, fill = "a") => ({ resourceType, resourceId, revision: 1, contentHash: `sha256:${fill.repeat(64)}`, receiptId: `receipt-${resourceId}` });
const analystMetric = (metricId, value) => ({
  metricId, status: "ready", definitionRef: exactRef("MetricDefinitionRevision", `workshop.analyst.${metricId}`), observationRef: exactRef("MetricObservation", `${metricId}-observation`, "b"), value,
  unit: "条", grain: "当前租户", window: cutoff, timezone: "Asia/Shanghai", cohortFilter: "隔离合同数据", numerator: value, denominator: 100,
  sourceRunRef: exactRef("SourceRun", `${metricId}-source`, "c"), qualityRef: exactRef("QualityReceipt", `${metricId}-quality`, "d"), reconciliationRef: exactRef("ReconciliationReceipt", `${metricId}-reconciliation`, "e"), lineageId: `${metricId}:lineage`, blockers: [],
});
const analystViews = ["overview", "drivers", "diagnosis", "plan", "effects", "evidence", "quality"].map((viewId) => {
  const metrics = viewId === "overview" ? [analystMetric("order_count", 124), analystMetric("product_count", 57), analystMetric("customer_count", 54)] : viewId === "quality" ? [analystMetric("failed_source_count", 2), analystMetric("stale_source_count", 1)] : [];
  return { viewId, status: "ready", resourceRevision: 1, dataCutoff: cutoff, readinessAxes: ["metric_query", "model", "eval", "plan_materialization", "professional_handoff"].map((axis) => ({ axis, status: "not_applicable", exactRef: null, blockers: [] })), metrics, authorityRefs: [], blockers: [], countLedger: { denominator: metrics.length, ready: metrics.length, unknown: 0, blocked: 0, conflict: 0 } };
});
const analyst = { schemaVersion: "aos.ecommerce-workshop.analyst-view/v1", tenant, resourceRevision: 1, evaluatedAt: cutoff, dataCutoff: cutoff, readiness: "degraded", views: analystViews, page: { limit: 100, count: 5, hasMore: false, nextCursor: null } };

const capabilityIds = ["material.collect", "strategy.plan", "copy.generate", "script.compose", "speech.synthesize", "video.compose", "content.review", "live.orchestrate", "platform.adapt", "performance.review"];
const capabilities = { tenant, count: 10, availableCount: 8, items: capabilityIds.map((capabilityId, index) => ({ capabilityId, revision: index + 1, displayName: capabilityId, lifecycle: "published", aliases: [], riskLevel: "medium", requiredDataRefs: [], requiredToolRefs: [], requiredCapabilityRefs: [], readiness: index === 1 ? "degraded" : index === 2 ? "blocked" : "available", readinessReasons: index === 1 ? ["DATA_FRESHNESS_LIMITED"] : index === 2 ? ["BINDING_REQUIRED"] : [], contentHash: String(index + 1).repeat(64).slice(0, 64) })) };
const agents = { tenant, items: [{ template: { templateId: "ecommerce.content_officer", revision: 3, displayName: "内容官", roleKey: "content_officer", lifecycle: "published", sourceRef: { resourceType: "AgentTemplate", resourceId: "content-officer", revision: "3", authority: "aip-agent-registry" }, sourceLicense: "internal", manifest: { logicIds: ["ecommerce.content.production"], responsibility: "内容生产", runtimeReadiness: "runnable", blockers: [] }, contentHash: rawHash }, instance: null, skills: [{ skillId: "ecommerce.skill.material-collect", revision: 2, canonicalLogicId: "ecommerce.content.production", lifecycle: "published", requiredCapabilities: ["material.collect"], riskLevel: "medium", contentHash: "b".repeat(64), logicRevisionRef: null }], requiredCapabilityIds: ["material.collect"], runtimeReadiness: "blocked", blockers: ["INSTANCE_NOT_INSTALLED"] }], stats: { definitionCount: 1, installedCount: 0, runnableCount: 0, skillDefinitionCount: 1, capabilityDefinitionCount: 10 } };

const assetRef = (assetType, assetId, revision = 1) => ({ assetType, assetId, revision, contentHash: rawHash });
const artifact = (artifactId, fill = "b") => ({ artifactType: "MemoryPayload", artifactId, revision: "1", contentHash: fill.repeat(64) });
const source = (licenseId) => ({ sourceKind: "task_outcome", sourceRef: { resourceType: "TaskRun", resourceId: "run-task-active", revision: "1", authority: "aip-task-runtime" }, observedAt: "2026-08-15T08:30:00Z", freshnessExpiresAt: "2026-09-15T08:30:00Z", licenseId, usagePolicy: "internal_only", contentHash: "c".repeat(64), provider: "aos", providerVersion: "1", applicability: ["ecommerce.customer-service"] });
const observations = [
  { tenant, observationId: "observation-success", agentInstanceRef: assetRef("AgentInstance", "agent-customer-service", 3), metricDefinitionRef: assetRef("MetricDefinition", "aip.task_success_rate"), evalContractRef: assetRef("EvalContract", "aip.customer-service"), evalReportRef: null, baselineCohortRef: null, treatmentCohortRef: null, exposureRefs: [], metrics: [], quality: "unknown", sourceRefs: [], cutoffAt: "2026-08-15T09:00:00Z", observedAt: "2026-08-15T09:30:00Z", conclusion: "insufficient_evidence", limitations: ["样本量不足"], observationHash: "d".repeat(64) },
  { tenant, observationId: "observation-thin", agentInstanceRef: assetRef("AgentInstance", "agent-content-officer", 2), metricDefinitionRef: assetRef("MetricDefinition", "aip.human_edit_rate"), evalContractRef: assetRef("EvalContract", "aip.content-officer"), evalReportRef: null, baselineCohortRef: null, treatmentCohortRef: null, exposureRefs: [], metrics: [], quality: "unknown", sourceRefs: [], cutoffAt: "2026-08-15T09:00:00Z", observedAt: "2026-08-15T09:40:00Z", conclusion: "insufficient_evidence", limitations: ["样本量不足"], observationHash: "e".repeat(64) },
];
const candidates = [
  { tenant, candidateId: "candidate-pending", status: "pending", scope: "workspace", version: 1, createdAt: "2026-08-15T09:10:00Z", updatedAt: "2026-08-15T09:10:00Z", quarantineReasons: [], request: { candidateLayer: "semantic", taskId: "task-active", runId: "run-task-active", subject: { resourceType: "Playbook", resourceId: "customer-service.allergy", authority: "aip-memory" }, payload: artifact("payload-pending"), source: source("internal-license"), confidence: 0.8, marking: ["internal"] } },
  { tenant, candidateId: "candidate-quarantined", status: "quarantined", scope: "workspace", version: 1, createdAt: "2026-08-15T09:20:00Z", updatedAt: "2026-08-15T09:20:00Z", quarantineReasons: ["来源许可未确认"], request: { candidateLayer: "episodic", taskId: "task-active", runId: "run-task-active", subject: { resourceType: "Playbook", resourceId: "content.publish-window", authority: "aip-memory" }, payload: artifact("payload-quarantined"), source: source("unknown-license"), confidence: 0.5, marking: ["internal"] } },
];
const memories = [{ item: { tenant, memoryItemId: "memory-promoted", memoryLayer: "semantic", status: "active", scope: "workspace", currentRevision: 3, version: 3, subject: { resourceType: "Playbook", resourceId: "customer-service.allergy", authority: "aip-memory" }, createdAt: "2026-08-15T09:30:00Z", updatedAt: "2026-08-15T09:30:00Z" }, revision: { tenant, memoryItemId: "memory-promoted", revision: 3, candidateId: "candidate-approved", contentHash: "f".repeat(64), sourceId: "source-1", sourceRevision: 1, payload: artifact("payload-promoted", "f"), confidence: 0.9, applicability: ["ecommerce.customer-service"], markings: ["internal"], effectiveAt: "2026-08-15T09:30:00Z", createdBy: "reviewer-1", createdAt: "2026-08-15T09:30:00Z" } }];

const scenarioBlocker = { code: "RUNTIME_AUTHORITY_NOT_AVAILABLE", dependency: "task-runtime", requiredAction: "attach exact runtime evidence" };
const dispatchScenario = { schemaVersion: "aos.ecommerce-workshop.dispatch-scenario/v1", status: "blocked", rootTaskGraphRef: null, rootTaskRunRef: null, dispatchBindingHash: null, evaluatedAt: cutoff, composition: { atomicSkillRefs: [], logicRevisionRef: null, roleBindings: [] }, stages: [], ledger: { tasksExpected: 0, tasksObserved: 0, handoffsExpected: 0, handoffsObserved: 0, decisionsExpected: 0, decisionsRecorded: 0, accepted: 0, rejected: 0, requestMore: 0, returned: 0, takeoverRequested: 0, takeoverDecided: 0, activeOwnerCount: 0 }, outcomeAxes: [], blockers: [scenarioBlocker], commands: { dispatch: false, decideHandoff: false, requestTakeover: false, approveTakeover: false, mutateOwner: false }, externalEffectsAllowed: false };
const batchScenario = { schemaVersion: "aos.ecommerce-workshop.batch-scenario/v1", status: "blocked", batchPreparationRevisionRef: null, batchStartDecisionRef: null, batchStartBindingHash: null, evaluatedAt: cutoff, composition: { atomicSkillRefs: [], logicRevisionRef: null, roleBindings: [] }, preparationDecisions: [], childOutcomes: [], stages: [], ledger: { frozenTotal: 0, included: 0, excluded: 0, blocked: 0, preparationUnknown: 0, childrenExpected: 0, childrenObserved: 0, succeeded: 0, failed: 0, cancelled: 0, childUnknown: 0, reconciled: 0, reconcileReceiptsObserved: 0 }, outcomeAxes: [], sideEffectLedger: { prepareExternalCalls: 0, providerCalls: 0, actionAttempts: 0, externalEffects: 0 }, blockers: [scenarioBlocker], commands: { prepare: false, start: false, cancel: false, reconcile: false }, automaticRetryAllowed: false, externalEffectsAllowed: false, releaseAllowed: false };

function reply(route, body, status = 200) { return route.fulfill({ status, contentType: "application/json; charset=utf-8", body: JSON.stringify(body) }); }
async function installRoutes(page) {
  const requests = []; const responses = []; const unknownGets = []; const taskPosts = []; let createdTask = null; let coreReadsAfterPost = 0;
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request(); const url = new URL(request.url()); const pathname = url.pathname; const method = request.method(); const headers = request.headers();
    const record = { method, pathname, search: url.search, orgId: headers["x-org-id"] ?? null, projectId: headers["x-project-id"] ?? null };
    requests.push(record);
    if (method === "POST" && pathname === "/api/v1/aip/tasks") {
      let body; try { body = request.postDataJSON(); } catch { body = null; }
      const entry = { ...record, idempotencyKey: headers["idempotency-key"] ?? null, body };
      taskPosts.push(entry);
      createdTask = task("fixture-task-1", body?.title ?? "无效任务", "pending", cutoff);
      createdTask.taskType = body?.type ?? "";
      const snapshot = { id: createdTask.taskId, type: createdTask.taskType, title: createdTask.title, description: body?.description ?? "", status: "pending", priority: body?.priority ?? 50, goal: body?.goal ?? {}, selectionRef: null, policyRevision: null, createdBy: { actorType: "user", actorId: "operator" }, createdAt: cutoff, currentPlanRevisionId: null, version: 1, updatedAt: cutoff };
      return reply(route, snapshot);
    }
    if (method !== "GET") return reply(route, { code: "AR2_7E_UNAUTHORIZED_WRITE", message: "write denied" }, 405);
    if (pathname === "/api/v1/me") return reply(route, { subject: "ar2-7e-cockpit", ...tenant, workspaceName: "AR2-7E 隔离验收", roles: ["operator"], markings: ["public"], tokenKind: "fixture" });
    if (pathname === "/api/v1/orgs") return reply(route, { items: [{ id: tenant.orgId, name: tenant.orgId }], currentOrgId: tenant.orgId });
    if (pathname === "/api/v1/workspaces") return reply(route, { items: [{ id: tenant.projectId, orgId: tenant.orgId, name: "AR2-7E 隔离验收" }], currentProjectId: tenant.projectId });
    if (pathname === "/api/v1/health") return reply(route, { status: "ok" });
    if (pathname === "/api/v1/ecommerce-workshop/modules") return reply(route, { schemaVersion: "aos.ecommerce-workshop/v1", tenant, evaluatedAt: cutoff, dataCutoff: cutoff, items: modules, count: modules.length });
    if (pathname === "/api/v1/ecommerce-workshop/views/task-cockpit") { if (createdTask) coreReadsAfterPost += 1; return reply(route, cockpitCore(createdTask, url.searchParams.get("status") ?? "")); }
    if (pathname === "/api/v1/ecommerce-workshop/views/task-cockpit/dispatch-scenario") return reply(route, dispatchScenario);
    if (pathname === "/api/v1/ecommerce-workshop/views/task-cockpit/batch-scenario") return reply(route, batchScenario);
    if (pathname === "/api/v1/ecommerce-workshop/views/analyst") return reply(route, analyst);
    if (pathname === "/api/v1/aip/capability-catalog") return reply(route, capabilities);
    if (pathname === "/api/v1/aip/agent-registry") return reply(route, agents);
    if (pathname === "/api/v1/aip/memory-authority/improvement-observations") return reply(route, observations);
    if (pathname === "/api/v1/aip/memory-authority/candidates") return reply(route, candidates);
    if (pathname === "/api/v1/aip/memory-authority/memories") return reply(route, memories);
    if (pathname === "/api/v1/ecommerce-workshop/source-readiness") return reply(route, { schemaVersion: "aos.ecommerce-workshop.source-readiness/v1", tenant, checkedAt: cutoff, cutoffAt: cutoff, status: "empty", sources: [], receiptRef: null, investigation: null });
    unknownGets.push(pathname); return reply(route, { code: "UNDECLARED_COCKPIT_FIXTURE", message: pathname }, 418);
  });
  page.on("response", (response) => { if (response.url().includes("/api/v1/")) responses.push({ pathname: new URL(response.url()).pathname, status: response.status() }); });
  return { requests, responses, unknownGets, taskPosts, get coreReadsAfterPost() { return coreReadsAfterPost; } };
}

async function dialogInsideViewport(dialog, viewport) {
  const box = await dialog.boundingBox();
  return Boolean(box && box.x >= -1 && box.y >= -1 && box.x + box.width <= viewport.width + 1 && box.y + box.height <= viewport.height + 1);
}
async function runUnit(browser, viewport) {
  const context = await browser.newContext({ viewport });
  await context.addInitScript((value) => sessionStorage.setItem("aos-tenant-v1", JSON.stringify(value)), { ...tenant, workspaceName: "AR2-7E 隔离验收", subject: "ar2-7e-cockpit", roles: ["operator"] });
  const page = await context.newPage(); const pageErrors = []; const consoleErrors = []; const failures = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("console", (message) => { if (message.type() === "error") consoleErrors.push(message.text()); });
  const transport = await installRoutes(page);
  const observed = { recommendation: null, preflightPosts: null, taskPost: null, readbackMatched: false, colleagues: [], capabilities: [], reviews: [], roleColumns: 0, tomorrow: null, calendar: false, filterRoundTrip: false, sidebarRoundTrip: false, scrollEnd: false };
  try {
    await page.goto(`${baseUrl}/workshop/cockpit`, { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.locator('.ecommerce-workshop-shell[data-module-id="ecommerce.task-cockpit"]').waitFor({ timeout: 10000 });
    const recommendation = page.locator(".task-cockpit-recommendation", { hasText: "复盘订单与商品规模" });
    await recommendation.waitFor({ timeout: 10000 });
    observed.recommendation = { label: (await recommendation.textContent())?.trim(), definitionRef: await recommendation.getAttribute("data-definition-ref"), observationRef: await recommendation.getAttribute("data-observation-ref") };
    await recommendation.click();
    const input = page.locator('input[aria-label="任务指令"]'); const commandText = await input.inputValue();
    if (!commandText.includes("栖月汇微商城") || !commandText.includes("124 笔订单")) failures.push("recommendation_fill_mismatch");
    await page.getByRole("button", { name: "下达", exact: true }).click();
    await page.getByText("安全预检通过", { exact: false }).waitFor();
    observed.preflightPosts = transport.taskPosts.length;
    if (observed.preflightPosts !== 0) failures.push(`preflight_posts_${observed.preflightPosts}`);
    await page.getByRole("button", { name: "确认下达", exact: true }).click();
    await page.getByText("已在任务流回读", { exact: false }).waitFor({ timeout: 10000 });
    observed.readbackMatched = (await page.locator("main").innerText()).includes("fixture-task-1");
    const post = transport.taskPosts[0];
    observed.taskPost = post ?? null;
    if (transport.taskPosts.length !== 1) failures.push(`task_posts_${transport.taskPosts.length}`);
    if (!post?.idempotencyKey?.startsWith("workshop-task-")) failures.push("idempotency_key_missing");
    if (post?.body?.type !== "ecommerce.workshop.business_task") failures.push("task_type_mismatch");
    if (post?.body?.goal?.workshopAssignment?.roleKey !== "shopping_advisor") failures.push("recommended_role_mismatch");
    if (!post?.body?.goal?.sourceEvidence?.definitionRef?.includes("order_count@1")) failures.push("source_definition_missing");
    if (!post?.body?.goal?.sourceEvidence?.observationRef?.includes("order_count-observation@1")) failures.push("source_observation_missing");
    if (!observed.readbackMatched || transport.coreReadsAfterPost < 1) failures.push("task_readback_missing");

    const colleagues = page.locator("[data-colleague-role]");
    for (let index = 0; index < await colleagues.count(); index += 1) {
      const trigger = colleagues.nth(index); const role = await trigger.getAttribute("data-colleague-role"); await trigger.click();
      const dialog = page.locator('[role="dialog"][aria-label$="介绍"]'); await dialog.waitFor();
      const inside = await dialogInsideViewport(dialog, viewport); observed.colleagues.push({ role, inside }); if (!inside) failures.push(`colleague_dialog_overflow_${role}`);
      await dialog.getByRole("button", { name: "关闭数字同事介绍" }).click();
    }
    const capabilityButtons = page.locator(".task-cockpit-visual-skills button");
    for (let index = 0; index < await capabilityButtons.count(); index += 1) {
      const trigger = capabilityButtons.nth(index); const label = ((await trigger.textContent()) ?? "").trim(); await trigger.click();
      const dialog = page.locator('[role="dialog"][aria-label$="贡献链"]'); await dialog.waitFor();
      const inside = await dialogInsideViewport(dialog, viewport); observed.capabilities.push({ label, inside }); if (!inside) failures.push(`capability_dialog_overflow_${index}`);
      await dialog.getByRole("button", { name: "关闭共享能力详情" }).click();
    }

    observed.reviews = await page.locator(".task-cockpit-review-section").evaluateAll((items) => items.map((item) => item.getAttribute("aria-label")));
    observed.roleColumns = await page.locator(".task-cockpit-visual-role-column").count();
    observed.tomorrow = ((await page.locator(".task-cockpit-visual-tomorrow").innerText()) ?? "").trim();
    if (observed.reviews.length !== 3) failures.push(`review_sections_${observed.reviews.length}`);
    if (observed.roleColumns !== 2) failures.push(`role_columns_${observed.roleColumns}`);
    if (!observed.tomorrow.includes("2 项待规划")) failures.push("tomorrow_pending_mismatch");
    if (!(await page.locator("main").innerText()).includes("样本量不足")) failures.push("memory_review_missing");

    const status = page.locator(".task-cockpit-visual-command select"); await status.selectOption("completed");
    await page.locator(".task-cockpit-visual-task-column").getByText("复盘朋友圈内容表现", { exact: true }).waitFor(); await status.selectOption(""); await page.locator(".task-cockpit-visual-task-column").getByText(commandText, { exact: true }).waitFor(); observed.filterRoundTrip = true;
    await page.evaluate(() => window.dispatchEvent(new Event("aos-workshop-cockpit-calendar")));
    await page.locator(".task-cockpit-calendar-preview").waitFor(); observed.calendar = true; await page.getByRole("button", { name: "返回任务流" }).click();
    await page.getByRole("button", { name: "折叠侧栏" }).click(); await page.getByRole("button", { name: "展开侧栏" }).click(); observed.sidebarRoundTrip = true;
    observed.scrollEnd = await page.locator(".content").evaluate((node) => { node.scrollTop = node.scrollHeight; return Math.abs(node.scrollTop + node.clientHeight - node.scrollHeight) <= 2; });

    const navCount = await page.locator(".nav [data-workshop-module-id]").count(); const h1Count = await page.locator("h1").count();
    const layout = await page.evaluate(() => ({ clientWidth: document.documentElement.clientWidth, scrollWidth: document.documentElement.scrollWidth, horizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1 }));
    const workshopWrites = transport.requests.filter((item) => item.pathname.startsWith("/api/v1/ecommerce-workshop/") && item.method !== "GET");
    const otherWrites = transport.requests.filter((item) => item.method !== "GET" && !(item.method === "POST" && item.pathname === "/api/v1/aip/tasks"));
    const tenantDrift = transport.requests.filter((item) => item.pathname.startsWith("/api/v1/ecommerce-workshop/") && (item.orgId !== tenant.orgId || item.projectId !== tenant.projectId));
    if (navCount !== 8) failures.push(`nav_count_${navCount}`); if (h1Count !== 1) failures.push(`h1_count_${h1Count}`);
    if (observed.colleagues.length !== 6) failures.push(`colleague_count_${observed.colleagues.length}`); if (observed.capabilities.length !== 10) failures.push(`capability_count_${observed.capabilities.length}`);
    if (!observed.calendar || !observed.filterRoundTrip || !observed.sidebarRoundTrip || !observed.scrollEnd) failures.push("interaction_roundtrip_incomplete");
    if (layout.horizontalOverflow) failures.push("horizontal_overflow"); if (workshopWrites.length) failures.push("workshop_write_detected"); if (otherWrites.length) failures.push("other_write_detected");
    if (tenantDrift.length) failures.push("tenant_header_drift"); if (transport.unknownGets.length) failures.push(`unknown_get_${transport.unknownGets.join("|")}`);
    if (transport.responses.some((item) => item.status >= 500)) failures.push("http_5xx"); if (pageErrors.length) failures.push("page_errors"); if (consoleErrors.length) failures.push("console_errors");
    await page.screenshot({ path: path.join(evidenceDir, `ar2-7e-task-cockpit-rich-${viewport.width}x${viewport.height}.png`), fullPage: true });
    return { viewport, result: failures.length ? "FAIL" : "PASS", failures, observed, navCount, h1Count, layout, pageErrors, consoleErrors, workshopWrites, otherWrites, ...transport };
  } catch (error) {
    failures.push(error instanceof Error ? error.message : String(error));
    await page.screenshot({ path: path.join(evidenceDir, `ar2-7e-task-cockpit-rich-diagnostic-${viewport.width}x${viewport.height}.png`), fullPage: true }).catch(() => {});
    return { viewport, result: "FAIL", failures, observed, pageErrors, consoleErrors, ...transport };
  } finally { await context.close(); }
}

const browser = await chromium.launch({ executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", headless: true });
const results = []; let consecutiveFailures = 0; let stoppedEarly = false;
try {
  for (const viewport of viewports) {
    const result = await runUnit(browser, viewport); results.push(result); console.log(`${viewport.width}x${viewport.height}: ${result.result}${result.failures.length ? ` ${result.failures.join(",")}` : ""}`);
    consecutiveFailures = result.result === "PASS" ? 0 : consecutiveFailures + 1;
    if (consecutiveFailures >= 2) { stoppedEarly = true; break; }
  }
} finally { await browser.close(); }
const counts = { passed: results.filter((item) => item.result === "PASS").length, total: results.length, taskPosts: results.reduce((sum, item) => sum + item.taskPosts.length, 0), preflightPosts: results.reduce((sum, item) => sum + (item.observed.preflightPosts ?? 0), 0), colleagues: results.reduce((sum, item) => sum + item.observed.colleagues.length, 0), capabilities: results.reduce((sum, item) => sum + item.observed.capabilities.length, 0), workshopWrites: results.reduce((sum, item) => sum + (item.workshopWrites?.length ?? 0), 0), otherWrites: results.reduce((sum, item) => sum + (item.otherWrites?.length ?? 0), 0), unknownGets: results.reduce((sum, item) => sum + item.unknownGets.length, 0), pageErrors: results.reduce((sum, item) => sum + item.pageErrors.length, 0), consoleErrors: results.reduce((sum, item) => sum + item.consoleErrors.length, 0), stoppedEarly };
const evidence = { schemaVersion: "aos.ar2-7e-task-cockpit-rich-browser/v1", generatedAt: new Date().toISOString(), baseUrl, authority: "AOS-000572 / AR2_7D_RUNTIME_WIRING_CANONICAL_ROUTER_GREEN", fixtureBoundary: "isolated contract data; the sole task POST is intercepted before backend transport", result: results.length === 3 && results.every((item) => item.result === "PASS") ? "PASS" : "FAIL", counts, results, boundaries: ["No fixture request reached a real AOS write handler or database.", "All Workshop requests remained tenant-scoped GET.", "No Provider, publication, customer contact, payment, migration, release, or push was attempted."] };
fs.writeFileSync(path.join(evidenceDir, "ar2-7e-task-cockpit-rich-browser.json"), `${JSON.stringify(evidence, null, 2)}\n`);
console.log(JSON.stringify({ result: evidence.result, counts }, null, 2));
if (evidence.result !== "PASS") process.exitCode = 1;
