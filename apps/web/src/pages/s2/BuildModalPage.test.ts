import { describe, expect, it } from "vitest";
import {
  STATUS_LABEL,
  STATUS_TONE,
  STEP_STATUS_LABEL,
  formatTimestamp,
  formatDuration,
  computeProgress,
  totalDuration,
  filterLogs,
  overallStatusFromSteps,
  validateConfig,
  configToApiPayload,
  type BuildStep,
  type BuildLogEntry,
  type BuildConfig,
} from "./BuildModalPage";

const MOCK_STEPS: BuildStep[] = [
  { id: "s1", name: "检出", status: "success", startedAt: new Date().toISOString(), durationMs: 5000, logLines: ["ok"] },
  { id: "s2", name: "编译", status: "success", startedAt: new Date().toISOString(), durationMs: 10000, logLines: ["ok"] },
  { id: "s3", name: "测试", status: "running", startedAt: new Date().toISOString(), logLines: ["running"] },
  { id: "s4", name: "部署", status: "pending", logLines: [] },
];

const MOCK_LOGS: BuildLogEntry[] = [
  { timestamp: new Date().toISOString(), level: "info", message: "started" },
  { timestamp: new Date().toISOString(), level: "warn", message: "slow test" },
  { timestamp: new Date().toISOString(), level: "error", message: "flaky error" },
];

const MOCK_CONFIG: BuildConfig = {
  target: "production",
  branch: "main",
  commitSha: "abc123",
  resourceClass: "large",
  env: ["KEY=val"],
  notifications: ["slack:#dev"],
  cacheEnabled: true,
  retries: 2,
};

// ── Labels ────────────────────────────────────────────
describe("BuildModalPage · STATUS_LABEL", () => {
  it("queued → 排队中", () => {
    expect(STATUS_LABEL.queued).toBe("排队中");
  });
  it("running → 运行中", () => {
    expect(STATUS_LABEL.running).toBe("运行中");
  });
  it("success → 成功", () => {
    expect(STATUS_LABEL.success).toBe("成功");
  });
  it("failed → 失败", () => {
    expect(STATUS_LABEL.failed).toBe("失败");
  });
  it("cancelled → 已取消", () => {
    expect(STATUS_LABEL.cancelled).toBe("已取消");
  });
});

describe("BuildModalPage · STATUS_TONE", () => {
  it("success → ok", () => {
    expect(STATUS_TONE.success).toBe("ok");
  });
  it("running → warn", () => {
    expect(STATUS_TONE.running).toBe("warn");
  });
  it("failed → bad", () => {
    expect(STATUS_TONE.failed).toBe("bad");
  });
});

describe("BuildModalPage · STEP_STATUS_LABEL", () => {
  it("pending → 等待", () => {
    expect(STEP_STATUS_LABEL.pending).toBe("等待");
  });
  it("running → 运行中", () => {
    expect(STEP_STATUS_LABEL.running).toBe("运行中");
  });
});

// ── formatTimestamp ───────────────────────────────────
describe("BuildModalPage · formatTimestamp", () => {
  it("empty → —", () => {
    expect(formatTimestamp("")).toBe("—");
  });
  it("just now", () => {
    expect(formatTimestamp(new Date().toISOString())).toBe("刚刚");
  });
});

// ── formatDuration ────────────────────────────────────
describe("BuildModalPage · formatDuration", () => {
  it("0 → —", () => {
    expect(formatDuration(0)).toBe("—");
  });
  it("negative → —", () => {
    expect(formatDuration(-1)).toBe("—");
  });
  it("< 1000 → ms", () => {
    expect(formatDuration(500)).toBe("500 ms");
  });
  it("< 60 → seconds", () => {
    expect(formatDuration(30000)).toBe("30s");
  });
  it(">= 60 → min + sec", () => {
    expect(formatDuration(90000)).toBe("1m 30s");
  });
});

// ── computeProgress ───────────────────────────────────
describe("BuildModalPage · computeProgress", () => {
  it("empty → 0", () => {
    expect(computeProgress([])).toBe(0);
  });
  it("2/4 done → 0.5", () => {
    expect(computeProgress(MOCK_STEPS)).toBe(0.5);
  });
  it("all done → 1", () => {
    const allDone: BuildStep[] = [
      { id: "s1", name: "a", status: "success", logLines: [] },
      { id: "s2", name: "b", status: "success", logLines: [] },
    ];
    expect(computeProgress(allDone)).toBe(1);
  });
});

// ── totalDuration ─────────────────────────────────────
describe("BuildModalPage · totalDuration", () => {
  it("empty → 0", () => {
    expect(totalDuration([])).toBe(0);
  });
  it("sums durations", () => {
    expect(totalDuration(MOCK_STEPS)).toBe(15000);
  });
});

// ── filterLogs ────────────────────────────────────────
describe("BuildModalPage · filterLogs", () => {
  it("all level + empty query → all", () => {
    expect(filterLogs(MOCK_LOGS, "all", "")).toHaveLength(3);
  });
  it("filter by error", () => {
    expect(filterLogs(MOCK_LOGS, "error", "")).toHaveLength(1);
  });
  it("filter by query", () => {
    expect(filterLogs(MOCK_LOGS, "all", "slow")).toHaveLength(1);
  });
  it("no match", () => {
    expect(filterLogs(MOCK_LOGS, "all", "xyz")).toHaveLength(0);
  });
});

// ── overallStatusFromSteps ────────────────────────────
describe("BuildModalPage · overallStatusFromSteps", () => {
  it("empty → queued", () => {
    expect(overallStatusFromSteps([])).toBe("queued");
  });
  it("has running → running", () => {
    expect(overallStatusFromSteps(MOCK_STEPS)).toBe("running");
  });
  it("all success → success", () => {
    const allSuccess: BuildStep[] = [
      { id: "s1", name: "a", status: "success", logLines: [] },
    ];
    expect(overallStatusFromSteps(allSuccess)).toBe("success");
  });
  it("has failed → failed", () => {
    const withFailed: BuildStep[] = [
      { id: "s1", name: "a", status: "success", logLines: [] },
      { id: "s2", name: "b", status: "failed", logLines: [] },
    ];
    expect(overallStatusFromSteps(withFailed)).toBe("failed");
  });
  it("all skipped → success", () => {
    const allSkipped: BuildStep[] = [
      { id: "s1", name: "a", status: "skipped", logLines: [] },
    ];
    expect(overallStatusFromSteps(allSkipped)).toBe("success");
  });
});

// ── validateConfig ────────────────────────────────────
describe("BuildModalPage · validateConfig", () => {
  it("valid config → null", () => {
    expect(validateConfig(MOCK_CONFIG)).toBeNull();
  });
  it("empty target → error", () => {
    expect(validateConfig({ ...MOCK_CONFIG, target: "" })).not.toBeNull();
  });
  it("empty branch → error", () => {
    expect(validateConfig({ ...MOCK_CONFIG, branch: "" })).not.toBeNull();
  });
  it("empty commitSha → error", () => {
    expect(validateConfig({ ...MOCK_CONFIG, commitSha: "" })).not.toBeNull();
  });
  it("negative retries → error", () => {
    expect(validateConfig({ ...MOCK_CONFIG, retries: -1 })).not.toBeNull();
  });
  it("retries > 5 → error", () => {
    expect(validateConfig({ ...MOCK_CONFIG, retries: 6 })).not.toBeNull();
  });
});

// ── configToApiPayload ────────────────────────────────
describe("BuildModalPage · configToApiPayload", () => {
  it("converts to snake_case", () => {
    const payload = configToApiPayload(MOCK_CONFIG);
    expect(payload.target).toBe("production");
    expect(payload.branch).toBe("main");
    expect(payload.commit_sha).toBe("abc123");
    expect(payload.resource_class).toBe("large");
    expect(payload.cache).toBe(true);
    expect(payload.max_retries).toBe(2);
  });
  it("filters empty env entries", () => {
    const config = { ...MOCK_CONFIG, env: ["A=1", "", "  ", "B=2"] };
    const payload = configToApiPayload(config);
    expect(payload.env_vars).toEqual(["A=1", "B=2"]);
  });
  it("filters empty notification entries", () => {
    const config = { ...MOCK_CONFIG, notifications: ["slack:#a", ""] };
    const payload = configToApiPayload(config);
    expect(payload.notifications).toEqual(["slack:#a"]);
  });
});
