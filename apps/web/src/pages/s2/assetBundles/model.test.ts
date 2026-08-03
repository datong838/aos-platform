import { describe, expect, it } from "vitest";

import { installationPageControls } from "./model";

describe("M3-2 installation page controls", () => {
  it("derives first, middle and last page boundaries from server paging", () => {
    expect(installationPageControls(45, 20, 0)).toEqual({
      hasPrevious: false,
      hasNext: true,
      previousOffset: 0,
      nextOffset: 20,
    });
    expect(installationPageControls(45, 20, 20)).toEqual({
      hasPrevious: true,
      hasNext: true,
      previousOffset: 0,
      nextOffset: 40,
    });
    expect(installationPageControls(45, 20, 40)).toEqual({
      hasPrevious: true,
      hasNext: false,
      previousOffset: 20,
      nextOffset: 60,
    });
  });

  it("keeps empty and defensive inputs within safe boundaries", () => {
    expect(installationPageControls(0, 20, 0)).toMatchObject({
      hasPrevious: false,
      hasNext: false,
    });
    expect(installationPageControls(-1, 0, -1)).toEqual({
      hasPrevious: false,
      hasNext: false,
      previousOffset: 0,
      nextOffset: 1,
    });
  });
});
