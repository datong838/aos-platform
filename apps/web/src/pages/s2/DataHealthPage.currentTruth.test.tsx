// @vitest-environment jsdom

import { act } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DataHealthPage } from "./DataHealthPage";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const apiMocks = vi.hoisted(() => ({ apiGet: vi.fn(), apiGetAuthoritative: vi.fn(), apiPost: vi.fn() }));
vi.mock("../../api/client", () => apiMocks);

describe("R41 data health current truth", () => {
  afterEach(() => vi.clearAllMocks());

  it("renders unavailable consistency as unknown instead of a perfect score", async () => {
    apiMocks.apiGetAuthoritative.mockResolvedValue({
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
    apiMocks.apiGetAuthoritative.mockResolvedValue(summary);
    const host = document.createElement("div");
    document.body.appendChild(host);
    const root = createRoot(host);
    await act(async () => root.render(<MemoryRouter><DataHealthPage /></MemoryRouter>));
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    const button = Array.from(host.querySelectorAll("button")).find((item) => item.textContent === "刷新检查结果")!;
    await act(async () => { button.click(); await Promise.resolve(); await Promise.resolve(); });
    expect(apiMocks.apiGetAuthoritative).toHaveBeenLastCalledWith("/v1/data-health/summary");
    expect(apiMocks.apiPost).not.toHaveBeenCalled();
    expect(host.textContent).toContain("检查结果已刷新");
    act(() => root.unmount());
    host.remove();
  });

  it("hides the previous score after a failed refresh and recovers with a new observation", async () => {
    const summary = {
      overallScore: 100, completeness: 1, consistency: null, timeliness: 1,
      totalRules: 12, passingRules: 12, openIssues: 0, criticalIssues: 0,
      rules: [], issues: [], trend: [],
    };
    apiMocks.apiGetAuthoritative.mockResolvedValueOnce(summary)
      .mockRejectedValueOnce(new Error("当前数据暂时无法核验，请稍后重试"))
      .mockResolvedValueOnce({ ...summary, overallScore: 71 });
    const host = document.createElement("div");
    document.body.appendChild(host);
    const root = createRoot(host);
    try {
      await act(async () => root.render(<MemoryRouter><DataHealthPage /></MemoryRouter>));
      expect(host.textContent).toContain("100/100");
      const button = Array.from(host.querySelectorAll("button")).find((item) => item.textContent === "刷新检查结果")!;
      await act(async () => { button.click(); });
      expect(host.textContent).toContain("当前数据暂时无法核验");
      expect(host.textContent).not.toContain("总体评分");
      expect(host.textContent).not.toContain("通过规则");
      expect(host.textContent).not.toContain("暂无健康数据");
      expect(button.disabled).toBe(false);
      await act(async () => { button.click(); });
      expect(host.textContent).toContain("71/100");
      expect(host.textContent).not.toContain("当前数据暂时无法核验");
      expect(apiMocks.apiGetAuthoritative).toHaveBeenCalledTimes(3);
      expect(apiMocks.apiPost).not.toHaveBeenCalled();
    } finally {
      act(() => root.unmount());
      host.remove();
    }
  });
  it("rejects offline cached success when the current observation is unavailable", async () => {
    apiMocks.apiGet.mockResolvedValue({
      overallScore: 100, completeness: 1, consistency: 1, timeliness: 1,
      totalRules: 12, passingRules: 12, openIssues: 0, criticalIssues: 0,
      rules: [], issues: [], trend: [],
    });
    apiMocks.apiGetAuthoritative.mockRejectedValue(new Error("当前离线，无法校验权威状态"));
    const host = document.createElement("div");
    document.body.appendChild(host);
    const root = createRoot(host);
    try {
      await act(async () => root.render(<MemoryRouter><DataHealthPage /></MemoryRouter>));
      expect(host.textContent).toContain("当前离线");
      expect(host.textContent).not.toContain("总体评分");
      const button = Array.from(host.querySelectorAll("button")).find((item) => item.textContent === "刷新检查结果")!;
      await act(async () => { button.click(); });
      expect(host.textContent).not.toContain("检查结果已刷新");
      expect(apiMocks.apiGet).not.toHaveBeenCalled();
      expect(apiMocks.apiGetAuthoritative).toHaveBeenCalledTimes(2);
    } finally {
      act(() => root.unmount());
      host.remove();
    }
  });

});
