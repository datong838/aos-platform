import { describe, expect, it } from "vitest";
import {
  CATEGORY_LABELS,
  connectorCapabilityLabel,
  filterCatalog,
  computeCatalogStats,
  type ConnectorCatalogCard,
  type CatalogFilter,
} from "./DataConnectionPage";

const MOCK_CATALOG: ConnectorCatalogCard[] = [
  { id: "jdbc-mysql", name: "MySQL JDBC", category: "database", description: "MySQL 连接器", capabilities: ["Batch syncs"], installed: true, required: true, runtime: "ready" },
  { id: "jdbc-postgres", name: "PostgreSQL JDBC", category: "database", description: "PostgreSQL 连接器", capabilities: ["Batch syncs", "Streaming syncs"], installed: true, required: true, runtime: "ready" },
  { id: "jdbc-oracle", name: "Oracle JDBC", category: "database", description: "Oracle 连接器", capabilities: ["Batch syncs"], installed: false, runtime: "stub" },
  { id: "file-local", name: "本地文件", category: "file", description: "本地文件", capabilities: ["Batch syncs"], installed: true, required: true, runtime: "ready" },
  { id: "file-object-store", name: "对象存储文件", category: "file", description: "对象存储", capabilities: ["Batch syncs", "Media syncs"], installed: true, required: true, runtime: "ready" },
  { id: "rest-api", name: "REST API", category: "api", description: "通用 REST API", capabilities: ["Batch syncs", "Webhooks"], installed: true, runtime: "ready" },
  { id: "shopify", name: "Shopify", category: "saas", description: "Shopify 电商", capabilities: ["Batch syncs"], installed: false, runtime: "stub" },
  { id: "salesforce", name: "Salesforce CRM", category: "saas", description: "Salesforce CRM", capabilities: ["Batch syncs"], installed: false, runtime: "stub" },
  { id: "kafka", name: "Kafka", category: "stream", description: "Kafka 事件流", capabilities: ["Streaming syncs"], installed: false, runtime: "stub" },
];

const NO_FILTER: CatalogFilter = { query: "", category: "all" };

describe("DataConnectionPage · CATEGORY_LABELS", () => {
  it("数据库 label", () => {
    expect(CATEGORY_LABELS.database).toBe("数据库");
  });
  it("SaaS label", () => {
    expect(CATEGORY_LABELS.saas).toBe("SaaS");
  });
  it("API label", () => {
    expect(CATEGORY_LABELS.api).toBe("API");
  });
  it("文件 label", () => {
    expect(CATEGORY_LABELS.file).toBe("文件");
  });
  it("流式 label", () => {
    expect(CATEGORY_LABELS.stream).toBe("流式");
  });
});

describe("DataConnectionPage · 用户文案", () => {
  it("将连接器能力代码翻译为产品语义", () => {
    expect(connectorCapabilityLabel("ingest")).toBe("数据入库");
    expect(connectorCapabilityLabel("ssh-tunnel")).toBe("SSH 隧道");
  });

  it("未知能力保持原值，避免伪造含义", () => {
    expect(connectorCapabilityLabel("future-capability")).toBe("future-capability");
  });
});

describe("DataConnectionPage · filterCatalog", () => {
  it("空筛选返回全部", () => {
    expect(filterCatalog(MOCK_CATALOG, NO_FILTER).length).toBe(MOCK_CATALOG.length);
  });
  it("按分类筛选 database", () => {
    const result = filterCatalog(MOCK_CATALOG, { ...NO_FILTER, category: "database" });
    expect(result.length).toBe(3);
    expect(result.every((c) => c.category === "database")).toBe(true);
  });
  it("按分类筛选 file", () => {
    const result = filterCatalog(MOCK_CATALOG, { ...NO_FILTER, category: "file" });
    expect(result.length).toBe(2);
  });
  it("搜索名称", () => {
    const result = filterCatalog(MOCK_CATALOG, { ...NO_FILTER, query: "kafka" });
    expect(result.length).toBe(1);
    expect(result[0].id).toBe("kafka");
  });
  it("搜索描述", () => {
    const result = filterCatalog(MOCK_CATALOG, { ...NO_FILTER, query: "Shopify" });
    expect(result.length).toBe(1);
    expect(result[0].id).toBe("shopify");
  });
  it("组合筛选", () => {
    const result = filterCatalog(MOCK_CATALOG, { query: "mysql", category: "database" });
    expect(result.length).toBe(1);
    expect(result[0].id).toBe("jdbc-mysql");
  });
  it("不修改原数组", () => {
    const orig = [...MOCK_CATALOG];
    filterCatalog(MOCK_CATALOG, { ...NO_FILTER, category: "database" });
    expect(MOCK_CATALOG).toEqual(orig);
  });
});

describe("DataConnectionPage · computeCatalogStats", () => {
  it("total 正确", () => {
    expect(computeCatalogStats(MOCK_CATALOG).total).toBe(9);
  });
  it("installed 正确", () => {
    expect(computeCatalogStats(MOCK_CATALOG).installed).toBe(5);
  });
  it("notInstalled 正确", () => {
    expect(computeCatalogStats(MOCK_CATALOG).notInstalled).toBe(4);
  });
  it("required 正确", () => {
    expect(computeCatalogStats(MOCK_CATALOG).required).toBe(4);
  });
  it("空数组返回全 0", () => {
    const s = computeCatalogStats([]);
    expect(s.total).toBe(0);
    expect(s.installed).toBe(0);
    expect(s.notInstalled).toBe(0);
    expect(s.required).toBe(0);
  });
});
