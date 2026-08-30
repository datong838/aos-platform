import { beforeEach, describe, expect, it, vi } from "vitest";

const { apiGet, apiPost } = vi.hoisted(() => ({ apiGet: vi.fn(), apiPost: vi.fn() }));
vi.mock("../client", () => ({ apiGet, apiPost }));
vi.mock("../tenant", () => ({ getTenant: () => ({ orgId: "org-org", projectId: "dev-project" }) }));

import { aipAgentControl } from "./index";

const hash = "a".repeat(64);
const tenant = { orgId: "org-org", projectId: "dev-project" };
const resource = (resourceType: string, resourceId: string) => ({ resourceType, resourceId, revision: "1", authority: "aip" });
const asset = (assetType: string, assetId: string) => ({ assetType, assetId, revision: 1, contentHash: hash });

describe("aipAgentControl read-only exact-ref client", () => {
  beforeEach(() => { apiGet.mockReset(); apiPost.mockReset(); });

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

  it("显式 issue/consume/decision，且 token 只进入当前 consume body", async () => {
    const envelope = { tenant, handoffId: "handoff-1", envelope: { taskRef: resource("Task", "task-1"), runRef: resource("TaskRun", "run-1"), senderInstance: asset("AgentInstance", "agent-1"), receiverInstance: asset("AgentInstance", "agent-2"), objectRefs: [], artifactRefs: [], evidenceRefs: [], context: {}, allowedContextFields: [], markings: ["internal"], expiresAt: "2026-08-24T11:00:00Z" }, status: "issued", version: 1, consumedAt: null, createdAt: "2026-08-24T10:00:00Z" };
    const receipt = (operation: string, resultType: string, resultId: string) => ({ tenant, receiptId: `receipt-${operation}`, operation, idempotencyKey: "idem-1", requestHash: "b".repeat(64), resourceRef: resource("TaskRun", "run-1"), resultRef: resource(resultType, resultId), status: "applied", createdBy: "user:dev", createdAt: "2026-08-24T10:00:00Z" });
    const issueInput = { handoffId: "handoff-1", envelope: envelope.envelope };
    apiPost.mockResolvedValueOnce({ handoff: envelope, bearerToken: "t".repeat(40), receipt: receipt("handoff.issue", "HandoffEnvelope", "handoff-1") });
    await expect(aipAgentControl.issueHandoff(issueInput, "issue-1")).resolves.toMatchObject({ bearerToken: "t".repeat(40) });
    expect(apiPost).toHaveBeenLastCalledWith("/v1/aip/handoffs", issueInput, { "Idempotency-Key": "issue-1" });

    const consumeInput = { bearerToken: "t".repeat(40), receiverInstance: asset("AgentInstance", "agent-2") };
    apiPost.mockResolvedValueOnce({ ...envelope, status: "consumed", version: 2, consumedAt: "2026-08-24T10:05:00Z" });
    await expect(aipAgentControl.consumeHandoff("handoff-1", consumeInput)).resolves.toMatchObject({ status: "consumed" });
    expect(apiPost).toHaveBeenLastCalledWith("/v1/aip/handoffs/handoff-1/consume", consumeInput);

    const decisionInput = { decision: "accepted" as const, expectedHeadVersion: 0, reasonCode: null, gapCodes: [], returnRefs: [], correlationRef: null, receiverInstance: asset("AgentInstance", "agent-2") };
    const decision = { tenant, decisionId: "decision-1", handoffId: "handoff-1", revision: 1, envelopeRef: resource("HandoffEnvelope", "handoff-1"), decision: "accepted", reasonCode: null, gapCodes: [], returnRefs: [], correlationRef: null, receiverInstance: asset("AgentInstance", "agent-2"), contentHash: "c".repeat(64), createdBy: "user:dev", createdAt: "2026-08-24T10:06:00Z" };
    apiPost.mockResolvedValueOnce({ decision, receipt: receipt("handoff.decision", "HandoffDecisionRevision", "decision-1") });
    await expect(aipAgentControl.createHandoffDecision("handoff-1", decisionInput, "decision-1")).resolves.toMatchObject({ decision: { decision: "accepted" } });
    expect(apiPost).toHaveBeenLastCalledWith("/v1/aip/handoffs/handoff-1/decisions", decisionInput, { "Idempotency-Key": "decision-1" });
  });

  it("命令输入对路径、幂等键和 bearer 失败关闭", async () => {
    await expect(aipAgentControl.consumeHandoff("../handoff", { bearerToken: "t".repeat(40), receiverInstance: asset("AgentInstance", "agent-2") })).rejects.toThrow("handoffId 非法");
    await expect(aipAgentControl.consumeHandoff("handoff-1", { bearerToken: " bad ", receiverInstance: asset("AgentInstance", "agent-2") })).rejects.toThrow("bearerToken 非法");
    await expect(aipAgentControl.issueHandoff({ handoffId: "handoff-1", envelope: {} as never }, " bad ")).rejects.toThrow("Idempotency-Key 非法");
  });

  it("发布与停用命令始终携带精确实例版本和幂等键", async () => {
    const instance = { tenant, instanceId: "agent-1", instanceRef: asset("AgentInstance", "agent-1"), template: asset("AgentTemplate", "template-1"), status: "active", overlay: { displayName: "数据参谋", allowedCapabilityIds: [] }, version: 2, updatedAt: "2026-08-30T00:00:00Z" };
    const receipt = { tenant, receiptId: "receipt-1", operation: "agent.activate", idempotencyKey: "activate-1", requestHash: "b".repeat(64), resourceRef: resource("AgentInstance", "agent-1"), resultRef: resource("AgentInstance", "agent-1"), status: "applied", createdBy: "user:dev", createdAt: "2026-08-30T00:00:00Z" };
    apiPost.mockResolvedValueOnce({ tenant, instance, capabilityBindingIds: ["binding-1"], receipt });
    await aipAgentControl.activateAgent("agent-1", 1, ["binding-1"], "activate-1");
    expect(apiPost).toHaveBeenLastCalledWith("/v1/aip/agents/agent-1/activate", { expectedVersion: 1, capabilityBindingIds: ["binding-1"] }, { "Idempotency-Key": "activate-1" });
    apiPost.mockResolvedValueOnce({ tenant, instance: { ...instance, status: "suspended", version: 3 }, capabilityBindingIds: [], receipt: { ...receipt, operation: "agent.suspend" } });
    await aipAgentControl.suspendAgent("agent-1", 2, "工作台人工停用回滚", "suspend-1");
    expect(apiPost).toHaveBeenLastCalledWith("/v1/aip/agents/agent-1/suspend", { expectedVersion: 2, reason: "工作台人工停用回滚" }, { "Idempotency-Key": "suspend-1" });
  });

  it("AgentRun 安全关联使用精确引用并在 queued 状态形成取消 Receipt", async () => {
    const request = {
      taskRef: resource("Task", "task-1"), planRef: resource("PlanRevision", "plan-1"),
      agentInstance: asset("AgentInstance", "agent-1"), skill: asset("SkillTemplate", "skill-1"),
      logic: asset("LogicRevision", "logic-1"), modelRoute: asset("ModelRouteRevision", "route-1"),
      policy: asset("RuntimePolicyRevision", "policy-1"), inputRefs: [],
    };
    const run = { tenant, agentRunId: "agent-run-1", taskId: "task-1", taskRunId: "task-run-1", instanceId: "agent-1", instanceVersion: 1, skillBindingId: "binding-1", request, status: "queued", version: 1, createdAt: "2026-08-30T00:00:00Z", updatedAt: "2026-08-30T00:00:00Z" };
    const receipt = (operation: string, idempotencyKey: string) => ({ tenant, receiptId: `receipt-${operation}`, operation, idempotencyKey, requestHash: "b".repeat(64), resourceRef: resource("AgentRun", "agent-run-1"), resultRef: resource("AgentRun", "agent-run-1"), status: "applied", createdBy: "user:dev", createdAt: "2026-08-30T00:00:00Z" });
    const createInput = { agentRunId: "agent-run-1", taskRunRef: resource("TaskRun", "task-run-1"), skillBindingId: "binding-1", run: request };
    apiPost.mockResolvedValueOnce({ tenant, agentRun: run, receipt: receipt("agent_run.create", "create-run-1") });
    await expect(aipAgentControl.createAgentRun(createInput, "create-run-1")).resolves.toMatchObject({ agentRun: { status: "queued" } });
    expect(apiPost).toHaveBeenLastCalledWith("/v1/aip/agent-runs", createInput, { "Idempotency-Key": "create-run-1" });
    apiPost.mockResolvedValueOnce({ tenant, agentRun: { ...run, status: "cancelled", version: 2 }, receipt: receipt("agent_run.cancel_queued", "cancel-run-1") });
    await expect(aipAgentControl.cancelQueuedAgentRun("agent-run-1", 1, "确定性沙箱验收完成", "cancel-run-1")).resolves.toMatchObject({ agentRun: { status: "cancelled" }, receipt: { operation: "agent_run.cancel_queued" } });
    expect(apiPost).toHaveBeenLastCalledWith("/v1/aip/agent-runs/agent-run-1/cancel-queued", { expectedVersion: 1, reason: "确定性沙箱验收完成" }, { "Idempotency-Key": "cancel-run-1" });
  });
});
