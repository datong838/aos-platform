import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { WorkshopDisasterRecoveryCard } from "./WorkshopDisasterRecoveryCard";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
describe("WorkshopDisasterRecoveryCard", () => {
  let host: HTMLDivElement; let root: Root;
  beforeEach(() => { host = document.createElement("div"); document.body.append(host); root = createRoot(host); });
  afterEach(async () => { await act(async () => root.unmount()); host.remove(); });
  it("renders an honest read-only blocked state without restore controls", async () => {
    await act(async () => root.render(<WorkshopDisasterRecoveryCard />));
    expect(host.textContent).toContain("等待灾备证据"); expect(host.textContent).toContain("未知（不以 0 代替）");
    expect(host.textContent).toContain("原子技能"); expect(host.textContent).toContain("逻辑编排"); expect(host.textContent).toContain("数字同事绑定"); expect(host.textContent).toContain("工作台贡献");
    expect(host.textContent).toContain("DR_RELEASE_ROOTS_REQUIRED"); expect(host.textContent).toContain("全部禁用"); expect(host.querySelectorAll("button")).toHaveLength(0);
  });
});
