import { act, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { EcommerceWorkshopModuleListResponse } from "../../api/ecommerceWorkshop";
import { setTenant } from "../../api/tenant";
import {
  EcommerceWorkshopCatalogProvider,
  findInstalledWorkshopRoute,
  isReplacedLegacyWorkshopRoute,
  resolveLegacyWorkshopRoute,
  useEcommerceWorkshopCatalog,
  type EcommerceWorkshopCatalogClient,
} from "./EcommerceWorkshopCatalogContext";
import { workshopCatalogFixture } from "./workshopTestFixtures";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

type Deferred<T> = {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (cause: unknown) => void;
};

function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  let reject!: (cause: unknown) => void;
  const promise = new Promise<T>((onResolve, onReject) => {
    resolve = onResolve;
    reject = onReject;
  });
  return { promise, resolve, reject };
}

async function flush() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
  });
}

function Probe() {
  const catalog = useEcommerceWorkshopCatalog();
  const [, rerender] = useState(0);
  return (
    <div>
      <output data-testid="phase">{catalog.phase}</output>
      <output data-testid="tenant">{catalog.tenantKey}</output>
      <output data-testid="modules">{catalog.modules.map((item) => item.moduleId).join(",")}</output>
      <button type="button" onClick={() => { catalog.reload(); rerender((value) => value + 1); }}>
        reload
      </button>
    </div>
  );
}

describe("EcommerceWorkshopCatalogContext", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    sessionStorage.clear();
    setTenant({ orgId: "org-org", projectId: "dev-project", workspaceName: "real" });
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
  });

  afterEach(() => {
    act(() => root.unmount());
    host.remove();
    setTenant({ orgId: "org-org", projectId: "dev-project", workspaceName: "real" });
  });

  it("切换租户立即清空旧目录，晚到响应不能污染新租户", async () => {
    const real = deferred<EcommerceWorkshopModuleListResponse>();
    const canary = deferred<EcommerceWorkshopModuleListResponse>();
    const listModules = vi
      .fn<() => Promise<EcommerceWorkshopModuleListResponse>>()
      .mockReturnValueOnce(real.promise)
      .mockReturnValueOnce(canary.promise);
    const client: EcommerceWorkshopCatalogClient = { listModules };

    await act(async () => root.render(
      <EcommerceWorkshopCatalogProvider client={client}><Probe /></EcommerceWorkshopCatalogProvider>,
    ));
    expect(listModules).toHaveBeenCalledTimes(1);

    await act(async () => {
      setTenant({ orgId: "dev-org", projectId: "dev-project", workspaceName: "canary" });
    });
    expect(listModules).toHaveBeenCalledTimes(2);
    expect(host.querySelector("[data-testid='tenant']")?.textContent).toBe("dev-org:dev-project");
    expect(host.querySelector("[data-testid='modules']")?.textContent).toBe("");

    await act(async () => real.resolve(workshopCatalogFixture()));
    await flush();
    expect(host.querySelector("[data-testid='phase']")?.textContent).toBe("loading");
    expect(host.querySelector("[data-testid='modules']")?.textContent).toBe("");

    await act(async () => canary.resolve(workshopCatalogFixture({
      orgId: "dev-org",
      projectId: "dev-project",
      items: [],
    })));
    await flush();
    expect(host.querySelector("[data-testid='phase']")?.textContent).toBe("empty");
  });

  it("同租户重试失败时显式 stale 并保留上一份快照", async () => {
    const listModules = vi
      .fn<() => Promise<EcommerceWorkshopModuleListResponse>>()
      .mockResolvedValueOnce(workshopCatalogFixture())
      .mockRejectedValueOnce(new Error("refresh failed"));

    await act(async () => root.render(
      <EcommerceWorkshopCatalogProvider client={{ listModules }}><Probe /></EcommerceWorkshopCatalogProvider>,
    ));
    await flush();
    expect(host.querySelector("[data-testid='phase']")?.textContent).toBe("ready");

    await act(async () => host.querySelector<HTMLButtonElement>("button")!.click());
    await flush();
    expect(host.querySelector("[data-testid='phase']")?.textContent).toBe("stale");
    expect(host.querySelector("[data-testid='modules']")?.textContent).toBe("ecommerce.operations");
  });

  it("服务响应租户与会话不一致时失败关闭", async () => {
    const listModules = vi.fn().mockResolvedValue(workshopCatalogFixture({
      orgId: "dev-org",
      projectId: "dev-project",
    }));
    await act(async () => root.render(
      <EcommerceWorkshopCatalogProvider client={{ listModules }}><Probe /></EcommerceWorkshopCatalogProvider>,
    ));
    await flush();
    expect(host.querySelector("[data-testid='phase']")?.textContent).toBe("failed");
    expect(host.querySelector("[data-testid='modules']")?.textContent).toBe("");
  });
});

describe("Workshop route projection", () => {
  const modules = workshopCatalogFixture().items;

  it("canonical 子路径归属同一 Module，legacy 只映射不生成第二 Module", () => {
    expect(findInstalledWorkshopRoute(modules, "/workshop/operations/orders")?.kind).toBe("canonical");
    expect(findInstalledWorkshopRoute(modules, "/workshop/orders")?.kind).toBe("legacy");
    expect(findInstalledWorkshopRoute(modules, "/workshop/orders")?.module.moduleId).toBe("ecommerce.operations");
  });

  it("只有 active projection 声明的 legacy route 才被替换", () => {
    expect(isReplacedLegacyWorkshopRoute(modules, "/workshop/orders")).toBe(true);
    expect(isReplacedLegacyWorkshopRoute([], "/workshop/orders")).toBe(false);
  });

  it("active replacement 优先 redirect；无显式 release Receipt 时保留旧入口", () => {
    const acceptedRetirement = {
      legacyRoute: "/workshop/orders",
      canonicalRoute: "/workshop/operations",
      disposition: "retired" as const,
      reason: null,
      decisionRef: "receipt://route-retirement/orders",
    };
    expect(resolveLegacyWorkshopRoute(modules, "/workshop/orders", [acceptedRetirement]).kind)
      .toBe("redirect");
    expect(resolveLegacyWorkshopRoute([], "/workshop/orders").kind).toBe("preserve");
    expect(resolveLegacyWorkshopRoute([], "/workshop/orders", [acceptedRetirement]).kind)
      .toBe("retired");
    expect(resolveLegacyWorkshopRoute([], "/workshop/orders", [{
      ...acceptedRetirement,
      decisionRef: null,
    }]).kind).toBe("preserve");
  });
});
