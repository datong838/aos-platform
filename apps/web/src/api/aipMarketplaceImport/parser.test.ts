import { describe, expect, it } from "vitest";
import { parseImportPreview, parseMarketplaceCatalog } from "./parser";

const h = "a".repeat(64);
const ref = { resourceType: "SolutionPack", resourceId: "solution.ecommerce.growth", revision: "1.3.0", authority: "asset-registry" };

describe("R18 marketplace/import strict parser", () => {
  it("accepts exact marketplace tenant response", () => {
    const parsed = parseMarketplaceCatalog({ tenant: { orgId: "org-org", projectId: "dev-project" }, items: [{ packageId: "solution.ecommerce.growth", version: "1.3.0", contentHash: h, displayName: "电商增长", publisher: "AOS", license: "Internal", sourceRef: ref, agentCount: 6, skillCount: 37, capabilityCount: 10, installedCount: 6, runnableCount: 1, discoverable: true, installAuthorized: false, agents: [{ templateId: "agent.one", displayName: "数据参谋", installed: true, runtimeReadiness: "blocked", blockers: ["eval_gate_unavailable"], repairHref: "/aip/evals", repairLabel: "检查评测门控" }] }], count: 1 }, { orgId: "org-org", projectId: "dev-project" });
    expect(parsed.items[0].skillCount).toBe(37);
    expect(parsed.items[0].installAuthorized).toBe(false);
  });

  it("rejects tenant drift and fake import authority", () => {
    expect(() => parseMarketplaceCatalog({ tenant: { orgId: "dev-org", projectId: "dev-project" }, items: [], count: 0 }, { orgId: "org-org", projectId: "dev-project" })).toThrow("tenant echo");
    const scan = { scannerId: "scanner", scannerVersion: "1", ruleSetHash: h, sourceRef: ref, sourceCommit: "abcdef1", sourceContentHash: h, licenseId: "MIT", sbomRef: ref, findings: [], status: "passed", accepted: true, artifactHash: h };
    const preview = { tenant: { orgId: "org-org", projectId: "dev-project" }, previewId: "preview-1", kind: "agent", status: "external_required", contentHash: h, steps: [{ step: "test", status: "external_required", contentHash: h, blockerCodes: [], summary: "需要独立授权" }], scanArtifact: scan, importJobAuthority: "created", approvalRequired: true };
    expect(() => parseImportPreview(preview)).toThrow("越权声明");
  });
});
