import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { WorkshopOperatingReadinessCard } from "./WorkshopOperatingReadinessCard";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

describe("WorkshopOperatingReadinessCard", () => {
  let host: HTMLDivElement;
  let root: Root;
  beforeEach(() => { host = document.createElement("div"); document.body.append(host); root = createRoot(host); });
  afterEach(async () => { await act(async () => root.unmount()); host.remove(); });

  it("renders an honest read-only blocked state without fake zero metrics or actions", async () => {
    await act(async () => root.render(<WorkshopOperatingReadinessCard />));
    expect(host.textContent).toContain("运营失败关闭");
    expect(host.textContent).toContain("未知（不以 0 代替）");
    expect(host.textContent).toContain("原子 Skill");
    expect(host.textContent).toContain("Logic 编排");
    expect(host.textContent).toContain("数字同事绑定");
    expect(host.textContent).toContain("工作台贡献");
    expect(host.textContent).toContain("OPERATING_RELEASE_ROOTS_REQUIRED");
    expect(host.querySelectorAll("button")).toHaveLength(0);
  });
});
