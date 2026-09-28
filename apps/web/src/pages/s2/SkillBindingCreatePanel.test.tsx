// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const product = vi.hoisted(() => ({ loadSkillBindingCandidate: vi.fn(), createProvisioningSkillBinding: vi.fn() }));
vi.mock("../../api/aipAgentControl/skillBindingProduct", () => product);
import { SkillBindingCreatePanel } from "./SkillBindingCreatePanel";

const hash = "a".repeat(64);
const tenant = { orgId: "org-org", projectId: "dev-project" };
const item = { instance: { tenant, instanceId: "ecommerce.data_advisor.default", status: "provisioning" }, skills: [] };
const skill = { skillId: "ecommerce.skill.D01", revision: 1, contentHash: hash, lifecycle: "evaluated" };
const snapshot = { tenant, capabilityBindings: [], skillBindings: [] };
const candidate = { instanceId: item.instance.instanceId, skill: { assetType: "SkillTemplate", assetId: skill.skillId, revision: 2, contentHash: hash }, capabilityBindingIds: [], budgetPolicyRef: { assetType: "BudgetPolicyRevision", assetId: "budget", revision: 1, contentHash: hash }, initialStatus: "provisioning" };

describe("SkillBindingCreatePanel", () => {
  let host: HTMLDivElement;
  let root: Root;
  beforeEach(() => {
    localStorage.clear();
    host = document.createElement("div"); document.body.append(host); root = createRoot(host);
    vi.clearAllMocks();
    product.loadSkillBindingCandidate.mockResolvedValue({ candidate, blockers: [] });
    product.createProvisioningSkillBinding.mockResolvedValue({ receiptId: "receipt-1" });
    vi.stubGlobal("crypto", { randomUUID: () => "123e4567-e89b-12d3-a456-426614174000" });
  });
  afterEach(() => { act(() => root.unmount()); host.remove(); vi.unstubAllGlobals(); });
  const button = (label: string) => Array.from(host.querySelectorAll("button")).find((value) => value.textContent?.includes(label));

  it("keeps current evaluated D01 read-only", async () => {
    await act(async () => root.render(<MemoryRouter><SkillBindingCreatePanel item={item} skill={skill} snapshot={snapshot} onCreated={vi.fn()} /></MemoryRouter>));
    expect(host.textContent).toContain("正式发布后才能配置绑定");
    expect(button("核验绑定候选")).toBeUndefined();
    expect(product.loadSkillBindingCandidate).not.toHaveBeenCalled();
    expect(product.createProvisioningSkillBinding).not.toHaveBeenCalled();
  });

  it("requires read-only candidate then explicit creation and Receipt readback", async () => {
    const published = { ...skill, revision: 2, lifecycle: "published" };
    const onCreated = vi.fn();
    await act(async () => root.render(<MemoryRouter><SkillBindingCreatePanel item={item} skill={published} snapshot={snapshot} onCreated={onCreated} /></MemoryRouter>));
    await act(async () => button("核验绑定候选")!.click());
    expect(host.textContent).toContain("待配置绑定");
    expect(product.createProvisioningSkillBinding).not.toHaveBeenCalled();
    await act(async () => button("确认创建待配置绑定")!.click());
    expect(product.createProvisioningSkillBinding).toHaveBeenCalledTimes(1);
    expect(host.textContent).toContain("receipt-1");
    expect(onCreated).toHaveBeenCalledTimes(1);
    expect(localStorage.length).toBe(0);
  });

  it("locks the same exact command after an unknown write result", async () => {
    const published = { ...skill, revision: 2, lifecycle: "published" };
    product.createProvisioningSkillBinding.mockRejectedValue(new Error("connection lost after send"));
    await act(async () => root.render(<MemoryRouter><SkillBindingCreatePanel item={item} skill={published} snapshot={snapshot} onCreated={vi.fn()} /></MemoryRouter>));
    await act(async () => button("核验绑定候选")!.click());
    await act(async () => button("确认创建待配置绑定")!.click());
    expect(host.textContent).toContain("结果未核清，禁止重发");
    expect(localStorage.length).toBe(1);
    expect(button("确认创建待配置绑定")).toBeUndefined();
    expect(product.createProvisioningSkillBinding).toHaveBeenCalledTimes(1);
  });
});
