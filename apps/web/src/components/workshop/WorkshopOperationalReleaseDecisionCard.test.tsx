import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { WorkshopOperationalReleaseDecisionCard } from "./WorkshopOperationalReleaseDecisionCard";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
describe("WorkshopOperationalReleaseDecisionCard", () => {
  let host: HTMLDivElement; let root: Root;
  beforeEach(() => { host = document.createElement("div"); document.body.append(host); root = createRoot(host); });
  afterEach(async () => { await act(async () => root.unmount()); host.remove(); });
  it("renders eight honest blocked capabilities, NO_GO and no state-changing controls", async () => {
    await act(async () => root.render(<WorkshopOperationalReleaseDecisionCard />));
    expect(host.textContent).toContain("暂不发布"); expect(host.textContent).toContain("0 / 8"); expect(host.textContent).toContain("8 blocked");
    expect(host.textContent).toContain("价格治理"); expect(host.textContent).toContain("客户运营"); expect(host.textContent).toContain("累计安全检查");
    expect(host.textContent).toContain("原子 Skill"); expect(host.textContent).toContain("Logic 编排"); expect(host.textContent).toContain("数字同事绑定"); expect(host.textContent).toContain("工作台贡献");
    expect(host.textContent).toContain("全部禁用"); expect(host.querySelectorAll("button")).toHaveLength(0);
  });
});
