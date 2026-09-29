import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import {
  buildNetworkActivationPreview,
  exactBlockedNetworkPreview,
  RuntimeNetworkPolicyPreviewPanel,
  type NetworkActivationPreviewInput,
} from "./RuntimeNetworkPolicyPreviewPanel";
import { CURRENT_AGNES_HOST } from "./RuntimeEgressPolicyPanel";

const INPUT: NetworkActivationPreviewInput = {
  policyId: "qyh-network", revision: "1", expectedHeadVersion: "0",
  host: CURRENT_AGNES_HOST, egressPolicyId: "qyh-egress", egressRevision: "1",
  egressContentHash: "a".repeat(64), owner: "qyh-owner",
  approvalRef: "text-only-reference", effectiveFrom: "2026-09-29T09:00",
  effectiveUntil: "2026-10-29T09:00",
};

describe("network activation read-only product preview", () => {
  it("builds only an exact bounded active candidate for preview", () => {
    const request = buildNetworkActivationPreview(INPUT);
    expect(request.expectedHeadVersion).toBe(0);
    expect(request.body.lifecycle).toBe("active");
    expect(request.body.allowedSchemes).toEqual(["https"]);
    expect(request.body.allowedHosts).toEqual([CURRENT_AGNES_HOST]);
    expect(request.body.allowedPorts).toEqual([443]);
    expect(request.body.tlsRequired).toBe(true);
    expect(request.body.publicFallbackAllowed).toBe(false);
    expect(request.body.egressPolicyRef).toEqual({
      assetType: "EgressPolicyRevision", assetId: "qyh-egress", revision: 1,
      contentHash: "a".repeat(64),
    });
  });

  it("rejects missing exact dependency, drifted host, unsafe version and window", () => {
    expect(() => buildNetworkActivationPreview({ ...INPUT, egressContentHash: "bad" })).toThrow("出站策略摘要");
    expect(() => buildNetworkActivationPreview({ ...INPUT, egressPolicyId: " " })).toThrow("出站策略 ID");
    expect(() => buildNetworkActivationPreview({ ...INPUT, host: "apihub.agnes-ai.com" })).toThrow("主机");
    expect(() => buildNetworkActivationPreview({ ...INPUT, revision: "1.5" })).toThrow("修订");
    expect(() => buildNetworkActivationPreview({ ...INPUT, expectedHeadVersion: "-1" })).toThrow("head 版本");
    expect(() => buildNetworkActivationPreview({ ...INPUT, effectiveUntil: INPUT.effectiveFrom })).toThrow("时间");
  });

  it("accepts only explicit fail-closed preview response", () => {
    const body = buildNetworkActivationPreview(INPUT).body;
    const blocked = {
      policyId: body.policyId, candidateRevision: 1, headRevision: 0, headVersion: 0,
      targetContentHash: "b".repeat(64), bindingHash: "c".repeat(64),
      activationAllowed: false,
      blockers: ["FORMAL_PRODUCER_UNAVAILABLE", "ATOMIC_APPROVAL_CONSUMER_UNAVAILABLE"],
    };
    expect(exactBlockedNetworkPreview(blocked, body)).toBe(true);
    expect(exactBlockedNetworkPreview({ ...blocked, activationAllowed: true }, body)).toBe(false);
    expect(exactBlockedNetworkPreview({ ...blocked, bindingHash: "bad" }, body)).toBe(false);
    expect(exactBlockedNetworkPreview({ ...blocked, blockers: [] }, body)).toBe(false);
    expect(exactBlockedNetworkPreview({ ...blocked, policyId: "other" }, body)).toBe(false);
  });

  it("renders a preview-only control with the approval boundary visible", () => {
    const html = renderToStaticMarkup(<RuntimeNetworkPolicyPreviewPanel />);
    expect(html).toContain("只读预览阻断项");
    expect(html).toContain("文本审批引用（不构成批准）");
    expect(html).not.toContain("发布网络策略");
  });
});
