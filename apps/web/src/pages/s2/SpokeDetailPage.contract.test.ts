import { describe, expect, it } from "vitest";
import { TABS } from "./SpokeDetailPage";

describe("SpokeDetailPage · honest detail views", () => {
  it("keeps five current-record views without client fixtures", () => {
    expect(TABS.map((tab) => tab.id)).toEqual(["overview", "plan", "plan-diff", "config", "maintenance"]);
  });
});
