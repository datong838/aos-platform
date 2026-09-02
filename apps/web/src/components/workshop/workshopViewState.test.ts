import { describe, expect, it } from "vitest";

import { deriveWorkshopViewState, pickPreferredWorkshopView } from "./workshopViewState";

type Slice = { id: string; status: "ready" | "blocked" | "conflict" | "unknown"; count: number };

describe("workshopViewState", () => {
  const hasData = (slice: Slice) => slice.count > 0;

  it("混合 ready/blocked 时保留部分可用并优先选择有数据的 ready 切片", () => {
    const slices: Slice[] = [
      { id: "blocked", status: "blocked", count: 0 },
      { id: "empty", status: "ready", count: 0 },
      { id: "usable", status: "ready", count: 12 },
    ];
    expect(deriveWorkshopViewState(slices, 12)).toBe("partial");
    expect(pickPreferredWorkshopView(slices, hasData)?.id).toBe("usable");
  });

  it("全 ready 且集合为空时返回可信 empty", () => {
    const slices: Slice[] = [{ id: "empty", status: "ready", count: 0 }];
    expect(deriveWorkshopViewState(slices, 0)).toBe("empty");
    expect(pickPreferredWorkshopView(slices, hasData)?.id).toBe("empty");
  });

  it("无 ready 时分别返回 conflict 与 blocked", () => {
    expect(deriveWorkshopViewState([{ id: "conflict", status: "conflict", count: 0 }], 0)).toBe("conflict");
    expect(deriveWorkshopViewState([{ id: "unknown", status: "unknown", count: 0 }], 0)).toBe("blocked");
  });
});
