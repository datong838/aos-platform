import { describe, expect, it } from "vitest";

import { ASSET_VIEW_TABS } from "./AssetBundlesPage";

describe("M3-2 AssetBundlesPage contract", () => {
  it("keeps only the canonical Registry and read-only Installation views", () => {
    expect(ASSET_VIEW_TABS).toEqual([
      { id: "registry", label: "资产 Registry" },
      { id: "installations", label: "安装管理（只读）" },
    ]);
  });
});
