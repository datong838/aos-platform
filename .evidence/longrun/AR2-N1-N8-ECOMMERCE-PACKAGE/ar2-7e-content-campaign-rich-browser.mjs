import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";

const evidenceDir = path.dirname(fileURLToPath(import.meta.url));
const baseUrl = "http://127.0.0.1:8434";
const tenant = { orgId: "org-org", projectId: "dev-project" };
const cutoff = "2026-08-24T13:00:00Z";
const hash = (fill = "a") => `sha256:${fill.repeat(64)}`;
const viewports = [{ width: 1280, height: 720 }, { width: 1440, height: 900 }, { width: 1920, height: 1080 }];
const moduleSpecs = [
  ["ecommerce.task-cockpit", "任务总控", "/workshop/cockpit"], ["ecommerce.content-campaign", "内容活动", "/workshop/content-campaign"],
  ["ecommerce.operations", "运营履约", "/workshop/operations"], ["ecommerce.creator-growth", "达人增长", "/workshop/creator-growth"],
  ["ecommerce.media-studio", "媒体工坊", "/workshop/media-studio"], ["ecommerce.analyst", "经营分析", "/workshop/analyst"],
  ["ecommerce.price-governance", "价格治理", "/workshop/price-governance"], ["ecommerce.customer", "客户经营", "/workshop/customer"],
];
const modules = moduleSpecs.map(([moduleId, label, route], index) => ({
  moduleId, displayName: label, menuLabel: label, route, slot: "workshop.primary.ecommerce", order: index + 1,
  installationRef: { installationId: `11111111-1111-4111-8111-${String(index + 1).padStart(12, "0")}`, revision: 8, compositionId: `22222222-2222-4222-8222-${String(index + 1).padStart(12, "0")}`, lockRevision: 12, lockHash: hash(), overlayRevision: "ar2-7e-content-rich-r1" },
  moduleRef: { publisher: "aos.ecommerce", bundleId: "solution.ecommerce.growth", version: "1.0.0", bundleContentHash: hash(), moduleArtifactRef: `bundle://${moduleId}`, moduleArtifactHash: hash() },
  readiness: "available", blockers: [], permissions: { roles: ["operator"], markings: ["public"], dataScopes: ["ecommerce:read"], actionTypes: [] },
  requiredObjects: [], requiredCapabilities: [], requiredAipFeatures: [], viewRefs: [], evalPackRefs: [], productionContractRefs: [], responsibilityTemplateRefs: [], impactCalculatorRefs: [], legacyAssetRefs: [], legacyRoutes: [], minimumRuntimeVersion: "1.0.0", dependencyRefs: [], lastReceiptRef: null,
}));

const ref = (resourceType, resourceId, fill = "a") => ({ resourceType, resourceId, revision: 1, contentHash: hash(fill), receiptId: `receipt-${resourceId}` });
const campaignRef = ref("CampaignRevision", "campaign-isolated-1");
const intentRef = ref("MasterContentIntentRevision", "intent-isolated-1", "b");
const variantRef = { ...ref("ContentVariant", "variant-isolated-1", "c"), intentRef, masterArtifactRef: { artifactId: "master-isolated-1", contentHash: hash("b") }, variantArtifactRef: { artifactId: "variant-isolated-1", contentHash: hash("c") }, relationId: "relation-isolated-1", relationType: "variant_of" };
const contentView = {
  schemaVersion: "aos.ecommerce-workshop.content-campaign-view/v1", tenant, evaluatedAt: cutoff, dataCutoff: cutoff, readiness: "degraded",
  slices: [
    { sliceId: "plan", status: "ready", dataCutoff: cutoff, authorityRefs: [campaignRef], items: [campaignRef], blockers: [], countLedger: { eligible: 1, attached: 1, unmatched: 0, conflicted: 0 } },
    { sliceId: "calendar", status: "ready", dataCutoff: cutoff, authorityRefs: [ref("CalendarEntryRevision", "calendar-isolated-1", "d")], items: [ref("CalendarEntryRevision", "calendar-isolated-1", "d")], blockers: [], countLedger: { eligible: 1, attached: 1, unmatched: 0, conflicted: 0 } },
    { sliceId: "content", status: "ready", dataCutoff: cutoff, authorityRefs: [intentRef], items: [intentRef, variantRef], blockers: [], countLedger: { eligible: 2, attached: 2, unmatched: 0, conflicted: 0 } },
  ], page: { limit: 100, count: 4, hasMore: false, nextCursor: null },
};
const productRef = (id, fill) => ({ resourceType: "Product", resourceId: id, revision: null, contentHash: hash(fill), authority: "ecom_object" });
const contentInputs = {
  schemaVersion: "aos.ecommerce-workshop.content-campaign-inputs/v1", tenant, evaluatedAt: cutoff, dataCutoff: cutoff, status: "ready",
  products: [
    { productRef: productRef("isolated:product:65", "a"), title: "隔离面膜套餐", price: "99.00", availableStock: 3, businessStatus: "1", sourceUpdatedAt: cutoff },
    { productRef: productRef("isolated:product:66", "d"), title: "隔离会员权益包", price: "199.00", availableStock: 68, businessStatus: "1", sourceUpdatedAt: cutoff },
  ],
  inventory: [{ skuRef: { resourceType: "ProductSku", resourceId: "isolated:sku:74", revision: null, contentHash: hash("b"), authority: "ecom_object" }, productRef: productRef("isolated:product:65", "a"), stock: 3, stockAlarm: 5, stockHealth: "low", sourceUpdatedAt: cutoff }],
  plans: [{ planRef: { resourceType: "CampaignRevision", resourceId: "campaign-isolated-1", revision: 1, contentHash: hash("c"), authority: "content_campaign_authority" }, lifecycle: "draft", channelIds: ["微信小店"], localStart: "2026-08-25 09:00", localEnd: "2026-08-25 21:00", sourceUpdatedAt: cutoff }],
  ledger: { products: 2, inventory: 1, plans: 1, unmatchedInventory: 0 }, unavailableGroups: [],
};
const zeroEffects = { providerInvocationCount: 0, approvalCreatedCount: 0, taskRunCreatedCount: 0, externalPublicationCount: 0, externalBusinessMutationCount: 0 };

function reply(route, body, status = 200) { return route.fulfill({ status, contentType: "application/json; charset=utf-8", body: JSON.stringify(body) }); }
async function installRoutes(page) {
  const requests = []; const responses = []; const unknownGets = []; const workflowPosts = []; const previewPosts = []; let version = 0; let decisions = []; let viewReads = 0; let inputReads = 0;
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request(); const url = new URL(request.url()); const pathname = url.pathname; const method = request.method(); const headers = request.headers();
    const record = { method, pathname, search: url.search, orgId: headers["x-org-id"] ?? null, projectId: headers["x-project-id"] ?? null };
    requests.push(record);
    if (method === "POST" && pathname === "/api/v1/ecommerce-workshop/views/content-campaign/workflow/commands") {
      let body; try { body = request.postDataJSON(); } catch { body = null; }
      const idempotencyKey = headers["idempotency-key"] ?? null; workflowPosts.push({ ...record, idempotencyKey, body });
      version += 1;
      if (body?.command === "apply_risk_decision" && body.riskDecision) decisions = [...decisions.filter((item) => item.category !== body.riskDecision.category), { ...body.riskDecision, appliedFromRevision: version - 1 }];
      if (body?.command === "undo_risk_decision") decisions = decisions.slice(0, -1);
      const draft = { resourceType: "TaskBriefRevision", resourceId: "brief-isolated-1", revision: version, version, contentHash: String(version).repeat(64), objective: body?.objective ?? "", channels: body?.channels ?? [], constraints: decisions.map((item) => item.constraint), riskDecisions: decisions, lastAction: body?.command === "apply_risk_decision" ? "risk_decision_applied" : body?.command === "undo_risk_decision" ? "risk_decision_undone" : body?.command ?? null };
      return reply(route, { tenant, command: body?.command, task: { taskId: "task-isolated-content-1", title: "隔离会员活动方案" }, draft, receipt: { receiptId: `content-receipt-${version}`, operation: version === 1 ? "task_brief.create" : "task_brief.revise", idempotencyKey, replay: false }, sideEffects: zeroEffects, message: `${body?.command} 已形成隔离草稿版本。` });
    }
    if (method === "POST" && pathname === "/api/v1/ecommerce-workshop/views/content-campaign/workflow/approval-preview") {
      let body; try { body = request.postDataJSON(); } catch { body = null; }
      previewPosts.push({ ...record, body });
      const draft = { resourceType: "TaskBriefRevision", resourceId: "brief-isolated-1", revision: version, version, contentHash: String(version).repeat(64), objective: "读取正式活动计划", channels: ["微信小店"], constraints: decisions.map((item) => item.constraint), riskDecisions: decisions, lastAction: "risk_decision_undone" };
      return reply(route, { tenant, status: "needs_input", approvalAllowed: false, draft, checks: [{ name: "正式预算与素材评审", passed: false, detail: "隔离验收不提供正式发布权威" }], nextActions: ["补充正式预算与素材评审条件"], evaluatedAt: cutoff, dataCutoff: cutoff, sideEffects: zeroEffects });
    }
    if (method !== "GET") return reply(route, { code: "AR2_7E_UNAUTHORIZED_WRITE", message: "write denied" }, 405);
    if (pathname === "/api/v1/me") return reply(route, { subject: "ar2-7e-content", ...tenant, workspaceName: "AR2-7E 隔离验收", roles: ["operator"], markings: ["public"], tokenKind: "fixture" });
    if (pathname === "/api/v1/orgs") return reply(route, { items: [{ id: tenant.orgId, name: tenant.orgId }], currentOrgId: tenant.orgId });
    if (pathname === "/api/v1/workspaces") return reply(route, { items: [{ id: tenant.projectId, orgId: tenant.orgId, name: "AR2-7E 隔离验收" }], currentProjectId: tenant.projectId });
    if (pathname === "/api/v1/health") return reply(route, { status: "ok" });
    if (pathname === "/api/v1/ecommerce-workshop/modules") return reply(route, { schemaVersion: "aos.ecommerce-workshop/v1", tenant, evaluatedAt: cutoff, dataCutoff: cutoff, items: modules, count: modules.length });
    if (pathname === "/api/v1/ecommerce-workshop/views/content-campaign") { viewReads += 1; return reply(route, contentView); }
    if (pathname === "/api/v1/ecommerce-workshop/views/content-campaign/real-inputs") { inputReads += 1; return reply(route, contentInputs); }
    if (pathname === "/api/v1/ecommerce-workshop/source-readiness") return reply(route, { schemaVersion: "aos.ecommerce-workshop.source-readiness/v1", tenant, checkedAt: cutoff, cutoffAt: cutoff, status: "empty", sources: [], receiptRef: null, investigation: null });
    unknownGets.push(pathname); return reply(route, { code: "UNDECLARED_CONTENT_FIXTURE", message: pathname }, 418);
  });
  page.on("response", (response) => { if (response.url().includes("/api/v1/")) responses.push({ pathname: new URL(response.url()).pathname, status: response.status() }); });
  return { requests, responses, unknownGets, workflowPosts, previewPosts, get viewReads() { return viewReads; }, get inputReads() { return inputReads; } };
}

async function clickAndWait(page, button, expectedVersion) {
  await button.click(); await page.getByText(`当前第 ${expectedVersion} 版`, { exact: false }).waitFor({ timeout: 10000 });
}
async function runUnit(browser, viewport) {
  const context = await browser.newContext({ viewport });
  await context.addInitScript((value) => sessionStorage.setItem("aos-tenant-v1", JSON.stringify(value)), { ...tenant, workspaceName: "AR2-7E 隔离验收", subject: "ar2-7e-content", roles: ["operator"] });
  const page = await context.newPage(); const pageErrors = []; const consoleErrors = []; const failures = [];
  page.on("pageerror", (error) => pageErrors.push(error.message)); page.on("console", (message) => { if (message.type() === "error") consoleErrors.push(message.text()); });
  const transport = await installRoutes(page);
  const observed = { tabs: [], calendarViews: [], templateFilters: [], activityFilters: [], products: [], commands: [], versions: [], receipts: [], approvalPreview: false, refreshReadback: false, sidebarRoundTrip: false, scrollEnd: false };
  try {
    await page.goto(`${baseUrl}/workshop/content-campaign`, { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.locator('.ecommerce-workshop-shell[data-module-id="ecommerce.content-campaign"]').waitFor({ timeout: 10000 });
    await page.locator(".content-campaign-slice").first().waitFor();
    const tabs = page.locator('.content-campaign-toolbar [role="tab"]');
    for (let index = 0; index < await tabs.count(); index += 1) { const tab = tabs.nth(index); observed.tabs.push(((await tab.textContent()) ?? "").trim()); await tab.click(); }
    if (!((await page.locator("main").textContent()) ?? "").includes("variant_of")) failures.push("content_variant_lineage_missing");

    await tabs.filter({ hasText: "内容日历" }).click();
    const calendarNav = page.locator('[aria-label="内容日历视图"] button');
    for (let index = 0; index < await calendarNav.count(); index += 1) { const button = calendarNav.nth(index); await button.click(); observed.calendarViews.push(((await button.textContent()) ?? "").trim()); }
    if (!(await page.locator(".content-campaign-schedule-list").innerText()).includes("活动计划")) failures.push("schedule_readback_missing");
    const products = page.locator(".content-campaign-product-choices button");
    for (let index = 0; index < await products.count(); index += 1) { await products.nth(index).click(); observed.products.push(((await products.nth(index).textContent()) ?? "").trim()); }
    if (!(await page.locator(".content-campaign-input-detail").innerText()).includes("隔离会员权益包")) failures.push("product_selection_missing");

    await tabs.filter({ hasText: "日常模板" }).click(); const templateButtons = page.locator('[aria-label="日常模板筛选"] button');
    for (let index = 0; index < await templateButtons.count(); index += 1) { const button = templateButtons.nth(index); await button.click(); observed.templateFilters.push(((await button.textContent()) ?? "").trim()); }
    if (!(await page.locator('[aria-label="日常模板业务视图"]').innerText()).includes("当前截止面没有正式日常模板记录")) failures.push("template_empty_boundary_missing");

    const filter = page.locator(".content-campaign-list-lane header button", { hasText: "筛选" }); await filter.click(); const filterButtons = page.locator(".content-campaign-filters button");
    for (let index = 0; index < await filterButtons.count(); index += 1) { const button = filterButtons.nth(index); await button.click(); observed.activityFilters.push(((await button.textContent()) ?? "").trim()); }
    await page.getByTitle("新建内部活动草稿").click(); await page.getByRole("button", { name: "读取正式活动计划", exact: true }).click();
    const intent = page.locator('textarea[aria-label="活动意图"]'); if ((await intent.inputValue()) !== "读取正式活动计划") failures.push("assistant_hint_fill_missing");
    await clickAndWait(page, page.getByRole("button", { name: "生成方案", exact: true }), 1);
    await clickAndWait(page, page.locator(".content-campaign-actionbar").getByRole("button", { name: "保存为草稿" }), 2);
    await clickAndWait(page, page.locator(".content-campaign-actionbar").getByRole("button", { name: "重新生成" }), 3);
    const risk = page.locator(".content-campaign-risk-list article");
    await clickAndWait(page, risk.nth(0).getByRole("button", { name: "采纳建议并重算" }), 4);
    await clickAndWait(page, risk.nth(1).getByRole("button", { name: "保持当前方案" }), 5);
    await clickAndWait(page, page.getByRole("button", { name: "撤销最近一次风险决策" }), 6);
    observed.commands = transport.workflowPosts.map((item) => item.body?.command); observed.versions = [1, 2, 3, 4, 5, 6]; observed.receipts = observed.versions.map((version) => `content-receipt-${version}`);
    await page.locator(".content-campaign-actionbar").getByRole("button", { name: "批准并发布" }).click();
    await page.getByText("补充正式预算与素材评审条件", { exact: false }).waitFor(); observed.approvalPreview = true;
    const readsBefore = [transport.viewReads, transport.inputReads]; await page.locator(".content-campaign-footnote").getByRole("button", { name: "重新读取" }).click(); await page.locator(".content-campaign-slice").first().waitFor();
    observed.refreshReadback = transport.viewReads > readsBefore[0] && transport.inputReads > readsBefore[1];
    await page.getByRole("button", { name: "折叠侧栏" }).click(); await page.getByRole("button", { name: "展开侧栏" }).click(); observed.sidebarRoundTrip = true;
    observed.scrollEnd = await page.locator(".content").evaluate((node) => { node.scrollTop = node.scrollHeight; return Math.abs(node.scrollTop + node.clientHeight - node.scrollHeight) <= 2; });

    const expectedCommands = ["generate", "save", "regenerate", "apply_risk_decision", "apply_risk_decision", "undo_risk_decision"];
    if (JSON.stringify(observed.commands) !== JSON.stringify(expectedCommands)) failures.push(`command_order_${observed.commands.join("|")}`);
    if (new Set(transport.workflowPosts.map((item) => item.idempotencyKey)).size !== 6 || transport.workflowPosts.some((item) => !item.idempotencyKey)) failures.push("idempotency_keys_not_unique");
    transport.workflowPosts.forEach((item, index) => { if (index > 0 && (item.body?.expectedVersion !== index || item.body?.draftRef?.revision !== index)) failures.push(`cas_drift_${index + 1}`); });
    if (transport.previewPosts.length !== 1 || transport.previewPosts[0]?.body?.draftRef?.revision !== 6) failures.push("approval_preview_drift");
    if (!observed.refreshReadback || !observed.sidebarRoundTrip || !observed.scrollEnd) failures.push("roundtrip_incomplete");
    const navCount = await page.locator(".nav [data-workshop-module-id]").count(); const h1Count = await page.locator("h1").count();
    const layout = await page.evaluate(() => ({ clientWidth: document.documentElement.clientWidth, scrollWidth: document.documentElement.scrollWidth, horizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1 }));
    const allowedPaths = new Set(["/api/v1/ecommerce-workshop/views/content-campaign/workflow/commands", "/api/v1/ecommerce-workshop/views/content-campaign/workflow/approval-preview"]);
    const otherWrites = transport.requests.filter((item) => item.method !== "GET" && !allowedPaths.has(item.pathname));
    const tenantDrift = transport.requests.filter((item) => item.pathname.startsWith("/api/v1/ecommerce-workshop/") && (item.orgId !== tenant.orgId || item.projectId !== tenant.projectId));
    if (navCount !== 8) failures.push(`nav_count_${navCount}`); if (h1Count !== 1) failures.push(`h1_count_${h1Count}`); if (observed.tabs.length !== 3 || observed.calendarViews.length !== 2 || observed.templateFilters.length !== 3 || observed.activityFilters.length !== 3 || observed.products.length !== 2) failures.push("interaction_count_drift");
    if (layout.horizontalOverflow) failures.push("horizontal_overflow"); if (otherWrites.length) failures.push("other_write_detected"); if (tenantDrift.length) failures.push("tenant_header_drift"); if (transport.unknownGets.length) failures.push(`unknown_get_${transport.unknownGets.join("|")}`);
    if (transport.responses.some((item) => item.status >= 500)) failures.push("http_5xx"); if (pageErrors.length) failures.push("page_errors"); if (consoleErrors.length) failures.push("console_errors");
    await page.screenshot({ path: path.join(evidenceDir, `ar2-7e-content-campaign-rich-${viewport.width}x${viewport.height}.png`), fullPage: true });
    return { viewport, result: failures.length ? "FAIL" : "PASS", failures, observed, navCount, h1Count, layout, pageErrors, consoleErrors, otherWrites, ...transport };
  } catch (error) {
    failures.push(error instanceof Error ? error.message : String(error)); await page.screenshot({ path: path.join(evidenceDir, `ar2-7e-content-campaign-rich-diagnostic-${viewport.width}x${viewport.height}.png`), fullPage: true }).catch(() => {});
    return { viewport, result: "FAIL", failures, observed, pageErrors, consoleErrors, ...transport };
  } finally { await context.close(); }
}

const browser = await chromium.launch({ executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", headless: true });
const results = []; let consecutiveFailures = 0; let stoppedEarly = false;
try { for (const viewport of viewports) { const result = await runUnit(browser, viewport); results.push(result); console.log(`${viewport.width}x${viewport.height}: ${result.result}${result.failures.length ? ` ${result.failures.join(",")}` : ""}`); consecutiveFailures = result.result === "PASS" ? 0 : consecutiveFailures + 1; if (consecutiveFailures >= 2) { stoppedEarly = true; break; } } } finally { await browser.close(); }
const counts = { passed: results.filter((item) => item.result === "PASS").length, total: results.length, workflowPosts: results.reduce((sum, item) => sum + item.workflowPosts.length, 0), previewPosts: results.reduce((sum, item) => sum + item.previewPosts.length, 0), otherWrites: results.reduce((sum, item) => sum + (item.otherWrites?.length ?? 0), 0), unknownGets: results.reduce((sum, item) => sum + item.unknownGets.length, 0), pageErrors: results.reduce((sum, item) => sum + item.pageErrors.length, 0), consoleErrors: results.reduce((sum, item) => sum + item.consoleErrors.length, 0), stoppedEarly };
const evidence = { schemaVersion: "aos.ar2-7e-content-campaign-rich-browser/v1", generatedAt: new Date().toISOString(), baseUrl, authority: "AOS-000572 / AR2_7D_RUNTIME_WIRING_CANONICAL_ROUTER_GREEN", fixtureBoundary: "isolated contract records; all workflow and approval-preview POSTs intercepted before backend transport", result: results.length === 3 && results.every((item) => item.result === "PASS") ? "PASS" : "FAIL", counts, zeroEffects, results, boundaries: ["Formal campaign facts remained GET-only and unchanged after refresh.", "The approval control produced a blocked preview only; no Approval or publication was created.", "No Provider, customer contact, payment, production migration, release, or push was attempted."] };
fs.writeFileSync(path.join(evidenceDir, "ar2-7e-content-campaign-rich-browser.json"), `${JSON.stringify(evidence, null, 2)}\n`); console.log(JSON.stringify({ result: evidence.result, counts }, null, 2)); if (evidence.result !== "PASS") process.exitCode = 1;
