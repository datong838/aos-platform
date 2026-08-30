import { describe, expect, it } from "vitest";

import { parseTaskRun, parseTimeline } from "./contracts";

const actor = { actorType: "user", actorId: "operator" };
const task = {
  id: "task-1", type: "logic_graph_run", title: "权威运行", description: "", status: "approved",
  priority: 50, goal: {}, selectionRef: null, policyRevision: null, createdBy: actor,
  createdAt: "2026-08-11T01:00:00Z", currentPlanRevisionId: "plan-1", version: 3,
  updatedAt: "2026-08-11T01:00:00Z",
};
const plan = {
  id: "plan-1", taskId: "task-1", revision: 1, contentHash: "a".repeat(64),
  steps: [{ stepKey: "execute", title: "执行" }], dependencies: [], risk: {},
  approvalStatus: "approved", approvedBy: "operator", approvedAt: "2026-08-11T01:00:00Z",
  createdBy: actor, createdAt: "2026-08-11T01:00:00Z",
};
const run = {
  id: "run-1", taskId: "task-1", planRevisionId: "plan-1", status: "queued",
  startedAt: null, finishedAt: null, lastCheckpointId: null, logicGraphId: "logic-1",
  logicRevision: 3, version: 1, createdBy: actor, createdAt: "2026-08-11T01:00:00Z",
  updatedAt: "2026-08-11T01:00:00Z",
};

describe("aipTasks contracts", () => {
  it("严格解析相互一致的 Task/Plan/Run timeline", () => {
    const timeline = parseTimeline({ task, plan, run, steps: [], checkpoints: [], artifacts: [], evidence: [] });
    expect(timeline.run.logicGraphId).toBe("logic-1");
    expect(timeline.plan.contentHash).toHaveLength(64);
  });

  it("接受权威暂停中间态，同时对未知状态和跨资源引用失败关闭", () => {
    expect(parseTaskRun({ ...run, status: "pausing" }).status).toBe("pausing");
    expect(parseTaskRun({ ...run, status: "paused" }).status).toBe("paused");
    expect(() => parseTaskRun({ ...run, status: "mostly-done" })).toThrow("unknown status");
    expect(() => parseTimeline({ task, plan, run: { ...run, taskId: "other" }, steps: [], checkpoints: [], artifacts: [], evidence: [] }))
      .toThrow("资源引用不一致");
  });
});
