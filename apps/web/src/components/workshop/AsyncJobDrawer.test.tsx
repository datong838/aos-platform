import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { AsyncJobProjection } from "../../api/aipAsyncJobs";
import { AsyncJobDrawer } from "./AsyncJobDrawer";

const projection: AsyncJobProjection = {
  tenant: { orgId: "org-org", projectId: "dev-project" }, count: 2,
  items: [
    { jobRef: { authority: "aos.research_job", authorityType: "research_job", jobId: "research-1", version: "2" }, taskRef: null, subjectRefs: [], status: "running", displayStatus: "partial", progress: { state: "partial", completedUnits: null, totalUnits: null }, partialRefs: [{ resourceType: "aip.artifact", resourceId: "artifact-1", revision: "a".repeat(64), authority: "aos.artifact" }], cancelability: "cancelable", resumability: "unsupported", reconcileRequired: false, cancelRequested: false, checkpointRef: null, receiptRefs: [], lineageRef: "aip.lineage/l-1@1", startedAt: "2026-08-25T01:00:00Z", updatedAt: "2026-08-25T01:01:00Z", deadline: null, nextPollAt: null, owner: "tester", blockedReasons: ["research_job_not_resumable"], permissions: { canCancel: true, canRetry: false, canReconcile: false } },
    { jobRef: { authority: "aos.knowledge_pipeline", authorityType: "knowledge_pipeline_run", jobId: "pipeline-1", version: "4" }, taskRef: null, subjectRefs: [], status: "paused", displayStatus: "paused", progress: { state: "unknown", completedUnits: null, totalUnits: null }, partialRefs: [], cancelability: "authority_owned", resumability: "supported", reconcileRequired: false, cancelRequested: false, checkpointRef: { resourceType: "aip.knowledge_pipeline_checkpoint_revision", resourceId: "schedule-1", revision: "3", authority: "aos.knowledge_pipeline" }, receiptRefs: [], lineageRef: null, startedAt: null, updatedAt: "2026-08-25T01:02:00Z", deadline: null, nextPollAt: null, owner: null, blockedReasons: ["knowledge_pipeline_commands_owned_by_pipeline_authority"], permissions: { canCancel: false, canRetry: false, canReconcile: false } },
  ],
};

describe("AsyncJobDrawer", () => {
  let host: HTMLDivElement; let root: Root;
  beforeEach(() => { host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host); });
  afterEach(() => { act(() => root.unmount()); host.remove(); });
  it("展示 partial 证据并不在统一视图提交命令", async () => {
    await act(async () => root.render(<AsyncJobDrawer load={vi.fn().mockResolvedValue(projection)} />));
    expect(host.textContent).toContain("研究任务"); expect(host.textContent).toContain("partial");
    expect(host.textContent).toContain("部分产物1"); expect(host.textContent).toContain("research_job_not_resumable");
    expect(Array.from(host.querySelectorAll<HTMLButtonElement>("button")).filter((button) => ["取消", "重试", "对账"].some((label) => button.textContent?.includes(label))).every((button) => button.disabled)).toBe(true);
  });
  it("切换流水线任务展示 exact checkpoint 与 authority 边界", async () => {
    await act(async () => root.render(<AsyncJobDrawer load={vi.fn().mockResolvedValue(projection)} />));
    const pipeline = Array.from(host.querySelectorAll<HTMLButtonElement>('nav button')).find((button) => button.textContent?.includes("pipeline-1"));
    act(() => pipeline?.click());
    expect(host.textContent).toContain("schedule-1@3");
    expect(host.textContent).toContain("knowledge_pipeline_commands_owned_by_pipeline_authority");
    expect(host.textContent).toContain("统一视图不复制命令状态机");
  });
  it("读取失败关闭且不自动重试", async () => {
    const load = vi.fn().mockRejectedValue(new Error("offline"));
    await act(async () => root.render(<AsyncJobDrawer load={load} />));
    expect(load).toHaveBeenCalledTimes(1); expect(host.textContent).toContain("读取失败关闭"); expect(host.textContent).toContain("未自动重试");
  });
});
