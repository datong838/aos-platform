import { describe, expect, it } from "vitest";
import {
  QYH_AUTHORIZED_EFFECTIVE_UNTIL,
  computeAuthorizedQyhWindow,
  targetMatchesAuthorizedQyhWindow,
} from "./qyhCostRenewalDefaults";

describe("QYH authorized renewal window defaults", () => {
  const ref = new Date("2026-10-31T12:00:00.000Z");

  it("uses the exact human-authorized expiry instead of a rolling window", () => {
    const w = computeAuthorizedQyhWindow(ref);
    expect(Date.parse(w.effectiveFrom)).toBeLessThanOrEqual(ref.getTime());
    expect(w.effectiveUntil).toBe(QYH_AUTHORIZED_EFFECTIVE_UNTIL);
    expect(w.effectiveUntil).toBe("2027-03-31T04:00:00.000Z");
  });

  it("rejects both shorter and later rolling targets", () => {
    const exact = { effectiveFrom: "2026-10-01T00:00:00Z", effectiveUntil: QYH_AUTHORIZED_EFFECTIVE_UNTIL };
    const short = { ...exact, effectiveUntil: "2027-02-01T00:00:00Z" };
    const later = { ...exact, effectiveUntil: "2027-04-01T00:00:00Z" };
    expect(targetMatchesAuthorizedQyhWindow(exact, ref)).toBe(true);
    expect(targetMatchesAuthorizedQyhWindow(short, ref)).toBe(false);
    expect(targetMatchesAuthorizedQyhWindow(later, ref)).toBe(false);
  });
});
