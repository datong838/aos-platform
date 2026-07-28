import { useState } from "react";
import { Link } from "react-router-dom";
import { PageChrome } from "../components/PageChrome";
import { tenantAuthHeaders } from "../api/tenant";
import { getApiBase } from "../api/apiBase";

const CHANNELS = [
  { id: "rc", label: "开发 (rc)" },
  { id: "beta", label: "试点 (beta)" },
  { id: "stable", label: "全量 (stable)" },
  { id: "hotfix", label: "紧急 hotfix", tone: "bad" as const },
];

export function PublishPage() {
  const [channel, setChannel] = useState("beta");
  const [msg, setMsg] = useState("");
  const [lastPub, setLastPub] = useState<{ id?: string; status?: string; idempotent?: boolean } | null>(
    null,
  );
  const [busy, setBusy] = useState(false);

  async function onPublish() {
    if (busy) return;
    setBusy(true);
    const key = `publish-${Date.now()}`;
    const headers = {
      ...tenantAuthHeaders(),
      "Idempotency-Key": key,
    };
    try {
      const created = await fetch(`${getApiBase()}/v1/modules`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          name: `风险告警 Module · ${channel}`,
          entryPath: "/workshop/inbox",
          objectType: "WorkOrder",
        }),
      });
      const body1 = await created.json();
      const mid = body1.id as string;
      const once = await fetch(`${getApiBase()}/v1/modules/${mid}/publish`, {
        method: "POST",
        headers,
        body: "{}",
      });
      const pub1 = await once.json();
      const twice = await fetch(`${getApiBase()}/v1/modules/${mid}/publish`, {
        method: "POST",
        headers,
        body: "{}",
      });
      const pub2 = await twice.json();
      setLastPub({
        id: mid,
        status: pub1.publish?.status || "ACCEPTED",
        idempotent: Boolean(pub2.idempotentReplay),
      });
      setMsg(
        pub2.idempotentReplay
          ? `发布幂等成功 · id=${mid} · ${pub1.publish?.status || "ACCEPTED"}`
          : `已发布 id=${mid} · 通道 ${channel}`,
      );
    } catch (e) {
      setMsg(String((e as Error).message || e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <PageChrome
      title="发布入口"
      lede="订单管理 · 发布入口"
    >
      <div style={{ maxWidth: 480, margin: "0 auto" }}>
        <div style={{
          background: "#fff",
          borderRadius: 2,
          border: "1px solid rgba(255,255,255,0.1)",
          padding: 24,
        }}>
          <div style={{ fontSize: 16, fontWeight: 500, color: "#111827", marginBottom: 4 }}>
            发布 · 风险告警管理 Module
          </div>
          <p style={{ fontSize: 12, color: "#6B7280", margin: "0 0 16px 0", lineHeight: 1.5 }}>
            工作台只提供入口；舰队 / Channel / Asset Bundle 在 Apollo 完成。
          </p>

          <div style={{ fontSize: 13, marginBottom: 8 }}>
            <div style={{ fontSize: 12, color: "#6B7280", marginBottom: 8 }}>目标通道</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {CHANNELS.map((c) => (
                <label key={c.id} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14, cursor: "pointer" }}>
                  <input
                    type="radio"
                    name="channel"
                    checked={channel === c.id}
                    onChange={() => setChannel(c.id)}
                  />
                  <span style={{ color: c.tone === "bad" ? "#DC2626" : "#111827" }}>{c.label}</span>
                </label>
              ))}
            </div>
          </div>

          <div style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 8,
            paddingTop: 8,
            marginBottom: 16,
          }}>
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
              to="/apollo/assets"
              style={{
                padding: "10px 12px",
                borderRadius: 2,
                background: "#EFF6FF",
                border: "1px solid #93C5FD",
                fontSize: 12,
                color: "#1D4ED8",
                textAlign: "center",
                textDecoration: "none",
              }}
            >
              FDE 资产包 →
            </Link>
            <Link
              to="/apollo/hub"
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
              Hub 舰队
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
            {busy ? "提交中…" : "发布 Module"}
          </button>

          <p style={{
            fontSize: 10,
            color: "#059669",
            border: "1px solid #A7F3D0",
            borderRadius: 2,
            padding: "10px 12px",
            background: "#ECFDF5",
            margin: 0,
            lineHeight: 1.5,
          }}>
            Spoke 出站轮询拉 Plan · Lite Spoke 同契约 · 见 Apollo 交付组
          </p>

          {lastPub && (
            <div style={{ marginTop: 16, padding: 12, borderRadius: 2, background: "var(--aos-surface-hover)", border: "1px solid var(--aos-border)" }}>
              <div style={{ fontSize: 12, fontWeight: 500, color: "#111827", marginBottom: 8 }}>上次发布结果</div>
              <div style={{ fontSize: 11, color: "#6B7280", lineHeight: 1.8 }}>
                <div>Module ID: <span style={{ fontFamily: "monospace", color: "#374151" }}>{lastPub.id || "—"}</span></div>
                <div>通道: <span style={{ color: "#374151" }}>{channel}</span></div>
                <div>状态: <span style={{ color: "#059669", fontWeight: 500 }}>{lastPub.status || "—"}</span></div>
                <div>幂等: <span style={{ color: lastPub.idempotent ? "#059669" : "#D97706" }}>{lastPub.idempotent ? "是（重放成功）" : "否"}</span></div>
              </div>
            </div>
          )}

          {msg && (
            <p style={{ fontSize: 12, color: "#374151", marginTop: 12, marginBottom: 0 }}>{msg}</p>
          )}
        </div>
      </div>
    </PageChrome>
  );
}
