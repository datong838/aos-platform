import { describe, it, expect } from "vitest";
import { CONNECTOR_TYPES, filterConnectorTypes } from "./DataSourceCreatePage";

describe("DataSourceCreatePage JDBC SSH 连接器", () => {
  it("jdbc-mysql-ssh 在 CONNECTOR_TYPES 中", () => {
    const found = CONNECTOR_TYPES.find((t) => t.id === "jdbc-mysql-ssh");
    expect(found).toBeDefined();
    expect(found?.category).toBe("database");
    expect(found?.name).toBe("MySQL SSH 隧道");
  });

  it("filterConnectorTypes 能搜到 jdbc-mysql-ssh", () => {
    const results = filterConnectorTypes("database", "ssh");
    expect(results.some((t) => t.id === "jdbc-mysql-ssh")).toBe(true);
  });

  it("niushop-mysql 已废弃，不在 CONNECTOR_TYPES 中", () => {
    const found = CONNECTOR_TYPES.find((t) => t.id === "niushop-mysql");
    expect(found).toBeUndefined();
  });
});
