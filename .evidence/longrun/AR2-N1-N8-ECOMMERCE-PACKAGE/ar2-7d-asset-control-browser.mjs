import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";

const evidenceDir = path.dirname(fileURLToPath(import.meta.url));
const target = "http://127.0.0.1:8434/apollo/assets";
const tenant = { orgId: "org-org", projectId: "dev-project" };
const firstId = "11111111-1111-4111-8111-111111111111";
const secondId = "22222222-2222-4222-8222-222222222222";
const firstGeneration = "33333333-3333-4333-8333-333333333333";
const secondGeneration = "44444444-4444-4444-8444-444444444444";
const hash = `sha256:${"a".repeat(64)}`;
const evidenceHash = `sha256:${"b".repeat(64)}`;
const resourceHash = `sha256:${"c".repeat(64)}`;

function event(sequence, fromState, toState, reason = null, evidence = null) {
  const minute = String(sequence - 1).padStart(2, "0");
  return {
    sequence,
    fromRevision: sequence === 1 ? null : sequence - 1,
    toRevision: sequence,
    fromState,
    toState,
    actor: sequence === 3 ? "reviewer@aos.test" : "operator@aos.test",
    reason,
    evidence,
    createdAt: `2026-09-10T01:${minute}:00Z`,
  };
}

function installation(installationId, displayName, uninstalled) {
  const compositionId = installationId === firstId
    ? "55555555-5555-4555-8555-555555555555"
    : "66666666-6666-4666-8666-666666666666";
  const decisionId = installationId === firstId
    ? "77777777-7777-4777-8777-777777777777"
    : "88888888-8888-4888-8888-888888888888";
  const currentRevision = uninstalled ? 6 : 5;
  const state = uninstalled ? "uninstalled" : "active";
  const times = [
    event(1, null, "draft"),
    event(2, "draft", "submitted"),
    event(3, "submitted", "approved"),
    event(4, "approved", "applied", null, {
      type: "dry_apply",
      evidenceRef: `evidence://ar2-7d/${installationId}/apply`,
      evidenceHash,
      status: "valid",
      observedAt: "2026-09-10T01:03:00Z",
    }),
    event(5, "applied", "active", null, {
      type: "verification",
      evidenceRef: `evidence://ar2-7d/${installationId}/verify`,
      evidenceHash,
      status: "valid",
      observedAt: "2026-09-10T01:04:00Z",
    }),
  ];
  if (uninstalled) {
    times.push(event(6, "active", "uninstalled", "第一代完成停用、资源释放与卸载"));
  }
  return {
    installationId,
    displayName,
    state,
    currentRevision,
    activeRevision: uninstalled ? null : 5,
    previousActiveRevision: uninstalled ? 5 : null,
    etagVersion: currentRevision,
    createdAt: "2026-09-10T01:00:00Z",
    updatedAt: `2026-09-10T01:0${currentRevision - 1}:00Z`,
    current: {
      installationId,
      revision: currentRevision,
      parentRevision: currentRevision - 1,
      state,
      compositionId,
      lockRevision: 1,
      lockHash: hash,
      permissionDiffHash: hash,
      migrationPlanHash: hash,
      contributionDiffHash: hash,
      overlayRevision: "ar2-7d-browser-readback",
      requestedBy: "operator@aos.test",
      decisionId,
      createdAt: `2026-09-10T01:0${currentRevision - 1}:00Z`,
    },
    decision: {
      decisionId,
      installationId,
      submittedRevision: 2,
      decision: "approved",
      actor: "reviewer@aos.test",
      lockHash: hash,
      permissionDiffHash: hash,
      migrationPlanHash: hash,
      contributionDiffHash: hash,
      reason: null,
      createdAt: "2026-09-10T01:02:00Z",
    },
    events: times,
  };
}

const firstInstallation = installation(firstId, "栖月汇增长包 · 第一代卸载审计", true);
const secondInstallation = installation(secondId, "栖月汇增长包 · 第二代当前安装", false);
const installationList = {
  items: [firstInstallation, secondInstallation].map((item) => ({
    installationId: item.installationId,
    displayName: item.displayName,
    state: item.state,
    currentRevision: item.currentRevision,
    activeRevision: item.activeRevision,
    previousActiveRevision: item.previousActiveRevision,
    etagVersion: item.etagVersion,
    createdAt: item.createdAt,
    updatedAt: item.updatedAt,
  })),
  total: 2,
  limit: 20,
  offset: 0,
};

function runtime(installationId) {
  const old = installationId === firstId;
  return {
    installationId,
    installationRevision: old ? 6 : 5,
    installationEtag: old ? 6 : 5,
    installationState: old ? "uninstalled" : "active",
    effectiveState: old ? "stopped" : "ready",
    binding: {
      generation: old ? firstGeneration : secondGeneration,
      installationRevision: old ? 5 : 5,
      profileRef: "runtime-profile/python-v1",
      configRef: old ? null : {
        configurationId: "99999999-9999-4999-8999-999999999999",
        revision: 2,
        hash,
      },
      executionEpoch: old ? 7 : 8,
      desiredState: old ? "uninstalled" : "enabled",
      observedState: old ? "stopped" : "ready",
      enabled: !old,
      operationFence: old,
      revision: old ? 8 : 4,
    },
    currentOperation: null,
    ui: old ? null : {
      title: "栖月汇增长包当前槽位",
      signedResourceUrl: `http://127.0.0.1:8434/__ar2_7d_slot/index.html?contentHash=${encodeURIComponent(resourceHash)}`,
      resourceHash,
      initialRoute: "/workshop/overview",
      routeClaims: ["/workshop/overview"],
      readOperationClaims: ["ecommerce.case.read"],
      commandOperationClaims: [],
    },
    allowedActions: old ? [] : ["disable"],
    reasons: old
      ? ["第一代运行资源已释放；旧审计保留只读，运行入口关闭。"]
      : ["第二代当前绑定已就绪；仅显示服务端允许的停用动作。"],
  };
}

function json(route, body, status = 200, headers = {}) {
  return route.fulfill({
    status,
    contentType: "application/json; charset=utf-8",
    headers,
    body: JSON.stringify(body),
  });
}

function count(log, method, pathname) {
  return log.filter((item) => item.method === method && item.pathname === pathname).length;
}

async function waitForCount(page, log, method, pathname, minimum) {
  for (let attempt = 0; attempt < 50; attempt += 1) {
    if (count(log, method, pathname) >= minimum) return;
    await page.waitForTimeout(100);
  }
  throw new Error(`request count timeout: ${method} ${pathname} >= ${minimum}`);
}

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});
const results = [];

try {
  for (const viewport of [
    { width: 1280, height: 720 },
    { width: 1440, height: 900 },
    { width: 1920, height: 1080 },
  ]) {
    const context = await browser.newContext({ viewport });
    await context.addInitScript((value) => {
      if (window.self === window.top) {
        sessionStorage.setItem("aos-tenant-v1", JSON.stringify(value));
      }
    }, {
      orgId: tenant.orgId,
      projectId: tenant.projectId,
      workspaceName: "栖月汇验收工作区",
      subject: "operator@aos.test",
      roles: ["asset-installer"],
    });
    const page = await context.newPage();
    const requests = [];
    const pageErrors = [];
    const consoleErrors = [];
    const serverErrors = [];

    page.on("pageerror", (error) => pageErrors.push(error.message));
    page.on("console", (message) => {
      if (message.type() === "error") consoleErrors.push(message.text());
    });
    page.on("response", (response) => {
      if (response.status() >= 500) serverErrors.push(`${response.status()} ${response.url()}`);
    });

    await page.route("**/__ar2_7d_slot/index.html?*", (route) => {
      const url = new URL(route.request().url());
      requests.push({ method: route.request().method(), pathname: url.pathname, search: url.search, orgId: null, projectId: null });
      return route.fulfill({
        status: 200,
        contentType: "text/html; charset=utf-8",
        body: "<!doctype html><html lang=zh-CN><body><h1>当前安装槽位已加载</h1><p>只读浏览器验收，不执行业务命令。</p></body></html>",
      });
    });
    await page.route("**/api/v1/**", async (route) => {
      const request = route.request();
      const url = new URL(request.url());
      const entry = {
        method: request.method(),
        pathname: url.pathname,
        search: url.search,
        orgId: request.headers()["x-org-id"] ?? null,
        projectId: request.headers()["x-project-id"] ?? null,
      };
      requests.push(entry);
      if (request.method() !== "GET") {
        return json(route, { code: "READ_ONLY_FIXTURE", message: "browser acceptance is read-only", details: null, traceId: "ar2-7d" }, 405);
      }
      if (url.pathname === "/api/v1/me") return json(route, {
        subject: "operator@aos.test", orgId: tenant.orgId, projectId: tenant.projectId,
        workspaceName: "栖月汇验收工作区", roles: ["asset-installer"], markings: [], tokenKind: "fixture",
      });
      if (url.pathname === "/api/v1/orgs") return json(route, { items: [{ id: tenant.orgId, name: "栖月汇" }], currentOrgId: tenant.orgId });
      if (url.pathname === "/api/v1/workspaces") return json(route, { items: [{ id: tenant.projectId, orgId: tenant.orgId, name: "栖月汇验收工作区" }], currentProjectId: tenant.projectId });
      if (url.pathname === "/api/v1/health") return json(route, { status: "ok" });
      if (url.pathname === "/api/v1/ecommerce-workshop/modules") return json(route, {
        schemaVersion: "aos.ecommerce-workshop/v1", tenant, evaluatedAt: "2026-09-10T02:00:00Z", dataCutoff: null, items: [], count: 0,
      });
      if (url.pathname === "/api/v1/asset-bundles") return json(route, []);
      if (url.pathname === "/api/v1/bundle-installations") return json(route, installationList);
      if (url.pathname === `/api/v1/bundle-installations/${firstId}`) return json(route, firstInstallation, 200, { ETag: '"6"' });
      if (url.pathname === `/api/v1/bundle-installations/${secondId}`) return json(route, secondInstallation, 200, { ETag: '"5"' });
      if (url.pathname === `/api/v1/bundle-runtime-installations/${firstId}`) return json(route, runtime(firstId));
      if (url.pathname === `/api/v1/bundle-runtime-installations/${secondId}`) return json(route, runtime(secondId));
      return json(route, { code: "NOT_FOUND", message: `fixture route not found: ${url.pathname}`, details: null, traceId: "ar2-7d" }, 404);
    });

    const failures = [];
    try {
      await page.goto(target, { waitUntil: "networkidle" });
      await page.getByRole("tab", { name: "安装管理" }).click();
      const firstRow = page.getByRole("row").filter({ hasText: "栖月汇增长包 · 第一代卸载审计" });
      await firstRow.waitFor();
      await firstRow.getByRole("button", { name: "查看事件" }).click();
      const runtimePanel = page.getByRole("region", { name: "运行实例控制" });
      await runtimePanel.getByText("stopped", { exact: true }).waitFor();
      await runtimePanel.getByText("uninstalled / stopped", { exact: true }).waitFor();
      if ((await runtimePanel.getByText(firstGeneration, { exact: true }).count()) !== 1) failures.push("first_generation_missing_from_audit");
      if ((await runtimePanel.getByRole("button", { name: /运行实例|运行资源|更新运行配置/ }).count()) !== 0) failures.push("uninstalled_runtime_action_visible");
      if (!(await page.getByText("当前状态是终态，没有可执行动作。", { exact: true }).isVisible())) failures.push("uninstalled_installation_not_terminal");

      const secondRow = page.getByRole("row").filter({ hasText: "栖月汇增长包 · 第二代当前安装" });
      await secondRow.waitFor();
      await secondRow.getByRole("button", { name: "查看事件" }).click();
      await runtimePanel.getByText("ready", { exact: true }).waitFor();
      await runtimePanel.getByText("enabled / ready", { exact: true }).waitFor();
      await runtimePanel.getByText(secondGeneration, { exact: true }).waitFor();
      await page.getByTitle("栖月汇增长包当前槽位").waitFor();
      await page.frameLocator('iframe[title="栖月汇增长包当前槽位"]').getByRole("heading", { name: "当前安装槽位已加载" }).waitFor();
      if ((await runtimePanel.getByText(firstGeneration, { exact: true }).count()) !== 0) failures.push("old_generation_visible_in_current_slot");
      if ((await runtimePanel.getByRole("button", { name: "停用运行实例" }).count()) !== 1) failures.push("current_allowed_action_mismatch");
      if (count(requests, "GET", "/__ar2_7d_slot/index.html") < 1) failures.push("current_slot_resource_not_loaded");

      const beforeRefresh = {
        list: count(requests, "GET", "/api/v1/bundle-installations"),
        detail: count(requests, "GET", `/api/v1/bundle-installations/${secondId}`),
        runtime: count(requests, "GET", `/api/v1/bundle-runtime-installations/${secondId}`),
      };
      await page.getByRole("button", { name: "刷新安装状态" }).click();
      await waitForCount(page, requests, "GET", "/api/v1/bundle-installations", beforeRefresh.list + 1);
      await waitForCount(page, requests, "GET", `/api/v1/bundle-installations/${secondId}`, beforeRefresh.detail + 1);
      await waitForCount(page, requests, "GET", `/api/v1/bundle-runtime-installations/${secondId}`, beforeRefresh.runtime + 1);

      await page.getByRole("tab", { name: "资产 Registry" }).click();
      await page.getByRole("tab", { name: "安装管理" }).click();
      await secondRow.waitFor();
      await page.getByRole("button", { name: "折叠侧栏" }).click();
      await page.getByRole("button", { name: "展开侧栏" }).waitFor();
      await page.getByRole("button", { name: "展开侧栏" }).click();
      await page.getByRole("button", { name: "折叠侧栏" }).waitFor();
      await runtimePanel.scrollIntoViewIfNeeded();

      const assetRequests = requests.filter((item) => item.pathname.includes("bundle-") || item.pathname.includes("asset-bundles"));
      if (assetRequests.some((item) => item.method !== "GET")) failures.push("asset_mutation_request_observed");
      if (assetRequests.some((item) => item.orgId !== tenant.orgId || item.projectId !== tenant.projectId)) failures.push("asset_tenant_headers_drifted");
      if (pageErrors.length) failures.push("page_errors_present");
      if (consoleErrors.length) failures.push("console_errors_present");
      if (serverErrors.length) failures.push("server_errors_present");

      const layout = await page.evaluate(() => ({
        clientWidth: document.documentElement.clientWidth,
        scrollWidth: document.documentElement.scrollWidth,
        scrollHeight: document.documentElement.scrollHeight,
      }));
      if (layout.scrollWidth > layout.clientWidth + 1) failures.push("horizontal_overflow");
      await page.screenshot({
        path: path.join(evidenceDir, `ar2-7d-asset-control-${viewport.width}x${viewport.height}.png`),
        fullPage: true,
      });
      results.push({
        viewport,
        result: failures.length ? "FAIL" : "PASS",
        failures,
        layout,
        requestCounts: {
          assetGet: assetRequests.filter((item) => item.method === "GET").length,
          assetPost: assetRequests.filter((item) => item.method === "POST").length,
          list: count(requests, "GET", "/api/v1/bundle-installations"),
          currentDetail: count(requests, "GET", `/api/v1/bundle-installations/${secondId}`),
          currentRuntime: count(requests, "GET", `/api/v1/bundle-runtime-installations/${secondId}`),
        },
        observed: {
          uninstalledTerminal: true,
          stoppedRuntime: true,
          currentReadyEnabled: true,
          onlyCurrentGenerationInSlot: true,
          currentSlotResourceLoaded: true,
          currentAllowedAction: "disable",
          refreshReadback: true,
          registryReturn: true,
          sidebarCollapseRestore: true,
        },
        pageErrors,
        consoleErrors,
        serverErrors,
        requests,
      });
    } catch (error) {
      failures.push(error instanceof Error ? error.message : String(error));
      await page.screenshot({
        path: path.join(evidenceDir, `ar2-7d-asset-control-diagnostic-${viewport.width}x${viewport.height}.png`),
        fullPage: true,
      });
      results.push({ viewport, result: "FAIL", failures, pageErrors, consoleErrors, serverErrors, requests });
    } finally {
      await context.close();
    }
  }
} finally {
  await browser.close();
}

const evidence = {
  schemaVersion: "aos.ar2-7d-asset-control-browser/v1",
  target,
  tenant,
  fixtureAuthority: "D6D2 state-shape projection only; not runtime authority evidence",
  result: results.every((item) => item.result === "PASS") ? "PASS" : "FAIL",
  results,
  boundaries: [
    "All asset-control API requests were GET; no installation or runtime command was sent.",
    "The fixture projects states already proven by isolated PostgreSQL and OCI D6D2 evidence.",
    "No Provider call, real tenant mutation, migration, publication, or push occurred.",
  ],
};
fs.writeFileSync(path.join(evidenceDir, "ar2-7d-asset-control-browser.json"), `${JSON.stringify(evidence, null, 2)}\n`);
console.log(JSON.stringify(evidence, null, 2));
if (evidence.result !== "PASS") process.exitCode = 1;
