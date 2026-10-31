import { describe, expect, it } from "vitest";
import {
  STABLE_DEV_MONTHS,
  addUtcMonths,
  computeStableDevWindow,
  minimumStableDevUntil,
  targetCoversStableDev,
} from "./qyhCostRenewalDefaults";

describe("stable dev window defaults", () => {
  const ref = new Date("2026-10-31T12:00:00.000Z");

  it("covers at least STABLE_DEV_MONTHS from reference", () => {
    const w = computeStableDevWindow(ref);
    expect(Date.parse(w.effectiveFrom)).toBeLessThanOrEqual(ref.getTime());
    expect(Date.parse(w.effectiveUntil)).toBeGreaterThanOrEqual(minimumStableDevUntil(ref));
    expect(addUtcMonths(ref, STABLE_DEV_MONTHS).toISOString()).toBe(w.effectiveUntil);
  });

  it("rejects targets shorter than the stable window", () => {
    const ok = { effectiveFrom: "2026-10-01T00:00:00Z", effectiveUntil: "2027-02-01T00:00:00Z" };
    const short = { effectiveFrom: "2026-10-01T00:00:00Z", effectiveUntil: "2026-11-30T00:00:00Z" };
    expect(targetCoversStableDev(ok, ref)).toBe(true);
    expect(targetCoversStableDev(short, ref)).toBe(false);
  });
});
