import { useState } from "react";
import { Link } from "react-router-dom";
import { apiPost } from "../../api/client";
import {
  BpBanner,
  BpMetricGrid,
} from "./blueprintUi";
import { S2Chrome, useJsonGet } from "./shared";

// ── Types ──────────────────────────────────────────────────────

export type SyncFrequency = "hourly" | "daily" | "weekly" | "realtime" | "custom";

export type IncrementalStrategy = "full" | "incremental" | "cdc";

export type ConflictResolution = "skip" | "overwrite" | "merge" | "manual";

export type SyncConfigForm = {
  frequency: SyncFrequency;
  customCron: string;
  incrementalStrategy: IncrementalStrategy;
  conflictResolution: ConflictResolution;
  notifyOnError: boolean;
  notifyOnComplete: boolean;
  notifyEmail: string;
  // advanced
  parallelism: number;
  batchSize: number;
  timeoutSec: number;
  maxRetries: number;
};

export type ConfigErrors = Partial<Record<keyof SyncConfigForm, string>>;

// ── Pure functions ─────────────────────────────────────────────

export const FREQUENCY_LABELS: Record<SyncFrequency, string> = {
  hourly: "每小时",
  daily: "每天",
  weekly: "每周",
  realtime: "实时",
  custom: "自定义 Cron",
};

export const STRATEGY_LABELS: Record<IncrementalStrategy, string> = {
  full: "全量同步",
  incremental: "增量同步",
  cdc: "CDC 变更捕获",
};

export const CONFLICT_LABELS: Record<ConflictResolution, string> = {
  skip: "跳过冲突",
  overwrite: "覆盖",
  merge: "合并",
  manual: "人工处理",
};

export const DEFAULT_CONFIG: SyncConfigForm = {
  frequency: "daily",
  customCron: "0 2 * * *",
  incrementalStrategy: "incremental",
  conflictResolution: "skip",
  notifyOnError: true,
  notifyOnComplete: false,
  notifyEmail: "ops@example.com",
  parallelism: 4,
  batchSize: 1000,
  timeoutSec: 300,
  maxRetries: 3,
};

export function validateConfig(form: SyncConfigForm): ConfigErrors {
  const errors: ConfigErrors = {};
  if (form.frequency === "custom") {
    const parts = form.customCron.trim().split(/\s+/);
    if (parts.length < 5) {
      errors.customCron = "Cron 表达式至少 5 段（分 时 日 月 周）";
    } else if (parts.length > 6) {
      errors.customCron = "Cron 表达式最多 6 段";
    }
  }
  if (form.notifyOnError || form.notifyOnComplete) {
    if (!form.notifyEmail.trim()) {
      errors.notifyEmail = "开启通知需填写邮箱";
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.notifyEmail)) {
      errors.notifyEmail = "邮箱格式不正确";
    }
  }
  if (form.parallelism < 1 || form.parallelism > 32) {
    errors.parallelism = "并行度范围 1-32";
  }
  if (form.batchSize < 1 || form.batchSize > 100000) {
    errors.batchSize = "批大小范围 1-100000";
  }
  if (form.timeoutSec < 10 || form.timeoutSec > 7200) {
    errors.timeoutSec = "超时范围 10-7200 秒";
  }
  if (form.maxRetries < 0 || form.maxRetries > 10) {
    errors.maxRetries = "重试次数范围 0-10";
  }
  return errors;
}

export function hasErrors(errors: ConfigErrors): boolean {
  return Object.keys(errors).length > 0;
}

export function configToApiPayload(form: SyncConfigForm): Record<string, unknown> {
  return {
    frequency: form.frequency,
    cron: form.frequency === "custom" ? form.customCron : undefined,
    incrementalStrategy: form.incrementalStrategy,
    conflictResolution: form.conflictResolution,
    notifications: {
      onError: form.notifyOnError,
      onComplete: form.notifyOnComplete,
      email: form.notifyEmail || undefined,
    },
    advanced: {
      parallelism: form.parallelism,
      batchSize: form.batchSize,
      timeoutSec: form.timeoutSec,
      maxRetries: form.maxRetries,
    },
  };
}

export function estimateSyncDuration(form: SyncConfigForm, rowCount: number): number {
  // rough estimate: rows / (batchSize * parallelism) * 0.5s overhead per batch
  if (rowCount <= 0) return 0;
  const batches = Math.ceil(rowCount / form.batchSize);
  const parallelBatches = Math.ceil(batches / form.parallelism);
  return parallelBatches * 500; // ms
}

export function formatDuration(ms: number): string {
  if (ms <= 0) return "—";
  if (ms < 1000) return `${ms} ms`;
  const sec = Math.floor(ms / 1000);
  if (sec < 60) return `${sec} 秒`;
  const min = Math.floor(sec / 60);
  return `${min} 分 ${sec % 60} 秒`;
}

// ── Page Component ─────────────────────────────────────────────

export function SyncConfigPage() {
  const schedules = useJsonGet<{ items: { id: string; name?: string; cron?: string; active?: boolean }[] }>("/v1/schedules");
  const [form, setForm] = useState<SyncConfigForm>(DEFAULT_CONFIG);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [errors, setErrors] = useState<ConfigErrors>({});
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);

  function updateField<K extends keyof SyncConfigForm>(key: K, value: SyncConfigForm[K]) {
    setForm({ ...form, [key]: value });
  }

  async function handleSave() {
    const errs = validateConfig(form);
    setErrors(errs);
    if (hasErrors(errs)) {
      setMsg("表单有错误 · 请修正后重试");
      return;
    }
    setBusy(true);
    setMsg("");
    try {
      await apiPost("/v1/sync-config", configToApiPayload(form));
      setMsg("配置已保存");
    } catch (e) {
      setMsg(String((e as Error).message || e));
    } finally {
      setBusy(false);
    }
  }

  async function handleTestConnection() {
    setMsg("");
    setTestResult(null);
    setBusy(true);
    try {
      const r = await apiPost<{ ok?: boolean; latencyMs?: number; error?: string }>("/v1/sync-config/test", configToApiPayload(form));
      if (r.ok) {
        setTestResult(`连接成功 · 延迟 ${r.latencyMs ?? "?"} ms`);
      } else {
        setTestResult(`连接失败 · ${r.error || "未知错误"}`);
      }
    } catch (e) {
      setTestResult(`连接失败 · ${String((e as Error).message || e)}`);
    } finally {
      setBusy(false);
    }
  }

  function handleReset() {
    setForm(DEFAULT_CONFIG);
    setErrors({});
    setMsg("已重置为默认值");
    setTestResult(null);
  }

  const scheduleCount = schedules.data?.items?.length ?? 0;

  return (
    <S2Chrome title="同步配置" lede="同步频率 / 增量策略 / 冲突解决 / 通知与高级参数">
      <Link to="/data/schedules" className="btn-nav" style={{ marginBottom: 8, display: "inline-block" }}>
        打开计划编辑器 →
      </Link>
      <Link to="/data" className="btn-nav" style={{ marginLeft: 8 }}>
        数据连接器 →
      </Link>
      <button type="button" className="btn" style={{ marginLeft: 8 }} onClick={() => schedules.reload()}>
        刷新
      </button>

      {schedules.err && <p className="error">{schedules.err}</p>}
      {msg && <p className="aos-text">{msg}</p>}

      <BpMetricGrid
        items={[
          { label: "已注册计划", value: scheduleCount, tone: "muted" },
          { label: "并行度", value: form.parallelism, tone: "ok" },
          { label: "批大小", value: form.batchSize, tone: "ok" },
          { label: "超时(秒)", value: form.timeoutSec, tone: "muted" },
        ]}
      />

      {/* Main config form */}
      <div className="bp-object-panel">
        <h2 className="aos-text" style={{ fontSize: "0.9rem", marginBottom: "0.5rem" }}>基本配置</h2>

        <label className="muted" style={{ display: "block", fontSize: "0.75rem", marginBottom: 4 }}>
          同步频率
          <select
            value={form.frequency}
            onChange={(e) => updateField("frequency", e.target.value as SyncFrequency)}
            style={{ display: "block", width: "100%", marginTop: 4 }}
          >
            {Object.entries(FREQUENCY_LABELS).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
        </label>

        {form.frequency === "custom" && (
          <label className="muted" style={{ display: "block", fontSize: "0.75rem", marginBottom: 4 }}>
            Cron 表达式
            <input
              value={form.customCron}
              onChange={(e) => updateField("customCron", e.target.value)}
              className="mono"
              style={{ display: "block", width: "100%", marginTop: 4 }}
            />
            {errors.customCron && <span className="error" style={{ fontSize: "0.7rem" }}>{errors.customCron}</span>}
          </label>
        )}

        <label className="muted" style={{ display: "block", fontSize: "0.75rem", marginBottom: 4, marginTop: 8 }}>
          增量策略
          <select
            value={form.incrementalStrategy}
            onChange={(e) => updateField("incrementalStrategy", e.target.value as IncrementalStrategy)}
            style={{ display: "block", width: "100%", marginTop: 4 }}
          >
            {Object.entries(STRATEGY_LABELS).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
        </label>

        <label className="muted" style={{ display: "block", fontSize: "0.75rem", marginBottom: 4, marginTop: 8 }}>
          冲突解决
          <select
            value={form.conflictResolution}
            onChange={(e) => updateField("conflictResolution", e.target.value as ConflictResolution)}
            style={{ display: "block", width: "100%", marginTop: 4 }}
          >
            {Object.entries(CONFLICT_LABELS).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
        </label>
      </div>

      {/* Notifications */}
      <div className="bp-object-panel" style={{ marginTop: "0.75rem" }}>
        <h2 className="aos-text" style={{ fontSize: "0.9rem", marginBottom: "0.5rem" }}>通知设置</h2>
        <label style={{ display: "block", marginBottom: 4 }}>
          <input
            type="checkbox"
            checked={form.notifyOnError}
            onChange={(e) => updateField("notifyOnError", e.target.checked)}
          />{" "}
          同步失败时通知
        </label>
        <label style={{ display: "block", marginBottom: 4 }}>
          <input
            type="checkbox"
            checked={form.notifyOnComplete}
            onChange={(e) => updateField("notifyOnComplete", e.target.checked)}
          />{" "}
          同步完成时通知
        </label>
        <label className="muted" style={{ display: "block", fontSize: "0.75rem", marginBottom: 4 }}>
          通知邮箱
          <input
            type="email"
            value={form.notifyEmail}
            onChange={(e) => updateField("notifyEmail", e.target.value)}
            placeholder="ops@example.com"
            style={{ display: "block", width: "100%", marginTop: 4 }}
          />
          {errors.notifyEmail && <span className="error" style={{ fontSize: "0.7rem" }}>{errors.notifyEmail}</span>}
        </label>
      </div>

      {/* Advanced settings (collapsible) */}
      <div className="bp-object-panel" style={{ marginTop: "0.75rem" }}>
        <button
          type="button"
          className="nav-link"
          style={{ fontWeight: 600, padding: 0 }}
          onClick={() => setShowAdvanced(!showAdvanced)}
        >
          {showAdvanced ? "▼" : "▶"} 高级设置
        </button>

        {showAdvanced && (
          <div style={{ marginTop: "0.5rem" }}>
            <label className="muted" style={{ display: "block", fontSize: "0.75rem", marginBottom: 4 }}>
              并行度 (1-32)
              <input
                type="number"
                value={form.parallelism}
                onChange={(e) => updateField("parallelism", Number(e.target.value))}
                min={1}
                max={32}
                style={{ display: "block", width: "100%", marginTop: 4 }}
              />
              {errors.parallelism && <span className="error" style={{ fontSize: "0.7rem" }}>{errors.parallelism}</span>}
            </label>
            <label className="muted" style={{ display: "block", fontSize: "0.75rem", marginBottom: 4, marginTop: 8 }}>
              批大小 (1-100000)
              <input
                type="number"
                value={form.batchSize}
                onChange={(e) => updateField("batchSize", Number(e.target.value))}
                min={1}
                max={100000}
                style={{ display: "block", width: "100%", marginTop: 4 }}
              />
              {errors.batchSize && <span className="error" style={{ fontSize: "0.7rem" }}>{errors.batchSize}</span>}
            </label>
            <label className="muted" style={{ display: "block", fontSize: "0.75rem", marginBottom: 4, marginTop: 8 }}>
              超时 (秒, 10-7200)
              <input
                type="number"
                value={form.timeoutSec}
                onChange={(e) => updateField("timeoutSec", Number(e.target.value))}
                min={10}
                max={7200}
                style={{ display: "block", width: "100%", marginTop: 4 }}
              />
              {errors.timeoutSec && <span className="error" style={{ fontSize: "0.7rem" }}>{errors.timeoutSec}</span>}
            </label>
            <label className="muted" style={{ display: "block", fontSize: "0.75rem", marginBottom: 4, marginTop: 8 }}>
              重试次数 (0-10)
              <input
                type="number"
                value={form.maxRetries}
                onChange={(e) => updateField("maxRetries", Number(e.target.value))}
                min={0}
                max={10}
                style={{ display: "block", width: "100%", marginTop: 4 }}
              />
              {errors.maxRetries && <span className="error" style={{ fontSize: "0.7rem" }}>{errors.maxRetries}</span>}
            </label>

            <BpBanner tone="info">
              预估同步 10 万行耗时：{" "}
              <strong>{formatDuration(estimateSyncDuration(form, 100000))}</strong>
            </BpBanner>
          </div>
        )}
      </div>

      {/* Action buttons */}
      <div style={{ display: "flex", gap: 8, marginTop: "1rem", flexWrap: "wrap" }}>
        <button type="button" className="btn-primary" disabled={busy} onClick={() => void handleSave()}>
          {busy ? "保存中…" : "保存配置"}
        </button>
        <button type="button" className="btn" disabled={busy} onClick={() => void handleTestConnection()}>
          测试连接
        </button>
        <button type="button" className="btn" onClick={() => handleReset()}>
          重置
        </button>
      </div>

      {testResult && (
        <p className={testResult.startsWith("连接成功") ? "aos-text" : "error"} style={{ marginTop: 8 }}>
          {testResult}
        </p>
      )}

      <BpBanner tone="info">
        同步配置聚焦调度参数与冲突策略 · 具体 Cron 编辑请在{" "}
        <Link to="/data/schedules">计划编辑器</Link> 操作 ·{" "}
        <Link to="/data/sync-routes">同步路由</Link> 管理分发路径
      </BpBanner>
    </S2Chrome>
  );
}
