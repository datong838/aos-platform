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

  it("available 只有一个 H1、skip link 和明确 W2 边界", async () => {
    await act(async () => root.render(
      <EcommerceWorkshopShell module={workshopModuleFixture()} dataCutoff="2026-08-14T09:59:00Z" />,
    ));
    expect(host.querySelectorAll("h1")).toHaveLength(1);
    expect(host.querySelector<HTMLAnchorElement>(".ecommerce-workshop-skip-link")?.hash).toBe("#ecommerce-workshop-main");
    expect(host.textContent).toContain("业务视图将在 W2 接入");
    expect(host.textContent).not.toContain("DEPENDENCY_NOT_GREEN");
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
      expect(host.querySelectorAll("h1")).toHaveLength(1);
      expect(heading?.textContent).toContain(module.label);
      expect(main).not.toBeNull();
      expect(host.querySelector<HTMLAnchorElement>(".ecommerce-workshop-skip-link")?.hash)
        .toBe("#ecommerce-workshop-main");
    });
  }

  it("unknown 不伪装业务视图，并完整显示依赖原因", async () => {
    await act(async () => root.render(
      <EcommerceWorkshopShell module={moduleWithReadiness("unknown")} dataCutoff={null} />,
    ));
    expect(host.textContent).toContain("就绪状态待验证");
    expect(host.textContent).toContain("DEPENDENCY_NOT_GREEN");
    expect(host.textContent).not.toContain("业务视图将在 W2 接入");
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
