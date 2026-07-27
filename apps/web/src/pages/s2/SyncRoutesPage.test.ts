import { describe, expect, it } from "vitest";
import {
  ROUTE_STATUS_LABELS,
  computeRouteStats,
  filterRoutesByTab,
  formatNextRun,
  progressPercent,
  routeStatusTone,
  toggleRouteStatus,
  type SyncRoute,
} from "./SyncRoutesPage";

const MOCK_ROUTES: SyncRoute[] = [
  { id: "r1", name: "订单全量", source: "pg", target: "ds:orders", frequency: "每小时", status: "active", nextRunAt: new Date(Date.now() + 60000).toISOString(), progress: 0.5, conflicts: 0 },
  { id: "r2", name: "增量同步", source: "mysql", target: "ds:clean", frequency: "15分钟", status: "active", progress: 0.8, conflicts: 2 },
  { id: "r3", name: "商品同步", source: "shopify", target: "ds:products", frequency: "每天", status: "paused", conflicts: 0 },
  { id: "r4", name: "归档同步", source: "s3", target: "ds:archive", frequency: "每周", status: "error", conflicts: 5 },
  { id: "r5", name: "天气拉取", source: "rest", target: "ds:weather", frequency: "每小时", status: "error", conflicts: 1 },
];

describe("SyncRoutesPage · routeStatusTone", () => {
  it("active → ok", () => {
    expect(routeStatusTone("active")).toBe("ok");
  });
  it("paused → warn", () => {
    expect(routeStatusTone("paused")).toBe("warn");
  });
  it("error → bad", () => {
    expect(routeStatusTone("error")).toBe("bad");
  });
});

describe("SyncRoutesPage · ROUTE_STATUS_LABELS", () => {
  it("运行中", () => {
    expect(ROUTE_STATUS_LABELS.active).toBe("运行中");
  });
  it("已暂停", () => {
    expect(ROUTE_STATUS_LABELS.paused).toBe("已暂停");
  });
  it("异常", () => {
    expect(ROUTE_STATUS_LABELS.error).toBe("异常");
  });
});

describe("SyncRoutesPage · computeRouteStats", () => {
  it("total 正确", () => {
    expect(computeRouteStats(MOCK_ROUTES).total).toBe(5);
  });
  it("active 正确", () => {
    expect(computeRouteStats(MOCK_ROUTES).active).toBe(2);
  });
  it("paused 正确", () => {
    expect(computeRouteStats(MOCK_ROUTES).paused).toBe(1);
  });
  it("error 正确", () => {
    expect(computeRouteStats(MOCK_ROUTES).error).toBe(2);
  });
  it("conflicts 汇总正确", () => {
    expect(computeRouteStats(MOCK_ROUTES).conflicts).toBe(8);
  });
  it("空数组全 0", () => {
    const s = computeRouteStats([]);
    expect(s.total).toBe(0);
    expect(s.conflicts).toBe(0);
  });
});

describe("SyncRoutesPage · filterRoutesByTab", () => {
  it("all 返回全部", () => {
    expect(filterRoutesByTab(MOCK_ROUTES, "all").length).toBe(5);
  });
  it("active 过滤", () => {
    const r = filterRoutesByTab(MOCK_ROUTES, "active");
    expect(r.length).toBe(2);
    expect(r.every((x) => x.status === "active")).toBe(true);
  });
  it("paused 过滤", () => {
    expect(filterRoutesByTab(MOCK_ROUTES, "paused").length).toBe(1);
  });
  it("error 过滤", () => {
    expect(filterRoutesByTab(MOCK_ROUTES, "error").length).toBe(2);
  });
});

describe("SyncRoutesPage · formatNextRun", () => {
  it("空值返回 —", () => {
    expect(formatNextRun(undefined)).toBe("—");
  });
  it("无效日期返回 —", () => {
    expect(formatNextRun("bad")).toBe("—");
  });
  it("有效日期返回字符串", () => {
    const iso = "2026-07-27T10:00:00Z";
    const result = formatNextRun(iso);
    expect(result).toContain("2026");
  });
});

describe("SyncRoutesPage · progressPercent", () => {
  it("null 返回 0", () => {
    expect(progressPercent(undefined)).toBe(0);
  });
  it("0.5 → 50", () => {
    expect(progressPercent(0.5)).toBe(50);
  });
  it("1.0 → 100", () => {
    expect(progressPercent(1.0)).toBe(100);
  });
  it("超过 1 截断到 100", () => {
    expect(progressPercent(1.5)).toBe(100);
  });
  it("负数截断到 0", () => {
    expect(progressPercent(-0.5)).toBe(0);
  });
});

describe("SyncRoutesPage · toggleRouteStatus", () => {
  it("active → paused", () => {
    expect(toggleRouteStatus({ status: "active" } as SyncRoute)).toBe("paused");
  });
  it("paused → active", () => {
    expect(toggleRouteStatus({ status: "paused" } as SyncRoute)).toBe("active");
  });
  it("error → active", () => {
    expect(toggleRouteStatus({ status: "error" } as SyncRoute)).toBe("active");
  });
});
