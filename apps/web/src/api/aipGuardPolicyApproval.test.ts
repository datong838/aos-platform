import { describe, expect, it } from "vitest";
import { buildGuardDecision, exactGuardDecisionResult } from "./aipGuardPolicyApproval";

describe("guard policy approval contract", () => {
  it("requires an explicit exact decision and never grants activation", () => {
    const request = buildGuardDecision({ proposalId: "proposal-1", proposalVersion: "1",
      proposalHash: "a".repeat(64), decision: "approved" });
    expect(request.body.expectedProposalVersion).toBe(1);
    expect(exactGuardDecisionResult({ status: "observed", proposalId: "proposal-1",
      approvalEventId: "event-1", decision: "approved", activationAuthorized: false }, request)).toBe(true);
    expect(exactGuardDecisionResult({ status: "observed", proposalId: "proposal-1",
      approvalEventId: "event-1", decision: "approved", activationAuthorized: true }, request)).toBe(false);
  });

  it("rejects missing choice and malformed hashes", () => {
    expect(() => buildGuardDecision({ proposalId: "proposal-1", proposalVersion: "1",
      proposalHash: "bad", decision: "approved" })).toThrow("64 位");
    expect(() => buildGuardDecision({ proposalId: "proposal-1", proposalVersion: "1",
      proposalHash: "a".repeat(64), decision: "" })).toThrow("明确选择");
  });
});
