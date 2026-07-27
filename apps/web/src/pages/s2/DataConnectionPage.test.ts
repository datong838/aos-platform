import { describe, expect, it } from "vitest";
import {
  CATEGORY_LABELS,
  STATUS_LABELS,
  computeConnectionStats,
  filterConnections,
  formatLastSync,
  paginate,
  statusTone,
  totalPages,
  type ConnectionCard,
  type ConnectionFilter,
} from "./DataConnectionPage";

const MOCK_ITEMS: ConnectionCard[] = [
  { id: "pg-prod", name: "PostgreSQL 生产库", category: "database", status: "online", tableCount: 48, lastSyncAt: new Date(Date.now() - 5 * 60000).toISOString() },
  { id: "mysql-orders", name: "MySQL 订单库", category: "database", status: "syncing", tableCount: 23, lastSyncAt: new Date(Date.now() - 2 * 60000).toISOString() },
  { id: "shopify", name: "Shopify 店铺", category: "saas", status: "online", tableCount: 12 },
  { id: "kafka", name: "Kafka 事件流", category: "stream", status: "online", tableCount: 5 },
  { id: "rest-weather", name: "天气 REST API", category: "api", status: "error", tableCount: 2 },
  { id: "s3", name: "S3 数据湖", category: "file", status: "offline", tableCount: 0 },
];

const NO_FILTER: ConnectionFilter = { query: "", category: "all", status: "all" };

describe("DataConnectionPage · statusTone", () => {
  it("online → ok", () => {
    expect(statusTone("online")).toBe("ok");
  });
  it("syncing → warn", () => {
    expect(statusTone("syncing")).toBe("warn");
  });
  it("error → bad", () => {
    expect(statusTone("error")).toBe("bad");
  });
  it("offline → muted", () => {
    expect(statusTone("offline")).toBe("muted");
  });
});

describe("DataConnectionPage · CATEGORY_LABELS / STATUS_LABELS", () => {
  it("数据库 label", () => {
    expect(CATEGORY_LABELS.database).toBe("数据库");
  });
  it("在线 label", () => {
    expect(STATUS_LABELS.online).toBe("在线");
  });
});

describe("DataConnectionPage · filterConnections", () => {
  it("空筛选返回全部", () => {
    expect(filterConnections(MOCK_ITEMS, NO_FILTER).length).toBe(MOCK_ITEMS.length);
  });
  it("按分类筛选 database", () => {
    const result = filterConnections(MOCK_ITEMS, { ...NO_FILTER, category: "database" });
    expect(result.length).toBe(2);
    expect(result.every((c) => c.category === "database")).toBe(true);
  });
  it("按状态筛选 online", () => {
    const result = filterConnections(MOCK_ITEMS, { ...NO_FILTER, status: "online" });
    expect(result.length).toBe(3);
  });
  it("搜索名称", () => {
    const result = filterConnections(MOCK_ITEMS, { ...NO_FILTER, query: "kafka" });
    expect(result.length).toBe(1);
    expect(result[0].id).toBe("kafka");
  });
  it("搜索 ID", () => {
    const result = filterConnections(MOCK_ITEMS, { ...NO_FILTER, query: "pg-prod" });
    expect(result.length).toBe(1);
  });
  it("组合筛选", () => {
    const result = filterConnections(MOCK_ITEMS, { query: "shop", category: "saas", status: "online" });
    expect(result.length).toBe(1);
    expect(result[0].id).toBe("shopify");
  });
  it("不修改原数组", () => {
    const orig = [...MOCK_ITEMS];
    filterConnections(MOCK_ITEMS, { ...NO_FILTER, category: "database" });
    expect(MOCK_ITEMS).toEqual(orig);
  });
});

describe("DataConnectionPage · computeConnectionStats", () => {
  it("total 正确", () => {
    expect(computeConnectionStats(MOCK_ITEMS).total).toBe(6);
  });
  it("online 正确", () => {
    expect(computeConnectionStats(MOCK_ITEMS).online).toBe(3);
  });
  it("error 正确", () => {
    expect(computeConnectionStats(MOCK_ITEMS).error).toBe(1);
  });
  it("totalTables 正确", () => {
    expect(computeConnectionStats(MOCK_ITEMS).totalTables).toBe(90);
  });
  it("空数组返回全 0", () => {
    const s = computeConnectionStats([]);
    expect(s.total).toBe(0);
    expect(s.totalTables).toBe(0);
  });
});

describe("DataConnectionPage · paginate / totalPages", () => {
  it("第一页返回前 pageSize 条", () => {
    const page = paginate(MOCK_ITEMS, 1, 2);
    expect(page.length).toBe(2);
    expect(page[0].id).toBe("pg-prod");
  });
  it("超出范围返回空", () => {
    expect(paginate(MOCK_ITEMS, 99, 2).length).toBe(0);
  });
  it("totalPages 向上取整", () => {
    expect(totalPages(6, 2)).toBe(3);
    expect(totalPages(5, 2)).toBe(3);
  });
  it("totalPages 至少 1", () => {
    expect(totalPages(0, 10)).toBe(1);
  });
});

describe("DataConnectionPage · formatLastSync", () => {
  it("空值返回 —", () => {
    expect(formatLastSync(undefined)).toBe("—");
  });
  it("无效日期返回 —", () => {
    expect(formatLastSync("not-a-date")).toBe("—");
  });
  it("1 分钟内返回刚刚", () => {
    expect(formatLastSync(new Date(Date.now() - 10000).toISOString())).toBe("刚刚");
  });
  it("小于 1 小时返回分钟", () => {
    const result = formatLastSync(new Date(Date.now() - 30 * 60000).toISOString());
    expect(result).toContain("分钟前");
  });
  it("大于 1 小时返回小时/天", () => {
    const result = formatLastSync(new Date(Date.now() - 3 * 86400000).toISOString());
    expect(result).toContain("天前");
  });
});
