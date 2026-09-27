import { describe, expect, it } from "vitest";

import { buildDataPolicyDraft, exactDataPolicyReadback, type DataPolicyInput } from "./RuntimeDataClassificationPanel";

const INPUT: DataPolicyInput = {
  policyId: "qyh-content-data", allowed: ["public_catalog", "approved_internal_knowledge"],
  effectiveFrom: "2026-09-27T09:00", effectiveUntil: "2026-10-27T09:00",
  owner: "qyh-owner", approvalRef: "approved-decision-ref",
};

describe("runtime data classification draft boundary", () => {
  it("keeps required prohibited classes and never activates a draft", () => {
    const body = buildDataPolicyDraft(INPUT);
    expect(body.lifecycle).toBe("draft");
    expect(body.allowedClassifications).toEqual(["approved_internal_knowledge", "public_catalog"]);
    expect(body.prohibitedClassifications).toEqual(expect.arrayContaining([
      "direct_pii", "raw_order_detail", "customer_conversation", "credential", "commercial_sensitive", "cross_tenant", "unknown",
    ]));
    expect(body.denyUnknown).toBe(true);
    expect(body.allowDirectPii).toBe(false);
    expect(body.allowCommercialSensitive).toBe(false);
    expect(body.allowCrossTenant).toBe(false);
  });

  it("rejects absent approval, empty or out-of-range classes and invalid window", () => {
    expect(() => buildDataPolicyDraft({ ...INPUT, approvalRef: " " })).toThrow("审批引用");
    expect(() => buildDataPolicyDraft({ ...INPUT, allowed: [] })).toThrow("数据类别");
    expect(() => buildDataPolicyDraft({ ...INPUT, allowed: ["direct_pii"] })).toThrow("数据类别");
    expect(() => buildDataPolicyDraft({ ...INPUT, allowed: ["public_catalog", "public_catalog"] })).toThrow("数据类别");
    expect(() => buildDataPolicyDraft({ ...INPUT, effectiveUntil: INPUT.effectiveFrom })).toThrow("生效起止时间");
  });

  it("requires exact tenant, content, fail-closed fields and hash on readback", () => {
    const body = buildDataPolicyDraft(INPUT);
    const tenant = { orgId: "org-org", projectId: "dev-project" };
    const row = { ...body, tenant, contentHash: "a".repeat(64) };
    expect(exactDataPolicyReadback(row, body, tenant)).toBe(true);
    expect(exactDataPolicyReadback({ ...row, lifecycle: "active" }, body, tenant)).toBe(false);
    expect(exactDataPolicyReadback({ ...row, allowDirectPii: true }, body, tenant)).toBe(false);
    expect(exactDataPolicyReadback({ ...row, allowedClassifications: ["raw_order_detail"] }, body, tenant)).toBe(false);
    expect(exactDataPolicyReadback({ ...row, tenant: { ...tenant, orgId: "dev-org" } }, body, tenant)).toBe(false);
    expect(exactDataPolicyReadback({ ...row, contentHash: "bad" }, body, tenant)).toBe(false);
  });
});
