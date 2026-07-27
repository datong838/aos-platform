import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiPost } from "../../api/client";
import {
  BpBanner,
  BpMetricGrid,
  BpStagePipeline,
  BpTable,
  BpTabs,
  BpToolbar,
} from "./blueprintUi";
import { S2Chrome, useJsonGet } from "./shared";

// ── Types ──────────────────────────────────────────────────────

export type BuildStatus =
  | "queued"
  | "running"
  | "success"
  | "failed"
  | "cancelled";

export type StepStatus = "pending" | "running" | "success" | "failed" | "skipped";

export type BuildStep = {
  id: string;
  name: string;
  status: StepStatus;
  startedAt?: string;
  durationMs?: number;
  logLines: string[];
};

export type BuildConfig = {
  target: string;
  branch: string;
  commitSha: string;
  resourceClass: "small" | "medium" | "large";
  env: string[];
  notifications: string[];
  cacheEnabled: boolean;
  retries: number;
};

export type BuildLogEntry = {
  timestamp: string;
  level: "info" | "warn" | "error";
  message: string;
};

export type BuildJob = {
  id: string;
  name: string;
  status: BuildStatus;
  triggeredBy: string;
  startedAt: string;
  finishedAt?: string;
  config: BuildConfig;
  steps: BuildStep[];
  logs: BuildLogEntry[];
};

// ── Pure functions ─────────────────────────────────────────────

export const STATUS_LABEL: Record<BuildStatus, string> = {
  queued: "排队中",
  running: "运行中",
  success: "成功",
  failed: "失败",
  cancelled: "已取消",
};

export const STATUS_TONE: Record<BuildStatus, "ok" | "warn" | "bad" | "muted"> = {
  queued: "muted",
  running: "warn",
  success: "ok",
  failed: "bad",
  cancelled: "muted",
};

export const STEP_STATUS_LABEL: Record<StepStatus, string> = {
  pending: "等待",
  running: "运行中",
  success: "成功",
  failed: "失败",
  skipped: "跳过",
};

export const STEP_STATUS_TONE: Record<StepStatus, "done" | "active" | "wait"> = {
  pending: "wait",
  running: "active",
  success: "done",
  failed: "active",
  skipped: "wait",
};

export function formatTimestamp(iso: string): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  const diff = Date.now() - d.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "刚刚";
  if (mins < 60) return `${mins} 分钟前`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} 小时前`;
  return `${Math.floor(hours / 24)} 天前`;
}

export function formatDuration(ms: number): string {
  if (ms <= 0) return "—";
  if (ms < 1000) return `${ms} ms`;
  const secs = Math.floor(ms / 1000);
  if (secs < 60) return `${secs}s`;
  const mins = Math.floor(secs / 60);
  const remSecs = secs % 60;
  return `${mins}m ${remSecs}s`;
}

export function computeProgress(steps: BuildStep[]): number {
  if (steps.length === 0) return 0;
  const done = steps.filter((s) => s.status === "success" || s.status === "failed" || s.status === "skipped").length;
  return done / steps.length;
}

export function totalDuration(steps: BuildStep[]): number {
  return steps.reduce((acc, s) => acc + (s.durationMs ?? 0), 0);
}

export function filterLogs(
  logs: BuildLogEntry[],
  level: "all" | "info" | "warn" | "error",
  query: string,
): BuildLogEntry[] {
  const q = query.trim().toLowerCase();
  return logs.filter((l) => {
    if (level !== "all" && l.level !== level) return false;
    if (!q) return true;
    return l.message.toLowerCase().includes(q);
  });
}

export function overallStatusFromSteps(steps: BuildStep[]): BuildStatus {
  if (steps.length === 0) return "queued";
  if (steps.some((s) => s.status === "running")) return "running";
  if (steps.every((s) => s.status === "success" || s.status === "skipped")) return "success";
  if (steps.some((s) => s.status === "failed")) return "failed";
  return "queued";
}

export function validateConfig(config: BuildConfig): string | null {
  if (!config.target.trim()) return "构建目标不能为空";
  if (!config.branch.trim()) return "分支不能为空";
  if (!config.commitSha.trim()) return "Commit SHA 不能为空";
  if (config.retries < 0 || config.retries > 5) return "重试次数必须在 0-5 之间";
  return null;
}

export function configToApiPayload(config: BuildConfig) {
  return {
    target: config.target,
    branch: config.branch,
    commit_sha: config.commitSha,
    resource_class: config.resourceClass,
    env_vars: config.env.filter((e) => e.trim()),
    notifications: config.notifications.filter((n) => n.trim()),
    cache: config.cacheEnabled,
    max_retries: config.retries,
  };
}

// ── Mock data ──────────────────────────────────────────────────

const DEMO_STEPS: BuildStep[] = [
  {
    id: "step-1",
    name: "检出代码",
    status: "success",
    startedAt: new Date(Date.now() - 300000).toISOString(),
    durationMs: 4500,
    logLines: ["Cloning into 'aos-platform...", "HEAD is now at a3f4b21", "Checkout complete."],
  },
  {
    id: "step-2",
    name: "安装依赖",
    status: "success",
    startedAt: new Date(Date.now() - 295000).toISOString(),
    durationMs: 67000,
    logLines: ["Installing packages...", "Collecting fastapi==0.104", "Collecting pydantic==2.5", "Dependencies installed."],
  },
  {
    id: "step-3",
    name: "编译 TypeScript",
    status: "success",
    startedAt: new Date(Date.now() - 228000).toISOString(),
    durationMs: 34000,
    logLines: ["tsc --noEmit", "Compiling...", "0 errors found."],
  },
  {
    id: "step-4",
    name: "运行测试",
    status: "running",
    startedAt: new Date(Date.now() - 194000).toISOString(),
    logLines: ["Running pytest...", "test_health.py ......... OK", "test_pipelines.py ... RUNNING"],
  },
  {
    id: "step-5",
    name: "构建镜像",
    status: "pending",
    logLines: [],
  },
  {
    id: "step-6",
    name: "部署",
    status: "pending",
    logLines: [],
  },
];

const DEMO_LOGS: BuildLogEntry[] = [
  { timestamp: new Date(Date.now() - 300000).toISOString(), level: "info", message: "Build #847 started by worker-3" },
  { timestamp: new Date(Date.now() - 299000).toISOString(), level: "info", message: "Using resource class: large" },
  { timestamp: new Date(Date.now() - 295000).toISOString(), level: "info", message: "Step 1: Checking out code" },
  { timestamp: new Date(Date.now() - 290000).toISOString(), level: "info", message: "Step 2: Installing dependencies" },
  { timestamp: new Date(Date.now() - 228000).toISOString(), level: "info", message: "Step 3: Compiling TypeScript" },
  { timestamp: new Date(Date.now() - 194000).toISOString(), level: "info", message: "Step 4: Running tests" },
  { timestamp: new Date(Date.now() - 60000).toISOString(), level: "warn", message: "test_pipeline_edge_case is slow (>30s)" },
  { timestamp: new Date(Date.now() - 30000).toISOString(), level: "error", message: "Flaky test detected: test_sync_retry" },
  { timestamp: new Date(Date.now() - 10000).toISOString(), level: "info", message: "Retrying flaky test..." },
];

const DEMO_CONFIG: BuildConfig = {
  target: "production",
  branch: "main",
  commitSha: "a3f4b21",
  resourceClass: "large",
  env: ["NODE_ENV=production", "SKIP_MIGRATIONS=false"],
  notifications: ["slack:#eng-data", "email:devops@company.com"],
  cacheEnabled: true,
  retries: 2,
};

const DEMO_BUILD: BuildJob = {
  id: "build-847",
  name: "Build #847",
  status: "running",
  triggeredBy: "worker-3",
  startedAt: new Date(Date.now() - 300000).toISOString(),
  config: DEMO_CONFIG,
  steps: DEMO_STEPS,
  logs: DEMO_LOGS,
};

// ── Page Component ─────────────────────────────────────────────

export function BuildModalPage() {
  const { data, err, loading } = useJsonGet<BuildJob>("/v1/builds/current");
  const build = data ?? DEMO_BUILD;

  const [tab, setTab] = useState("steps");
  const [logLevel, setLogLevel] = useState<"all" | "info" | "warn" | "error">("all");
  const [logQuery, setLogQuery] = useState("");
  const [config, setConfig] = useState<BuildConfig>(build.config);
  const [msg, setMsg] = useState("");

  const filteredLogs = useMemo(
    () => filterLogs(build.logs, logLevel, logQuery),
    [build.logs, logLevel, logQuery],
  );

  const progress = useMemo(() => computeProgress(build.steps), [build.steps]);
  const totalMs = useMemo(() => totalDuration(build.steps), [build.steps]);

  const configError = useMemo(() => validateConfig(config), [config]);

  async function handleStart() {
    setMsg("");
    if (configError) {
      setMsg(configError);
      return;
    }
    try {
      await apiPost("/v1/builds", configToApiPayload(config));
      setMsg("构建已启动");
    } catch (e) {
      setMsg(String((e as Error).message || e));
    }
  }

  async function handleCancel() {
    setMsg("");
    try {
      await apiPost(`/v1/builds/${build.id}/cancel`, {});
      setMsg("构建已取消");
    } catch (e) {
      setMsg(String((e as Error).message || e));
    }
  }

  async function handleRetry() {
    setMsg("");
    try {
      await apiPost(`/v1/builds/${build.id}/retry`, {});
      setMsg("构建已重试");
    } catch (e) {
      setMsg(String((e as Error).message || e));
    }
  }

  return (
    <S2Chrome title={`构建 · ${build.name}`} lede={`状态: ${STATUS_LABEL[build.status]} · 触发者: ${build.triggeredBy}`}>
      <BpToolbar>
        <button type="button" className="btn-primary" onClick={() => void handleStart()}>
          开始构建
        </button>
        <button type="button" className="btn-nav" onClick={() => void handleCancel()}>
          取消
        </button>
        <button type="button" className="btn-nav" onClick={() => void handleRetry()}>
          重试
        </button>
        <Link to="/data/builds" className="btn-nav">构建列表</Link>
      </BpToolbar>

      {loading && <p className="muted">加载中…</p>}
      {err && <p className="error">{err}</p>}
      {msg && <p className="aos-text">{msg}</p>}

      <BpMetricGrid
        items={[
          { label: "状态", value: STATUS_LABEL[build.status], tone: STATUS_TONE[build.status] },
          { label: "进度", value: `${Math.round(progress * 100)}%`, tone: progress === 1 ? "ok" : "warn" },
          { label: "总耗时", value: formatDuration(totalMs), tone: "muted" },
          { label: "步骤数", value: build.steps.length, tone: "muted" },
        ]}
      />

      <BpTabs
        tabs={[
          { id: "steps", label: "步骤" },
          { id: "config", label: "配置" },
          { id: "logs", label: "日志" },
        ]}
        active={tab}
        onChange={setTab}
      />

      {tab === "steps" && (
        <div>
          <div style={{ marginBottom: "0.75rem" }}>
            <div className="bp-progress" style={{ height: 8 }}>
              <div
                className="bp-progress-bar"
                style={{ width: `${Math.round(progress * 100)}%` }}
              />
            </div>
          </div>
          <BpStagePipeline
            stages={build.steps.map((s) => ({
              step: s.id,
              title: s.name,
              status: STEP_STATUS_LABEL[s.status],
              tone: STEP_STATUS_TONE[s.status],
              progress: s.status === "running" ? 0.5 : undefined,
            }))}
          />
          <BpTable
            columns={["步骤", "状态", "耗时", "日志行数"]}
            rows={build.steps.map((s) => [
              <span className="mono">{s.name}</span>,
              <span className={`bp-discover-badge bp-discover-badge-${
                s.status === "success" ? "ok" : s.status === "running" ? "warn" : s.status === "failed" ? "bad" : "muted"
              }`}>
                {STEP_STATUS_LABEL[s.status]}
              </span>,
              s.durationMs != null ? formatDuration(s.durationMs) : "—",
              s.logLines.length,
            ])}
          />
        </div>
      )}

      {tab === "config" && (
        <div className="bp-object-panel">
          <h3 className="aos-text" style={{ fontSize: "0.85rem", marginBottom: "0.5rem" }}>构建配置</h3>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem" }}>
            <label>
              目标环境
              <input
                type="text"
                value={config.target}
                onChange={(e) => setConfig({ ...config, target: e.target.value })}
                style={{ width: "100%" }}
              />
            </label>
            <label>
              分支
              <input
                type="text"
                value={config.branch}
                onChange={(e) => setConfig({ ...config, branch: e.target.value })}
                style={{ width: "100%" }}
              />
            </label>
            <label>
              Commit SHA
              <input
                type="text"
                value={config.commitSha}
                onChange={(e) => setConfig({ ...config, commitSha: e.target.value })}
                style={{ width: "100%" }}
              />
            </label>
            <label>
              资源规格
              <select
                value={config.resourceClass}
                onChange={(e) => setConfig({ ...config, resourceClass: e.target.value as BuildConfig["resourceClass"] })}
                style={{ width: "100%" }}
              >
                <option value="small">Small (2 CPU / 4GB)</option>
                <option value="medium">Medium (4 CPU / 8GB)</option>
                <option value="large">Large (8 CPU / 16GB)</option>
              </select>
            </label>
            <label>
              重试次数
              <input
                type="number"
                min={0}
                max={5}
                value={config.retries}
                onChange={(e) => setConfig({ ...config, retries: Number(e.target.value) })}
                style={{ width: "100%" }}
              />
            </label>
            <label>
              启用缓存
              <input
                type="checkbox"
                checked={config.cacheEnabled}
                onChange={(e) => setConfig({ ...config, cacheEnabled: e.target.checked })}
              />
            </label>
          </div>
          <div style={{ marginTop: "0.5rem" }}>
            <label>
              环境变量（每行一个）
              <textarea
                value={config.env.join("\n")}
                onChange={(e) => setConfig({ ...config, env: e.target.value.split("\n") })}
                rows={3}
                style={{ width: "100%", fontFamily: "monospace" }}
              />
            </label>
          </div>
          {configError && (
            <BpBanner tone="warn">{configError}</BpBanner>
          )}
        </div>
      )}

      {tab === "logs" && (
        <div>
          <BpToolbar>
            <select value={logLevel} onChange={(e) => setLogLevel(e.target.value as typeof logLevel)}>
              <option value="all">全部级别</option>
              <option value="info">Info</option>
              <option value="warn">Warn</option>
              <option value="error">Error</option>
            </select>
            <input
              type="search"
              placeholder="搜索日志…"
              value={logQuery}
              onChange={(e) => setLogQuery(e.target.value)}
              style={{ minWidth: 200 }}
            />
            <span className="muted" style={{ fontSize: "0.75rem" }}>
              {filteredLogs.length} / {build.logs.length} 条
            </span>
          </BpToolbar>
          <div className="bp-object-panel" style={{ maxHeight: 400, overflowY: "auto", fontFamily: "monospace", fontSize: "0.75rem" }}>
            {filteredLogs.map((l, i) => (
              <div
                key={i}
                style={{
                  padding: "2px 0",
                  color:
                    l.level === "error"
                      ? "var(--p-bad, #dc2626)"
                      : l.level === "warn"
                        ? "var(--p-warn, #d97706)"
                        : "var(--p-text, #1f2937)",
                }}
              >
                <span className="muted">[{new Date(l.timestamp).toLocaleTimeString()}]</span>{" "}
                <strong>[{l.level.toUpperCase()}]</strong> {l.message}
              </div>
            ))}
          </div>
        </div>
      )}

      <BpBanner tone="info">
        对齐 <code>pipeline.html</code> 构建弹窗 · 步骤/配置/日志三 Tab ·{" "}
        <Link to="/data/builds">构建列表</Link>
      </BpBanner>
    </S2Chrome>
  );
}
