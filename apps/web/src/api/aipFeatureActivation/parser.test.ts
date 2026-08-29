import { describe, expect, it } from "vitest";
import { parseAipFeatureActivationCommand, parseAipFeatureActivationList } from "./parser";

const hash = `sha256:${"a".repeat(64)}`;
const tenant = { orgId: "org-org", projectId: "dev-project" };

describe("AIP FeatureActivation parser", () => {
  it("接受租户绑定的精确投影与 Receipt", () => {
    const list = parseAipFeatureActivationList({ schemaVersion: "aos.ecommerce-workshop.feature-activation-list/v1", tenant, evaluatedAt: "2026-08-29T10:00:00Z", items: [{ featureId: "aip.analysis", revision: 2, contentHash: hash, status: "active", activatedAt: "2026-08-29T09:00:00Z", expiresAt: "2026-08-29T12:00:00Z" }] });
    expect(list.items[0].revision).toBe(2);
    const result = parseAipFeatureActivationCommand({ tenant, replayed: false, receipt: { schemaVersion: "aos.ecommerce-workshop.feature-activation-command-receipt/v1", receiptId: "r-1", featureId: "aip.analysis", operation: "revoke", revision: 2, status: "revoked", contentHash: hash, createdAt: "2026-08-29T10:01:00Z" } });
    expect(result.receipt.status).toBe("revoked");
  });

  it("拒绝重复 feature 和伪造 hash", () => {
    const item = { featureId: "aip.analysis", revision: 1, contentHash: hash, status: "active", activatedAt: "2026-08-29T09:00:00Z", expiresAt: null };
    expect(() => parseAipFeatureActivationList({ schemaVersion: "aos.ecommerce-workshop.feature-activation-list/v1", tenant, evaluatedAt: "2026-08-29T10:00:00Z", items: [item, item] })).toThrow(/重复/);
    expect(() => parseAipFeatureActivationCommand({ tenant, replayed: false, receipt: { schemaVersion: "aos.ecommerce-workshop.feature-activation-command-receipt/v1", receiptId: "r-1", featureId: "aip.analysis", operation: "activate", revision: 1, status: "active", contentHash: "demo", createdAt: "2026-08-29T10:01:00Z" } })).toThrow(/exact ref/);
  });
});
