import { describe, expect, it } from "vitest";

import { ASSET_VIEW_TABS } from "./AssetBundlesPage";

describe("M3-4 AssetBundlesPage contract", () => {
  it("adds preflight while keeping Registry and Installation views", () => {
    expect(ASSET_VIEW_TABS).toEqual([
      { id: "registry", label: "资产 Registry" },
      { id: "composition", label: "组合预检与创建" },
      { id: "installations", label: "安装管理" },
    ]);
  });
});
