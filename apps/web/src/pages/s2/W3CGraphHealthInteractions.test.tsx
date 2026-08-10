// @vitest-environment jsdom

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { GraphHealthPage } from "./ontology";

const apiMocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiPut: vi.fn(),
  apiDelete: vi.fn(),
}));

vi.mock("../../api/client", () => apiMocks);

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

async function flush() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
  });
}

describe("Wave 3C W3 · Graph Health TTL 两阶段确认", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    Object.values(apiMocks).forEach((mock) => mock.mockReset());
    apiMocks.apiGet.mockResolvedValue({
      score: 98,
      metrics: { objectTypes: 2, instances: 4, edges: 3, orphanInstances: 1, archiveCandidates: 1, insightTtlDays: 90, engine: "live" },
      issues: [],
      archivePreview: [],
    });
  });

  afterEach(() => {
    act(() => root.unmount());
    host.remove();
  });

  it("首次点击只 dry-run，展示冻结候选，取消不执行写归档", async () => {
    apiMocks.apiPost.mockResolvedValue({
      dryRun: true,
      ttlDays: 90,
      candidateCount: 1,
      archivedCount: 0,
      archivedIds: [],
      candidates: [{ id: "insight-1", objectId: "obj-1", createdAt: "2026-01-01" }],
    });
    await act(async () => root.render(<MemoryRouter><GraphHealthPage /></MemoryRouter>));
    await flush();
    const run = Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find((button) => button.textContent === "运行 TTL 归档")!;
    await act(async () => run.click());
    await flush();

    expect(apiMocks.apiPost).toHaveBeenCalledTimes(1);
    expect(apiMocks.apiPost).toHaveBeenCalledWith("/v1/ops/ttl/run", { dryRun: true });
    expect(host.textContent).toContain("insight-1");
    expect(host.textContent).toContain("软归档");
    const cancel = Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find((button) => button.textContent === "取消")!;
    await act(async () => cancel.click());
    expect(apiMocks.apiPost).toHaveBeenCalledTimes(1);
    expect(host.textContent).not.toContain("确认归档 1 项");
  });

  it("确认使用冻结快照执行，校验回包后重读并清空预览", async () => {
    apiMocks.apiPost
      .mockResolvedValueOnce({ dryRun: true, ttlDays: 90, candidateCount: 1, archivedCount: 0, archivedIds: [], candidates: [{ id: "insight-1" }] })
      .mockResolvedValueOnce({ dryRun: false, ttlDays: 90, candidateCount: 1, archivedCount: 1, archivedIds: ["insight-1"], candidates: [{ id: "insight-1" }] });
    await act(async () => root.render(<MemoryRouter><GraphHealthPage /></MemoryRouter>));
    await flush();
    const run = Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find((button) => button.textContent === "运行 TTL 归档")!;
    await act(async () => run.click());
    await flush();
    const confirm = Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find((button) => button.textContent === "确认归档 1 项")!;
    await act(async () => confirm.click());
    await flush();

    expect(apiMocks.apiPost).toHaveBeenNthCalledWith(2, "/v1/ops/ttl/run", { dryRun: false });
    expect(apiMocks.apiGet).toHaveBeenCalledTimes(2);
    expect(host.textContent).toContain("已软归档 1");
    expect(host.textContent).not.toContain("确认归档 1 项");
  });

  it("dry-run 为零候选时禁用执行", async () => {
    apiMocks.apiPost.mockResolvedValue({
      dryRun: true,
      ttlDays: 90,
      candidateCount: 0,
      archivedCount: 0,
      archivedIds: [],
      candidates: [],
    });
    await act(async () => root.render(<MemoryRouter><GraphHealthPage /></MemoryRouter>));
    await flush();
    const run = Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find((button) => button.textContent === "运行 TTL 归档")!;
    await act(async () => run.click());
    await flush();

    const confirm = Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find((button) => button.textContent === "确认归档 0 项")!;
    expect(confirm.disabled).toBe(true);
    expect(host.textContent).toContain("无归档候选");
  });

  it("dry-run 失败时不打开确认区", async () => {
    apiMocks.apiPost.mockRejectedValue(new Error("dry-run unavailable"));
    await act(async () => root.render(<MemoryRouter><GraphHealthPage /></MemoryRouter>));
    await flush();
    const run = Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find((button) => button.textContent === "运行 TTL 归档")!;
    await act(async () => run.click());
    await flush();

    expect(host.textContent).toContain("dry-run unavailable");
    expect(host.querySelector("[data-testid='ttl-confirmation']")).toBeNull();
  });

  it("执行候选与冻结快照不一致时 fail-closed 并保留预览", async () => {
    apiMocks.apiPost
      .mockResolvedValueOnce({ dryRun: true, ttlDays: 90, candidateCount: 1, archivedCount: 0, archivedIds: [], candidates: [{ id: "insight-1" }] })
      .mockResolvedValueOnce({ dryRun: false, ttlDays: 90, candidateCount: 1, archivedCount: 1, archivedIds: ["insight-2"], candidates: [{ id: "insight-2" }] });
    await act(async () => root.render(<MemoryRouter><GraphHealthPage /></MemoryRouter>));
    await flush();
    const run = Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find((button) => button.textContent === "运行 TTL 归档")!;
    await act(async () => run.click());
    await flush();
    const confirm = Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find((button) => button.textContent === "确认归档 1 项")!;
    await act(async () => confirm.click());
    await flush();

    expect(host.textContent).toContain("执行回包与冻结快照不一致");
    expect(host.textContent).not.toContain("TTL 归档完成");
    expect(host.textContent).toContain("insight-1");
    expect(host.querySelector("[data-testid='ttl-confirmation']")).not.toBeNull();
    expect(apiMocks.apiGet).toHaveBeenCalledTimes(1);
  });

  it("展示可复算计分、属性分类，并区分普通无边与必需关系缺失", async () => {
    apiMocks.apiGet.mockResolvedValue({
      score: 75,
      scoreStatus: "known",
      scoreVersion: "GH-SCORE-v2",
      breakdown: [
        { code: "GH-03", affectedObjects: 20, denominator: 100, rate: 0.2, threshold: 0.1, maxDeduction: 25, deduction: 25 },
      ],
      metrics: {
        objectTypes: 12, instances: 617, edges: 492, orphanInstances: 20, unlinkedInstances: 237,
        requiredLinkEligible: 300, danglingEdges: 0, propConflicts: 0, engine: "ecom_authoritative",
        propertyClassification: { canonical: 5000, system: 400, compatibilityAlias: 8, actualConflict: 0 },
      },
      issues: [{ code: "GH-03", object: "必需关系缺失 ×20", message: "仅统计必需关系" }],
    });
    await act(async () => root.render(<MemoryRouter><GraphHealthPage /></MemoryRouter>));
    await flush();

    expect(host.textContent).toContain("公式=GH-SCORE-v2");
    expect(host.textContent).toContain("兼容别名 8");
    expect(host.textContent).toContain("普通无边对象 237 不直接扣分");
    expect(host.textContent).toContain("20 / 100");
    expect(host.querySelector("select[aria-label='图谱健康问题类型']")).not.toBeNull();
    expect(host.textContent).toContain("问题图谱");
  });
});
