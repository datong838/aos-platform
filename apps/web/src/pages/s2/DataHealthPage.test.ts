import { describe, expect, it } from "vitest";
import {
  SEVERITY_LABEL,
  SEVERITY_TONE,
  RULE_TYPE_LABEL,
  RULE_STATUS_LABEL,
  RULE_STATUS_TONE,
  formatTimestamp,
  formatPercent,
  scoreToTone,
  filterIssues,
  filterRules,
  sortIssuesBySeverity,
  calculatePassRate,
  checkRuleViolation,
  ruleEffectiveness,
  type HealthIssue,
  type QualityRule,
} from "./DataHealthPage";

const MOCK_ISSUES: HealthIssue[] = [
  { id: "i1", severity: "warning", table: "orders", column: "amount", message: "null rate high", detectedAt: new Date(Date.now() - 60000).toISOString() },
  { id: "i2", severity: "critical", table: "sync", column: "ts", message: "delayed", detectedAt: new Date(Date.now() - 120000).toISOString() },
  { id: "i3", severity: "info", table: "dim", column: "name", message: "new value", detectedAt: new Date(Date.now() - 30000).toISOString() },
];

const MOCK_RULES: QualityRule[] = [
  { id: "r1", name: "非空检查", type: "completeness", target: "orders", status: "passing", lastCheckedAt: new Date().toISOString(), threshold: 0.99, actual: 1.0 },
  { id: "r2", name: "正值校验", type: "validity", target: "orders", status: "failing", lastCheckedAt: new Date().toISOString(), threshold: 1.0, actual: 0.95 },
  { id: "r3", name: "唯一性", type: "uniqueness", target: "customers", status: "passing", lastCheckedAt: new Date().toISOString(), threshold: 0.99, actual: 0.995 },
];

// ── Labels ────────────────────────────────────────────
describe("DataHealthPage · SEVERITY_LABEL", () => {
  it("critical → 严重", () => {
    expect(SEVERITY_LABEL.critical).toBe("严重");
  });
  it("has 3 levels", () => {
    expect(Object.keys(SEVERITY_LABEL)).toHaveLength(3);
  });
});

describe("DataHealthPage · SEVERITY_TONE", () => {
  it("critical → bad", () => {
    expect(SEVERITY_TONE.critical).toBe("bad");
  });
  it("info → muted", () => {
    expect(SEVERITY_TONE.info).toBe("muted");
  });
});

describe("DataHealthPage · RULE_TYPE_LABEL", () => {
  it("completeness → 完整性", () => {
    expect(RULE_TYPE_LABEL.completeness).toBe("完整性");
  });
  it("timeliness → 时效性", () => {
    expect(RULE_TYPE_LABEL.timeliness).toBe("时效性");
  });
});

describe("DataHealthPage · RULE_STATUS_LABEL", () => {
  it("passing → 通过", () => {
    expect(RULE_STATUS_LABEL.passing).toBe("通过");
  });
  it("failing → 失败", () => {
    expect(RULE_STATUS_LABEL.failing).toBe("失败");
  });
});

describe("DataHealthPage · RULE_STATUS_TONE", () => {
  it("passing → ok", () => {
    expect(RULE_STATUS_TONE.passing).toBe("ok");
  });
  it("error → bad", () => {
    expect(RULE_STATUS_TONE.error).toBe("bad");
  });
});

// ── formatTimestamp ───────────────────────────────────
describe("DataHealthPage · formatTimestamp", () => {
  it("empty → —", () => {
    expect(formatTimestamp("")).toBe("—");
  });
  it("invalid → —", () => {
    expect(formatTimestamp("invalid")).toBe("—");
  });
  it("just now", () => {
    expect(formatTimestamp(new Date().toISOString())).toBe("刚刚");
  });
});

// ── formatPercent ─────────────────────────────────────
describe("DataHealthPage · formatPercent", () => {
  it("0 → 0%", () => {
    expect(formatPercent(0)).toBe("0%");
  });
  it("1 → 100%", () => {
    expect(formatPercent(1)).toBe("100%");
  });
  it("0.123 → 12.3%", () => {
    expect(formatPercent(0.123)).toBe("12.3%");
  });
  it("very small → <0.1%", () => {
    expect(formatPercent(0.0001)).toBe("<0.1%");
  });
});

// ── scoreToTone ───────────────────────────────────────
describe("DataHealthPage · scoreToTone", () => {
  it(">=90 → ok", () => {
    expect(scoreToTone(95)).toBe("ok");
    expect(scoreToTone(90)).toBe("ok");
  });
  it(">=70 → warn", () => {
    expect(scoreToTone(75)).toBe("warn");
    expect(scoreToTone(70)).toBe("warn");
  });
  it("<70 → bad", () => {
    expect(scoreToTone(69)).toBe("bad");
    expect(scoreToTone(0)).toBe("bad");
  });
});

// ── filterIssues ──────────────────────────────────────
describe("DataHealthPage · filterIssues", () => {
  it("all severity + empty query → all", () => {
    expect(filterIssues(MOCK_ISSUES, "all", "")).toHaveLength(3);
  });
  it("filter by critical", () => {
    expect(filterIssues(MOCK_ISSUES, "critical", "")).toHaveLength(1);
  });
  it("filter by table name", () => {
    expect(filterIssues(MOCK_ISSUES, "all", "orders")).toHaveLength(1);
  });
  it("no match", () => {
    expect(filterIssues(MOCK_ISSUES, "all", "xyz")).toHaveLength(0);
  });
});

// ── filterRules ───────────────────────────────────────
describe("DataHealthPage · filterRules", () => {
  it("all status + empty query → all", () => {
    expect(filterRules(MOCK_RULES, "all", "")).toHaveLength(3);
  });
  it("filter by passing", () => {
    expect(filterRules(MOCK_RULES, "passing", "")).toHaveLength(2);
  });
  it("filter by target", () => {
    expect(filterRules(MOCK_RULES, "all", "orders")).toHaveLength(2);
  });
});

// ── sortIssuesBySeverity ──────────────────────────────
describe("DataHealthPage · sortIssuesBySeverity", () => {
  it("critical first", () => {
    const sorted = sortIssuesBySeverity(MOCK_ISSUES);
    expect(sorted[0].severity).toBe("critical");
    expect(sorted[1].severity).toBe("warning");
    expect(sorted[2].severity).toBe("info");
  });
});

// ── calculatePassRate ─────────────────────────────────
describe("DataHealthPage · calculatePassRate", () => {
  it("empty → 0", () => {
    expect(calculatePassRate([])).toBe(0);
  });
  it("2/3 passing", () => {
    expect(calculatePassRate(MOCK_RULES)).toBeCloseTo(2 / 3, 5);
  });
});

// ── checkRuleViolation ────────────────────────────────
describe("DataHealthPage · checkRuleViolation", () => {
  it("actual >= threshold → no violation", () => {
    expect(checkRuleViolation(MOCK_RULES[0])).toBe(false);
  });
  it("actual < threshold → violation", () => {
    expect(checkRuleViolation(MOCK_RULES[1])).toBe(true);
  });
});

// ── ruleEffectiveness ─────────────────────────────────
describe("DataHealthPage · ruleEffectiveness", () => {
  it("counts correctly", () => {
    const eff = ruleEffectiveness(MOCK_RULES);
    expect(eff.total).toBe(3);
    expect(eff.effective).toBe(2);
    expect(eff.ineffective).toBe(1);
  });
  it("empty → all zeros", () => {
    const eff = ruleEffectiveness([]);
    expect(eff.total).toBe(0);
    expect(eff.effective).toBe(0);
  });
});
