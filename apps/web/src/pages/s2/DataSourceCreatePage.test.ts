import { describe, expect, it } from "vitest";
import {
  CONNECTOR_TYPES,
  WIZARD_STEPS,
  canAdvance,
  filterConnectorTypes,
  hasConfigErrors,
  selectedTableRowCount,
  selectedTableCount,
  selectAllTables,
  stepProgress,
  toggleTableSelection,
  validateConnectionConfig,
  type ConnectionConfig,
  type TableSelection,
  type ConnectorType,
} from "./DataSourceCreatePage";

const PG_TYPE: ConnectorType = CONNECTOR_TYPES.find((t) => t.id === "postgresql")!;
const REST_TYPE: ConnectorType = CONNECTOR_TYPES.find((t) => t.id === "rest-api")!;
const CSV_TYPE: ConnectorType = CONNECTOR_TYPES.find((t) => t.id === "file-csv")!;

const EMPTY_CONFIG: ConnectionConfig = {
  host: "", port: "", database: "", username: "", password: "",
  apiKey: "", apiUrl: "", filePath: "",
};

const VALID_PG_CONFIG: ConnectionConfig = {
  ...EMPTY_CONFIG,
  host: "localhost",
  port: "5432",
  database: "mydb",
  username: "admin",
  password: "secret",
};

const MOCK_TABLES: TableSelection[] = [
  { name: "orders", selected: true, rowCount: 1000 },
  { name: "products", selected: false, rowCount: 500 },
  { name: "customers", selected: true, rowCount: 2000 },
];

describe("DataSourceCreatePage · WIZARD_STEPS", () => {
  it("5 个步骤", () => {
    expect(WIZARD_STEPS.length).toBe(5);
  });
  it("第一步是选择类型", () => {
    expect(WIZARD_STEPS[0].label).toBe("选择类型");
  });
  it("最后一步是完成", () => {
    expect(WIZARD_STEPS[4].label).toBe("完成");
  });
});

describe("DataSourceCreatePage · stepProgress", () => {
  it("step 0 → 20%", () => { expect(stepProgress(0)).toBe(20); });
  it("step 2 → 60%", () => { expect(stepProgress(2)).toBe(60); });
  it("step 4 → 100%", () => { expect(stepProgress(4)).toBe(100); });
});

describe("DataSourceCreatePage · canAdvance", () => {
  it("条件为 true 可前进", () => {
    expect(canAdvance(0, [true, false, false, false, false])).toBe(true);
  });
  it("条件为 false 不可前进", () => {
    expect(canAdvance(1, [true, false, false, false, false])).toBe(false);
  });
});

describe("DataSourceCreatePage · filterConnectorTypes", () => {
  it("无筛选返回全部", () => {
    expect(filterConnectorTypes("all", "").length).toBe(CONNECTOR_TYPES.length);
  });
  it("按分类 database", () => {
    const r = filterConnectorTypes("database", "");
    expect(r.every((t) => t.category === "database")).toBe(true);
  });
  it("搜索 postgres", () => {
    const r = filterConnectorTypes("all", "postgres");
    expect(r.length).toBe(1);
    expect(r[0].id).toBe("postgresql");
  });
  it("搜索描述匹配", () => {
    const r = filterConnectorTypes("all", "CRM");
    expect(r.length).toBeGreaterThanOrEqual(1);
  });
});

describe("DataSourceCreatePage · validateConnectionConfig", () => {
  it("无类型报错", () => {
    const errs = validateConnectionConfig(null, EMPTY_CONFIG);
    expect(errs.type).toBeDefined();
  });
  it("PG 空配置报错", () => {
    const errs = validateConnectionConfig(PG_TYPE, EMPTY_CONFIG);
    expect(errs.host).toBeDefined();
    expect(errs.port).toBeDefined();
    expect(errs.database).toBeDefined();
    expect(errs.username).toBeDefined();
    expect(errs.password).toBeDefined();
  });
  it("PG 有效配置无错误", () => {
    const errs = validateConnectionConfig(PG_TYPE, VALID_PG_CONFIG);
    expect(hasConfigErrors(errs)).toBe(false);
  });
  it("PG 端口非数字报错", () => {
    const errs = validateConnectionConfig(PG_TYPE, { ...VALID_PG_CONFIG, port: "abc" });
    expect(errs.port).toBeDefined();
  });
  it("PG 端口超出范围报错", () => {
    const errs = validateConnectionConfig(PG_TYPE, { ...VALID_PG_CONFIG, port: "99999" });
    expect(errs.port).toBeDefined();
  });
  it("REST API 无 URL 报错", () => {
    const errs = validateConnectionConfig(REST_TYPE, EMPTY_CONFIG);
    expect(errs.apiUrl).toBeDefined();
    expect(errs.apiKey).toBeDefined();
  });
  it("REST API URL 非 http 开头报错", () => {
    const errs = validateConnectionConfig(REST_TYPE, { ...EMPTY_CONFIG, apiUrl: "ftp://bad", apiKey: "k" });
    expect(errs.apiUrl).toBeDefined();
  });
  it("CSV 无文件路径报错", () => {
    const errs = validateConnectionConfig(CSV_TYPE, EMPTY_CONFIG);
    expect(errs.filePath).toBeDefined();
  });
});

describe("DataSourceCreatePage · hasConfigErrors", () => {
  it("空对象返回 false", () => {
    expect(hasConfigErrors({})).toBe(false);
  });
  it("有键返回 true", () => {
    expect(hasConfigErrors({ host: "必填" })).toBe(true);
  });
});

describe("DataSourceCreatePage · selectedTableCount", () => {
  it("统计选中数", () => {
    expect(selectedTableCount(MOCK_TABLES)).toBe(2);
  });
  it("全不选返回 0", () => {
    expect(selectedTableCount(selectAllTables(MOCK_TABLES, false))).toBe(0);
  });
  it("全选返回全部", () => {
    expect(selectedTableCount(selectAllTables(MOCK_TABLES, true))).toBe(3);
  });
});

describe("DataSourceCreatePage · selectedTableRowCount", () => {
  it("统计选中行数", () => {
    expect(selectedTableRowCount(MOCK_TABLES)).toBe(3000);
  });
});

describe("DataSourceCreatePage · toggleTableSelection", () => {
  it("取消已选", () => {
    const r = toggleTableSelection(MOCK_TABLES, "orders");
    expect(r.find((t) => t.name === "orders")!.selected).toBe(false);
  });
  it("选中未选", () => {
    const r = toggleTableSelection(MOCK_TABLES, "products");
    expect(r.find((t) => t.name === "products")!.selected).toBe(true);
  });
  it("不影响其他表", () => {
    const r = toggleTableSelection(MOCK_TABLES, "orders");
    expect(r.find((t) => t.name === "customers")!.selected).toBe(true);
  });
});
