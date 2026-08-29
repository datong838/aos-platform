import { describe, expect, it } from "vitest";
import { stageBadge } from "./ReleasesPage";

describe("ReleasesPage · 通道文案", () => {
  it("候选与稳定通道使用中文产品语义", () => {
    expect(stageBadge("rc")).toEqual({
      label: "候选",
      cls: "bp-discover-badge bp-discover-badge-warn",
    });
    expect(stageBadge("stable")).toEqual({
      label: "稳定",
      cls: "bp-discover-badge bp-discover-badge-ok",
    });
  });
});
