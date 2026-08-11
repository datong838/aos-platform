import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { AipTasksSdk, TaskTimeline } from "../../api/aipTasks";
import { CanonicalTaskRunPanel } from "./CanonicalTaskRunPanel";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const actor = { actorType: "user", actorId: "operator" };
function timeline(taskStatus = "approved", runStatus = "queued"): TaskTimeline {
  return {
    task: { id: "task-1", type: "logic_graph_run", title: "运行", description: "", status: taskStatus as TaskTimeline["task"]["status"], priority: 50, goal: {}, selectionRef: null, policyRevision: null, createdBy: actor, createdAt: "2026-08-11T01:00:00Z", currentPlanRevisionId: "plan-1", version: 3, updatedAt: "2026-08-11T01:00:00Z" },
    plan: { id: "plan-1", taskId: "task-1", revision: 1, contentHash: "a".repeat(64), steps: [{ stepKey: "execute", title: "执行" }], dependencies: [], risk: {}, approvalStatus: "approved", approvedBy: "operator", approvedAt: "2026-08-11T01:00:00Z", createdBy: actor, createdAt: "2026-08-11T01:00:00Z" },
    run: { id: "run-1", taskId: "task-1", planRevisionId: "plan-1", status: runStatus as TaskTimeline["run"]["status"], startedAt: null, finishedAt: null, lastCheckpointId: null, logicGraphId: "logic-1", logicRevision: 2, version: 1, createdBy: actor, createdAt: "2026-08-11T01:00:00Z", updatedAt: "2026-08-11T01:00:00Z" },
    steps: [], checkpoints: [], artifacts: [], evidence: [],
  };
}

function button(host: HTMLElement, label: string): HTMLButtonElement {
  const found = [...host.querySelectorAll<HTMLButtonElement>("button")].find((item) => item.textContent?.includes(label));
  if (!found) throw new Error(`button not found: ${label}`);
  return found;
}

describe("CanonicalTaskRunPanel", () => {
  let host: HTMLDivElement;
  let root: Root;
  beforeEach(() => { host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host); });
  afterEach(() => { act(() => root.unmount()); host.remove(); });

  it("刷新后按 graph 从服务端恢复 queued Run，并只开放合法控制", async () => {
    const data = timeline();
    const sdk = {
      listRunsByLogic: vi.fn().mockResolvedValue({ items: [data.run], count: 1 }),
      timeline: vi.fn().mockResolvedValue(data),
    } as unknown as AipTasksSdk;
    await act(async () => root.render(<CanonicalTaskRunPanel graphId="logic-1" graphRevision={2} graphName="真实逻辑" sdk={sdk} />));
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    expect(host.textContent).toContain("等待启动");
    expect(host.textContent).toContain("PostgreSQL authority");
    expect(button(host, "启动").disabled).toBe(false);
    expect(button(host, "暂停").disabled).toBe(true);
    expect(sdk.listRunsByLogic).toHaveBeenCalledWith("logic-1");
  });

  it("unknown 明确要求对账并禁用重复动作", async () => {
    const data = timeline("paused", "unknown");
    const sdk = { listRunsByLogic: vi.fn().mockResolvedValue({ items: [data.run], count: 1 }), timeline: vi.fn().mockResolvedValue(data) } as unknown as AipTasksSdk;
    await act(async () => root.render(<CanonicalTaskRunPanel graphId="logic-1" graphRevision={2} graphName="真实逻辑" sdk={sdk} />));
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    expect(host.textContent).toContain("外部动作结果不确定");
    expect(button(host, "启动").disabled).toBe(true);
    expect(button(host, "恢复").disabled).toBe(true);
    expect(button(host, "取消").disabled).toBe(true);
  });
});
