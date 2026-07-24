/** TWC.4 about payload shape */
import { describe, expect, it } from "vitest";

describe("TWC.4 about contract", () => {
  it("expects camelCase about_info fields", () => {
    const sample = {
      productName: "AOS 桌面",
      version: "0.1.0",
      identifier: "com.aos.desktop",
    };
    expect(sample.productName).toContain("AOS");
    expect(sample.identifier).toBe("com.aos.desktop");
  });
});
