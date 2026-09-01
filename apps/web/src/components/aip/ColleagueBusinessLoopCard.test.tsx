// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { ColleagueBusinessLoopCard } from "./ColleagueBusinessLoopCard";

describe("ColleagueBusinessLoopCard", () => {
  afterEach(() => { document.body.innerHTML = ""; });

  it("用中文业务链展示输入、Logic、产出、贡献与回读", async () => {
    const host = document.createElement("div"); document.body.appendChild(host);
    const root = createRoot(host);
    await act(async () => root.render(<MemoryRouter><ColleagueBusinessLoopCard roleKey="data_advisor" logicIds={["D03"]} runtimeReadiness="runnable" /></MemoryRouter>));
    expect(host.textContent).toContain("经营问题与正式经营数据");
    expect(host.textContent).toContain("已版本化业务逻辑");
    expect(host.textContent).toContain("经营结论、证据与任务建议");
    expect(host.textContent).toContain("工作台贡献");
    expect(host.querySelector<HTMLAnchorElement>("[data-testid='colleague-enter-workshop']")?.getAttribute("href")).toContain("colleague=data_advisor");
    expect(host.querySelector<HTMLAnchorElement>("[data-testid='colleague-read-contribution']")?.getAttribute("href")).toContain("focus=contribution");
    await act(async () => root.unmount());
  });

  it("Logic 缺失时保持需核验且不出现伪造编号", async () => {
    const host = document.createElement("div"); document.body.appendChild(host);
    const root = createRoot(host);
    await act(async () => root.render(<MemoryRouter><ColleagueBusinessLoopCard roleKey="content_officer" logicIds={[]} runtimeReadiness="blocked" /></MemoryRouter>));
    expect(host.textContent).toContain("业务逻辑需核验");
    expect(host.textContent).not.toMatch(/C0\d/);
    await act(async () => root.unmount());
  });
});
