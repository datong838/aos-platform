import { useState } from "react";
import { Link } from "react-router-dom";
import { PageChrome } from "../components/PageChrome";
import { BpBanner, BpPropGrid, BpToolbar } from "./s2/blueprintUi";

const API_BASE = import.meta.env.VITE_AOS_API_BASE ?? "http://127.0.0.1:8080";

const CHANNELS = [
  { id: "rc", label: "开发 (rc)" },
  { id: "beta", label: "试点 (beta)" },
  { id: "stable", label: "全量 (stable)" },
  { id: "hotfix", label: "紧急 hotfix", tone: "bad" as const },
];

/** 90 · 对齐 workshop-publish · 居中卡片 + 2×2 通道链接格 */
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
      Authorization: "Bearer dev",
      "X-Org-Id": "dev-org",
      "X-Project-Id": "dev-project",
      "Content-Type": "application/json",
      "Idempotency-Key": key,
    };
    try {
      const created = await fetch(`${API_BASE}/v1/modules`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          name: `运营台 Module · ${channel}`,
          entryPath: "/workshop/inbox",
          objectType: "WorkOrder",
        }),
      });
      const body1 = await created.json();
      const mid = body1.id as string;
      const once = await fetch(`${API_BASE}/v1/modules/${mid}/publish`, {
        method: "POST",
        headers,
        body: "{}",
      });
      const pub1 = await once.json();
      const twice = await fetch(`${API_BASE}/v1/modules/${mid}/publish`, {
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
      lede="90 · 发布 · 运营台 Module · Apollo Lite Adapter"
    >
      <div className="bp-publish-shell">
        <div className="bp-publish-card">
          <div className="bp-ws-section-title">发布 · 运营台 Module</div>
          <p className="muted" style={{ fontSize: "0.875rem" }}>
            工作台只提供入口；舰队 / Channel / Asset Bundle 在 Apollo 完成。
          </p>

          <div className="bp-ws-section-title" style={{ marginTop: "1rem" }}>
            目标通道
          </div>
          <ul style={{ listStyle: "none", padding: 0, margin: "0.5rem 0" }}>
            {CHANNELS.map((c) => (
              <li key={c.id} style={{ marginBottom: 6 }}>
                <label className="aos-text" style={{ fontSize: "0.875rem" }}>
                  <input
                    type="radio"
                    name="channel"
                    checked={channel === c.id}
                    onChange={() => setChannel(c.id)}
                  />{" "}
                  <span className={c.tone === "bad" ? "bp-prop-warn" : ""}>{c.label}</span>
                </label>
              </li>
            ))}
          </ul>

          <BpToolbar>
            <button type="button" className="btn" disabled={busy} onClick={() => void onPublish()}>
              {busy ? "提交中…" : "发布 Module"}
            </button>
          </BpToolbar>

          <div className="bp-publish-links">
            <Link to="/workshop/inbox" className="bp-publish-link bp-publish-link-emerald">
              预览运营台 →
            </Link>
            <Link to="/workshop/canvas" className="bp-publish-link bp-publish-link-sky">
              返回画布 →
            </Link>
            <Link to="/workshop/module-interface" className="bp-publish-link">
              模块接口
            </Link>
            <span className="bp-publish-link muted" style={{ cursor: "default", opacity: 0.65 }}>
              Apollo Release（规划中）
            </span>
          </div>

          <BpBanner tone="info">
            Module 发布走 API 幂等 · Apollo 舰队 / Channel / 资产包能力规划中
          </BpBanner>

          {lastPub && (
            <div style={{ marginTop: "0.75rem" }}>
              <BpPropGrid
                items={[
                  { label: "Module ID", value: lastPub.id || "—" },
                  { label: "通道", value: channel },
                  { label: "状态", value: lastPub.status || "—", tone: "ok" },
                  { label: "幂等", value: lastPub.idempotent ? "是" : "否" },
                ]}
              />
            </div>
          )}

          {msg && <p className="aos-text" style={{ marginTop: "0.75rem" }}>{msg}</p>}
        </div>
      </div>
    </PageChrome>
  );
}
