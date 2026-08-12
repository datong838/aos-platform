// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const sdk = vi.hoisted(() => ({ candidates: vi.fn(), memories: vi.fn(), candidateEvents: vi.fn(), query: vi.fn() }));
vi.mock("../../api/aipMemory", () => ({ aipMemorySdk: sdk }));

import { MemoryGovernancePage, authoritySubjectLabel, memoryStatusLabel } from "./MemoryGovernancePage";

describe("MemoryGovernancePage", () => {
  let host: HTMLDivElement;
  beforeEach(() => { host = document.createElement("div"); document.body.appendChild(host); sdk.candidates.mockReset(); sdk.memories.mockReset(); sdk.candidateEvents.mockReset(); sdk.query.mockReset(); });
  afterEach(() => { host.remove(); });

  it("将权威状态和主体显示成人可读标签", () => {
    expect(memoryStatusLabel("quarantined")).toBe("已隔离");
    expect(authoritySubjectLabel({ resourceType: "Product", resourceId: "p-1" })).toBe("Product · p-1");
  });

  it("真实空列表保持空态，不注入静态知识", async () => {
    sdk.candidates.mockResolvedValue([]); sdk.memories.mockResolvedValue([]);
    const root = createRoot(host);
    await act(async () => root.render(<MemoryRouter><MemoryGovernancePage /></MemoryRouter>));
    await act(async () => undefined);
    expect(host.textContent).toContain("当前租户没有待治理或历史 Candidate");
    expect(host.textContent).not.toContain("示例 Candidate");
    await act(async () => root.unmount());
  });

  it("API 错误失败关闭且 query 初始不自动执行", async () => {
    sdk.candidates.mockRejectedValue(new Error("authority unavailable")); sdk.memories.mockResolvedValue([]);
    const root = createRoot(host);
    await act(async () => root.render(<MemoryRouter><MemoryGovernancePage /></MemoryRouter>));
    await act(async () => undefined);
    expect(host.textContent).toContain("Memory authority 读取失败");
    expect(sdk.query).not.toHaveBeenCalled();
    await act(async () => root.unmount());
  });
});
