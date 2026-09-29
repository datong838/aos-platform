// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const product = vi.hoisted(() => ({
  loadSkillBindingEvaluationCandidate: vi.fn(), previewSkillBindingEvaluation: vi.fn(),
  evaluateSkillBinding: vi.fn(), activateSkillBinding: vi.fn(), readSkillBindingForReconciliation: vi.fn(),
}));
vi.mock("../../api/aipAgentControl/skillBindingLifecycleProduct", () => product);
import { SkillBindingLifecyclePanel } from "./SkillBindingLifecyclePanel";

const hash = "a".repeat(64);
const tenant = { orgId: "org-org", projectId: "dev-project" };
const ref = (assetType: string, assetId: string) => ({ assetType, assetId, revision: 1, contentHash: hash });
const skill = { skillId: "ecommerce.skill.D01", revision: 2, contentHash: hash, lifecycle: "published" };
const binding = { tenant, bindingId: "binding-d01", instanceId: "ecommerce.data_advisor.default",
  skill: { ...ref("SkillTemplate", skill.skillId), revision: 2 }, capabilityBindingIds: ["cap-data"],
  budgetPolicyRef: ref("BudgetPolicyRevision", "budget"), status: "provisioning", version: 1,
  readiness: "unknown", dependencySnapshotHash: null, readinessExpiresAt: null };
const item = { instance: { tenant, instanceId: binding.instanceId, status: "active" } };
const candidate = { bindingId: binding.bindingId, instanceId: binding.instanceId, expectedVersion: 1,
  skill: binding.skill, capabilityBindingIds: binding.capabilityBindingIds, budgetPolicyRef: binding.budgetPolicyRef,
  dependencies: { modelRouteRef: ref("ModelRouteRevision", "route"),
    runtimePolicyRef: ref("RuntimePolicyRevision", "policy"), evalGateRef: ref("EvalGateDecision", "gate"),
    budgetPolicyRef: binding.budgetPolicyRef } };
const preview = { readiness: "available", reasons: [], dependencySnapshotHash: hash,
  evaluatedAt: "2026-09-29T01:00:00Z", expiresAt: "2099-09-29T01:15:00Z" };

describe("SkillBindingLifecyclePanel", () => {
  let host: HTMLDivElement;
  let root: Root;
  const button = (label: string) => Array.from(host.querySelectorAll("button")).find((value) => value.textContent?.includes(label));
  beforeEach(() => {
    localStorage.clear(); host = document.createElement("div"); document.body.append(host); root = createRoot(host);
    vi.clearAllMocks();
    product.loadSkillBindingEvaluationCandidate.mockResolvedValue({ candidate, blockers: [] });
    product.previewSkillBindingEvaluation.mockResolvedValue(preview);
    product.evaluateSkillBinding.mockResolvedValue({ version: 2, receiptId: "receipt-eval", dependencySnapshotHash: hash,
      readiness: "available", expiresAt: preview.expiresAt });
    product.activateSkillBinding.mockResolvedValue({ version: 3, receiptId: "receipt-active" });
    product.readSkillBindingForReconciliation.mockResolvedValue({ status: "provisioning", version: 2 });
    vi.stubGlobal("crypto", { randomUUID: () => "123e4567-e89b-12d3-a456-426614174000" });
  });
  afterEach(() => { act(() => root.unmount()); host.remove(); vi.unstubAllGlobals(); });

  it("keeps current evaluated D01 closed without a preview or command", async () => {
    await act(async () => root.render(<SkillBindingLifecyclePanel item={item} skill={{ ...skill, lifecycle: "evaluated" }} binding={binding} onUpdated={vi.fn()} />));
    expect(host.textContent).toContain("正式发布");
    expect(product.loadSkillBindingEvaluationCandidate).not.toHaveBeenCalled();
    expect(button("核验评估候选")).toBeUndefined();
  });

  it("requires preview and explicit confirmation before evaluating once", async () => {
    const onUpdated = vi.fn();
    await act(async () => root.render(<SkillBindingLifecyclePanel item={item} skill={skill} binding={binding} onUpdated={onUpdated} />));
    await act(async () => button("核验评估候选")!.click());
    expect(product.evaluateSkillBinding).not.toHaveBeenCalled();
    await act(async () => button("确认评估绑定")!.click());
    expect(product.evaluateSkillBinding).toHaveBeenCalledTimes(1);
    expect(host.textContent).toContain("receipt-eval");
    expect(onUpdated).toHaveBeenCalledTimes(1);
    expect(localStorage.length).toBe(0);
  });

  it("shows Owner preview blockers without creating an evaluation Receipt", async () => {
    product.previewSkillBindingEvaluation.mockResolvedValue({ ...preview, readiness: "blocked", reasons: ["MODEL_ROUTE_BLOCKED"] });
    await act(async () => root.render(<SkillBindingLifecyclePanel item={item} skill={skill} binding={binding} onUpdated={vi.fn()} />));
    await act(async () => button("核验评估候选")!.click());
    expect(host.textContent).toContain("MODEL_ROUTE_BLOCKED");
    expect(button("确认评估绑定")).toBeUndefined();
    expect(product.evaluateSkillBinding).not.toHaveBeenCalled();
  });

  it("offers activation only for matching fresh persisted readiness", async () => {
    const evaluated = { ...binding, version: 2, readiness: "available", dependencySnapshotHash: hash,
      readinessExpiresAt: preview.expiresAt };
    await act(async () => root.render(<SkillBindingLifecyclePanel item={item} skill={skill} binding={evaluated} onUpdated={vi.fn()} />));
    await act(async () => button("核验激活候选")!.click());
    expect(button("确认激活绑定")).toBeTruthy();
    await act(async () => button("确认激活绑定")!.click());
    expect(product.activateSkillBinding).toHaveBeenCalledTimes(1);
    expect(host.textContent).toContain("receipt-active");
  });

  it("retains unknown command marker and only offers read-only reconciliation", async () => {
    product.evaluateSkillBinding.mockImplementation(async (...args: unknown[]) => {
      (args[3] as () => void)();
      throw new Error("connection lost after send");
    });
    await act(async () => root.render(<SkillBindingLifecyclePanel item={item} skill={skill} binding={binding} onUpdated={vi.fn()} />));
    await act(async () => button("核验评估候选")!.click());
    await act(async () => button("确认评估绑定")!.click());
    expect(localStorage.length).toBe(1);
    expect(host.textContent).toContain("禁止重发");
    expect(button("确认评估绑定")).toBeUndefined();
    await act(async () => button("只读对账")!.click());
    expect(product.readSkillBindingForReconciliation).toHaveBeenCalledTimes(1);
    expect(product.evaluateSkillBinding).toHaveBeenCalledTimes(1);
    expect(localStorage.length).toBe(1);
  });

  it("does not leave an unknown marker when read-only precheck rejects before send", async () => {
    product.evaluateSkillBinding.mockRejectedValue(new Error("version drift before send"));
    await act(async () => root.render(<SkillBindingLifecyclePanel item={item} skill={skill} binding={binding} onUpdated={vi.fn()} />));
    await act(async () => button("核验评估候选")!.click());
    await act(async () => button("确认评估绑定")!.click());
    expect(host.textContent).toContain("命令未发送，请重新核验");
    expect(localStorage.length).toBe(0);
    expect(button("只读对账")).toBeUndefined();
  });
});
