import { describe, expect, it } from "vitest";
import {
  CONFLICT_LABELS,
  DEFAULT_CONFIG,
  FREQUENCY_LABELS,
  STRATEGY_LABELS,
  configToApiPayload,
  estimateSyncDuration,
  formatDuration,
  formFromSchedule,
  hasErrors,
  validateConfig,
  type SyncConfigForm,
} from "./SyncConfigPage";

function makeForm(overrides: Partial<SyncConfigForm> = {}): SyncConfigForm {
  return { ...DEFAULT_CONFIG, ...overrides };
}

describe("SyncConfigPage · FREQUENCY_LABELS", () => {
  it("每小时", () => { expect(FREQUENCY_LABELS.hourly).toBe("每小时"); });
  it("自定义", () => { expect(FREQUENCY_LABELS.custom).toBe("自定义 Cron"); });
});

describe("SyncConfigPage · STRATEGY_LABELS", () => {
  it("全量同步", () => { expect(STRATEGY_LABELS.full).toBe("全量同步"); });
  it("增量同步", () => { expect(STRATEGY_LABELS.incremental).toBe("增量同步"); });
  it("CDC", () => { expect(STRATEGY_LABELS.cdc).toBe("CDC 变更捕获"); });
});

describe("SyncConfigPage · CONFLICT_LABELS", () => {
  it("跳过冲突", () => { expect(CONFLICT_LABELS.skip).toBe("跳过冲突"); });
  it("覆盖", () => { expect(CONFLICT_LABELS.overwrite).toBe("覆盖"); });
});

describe("SyncConfigPage · validateConfig · custom cron", () => {
  it("自定义频率 + 有效 cron 无错误", () => {
    const errs = validateConfig(makeForm({ frequency: "custom", customCron: "0 2 * * *" }));
    expect(errs.customCron).toBeUndefined();
  });
  it("自定义频率 + cron 少于 5 段报错", () => {
    const errs = validateConfig(makeForm({ frequency: "custom", customCron: "0 2" }));
    expect(errs.customCron).toBeDefined();
  });
  it("自定义频率 + cron 超过 6 段报错", () => {
    const errs = validateConfig(makeForm({ frequency: "custom", customCron: "0 2 * * 1 1 1" }));
    expect(errs.customCron).toBeDefined();
  });
});

describe("SyncConfigPage · validateConfig · email", () => {
  it("默认配置不注入演示邮箱或通知副作用", () => {
    expect(DEFAULT_CONFIG.notifyEmail).toBe("");
    expect(DEFAULT_CONFIG.notifyOnError).toBe(false);
  });
  it("开启通知但无邮箱报错", () => {
    const errs = validateConfig(makeForm({ notifyOnError: true, notifyEmail: "" }));
    expect(errs.notifyEmail).toBeDefined();
  });
  it("邮箱格式不对报错", () => {
    const errs = validateConfig(makeForm({ notifyOnError: true, notifyEmail: "bad" }));
    expect(errs.notifyEmail).toBeDefined();
  });
  it("有效邮箱无错误", () => {
    const errs = validateConfig(makeForm({ notifyOnError: true, notifyEmail: "ops@test.com" }));
    expect(errs.notifyEmail).toBeUndefined();
  });
  it("不开通知时邮箱可空", () => {
    const errs = validateConfig(makeForm({ notifyOnError: false, notifyOnComplete: false, notifyEmail: "" }));
    expect(errs.notifyEmail).toBeUndefined();
  });
});

describe("SyncConfigPage · current schedule", () => {
  it("从正式计划读取 Cron 和已保存配置", () => {
    expect(formFromSchedule({
      id: "sch-current",
      cron: "15 3 * * *",
      ingest: { syncConfig: { batchSize: 500 } },
    })).toMatchObject({ frequency: "custom", customCron: "15 3 * * *", batchSize: 500 });
  });
});

describe("SyncConfigPage · validateConfig · advanced", () => {
  it("并行度 0 报错", () => {
    const errs = validateConfig(makeForm({ parallelism: 0 }));
    expect(errs.parallelism).toBeDefined();
  });
  it("并行度 33 报错", () => {
    const errs = validateConfig(makeForm({ parallelism: 33 }));
    expect(errs.parallelism).toBeDefined();
  });
  it("批大小 0 报错", () => {
    const errs = validateConfig(makeForm({ batchSize: 0 }));
    expect(errs.batchSize).toBeDefined();
  });
  it("重试次数 -1 报错", () => {
    const errs = validateConfig(makeForm({ maxRetries: -1 }));
    expect(errs.maxRetries).toBeDefined();
  });
  it("默认配置无错误", () => {
    expect(hasErrors(validateConfig(DEFAULT_CONFIG))).toBe(false);
  });
});

describe("SyncConfigPage · configToApiPayload", () => {
  it("包含 frequency", () => {
    expect(configToApiPayload(DEFAULT_CONFIG).frequency).toBe("daily");
  });
  it("非 custom 时不含 cron", () => {
    const p = configToApiPayload(DEFAULT_CONFIG);
    expect(p.cron).toBeUndefined();
  });
  it("custom 时含 cron", () => {
    const p = configToApiPayload(makeForm({ frequency: "custom", customCron: "0 0 * * *" }));
    expect(p.cron).toBe("0 0 * * *");
  });
  it("包含 advanced.parallelism", () => {
    const p = configToApiPayload(DEFAULT_CONFIG);
    expect((p.advanced as Record<string, unknown>).parallelism).toBe(4);
  });
});

describe("SyncConfigPage · estimateSyncDuration", () => {
  it("0 行返回 0", () => {
    expect(estimateSyncDuration(DEFAULT_CONFIG, 0)).toBe(0);
  });
  it("正数行返回正数 ms", () => {
    expect(estimateSyncDuration(DEFAULT_CONFIG, 10000)).toBeGreaterThan(0);
  });
  it("更大并行度 → 更短耗时", () => {
    const slow = estimateSyncDuration(makeForm({ parallelism: 1, batchSize: 100 }), 10000);
    const fast = estimateSyncDuration(makeForm({ parallelism: 8, batchSize: 100 }), 10000);
    expect(fast).toBeLessThan(slow);
  });
});

describe("SyncConfigPage · formatDuration", () => {
  it("0 返回 —", () => { expect(formatDuration(0)).toBe("—"); });
  it("<1s 返回 ms", () => { expect(formatDuration(500)).toBe("500 ms"); });
  it("<60s 返回秒", () => { expect(formatDuration(30000)).toBe("30 秒"); });
  it(">=60s 返回分秒", () => {
    const r = formatDuration(90000);
    expect(r).toContain("分");
    expect(r).toContain("秒");
  });
});
