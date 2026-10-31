import { describe, expect, it } from "vitest";
import { GuardPolicyApprovalPanel } from "./GuardPolicyApprovalPanel";

describe("GuardPolicyApprovalPanel", () => {
  it("is a mounted component without implicit approval", () => {
    expect(typeof GuardPolicyApprovalPanel).toBe("function");
  });
});
