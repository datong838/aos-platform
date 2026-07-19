import { describe, expect, it } from "vitest";
import { formatTrayTooltip } from "./trayTooltip";

describe("195m formatTrayTooltip", () => {
  it("online empty → default", () => {
    expect(formatTrayTooltip("online", 0)).toBe("AOS 桌面");
  });

  it("offline empty", () => {
    expect(formatTrayTooltip("offline", 0)).toBe("AOS 桌面 · 离线");
  });

  it("offline with queue", () => {
    expect(formatTrayTooltip("offline", 2)).toBe("AOS 桌面 · 离线（待同步 2）");
  });

  it("online with queue", () => {
    expect(formatTrayTooltip("online", 3)).toBe("AOS 桌面 · 待同步 3");
  });
});
