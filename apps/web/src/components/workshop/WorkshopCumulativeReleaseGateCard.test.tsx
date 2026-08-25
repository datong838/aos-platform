import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { WorkshopCumulativeReleaseGateCard } from "./WorkshopCumulativeReleaseGateCard";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
describe("WorkshopCumulativeReleaseGateCard", () => {
  let host: HTMLDivElement; let root: Root;
  beforeEach(() => { host = document.createElement("div"); document.body.append(host); root = createRoot(host); });
  afterEach(async () => { await act(async () => root.unmount()); host.remove(); });
  it("renders fourteen honest unknown columns and no state-changing controls", async () => {
    await act(async () => root.render(<WorkshopCumulativeReleaseGateCard />));
    expect(host.textContent).toContain("累计门失败关闭"); expect(host.textContent).toContain("0 / 14"); expect(host.textContent).toContain("0 / 8");
    expect(host.textContent).toContain("OpenAPI"); expect(host.textContent).toContain("Alembic"); expect(host.textContent).toContain("Receipt Readback");
    expect(host.textContent).toContain("原子 Skill"); expect(host.textContent).toContain("Logic 编排"); expect(host.textContent).toContain("数字同事绑定"); expect(host.textContent).toContain("工作台贡献");
    expect(host.textContent).toContain("未知（不以 0 代替）"); expect(host.textContent).toContain("全部禁用"); expect(host.querySelectorAll("button")).toHaveLength(0);
  });
});
