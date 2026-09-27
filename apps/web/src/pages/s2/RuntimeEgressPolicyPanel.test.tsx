import { describe, expect, it } from "vitest";

import { buildEgressDraft, CURRENT_AGNES_HOST, exactEgressReadback, type EgressDraftInput } from "./RuntimeEgressPolicyPanel";

const INPUT: EgressDraftInput = {
  policyId: "qyh-egress", host: CURRENT_AGNES_HOST, owner: "qyh-owner", approvalRef: "approved-decision-ref",
  effectiveFrom: "2026-09-27T09:00", effectiveUntil: "2026-10-27T09:00",
};

describe("runtime egress draft boundary", () => {
  it("only proposes current HTTPS/443 Agnes host, unknown region and no fallback", () => {
    const body = buildEgressDraft(INPUT);
    expect(body.lifecycle).toBe("draft");
    expect(body.allowedSchemes).toEqual(["https"]);
    expect(body.allowedHosts).toEqual([CURRENT_AGNES_HOST]);
    expect(body.allowedPorts).toEqual([443]);
    expect(body.allowPublicFallback).toBe(false);
    expect(body.unknownDestinationBehavior).toBe("block");
    expect(body.regionState).toBe("unknown");
    expect(body.region).toBeNull();
  });

  it("rejects missing approval, unselected or historical host and invalid window", () => {
    expect(() => buildEgressDraft({ ...INPUT, approvalRef: " " })).toThrow("审批引用");
    expect(() => buildEgressDraft({ ...INPUT, host: "" })).toThrow("主机");
    expect(() => buildEgressDraft({ ...INPUT, host: "apihub.agnes-ai.com" })).toThrow("主机");
    expect(() => buildEgressDraft({ ...INPUT, effectiveUntil: INPUT.effectiveFrom })).toThrow("生效起止时间");
  });

  it("rejects drifted tenant, region, host, endpoint or hash on readback", () => {
    const body = buildEgressDraft(INPUT);
    const tenant = { orgId: "org-org", projectId: "dev-project" };
    const row = { ...body, tenant, contentHash: "a".repeat(64) };
    expect(exactEgressReadback(row, body, tenant)).toBe(true);
    expect(exactEgressReadback({ ...row, lifecycle: "active" }, body, tenant)).toBe(false);
    expect(exactEgressReadback({ ...row, regionState: "confirmed" }, body, tenant)).toBe(false);
    expect(exactEgressReadback({ ...row, allowedHosts: ["apihub.agnes-ai.com"] }, body, tenant)).toBe(false);
    expect(exactEgressReadback({ ...row, allowedPorts: [80] }, body, tenant)).toBe(false);
    expect(exactEgressReadback({ ...row, tenant: { ...tenant, projectId: "other" } }, body, tenant)).toBe(false);
    expect(exactEgressReadback({ ...row, contentHash: "bad" }, body, tenant)).toBe(false);
  });
});
