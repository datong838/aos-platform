import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";

const evidenceDir = path.dirname(fileURLToPath(import.meta.url));
const baseUrl = "http://127.0.0.1:8434";
const tenant = { orgId: "org-org", projectId: "dev-project" };
const cutoff = "2026-08-24T13:00:00Z";
const rawHash = (fill = "a") => fill.repeat(64);
const hash = (fill = "a") => `sha256:${rawHash(fill)}`;
const viewports = [{ width: 1280, height: 720 }, { width: 1440, height: 900 }, { width: 1920, height: 1080 }];
const sliceIds = ["orders", "orderLines", "inventory", "shipments", "payments", "aftersaleEvents", "operationCases"];
const commandIds = ["classify", "createCase", "changeMembership", "manageSla", "automationKill", "refund"];
const moduleSpecs = [
  ["ecommerce.task-cockpit", "任务总控", "/workshop/cockpit"], ["ecommerce.content-campaign", "内容活动", "/workshop/content-campaign"],
  ["ecommerce.operations", "运营履约", "/workshop/operations"], ["ecommerce.creator-growth", "达人增长", "/workshop/creator-growth"],
  ["ecommerce.media-studio", "媒体工坊", "/workshop/media-studio"], ["ecommerce.analyst", "经营分析", "/workshop/analyst"],
  ["ecommerce.price-governance", "价格治理", "/workshop/price-governance"], ["ecommerce.customer", "客户经营", "/workshop/customer"],
];
const modules = moduleSpecs.map(([moduleId, label, route], index) => ({
  moduleId, displayName: label, menuLabel: label, route, slot: "workshop.primary.ecommerce", order: index + 1,
  installationRef: { installationId: `11111111-1111-4111-8111-${String(index + 1).padStart(12, "0")}`, revision: 8, compositionId: `22222222-2222-4222-8222-${String(index + 1).padStart(12, "0")}`, lockRevision: 12, lockHash: hash(), overlayRevision: "ar2-7e-operations-rich-r1" },
  moduleRef: { publisher: "aos.ecommerce", bundleId: "solution.ecommerce.operations", version: "1.0.0", bundleContentHash: hash(), moduleArtifactRef: `bundle://${moduleId}`, moduleArtifactHash: hash() },
  readiness: "available", blockers: [], permissions: { roles: ["operator"], markings: ["public"], dataScopes: ["ecommerce:read"], actionTypes: [] },
  requiredObjects: [], requiredCapabilities: [], requiredAipFeatures: [], viewRefs: [], evalPackRefs: [], productionContractRefs: [], responsibilityTemplateRefs: [], impactCalculatorRefs: [], legacyAssetRefs: [], legacyRoutes: [], minimumRuntimeVersion: "1.0.0", dependencyRefs: [], lastReceiptRef: null,
}));

const authorityRef = (sliceId, index) => ({ resourceType: "ReadAuthority", resourceId: `isolated:${sliceId}:${index + 1}`, revision: index + 1, contentHash: hash(String((index % 6) + 1)), receiptId: `receipt-isolated-${sliceId}` });
const ledgers = [[4, 3, 1, 0], [5, 5, 0, 0], [3, 2, 0, 1], [2, 2, 0, 0], [4, 4, 0, 0], [2, 2, 0, 0], [2, 2, 0, 0]];
const operationsView = {
  schemaVersion: "aos.ecommerce-workshop.operations-view/v1", tenant, evaluatedAt: cutoff, dataCutoff: cutoff, readiness: "degraded",
  slices: sliceIds.map((sliceId, index) => ({ sliceId, status: "ready", dataCutoff: cutoff, authorityRefs: [authorityRef(sliceId, index)], blockers: [], countLedger: { sourceTotal: ledgers[index][0], attached: ledgers[index][1], unmatched: ledgers[index][2], conflicted: ledgers[index][3] } })),
  page: { limit: 50, count: 20, hasMore: false, nextCursor: null },
};
const commandReadiness = {
  schemaVersion: "aos.ecommerce-workshop.operation-command-readiness/v1", tenant, evaluatedAt: cutoff,
  commands: commandIds.map((commandId, index) => ({ commandId, label: ["分类事件", "创建运营工单", "调整工单成员", "管理服务时限", "停止自动化", "退款"][index], status: "blocked", risk: index > 3 ? "high" : "controlled", sideEffect: index === 5 ? "external" : "internalAuthority", blockers: [{ code: index === 5 ? "EXTERNAL_ACTION_GATE_NOT_BOUND" : "OPERATION_COMMAND_HANDLER_NOT_BOUND", dependency: "AR2_7E_ISOLATED_ACCEPTANCE", requiredAction: "保持命令关闭，仅验证页面预检" }] })),
};
const workspaceRef = (resourceType, resourceId, fill) => ({ tenant, resourceType, resourceId, contentHash: rawHash(fill), sourceUpdatedAt: cutoff });
const inventoryRef = workspaceRef("ProductSku", "isolated:sku:74", "c");
const aftersaleRef = workspaceRef("AftersaleEvent", "isolated:aftersale:29", "d");
const operationWorkspace = {
  schemaVersion: "aos.ecommerce-workshop.operation-case-workspace/v1", tenant, status: "ready", evaluatedAt: cutoff, dataCutoff: cutoff,
  sources: ["orders", "inventory", "shipments", "aftersaleEvents", "payments", "operationCases"].map((sourceId, index) => ({ sourceId, status: "ready", count: [1, 1, 0, 1, 0, 0][index], blocker: null })),
  cases: [],
  candidates: [
    { candidateId: rawHash("d"), kind: "inventory_data_gap", title: "隔离库存资料待核对", summary: "隔离 SKU 的数量差异需要内部核对。", priority: "high", memberRefs: [inventoryRef], externalEffectAllowed: false },
    { candidateId: rawHash("e"), kind: "aftersale_followup", title: "隔离售后事件待跟进", summary: "隔离售后事件仅形成内部跟进建议。", priority: "normal", memberRefs: [aftersaleRef], externalEffectAllowed: false },
  ],
  availableRefs: [inventoryRef, aftersaleRef],
  ledger: { sourceTotal: 3, assigned: 1, unassigned: 2, candidates: 2, openCases: 0, pausedCases: 0, closedCases: 0 }, externalEffectAllowed: false,
};
const observation = { schemaVersion: "aos.ecommerce-workshop.operation-command-observation/v1", tenant, proposalId: "proposal-isolated-observation", leaseId: "lease-isolated-observation", commandId: "classify", status: "applied", proposalHash: rawHash("a"), receiptId: "action-receipt-isolated-1", requestFingerprint: rawHash("b"), operationReceiptId: "operation-receipt-isolated-1", replayAllowed: false };

function draftSnapshot(draftId, revision, body) { return { draftId, revision, version: revision, lifecycle: "editable", request: body, actionTypeRevisionHash: rawHash("a"), riskLevel: "R2", approvalPolicyHash: rawHash("b"), contentHash: rawHash(draftId.endsWith("v1") ? "c" : "d"), submittedProposalId: null, createdBy: { actorType: "user", actorId: "ar2-7e-operator" }, createdAt: cutoff }; }
function bundle(version, status = "drafted") {
  const suffix = version === 1 ? "v1" : "v2"; const proposalHash = rawHash(version === 1 ? "e" : "f");
  return { proposal: { id: `proposal-isolated-${suffix}`, actionType: { actionTypeId: "ecommerce.operation.create-case", revisionHash: rawHash("a"), objectType: "OperationCase" }, taskId: null, runId: null, objectRef: { resourceType: "ProductSku", resourceId: inventoryRef.resourceId, revision: inventoryRef.contentHash, authority: "ecommerce-workshop.operation-case-workspace" }, impactPreviewRef: null, purpose: "隔离库存资料待核对", riskLevel: "R2", payload: { candidateId: rawHash("d"), priority: version === 1 ? "high" : "normal", summary: "核对正式来源，确认差异后再决定内部处置路径。", memberRefs: [inventoryRef], externalEffectAllowed: false }, proposalHash, status, expiresAt: "2099-01-01T00:00:00.000Z", version, createdBy: { actorType: "user", actorId: "ar2-7e-operator" }, createdAt: cutoff, updatedAt: cutoff, clientRiskHint: "R2", policySnapshot: {}, diff: {}, evidenceRefs: [{ resourceType: "ProductSku", resourceId: inventoryRef.resourceId, revision: inventoryRef.contentHash, authority: "ecommerce-workshop.operation-case-workspace" }], actionBindingHash: null, approvalPolicyHash: rawHash("b"), sourceDraftRef: { resourceType: "ActionDraftRevision", resourceId: `draft-isolated-${suffix}`, revision: 1, contentHash: rawHash(version === 1 ? "c" : "d") }, compensationOriginalProposalId: null, compensationOriginalReceiptId: null, compensationPolicyRef: null, compensationEffect: null, compensationResidualEffect: null }, draft: { id: `draft-isolated-${suffix}`, proposalId: `proposal-isolated-${suffix}`, proposalVersion: version, proposalHash, diff: {}, evidenceRefs: [], status: "awaiting_approval", createdAt: cutoff }, approvals: [] };
}
function reply(route, body, status = 200) { return route.fulfill({ status, contentType: "application/json; charset=utf-8", body: JSON.stringify(body) }); }

async function installRoutes(page) {
  const requests = []; const responses = []; const unknownGets = []; const actionWrites = []; let viewReads = 0; let workspaceReads = 0; let readinessReads = 0; let observationReads = 0; let draftCreates = 0; let draftSubmits = 0;
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request(); const url = new URL(request.url()); const pathname = url.pathname; const method = request.method(); const headers = request.headers();
    let body = null; if (method !== "GET") { try { body = request.postDataJSON(); } catch { body = null; } }
    const record = { method, pathname, orgId: headers["x-org-id"] ?? null, projectId: headers["x-project-id"] ?? null, idempotencyKey: headers["idempotency-key"] ?? null, body }; requests.push(record);
    if (method === "POST" && pathname === "/api/v1/aip/action-drafts") { actionWrites.push(record); draftCreates += 1; return reply(route, draftSnapshot(`draft-isolated-v${draftCreates}`, 1, body)); }
    if (method === "POST" && /^\/api\/v1\/aip\/action-drafts\/draft-isolated-v[12]\/submit$/.test(pathname)) { actionWrites.push(record); draftSubmits += 1; return reply(route, bundle(draftSubmits)); }
    if (method === "POST" && pathname === "/api/v1/aip/action-proposals/proposal-isolated-v2/withdraw") { actionWrites.push(record); return reply(route, bundle(2, "withdrawn")); }
    if (method !== "GET") return reply(route, { code: "AR2_7E_UNAUTHORIZED_WRITE", message: "write denied" }, 405);
    if (pathname === "/api/v1/me") return reply(route, { subject: "ar2-7e-operations", ...tenant, workspaceName: "AR2-7E 隔离验收", roles: ["operator"], markings: ["public"], tokenKind: "fixture" });
    if (pathname === "/api/v1/orgs") return reply(route, { items: [{ id: tenant.orgId, name: tenant.orgId }], currentOrgId: tenant.orgId });
    if (pathname === "/api/v1/workspaces") return reply(route, { items: [{ id: tenant.projectId, orgId: tenant.orgId, name: "AR2-7E 隔离验收" }], currentProjectId: tenant.projectId });
    if (pathname === "/api/v1/health") return reply(route, { status: "ok" });
    if (pathname === "/api/v1/ecommerce-workshop/modules") return reply(route, { schemaVersion: "aos.ecommerce-workshop/v1", tenant, evaluatedAt: cutoff, dataCutoff: cutoff, items: modules, count: modules.length });
    if (pathname === "/api/v1/ecommerce-workshop/views/operations") { viewReads += 1; return reply(route, operationsView); }
    if (pathname === "/api/v1/ecommerce-workshop/views/operations/cases") { workspaceReads += 1; return reply(route, operationWorkspace); }
    if (pathname === "/api/v1/ecommerce-workshop/commands/operations/readiness") { readinessReads += 1; return reply(route, commandReadiness); }
    if (pathname === "/api/v1/ecommerce-workshop/commands/operations/observations/proposal-isolated-observation/leases/lease-isolated-observation") { observationReads += 1; return reply(route, observation); }
    if (pathname === "/api/v1/aip/action-proposals/proposal-isolated-v1/timeline") return reply(route, { bundle: bundle(1), events: [{ eventId: "event-isolated-submitted", eventType: "submitted", actorId: "ar2-7e-operator", proposalVersion: 1, proposalHash: rawHash("e"), payload: {}, createdAt: cutoff }] });
    if (pathname === "/api/v1/ecommerce-workshop/source-readiness") return reply(route, { schemaVersion: "aos.ecommerce-workshop.source-readiness/v1", tenant, checkedAt: cutoff, cutoffAt: cutoff, status: "empty", sources: [], receiptRef: null, investigation: null });
    unknownGets.push(pathname); return reply(route, { code: "UNDECLARED_OPERATIONS_FIXTURE", message: pathname }, 418);
  });
  page.on("response", (response) => { if (response.url().includes("/api/v1/")) responses.push({ pathname: new URL(response.url()).pathname, status: response.status() }); });
  return { requests, responses, unknownGets, actionWrites, get viewReads() { return viewReads; }, get workspaceReads() { return workspaceReads; }, get readinessReads() { return readinessReads; }, get observationReads() { return observationReads; } };
}

async function runUnit(browser, viewport) {
  const context = await browser.newContext({ viewport });
  await context.addInitScript((value) => sessionStorage.setItem("aos-tenant-v1", JSON.stringify(value)), { ...tenant, workspaceName: "AR2-7E 隔离验收", subject: "ar2-7e-operations", roles: ["operator"] });
  const page = await context.newPage(); const pageErrors = []; const consoleErrors = []; const failures = [];
  page.on("pageerror", (error) => pageErrors.push(error.message)); page.on("console", (message) => { if (message.type() === "error") consoleErrors.push(message.text()); });
  const transport = await installRoutes(page);
  const observed = { filters: [], searches: [], details: [], workflow: [], proposalVersions: [], approvalPreview: false, receiptReadback: false, refreshReadback: false, sidebarRoundTrip: false, scrollEnd: false };
  try {
    await page.goto(`${baseUrl}/workshop/operations`, { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.locator('.ecommerce-workshop-shell[data-module-id="ecommerce.operations"]').waitFor({ timeout: 10000 });
    await page.locator(".operations-read-model").waitFor();
    const mainText = (await page.locator("main").innerText());
    for (const expected of ["来源总量", "已挂接", "数据差异", "隔离库存资料待核对", "隔离售后事件待跟进"]) if (!mainText.includes(expected)) failures.push(`initial_readback_missing_${expected}`);

    const filters = page.locator(".operations-queue-filter");
    for (let index = 0; index < await filters.count(); index += 1) { const button = filters.nth(index); await button.click(); observed.filters.push(((await button.textContent()) ?? "").replace(/\d+$/, "").trim()); }
    await filters.first().click();
    const search = page.getByLabel("搜索运营待办");
    await search.fill("isolated:orders:1"); observed.searches.push("order-hit"); if (!(await page.locator(".operations-slice-switcher").textContent()).includes("订单")) failures.push("order_search_missing");
    await search.fill("isolated:no-match"); observed.searches.push("no-match"); const emptyText = await page.locator("main").textContent(); if (!(emptyText.includes("当前筛选下没有匹配的正式业务视图") && emptyText.includes("当前搜索没有匹配的内部处理候选"))) failures.push("credible_empty_missing");
    await search.fill(""); observed.searches.push("cleared");

    const switcher = page.locator(".operations-slice-switcher"); await switcher.locator("summary").click();
    await switcher.locator("button").filter({ hasText: "订单" }).first().click();
    await page.getByRole("button", { name: "查看原订单" }).click(); if (!(await page.getByRole("dialog").innerText()).includes("ReadAuthority")) failures.push("order_source_dialog_missing"); observed.details.push("order-source"); await page.getByLabel("关闭详情").click();
    await page.locator(".operations-detail-actions").getByRole("button", { name: "处理日志" }).click(); if (!(await page.getByRole("dialog").innerText()).includes("同一数据截止")) failures.push("order_log_dialog_missing"); observed.details.push("order-log"); await page.getByLabel("关闭详情").click();
    await switcher.locator("button").filter({ hasText: "售后事件" }).click();
    await page.getByRole("button", { name: "查看原始业务对象" }).click(); if (!(await page.getByRole("dialog").innerText()).includes("isolated:aftersaleEvents:6")) failures.push("aftersale_source_dialog_missing"); observed.details.push("aftersale-source"); await page.getByLabel("关闭详情").click();
    await page.locator(".operations-detail-actions").getByRole("button", { name: "处理日志" }).click(); if (!(await page.getByRole("dialog").innerText()).includes("来源 2")) failures.push("aftersale_log_counts_missing"); observed.details.push("aftersale-log"); await page.getByLabel("关闭详情").click();
    await page.getByRole("button", { name: "查看建议依据" }).click(); await page.getByText("建议仅根据当前数量守恒和正式来源生成", { exact: false }).waitFor();
    await page.getByRole("button", { name: "查看完整 SOP" }).click(); await page.getByText("核对订单、支付、履约和售后的同一截止面", { exact: false }).waitFor();
    await page.getByRole("button", { name: "完整处理 SOP" }).click(); await page.getByText("由独立审批人审核", { exact: false }).waitFor();

    const workflow = page.locator(".operations-internal-workflow");
    await workflow.getByRole("button", { name: "新建处理" }).click(); observed.workflow.push("new");
    await workflow.getByRole("button", { name: "采纳建议" }).click(); observed.workflow.push("adopt");
    await workflow.getByRole("button", { name: "保存并提交审批" }).click(); await page.getByText("内部处理提案已形成", { exact: false }).waitFor(); observed.workflow.push("create"); observed.proposalVersions.push(1);
    await workflow.getByRole("button", { name: "处理日志" }).click(); await page.getByText("submitted", { exact: true }).waitFor(); observed.workflow.push("timeline");
    await workflow.getByRole("button", { name: "修改" }).click(); await page.getByLabel("处理优先级").selectOption("normal"); await page.getByLabel("处置说明").fill("隔离替代版本：继续核对正式来源。\n");
    await workflow.getByRole("button", { name: "提交修改" }).click(); await page.getByText("修改已形成新提案", { exact: false }).waitFor(); observed.workflow.push("revise"); observed.proposalVersions.push(2);
    await workflow.getByRole("button", { name: "批准预览" }).click(); await page.getByText("需由独立审批人批准后取得执行租约", { exact: false }).waitFor(); observed.approvalPreview = true;
    await workflow.getByRole("button", { name: "驳回/撤回" }).click(); await page.getByText("未触发业务执行", { exact: false }).waitFor(); observed.workflow.push("withdraw");

    const observationForm = page.locator(".operations-observation-form"); const inputs = observationForm.locator("input");
    await inputs.nth(0).fill("proposal-isolated-observation"); await inputs.nth(1).fill("lease-isolated-observation"); await observationForm.getByRole("button", { name: "读取证据" }).click();
    await page.getByText("operation-receipt-isolated-1", { exact: false }).waitFor(); if (!(await page.locator(".operations-observation-result").innerText()).includes("禁止自动重放")) failures.push("receipt_replay_boundary_missing"); observed.receiptReadback = true;

    const readsBefore = [transport.viewReads, transport.workspaceReads, transport.readinessReads]; await page.locator(".content").evaluate((node) => { node.scrollTop = 0; }); await page.locator(".workshop-visual-header-actions").getByRole("button", { name: "重新读取" }).click(); await page.locator(".operations-read-model").waitFor();
    observed.refreshReadback = transport.viewReads > readsBefore[0] && transport.workspaceReads > readsBefore[1] && transport.readinessReads > readsBefore[2];
    await page.getByRole("button", { name: "折叠侧栏" }).click(); await page.getByRole("button", { name: "展开侧栏" }).click(); observed.sidebarRoundTrip = true;
    observed.scrollEnd = await page.locator(".content").evaluate((node) => { node.scrollTop = node.scrollHeight; return Math.abs(node.scrollTop + node.clientHeight - node.scrollHeight) <= 2; });

    const expectedPaths = ["/api/v1/aip/action-drafts", "/api/v1/aip/action-drafts/draft-isolated-v1/submit", "/api/v1/aip/action-drafts", "/api/v1/aip/action-drafts/draft-isolated-v2/submit", "/api/v1/aip/action-proposals/proposal-isolated-v2/withdraw"];
    if (JSON.stringify(transport.actionWrites.map((item) => item.pathname)) !== JSON.stringify(expectedPaths)) failures.push(`action_write_order_${transport.actionWrites.map((item) => item.pathname).join("|")}`);
    if (new Set(transport.actionWrites.map((item) => item.idempotencyKey)).size !== 5 || transport.actionWrites.some((item) => !item.idempotencyKey)) failures.push("idempotency_keys_not_unique");
    const submit1 = transport.actionWrites[1]?.body; const submit2 = transport.actionWrites[3]?.body; const withdraw = transport.actionWrites[4]?.body;
    if (submit1?.expectedRevision !== 1 || submit1?.expectedContentHash !== rawHash("c") || submit2?.expectedRevision !== 1 || submit2?.expectedContentHash !== rawHash("d") || withdraw?.expectedProposalVersion !== 2 || withdraw?.expectedProposalHash !== rawHash("f")) failures.push("cas_drift");
    if (transport.observationReads !== 1 || !observed.approvalPreview || !observed.receiptReadback || !observed.refreshReadback || !observed.sidebarRoundTrip || !observed.scrollEnd) failures.push("required_roundtrip_incomplete");
    const navCount = await page.locator(".nav [data-workshop-module-id]").count(); const h1Count = await page.locator("h1").count();
    const layout = await page.evaluate(() => ({ clientWidth: document.documentElement.clientWidth, scrollWidth: document.documentElement.scrollWidth, horizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1 }));
    const allowedWrites = new Set(expectedPaths); const otherWrites = transport.requests.filter((item) => item.method !== "GET" && !allowedWrites.has(item.pathname));
    const forbiddenWrites = transport.requests.filter((item) => item.method !== "GET" && /(decision|lease|execute|refund|shipment|publish|provider)/i.test(item.pathname));
    const tenantDrift = transport.requests.filter((item) => item.pathname.startsWith("/api/v1/ecommerce-workshop/") && (item.orgId !== tenant.orgId || item.projectId !== tenant.projectId));
    if (navCount !== 8) failures.push(`nav_count_${navCount}`); if (h1Count !== 1) failures.push(`h1_count_${h1Count}`); if (observed.filters.length !== 4 || observed.searches.length !== 3 || observed.details.length !== 4) failures.push("interaction_count_drift");
    if (layout.horizontalOverflow) failures.push("horizontal_overflow"); if (otherWrites.length) failures.push("other_write_detected"); if (forbiddenWrites.length) failures.push("forbidden_business_write_detected"); if (tenantDrift.length) failures.push("tenant_header_drift"); if (transport.unknownGets.length) failures.push(`unknown_get_${transport.unknownGets.join("|")}`);
    if (transport.responses.some((item) => item.status >= 500)) failures.push("http_5xx"); if (pageErrors.length) failures.push("page_errors"); if (consoleErrors.length) failures.push("console_errors");
    await page.screenshot({ path: path.join(evidenceDir, `ar2-7e-operations-rich-${viewport.width}x${viewport.height}.png`), fullPage: true });
    return { viewport, result: failures.length ? "FAIL" : "PASS", failures, observed, navCount, h1Count, layout, pageErrors, consoleErrors, otherWrites, forbiddenWrites, tenantDrift, ...transport };
  } catch (error) {
    failures.push(error instanceof Error ? error.message : String(error)); await page.screenshot({ path: path.join(evidenceDir, `ar2-7e-operations-rich-diagnostic-${viewport.width}x${viewport.height}.png`), fullPage: true }).catch(() => {});
    return { viewport, result: "FAIL", failures, observed, pageErrors, consoleErrors, ...transport };
  } finally { await context.close(); }
}

const browser = await chromium.launch({ executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", headless: true });
const results = []; let consecutiveFailures = 0; let stoppedEarly = false;
try { for (const viewport of viewports) { const result = await runUnit(browser, viewport); results.push(result); console.log(`${viewport.width}x${viewport.height}: ${result.result}${result.failures.length ? ` ${result.failures.join(",")}` : ""}`); consecutiveFailures = result.result === "PASS" ? 0 : consecutiveFailures + 1; if (consecutiveFailures >= 2) { stoppedEarly = true; break; } } } finally { await browser.close(); }
const counts = { passed: results.filter((item) => item.result === "PASS").length, total: results.length, actionWrites: results.reduce((sum, item) => sum + item.actionWrites.length, 0), observationReads: results.reduce((sum, item) => sum + item.observationReads, 0), otherWrites: results.reduce((sum, item) => sum + (item.otherWrites?.length ?? 0), 0), forbiddenWrites: results.reduce((sum, item) => sum + (item.forbiddenWrites?.length ?? 0), 0), unknownGets: results.reduce((sum, item) => sum + item.unknownGets.length, 0), pageErrors: results.reduce((sum, item) => sum + item.pageErrors.length, 0), consoleErrors: results.reduce((sum, item) => sum + item.consoleErrors.length, 0), stoppedEarly };
const zeroEffects = { approvalCount: 0, leaseCount: 0, executionCount: 0, refundCount: 0, shipmentMutationCount: 0, providerInvocationCount: 0, externalPublicationCount: 0, externalBusinessMutationCount: 0 };
const evidence = { schemaVersion: "aos.ar2-7e-operations-rich-browser/v1", generatedAt: new Date().toISOString(), baseUrl, authority: "AOS-000572 / AR2_7D_RUNTIME_WIRING_CANONICAL_ROUTER_GREEN", fixtureBoundary: "isolated contract records; five internal Action Proposal writes per viewport intercepted before backend transport", result: results.length === 3 && results.every((item) => item.result === "PASS") ? "PASS" : "FAIL", counts, zeroEffects, results, boundaries: ["Formal operations facts, command readiness, candidates, and observations remained GET-only.", "Approval preview was local text only; no approval, lease, execution, refund, or shipment request was made.", "No Provider, customer contact, payment, production migration, release, push, or real business mutation was attempted."] };
fs.writeFileSync(path.join(evidenceDir, "ar2-7e-operations-rich-browser.json"), `${JSON.stringify(evidence, null, 2)}\n`); console.log(JSON.stringify({ result: evidence.result, counts }, null, 2)); if (evidence.result !== "PASS") process.exitCode = 1;
