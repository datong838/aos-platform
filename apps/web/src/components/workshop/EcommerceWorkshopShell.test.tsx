import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { EcommerceWorkshopShell, WORKSHOP_FOCUS_EVENT } from "./EcommerceWorkshopShell";
import { WORKSHOP_ACCEPTANCE_MODULES } from "./workshopAcceptance";
import { moduleWithReadiness, workshopModuleFixture } from "./workshopTestFixtures";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

describe("EcommerceWorkshopShell", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
  });

  afterEach(() => {
    act(() => root.unmount());
    host.remove();
  });

  it("available 只有一个 H1、skip link 和明确正式读模型边界", async () => {
    await act(async () => root.render(
      <EcommerceWorkshopShell module={workshopModuleFixture()} dataCutoff="2026-08-14T09:59:00Z" />,
    ));
    expect(host.querySelectorAll("h1")).toHaveLength(1);
    expect(host.querySelector<HTMLAnchorElement>(".ecommerce-workshop-skip-link")?.hash).toBe("#ecommerce-workshop-main");
    expect(host.textContent).toContain("业务视图等待正式读模型接入");
    expect(host.textContent).not.toContain("DEPENDENCY_NOT_GREEN");
  });

  it("技术上下文默认折叠但保留 exact refs、readiness 与键盘可展开语义", async () => {
    const module = workshopModuleFixture();
    await act(async () => root.render(
      <EcommerceWorkshopShell module={module} dataCutoff="2026-08-14T09:59:00Z" />,
    ));
    const context = host.querySelector<HTMLDetailsElement>(".ecommerce-workshop-technical-context");
    const summary = context?.querySelector("summary");
    expect(context?.open).toBe(false);
    expect(summary?.textContent).toContain("模块安装上下文");
    expect(summary?.textContent).toContain(module.moduleId);
    expect(summary?.textContent).toContain("安装目录截止");
    expect(summary?.textContent).toContain("2026-08-14T09:59:00Z");
    expect(context?.querySelector("[aria-label='模块版本上下文']")?.textContent).toContain("Bundle");
    expect(context?.textContent).toContain("数据源就绪度");
  });

  for (const module of WORKSHOP_ACCEPTANCE_MODULES) {
    it(`${module.moduleId} 保留唯一 H1、精确路由与可达主区`, async () => {
      await act(async () => root.render(
        <EcommerceWorkshopShell
          module={workshopModuleFixture({
            moduleId: module.moduleId,
            displayName: module.label,
            menuLabel: module.label,
            route: module.route,
          })}
          dataCutoff="2026-08-14T09:59:00Z"
        />,
      ));
      const heading = host.querySelector("h1");
      const main = host.querySelector("#ecommerce-workshop-main");
      const appHeaderOwnsHeading = module.moduleId === "ecommerce.analyst"
        || module.moduleId === "ecommerce.price-governance"
        || module.moduleId === "ecommerce.customer";
      expect(host.querySelectorAll("h1")).toHaveLength(appHeaderOwnsHeading ? 0 : 1);
      if (module.moduleId === "ecommerce.analyst") {
        expect(host.querySelector(".analyst-exact-context-strip")?.textContent).toContain("渠道未选择");
        expect(host.querySelector(".analyst-exact-context-strip")?.textContent).toContain("业务操作：只读");
      } else if (appHeaderOwnsHeading) {
        expect(host.querySelector(".ecommerce-workshop-module-title")?.textContent).toContain(module.label);
      } else {
        expect(heading?.textContent).toContain(module.label);
      }
      expect(main).not.toBeNull();
      expect(host.querySelector(".ecommerce-workshop-shell")?.getAttribute("data-module-id"))
        .toBe(module.moduleId);
      expect(host.querySelector<HTMLAnchorElement>(".ecommerce-workshop-skip-link")?.hash)
        .toBe("#ecommerce-workshop-main");
    });
  }

  it("unknown 不伪装业务视图，并完整显示依赖原因", async () => {
    await act(async () => root.render(
      <EcommerceWorkshopShell module={moduleWithReadiness("unknown")} dataCutoff={null} />,
    ));
    expect(host.textContent).toContain("模块能力待核对");
    expect(host.textContent).toContain("下方业务视图按自身当前 canonical GET 独立判定");
    expect(host.textContent).toContain("DEPENDENCY_NOT_GREEN");
    expect(host.textContent).not.toContain("业务视图等待正式读模型接入");
  });

  it("卸载时发送退出专注事件，平台壳不会残留隐藏状态", async () => {
    const seen: boolean[] = [];
    const listener = (event: Event) => {
      seen.push((event as CustomEvent<{ active: boolean }>).detail.active);
    };
    window.addEventListener(WORKSHOP_FOCUS_EVENT, listener);
    await act(async () => root.render(
      <EcommerceWorkshopShell module={workshopModuleFixture()} dataCutoff={null} />,
    ));
    const focus = host.querySelector<HTMLButtonElement>(".ecommerce-workshop-focus-button")!;
    await act(async () => focus.click());
    act(() => root.unmount());
    root = createRoot(host);
    window.removeEventListener(WORKSHOP_FOCUS_EVENT, listener);
    expect(seen).toEqual([true, false]);
  });
});
