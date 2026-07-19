import { describe, expect, it } from "vitest";
import {
  DEFAULT_DESKTOP_VIEW,
  isDefaultBuddyClassic,
  resolveDesktopView,
} from "./buddyMode";

describe("TWC.11 Buddy classic is not default home", () => {
  it("default view is cockpit", () => {
    expect(DEFAULT_DESKTOP_VIEW).toBe("cockpit");
    expect(isDefaultBuddyClassic("cockpit")).toBe(false);
    expect(isDefaultBuddyClassic("buddy-classic")).toBe(false);
  });

  it("can resolve classic on demand", () => {
    expect(resolveDesktopView("buddy-classic")).toBe("buddy-classic");
    expect(resolveDesktopView(null)).toBe("cockpit");
  });
});
