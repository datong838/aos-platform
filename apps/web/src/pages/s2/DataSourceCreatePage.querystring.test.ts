import { describe, it, expect } from "vitest";
import { CONNECTOR_TYPES, filterConnectorTypes } from "./DataSourceCreatePage";

describe("DataSourceCreatePage niushop connector", () => {
  it("niushop-mysql 在 CONNECTOR_TYPES 中", () => {
    const found = CONNECTOR_TYPES.find((t) => t.id === "niushop-mysql");
    expect(found).toBeDefined();
    expect(found?.category).toBe("database");
    expect(found?.name).toBe("Niushop 微商城");
  });

  it("filterConnectorTypes 能搜到 niushop-mysql", () => {
    const results = filterConnectorTypes("database", "niushop");
    expect(results.some((t) => t.id === "niushop-mysql")).toBe(true);
  });

  it("filterConnectorTypes 中文搜到微商城", () => {
    const results = filterConnectorTypes("all", "微商城");
    expect(results.some((t) => t.id === "niushop-mysql")).toBe(true);
  });
});
