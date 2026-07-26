import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiGet, apiPost } from "../api/client";
import { PageChrome } from "../components/PageChrome";

type CapItem = { id: string; kind?: string; endpoint?: string };

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
  ready: { label: "就绪", border: "#86EFAC", color: "#16A34A" },
  session: { label: "会话中", border: "#93C5FD", color: "#2563EB" },
  stopped: { label: "停用", border: "#E5E7EB", color: "#6B7280" },
};

type CfgType = "job" | "script" | "session" | "http";

const CFG_TYPE_META: { id: CfgType; title: string; desc: string }[] = [
  { id: "job", title: "Media Job", desc: "C1 · submit / status / artifact" },
  { id: "script", title: "Script Engine", desc: "C0 sync · 或短 Job" },
  { id: "session", title: "Avatar Session", desc: "C2 · open / push / close" },
  { id: "http", title: "HTTP Adapter", desc: "自定义重包契约" },
];

export function CapabilityPage() {
  const [items, setItems] = useState<CapItem[]>([]);
  const [mediaRid, setMediaRid] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState("");
  const [cfgType, setCfgType] = useState<CfgType | null>(null);

  async function reloadCaps() {
    try {
      const r = await apiGet<{ items: CapItem[] }>("/v1/aip/capabilities");
      setItems(r.items || []);
    } catch (e) {
      setErr(String((e as Error).message || e));
    }
  }

  useEffect(() => {
    void reloadCaps();
  }, []);

  const registered = useMemo(() => new Set(items.map((c) => c.id)), [items]);

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

  return (
    <PageChrome
      title="智能体插件"
      lede="大脑 vs 肌肉 · C0 同步轻能力可进 Function；C1 Job / C2 Session 外置 Adapter"
    >
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
        <div style={{ background: "#EFF6FF", border: "1px solid #BFDBFE", borderRadius: 8, padding: 12, marginBottom: 16, fontSize: 13, color: "#1E40AF" }}>
          {msg}
        </div>
      )}
      {err && (
        <div style={{ background: "#FEF2F2", border: "1px solid #FECACA", borderRadius: 8, padding: 12, marginBottom: 16, fontSize: 13, color: "#991B1B" }}>
          {err}
        </div>
      )}
      {mediaRid && (
        <div style={{ fontSize: 13, marginBottom: 16 }}>
          产物 MediaSet：<code style={{ background: "#F3F4F6", padding: "2px 6px", borderRadius: 4 }}>{mediaRid}</code>{" "}
          · <Link to="/data/media-sets" style={{ color: "#4F46E5" }}>媒体集 →</Link>
        </div>
      )}
      {sessionId && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginBottom: 16 }}>
          <div style={{ border: "1px solid #E5E7EB", borderRadius: 8, padding: 12, background: "#fff" }}>
            <div style={{ fontSize: 11, color: "#6B7280" }}>Session ID</div>
            <div style={{ fontSize: 14, fontWeight: 500, color: "#16A34A", marginTop: 4 }}>{sessionId}</div>
          </div>
          <div style={{ border: "1px solid #E5E7EB", borderRadius: 8, padding: 12, background: "#fff" }}>
            <div style={{ fontSize: 11, color: "#6B7280" }}>AV 外置</div>
            <div style={{ fontSize: 14, fontWeight: 500, color: "#16A34A", marginTop: 4 }}>是</div>
          </div>
          <div style={{ border: "1px solid #E5E7EB", borderRadius: 8, padding: 12, background: "#fff" }}>
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
          borderRadius: 12,
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
            return (
              <div
                key={cap.id}
                style={{
                  border: `1px solid ${statusMeta.border}`,
                  borderRadius: 12,
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
                    onClick={() => setCfgType(cap.kindLabel.includes("Job") ? "job" : cap.kindLabel.includes("Session") ? "session" : "script")}
                    style={{
                      padding: "4px 10px",
                      borderRadius: 6,
                      border: "1px solid #E5E7EB",
                      background: "#fff",
                      fontSize: 12,
                      color: "#374151",
                      cursor: "pointer",
                    }}
                  >
                    配置
                  </button>
                  <button
                    type="button"
                    style={{
                      padding: "4px 10px",
                      borderRadius: 6,
                      border: "1px solid #E5E7EB",
                      background: "#fff",
                      fontSize: 12,
                      color: "#6B7280",
                      cursor: "pointer",
                    }}
                  >
                    {cap.kindLabel.includes("Job") ? "查看 Job" : cap.kindLabel.includes("Session") ? "场次 Object" : "测连通"}
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
              borderRadius: 12,
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
                  borderRadius: 8,
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
              borderRadius: 12,
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
                  borderRadius: 8,
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
            const active = cfgType === t.id;
            return (
              <button
                key={t.id}
                type="button"
                onClick={() => setCfgType(t.id)}
                style={{
                  textAlign: "left",
                  borderRadius: 12,
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
      {cfgType && (
        <section
          style={{
            border: "1px solid #E5E7EB",
            borderRadius: 12,
            background: "#fff",
            padding: 20,
            marginBottom: 24,
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
            <h2 style={{ fontSize: 14, fontWeight: 500, color: "#111827", margin: 0 }}>
              配置 · {CFG_TYPE_META.find((t) => t.id === cfgType)?.title}
            </h2>
            <span style={{ fontSize: 10, color: "#6B7280" }}>Manifest · Vault ref · 回调验签</span>
          </div>

          {cfgType === "job" && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, fontSize: 12 }}>
              <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <span style={{ color: "#6B7280" }}>Adapter 端点</span>
                <input style={inputStyle} defaultValue="https://cap.internal/video/v1" />
              </label>
              <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <span style={{ color: "#6B7280" }}>并发配额</span>
                <input style={inputStyle} defaultValue="4" />
              </label>
              <label style={{ display: "flex", flexDirection: "column", gap: 4, gridColumn: "span 2" }}>
                <span style={{ color: "#6B7280" }}>密钥 secret ref</span>
                <input style={inputStyle} defaultValue="vault://aip/capabilities/short-video#token" />
              </label>
              <label style={{ display: "flex", flexDirection: "column", gap: 4, gridColumn: "span 2" }}>
                <span style={{ color: "#6B7280" }}>回调 Webhook（验签）</span>
                <input style={inputStyle} defaultValue="https://aos-api/v1/aip/capabilities/cb/video" />
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
                <select style={inputStyle}>
                  <option>sync（C0）</option>
                  <option>job（C1）</option>
                </select>
              </label>
              <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <span style={{ color: "#6B7280" }}>超时提示 (s)</span>
                <input style={inputStyle} defaultValue="15" />
              </label>
              <label style={{ display: "flex", flexDirection: "column", gap: 4, gridColumn: "span 2" }}>
                <span style={{ color: "#6B7280" }}>输出 Object Type</span>
                <input style={inputStyle} defaultValue="LiveScript" />
              </label>
            </div>
          )}

          {cfgType === "session" && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, fontSize: 12 }}>
              <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <span style={{ color: "#6B7280" }}>Session Gateway</span>
                <input style={inputStyle} defaultValue="wss://avatar.internal/session" />
              </label>
              <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <span style={{ color: "#6B7280" }}>会话 Object</span>
                <input style={inputStyle} defaultValue="AvatarSession" />
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: 8, color: "#374151", marginTop: 12 }}>
                <input type="checkbox" defaultChecked /> AV 流外置（平台不进沙箱）
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: 8, color: "#374151", marginTop: 12 }}>
                <input type="checkbox" defaultChecked /> 开播须 Draft / Action
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
                <select style={inputStyle}>
                  <option>job</option>
                  <option>session</option>
                  <option>sync</option>
                </select>
              </label>
              <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <span style={{ color: "#6B7280" }}>Base URL</span>
                <input style={inputStyle} defaultValue="https://pkg.example/api" />
              </label>
              <label style={{ display: "flex", flexDirection: "column", gap: 4, gridColumn: "span 2" }}>
                <span style={{ color: "#6B7280" }}>Manifest JSON / 包路径</span>
                <input style={inputStyle} defaultValue="capability://org/custom-pkg@1.0" />
              </label>
            </div>
          )}

          <div style={{ display: "flex", gap: 8, paddingTop: 12, marginTop: 16, borderTop: "1px solid #F3F4F6" }}>
            <button
              type="button"
              style={{
                padding: "6px 12px",
                borderRadius: 6,
                border: "1px solid #86EFAC",
                background: "#fff",
                fontSize: 12,
                color: "#16A34A",
                cursor: "pointer",
              }}
            >
              测连通 / 健康
            </button>
            <button
              type="button"
              style={{
                padding: "6px 12px",
                borderRadius: 6,
                border: "1px solid #FDE68A",
                background: "#FEF3C7",
                fontSize: 12,
                color: "#92400E",
                cursor: "pointer",
              }}
            >
              保存并启用
            </button>
            <Link
              to="/aip/tools"
              style={{
                padding: "6px 12px",
                borderRadius: 6,
                border: "1px solid #E5E7EB",
                background: "#fff",
                fontSize: 12,
                color: "#6B7280",
                textDecoration: "none",
              }}
            >
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
                  borderRadius: 8,
                  padding: 12,
                  background: "#fff",
                  fontSize: 13,
                }}
              >
                <strong>{c.id}</strong> · {c.kind || "sync"}{" "}
                <span style={{ color: "#9CA3AF" }}>{c.endpoint || ""}</span>
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
        <Link to="/aip/tools" style={{ color: "#4F46E5" }}>工具面板 →</Link>
        <Link to="/data/media-sets" style={{ color: "#4F46E5" }}>MediaSet →</Link>
        <Link to="/aip/drafts" style={{ color: "#4F46E5" }}>Draft 审批 →</Link>
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
