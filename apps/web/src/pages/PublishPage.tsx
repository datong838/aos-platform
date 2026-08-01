import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { PageChrome } from "../components/PageChrome";
import { apiGet, apiPost } from "../api/client";

export type PublishEnv = {
  id: string;
  label: string;
  step: number;
};

/** 开发 → 测试 → 预发布 → 生产 · 对齐 checklist §7.5 */
export const PUBLISH_ENVS: PublishEnv[] = [
  { id: "dev", label: "开发", step: 0 },
  { id: "test", label: "测试", step: 1 },
  { id: "staging", label: "预发布", step: 2 },
  { id: "prod", label: "生产", step: 3 },
];

export type DeploymentItem = {
  id?: string;
  environment?: string;
  version?: string;
  status?: string;
  createdAt?: string;
};

export type ModuleListItem = {
  id: string;
  name?: string;
  status?: string;
};

type PublishApiResponse = ModuleListItem & {
  publish?: { status?: string; channel?: string };
  idempotentReplay?: boolean;
};

type DeployApiResponse = {
  ok?: boolean;
  item?: DeploymentItem;
};

type PhaseState = "idle" | "running" | "ok" | "err" | "validation_err";

export function envStepIndex(envId: string): number {
  const found = PUBLISH_ENVS.find((e) => e.id === envId);
  return found ? found.step : 0;
}

export function stepState(
  stepIndex: number,
  currentEnvId: string,
): "done" | "current" | "pending" {
  const cur = envStepIndex(currentEnvId);
  if (stepIndex < cur) return "done";
  if (stepIndex === cur) return "current";
  return "pending";
}

export function pickLatestByEnv(
  items: DeploymentItem[],
): Record<string, DeploymentItem> {
  const map: Record<string, DeploymentItem> = {};
  for (const it of items) {
    const env = String(it.environment || "");
    if (!env) continue;
    if (!map[env]) map[env] = it;
  }
  return map;
}

export function formatPublishResult(opts: {
  ok: boolean;
  phase?: "publish" | "idempotency" | "deploy";
  moduleId?: string;
  env?: string;
  status?: string;
  idempotent?: boolean;
  error?: string;
}): string {
  if (!opts.ok) {
    if (opts.phase === "deploy") {
      return `发布已接受，但部署失败${opts.error ? ` · ${opts.error}` : ""}`;
    }
    if (opts.phase === "idempotency") {
      return `发布已接受，但幂等校验失败${opts.error ? ` · ${opts.error}` : ""}`;
    }
    return `发布失败${opts.error ? ` · ${opts.error}` : ""}`;
  }
  const parts = [
    `发布与部署成功`,
    opts.moduleId ? `id=${opts.moduleId}` : null,
    opts.env ? `环境 ${opts.env}` : null,
    opts.status || "ACCEPTED",
    opts.idempotent ? "幂等重放" : null,
  ].filter(Boolean);
  return parts.join(" · ");
}

export function assertPublishAccepted(payload: PublishApiResponse, expectedModuleId: string): void {
  if (payload.id !== expectedModuleId) {
    throw new Error(`发布响应 Module 不匹配：期望 ${expectedModuleId}，实际 ${payload.id || "—"}`);
  }
  if (payload.status !== "published" || payload.publish?.status !== "ACCEPTED") {
    throw new Error("发布接口未返回 ACCEPTED 状态");
  }
}

export function assertIdempotentReplay(payload: PublishApiResponse): void {
  if (payload.idempotentReplay !== true) {
    throw new Error("幂等重放校验失败：第二次请求未返回 idempotentReplay=true");
  }
}

export function assertDeploySucceeded(
  payload: DeployApiResponse,
  expectedEnvironment: string,
): DeploymentItem {
  if (payload.ok !== true || !payload.item?.id || payload.item.status !== "success") {
    throw new Error("部署接口未返回 success 记录");
  }
  if (payload.item.environment !== expectedEnvironment) {
    throw new Error(
      `部署响应环境不匹配：期望 ${expectedEnvironment}，实际 ${payload.item.environment || "—"}`,
    );
  }
  return payload.item;
}

export function PublishPage() {
  const [searchParams] = useSearchParams();
  const requestedModuleId = searchParams.get("moduleId") || "";
  const [modules, setModules] = useState<ModuleListItem[]>([]);
  const [moduleId, setModuleId] = useState("");
  const [env, setEnv] = useState("staging");
  const [deployments, setDeployments] = useState<DeploymentItem[]>([]);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [deploymentLoadErr, setDeploymentLoadErr] = useState<string | null>(null);
  const [msg, setMsg] = useState("");
  const [pubState, setPubState] = useState<"idle" | "ok" | "err">("idle");
  const [publishPhase, setPublishPhase] = useState<PhaseState>("idle");
  const [deployPhase, setDeployPhase] = useState<PhaseState>("idle");
  const [lastPub, setLastPub] = useState<{
    id?: string;
    status?: string;
    channel?: string;
    idempotent?: boolean;
    environment?: string;
    deploymentId?: string;
    deploymentStatus?: string;
  } | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    apiGet<{ items?: ModuleListItem[] }>("/v1/modules")
      .then((r) => {
        const items = (r.items || []).filter((m) => m.id);
        setModules(items);
        if (items.length > 0) {
          setModuleId((prev) => {
            if (prev) return prev;
            if (requestedModuleId && items.some((item) => item.id === requestedModuleId)) {
              return requestedModuleId;
            }
            return items[0].id;
          });
        }
      })
      .catch((e) => setLoadErr(String((e as Error).message || e)));
  }, [requestedModuleId]);

  const loadDeploymentHistory = useCallback(async (mid: string) => {
    try {
      const result = await apiGet<{ items?: DeploymentItem[] }>(
        `/v1/modules/${encodeURIComponent(mid)}/deployments`,
      );
      setDeployments(result.items || []);
      setDeploymentLoadErr(null);
    } catch (e) {
      setDeployments([]);
      setDeploymentLoadErr(`部署历史加载失败：${String((e as Error).message || e)}`);
      throw e;
    }
  }, []);

  useEffect(() => {
    if (!moduleId) {
      setDeployments([]);
      setDeploymentLoadErr(null);
      return;
    }
    void loadDeploymentHistory(moduleId).catch(() => {});
  }, [loadDeploymentHistory, moduleId]);

  const byEnv = pickLatestByEnv(deployments);
  const selectedMod = modules.find((m) => m.id === moduleId);

  async function ensureModuleId(): Promise<string> {
    if (moduleId) return moduleId;
    const created = await apiPost<ModuleListItem>("/v1/modules", {
      name: `发布 Module · ${env}`,
      entryPath: "/workshop/inbox",
      objectType: "WorkOrder",
    });
    const mid = created.id;
    setModules((prev) => [...prev, created]);
    setModuleId(mid);
    return mid;
  }

  async function onPublish() {
    if (busy) return;
    setBusy(true);
    setPubState("idle");
    setPublishPhase("running");
    setDeployPhase("idle");
    setMsg("");
    const key = `publish-${Date.now()}`;
    const headers = { "Idempotency-Key": key };
    let publishAccepted = false;
    let idempotencyVerified = false;
    try {
      const mid = await ensureModuleId();
      const path = `/v1/modules/${encodeURIComponent(mid)}/publish`;
      const pub1 = await apiPost<PublishApiResponse>(path, {}, headers);
      assertPublishAccepted(pub1, mid);
      publishAccepted = true;
      const pub2 = await apiPost<PublishApiResponse>(path, {}, headers);
      assertPublishAccepted(pub2, mid);
      assertIdempotentReplay(pub2);
      idempotencyVerified = true;
      setPublishPhase("ok");
      setDeployPhase("running");

      const deployResponse = await apiPost<DeployApiResponse>(
        `/v1/modules/${encodeURIComponent(mid)}/deploy`,
        {
          environment: env,
          version: "1.0.0",
          configSnapshot: { channel: env, via: "workshop-publish" },
        },
      );
      const deployment = assertDeploySucceeded(deployResponse, env);
      setDeployPhase("ok");
      await loadDeploymentHistory(mid).catch(() => {});

      const status = pub1.publish?.status || "ACCEPTED";
      const idempotent = Boolean(pub2.idempotentReplay);
      setLastPub({
        id: mid,
        status,
        channel: pub1.publish?.channel || env,
        idempotent,
        environment: env,
        deploymentId: deployment.id,
        deploymentStatus: deployment.status,
      });
      setPubState("ok");
      setMsg(
        formatPublishResult({
          ok: true,
          moduleId: mid,
          env,
          status,
          idempotent,
        }),
      );
    } catch (e) {
      if (idempotencyVerified) {
        setDeployPhase("err");
      } else if (publishAccepted) {
        setPublishPhase("validation_err");
      } else {
        setPublishPhase("err");
      }
      setPubState("err");
      setLastPub(null);
      setMsg(formatPublishResult({
        ok: false,
        phase: idempotencyVerified ? "deploy" : publishAccepted ? "idempotency" : "publish",
        error: String((e as Error).message || e),
      }));
    } finally {
      setBusy(false);
    }
  }

  return (
    <PageChrome title="发布入口" lede="订单管理 · 发布入口">
      <div className="w2-b4-publish" style={{ maxWidth: 640, margin: "0 auto" }}>
        <div
          style={{
            background: "#fff",
            borderRadius: 2,
            border: "1px solid var(--aos-border, #E5E7EB)",
            padding: 24,
          }}
        >
          <div style={{ fontSize: 16, fontWeight: 500, color: "#111827", marginBottom: 4 }}>
            发布 · {selectedMod?.name || "选择 Module"}
          </div>
          <p style={{ fontSize: 12, color: "#6B7280", margin: "0 0 16px 0", lineHeight: 1.5 }}>
            步骤与 <code style={{ fontSize: 11 }}>POST /v1/modules/:id/publish</code> 对齐；部署记录写{" "}
            <code style={{ fontSize: 11 }}>/deploy</code>。
          </p>

          {/* 模块选择 */}
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 12, color: "#6B7280", marginBottom: 6 }}>目标模块</div>
            <select
              aria-label="publish-module"
              value={moduleId}
              onChange={(e) => setModuleId(e.target.value)}
              style={{
                width: "100%",
                padding: "8px 10px",
                fontSize: 13,
                borderRadius: 2,
                border: "1px solid #E5E7EB",
                background: "#fff",
              }}
            >
              {modules.length === 0 && <option value="">（无模块 · 发布时自动创建）</option>}
              {modules.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name || m.id} {m.status ? `· ${m.status}` : ""}
                </option>
              ))}
            </select>
            {loadErr && (
              <p style={{ fontSize: 11, color: "#DC2626", margin: "6px 0 0" }}>{loadErr}</p>
            )}
          </div>

          {/* 步骤条 */}
          <div className="w2-b4-steps" style={{ display: "flex", gap: 0, marginBottom: 20 }} role="list">
            {PUBLISH_ENVS.map((e, i) => {
              const st = stepState(i, env);
              const color =
                st === "done" ? "#059669" : st === "current" ? "#2563EB" : "#9CA3AF";
              return (
                <div
                  key={e.id}
                  role="listitem"
                  style={{ flex: 1, textAlign: "center", position: "relative" }}
                >
                  {i > 0 && (
                    <div
                      style={{
                        position: "absolute",
                        left: "-50%",
                        right: "50%",
                        top: 11,
                        height: 2,
                        background: envStepIndex(env) >= i ? "#059669" : "#E5E7EB",
                        zIndex: 0,
                      }}
                    />
                  )}
                  <div
                    style={{
                      width: 24,
                      height: 24,
                      borderRadius: "50%",
                      margin: "0 auto 6px",
                      background: st === "pending" ? "#F3F4F6" : color,
                      color: st === "pending" ? "#6B7280" : "#fff",
                      fontSize: 11,
                      fontWeight: 600,
                      lineHeight: "24px",
                      position: "relative",
                      zIndex: 1,
                    }}
                  >
                    {st === "done" ? "✓" : i + 1}
                  </div>
                  <div style={{ fontSize: 11, color, fontWeight: st === "current" ? 600 : 400 }}>
                    {e.label}
                  </div>
                </div>
              );
            })}
          </div>

          {/* 环境卡 */}
          <div style={{ fontSize: 12, color: "#6B7280", marginBottom: 8 }}>目标环境</div>
          <div
            className="w2-b4-env-grid"
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: 8,
              marginBottom: 16,
            }}
          >
            {PUBLISH_ENVS.map((e) => {
              const dep = byEnv[e.id];
              const selected = env === e.id;
              return (
                <button
                  key={e.id}
                  type="button"
                  className={`w2-b4-env-card${selected ? " is-selected" : ""}`}
                  onClick={() => setEnv(e.id)}
                  aria-pressed={selected}
                  style={{
                    textAlign: "left",
                    padding: "12px 14px",
                    borderRadius: 2,
                    border: selected ? "1px solid #2563EB" : "1px solid #E5E7EB",
                    background: selected ? "#EFF6FF" : "#fff",
                    cursor: "pointer",
                  }}
                >
                  <div style={{ fontSize: 13, fontWeight: 500, color: "#111827" }}>{e.label}</div>
                  <div style={{ fontSize: 11, color: "#6B7280", marginTop: 4 }}>
                    {dep
                      ? `${dep.status || "success"} · ${dep.version || "—"}`
                      : "尚未部署"}
                  </div>
                </button>
              );
            })}
          </div>
          {deploymentLoadErr && (
            <p
              role="alert"
              data-testid="deployment-history-error"
              style={{ fontSize: 11, color: "#DC2626", margin: "-8px 0 16px" }}
            >
              {deploymentLoadErr}
            </p>
          )}

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: 8,
              paddingTop: 4,
              marginBottom: 16,
            }}
          >
            <Link
              to="/apollo/release"
              style={{
                padding: "10px 12px",
                borderRadius: 2,
                background: "#ECFDF5",
                border: "1px solid #86EFAC",
                fontSize: 12,
                color: "#047857",
                textAlign: "center",
                textDecoration: "none",
              }}
            >
              打开 Release 通道 →
            </Link>
            <Link
              to="/workshop/canvas"
              style={{
                padding: "10px 12px",
                borderRadius: 2,
                border: "1px solid #E5E7EB",
                fontSize: 12,
                color: "#374151",
                textAlign: "center",
                textDecoration: "none",
              }}
            >
              返回画布
            </Link>
          </div>

          <button
            type="button"
            onClick={() => void onPublish()}
            disabled={busy}
            style={{
              width: "100%",
              padding: "10px 16px",
              fontSize: 13,
              fontWeight: 500,
              border: "none",
              borderRadius: 2,
              background: busy ? "#E5E7EB" : "var(--aos-accent)",
              color: busy ? "#9CA3AF" : "#fff",
              cursor: busy ? "not-allowed" : "pointer",
              marginBottom: 12,
            }}
          >
            {busy ? "提交中…" : `发布到${PUBLISH_ENVS.find((e) => e.id === env)?.label || env}`}
          </button>

          {(publishPhase !== "idle" || deployPhase !== "idle") && (
            <div
              data-testid="publish-phase-status"
              style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 12 }}
            >
              <div style={{ padding: "8px 10px", border: "1px solid #E5E7EB", borderRadius: 2, fontSize: 11 }}>
                发布：{publishPhase === "running" ? "处理中" : publishPhase === "ok" ? "已接受" : publishPhase === "validation_err" ? "已接受·幂等失败" : publishPhase === "err" ? "失败" : "未开始"}
              </div>
              <div style={{ padding: "8px 10px", border: "1px solid #E5E7EB", borderRadius: 2, fontSize: 11 }}>
                部署：{deployPhase === "running" ? "处理中" : deployPhase === "ok" ? "成功" : deployPhase === "err" ? "失败" : "未开始"}
              </div>
            </div>
          )}

          {pubState === "ok" && (
            <div
              className="w2-b4-banner is-ok"
              style={{
                fontSize: 12,
                color: "#059669",
                border: "1px solid #A7F3D0",
                borderRadius: 2,
                padding: "10px 12px",
                background: "#ECFDF5",
                marginBottom: 12,
                lineHeight: 1.5,
              }}
            >
              {msg}
            </div>
          )}
          {pubState === "err" && (
            <div
              className="w2-b4-banner is-err"
              style={{
                fontSize: 12,
                color: "#DC2626",
                border: "1px solid #FECACA",
                borderRadius: 2,
                padding: "10px 12px",
                background: "#FEF2F2",
                marginBottom: 12,
                lineHeight: 1.5,
              }}
            >
              {msg}
            </div>
          )}
          {pubState === "idle" && (
            <p
              style={{
                fontSize: 10,
                color: "#059669",
                border: "1px solid #A7F3D0",
                borderRadius: 2,
                padding: "10px 12px",
                background: "#ECFDF5",
                margin: "0 0 12px",
                lineHeight: 1.5,
              }}
            >
              Spoke 出站轮询拉 Plan · Lite Spoke 同契约 · 见 Apollo 交付组
            </p>
          )}

          {lastPub && (
            <div
              style={{
                marginTop: 4,
                padding: 12,
                borderRadius: 2,
                background: "var(--aos-surface-hover, #F9FAFB)",
                border: "1px solid var(--aos-border, #E5E7EB)",
              }}
            >
              <div style={{ fontSize: 12, fontWeight: 500, color: "#111827", marginBottom: 8 }}>
                上次发布结果
              </div>
              <div style={{ fontSize: 11, color: "#6B7280", lineHeight: 1.8 }}>
                <div>
                  Module ID:{" "}
                  <span style={{ fontFamily: "monospace", color: "#374151" }}>
                    {lastPub.id || "—"}
                  </span>
                </div>
                <div>
                  环境: <span style={{ color: "#374151" }}>{lastPub.environment || "—"}</span>
                </div>
                <div>
                  API channel:{" "}
                  <span style={{ color: "#374151" }}>{lastPub.channel || "—"}</span>
                </div>
                <div>
                  状态:{" "}
                  <span style={{ color: "#059669", fontWeight: 500 }}>
                    {lastPub.status || "—"}
                  </span>
                </div>
                <div>
                  幂等:{" "}
                  <span style={{ color: lastPub.idempotent ? "#059669" : "#D97706" }}>
                    {lastPub.idempotent ? "是（重放成功）" : "否"}
                  </span>
                </div>
                <div>
                  部署记录:{" "}
                  <span style={{ color: "#059669" }}>
                    {lastPub.deploymentStatus || "—"} · {lastPub.deploymentId || "—"}
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </PageChrome>
  );
}
