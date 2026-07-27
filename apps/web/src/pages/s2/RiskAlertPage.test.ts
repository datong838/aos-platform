import { describe, expect, it } from "vitest";
import {
  SEVERITY_META,
  STATUS_META,
  SEVERITY_FILTERS,
  MOCK_ALERTS,
  filterBySeverity,
  computeStats,
  formatAlertTime,
  type RiskAlert,
} from "./RiskAlertPage";

describe("RiskAlertPage · SEVERITY_META", () => {
  it("包含 critical/warning/info 三种严重度", () => {
    expect(SEVERITY_META.critical).toBeTruthy();
    expect(SEVERITY_META.warning).toBeTruthy();
    expect(SEVERITY_META.info).toBeTruthy();
  });

  it("每个严重度有 label/color/bg/icon", () => {
    for (const key of Object.keys(SEVERITY_META)) {
      const s = SEVERITY_META[key as keyof typeof SEVERITY_META];
      expect(s.label.length).toBeGreaterThan(0);
      expect(s.color.length).toBeGreaterThan(0);
      expect(s.bg.length).toBeGreaterThan(0);
      expect(s.icon.length).toBeGreaterThan(0);
    }
  });
});

describe("RiskAlertPage · STATUS_META", () => {
  it("包含 open/processing/resolved 三种状态", () => {
    expect(STATUS_META.open).toBeTruthy();
    expect(STATUS_META.processing).toBeTruthy();
    expect(STATUS_META.resolved).toBeTruthy();
  });

  it("每个状态有 label/color/bg", () => {
    for (const key of Object.keys(STATUS_META)) {
      const s = STATUS_META[key as keyof typeof STATUS_META];
      expect(s.label.length).toBeGreaterThan(0);
      expect(s.color.length).toBeGreaterThan(0);
      expect(s.bg.length).toBeGreaterThan(0);
    }
  });
});

describe("RiskAlertPage · SEVERITY_FILTERS", () => {
  it("包含 all + 3 个严重度", () => {
    expect(SEVERITY_FILTERS.length).toBe(4);
  });

  it("第一个是 all", () => {
    expect(SEVERITY_FILTERS[0].id).toBe("all");
    expect(SEVERITY_FILTERS[0].label).toBe("全部");
  });
});

describe("RiskAlertPage · MOCK_ALERTS", () => {
  it("至少 5 条告警", () => {
    expect(MOCK_ALERTS.length).toBeGreaterThanOrEqual(5);
  });

  it("每条告警有完整字段", () => {
    for (const a of MOCK_ALERTS) {
      expect(a.id.length).toBeGreaterThan(0);
      expect(a.time.length).toBeGreaterThan(0);
      expect(a.type.length).toBeGreaterThan(0);
      expect(["critical", "warning", "info"]).toContain(a.severity);
      expect(a.source.length).toBeGreaterThan(0);
      expect(["open", "processing", "resolved"]).toContain(a.status);
      expect(a.title.length).toBeGreaterThan(0);
    }
  });

  it("包含至少 1 条 critical", () => {
    expect(MOCK_ALERTS.some((a) => a.severity === "critical")).toBe(true);
  });

  it("包含至少 1 条 warning", () => {
    expect(MOCK_ALERTS.some((a) => a.severity === "warning")).toBe(true);
  });

  it("包含至少 1 条 info", () => {
    expect(MOCK_ALERTS.some((a) => a.severity === "info")).toBe(true);
  });

  it("detail 字段有触发规则", () => {
    const withDetail = MOCK_ALERTS.filter((a) => a.detail);
    expect(withDetail.length).toBeGreaterThan(0);
    for (const a of withDetail) {
      expect(a.detail!.trigger.length).toBeGreaterThan(0);
    }
  });
});

describe("RiskAlertPage · filterBySeverity", () => {
  it("all 返回全部", () => {
    const result = filterBySeverity(MOCK_ALERTS, "all");
    expect(result.length).toBe(MOCK_ALERTS.length);
  });

  it("critical 只返回严重告警", () => {
    const result = filterBySeverity(MOCK_ALERTS, "critical");
    expect(result.every((a) => a.severity === "critical")).toBe(true);
    expect(result.length).toBeGreaterThan(0);
  });

  it("warning 只返回警告告警", () => {
    const result = filterBySeverity(MOCK_ALERTS, "warning");
    expect(result.every((a) => a.severity === "warning")).toBe(true);
  });

  it("info 只返回提示告警", () => {
    const result = filterBySeverity(MOCK_ALERTS, "info");
    expect(result.every((a) => a.severity === "info")).toBe(true);
  });

  it("不修改原数组", () => {
    const original = [...MOCK_ALERTS];
    filterBySeverity(MOCK_ALERTS, "critical");
    expect(MOCK_ALERTS).toEqual(original);
  });
});

describe("RiskAlertPage · computeStats", () => {
  it("返回 total/critical/processing/resolved", () => {
    const stats = computeStats(MOCK_ALERTS);
    expect(stats).toHaveProperty("total");
    expect(stats).toHaveProperty("critical");
    expect(stats).toHaveProperty("processing");
    expect(stats).toHaveProperty("resolved");
  });

  it("total 等于告警总数", () => {
    const stats = computeStats(MOCK_ALERTS);
    expect(stats.total).toBe(MOCK_ALERTS.length);
  });

  it("critical 数量正确", () => {
    const expected = MOCK_ALERTS.filter((a) => a.severity === "critical").length;
    const stats = computeStats(MOCK_ALERTS);
    expect(stats.critical).toBe(expected);
  });

  it("processing 数量正确", () => {
    const expected = MOCK_ALERTS.filter((a) => a.status === "processing").length;
    const stats = computeStats(MOCK_ALERTS);
    expect(stats.processing).toBe(expected);
  });

  it("resolved 数量正确", () => {
    const expected = MOCK_ALERTS.filter((a) => a.status === "resolved").length;
    const stats = computeStats(MOCK_ALERTS);
    expect(stats.resolved).toBe(expected);
  });

  it("空数组返回全 0", () => {
    const stats = computeStats([]);
    expect(stats.total).toBe(0);
    expect(stats.critical).toBe(0);
    expect(stats.processing).toBe(0);
    expect(stats.resolved).toBe(0);
  });
});

describe("RiskAlertPage · formatAlertTime", () => {
  it("1 分钟内 → 刚刚", () => {
    expect(formatAlertTime(new Date(Date.now() - 30_000).toISOString())).toBe("刚刚");
  });

  it("分钟级包含「分钟前」", () => {
    const result = formatAlertTime(new Date(Date.now() - 5 * 60_000).toISOString());
    expect(result).toContain("分钟前");
  });

  it("小时级包含「小时前」", () => {
    const result = formatAlertTime(new Date(Date.now() - 3 * 3600_000).toISOString());
    expect(result).toContain("小时前");
  });

  it("天级包含「天前」", () => {
    const result = formatAlertTime(new Date(Date.now() - 3 * 86400_000).toISOString());
    expect(result).toContain("天前");
  });
});

describe("RiskAlertPage · 边界场景", () => {
  it("空告警列表 filterBySeverity 返回空", () => {
    expect(filterBySeverity([], "all")).toEqual([]);
    expect(filterBySeverity([], "critical")).toEqual([]);
  });

  it("空告警列表 computeStats 全 0", () => {
    const stats = computeStats([]);
    expect(stats.total).toBe(0);
  });

  it("自定义告警数据 filterBySeverity 正确", () => {
    const custom: RiskAlert[] = [
      {
        id: "test-1",
        time: new Date().toISOString(),
        type: "测试",
        severity: "critical",
        source: "测试",
        status: "open",
        title: "测试告警",
      },
    ];
    expect(filterBySeverity(custom, "critical")).toHaveLength(1);
    expect(filterBySeverity(custom, "warning")).toHaveLength(0);
  });
});
