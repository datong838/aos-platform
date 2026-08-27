import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { AsyncStateBoundary, type AsyncState } from "./AsyncStateBoundary";
import { CapabilityBlocker } from "./CapabilityBlocker";
import { moduleWithReadiness } from "./workshopTestFixtures";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

describe("Workshop state boundaries", () => {
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

  const states: AsyncState[] = [
    "loading", "empty", "forbidden", "stale", "partial", "failed",
    "unknown", "blocked", "not-installed",
  ];

  for (const state of states) {
    it(`${state} 有可访问状态且不伪装 ready`, async () => {
      await act(async () => root.render(
        <AsyncStateBoundary state={state} dataCutoff="2026-08-14T09:59:00Z">
          <span data-testid="preserved">已验证旧内容</span>
        </AsyncStateBoundary>,
      ));
      expect(host.querySelector("[role='status'], [role='alert']")).not.toBeNull();
      expect(host.textContent).toContain("数据截止");
      expect(Boolean(host.querySelector("[data-testid='preserved']"))).toBe(
        state === "stale" || state === "partial",
      );
    });
  }

  it("available 不显示 blocker，unknown 显示原因与 authority 缺失", async () => {
    const available = moduleWithReadiness("available");
    await act(async () => root.render(
      <CapabilityBlocker readiness={available.readiness} blockers={available.blockers} />,
    ));
    expect(host.textContent).toBe("");

    const unknown = moduleWithReadiness("unknown");
    await act(async () => root.render(
      <CapabilityBlocker readiness={unknown.readiness} blockers={unknown.blockers} />,
    ));
    expect(host.textContent).toContain("DEPENDENCY_NOT_GREEN");
    expect(host.textContent).toContain("当前没有可验证的数据依据");
  });
});
