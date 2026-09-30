import { describe, expect, it, vi } from "vitest";
import type { AipClient } from "../aip/client";
import { NetworkDecisionSdk } from "./networkDecision";

describe("network decision product transport", () => {
  it("queries saved intent without rebuilding reason or generating a client key", async () => {
    const request = vi.fn().mockResolvedValue({ status: "unresolved" });
    const sdk = new NetworkDecisionSdk({ request } as unknown as AipClient);
    expect(await sdk.inquire("proposal-1", 3)).toEqual({ status: "unresolved" });
    expect(request).toHaveBeenCalledWith("getNetworkDecisionIntent", { params: { proposal_id: "proposal-1", version: "3" } });
  });
  it("submits exact version/hash once and does not retry an unknown transport result", async () => {
    const request = vi.fn().mockRejectedValue(new Error("disconnected"));
    const sdk = new NetworkDecisionSdk({ request } as unknown as AipClient);
    const body = { expectedProposalVersion: 3, expectedProposalHash: "a".repeat(64), decision: "approved" as const, reason: "reviewed" };
    await expect(sdk.submit("proposal-1", body)).rejects.toThrow("disconnected");
    expect(request).toHaveBeenCalledTimes(1);
    expect(request).toHaveBeenCalledWith("submitNetworkDecisionIntent", { params: { proposal_id: "proposal-1" }, body });
  });
  it.each([{ status: "observed" }, { status: "observed", eventId: "event", decision: "bad" }, { status: "not_attempted", eventId: "event" }])("rejects malformed proof %j", async (value) => {
    const sdk = new NetworkDecisionSdk({ request: vi.fn().mockResolvedValue(value) } as unknown as AipClient);
    await expect(sdk.inquire("p", 1)).rejects.toThrow();
  });
});
