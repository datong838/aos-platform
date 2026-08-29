// @vitest-environment jsdom

import { act } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DataHealthPage } from "./DataHealthPage";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const apiMocks = vi.hoisted(() => ({ apiGet: vi.fn(), apiPost: vi.fn() }));
vi.mock("../../api/client", () => apiMocks);

describe("R41 data health current truth", () => {
  afterEach(() => vi.clearAllMocks());

  it("renders unavailable consistency as unknown instead of a perfect score", async () => {
    apiMocks.apiGet.mockResolvedValue({
      overallScore: 100,
      completeness: 1,
      consistency: null,
      timeliness: 1,
      totalRules: 1,
      passingRules: 1,
      openIssues: 0,
      criticalIssues: 0,
      rules: [],
      issues: [],
      trend: [{ date: "2026-08-29", score: 100 }],
    });
    const host = document.createElement("div");
    document.body.appendChild(host);
    const root = createRoot(host);
    await act(async () => root.render(<MemoryRouter><DataHealthPage /></MemoryRouter>));
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    expect(host.textContent).toContain("一致率未知");
    expect(host.textContent).not.toContain("一致率100%");
    act(() => root.unmount());
    host.remove();
  });

  it("refreshes the current GET summary and never posts to a missing check endpoint", async () => {
    const summary = {
      overallScore: 71, completeness: 0.75, consistency: null, timeliness: 2 / 3,
      totalRules: 12, passingRules: 9, openIssues: 3, criticalIssues: 3,
      rules: [], issues: [], trend: [{ date: "2026-08-29", score: 67 }],
    };
    apiMocks.apiGet.mockResolvedValue(summary);
    const host = document.createElement("div");
    document.body.appendChild(host);
    const root = createRoot(host);
    await act(async () => root.render(<MemoryRouter><DataHealthPage /></MemoryRouter>));
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    const button = Array.from(host.querySelectorAll("button")).find((item) => item.textContent === "刷新检查结果")!;
    await act(async () => { button.click(); await Promise.resolve(); await Promise.resolve(); });
    expect(apiMocks.apiGet).toHaveBeenLastCalledWith("/v1/data-health/summary");
    expect(apiMocks.apiPost).not.toHaveBeenCalled();
    expect(host.textContent).toContain("检查结果已刷新");
    act(() => root.unmount());
    host.remove();
  });
});
