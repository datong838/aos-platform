// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const sdk = vi.hoisted(() => ({
  candidates: vi.fn(), memories: vi.fn(), candidateEvents: vi.fn(), query: vi.fn(),
  pipelinePolicies: vi.fn(), pipelineSchedules: vi.fn(), pipelineRuns: vi.fn(),
  transitionPipelineSchedule: vi.fn(), pipelineReceipt: vi.fn(), pipelineCheckpoint: vi.fn(), pipelineAlerts: vi.fn(),
}));
vi.mock("../../api/aipMemory", () => ({ aipMemorySdk: sdk }));

import { MemoryGovernancePage, authoritySubjectLabel, memoryStatusLabel } from "./MemoryGovernancePage";

describe("MemoryGovernancePage", () => {
  let host: HTMLDivElement;
  beforeEach(() => {
    host = document.createElement("div"); document.body.appendChild(host);
    Object.values(sdk).forEach((mock) => mock.mockReset());
    sdk.pipelinePolicies.mockResolvedValue([]); sdk.pipelineSchedules.mockResolvedValue([]); sdk.pipelineRuns.mockResolvedValue([]);
  });
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

  it("七条策略无 Schedule 时诚实禁用，不伪造运行", async () => {
    sdk.candidates.mockResolvedValue([]); sdk.memories.mockResolvedValue([]);
    sdk.pipelinePolicies.mockResolvedValue([{ pipelineKind: "seed_import", allowedTriggers: ["manual"], defaultStatus: "paused", requiredDependencies: ["license"], allowedReceiptTypes: ["aip.artifact_receipt"], allowedSourceKinds: ["authorized_document"] }]);
    const root = createRoot(host);
    await act(async () => root.render(<MemoryRouter><MemoryGovernancePage /></MemoryRouter>));
    await act(async () => undefined);
    const tab = host.querySelector('[data-testid="memory-tab-pipelines"]') as HTMLButtonElement;
    await act(async () => tab.click());
    expect(host.textContent).toContain("种子知识导入");
    expect(host.textContent).toContain("未注册 Schedule");
    expect((Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "等待权威配置") as HTMLButtonElement).disabled).toBe(true);
    await act(async () => root.unmount());
  });

  it("已暂停 Schedule 的启用动作调用真实 transition API", async () => {
    sdk.candidates.mockResolvedValue([]); sdk.memories.mockResolvedValue([]);
    sdk.pipelinePolicies.mockResolvedValue([{ pipelineKind: "seed_import", allowedTriggers: ["manual"], defaultStatus: "paused", requiredDependencies: ["license"], allowedReceiptTypes: ["aip.artifact_receipt"], allowedSourceKinds: ["authorized_document"] }]);
    sdk.pipelineSchedules.mockResolvedValue([{ tenant: { orgId: "org-org", projectId: "dev-project" }, scheduleId: "seed-1", pipelineKind: "seed_import", trigger: "manual", config: { artifactType: "pipeline-config", artifactId: "config-1", revision: "1", contentHash: "a".repeat(64) }, status: "paused", checkpointVersion: 0, version: 3, createdAt: "2026-08-13T00:00:00Z", updatedAt: "2026-08-13T00:00:00Z" }]);
    sdk.transitionPipelineSchedule.mockResolvedValue({});
    const root = createRoot(host);
    await act(async () => root.render(<MemoryRouter><MemoryGovernancePage /></MemoryRouter>));
    await act(async () => undefined);
    await act(async () => (host.querySelector('[data-testid="memory-tab-pipelines"]') as HTMLButtonElement).click());
    const action = Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "尝试启用") as HTMLButtonElement;
    await act(async () => action.click());
    expect(sdk.transitionPipelineSchedule).toHaveBeenCalledWith("seed-1", expect.objectContaining({ expectedVersion: 3, fromStatus: "paused", toStatus: "active" }));
    await act(async () => root.unmount());
  });
});
