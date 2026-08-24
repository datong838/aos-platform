import { beforeEach, describe, expect, it, vi } from "vitest";

const { apiGet } = vi.hoisted(() => ({ apiGet: vi.fn() }));
vi.mock("../client", () => ({ apiGet, apiPost: vi.fn() }));
vi.mock("../tenant", () => ({ getTenant: () => ({ orgId: "org-org", projectId: "dev-project" }) }));

import { aipAgentControl } from "./index";

const hash = "a".repeat(64);
const tenant = { orgId: "org-org", projectId: "dev-project" };
const resource = (resourceType: string, resourceId: string) => ({ resourceType, resourceId, revision: "1", authority: "aip" });
const asset = (assetType: string, assetId: string) => ({ assetType, assetId, revision: 1, contentHash: hash });

describe("aipAgentControl read-only exact-ref client", () => {
  beforeEach(() => apiGet.mockReset());

  it("读取 canonical AgentRun 且拒绝路径注入", async () => {
    apiGet.mockResolvedValue({ tenant, agentRunId: "run-1", taskId: "task-1", taskRunId: "task-run-1", instanceId: "agent-1", instanceVersion: 1, skillBindingId: "binding-1", request: { taskRef: resource("Task", "task-1"), planRef: resource("PlanRevision", "plan-1"), agentInstance: asset("AgentInstance", "agent-1"), skill: asset("SkillTemplate", "skill-1"), logic: asset("LogicRevision", "logic-1"), modelRoute: asset("ModelRouteRevision", "route-1"), policy: asset("RuntimePolicyRevision", "policy-1"), inputRefs: [] }, status: "running", version: 1, createdAt: "2026-08-24T10:00:00Z", updatedAt: "2026-08-24T10:01:00Z" });
    await expect(aipAgentControl.getAgentRun("run-1")).resolves.toMatchObject({ agentRunId: "run-1" });
    expect(apiGet).toHaveBeenCalledWith("/v1/aip/agent-runs/run-1");
    await expect(aipAgentControl.getAgentRun("../run-1")).rejects.toThrow("agentRunId 非法");
  });

  it("读取 canonical Handoff 与 Decision 列表", async () => {
    apiGet.mockResolvedValueOnce({ tenant, handoffId: "handoff-1", envelope: { taskRef: resource("Task", "task-1"), runRef: resource("TaskRun", "run-1"), senderInstance: asset("AgentInstance", "agent-1"), receiverInstance: asset("AgentInstance", "agent-2"), objectRefs: [], artifactRefs: [], evidenceRefs: [], context: {}, allowedContextFields: [], markings: ["internal"], expiresAt: "2026-08-24T11:00:00Z" }, status: "issued", version: 1, consumedAt: null, createdAt: "2026-08-24T10:00:00Z" });
    await expect(aipAgentControl.getHandoff("handoff-1")).resolves.toMatchObject({ handoffId: "handoff-1" });
    expect(apiGet).toHaveBeenLastCalledWith("/v1/aip/handoffs/handoff-1");
    apiGet.mockResolvedValueOnce({ tenant, handoffId: "handoff-1", items: [], count: 0, headVersion: 0 });
    await expect(aipAgentControl.listHandoffDecisions("handoff-1")).resolves.toMatchObject({ count: 0 });
    expect(apiGet).toHaveBeenLastCalledWith("/v1/aip/handoffs/handoff-1/decisions");
  });
});
