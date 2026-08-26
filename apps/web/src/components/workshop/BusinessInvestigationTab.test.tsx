import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { InvestigationCaseRevision, InvestigationReadClient, InvestigationRunListResponse } from "../../api/ecommerceInvestigation";
import { EcommerceInvestigationClientError } from "../../api/ecommerceInvestigation";
import { BusinessInvestigationTab } from "./BusinessInvestigationTab";

const hash = `sha256:${"a".repeat(64)}`; const tenant = { orgId: "org-org", projectId: "dev-project" }; const ref = (resourceType: string, resourceId: string) => ({ resourceType, resourceId, revision: 1, contentHash: hash });
const makeCase = (caseId: string, channelId: string, entityId: string, title: string): InvestigationCaseRevision => ({ schemaVersion: "aos.ecommerce.business-investigation-case/v1", tenant, caseId, revision: 1, version: 1, priorRef: null, contentHash: hash, lifecycle: "ACTIVE", analysisType: "initial_store_analysis", title, purposeCode: "business.investigation.initial", channelRef: ref("ChannelRevision", channelId), businessEntityRef: ref("BusinessEntityRevision", entityId), entityChannelBindingRef: ref("BusinessEntityChannelBindingRevision", `${channelId}-${entityId}`), investigationProfileRef: ref("InvestigationProfileRevision", `profile-${entityId}`), scopeRef: ref("InvestigationScopeRevision", `scope-${entityId}`), schedulePolicyRef: null, createdBy: "user-1", createdAt: "2026-08-26T08:00:00Z" });
const cases = [makeCase("case-a", "private-mall", "store-a", "私域首析"), makeCase("case-b", "private-mall", "store-b", "私域复盘"), makeCase("case-c", "wechat-store", "store-c", "微信首析")];
const emptyRuns = (): InvestigationRunListResponse => ({ tenant, items: [], count: 0 });

describe("BusinessInvestigationTab", () => {
  let host: HTMLDivElement; let root: Root;
  beforeEach(() => { host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host); });
  afterEach(() => { act(() => root.unmount()); host.remove(); });
  it("展示 canonical 三级选择并保持 GET-only 边界", async () => {
    const client: InvestigationReadClient = { listCases: vi.fn().mockResolvedValue({ tenant, items: cases, count: 3 }), listRuns: vi.fn().mockResolvedValue(emptyRuns()) };
    await act(async () => root.render(<BusinessInvestigationTab id="panel" labelledBy="tab" client={client} />));
    expect(host.querySelector<HTMLSelectElement>('[aria-label="渠道视角"]')?.value).toBe("private-mall"); expect(host.querySelectorAll('[role="radio"]')).toHaveLength(2); expect(host.querySelector<HTMLSelectElement>('[aria-label="分析记录"]')?.value).toBe("case-a"); expect(host.textContent).toContain("当前 Case 尚无 Run"); expect(host.textContent).toContain("写入口0"); expect(host.textContent).not.toMatch(/创建 Case|开始分析|继续运行|请求补数|执行 Handoff/);
  });
  it("切换渠道时原子替换实体与 Case 并忽略晚到 Run", async () => {
    let resolveOld!: (value: InvestigationRunListResponse) => void; const oldRun = new Promise<InvestigationRunListResponse>((resolve) => { resolveOld = resolve; });
    const client: InvestigationReadClient = { listCases: vi.fn().mockResolvedValue({ tenant, items: cases, count: 3 }), listRuns: vi.fn().mockImplementation((caseId) => caseId === "case-a" ? oldRun : Promise.resolve(emptyRuns())) };
    await act(async () => root.render(<BusinessInvestigationTab id="panel" labelledBy="tab" client={client} />)); const channel = host.querySelector<HTMLSelectElement>('[aria-label="渠道视角"]')!;
    await act(async () => { channel.value = "wechat-store"; channel.dispatchEvent(new Event("change", { bubbles: true })); });
    expect(host.textContent).toContain("store-c"); expect(host.textContent).toContain("微信首析"); expect(host.textContent).not.toContain("store-a");
    await act(async () => resolveOld(emptyRuns())); expect(host.textContent).toContain("微信首析"); expect(host.textContent).not.toContain("私域首析");
  });
  it("区分空态、无权限和失败且不保留旧选择", async () => {
    const emptyClient: InvestigationReadClient = { listCases: vi.fn().mockResolvedValue({ tenant, items: [], count: 0 }), listRuns: vi.fn() };
    await act(async () => root.render(<BusinessInvestigationTab id="panel" labelledBy="tab" client={emptyClient} />)); expect(host.textContent).toContain("当前没有可见分析记录");
    const forbidden: InvestigationReadClient = { listCases: vi.fn().mockRejectedValue(new EcommerceInvestigationClientError("forbidden", 403, "FORBIDDEN")), listRuns: vi.fn() };
    await act(async () => root.render(<BusinessInvestigationTab id="panel" labelledBy="tab" client={forbidden} />)); expect(host.textContent).toContain("无权读取生意探究"); expect(host.textContent).not.toContain("store-a");
  });
});
