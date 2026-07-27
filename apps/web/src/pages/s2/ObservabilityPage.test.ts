import { describe, expect, it } from "vitest";
import {
  avgTrend,
  countAlertStatus,
  deltaTone,
  errorRateLevel,
  filterAlerts,
  filterTraces,
  formatCount,
  formatDelta,
  formatDuration,
  latencyLevel,
  normalizeSpans,
  pointsForRange,
  sparklinePath,
  TIME_RANGES,
  type AlertRow,
  type TraceRow,
  type TraceSpan,
  type TrendPoint,
} from "./ObservabilityPage";

const TRACES: TraceRow[] = [
  { traceId: "t_001", rootSpan: "sendEmail", service: "aip-functions", durationMs: 12261, status: "ok", spans: 13, startedAt: "10:42" },
  { traceId: "t_002", rootSpan: "llm_summarize", service: "llm-router", durationMs: 6012, status: "error", spans: 4, startedAt: "10:41" },
  { traceId: "t_003", rootSpan: "query.objects", service: "ontology-api", durationMs: 348, status: "ok", spans: 6, startedAt: "10:41" },
];

const ALERTS: AlertRow[] = [
  { id: "a1", name: "P95 高", severity: "critical", status: "firing", firedAt: "10:44", value: "942ms" },
  { id: "a2", name: "错误率高", severity: "warning", status: "acknowledged", firedAt: "10:40", value: "6.1%" },
  { id: "a3", name: "Token 80%", severity: "warning", status: "firing", firedAt: "10:35", value: "82%" },
  { id: "a4", name: "Pod 重启", severity: "info", status: "silenced", firedAt: "10:20", value: "1" },
];

describe("ObservabilityPage · formatCount", () => {
  it("小于 1000 原样返回", () => {
    expect(formatCount(42)).toBe("42");
    expect(formatCount(999)).toBe("999");
  });

  it("千级别加 K", () => {
    expect(formatCount(1500)).toBe("1.5K");
    expect(formatCount(12400)).toBe("12.4K");
  });

  it("百万级别加 M", () => {
    expect(formatCount(2_840_000)).toBe("2.84M");
  });

  it("十亿级别加 B", () => {
    expect(formatCount(1_500_000_000)).toBe("1.50B");
  });
});

describe("ObservabilityPage · formatDuration", () => {
  it("< 1000 返回 ms", () => {
    expect(formatDuration(348)).toBe("348ms");
    expect(formatDuration(999)).toBe("999ms");
  });

  it(">= 1000 返回 s（两位小数）", () => {
    expect(formatDuration(12261)).toBe("12.26s");
    expect(formatDuration(6012)).toBe("6.01s");
  });
});

describe("ObservabilityPage · formatDelta & deltaTone", () => {
  it("正数加 + 前缀", () => {
    expect(formatDelta(8.2)).toBe("+8.2%");
  });

  it("负数不加前缀", () => {
    expect(formatDelta(-3.1)).toBe("-3.1%");
  });

  it("0 不加前缀（formatDelta 只对 > 0 加 +）", () => {
    expect(formatDelta(0)).toBe("0.0%");
  });

  it("deltaTone 上升为 up", () => {
    expect(deltaTone(8.2)).toBe("up");
    expect(deltaTone(15.6)).toBe("up");
  });

  it("deltaTone 下降为 down", () => {
    expect(deltaTone(-12.5)).toBe("down");
    expect(deltaTone(-3.1)).toBe("down");
  });

  it("deltaTone 0±0.5 为 flat", () => {
    expect(deltaTone(0)).toBe("flat");
    expect(deltaTone(0.3)).toBe("flat");
    expect(deltaTone(-0.4)).toBe("flat");
  });
});

describe("ObservabilityPage · latencyLevel / errorRateLevel", () => {
  it("latency good <= 200", () => {
    expect(latencyLevel(100)).toBe("good");
    expect(latencyLevel(200)).toBe("good");
  });

  it("latency warn 201-800", () => {
    expect(latencyLevel(500)).toBe("warn");
    expect(latencyLevel(800)).toBe("warn");
  });

  it("latency bad > 800", () => {
    expect(latencyLevel(801)).toBe("bad");
    expect(latencyLevel(2000)).toBe("bad");
  });

  it("errorRate good <= 0.01", () => {
    expect(errorRateLevel(0)).toBe("good");
    expect(errorRateLevel(0.01)).toBe("good");
  });

  it("errorRate warn 0.01-0.05", () => {
    expect(errorRateLevel(0.02)).toBe("warn");
    expect(errorRateLevel(0.05)).toBe("warn");
  });

  it("errorRate bad > 0.05", () => {
    expect(errorRateLevel(0.06)).toBe("bad");
    expect(errorRateLevel(0.5)).toBe("bad");
  });
});

describe("ObservabilityPage · filterTraces", () => {
  it("空关键字返回全部", () => {
    expect(filterTraces(TRACES, "")).toHaveLength(3);
    expect(filterTraces(TRACES, "   ")).toHaveLength(3);
  });

  it("按 traceId 匹配", () => {
    const r = filterTraces(TRACES, "t_002");
    expect(r).toHaveLength(1);
    expect(r[0].traceId).toBe("t_002");
  });

  it("按 service 匹配（大小写不敏感）", () => {
    const r = filterTraces(TRACES, "LLM");
    expect(r).toHaveLength(1);
    expect(r[0].service).toBe("llm-router");
  });

  it("按 rootSpan 匹配", () => {
    const r = filterTraces(TRACES, "sendemail");
    expect(r).toHaveLength(1);
    expect(r[0].rootSpan).toBe("sendEmail");
  });

  it("无匹配返回空数组", () => {
    expect(filterTraces(TRACES, "nope")).toEqual([]);
  });
});

describe("ObservabilityPage · filterAlerts & countAlertStatus", () => {
  it("all 返回全部", () => {
    expect(filterAlerts(ALERTS, "all")).toHaveLength(4);
  });

  it("critical 只返回严重", () => {
    const r = filterAlerts(ALERTS, "critical");
    expect(r).toHaveLength(1);
    expect(r[0].id).toBe("a1");
  });

  it("warning 返回所有警告", () => {
    expect(filterAlerts(ALERTS, "warning")).toHaveLength(2);
  });

  it("countAlertStatus 统计各状态", () => {
    const c = countAlertStatus(ALERTS);
    expect(c.firing).toBe(2);
    expect(c.acknowledged).toBe(1);
    expect(c.silenced).toBe(1);
  });

  it("countAlertStatus 空数组全 0", () => {
    const c = countAlertStatus([]);
    expect(c).toEqual({ firing: 0, acknowledged: 0, silenced: 0 });
  });
});

describe("ObservabilityPage · normalizeSpans", () => {
  it("空数组返回空", () => {
    expect(normalizeSpans([])).toEqual([]);
  });

  it("归一化到 0-100", () => {
    const spans: TraceSpan[] = [
      { id: "s1", name: "a", service: "x", startMs: 0, durationMs: 1000, level: 0, kind: "parent" },
      { id: "s2", name: "b", service: "x", startMs: 500, durationMs: 500, level: 1, kind: "nested" },
    ];
    const r = normalizeSpans(spans);
    // 最大结束时间是 1000，归一化后 s1 的 start 应该是 0，duration 是 100
    expect(r[0].startMs).toBeCloseTo(0);
    expect(r[0].durationMs).toBeCloseTo(100);
    expect(r[1].startMs).toBeCloseTo(50);
    expect(r[1].durationMs).toBeCloseTo(50);
  });
});

describe("ObservabilityPage · avgTrend & sparklinePath", () => {
  const points: TrendPoint[] = [
    { t: "0m", requests: 100, latencyMs: 200, errors: 0 },
    { t: "5m", requests: 200, latencyMs: 300, errors: 2 },
    { t: "10m", requests: 300, latencyMs: 400, errors: 1 },
  ];

  it("avgTrend 计算平均值", () => {
    expect(avgTrend(points, "requests")).toBeCloseTo(200);
    expect(avgTrend(points, "latencyMs")).toBeCloseTo(300);
    expect(avgTrend(points, "errors")).toBeCloseTo(1);
  });

  it("avgTrend 空数组返回 0", () => {
    expect(avgTrend([], "requests")).toBe(0);
  });

  it("sparklinePath 生成 M/L 指令", () => {
    const path = sparklinePath([1, 2, 3]);
    expect(path.startsWith("M")).toBe(true);
    expect(path).toContain("L");
  });

  it("sparklinePath 空数组返回空字符串", () => {
    expect(sparklinePath([])).toBe("");
  });
});

describe("ObservabilityPage · 时间范围", () => {
  it("TIME_RANGES 包含 4 个选项", () => {
    expect(TIME_RANGES).toEqual(["1h", "6h", "24h", "7d"]);
    expect(TIME_RANGES).toHaveLength(4);
  });

  it("pointsForRange 返回正整数", () => {
    expect(pointsForRange("1h")).toBe(12);
    expect(pointsForRange("6h")).toBe(24);
    expect(pointsForRange("24h")).toBe(48);
    expect(pointsForRange("7d")).toBe(56);
  });
});
