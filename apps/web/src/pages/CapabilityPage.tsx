import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiGet, apiPost, apiPut } from "../api/client";
import { PageChrome } from "../components/PageChrome";

export type CapItem = {
  id: string;
  kind?: string;
  endpoint?: string;
  name?: string;
  category?: string;
  description?: string;
  enabled?: boolean;
  config?: Record<string, unknown>;
};

type CapabilityCard = {
  id: string;
  title: string;
  kindLabel: string;
  desc: string;
  status: "ready" | "session" | "stopped";
};

const CAPABILITY_CARDS: CapabilityCard[] = [
  { id: "video-job", title: "短视频生成", kindLabel: "C1 Job · GPU · → MediaSet", desc: "重能力 · 产物写入 MediaSet", status: "ready" },
  { id: "live-script", title: "直播稿引擎", kindLabel: "C0 sync / 可升 C1 · → LiveScript", desc: "同步轻能力 · 可进 Function", status: "ready" },
  { id: "avatar-commerce", title: "电商可交互数字人", kindLabel: "C2 Session · AV 外置 · AvatarSession", desc: "会话型 · 平台不进沙箱", status: "session" },
  { id: "avatar-edu", title: "教育可交互数字人", kindLabel: "C2 Session · 课纲 Wiki · CourseSession", desc: "会话型 · 课纲关联 Wiki", status: "stopped" },
];

const STATUS_META: Record<CapabilityCard["status"], { label: string; border: string; color: string }> = {
  ready: { label: "就绪", border: "var(--aos-green-border)", color: "var(--aos-green-700)" },
  session: { label: "会话中", border: "var(--aos-blue-border)", color: "var(--aos-blue-600)" },
  stopped: { label: "停用", border: "var(--aos-border)", color: "var(--aos-text-secondary)" },
};

export type CfgType = "job" | "script" | "session" | "http";

const CFG_TYPE_META: { id: CfgType; title: string; desc: string; defaultCapId: string }[] = [
  { id: "job", title: "Media Job", desc: "C1 · submit / status / artifact", defaultCapId: "video-job" },
  { id: "script", title: "Script Engine", desc: "C0 sync · 或短 Job", defaultCapId: "live-script" },
  { id: "session", title: "Avatar Session", desc: "C2 · open / push / close", defaultCapId: "avatar-commerce" },
  { id: "http", title: "HTTP Adapter", desc: "自定义重包契约", defaultCapId: "http-adapter" },
];

export type CapConfigForm = {
  endpoint: string;
  concurrency: string;
  secretRef: string;
  webhook: string;
  mode: string;
  timeoutSec: string;
  outputObjectType: string;
  gateway: string;
  sessionObject: string;
  avExternal: boolean;
  draftGate: boolean;
  httpKind: string;
  baseUrl: string;
  manifest: string;
};

const CFG_STORAGE_PREFIX = "aos.cap.cfg.";

export function pathLabel(demo: boolean): string {
  return demo ? "演示路径" : "真 API";
}

export function defaultConfigFor(cfgType: CfgType): CapConfigForm {
  switch (cfgType) {
    case "job":
      return {
        endpoint: "https://cap.internal/video/v1",
        concurrency: "4",
        secretRef: "vault://aip/capabilities/short-video#token",
        webhook: "https://aos-api/v1/aip/capabilities/cb/video",
        mode: "sync",
        timeoutSec: "15",
        outputObjectType: "LiveScript",
        gateway: "wss://avatar.internal/session",
        sessionObject: "AvatarSession",
        avExternal: true,
        draftGate: true,
        httpKind: "job",
        baseUrl: "https://pkg.example/api",
        manifest: "capability://org/custom-pkg@1.0",
      };
    case "script":
      return {
        ...defaultConfigFor("job"),
        endpoint: "https://cap.internal/script/v1",
        mode: "sync",
        timeoutSec: "15",
        outputObjectType: "LiveScript",
      };
    case "session":
      return {
        ...defaultConfigFor("job"),
        gateway: "wss://avatar.internal/session",
        sessionObject: "AvatarSession",
        endpoint: "wss://avatar.internal/session",
        avExternal: true,
        draftGate: true,
      };
    case "http":
      return {
        ...defaultConfigFor("job"),
        httpKind: "job",
        baseUrl: "https://pkg.example/api",
        manifest: "capability://org/custom-pkg@1.0",
        endpoint: "https://pkg.example/api",
      };
  }
}

export function cfgTypeFromCard(cap: CapabilityCard): CfgType {
  if (cap.kindLabel.includes("Job")) return "job";
  if (cap.kindLabel.includes("Session")) return "session";
  return "script";
}

export function mergeLiveItem(form: CapConfigForm, item?: CapItem | null): CapConfigForm {
  if (!item) return form;
  const cfg = (item.config || {}) as Record<string, unknown>;
  const str = (k: string, fallback: string) => {
    const v = cfg[k];
    return v === undefined || v === null ? fallback : String(v);
  };
  const bool = (k: string, fallback: boolean) => {
    const v = cfg[k];
    return typeof v === "boolean" ? v : fallback;
  };
  return {
    ...form,
    endpoint: str("endpoint", item.endpoint || form.endpoint),
    concurrency: str("concurrency", form.concurrency),
    secretRef: str("secretRef", form.secretRef),
    webhook: str("webhook", form.webhook),
    mode: str("mode", form.mode),
    timeoutSec: str("timeoutSec", form.timeoutSec),
    outputObjectType: str("outputObjectType", form.outputObjectType),
    gateway: str("gateway", form.gateway),
    sessionObject: str("sessionObject", form.sessionObject),
    avExternal: bool("avExternal", form.avExternal),
    draftGate: bool("draftGate", form.draftGate),
    httpKind: str("kind", form.httpKind) === "script" || str("kind", form.httpKind) === "session" || str("kind", form.httpKind) === "sync" || str("kind", form.httpKind) === "job"
      ? str("kind", form.httpKind)
      : form.httpKind,
    baseUrl: str("baseUrl", form.baseUrl),
    manifest: str("manifest", form.manifest),
  };
}

export function formToConfig(cfgType: CfgType, form: CapConfigForm): Record<string, unknown> {
  switch (cfgType) {
    case "job":
      return {
        kind: "job",
        endpoint: form.endpoint,
        concurrency: Number(form.concurrency) || 0,
        secretRef: form.secretRef,
        webhook: form.webhook,
      };
    case "script":
      return {
        kind: "script",
        mode: form.mode,
        timeoutSec: Number(form.timeoutSec) || 0,
        outputObjectType: form.outputObjectType,
        endpoint: form.endpoint || undefined,
      };
    case "session":
      return {
        kind: "session",
        gateway: form.gateway,
        sessionObject: form.sessionObject,
        avExternal: form.avExternal,
        draftGate: form.draftGate,
        endpoint: form.gateway,
      };
    case "http":
      return {
        kind: form.httpKind || "job",
        baseUrl: form.baseUrl,
        manifest: form.manifest,
        endpoint: form.baseUrl,
      };
  }
}

export function resolveEndpoint(cfgType: CfgType, form: CapConfigForm): string {
  if (cfgType === "session") return form.gateway;
  if (cfgType === "http") return form.baseUrl;
  return form.endpoint;
}

export function simulateConnectivity(capId: string, endpoint: string): {
  ok: boolean;
  status: string;
  latencyMs: number;
  endpoint: string;
  capabilityId: string;
  message: string;
} {
  const ok = Boolean(endpoint);
  return {
    ok,
    status: ok ? "healthy" : "unhealthy",
    latencyMs: 18,
    endpoint: endpoint || `mock://local/${capId}`,
    capabilityId: capId,
    message: ok ? "connectivity ok (local)" : "missing endpoint",
  };
}

export function formatSaveMsg(demo: boolean, capId: string, detail?: string): string {
  if (demo) {
    return `已本地保存 ${capId} · 演示路径${detail ? `（${detail}）` : ""}`;
  }
  return `已保存并启用 ${capId}`;
}

export function formatTestMsg(demo: boolean, ok: boolean, latencyMs?: number): string {
  const base = ok ? "连通正常" : "连通失败";
  const lat = latencyMs != null ? ` · ${latencyMs}ms` : "";
  return demo ? `${base}${lat} · 演示路径` : `${base}${lat}`;
}

export function loadLocalConfig(capId: string): CapConfigForm | null {
  try {
    const raw = localStorage.getItem(CFG_STORAGE_PREFIX + capId);
    if (!raw) return null;
    return JSON.parse(raw) as CapConfigForm;
  } catch {
    return null;
  }
}

export function saveLocalConfig(capId: string, form: CapConfigForm): void {
  localStorage.setItem(CFG_STORAGE_PREFIX + capId, JSON.stringify(form));
}

export function normalizeListItems(payload: unknown): CapItem[] {
  if (!payload || typeof payload !== "object") return [];
  const items = (payload as { items?: unknown }).items;
  if (!Array.isArray(items)) return [];
  return items
    .filter((x): x is Record<string, unknown> => !!x && typeof x === "object" && typeof (x as CapItem).id === "string")
    .map((x) => ({
      id: String(x.id),
      kind: x.kind != null ? String(x.kind) : undefined,
      endpoint: x.endpoint != null ? String(x.endpoint) : undefined,
      name: x.name != null ? String(x.name) : undefined,
      category: x.category != null ? String(x.category) : undefined,
      description: x.description != null ? String(x.description) : undefined,
      enabled: typeof x.enabled === "boolean" ? x.enabled : undefined,
      config: x.config && typeof x.config === "object" ? (x.config as Record<string, unknown>) : undefined,
    }));
}

export function CapabilityPage() {
  const [items, setItems] = useState<CapItem[]>([]);
  const [listSource, setListSource] = useState<"live" | "demo">("demo");
  const [mediaRid, setMediaRid] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState("");
  const [cfgType, setCfgType] = useState<CfgType | null>(null);
  const [editingCapId, setEditingCapId] = useState<string | null>(null);
  const [form, setForm] = useState<CapConfigForm>(() => defaultConfigFor("job"));
  const [busy, setBusy] = useState(false);

  async function reloadCaps() {
    try {
      const r = await apiGet<{ items: CapItem[] }>("/v1/aip/capabilities");
      setItems(normalizeListItems(r));
      setListSource("live");
      setErr(null);
    } catch (e) {
      setListSource("demo");
      setErr(`列表不可用 · 演示路径（${String((e as Error).message || e)}）`);
    }
  }

  useEffect(() => {
    void reloadCaps();
  }, []);

  const registered = useMemo(() => new Set(items.map((c) => c.id)), [items]);
  const itemsById = useMemo(() => {
    const m = new Map<string, CapItem>();
    for (const it of items) m.set(it.id, it);
    return m;
  }, [items]);

  function openConfig(nextType: CfgType, capId: string) {
    setCfgType(nextType);
    setEditingCapId(capId);
    const base = defaultConfigFor(nextType);
    const local = loadLocalConfig(capId);
    const merged = mergeLiveItem(local || base, itemsById.get(capId));
    setForm(merged);
  }

  function patchForm<K extends keyof CapConfigForm>(key: K, value: CapConfigForm[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function saveConfig() {
    if (!cfgType || !editingCapId) return;
    setErr(null);
    setMsg("");
    setBusy(true);
    const config = formToConfig(cfgType, form);
    try {
      await apiPut(`/v1/aip/capabilities/${encodeURIComponent(editingCapId)}`, {
        enabled: true,
        config,
        name: CAPABILITY_CARDS.find((c) => c.id === editingCapId)?.title || editingCapId,
        description: CFG_TYPE_META.find((t) => t.id === cfgType)?.desc,
      });
      saveLocalConfig(editingCapId, form);
      setMsg(formatSaveMsg(false, editingCapId));
      await reloadCaps();
    } catch (e) {
      saveLocalConfig(editingCapId, form);
      setListSource("demo");
      setMsg(formatSaveMsg(true, editingCapId, String((e as Error).message || e)));
    } finally {
      setBusy(false);
    }
  }

  async function runConnectivity(capId: string, endpoint: string) {
    setErr(null);
    setMsg("");
    setBusy(true);
    try {
      const r = await apiPost<{
        ok?: boolean;
        status?: string;
        latencyMs?: number;
        message?: string;
      }>("/v1/aip/capabilities/test", { id: capId, endpoint });
      const ok = r.ok !== false && r.status !== "unhealthy";
      setMsg(formatTestMsg(false, ok, r.latencyMs));
    } catch (e) {
      setListSource("demo");
      setMsg(
        formatTestMsg(true, false) +
          `（真实连通接口失败：${String((e as Error).message || e)}；未用本地模拟结果冒充成功）`,
      );
    } finally {
      setBusy(false);
    }
  }

  async function runJob() {
    setErr(null);
    setMsg("");
    try {
      await apiPost("/v1/aip/capabilities", { id: "video-job", kind: "job" });
      const job = await apiPost<{
        jobId: string;
        artifact?: { mediaRid?: string; rid?: string };
      }>("/v1/aip/capabilities/video-job/invoke", {
        kind: "job",
        input: { clip: "demo" },
      });
      const rid = job.artifact?.mediaRid || job.artifact?.rid || null;
      setMediaRid(rid);
      setMsg(`Job ${job.jobId} 完成`);
      await reloadCaps();
    } catch (e) {
      setErr(String((e as Error).message || e));
    }
  }

  async function openSession() {
    setErr(null);
    try {
      const r = await apiPost<{ sessionId?: string; status?: string }>(
        "/v1/aip/capabilities/session/open",
        { avatar: "commerce", objectType: "AvatarSession" },
      );
      setSessionId(r.sessionId || null);
      setMsg(`Session ${r.sessionId} · ${r.status}`);
    } catch (e) {
      setErr(String((e as Error).message || e));
    }
  }

  const demo = listSource === "demo";

  return (
    <PageChrome
      title="智能体插件"
      lede="大脑 vs 肌肉 · C0 同步轻能力可进 Function；C1 Job / C2 Session 外置 Adapter"
    >
      <div className={`w4-b5-banner ${demo ? "is-demo" : "is-live"}`}>
        <span className={`w4-b5-badge ${demo ? "is-demo" : "is-live"}`}>{pathLabel(demo)}</span>
        <span className="w4-b5-banner-text">
          {demo
            ? "列表或写接口不可用时保留静态卡与本地配置；保存/测连通可降级。"
            : "列表来自 GET /v1/aip/capabilities；配置 PUT、连通 POST /test。"}
        </span>
      </div>

      {/* 顶部操作 */}
      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <button type="button" className="btn" onClick={() => void runJob()}>
          登记并提交 Job
        </button>
        <button type="button" className="btn" onClick={() => void openSession()}>
          打开 C2 Session
        </button>
        <button type="button" className="btn" onClick={() => void reloadCaps()}>
          刷新
        </button>
      </div>

      {msg && (
        <div className="w4-b5-msg is-ok">{msg}</div>
      )}
      {err && (
        <div className="w4-b5-msg is-err">{err}</div>
      )}
      {mediaRid && (
        <div style={{ fontSize: 13, marginBottom: 16 }}>
          产物 MediaSet：<code style={{ background: "var(--aos-gray-100)", padding: "2px 6px", borderRadius: 4 }}>{mediaRid}</code>{" "}
          · <Link to="/data/media-sets" style={{ color: "var(--aos-indigo-600)" }}>媒体集 →</Link>
        </div>
      )}
      {sessionId && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginBottom: 16 }}>
          <div style={{ border: "1px solid var(--aos-border)", borderRadius: 2, padding: 12, background: "var(--aos-surface)" }}>
            <div style={{ fontSize: 11, color: "#6B7280" }}>Session ID</div>
            <div style={{ fontSize: 14, fontWeight: 500, color: "#16A34A", marginTop: 4 }}>{sessionId}</div>
          </div>
          <div style={{ border: "1px solid var(--aos-border)", borderRadius: 2, padding: 12, background: "var(--aos-surface)" }}>
            <div style={{ fontSize: 11, color: "#6B7280" }}>AV 外置</div>
            <div style={{ fontSize: 14, fontWeight: 500, color: "#16A34A", marginTop: 4 }}>是</div>
          </div>
          <div style={{ border: "1px solid var(--aos-border)", borderRadius: 2, padding: 12, background: "var(--aos-surface)" }}>
            <div style={{ fontSize: 11, color: "#6B7280" }}>Draft 门控</div>
            <div style={{ fontSize: 14, fontWeight: 500, color: "#D97706", marginTop: 4 }}>默认</div>
          </div>
        </div>
      )}

      {/* 大脑 vs 肌肉 说明卡 */}
      <div
        style={{
          background: "#FEF9C3",
          border: "1px solid #FDE68A",
          borderRadius: 2,
          padding: 16,
          marginBottom: 24,
          fontSize: 12,
          color: "#374151",
          display: "flex",
          flexDirection: "column",
          gap: 4,
        }}
      >
        <div style={{ fontSize: 14, fontWeight: 600, color: "#92400E" }}>大脑 vs 肌肉</div>
        <p style={{ margin: 0, lineHeight: 1.6 }}>
          C0 同步轻能力可进 Function；C1 Job / C2 Session（短视频、可交互数字人）外置 Adapter，超 FUNC-03（60s/2GB）禁止塞进沙箱。
        </p>
      </div>

      {/* 已接入 */}
      <section style={{ marginBottom: 24 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <h2 style={{ fontSize: 14, fontWeight: 500, color: "#111827", margin: 0 }}>已接入</h2>
          <span style={{ fontSize: 10, color: "#6B7280" }}>kind · 健康 · 配额</span>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 12 }}>
          {CAPABILITY_CARDS.map((cap) => {
            const statusMeta = STATUS_META[cap.status];
            const isRegistered = registered.has(cap.id);
            const label = isRegistered ? "已登记" : statusMeta.label;
            const cardCfgType = cfgTypeFromCard(cap);
            return (
              <div
                key={cap.id}
                style={{
                  border: `1px solid ${statusMeta.border}`,
                  borderRadius: 2,
                  background: "#fff",
                  padding: 16,
                  display: "flex",
                  flexDirection: "column",
                  gap: 12,
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 500, color: "#111827" }}>{cap.title}</div>
                    <div style={{ fontSize: 12, color: "#6B7280", marginTop: 4 }}>{cap.kindLabel}</div>
                  </div>
                  <span
                    style={{
                      fontSize: 10,
                      padding: "2px 8px",
                      borderRadius: 4,
                      border: `1px solid ${statusMeta.border}`,
                      color: statusMeta.color,
                      whiteSpace: "nowrap",
                    }}
                  >
                    {label}
                  </span>
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                  <button
                    type="button"
                    className="w4-b5-chip-btn"
                    onClick={() => openConfig(cardCfgType, cap.id)}
                  >
                    配置
                  </button>
                  <button
                    type="button"
                    className="w4-b5-chip-btn"
                    disabled={busy}
                    onClick={() => {
                      const ep =
                        resolveEndpoint(cardCfgType, mergeLiveItem(defaultConfigFor(cardCfgType), itemsById.get(cap.id)));
                      void runConnectivity(cap.id, ep);
                    }}
                  >
                    {cap.kindLabel.includes("Job") ? "测连通" : cap.kindLabel.includes("Session") ? "测连通" : "测连通"}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* 接入新能力 */}
      <section style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 14, fontWeight: 500, color: "#111827", marginBottom: 4 }}>接入新能力</h2>
        <p style={{ fontSize: 12, color: "#6B7280", margin: "0 0 12px" }}>两种接入路径，选择后进入向导</p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 12 }}>
          <Link
            to="/aip/capability-import"
            style={{
              display: "block",
              border: "2px solid #BFDBFE",
              background: "#EFF6FF",
              borderRadius: 2,
              padding: 16,
              textDecoration: "none",
              transition: "all 0.15s",
            }}
          >
            <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
              <div
                style={{
                  width: 40,
                  height: 40,
                  borderRadius: 2,
                  background: "#DBEAFE",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                }}
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#2563EB" strokeWidth="1.5">
                  <path d="M12 5v14M5 12h14" strokeLinecap="round" />
                </svg>
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 14, fontWeight: 500, color: "#111827" }}>插件引入（Capability Manifest）</div>
                <div style={{ fontSize: 11, color: "#6B7280", marginTop: 4 }}>通过 YAML 声明接入外部 C0/C1/C2 能力，4 步向导</div>
              </div>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#9CA3AF" strokeWidth="2" style={{ marginTop: 4 }}>
                <path d="M9 5l7 7-7 7" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
          </Link>
          <Link
            to="/aip/agent-import"
            style={{
              display: "block",
              border: "2px solid #FDE68A",
              background: "#FFFBEB",
              borderRadius: 2,
              padding: 16,
              textDecoration: "none",
              transition: "all 0.15s",
            }}
          >
            <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
              <div
                style={{
                  width: 40,
                  height: 40,
                  borderRadius: 2,
                  background: "#FEF3C7",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                }}
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#D97706" strokeWidth="1.5">
                  <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 14, fontWeight: 500, color: "#111827" }}>外部 Agent 导入（Adapter 桥接）</div>
                <div style={{ fontSize: 11, color: "#6B7280", marginTop: 4 }}>从 awesome-llm-apps 等开源社区导入，5 步向导</div>
              </div>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#9CA3AF" strokeWidth="2" style={{ marginTop: 4 }}>
                <path d="M9 5l7 7-7 7" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
          </Link>
        </div>
      </section>

      {/* 可接入类型 */}
      <section style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 14, fontWeight: 500, color: "#111827", marginBottom: 12 }}>可接入类型</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 12 }}>
          {CFG_TYPE_META.map((t) => {
            const active = cfgType === t.id && editingCapId === t.defaultCapId;
            return (
              <button
                key={t.id}
                type="button"
                onClick={() => openConfig(t.id, t.defaultCapId)}
                style={{
                  textAlign: "left",
                  borderRadius: 2,
                  border: active ? "1px dashed #F59E0B" : "1px dashed #D1D5DB",
                  background: active ? "#FFFBEB" : "#F9FAFB",
                  padding: 16,
                  cursor: "pointer",
                  transition: "all 0.15s",
                }}
              >
                <div style={{ fontSize: 14, fontWeight: 500, color: "#111827" }}>{t.title}</div>
                <div style={{ fontSize: 11, color: "#6B7280", marginTop: 4 }}>{t.desc}</div>
              </button>
            );
          })}
        </div>
      </section>

      {/* 配置面板（按 cfgType 切换 4 种表单） */}
      {cfgType && editingCapId && (
        <section className="w4-b5-cfg-panel">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
            <h2 style={{ fontSize: 14, fontWeight: 500, color: "#111827", margin: 0 }}>
              配置 · {CFG_TYPE_META.find((t) => t.id === cfgType)?.title} · <code>{editingCapId}</code>
            </h2>
            <span style={{ fontSize: 10, color: "#6B7280" }}>Manifest · Vault ref · 回调验签</span>
          </div>

          {cfgType === "job" && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, fontSize: 12 }}>
              <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <span style={{ color: "#6B7280" }}>Adapter 端点</span>
                <input style={inputStyle} value={form.endpoint} onChange={(e) => patchForm("endpoint", e.target.value)} />
              </label>
              <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <span style={{ color: "#6B7280" }}>并发配额</span>
                <input style={inputStyle} value={form.concurrency} onChange={(e) => patchForm("concurrency", e.target.value)} />
              </label>
              <label style={{ display: "flex", flexDirection: "column", gap: 4, gridColumn: "span 2" }}>
                <span style={{ color: "#6B7280" }}>密钥 secret ref</span>
                <input style={inputStyle} value={form.secretRef} onChange={(e) => patchForm("secretRef", e.target.value)} />
              </label>
              <label style={{ display: "flex", flexDirection: "column", gap: 4, gridColumn: "span 2" }}>
                <span style={{ color: "#6B7280" }}>回调 Webhook（验签）</span>
                <input style={inputStyle} value={form.webhook} onChange={(e) => patchForm("webhook", e.target.value)} />
              </label>
              <p style={{ gridColumn: "span 2", color: "#6B7280", fontSize: 11, margin: 0 }}>
                产物写入 MediaSet；MediaJob Object 仅存状态与 RID。Logic 挂 Call Capability → Action 盖章。
              </p>
            </div>
          )}

          {cfgType === "script" && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, fontSize: 12 }}>
              <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <span style={{ color: "#6B7280" }}>模式</span>
                <select style={inputStyle} value={form.mode} onChange={(e) => patchForm("mode", e.target.value)}>
                  <option value="sync">sync（C0）</option>
                  <option value="job">job（C1）</option>
                </select>
              </label>
              <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <span style={{ color: "#6B7280" }}>超时提示 (s)</span>
                <input style={inputStyle} value={form.timeoutSec} onChange={(e) => patchForm("timeoutSec", e.target.value)} />
              </label>
              <label style={{ display: "flex", flexDirection: "column", gap: 4, gridColumn: "span 2" }}>
                <span style={{ color: "#6B7280" }}>输出 Object Type</span>
                <input style={inputStyle} value={form.outputObjectType} onChange={(e) => patchForm("outputObjectType", e.target.value)} />
              </label>
            </div>
          )}

          {cfgType === "session" && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, fontSize: 12 }}>
              <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <span style={{ color: "#6B7280" }}>Session Gateway</span>
                <input style={inputStyle} value={form.gateway} onChange={(e) => patchForm("gateway", e.target.value)} />
              </label>
              <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <span style={{ color: "#6B7280" }}>会话 Object</span>
                <input style={inputStyle} value={form.sessionObject} onChange={(e) => patchForm("sessionObject", e.target.value)} />
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: 8, color: "#374151", marginTop: 12 }}>
                <input type="checkbox" checked={form.avExternal} onChange={(e) => patchForm("avExternal", e.target.checked)} /> AV 流外置（平台不进沙箱）
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: 8, color: "#374151", marginTop: 12 }}>
                <input type="checkbox" checked={form.draftGate} onChange={(e) => patchForm("draftGate", e.target.checked)} /> 开播须 Draft / Action
              </label>
              <p style={{ gridColumn: "span 2", color: "#6B7280", fontSize: 11, margin: 0 }}>
                Agent 只推话术与 Wiki；实时音视频在数字人引擎。对齐 07b 旅程 P3。
              </p>
            </div>
          )}

          {cfgType === "http" && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, fontSize: 12 }}>
              <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <span style={{ color: "#6B7280" }}>kind</span>
                <select style={inputStyle} value={form.httpKind} onChange={(e) => patchForm("httpKind", e.target.value)}>
                  <option value="job">job</option>
                  <option value="session">session</option>
                  <option value="sync">sync</option>
                </select>
              </label>
              <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <span style={{ color: "#6B7280" }}>Base URL</span>
                <input style={inputStyle} value={form.baseUrl} onChange={(e) => patchForm("baseUrl", e.target.value)} />
              </label>
              <label style={{ display: "flex", flexDirection: "column", gap: 4, gridColumn: "span 2" }}>
                <span style={{ color: "#6B7280" }}>Manifest JSON / 包路径</span>
                <input style={inputStyle} value={form.manifest} onChange={(e) => patchForm("manifest", e.target.value)} />
              </label>
            </div>
          )}

          <div className="w4-b5-cfg-actions">
            <button
              type="button"
              className="w4-b5-btn w4-b5-btn-test"
              disabled={busy}
              onClick={() => void runConnectivity(editingCapId, resolveEndpoint(cfgType, form))}
            >
              {busy ? "处理中…" : "测连通 / 健康"}
            </button>
            <button
              type="button"
              className="w4-b5-btn w4-b5-btn-save"
              disabled={busy}
              onClick={() => void saveConfig()}
            >
              {busy ? "处理中…" : "保存并启用"}
            </button>
            <Link to="/aip/tools" className="w4-b5-btn w4-b5-btn-link">
              去工具面板挂载 →
            </Link>
          </div>
        </section>
      )}

      {/* API 登记 */}
      {items.length > 0 && (
        <section style={{ marginBottom: 16 }}>
          <h2 style={{ fontSize: 14, fontWeight: 500, color: "#111827", marginBottom: 8 }}>API 登记 ({items.length})</h2>
          <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 8 }}>
            {items.map((c) => (
              <li
                key={c.id}
                style={{
                  border: "1px solid #E5E7EB",
                  borderRadius: 2,
                  padding: 12,
                  background: "#fff",
                  fontSize: 13,
                }}
              >
                <strong>{c.name || c.id}</strong> · {c.kind || (c.config?.kind as string) || c.category || "sync"}{" "}
                <span style={{ color: "#9CA3AF" }}>
                  {c.endpoint || (c.config?.endpoint as string) || ""}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* 底部链接 */}
      <div
        style={{
          display: "flex",
          gap: 16,
          padding: "12px 0",
          borderTop: "1px solid #F3F4F6",
          fontSize: 12,
        }}
      >
        <Link to="/aip/tools" style={{ color: "var(--aos-indigo-600)" }}>工具面板 →</Link>
        <Link to="/data/media-sets" style={{ color: "var(--aos-indigo-600)" }}>MediaSet →</Link>
        <Link to="/aip/drafts" style={{ color: "var(--aos-indigo-600)" }}>Draft 审批 →</Link>
      </div>

      <p style={{ fontSize: 11, color: "#6B7280", margin: "12px 0 0" }}>
        蓝图口径：07b · CAP-01～07 · T07 §5.3。登记 ≠ Marketplace；GPU 服务优先客户前置（23/24）。
      </p>
    </PageChrome>
  );
}

const inputStyle = {
  width: "100%",
  background: "#F0F2F5",
  border: "1px solid #E5E7EB",
  borderRadius: 4,
  padding: "6px 8px",
  fontSize: 12,
  color: "#111827",
  outline: "none" as const,
};
