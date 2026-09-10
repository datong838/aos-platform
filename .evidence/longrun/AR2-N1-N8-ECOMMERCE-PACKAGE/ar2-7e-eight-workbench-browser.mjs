import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";

const evidenceDir = path.dirname(fileURLToPath(import.meta.url));
const baseUrl = "http://127.0.0.1:8434";
const positiveTenant = { orgId: "org-org", projectId: "dev-project" };
const canaryTenant = { orgId: "dev-org", projectId: "dev-project" };
const hashA = `sha256:${"a".repeat(64)}`;
const hashB = `sha256:${"b".repeat(64)}`;

const pages = [
  { key: "cockpit", route: "/workshop/cockpit", moduleId: "ecommerce.task-cockpit", label: "日常任务总控大屏" },
  { key: "content-campaign", route: "/workshop/content-campaign", moduleId: "ecommerce.content-campaign", label: "内容与活动工作台" },
  { key: "operations", route: "/workshop/operations", moduleId: "ecommerce.operations", label: "统一运营驾驶舱", legacyRoutes: ["/workshop/inventory", "/workshop/orders"] },
  { key: "creator-growth", route: "/workshop/creator-growth", moduleId: "ecommerce.creator-growth", label: "达人邀约驾驶舱" },
  { key: "media-studio", route: "/workshop/media-studio", moduleId: "ecommerce.media-studio", label: "多媒体内容生产" },
  { key: "analyst", route: "/workshop/analyst", moduleId: "ecommerce.analyst", label: "经营参谋 · 增长指挥中心" },
  { key: "price-governance", route: "/workshop/price-governance", moduleId: "ecommerce.price-governance", label: "价格治理驾驶舱" },
  { key: "customer", route: "/workshop/customer", moduleId: "ecommerce.customer", label: "客户关系工作台" },
];

const viewports = [
  { width: 1280, height: 720 },
  { width: 1440, height: 900 },
  { width: 1920, height: 1080 },
];

function moduleFixture(spec, index) {
  return {
    moduleId: spec.moduleId,
    displayName: spec.label,
    menuLabel: spec.label,
    route: spec.route,
    slot: "workshop.primary.ecommerce",
    order: index + 1,
    installationRef: {
      installationId: `11111111-1111-4111-8111-${String(index + 1).padStart(12, "0")}`,
      revision: 7,
      compositionId: `22222222-2222-4222-8222-${String(index + 1).padStart(12, "0")}`,
      lockRevision: 11,
      lockHash: hashA,
      overlayRevision: "ar2-7e-browser-r1",
    },
    moduleRef: {
      publisher: "aos.ecommerce",
      bundleId: "solution.ecommerce.growth",
      version: "1.0.0",
      bundleContentHash: hashA,
      moduleArtifactRef: `bundle://catalog/solutions/ecommerce/content/workshops/${spec.moduleId}.json`,
      moduleArtifactHash: hashB,
    },
    readiness: "available",
    blockers: [],
    permissions: {
      roles: ["operator"],
      markings: ["public"],
      dataScopes: ["ecommerce:read"],
      actionTypes: [],
    },
    requiredObjects: [],
    requiredCapabilities: [],
    requiredAipFeatures: [],
    viewRefs: [],
    evalPackRefs: [],
    productionContractRefs: [],
    responsibilityTemplateRefs: [],
    impactCalculatorRefs: [],
    legacyAssetRefs: [],
    legacyRoutes: spec.legacyRoutes ?? [],
    minimumRuntimeVersion: "1.0.0",
    dependencyRefs: [],
    lastReceiptRef: null,
  };
}

const installedModules = pages.map(moduleFixture);

function json(route, body, status = 200) {
  return route.fulfill({
    status,
    contentType: "application/json; charset=utf-8",
    body: JSON.stringify(body),
  });
}

function errorBody(code, message) {
  return { code, message, details: null, traceId: "ar2-7e-browser" };
}

function catalog(tenant, items) {
  return {
    schemaVersion: "aos.ecommerce-workshop/v1",
    tenant,
    evaluatedAt: "2026-09-10T04:00:00Z",
    dataCutoff: "2026-09-10T03:59:00Z",
    items,
    count: items.length,
  };
}

async function installFixtureRoutes(page, { tenant, catalogMode }) {
  const requests = [];
  const responses = [];
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    requests.push({
      method: request.method(),
      pathname: url.pathname,
      search: url.search,
      orgId: request.headers()["x-org-id"] ?? null,
      projectId: request.headers()["x-project-id"] ?? null,
    });
    if (request.method() !== "GET") {
      responses.push({ pathname: url.pathname, status: 405 });
      return json(route, errorBody("READ_ONLY_BROWSER_ACCEPTANCE", "只读验收拒绝写请求"), 405);
    }
    if (url.pathname === "/api/v1/me") {
      responses.push({ pathname: url.pathname, status: 200 });
      return json(route, { subject: "ar2-7e-browser", ...tenant, workspaceName: "AR2-7E 隔离验收", roles: ["operator"], markings: ["public"], tokenKind: "fixture" });
    }
    if (url.pathname === "/api/v1/orgs") {
      responses.push({ pathname: url.pathname, status: 200 });
      return json(route, { items: [{ id: tenant.orgId, name: tenant.orgId }], currentOrgId: tenant.orgId });
    }
    if (url.pathname === "/api/v1/workspaces") {
      responses.push({ pathname: url.pathname, status: 200 });
      return json(route, { items: [{ id: tenant.projectId, orgId: tenant.orgId, name: "AR2-7E 隔离验收" }], currentProjectId: tenant.projectId });
    }
    if (url.pathname === "/api/v1/health") {
      responses.push({ pathname: url.pathname, status: 200 });
      return json(route, { status: "ok" });
    }
    if (url.pathname === "/api/v1/ecommerce-workshop/modules") {
      if (catalogMode === "forbidden") {
        responses.push({ pathname: url.pathname, status: 403 });
        return json(route, errorBody("FORBIDDEN", "当前主体无权读取工作台目录"), 403);
      }
      if (catalogMode === "failed") {
        responses.push({ pathname: url.pathname, status: 503 });
        return json(route, errorBody("CATALOG_UNAVAILABLE", "工作台目录暂不可用"), 503);
      }
      const items = catalogMode === "ready" ? installedModules : [];
      responses.push({ pathname: url.pathname, status: 200 });
      return json(route, catalog(tenant, items));
    }
    responses.push({ pathname: url.pathname, status: 403 });
    return json(route, errorBody("DATA_READ_NOT_AUTHORIZED", "7E 隔离验收不读取真实业务数据"), 403);
  });
  return { requests, responses };
}

function startDiagnostics(page) {
  const pageErrors = [];
  const consoleErrors = [];
  const expectedNetworkConsoleErrors = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const value = message.text();
    if (/^Failed to load resource: the server responded with a status of (403|503) \(/.test(value)) {
      expectedNetworkConsoleErrors.push(value);
    } else {
      consoleErrors.push(value);
    }
  });
  return { pageErrors, consoleErrors, expectedNetworkConsoleErrors };
}

async function createContext(browser, tenant, viewport) {
  const context = await browser.newContext({ viewport });
  await context.addInitScript((value) => {
    if (window.self === window.top) {
      sessionStorage.setItem("aos-tenant-v1", JSON.stringify(value));
    }
  }, { ...tenant, workspaceName: "AR2-7E 隔离验收", subject: "ar2-7e-browser", roles: ["operator"] });
  return context;
}

async function layoutSnapshot(page) {
  return page.evaluate(() => {
    const root = document.documentElement;
    const content = document.querySelector(".content");
    const nav = document.querySelector(".nav");
    return {
      clientWidth: root.clientWidth,
      scrollWidth: root.scrollWidth,
      horizontalOverflow: root.scrollWidth > root.clientWidth + 1,
      content: content ? { clientHeight: content.clientHeight, scrollHeight: content.scrollHeight, scrollable: content.scrollHeight > content.clientHeight + 1 } : null,
      nav: nav ? { clientHeight: nav.clientHeight, scrollHeight: nav.scrollHeight, scrollable: nav.scrollHeight > nav.clientHeight + 1 } : null,
    };
  });
}

function workshopBusinessRequests(requests) {
  return requests.filter((item) => item.pathname.startsWith("/api/v1/ecommerce-workshop/"));
}

async function runPositiveUnit(browser, spec, viewport) {
  const context = await createContext(browser, positiveTenant, viewport);
  const page = await context.newPage();
  const diagnostics = startDiagnostics(page);
  const transport = await installFixtureRoutes(page, { tenant: positiveTenant, catalogMode: "ready" });
  const failures = [];
  const observed = {};
  try {
    await page.goto(`${baseUrl}${spec.route}`, { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.locator(`.ecommerce-workshop-shell[data-module-id="${spec.moduleId}"]`).waitFor({ timeout: 10000 });
    await page.waitForTimeout(300);

    observed.specializedShell = await page.locator(".p-app.is-workshop-primary-visual").count() === 1;
    observed.moduleShell = await page.locator(`.ecommerce-workshop-shell[data-module-id="${spec.moduleId}"]`).count() === 1;
    observed.titleVisible = await page.getByText(spec.label, { exact: true }).first().isVisible().catch(() => false);
    observed.workshopNavCount = await page.locator(".nav [data-workshop-module-id]").count();
    observed.activeNavCount = await page.locator(".nav a[aria-current='page']").count();
    observed.h1Count = await page.locator("h1").count();
    observed.hostFailureCount = await page.locator(".ecommerce-workshop-host-state").count();
    observed.dataReadDenied = await page.getByText(/没有访问权限|无权|正式服务未返回|读取失败|暂不可用/).count() > 0;
    observed.headerActions = await page.locator(".workshop-visual-header-actions button").evaluateAll((buttons) => buttons.map((button) => ({
      label: button.textContent?.trim() ?? "",
      disabled: button.disabled,
    })));
    observed.unauthorizedEnabledHeaderActions = observed.headerActions.filter((item) => !item.disabled && !["筛选", "查看内容计划"].includes(item.label));

    const tabs = page.locator("main [role='tab']:visible:not([disabled])");
    observed.tabCount = await tabs.count();
    observed.tabSwitched = false;
    if (observed.tabCount > 1) {
      await tabs.last().click();
      observed.tabSwitched = true;
    }

    const collapse = page.getByRole("button", { name: "折叠侧栏" });
    const expand = page.getByRole("button", { name: "展开侧栏" });
    await collapse.click();
    await expand.waitFor();
    await expand.click();
    await collapse.waitFor();
    observed.sidebarCollapseRestore = true;

    const layout = await layoutSnapshot(page);
    const businessRequests = workshopBusinessRequests(transport.requests);
    const nonGet = businessRequests.filter((item) => item.method !== "GET");
    const tenantDrift = businessRequests.filter((item) => item.orgId !== positiveTenant.orgId || item.projectId !== positiveTenant.projectId);
    const serverErrors = transport.responses.filter((item) => item.status >= 500);

    if (!observed.specializedShell) failures.push("specialized_shell_missing");
    if (!observed.moduleShell) failures.push("module_shell_missing");
    if (!observed.titleVisible) failures.push("specialized_title_missing");
    if (observed.workshopNavCount !== 8) failures.push(`workshop_nav_count_${observed.workshopNavCount}`);
    if (observed.activeNavCount !== 1) failures.push(`active_nav_count_${observed.activeNavCount}`);
    if (observed.h1Count !== 1) failures.push(`h1_count_${observed.h1Count}`);
    if (observed.hostFailureCount !== 0) failures.push("route_host_failed");
    if (!observed.dataReadDenied) failures.push("data_read_failure_not_visible");
    if (observed.unauthorizedEnabledHeaderActions.length) failures.push(`unauthorized_header_actions_${observed.unauthorizedEnabledHeaderActions.map((item) => item.label).join("|")}`);
    if (layout.horizontalOverflow) failures.push("horizontal_overflow");
    if (nonGet.length) failures.push("non_get_workshop_request");
    if (tenantDrift.length) failures.push("workshop_tenant_header_drift");
    if (serverErrors.length) failures.push("http_5xx_present");
    if (diagnostics.pageErrors.length) failures.push("page_errors_present");
    if (diagnostics.consoleErrors.length) failures.push("console_errors_present");

    await page.screenshot({
      path: path.join(evidenceDir, `ar2-7e-${spec.key}-${viewport.width}x${viewport.height}.png`),
      fullPage: true,
    });
    return { spec, viewport, result: failures.length ? "FAIL" : "PASS", failures, observed, layout, ...diagnostics, requests: transport.requests, responses: transport.responses };
  } catch (error) {
    failures.push(error instanceof Error ? error.message : String(error));
    await page.screenshot({ path: path.join(evidenceDir, `ar2-7e-${spec.key}-diagnostic-${viewport.width}x${viewport.height}.png`), fullPage: true }).catch(() => {});
    return { spec, viewport, result: "FAIL", failures, observed, ...diagnostics, requests: transport.requests, responses: transport.responses };
  } finally {
    await context.close();
  }
}

async function runNegative(browser, test) {
  const viewport = { width: 1440, height: 900 };
  const context = await createContext(browser, test.tenant, viewport);
  const page = await context.newPage();
  const diagnostics = startDiagnostics(page);
  const transport = await installFixtureRoutes(page, { tenant: test.tenant, catalogMode: test.catalogMode });
  const failures = [];
  try {
    await page.goto(`${baseUrl}${test.route}`, { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForTimeout(500);
    if (test.expectedPath) await page.waitForURL((url) => url.pathname === test.expectedPath, { timeout: 10000 });

    const currentPath = new URL(page.url()).pathname;
    const specializedCount = await page.locator(".p-app.is-workshop-primary-visual").count();
    const moduleNavCount = await page.locator(".nav [data-workshop-module-id]").count();
    const hostText = await page.locator(".ecommerce-workshop-host-state").textContent().catch(() => null);
    const dataRequests = workshopBusinessRequests(transport.requests).filter((item) => item.pathname !== "/api/v1/ecommerce-workshop/modules");
    const nonGet = workshopBusinessRequests(transport.requests).filter((item) => item.method !== "GET");
    const unexpected5xx = transport.responses.filter((item) => item.status >= 500 && !(test.catalogMode === "failed" && item.pathname === "/api/v1/ecommerce-workshop/modules"));

    if (test.expectedPath && currentPath !== test.expectedPath) failures.push(`path_${currentPath}`);
    if (test.expectInstalled) {
      if (specializedCount !== 1) failures.push("declared_legacy_specialized_shell_missing");
      if (moduleNavCount !== 8) failures.push(`declared_legacy_nav_count_${moduleNavCount}`);
    } else {
      if (specializedCount !== 0) failures.push("specialized_shell_leaked");
      if (moduleNavCount !== 0) failures.push(`module_nav_leaked_${moduleNavCount}`);
      if (!hostText?.includes(test.expectedText)) failures.push(`host_state_missing_${test.expectedText}`);
      if (dataRequests.length) failures.push("business_read_started_without_catalog_capability");
    }
    if (nonGet.length) failures.push("non_get_workshop_request");
    if (unexpected5xx.length) failures.push("unexpected_http_5xx");
    if (diagnostics.pageErrors.length) failures.push("page_errors_present");
    if (diagnostics.consoleErrors.length) failures.push("console_errors_present");
    const layout = await layoutSnapshot(page);
    if (layout.horizontalOverflow) failures.push("horizontal_overflow");

    await page.screenshot({ path: path.join(evidenceDir, `ar2-7e-negative-${test.key}.png`), fullPage: true });
    return { key: test.key, result: failures.length ? "FAIL" : "PASS", failures, currentPath, specializedCount, moduleNavCount, hostText, layout, ...diagnostics, requests: transport.requests, responses: transport.responses };
  } catch (error) {
    failures.push(error instanceof Error ? error.message : String(error));
    await page.screenshot({ path: path.join(evidenceDir, `ar2-7e-negative-${test.key}-diagnostic.png`), fullPage: true }).catch(() => {});
    return { key: test.key, result: "FAIL", failures, ...diagnostics, requests: transport.requests, responses: transport.responses };
  } finally {
    await context.close();
  }
}

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});

const positiveResults = [];
const negativeResults = [];
let stoppedEarly = false;
try {
  let consecutivePositiveFailures = 0;
  positiveLoop:
  for (const spec of pages) {
    for (const viewport of viewports) {
      const result = await runPositiveUnit(browser, spec, viewport);
      positiveResults.push(result);
      console.log(`positive ${spec.key} ${viewport.width}x${viewport.height}: ${result.result}${result.failures.length ? ` ${result.failures.join(",")}` : ""}`);
      consecutivePositiveFailures = result.result === "PASS" ? 0 : consecutivePositiveFailures + 1;
      if (consecutivePositiveFailures >= 2) {
        stoppedEarly = true;
        console.log("positive matrix stopped after two consecutive failures");
        break positiveLoop;
      }
    }
  }

  const negativeTests = stoppedEarly ? [] : [
    ...pages.map((spec) => ({ key: `empty-${spec.key}`, route: spec.route, tenant: positiveTenant, catalogMode: "empty", expectedText: "模块未安装" })),
    { key: "catalog-forbidden", route: "/workshop/operations", tenant: positiveTenant, catalogMode: "forbidden", expectedText: "没有访问权限" },
    { key: "catalog-failed", route: "/workshop/operations", tenant: positiveTenant, catalogMode: "failed", expectedText: "读取失败" },
    { key: "legacy-declared", route: "/workshop/orders", tenant: positiveTenant, catalogMode: "ready", expectedPath: "/workshop/operations", expectInstalled: true },
    { key: "legacy-uninstalled", route: "/workshop/orders", tenant: positiveTenant, catalogMode: "empty", expectedText: "模块未安装" },
    { key: "canary-empty", route: "/workshop/operations", tenant: canaryTenant, catalogMode: "empty", expectedText: "模块未安装" },
  ];
  for (const test of negativeTests) {
    const result = await runNegative(browser, test);
    negativeResults.push(result);
    console.log(`negative ${test.key}: ${result.result}${result.failures.length ? ` ${result.failures.join(",")}` : ""}`);
  }
} finally {
  await browser.close();
}

const allResults = [...positiveResults, ...negativeResults];
const evidence = {
  schemaVersion: "aos.ar2-7e-eight-workbench-browser/v1",
  generatedAt: new Date().toISOString(),
  baseUrl,
  authority: "AOS-000572 / AR2_7D_RUNTIME_WIRING_CANONICAL_ROUTER_GREEN",
  fixtureBoundary: "isolated catalog plus explicit business-read denial; no real tenant business data",
  result: allResults.every((item) => item.result === "PASS") ? "PASS" : "FAIL",
  counts: {
    positivePassed: positiveResults.filter((item) => item.result === "PASS").length,
    positiveTotal: positiveResults.length,
    negativePassed: negativeResults.filter((item) => item.result === "PASS").length,
    negativeTotal: negativeResults.length,
    nonGetWorkshopRequests: allResults.flatMap((item) => workshopBusinessRequests(item.requests ?? [])).filter((item) => item.method !== "GET").length,
    pageErrors: allResults.reduce((sum, item) => sum + (item.pageErrors?.length ?? 0), 0),
    consoleErrors: allResults.reduce((sum, item) => sum + (item.consoleErrors?.length ?? 0), 0),
    expectedNetworkConsoleErrors: allResults.reduce((sum, item) => sum + (item.expectedNetworkConsoleErrors?.length ?? 0), 0),
    stoppedEarly,
  },
  positiveResults,
  negativeResults,
  boundaries: [
    "The browser fixture exposed installed routing and denied real business reads explicitly.",
    "Every intercepted Workshop request was required to be GET and tenant scoped.",
    "No Provider call, real business mutation, publication, migration, or push occurred.",
  ],
};

fs.writeFileSync(path.join(evidenceDir, "ar2-7e-eight-workbench-browser.json"), `${JSON.stringify(evidence, null, 2)}\n`);
console.log(JSON.stringify({ result: evidence.result, counts: evidence.counts }, null, 2));
if (evidence.result !== "PASS") process.exitCode = 1;
