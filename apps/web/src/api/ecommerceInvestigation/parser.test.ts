import { describe, expect, it } from "vitest";
import { parseInvestigationCaseList, parseInvestigationRunList } from "./parser";

const hash = `sha256:${"a".repeat(64)}`; const tenant = { orgId: "org-org", projectId: "dev-project" };
const ref = (resourceType: string, resourceId: string, revision = 1) => ({ resourceType, resourceId, revision, contentHash: hash });
const caseItem = { schemaVersion: "aos.ecommerce.business-investigation-case/v1", tenant, caseId: "case-1", revision: 1, version: 1, priorRef: null, contentHash: hash, lifecycle: "ACTIVE", analysisType: "initial_store_analysis", title: "首次全店经营分析", purposeCode: "business.investigation.initial", channelRef: ref("ChannelRevision", "private-mall"), businessEntityRef: ref("BusinessEntityRevision", "store-1"), entityChannelBindingRef: ref("BusinessEntityChannelBindingRevision", "binding-1"), investigationProfileRef: ref("InvestigationProfileRevision", "profile-1"), scopeRef: ref("InvestigationScopeRevision", "scope-1"), schedulePolicyRef: null, createdBy: "user-1", createdAt: "2026-08-26T08:00:00Z" };
const runItem = { authority: { schemaVersion: "aos.ecommerce.business-investigation-run/v1", tenant, runId: "run-1", version: 1, contentHash: hash, caseRef: ref("BusinessInvestigationCaseRevision", "case-1"), analysisType: "initial_store_analysis", triggerKind: "manual", triggerKey: "manual:run-1", lifecycle: "PREPARING", control: "RUNNING", createdBy: "user-1", createdAt: "2026-08-26T08:01:00Z" }, state: { schemaVersion: "aos.ecommerce.business-investigation-run-state/v1", tenant, runId: "run-1", version: 1, priorRef: null, lifecycle: "PREPARING", control: "RUNNING", eventSequence: 1, contentHash: hash, pendingRequirementRef: null, uncertainCommand: null, createdBy: "user-1", createdAt: "2026-08-26T08:01:00Z" } };

describe("ecommerceInvestigation strict parser", () => {
  it("解析 tenant-scoped Case 与 Run canonical 列表", () => {
    expect(parseInvestigationCaseList({ tenant, items: [caseItem], count: 1 }, tenant).items[0]?.channelRef.resourceId).toBe("private-mall");
    expect(parseInvestigationRunList({ tenant, items: [runItem], count: 1 }, "case-1", tenant).items[0]?.state.control).toBe("RUNNING");
  });
  it("拒绝未知字段、非法 hash、count 与 tenant 漂移", () => {
    expect(() => parseInvestigationCaseList({ tenant, items: [caseItem], count: 1, tenantOverride: true })).toThrow(/字段漂移/);
    expect(() => parseInvestigationCaseList({ tenant, items: [{ ...caseItem, contentHash: "sha256:bad" }], count: 1 })).toThrow(/contentHash/);
    expect(() => parseInvestigationCaseList({ tenant, items: [caseItem], count: 0 })).toThrow(/不守恒/);
    expect(() => parseInvestigationCaseList({ tenant, items: [caseItem], count: 1 }, { orgId: "dev-org", projectId: "dev-project" })).toThrow(/tenant 漂移/);
  });
  it("拒绝 Run 跨 Case、重复 ID 与状态 revision 漂移", () => {
    expect(() => parseInvestigationRunList({ tenant, items: [runItem], count: 1 }, "other-case")).toThrow(/caseRef 漂移/);
    expect(() => parseInvestigationRunList({ tenant, items: [runItem, runItem], count: 2 }, "case-1")).toThrow(/identity 不守恒/);
    expect(() => parseInvestigationRunList({ tenant, items: [{ ...runItem, state: { ...runItem.state, eventSequence: 2 } }], count: 1 }, "case-1")).toThrow(/eventSequence/);
  });
});
